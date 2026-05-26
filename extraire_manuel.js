/**
 * ╔══════════════════════════════════════════════════════════╗
 * ║  SCRIPT EXTRACTION MANUELLE — La Centrale Autocentre     ║
 * ║                                                          ║
 * ║  1. Ouvrir Chrome sur https://pros.lacentrale.fr/C054723 ║
 * ║  2. Appuyer sur F12 → onglet "Console"                  ║
 * ║  3. Coller tout ce script et appuyer sur Entrée          ║
 * ║  4. Le script parcourt toutes les pages automatiquement  ║
 * ║  5. À la fin → fichier vehicules.json téléchargé        ║
 * ╚══════════════════════════════════════════════════════════╝
 */

(async function extraireAutocentre() {

    const GITHUB_TOKEN = 'VOTRE_TOKEN_ICI'; // remplacer par votre token GitHub
    const GITHUB_REPO  = 'autocentresas/autocentre-site';
    const GITHUB_PATH  = 'vehicules.json';

    console.log('%c🚗 Extraction Autocentre La Centrale démarrée…', 'color:#2563eb;font-size:14px;font-weight:bold');

    // ── Extraction d'une page ────────────────────────────────────────────────
    function extrairePage() {
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
                res.push({ id, titre, version, url, photo, prix, km, annee, carburant: carb, boite });
            } catch(e) {}
        });
        return res;
    }

    // ── Attente d'un sélecteur ───────────────────────────────────────────────
    function attendre(ms) {
        return new Promise(r => setTimeout(r, ms));
    }
    function attendreElement(sel, timeout = 10000) {
        return new Promise((resolve) => {
            const start = Date.now();
            const check = () => {
                const el = document.querySelector(sel);
                if (el) return resolve(el);
                if (Date.now() - start > timeout) return resolve(null);
                setTimeout(check, 300);
            };
            check();
        });
    }

    // ── Boucle principale ────────────────────────────────────────────────────
    const tousTous = [];
    let pageActuelle = 1;

    while (true) {
        // Attendre que les cartes soient chargées
        await attendreElement('div.searchCard');
        await attendre(1000);

        const vehicules = extrairePage();
        tousTous.push(...vehicules);
        console.log(`  Page ${pageActuelle} : ${vehicules.length} annonces | total : ${tousTous.length}`);

        // Chercher le lien "page suivante"
        const prochainePage = pageActuelle + 1;
        const lienSuivant = document.querySelector(`a[href*="page=${prochainePage}"]`);

        if (!lienSuivant) {
            console.log('%c✅ Toutes les pages extraites !', 'color:green;font-weight:bold');
            break;
        }

        // Scroll vers le lien et cliquer
        lienSuivant.scrollIntoView({ behavior: 'smooth', block: 'center' });
        await attendre(800);
        lienSuivant.click();

        // Attendre le chargement de la nouvelle page
        await attendre(2000);
        await attendreElement('div.searchCard', 15000);
        await attendre(1500);
        pageActuelle++;

        if (pageActuelle > 25) break; // sécurité
    }

    // ── Dédoublonnage ────────────────────────────────────────────────────────
    const vus = {};
    for (const v of tousTous) {
        if (v.id && !vus[v.id]) {
            // Nettoyer prix
            v.prix = v.prix.replace(/\s+/g, ' ').trim();
            if (v.prix && !v.prix.includes('€')) v.prix += ' €';
            // Nettoyer km
            const kmM = v.km.match(/([\d\s]+)\s*km/i);
            if (kmM) v.km = kmM[0].trim();
            vus[v.id] = v;
        }
    }
    const vehiculesFinaux = Object.values(vus);

    // ── Construire vehicules.json ─────────────────────────────────────────────
    const now = new Date();
    const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${now.getFullYear()} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
    const data = { derniere_maj: dateStr, vehicules: vehiculesFinaux };
    const jsonStr = JSON.stringify(data, null, 2);

    console.log(`%c📦 ${vehiculesFinaux.length} véhicules extraits`, 'color:#2563eb;font-weight:bold');

    // ── Push vers GitHub ─────────────────────────────────────────────────────
    console.log('📤 Envoi vers GitHub…');
    try {
        const apiUrl = `https://api.github.com/repos/${GITHUB_REPO}/contents/${GITHUB_PATH}`;
        const headers = {
            'Authorization': `token ${GITHUB_TOKEN}`,
            'Content-Type': 'application/json',
            'User-Agent': 'autocentre-browser/1.0'
        };

        // Récupérer SHA actuel
        let sha = '';
        try {
            const getResp = await fetch(apiUrl, { headers });
            if (getResp.ok) {
                const current = await getResp.json();
                sha = current.sha || '';
            }
        } catch(e) {}

        // Encoder en base64
        const encoded = btoa(unescape(encodeURIComponent(jsonStr)));

        const payload = {
            message: `🚗 ${vehiculesFinaux.length} véhicules — ${dateStr}`,
            content: encoded,
            sha: sha
        };

        const putResp = await fetch(apiUrl, {
            method: 'PUT',
            headers,
            body: JSON.stringify(payload)
        });

        if (putResp.ok) {
            const result = await putResp.json();
            const commitSha = result?.commit?.sha?.slice(0, 10) || '?';
            console.log(`%c✅ GitHub mis à jour — commit ${commitSha}`, 'color:green;font-weight:bold');
            console.log(`%c🌐 Site : https://autocentresas.github.io/autocentre-site/`, 'color:#2563eb');
        } else {
            const err = await putResp.text();
            console.error('❌ Erreur GitHub :', putResp.status, err);
        }
    } catch(e) {
        console.error('❌ Erreur push :', e);
    }

    // ── Télécharger le fichier en local aussi ────────────────────────────────
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'vehicules.json';
    a.click();
    URL.revokeObjectURL(url);
    console.log('%c💾 vehicules.json téléchargé localement', 'color:gray');

})();
