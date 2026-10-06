-- T05 OWNED TABLES ONLY. Main agent must allocate the global Flyway version.
-- Execute as editorial_migrator, after T02 bootstrap/beforeMigrate and after T03 app_user.
-- Prerequisite order per tables.json: policy_version & prompt_version before editorial_skill_version
-- (they are referenced by the skill config's JSON policy/prompt refs, validated at service layer).
--
-- Runtime privileges: DRAFT editable, PUBLISHED immutable, RETIRE is a controlled status change.
-- Immutability is enforced by SECURITY DEFINER trigger functions (owned by editorial_migrator)
-- IN ADDITION to the service layer. Runtime role has NO global UPDATE/DELETE/TRUNCATE on any table;
-- it only receives SELECT/INSERT/UPDATE where a controlled mutation is required.

-- ---------------------------------------------------------------- policy_version
CREATE TABLE editorial.policy_version (
 id uuid PRIMARY KEY,
 policy_type varchar(20) NOT NULL CHECK (policy_type IN ('FACT','LICENSE','QA','WATERMARK','COST')),
 version varchar(40) NOT NULL CHECK (version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
 rules jsonb NOT NULL CHECK (jsonb_typeof(rules) = 'object'),
 hash char(64) NOT NULL CHECK (hash ~ '^[a-f0-9]{64}$'),
 status varchar(20) NOT NULL CHECK (status IN ('DRAFT','PUBLISHED','RETIRED')),
 created_by uuid NOT NULL REFERENCES editorial.app_user(id),
 published_by uuid REFERENCES editorial.app_user(id),
 published_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 lock_version bigint NOT NULL DEFAULT 1,
 UNIQUE (policy_type, version)
);
CREATE INDEX policy_type_status ON editorial.policy_version(policy_type, status);

-- ---------------------------------------------------------------- prompt_version
CREATE TABLE editorial.prompt_version (
 id uuid PRIMARY KEY,
 agent_name varchar(80) NOT NULL,
 version varchar(40) NOT NULL CHECK (version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
 system_template text NOT NULL,
 user_template text NOT NULL,
 output_schema jsonb NOT NULL CHECK (jsonb_typeof(output_schema) = 'object'),
 hash char(64) NOT NULL CHECK (hash ~ '^[a-f0-9]{64}$'),
 status varchar(20) NOT NULL CHECK (status IN ('DRAFT','PUBLISHED')),
 created_by uuid NOT NULL REFERENCES editorial.app_user(id),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 lock_version bigint NOT NULL DEFAULT 1,
 UNIQUE (agent_name, version)
);
CREATE INDEX prompt_agent_status ON editorial.prompt_version(agent_name, status);

-- ---------------------------------------------------------------- editorial_skill
CREATE TABLE editorial.editorial_skill (
 id uuid PRIMARY KEY,
 code varchar(100) NOT NULL UNIQUE,
 name varchar(100) NOT NULL,
 owner_id uuid NOT NULL REFERENCES editorial.app_user(id),
 active_version_id uuid,                                  -- deferred FK -> editorial_skill_version(id)
 created_by uuid NOT NULL REFERENCES editorial.app_user(id),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 lock_version bigint NOT NULL DEFAULT 1
);
CREATE INDEX skill_owner ON editorial.editorial_skill(owner_id, created_at DESC, id DESC);

-- ---------------------------------------------------------------- editorial_skill_version
CREATE TABLE editorial.editorial_skill_version (
 id uuid PRIMARY KEY,
 skill_id uuid NOT NULL REFERENCES editorial.editorial_skill(id),
 version varchar(40) NOT NULL CHECK (version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
 config jsonb NOT NULL CHECK (jsonb_typeof(config) = 'object'),
 rules_hash char(64) NOT NULL CHECK (rules_hash ~ '^[a-f0-9]{64}$'),
 schema_version varchar(40) NOT NULL,
 status varchar(20) NOT NULL CHECK (status IN ('DRAFT','PUBLISHED','RETIRED')),
 parent_version_id uuid,                                  -- deferred self FK
 change_log varchar(1000),
 created_by uuid NOT NULL REFERENCES editorial.app_user(id),
 published_by uuid REFERENCES editorial.app_user(id),
 published_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 lock_version bigint NOT NULL DEFAULT 1,
 UNIQUE (skill_id, version)
);
CREATE INDEX skill_version_skill ON editorial.editorial_skill_version(skill_id, created_at DESC, id DESC);

-- ---------------------------------------------------------------- immutability guards
-- Published/retired content is immutable at the database level, independent of the service layer.
CREATE FUNCTION editorial.t05_skill_version_guard() RETURNS trigger AS $$
BEGIN
  -- Row identity and creation provenance never change, including while still a draft.
  IF NEW.id IS DISTINCT FROM OLD.id OR NEW.created_by IS DISTINCT FROM OLD.created_by
     OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
    RAISE EXCEPTION 'version identity and creation metadata are immutable';
  END IF;
  IF OLD.status <> 'DRAFT' THEN
    IF (to_jsonb(NEW) - ARRAY['status', 'updated_at', 'lock_version']) IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status', 'updated_at', 'lock_version']) THEN
      RAISE EXCEPTION 'published skill version content is immutable';
    END IF;
  END IF;
  IF OLD.status = 'DRAFT' AND NEW.status NOT IN ('DRAFT','PUBLISHED') THEN RAISE EXCEPTION 'draft may only be edited or published';
  END IF;
  IF OLD.status = 'PUBLISHED' AND NEW.status NOT IN ('PUBLISHED','RETIRED') THEN RAISE EXCEPTION 'published may only be retired';
  END IF;
  IF OLD.status = 'RETIRED' AND NEW.status <> 'RETIRED' THEN RAISE EXCEPTION 'retired is terminal';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = editorial;
REVOKE ALL ON FUNCTION editorial.t05_skill_version_guard() FROM PUBLIC;
CREATE TRIGGER t05_skill_version_guard BEFORE UPDATE ON editorial.editorial_skill_version
  FOR EACH ROW EXECUTE FUNCTION editorial.t05_skill_version_guard();

CREATE FUNCTION editorial.t05_policy_version_guard() RETURNS trigger AS $$
BEGIN
  -- Row identity and creation provenance never change, including while still a draft.
  IF NEW.id IS DISTINCT FROM OLD.id OR NEW.created_by IS DISTINCT FROM OLD.created_by
     OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
    RAISE EXCEPTION 'version identity and creation metadata are immutable';
  END IF;
  IF OLD.status <> 'DRAFT' THEN
    IF (to_jsonb(NEW) - ARRAY['status', 'updated_at', 'lock_version']) IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['status', 'updated_at', 'lock_version']) THEN
      RAISE EXCEPTION 'published policy rules are immutable';
    END IF;
  END IF;
  IF OLD.status = 'DRAFT' AND NEW.status NOT IN ('DRAFT','PUBLISHED') THEN RAISE EXCEPTION 'draft may only be edited or published';
  END IF;
  IF OLD.status = 'PUBLISHED' AND NEW.status NOT IN ('PUBLISHED','RETIRED') THEN RAISE EXCEPTION 'published may only be retired';
  END IF;
  IF OLD.status = 'RETIRED' AND NEW.status <> 'RETIRED' THEN RAISE EXCEPTION 'retired is terminal';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = editorial;
REVOKE ALL ON FUNCTION editorial.t05_policy_version_guard() FROM PUBLIC;
CREATE TRIGGER t05_policy_version_guard BEFORE UPDATE ON editorial.policy_version
  FOR EACH ROW EXECUTE FUNCTION editorial.t05_policy_version_guard();

CREATE FUNCTION editorial.t05_prompt_version_guard() RETURNS trigger AS $$
BEGIN
  -- Row identity and creation provenance never change, including while still a draft.
  IF NEW.id IS DISTINCT FROM OLD.id OR NEW.created_by IS DISTINCT FROM OLD.created_by
     OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
    RAISE EXCEPTION 'version identity and creation metadata are immutable';
  END IF;
  IF OLD.status <> 'DRAFT' THEN
    IF (to_jsonb(NEW) - ARRAY['updated_at', 'lock_version']) IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['updated_at', 'lock_version']) THEN
      RAISE EXCEPTION 'published prompt templates are immutable';
    END IF;
  END IF;
  IF OLD.status <> 'DRAFT' AND NEW.status = 'DRAFT' THEN RAISE EXCEPTION 'published may not revert to draft';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = editorial;
REVOKE ALL ON FUNCTION editorial.t05_prompt_version_guard() FROM PUBLIC;
CREATE TRIGGER t05_prompt_version_guard BEFORE UPDATE ON editorial.prompt_version
  FOR EACH ROW EXECUTE FUNCTION editorial.t05_prompt_version_guard();

-- ---------------------------------------------------------------- grants
REVOKE ALL ON editorial.policy_version, editorial.prompt_version,
             editorial.editorial_skill, editorial.editorial_skill_version FROM PUBLIC, editorial_runtime;
GRANT SELECT, INSERT, UPDATE ON editorial.policy_version,
       editorial.prompt_version, editorial.editorial_skill,
       editorial.editorial_skill_version TO editorial_runtime;
-- No runtime DELETE/TRUNCATE anywhere. Deletion is a retention_worker controlled flow (T37).
-- Trigger functions are not EXECUTE-granted to runtime: they fire with the invoker's privilege
-- but EXECUTE is only checked at CREATE TRIGGER time, and beforeMigrate keeps PUBLIC EXECUTE revoked.
