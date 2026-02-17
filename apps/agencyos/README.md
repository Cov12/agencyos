# AgencyOS Wrapper Layer

This directory contains all AgencyOS-specific code that wraps around OpenWebUI.

## Architecture

AgencyOS is a **thin wrapper layer** on top of OpenWebUI. All customizations live here — 
not scattered throughout OpenWebUI internals. This keeps upstream merges clean.

## Structure

```
apps/agencyos/
├── backend/
│   ├── routers/       # FastAPI route extensions (departments, orchestrator, approvals)
│   ├── models/        # SQLAlchemy/Pydantic models (orgs, departments, proposals)
│   ├── services/      # Business logic (orchestrator, model router, dept engines)
│   ├── middleware/     # Auth/tenancy middleware (org context injection)
│   └── __init__.py
├── frontend/
│   ├── components/    # Svelte components (dept switcher, approval inbox, org nav)
│   ├── stores/        # Svelte stores (org context, active department, proposals)
│   └── routes/        # SvelteKit route additions
├── config/
│   ├── departments.yaml    # Department definitions & model assignments
│   ├── model_tiers.yaml    # Model routing rules per role
│   └── permissions.yaml    # Role-based permission matrix
└── docs/
    └── architecture.md     # Technical architecture documentation
```

## Design Principles

1. **Isolation** — Custom code stays in `apps/agencyos/`, never in OpenWebUI core
2. **Config-driven** — Department structure, model tiers, permissions all in YAML
3. **Delegated Mode** — No AI auto-execution. All actions require human approval.
4. **Dual DB** — OpenWebUI DB (AI/conversations) + WorkPipe DB (CRM/business)
5. **Multi-tenant** — RLS on shared Postgres (Phase 1) → DB-per-tenant (Enterprise)
