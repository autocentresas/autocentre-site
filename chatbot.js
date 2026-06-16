(function () {
  const FAQ = [
    {
      keys: ["horaire", "heure", "ouvert", "ouverture", "ferme", "fermeture", "quand", "matin", "soir", "samedi", "dimanche", "lundi", "weekend", "week-end", "jour"],
      answer: "🕐 Nous sommes ouverts du <strong>lundi au samedi de 10h à 19h</strong>, sans rendez-vous. Nous sommes fermés le dimanche."
    },
    {
      keys: ["adresse", "ou etes", "ou est", "situe", "trouver", "localisation", "venir", "plan", "brie", "brie-comte", "77", "seine", "marne", "comment venir", "comment acceder", "itineraire", "gps", "maps", "google maps"],
      answer: "📍 Nous sommes situés à <strong>Brie-Comte-Robert (77170)</strong>, en Seine-et-Marne. Cherchez « Autocentre Brie-Comte-Robert » sur Google Maps pour l'itinéraire."
    },
    {
      keys: ["telephone", "appeler", "numero", "tel", "phone", "joindre", "appel", "vous appeler", "vous joindre", "vous contacter par telephone"],
      answer: "📞 Vous pouvez nous appeler au <strong>07 49 44 07 63</strong>, du lundi au samedi de 10h à 19h."
    },
    {
      keys: ["mail", "email", "courriel", "gmail", "ecrire", "envoyer un mail", "envoyer un message", "par email", "par mail"],
      answer: "✉️ Notre adresse e-mail : <strong>autocentresas@gmail.com</strong>. Nous répondons rapidement !"
    },
    {
      keys: ["contact", "contacter", "prendre contact", "vous contacter", "vous joindre", "renseignement", "information", "renseigner", "question", "demande"],
      answer: "📬 Pour nous contacter : appelez le <strong>07 49 44 07 63</strong> ou écrivez à <strong>autocentresas@gmail.com</strong>. Vous pouvez aussi utiliser le formulaire de contact en bas de la page."
    },
    {
      keys: ["vehicule", "voiture", "stock", "dispo", "disponible", "acheter", "vente", "vendre", "catalogue", "annonce", "modele", "marque", "occasion", "vo", "voir les voitures", "quelles voitures", "avez vous des voitures", "combien de voitures"],
      answer: "🚗 Nous avons plus de <strong>170 véhicules en stock</strong>, toutes marques confondues. Consultez notre catalogue directement sur cette page ou venez sans rendez-vous !"
    },
    {
      keys: ["prix", "tarif", "combien", "cout", "budget", "combien ca coute", "quel prix", "pas cher", "moins cher", "fourchette", "gamme de prix"],
      answer: "💰 Les prix sont affichés sur chaque véhicule dans notre catalogue. Pour une offre personnalisée, contactez-nous au <strong>07 49 44 07 63</strong>."
    },
    {
      keys: ["reprise", "reprendre", "echange", "racheter", "vous reprenez", "vous rachetez", "reprendre mon vehicule", "reprendre ma voiture", "echange vehicule", "racheter mon vehicule", "vendre ma voiture"],
      answer: "🔄 Oui, nous reprenons votre véhicule à condition qu'il soit à <strong>moins de 180 000 km et moins de 10 ans</strong> ! Contactez-nous avec les infos de votre voiture (marque, modèle, km, année)."
    },
    {
      keys: ["garantie", "garanti", "panne", "sav", "vous garantissez", "vehicule garanti", "garantie incluse", "combien de temps garantie", "duree garantie"],
      answer: "🛡️ Tous nos véhicules sont vendus avec une garantie possible <strong>jusqu'à 24 mois</strong>. Renseignez-vous auprès de nos conseillers pour les détails."
    },
    {
      keys: ["financement", "credit", "mensualite", "pret", "leasing", "financements", "vous faites des financements", "proposez vous un financement", "financer", "payer en plusieurs fois", "facilite de paiement", "paiement echelonne"],
      answer: "💳 Nous ne proposons pas de financement. Le paiement s'effectue en une seule fois. Pour toute question, appelez-nous au <strong>07 49 44 07 63</strong>."
    },
    {
      keys: ["livraison", "livrer", "domicile", "transport", "vous livrez", "livraison possible", "livrer le vehicule", "amener la voiture"],
      answer: "🚚 Contactez-nous directement au <strong>07 49 44 07 63</strong> pour discuter des options de livraison."
    },
    {
      keys: ["essai", "essayer", "tester", "test drive", "faire un essai", "essai routier", "essayer une voiture", "tester un vehicule"],
      answer: "🔑 Venez tester nos véhicules directement chez nous, <strong>sans rendez-vous</strong>, du lundi au samedi de 10h à 19h à Brie-Comte-Robert."
    },
    {
      keys: ["rendez-vous", "rdv", "rendez vous", "appointment", "prendre rdv", "sans rdv", "faut il un rdv", "besoin rdv"],
      answer: "📅 Pas besoin de rendez-vous ! Venez directement chez nous du <strong>lundi au samedi de 10h à 19h</strong>."
    },
    {
      keys: ["bonjour", "salut", "hello", "bonsoir", "coucou", "bonne journee", "bonne soiree", "hey"],
      answer: "👋 Bonjour ! Je suis <strong>Arthur</strong>, l'assistant Autocentre. Comment puis-je vous aider ?"
    },
    {
      keys: ["merci", "super", "parfait", "nickel", "ok merci", "top merci", "c est tout", "bonne journee"],
      answer: "😊 Avec plaisir ! N'hésitez pas si vous avez d'autres questions. Bonne journée !"
    },
    {
      keys: ["arthur", "qui es tu", "qui etes vous", "bot", "assistant", "robot", "intelligence artificielle", "ia"],
      answer: "🤖 Je suis <strong>Arthur</strong>, l'assistant virtuel d'Autocentre ! Je peux vous renseigner sur nos véhicules, horaires, services et plus encore. Pour une question complexe, contactez-nous au <strong>07 49 44 07 63</strong>."
    },
    {
      keys: ["carte grise", "immatriculation", "homologation", "controle technique"],
      answer: "📄 Nous vous accompagnons dans les démarches administratives. Contactez-nous au <strong>07 49 44 07 63</strong> pour plus d'informations."
    },
    {
      keys: ["kilometrage", "km", "kilom", "kilométrage", "combien de km"],
      answer: "🔢 Le kilométrage de chaque véhicule est indiqué sur les fiches dans notre catalogue. Venez vérifier sur place ou appelez le <strong>07 49 44 07 63</strong>."
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

  const DEFAULT = "Je n'ai pas bien compris votre question 😅 Vous pouvez nous appeler au <strong>07 49 44 07 63</strong> ou écrire à <strong>autocentresas@gmail.com</strong> et on vous répondra avec plaisir !";

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