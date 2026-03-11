# ghost_check.py - background job that flags "ghost" buyers
#
# A ghost = buyer who gets the delivery but never approves or disputes.
# This runs every hour and checks for orders stuck in DELIVERED for 72+ hours.
# 72 hours because it covers a weekend but doesn't leave sellers hanging too long.
#
# Copilot helped me add the NOT IN subquery for disputes - I originally
# forgot to exclude orders that already had a dispute filed.

import logging
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


def check_for_ghosts(app):
    """Flag buyers who ghosted after delivery (72h+ no response)."""
    with app.app_context():
        from models import get_db
        db = get_db()

        # orders delivered 72+ hours ago with no ghost flag or dispute yet
        ghost_orders = db.execute("""
            SELECT o.id AS order_id, o.buyer_id, u.username AS buyer_name
            FROM orders o
            JOIN users u ON o.buyer_id = u.id
            WHERE o.status = 'DELIVERED'
              AND o.delivered_at < datetime('now', '-72 hours')
              AND o.id NOT IN (SELECT order_id FROM ghost_flags)
              AND o.id NOT IN (SELECT order_id FROM disputes)
        """)

        if not ghost_orders:
            logger.info("Ghost check: No new ghosts detected.")
            return

        for order in ghost_orders:
            db.execute(
                "INSERT INTO ghost_flags (buyer_id, order_id, auto_detected) "
                "VALUES (?, ?, 1)",
                order["buyer_id"], order["order_id"]
            )

            # Increment the buyer's ghost_count
            db.execute(
                "UPDATE users SET ghost_count = ghost_count + 1 WHERE id = ?",
                order["buyer_id"]
            )

            logger.info(
                "Ghost flag created for order %s, buyer '%s' (ID: %s)",
                order["order_id"], order["buyer_name"], order["buyer_id"]
            )

        logger.info("Ghost check complete: %d new ghost(s) flagged.", len(ghost_orders))


def start_ghost_checker(app):
    """
    Start the APScheduler background job for ghost detection.
    Called from app.py after the app is created.
    The job runs every hour.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=check_for_ghosts,
        trigger="interval",
        hours=1,
        args=[app],
        id="ghost_check",
        name="Check for ghost buyers",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Ghost checker scheduler started (runs every hour).")
