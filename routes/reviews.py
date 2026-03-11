# routes/reviews.py
# Copilot confirmed the edge cases I was worried about
# (what if someone reviews an order they're not part of, etc.)

from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import get_db
from helpers import flash_error, flash_success

reviews_bp = Blueprint("reviews", __name__)


@reviews_bp.route("/reviews/submit", methods=["POST"])
@login_required
def submit():
    db = get_db()

    order_id = request.form.get("order_id", type=int)
    rating = request.form.get("rating", type=int)
    comment = request.form.get("comment", "").strip()

    if not order_id or not rating:
        flash_error("Order ID and rating are required.")
        return redirect(url_for("orders.index"))

    if rating < 1 or rating > 5:
        flash_error("Rating must be between 1 and 5.")
        return redirect(url_for("orders.detail", order_id=order_id))

    # Fetch the order
    order = db.execute("SELECT * FROM orders WHERE id = ?", order_id)
    if not order:
        flash_error("Order not found.")
        return redirect(url_for("orders.index"))

    order = order[0]

    # Only APPROVED orders can be reviewed
    if order["status"] != "APPROVED":
        flash_error("You can only review completed (approved) orders.")
        return redirect(url_for("orders.detail", order_id=order_id))

    # Must be buyer or seller of this order
    if current_user.id not in (order["buyer_id"], order["seller_id"]):
        flash_error("You are not part of this order.")
        return redirect(url_for("orders.index"))

    # buyer reviews seller, seller reviews buyer
    if current_user.id == order["buyer_id"]:
        reviewee_id = order["seller_id"]
    else:
        reviewee_id = order["buyer_id"]

    # Check if already reviewed
    existing = db.execute(
        "SELECT id FROM reviews WHERE order_id = ? AND reviewer_id = ?",
        order_id, current_user.id
    )
    if existing:
        flash_error("You have already reviewed this order.")
        return redirect(url_for("orders.detail", order_id=order_id))

    # Insert the review
    db.execute(
        "INSERT INTO reviews (order_id, reviewer_id, reviewee_id, rating, comment) "
        "VALUES (?, ?, ?, ?, ?)",
        order_id, current_user.id, reviewee_id, rating, comment
    )

    flash_success("Review submitted! Thank you for your feedback.")
    return redirect(url_for("orders.detail", order_id=order_id))
