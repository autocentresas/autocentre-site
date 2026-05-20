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

/* ===== STOCK DYNAMIQUE — vehicules.json ===== */
(function chargerStock() {
  const section = document.getElementById('stock-section');
  const grid    = document.getElementById('stockGrid');
  const countEl = document.getElementById('stock-count');
  const majEl   = document.getElementById('stock-maj');
  if (!section || !grid) return;

  fetch('vehicules.json?_=' + Date.now())
    .then(r => r.json())
    .then(data => {
      const liste = data.vehicules || [];
      if (!liste.length) return; // reste caché si vide

      section.style.display = 'block';
      countEl.textContent   = liste.length + ' véhicule' + (liste.length > 1 ? 's' : '');
      if (data.derniere_maj) {
        majEl.textContent = 'Mis à jour le ' + data.derniere_maj;
      }

      // Trie du plus récent au plus ancien (ordre d'insertion)
      grid.innerHTML = liste.map((v, i) => {
        const isNew   = i < 3;
        const details = [v.annee, v.km].filter(Boolean).join(' · ');
        const imgHtml = v.photo
          ? `<img src="${escHtml(v.photo)}" alt="${escHtml(v.titre)}" loading="lazy"
               onerror="this.parentElement.innerHTML='<div class=stock-img-placeholder><svg viewBox=\\'0 0 48 48\\' fill=\\'none\\'><circle cx=\\'24\\' cy=\\'24\\' r=\\'20\\' stroke=\\'currentColor\\' stroke-width=\\'2\\'/><path d=\\'M14 30l6-10 5 7 3-4 6 7H14z\\' stroke=\\'currentColor\\' stroke-width=\\'2\\'/></svg></div>'" />`
          : `<div class="stock-img-placeholder"><svg viewBox="0 0 48 48" fill="none"><circle cx="24" cy="24" r="20" stroke="currentColor" stroke-width="2"/><path d="M14 30l6-10 5 7 3-4 6 7H14z" stroke="currentColor" stroke-width="2"/></svg></div>`;

        return `
          <a class="stock-card" href="${escHtml(v.url || 'https://pros.lacentrale.fr/C054723')}" target="_blank" rel="noopener">
            <div class="stock-img">
              ${imgHtml}
              ${v.prix ? `<span class="stock-price">${escHtml(v.prix)}</span>` : ''}
              ${isNew   ? `<span class="stock-badge-new">Nouveau</span>` : ''}
            </div>
            <div class="stock-info">
              <h4>${escHtml(v.titre || 'Véhicule')}</h4>
              ${details ? `<p>${escHtml(details)}</p>` : ''}
              <span class="stock-info-link">Voir sur La Centrale →</span>
            </div>
          </a>`;
      }).join('');

      // Active les animations reveal sur les nouvelles cartes
      document.querySelectorAll('.stock-card').forEach(el => {
        el.classList.add('reveal-up');
        revealObserver.observe(el);
      });
    })
    .catch(() => {}); // JSON absent = section reste cachée
})();

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

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
