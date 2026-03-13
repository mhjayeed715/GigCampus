# GigCampus Design Document

## Overview
GigCampus is a campus-only micro-gig marketplace built with Flask and SQLite. It solves the problem of connecting students for small tasks within a university community.

## Technology Choices

### Flask vs Django
I chose Flask because:
- CS50 Week 9 teaches Flask, making it the natural choice
- Explicit routing and SQL queries are more readable and educational
- No hidden ORM magic or auto-generated admin panels
- Lightweight and perfect for a single-campus pilot
- Easier to understand every line of code

### SQLite vs PostgreSQL
- Single-file database with zero setup
- Sufficient for a single-campus deployment
- Matches CS50's curriculum (used throughout the course)
- Can migrate to PostgreSQL via SQLAlchemy if scaling to multiple universities

### Real-time Chat: Flask-SocketIO
- WebSocket support for instant messaging without page refresh
- Allows sellers to send offers directly in chat, which auto-create orders
- Integrates seamlessly with Flask

## Database Schema

11 tables with proper foreign key constraints:

- **users** — Student accounts with verification status, ghost count, ratings
- **gigs** — Job postings with title, description, price, category, images
- **gig_images** — Portfolio images (up to 3 per gig)
- **orders** — Transactions with state machine (PENDING → ACCEPTED → IN_PROGRESS → DELIVERED → APPROVED)
- **order_history** — Append-only audit trail of every status change
- **conversations** — Chat threads between buyer and seller
- **messages** — Individual messages with optional offer amounts
- **reviews** — 1-5 star ratings with comments (one per order per reviewer)
- **wishlists** — Buyer's saved gigs
- **ghost_flags** — Records of buyers who ghost sellers
- **disputes** — Conflict resolution with admin notes

## Key Features

### 1. Student Verification
- Requires `.ac.bd` university email
- Student ID photo upload (renamed with UUID for security)
- Manual admin approval before account goes live
- Ensures only real, enrolled students can use the platform

### 2. Order State Machine
Implemented in `routes/orders.py` using a `VALID_TRANSITIONS` dictionary:
```
PENDING → ACCEPTED → IN_PROGRESS → DELIVERED → APPROVED
         ↓                                      ↓
      CANCELLED                            DISPUTED
```

Every transition is validated and logged to `order_history`, creating an immutable audit trail. This prevents invalid state changes and gives both parties a clear record of what happened.

### 3. Ghost Detection (`ghost_check.py`)
Runs hourly via APScheduler:
- Finds orders stuck in DELIVERED status for >72 hours
- Buyer hasn't approved or disputed
- Creates a `ghost_flag` and increments buyer's `ghost_count`
- Ghost count is public on profiles and gig cards

72 hours chosen because:
- Covers a full weekend (realistic review time)
- Short enough that sellers aren't stuck waiting forever
- Prevents abuse of the system

### 4. Real-time Chat with Offers
- Sellers can send special "offer" messages with a BDT amount
- Buyer clicks "Accept" → order auto-created from that offer
- Entire negotiation-to-order flow happens in chat
- No page refresh needed (WebSocket-powered)

### 5. Admin Panel
- Verify student IDs (approve/reject)
- Resolve disputes (mark resolved/dismissed with notes)
- Full user management (edit, delete, reset passwords)
- Searchable user table
- Prevents deletion of admin accounts or users with active orders

### 6. Dashboard Analytics
- Total BDT earned/spent
- Active gigs and completed orders
- Completion rate and average rating
- Leaderboard: top 5 sellers per skill category
- Score = average rating × completed orders
- Live counters (polled every 30 seconds)
- Chart.js skill supply-vs-demand visualization

## Design Decisions

### Why Raw SQL Instead of ORM?
- More explicit and educational
- Easier to debug and understand
- Matches CS50's curriculum
- Can write complex queries without ORM abstraction

### Why Append-Only Order History?
- Immutable audit trail prevents tampering
- Both parties can see exactly what happened and when
- Reduces "he said she said" disputes
- Makes debugging easier

### Why Manual Admin Verification?
- Prevents fake accounts and outsiders
- Ensures community trust
- Scalable to multiple universities (each has their own admin)
- One-time cost per user

### Why 72-Hour Ghost Cutoff?
- Covers a full weekend
- Realistic time for buyer to review work
- Prevents sellers from being stuck indefinitely
- Balances fairness with accountability

### Why Public Ghost Count?
- Transparency helps sellers make informed decisions
- Incentivizes buyers to approve orders promptly
- Creates accountability without being punitive
- Buyers can improve their reputation by being responsive

## Frontend Architecture

### No Build Tools
- Bootstrap 5 from CDN
- Chart.js from CDN
- Vanilla JavaScript (no React/Vue)
- Jinja2 template inheritance

### JavaScript Files
- **chat.js** — SocketIO connection, message rendering, offer acceptance
- **counter.js** — Polls `/platform-stats` every 30 seconds, animates counters
- **filters.js** — Auto-submits gig filter form on dropdown change

### CSS
- Custom styling in `static/css/style.css`
- Hero gradient, card hover effects, chat bubbles, status badges
- Responsive media queries for mobile

## Security Considerations

### Password Hashing
- Werkzeug's scrypt hashing (industry standard)
- Never stored in plaintext

### File Uploads
- UUID-based filenames prevent directory traversal
- Extension whitelist (jpg, jpeg, png, gif, pdf)
- Stored outside web root
- Max file size: 16 MB

### CSRF Protection
- Flask-Login session management
- Form tokens in templates

### SQL Injection Prevention
- Parameterized queries throughout
- cs50 library handles escaping

## Challenges & Solutions

### Challenge: Real-time Chat on Windows
**Solution:** Flask-SocketIO with gevent on production (Render), threading locally

### Challenge: Preventing Invalid Order Transitions
**Solution:** State machine with `VALID_TRANSITIONS` dictionary and validation function

### Challenge: Detecting Ghosting Without Manual Reports
**Solution:** Automated hourly job checking for stale DELIVERED orders

### Challenge: Scaling to Multiple Universities
**Solution:** Admin-per-university model, email domain verification, database schema supports multiple institutions

## Future Improvements

1. **Payment Integration** — Stripe/bKash for actual money transfers
2. **Dispute Resolution** — Automated mediation before admin escalation
3. **Skill Verification** — Portfolio review or test-based skill badges
4. **Reputation System** — More nuanced scoring (recency, category-specific ratings)
5. **Mobile App** — React Native or Flutter
6. **Multi-University** — Expand to other campuses with separate admin teams
7. **Notifications** — Email/SMS alerts for order updates
8. **Search Improvements** — Full-text search, filters by skill level
