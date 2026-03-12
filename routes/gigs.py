# routes/gigs.py - browsing, creating gigs, wishlists
# the dynamic WHERE clause was tricky - looked up how to build it
# with parameterized queries (Copilot helped with that part)

import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import get_db
from helpers import allowed_file, verified_required, flash_error, flash_success, CATEGORIES

gigs_bp = Blueprint("gigs", __name__)


@gigs_bp.route("/gigs")
def index():
    """Browse gigs with optional filters, paginated."""
    db = get_db()

    # Read filter query params
    category = request.args.get("category", "").strip()
    price_max = request.args.get("price_max", "").strip()
    min_rating = request.args.get("min_rating", "").strip()
    keyword = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 12

    # Build dynamic WHERE clause
    conditions = ["g.status = 'active'"]
    params = []

    if category and category in CATEGORIES:
        conditions.append("g.category = ?")
        params.append(category)

    if price_max:
        try:
            conditions.append("g.price_min <= ?")
            params.append(int(price_max))
        except ValueError:
            pass

    if keyword:
        conditions.append("(g.title LIKE ? OR g.description LIKE ?)")
        params.append(f"%{keyword}%")
        params.append(f"%{keyword}%")

    where_clause = " AND ".join(conditions)

    # Main query — join with users to get seller info and rating
    query = f"""
        SELECT g.*, u.username AS seller_name, u.avatar AS seller_avatar,
               u.ghost_count AS seller_ghost_count,
               COALESCE((SELECT AVG(r.rating) FROM reviews r
                         WHERE r.reviewee_id = g.seller_id), 0) AS avg_rating,
               COALESCE((SELECT COUNT(r.id) FROM reviews r
                         WHERE r.reviewee_id = g.seller_id), 0) AS review_count
        FROM gigs g
        JOIN users u ON g.seller_id = u.id
        WHERE {where_clause}
    """

    # Filter by minimum rating after the join (uses HAVING-like logic)
    if min_rating:
        try:
            mr = float(min_rating)
            query += " AND COALESCE((SELECT AVG(r.rating) FROM reviews r WHERE r.reviewee_id = g.seller_id), 0) >= ?"
            params.append(mr)
        except ValueError:
            pass

    # Count total for pagination
    count_query = f"SELECT COUNT(*) AS total FROM gigs g JOIN users u ON g.seller_id = u.id WHERE {where_clause}"
    # Simpler: just count from the base conditions
    count_result = db.execute(
        f"SELECT COUNT(*) AS total FROM gigs g WHERE {' AND '.join(conditions)}",
        *params[:len(params) - (1 if min_rating else 0)]
    )
    total = count_result[0]["total"] if count_result else 0
    total_pages = max(1, (total + per_page - 1) // per_page)

    # Add ordering and pagination
    offset = (page - 1) * per_page
    query += " ORDER BY g.created_at DESC LIMIT ? OFFSET ?"
    params.append(per_page)
    params.append(offset)

    gigs = db.execute(query, *params)

    return render_template(
        "gigs/index.html",
        gigs=gigs,
        categories=CATEGORIES,
        selected_category=category,
        price_max=price_max,
        min_rating=min_rating,
        keyword=keyword,
        page=page,
        total_pages=total_pages
    )


@gigs_bp.route("/gigs/<int:gig_id>")
def detail(gig_id):
    db = get_db()

    # Fetch gig with seller info
    rows = db.execute(
        "SELECT g.*, u.username AS seller_name, u.avatar AS seller_avatar, "
        "u.department AS seller_department, u.university AS seller_university, "
        "u.ghost_count AS seller_ghost_count, u.skills_csv AS seller_skills, "
        "COALESCE((SELECT AVG(r.rating) FROM reviews r WHERE r.reviewee_id = g.seller_id), 0) AS avg_rating, "
        "COALESCE((SELECT COUNT(r.id) FROM reviews r WHERE r.reviewee_id = g.seller_id), 0) AS review_count "
        "FROM gigs g JOIN users u ON g.seller_id = u.id WHERE g.id = ?",
        gig_id
    )

    if not rows:
        flash_error("Gig not found.")
        return redirect(url_for("gigs.index"))

    gig = rows[0]

    # Fetch gig images
    images = db.execute("SELECT * FROM gig_images WHERE gig_id = ?", gig_id)

    # Fetch recent reviews for this seller
    reviews = db.execute(
        "SELECT r.*, u.username AS reviewer_name FROM reviews r "
        "JOIN users u ON r.reviewer_id = u.id "
        "WHERE r.reviewee_id = ? ORDER BY r.created_at DESC LIMIT 5",
        gig["seller_id"]
    )

    # Check if current user has this gig wishlisted
    is_wishlisted = False
    if current_user.is_authenticated:
        wl = db.execute(
            "SELECT id FROM wishlists WHERE user_id = ? AND gig_id = ?",
            current_user.id, gig_id
        )
        is_wishlisted = len(wl) > 0

    return render_template(
        "gigs/detail.html",
        gig=gig,
        images=images,
        reviews=reviews,
        is_wishlisted=is_wishlisted
    )


@gigs_bp.route("/gigs/create", methods=["GET", "POST"])
@login_required
@verified_required
def create():
    if request.method == "POST":
        db = get_db()

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        price_min = request.form.get("price_min", "")
        price_max = request.form.get("price_max", "")
        delivery_days = request.form.get("delivery_days", "")
        campus_location = request.form.get("campus_location", "").strip()

        if not all([title, description, category, price_min, price_max, delivery_days]):
            flash_error("Please fill in all required fields.")
            return render_template("gigs/create.html", categories=CATEGORIES)

        if category not in CATEGORIES:
            flash_error("Invalid category selected.")
            return render_template("gigs/create.html", categories=CATEGORIES)

        try:
            price_min_int = int(price_min)
            price_max_int = int(price_max)
            delivery_days_int = int(delivery_days)
        except ValueError:
            flash_error("Price and delivery days must be numbers.")
            return render_template("gigs/create.html", categories=CATEGORIES)

        if price_min_int < 0 or price_max_int < price_min_int:
            flash_error("Invalid price range.")
            return render_template("gigs/create.html", categories=CATEGORIES)

        if delivery_days_int < 1:
            flash_error("Delivery days must be at least 1.")
            return render_template("gigs/create.html", categories=CATEGORIES)

        # --- Insert gig ---
        gig_id = db.execute(
            "INSERT INTO gigs (seller_id, title, description, category, price_min, "
            "price_max, delivery_days, campus_location) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            current_user.id, title, description, category,
            price_min_int, price_max_int, delivery_days_int, campus_location
        )

        # save up to 3 portfolio images
        files = request.files.getlist("images")
        saved_count = 0
        for file in files:
            if saved_count >= 3:
                break
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit(".", 1)[1].lower()
                random_name = f"{uuid.uuid4().hex}.{ext}"
                save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "gigs", random_name)
                file.save(save_path)
                db.execute(
                    "INSERT INTO gig_images (gig_id, image_path) VALUES (?, ?)",
                    gig_id, random_name
                )
                saved_count += 1

        flash_success("Gig created successfully!")
        return redirect(url_for("gigs.detail", gig_id=gig_id))

    return render_template("gigs/create.html", categories=CATEGORIES)


@gigs_bp.route("/gigs/<int:gig_id>/wishlist", methods=["POST"])
@login_required
def toggle_wishlist(gig_id):
    """Toggle save/unsave a gig to wishlist. Returns JSON for AJAX."""
    db = get_db()

    # Check if gig exists
    gig = db.execute("SELECT id FROM gigs WHERE id = ?", gig_id)
    if not gig:
        return jsonify({"error": "Gig not found"}), 404

    # Check if already wishlisted
    existing = db.execute(
        "SELECT id FROM wishlists WHERE user_id = ? AND gig_id = ?",
        current_user.id, gig_id
    )

    if existing:
        # Remove from wishlist
        db.execute("DELETE FROM wishlists WHERE user_id = ? AND gig_id = ?",
                   current_user.id, gig_id)
        return jsonify({"saved": False})
    else:
        # Add to wishlist
        db.execute("INSERT INTO wishlists (user_id, gig_id) VALUES (?, ?)",
                   current_user.id, gig_id)
        return jsonify({"saved": True})


@gigs_bp.route("/gigs/<int:gig_id>/edit", methods=["GET", "POST"])
@login_required
@verified_required
def edit(gig_id):
    db = get_db()

    rows = db.execute("SELECT * FROM gigs WHERE id = ?", gig_id)
    if not rows:
        flash_error("Gig not found.")
        return redirect(url_for("gigs.index"))

    gig = rows[0]
    if gig["seller_id"] != current_user.id:
        flash_error("You can only edit your own gigs.")
        return redirect(url_for("gigs.detail", gig_id=gig_id))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        price_min = request.form.get("price_min", "")
        price_max = request.form.get("price_max", "")
        delivery_days = request.form.get("delivery_days", "")
        campus_location = request.form.get("campus_location", "").strip()

        if not all([title, description, category, price_min, price_max, delivery_days]):
            flash_error("Please fill in all required fields.")
            return render_template("gigs/edit.html", gig=gig, categories=CATEGORIES)

        if category not in CATEGORIES:
            flash_error("Invalid category.")
            return render_template("gigs/edit.html", gig=gig, categories=CATEGORIES)

        try:
            price_min_int = int(price_min)
            price_max_int = int(price_max)
            delivery_days_int = int(delivery_days)
        except ValueError:
            flash_error("Price and delivery days must be numbers.")
            return render_template("gigs/edit.html", gig=gig, categories=CATEGORIES)

        if price_min_int < 0 or price_max_int < price_min_int:
            flash_error("Invalid price range.")
            return render_template("gigs/edit.html", gig=gig, categories=CATEGORIES)

        if delivery_days_int < 1:
            flash_error("Delivery days must be at least 1.")
            return render_template("gigs/edit.html", gig=gig, categories=CATEGORIES)

        db.execute(
            "UPDATE gigs SET title = ?, description = ?, category = ?, price_min = ?, "
            "price_max = ?, delivery_days = ?, campus_location = ? WHERE id = ?",
            title, description, category, price_min_int,
            price_max_int, delivery_days_int, campus_location, gig_id
        )

        # handle new images if uploaded (replace old ones)
        files = request.files.getlist("images")
        new_files = [f for f in files if f and f.filename and allowed_file(f.filename)]
        if new_files:
            # delete old images from disk
            old_images = db.execute("SELECT image_path FROM gig_images WHERE gig_id = ?", gig_id)
            for img in old_images:
                old_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "gigs", img["image_path"])
                if os.path.exists(old_path):
                    os.remove(old_path)
            db.execute("DELETE FROM gig_images WHERE gig_id = ?", gig_id)

            saved_count = 0
            for file in new_files:
                if saved_count >= 3:
                    break
                ext = file.filename.rsplit(".", 1)[1].lower()
                random_name = f"{uuid.uuid4().hex}.{ext}"
                save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "gigs", random_name)
                file.save(save_path)
                db.execute(
                    "INSERT INTO gig_images (gig_id, image_path) VALUES (?, ?)",
                    gig_id, random_name
                )
                saved_count += 1

        flash_success("Gig updated!")
        return redirect(url_for("gigs.detail", gig_id=gig_id))

    images = db.execute("SELECT * FROM gig_images WHERE gig_id = ?", gig_id)
    return render_template("gigs/edit.html", gig=gig, images=images, categories=CATEGORIES)


@gigs_bp.route("/gigs/<int:gig_id>/delete", methods=["POST"])
@login_required
def delete(gig_id):
    db = get_db()

    rows = db.execute("SELECT * FROM gigs WHERE id = ?", gig_id)
    if not rows:
        flash_error("Gig not found.")
        return redirect(url_for("gigs.index"))

    gig = rows[0]
    if gig["seller_id"] != current_user.id and not current_user.is_admin:
        flash_error("You can only delete your own gigs.")
        return redirect(url_for("gigs.detail", gig_id=gig_id))

    # check for active orders
    active = db.execute(
        "SELECT id FROM orders WHERE gig_id = ? AND status NOT IN ('COMPLETED', 'CANCELLED')",
        gig_id
    )
    if active:
        flash_error("Can't delete a gig with active orders.")
        return redirect(url_for("gigs.detail", gig_id=gig_id))

    # delete images from disk
    old_images = db.execute("SELECT image_path FROM gig_images WHERE gig_id = ?", gig_id)
    for img in old_images:
        old_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "gigs", img["image_path"])
        if os.path.exists(old_path):
            os.remove(old_path)

    db.execute("DELETE FROM gig_images WHERE gig_id = ?", gig_id)
    db.execute("DELETE FROM wishlists WHERE gig_id = ?", gig_id)
    db.execute("DELETE FROM gigs WHERE id = ?", gig_id)

    flash_success("Gig deleted.")
    return redirect(url_for("gigs.index"))
