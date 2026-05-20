"""
Scraper La Centrale — Autocentre C054723
URL cible : https://pros.lacentrale.fr/C054723
Récupère toutes les annonces (photo, titre, prix, km, année) et met à jour vehicules.json

Stratégies anti-DataDome :
  - playwright-stealth (masque les signatures d'automatisation)
  - Non-headless via Xvfb sur GitHub Actions (DISPLAY=:99)
  - Attente active jusqu'à résolution du challenge (max 45s)

Stratégies d'extraction (par ordre) :
  1. Interception des réponses API JSON (XHR/fetch)
  2. Extraction window.__NEXT_DATA__ / __NUXT__ / __INITIAL_STATE__
  3. Parsing DOM CSS (fallback)
"""

import json, os, sys, re, time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

try:
    from playwright_stealth import stealth_sync
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False
    print("  [AVERT] playwright-stealth non installé — mode stealth désactivé")

PAGE_PRO  = "https://pros.lacentrale.fr/C054723"
DATA_FILE = "vehicules.json"

# Si DISPLAY est défini (Xvfb lancé dans le workflow), on utilise le mode non-headless
HEADLESS = os.environ.get("DISPLAY") is None
print(f"  Mode : {'headless' if HEADLESS else 'non-headless (Xvfb)'}")

# ─── utilitaires ──────────────────────────────────────────────────────────────

def charger():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"derniere_maj": None, "vehicules": []}

def sauvegarder(data):
    data["derniere_maj"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def nettoyer_prix(txt):
    if not txt:
        return ""
    txt = re.sub(r"\s+", " ", txt.strip())
    txt = re.sub(r"[^\d\s€.,]", "", txt).strip()
    if txt and "€" not in txt:
        txt += " €"
    return txt

def nettoyer_km(txt):
    if not txt:
        return ""
    m = re.search(r"([\d\s]+)\s*km", txt, re.IGNORECASE)
    if m:
        return m.group(0).strip()
    return txt.strip()

# ─── extraction depuis réponses API interceptées ──────────────────────────────

def extraire_depuis_api(api_responses):
    """Tente de trouver des annonces dans les réponses JSON interceptées."""
    vehicules = []
    for entry in api_responses:
        url  = entry["url"]
        data = entry["data"]
        found = _chercher_annonces_dans_json(data, url)
        if found:
            print(f"  ✓ API ({len(found)} annonces) : {url[:90]}")
            vehicules.extend(found)
            if len(vehicules) > 5:
                break
    return vehicules

def _chercher_annonces_dans_json(obj, url="", depth=0):
    """Parcourt récursivement un objet JSON pour trouver des annonces."""
    if depth > 8:
        return []
    if isinstance(obj, list) and len(obj) >= 2:
        sample = obj[0] if obj else {}
        if isinstance(sample, dict):
            keys = set(sample.keys())
            if keys & {"makeLabel", "modelLabel", "price", "mileage", "id", "title",
                       "brandLabel", "fuelLabel", "gearboxLabel", "firstRegistrationYear",
                       "photos", "images", "picture", "thumbnail", "url", "link"}:
                return [_normaliser_annonce(item, url) for item in obj if isinstance(item, dict)]
    if isinstance(obj, dict):
        for key in ("ads", "vehicles", "vehicules", "listings", "results",
                    "items", "annonces", "data", "list", "searchResults",
                    "classifiedAds", "classified"):
            if key in obj and isinstance(obj[key], (list, dict)):
                found = _chercher_annonces_dans_json(obj[key], url, depth+1)
                if found:
                    return found
        for v in obj.values():
            if isinstance(v, (dict, list)):
                found = _chercher_annonces_dans_json(v, url, depth+1)
                if found:
                    return found
    return []

def _normaliser_annonce(item, source_url=""):
    """Normalise un objet JSON brut en format vehicule standard."""
    def g(*keys):
        for k in keys:
            if k in item and item[k]:
                return str(item[k])
        return ""

    vid = g("id", "classifiedId", "adId", "vehicleId")
    if not vid:
        raw_url = g("url", "link", "detailUrl", "seoUrl")
        m = re.search(r"(\d{7,})", raw_url)
        vid = m.group(1) if m else str(abs(hash(str(item))))[:10]

    make    = g("makeLabel", "brandLabel", "make", "brand", "marque")
    model   = g("modelLabel", "model", "modele")
    version = g("versionLabel", "version", "titre", "title", "label")
    if make and model:
        titre = f"{make} {model}"
        if version and version not in titre:
            titre += f" {version}"
    else:
        titre = version or g("titre", "title", "label", "name") or "Véhicule"

    raw_url = g("url", "link", "detailUrl", "seoUrl", "annonce_url")
    if raw_url and not raw_url.startswith("http"):
        raw_url = "https://www.lacentrale.fr" + raw_url

    photo = ""
    for k in ("photos", "images", "pictures"):
        if k in item:
            imgs = item[k]
            if isinstance(imgs, list) and imgs:
                first = imgs[0]
                photo = first if isinstance(first, str) else (first.get("url") or first.get("src") or "")
            break
    if not photo:
        photo = g("photo", "picture", "thumbnail", "image", "photoUrl")
    if photo and not photo.startswith("http"):
        photo = "https:" + photo if photo.startswith("//") else "https://www.lacentrale.fr" + photo

    prix_raw = item.get("price") or item.get("prix") or item.get("sellingPrice") or item.get("displayPrice") or ""
    if isinstance(prix_raw, (int, float)):
        prix = f"{int(prix_raw):,}".replace(",", " ") + " €"
    else:
        prix = nettoyer_prix(str(prix_raw)) if prix_raw else ""

    km_raw = item.get("mileage") or item.get("km") or item.get("kilometrage") or ""
    if isinstance(km_raw, (int, float)):
        km = f"{int(km_raw):,}".replace(",", " ") + " km"
    else:
        km = nettoyer_km(str(km_raw)) if km_raw else ""

    annee = g("firstRegistrationYear", "year", "annee", "yearOfRegistration", "registrationYear")
    if annee and len(annee) > 4:
        m2 = re.search(r"(19|20)\d{2}", annee)
        annee = m2.group(0) if m2 else annee[:4]

    carburant = g("fuelLabel", "fuel", "carburant", "energy")
    boite     = g("gearboxLabel", "gearbox", "transmission", "boite")

    return {"id": vid, "titre": titre, "url": raw_url, "photo": photo,
            "prix": prix, "km": km, "annee": annee, "carburant": carburant, "boite": boite}

# ─── extraction JS (DOM + état embarqué) ─────────────────────────────────────

JS_EXTRACT_EMBEDDED = r"""
() => {
    // Next.js
    if (window.__NEXT_DATA__) return { _source: '__NEXT_DATA__', data: window.__NEXT_DATA__ };
    // Nuxt
    if (window.__NUXT__)      return { _source: '__NUXT__',      data: window.__NUXT__ };
    // Autres stores
    for (const k of ['__INITIAL_STATE__','__APP_STATE__','__STATE__','__data__']) {
        try {
            const v = window[k];
            if (v && typeof v === 'object') return { _source: k, data: v };
        } catch(e) {}
    }
    // <script type="application/json">
    for (const s of document.querySelectorAll('script[type="application/json"]')) {
        try {
            const d = JSON.parse(s.textContent);
            if (d && typeof d === 'object') return { _source: 'script[json]', data: d };
        } catch(e) {}
    }
    return null;
}
"""

JS_EXTRACT_DOM = r"""
() => {
    const CARD_SELECTORS = [
        '[data-cy="vehicleCard"]',
        '[class*="vehicleCard"]',
        '[class*="VehicleCard"]',
        '[class*="vehicle-card"]',
        '[class*="classifiedCard"]',
        'a[href*="auto-occasion"]',
        'article[class*="listing"]',
        '[class*="searchCard"]',
        '[class*="annonce"]',
        '[data-testid*="card"]',
        '[data-testid*="vehicle"]',
    ];

    let cards = [];
    for (const sel of CARD_SELECTORS) {
        try {
            const found = Array.from(document.querySelectorAll(sel))
                .filter(el => el.textContent && el.textContent.length > 20);
            if (found.length > 1) { cards = found; break; }
        } catch(e) {}
    }

    if (cards.length === 0) {
        cards = Array.from(document.querySelectorAll('a'))
            .filter(a => (a.href.includes('auto-occasion') || a.href.includes('annonce'))
                      && a.querySelector('img'));
    }

    const vehicules = [];
    const vus = new Set();

    cards.forEach(card => {
        try {
            const linkEl = card.tagName === 'A' ? card
                         : card.querySelector('a[href*="auto-occasion"]')
                        || card.querySelector('a[href*="annonce"]')
                        || card.querySelector('a');
            const url = linkEl ? linkEl.href : '';
            if (!url || vus.has(url)) return;
            vus.add(url);

            const idMatch = url.match(/annonce[- _]?(\d{6,})/i) || url.match(/\/(\d{7,})/);
            const id = idMatch ? idMatch[1] : btoa(url).slice(0, 12);

            const img = card.querySelector('img');
            let photo = '';
            if (img) {
                photo = img.src || img.dataset.src || img.dataset.lazySrc
                     || img.getAttribute('data-original') || '';
                photo = photo.replace(/\/thumbnail\/|\/small\/|_small\.|_thumb\./, '/large/');
            }

            const titreEl = card.querySelector('h2,h3,h4,[class*="title"],[class*="Title"],[class*="name"],[class*="label"]');
            const titre = titreEl ? titreEl.textContent.trim() : '';

            const prixEl = card.querySelector('[class*="price"],[class*="Price"],[data-cy*="price"],[class*="prix"]');
            let prix = prixEl ? prixEl.textContent.trim() : '';
            if (!prix) {
                const all = Array.from(card.querySelectorAll('*'));
                const found = all.find(el =>
                    el.children.length === 0 && /\d[\d\s]{2,}[€]/.test(el.textContent)
                );
                prix = found ? found.textContent.trim() : '';
            }

            const allText = Array.from(card.querySelectorAll('span,li,p,div,[class*="detail"],[class*="info"]'))
                .map(el => el.textContent.trim()).filter(Boolean);
            const anneeMatch = allText.find(s => /^(19|20)\d{2}$/.test(s)) || '';
            const kmMatch    = allText.find(s => /\d[\d\s]*\s*km/i.test(s)) || '';
            const carburant  = allText.find(s => /diesel|essence|hybride|électrique|gpl/i.test(s)) || '';
            const boite      = allText.find(s => /automatique|manuelle|auto\b/i.test(s)) || '';

            if (!titre && !prix) return;
            vehicules.push({ id, titre, url, photo, prix, km: kmMatch, annee: anneeMatch, carburant, boite });
        } catch(e) {}
    });

    return vehicules;
}
"""

# ─── helpers ─────────────────────────────────────────────────────────────────

def accepter_cookies(page):
    for txt in ["Tout accepter", "Accepter tout", "Accepter et continuer",
                "Accepter", "J'accepte", "OK", "Continuer"]:
        try:
            btn = page.locator(f'button:has-text("{txt}")').first
            if btn.is_visible(timeout=1500):
                btn.click()
                page.wait_for_timeout(600)
                return
        except Exception:
            pass

def attendre_fin_challenge(page, timeout_s=45):
    """
    Attend que DataDome/Cloudflare laisse passer la requête.
    Le challenge a le titre 'lacentrale.fr' et une mini-animation CSS.
    Retourne True si le vrai contenu est chargé.
    """
    print(f"  Attente résolution challenge (max {timeout_s}s)…")
    for i in range(timeout_s):
        title = page.title()
        url   = page.url
        # Le challenge a le titre générique "lacentrale.fr"
        if title and title != "lacentrale.fr":
            print(f"  ✓ Challenge passé après {i}s — titre : {title}")
            return True
        if i > 0 and i % 5 == 0:
            print(f"    … {i}s — titre actuel : '{title}' | url : {url[:60]}")
        time.sleep(1)
    print(f"  ✗ Challenge non résolu après {timeout_s}s")
    return False

def attendre_annonces(page):
    selectors = [
        'a[href*="auto-occasion"]', 'a[href*="annonce"]',
        '[class*="vehicleCard"]', '[class*="VehicleCard"]',
        '[data-cy="vehicleCard"]', '[class*="classifiedCard"]',
        '.searchCard', '[data-testid*="vehicle"]',
    ]
    for sel in selectors:
        try:
            page.wait_for_selector(sel, timeout=5000)
            return True
        except Exception:
            pass
    return False

# ─── scraper principal ────────────────────────────────────────────────────────

def scraper():
    data_initiale = charger()
    ids_existants = {v["id"]: v for v in data_initiale.get("vehicules", []) if v.get("id")}

    vehicules_en_ligne = []
    api_responses      = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--window-size=1440,900",
            ]
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
            viewport={"width": 1440, "height": 900},
            extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"},
        )

        # Stealth JS manuel (fonctionne même sans playwright-stealth)
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver',  { get: () => undefined });
            Object.defineProperty(navigator, 'plugins',    { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages',  { get: () => ['fr-FR','fr','en-US','en'] });
            Object.defineProperty(navigator, 'platform',   { get: () => 'MacIntel' });
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
            window.chrome = { runtime: {}, app: {}, csi: function(){}, loadTimes: function(){} };
            const orig = window.navigator.permissions.query;
            window.navigator.permissions.query = (p) =>
                p.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : orig(p);
        """)

        page = context.new_page()

        # Playwright-stealth si disponible
        if HAS_STEALTH:
            stealth_sync(page)
            print("  playwright-stealth appliqué")

        # ── Interception réseau ──────────────────────────────────────────────
        def on_response(response):
            url = response.url
            if not any(d in url for d in ["lacentrale", "lcdnm", "lccdn"]):
                return
            ct = response.headers.get("content-type", "")
            if "json" not in ct:
                return
            try:
                body = response.json()
                print(f"  [API] {response.status} {url[:100]}")
                api_responses.append({"url": url, "data": body})
            except Exception:
                pass

        page.on("response", on_response)

        try:
            print(f"\nChargement de {PAGE_PRO} …")
            page.goto(PAGE_PRO, wait_until="domcontentloaded", timeout=60000)

            print(f"  Titre initial : {page.title()}")
            print(f"  URL finale    : {page.url}")

            # Attendre la fin du challenge DataDome (jusqu'à 45s)
            challenge_ok = attendre_fin_challenge(page, timeout_s=45)

            if not challenge_ok:
                # Dernière chance : log HTML pour diagnostic
                html_snippet = page.content()[:800]
                print(f"  HTML (début) :\n{html_snippet}")
                browser.close()
                return 0

            # Bannière cookies
            accepter_cookies(page)
            page.wait_for_timeout(2000)

            # Scroller pour charger le contenu lazy
            for _ in range(5):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(600)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1000)

            # ── Stratégie 1 : API réseau ─────────────────────────────────────
            if api_responses:
                vehicules_api = extraire_depuis_api(api_responses)
                if vehicules_api:
                    print(f"  → {len(vehicules_api)} annonce(s) via API réseau")
                    vehicules_en_ligne = vehicules_api

            # ── Stratégie 2 : état JS embarqué ──────────────────────────────
            if not vehicules_en_ligne:
                embedded = page.evaluate(JS_EXTRACT_EMBEDDED)
                if embedded:
                    src = embedded.get("_source", "?")
                    print(f"  → Données embarquées ({src}), analyse…")
                    found = _chercher_annonces_dans_json(embedded.get("data", {}))
                    if found:
                        print(f"  → {len(found)} annonce(s) dans {src}")
                        vehicules_en_ligne = found

            # ── Stratégie 3 : DOM ────────────────────────────────────────────
            if not vehicules_en_ligne:
                trouve = attendre_annonces(page)
                if not trouve:
                    print("  Aucun sélecteur DOM reconnu — HTML extrait :")
                    print(page.content()[:800])
                else:
                    vehicules_dom = page.evaluate(JS_EXTRACT_DOM)
                    print(f"  → {len(vehicules_dom)} annonce(s) via DOM")
                    vehicules_en_ligne = vehicules_dom

                    # Pagination
                    page_num = 2
                    while page_num <= 20 and vehicules_dom:
                        next_btn = None
                        for sel in ['a[aria-label*="suivant"]', 'a[title*="suivant"]',
                                    'button:has-text("Suivant")', '[data-cy="nextPage"]',
                                    '.pagination a:last-child', 'a.next',
                                    '[aria-label*="next"]']:
                            try:
                                btn = page.locator(sel).first
                                if btn.is_visible(timeout=1000):
                                    next_btn = btn
                                    break
                            except Exception:
                                pass
                        if not next_btn:
                            break
                        next_btn.click()
                        page.wait_for_timeout(2500)
                        accepter_cookies(page)
                        attendre_annonces(page)
                        for _ in range(3):
                            page.evaluate("window.scrollBy(0, window.innerHeight)")
                            page.wait_for_timeout(400)
                        page_veh = page.evaluate(JS_EXTRACT_DOM)
                        print(f"  Page {page_num} : {len(page_veh)} annonce(s)")
                        vehicules_en_ligne.extend(page_veh)
                        page_num += 1

        except PWTimeout:
            print("  Timeout lors du chargement")
        except Exception as e:
            print(f"  Erreur inattendue : {e}")
            import traceback; traceback.print_exc()
        finally:
            browser.close()

    # ── Dédoublonnage ────────────────────────────────────────────────────────
    vus = {}
    for v in vehicules_en_ligne:
        if v.get("id") and v["id"] not in vus:
            v["prix"] = nettoyer_prix(v.get("prix", ""))
            v["km"]   = nettoyer_km(v.get("km", ""))
            vus[v["id"]] = v

    vehicules_en_ligne = list(vus.values())

    nouveaux = [v for v in vehicules_en_ligne if v["id"] not in ids_existants]
    retires  = [v for v in data_initiale.get("vehicules", [])
                if v.get("id") and v["id"] not in vus]

    for v in nouveaux:
        print(f"  + Nouveau : {v['titre']} | {v['prix']} | {v['km']} | {v['annee']}")
    for v in retires:
        print(f"  - Retiré  : {v['titre']}")

    for v in vehicules_en_ligne:
        vid = v["id"]
        if vid in ids_existants and v["prix"] and ids_existants[vid].get("prix") != v["prix"]:
            print(f"  ~ Prix modifié : {v['titre']} → {v['prix']}")

    data_initiale["vehicules"] = vehicules_en_ligne
    sauvegarder(data_initiale)

    total = len(vehicules_en_ligne)
    print(f"\n✅ {total} véhicule(s) | {len(nouveaux)} nouveau(x) | {len(retires)} retiré(s)")
    return len(nouveaux)


if __name__ == "__main__":
    scraper()
    sys.exit(0)
