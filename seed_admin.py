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

    # Check if admin already exists
    existing = db.execute("SELECT id FROM users WHERE email = ?", ADMIN_EMAIL)
    if existing:
        print(f"[!] Admin already exists — email: {ADMIN_EMAIL}")
    else:
        pw_hash = generate_password_hash(ADMIN_PASSWORD)
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
        print("  Admin account created successfully!")
        print("=" * 45)
        print(f"  Email    : {ADMIN_EMAIL}")
        print(f"  Password : {ADMIN_PASSWORD}")
        print("=" * 45)
        print("  Change the password after first login.")
        print("=" * 45)
