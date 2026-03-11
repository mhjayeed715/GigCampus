# routes/chat.py - real-time messaging with Flask-SocketIO
# Used the SocketIO docs for the room join/leave pattern.
# The offer-to-order flow I figured out myself but Copilot
# helped me get the emit() calls right.

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask_socketio import emit, join_room, leave_room
from app import socketio
from models import get_db
from helpers import flash_error, flash_success, verified_required
from datetime import datetime

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/inbox")
@login_required
def inbox():
    db = get_db()

    conversations = db.execute(
        """
        SELECT c.*,
               g.title  AS gig_title,
               buyer.username  AS buyer_name,
               seller.username AS seller_name,
               buyer.avatar    AS buyer_avatar,
               seller.avatar   AS seller_avatar,
               (SELECT body FROM messages
                WHERE conversation_id = c.id
                ORDER BY created_at DESC LIMIT 1) AS last_message,
               (SELECT created_at FROM messages
                WHERE conversation_id = c.id
                ORDER BY created_at DESC LIMIT 1) AS last_message_at,
               (SELECT COUNT(*) FROM messages
                WHERE conversation_id = c.id
                  AND sender_id != ?
                  AND is_read = 0) AS unread_count
        FROM conversations c
        JOIN users buyer  ON c.buyer_id  = buyer.id
        JOIN users seller ON c.seller_id = seller.id
        LEFT JOIN gigs g  ON c.gig_id    = g.id
        WHERE c.buyer_id = ? OR c.seller_id = ?
        ORDER BY last_message_at DESC
        """,
        current_user.id, current_user.id, current_user.id
    )

    return render_template("chat/inbox.html", conversations=conversations)


@chat_bp.route("/chat/<int:conversation_id>")
@login_required
def window(conversation_id):
    db = get_db()

    conv = db.execute("SELECT * FROM conversations WHERE id = ?", conversation_id)
    if not conv:
        flash_error("Conversation not found.")
        return redirect(url_for("orders.index"))

    conv = conv[0]

    # only participants can see this chat
    if current_user.id not in (conv["buyer_id"], conv["seller_id"]):
        flash_error("You do not have permission to view this conversation.")
        return redirect(url_for("orders.index"))

    # figure out who the other person is
    if current_user.id == conv["buyer_id"]:
        other_user = db.execute("SELECT username, avatar FROM users WHERE id = ?", conv["seller_id"])
    else:
        other_user = db.execute("SELECT username, avatar FROM users WHERE id = ?", conv["buyer_id"])

    other_user = other_user[0] if other_user else {"username": "Unknown", "avatar": "default.png"}

    # gig info if linked
    gig = None
    if conv["gig_id"]:
        gig_rows = db.execute("SELECT id, title FROM gigs WHERE id = ?", conv["gig_id"])
        gig = gig_rows[0] if gig_rows else None

    # last 50 messages
    messages = db.execute(
        "SELECT m.*, u.username AS sender_name, u.avatar AS sender_avatar "
        "FROM messages m JOIN users u ON m.sender_id = u.id "
        "WHERE m.conversation_id = ? ORDER BY m.created_at ASC LIMIT 50",
        conversation_id
    )

    # mark messages from the other person as read
    db.execute(
        "UPDATE messages SET is_read = 1 WHERE conversation_id = ? AND sender_id != ?",
        conversation_id, current_user.id
    )

    return render_template(
        "chat/window.html",
        conversation=conv,
        messages=messages,
        other_user=other_user,
        gig=gig
    )


@chat_bp.route("/chat/start/<int:gig_id>", methods=["POST"])
@login_required
@verified_required
def start_conversation(gig_id):
    db = get_db()

    # Get the gig
    gig = db.execute("SELECT * FROM gigs WHERE id = ?", gig_id)
    if not gig:
        flash_error("Gig not found.")
        return redirect(url_for("gigs.index"))

    gig = gig[0]

    if gig["seller_id"] == current_user.id:
        flash_error("You cannot message yourself about your own gig.")
        return redirect(url_for("gigs.detail", gig_id=gig_id))

    # check if conversation already exists
    existing = db.execute(
        "SELECT id FROM conversations WHERE gig_id = ? AND buyer_id = ? AND seller_id = ?",
        gig_id, current_user.id, gig["seller_id"]
    )

    if existing:
        return redirect(url_for("chat.window", conversation_id=existing[0]["id"]))

    # Create new conversation
    conv_id = db.execute(
        "INSERT INTO conversations (gig_id, buyer_id, seller_id) VALUES (?, ?, ?)",
        gig_id, current_user.id, gig["seller_id"]
    )

    return redirect(url_for("chat.window", conversation_id=conv_id))


# SocketIO event handlers

@socketio.on("join")
def handle_join(data):
    conversation_id = data.get("conversation_id")
    if conversation_id:
        join_room(str(conversation_id))
        emit("status", {"msg": f"{current_user.username} joined the chat"}, room=str(conversation_id))


@socketio.on("send_message")
def handle_send_message(data):
    db = get_db()

    conversation_id = data.get("conversation_id")
    body = data.get("body", "").strip()
    msg_type = data.get("msg_type", "text")
    offer_amount = data.get("offer_amount")

    if not body and msg_type == "text":
        return

    # make sure user is actually in this conversation
    conv = db.execute("SELECT * FROM conversations WHERE id = ?", conversation_id)
    if not conv:
        return
    conv = conv[0]
    if current_user.id not in (conv["buyer_id"], conv["seller_id"]):
        return

    # save to db
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg_id = db.execute(
        "INSERT INTO messages (conversation_id, sender_id, body, msg_type, offer_amount, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        conversation_id, current_user.id, body, msg_type, offer_amount, now
    )

    # broadcast to everyone in the room
    emit("new_message", {
        "id": msg_id,
        "sender_id": current_user.id,
        "sender_name": current_user.username,
        "sender_avatar": current_user.avatar,
        "body": body,
        "msg_type": msg_type,
        "offer_amount": offer_amount,
        "created_at": now
    }, room=str(conversation_id))


@socketio.on("accept_offer")
def handle_accept_offer(data):
    """Buyer accepts a chat offer -> creates a real Order."""
    db = get_db()

    message_id = data.get("message_id")
    if not message_id:
        return

    # Fetch the offer message
    msg = db.execute("SELECT * FROM messages WHERE id = ? AND msg_type = 'offer'", message_id)
    if not msg:
        return
    msg = msg[0]

    # Fetch the conversation
    conv = db.execute("SELECT * FROM conversations WHERE id = ?", msg["conversation_id"])
    if not conv:
        return
    conv = conv[0]

    # Only the buyer can accept an offer
    if current_user.id != conv["buyer_id"]:
        return

    # Mark the offer as accepted
    db.execute("UPDATE messages SET offer_status = 'accepted' WHERE id = ?", message_id)

    # Create a formal order from the offer
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    order_id = db.execute(
        "INSERT INTO orders (gig_id, buyer_id, seller_id, agreed_price, status, payment_confirmed_at) "
        "VALUES (?, ?, ?, ?, 'PENDING', ?)",
        conv["gig_id"], conv["buyer_id"], conv["seller_id"], msg["offer_amount"], now
    )

    # Log in order_history
    db.execute(
        "INSERT INTO order_history (order_id, old_status, new_status, changed_by, note) "
        "VALUES (?, NULL, 'PENDING', ?, 'Order created from chat offer')",
        order_id, current_user.id
    )

    # Notify the room
    emit("offer_accepted", {
        "message_id": message_id,
        "order_id": order_id,
        "accepted_by": current_user.username
    }, room=str(msg["conversation_id"]))
