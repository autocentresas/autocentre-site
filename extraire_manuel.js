/**
 * ╔══════════════════════════════════════════════════════════╗
 * ║  SCRIPT EXTRACTION MANUELLE — La Centrale Autocentre     ║
 * ║                                                          ║
 * ║  1. Ouvrir Chrome sur https://pros.lacentrale.fr/C054723 ║
 * ║  2. Appuyer sur F12 → onglet "Console"                  ║
 * ║  3. Coller tout ce script et appuyer sur Entrée          ║
 * ║  4. Attendre la fin (~2 minutes)                         ║
 * ║  5. Le site est mis à jour automatiquement               ║
 * ╚══════════════════════════════════════════════════════════╝
 *
 * NOTE : Ce script reste sur la page 1 et charge les autres
 *        pages en arrière-plan (pas de rechargement = le
 *        script ne disparaît pas).
 */

(async function extraireAutocentre() {

    const GITHUB_TOKEN = 'VOTRE_TOKEN_ICI'; // ← remplacer par votre token
    const GITHUB_REPO  = 'autocentresas/autocentre-site';
    const GITHUB_PATH  = 'vehicules.json';
    const DEALER_ID    = 'C054723';

    console.log('%c🚗 Extraction Autocentre démarrée…', 'color:#2563eb;font-size:14px;font-weight:bold');

    // ── Attente simple ───────────────────────────────────────────────────────
    const sleep = ms => new Promise(r => setTimeout(r, ms));

    // ── Extraire les véhicules depuis un document HTML ────────────────────────
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

                const idM = href.match(/\/annonce\/(\d+)/);
                const id  = idM ? idM[1] : href.slice(-12);
                const url = 'https://pros.lacentrale.fr' + href;

                const img   = card.querySelector('img');
                let photo   = img ? (img.getAttribute('src') || '') : '';
                photo = photo.replace(/size=\d+x\d+/, 'size=640x480');

                const titreEl = card.querySelector('[class*="vehiclecardV2_title"]');
                const titre   = titreEl ? titreEl.textContent.trim() : '';

                const subEl   = card.querySelector('[class*="vehiclecardV2_subTitle"]');
                const version = subEl ? subEl.textContent.trim() : '';

                const prixEl  = card.querySelector('[class*="vehiclecardV2_vehiclePrice__"]');
                const prix    = prixEl ? prixEl.textContent.trim() : '';

                const texts   = Array.from(card.querySelectorAll('[class*="Text_Text_body-medium"]'))
                                    .map(el => el.textContent.trim()).filter(t => t && t.length > 1);

                const annee  = texts.find(t => /^(19|20)\d{2}$/.test(t))  || '';
                const km     = texts.find(t => /\d[\d\s]*\s*km/i.test(t)) || '';
                const carb   = texts.find(t => /diesel|essence|hybride|electrique|électrique|gpl/i.test(t)) || '';
                const boite  = texts.find(t => /^auto$|^automatique$|^manuelle?$|^mec$/i.test(t.trim().toLowerCase())) || '';

                if (!titre && !prix) continue;
                res.push({ id, titre, version, url, photo, prix, km, annee, carburant: carb, boite });
            } catch(e) {}
        }
        return res;
    }

    // ── Charger une page en arrière-plan (fetch = garde le script en vie) ─────
    async function chargerPage(pnum) {
        const url = `/C054723/index?freetext_conversationid=&options=&page=${pnum}&vertical=car`;
        try {
            const resp = await fetch(url, {
                credentials: 'include',   // envoie les cookies DataDome automatiquement
                headers: {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'fr-FR,fr;q=0.9',
                    'Cache-Control': 'no-cache',
                }
            });
            if (!resp.ok) {
                console.warn(`  Page ${pnum} : HTTP ${resp.status}`);
                return null;
            }
            const html = await resp.text();
            // Vérifier que ce n'est pas une page DataDome vide
            if (!html.includes('searchCard') && html.includes('datadome')) {
                console.warn(`  Page ${pnum} : bloquée par DataDome`);
                return null;
            }
            return html;
        } catch(e) {
            console.error(`  Page ${pnum} : erreur fetch`, e);
            return null;
        }
    }

    // ── Parser HTML en document ───────────────────────────────────────────────
    function parseHTML(html) {
        const parser = new DOMParser();
        return parser.parseFromString(html, 'text/html');
    }

    // ── Détecter le nombre de pages depuis la page actuelle ───────────────────
    function detecterMaxPage() {
        let max = 1;
        document.querySelectorAll('a[href*="page="]').forEach(a => {
            const m = (a.getAttribute('href') || '').match(/page=(\d+)/);
            if (m) {
                const n = parseInt(m[1]);
                if (n > max) max = n;
            }
        });
        return max;
    }

    // ═════════════════════════════════════════════════════════════════════════
    // EXTRACTION PRINCIPALE
    // ═════════════════════════════════════════════════════════════════════════

    // Page 1 : déjà chargée dans le navigateur
    await sleep(500);
    const page1Vehicules = extraireDepuisDoc(document);
    const maxPage = detecterMaxPage();
    console.log(`  Page  1 : ${page1Vehicules.length} annonces | ${maxPage} pages au total`);

    const tousTous = [...page1Vehicules];

    // Pages 2 à maxPage : via fetch (arrière-plan)
    let blockeesConsec = 0;
    for (let pnum = 2; pnum <= maxPage; pnum++) {
        await sleep(1500 + Math.random() * 1500); // pause 1.5-3s entre pages

        const html = await chargerPage(pnum);
        if (!html) {
            blockeesConsec++;
            if (blockeesConsec >= 3) {
                console.warn('  3 pages bloquées consécutivement — arrêt');
                break;
            }
            await sleep(5000); // pause supplémentaire si bloqué
            continue;
        }
        blockeesConsec = 0;

        const doc      = parseHTML(html);
        const vehicules = extraireDepuisDoc(doc);

        // Si 0 résultats via les sélecteurs HTML (page peut-être rendue côté client)
        // → essayer de trouver les données JSON injectées dans la page (Next.js __NEXT_DATA__)
        let vehiculesPage = vehicules;
        if (vehiculesPage.length === 0) {
            const nextDataEl = doc.querySelector('#__NEXT_DATA__');
            if (nextDataEl) {
                try {
                    const nextData = JSON.parse(nextDataEl.textContent);
                    // Chercher les annonces dans le JSON Next.js (structure variable)
                    const annonces = nextData?.props?.pageProps?.searchResult?.items
                                  || nextData?.props?.pageProps?.listings
                                  || nextData?.props?.pageProps?.ads
                                  || [];
                    for (const item of annonces) {
                        try {
                            vehiculesPage.push({
                                id:        String(item.id || item.adId || ''),
                                titre:     item.makeName ? `${item.makeName} ${item.modelName || ''}`.trim() : (item.title || ''),
                                version:   item.versionName || item.version || '',
                                url:       item.url ? 'https://pros.lacentrale.fr' + item.url : '',
                                photo:     item.photos?.[0]?.url || item.mainPhotoUrl || '',
                                prix:      item.price ? String(item.price) : '',
                                km:        item.mileage ? String(item.mileage) + ' km' : '',
                                annee:     item.year ? String(item.year) : '',
                                carburant: item.fuelType || '',
                                boite:     item.gearboxType || ''
                            });
                        } catch(e) {}
                    }
                } catch(e) {}
            }
        }

        tousTous.push(...vehiculesPage);
        console.log(`  Page ${String(pnum).padStart(2,' ')} : ${vehiculesPage.length} annonces | total : ${tousTous.length}`);

        if (vehiculesPage.length === 0) {
            console.log(`  Page ${pnum} vide — fin`);
            break;
        }
    }

    // ── Dédoublonnage ─────────────────────────────────────────────────────────
    const vus = {};
    for (const v of tousTous) {
        if (!v.id || vus[v.id]) continue;
        // Nettoyer prix
        v.prix = (v.prix || '').replace(/\s+/g, ' ').trim();
        if (v.prix && !v.prix.includes('€')) v.prix += ' €';
        // Nettoyer km
        const kmM = (v.km || '').match(/([\d\s]+)\s*km/i);
        if (kmM) v.km = kmM[0].trim();
        vus[v.id] = v;
    }
    const vehiculesFinaux = Object.values(vus);

    // ── Construire vehicules.json ──────────────────────────────────────────────
    const now     = new Date();
    const dateStr = `${String(now.getDate()).padStart(2,'0')}/${String(now.getMonth()+1).padStart(2,'0')}/${now.getFullYear()} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
    const data    = { derniere_maj: dateStr, vehicules: vehiculesFinaux };
    const jsonStr = JSON.stringify(data, null, 2);

    console.log(`%c📦 ${vehiculesFinaux.length} véhicules au total`, 'color:#2563eb;font-weight:bold');

    // ── Télécharger vehicules.json en local ───────────────────────────────────
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const dlUrl = URL.createObjectURL(blob);
    const dlA   = Object.assign(document.createElement('a'), { href: dlUrl, download: 'vehicules.json' });
    dlA.click();
    URL.revokeObjectURL(dlUrl);
    console.log('%c💾 vehicules.json téléchargé localement', 'color:gray');

    // ── Push vers GitHub ───────────────────────────────────────────────────────
    if (!GITHUB_TOKEN || GITHUB_TOKEN === 'VOTRE_TOKEN_ICI') {
        console.warn('⚠️ Token GitHub non configuré — fichier téléchargé mais site non mis à jour.');
        console.warn('   Remplacez VOTRE_TOKEN_ICI dans le script par votre token.');
        return;
    }

    console.log('📤 Envoi vers GitHub…');
    try {
        const apiUrl  = `https://api.github.com/repos/${GITHUB_REPO}/contents/${GITHUB_PATH}`;
        const authHdr = { 'Authorization': `token ${GITHUB_TOKEN}`, 'Content-Type': 'application/json' };

        let sha = '';
        try {
            const r = await fetch(apiUrl, { headers: authHdr });
            if (r.ok) sha = (await r.json()).sha || '';
        } catch(e) {}

        const encoded = btoa(unescape(encodeURIComponent(jsonStr)));
        const payload = { message: `🚗 ${vehiculesFinaux.length} véhicules — ${dateStr}`, content: encoded, sha };

        const putResp = await fetch(apiUrl, { method: 'PUT', headers: authHdr, body: JSON.stringify(payload) });
        if (putResp.ok) {
            const commitSha = (await putResp.json())?.commit?.sha?.slice(0, 10) || '?';
            console.log(`%c✅ Site mis à jour — commit ${commitSha}`, 'color:green;font-weight:bold');
            console.log('%c🌐 https://autocentresas.github.io/autocentre-site/', 'color:#2563eb');
        } else {
            console.error('❌ Erreur GitHub :', putResp.status, await putResp.text());
        }
    } catch(e) {
        console.error('❌ Erreur push :', e);
    }

})();
