package com.example.editorial.storage;

import java.sql.Connection;
import java.sql.SQLException;
import java.util.Objects;
import java.util.UUID;
import javax.sql.DataSource;
import org.springframework.jdbc.core.ConnectionCallback;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.orm.jpa.JpaTransactionManager;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionSynchronizationManager;

/** Cross-process object coordination on the same database as the reference transaction.
 * PostgreSQL releases this lock only at transaction completion, including rollback/crash.
 * UUID collisions only serialize unrelated objects; they cannot weaken protection.
 */
public final class ObjectTransactionLock {
    private final JdbcTemplate db;

    public ObjectTransactionLock(PlatformTransactionManager manager) {
        DataSource source;
        if (manager instanceof DataSourceTransactionManager jdbc) source = jdbc.getDataSource();
        else if (manager instanceof JpaTransactionManager jpa) source = jpa.getDataSource();
        else throw new IllegalArgumentException("storage requires a PostgreSQL JDBC/JPA transaction manager");
        db = new JdbcTemplate(Objects.requireNonNull(source));
    }

    public void acquire(String objectId) {
        if (!TransactionSynchronizationManager.isActualTransactionActive())
            throw new IllegalStateException("object coordination requires an active reference transaction");
        UUID id = UUID.fromString(objectId);
        long lockId = id.getMostSignificantBits() ^ id.getLeastSignificantBits();
        db.execute((ConnectionCallback<Void>) connection -> {
            if (connection.getAutoCommit() || connection.getTransactionIsolation() != Connection.TRANSACTION_READ_COMMITTED)
                throw new SQLException("object coordination requires READ COMMITTED on the reference connection");
            try (var statement = connection.prepareStatement("SELECT pg_advisory_xact_lock(?)")) {
                statement.setLong(1, lockId);
                statement.execute();
            }
            return null;
        });
    }
}
