# helpers.py - shared utilities
# got the allowed_file pattern from Flask docs, added extra extensions

from functools import wraps
from flask import redirect, url_for, flash, session
from flask_login import current_user, UserMixin


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "zip", "docx"}

CATEGORIES = [
    "Design", "Coding", "Writing", "Tutoring",
    "Data Entry", "Photography", "Translation", "Other"
]


def allowed_file(filename):
    """Check if file extension is allowed."""
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def format_bdt(amount):
    """1500 → '1,500 BDT'"""
    if amount is None:
        return "0 BDT"
    return f"{int(amount):,} BDT"


def verified_required(f):
    """Block unverified users. Use after @login_required."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_verified:
            flash("Your account is pending verification. You cannot perform this action yet.", "warning")
            return redirect(url_for("dashboard.index"))
        return f(*args, **kwargs)
    return decorated_function


class User(UserMixin):
    """Wraps a DB row for Flask-Login."""
    def __init__(self, user_dict):
        self.id = user_dict["id"]
        self.username = user_dict["username"]
        self.email = user_dict["email"]
        self.university = user_dict["university"]
        self.department = user_dict["department"]
        self.year_of_study = user_dict["year_of_study"]
        self.skills_csv = user_dict.get("skills_csv", "")
        self.avatar = user_dict.get("avatar", "default.png")
        self.student_id_image = user_dict.get("student_id_image", "")
        self.is_verified = user_dict.get("is_verified", 0)
        self.is_admin = user_dict.get("is_admin", 0)
        self.ghost_count = user_dict.get("ghost_count", 0)
        self.created_at = user_dict.get("created_at", "")

    def get_id(self):
        return str(self.id)

    @property
    def skills_list(self):
        if not self.skills_csv:
            return []
        return [s.strip() for s in self.skills_csv.split(",") if s.strip()]


def make_user_obj(row):
    if row is None:
        return None
    return User(row)


def flash_error(message):
    flash(message, "danger")


def flash_success(message):
    flash(message, "success")
