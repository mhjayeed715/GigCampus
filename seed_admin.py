"""
seed_admin.py — Creates the default admin account for GigCampus.

Run once:  python seed_admin.py

Admin credentials:
  Email    : admin@gigcampus.ac.bd
  Password : Admin@1234
"""

from app import create_app
from models import get_db
from werkzeug.security import generate_password_hash
from datetime import datetime

app = create_app()

ADMIN_EMAIL    = "admin@gigcampus.ac.bd"   # format: name@varsityname.ac.bd
ADMIN_PASSWORD = "Admin@1234"
ADMIN_USERNAME = "admin"


with app.app_context():
    db = get_db()
    
    # -------------------------------------------------------------------------
    # FORCE RESET: Delete existing admin and recreate to ensure password works
    # -------------------------------------------------------------------------
    print(f"[!] Processing admin account for: {ADMIN_EMAIL}")
    
    # Check if admin already exists
    existing = db.execute("SELECT id FROM users WHERE email = ?", ADMIN_EMAIL)
    if existing:
        print("[!] Deleting existing admin user...")
        
        # We need to be careful with foreign keys if the admin has activity
        # But this is a seeding script, so we'll try to delete cleanly
        try:
            db.execute("DELETE FROM users WHERE email = ?", ADMIN_EMAIL)
            print("  Deleted successfully.")
        except Exception as e:
            print(f"  Warning: Could not delete old admin (maybe foreign keys?): {e}")
            # Fallback: Just update the password hash
            pw_hash = generate_password_hash(ADMIN_PASSWORD, method="scrypt")
            db.execute("UPDATE users SET password_hash = ? WHERE email = ?", pw_hash, ADMIN_EMAIL)
            print("  Updated password hash instead.")
            exit(0) # Done here if we updated

    # Insert fresh admin record (if we deleted it successfully or it didn't exist)
    pw_hash = generate_password_hash(ADMIN_PASSWORD, method="scrypt")
    
    try:
        db.execute(
            """INSERT INTO users
               (username, email, password_hash, university, department,
                year_of_study, student_id_image, is_verified, is_admin, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?)""",
            ADMIN_USERNAME, ADMIN_EMAIL, pw_hash,
            "GigCampus University", "Administration", "N/A", "",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        print("=" * 45)
        print("  Admin account (re)created successfully!")
        print("=" * 45)
        print(f"  Email    : {ADMIN_EMAIL}")
        print(f"  Password : {ADMIN_PASSWORD}")
        print("=" * 45)
    except Exception as e:
        print(f"Error creating admin: {e}")

