/* ===== NAVBAR SCROLL ===== */
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  navbar.classList.toggle('scrolled', window.scrollY > 40);
}, { passive: true });

/* ===== MOBILE MENU ===== */
const burger = document.getElementById('burger');
const navLinks = document.getElementById('nav-links');

burger.addEventListener('click', () => {
  const isOpen = navLinks.classList.toggle('open');
  burger.classList.toggle('open', isOpen);
  burger.setAttribute('aria-expanded', isOpen);
});

navLinks.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => {
    navLinks.classList.remove('open');
    burger.classList.remove('open');
  });
});

/* ===== HERO SLIDER ===== */
(function initSlider() {
  const slides = document.querySelectorAll('.slide');
  const dots   = document.querySelectorAll('.dot');
  let current  = 0;
  let timer    = null;
  const INTERVAL = 4500;

  function goTo(index) {
    slides[current].classList.remove('active');
    dots[current].classList.remove('active');
    current = (index + slides.length) % slides.length;
    slides[current].classList.add('active');
    dots[current].classList.add('active');
  }

  function next() { goTo(current + 1); }

  function start() { timer = setInterval(next, INTERVAL); }
  function stop()  { clearInterval(timer); }

  dots.forEach(dot => {
    dot.addEventListener('click', () => {
      stop();
      goTo(parseInt(dot.dataset.index, 10));
      start();
    });
  });

  const hero = document.getElementById('hero');
  hero.addEventListener('mouseenter', stop);
  hero.addEventListener('mouseleave', start);

  start();
})();

/* ===== SCROLL REVEAL ===== */
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
      revealObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

document.querySelectorAll('.reveal-up, .reveal-left, .reveal-right').forEach(el => {
  revealObserver.observe(el);
});

/* ===== COUNT-UP ANIMATION ===== */
function animateCount(el) {
  const target   = parseInt(el.dataset.target, 10);
  const duration = 1800;
  const start    = performance.now();

  function step(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased    = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.floor(eased * target);
    if (progress < 1) requestAnimationFrame(step);
    else el.textContent = target;
  }
  requestAnimationFrame(step);
}

const countObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      animateCount(entry.target);
      countObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.5 });

document.querySelectorAll('.count-up').forEach(el => countObserver.observe(el));

/* ===== STOCK DYNAMIQUE — vehicules.json + vehicules_vendus.json ===== */
(function chargerStock() {
  const section   = document.getElementById('stock-section');
  const grid      = document.getElementById('stockGrid');
  const countEl   = document.getElementById('stock-count');
  const vendusEl  = document.getElementById('vendus-count');
  const majEl     = document.getElementById('stock-maj');
  const tabs      = document.querySelectorAll('.stock-tab');
  if (!section || !grid) return;

  let listeStock  = [];
  let listeVendus = [];
  let ongletActif = 'stock';

  function renderGrid(liste, isVendus) {
    if (!liste.length) {
      grid.innerHTML = '<p class="stock-empty">Aucun véhicule.</p>';
      return;
    }
    grid.innerHTML = liste.map((v, i) => {
      const isNew   = !isVendus && i < 3;
      const details = [v.annee, v.km, v.carburant].filter(Boolean).join(' · ');
      const imgSrc  = v.photo_local || v.photo || '';
      const imgFb   = v.photo_local && v.photo ? escHtml(v.photo) : '';
      const imgHtml = imgSrc
        ? `<img src="${escHtml(imgSrc)}" alt="${escHtml(v.titre)}" loading="lazy" referrerpolicy="no-referrer" onerror="stockImgErr(this,'${imgFb}')" />`
        : `<div class="stock-img-placeholder"><svg viewBox="0 0 48 48" fill="none"><circle cx="24" cy="24" r="20" stroke="currentColor" stroke-width="2"/><path d="M14 30l6-10 5 7 3-4 6 7H14z" stroke="currentColor" stroke-width="2"/></svg></div>`;

      return `
        <a class="stock-card${isVendus ? ' stock-card-vendu' : ''}" href="${escHtml(v.url || 'https://pros.lacentrale.fr/C054723')}" target="_blank" rel="noopener">
          <div class="stock-img">
            ${imgHtml}
            ${v.prix ? `<span class="stock-price">${escHtml(v.prix)}</span>` : ''}
            ${isNew   ? `<span class="stock-badge-new">Nouveau</span>` : ''}
          </div>
          <div class="stock-info">
            ${isVendus ? `<span class="stock-badge-vendu-stars">★★★★★</span>` : ''}
            <h4>${escHtml(v.titre || 'Véhicule')}</h4>
            ${details ? `<p>${escHtml(details)}</p>` : ''}
            <span class="stock-info-link">${isVendus ? 'Voir l\'annonce →' : 'Voir sur La Centrale →'}</span>
          </div>
        </a>`;
    }).join('');

    document.querySelectorAll('.stock-card').forEach(el => {
      el.classList.add('reveal-up');
      revealObserver.observe(el);
    });
  }

  // Onglets
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      ongletActif = tab.dataset.tab;
      if (ongletActif === 'stock') renderGrid(listeStock, false);
      else renderGrid(listeVendus, true);
    });
  });

  // Chargement des deux JSON en parallèle
  Promise.all([
    fetch('vehicules.json?_=' + Date.now()).then(r => r.json()).catch(() => ({ vehicules: [] })),
    fetch('vehicules_vendus.json?_=' + Date.now()).then(r => r.json()).catch(() => ({ vehicules: [] }))
  ]).then(([dataStock, dataVendus]) => {
    listeStock  = dataStock.vehicules  || [];
    listeVendus = dataVendus.vehicules || [];

    if (!listeStock.length && !listeVendus.length) return;

    section.style.display = 'block';
    if (countEl)  countEl.textContent  = listeStock.length  + ' véhicule' + (listeStock.length  > 1 ? 's' : '');
    if (vendusEl) vendusEl.textContent = listeVendus.length + ' véhicule' + (listeVendus.length > 1 ? 's' : '');
    if (dataStock.derniere_maj && majEl) majEl.textContent = 'Mis à jour le ' + dataStock.derniere_maj;

    renderGrid(listeStock, false);
  });
})();

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* Gestion erreur photo : tente l'URL La Centrale en fallback, sinon placeholder */
function stockImgErr(img, fallbackUrl) {
  const placeholder = '<div class="stock-img-placeholder"><svg viewBox="0 0 48 48" fill="none"><circle cx="24" cy="24" r="20" stroke="currentColor" stroke-width="2"/><path d="M14 30l6-10 5 7 3-4 6 7H14z" stroke="currentColor" stroke-width="2"/></svg></div>';
  if (fallbackUrl) {
    img.referrerPolicy = 'no-referrer';
    img.onerror = function() { this.outerHTML = placeholder; };
    img.src = fallbackUrl;
  } else {
    img.outerHTML = placeholder;
  }
}

/* ===== THEME TOGGLE ===== */
(function() {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;
  if (localStorage.getItem('theme') === 'light') {
    document.body.classList.add('light');
    btn.style.color = '#1d4ed8';
  }
  btn.addEventListener('click', () => {
    const isLight = document.body.classList.toggle('light');
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
    btn.style.color = isLight ? '#1d4ed8' : '';
  });
})();

/* ===== CONTACT FORM (simulation) ===== */
const form = document.getElementById('contact-form');
if (form) {
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Envoi en cours…';

    setTimeout(() => {
      form.innerHTML = `
        <div class="form-success active">
          <svg viewBox="0 0 48 48" fill="none">
            <circle cx="24" cy="24" r="22" stroke="currentColor" stroke-width="2"/>
            <path d="M14 24l8 8 12-14" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <h3>Message envoyé !</h3>
          <p>Nous vous répondrons dans les plus brefs délais.<br />
          Vous pouvez aussi nous appeler au <a href="tel:+33749440763" style="color:var(--blue-light)">07 49 44 07 63</a>.</p>
        </div>`;
    }, 1200);
  });
}

/* ===== ACTIVE NAV LINK ON SCROLL ===== */
const sections   = document.querySelectorAll('section[id]');
const navAnchors = document.querySelectorAll('.nav-links a[href^="#"]');

const sectionObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const id = entry.target.getAttribute('id');
      navAnchors.forEach(a => {
        a.style.color = a.getAttribute('href') === `#${id}` ? 'var(--white)' : '';
      });
    }
  });
}, { threshold: 0.4 });

sections.forEach(s => sectionObserver.observe(s));
