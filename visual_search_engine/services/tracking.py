import time
from database.connection import get_connection

def track_event(user_id, product_id, event_type, dwell_time=0):
    """
    Logs a user interaction event into the database.
    event_type can be 'view', 'click', 'wishlist', 'purchase'.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO user_events (user_id, product_id, event_type, dwell_time) VALUES (?, ?, ?, ?)",
            (user_id, product_id, event_type, dwell_time)
        )
        conn.commit()
    except Exception as e:
        print(f"Error logging event: {e}")
    finally:
        conn.close()

def get_user_events(user_id):
    """Retrieves all event history for a given user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT product_id, event_type, timestamp, dwell_time FROM user_events WHERE user_id = ? ORDER BY timestamp DESC",
        (user_id,)
    )
    events = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return events
