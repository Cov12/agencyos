-- 002_add_portal_org_id.sql
--
-- Adds agencyos_organization.portal_org_id — the Portal org id (a CUID) the bridge
-- runs through cortex_bridge._resolve_company_id to derive each org's Cortex company
-- UUID, in lockstep with Cortex's resolvePortalCompany. NULL rows fall back to the
-- WBIT_COMPANY_ID pin, so this migration is safe to apply before any backfill.
--
-- NOTE: AgencyOS table creation uses SQLAlchemy create_all (mount.py), which only
-- creates MISSING tables — it never ALTERs an existing one. So this column must be
-- added by hand on already-provisioned databases (e.g. Neon prod).
--
-- Apply:
--   psql "$DATABASE_URL" -f apps/agencyos/backend/migrations/002_add_portal_org_id.sql

ALTER TABLE agencyos_organization
    ADD COLUMN IF NOT EXISTS portal_org_id varchar;

-- Backfill WBIT's row so it resolves through the override (-> …c0de) instead of the
-- pin fallback. Replace the slug if WBIT's org slug differs in this database.
-- The CUID below is WBIT's Portal org id (matches PORTAL_COMPANY_OVERRIDES on both
-- Cortex and AgencyOS).
UPDATE agencyos_organization
    SET portal_org_id = 'cmpswvysr000029jthi4waszr'
    WHERE slug = 'wbit'
      AND portal_org_id IS NULL;

-- Verify:
--   SELECT id, slug, portal_org_id FROM agencyos_organization;

-- Rollback:
--   ALTER TABLE agencyos_organization DROP COLUMN IF EXISTS portal_org_id;
