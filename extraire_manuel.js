/**
 * ╔══════════════════════════════════════════════════════════╗
 * ║  SCRIPT EXTRACTION + PHOTOS — La Centrale Autocentre     ║
 * ║                                                          ║
 * ║  1. Ouvrir Chrome sur https://pros.lacentrale.fr/C054723 ║
 * ║  2. Appuyer sur F12 → onglet "Console"                  ║
 * ║  3. Coller tout ce script et appuyer sur Entrée          ║
 * ║  4. Attendre la fin (~5 minutes avec photos)             ║
 * ║  5. Le site est mis à jour avec photos + prix            ║
 * ╚══════════════════════════════════════════════════════════╝
 */

(async function extraireAutocentre() {

    const GITHUB_TOKEN = 'VOTRE_TOKEN_ICI'; // ← remplacer par votre token
    const GITHUB_REPO  = 'autocentresas/autocentre-site';
    const GITHUB_PATH  = 'vehicules.json';

    console.log('%c🚗 Extraction Autocentre démarrée…', 'color:#2563eb;font-size:14px;font-weight:bold');

    const sleep = ms => new Promise(r => setTimeout(r, ms));

    // ════════════════════════════════════════════════════════
    // 1. EXTRACTION DES VÉHICULES (toutes les pages)
    // ════════════════════════════════════════════════════════

    function extraireDepuisDoc(doc) {
        const cards = Array.from(doc.querySelectorAll('div.searchCard'));
        const vus = new Set();
        const res = [];
        for (const card of cards) {
            try {
                const a = card.querySelector('a[data-testid="vehicleCardV2"]');
                if (!a) continue;
                const href = a.getAttribute('href');
                if (!href || vus.has(href)) continue;
                vus.add(href);
                const idM  = href.match(/\/annonce\/(\d+)/);
                const id   = idM ? idM[1] : href.slice(-12);
                const url  = 'https://pros.lacentrale.fr' + href;
                const img  = card.querySelector('img');
                let photo  = img ? (img.getAttribute('src') || '') : '';
                photo = photo.replace(/size=\d+x\d+/, 'size=640x480');
                const titreEl = card.querySelector('[class*="vehiclecardV2_title"]');
                const titre   = titreEl ? titreEl.textContent.trim() : '';
                const subEl   = card.querySelector('[class*="vehiclecardV2_subTitle"]');
                const version = subEl ? subEl.textContent.trim() : '';
                const prixEl  = card.querySelector('[class*="vehiclecardV2_vehiclePrice__"]');
                const prix    = prixEl ? prixEl.textContent.trim() : '';
                const texts   = Array.from(card.querySelectorAll('[class*="Text_Text_body-medium"]'))
                                    .map(e => e.textContent.trim()).filter(t => t && t.length > 1);
                const annee  = texts.find(t => /^(19|20)\d{2}$/.test(t)) || '';
                const km     = texts.find(t => /\d[\d\s]*\s*km/i.test(t)) || '';
                const carb   = texts.find(t => /diesel|essence|hybride|electrique|électrique|gpl/i.test(t)) || '';
                const boite  = texts.find(t => /^auto$|^automatique$|^manuelle?$|^mec$/i.test(t.trim().toLowerCase())) || '';
                if (!titre && !prix) continue;
                res.push({ id, titre, version, url, photo, prix, km, annee, carburant: carb, boite });
            } catch(e) {}
        }
        return res;
    }

    async function chargerPage(pnum) {
        const url = `/C054723/index?freetext_conversationid=&options=&page=${pnum}&vertical=car`;
        try {
            const resp = await fetch(url, { credentials: 'include',
                headers: { 'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'fr-FR,fr;q=0.9' }
            });
            if (!resp.ok) return null;
            const html = await resp.text();
            if (!html.includes('searchCard') && html.includes('datadome')) return null;
            return html;
        } catch(e) { return null; }
    }

    function detecterMaxPage() {
        let max = 1;
        document.querySelectorAll('a[href*="page="]').forEach(a => {
            const m = (a.getAttribute('href') || '').match(/page=(\d+)/);
            if (m) { const n = parseInt(m[1]); if (n > max) max = n; }
        });
        return Math.max(max, 25);
    }

    // Page 1
    await sleep(500);
    const page1V = extraireDepuisDoc(document);
    const maxPage = detecterMaxPage();
    console.log(`  Page  1 : ${page1V.length} annonces | max détecté : ${maxPage}`);

    const tousTous = [...page1V];
    let blockeesConsec = 0;
    let videsConsec    = 0;

    for (let pnum = 2; pnum <= maxPage; pnum++) {
        await sleep(1200 + Math.random() * 1200);
        const html = await chargerPage(pnum);
        if (!html) {
            blockeesConsec++;
            if (blockeesConsec >= 3) { console.warn('  DataDome — arrêt'); break; }
            await sleep(5000);
            continue;
        }
        blockeesConsec = 0;
        const v = extraireDepuisDoc(new DOMParser().parseFromString(html, 'text/html'));
        tousTous.push(...v);
        console.log(`  Page ${String(pnum).padStart(2,' ')} : ${v.length} annonces | total : ${tousTous.length}`);
        if (v.length === 0) {
            videsConsec++;
            if (videsConsec >= 2) { console.log(`  Fin des annonces à la page ${pnum - 1}`); break; }
        } else {
            videsConsec = 0;
        }
    }

    // Dédoublonnage + nettoyage
    const vus = {};
    for (const v of tousTous) {
        if (!v.id || vus[v.id]) continue;
        v.prix = (v.prix || '').replace(/\s+/g, ' ').trim();
        if (v.prix && !v.prix.includes('€')) v.prix += ' €';
        const kmM = (v.km || '').match(/([\d\s]+)\s*km/i);
        if (kmM) v.km = kmM[0].trim();
        vus[v.id] = v;
    }
    const vehiculesFinaux = Object.values(vus);
    console.log(`%c📦 ${vehiculesFinaux.length} véhicules extraits`, 'color:#2563eb;font-weight:bold');

    if (!GITHUB_TOKEN || GITHUB_TOKEN === 'VOTRE_TOKEN_ICI') {
        console.warn('⚠️ Token GitHub manquant — ajoutez votre token.');
        return;
    }

    const authHdr = { 'Authorization': `token ${GITHUB_TOKEN}`, 'Content-Type': 'application/json' };

    // ════════════════════════════════════════════════════════
    // 2. TÉLÉCHARGEMENT DES PHOTOS depuis La Centrale
    //    (votre navigateur a les accès → ça marche ici)
    // ════════════════════════════════════════════════════════

    console.log('%c📸 Téléchargement des photos…', 'color:#2563eb;font-weight:bold');

    async function downloadPhotoBase64(photoUrl) {
        if (!photoUrl) return null;
        try {
            // Essai 1 : fetch direct (marche si votre IP est autorisée)
            const resp = await fetch(photoUrl, { credentials: 'omit', mode: 'cors' });
            if (resp.ok) {
                const blob   = await resp.blob();
                const base64 = await new Promise(res => {
                    const r = new FileReader();
                    r.onloadend = () => res(r.result.split(',')[1]);
                    r.readAsDataURL(blob);
                });
                return base64;
            }
        } catch(e) {}

        // Essai 2 : via <img> + canvas (avec cookies session)
        return new Promise(resolve => {
            const img    = new Image();
            const canvas = document.createElement('canvas');
            img.crossOrigin = 'use-credentials';
            img.onload = () => {
                try {
                    canvas.width  = img.naturalWidth  || 640;
                    canvas.height = img.naturalHeight || 480;
                    canvas.getContext('2d').drawImage(img, 0, 0);
                    resolve(canvas.toDataURL('image/jpeg', 0.82).split(',')[1]);
                } catch(e) { resolve(null); }
            };
            img.onerror = () => resolve(null);
            img.src = photoUrl + (photoUrl.includes('?') ? '&' : '?') + '_t=' + Date.now();
            setTimeout(() => resolve(null), 8000); // timeout 8s
        });
    }

    async function pushPhotoGitHub(vehiculeId, base64Data) {
        const remotePath = `photos/${vehiculeId}.jpg`;
        const apiUrl     = `https://api.github.com/repos/${GITHUB_REPO}/contents/${remotePath}`;
        // Essayer de créer sans SHA (nouveau fichier)
        const payload = { message: `📸 Photo ${vehiculeId}`, content: base64Data };
        try {
            const r = await fetch(apiUrl, { method: 'PUT', headers: authHdr, body: JSON.stringify(payload) });
            if (r.ok || r.status === 201) return true;
            if (r.status === 409 || r.status === 422) {
                // Fichier existe déjà → récupérer SHA et mettre à jour
                try {
                    const existing = await (await fetch(apiUrl, { headers: authHdr })).json();
                    const sha = existing.sha || '';
                    const r2  = await fetch(apiUrl, {
                        method: 'PUT', headers: authHdr,
                        body: JSON.stringify({ ...payload, sha })
                    });
                    return r2.ok;
                } catch(e) { return false; }
            }
            return false;
        } catch(e) { return false; }
    }

    // Télécharger + pousser par lots de 4
    let photosOk = 0;
    const BATCH  = 4;
    for (let i = 0; i < vehiculesFinaux.length; i += BATCH) {
        const lot = vehiculesFinaux.slice(i, i + BATCH);
        await Promise.all(lot.map(async v => {
            if (!v.photo) return;
            const b64 = await downloadPhotoBase64(v.photo);
            if (b64) {
                const ok = await pushPhotoGitHub(v.id, b64);
                if (ok) {
                    v.photo_local = `photos/${v.id}.jpg`;
                    photosOk++;
                }
            }
        }));
        if (i % 20 === 0 && i > 0) {
            console.log(`  Photos : ${photosOk} poussées (${i + BATCH}/${vehiculesFinaux.length})`);
        }
        await sleep(600); // pause entre les lots
    }
    console.log(`%c  ✓ ${photosOk}/${vehiculesFinaux.length} photos stockées sur GitHub`, 'color:green');

    // ════════════════════════════════════════════════════════
    // 3. PUSH vehicules.json
    // ════════════════════════════════════════════════════════

    const now     = new Date();
    const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${now.getFullYear()} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
    const data    = { derniere_maj: dateStr, vehicules: vehiculesFinaux };
    const jsonStr = JSON.stringify(data, null, 2);

    // Téléchargement local
    const dlA = Object.assign(document.createElement('a'), {
        href: URL.createObjectURL(new Blob([jsonStr], { type: 'application/json' })),
        download: 'vehicules.json'
    });
    dlA.click();

    console.log('📤 Push vehicules.json → GitHub…');
    try {
        const apiUrl = `https://api.github.com/repos/${GITHUB_REPO}/contents/${GITHUB_PATH}`;
        let sha = '';
        try { sha = (await (await fetch(apiUrl, { headers: authHdr })).json()).sha || ''; } catch(e) {}
        const encoded = btoa(unescape(encodeURIComponent(jsonStr)));
        const putR = await fetch(apiUrl, {
            method: 'PUT', headers: authHdr,
            body: JSON.stringify({ message: `🚗 ${vehiculesFinaux.length} véhicules + ${photosOk} photos — ${dateStr}`, content: encoded, sha })
        });
        if (putR.ok) {
            const sha2 = (await putR.json())?.commit?.sha?.slice(0, 10) || '?';
            console.log(`%c✅ Site mis à jour ! ${vehiculesFinaux.length} véhicules, ${photosOk} photos — commit ${sha2}`, 'color:green;font-weight:bold;font-size:13px');
            console.log('%c🌐 https://autocentresas.github.io/autocentre-site/', 'color:#2563eb');
        } else {
            console.error('❌ Erreur push JSON :', putR.status);
        }
    } catch(e) {
        console.error('❌ Erreur :', e);
    }

})();
