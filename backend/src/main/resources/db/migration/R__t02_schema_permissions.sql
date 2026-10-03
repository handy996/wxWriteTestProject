-- Infrastructure only. No business table and no global version number allocated.
REVOKE ALL ON SCHEMA editorial FROM PUBLIC;
GRANT USAGE ON SCHEMA editorial TO editorial_runtime;
REVOKE CREATE ON SCHEMA editorial FROM editorial_runtime;
REVOKE ALL ON SCHEMA editorial_migrations FROM PUBLIC, editorial_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE editorial_migrator IN SCHEMA editorial
    REVOKE ALL ON TABLES FROM PUBLIC, editorial_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE editorial_migrator IN SCHEMA editorial
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, editorial_runtime;
-- Domain migration owners must grant table/column rights explicitly per T00.
