"""
Scraper La Centrale — Autocentre C054723
=========================================
Stratégie hybride :
  1. Playwright NON-HEADLESS → page 1 (passe DataDome) + récupère les cookies de session
  2. curl-cffi + BeautifulSoup → pages 2-20 avec les cookies du navigateur
     (évite d'ouvrir une fenêtre Chrome pour chaque page)
  3. Si curl-cffi échoue → retry Playwright (fallback)

Automatisation Mac : launchd via ~/autocentre/mac_run.sh (toutes les 2h)
Lancer manuellement : python3 scraper.py
"""

import json, os, re, sys, time, base64, random
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
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token and token.startswith("ghp_"):
        return token
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
        sha = push_file_to_github(
            token, headers, DATA_FILE, GITHUB_PATH,
            f"🚗 Véhicules mis à jour — {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        print(f"  [GitHub] ✓ vehicules.json → commit {sha}")

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
                pass
        if pushed_photos:
            print(f"  [GitHub] ✓ {pushed_photos} photo(s) poussée(s)")
        return True
    except Exception as e:
        print(f"  [GitHub] Erreur push : {e}")
        return False

# ─── Extraction JS (Playwright, injecté dans la page) ─────────────────────────

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

            const img = card.querySelector('img');
            let photo = img ? (img.getAttribute('src') || '') : '';
            photo = photo.replace(/size=\d+x\d+/, 'size=640x480');

            const titreEl = card.querySelector('[class*="vehiclecardV2_title"]');
            const titre = titreEl ? titreEl.textContent.trim() : '';

            const subEl = card.querySelector('[class*="vehiclecardV2_subTitle"]');
            const version = subEl ? subEl.textContent.trim() : '';

            const prixEl = card.querySelector('[class*="vehiclecardV2_vehiclePrice__"]');
            const prix = prixEl ? prixEl.textContent.trim() : '';

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

# ─── Extraction HTML (BeautifulSoup, pour curl-cffi) ──────────────────────────

def extraire_via_html(html):
    """Extrait les véhicules depuis HTML brut (server-rendered)."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    soup = BeautifulSoup(html, "html.parser")
    vus = set()
    res = []

    # Chercher toutes les cartes véhicules
    for a in soup.find_all("a", attrs={"data-testid": "vehicleCardV2"}):
        try:
            href = a.get("href", "")
            if not href or href in vus:
                continue
            vus.add(href)

            id_m = re.search(r"/annonce/(\d+)", href)
            vid = id_m.group(1) if id_m else href[-12:]
            url = "https://pros.lacentrale.fr" + href

            # Chercher la carte parente
            card = a
            for _ in range(5):  # remonter jusqu'à 5 niveaux
                card = card.parent
                if card and card.get("class") and any("searchCard" in c for c in card.get("class", [])):
                    break

            # Photo
            img = card.find("img") if card else None
            photo = img.get("src", "") if img else ""
            photo = re.sub(r"size=\d+x\d+", "size=640x480", photo)

            # Titre
            titre_el = card.find(class_=re.compile(r"vehiclecardV2_title")) if card else None
            titre = titre_el.get_text(strip=True) if titre_el else ""

            # Version
            sub_el = card.find(class_=re.compile(r"vehiclecardV2_subTitle")) if card else None
            version = sub_el.get_text(strip=True) if sub_el else ""

            # Prix
            prix_el = card.find(class_=re.compile(r"vehiclecardV2_vehiclePrice")) if card else None
            prix = prix_el.get_text(strip=True) if prix_el else ""

            # Détails
            texts = []
            if card:
                for el in card.find_all(class_=re.compile(r"Text_Text_body-medium")):
                    t = el.get_text(strip=True)
                    if t and len(t) > 1:
                        texts.append(t)

            annee = next((t for t in texts if re.match(r"^(19|20)\d{2}$", t)), "")
            km    = next((t for t in texts if re.search(r"\d[\d\s]*\s*km", t, re.I)), "")
            carb  = next((t for t in texts if re.search(r"diesel|essence|hybride|electrique|électrique|gpl", t, re.I)), "")
            boite = next((t for t in texts if re.match(r"^auto$|^automatique$|^manuelle?$|^mec$", t.strip(), re.I)), "")

            if not titre and not prix:
                continue
            res.append({"id": vid, "titre": titre, "version": version, "url": url,
                        "photo": photo, "prix": prix, "km": km, "annee": annee,
                        "carburant": carb, "boite": boite})
        except Exception:
            pass
    return res

# ─── Scraper principal ─────────────────────────────────────────────────────────

def scraper():
    data_initiale = charger()
    ids_existants = {v["id"]: v for v in data_initiale.get("vehicules", []) if v.get("id")}

    print(f"\n{'='*55}")
    print(f" Scraper La Centrale — {DEALER_ID}")
    print(f" {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'='*55}")

    vehicules_en_ligne = []
    session_cookies = []   # cookies récupérés depuis Playwright
    max_page = 1

    # ── Phase 1 : Playwright — page 1 + cookies DataDome ──────────────────────
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=os.environ.get("CI", "false").lower() == "true",
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

        # Intercepter photos
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
                body = response.body()
                if len(body) > 5000:
                    with open(local_path, "wb") as f:
                        f.write(body)
                    photos_intercepted[ref_id] = local_path
            except Exception:
                pass
        page.on("response", handle_response)

        try:
            print(f"\n[Phase 1] Chargement de {PAGE_PRO} …")
            page.goto(PAGE_PRO, wait_until="domcontentloaded", timeout=60000)

            # Attendre DataDome (max 45s)
            passed = False
            for i in range(45):
                try:
                    title = page.title()
                except Exception as e:
                    print(f"  Erreur titre ({i}s) : {e}")
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

            # Cookies
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

            # Scroll humain page 1
            for pct in [15, 30, 45, 60, 75, 90, 100, 70]:
                page.evaluate(f"window.scrollTo({{top: document.body.scrollHeight * {pct/100}, behavior: 'smooth'}})")
                page.wait_for_timeout(random.randint(300, 600))

            # Extraire page 1
            v = page.evaluate(EXTRACT_JS)
            vehicules_en_ligne.extend(v)
            print(f"  Page  1 : {len(v):3d} annonces | total : {len(vehicules_en_ligne)}")

            # Récupérer les cookies de session (pour curl-cffi)
            session_cookies = ctx.cookies()

            # Détecter le nombre de pages
            page.evaluate("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'})")
            page.wait_for_timeout(800)
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
                        if n >= 2:
                            page_nums.add(n)
            except Exception:
                pass
            max_page = max(page_nums) if page_nums else 1
            print(f"  Pages détectées : {sorted(page_nums)} → {max_page} pages au total")

            # ── Phase 2b : Playwright pages 2+ (même session navigateur) ─────────
            if max_page >= 2:
                print(f"\n[Phase 2b] Playwright pages 2 à {max_page} (même navigateur)…")
                vides_consec = 0
                for pnum in range(2, max_page + 1):
                    try:
                        page.goto(PAGE_PAG.format(pnum), wait_until="domcontentloaded", timeout=35000)
                        page.wait_for_timeout(random.randint(1200, 2500))
                        # Scroll progressif pour déclencher le lazy-loading de toutes les photos
                        for pct in [20, 40, 60, 80, 100]:
                            page.evaluate(f"window.scrollTo({{top: document.body.scrollHeight * {pct/100}, behavior: 'smooth'}})")
                            page.wait_for_timeout(random.randint(400, 700))
                        page.wait_for_timeout(random.randint(600, 1000))
                        v = page.evaluate(EXTRACT_JS)
                        vehicules_en_ligne.extend(v)
                        print(f"  Page {pnum:2d} : {len(v):3d} annonces | total : {len(vehicules_en_ligne)}")
                        if len(v) == 0:
                            vides_consec += 1
                            if vides_consec >= 2:
                                print(f"  Fin des annonces à la page {pnum - 1}")
                                break
                        else:
                            vides_consec = 0
                        time.sleep(random.uniform(2.5, 5.0))
                    except Exception as e:
                        print(f"  Page {pnum:2d} : erreur Playwright — {e}")
                        break

        except PWTimeout:
            print("  Timeout chargement initial")
        except Exception as e:
            print(f"  Erreur : {e}")
            import traceback; traceback.print_exc()
        finally:
            browser.close()

    # ── Garde-fou : arrêt si résultat insuffisant ─────────────────────────────
    nb_existants = len(data_initiale.get("vehicules", []))
    if not vehicules_en_ligne:
        print(f"\n⚠️  Page 1 vide (DataDome probable) — {nb_existants} véhicule(s) conservés, aucun changement.")
        return 0
    # Si on récupère moins de 50 % du stock connu → scrape partiel
    # On sauvegarde quand même les photos capturées, mais on ne touche pas à la liste
    seuil = max(10, int(nb_existants * 0.5))
    if nb_existants > 0 and len(vehicules_en_ligne) < seuil:
        print(f"\n⚠️  Scrape incomplet : {len(vehicules_en_ligne)} véhicule(s) récupéré(s) sur {nb_existants} connus.")
        print(f"   Seuil minimum : {seuil} — liste véhicules NON écrasée.")
        # Injecte les nouvelles photos dans le fichier existant sans modifier la liste
        nb_photos_ajoutees = 0
        for v_existing in data_initiale.get("vehicules", []):
            vid = v_existing.get("id", "")
            if not vid or v_existing.get("photo_local"):
                continue
            local_photo = os.path.join(PHOTOS_DIR, f"{vid}.jpg")
            if os.path.exists(local_photo) and os.path.getsize(local_photo) > 5000:
                v_existing["photo_local"] = f"photos/{vid}.jpg"
                nb_photos_ajoutees += 1
        if nb_photos_ajoutees:
            print(f"   {nb_photos_ajoutees} photo(s) ajoutée(s) aux véhicules existants.")
            sauvegarder(data_initiale)
            token = get_github_token()
            push_to_github(token)
        else:
            print("   Aucune nouvelle photo — aucun changement.")
        return 0

    # ── Phase 2 : curl-cffi — pages 2 à max_page ──────────────────────────────
    if max_page >= 2 and session_cookies:
        print(f"\n[Phase 2] curl-cffi pour pages 2 à {max_page} (cookies navigateur)…")

        try:
            import curl_cffi.requests as crequests
            from bs4 import BeautifulSoup

            cr_session = crequests.Session(impersonate="chrome124")

            # Injecter les cookies du navigateur
            for c in session_cookies:
                domain = c.get("domain", "")
                if "lacentrale" in domain or domain == "":
                    cr_session.cookies.set(
                        c["name"], c["value"],
                        domain=domain.lstrip(".") if domain else "pros.lacentrale.fr"
                    )

            request_headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": PAGE_PRO,
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }

            curl_blocked = 0
            for pnum in range(2, max_page + 1):
                try:
                    url_pag = PAGE_PAG.format(pnum)
                    # Mettre à jour le Referer à chaque page
                    if pnum > 2:
                        request_headers["Referer"] = PAGE_PAG.format(pnum - 1)

                    resp = cr_session.get(url_pag, headers=request_headers, timeout=30)

                    if resp.status_code != 200:
                        curl_blocked += 1
                        print(f"  Page {pnum:2d} : HTTP {resp.status_code} — DataDome (curl)")
                        if curl_blocked >= 3:
                            print("  curl-cffi bloqué — arrêt")
                            break
                        time.sleep(random.uniform(15, 25))
                        continue

                    # Vérifier si la page est la vraie page (pas une page DataDome)
                    html = resp.text
                    if "datadome" in html[:2000].lower() and "searchCard" not in html:
                        curl_blocked += 1
                        print(f"  Page {pnum:2d} : DataDome détecté dans HTML (curl)")
                        if curl_blocked >= 3:
                            break
                        time.sleep(random.uniform(15, 25))
                        continue

                    curl_blocked = 0  # succès → reset
                    v = extraire_via_html(html)
                    vehicules_en_ligne.extend(v)
                    print(f"  Page {pnum:2d} : {len(v):3d} annonces | total : {len(vehicules_en_ligne)}")

                    if len(v) == 0:
                        # Page vide — peut-être fin ou rendu client uniquement
                        print(f"  Page {pnum:2d} : 0 résultats (HTML peut-être vide, rendu JS ?)")
                        # On continue quand même au cas où c'est une page "trou"
                        if pnum >= 3:  # après 2 pages vides consécutives → arrêt
                            break

                    # Pause humaine
                    time.sleep(random.uniform(3.0, 6.0))

                except Exception as e:
                    print(f"  Page {pnum:2d} : erreur curl-cffi — {e}")
                    break

        except ImportError:
            print("  curl-cffi non installé — pages 2+ ignorées")
        except Exception as e:
            print(f"  [Phase 2] Erreur : {e}")

    # ── Dédoublonnage ──────────────────────────────────────────────────────────
    vus = {}
    for v in vehicules_en_ligne:
        if v.get("id") and v["id"] not in vus:
            # Préserver photo_local si elle existait
            old_v = ids_existants.get(v["id"], {})
            v["prix"] = nettoyer_prix(v.get("prix", ""))
            v["km"]   = nettoyer_km(v.get("km", ""))
            if old_v.get("photo_local"):
                v["photo_local"] = old_v["photo_local"]
            vus[v["id"]] = v

    vehicules_en_ligne = list(vus.values())

    # ── Photos interceptées ────────────────────────────────────────────────────
    print("\nAssociation des photos…")
    photos_associees = 0
    for v in vehicules_en_ligne:
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
                photos_associees += 1
    if photos_associees:
        print(f"  {photos_associees} nouvelle(s) photo(s) associée(s)")

    # ── Diff ───────────────────────────────────────────────────────────────────
    nouveaux = [v for v in vehicules_en_ligne if v["id"] not in ids_existants]
    retires  = [v for v in data_initiale.get("vehicules", [])
                if v.get("id") and v["id"] not in vus]

    for v in nouveaux[:20]:
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

    # ── Push GitHub ───────────────────────────────────────────────────────────
    if nouveaux or retires or prix_changes or total != len(ids_existants):
        print("Synchronisation GitHub…")
        token = get_github_token()
        push_to_github(token)
    else:
        print("Aucun changement — GitHub déjà à jour.")

    return len(nouveaux)


if __name__ == "__main__":
    scraper()
    sys.exit(0)
