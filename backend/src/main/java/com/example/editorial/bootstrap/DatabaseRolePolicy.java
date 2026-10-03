package com.example.editorial.bootstrap;

import java.sql.Connection;
import java.sql.ResultSet;
import javax.sql.DataSource;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

/** Verify effective DB privileges, including credentials supplied through a JDBC URL. */
@Component
final class DatabaseRolePolicy implements ApplicationRunner {
    private final DataSource dataSource;
    DatabaseRolePolicy(DataSource dataSource) { this.dataSource = dataSource; }

    @Override public void run(ApplicationArguments args) throws Exception {
        try (Connection connection = dataSource.getConnection();
             var statement = connection.createStatement();
             ResultSet result = statement.executeQuery("""
                 SELECT current_user = 'editorial_runtime'
                    AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
                    AND NOT pg_has_role(current_user, 'editorial_migrator', 'MEMBER')
                    AND NOT pg_has_role(current_user, 'editorial_retention', 'MEMBER')
                    AND NOT has_database_privilege(current_database(), 'CREATE')
                    AND NOT has_database_privilege(current_database(), 'TEMP')
                    AND NOT has_schema_privilege('editorial', 'CREATE')
                    AND NOT has_schema_privilege('public', 'CREATE')
                    AND NOT has_schema_privilege('editorial_migrations', 'USAGE')
                 FROM pg_roles WHERE rolname = current_user
                 """)) {
            if (!result.next() || !result.getBoolean(1)) {
                throw new IllegalStateException("T02_DB_PRIVILEGES: runtime role has unexpected privileges");
            }
        }
    }
}
