"""
Scraper La Centrale — Autocentre C054723
=========================================
Conçu pour tourner sur le Mac en tâche de fond (launchd).
Utilise Playwright en mode NON-HEADLESS pour contourner DataDome.

Fonctionnement :
  1. Ouvre Chrome (fenêtre visible brièvement)
  2. Parcourt toutes les pages de pros.lacentrale.fr/C054723
  3. Extrait jusqu'à 200 véhicules (titre, prix, km, année, photo, URL)
  4. Enregistre vehicules.json localement
  5. Si changement détecté → push automatique sur GitHub

Lancer manuellement : python3 scraper.py
Automatisation Mac  : launchd (voir com.autocentre.scraper.plist)
"""

import json, os, re, sys, time, base64, subprocess, random
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ─── Configuration ─────────────────────────────────────────────────────────────
DEALER_ID   = "C054723"
PAGE_PRO    = f"https://pros.lacentrale.fr/{DEALER_ID}"
PAGE_PAG    = f"https://pros.lacentrale.fr/{DEALER_ID}/index?freetext_conversationid=&options=&page={{}}&vertical=car"
DATA_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vehicules.json")
PHOTOS_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "photos")
GITHUB_REPO = "autocentresas/autocentre-site"
GITHUB_PATH = "vehicules.json"

os.makedirs(PHOTOS_DIR, exist_ok=True)

# ─── Utilitaires ───────────────────────────────────────────────────────────────

def charger():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"derniere_maj": None, "vehicules": []}

def sauvegarder(data):
    data["derniere_maj"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    with open(DATA_FILE, "w", encoding="utf-8") as f:
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

def get_github_token():
    """
    Récupère le token GitHub.
    Ordre de priorité :
      1. Variable d'environnement GITHUB_TOKEN (définie par mac_run.sh via keychain)
      2. Fichier ~/.autocentre_token (fallback manuel)
    """
    # 1) Variable d'environnement (définie par le shell script)
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token and token.startswith("ghp_"):
        return token

    # 2) Fichier local
    token_file = os.path.expanduser("~/.autocentre_token")
    if os.path.exists(token_file):
        try:
            with open(token_file) as f:
                token = f.read().strip()
            if token.startswith("ghp_"):
                return token
        except Exception:
            pass

    return ""

def push_file_to_github(token, headers, local_path, remote_path, message):
    """Pousse un fichier unique vers GitHub via l'API."""
    import urllib.request
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{remote_path}"
    req = urllib.request.Request(api_url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            sha = json.loads(resp.read()).get("sha", "")
    except Exception:
        sha = ""
    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    payload = json.dumps({"message": message, "content": content, "sha": sha}).encode()
    req2 = urllib.request.Request(api_url, data=payload, headers=headers, method="PUT")
    with urllib.request.urlopen(req2) as resp:
        return json.loads(resp.read()).get("commit", {}).get("sha", "")[:10]

def push_to_github(token):
    """Pousse vehicules.json + photos nouvelles vers GitHub via l'API."""
    if not token:
        print("  [GitHub] Token non disponible — skip push")
        return False
    try:
        import urllib.request
        headers = {
            "Authorization": f"token {token}",
            "Content-Type": "application/json",
            "User-Agent": "autocentre-scraper/1.0"
        }
        # 1) Pousser vehicules.json
        sha = push_file_to_github(
            token, headers, DATA_FILE, GITHUB_PATH,
            f"🚗 Véhicules mis à jour — {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        print(f"  [GitHub] ✓ vehicules.json → commit {sha}")

        # 2) Pousser les nouvelles photos (celles présentes localement)
        pushed_photos = 0
        for fname in os.listdir(PHOTOS_DIR):
            if not fname.endswith(".jpg"):
                continue
            local_photo = os.path.join(PHOTOS_DIR, fname)
            remote_photo = f"photos/{fname}"
            try:
                push_file_to_github(
                    token, headers, local_photo, remote_photo,
                    f"📸 Photo {fname}"
                )
                pushed_photos += 1
            except Exception as e:
                print(f"  [GitHub] Photo {fname} : {e}")
        if pushed_photos:
            print(f"  [GitHub] ✓ {pushed_photos} photo(s) poussée(s)")
        return True
    except Exception as e:
        print(f"  [GitHub] Erreur push : {e}")
        return False

# ─── Extraction JS (injecté dans la page Playwright) ──────────────────────────

EXTRACT_JS = r"""
() => {
    const cards = Array.from(document.querySelectorAll('div.searchCard'));
    const vus = new Set();
    const res = [];
    cards.forEach(card => {
        try {
            const a = card.querySelector('a[data-testid="vehicleCardV2"]');
            if (!a) return;
            const href = a.getAttribute('href');
            if (!href || vus.has(href)) return;
            vus.add(href);

            const idM = href.match(/\/annonce\/(\d+)/);
            const id = idM ? idM[1] : href.slice(-12);
            const url = 'https://pros.lacentrale.fr' + href;

            // Photo principale (première img)
            const img = card.querySelector('img');
            let photo = img ? (img.getAttribute('src') || '') : '';
            // Augmenter la résolution
            photo = photo.replace(/size=\d+x\d+/, 'size=640x480');

            // Titre
            const titreEl = card.querySelector('[class*="vehiclecardV2_title"]');
            const titre = titreEl ? titreEl.textContent.trim() : '';

            // Version/sous-titre
            const subEl = card.querySelector('[class*="vehiclecardV2_subTitle"]');
            const version = subEl ? subEl.textContent.trim() : '';

            // Prix
            const prixEl = card.querySelector('[class*="vehiclecardV2_vehiclePrice__"]');
            const prix = prixEl ? prixEl.textContent.trim() : '';

            // Détails (year, km, fuel, gearbox) via classe Text_Text_body-medium
            const texts = Array.from(card.querySelectorAll('[class*="Text_Text_body-medium"]'))
                .map(el => el.textContent.trim()).filter(t => t && t.length > 1);

            const annee  = texts.find(t => /^(19|20)\d{2}$/.test(t)) || '';
            const km     = texts.find(t => /\d[\d\s]*\s*km/i.test(t)) || '';
            const carb   = texts.find(t => /diesel|essence|hybride|electrique|électrique|gpl/i.test(t)) || '';
            const boite  = texts.find(t => /^auto$|^automatique$|^manuelle?$|^mec$/i.test(t.trim().toLowerCase())) || '';

            if (!titre && !prix) return;
            res.push({id, titre, version, url, photo, prix, km, annee, carburant: carb, boite});
        } catch(e) {}
    });
    return res;
}
"""

# ─── Scraper principal ─────────────────────────────────────────────────────────

def scraper():
    data_initiale = charger()
    ids_existants = {v["id"]: v for v in data_initiale.get("vehicules", []) if v.get("id")}

    print(f"\n{'='*55}")
    print(f" Scraper La Centrale — {DEALER_ID}")
    print(f" {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'='*55}")

    vehicules_en_ligne = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,   # Non-headless OBLIGATOIRE pour passer DataDome
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
            viewport={"width": 1440, "height": 900},
            extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"},
        )
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver',  { get: () => undefined });
            Object.defineProperty(navigator, 'plugins',    { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages',  { get: () => ['fr-FR','fr','en-US'] });
            Object.defineProperty(navigator, 'platform',   { get: () => 'MacIntel' });
            window.chrome = { runtime: {} };
        """)

        page = ctx.new_page()

        # ── Intercepter les images La Centrale pour les sauvegarder localement ──
        photos_intercepted = {}  # ref_id → chemin local

        def handle_response(response):
            """Capture les images des véhicules au vol pendant le chargement de page."""
            try:
                url = response.url
                if "pictures.lacentrale.fr" not in url:
                    return
                if response.status != 200:
                    return
                m = re.search(r'W(\d+)_STANDARD_0', url)
                if not m:
                    return
                ref_id = m.group(1)
                # ID complet = commençant par "871034" + ref_id
                full_id = "871034" + ref_id  # sera mis à jour avec le vrai ID
                local_path = os.path.join(PHOTOS_DIR, f"ref_{ref_id}.jpg")
                if os.path.exists(local_path) and os.path.getsize(local_path) > 5000:
                    photos_intercepted[ref_id] = local_path
                    return
                try:
                    body = response.body()
                    if len(body) > 5000:
                        with open(local_path, "wb") as f:
                            f.write(body)
                        photos_intercepted[ref_id] = local_path
                except Exception:
                    pass
            except Exception:
                pass

        page.on("response", handle_response)

        try:
            print(f"\nChargement de {PAGE_PRO} …")
            page.goto(PAGE_PRO, wait_until="domcontentloaded", timeout=60000)

            # Attendre que DataDome laisse passer (max 45s)
            passed = False
            for i in range(45):
                try:
                    title = page.title()
                except Exception as e:
                    print(f"  Erreur lecture titre ({i}s) : {e}")
                    break
                if title and title not in ("lacentrale.fr", "pros.lacentrale.fr", ""):
                    print(f"  Page chargée ({i}s) : {title[:60]}")
                    passed = True
                    break
                if i % 10 == 0 and i > 0:
                    print(f"  … attente {i}s — titre : '{title}'")
                time.sleep(1)

            if not passed:
                print("  DataDome non résolu — scraping annulé (données inchangées)")
                browser.close()
                return 0

            # Bannière cookies
            for txt in ["Tout accepter", "Accepter tout", "Accepter", "J'accepte"]:
                try:
                    btn = page.locator(f'button:has-text("{txt}")').first
                    if btn.is_visible(timeout=1500):
                        btn.click()
                        page.wait_for_timeout(700)
                        break
                except Exception:
                    pass

            page.wait_for_timeout(2000)

            # ── Page 1 : scroll humain avant d'extraire ──────────────────────
            # Simuler la lecture : scroll progressif
            for scroll_pct in [25, 50, 75, 100, 50]:
                page.evaluate(f"window.scrollTo({{top: document.body.scrollHeight * {scroll_pct/100}, behavior: 'smooth'}})")
                page.wait_for_timeout(random.randint(300, 600))

            v = page.evaluate(EXTRACT_JS)
            vehicules_en_ligne.extend(v)
            print(f"  Page  1 : {len(v):3d} annonces | total : {len(vehicules_en_ligne)}")

            # Remonter en haut pour voir la pagination
            page.evaluate("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'})")
            page.wait_for_timeout(800)

            # Découvrir le nombre de pages depuis la pagination
            page_nums = set()
            try:
                hrefs = page.eval_on_selector_all(
                    'a[href*="page="]',
                    'els => els.map(a => a.getAttribute("href"))'
                )
                for h in hrefs:
                    m = re.search(r'page=(\d+)', h or "")
                    if m:
                        n = int(m.group(1))
                        if n >= 2:  # ignorer page=0 ou page=1
                            page_nums.add(n)
            except Exception:
                pass
            max_page = max(page_nums) if page_nums else 1
            print(f"  Pages détectées : {sorted(page_nums)} → scraping jusqu'à page {max_page}")

            # ── Pages 2 à max_page ──────────────────────────────────────────
            pnum = 2
            datadome_consec = 0   # compteur d'échecs consécutifs DataDome
            stop = False

            while pnum <= max_page and not stop:
                try:
                    clicked = False

                    # Stratégie 1 : cliquer sur le lien de pagination (plus humain)
                    try:
                        link = page.locator(f'a[href*="page={pnum}"]').first
                        if link.is_visible(timeout=2000):
                            link.scroll_into_view_if_needed()
                            page.wait_for_timeout(random.randint(400, 800))
                            box = link.bounding_box()
                            if box:
                                page.mouse.move(
                                    box["x"] + box["width"] / 2 + random.randint(-5, 5),
                                    box["y"] + box["height"] / 2 + random.randint(-3, 3)
                                )
                                page.wait_for_timeout(random.randint(200, 400))
                            link.click()
                            page.wait_for_load_state("domcontentloaded", timeout=30000)
                            page.wait_for_timeout(random.randint(1800, 2800))
                            clicked = True
                    except Exception:
                        pass

                    # Stratégie 2 : navigation directe (fallback)
                    if not clicked:
                        url_pag = PAGE_PAG.format(pnum)
                        page.goto(url_pag, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(random.randint(2000, 3000))

                    try:
                        title = page.title()
                    except Exception:
                        # Browser fermé par DataDome → arrêt propre
                        print(f"  Page {pnum:2d} : navigateur fermé par DataDome — arrêt")
                        stop = True
                        break

                    if title.lower() in ("lacentrale.fr", "pros.lacentrale.fr", "") or "datadome" in title.lower():
                        datadome_consec += 1
                        print(f"  Page {pnum:2d} : DataDome! (titre: '{title}') — échec {datadome_consec}/3")
                        if datadome_consec >= 3:
                            print("  DataDome persistant — arrêt du scraping")
                            stop = True
                            break
                        # Retourner sur la page principale pour régénérer la session
                        print(f"  Retour page principale + attente 25s...")
                        time.sleep(25)
                        try:
                            page.goto(PAGE_PRO, wait_until="domcontentloaded", timeout=60000)
                            page.wait_for_timeout(random.randint(3000, 5000))
                            page.evaluate("window.scrollTo({top: document.body.scrollHeight * 0.5, behavior: 'smooth'})")
                            page.wait_for_timeout(1500)
                        except Exception:
                            # Browser fermé pendant le retry → arrêt propre
                            print(f"  Navigateur fermé pendant retry — arrêt")
                            stop = True
                            break
                        # Réessayer la même page (ne pas incrémenter pnum)
                        continue

                    datadome_consec = 0  # succès → réinitialiser le compteur

                    # Scroll humain sur la page
                    for scroll_pct in [30, 70, 100, 50]:
                        page.evaluate(f"window.scrollTo({{top: document.body.scrollHeight * {scroll_pct/100}, behavior: 'smooth'}})")
                        page.wait_for_timeout(random.randint(250, 500))

                    v = page.evaluate(EXTRACT_JS)
                    vehicules_en_ligne.extend(v)
                    print(f"  Page {pnum:2d} : {len(v):3d} annonces | total : {len(vehicules_en_ligne)}")

                    if len(v) == 0:
                        print(f"  Page {pnum:2d} vide — arrêt")
                        stop = True
                        break

                    # Scroll bas pour voir la pagination suivante
                    page.evaluate("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'})")
                    page.wait_for_timeout(random.randint(600, 1000))

                    # Pause aléatoire entre les pages (comportement humain)
                    pause = random.uniform(2.5, 4.0)
                    time.sleep(pause)
                    pnum += 1

                except PWTimeout:
                    print(f"  Page {pnum}: timeout — arrêt")
                    stop = True
                    break
                except Exception as e:
                    print(f"  Page {pnum}: erreur {e}")
                    stop = True
                    break

        except PWTimeout:
            print("  Timeout chargement initial")
        except Exception as e:
            print(f"  Erreur : {e}")
            import traceback; traceback.print_exc()
        finally:
            browser.close()

    # ── Garde-fou : ne jamais écraser si 0 véhicule récupéré ─────────────────
    if not vehicules_en_ligne:
        nb_existants = len(data_initiale.get("vehicules", []))
        print(f"\n⚠️  Aucun véhicule récupéré (DataDome probable).")
        print(f"   Conservation des {nb_existants} véhicule(s) existants — aucun changement.")
        return 0

    # ── Dédoublonnage ──────────────────────────────────────────────────────────
    vus = {}
    for v in vehicules_en_ligne:
        if v.get("id") and v["id"] not in vus:
            v["prix"] = nettoyer_prix(v.get("prix", ""))
            v["km"]   = nettoyer_km(v.get("km", ""))
            vus[v["id"]] = v

    vehicules_en_ligne = list(vus.values())

    # ── Téléchargement des photos manquantes ──────────────────────────────────
    # Les photos La Centrale ont hotlink protection → on les stocke sur GitHub
    print("\nTéléchargement des photos…")
    photos_dl = 0
    try:
        for v in vehicules_en_ligne:
            vid = v.get("id", "")
            if not vid:
                continue
            local_photo = os.path.join(PHOTOS_DIR, f"{vid}.jpg")

            # 1) Déjà téléchargée localement ?
            if os.path.exists(local_photo) and os.path.getsize(local_photo) > 5000:
                v["photo_local"] = f"photos/{vid}.jpg"
                continue

            # 2) Interceptée par Playwright ? (renommer ref_XXXXXX.jpg → ID.jpg)
            photo_url = v.get("photo", "")
            ref_m = re.search(r'W(\d+)_STANDARD_0', photo_url) if photo_url else None
            if ref_m:
                ref_id = ref_m.group(1)
                ref_path = os.path.join(PHOTOS_DIR, f"ref_{ref_id}.jpg")
                if ref_id in photos_intercepted and os.path.exists(ref_path):
                    os.rename(ref_path, local_photo)
                    v["photo_local"] = f"photos/{vid}.jpg"
                    photos_dl += 1
                    continue

    except Exception as e:
        print(f"  Erreur photos interceptées : {e}")
    print(f"  {photos_dl} photo(s) capturée(s) via navigateur")

    # ── Diff ───────────────────────────────────────────────────────────────────
    nouveaux = [v for v in vehicules_en_ligne if v["id"] not in ids_existants]
    retires  = [v for v in data_initiale.get("vehicules", [])
                if v.get("id") and v["id"] not in vus]

    for v in nouveaux[:20]:  # max 20 logs
        print(f"  + Nouveau : {v['titre']} | {v['prix']} | {v['km']} | {v['annee']}")
    for v in retires[:10]:
        print(f"  - Retiré  : {v['titre']}")

    prix_changes = []
    for v in vehicules_en_ligne:
        vid = v["id"]
        if vid in ids_existants and v["prix"] and ids_existants[vid].get("prix") != v["prix"]:
            prix_changes.append(f"{v['titre']} : {ids_existants[vid].get('prix')} → {v['prix']}")
    for c in prix_changes[:10]:
        print(f"  ~ Prix modifié : {c}")

    # ── Sauvegarde ─────────────────────────────────────────────────────────────
    data_initiale["vehicules"] = vehicules_en_ligne
    sauvegarder(data_initiale)

    total = len(vehicules_en_ligne)
    print(f"\n{'='*55}")
    print(f" ✅ {total} véhicule(s) | +{len(nouveaux)} nouveau(x) | -{len(retires)} retiré(s) | ~{len(prix_changes)} prix modifié(s)")
    print(f"{'='*55}\n")

    # ── Push GitHub si changement ───────────────────────────────────────────────
    if nouveaux or retires or prix_changes or not ids_existants:
        print("Synchronisation GitHub…")
        token = get_github_token()
        push_to_github(token)
    else:
        print("Aucun changement — GitHub déjà à jour.")

    return len(nouveaux)


if __name__ == "__main__":
    scraper()
    sys.exit(0)
