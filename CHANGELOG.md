# Changelog — FitProgress Backend

Toutes les modifications notables sont documentées ici.
Format : [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/)
Versionnage : [Semantic Versioning](https://semver.org/lang/fr/)

---

## [1.0.0] — 2026-03-05

### 🚀 Version initiale — Prête pour la MEP mobile

#### Ajouté
- **Architecture backend complète** : FastAPI 0.135 + SQLAlchemy 2.0 async + PostgreSQL 16 + Redis 7
- **Authentification** : Auth0 RS256 JWT, validation JWKS avec cache Redis (1h TTL)
- **7 domaines métier** : auth, users, exercises, programs, workouts, progression, gamification
- **Moteur de progression** : 6 étapes (analyse → PR → décision → plateau 3x → validation reset → ajustements RPE)
- **58 exercices standard** seedés (11 catégories : COMPOUND_CHEST, SHOULDERS, TRICEPS, ISOLATION_CHEST, COMPOUND_BACK, BICEPS, ISOLATION_BACK, COMPOUND_LEGS, ISOLATION_LEGS, CORE, CARDIO)
- **Push notifications** : infrastructure complète APNs (iOS) + FCM v1 (Android) via Celery + Redis
  - `POST /api/v1/notifications/device-token` — enregistrement token
  - `DELETE /api/v1/notifications/device-token/{token}` — désenregistrement
  - `GET/PUT /api/v1/notifications/preferences` — préférences de rappel
  - `POST /api/v1/notifications/test-push` — test d'envoi (dev)
  - Tâche Beat Celery : rappels d'entraînement quotidiens (toutes les heures)
- **Nginx** : terminaison SSL, rate limiting, reverse proxy, HTTP/2
- **Docker Compose** : dev (app + postgres + redis + celery_worker + celery_beat) et prod
- **Sécurité** : 7 couches (TLS → Rate Limit ×2 → CORS → JWT RS256 → Ownership → Soft Delete → Security Headers)
- **Migration** `002_add_notifications` : tables `device_tokens` + `user_notification_prefs`

#### Endpoints disponibles (36 routes)
| Domaine | Routes |
|---------|--------|
| Health | `GET /health` |
| Auth | `POST /auth/sync`, `GET /auth/me` |
| Users | `GET/PUT /users/profile`, `POST /users/onboarding` |
| Exercises | CRUD complet + pagination cursor |
| Programs | CRUD + activation + jours + exercices par jour + réordonnancement |
| Workouts | Sessions + sets + complétion |
| Progression | `GET /overview`, `GET /logs`, `GET /analysis/{id}`, `GET /plateaus`, `POST /reset/validate` |
| Gamification | stats, streak, personal-records, progress-score, activity-history |
| Notifications | device-token, preferences, test-push |

#### Sécurité
- Aucun secret codé en dur — tout via variables d'environnement
- UUIDs comme PKs (pas d'énumération)
- Soft delete universel (jamais de suppression physique des données utilisateur)
- `verify_ownership` sur toutes les ressources utilisateur

---

## [0.9.0] — 2026-03-04 *(pre-release)*

### Corrigé
- **Nginx** : `$host` → `$server_name` (Host Header Injection — Semgrep blocking findings × 7)
- **Nginx** : structure manquante `events {}` + `http {}`, deprecation HTTP/2 `listen 443 ssl http2` → `listen 443 ssl; http2 on;`
- **Nginx** : DNS resolver Docker `127.0.0.11` + pattern `set $backend` pour résolution différée
- **Progression** : `GET /progression/overview` 500 error — jointure SQLAlchemy malformée (`first_result`) corrigée, `weight_change_kg` calculé correctement

---

## Prochaines versions prévues

### [1.1.0] — Fonctionnalités mobiles
- [ ] Seeding complet des exercices (variantes, tempo, équipement requis)
- [ ] Background tasks Celery : notifications personnalisées basées sur la progression
- [ ] Admin panel (Django admin ou custom FastAPI)
- [ ] Webhook Auth0 pour la suppression d'utilisateur

### [2.0.0] — Scale
- [ ] Cache de requêtes Redis (réponses GET fréquentes)
- [ ] Monitoring (Sentry, Datadog)
- [ ] Tests d'intégration complets (pytest-asyncio)
- [ ] CI/CD GitHub Actions
