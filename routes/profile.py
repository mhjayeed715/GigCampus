# routes/profile.py - public student profiles

from flask import Blueprint, render_template, redirect, url_for
from models import get_db
from helpers import flash_error

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/profile/<username>")
def view(username):
    db = get_db()

    user = db.execute("SELECT * FROM users WHERE username = ?", username)
    if not user:
        flash_error("User not found.")
        return redirect(url_for("index"))

    user = user[0]

    # Fetch user's active gigs
    gigs = db.execute(
        "SELECT g.*, "
        "COALESCE((SELECT AVG(r.rating) FROM reviews r WHERE r.reviewee_id = g.seller_id), 0) AS avg_rating "
        "FROM gigs g WHERE g.seller_id = ? AND g.status = 'active' "
        "ORDER BY g.created_at DESC",
        user["id"]
    )

    # Fetch reviews received
    reviews = db.execute(
        "SELECT r.*, u.username AS reviewer_name, u.avatar AS reviewer_avatar "
        "FROM reviews r JOIN users u ON r.reviewer_id = u.id "
        "WHERE r.reviewee_id = ? ORDER BY r.created_at DESC LIMIT 10",
        user["id"]
    )

    # Stats
    avg_rating_row = db.execute(
        "SELECT COALESCE(AVG(rating), 0) AS avg, COUNT(*) AS count "
        "FROM reviews WHERE reviewee_id = ?",
        user["id"]
    )
    avg_rating = round(avg_rating_row[0]["avg"], 1) if avg_rating_row else 0
    review_count = avg_rating_row[0]["count"] if avg_rating_row else 0

    completed_orders = db.execute(
        "SELECT COUNT(*) AS count FROM orders WHERE seller_id = ? AND status = 'APPROVED'",
        user["id"]
    )
    completed_count = completed_orders[0]["count"] if completed_orders else 0

    return render_template(
        "profile/view.html",
        profile_user=user,
        gigs=gigs,
        reviews=reviews,
        avg_rating=avg_rating,
        review_count=review_count,
        completed_count=completed_count
    )
