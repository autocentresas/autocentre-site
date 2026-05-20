"""
Scraper La Centrale — Autocentre C054723
Récupère les annonces du garage et met à jour vehicules.json

Stratégies (dans l'ordre) :
  1. curl-cffi (imite l'empreinte TLS de Chrome → contourne DataDome côté IP)
  2. URL publique www.lacentrale.fr avec le filtre dealer
  3. Playwright + stealth + Xvfb (fallback navigateur complet)
"""

import json, os, sys, re, time
from datetime import datetime
from bs4 import BeautifulSoup

# ─── constantes ───────────────────────────────────────────────────────────────

DEALER_ID  = "C054723"
PAGE_PRO   = f"https://pros.lacentrale.fr/{DEALER_ID}"
PAGE_WWW   = f"https://www.lacentrale.fr/listing.php?makesModelsCommercialNames=&criterias=&VENDEUR={DEALER_ID}"
DATA_FILE  = "vehicules.json"

HEADERS_CHROME = {
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control":   "no-cache",
    "Pragma":          "no-cache",
    "Sec-Ch-Ua":       '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile":"?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest":  "document",
    "Sec-Fetch-Mode":  "navigate",
    "Sec-Fetch-Site":  "none",
    "Sec-Fetch-User":  "?1",
    "Upgrade-Insecure-Requests": "1",
}

# Mode headless/non-headless selon DISPLAY (Xvfb dans le workflow)
HEADLESS = os.environ.get("DISPLAY") is None

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

def is_datadome(html: str) -> bool:
    """Retourne True si la page est une page challenge DataDome."""
    return ("captcha-delivery.com" in html or
            "datadome" in html.lower() or
            "<title>lacentrale.fr</title>" in html)

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
    return m.group(0).strip() if m else txt.strip()

# ─── Stratégie 1 : curl-cffi (TLS Chrome spoofing) ───────────────────────────

def scraper_curl(url, session=None):
    """
    Essaie de scraper via curl-cffi qui imite exactement l'empreinte TLS de Chrome.
    DataDome vérifie le TLS fingerprint (JA3/JA4) en premier — cette méthode le contourne.
    Retourne (html, vehicules) ou (None, []).
    """
    try:
        from curl_cffi import requests as cf
    except ImportError:
        print("  curl-cffi non disponible")
        return None, []

    try:
        print(f"  [curl-cffi] GET {url[:70]}…")
        if session is None:
            session = cf.Session(impersonate="chrome124")

        resp = session.get(url, headers=HEADERS_CHROME, timeout=30, allow_redirects=True)
        html = resp.text
        print(f"  [curl-cffi] status={resp.status_code}  len={len(html)}")

        if is_datadome(html):
            print("  [curl-cffi] DataDome challenge détecté dans la réponse")
            return None, []

        if resp.status_code != 200:
            print(f"  [curl-cffi] Statut inattendu : {resp.status_code}")
            return None, []

        # Cherche du JSON embarqué (Next.js / Nuxt / state)
        vehicules = []
        vehicules = _extraire_json_html(html) or []

        # Si pas de JSON, tente l'API JSON directe
        if not vehicules:
            vehicules = _tenter_api_json(session, url)

        # Sinon, parsing HTML
        if not vehicules:
            vehicules = _parser_html(html, url)

        return html, vehicules

    except Exception as e:
        print(f"  [curl-cffi] Erreur : {e}")
        return None, []

def _tenter_api_json(session, base_url):
    """Tente d'appeler des API JSON courantes de La Centrale."""
    endpoints = [
        f"https://pros.lacentrale.fr/api/dealer/{DEALER_ID}/vehicles",
        f"https://pros.lacentrale.fr/api/dealers/{DEALER_ID}/classifieds",
        f"https://www.lacentrale.fr/api/v2/search?VENDEUR={DEALER_ID}",
        f"https://www.lacentrale.fr/api/search?vendor={DEALER_ID}",
        f"https://pros.lacentrale.fr/api/{DEALER_ID}/ads",
    ]
    hdrs = {**HEADERS_CHROME,
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest"}
    for ep in endpoints:
        try:
            r = session.get(ep, headers=hdrs, timeout=10)
            if r.status_code == 200 and "json" in r.headers.get("content-type",""):
                data = r.json()
                found = _chercher_annonces_dans_json(data, ep)
                if found:
                    print(f"  [API directe] {len(found)} annonces depuis {ep[:70]}")
                    return found
        except Exception:
            pass
    return []

def _extraire_json_html(html: str):
    """Extrait les annonces depuis les objets JSON embarqués dans le HTML."""
    vehicules = []
    # Cherche window.__NEXT_DATA__, __NUXT__, __INITIAL_STATE__
    patterns = [
        r'window\.__NEXT_DATA__\s*=\s*(\{.+?\})(?=\s*</script>)',
        r'window\.__NUXT__\s*=\s*(\{.+?\})(?=\s*</script>)',
        r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\})(?=\s*</script>)',
        r'<script[^>]+type="application/json"[^>]*>(\{.+?\})</script>',
        r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.+?)</script>',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.DOTALL | re.IGNORECASE)
        if m:
            try:
                obj = json.loads(m.group(1))
                found = _chercher_annonces_dans_json(obj)
                if found:
                    print(f"  [JSON embarqué] {len(found)} annonces")
                    vehicules.extend(found)
                    break
            except Exception:
                pass
    return vehicules

def _parser_html(html: str, base_url: str):
    """Parse le HTML pour extraire les annonces via BeautifulSoup."""
    soup = BeautifulSoup(html, "html.parser")
    vehicules = []
    vus = set()

    # Sélecteurs CSS communs
    card_selectors = [
        {"data-cy": "vehicleCard"},
        {"class": re.compile(r"vehicleCard|VehicleCard|vehicle-card|classifiedCard|searchCard|annonce")},
    ]

    cards = []
    for sel in card_selectors:
        found = soup.find_all(attrs=sel)
        if len(found) > 1:
            cards = found
            break

    # Fallback : liens avec auto-occasion dans l'href
    if not cards:
        cards = [a for a in soup.find_all("a", href=True)
                 if "auto-occasion" in a.get("href","") and a.find("img")]

    for card in cards:
        try:
            link_el = card if card.name == "a" else card.find("a", href=re.compile(r"auto-occasion|annonce"))
            url = link_el["href"] if link_el else ""
            if not url:
                continue
            if not url.startswith("http"):
                url = "https://www.lacentrale.fr" + url
            if url in vus:
                continue
            vus.add(url)

            id_m = re.search(r"annonce[- _]?(\d{6,})", url, re.I) or re.search(r"/(\d{7,})", url)
            vid = id_m.group(1) if id_m else url[-12:]

            img = card.find("img")
            photo = ""
            if img:
                photo = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
                if photo and not photo.startswith("http"):
                    photo = "https:" + photo if photo.startswith("//") else "https://www.lacentrale.fr" + photo

            titre_el = card.find(["h2","h3","h4"], class_=re.compile(r"title|Title|name|label", re.I))
            if not titre_el:
                titre_el = card.find(class_=re.compile(r"title|Title|name|label", re.I))
            titre = titre_el.get_text(strip=True) if titre_el else ""

            prix_el = card.find(class_=re.compile(r"price|Price|prix", re.I))
            prix = prix_el.get_text(strip=True) if prix_el else ""
            if not prix:
                for el in card.find_all(string=re.compile(r"\d[\d\s]{2,}€")):
                    prix = str(el).strip()
                    break

            texts = [t.strip() for t in card.stripped_strings]
            annee = next((t for t in texts if re.match(r"^(19|20)\d{2}$", t)), "")
            km    = next((t for t in texts if re.search(r"\d[\d\s]*\s*km", t, re.I)), "")
            carb  = next((t for t in texts if re.search(r"diesel|essence|hybride|électrique|gpl", t, re.I)), "")
            boite = next((t for t in texts if re.search(r"automatique|manuelle|auto\b", t, re.I)), "")

            if not titre and not prix:
                continue

            vehicules.append({"id": vid, "titre": titre, "url": url, "photo": photo,
                               "prix": prix, "km": km, "annee": annee,
                               "carburant": carb, "boite": boite})
        except Exception:
            pass

    return vehicules

# ─── Stratégie 2 : Playwright complet ─────────────────────────────────────────

JS_EXTRACT_EMBEDDED = r"""
() => {
    if (window.__NEXT_DATA__) return { _source: '__NEXT_DATA__', data: window.__NEXT_DATA__ };
    if (window.__NUXT__)      return { _source: '__NUXT__',      data: window.__NUXT__ };
    for (const k of ['__INITIAL_STATE__','__APP_STATE__','__STATE__','__data__']) {
        try {
            const v = window[k];
            if (v && typeof v === 'object') return { _source: k, data: v };
        } catch(e) {}
    }
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
    const SELS = [
        '[data-cy="vehicleCard"]','[class*="vehicleCard"]','[class*="VehicleCard"]',
        '[class*="vehicle-card"]','[class*="classifiedCard"]','a[href*="auto-occasion"]',
        'article[class*="listing"]','[class*="searchCard"]','[class*="annonce"]',
        '[data-testid*="card"]','[data-testid*="vehicle"]',
    ];
    let cards = [];
    for (const sel of SELS) {
        try {
            const found = Array.from(document.querySelectorAll(sel))
                .filter(el => el.textContent && el.textContent.length > 20);
            if (found.length > 1) { cards = found; break; }
        } catch(e) {}
    }
    if (!cards.length) {
        cards = Array.from(document.querySelectorAll('a'))
            .filter(a => (a.href.includes('auto-occasion')||a.href.includes('annonce')) && a.querySelector('img'));
    }
    const vehicules = [];
    const vus = new Set();
    cards.forEach(card => {
        try {
            const linkEl = card.tagName==='A' ? card
                : card.querySelector('a[href*="auto-occasion"]') || card.querySelector('a[href*="annonce"]') || card.querySelector('a');
            const url = linkEl ? linkEl.href : '';
            if (!url || vus.has(url)) return;
            vus.add(url);
            const idMatch = url.match(/annonce[- _]?(\d{6,})/i) || url.match(/\/(\d{7,})/);
            const id = idMatch ? idMatch[1] : btoa(url).slice(0,12);
            const img = card.querySelector('img');
            let photo = img ? (img.src||img.dataset.src||img.dataset.lazySrc||img.getAttribute('data-original')||'') : '';
            photo = photo.replace(/\/thumbnail\/|\/small\/|_small\.|_thumb\./, '/large/');
            const titreEl = card.querySelector('h2,h3,h4,[class*="title"],[class*="Title"],[class*="name"]');
            const titre = titreEl ? titreEl.textContent.trim() : '';
            const prixEl = card.querySelector('[class*="price"],[class*="Price"],[data-cy*="price"]');
            let prix = prixEl ? prixEl.textContent.trim() : '';
            if (!prix) {
                const f = Array.from(card.querySelectorAll('*')).find(el => el.children.length===0 && /\d[\d\s]{2,}[€]/.test(el.textContent));
                prix = f ? f.textContent.trim() : '';
            }
            const texts = Array.from(card.querySelectorAll('span,li,p,div')).map(el=>el.textContent.trim()).filter(Boolean);
            const annee = texts.find(s=>/^(19|20)\d{2}$/.test(s))||'';
            const km    = texts.find(s=>/\d[\d\s]*\s*km/i.test(s))||'';
            const carb  = texts.find(s=>/diesel|essence|hybride|électrique|gpl/i.test(s))||'';
            const boite = texts.find(s=>/automatique|manuelle|auto\b/i.test(s))||'';
            if (!titre && !prix) return;
            vehicules.push({id,titre,url,photo,prix,km,annee,carburant:carb,boite});
        } catch(e) {}
    });
    return vehicules;
}
"""

def scraper_playwright(url):
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    try:
        from playwright_stealth import stealth_sync
        HAS_STEALTH = True
    except ImportError:
        HAS_STEALTH = False

    vehicules = []
    api_responses = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=["--no-sandbox","--disable-setuid-sandbox",
                  "--disable-blink-features=AutomationControlled",
                  "--disable-dev-shm-usage","--window-size=1440,900"]
        )
        context = browser.new_context(
            user_agent=HEADERS_CHROME["User-Agent"],
            locale="fr-FR", viewport={"width":1440,"height":900},
            extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"},
        )
        context.add_init_script("""
            Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
            Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
            Object.defineProperty(navigator,'languages',{get:()=>['fr-FR','fr','en-US','en']});
            Object.defineProperty(navigator,'platform',{get:()=>'MacIntel'});
            Object.defineProperty(navigator,'hardwareConcurrency',{get:()=>8});
            window.chrome={runtime:{},app:{},csi:function(){},loadTimes:function(){}};
        """)

        page = context.new_page()
        if HAS_STEALTH:
            stealth_sync(page)

        def on_response(response):
            u = response.url
            if not any(d in u for d in ["lacentrale","lcdnm","lccdn"]):
                return
            if "json" not in response.headers.get("content-type",""):
                return
            try:
                api_responses.append({"url":u,"data":response.json()})
            except Exception:
                pass
        page.on("response", on_response)

        try:
            print(f"  [Playwright] GET {url[:70]} (headless={HEADLESS})…")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Attendre résolution challenge DataDome (max 60s)
            for i in range(60):
                t = page.title()
                if t and t not in ("lacentrale.fr", "pros.lacentrale.fr", ""):
                    print(f"  [Playwright] Challenge passé après {i}s — titre: {t}")
                    break
                if i > 0 and i % 10 == 0:
                    print(f"  [Playwright] … {i}s — titre: '{t}'")
                time.sleep(1)
            else:
                print("  [Playwright] Challenge non résolu après 60s — abandon")
                browser.close()
                return []

            # Cookies + scroll
            for btn_txt in ["Tout accepter","Accepter","J'accepte","OK"]:
                try:
                    btn = page.locator(f'button:has-text("{btn_txt}")').first
                    if btn.is_visible(timeout=1000):
                        btn.click(); page.wait_for_timeout(500); break
                except Exception:
                    pass

            for _ in range(4):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(500)
            page.evaluate("window.scrollTo(0,0)")
            page.wait_for_timeout(800)

            # API réseau
            if api_responses:
                for entry in api_responses:
                    found = _chercher_annonces_dans_json(entry["data"], entry["url"])
                    if found:
                        print(f"  [Playwright/API] {len(found)} annonces depuis {entry['url'][:70]}")
                        vehicules.extend(found)
                        break

            # JSON embarqué
            if not vehicules:
                emb = page.evaluate(JS_EXTRACT_EMBEDDED)
                if emb:
                    found = _chercher_annonces_dans_json(emb.get("data",{}))
                    if found:
                        print(f"  [Playwright/JS] {len(found)} annonces ({emb.get('_source')})")
                        vehicules = found

            # DOM
            if not vehicules:
                vehicules = page.evaluate(JS_EXTRACT_DOM)
                print(f"  [Playwright/DOM] {len(vehicules)} annonces")

                # Pagination
                page_num = 2
                while page_num <= 15 and vehicules:
                    nb = None
                    for sel in ['a[aria-label*="suivant"]','button:has-text("Suivant")','[data-cy="nextPage"]','.pagination a:last-child']:
                        try:
                            b = page.locator(sel).first
                            if b.is_visible(timeout=1000):
                                nb = b; break
                        except Exception:
                            pass
                    if not nb:
                        break
                    nb.click()
                    page.wait_for_timeout(2500)
                    for _ in range(3):
                        page.evaluate("window.scrollBy(0, window.innerHeight)")
                        page.wait_for_timeout(400)
                    pv = page.evaluate(JS_EXTRACT_DOM)
                    print(f"  [Playwright/DOM] page {page_num}: {len(pv)} annonces")
                    vehicules.extend(pv)
                    page_num += 1

        except PWTimeout:
            print("  [Playwright] Timeout")
        except Exception as e:
            print(f"  [Playwright] Erreur : {e}")
            import traceback; traceback.print_exc()
        finally:
            browser.close()

    return vehicules

# ─── Extraction JSON générique ────────────────────────────────────────────────

def _chercher_annonces_dans_json(obj, url="", depth=0):
    if depth > 8:
        return []
    if isinstance(obj, list) and len(obj) >= 2:
        sample = obj[0] if obj else {}
        if isinstance(sample, dict):
            keys = set(sample.keys())
            if keys & {"makeLabel","modelLabel","price","mileage","id","title",
                       "brandLabel","fuelLabel","gearboxLabel","firstRegistrationYear",
                       "photos","images","picture","thumbnail","url","link"}:
                return [_normaliser_annonce(i, url) for i in obj if isinstance(i, dict)]
    if isinstance(obj, dict):
        for key in ("ads","vehicles","vehicules","listings","results","items",
                    "annonces","data","list","searchResults","classifiedAds","classified"):
            if key in obj and isinstance(obj[key], (list,dict)):
                found = _chercher_annonces_dans_json(obj[key], url, depth+1)
                if found:
                    return found
        for v in obj.values():
            if isinstance(v, (dict,list)):
                found = _chercher_annonces_dans_json(v, url, depth+1)
                if found:
                    return found
    return []

def _normaliser_annonce(item, source_url=""):
    def g(*keys):
        for k in keys:
            if k in item and item[k]: return str(item[k])
        return ""

    vid = g("id","classifiedId","adId","vehicleId")
    if not vid:
        raw_url = g("url","link","detailUrl","seoUrl")
        m = re.search(r"(\d{7,})", raw_url)
        vid = m.group(1) if m else str(abs(hash(str(item))))[:10]

    make  = g("makeLabel","brandLabel","make","brand","marque")
    model = g("modelLabel","model","modele")
    ver   = g("versionLabel","version","titre","title","label")
    if make and model:
        titre = f"{make} {model}" + (f" {ver}" if ver and ver not in f"{make} {model}" else "")
    else:
        titre = ver or g("titre","title","label","name") or "Véhicule"

    raw_url = g("url","link","detailUrl","seoUrl","annonce_url")
    if raw_url and not raw_url.startswith("http"):
        raw_url = "https://www.lacentrale.fr" + raw_url

    photo = ""
    for k in ("photos","images","pictures"):
        if k in item:
            imgs = item[k]
            if isinstance(imgs, list) and imgs:
                first = imgs[0]
                photo = first if isinstance(first, str) else (first.get("url") or first.get("src") or "")
            break
    if not photo:
        photo = g("photo","picture","thumbnail","image","photoUrl")
    if photo and not photo.startswith("http"):
        photo = "https:" + photo if photo.startswith("//") else "https://www.lacentrale.fr" + photo

    prix_raw = item.get("price") or item.get("prix") or item.get("sellingPrice") or ""
    if isinstance(prix_raw, (int,float)):
        prix = f"{int(prix_raw):,}".replace(",","") + " €"
    else:
        prix = nettoyer_prix(str(prix_raw)) if prix_raw else ""

    km_raw = item.get("mileage") or item.get("km") or item.get("kilometrage") or ""
    if isinstance(km_raw, (int,float)):
        km = f"{int(km_raw):,}".replace(",","") + " km"
    else:
        km = nettoyer_km(str(km_raw)) if km_raw else ""

    annee = g("firstRegistrationYear","year","annee","yearOfRegistration","registrationYear")
    if annee and len(annee) > 4:
        m2 = re.search(r"(19|20)\d{2}", annee)
        annee = m2.group(0) if m2 else annee[:4]

    return {"id": vid, "titre": titre.strip(), "url": raw_url,
            "photo": photo, "prix": prix, "km": km, "annee": annee,
            "carburant": g("fuelLabel","fuel","carburant","energy"),
            "boite":     g("gearboxLabel","gearbox","transmission","boite")}

# ─── Scraper principal ────────────────────────────────────────────────────────

def scraper():
    data_initiale = charger()
    ids_existants = {v["id"]: v for v in data_initiale.get("vehicules", []) if v.get("id")}

    vehicules_en_ligne = []

    # ── Tier 1 : curl-cffi sur l'URL pro ────────────────────────────────────
    print(f"\n=== Tier 1 : curl-cffi / {PAGE_PRO} ===")
    _, vehicules_en_ligne = scraper_curl(PAGE_PRO)

    # ── Tier 2 : curl-cffi sur l'URL publique www ────────────────────────────
    if not vehicules_en_ligne:
        print(f"\n=== Tier 2 : curl-cffi / {PAGE_WWW[:60]} ===")
        _, vehicules_en_ligne = scraper_curl(PAGE_WWW)

    # ── Tier 3 : Playwright complet sur l'URL pro ────────────────────────────
    if not vehicules_en_ligne:
        print(f"\n=== Tier 3 : Playwright / {PAGE_PRO} ===")
        vehicules_en_ligne = scraper_playwright(PAGE_PRO)

    # ── Tier 4 : Playwright sur l'URL publique ───────────────────────────────
    if not vehicules_en_ligne:
        print(f"\n=== Tier 4 : Playwright / {PAGE_WWW[:60]} ===")
        vehicules_en_ligne = scraper_playwright(PAGE_WWW)

    # ── Dédoublonnage ────────────────────────────────────────────────────────
    vus = {}
    for v in vehicules_en_ligne:
        if v.get("id") and v["id"] not in vus:
            v["prix"] = nettoyer_prix(v.get("prix",""))
            v["km"]   = nettoyer_km(v.get("km",""))
            vus[v["id"]] = v

    vehicules_en_ligne = list(vus.values())

    nouveaux = [v for v in vehicules_en_ligne if v["id"] not in ids_existants]
    retires  = [v for v in data_initiale.get("vehicules",[])
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
