import unittest
import os
import sqlite3
import datetime
import tempfile
from unittest import mock

# Add the project root to the Python path to allow importing 'database'
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import database

class TestDatabaseUtils(unittest.TestCase):
    """Base class for database tests, handling common setup for in-memory DB."""

    @classmethod
    def setUpClass(cls):
        """Patch environment for the entire test class to use a consistent in-memory DB."""
        cls.getenv_patcher = mock.patch.dict(os.environ, {"DB_PATH": ":memory:"})
        cls.getenv_patcher.start()
        # Force database module to re-evaluate DATABASE_FILE_PATH based on the mocked environment
        # This ensures that when database.py is imported or used by tests, it sees :memory:
        database.DATABASE_FILE_PATH = database.os.getenv("DB_PATH", "discord_bot.db")


    @classmethod
    def tearDownClass(cls):
        """Stop patching after all tests in the class have run."""
        cls.getenv_patcher.stop()
        # Reset DATABASE_FILE_PATH in the module to its original evaluation logic
        database.DATABASE_FILE_PATH = database.os.getenv("DB_PATH", "discord_bot.db")


    def setUp(self):
        """Set up for each test method. Initializes a fresh in-memory database."""
        # Ensure DATABASE_FILE_PATH is correctly set to :memory: for each test instance
        # This is mostly redundant if setUpClass worked, but good for safety.
        database.DATABASE_FILE_PATH = ":memory:" 
        
        # Initialize the database (this will now use :memory: and also closes any prior global connection)
        database.init_db()
        
        # Get a direct connection for test-specific setup if needed.
        self.conn = database.get_db_connection()

    def tearDown(self):
        """Tear down after each test method."""
        # Close the global connection if it's open
        database.close_db_connection()


class TestGetLastDailyClaim(TestDatabaseUtils):

    def test_get_last_daily_claim_non_existent_user(self):
        """Test get_last_daily_claim for a user that doesn't exist."""
        self.assertIsNone(database.get_last_daily_claim("new_user_1"))

    def test_get_last_daily_claim_null_timestamp(self):
        """Test get_last_daily_claim when last_daily_claim is NULL in DB."""
        user_id = "user_with_null_claim"
        database.create_user_if_not_exists(user_id) 
        # last_daily_claim is NULL by default upon user creation if not set by set_last_daily_claim
        self.assertIsNone(database.get_last_daily_claim(user_id))

    def test_get_last_daily_claim_valid_utc_iso_string(self):
        """Test with a valid ISO 8601 UTC timestamp string."""
        user_id = "user_utc_iso"
        dt_utc = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        database.create_user_if_not_exists(user_id)
        database.set_last_daily_claim(user_id, dt_utc) # set_last_daily_claim stores it as ISO string
        
        retrieved_dt = database.get_last_daily_claim(user_id)
        self.assertIsNotNone(retrieved_dt)
        self.assertEqual(retrieved_dt, dt_utc)
        self.assertEqual(retrieved_dt.tzinfo, datetime.timezone.utc)

    def test_get_last_daily_claim_valid_naive_iso_string_as_utc(self):
        """Test with a valid naive ISO 8601 string, expecting it to be treated as UTC."""
        user_id = "user_naive_iso"
        dt_naive_str = "2023-01-01T12:00:00" 
        dt_expected_utc = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        
        database.create_user_if_not_exists(user_id)
        # Manually insert the naive string to bypass set_last_daily_claim's auto-UTC conversion
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET last_daily_claim = ? WHERE user_id = ?", (dt_naive_str, user_id))
        self.conn.commit()
        cursor.close()

        retrieved_dt = database.get_last_daily_claim(user_id)
        self.assertIsNotNone(retrieved_dt)
        self.assertEqual(retrieved_dt, dt_expected_utc)
        self.assertEqual(retrieved_dt.tzinfo, datetime.timezone.utc)

    def test_get_last_daily_claim_invalid_iso_string(self):
        """Test with an invalid/corrupted timestamp string."""
        user_id = "user_invalid_iso"
        invalid_str = "not-a-datetime-string"
        database.create_user_if_not_exists(user_id)
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET last_daily_claim = ? WHERE user_id = ?", (invalid_str, user_id))
        self.conn.commit()
        cursor.close()
        self.assertIsNone(database.get_last_daily_claim(user_id))

    def test_get_last_daily_claim_datetime_object_directly_in_db(self):
        """Test if a datetime object (not string) is somehow in DB (SQLite TIMESTAMP type)."""
        user_id = "user_dt_object"
        dt_naive = datetime.datetime(2023, 5, 1, 10, 0, 0) 
        dt_expected_utc = dt_naive.replace(tzinfo=datetime.timezone.utc)

        database.create_user_if_not_exists(user_id)
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET last_daily_claim = ? WHERE user_id = ?", (dt_naive, user_id))
        self.conn.commit()
        cursor.close()
        
        retrieved_dt = database.get_last_daily_claim(user_id)
        self.assertIsNotNone(retrieved_dt)
        self.assertEqual(retrieved_dt, dt_expected_utc)
        self.assertEqual(retrieved_dt.tzinfo, datetime.timezone.utc)


class TestGetTopUsersByCurrency(TestDatabaseUtils):

    def _add_user(self, user_id, currency):
        database.create_user_if_not_exists(user_id)
        # Use the module's update function which handles currency correctly
        current_currency = database.get_user_currency(user_id)
        database.update_user_currency(user_id, currency - current_currency)


    def test_get_top_users_empty_database(self):
        """Test when no users have currency or table is effectively empty for ranking."""
        # init_db creates tables, but no users with currency yet
        self.assertEqual(database.get_top_users_by_currency(limit=5), [])

    def test_get_top_users_varying_currencies(self):
        """Test with multiple users, varying currencies, and limit."""
        self._add_user("user1", 100)
        self._add_user("user2", 500)
        self._add_user("user3", 50)
        self._add_user("user4", 1000)
        self._add_user("user5", 200)

        expected_order_limit_3 = [("user4", 1000), ("user2", 500), ("user5", 200)]
        self.assertEqual(database.get_top_users_by_currency(limit=3), expected_order_limit_3)

        expected_order_limit_5 = [
            ("user4", 1000), ("user2", 500), ("user5", 200), ("user1", 100), ("user3", 50)
        ]
        self.assertEqual(database.get_top_users_by_currency(limit=5), expected_order_limit_5)
    
    def test_get_top_users_fewer_than_limit(self):
        """Test when the number of users is less than the limit."""
        self._add_user("userA", 700)
        self._add_user("userB", 300)
        
        expected_order = [("userA", 700), ("userB", 300)]
        self.assertEqual(database.get_top_users_by_currency(limit=5), expected_order)

    def test_get_top_users_with_zero_currency(self):
        """Test users with zero currency are included and correctly ordered."""
        self._add_user("user_rich", 100)
        database.create_user_if_not_exists("user_poor") # Default 0 currency
        self._add_user("user_middle", 50)
        
        expected_order = [("user_rich", 100), ("user_middle", 50), ("user_poor", 0)]
        # Fetch enough to ensure user_poor is included if they exist
        self.assertEqual(database.get_top_users_by_currency(limit=3), expected_order)


    def test_get_top_users_different_limits(self):
        """Test with various limit values."""
        self._add_user("u1", 10)
        self._add_user("u2", 20)
        self._add_user("u3", 30)
        
        self.assertEqual(database.get_top_users_by_currency(limit=1), [("u3", 30)])
        self.assertEqual(database.get_top_users_by_currency(limit=2), [("u3", 30), ("u2", 20)])
        self.assertEqual(database.get_top_users_by_currency(limit=3), [("u3", 30), ("u2", 20), ("u1", 10)])
        self.assertEqual(database.get_top_users_by_currency(limit=0), []) 


class TestDatabasePathConfiguration(unittest.TestCase):
    """Tests database file path configuration via DB_PATH environment variable."""

    def setUp(self):
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir_path = self.temp_dir_obj.name
        self.custom_db_file_path = os.path.join(self.temp_dir_path, "custom_test_db.sqlite3")
        
        # Store original os.environ["DB_PATH"] if it exists, to restore it later
        self.original_env_db_path = os.environ.get("DB_PATH")
        os.environ["DB_PATH"] = self.custom_db_file_path

        # Critical: Force the database module to re-evaluate its DATABASE_FILE_PATH global
        # This simulates the module being imported *after* the env var is set.
        self.original_module_db_path_val = database.DATABASE_FILE_PATH
        database.DATABASE_FILE_PATH = database.os.getenv("DB_PATH") # Re-set based on NEW env var

    def tearDown(self):
        database.close_db_connection() # Ensure the file is released if open
        
        # Restore original DB_PATH env var if it existed, or remove if it didn't
        if self.original_env_db_path is not None:
            os.environ["DB_PATH"] = self.original_env_db_path
        elif "DB_PATH" in os.environ:
            del os.environ["DB_PATH"]

        # Restore the module's DATABASE_FILE_PATH to what it was before this test class
        database.DATABASE_FILE_PATH = self.original_module_db_path_val
        
        self.temp_dir_obj.cleanup()


    def test_db_file_creation_at_custom_path(self):
        """Test if init_db creates the DB file at the path specified by DB_PATH."""
        self.assertFalse(os.path.exists(self.custom_db_file_path), 
                         "DB should not exist before init_db at custom path.")
        
        database.init_db() # Should use self.custom_db_file_path due to setUp logic
        
        self.assertTrue(os.path.exists(self.custom_db_file_path), 
                        "DB file was not created at custom path by init_db.")

        conn = database.get_db_connection() # Should connect to the custom path DB
        self.assertIsNotNone(conn, "Connection should be established to custom path DB.")
        
        # Verify it's the correct database by checking for expected tables
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
            self.assertIsNotNone(cursor.fetchone(), "Users table not found in DB at custom path.")
        finally:
            cursor.close()
            database.close_db_connection() # Close this specific connection

if __name__ == '__main__':
    unittest.main()
