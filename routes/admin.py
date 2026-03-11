# routes/admin.py - admin panel for verifying students and handling disputes

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import get_db
from helpers import flash_error, flash_success

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
