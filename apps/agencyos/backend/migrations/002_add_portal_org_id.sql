-- 002_add_portal_org_id.sql
--
-- Adds agencyos_organization.portal_org_id — the Portal org id (a CUID) the bridge runs
-- through cortex_bridge._resolve_company_id to derive each org's Cortex company UUID, in
-- lockstep with Cortex's resolvePortalCompany. NULL rows fall back to the WBIT_COMPANY_ID
-- pin, so the column add is safe to apply before any backfill.
--
-- ⚠️ AgencyOS prod runs on SQLite, NOT Postgres — do NOT run this with psql.
--   AgencyOS is an OpenWebUI fork. With no DATABASE_URL set, OpenWebUI falls back to
--   sqlite:///{DATA_DIR}/webui.db (backend/open_webui/env.py:283). On Render that file
--   lives on a MOUNTED DISK at /app/backend/data/webui.db, so it persists across deploys.
--   There is no Neon/Postgres database for AgencyOS.
--
-- SQLite notes: ALTER TABLE ... ADD COLUMN has no IF NOT EXISTS (run it exactly once), and
-- create_all (mount.py) only creates MISSING tables — it never ALTERs — so the column is
-- added by hand against the live webui.db.
--
-- Apply from the AgencyOS service shell. Neither psql nor the sqlite3 CLI is installed in
-- the container; python3 is (the app runs on it):
--
--   # back up first (a SQLite backup is just a file copy)
--   cp /app/backend/data/webui.db /app/backend/data/webui.db.bak
--
--   # add the column
--   python3 -c "import sqlite3; c=sqlite3.connect('/app/backend/data/webui.db'); \
--     c.execute('ALTER TABLE agencyos_organization ADD COLUMN portal_org_id varchar'); \
--     c.commit()"
--
--   # backfill WBIT's org (see note below) and verify
--   python3 -c "import sqlite3; c=sqlite3.connect('/app/backend/data/webui.db'); \
--     c.execute('UPDATE agencyos_organization SET portal_org_id=? WHERE slug=?', \
--       ('cmpswvysr000029jthi4waszr','default')); c.commit(); \
--     print(c.execute('SELECT id, slug, portal_org_id FROM agencyos_organization').fetchall())"
--
-- The equivalent SQL (SQLite dialect) is below, if a sqlite3 client is available:
--   sqlite3 /app/backend/data/webui.db < 002_add_portal_org_id.sql

ALTER TABLE agencyos_organization ADD COLUMN portal_org_id varchar;

-- Backfill WBIT's org. AgencyOS prod is single-tenant: exactly one row — the OpenWebUI
-- default org (slug 'default', name 'My Organization', id 90de5276-9474-486c-95db-d9d98eb5a848).
-- The CUID below is WBIT's Portal org id; with PORTAL_COMPANY_OVERRIDES mapping it to …c0de
-- on both Cortex and AgencyOS, the bridge resolves this org to the SAME company it used under
-- the old WBIT_COMPANY_ID pin — no behavior change, now via the per-org path.
UPDATE agencyos_organization
    SET portal_org_id = 'cmpswvysr000029jthi4waszr'
    WHERE slug = 'default'
      AND portal_org_id IS NULL;

-- Verify (expect: [('90de5276-...', 'default', 'cmpswvysr000029jthi4waszr')]):
--   SELECT id, slug, portal_org_id FROM agencyos_organization;

-- Rollback (SQLite 3.35+ supports DROP COLUMN; older requires a table rebuild):
--   ALTER TABLE agencyos_organization DROP COLUMN portal_org_id;
