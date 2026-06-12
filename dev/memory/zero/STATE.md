# Current State (maintained by zero)

Reviewed: 2026-06-12 (zero session, AUTO — P5-lite baseline ETA, full-stack)
Branch: feat/p5-baseline-eta (stacked on feat/p6-admin-kpis)  | Dirty: ETA slice (3 new + ~14 modified), uncommitted
Backend tests: **268 passed** (255 prior + 13 new ETA; ~3.7s)
Frontend gates: ESLint clean · `tsc --noEmit` clean · **vitest 26 passed** (5 new) · **next build** OK
Lint (backend): ruff **clean**; ruff format **clean**; `manage.py check` **no issues**;
makemigrations --check **No changes** (no model change); spectacular --validate --fail-on-warn **clean**

> Backend deps in `backend/.venv` (gitignored): `source backend/.venv/bin/activate`,
> `DJANGO_SETTINGS_MODULE=config.settings.test python -m pytest`.
> Frontend deps installed (`frontend/node_modules`): `npm run lint|typecheck|test|build`.
> `next build` is memory-heavy on WSL2 — if it exits 137 (OOM), retry alone (not alongside vitest).

## Active Plans
| Plan (dev/memory/<task>/) | Status | Next step |
|---|---|---|
| dev/memory/p6-admin-kpis/Planning.md | DONE — committed on feat/p6-admin-kpis (1deced0, 54d7561, a83da38), not merged | User to ship: PR feat/p6-admin-kpis → main (deferred — chose to stack ETA) |
| dev/memory/p5-baseline-eta/Planning.md | DONE — backend + frontend implemented & verified, NOT committed | User to ship: commit feat/p5-baseline-eta, push, PR (zero won't commit unless asked) |

## Proposed Next (ranked)
1. **Ship the stack** — PR `feat/p6-admin-kpis` → main, then `feat/p5-baseline-eta` (or squash both). On request.
2. **ETA polish (optional, cheap):** straight-line haversine is optimistic vs road distance —
   add a ~1.3× fudge factor; and push ETA over the WS `LocationEvent` for sub-second refresh
   (today it refreshes on the REST cadence: fleet 30s, route on focus/stale).
3. **P6 cont. — real-time alerts feed** (`/ws/alerts/`) + admin incident feed (SOS/deviation/
   overspeed). Reuses driver_logs SOS + notifications + Channels. ~1 session.
4. **P6 cont. — analytics_snapshots + Celery rollups + Recharts views + exports.** Larger.
5. **P7 — health-check** (`GET /api/health/` DB/Redis probes) + prod compose/nginx; CI 3.12→3.13.

## Blockers / Decisions needed
- None. ETA slice complete & verified on its branch; awaiting user to ship or pick the next track.
