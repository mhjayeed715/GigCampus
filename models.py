# models.py - database schema
# I drew the ER diagram on paper first then wrote these CREATE TABLEs
# Had Copilot double-check my foreign keys — caught two wrong references

from cs50 import SQL

db = None


def get_db():
    return db


def init_db(app):
    """Create tables if they don't exist. Called once from create_app()."""
    global db

    # Ensure the database file exists
    import os
    db_path = app.config["DATABASE"]
    if not os.path.exists(db_path):
        open(db_path, "w").close()

    db = SQL("sqlite:///" + db_path)

    db.execute("PRAGMA foreign_keys = ON")

    # migration: add is_read to messages if missing (added this later when
    # I realized I needed read receipts for the unread badge)
    import sqlite3 as _sqlite3
    _conn = _sqlite3.connect(db_path)
    cols = [r[1] for r in _conn.execute("PRAGMA table_info(messages)").fetchall()]
    if "is_read" not in cols and cols:  # cols is empty if table not created yet
        _conn.execute("ALTER TABLE messages ADD COLUMN is_read INTEGER DEFAULT 0")
        _conn.commit()
    _conn.close()

    # USERS
    # skills_csv = comma-separated for simplicity, is_verified starts at 0
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            university TEXT NOT NULL,
            department TEXT NOT NULL,
            year_of_study INTEGER NOT NULL,
            skills_csv TEXT DEFAULT '',
            avatar TEXT DEFAULT 'default.png',
            student_id_image TEXT NOT NULL,
            is_verified INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            ghost_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # GIGS
    db.execute("""
        CREATE TABLE IF NOT EXISTS gigs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            price_min INTEGER NOT NULL,
            price_max INTEGER NOT NULL,
            delivery_days INTEGER NOT NULL,
            campus_location TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (seller_id) REFERENCES users(id)
        )
    """)

    # GIG_IMAGES (up to 3 per gig)
    db.execute("""
        CREATE TABLE IF NOT EXISTS gig_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gig_id INTEGER NOT NULL,
            image_path TEXT NOT NULL,
            FOREIGN KEY (gig_id) REFERENCES gigs(id)
        )
    """)

    # ORDERS - tracks the full order lifecycle
    # statuses: PENDING, ACCEPTED, IN_PROGRESS, DELIVERED, APPROVED, DISPUTED, CANCELLED
    db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gig_id INTEGER NOT NULL,
            buyer_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL,
            agreed_price INTEGER NOT NULL,
            status TEXT DEFAULT 'PENDING',
            payment_confirmed_at TIMESTAMP,
            delivered_at TIMESTAMP,
            approved_at TIMESTAMP,
            delivery_file TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (gig_id) REFERENCES gigs(id),
            FOREIGN KEY (buyer_id) REFERENCES users(id),
            FOREIGN KEY (seller_id) REFERENCES users(id)
        )
    """)

    # ORDER_HISTORY - append-only audit trail, never updated
    db.execute("""
        CREATE TABLE IF NOT EXISTS order_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            old_status TEXT,
            new_status TEXT NOT NULL,
            changed_by INTEGER NOT NULL,
            note TEXT DEFAULT '',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (changed_by) REFERENCES users(id)
        )
    """)

    # CONVERSATIONS - one per buyer+seller+gig combo
    db.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gig_id INTEGER,
            buyer_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (gig_id) REFERENCES gigs(id),
            FOREIGN KEY (buyer_id) REFERENCES users(id),
            FOREIGN KEY (seller_id) REFERENCES users(id)
        )
    """)

    # MESSAGES
    # msg_type can be 'text', 'offer', or 'file'
    db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            msg_type TEXT DEFAULT 'text',
            offer_amount INTEGER,
            offer_status TEXT DEFAULT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id),
            FOREIGN KEY (sender_id) REFERENCES users(id)
        )
    """)

    # REVIEWS - unique on (order_id, reviewer_id) so no duplicates
    db.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            reviewer_id INTEGER NOT NULL,
            reviewee_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
            comment TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (reviewer_id) REFERENCES users(id),
            FOREIGN KEY (reviewee_id) REFERENCES users(id),
            UNIQUE (order_id, reviewer_id)
        )
    """)

    # WISHLISTS
    db.execute("""
        CREATE TABLE IF NOT EXISTS wishlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            gig_id INTEGER NOT NULL,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (gig_id) REFERENCES gigs(id),
            UNIQUE (user_id, gig_id)
        )
    """)

    # GHOST_FLAGS - auto_detected=1 means the scheduler created this
    db.execute("""
        CREATE TABLE IF NOT EXISTS ghost_flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            auto_detected INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (buyer_id) REFERENCES users(id),
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    """)

    # DISPUTES
    db.execute("""
        CREATE TABLE IF NOT EXISTS disputes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            raised_by INTEGER NOT NULL,
            reason TEXT NOT NULL,
            evidence_text TEXT DEFAULT '',
            evidence_file TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            admin_note TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (raised_by) REFERENCES users(id)
        )
    """)

    return db
