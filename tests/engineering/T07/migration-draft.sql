-- T07 draft; main agent assigns global Flyway version. Existing T03/T05/T06 migrations untouched.
CREATE TABLE editorial.change_proposal (
 id uuid PRIMARY KEY, article_id uuid NOT NULL REFERENCES editorial.article_job(id),
 owner_id uuid NOT NULL REFERENCES editorial.app_user(id),
 base_version_id uuid NOT NULL, proposed_version_id uuid NOT NULL, accepted_version_id uuid,
 status varchar(20) NOT NULL CHECK(status IN ('PENDING','ACCEPTED','REJECTED','STALE')),
 document jsonb NOT NULL, reason varchar(1000), lock_version bigint NOT NULL DEFAULT 1,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(article_id,id), UNIQUE(article_id,proposed_version_id),
 FOREIGN KEY(article_id,base_version_id) REFERENCES editorial.article_version(article_id,id),
 FOREIGN KEY(article_id,proposed_version_id) REFERENCES editorial.article_version(article_id,id),
 FOREIGN KEY(article_id,accepted_version_id) REFERENCES editorial.article_version(article_id,id),
 CHECK((status='ACCEPTED')=(accepted_version_id IS NOT NULL)),
 CHECK(status<>'REJECTED' OR (reason IS NOT NULL AND length(btrim(reason))>0))
);
CREATE INDEX proposal_owner_page ON editorial.change_proposal(owner_id,article_id,id DESC);
CREATE INDEX proposal_status_page ON editorial.change_proposal(article_id,status,id DESC);
CREATE INDEX proposal_base ON editorial.change_proposal(article_id,base_version_id);
CREATE INDEX proposal_accepted ON editorial.change_proposal(article_id,accepted_version_id);
CREATE FUNCTION editorial.t07_proposal_guard() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,editorial AS $$
DECLARE j editorial.article_job;
BEGIN
 SELECT * INTO j FROM editorial.article_job WHERE id=NEW.article_id FOR UPDATE;
 IF j.owner_id<>NEW.owner_id OR j.deletion_pending OR j.status='CANCELLED' THEN RAISE EXCEPTION 'proposal scope blocked'; END IF;
 IF TG_OP='UPDATE' THEN
  IF OLD.status<>'PENDING' OR NEW.lock_version<>OLD.lock_version+1 OR NEW.id<>OLD.id OR NEW.article_id<>OLD.article_id
   OR NEW.owner_id<>OLD.owner_id OR NEW.base_version_id<>OLD.base_version_id OR NEW.proposed_version_id<>OLD.proposed_version_id
   OR NEW.created_at<>OLD.created_at OR (NEW.document - 'status' - 'acceptedVersionId' - 'meta')<>(OLD.document - 'status' - 'acceptedVersionId' - 'meta')
   OR ((NEW.document->'meta') - 'stale')<>((OLD.document->'meta') - 'stale') THEN RAISE EXCEPTION 'proposal immutable or disposed'; END IF;
 END IF;
 IF NEW.document->'meta'->>'id' IS DISTINCT FROM NEW.id::text OR NEW.document->'meta'->>'articleId' IS DISTINCT FROM NEW.article_id::text
  OR NEW.document->'meta'->>'ownerId' IS DISTINCT FROM NEW.owner_id::text OR NEW.document->>'baseVersionId' IS DISTINCT FROM NEW.base_version_id::text
  OR NEW.document->>'proposedVersionId' IS DISTINCT FROM NEW.proposed_version_id::text OR NEW.document->>'acceptedVersionId' IS DISTINCT FROM NEW.accepted_version_id::text
  OR NEW.document->>'status' IS DISTINCT FROM NEW.status THEN RAISE EXCEPTION 'proposal projection mismatch'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER proposal_guard BEFORE INSERT OR UPDATE ON editorial.change_proposal FOR EACH ROW EXECUTE FUNCTION editorial.t07_proposal_guard();
REVOKE ALL ON editorial.change_proposal FROM editorial_runtime;
GRANT SELECT,INSERT,UPDATE ON editorial.change_proposal TO editorial_runtime;
REVOKE ALL ON FUNCTION editorial.t07_proposal_guard() FROM PUBLIC;
