import unittest
import sqlite3
from datetime import datetime, timedelta, timezone
import database

def setup_in_memory_db():
    database.init_db(db_name_override=':memory:')

class TestDatabase(unittest.TestCase):
    def setUp(self):
        setup_in_memory_db()

    def tearDown(self):
        if hasattr(database, '_db_connection') and database._db_connection:
            database._db_connection.close()
            database._db_connection = None # Reset for next test, if any in same suite run

    def test_init_db_creates_tables(self):
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
        self.assertIsNotNone(cursor.fetchone())
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings';")
        self.assertIsNotNone(cursor.fetchone())

    def test_init_db_default_settings(self):
        self.assertEqual(database.get_setting('daily_cooldown_minutes'), '120')

    def test_create_user_if_not_exists(self):
        user_id = 'test_user_1'
        database.create_user_if_not_exists(user_id)
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id=?;", (user_id,))
        self.assertIsNotNone(cursor.fetchone())
        # Test that calling it again doesn't create a duplicate or error
        database.create_user_if_not_exists(user_id)
        cursor.execute("SELECT COUNT(*) FROM users WHERE user_id=?;", (user_id,))
        self.assertEqual(cursor.fetchone()[0], 1)

    def test_get_user_currency(self):
        user_id = 'test_user_2'
        # User should be created by get_user_currency if not exists, with 0 currency
        self.assertEqual(database.get_user_currency(user_id), 0) 
        
        # Manually update currency for further testing
        conn = database.get_db_connection()
        cursor = conn.cursor()
        # Ensure user is created by get_user_currency or manually if needed by logic
        database.create_user_if_not_exists(user_id) 
        cursor.execute("UPDATE users SET currency = 100 WHERE user_id = ?;", (user_id,))
        conn.commit()
        self.assertEqual(database.get_user_currency(user_id), 100)


    def test_update_user_currency(self):
        user_id = 'test_user_3'
        # First update should also create the user
        database.update_user_currency(user_id, 500)
        self.assertEqual(database.get_user_currency(user_id), 500)
        
        database.update_user_currency(user_id, -200)
        self.assertEqual(database.get_user_currency(user_id), 300)
        
        # Test that currency does not go below zero
        database.update_user_currency(user_id, -1000)
        self.assertEqual(database.get_user_currency(user_id), 0)

    def test_daily_claim_timestamps(self):
        user_id = 'test_user_4'
        # User should be created by get_last_daily_claim if not exists
        self.assertIsNone(database.get_last_daily_claim(user_id))
        
        claim_time = datetime.now(timezone.utc).replace(microsecond=0) # Use timezone-aware datetime
        database.set_last_daily_claim(user_id, claim_time)
        
        retrieved_time = database.get_last_daily_claim(user_id)
        self.assertIsInstance(retrieved_time, datetime)
        
        # Ensure retrieved_time is timezone-aware (UTC) for comparison
        # This handles cases where database might return naive datetime for TIMESTAMP
        if retrieved_time.tzinfo is None or retrieved_time.tzinfo.utcoffset(retrieved_time) is None:
            retrieved_time = retrieved_time.replace(tzinfo=timezone.utc)
            
        self.assertEqual(retrieved_time, claim_time)

    def test_settings_management(self):
        setting_key = 'test_setting_key'
        self.assertIsNone(database.get_setting(setting_key))
        
        database.set_setting(setting_key, 'value1')
        self.assertEqual(database.get_setting(setting_key), 'value1')
        
        database.set_setting(setting_key, 'value2')
        self.assertEqual(database.get_setting(setting_key), 'value2')

if __name__ == '__main__':
    unittest.main()
