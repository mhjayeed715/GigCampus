# routes/dashboard.py - personal stats, leaderboard, JSON APIs for charts
# Copilot helped with the skill-gap subquery structure

from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from models import get_db
from helpers import CATEGORIES

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def index():
    db = get_db()

    # BDT earned as seller
    earned_row = db.execute(
        "SELECT COALESCE(SUM(agreed_price), 0) AS total "
        "FROM orders WHERE seller_id = ? AND status = 'APPROVED'",
        current_user.id
    )
    total_earned = earned_row[0]["total"] if earned_row else 0

    # BDT spent as buyer
    spent_row = db.execute(
        "SELECT COALESCE(SUM(agreed_price), 0) AS total "
        "FROM orders WHERE buyer_id = ? AND status = 'APPROVED'",
        current_user.id
    )
    total_spent = spent_row[0]["total"] if spent_row else 0

    # active gigs
    active_gigs = db.execute(
        "SELECT COUNT(*) AS count FROM gigs WHERE seller_id = ? AND status = 'active'",
        current_user.id
    )
    active_gig_count = active_gigs[0]["count"] if active_gigs else 0

    # completed orders (seller)
    completed = db.execute(
        "SELECT COUNT(*) AS count FROM orders WHERE seller_id = ? AND status = 'APPROVED'",
        current_user.id
    )
    completed_count = completed[0]["count"] if completed else 0

    total_orders = db.execute(
        "SELECT COUNT(*) AS count FROM orders WHERE seller_id = ?",
        current_user.id
    )
    total_order_count = total_orders[0]["count"] if total_orders else 0

    # Completion rate
    completion_rate = 0
    if total_order_count > 0:
        completion_rate = round((completed_count / total_order_count) * 100)

    # avg rating
    avg_rating_row = db.execute(
        "SELECT COALESCE(AVG(rating), 0) AS avg_rating, COUNT(*) AS count "
        "FROM reviews WHERE reviewee_id = ?",
        current_user.id
    )
    avg_rating = round(avg_rating_row[0]["avg_rating"], 1) if avg_rating_row else 0
    review_count = avg_rating_row[0]["count"] if avg_rating_row else 0

    # recent orders
    recent = db.execute(
        "SELECT o.*, g.title AS gig_title, "
        "buyer.username AS buyer_name, seller.username AS seller_name "
        "FROM orders o "
        "JOIN gigs g ON o.gig_id = g.id "
        "JOIN users buyer ON o.buyer_id = buyer.id "
        "JOIN users seller ON o.seller_id = seller.id "
        "WHERE (o.buyer_id = ? OR o.seller_id = ?) "
        "ORDER BY o.created_at DESC LIMIT 5",
        current_user.id, current_user.id
    )

    my_gigs = db.execute(
        "SELECT * FROM gigs WHERE seller_id = ? ORDER BY created_at DESC",
        current_user.id
    )

    return render_template(
        "dashboard/index.html",
        total_earned=total_earned,
        total_spent=total_spent,
        active_gig_count=active_gig_count,
        completed_count=completed_count,
        completion_rate=completion_rate,
        avg_rating=avg_rating,
        review_count=review_count,
        recent=recent,
        my_gigs=my_gigs
    )


@dashboard_bp.route("/leaderboard")
def leaderboard():
    """Top 5 per category, ranked by rating * completions."""
    db = get_db()

    leaders = {}
    for category in CATEGORIES:
        rows = db.execute(
            "SELECT u.id, u.username, u.avatar, u.department, "
            "COALESCE(AVG(r.rating), 0) AS avg_rating, "
            "COUNT(DISTINCT o.id) AS completed_orders, "
            "(COALESCE(AVG(r.rating), 0) * COUNT(DISTINCT o.id)) AS score "
            "FROM users u "
            "JOIN gigs g ON g.seller_id = u.id AND g.category = ? "
            "LEFT JOIN orders o ON o.seller_id = u.id AND o.status = 'APPROVED' "
            "LEFT JOIN reviews r ON r.reviewee_id = u.id "
            "WHERE u.is_verified = 1 "
            "GROUP BY u.id "
            "HAVING score > 0 "
            "ORDER BY score DESC LIMIT 5",
            category
        )
        if rows:
            leaders[category] = rows

    return render_template("dashboard/leaderboard.html", leaders=leaders, categories=CATEGORIES)


@dashboard_bp.route("/platform-stats")
def platform_stats():
    """JSON for the homepage live counter (polled every 30s)."""
    db = get_db()

    bdt = db.execute("SELECT COALESCE(SUM(agreed_price), 0) AS total FROM orders WHERE status = 'APPROVED'")
    gigs_completed = db.execute("SELECT COUNT(*) AS count FROM orders WHERE status = 'APPROVED'")
    students = db.execute("SELECT COUNT(*) AS count FROM users WHERE is_verified = 1")

    return jsonify({
        "total_bdt_earned": bdt[0]["total"] if bdt else 0,
        "total_gigs_completed": gigs_completed[0]["count"] if gigs_completed else 0,
        "active_students": students[0]["count"] if students else 0
    })


@dashboard_bp.route("/skill-gap")
def skill_gap():
    """JSON for Chart.js - demand vs supply per category."""
    db = get_db()

    data = []
    for category in CATEGORIES:
        # demand = orders in last 30 days, supply = active sellers
        demand_row = db.execute(
            "SELECT COUNT(*) AS count FROM orders o "
            "JOIN gigs g ON o.gig_id = g.id "
            "WHERE g.category = ? AND o.created_at >= datetime('now', '-30 days')",
            category
        )

        supply_row = db.execute(
            "SELECT COUNT(DISTINCT g.seller_id) AS count FROM gigs g "
            "WHERE g.category = ? AND g.status = 'active'",
            category
        )

        data.append({
            "category": category,
            "demand": demand_row[0]["count"] if demand_row else 0,
            "supply": supply_row[0]["count"] if supply_row else 0
        })

    return jsonify(data)
