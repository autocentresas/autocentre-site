#!/bin/bash
# ============================================================
# mac_run.sh — Lance le scraper Autocentre sur Mac
# Appelé automatiquement par launchd toutes les 2h
# ============================================================

# Dossier du projet
PROJET="/Users/chaudryakhtar/Desktop/site web autocentre"

# Log
LOG_DIR="$HOME/Library/Logs"
LOG_FILE="$LOG_DIR/autocentre_scraper.log"
mkdir -p "$LOG_DIR"

echo "======================================" >> "$LOG_FILE"
echo "$(date '+%d/%m/%Y %H:%M:%S') — Démarrage" >> "$LOG_FILE"

# Activer le PATH complet (nécessaire pour launchd qui a un PATH limité)
export PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH"

# Trouver python3 avec playwright installé
PYTHON=""
for py in python3.11 python3.10 python3 /usr/bin/python3 /opt/homebrew/bin/python3; do
    if "$py" -c "import playwright" 2>/dev/null; then
        PYTHON="$py"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python avec playwright non trouvé" >> "$LOG_FILE"
    exit 1
fi

echo "Python: $PYTHON" >> "$LOG_FILE"

# Récupérer le token GitHub depuis le trousseau macOS
GITHUB_TOKEN=$(security find-internet-password -s github.com -a autocentresas -w 2>/dev/null)
export GITHUB_TOKEN
if [ -z "$GITHUB_TOKEN" ]; then
    echo "WARN: Token GitHub non trouvé dans le trousseau" >> "$LOG_FILE"
fi

# Lancer le scraper
cd "$PROJET" && "$PYTHON" scraper.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

echo "Code retour: $EXIT_CODE" >> "$LOG_FILE"
echo "$(date '+%d/%m/%Y %H:%M:%S') — Terminé" >> "$LOG_FILE"

exit $EXIT_CODE
