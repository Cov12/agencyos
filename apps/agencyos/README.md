# AgencyOS Wrapper Layer

This directory contains all AgencyOS-specific code that wraps around OpenWebUI.

**Part of the WBIT product suite.** Auth and billing managed by [WBIT Portal](https://portal.wbit.app).

## Architecture

AgencyOS is a **thin wrapper layer** on top of OpenWebUI. All customizations live here — 
not scattered throughout OpenWebUI internals. This keeps upstream merges clean.

### Authentication

AgencyOS will accept Portal-issued JWTs (same pattern as WorkPipe and Drive). The auth flow:

1. User signs in on `portal.wbit.app`
2. Portal redirects to AgencyOS `/auth/callback?token=<jwt>`
3. AgencyOS validates JWT, sets HTTP-only cookie (`wbit_token`)
4. Middleware checks cookie on every request

AgencyOS has **zero knowledge of Clerk** or any auth provider. To swap providers, change Portal only.

**Status:** Auth integration not yet implemented. Currently uses OpenWebUI's built-in auth.

### Relationship to WorkPipe

- **AgencyOS** = Intelligence + Delegation (AI agents, dept routing, model tiering)
- **WorkPipe** = Execution + CRM (pipelines, contacts, invoices, funnels)
- AgencyOS includes WorkPipe integration; WorkPipe-only does NOT include AgencyOS
- CRM operations go through WorkPipe Internal API (abstract `CRMAdapter` interface)

## Structure

```
apps/agencyos/
├── backend/
│   ├── routers/       # FastAPI route extensions (departments, orchestrator, approvals)
│   ├── models/        # SQLAlchemy/Pydantic models (orgs, departments, proposals)
│   ├── services/      # Business logic (Cortex bridge, orchestrator, proposals)
│   ├── middleware/     # Auth/tenancy middleware (org context injection)
│   └── __init__.py
├── frontend/
│   ├── components/    # Svelte 4 components (dept switcher, approval inbox, org nav)
│   ├── stores/        # Svelte stores (org context, active department, proposals)
│   └── routes/        # SvelteKit route additions
├── config/
│   ├── departments.yaml    # Department definitions & model assignments
│   └── permissions.yaml    # Role-based permission matrix
└── docs/
    └── architecture.md     # Technical architecture documentation
```

## Design Principles

1. **Isolation** — Custom code stays in `apps/agencyos/`, never in OpenWebUI core
2. **Config-driven** — Department structure and permissions in YAML; the LLM brain lives in Cortex (the WBIT Assistant), reached via the Cortex bridge
3. **Delegated Mode** — No AI auto-execution. All actions require human approval.
4. **Dual DB** — OpenWebUI DB (AI/conversations) + WorkPipe DB (CRM/business)
5. **Multi-tenant** — RLS on shared Postgres (Phase 1) → DB-per-tenant (Enterprise)

## Pricing

Managed via Portal. Per-app subscriptions:

| Tier | Monthly | Annual (15% off) |
|------|---------|-------------------|
| Starter | $79/mo | $67.15/mo |
| Growth | $199/mo | $169.15/mo |
| Enterprise | $499/mo | $424.15/mo |

## Tech Stack

- **Backend**: FastAPI (Python 3.11+), mounted at `/api/agencyos/`
- **Frontend**: Svelte 4 (NOT Svelte 5 runes), Tailwind CSS
- **AI Models**: Tiered routing — Chief (premium cloud), Dept Heads (mid-tier), Agents (local Ollama)
- **Database**: Shared Postgres with RLS
- **Hosting**: Render (deploys from `agencyos-prod` branch)

## Deployment

Render Web Service. Docker image uses `node:22-alpine` (frontend) + `python:3.11` (backend). Currently at `agencyos-ije4.onrender.com`.
