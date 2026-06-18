"""
Récupère les photos des véhicules vendus en visitant chaque page d'archive.
Usage : python3 importer_photos_vendus.py
"""
import json, os, re, random, time
from playwright.sync_api import sync_playwright

VENDUS_FILE = "vehicules_vendus.json"
PHOTOS_DIR  = "photos"
BASE_URL    = "https://pilot.lacentrale.fr"

os.makedirs(PHOTOS_DIR, exist_ok=True)

def main():
    with open(VENDUS_FILE, encoding="utf-8") as f:
        data = json.load(f)

    vehicules = data["vehicules"]
    a_traiter = [v for v in vehicules if v.get("id") and not os.path.exists(f"{PHOTOS_DIR}/{v['id']}.jpg")]
    print(f"{len(a_traiter)} véhicules sans photo à traiter")

    if not a_traiter:
        print("Toutes les photos sont déjà présentes.")
        return

    print("\nOuvre le navigateur, connecte-toi à pilot.lacentrale.fr, puis appuie sur ENTRÉE...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="fr-FR",
            viewport={"width": 1440, "height": 900},
        )
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        page = ctx.new_page()

        photos_capturees = {}
        def handle_response(response):
            try:
                url = response.url
                if "pictures.lacentrale.fr" not in url or response.status != 200:
                    return
                try:
                    body = response.body()
                except Exception:
                    return
                if len(body) < 5000:
                    return
                # Extraire l'ID depuis l'URL de la photo
                for vid in list(photos_capturees.keys()) + ["__pending__"]:
                    pass
                photos_capturees[url] = body
            except Exception:
                pass
        page.on("response", handle_response)

        page.goto(f"{BASE_URL}/C054723", wait_until="domcontentloaded", timeout=60000)
        input("→ Appuie sur ENTRÉE une fois connecté... ")

        ok = 0
        for i, v in enumerate(a_traiter):
            vid   = v["id"]
            url   = v.get("url", f"{BASE_URL}/C054723/annonces/archives/{vid}")
            local = f"{PHOTOS_DIR}/{vid}.jpg"
            print(f"  [{i+1:3d}/{len(a_traiter)}] {v.get('titre','')[:35]}…", end=" ", flush=True)

            photos_capturees.clear()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(random.randint(1500, 2500))

                # Scroll pour déclencher le lazy loading de la photo
                page.evaluate("window.scrollTo({top: 400, behavior: 'smooth'})")
                page.wait_for_timeout(1000)

                # Chercher la photo dans les réponses capturées
                saved = False
                for photo_url, body in photos_capturees.items():
                    with open(local, "wb") as f2:
                        f2.write(body)
                    v["photo_local"] = f"photos/{vid}.jpg"
                    v["photo"]       = photo_url
                    print(f"✓ ({len(body)//1024} Ko)")
                    ok += 1
                    saved = True
                    break

                if not saved:
                    # Essayer de trouver l'URL de la photo dans la page
                    img_url = page.evaluate("""() => {
                        const img = document.querySelector('img[src*="pictures.lacentrale"]');
                        return img ? img.src : null;
                    }""")
                    if img_url:
                        v["photo"] = img_url
                        print(f"URL trouvée (non téléchargée)")
                    else:
                        print("✗")

            except Exception as e:
                print(f"✗ ({str(e)[:30]})")

            # Sauvegarde intermédiaire toutes les 20 photos
            if (i + 1) % 20 == 0:
                with open(VENDUS_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"    [Sauvegarde intermédiaire — {ok} photos OK]")

            time.sleep(random.uniform(1.5, 3))

        browser.close()

    with open(VENDUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f" ✅ {ok} photo(s) récupérée(s) sur {len(a_traiter)}")
    print(f"{'='*50}")
    print("\nEnsuite :")
    print("  git add photos/ vehicules_vendus.json")
    print('  git commit -m "Photos véhicules vendus"')
    print("  git push origin main")

if __name__ == "__main__":
    main()