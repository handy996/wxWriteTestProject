-- Must run before versioned domain migrations, including on the first startup.
-- Schema-level REVOKE cannot subtract PostgreSQL's global PUBLIC default.
ALTER DEFAULT PRIVILEGES FOR ROLE editorial_migrator
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, editorial_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE editorial_migrator IN SCHEMA editorial
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, editorial_runtime;
