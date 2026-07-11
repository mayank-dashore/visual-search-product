from .connection import get_connection

def initialize_database():
    """Creates tables if they do not exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Products Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        image_path TEXT NOT NULL,
        stock INTEGER NOT NULL
    )
    """)
    
    # 2. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        profile_type TEXT NOT NULL
    )
    """)
    
    # 3. User Events Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        event_type TEXT NOT NULL, -- 'view', 'click', 'wishlist', 'purchase'
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        dwell_time INTEGER DEFAULT 0, -- in seconds
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    )
    """)
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    initialize_database()
    print("Database tables initialized successfully.")
