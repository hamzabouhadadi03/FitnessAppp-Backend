#!/usr/bin/env bash
# =============================================================================
# FitProgress — Setup Monitoring Access
#
# Configure l'accès HTTPS à Grafana via monitoring.fitprogress.ovh
#
# Ce script est idempotent : il peut être ré-exécuté sans risque.
#
# Prérequis :
#   1. DNS : Enregistrement A pour monitoring.fitprogress.ovh → IP du serveur
#   2. Port 80 et 443 ouverts dans le pare-feu
#   3. certbot installé sur le serveur (apt install certbot)
#   4. Le stack prod doit déjà être lancé (docker compose prod up -d)
#   5. Le stack monitoring doit déjà être lancé (docker compose monitoring up -d)
#
# Usage :
#   cd /home/hamza/fitprogress-backend
#   bash scripts/setup-monitoring-access.sh
# =============================================================================
set -euo pipefail

DOMAIN="monitoring.fitprogress.ovh"
BACKEND_DIR="/home/hamza/fitprogress-backend"
SSL_DIR="$BACKEND_DIR/nginx/ssl-monitoring"
HTPASSWD_FILE="$BACKEND_DIR/nginx/monitoring.htpasswd"
COMPOSE_PROD="$BACKEND_DIR/docker-compose.prod.yml"
COMPOSE_MON="$BACKEND_DIR/docker-compose.monitoring.yml"
EMAIL="admin@fitprogress.ovh"

# Couleurs pour les logs
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log_ok()   { echo -e "${GREEN}✅ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_err()  { echo -e "${RED}❌ $1${NC}"; exit 1; }

echo "========================================"
echo " FitProgress — Monitoring Access Setup"
echo " Domaine : https://$DOMAIN"
echo "========================================"
echo ""

# ---------------------------------------------------------------------------
# Étape 0 — Vérifications préalables
# ---------------------------------------------------------------------------
echo "--- Étape 0 : Vérifications ---"

# Vérifier que le script tourne depuis le bon répertoire
cd "$BACKEND_DIR" || log_err "Répertoire $BACKEND_DIR introuvable"

# Vérifier certbot
if ! command -v certbot &>/dev/null; then
    log_warn "certbot non installé — installation..."
    apt-get update -qq && apt-get install -y certbot -qq
fi
log_ok "certbot disponible"

# Vérifier apache2-utils (pour htpasswd)
if ! command -v htpasswd &>/dev/null; then
    log_warn "apache2-utils non installé — installation..."
    apt-get install -y apache2-utils -qq
fi
log_ok "htpasswd disponible"

# Charger le .env pour récupérer GRAFANA_ADMIN_PASSWORD
if [[ -f "$BACKEND_DIR/.env" ]]; then
    # shellcheck disable=SC2046
    export $(grep -v '^#' "$BACKEND_DIR/.env" | grep -v '^$' | xargs)
fi

GRAFANA_PASS="${GRAFANA_ADMIN_PASSWORD:-}"
if [[ -z "$GRAFANA_PASS" ]]; then
    log_warn "GRAFANA_ADMIN_PASSWORD absent du .env — génération d'un mot de passe..."
    GRAFANA_PASS="$(openssl rand -hex 16)"
    echo "GRAFANA_ADMIN_PASSWORD=$GRAFANA_PASS" >> "$BACKEND_DIR/.env"
    log_warn "Mot de passe Grafana : $GRAFANA_PASS  ← NOTER ET CONSERVER"
fi

# Vérifier la résolution DNS du domaine
log_warn "Vérification DNS pour $DOMAIN..."
if ! host "$DOMAIN" &>/dev/null; then
    log_warn "DNS $DOMAIN non résolu — Continue quand même (certbot échouera si DNS absent)"
else
    RESOLVED_IP=$(host "$DOMAIN" | awk '/has address/ {print $NF; exit}')
    log_ok "DNS OK — $DOMAIN → $RESOLVED_IP"
fi

echo ""

# ---------------------------------------------------------------------------
# Étape 1 — Créer un certificat auto-signé temporaire
#            (permet à nginx de démarrer avec le nouveau bloc monitoring)
# ---------------------------------------------------------------------------
echo "--- Étape 1 : Certificat temporaire (bootstrap nginx) ---"

mkdir -p "$SSL_DIR"

if [[ ! -f "$SSL_DIR/fullchain.pem" ]]; then
    log_warn "Génération d'un certificat auto-signé temporaire..."
    openssl req -x509 -nodes -newkey rsa:2048 \
        -keyout "$SSL_DIR/privkey.pem" \
        -out "$SSL_DIR/fullchain.pem" \
        -days 1 \
        -subj "/C=FR/O=FitProgress/CN=$DOMAIN" \
        -quiet
    chmod 600 "$SSL_DIR/privkey.pem"
    log_ok "Certificat auto-signé créé (valide 1 jour — sera remplacé)"
else
    log_ok "Certificat existant conservé"
fi

echo ""

# ---------------------------------------------------------------------------
# Étape 2 — Créer le fichier htpasswd
# ---------------------------------------------------------------------------
echo "--- Étape 2 : Authentification Basic Auth ---"

if [[ -f "$HTPASSWD_FILE" ]] && htpasswd -v "$HTPASSWD_FILE" admin <<< "$GRAFANA_PASS" &>/dev/null; then
    log_ok "htpasswd existant et valide — conservation"
else
    htpasswd -bc "$HTPASSWD_FILE" admin "$GRAFANA_PASS"
    chmod 640 "$HTPASSWD_FILE"
    log_ok "htpasswd créé (utilisateur: admin)"
fi

echo ""

# ---------------------------------------------------------------------------
# Étape 3 — Redémarrer nginx pour charger la nouvelle config monitoring
# ---------------------------------------------------------------------------
echo "--- Étape 3 : Redémarrage nginx (chargement config monitoring) ---"

# Tester la config nginx avant de redémarrer
docker compose -f "$COMPOSE_PROD" exec nginx nginx -t 2>&1 \
    && log_ok "Config nginx valide" \
    || log_err "Config nginx invalide — vérifier nginx/nginx.conf"

docker compose -f "$COMPOSE_PROD" restart nginx
sleep 5
log_ok "nginx redémarré (certificat auto-signé actif pour $DOMAIN)"

echo ""

# ---------------------------------------------------------------------------
# Étape 4 — Obtenir le vrai certificat Let's Encrypt
#            Méthode : standalone (port 80 repris temporairement par certbot)
#            Nginx est stoppé brièvement (~15-30 secondes)
# ---------------------------------------------------------------------------
echo "--- Étape 4 : Certificat Let's Encrypt (interruption nginx ~30s) ---"

LETSENCRYPT_DIR="/etc/letsencrypt/live/$DOMAIN"

if [[ -d "$LETSENCRYPT_DIR" ]] && openssl x509 -checkend 86400 -noout -in "$LETSENCRYPT_DIR/fullchain.pem" 2>/dev/null; then
    log_ok "Certificat Let's Encrypt valide existant — renouvellement ignoré"
    cp "$LETSENCRYPT_DIR/fullchain.pem" "$SSL_DIR/fullchain.pem"
    cp "$LETSENCRYPT_DIR/privkey.pem"   "$SSL_DIR/privkey.pem"
    chmod 600 "$SSL_DIR/privkey.pem"
    log_ok "Certificat copié vers nginx/ssl-monitoring/"
else
    log_warn "Arrêt nginx pour certbot standalone (~30s d'interruption)..."
    docker compose -f "$COMPOSE_PROD" stop nginx

    certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        -d "$DOMAIN" \
        || {
            log_warn "certbot échoué — redémarrage nginx avec certificat auto-signé"
            docker compose -f "$COMPOSE_PROD" start nginx
            log_err "Échec Let's Encrypt — vérifier DNS et pare-feu (ports 80/443)"
        }

    log_ok "Certificat Let's Encrypt obtenu"

    cp "$LETSENCRYPT_DIR/fullchain.pem" "$SSL_DIR/fullchain.pem"
    cp "$LETSENCRYPT_DIR/privkey.pem"   "$SSL_DIR/privkey.pem"
    chmod 600 "$SSL_DIR/privkey.pem"
    log_ok "Certificat copié vers nginx/ssl-monitoring/"

    docker compose -f "$COMPOSE_PROD" start nginx
    sleep 5
    log_ok "nginx redémarré (certificat Let's Encrypt actif)"
fi

echo ""

# ---------------------------------------------------------------------------
# Étape 5 — Recharger nginx avec le vrai certificat
# ---------------------------------------------------------------------------
echo "--- Étape 5 : Rechargement nginx (vrai certificat) ---"

docker compose -f "$COMPOSE_PROD" exec nginx nginx -s reload
log_ok "nginx rechargé avec le certificat Let's Encrypt"

echo ""

# ---------------------------------------------------------------------------
# Étape 6 — Redémarrer Grafana avec le nouveau ROOT_URL
# ---------------------------------------------------------------------------
echo "--- Étape 6 : Redémarrage Grafana (mise à jour ROOT_URL) ---"

docker compose -f "$COMPOSE_MON" --env-file "$BACKEND_DIR/.env" restart grafana
sleep 8
log_ok "Grafana redémarré — ROOT_URL : https://$DOMAIN/"

echo ""

# ---------------------------------------------------------------------------
# Étape 7 — Vérification finale
# ---------------------------------------------------------------------------
echo "--- Étape 7 : Vérifications ---"

# Test HTTP → HTTPS redirect
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://$DOMAIN/" --max-time 10 || echo "000")
if [[ "$HTTP_CODE" == "301" ]]; then
    log_ok "HTTP → HTTPS redirect (301) ✓"
else
    log_warn "Redirect HTTP→HTTPS : code $HTTP_CODE (attendu 301)"
fi

# Test HTTPS avec Basic Auth (sans credentials → 401)
HTTPS_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://$DOMAIN/" --max-time 10 || echo "000")
if [[ "$HTTPS_CODE" == "401" ]]; then
    log_ok "Basic Auth active — retourne 401 sans credentials ✓"
elif [[ "$HTTPS_CODE" == "200" ]]; then
    log_warn "Grafana accessible sans auth (401 attendu) — vérifier monitoring.htpasswd"
else
    log_warn "HTTPS response : $HTTPS_CODE (401 attendu)"
fi

# Test HTTPS avec credentials valides → 200
AUTHED_CODE=$(curl -sk -o /dev/null -w "%{http_code}" \
    -u "admin:$GRAFANA_PASS" "https://$DOMAIN/" --max-time 10 || echo "000")
if [[ "$AUTHED_CODE" == "200" ]]; then
    log_ok "Grafana accessible avec credentials ✓"
else
    log_warn "Grafana avec auth : code $AUTHED_CODE (200 attendu) — vérifier Grafana logs"
fi

# ---------------------------------------------------------------------------
# Résumé
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
echo -e "${GREEN} SETUP TERMINÉ${NC}"
echo "========================================"
echo ""
echo "  URL      : https://$DOMAIN"
echo "  Login    : admin"
echo "  Password : [GRAFANA_ADMIN_PASSWORD dans .env]"
echo ""
echo " Renouvellement auto du cert (ajouter au cron si besoin) :"
echo "   0 3 * * 0 certbot renew --quiet && cp /etc/letsencrypt/live/$DOMAIN/*.pem $SSL_DIR/ && docker compose -f $COMPOSE_PROD exec nginx nginx -s reload"
echo ""
