-- T08 only. Main agent assigns the global Flyway version (proposed V5) after T03 + T06; touches no other domain table.
-- Draft: apply manually to an isolated database. Nothing here seeds a price, so every provider starts unknown-priced
-- and an automatic image generation stays refused until an operator publishes a price version.
CREATE TABLE editorial.cost_pricing_version (
  id uuid PRIMARY KEY, provider varchar(64) NOT NULL, model varchar(128) NOT NULL,
  version varchar(40) NOT NULL CHECK (version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
  currency varchar(3) NOT NULL CHECK (currency='USD'),
  rules jsonb NOT NULL CHECK (jsonb_typeof(rules)='object'),
  hash char(64) NOT NULL CHECK (hash ~ '^[a-f0-9]{64}$'),
  status varchar(16) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','PUBLISHED','RETIRED')),
  effective_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  lock_version bigint NOT NULL DEFAULT 1 CHECK (lock_version BETWEEN 1 AND 2147483647),
  created_by uuid NOT NULL REFERENCES editorial.app_user(id),
  updated_by uuid NOT NULL REFERENCES editorial.app_user(id),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE (provider, model, version)
);
CREATE UNIQUE INDEX cost_pricing_one_published ON editorial.cost_pricing_version(provider, model) WHERE status='PUBLISHED';
CREATE INDEX cost_pricing_status ON editorial.cost_pricing_version(status, provider, model);

-- cost_ledger: one row per reservation (kind='ESTIMATED') plus one append-only fact per settlement (kind='ACTUAL').
-- A settlement key is unique across the ledger, which is what makes settlement idempotent in the database too.
CREATE TABLE editorial.cost_ledger (
  id uuid PRIMARY KEY,
  article_id uuid NOT NULL REFERENCES editorial.article_job(id),
  owner_id uuid NOT NULL REFERENCES editorial.app_user(id),
  execution_id uuid NOT NULL,
  execution_kind varchar(10) NOT NULL CHECK (execution_kind IN ('AGENT','TOOL')),
  reservation_id uuid NOT NULL REFERENCES editorial.cost_ledger(id),
  kind varchar(10) NOT NULL CHECK (kind IN ('ESTIMATED','ACTUAL')),
  status varchar(10) NOT NULL CHECK (status IN ('RESERVED','SETTLED','RELEASED','UNKNOWN')),
  amount numeric(18,6) NOT NULL CHECK (amount>=0),
  currency varchar(3) NOT NULL CHECK (currency='USD'),
  pricing_version uuid NOT NULL REFERENCES editorial.cost_pricing_version(id),
  pricing_hash char(64) NOT NULL CHECK (pricing_hash ~ '^[a-f0-9]{64}$'),
  idempotency_key uuid NOT NULL UNIQUE,
  settlement_key uuid UNIQUE,
  settlement_hash char(64) CHECK (settlement_hash IS NULL OR settlement_hash ~ '^[a-f0-9]{64}$'),
  provider varchar(64) NOT NULL, model varchar(128) NOT NULL,
  capability varchar(20) NOT NULL CHECK (capability IN ('TEXT','VISION','SEARCH','GENERATION')),
  bucket_day date NOT NULL,
  claim_id uuid, slot_id uuid,
  search_calls integer NOT NULL DEFAULT 0 CHECK (search_calls>=0),
  image_units integer NOT NULL DEFAULT 0 CHECK (image_units>=0),
  input_tokens integer NOT NULL DEFAULT 0 CHECK (input_tokens>=0),
  cached_input_tokens integer NOT NULL DEFAULT 0 CHECK (cached_input_tokens>=0 AND cached_input_tokens<=input_tokens),
  output_tokens integer NOT NULL DEFAULT 0 CHECK (output_tokens>=0),
  reasoning_tokens integer CHECK (reasoning_tokens IS NULL OR reasoning_tokens>=0),
  usage jsonb NOT NULL CHECK (jsonb_typeof(usage)='object'),
  counters jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(counters)='object'),
  provider_request_id varchar(1000),
  settled_amount numeric(18,6) CHECK (settled_amount IS NULL OR settled_amount>=0),
  released_amount numeric(18,6) NOT NULL DEFAULT 0 CHECK (released_amount>=0),
  over_run numeric(18,6) NOT NULL DEFAULT 0 CHECK (over_run>=0),
  reconciled_at timestamptz,
  lock_version bigint NOT NULL DEFAULT 1 CHECK (lock_version BETWEEN 1 AND 2147483647),
  created_by uuid NOT NULL REFERENCES editorial.app_user(id),
  updated_by uuid NOT NULL REFERENCES editorial.app_user(id),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  trace_id uuid NOT NULL,
  CHECK ((kind='ESTIMATED' AND reservation_id=id) OR (kind='ACTUAL' AND reservation_id<>id)),
  CHECK ((kind='ACTUAL' AND settlement_key IS NOT NULL) OR (kind='ESTIMATED' AND settlement_key IS NULL)),
  CHECK ((status='SETTLED' AND settled_amount IS NOT NULL) OR (status<>'SETTLED' AND settled_amount IS NULL)),
  CHECK (status<>'RESERVED' OR (kind='ESTIMATED' AND reconciled_at IS NULL)),
  CHECK (status<>'RELEASED' OR released_amount>0 OR amount=0),
  CHECK (reconciled_at IS NULL OR status IN ('SETTLED','RELEASED'))
);
CREATE INDEX cost_ledger_article ON editorial.cost_ledger(article_id, kind, status, amount);
CREATE INDEX cost_ledger_day ON editorial.cost_ledger(owner_id, bucket_day, kind, status);
CREATE INDEX cost_ledger_provider ON editorial.cost_ledger(owner_id, provider, model, bucket_day, kind, status);
CREATE INDEX cost_ledger_reservation ON editorial.cost_ledger(reservation_id, kind, status);
CREATE INDEX cost_ledger_claim ON editorial.cost_ledger(claim_id) WHERE claim_id IS NOT NULL;
CREATE INDEX cost_ledger_slot ON editorial.cost_ledger(slot_id) WHERE slot_id IS NOT NULL;
CREATE INDEX cost_ledger_counters ON editorial.cost_ledger USING gin (counters jsonb_path_ops);

-- Admission: the article ceiling is a database rule, not only an application check. The article row is locked
-- before the occupancy aggregate runs, so a writer that skipped the service's scope locks still cannot
-- oversubscribe an article — serially, or with two INSERTs in flight at once. This repeats the article ceiling
-- and nothing else, because it is the single limit stored in a table (article_job.budget_limit): the daily
-- budget, the count caps and the provider quota live in configuration, so those bind the service path alone.
CREATE FUNCTION editorial.t08_admit_estimate() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,editorial AS $$
DECLARE limit_amount numeric(18,6); occupied numeric(18,6);
BEGIN
  IF NEW.kind<>'ESTIMATED' THEN RETURN NEW; END IF;
  SELECT budget_limit INTO limit_amount FROM editorial.article_job WHERE id=NEW.article_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'reservation without an article' USING ERRCODE='23503'; END IF;
  SELECT coalesce(sum(l.amount) FILTER (WHERE (l.kind='ESTIMATED' AND l.status IN ('RESERVED','UNKNOWN'))
      OR (l.kind='ACTUAL' AND l.status='SETTLED')),0) INTO occupied
    FROM editorial.cost_ledger l WHERE l.article_id=NEW.article_id;
  IF occupied + NEW.amount > limit_amount THEN RAISE EXCEPTION 'cost budget ceiling' USING ERRCODE='23514'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER cost_ledger_admit BEFORE INSERT ON editorial.cost_ledger FOR EACH ROW EXECUTE FUNCTION editorial.t08_admit_estimate();

-- Ledger mutation rules: settlement facts are append-only, an estimate keeps its frozen amount, and the status
-- machine is the same one the application enforces.
CREATE FUNCTION editorial.t08_guard_ledger() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,editorial AS $$
BEGIN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'cost ledger is append-only' USING ERRCODE='42501'; END IF;
  IF NEW.kind='ACTUAL' THEN RAISE EXCEPTION 'settlement fact is immutable' USING ERRCODE='42501'; END IF;
  IF NEW.id<>OLD.id OR NEW.article_id<>OLD.article_id OR NEW.owner_id<>OLD.owner_id OR NEW.execution_id<>OLD.execution_id
     OR NEW.execution_kind<>OLD.execution_kind OR NEW.reservation_id<>OLD.reservation_id OR NEW.kind<>OLD.kind
     OR NEW.amount<>OLD.amount OR NEW.currency<>OLD.currency OR NEW.pricing_version<>OLD.pricing_version
     OR NEW.pricing_hash<>OLD.pricing_hash OR NEW.idempotency_key<>OLD.idempotency_key OR NEW.provider<>OLD.provider
     OR NEW.model<>OLD.model OR NEW.capability<>OLD.capability OR NEW.bucket_day<>OLD.bucket_day
     OR NEW.claim_id IS DISTINCT FROM OLD.claim_id OR NEW.slot_id IS DISTINCT FROM OLD.slot_id
     OR NEW.usage<>OLD.usage OR NEW.counters<>OLD.counters OR NEW.created_by<>OLD.created_by
     OR NEW.created_at<>OLD.created_at THEN RAISE EXCEPTION 'reservation fact immutable' USING ERRCODE='42501'; END IF;
  IF NEW.lock_version<>OLD.lock_version+1 THEN RAISE EXCEPTION 'ledger revision required' USING ERRCODE='42501'; END IF;
  IF OLD.status='RESERVED' AND NEW.status IN ('SETTLED','RELEASED','UNKNOWN') THEN RETURN NEW; END IF;
  IF OLD.status='UNKNOWN' AND NEW.status IN ('SETTLED','RELEASED') THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'illegal ledger transition' USING ERRCODE='42501';
END $$;
CREATE TRIGGER cost_ledger_guard BEFORE UPDATE OR DELETE ON editorial.cost_ledger FOR EACH ROW EXECUTE FUNCTION editorial.t08_guard_ledger();

-- Every reservation must have exactly the settlement facts its status claims, so a held amount can never be
-- detached from the outcome that produced it, and the head mirror must equal the appended fact.
CREATE FUNCTION editorial.t08_ledger_consistent() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,editorial AS $$
DECLARE head editorial.cost_ledger; facts integer; wrong integer;
BEGIN
  IF NEW.kind='ACTUAL' THEN SELECT * INTO head FROM editorial.cost_ledger WHERE id=NEW.reservation_id;
  ELSE SELECT * INTO head FROM editorial.cost_ledger WHERE id=NEW.id; END IF;
  IF NOT FOUND OR head.kind<>'ESTIMATED' THEN RETURN NULL; END IF;
  SELECT count(*) INTO facts FROM editorial.cost_ledger f WHERE f.reservation_id=head.id AND f.kind='ACTUAL'
    AND f.status IN ('SETTLED','RELEASED');
  IF head.status='RESERVED' THEN
    IF facts>0 OR EXISTS(SELECT 1 FROM editorial.cost_ledger f WHERE f.reservation_id=head.id AND f.kind='ACTUAL'
      AND f.status='UNKNOWN') THEN RAISE EXCEPTION 'reserved row already settled' USING ERRCODE='23514'; END IF;
  ELSIF head.status='UNKNOWN' THEN
    IF facts>0 THEN RAISE EXCEPTION 'reconciled row still unknown' USING ERRCODE='23514'; END IF;
    IF NOT EXISTS(SELECT 1 FROM editorial.cost_ledger f WHERE f.reservation_id=head.id AND f.status='UNKNOWN')
      THEN RAISE EXCEPTION 'unresolved fact missing' USING ERRCODE='23514'; END IF;
  ELSE
    IF facts<>1 THEN RAISE EXCEPTION 'terminal row needs exactly one fact' USING ERRCODE='23514'; END IF;
    SELECT count(*) INTO wrong FROM editorial.cost_ledger f WHERE f.reservation_id=head.id AND f.kind='ACTUAL'
      AND f.status IN ('SETTLED','RELEASED')
      AND (f.status<>head.status OR f.amount IS DISTINCT FROM coalesce(head.settled_amount,0)
        OR f.settled_amount IS DISTINCT FROM head.settled_amount);
    IF wrong>0 THEN RAISE EXCEPTION 'ledger fact mismatch' USING ERRCODE='23514'; END IF;
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER cost_ledger_consistent AFTER INSERT OR UPDATE ON editorial.cost_ledger
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION editorial.t08_ledger_consistent();

-- A published price version is frozen; retirement is the only legal change, and retirement needs a revision.
CREATE FUNCTION editorial.t08_guard_pricing() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,editorial AS $$
BEGIN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'price version immutable' USING ERRCODE='42501'; END IF;
  IF NEW.id<>OLD.id OR NEW.provider<>OLD.provider OR NEW.model<>OLD.model OR NEW.version<>OLD.version
     OR NEW.currency<>OLD.currency OR NEW.rules<>OLD.rules OR NEW.hash<>OLD.hash OR NEW.created_by<>OLD.created_by
     OR NEW.created_at<>OLD.created_at THEN RAISE EXCEPTION 'price rules immutable' USING ERRCODE='42501'; END IF;
  IF OLD.status='PUBLISHED' AND NEW.status<>'RETIRED' THEN RAISE EXCEPTION 'published price only retires' USING ERRCODE='42501'; END IF;
  IF OLD.status='RETIRED' THEN RAISE EXCEPTION 'retired price version final' USING ERRCODE='42501'; END IF;
  IF NEW.lock_version<>OLD.lock_version+1 THEN RAISE EXCEPTION 'price revision required' USING ERRCODE='42501'; END IF;
  IF NEW.status='PUBLISHED' AND (SELECT count(*) FROM editorial.cost_pricing_version p WHERE p.provider=NEW.provider
     AND p.model=NEW.model AND p.status='PUBLISHED' AND p.id<>NEW.id)>0
    THEN RAISE EXCEPTION 'duplicate published price' USING ERRCODE='23505'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER cost_pricing_guard BEFORE UPDATE OR DELETE ON editorial.cost_pricing_version
  FOR EACH ROW EXECUTE FUNCTION editorial.t08_guard_pricing();

-- New domain tables are ungranted by default (R__t02_schema_permissions revokes everything from PUBLIC and from
-- the runtime role), so the runtime role needs exactly these rights and nothing else.
-- No DELETE and no TRUNCATE on cost_ledger: cancellation and cleanup are state transitions, not erasure, and a
-- retention role must never be able to drop a cost fact.
REVOKE ALL ON editorial.cost_ledger,editorial.cost_pricing_version FROM PUBLIC,editorial_runtime,editorial_retention;
GRANT SELECT ON editorial.cost_pricing_version TO editorial_runtime;
GRANT SELECT,INSERT,UPDATE ON editorial.cost_ledger TO editorial_runtime;
-- A published price is an operator action. Until an admin command exists in a later task the migrator role, not
-- the runtime role, is the only writer; the runtime role keeps read access so reservation can price a call, and
-- the guard trigger still freezes the rules once a version is published.
REVOKE ALL ON FUNCTION editorial.t08_admit_estimate(),editorial.t08_guard_ledger(),
    editorial.t08_ledger_consistent(),editorial.t08_guard_pricing() FROM PUBLIC;
