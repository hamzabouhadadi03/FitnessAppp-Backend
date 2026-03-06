#!/bin/bash
# =============================================================================
# FitProgress — Création des fichiers de secrets Docker
#
# À exécuter UNE SEULE FOIS sur le serveur de production, depuis le répertoire
# fitprogress-backend/, APRÈS avoir configuré le fichier .env.
#
# Usage : bash scripts/setup-secrets.sh
#
# Résultat : crée le répertoire ./secrets/ avec un fichier par secret.
# Ces fichiers sont montés dans /run/secrets/<nom> par Docker Compose.
# pydantic-settings les lit automatiquement (secrets_dir="/run/secrets").
# =============================================================================
set -euo pipefail

SECRETS_DIR="$(dirname "$0")/../secrets"
ENV_FILE="$(dirname "$0")/../.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Fichier .env introuvable : $ENV_FILE"
    echo "   Créez d'abord votre .env depuis .env.example"
    exit 1
fi

echo "📁 Création du répertoire secrets/..."
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

# Source du .env pour lire les variables
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

# Fonction utilitaire
write_secret() {
    local name="$1"
    local value="$2"
    local file="$SECRETS_DIR/${name}.txt"

    if [ -z "$value" ]; then
        echo "  ⚠️  $name est vide — fichier non créé (valeur optionnelle)"
        return
    fi

    printf '%s' "$value" > "$file"
    chmod 600 "$file"
    echo "  ✅ $name.txt créé"
}

echo ""
echo "🔐 Écriture des secrets..."
write_secret "secret_key"             "${SECRET_KEY:-}"
write_secret "database_url"           "${DATABASE_URL:-}"
write_secret "redis_url"              "${REDIS_URL:-}"
write_secret "apns_private_key"       "${APNS_PRIVATE_KEY:-}"
write_secret "fcm_service_account_json" "${FCM_SERVICE_ACCOUNT_JSON:-}"

echo ""
echo "✅ Secrets créés dans $SECRETS_DIR/"
echo "   Permissions vérifiées : 700 sur le répertoire, 600 sur chaque fichier."
echo ""
echo "⚠️  Ce répertoire est dans .gitignore — ne jamais le committer."
echo ""
ls -la "$SECRETS_DIR/"
