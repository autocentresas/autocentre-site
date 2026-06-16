"""
Téléchargeur de photos manquantes — Autocentre
================================================
Usage : python3 telecharger_photos.py

Durée estimée : ~8-12s par véhicule. Pour 157 véhicules ≈ 25-35 minutes.
"""

import json, os, time, random, base64
from datetime import datetime
from playwright.sync_api import sync_playwright

DATA_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vehicules.json")
PHOTOS_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "photos")
GITHUB_REPO = "autocentresas/autocentre-site"
os.makedirs(PHOTOS_DIR, exist_ok=True)


def charger():
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def sauvegarder(data):
    data["derniere_maj"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("  [JSON] vehicules.json sauvegardé")


def get_github_token():
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token and token.startswith("ghp_"):
        return token
    token_file = os.path.expanduser("~/.autocentre_token")
    if os.path.exists(token_file):
        try:
            with open(token_file) as f:
                return f.read().strip()
        except Exception:
            pass
    return ""


def push_file_github(token, local_path, remote_path, message):
    import urllib.request
    headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/json",
        "User-Agent": "autocentre-scraper/1.0"
    }
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{remote_path}"
    sha = ""
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as r:
            sha = json.loads(r.read()).get("sha", "")
    except Exception:
        pass
    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    payload = json.dumps({"message": message, "content": content, "sha": sha}).encode()
    req2 = urllib.request.Request(api_url, data=payload, headers=headers, method="PUT")
    with urllib.request.urlopen(req2) as r:
        return json.loads(r.read()).get("commit", {}).get("sha", "")[:10]


def push_tout_github(token, vehicules_modifies):
    if not token:
        print("  [GitHub] Token absent — push ignoré")
        return
    try:
        push_file_github(token, DATA_FILE, "vehicules.json",
                         f"Photos ajoutées — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        print("  [GitHub] ✓ vehicules.json")
        nb = 0
        for v in vehicules_modifies:
            fname = f"{v['id']}.jpg"
            local = os.path.join(PHOTOS_DIR, fname)
            if os.path.exists(local):
                try:
                    push_file_github(token, local, f"photos/{fname}", f"Photo {fname}")
                    nb += 1
                except Exception as e:
                    print(f"  [GitHub] Erreur {fname} : {e}")
        print(f"  [GitHub] ✓ {nb} photo(s) poussée(s)")
    except Exception as e:
        print(f"  [GitHub] Erreur : {e}")


def telecharger_photo_vehicle(page, vehicule, timeout_ms=15000):
    url = vehicule.get("url", "")
    if not url:
        return None

    photo_body = None
    photo_event = {"done": False}

    def on_response(response):
        try:
            if "pictures.lacentrale.fr" not in response.url:
                return
            if response.status != 200:
                return
            if "_STANDARD_0" not in response.url and "size=640" not in response.url:
                return
            body = response.body()
            if len(body) > 5000:
                nonlocal photo_body
                photo_body = body
                photo_event["done"] = True
        except Exception:
            pass

    page.on("response", on_response)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        page.evaluate("window.scrollTo({top: 400, behavior: 'smooth'})")
        deadline = time.time() + timeout_ms / 1000
        while not photo_event["done"] and time.time() < deadline:
            time.sleep(0.2)
    except Exception:
        pass
    finally:
        page.remove_listener("response", on_response)

    return photo_body


def main():
    data = charger()
    vehicules = data.get("vehicules", [])
    sans_photo = [v for v in vehicules if not v.get("photo_local")]

    print(f"\n{'='*55}")
    print(f" Téléchargeur de photos — Autocentre")
    print(f" {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'='*55}")
    print(f"\n{len(vehicules)} véhicules au total")
    print(f"{len(sans_photo)} sans photo locale\n")

    if not sans_photo:
        print("✅ Toutes les photos sont déjà téléchargées !")
        return

    token = get_github_token()
    vehicules_modifies = []
    nb_ok = 0
    nb_err = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"]
        )
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="fr-FR",
            viewport={"width": 1440, "height": 900},
            extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"},
        )
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins',   { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR','fr','en-US'] });
            Object.defineProperty(navigator, 'platform',  { get: () => 'MacIntel' });
            window.chrome = { runtime: {} };
        """)

        page = ctx.new_page()

        print("Chargement initial La Centrale (cookies DataDome)…")
        try:
            page.goto("https://pros.lacentrale.fr/C054723", wait_until="domcontentloaded", timeout=60000)
            for i in range(30):
                title = page.title()
                if title and title not in ("lacentrale.fr", "pros.lacentrale.fr", ""):
                    print(f"  ✓ Connecté ({i}s) : {title[:50]}")
                    break
                if i % 10 == 0 and i > 0:
                    print(f"  … attente {i}s")
                time.sleep(1)
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
        except Exception as e:
            print(f"  Erreur chargement initial : {e}")

        print(f"\nTéléchargement des {len(sans_photo)} photos manquantes…\n")

        for i, v in enumerate(sans_photo, 1):
            vid = v["id"]
            titre = v.get("titre", vid)
            local_path = os.path.join(PHOTOS_DIR, f"{vid}.jpg")

            if os.path.exists(local_path) and os.path.getsize(local_path) > 5000:
                v["photo_local"] = f"photos/{vid}.jpg"
                vehicules_modifies.append(v)
                nb_ok += 1
                print(f"  [{i:3d}/{len(sans_photo)}] ✓ (déjà sur disque) {titre}")
                continue

            print(f"  [{i:3d}/{len(sans_photo)}] {titre} … ", end="", flush=True)
            body = telecharger_photo_vehicle(page, v)

            if body and len(body) > 5000:
                with open(local_path, "wb") as f:
                    f.write(body)
                v["photo_local"] = f"photos/{vid}.jpg"
                vehicules_modifies.append(v)
                nb_ok += 1
                print(f"✓ ({len(body)//1024} Ko)")
            else:
                nb_err += 1
                print("✗ (photo non capturée)")

            if i % 10 == 0:
                sauvegarder(data)
                print(f"\n  [Sauvegarde intermédiaire après {i} véhicules]\n")

            time.sleep(random.uniform(1.5, 3.0))

        browser.close()

    print(f"\n{'='*55}")
    print(f" ✅ {nb_ok} photo(s) téléchargée(s) | ✗ {nb_err} échec(s)")
    print(f"{'='*55}\n")

    if vehicules_modifies:
        sauvegarder(data)
        print("\nSynchronisation GitHub…")
        push_tout_github(token, vehicules_modifies)
    else:
        print("Aucune nouvelle photo — aucun changement.")


if __name__ == "__main__":
    main()