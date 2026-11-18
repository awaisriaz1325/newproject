-- Local/dev bootstrap: run once as a superuser. In managed Postgres (Neon), create these roles
-- in the provider console with equivalent attributes.
-- compback_owner: owns schema objects, runs migrations.
-- compback_app:   used by API and worker; NOT owner, NO BYPASSRLS -> RLS always applies.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compback_owner') THEN
    CREATE ROLE compback_owner LOGIN PASSWORD 'compback_owner' NOSUPERUSER NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compback_app') THEN
    CREATE ROLE compback_app LOGIN PASSWORD 'compback_app' NOSUPERUSER NOBYPASSRLS;
  END IF;
END $$;
