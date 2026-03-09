# routes/auth.py - registration, login, logout
# referenced CS50 Week 9 notes and Flask-Login docs for session stuff
# Copilot suggested scrypt for password hashing instead of pbkdf2

import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import get_db
from helpers import allowed_file, make_user_obj, flash_error, flash_success

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        db = get_db()

        # Collect form fields
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirmation = request.form.get("confirmation", "")
        university = request.form.get("university", "").strip()
        department = request.form.get("department", "").strip()
        year_of_study = request.form.get("year_of_study", "")
        skills = request.form.get("skills", "").strip()

        # --- Validate ---
        if not all([username, email, password, confirmation, university, department, year_of_study]):
            flash_error("All fields are required.")
            return render_template("auth/register.html")

        if password != confirmation:
            flash_error("Passwords do not match.")
            return render_template("auth/register.html")

        if len(password) < 6:
            flash_error("Password must be at least 6 characters.")
            return render_template("auth/register.html")

        # only .ac.bd emails (university emails)
        if not email.endswith(".ac.bd"):
            flash_error("Only university edu email addresses are accepted.")
            return render_template("auth/register.html")

        existing = db.execute("SELECT id FROM users WHERE username = ? OR email = ?", username, email)
        if existing:
            flash_error("Username or email already taken.")
            return render_template("auth/register.html")

        # --- Student ID upload ---
        if "student_id_image" not in request.files:
            flash_error("Student ID image is required.")
            return render_template("auth/register.html")

        file = request.files["student_id_image"]
        if file.filename == "":
            flash_error("No file selected for student ID.")
            return render_template("auth/register.html")

        if not allowed_file(file.filename):
            flash_error("Invalid file type. Allowed: PNG, JPG, JPEG, GIF, PDF.")
            return render_template("auth/register.html")

        # save with UUID filename so nobody can guess the path
        ext = file.filename.rsplit(".", 1)[1].lower()
        random_filename = f"{uuid.uuid4().hex}.{ext}"
        upload_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "ids", random_filename)
        file.save(upload_path)

        # --- Insert into DB ---
        password_hash = generate_password_hash(password, method="scrypt")

        try:
            year_int = int(year_of_study)
        except ValueError:
            flash_error("Year of study must be a number.")
            return render_template("auth/register.html")

        db.execute(
            "INSERT INTO users (username, email, password_hash, university, department, "
            "year_of_study, skills_csv, student_id_image) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            username, email, password_hash, university, department,
            year_int, skills, random_filename
        )

        flash_success("Registration submitted! Awaiting admin verification.")
        return redirect(url_for("auth.login"))

    # GET request — show the registration form
    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        db = get_db()

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash_error("Email and password are required.")
            return render_template("auth/login.html")

        # Look up user by email
        rows = db.execute("SELECT * FROM users WHERE email = ?", email)
        if not rows:
            flash_error("Invalid email or password.")
            return render_template("auth/login.html")

        user_row = rows[0]

        # Verify password
        if not check_password_hash(user_row["password_hash"], password):
            flash_error("Invalid email or password.")
            return render_template("auth/login.html")

        # Check verification status — do not log in unverified users
        if user_row["is_verified"] == 0:
            flash("Your account is pending admin verification. Please wait.", "warning")
            return render_template("auth/login.html")

        # Success — create session
        user_obj = make_user_obj(user_row)
        login_user(user_obj)
        flash_success(f"Welcome back, {user_obj.username}!")

        # Redirect to the page they were trying to access, or dashboard
        next_page = request.args.get("next")
        return redirect(next_page or url_for("dashboard.index"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    """Log out and clear session."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))
