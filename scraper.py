"""
Scraper La Centrale — Autocentre C054723
URL cible : https://pros.lacentrale.fr/C054723
Récupère toutes les annonces (photo, titre, prix, km, année) et met à jour vehicules.json
"""

import json, os, sys, re, time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

PAGE_PRO  = "https://pros.lacentrale.fr/C054723"
DATA_FILE = "vehicules.json"

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
    # garde uniquement les chiffres et le symbole €
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

# ─── extraction JS exécutée dans la page ──────────────────────────────────────

JS_EXTRACT = r"""
() => {
    // Sélecteurs connus de La Centrale (pros.lacentrale.fr)
    const CARD_SELECTORS = [
        'a[href*="auto-occasion"]',
        '[class*="vehicleCard"]',
        '[class*="VehicleCard"]',
        '[data-cy="vehicleCard"]',
        'article[class*="listing"]',
        '.searchCard',
        '[class*="card"][class*="vehicle"]',
        '[class*="annonce"]'
    ];

    let cards = [];
    for (const sel of CARD_SELECTORS) {
        const found = Array.from(document.querySelectorAll(sel))
            .filter(el => el.querySelector('img') && el.textContent.length > 20);
        if (found.length > 2) { cards = found; break; }
    }

    // fallback : tous les liens avec une image qui contiennent un prix
    if (cards.length === 0) {
        cards = Array.from(document.querySelectorAll('a'))
            .filter(a => a.href.includes('auto-occasion') && a.querySelector('img'));
    }

    const vehicules = [];
    const vus = new Set();

    cards.forEach(card => {
        try {
            // URL de l'annonce
            const linkEl = card.tagName === 'A' ? card : card.querySelector('a[href*="auto-occasion"]');
            const url = linkEl ? linkEl.href : '';
            if (!url || vus.has(url)) return;
            vus.add(url);

            // ID depuis l'URL
            const idMatch = url.match(/annonce[- _]?(\d{6,})/i) || url.match(/\/(\d{7,})/);
            const id = idMatch ? idMatch[1] : btoa(url).slice(0, 12);

            // Photo
            const img = card.querySelector('img');
            let photo = '';
            if (img) {
                photo = img.src || img.dataset.src || img.dataset.lazySrc
                     || img.getAttribute('data-original') || '';
                // Remplace les petites vignettes par la version HD
                photo = photo.replace(/\/thumbnail\/|\/small\/|_small\.|_thumb\./, '/large/');
            }

            // Titre
            const titreEl = card.querySelector('h2,h3,h4,[class*="title"],[class*="Title"],[class*="name"]');
            const titre = titreEl ? titreEl.textContent.trim() : '';

            // Prix
            const prixEl = card.querySelector('[class*="price"],[class*="Price"],[data-cy*="price"]');
            let prix = prixEl ? prixEl.textContent.trim() : '';
            if (!prix) {
                // cherche un texte qui contient un nombre suivi de €
                const all = Array.from(card.querySelectorAll('*'));
                const found = all.find(el =>
                    el.children.length === 0 && /\d[\d\s]{3,}[€]/.test(el.textContent)
                );
                prix = found ? found.textContent.trim() : '';
            }

            // Détails : année + km
            const allSpans = Array.from(card.querySelectorAll('span,li,p,[class*="detail"]'))
                .map(el => el.textContent.trim()).filter(Boolean);
            const anneeMatch  = allSpans.find(s => /^(19|20)\d{2}$/.test(s)) || '';
            const kmMatch     = allSpans.find(s => /\d[\d\s]*\s*km/i.test(s)) || '';
            const carburant   = allSpans.find(s => /diesel|essence|hybride|électrique|gpl/i.test(s)) || '';
            const boite       = allSpans.find(s => /automatique|manuelle|auto\b/i.test(s)) || '';

            if (!titre && !prix) return; // ignore les faux positifs

            vehicules.push({ id, titre, url, photo, prix, km: kmMatch, annee: anneeMatch, carburant, boite });
        } catch(e) {}
    });

    return vehicules;
}
"""

# ─── scraper principal ────────────────────────────────────────────────────────

def accepter_cookies(page):
    for txt in ["Tout accepter", "Accepter tout", "Accepter", "J'accepte", "OK"]:
        try:
            btn = page.locator(f'button:has-text("{txt}")').first
            if btn.is_visible(timeout=2000):
                btn.click()
                page.wait_for_timeout(600)
                return
        except Exception:
            pass

def attendre_annonces(page):
    """Attend que des annonces soient visibles dans la page."""
    selectors = [
        'a[href*="auto-occasion"]',
        '[class*="vehicleCard"]',
        '[class*="VehicleCard"]',
        '[data-cy="vehicleCard"]',
        '.searchCard',
    ]
    for sel in selectors:
        try:
            page.wait_for_selector(sel, timeout=8000)
            return True
        except Exception:
            pass
    return False

def scraper():
    data_initiale = charger()
    ids_existants = {v["id"]: v for v in data_initiale.get("vehicules", []) if v.get("id")}

    vehicules_en_ligne = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
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

        # Masque navigator.webdriver
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3] });
        """)

        page = context.new_page()

        try:
            print(f"Chargement de {PAGE_PRO} …")
            page.goto(PAGE_PRO, wait_until="domcontentloaded", timeout=50000)
            page.wait_for_timeout(3000)

            # Gérer le captcha / cookie banner
            accepter_cookies(page)
            page.wait_for_timeout(1500)

            # Si Cloudflare challenge, attendre qu'il se résolve
            if "captcha" in page.url.lower() or "challenge" in page.url.lower():
                print("  Cloudflare challenge détecté, attente 10s…")
                page.wait_for_timeout(10000)

            # Attendre les annonces
            trouve = attendre_annonces(page)
            if not trouve:
                print("  Aucune annonce détectée après attente — arrêt")
                browser.close()
                return 0

            # Scroller pour charger le contenu lazy
            for _ in range(4):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(600)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)

            # Extraire les annonces
            vehicules_en_ligne = page.evaluate(JS_EXTRACT)
            print(f"  {len(vehicules_en_ligne)} annonce(s) trouvée(s) sur La Centrale")

            # Pagination : charge les pages suivantes si disponible
            page_num = 2
            while page_num <= 20:  # max 20 pages de sécurité
                next_btn = None
                for sel in ['a[aria-label*="suivant"]', 'a[title*="suivant"]',
                             'button:has-text("Suivant")', '[data-cy="nextPage"]',
                             '.pagination a:last-child', 'a.next']:
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

                page_veh = page.evaluate(JS_EXTRACT)
                print(f"  Page {page_num} : {len(page_veh)} annonce(s)")
                vehicules_en_ligne.extend(page_veh)
                page_num += 1

        except PWTimeout:
            print("  Timeout lors du chargement")
        except Exception as e:
            print(f"  Erreur inattendue : {e}")
        finally:
            browser.close()

    # Dédoublonnage par ID
    vus = {}
    for v in vehicules_en_ligne:
        if v.get("id") and v["id"] not in vus:
            v["prix"]  = nettoyer_prix(v.get("prix", ""))
            v["km"]    = nettoyer_km(v.get("km", ""))
            vus[v["id"]] = v

    vehicules_en_ligne = list(vus.values())

    # Nouveaux véhicules
    nouveaux = [v for v in vehicules_en_ligne if v["id"] not in ids_existants]
    retires  = [v for v in data_initiale.get("vehicules", [])
                if v.get("id") and v["id"] not in vus]

    for v in nouveaux:
        print(f"  + Nouveau : {v['titre']} | {v['prix']} | {v['km']} | {v['annee']}")
    for v in retires:
        print(f"  - Retiré  : {v['titre']}")

    # Mise à jour prix des véhicules existants
    for v in vehicules_en_ligne:
        vid = v["id"]
        if vid in ids_existants and v["prix"] and ids_existants[vid].get("prix") != v["prix"]:
            print(f"  ~ Prix modifié : {v['titre']} → {v['prix']}")

    data_initiale["vehicules"] = vehicules_en_ligne  # liste complète = ce qui est en ligne
    sauvegarder(data_initiale)

    total = len(vehicules_en_ligne)
    print(f"\n✅ {total} véhicule(s) sur le site | {len(nouveaux)} nouveau(x) | {len(retires)} retiré(s)")
    return len(nouveaux)


if __name__ == "__main__":
    scraper()
    sys.exit(0)
