-- Isolated regression fixture only: NEVER package as an application migration.
CREATE FUNCTION editorial.t02_versioned_probe() RETURNS integer
LANGUAGE sql AS 'SELECT 42';
DO $probe$
BEGIN
    IF has_function_privilege('editorial_runtime', 'editorial.t02_versioned_probe()', 'EXECUTE') THEN
        RAISE EXCEPTION 'T02 regression: function executable before repeatable migrations';
    END IF;
END
$probe$;
