-- DESIGN DRAFT ONLY. T06/main agent must allocate Flyway version after schema integration.
-- Not a complete migration; not executed against PostgreSQL in T00.
-- Assumes article_job(id, original_version_id,current_version_id) and
-- article_version(article_id,id,kind) exist with UNIQUE(article_id,id).
ALTER TABLE article_job ADD CONSTRAINT fk_job_original_same_article
  FOREIGN KEY (id, original_version_id) REFERENCES article_version(article_id,id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE article_job ADD CONSTRAINT fk_job_current_same_article
  FOREIGN KEY (id, current_version_id) REFERENCES article_version(article_id,id)
  DEFERRABLE INITIALLY DEFERRED;

CREATE FUNCTION check_job_complete_at_commit() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE j record;
BEGIN
  -- Re-read final row; NEW may represent the initial insert with null pointers.
  SELECT * INTO j FROM article_job WHERE id = NEW.id;
  IF NOT FOUND THEN RETURN NULL; END IF; -- approved retention deletion in same tx
  IF j.original_version_id IS NULL OR j.current_version_id IS NULL THEN
    RAISE EXCEPTION 'incomplete article job' USING ERRCODE = '23514';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM article_version v WHERE v.article_id=j.id
      AND v.id=j.original_version_id AND v.kind='ORIGINAL') THEN
    RAISE EXCEPTION 'original must be same-article ORIGINAL' USING ERRCODE = '23514';
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER article_job_complete
  AFTER INSERT OR UPDATE ON article_job DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION check_job_complete_at_commit();

-- Integrator: also freeze original_version_id after initial completion; runtime
-- cannot delete versions. Install config publication immutability triggers and
-- column-only UPDATE(active) grants separately. Never blanket-revoke UPDATE on
-- all configuration tables, nor grant UPDATE on selection content.
