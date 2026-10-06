package com.example.editorial.article.version;

import static org.junit.jupiter.api.Assertions.*;
import com.example.editorial.EditorialApplication;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest(classes=EditorialApplication.class,webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT,properties="spring.flyway.target=3")
@org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable(named="T06_REAL_PG",matches="true")
class T07UpgradeTest extends T07Support {
    @Test void addsProposalTableWithoutChangingPopulatedT03T05T06OrExecutedMigrations()throws Exception {
        var c=signed();var article=create(c);
        String before=db.queryForObject("SELECT jsonb_build_object('users',(SELECT jsonb_agg(to_jsonb(x) ORDER BY id) FROM editorial.app_user x),'skills',(SELECT jsonb_agg(to_jsonb(x) ORDER BY id) FROM editorial.editorial_skill_version x),'jobs',(SELECT jsonb_agg(to_jsonb(x) ORDER BY id) FROM editorial.article_job x),'versions',(SELECT jsonb_agg(to_jsonb(x) ORDER BY id) FROM editorial.article_version x))::text",String.class);
        String history;
        try(var cn=admin();var s=cn.createStatement();var rs=s.executeQuery("SELECT jsonb_agg(to_jsonb(h) ORDER BY installed_rank)::text FROM editorial_migrations.flyway_schema_history h")){assertTrue(rs.next());history=rs.getString(1);}
        var f=Flyway.configure().dataSource(System.getenv("DB_URL"),"editorial_migrator",System.getenv("DB_MIGRATION_PASSWORD")).locations(System.getenv("SPRING_FLYWAY_LOCATIONS").split(",")).schemas("editorial_migrations","editorial").defaultSchema("editorial_migrations").createSchemas(false).cleanDisabled(true).load();
        assertEquals(1,f.migrate().migrationsExecuted);assertEquals(0,f.migrate().migrationsExecuted);
        assertEquals(before,db.queryForObject("SELECT jsonb_build_object('users',(SELECT jsonb_agg(to_jsonb(x) ORDER BY id) FROM editorial.app_user x),'skills',(SELECT jsonb_agg(to_jsonb(x) ORDER BY id) FROM editorial.editorial_skill_version x),'jobs',(SELECT jsonb_agg(to_jsonb(x) ORDER BY id) FROM editorial.article_job x),'versions',(SELECT jsonb_agg(to_jsonb(x) ORDER BY id) FROM editorial.article_version x))::text",String.class));
        try(var cn=admin();var s=cn.createStatement();var rs=s.executeQuery("SELECT jsonb_agg(to_jsonb(h) ORDER BY installed_rank)::text FROM editorial_migrations.flyway_schema_history h WHERE version IS DISTINCT FROM '4'")){assertTrue(rs.next());assertEquals(history,rs.getString(1));}
        assertEquals(200,c.get(path(article)+"/proposals").statusCode());assertEquals(1,count(article));
    }
}
