import sqlite3
import datetime

# Global connection variables
_db_connection = None
_db_name = "discord_bot.db" # Default database name

def get_db_connection():
    """
    Returns the global database connection. Initializes it if it's None.
    Uses sqlite3.PARSE_DECLTYPES and sqlite3.PARSE_COLNAMES for type detection.
    """
    global _db_connection, _db_name
    if _db_connection is None:
        try:
            _db_connection = sqlite3.connect(_db_name, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
            # Optional: Set row_factory for dict-like access if preferred, though not strictly needed for current functions
            # _db_connection.row_factory = sqlite3.Row 
        except sqlite3.Error as e:
            print(f"Error connecting to database {_db_name}: {e}")
            raise # Re-raise the exception if connection fails
    return _db_connection

def close_db_connection(): # Helper function to close, if needed by application logic elsewhere
    global _db_connection
    if _db_connection is not None:
        _db_connection.close()
        _db_connection = None

def init_db(db_name_override=None):
    """
    Initializes the database:
    - Closes any existing connection.
    - Updates the database name if db_name_override is provided.
    - Establishes a new connection.
    - Creates tables if they don't exist and inserts default settings.
    """
    global _db_name, _db_connection

    if _db_connection is not None:
        _db_connection.close()
        _db_connection = None
    
    if db_name_override:
        _db_name = db_name_override
    
    conn = get_db_connection() # Establishes new connection with potentially updated _db_name
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

def create_user_if_not_exists(user_id: str):
    """Creates a new user with default currency 0 if the user does not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, currency)
        VALUES (?, ?)
    """, (user_id, 0))
    conn.commit()
    # conn.close()

def get_user_currency(user_id: str) -> int:
    """Returns the currency for the given user_id."""
    create_user_if_not_exists(user_id) # Ensures user row exists
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT currency FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    # conn.close()
    return result[0] if result else 0

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
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users
        SET currency = ?
        WHERE user_id = ?
    """, (new_currency, user_id))
    conn.commit()
    # conn.close()
    return new_currency

def get_last_daily_claim(user_id: str):
    """Returns the last_daily_claim timestamp for the user. Can be None if never claimed."""
    create_user_if_not_exists(user_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT last_daily_claim FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result and result[0]:
        value = result[0]

        dt = None
        if isinstance(value, str):
            try:
                dt = datetime.datetime.fromisoformat(value)
            except ValueError:
                return None
        elif isinstance(value, datetime.datetime):
            dt = value
        else:
            return None
        
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.timezone.utc)
        elif dt.tzinfo != datetime.timezone.utc:
            return dt.astimezone(datetime.timezone.utc)
        
        return dt
    
    return None

def set_last_daily_claim(user_id: str, timestamp: datetime.datetime):
    """Updates the last_daily_claim for the user with the given timestamp."""
    create_user_if_not_exists(user_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users
        SET last_daily_claim = ?
        WHERE user_id = ?
    """, (timestamp.isoformat(), user_id)) # Store as ISO string for broader compatibility
    conn.commit()
    # conn.close()

def get_setting(key: str) -> str | None:
    """Returns the value for the given key from the settings table. Returns None if not found."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = cursor.fetchone()
    # conn.close()
    return result[0] if result else None

def set_setting(key: str, value: str):
    """Inserts or replaces a setting in the settings table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO settings (key, value)
        VALUES (?, ?)
    """, (key, value))
    conn.commit()
    # conn.close()

if __name__ == '__main__':
    # Example Usage (optional - for testing)
    init_db() # Initializes with default 'discord_bot.db'
    
    # Test user creation and currency
    test_user_id = "test_user_123"
    create_user_if_not_exists(test_user_id)
    print(f"User {test_user_id} currency: {get_user_currency(test_user_id)}")
    
    update_user_currency(test_user_id, 50)
    print(f"User {test_user_id} currency after +50: {get_user_currency(test_user_id)}")
    
    update_user_currency(test_user_id, -100)
    print(f"User {test_user_id} currency after -100 (should be 0): {get_user_currency(test_user_id)}")

    # Test daily claim
    now = datetime.datetime.now()
    set_last_daily_claim(test_user_id, now)
    retrieved_claim_time = get_last_daily_claim(test_user_id)
    print(f"User {test_user_id} last daily claim: {retrieved_claim_time}")

    # Test settings
    print(f"Initial daily_cooldown_minutes: {get_setting('daily_cooldown_minutes')}")
    set_setting("daily_cooldown_minutes", "180")
    print(f"Updated daily_cooldown_minutes: {get_setting('daily_cooldown_minutes')}")
    
    print("Database operations test complete.")
