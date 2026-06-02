# Smart Transit AI

> Intelligent public-transportation platform — live bus tracking, AI-predicted ETAs &
> occupancy, digital ticketing, and a real-time operations dashboard.

**Status:** 🟡 Planning / Architecture phase. This repository currently contains
**design documents only** — no application code has been generated yet. The documents
in [`docs/`](docs/) define the system before we build it.

---

## What this is

Three web applications backed by a single real-time, AI-augmented API layer:

| App | Audience | Core job |
|-----|----------|----------|
| **Passenger Web App** | Riders | Find routes, track buses live, see AI ETA/occupancy, buy QR tickets |
| **Driver Portal** | Drivers | Start/end trips, stream GPS, report delays, SOS |
| **Admin Dashboard** | Operators | Live fleet map, KPIs, CRUD management, analytics, anomaly alerts |

## Tech stack (target)

- **Frontend:** Next.js 16 (App Router, React 19, TS) · Tailwind v4 + ShadCN · TanStack Query/Table/Form · Zustand · Zod · Socket-aware client · Google Maps JS API · Framer Motion · Recharts
- **Backend:** Django 6 + DRF · Django Channels (WebSockets) · PostgreSQL · Redis (cache + channel layer) · Celery + Celery Beat · JWT auth
- **AI/ML:** Pandas · NumPy · scikit-learn · XGBoost · TensorFlow (LSTM)
- **DevOps:** Docker Compose · Nginx · GitHub Actions · AWS / DigitalOcean

### Pinned versions (latest stable, verified 2026-05-27)

The spec named floor versions (`Next.js 15+`, `Django 5+`); we build on the **current latest stable** of each.

| Component | Version | Note |
|-----------|---------|------|
| Node.js | **24 LTS** | Active LTS; Node 26 is Current but not yet LTS (Oct 2026). |
| Next.js | **16.2** | App Router, Turbopack default. |
| React | **19** | Baseline for Next 16. |
| Tailwind CSS | **4.3** | CSS-first config. |
| Python | **3.13** | ⚠ Not 3.14 — Celery 5.6 supports Python ≤ 3.13. |
| Django | **6.0** | Built-in tasks framework, native CSP. |
| Django REST Framework | **3.17** | Django 6 + Python 3.14 support. |
| Django Channels | **4.3** | Daphne/ASGI, Django 5.2+ compatible. |
| Celery | **5.6** | Pins Redis client ≤ 5.2.1; caps runtime at Python 3.13. |
| PostgreSQL | **17** | |
| Redis | **7.x** | Cache + Channels layer + Celery broker. |

> TanStack Query stays on **v5** and TanStack Table on **v8** — those are the current major lines, as the spec specified.

## Planned repository layout

```
smart-transit-ai/
├── docker-compose.yml  # dev stack: postgres, redis, web, ws, worker, beat
├── frontend/     # Next.js 16 — (auth) (passenger) (driver) (admin) route groups
├── backend/      # Django 6 — apps/, ai_modules/, channels/, config/, celery_tasks/
├── infra/        # nginx + docker-compose.prod.yml (P7)
├── .github/      # CI workflows
└── docs/         # ◀ you are here
```

## Design documents

Read in this order:

1. **[architecture.md](docs/architecture.md)** — system topology, the real-time pipeline, AI serving, security, deployment.
2. **[er-diagram.md](docs/er-diagram.md)** — all 12 tables, relationships, enums, indexing strategy.
3. **[api-contract.md](docs/api-contract.md)** — every `/api/v1` endpoint, the response envelope, auth, pagination, WebSocket channels.
4. **[build-plan.md](docs/build-plan.md)** — phased delivery plan (P0 → P6) mapped to the acceptance criteria.

## Next step

Pick a phase from [build-plan.md](docs/build-plan.md). **P0 (backend foundation + auth)**
is the recommended first implementation session — everything else depends on it.
