-- Incremental correction for functions created before the global default fix.
-- Keep explicit domain grants to editorial_runtime. Only remove PUBLIC access
-- from migration-owned routines in the application schema; do not touch other
-- owners, schemas, tables or columns. RESTRICT intentionally fails on dependencies.
DO $t02$
DECLARE
    routine record;
BEGIN
    FOR routine IN
        SELECT n.nspname, p.proname, pg_get_function_identity_arguments(p.oid) AS args
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'editorial'
          AND p.proowner = 'editorial_migrator'::regrole
          AND EXISTS (
              SELECT 1 FROM aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) acl
              WHERE acl.grantee = 0 AND acl.privilege_type = 'EXECUTE'
          )
    LOOP
        EXECUTE format('REVOKE EXECUTE ON ROUTINE %I.%I(%s) FROM PUBLIC RESTRICT',
                       routine.nspname, routine.proname, routine.args);
    END LOOP;
END
$t02$;
