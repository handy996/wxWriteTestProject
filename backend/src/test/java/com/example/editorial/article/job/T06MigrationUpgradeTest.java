package com.example.editorial.article.job;

import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.flywaydb.core.Flyway;
import java.sql.*;
import java.util.UUID;

@EnabledIfEnvironmentVariable(named="T06_REAL_PG",matches="true")
class T06MigrationUpgradeTest {
    Flyway migrateTo(String target) {
        var c=Flyway.configure().dataSource(System.getenv("DB_URL"),"editorial_migrator",System.getenv("DB_MIGRATION_PASSWORD"))
            .locations(System.getenv("SPRING_FLYWAY_LOCATIONS").split(","))
            .schemas("editorial_migrations","editorial").defaultSchema("editorial_migrations").createSchemas(false).cleanDisabled(true);
        if(target!=null)c.target(target);return c.load();
    }
    String query(Connection c,String sql)throws Exception {try(var s=c.createStatement();var r=s.executeQuery(sql)){assertTrue(r.next());return r.getString(1);}}
    @Test void upgradesPopulatedT03T05DraftWithoutChangingRowsOrHistory()throws Exception {
        migrateTo("2").migrate();
        try(var c=DriverManager.getConnection(System.getenv("DB_URL"),"editorial_admin",System.getenv("T06_ADMIN_PASSWORD"))) {
            UUID id=UUID.randomUUID(),skill=UUID.randomUUID();
            try(var s=c.createStatement()) {
                s.execute("INSERT INTO editorial.app_user(id,username,display_name,actor_type) VALUES('"+id+"','upgrade-actor','Existing actor','SYSTEM_WORKER')");
                s.execute("INSERT INTO editorial.editorial_skill(id,code,name,owner_id,created_by) VALUES('"+skill+"','upgrade-skill','Existing skill','"+id+"','"+id+"')");
            }
            String before=query(c,"SELECT to_jsonb(s)::text FROM editorial.editorial_skill s WHERE id='"+skill+"'");
            String history=query(c,"SELECT json_agg(h ORDER BY installed_rank)::text FROM editorial_migrations.flyway_schema_history h WHERE version IN ('1','2')");
            assertEquals("0",query(c,"SELECT count(*) FROM information_schema.tables WHERE table_schema='editorial' AND table_name IN ('article_job','article_version')"));
            assertEquals(1,migrateTo(null).migrate().migrationsExecuted);
            assertEquals("2",query(c,"SELECT count(*) FROM information_schema.tables WHERE table_schema='editorial' AND table_name IN ('article_job','article_version')"));
            assertEquals(before,query(c,"SELECT to_jsonb(s)::text FROM editorial.editorial_skill s WHERE id='"+skill+"'"));
            assertEquals(history,query(c,"SELECT json_agg(h ORDER BY installed_rank)::text FROM editorial_migrations.flyway_schema_history h WHERE version IN ('1','2')"));
            assertEquals(0,migrateTo(null).migrate().migrationsExecuted);
            assertEquals("false",query(c,"SELECT has_table_privilege('editorial_runtime','editorial.article_version','UPDATE')::text"));
        }
    }
}
