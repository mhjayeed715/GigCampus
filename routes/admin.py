# routes/admin.py - admin panel for verifying students and handling disputes

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import get_db
from helpers import flash_error, flash_success
from werkzeug.security import generate_password_hash

admin_bp = Blueprint("admin", __name__)


def admin_required(f):
    """Only admins can access."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash_error("Admin access required.")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route("/admin/pending")
@login_required
@admin_required
def pending():
    db = get_db()

    users = db.execute(
        "SELECT * FROM users WHERE is_verified = 0 ORDER BY created_at DESC"
    )

    return render_template("admin/pending.html", users=users)


@admin_bp.route("/admin/verify/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def verify(user_id):
    db = get_db()

    user = db.execute("SELECT id, username FROM users WHERE id = ?", user_id)
    if not user:
        flash_error("User not found.")
        return redirect(url_for("admin.pending"))

    db.execute("UPDATE users SET is_verified = 1 WHERE id = ?", user_id)

    flash_success(f"Student '{user[0]['username']}' has been verified!")
    return redirect(url_for("admin.pending"))


@admin_bp.route("/admin/reject/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def reject(user_id):
    db = get_db()

    user = db.execute("SELECT id, username FROM users WHERE id = ?", user_id)
    if not user:
        flash_error("User not found.")
        return redirect(url_for("admin.pending"))

    db.execute("DELETE FROM users WHERE id = ?", user_id)

    flash_success(f"Registration for '{user[0]['username']}' has been rejected.")
    return redirect(url_for("admin.pending"))


@admin_bp.route("/admin/disputes")
@login_required
@admin_required
def disputes():
    db = get_db()

    disputes_list = db.execute(
        "SELECT d.*, u.username AS raised_by_name, g.title AS gig_title, "
        "o.agreed_price, o.status AS order_status "
        "FROM disputes d "
        "JOIN users u ON d.raised_by = u.id "
        "JOIN orders o ON d.order_id = o.id "
        "JOIN gigs g ON o.gig_id = g.id "
        "ORDER BY d.created_at DESC"
    )

    return render_template("admin/disputes.html", disputes=disputes_list)


@admin_bp.route("/admin/disputes/<int:dispute_id>/resolve", methods=["POST"])
@login_required
@admin_required
def resolve_dispute(dispute_id):
    db = get_db()

    admin_note = request.form.get("admin_note", "").strip()
    action = request.form.get("action", "resolved")

    if action not in ("resolved", "dismissed"):
        action = "resolved"

    db.execute(
        "UPDATE disputes SET status = ?, admin_note = ? WHERE id = ?",
        action, admin_note, dispute_id
    )

    flash_success(f"Dispute has been {action}.")
    return redirect(url_for("admin.disputes"))


# --- User management ---

@admin_bp.route("/admin/users")
@login_required
@admin_required
def users():
    db = get_db()
    q = request.args.get("q", "").strip()

    if q:
        user_list = db.execute(
            "SELECT * FROM users WHERE username LIKE ? OR email LIKE ? ORDER BY created_at DESC",
            f"%{q}%", f"%{q}%"
        )
    else:
        user_list = db.execute("SELECT * FROM users ORDER BY created_at DESC")

    return render_template("admin/users.html", users=user_list, search=q)


@admin_bp.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    db = get_db()

    rows = db.execute("SELECT * FROM users WHERE id = ?", user_id)
    if not rows:
        flash_error("User not found.")
        return redirect(url_for("admin.users"))

    user = rows[0]

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        university = request.form.get("university", "").strip()
        department = request.form.get("department", "").strip()
        year_of_study = request.form.get("year_of_study", "")
        is_verified = 1 if request.form.get("is_verified") else 0
        is_admin = 1 if request.form.get("is_admin") else 0
        ghost_count = request.form.get("ghost_count", "0")
        new_password = request.form.get("new_password", "").strip()

        if not all([username, email, university, department, year_of_study]):
            flash_error("Required fields cannot be empty.")
            return render_template("admin/edit_user.html", user=user)

        # check unique username/email (excluding this user)
        dup = db.execute(
            "SELECT id FROM users WHERE (username = ? OR email = ?) AND id != ?",
            username, email, user_id
        )
        if dup:
            flash_error("Username or email already taken by another user.")
            return render_template("admin/edit_user.html", user=user)

        try:
            ghost_int = max(0, int(ghost_count))
        except ValueError:
            ghost_int = user["ghost_count"]

        db.execute(
            "UPDATE users SET username = ?, email = ?, university = ?, department = ?, "
            "year_of_study = ?, is_verified = ?, is_admin = ?, ghost_count = ? WHERE id = ?",
            username, email, university, department,
            year_of_study, is_verified, is_admin, ghost_int, user_id
        )

        if new_password:
            pw_hash = generate_password_hash(new_password)
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?", pw_hash, user_id)

        flash_success(f"User '{username}' updated.")
        return redirect(url_for("admin.users"))

    return render_template("admin/edit_user.html", user=user)


@admin_bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    db = get_db()

    user = db.execute("SELECT id, username, is_admin FROM users WHERE id = ?", user_id)
    if not user:
        flash_error("User not found.")
        return redirect(url_for("admin.users"))

    if user[0]["is_admin"]:
        flash_error("Cannot delete an admin account.")
        return redirect(url_for("admin.users"))

    # check for active orders
    active = db.execute(
        "SELECT id FROM orders WHERE (buyer_id = ? OR seller_id = ?) "
        "AND status NOT IN ('COMPLETED', 'CANCELLED', 'APPROVED', 'DISPUTED')",
        user_id, user_id
    )
    if active:
        flash_error("Cannot delete user with active orders.")
        return redirect(url_for("admin.users"))

    username = user[0]["username"]

    # clean up all related records (foreign keys are enforced)
    # get user's gig ids first
    user_gigs = db.execute("SELECT id FROM gigs WHERE seller_id = ?", user_id)
    for g in user_gigs:
        db.execute("DELETE FROM gig_images WHERE gig_id = ?", g["id"])
        db.execute("DELETE FROM wishlists WHERE gig_id = ?", g["id"])

    # orders where user is buyer or seller
    user_orders = db.execute(
        "SELECT id FROM orders WHERE buyer_id = ? OR seller_id = ?", user_id, user_id
    )
    for o in user_orders:
        db.execute("DELETE FROM order_history WHERE order_id = ?", o["id"])
        db.execute("DELETE FROM ghost_flags WHERE order_id = ?", o["id"])
        db.execute("DELETE FROM disputes WHERE order_id = ?", o["id"])
        db.execute("DELETE FROM reviews WHERE order_id = ?", o["id"])

    db.execute("DELETE FROM orders WHERE buyer_id = ? OR seller_id = ?", user_id, user_id)

    # conversations and messages
    convos = db.execute(
        "SELECT id FROM conversations WHERE buyer_id = ? OR seller_id = ?", user_id, user_id
    )
    for c in convos:
        db.execute("DELETE FROM messages WHERE conversation_id = ?", c["id"])
    db.execute("DELETE FROM conversations WHERE buyer_id = ? OR seller_id = ?", user_id, user_id)

    db.execute("DELETE FROM messages WHERE sender_id = ?", user_id)
    db.execute("DELETE FROM reviews WHERE reviewer_id = ? OR reviewee_id = ?", user_id, user_id)
    db.execute("DELETE FROM ghost_flags WHERE buyer_id = ?", user_id)
    db.execute("DELETE FROM wishlists WHERE user_id = ?", user_id)
    db.execute("DELETE FROM gigs WHERE seller_id = ?", user_id)
    db.execute("DELETE FROM users WHERE id = ?", user_id)

    flash_success(f"User '{username}' deleted.")
    return redirect(url_for("admin.users"))
