-- Run once on a new database as the bootstrap administrator, never the runtime user.
-- Password variables are populated with psql \getenv; never passed on argv.
\set ON_ERROR_STOP on
\getenv runtime_password DB_RUNTIME_PASSWORD
\getenv migration_password DB_MIGRATION_PASSWORD
CREATE ROLE editorial_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD :'migration_password';
CREATE ROLE editorial_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD :'runtime_password';
CREATE ROLE editorial_retention NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
REVOKE ALL ON DATABASE editorial FROM PUBLIC;
GRANT CONNECT ON DATABASE editorial TO editorial_migrator, editorial_runtime;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA editorial AUTHORIZATION editorial_migrator;
CREATE SCHEMA editorial_migrations AUTHORIZATION editorial_migrator;
REVOKE ALL ON SCHEMA editorial, editorial_migrations FROM PUBLIC;
GRANT USAGE ON SCHEMA editorial TO editorial_runtime;
