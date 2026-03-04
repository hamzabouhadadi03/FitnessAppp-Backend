# FitProgress Backend

Production-ready FastAPI backend for **FitProgress** — a SaaS fitness progression app with an intelligent auto-progression engine.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.111 |
| Language | Python 3.12 |
| ORM | SQLAlchemy 2.0 async |
| Migrations | Alembic |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Auth | Auth0 (JWT RS256) |
| Validation | Pydantic v2 |
| Rate Limiting | SlowAPI |
| Reverse Proxy | Nginx |
| Containers | Docker + Docker Compose |
| Logging | structlog (JSON) |
| Testing | pytest + pytest-asyncio + httpx |

---

## Prerequisites

- Docker 24+ and Docker Compose v2
- Python 3.12 (for local dev without Docker)
- An Auth0 tenant with an API created

---

## Local Development Setup (3 commands)

```bash
# 1. Copy environment variables and fill in your values
cp .env.example .env

# 2. Start all services (PostgreSQL, Redis, FastAPI with hot reload)
docker compose up --build

# 3. Run database migrations
docker compose exec app alembic upgrade head
```

The API will be available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs` (development only).

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Random 64-char hex string (`openssl rand -hex 32`) |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://user:pass@postgres:5432/fitprogress` |
| `REDIS_URL` | Yes | `redis://redis:6379/0` |
| `AUTH0_DOMAIN` | Yes | `your-tenant.auth0.com` (no `https://`) |
| `AUTH0_AUDIENCE` | Yes | API identifier from Auth0 dashboard |
| `CORS_ORIGINS` | Yes | Comma-separated allowed origins |
| `APP_ENV` | Yes | `development` or `production` |
| `DEBUG` | Yes | `true` in dev, `false` in prod |

See `.env.example` for the full list.

---

## Running Tests

```bash
# Install dev dependencies
pip install -r requirements.txt
pip install aiosqlite pytest pytest-asyncio httpx

# Run all tests
pytest tests/ -v

# Run specific test module
pytest tests/test_progression/test_engine.py -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

---

## API Overview

All endpoints live under `/api/v1/`. Every protected endpoint requires:

```
Authorization: Bearer <Auth0 JWT>
```

### Auth
| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/sync` | Sync Auth0 user to DB (call after login) |
| `GET` | `/auth/me` | Current user info |

### Users
| Method | Path | Description |
|---|---|---|
| `GET` | `/users/profile` | Get profile |
| `PUT` | `/users/profile` | Update profile |
| `POST` | `/users/onboarding` | Complete onboarding |
| `DELETE` | `/users/account` | Soft delete account |

### Programs
| Method | Path | Description |
|---|---|---|
| `GET/POST` | `/programs/` | List / create programs |
| `GET/PUT/DELETE` | `/programs/{id}` | Get / update / delete program |
| `POST` | `/programs/{id}/activate` | Set as active program |
| `GET/POST` | `/programs/{id}/days` | List / add days |
| `GET/POST` | `/programs/{id}/days/{day_id}/exercises` | List / add exercises to day |

### Workouts
| Method | Path | Description |
|---|---|---|
| `POST` | `/workouts/sessions` | Start new session |
| `GET` | `/workouts/sessions` | List sessions (paginated) |
| `PUT` | `/workouts/sessions/{id}/complete` | Complete session → triggers engine |
| `POST` | `/workouts/sessions/{id}/sets` | Add set |

### Progression
| Method | Path | Description |
|---|---|---|
| `GET` | `/progression/analysis/{pde_id}` | History + current suggestion |
| `POST` | `/progression/reset/validate` | Confirm plateau reset |
| `GET` | `/progression/plateaus` | All active plateaus |
| `GET` | `/progression/overview` | Global exercise summary |

### Gamification
| Method | Path | Description |
|---|---|---|
| `GET` | `/gamification/stats` | Total sessions, volume, PRs |
| `GET` | `/gamification/streak` | Current + longest streak |
| `GET` | `/gamification/personal-records` | All-time PRs per exercise |
| `GET` | `/gamification/progress-score` | Monthly score (0–100) |
| `GET` | `/gamification/activity-history` | 12-week heatmap |

---

## Progression Engine

The core algorithm lives in `app/progression/engine.py` as **pure functions** (zero I/O).

**Decision flow per session:**

1. Analyze working sets (reps vs. target range, RPE mode)
2. Check for Personal Record
3. Decide: increase (+2.5%), consolidate, or flag failure
4. After 3 consecutive stalled sessions → `PLATEAU_DETECTED`
5. User confirms via `POST /progression/reset/validate` → 6% weight reduction applied
6. RPE adjustment: 2 consecutive EASY sessions → 5% increase instead of 2.5%

---

## Production Deployment

```bash
# 1. Fill in production .env (DEBUG=false, APP_ENV=production)

# 2. Generate SSL certificates
certbot certonly --standalone -d yourdomain.com
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/

# 3. Start production stack
docker compose -f docker-compose.prod.yml up -d

# 4. Run migrations
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
```

### Resource Allocation (production)

| Service | RAM Limit |
|---|---|
| app (4 workers) | 512 MB |
| postgres | 512 MB |
| redis | 256 MB |

---

## Security

- Auth0 RS256 JWT validation on every protected endpoint
- JWKS cached in Redis (3600s TTL) — no Auth0 dependency per request
- Rate limiting: 100 req/min globally, 10 req/min for auth endpoints
- UUID primary keys (prevents enumeration attacks)
- Soft delete everywhere — no hard deletes
- Ownership verification on every data access (`verify_ownership()`)
- Security headers: `X-Frame-Options`, `CSP`, `HSTS`, `X-Content-Type-Options`
- Structured JSON logging — no PII, no tokens logged
- No raw SQL — SQLAlchemy ORM only

---

## Project Structure

```
fitprogress-backend/
├── app/
│   ├── main.py              # App factory
│   ├── api/v1/router.py     # Aggregates all routers
│   ├── core/                # Config, security, DB, logging
│   ├── auth/                # Auth0 sync + /me
│   ├── users/               # Profile, onboarding
│   ├── exercises/           # Exercise library
│   ├── programs/            # Programs, days, exercises
│   ├── workouts/            # Sessions, sets
│   ├── progression/         # Engine + analysis routes
│   └── gamification/        # Stats, streaks, PRs
├── alembic/                 # Migrations
├── tests/                   # pytest test suite
├── nginx/                   # Nginx config + SSL
├── docker/                  # Dockerfiles
├── docker-compose.yml       # Dev
└── docker-compose.prod.yml  # Production
```
