(function () {
  const FAQ = [
    {
      keys: ["horaire", "heure", "ouvert", "ouverture", "fermé", "fermeture", "quand"],
      answer: "🕐 Nous sommes ouverts du lundi au samedi de 10h à 19h, sans rendez-vous."
    },
    {
      keys: ["adresse", "où", "situé", "trouver", "localisation", "venir", "plan", "brie"],
      answer: "📍 Nous sommes situés à Brie-Comte-Robert (77170), en Seine-et-Marne. Retrouvez-nous facilement via Google Maps en cherchant « Autocentre Brie-Comte-Robert »."
    },
    {
      keys: ["téléphone", "appeler", "numéro", "tel", "phone", "joindre"],
      answer: "📞 Vous pouvez nous appeler au <strong>07 49 44 07 63</strong>, du lundi au samedi de 10h à 19h."
    },
    {
      keys: ["mail", "email", "courriel", "gmail", "écrire"],
      answer: "✉️ Notre adresse e-mail : <strong>autocentresas@gmail.com</strong>. Nous répondons rapidement !"
    },
    {
      keys: ["contact", "contacter", "message", "renseignement"],
      answer: "📬 Pour nous contacter : appelez le <strong>07 49 44 07 63</strong> ou écrivez à <strong>autocentresas@gmail.com</strong>. Vous pouvez aussi remplir le formulaire de contact en bas de la page."
    },
    {
      keys: ["véhicule", "voiture", "stock", "dispo", "disponible", "acheter", "vente", "vendre"],
      answer: "🚗 Nous avons plus de 170 véhicules en stock, toutes marques confondues. Consultez notre catalogue directement sur cette page, ou venez sans rendez-vous !"
    },
    {
      keys: ["prix", "tarif", "combien", "coût", "budget"],
      answer: "💰 Les prix sont affichés sur chaque véhicule dans notre catalogue. Pour une offre personnalisée ou un financement, contactez-nous au <strong>07 49 44 07 63</strong>."
    },
    {
      keys: ["reprise", "reprendre", "échange", "racheter"],
      answer: "🔄 Oui, nous reprenons votre véhicule ! Contactez-nous avec les infos de votre voiture (marque, modèle, kilométrage, année) et nous vous ferons une offre."
    },
    {
      keys: ["garantie", "garanti", "panne", "sav"],
      answer: "🛡️ Tous nos véhicules sont vendus avec une garantie. Renseignez-vous auprès de nos conseillers pour les détails selon le véhicule choisi."
    },
    {
      keys: ["financement", "crédit", "mensualité", "prêt", "leasing"],
      answer: "💳 Nous proposons des solutions de financement adaptées à votre budget. Contactez-nous au <strong>07 49 44 07 63</strong> pour étudier votre dossier."
    },
    {
      keys: ["livraison", "livrer", "domicile", "transport"],
      answer: "🚚 Nous pouvons vous renseigner sur les options de livraison. Contactez-nous directement pour en discuter."
    },
    {
      keys: ["essai", "essayer", "tester", "test drive"],
      answer: "🔑 Venez tester nos véhicules directement chez nous, sans rendez-vous, du lundi au samedi de 10h à 19h à Brie-Comte-Robert."
    },
    {
      keys: ["bonjour", "salut", "hello", "bonsoir", "coucou"],
      answer: "👋 Bonjour ! Je suis Arthur, l'assistant Autocentre. Comment puis-je vous aider ?"
    },
    {
      keys: ["merci", "super", "parfait", "nickel", "ok", "top"],
      answer: "😊 Avec plaisir ! N'hésitez pas si vous avez d'autres questions."
    },
    {
      keys: ["arthur", "qui es-tu", "qui êtes-vous", "bot", "assistant"],
      answer: "🤖 Je suis Arthur, l'assistant virtuel d'Autocentre. Je peux vous renseigner sur nos véhicules, nos horaires, nos services et bien plus encore !"
    }
  ];

  const SUGGESTION_QUESTIONS = {
    horaires:  "Quels sont vos horaires ?",
    adresse:   "Où êtes-vous situés ?",
    vehicules: "Quels véhicules avez-vous en stock ?",
    contact:   "Comment vous contacter ?",
    reprise:   "Faites-vous la reprise de véhicules ?",
    garantie:  "Proposez-vous une garantie ?"
  };

  const DEFAULT = "Je n'ai pas bien compris votre question 😅 Vous pouvez nous appeler au <strong>07 49 44 07 63</strong> ou écrire à <strong>autocentresas@gmail.com</strong> — Arthur vous redirige vers les humains !";

  function normalize(str) {
    return str.toLowerCase()
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9\s]/g, " ");
  }

  function getAnswer(question) {
    const q = normalize(question);
    for (const entry of FAQ) {
      if (entry.keys.some(k => q.includes(normalize(k)))) {
        return entry.answer;
      }
    }
    return DEFAULT;
  }

  const bubble    = document.getElementById("chat-bubble");
  const win       = document.getElementById("chat-window");
  const messages  = document.getElementById("chat-messages");
  const input     = document.getElementById("chat-input");
  const sendBtn   = document.getElementById("chat-send");
  const iconOpen  = document.getElementById("chat-icon-open");
  const iconClose = document.getElementById("chat-icon-close");

  let isOpen = false;

  function toggleChat() {
    isOpen = !isOpen;
    win.classList.toggle("open", isOpen);
    win.setAttribute("aria-hidden", !isOpen);
    iconOpen.style.display  = isOpen ? "none" : "";
    iconClose.style.display = isOpen ? "" : "none";
    if (isOpen) input.focus();
  }

  function addMessage(text, role) {
    const div = document.createElement("div");
    div.className = "chat-msg " + role;
    div.innerHTML = text;
    const sugg = document.getElementById("chat-suggestions");
    if (sugg) sugg.remove();
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  function send(text) {
    text = text.trim();
    if (!text) return;
    addMessage(escHtml(text), "user");
    input.value = "";
    const typing = document.createElement("div");
    typing.className = "chat-msg bot";
    typing.textContent = "…";
    messages.appendChild(typing);
    messages.scrollTop = messages.scrollHeight;
    setTimeout(() => {
      typing.remove();
      addMessage(getAnswer(text), "bot");
    }, 500);
  }

  function escHtml(s) {
    return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }

  bubble.addEventListener("click", toggleChat);
  bubble.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") toggleChat(); });
  sendBtn.addEventListener("click", () => send(input.value));
  input.addEventListener("keydown", e => { if (e.key === "Enter") send(input.value); });

  document.querySelectorAll(".chat-suggest").forEach(btn => {
    btn.addEventListener("click", () => {
      send(SUGGESTION_QUESTIONS[btn.dataset.q] || btn.textContent);
    });
  });
})();