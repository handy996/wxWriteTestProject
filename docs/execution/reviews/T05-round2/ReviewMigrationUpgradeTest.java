package com.example.editorial.editorial.skill;
import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.Test;
import org.flywaydb.core.Flyway;
import java.sql.*;
import java.util.*;
class ReviewMigrationUpgradeTest {
    Flyway migration(String target) {
        var config=Flyway.configure().dataSource(System.getenv("DB_URL"),"editorial_migrator",System.getenv("DB_MIGRATION_PASSWORD"))
            .locations(System.getenv("SPRING_FLYWAY_LOCATIONS").split(","))
            .schemas("editorial_migrations","editorial").defaultSchema("editorial_migrations").createSchemas(false).cleanDisabled(true);
        if(target!=null)config.target(target);
        return config.load();
    }
    String query(Connection c,String sql)throws Exception {
        try(var s=c.createStatement();var r=s.executeQuery(sql)){assertTrue(r.next());return r.getString(1);}
    }
    @Test void addT05ToPopulatedT03DraftAndRepeatWithoutChangingHistory()throws Exception {
        migration("1").migrate();
        try(var c=DriverManager.getConnection(System.getenv("DB_URL"),"editorial_admin",System.getenv("T05_ADMIN_PASSWORD"))) {
            UUID id=UUID.randomUUID();
            try(var s=c.prepareStatement("INSERT INTO editorial.app_user(id,username,display_name,actor_type) VALUES(?,?,?,'SYSTEM_WORKER')")) {
                s.setObject(1,id);s.setString(2,"upgrade-existing-system");s.setString(3,"Existing actor retained");assertEquals(1,s.executeUpdate());
            }
            String userBefore=query(c,"SELECT to_jsonb(u)::text FROM editorial.app_user u WHERE id='"+id+"'");
            String historyBefore=query(c,"SELECT to_jsonb(h)::text FROM editorial_migrations.flyway_schema_history h WHERE version='1'");
            assertEquals("0",query(c,"SELECT count(*) FROM information_schema.tables WHERE table_schema='editorial' AND table_name IN ('editorial_skill','editorial_skill_version','policy_version','prompt_version')"));
            var result=migration(null).migrate();
            assertEquals(1,result.migrationsExecuted);
            assertEquals("4",query(c,"SELECT count(*) FROM information_schema.tables WHERE table_schema='editorial' AND table_name IN ('editorial_skill','editorial_skill_version','policy_version','prompt_version')"));
            assertEquals(userBefore,query(c,"SELECT to_jsonb(u)::text FROM editorial.app_user u WHERE id='"+id+"'"));
            assertEquals(historyBefore,query(c,"SELECT to_jsonb(h)::text FROM editorial_migrations.flyway_schema_history h WHERE version='1'"));
            String allHistory=query(c,"SELECT json_agg(h ORDER BY installed_rank)::text FROM editorial_migrations.flyway_schema_history h");
            assertEquals(0,migration(null).migrate().migrationsExecuted);
            assertEquals(allHistory,query(c,"SELECT json_agg(h ORDER BY installed_rank)::text FROM editorial_migrations.flyway_schema_history h"));
        }
    }
}
