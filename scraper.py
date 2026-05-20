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

import json, os, re, sys, time, base64, subprocess
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ─── Configuration ─────────────────────────────────────────────────────────────
DEALER_ID   = "C054723"
PAGE_PRO    = f"https://pros.lacentrale.fr/{DEALER_ID}"
PAGE_PAG    = f"https://pros.lacentrale.fr/{DEALER_ID}/index?freetext_conversationid=&options=&page={{}}&vertical=car"
DATA_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vehicules.json")
GITHUB_REPO = "autocentresas/autocentre-site"
GITHUB_PATH = "vehicules.json"

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

def push_to_github(token):
    """Pousse vehicules.json vers GitHub via l'API."""
    if not token:
        print("  [GitHub] Token non disponible — skip push")
        return False
    try:
        import urllib.request
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"
        headers = {
            "Authorization": f"token {token}",
            "Content-Type": "application/json",
            "User-Agent": "autocentre-scraper/1.0"
        }
        # Récupérer le SHA actuel
        req = urllib.request.Request(api_url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                current = json.loads(resp.read())
                sha = current.get("sha", "")
        except Exception:
            sha = ""

        # Préparer le contenu
        with open(DATA_FILE, "rb") as f:
            content = base64.b64encode(f.read()).decode()

        payload = json.dumps({
            "message": f"🚗 Véhicules mis à jour — {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            "content": content,
            "sha": sha
        }).encode()

        req2 = urllib.request.Request(api_url, data=payload, headers=headers, method="PUT")
        with urllib.request.urlopen(req2) as resp:
            result = json.loads(resp.read())
            commit_sha = result.get("commit", {}).get("sha", "")[:10]
            print(f"  [GitHub] ✓ Commit {commit_sha}")
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

        try:
            print(f"\nChargement de {PAGE_PRO} …")
            page.goto(PAGE_PRO, wait_until="domcontentloaded", timeout=60000)

            # Attendre que DataDome laisse passer (max 45s)
            passed = False
            for i in range(45):
                title = page.title()
                if title and title not in ("lacentrale.fr", "pros.lacentrale.fr", ""):
                    print(f"  Page chargée ({i}s) : {title[:60]}")
                    passed = True
                    break
                if i % 10 == 0 and i > 0:
                    print(f"  … attente {i}s — titre : '{title}'")
                time.sleep(1)

            if not passed:
                print("  DataDome non résolu — scraping annulé")
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

            page.wait_for_timeout(1500)

            # ── Page 1 ───────────────────────────────────────────────────────
            v = page.evaluate(EXTRACT_JS)
            vehicules_en_ligne.extend(v)
            print(f"  Page  1 : {len(v):3d} annonces | total : {len(vehicules_en_ligne)}")

            # Découvrir le nombre de pages depuis la pagination
            page_nums = set()
            try:
                hrefs = page.eval_on_selector_all(
                    '.pagination__desktop a[href]',
                    'els => els.map(a => a.getAttribute("href"))'
                )
                for h in hrefs:
                    m = re.search(r'page=(\d+)', h or "")
                    if m: page_nums.add(int(m.group(1)))
            except Exception:
                pass
            max_page = max(page_nums) if page_nums else 1
            print(f"  Pages détectées : {sorted(page_nums)} → scraping jusqu'à page {max_page}")

            # ── Pages 2 à max_page ──────────────────────────────────────────
            for pnum in range(2, max_page + 1):
                try:
                    url_pag = PAGE_PAG.format(pnum)
                    page.goto(url_pag, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(1200)

                    title = page.title()
                    if title in ("lacentrale.fr", ""):
                        print(f"  Page {pnum:2d} : DataDome! Arrêt.")
                        break

                    v = page.evaluate(EXTRACT_JS)
                    vehicules_en_ligne.extend(v)
                    print(f"  Page {pnum:2d} : {len(v):3d} annonces | total : {len(vehicules_en_ligne)}")

                    if len(v) == 0:
                        break
                    time.sleep(1.5)  # pause polie (évite le rate-limiting DataDome)

                except PWTimeout:
                    print(f"  Page {pnum}: timeout — arrêt")
                    break
                except Exception as e:
                    print(f"  Page {pnum}: erreur {e}")
                    break

        except PWTimeout:
            print("  Timeout chargement initial")
        except Exception as e:
            print(f"  Erreur : {e}")
            import traceback; traceback.print_exc()
        finally:
            browser.close()

    # ── Dédoublonnage ──────────────────────────────────────────────────────────
    vus = {}
    for v in vehicules_en_ligne:
        if v.get("id") and v["id"] not in vus:
            v["prix"] = nettoyer_prix(v.get("prix", ""))
            v["km"]   = nettoyer_km(v.get("km", ""))
            vus[v["id"]] = v

    vehicules_en_ligne = list(vus.values())

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
