-- T03 OWNED TABLES ONLY. Main agent must allocate the global Flyway version.
-- Execute as editorial_migrator, after T02 bootstrap/beforeMigrate permissions.
CREATE TABLE editorial.app_user (
 id uuid PRIMARY KEY,
 username varchar(100) NOT NULL UNIQUE,
 display_name varchar(1000) NOT NULL,
 actor_type varchar(20) NOT NULL CHECK (actor_type IN ('OWNER','SYSTEM_WORKER')),
 password_hash varchar(500),
 enabled boolean NOT NULL DEFAULT true,
 bootstrap_key varchar(20) UNIQUE,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK ((actor_type='OWNER' AND password_hash IS NOT NULL) OR
        (actor_type='SYSTEM_WORKER' AND password_hash IS NULL))
);
CREATE UNIQUE INDEX app_user_single_system ON editorial.app_user(actor_type) WHERE actor_type='SYSTEM_WORKER';
CREATE TABLE editorial.audit_log (
 id uuid PRIMARY KEY,
 actor_id uuid NOT NULL REFERENCES editorial.app_user(id),
 actor_type varchar(20) NOT NULL CHECK (actor_type IN ('OWNER','SYSTEM_WORKER')),
 action varchar(80) NOT NULL,
 article_id uuid,
 entity_type varchar(80) NOT NULL,
 entity_id uuid NOT NULL,
 before_hash char(64) CHECK (before_hash ~ '^[a-f0-9]{64}$'),
 after_hash char(64) CHECK (after_hash ~ '^[a-f0-9]{64}$'),
 detail jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (detail='{}'::jsonb),
 trace_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
-- Article/entity metadata deliberately has no cascading business FK (retention contract).
CREATE INDEX audit_article_time ON editorial.audit_log(article_id,created_at DESC,id DESC);
CREATE INDEX audit_actor_time ON editorial.audit_log(actor_id,created_at DESC);
CREATE INDEX audit_login_window ON editorial.audit_log(entity_id,created_at) WHERE action='AUTH_ATTEMPT';
CREATE TABLE editorial.idempotency_record (
 id uuid PRIMARY KEY,
 owner_id uuid NOT NULL REFERENCES editorial.app_user(id),
 route text NOT NULL,
 key uuid NOT NULL,
 request_hash char(64) NOT NULL CHECK (request_hash ~ '^[a-f0-9]{64}$'),
 operation_id uuid,
 response_code integer NOT NULL CHECK (response_code BETWEEN 200 AND 299),
 response_body bytea NOT NULL,
 response_headers jsonb NOT NULL,
 expires_at timestamptz NOT NULL DEFAULT (clock_timestamp()+interval '7 days'),
 UNIQUE(owner_id,route,key)
);
REVOKE ALL ON editorial.app_user,editorial.audit_log,editorial.idempotency_record FROM PUBLIC,editorial_runtime;
GRANT SELECT,INSERT ON editorial.app_user,editorial.audit_log,editorial.idempotency_record TO editorial_runtime;
-- No runtime UPDATE/DELETE/TRUNCATE, even for idempotency: only final responses are inserted.
-- Account lifecycle is currently deployment-admin controlled; future commands need audited grants.
