# =============================================================================
# FitProgress — Dockerfile de Développement
# Rechargement automatique activé, utilisateur non-root.
# =============================================================================
FROM python:3.12-slim

# Sécurité : exécution avec un utilisateur non-root
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

# Installation des dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installation des dépendances Python en tant que root (avant le changement d'utilisateur)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Passage à l'utilisateur non-root
USER appuser

# Copie du code source de l'application
COPY --chown=appuser:appgroup . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
