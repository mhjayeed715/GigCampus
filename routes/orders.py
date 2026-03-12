# routes/orders.py - order lifecycle with state machine
# I sketched the state transitions on paper first then coded the dict.
# Copilot flagged that DISPUTED needed to be a terminal state too
# (I originally only had APPROVED and CANCELLED as terminal).

import os
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import get_db
from helpers import allowed_file, verified_required, flash_error, flash_success

orders_bp = Blueprint("orders", __name__)

# which transitions are allowed from each status
VALID_TRANSITIONS = {
    "PENDING":      ["ACCEPTED", "CANCELLED"],
    "ACCEPTED":     ["IN_PROGRESS", "CANCELLED"],
    "IN_PROGRESS":  ["DELIVERED", "DISPUTED"],
    "DELIVERED":    ["APPROVED", "DISPUTED"],
    "APPROVED":     [],
    "DISPUTED":     [],
    "CANCELLED":    [],
}


def transition_order(db, order_id, new_status, user_id, note=""):
    """Validate and execute a status transition, log it to order_history."""
    order = db.execute("SELECT * FROM orders WHERE id = ?", order_id)
    if not order:
        raise ValueError("Order not found.")

    current_status = order[0]["status"]

    if new_status not in VALID_TRANSITIONS.get(current_status, []):
        raise ValueError(
            f"Cannot transition from {current_status} to {new_status}."
        )

    db.execute("UPDATE orders SET status = ? WHERE id = ?", new_status, order_id)

    # audit trail
    db.execute(
        "INSERT INTO order_history (order_id, old_status, new_status, changed_by, note) "
        "VALUES (?, ?, ?, ?, ?)",
        order_id, current_status, new_status, user_id, note
    )

    return True


@orders_bp.route("/orders", methods=["GET"])
@login_required
def index():
    db = get_db()

    buying = db.execute(
        "SELECT o.*, COALESCE(g.title, '[Deleted Gig]') AS gig_title, "
        "COALESCE(u.username, '[Deleted User]') AS seller_name "
        "FROM orders o "
        "LEFT JOIN gigs g ON o.gig_id = g.id "
        "LEFT JOIN users u ON o.seller_id = u.id "
        "WHERE o.buyer_id = ? ORDER BY o.created_at DESC",
        current_user.id
    )

    selling = db.execute(
        "SELECT o.*, COALESCE(g.title, '[Deleted Gig]') AS gig_title, "
        "COALESCE(u.username, '[Deleted User]') AS buyer_name "
        "FROM orders o "
        "LEFT JOIN gigs g ON o.gig_id = g.id "
        "LEFT JOIN users u ON o.buyer_id = u.id "
        "WHERE o.seller_id = ? ORDER BY o.created_at DESC",
        current_user.id
    )

    return render_template("orders/index.html", buying=buying, selling=selling)


@orders_bp.route("/orders/<int:order_id>")
@login_required
def detail(order_id):
    db = get_db()

    order = db.execute(
        "SELECT o.*, COALESCE(g.title, '[Deleted Gig]') AS gig_title, "
        "COALESCE(g.description, '') AS gig_description, "
        "COALESCE(buyer.username, '[Deleted User]') AS buyer_name, "
        "COALESCE(seller.username, '[Deleted User]') AS seller_name, "
        "COALESCE(buyer.ghost_count, 0) AS buyer_ghost_count "
        "FROM orders o "
        "LEFT JOIN gigs g ON o.gig_id = g.id "
        "LEFT JOIN users buyer ON o.buyer_id = buyer.id "
        "LEFT JOIN users seller ON o.seller_id = seller.id "
        "WHERE o.id = ?",
        order_id
    )

    if not order:
        flash_error("Order not found.")
        return redirect(url_for("orders.index"))

    order = order[0]

    # only buyer/seller can see this
    if current_user.id != order["buyer_id"] and current_user.id != order["seller_id"]:
        flash_error("You do not have permission to view this order.")
        return redirect(url_for("orders.index"))

    # timeline
    history = db.execute(
        "SELECT oh.*, u.username AS changed_by_name "
        "FROM order_history oh "
        "JOIN users u ON oh.changed_by = u.id "
        "WHERE oh.order_id = ? ORDER BY oh.timestamp ASC",
        order_id
    )

    # did current user already review this order?
    existing_review = db.execute(
        "SELECT id FROM reviews WHERE order_id = ? AND reviewer_id = ?",
        order_id, current_user.id
    )
    has_reviewed = len(existing_review) > 0

    # check for existing conversation
    conv = db.execute(
        "SELECT id FROM conversations WHERE gig_id = (SELECT gig_id FROM orders WHERE id = ?) "
        "AND buyer_id = ? AND seller_id = ?",
        order_id, order["buyer_id"], order["seller_id"]
    )
    conversation_id = conv[0]["id"] if conv else None

    return render_template(
        "orders/detail.html",
        order=order,
        history=history,
        has_reviewed=has_reviewed,
        conversation_id=conversation_id
    )


@orders_bp.route("/orders", methods=["POST"])
@login_required
@verified_required
def create():
    db = get_db()

    gig_id = request.form.get("gig_id", type=int)
    agreed_price = request.form.get("agreed_price", type=int)

    if not gig_id or not agreed_price:
        flash_error("Gig ID and agreed price are required.")
        return redirect(url_for("gigs.index"))

    # Fetch the gig
    gig = db.execute("SELECT * FROM gigs WHERE id = ? AND status = 'active'", gig_id)
    if not gig:
        flash_error("Gig not found or no longer active.")
        return redirect(url_for("gigs.index"))

    gig = gig[0]

    if gig["seller_id"] == current_user.id:
        flash_error("You cannot order your own gig.")
        return redirect(url_for("gigs.detail", gig_id=gig_id))

    if agreed_price < 0:
        flash_error("Invalid price.")
        return redirect(url_for("gigs.detail", gig_id=gig_id))

    # create the order
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    order_id = db.execute(
        "INSERT INTO orders (gig_id, buyer_id, seller_id, agreed_price, status, payment_confirmed_at) "
        "VALUES (?, ?, ?, ?, 'PENDING', ?)",
        gig_id, current_user.id, gig["seller_id"], agreed_price, now
    )

    # log initial status
    db.execute(
        "INSERT INTO order_history (order_id, old_status, new_status, changed_by, note) "
        "VALUES (?, NULL, 'PENDING', ?, 'Order placed')",
        order_id, current_user.id
    )

    flash_success("Order placed successfully! Waiting for seller to accept.")
    return redirect(url_for("orders.detail", order_id=order_id))


@orders_bp.route("/orders/<int:order_id>/accept", methods=["POST"])
@login_required
def accept(order_id):
    """PENDING → ACCEPTED"""
    db = get_db()

    order = db.execute("SELECT * FROM orders WHERE id = ?", order_id)
    if not order:
        flash_error("Order not found.")
        return redirect(url_for("orders.index"))

    order = order[0]

    # only seller can accept
    if current_user.id != order["seller_id"]:
        flash_error("Only the seller can accept this order.")
        return redirect(url_for("orders.detail", order_id=order_id))

    try:
        transition_order(db, order_id, "ACCEPTED", current_user.id, "Order accepted by seller")
    except ValueError as e:
        flash_error(str(e))
        return redirect(url_for("orders.detail", order_id=order_id))

    # create conversation if there isn't one yet
    existing_conv = db.execute(
        "SELECT id FROM conversations WHERE gig_id = ? AND buyer_id = ? AND seller_id = ?",
        order["gig_id"], order["buyer_id"], order["seller_id"]
    )
    if not existing_conv:
        db.execute(
            "INSERT INTO conversations (gig_id, buyer_id, seller_id) VALUES (?, ?, ?)",
            order["gig_id"], order["buyer_id"], order["seller_id"]
        )

    flash_success("Order accepted! You can now start working on it.")
    return redirect(url_for("orders.detail", order_id=order_id))


@orders_bp.route("/orders/<int:order_id>/start", methods=["POST"])
@login_required
def start(order_id):
    """ACCEPTED → IN_PROGRESS"""
    db = get_db()

    order = db.execute("SELECT * FROM orders WHERE id = ?", order_id)
    if not order or current_user.id != order[0]["seller_id"]:
        flash_error("Permission denied.")
        return redirect(url_for("orders.index"))

    try:
        transition_order(db, order_id, "IN_PROGRESS", current_user.id, "Work started")
    except ValueError as e:
        flash_error(str(e))

    return redirect(url_for("orders.detail", order_id=order_id))


@orders_bp.route("/orders/<int:order_id>/deliver", methods=["POST"])
@login_required
def deliver(order_id):
    """Seller uploads deliverable."""
    db = get_db()

    order = db.execute("SELECT * FROM orders WHERE id = ?", order_id)
    if not order:
        flash_error("Order not found.")
        return redirect(url_for("orders.index"))

    order = order[0]

    if current_user.id != order["seller_id"]:
        flash_error("Only the seller can deliver this order.")
        return redirect(url_for("orders.detail", order_id=order_id))

    # File upload required
    if "delivery_file" not in request.files:
        flash_error("Please upload a delivery file.")
        return redirect(url_for("orders.detail", order_id=order_id))

    file = request.files["delivery_file"]
    if file.filename == "":
        flash_error("No file selected.")
        return redirect(url_for("orders.detail", order_id=order_id))

    if not allowed_file(file.filename):
        flash_error("Invalid file type.")
        return redirect(url_for("orders.detail", order_id=order_id))

    # Save file
    ext = file.filename.rsplit(".", 1)[1].lower()
    random_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "deliverables", random_name)
    file.save(save_path)

    # update order with file path and timestamp
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "UPDATE orders SET delivery_file = ?, delivered_at = ? WHERE id = ?",
        random_name, now, order_id
    )

    # handle transition (might be from ACCEPTED or IN_PROGRESS)
    current_status = order["status"]
    if current_status == "ACCEPTED":
        # First transition to IN_PROGRESS, then to DELIVERED
        transition_order(db, order_id, "IN_PROGRESS", current_user.id, "Work started")
        transition_order(db, order_id, "DELIVERED", current_user.id, "Delivery uploaded")
    elif current_status == "IN_PROGRESS":
        transition_order(db, order_id, "DELIVERED", current_user.id, "Delivery uploaded")
    else:
        flash_error(f"Cannot deliver from status: {current_status}")
        return redirect(url_for("orders.detail", order_id=order_id))

    flash_success("Order delivered! Waiting for buyer approval.")
    return redirect(url_for("orders.detail", order_id=order_id))


@orders_bp.route("/orders/<int:order_id>/approve", methods=["POST"])
@login_required
def approve(order_id):
    """DELIVERED → APPROVED"""
    db = get_db()

    order = db.execute("SELECT * FROM orders WHERE id = ?", order_id)
    if not order:
        flash_error("Order not found.")
        return redirect(url_for("orders.index"))

    order = order[0]

    if current_user.id != order["buyer_id"]:
        flash_error("Only the buyer can approve this order.")
        return redirect(url_for("orders.detail", order_id=order_id))

    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute("UPDATE orders SET approved_at = ? WHERE id = ?", now, order_id)
        transition_order(db, order_id, "APPROVED", current_user.id, "Delivery approved by buyer")
    except ValueError as e:
        flash_error(str(e))
        return redirect(url_for("orders.detail", order_id=order_id))

    flash_success("Order complete! Please leave a review.")
    return redirect(url_for("orders.detail", order_id=order_id))


@orders_bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@login_required
def cancel(order_id):
    db = get_db()

    order = db.execute("SELECT * FROM orders WHERE id = ?", order_id)
    if not order:
        flash_error("Order not found.")
        return redirect(url_for("orders.index"))

    order = order[0]

    if current_user.id not in (order["buyer_id"], order["seller_id"]):
        flash_error("Permission denied.")
        return redirect(url_for("orders.index"))

    try:
        transition_order(db, order_id, "CANCELLED", current_user.id, "Order cancelled")
    except ValueError as e:
        flash_error(str(e))

    return redirect(url_for("orders.detail", order_id=order_id))


@orders_bp.route("/orders/<int:order_id>/dispute", methods=["POST"])
@login_required
def dispute(order_id):
    db = get_db()

    order = db.execute("SELECT * FROM orders WHERE id = ?", order_id)
    if not order:
        flash_error("Order not found.")
        return redirect(url_for("orders.index"))

    order = order[0]

    if current_user.id not in (order["buyer_id"], order["seller_id"]):
        flash_error("Permission denied.")
        return redirect(url_for("orders.index"))

    reason = request.form.get("reason", "").strip()
    evidence_text = request.form.get("evidence_text", "").strip()

    if not reason:
        flash_error("Please provide a reason for the dispute.")
        return redirect(url_for("orders.detail", order_id=order_id))

    # Handle evidence file if uploaded
    evidence_file = ""
    if "evidence_file" in request.files:
        file = request.files["evidence_file"]
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit(".", 1)[1].lower()
            random_name = f"{uuid.uuid4().hex}.{ext}"
            save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "deliverables", random_name)
            file.save(save_path)
            evidence_file = random_name

    # Create dispute
    db.execute(
        "INSERT INTO disputes (order_id, raised_by, reason, evidence_text, evidence_file) "
        "VALUES (?, ?, ?, ?, ?)",
        order_id, current_user.id, reason, evidence_text, evidence_file
    )

    # Transition order to DISPUTED
    try:
        transition_order(db, order_id, "DISPUTED", current_user.id, f"Dispute raised: {reason}")
    except ValueError as e:
        flash_error(str(e))
        return redirect(url_for("orders.detail", order_id=order_id))

    flash_success("Dispute submitted. An admin will review it.")
    return redirect(url_for("orders.detail", order_id=order_id))
