import sqlite3
import datetime
import os

# Global connection variables
_db_connection = None
DATABASE_FILE_PATH = os.getenv("DB_PATH", "discord_bot.db")

def get_db_connection():
    """
    Returns the global database connection. Initializes it if it's None.
    Uses sqlite3.PARSE_DECLTYPES and sqlite3.PARSE_COLNAMES for type detection.
    """
    global _db_connection
    if _db_connection is None:
        try:
            # Ensure directory exists for the database file
            db_dir = os.path.dirname(DATABASE_FILE_PATH)
            if db_dir: # If dirname is not empty, create it
                os.makedirs(db_dir, exist_ok=True)
            
            # Custom converter for timestamp to handle various ISO formats including 'T' separator
            def convert_timestamp_custom(val_bytes):
                val_str = val_bytes.decode('utf-8')
                try:
                    return datetime.datetime.fromisoformat(val_str)
                except ValueError:
                    # Handle cases where it might be a different format or invalid
                    # For this specific converter, if fromisoformat fails, maybe return None or raise
                    # If it's an invalid string not meant to be a timestamp, returning None might be desired.
                    # However, the default converter would raise an error.
                    # Let's try to be somewhat compatible with default behavior for valid but non-ISO.
                    # For now, stick to fromisoformat and let it raise for truly bad strings.
                    # The get_last_daily_claim function has its own try-except for parsing.
                    # The issue is the default SQLite converter itself raising error before our logic.
                    # This custom converter aims to make the SQLite layer more robust.
                    # If fromisoformat fails, it will raise ValueError, which SQLite might catch or pass up.
                    # The key is that it *should* parse valid ISO with 'T'.
                    return datetime.datetime.fromisoformat(val_str) # Re-raise if truly invalid

            sqlite3.register_converter("timestamp", convert_timestamp_custom)
            
            _db_connection = sqlite3.connect(
                DATABASE_FILE_PATH, 
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            # Optional: Set row_factory for dict-like access if preferred, though not strictly needed for current functions
            # _db_connection.row_factory = sqlite3.Row 
        except sqlite3.Error as e:
            print(f"Error connecting to database {DATABASE_FILE_PATH}: {e}")
            raise # Re-raise the exception if connection fails
    return _db_connection

def close_db_connection(): # Helper function to close, if needed by application logic elsewhere
    global _db_connection
    if _db_connection is not None:
        _db_connection.close()
        _db_connection = None

def init_db():
    """
    Initializes the database:
    - Closes any existing connection.
    - Establishes a new connection using DATABASE_FILE_PATH.
    - Creates tables if they don't exist and inserts default settings.
    """
    global _db_connection

    if _db_connection is not None:
        _db_connection.close()
        _db_connection = None
    
    # DATABASE_FILE_PATH is used by get_db_connection, ensure directory exists
    db_dir = os.path.dirname(DATABASE_FILE_PATH)
    if db_dir: # If dirname is not empty, create it
        os.makedirs(db_dir, exist_ok=True)
        
    conn = get_db_connection() # Establishes new connection with DATABASE_FILE_PATH
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            currency INTEGER DEFAULT 0,
            last_daily_claim TIMESTAMP
        )
    """)

    # Create settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Insert default daily_cooldown_minutes if not present
    cursor.execute("""
        INSERT OR IGNORE INTO settings (key, value)
        VALUES (?, ?)
    """, ("daily_cooldown_minutes", "120"))

    conn.commit()
    # conn.close() # Connection is now managed globally

# Note: _db_name global variable is no longer used and can be considered removed.

def create_user_if_not_exists(user_id: str):
    """Creates a new user with default currency 0 if the user does not exist."""
    conn = get_db_connection()
    cursor = None  # Initialize cursor to None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, currency)
            VALUES (?, ?)
        """, (user_id, 0))
        conn.commit()
    except sqlite3.Error as e:
        print(f"SQLite error in create_user_if_not_exists: {e}")
    finally:
        if cursor:
            cursor.close()
    # conn.close()

def get_user_currency(user_id: str) -> int:
    """Returns the currency for the given user_id."""
    create_user_if_not_exists(user_id) # Ensures user row exists
    conn = get_db_connection()
    cursor = None  # Initialize cursor to None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT currency FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0
    except sqlite3.Error as e:
        print(f"SQLite error in get_user_currency: {e}")
        return 0 # Return a default value in case of error
    finally:
        if cursor:
            cursor.close()
    # conn.close()

def update_user_currency(user_id: str, amount_change: int) -> int:
    """Updates the user's currency by amount_change. Ensures currency does not go below zero."""
    # create_user_if_not_exists(user_id) # get_user_currency below will call this
    
    # Important: Read current currency and calculate new currency within the same transaction
    # if possible, or at least using the same connection without intermediate commits
    # from other operations if concurrency were a concern. For this bot, it's simpler.
    
    current_currency = get_user_currency(user_id) # This uses its own cursor, but on the same global conn
    new_currency = current_currency + amount_change
    if new_currency < 0:
        new_currency = 0
        
    conn = get_db_connection()
    cursor = None  # Initialize cursor to None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET currency = ?
            WHERE user_id = ?
        """, (new_currency, user_id))
        conn.commit()
        return new_currency
    except sqlite3.Error as e:
        print(f"SQLite error in update_user_currency: {e}")
        return current_currency # Return current_currency in case of error to indicate no change
    finally:
        if cursor:
            cursor.close()
    # conn.close()

def get_last_daily_claim(user_id: str):
    """Returns the last_daily_claim timestamp for the user. Can be None if never claimed."""
    create_user_if_not_exists(user_id)
    conn = get_db_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT last_daily_claim FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone() # The custom converter runs here

        if not result or result[0] is None:
            return None # No timestamp in DB or it's explicitly NULL

        value = result[0] # This should be a datetime object if converter succeeded, or potentially string if converter failed gracefully (not current impl)

        dt = None
        if isinstance(value, datetime.datetime):
            dt = value
        elif isinstance(value, str): # Fallback if converter somehow didn't run or returned string
            try:
                dt = datetime.datetime.fromisoformat(value)
            except ValueError:
                print(f"Invalid ISO string format in get_last_daily_claim after DB fetch: {value}")
                return None 
        else:
            # Value is neither a datetime object nor a string that fromisoformat can handle
            print(f"Unexpected type for last_daily_claim in DB: {type(value)}")
            return None
        
        # If dt is still None at this point (e.g. if it was an unparseable string that slipped through)
        if dt is None: # Should be redundant if the above logic is sound
             print(f"dt became None unexpectedly for value: {value}")
             return None

        # Ensure the datetime is timezone-aware and in UTC
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.timezone.utc)
        elif dt.tzinfo != datetime.timezone.utc:
            return dt.astimezone(datetime.timezone.utc)
        
        return dt # Already an aware UTC datetime
        
    except (sqlite3.Error, ValueError) as e: # Catch ValueError from converter too
        print(f"Error in get_last_daily_claim (SQLite or conversion error): {e}")
        return None 
    finally:
        if cursor:
            cursor.close()

def set_last_daily_claim(user_id: str, timestamp: datetime.datetime):
    """Updates the last_daily_claim for the user with the given timestamp."""
    create_user_if_not_exists(user_id)
    conn = get_db_connection()
    cursor = None  # Initialize cursor to None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET last_daily_claim = ?
            WHERE user_id = ?
        """, (timestamp.isoformat(), user_id)) # Store as standard ISO string
        conn.commit()
    except sqlite3.Error as e:
        print(f"SQLite error in set_last_daily_claim: {e}")
    finally:
        if cursor:
            cursor.close()
    # conn.close()

def get_setting(key: str) -> str | None:
    """Returns the value for the given key from the settings table. Returns None if not found."""
    conn = get_db_connection()
    cursor = None  # Initialize cursor to None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = cursor.fetchone()
        return result[0] if result else None
    except sqlite3.Error as e:
        print(f"SQLite error in get_setting: {e}")
        return None # Return None in case of error
    finally:
        if cursor:
            cursor.close()
    # conn.close()

def set_setting(key: str, value: str):
    """Inserts or replaces a setting in the settings table."""
    conn = get_db_connection()
    cursor = None  # Initialize cursor to None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value)
            VALUES (?, ?)
        """, (key, value))
        conn.commit()
    except sqlite3.Error as e:
        print(f"SQLite error in set_setting: {e}")
    finally:
        if cursor:
            cursor.close()
    # conn.close()

def get_top_users_by_currency(limit: int = 10) -> list[tuple[str, int]]:
    """
    Retrieves the top users ordered by their currency in descending order.

    Args:
        limit (int): The maximum number of top users to retrieve. Defaults to 10.

    Returns:
        list[tuple[str, int]]: A list of tuples, where each tuple contains
                                (user_id, currency). Returns an empty list
                                if an error occurs or no users are found.
    """
    conn = get_db_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, currency 
            FROM users 
            ORDER BY currency DESC 
            LIMIT ?
        """, (limit,))
        results = cursor.fetchall()
        return results
    except sqlite3.Error as e:
        print(f"SQLite error in get_top_users_by_currency: {e}")
        return [] # Return empty list in case of error
    finally:
        if cursor:
            cursor.close()

if __name__ == '__main__':
    # Example Usage (optional - for testing)
    init_db() # Initializes with default 'discord_bot.db'
    
    # Test user creation and currency
    test_user_id = "test_user_123"
    create_user_if_not_exists(test_user_id)
    print(f"User {test_user_id} currency: {get_user_currency(test_user_id)}")
    
    update_user_currency(test_user_id, 50)
    print(f"User {test_user_id} currency after +50: {get_user_currency(test_user_id)}")
    
    update_user_currency(test_user_id, -100) # Should set currency to 0
    print(f"User {test_user_id} currency after -100 (should be 0): {get_user_currency(test_user_id)}")

    # Create some more users for leaderboard testing
    users_for_leaderboard = [
        ("leader_user_A", 1000),
        ("leader_user_B", 500),
        ("leader_user_C", 1200),
        ("leader_user_D", 200),
        ("leader_user_E", 1500)
    ]

    for uid, curr in users_for_leaderboard:
        create_user_if_not_exists(uid)
        # Directly update currency for simplicity in testing, bypassing negative checks for this setup
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET currency = ? WHERE user_id = ?", (curr, uid))
        conn.commit()
        if cursor: cursor.close()
        print(f"User {uid} set to currency: {get_user_currency(uid)}")


    # Test daily claim
    now = datetime.datetime.now()
    set_last_daily_claim(test_user_id, now) # test_user_123 should have 0 currency
    retrieved_claim_time = get_last_daily_claim(test_user_id)
    print(f"User {test_user_id} last daily claim: {retrieved_claim_time}")

    # Test settings
    print(f"Initial daily_cooldown_minutes: {get_setting('daily_cooldown_minutes')}")
    set_setting("daily_cooldown_minutes", "180")
    print(f"Updated daily_cooldown_minutes: {get_setting('daily_cooldown_minutes')}")

    # Test get_top_users_by_currency
    print("\nTesting Leaderboard Function:")
    top_3_users = get_top_users_by_currency(limit=3)
    print(f"Top 3 users by currency: {top_3_users}")
    # Expected: [('leader_user_E', 1500), ('leader_user_C', 1200), ('leader_user_A', 1000)]
    
    top_10_users = get_top_users_by_currency() # Default limit 10
    print(f"Top 10 users by currency: {top_10_users}")
    # Expected: E, C, A, B, D, then test_user_123 (currency 0)
    
    print("\nDatabase operations test complete.")
