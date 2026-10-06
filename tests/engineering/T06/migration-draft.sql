-- T06 only. Main agent assigns the global version after T03 + T05; no other domain tables.
CREATE TABLE editorial.article_job (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL REFERENCES editorial.app_user(id),
 name varchar(300) NOT NULL, original_version_id uuid, current_version_id uuid,
 skill_version_id uuid NOT NULL REFERENCES editorial.editorial_skill_version(id),
 target_length integer NOT NULL CHECK(target_length BETWEEN 1500 AND 5000),
 budget_limit numeric(18,6) NOT NULL CHECK(budget_limit>=0), currency varchar(3) NOT NULL CHECK(currency='USD'),
 spent_amount numeric(18,6) NOT NULL DEFAULT 0 CHECK(spent_amount>=0),
 reserved_amount numeric(18,6) NOT NULL DEFAULT 0 CHECK(reserved_amount>=0),
 status varchar(40) NOT NULL DEFAULT 'CREATED', lock_version bigint NOT NULL DEFAULT 1 CHECK(lock_version BETWEEN 1 AND 2147483647),
 summary jsonb NOT NULL, style_snapshot jsonb NOT NULL, original_rights_basis jsonb NOT NULL CHECK(jsonb_typeof(original_rights_basis)='array' AND jsonb_array_length(original_rights_basis)>0),
 deletion_pending boolean NOT NULL DEFAULT false,
 created_by uuid NOT NULL REFERENCES editorial.app_user(id), updated_by uuid NOT NULL REFERENCES editorial.app_user(id),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp(), archived_at timestamptz,
 CHECK(status IN ('CREATED','ANALYZING','ANALYZED','FACT_CHECKING','FACT_VERIFIED','WRITING','DRAFTED','REVIEWING','REVIEWED','REVISING','REVISED','FACT_RECHECKING','FACT_RECHECKED','IMAGE_PLANNING','IMAGE_SEARCHING','IMAGE_GENERATING','WAITING_IMAGE_SELECTION','IMAGES_READY','FINAL_QA','READY_FOR_REVIEW','HUMAN_REVIEW','APPROVED','REJECTED','NEEDS_REVISION','WAITING_MANUAL','PAUSED','FAILED','CANCELLED'))
);
CREATE INDEX article_job_owner_status ON editorial.article_job(owner_id,status,updated_at DESC);
CREATE INDEX article_job_skill ON editorial.article_job(skill_version_id);
CREATE INDEX article_job_original ON editorial.article_job(id,original_version_id);
CREATE INDEX article_job_current ON editorial.article_job(id,current_version_id);
CREATE INDEX article_job_created_by ON editorial.article_job(created_by);
CREATE INDEX article_job_updated_by ON editorial.article_job(updated_by);
CREATE TABLE editorial.article_version (
 id uuid PRIMARY KEY, article_id uuid NOT NULL REFERENCES editorial.article_job(id),
 version_no integer NOT NULL CHECK(version_no>0), parent_version_id uuid, restored_from_version_id uuid,
 kind varchar(20) NOT NULL CHECK(kind IN ('ORIGINAL','DRAFT','REVISION','MANUAL','RESTORE')),
 document jsonb NOT NULL, content_hash char(64) NOT NULL CHECK(content_hash~'^[a-f0-9]{64}$'),
 input_hash char(64) NOT NULL CHECK(input_hash~'^[a-f0-9]{64}$'), style_snapshot jsonb NOT NULL,
 object_ref jsonb NOT NULL, created_by uuid NOT NULL REFERENCES editorial.app_user(id), created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(article_id,id), UNIQUE(article_id,version_no),
 CHECK ((kind='ORIGINAL' AND version_no=1 AND parent_version_id IS NULL AND restored_from_version_id IS NULL) OR (kind<>'ORIGINAL' AND version_no>1 AND parent_version_id IS NOT NULL)),
 FOREIGN KEY(article_id,parent_version_id) REFERENCES editorial.article_version(article_id,id),
 FOREIGN KEY(article_id,restored_from_version_id) REFERENCES editorial.article_version(article_id,id)
);
CREATE UNIQUE INDEX article_one_original ON editorial.article_version(article_id) WHERE kind='ORIGINAL';
CREATE UNIQUE INDEX article_object_key ON editorial.article_version((object_ref->>'key'));
CREATE INDEX article_version_created ON editorial.article_version(article_id,created_at);
CREATE INDEX article_version_parent ON editorial.article_version(article_id,parent_version_id);
CREATE INDEX article_version_restored ON editorial.article_version(article_id,restored_from_version_id);
CREATE INDEX article_version_creator ON editorial.article_version(created_by);
ALTER TABLE editorial.article_job ADD CONSTRAINT article_original_fk FOREIGN KEY(id,original_version_id) REFERENCES editorial.article_version(article_id,id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE editorial.article_job ADD CONSTRAINT article_current_fk FOREIGN KEY(id,current_version_id) REFERENCES editorial.article_version(article_id,id) DEFERRABLE INITIALLY DEFERRED;
CREATE FUNCTION editorial.t06_job_complete() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,editorial AS $$
DECLARE j editorial.article_job; r jsonb;
BEGIN
 SELECT * INTO j FROM editorial.article_job WHERE id=NEW.id;
 IF NOT FOUND THEN RETURN NULL; END IF;
 IF j.original_version_id IS NULL OR j.current_version_id IS NULL THEN RAISE EXCEPTION 'incomplete article job' USING ERRCODE='23514'; END IF;
 IF NOT EXISTS(SELECT 1 FROM editorial.article_version WHERE article_id=j.id AND id=j.original_version_id AND kind='ORIGINAL') THEN RAISE EXCEPTION 'invalid original pointer' USING ERRCODE='23514'; END IF;
 IF j.summary->>'id' IS DISTINCT FROM j.id::text OR j.summary->>'ownerId' IS DISTINCT FROM j.owner_id::text
 OR j.summary->>'originalVersionId' IS DISTINCT FROM j.original_version_id::text OR j.summary->>'currentVersionId' IS DISTINCT FROM j.current_version_id::text
 OR j.summary->>'skillVersionId' IS DISTINCT FROM j.skill_version_id::text OR j.summary->>'status' IS DISTINCT FROM j.status
 OR j.summary->>'name' IS DISTINCT FROM j.name OR (j.summary->>'lockVersion')::bigint IS DISTINCT FROM j.lock_version
 OR (j.summary->>'targetLength')::integer IS DISTINCT FROM j.target_length OR (j.summary->>'budget')::numeric IS DISTINCT FROM j.budget_limit
 OR (j.summary->>'archived')::boolean IS DISTINCT FROM (j.archived_at IS NOT NULL) THEN RAISE EXCEPTION 'article projection mismatch' USING ERRCODE='23514'; END IF;
 FOR r IN SELECT value FROM jsonb_array_elements(j.original_rights_basis) LOOP
   IF r->>'articleId' IS DISTINCT FROM j.id::text OR NOT EXISTS(SELECT 1 FROM editorial.article_version v WHERE v.article_id=j.id AND v.id=(r->>'versionId')::uuid AND v.content_hash=r->>'contentHash') THEN RAISE EXCEPTION 'rights scope mismatch' USING ERRCODE='23514'; END IF;
 END LOOP;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER article_complete AFTER INSERT OR UPDATE ON editorial.article_job DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION editorial.t06_job_complete();
CREATE FUNCTION editorial.t06_guard_job() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,editorial AS $$
DECLARE i integer;
BEGIN
 IF NEW.id<>OLD.id OR NEW.owner_id<>OLD.owner_id OR NEW.created_by<>OLD.created_by OR NEW.created_at<>OLD.created_at THEN RAISE EXCEPTION 'article identity immutable'; END IF;
 IF OLD.original_version_id IS NOT NULL AND NEW.original_version_id IS DISTINCT FROM OLD.original_version_id THEN RAISE EXCEPTION 'original pointer immutable'; END IF;
 IF OLD.original_version_id IS NOT NULL AND NEW.lock_version<>OLD.lock_version+1 THEN RAISE EXCEPTION 'article revision required'; END IF;
 IF OLD.status='CANCELLED' AND (NEW.status<>'CANCELLED' OR NEW.current_version_id<>OLD.current_version_id OR NEW.skill_version_id<>OLD.skill_version_id OR NEW.target_length<>OLD.target_length) THEN RAISE EXCEPTION 'cancelled article'; END IF;
 IF OLD.deletion_pending AND NOT NEW.deletion_pending THEN RAISE EXCEPTION 'deletion cannot be revoked'; END IF;
 IF jsonb_array_length(NEW.original_rights_basis)<jsonb_array_length(OLD.original_rights_basis) THEN RAISE EXCEPTION 'rights append only'; END IF;
 FOR i IN 0..jsonb_array_length(OLD.original_rights_basis)-1 LOOP
  IF NEW.original_rights_basis->i IS DISTINCT FROM OLD.original_rights_basis->i THEN RAISE EXCEPTION 'rights append only'; END IF;
 END LOOP;
 RETURN NEW;
END $$;
CREATE TRIGGER article_guard BEFORE UPDATE ON editorial.article_job FOR EACH ROW EXECUTE FUNCTION editorial.t06_guard_job();
CREATE FUNCTION editorial.t06_guard_version() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,editorial AS $$
DECLARE j editorial.article_job;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'article version immutable'; END IF;
 SELECT * INTO j FROM editorial.article_job WHERE id=NEW.article_id FOR UPDATE;
 IF j.deletion_pending OR j.status='CANCELLED' THEN RAISE EXCEPTION 'article write blocked'; END IF;
 IF NEW.document->'meta'->>'id' IS DISTINCT FROM NEW.id::text OR NEW.document->'meta'->>'articleId' IS DISTINCT FROM NEW.article_id::text
 OR NEW.document->'meta'->>'ownerId' IS DISTINCT FROM j.owner_id::text OR NEW.document->'meta'->>'versionId' IS DISTINCT FROM NEW.id::text
 OR NEW.document->'meta'->>'contentHash' IS DISTINCT FROM NEW.content_hash OR NEW.document->>'kind' IS DISTINCT FROM NEW.kind
 OR (NEW.document->>'versionNo')::integer IS DISTINCT FROM NEW.version_no THEN RAISE EXCEPTION 'version projection mismatch' USING ERRCODE='23514'; END IF;
 IF EXISTS(SELECT 1 FROM editorial.article_version WHERE article_id=NEW.article_id AND id IN (NEW.parent_version_id,NEW.restored_from_version_id) AND version_no>=NEW.version_no) THEN RAISE EXCEPTION 'version ancestry invalid' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER version_guard BEFORE INSERT OR UPDATE ON editorial.article_version FOR EACH ROW EXECUTE FUNCTION editorial.t06_guard_version();
REVOKE ALL ON editorial.article_job,editorial.article_version FROM editorial_runtime;
GRANT SELECT,INSERT,UPDATE ON editorial.article_job TO editorial_runtime;
GRANT SELECT,INSERT ON editorial.article_version TO editorial_runtime;
REVOKE ALL ON FUNCTION editorial.t06_job_complete(),editorial.t06_guard_job(),editorial.t06_guard_version() FROM PUBLIC;
