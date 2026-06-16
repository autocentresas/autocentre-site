(function () {
  const FAQ = [
    {
      keys: ["horaire", "heure", "ouvert", "ouverture", "ferm", "fermeture", "quand", "matin", "soir", "samedi", "dimanche", "lundi", "semaine", "week", "weekend", "jour", "ouvre", "ferme", "plage horaire", "a quelle heure", "vous ouvrez", "vous fermez", "c est ouvert", "c est ferm"],
      answer: "🕐 Nous sommes ouverts du <strong>lundi au samedi de 10h à 19h</strong>, sans rendez-vous. Fermés le dimanche."
    },
    {
      keys: ["adresse", "ou etes", "ou vous", "situe", "trouver", "localisation", "venir", "plan", "brie", "77", "seine", "marne", "comment venir", "ou se trouve", "ou est", "chemin", "itineraire", "gps", "maps", "trajet"],
      answer: "📍 Nous sommes situés au <strong>2 rue Léonard de Vinci, 77170 Brie-Comte-Robert</strong> (Seine-et-Marne). Cherchez « Autocentre Brie-Comte-Robert » sur Google Maps !"
    },
    {
      keys: ["telephone", "appeler", "numero", "tel", "phone", "joindre", "rappeler", "appel", "sonner", "composer", "je peux appeler", "on peut appeler", "quel est votre numero"],
      answer: "📞 Vous pouvez nous appeler au <strong>07 49 44 07 63</strong>, du lundi au samedi de 10h à 19h."
    },
    {
      keys: ["mail", "email", "courriel", "gmail", "ecrire", "envoyer", "message ecrit", "adresse mail", "adresse email", "par mail", "par email", "vous ecrire"],
      answer: "✉️ Notre adresse e-mail : <strong>autocentresas@gmail.com</strong>. Nous répondons rapidement !"
    },
    {
      keys: ["contacter", "contact", "renseignement", "informations", "info", "comment vous joindre", "prendre contact", "vous parler", "parler a quelqu", "joindre", "echanger"],
      answer: "📬 Pour nous contacter : appelez le <strong>07 49 44 07 63</strong> ou écrivez à <strong>autocentresas@gmail.com</strong>. Vous pouvez aussi remplir le formulaire de contact en bas de la page."
    },
    {
      keys: ["vehicule", "voiture", "stock", "dispo", "disponible", "acheter", "vente", "vendre", "catalogue", "annonce", "occasion", "modele", "marque", "berline", "suv", "citadine", "coupé", "coupe", "break", "monospace", "4x4", "combien de voiture", "ce que vous avez", "ce que vous vendez", "qu est ce que vous vendez", "vous avez quoi"],
      answer: "🚗 Nous avons <strong>plus de 170 véhicules en stock</strong>, toutes marques confondues (Renault, Peugeot, Citroën, BMW, Mercedes, Audi...). Consultez notre catalogue sur cette page ou venez directement !"
    },
    {
      keys: ["prix", "tarif", "combien", "cout", "budget", "ca coute", "ca vaut", "valeur", "fourchette", "cher", "pas cher", "abordable", "c est combien", "quel prix", "a partir de"],
      answer: "💰 Les prix sont affichés sur chaque véhicule dans notre catalogue. Pour une offre personnalisée, appelez-nous au <strong>07 49 44 07 63</strong>."
    },
    {
      keys: ["reprise", "reprendre", "echange", "racheter", "rachat", "revendre", "vendre ma voiture", "vous reprenez", "vous rachetez", "mon ancienne voiture", "mon vehicule actuel", "part exchange", "estimation", "estimer"],
      answer: "🔄 Oui, nous reprenons votre véhicule ! Contactez-nous avec la marque, le modèle, le kilométrage et l'année — nous vous ferons une offre rapidement."
    },
    {
      keys: ["garantie", "garanti", "panne", "sav", "apres vente", "service apres", "probleme apres", "tombe en panne", "defaut", "reclamation", "avec garantie", "combien de temps garantie", "duree garantie"],
      answer: "🛡️ Tous nos véhicules sont vendus avec une garantie. Contactez-nous au <strong>07 49 44 07 63</strong> pour connaître les détails selon le véhicule choisi."
    },
    {
      keys: ["financement", "credit", "mensualite", "pret", "leasing", "loa", "lld", "payer en plusieurs", "echelonner", "apport", "taux", "paiement", "vous faites des credit", "vous faites du financement", "possibilite financement", "aide financement"],
      answer: "💳 Oui, nous proposons des <strong>solutions de financement</strong> adaptées à votre budget (crédit, LOA, LLD). Appelez-nous au <strong>07 49 44 07 63</strong> pour étudier votre dossier."
    },
    {
      keys: ["livraison", "livrer", "domicile", "transport", "vous livrez", "livraison a domicile", "livrez vous", "faire livrer", "recevoir la voiture", "amener la voiture"],
      answer: "🚚 Oui, nous proposons la livraison à domicile. Contactez-nous au <strong>07 49 44 07 63</strong> pour en discuter et connaître les conditions."
    },
    {
      keys: ["essai", "essayer", "tester", "test drive", "faire un essai", "faire un tour", "conduire avant", "je peux tester", "on peut essayer", "essai gratuit"],
      answer: "🔑 Bien sûr ! Venez tester nos véhicules directement chez nous, <strong>sans rendez-vous</strong>, du lundi au samedi de 10h à 19h."
    },
    {
      keys: ["carte grise", "immatriculation", "papier", "demarche", "administratif", "vous vous occupez", "vous faites la carte"],
      answer: "📄 Oui, nous nous occupons de la carte grise à votre place ! Ce service est proposé moyennant des frais administratifs. Vous repartez sans vous soucier de la paperasse."
    },
    {
      keys: ["rendez vous", "rdv", "prendre rendez", "reservation", "reserver", "faut il un rdv", "besoin rdv", "sans rendez"],
      answer: "✅ Aucun rendez-vous nécessaire ! Venez directement du <strong>lundi au samedi de 10h à 19h</strong> — tous nos véhicules sont disponibles immédiatement."
    },
    {
      keys: ["kilometrage", "kilometre", "km", "kilom", "combien de km", "faible km", "peu de km"],
      answer: "📊 Le kilométrage de chaque véhicule est indiqué dans notre catalogue. N'hésitez pas à nous appeler au <strong>07 49 44 07 63</strong> pour plus de détails sur un véhicule précis."
    },
    {
      keys: ["utilitaire", "fourgon", "camionnette", "fourgonnette", "van", "vito", "trafic", "transporter", "master", "transit", "professionnel", "pro"],
      answer: "🚐 Oui, nous avons une sélection d'<strong>utilitaires</strong> (fourgons, camionnettes, vans) adaptés aux professionnels. Venez voir notre stock ou consultez notre catalogue !"
    },
    {
      keys: ["bonjour", "salut", "hello", "bonsoir", "coucou", "hi", "bonne journee", "bonne soiree"],
      answer: "👋 Bonjour ! Bienvenue chez Autocentre. Je suis Arthur, comment puis-je vous aider ?"
    },
    {
      keys: ["merci", "super", "parfait", "nickel", "genial", "excellent", "impeccable", "top", "cool", "tres bien", "bonne journee"],
      answer: "😊 Avec plaisir ! N'hésitez pas si vous avez d'autres questions. À bientôt chez Autocentre !"
    },
    {
      keys: ["arthur", "qui es tu", "qui etes vous", "c est quoi", "c est qui", "vous etes qui", "tu es qui", "bot", "robot", "assistant", "ia"],
      answer: "🤖 Je suis Arthur, l'assistant virtuel d'Autocentre ! Je peux répondre à vos questions sur nos horaires, nos véhicules, nos services et plus encore. Pour une réponse humaine, appelez le <strong>07 49 44 07 63</strong>."
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

  const DEFAULT = "Je n'ai pas bien compris votre question 😅 Vous pouvez nous appeler au <strong>07 49 44 07 63</strong> ou écrire à <strong>autocentresas@gmail.com</strong> — nous serons ravis de vous aider !";

  function normalize(str) {
    return str.toLowerCase()
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9\s]/g, " ")
      .replace(/\s+/g, " ").trim();
  }

  function getAnswer(question) {
    const q = normalize(question);
    let best = null;
    let bestScore = 0;
    for (const entry of FAQ) {
      let score = 0;
      for (const k of entry.keys) {
        if (q.includes(normalize(k))) score++;
      }
      if (score > bestScore) {
        bestScore = score;
        best = entry;
      }
    }
    return bestScore > 0 ? best.answer : DEFAULT;
  }

  // DOM
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

  function addTyping() {
    const div = document.createElement("div");
    div.className = "chat-msg bot";
    div.id = "chat-typing";
    div.textContent = "…";
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  function send(text) {
    text = text.trim();
    if (!text) return;
    addMessage(escHtml(text), "user");
    input.value = "";
    const typing = addTyping();
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
      const q = SUGGESTION_QUESTIONS[btn.dataset.q] || btn.textContent;
      send(q);
    });
  });
})();