# This is a realistic database testing module that simulates testing database operations
import random
import time
from datetime import datetime, timedelta

import pytest


# Mock database connection and cursor classes
class MockCursor:
    def __init__(self, connection, query_times=None):
        self.connection = connection
        self.query_times = query_times or {}
        self.rowcount = 0
        self.description = []
        self._results = []

    def execute(self, query, params=None):
        # Simulate query execution time based on query complexity
        query_type = query.strip().lower().split()[0] if query.strip() else ""

        # Determine query time based on type and complexity
        if query_type in self.query_times:
            base_time = self.query_times[query_type]
        else:
            base_time = 0.05  # Default time

        # Add randomness and occasional slowness
        if random.random() < 0.1:
            # Simulate an occasionally slow query
            time.sleep(base_time * random.uniform(3, 8))
        else:
            time.sleep(base_time * random.uniform(0.8, 1.5))

        # Set rowcount based on query type
        if query_type == "select":
            self.rowcount = random.randint(5, 50)
            self._results = [self._generate_row() for _ in range(self.rowcount)]
        elif query_type in ("insert", "update", "delete"):
            self.rowcount = random.randint(1, 10)

        # Simulate database errors occasionally
        if random.random() < 0.08:
            error_types = {
                "select": "DatabaseError: Error executing query",
                "insert": "IntegrityError: Duplicate key value violates unique constraint",
                "update": "DatabaseError: Update failed due to constraint violation",
                "delete": "DatabaseError: Cannot delete due to foreign key constraint",
            }
            if query_type in error_types and random.random() < 0.5:
                raise Exception(error_types[query_type])

        return self

    def fetchall(self):
        return self._results

    def fetchone(self):
        return self._results[0] if self._results else None

    def close(self):
        pass

    def _generate_row(self):
        # Generate a random row of data
        return {
            "id": random.randint(1, 10000),
            "name": f"Item-{random.randint(1000, 9999)}",
            "created": datetime.now() - timedelta(days=random.randint(0, 30)),
            "status": random.choice(["active", "inactive", "pending", "archived"]),
            "value": round(random.uniform(10, 1000), 2),
        }


class MockConnection:
    def __init__(self, db_type="postgres"):
        self.db_type = db_type
        self.is_connected = True
        self.autocommit = False
        self.in_transaction = False

        # Define typical query times by database type and operation
        self.query_times = {
            "postgres": {
                "select": 0.08,
                "insert": 0.05,
                "update": 0.06,
                "delete": 0.04,
                "create": 0.1,
                "drop": 0.03,
            },
            "mysql": {
                "select": 0.07,
                "insert": 0.04,
                "update": 0.05,
                "delete": 0.03,
                "create": 0.09,
                "drop": 0.02,
            },
        }

    def cursor(self):
        if not self.is_connected:
            raise Exception("DatabaseError: Connection is closed")
        return MockCursor(self, self.query_times.get(self.db_type, {}))

    def commit(self):
        if not self.is_connected:
            raise Exception("DatabaseError: Connection is closed")

        # Simulate commit time
        time.sleep(random.uniform(0.01, 0.05))

        # Simulate commit failures occasionally
        if self.in_transaction and random.random() < 0.05:
            raise Exception("DatabaseError: Could not commit transaction")

        self.in_transaction = False

    def rollback(self):
        if not self.is_connected:
            raise Exception("DatabaseError: Connection is closed")

        # Simulate rollback time
        time.sleep(random.uniform(0.01, 0.03))
        self.in_transaction = False

    def close(self):
        # Simulate connection close time
        time.sleep(random.uniform(0.01, 0.02))
        self.is_connected = False


# Fixtures for database testing
@pytest.fixture
def db_connection():
    """Create a database connection for testing."""
    # Randomly choose a database type to test compatibility
    db_type = random.choice(["postgres", "mysql"])
    conn = MockConnection(db_type=db_type)
    yield conn
    conn.close()


@pytest.fixture
def transaction(db_connection):
    """Create a transaction for testing."""
    conn = db_connection
    conn.in_transaction = True
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        if conn.in_transaction:
            conn.rollback()


# Basic database tests
def test_db_connection(db_connection):
    """Test database connection."""
    assert db_connection.is_connected

    # Test creating a cursor
    cursor = db_connection.cursor()
    assert cursor is not None


def test_simple_query(db_connection):
    """Test executing a simple query."""
    cursor = db_connection.cursor()
    cursor.execute("SELECT * FROM users LIMIT 10")

    # Check that we got some results
    results = cursor.fetchall()
    assert len(results) > 0


# Test with transaction that should succeed
def test_successful_transaction(transaction):
    """Test a successful database transaction."""
    conn = transaction
    cursor = conn.cursor()

    # Insert a new record
    cursor.execute("INSERT INTO users (name, email) VALUES ('Test User', 'test@example.com')")

    # Update a record
    cursor.execute("UPDATE users SET status = 'active' WHERE email = 'test@example.com'")

    # Commit the transaction
    conn.commit()

    # Verify the record exists
    cursor.execute("SELECT * FROM users WHERE email = 'test@example.com'")
    result = cursor.fetchone()
    assert result is not None
    assert result["status"] == "active"


# Test with transaction that should be rolled back
def test_transaction_rollback(transaction):
    """Test rolling back a transaction after an error."""
    conn = transaction
    cursor = conn.cursor()

    # Insert a new record
    cursor.execute("INSERT INTO users (name, email) VALUES ('Rollback User', 'rollback@example.com')")

    # Simulate an error condition about 20% of the time
    if random.random() < 0.2:
        # Force a rollback
        conn.rollback()

        # Verify the record doesn't exist (should return None after rollback)
        cursor.execute("SELECT * FROM users WHERE email = 'rollback@example.com'")
        result = cursor.fetchone()
        assert result is None
        pytest.fail("Transaction was rolled back due to an error")
    else:
        # Complete the transaction normally
        conn.commit()

        # Verify the record exists
        cursor.execute("SELECT * FROM users WHERE email = 'rollback@example.com'")
        result = cursor.fetchone()
        assert result is not None


# Test with occasional connection issues
def test_connection_stability(db_connection):
    """Test database connection stability."""
    conn = db_connection

    # Simulate connection issues about 5% of the time
    if random.random() < 0.05:
        conn.is_connected = False

        # This should raise an exception
        with pytest.raises(Exception):
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            pytest.fail("Connection was lost but no exception was raised")
    else:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        assert cursor.fetchone() is not None


# Test with slow queries
def test_query_performance(db_connection):
    """Test query performance with complex joins."""
    cursor = db_connection.cursor()

    # Complex query with joins that might be slow
    query = """
    SELECT u.id, u.name, u.email, o.id as order_id, o.total,
           p.id as product_id, p.name as product_name
    FROM users u
    JOIN orders o ON u.id = o.user_id
    JOIN order_items oi ON o.id = oi.order_id
    JOIN products p ON oi.product_id = p.id
    WHERE u.status = 'active'
    AND o.created > '2023-01-01'
    ORDER BY o.created DESC
    LIMIT 100
    """

    # Set a timeout for the query
    start_time = time.time()
    timeout = 1.0  # 1 second timeout

    # Execute the query
    try:
        cursor.execute(query)
        results = cursor.fetchall()

        # Check execution time
        execution_time = time.time() - start_time

        # Fail if the query was too slow (simulating a performance test failure)
        if execution_time > timeout:
            pytest.fail(f"Query took too long to execute: {execution_time:.2f}s > {timeout:.2f}s")

        assert len(results) > 0
    except Exception as e:
        # This will catch both timeout errors and database errors
        pytest.fail(f"Query failed: {str(e)}")


# Test with data validation
def test_data_integrity(db_connection):
    """Test data integrity constraints."""
    cursor = db_connection.cursor()

    # Try to insert a record with invalid data
    try:
        cursor.execute("INSERT INTO users (name, email) VALUES (NULL, 'invalid@example.com')")
        db_connection.commit()

        # If we get here without an exception, the test should fail randomly
        # to simulate integrity constraint violations
        if random.random() < 0.3:
            pytest.fail("Data integrity constraint should have been violated")
    except Exception as e:
        # Expected exception for data integrity violation
        assert "constraint" in str(e).lower() or "null" in str(e).lower()


# Test with database-specific features
def test_db_specific_features(db_connection):
    """Test database-specific features."""
    # This test will fail on certain database types
    if db_connection.db_type == "mysql" and random.random() < 0.25:
        pytest.fail("This feature is not supported in MySQL")

    cursor = db_connection.cursor()

    # Use a database-specific query syntax
    if db_connection.db_type == "postgres":
        cursor.execute("SELECT * FROM users WHERE email ILIKE '%@example.com'")
    else:
        cursor.execute("SELECT * FROM users WHERE email LIKE '%@example.com'")

    results = cursor.fetchall()
    assert len(results) >= 0


# Test with dependency chain
@pytest.mark.dependency()
def test_create_schema(db_connection):
    """Test creating a database schema."""
    cursor = db_connection.cursor()

    # Create a test schema
    cursor.execute("CREATE SCHEMA IF NOT EXISTS test_schema")
    db_connection.commit()

    # This test will fail occasionally
    if random.random() < 0.07:
        pytest.fail("Failed to create schema")


@pytest.mark.dependency(depends=["test_create_schema"])
def test_create_table(db_connection):
    """Test creating a table in the schema (depends on schema creation)."""
    cursor = db_connection.cursor()

    # Create a test table
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS test_schema.test_table (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    )
    db_connection.commit()

    # Verify the table exists
    cursor.execute("SELECT * FROM test_schema.test_table")
    assert True


@pytest.mark.dependency(depends=["test_create_table"])
def test_insert_data(db_connection):
    """Test inserting data into the table (depends on table creation)."""
    cursor = db_connection.cursor()

    # Insert test data
    cursor.execute(
        """
    INSERT INTO test_schema.test_table (name) VALUES ('Test Record')
    """
    )
    db_connection.commit()

    # Verify the data was inserted
    cursor.execute("SELECT * FROM test_schema.test_table WHERE name = 'Test Record'")
    result = cursor.fetchone()
    assert result is not None
    assert result["name"] == "Test Record"
