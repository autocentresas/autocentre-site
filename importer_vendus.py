"""
Importation des véhicules vendus (supprimés) depuis La Centrale
================================================================
Usage : python3 importer_vendus.py
"""

import json, os, re, time, random
from datetime import datetime
from playwright.sync_api import sync_playwright

DEALER_ID   = "C054723"
PAGE_PRO    = f"https://pilot.lacentrale.fr/{DEALER_ID}/annonces/archives"
VENDUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vehicules_vendus.json")
PHOTOS_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "photos")

os.makedirs(PHOTOS_DIR, exist_ok=True)

EXTRACT_JS = r"""
() => {
    const vus = new Set();
    const res = [];
    const links = Array.from(document.querySelectorAll('a[href*="/annonces/archives/W"]'));
    links.forEach(a => {
        const href = a.getAttribute('href') || '';
        if (!href || vus.has(href)) return;
        vus.add(href);
        const idM = href.match(/\/archives\/(W\d+)/);
        const id = idM ? idM[1] : '';
        if (!id) return;
        const url = 'https://pilot.lacentrale.fr' + href.split('?')[0];
        const card = a.closest('li') || a.closest('article') || a.parentElement || a;
        const img = card.querySelector('img');
        let photo = img ? (img.getAttribute('src') || '') : '';
        const allText = (card.innerText || card.textContent || '').replace(/\s+/g, ' ').trim();
        const lines = allText.split(/[·\n|]/).map(l => l.trim()).filter(Boolean);
        const titre = lines[0] || '';
        const annee = lines.find(t => /^(19|20)\d{2}$/.test(t.trim())) || '';
        const km    = lines.find(t => /\d[\d\s]*\s*km/i.test(t)) || '';
        const carb  = lines.find(t => /diesel|essence|hybride|electrique|électrique|gpl/i.test(t)) || '';
        const prix  = lines.find(t => /\d[\d\s]*\s*€/.test(t)) || '';
        res.push({id, titre, version:'', url, photo, prix, km, annee, carburant:carb, boite:''});
    });
    return res;
}
"""

def charger_vendus():
    if os.path.exists(VENDUS_FILE):
        try:
            with open(VENDUS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"vehicules": []}

def sauvegarder_vendus(data):
    data["derniere_maj"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    with open(VENDUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def nettoyer_prix(txt):
    if not txt: return ""
    txt = re.sub(r"\s+", " ", txt.strip())
    txt = re.sub(r"[^\d\s€.,]", "", txt).strip()
    if txt and "€" not in txt: txt += " €"
    return txt

def nettoyer_km(txt):
    if not txt: return ""
    m = re.search(r"([\d\s]+)\s*km", txt, re.IGNORECASE)
    return m.group(0).strip() if m else txt.strip()

def main():
    print("\n" + "="*60)
    print(" Importation des véhicules vendus — La Centrale")
    print("="*60)
    print(f"\n📂 Fichier destination : {VENDUS_FILE}")

    vendus_existants = charger_vendus()
    ids_deja_vendus = {v["id"] for v in vendus_existants.get("vehicules", [])}
    print(f"   Vendus déjà enregistrés : {len(ids_deja_vendus)}")

    print("\n🌐 Ouverture du navigateur sur la page des archives…")
    print("   → Connecte-toi à La Centrale si besoin")
    print("   → Attends que les voitures archivées apparaissent dans le navigateur")
    print("   → Reviens ici et appuie sur ENTRÉE\n")

    nouveaux_vendus = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
            viewport={"width": 1440, "height": 900},
        )
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        page = ctx.new_page()

        photos_intercepted = {}
        def handle_response(response):
            try:
                url = response.url
                if "pictures.lacentrale.fr" not in url or response.status != 200:
                    return
                m = re.search(r'W(\d+)_STANDARD_0', url)
                if not m:
                    return
                ref_id = m.group(1)
                local_path = os.path.join(PHOTOS_DIR, f"ref_{ref_id}.jpg")
                if os.path.exists(local_path) and os.path.getsize(local_path) > 5000:
                    photos_intercepted[ref_id] = local_path
                    return
                try:
                    body = response.body()
                except Exception:
                    return
                if len(body) > 5000:
                    with open(local_path, "wb") as f:
                        f.write(body)
                    photos_intercepted[ref_id] = local_path
            except Exception:
                pass
        page.on("response", handle_response)

        page.goto(PAGE_PRO, wait_until="domcontentloaded", timeout=60000)

        input("→ Appuie sur ENTRÉE quand les voitures sont visibles dans le navigateur... ")

        print("   Attente chargement JS (5s)…")
        page.wait_for_timeout(5000)

        current_url = page.url
        print(f"   URL actuelle : {current_url}")

        page_num = 1
        vides_consec = 0

        while True:
            print(f"\n   Page {page_num}…", end=" ", flush=True)

            try:
                for pct in [25, 50, 75, 100]:
                    page.evaluate(f"window.scrollTo({{top: document.body.scrollHeight * {pct/100}, behavior: 'smooth'}})")
                    page.wait_for_timeout(600)
                page.wait_for_timeout(1000)
            except Exception:
                pass

            vehicules = page.evaluate(EXTRACT_JS)
            nb = len(vehicules)
            print(f"{nb} véhicule(s) trouvé(s)")

            if nb == 0:
                vides_consec += 1
                if vides_consec >= 2:
                    print("   Fin des annonces.")
                    break
            else:
                vides_consec = 0
                for v in vehicules:
                    v["prix"] = nettoyer_prix(v.get("prix", ""))
                    v["km"]   = nettoyer_km(v.get("km", ""))
                    if v.get("id") and v["id"] not in ids_deja_vendus:
                        nouveaux_vendus.append(v)
                        ids_deja_vendus.add(v["id"])

            next_found = False
            try:
                next_url = None
                hrefs = page.eval_on_selector_all(
                    'a[href*="page="]',
                    'els => els.map(a => a.getAttribute("href"))'
                )
                for h in hrefs:
                    m = re.search(r'page=(\d+)', h or "")
                    if m and int(m.group(1)) == page_num + 1:
                        next_url = "https://pilot.lacentrale.fr" + h if h.startswith("/") else h
                        break

                if not next_url:
                    for sel in ['button:has-text("Suivant")', 'a:has-text("Suivant")', '[aria-label="Page suivante"]']:
                        try:
                            btn = page.locator(sel).first
                            if btn.is_visible(timeout=1000) and btn.is_enabled():
                                btn.click()
                                page.wait_for_timeout(3000)
                                next_found = True
                                break
                        except Exception:
                            pass

                if next_url and not next_found:
                    page.goto(next_url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(3000)
                    next_found = True

            except Exception as e:
                print(f"   Erreur navigation : {e}")

            if not next_found and nb > 0:
                print("   Pas de page suivante trouvée.")
                break

            page_num += 1
            if page_num > 50:
                break

            time.sleep(random.uniform(2, 3))

        browser.close()

    for v in nouveaux_vendus:
        vid = v.get("id", "")
        if not vid:
            continue
        local_photo = os.path.join(PHOTOS_DIR, f"{vid}.jpg")
        if os.path.exists(local_photo) and os.path.getsize(local_photo) > 5000:
            v["photo_local"] = f"photos/{vid}.jpg"
            continue
        photo_url = v.get("photo", "")
        ref_m = re.search(r'W(\d+)_STANDARD_0', photo_url) if photo_url else None
        if ref_m:
            ref_id = ref_m.group(1)
            ref_path = os.path.join(PHOTOS_DIR, f"ref_{ref_id}.jpg")
            if ref_id in photos_intercepted and os.path.exists(ref_path):
                os.rename(ref_path, local_photo)
                v["photo_local"] = f"photos/{vid}.jpg"

    if nouveaux_vendus:
        vendus_existants["vehicules"].extend(nouveaux_vendus)
        sauvegarder_vendus(vendus_existants)
        total_final = len(vendus_existants["vehicules"])
        print(f"\n{'='*60}")
        print(f" ✅ {len(nouveaux_vendus)} nouveau(x) véhicule(s) vendu(s) importé(s)")
        print(f"    Total vendus : {total_final}")
        print(f"    Fichier : {VENDUS_FILE}")
        print(f"{'='*60}")
        print("\n📤 Pour publier :")
        print("   git add vehicules_vendus.json photos/")
        print('   git commit -m "Import véhicules vendus"')
        print("   git push origin main\n")
    else:
        print("\n⚠️  Aucun nouveau véhicule vendu trouvé.")

if __name__ == "__main__":
    main()