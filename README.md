# GigCampus

#### Video Demo: https://youtu.be/qiRYTkmh1co

#### Description:

GigCampus is a campus-only micro-gig marketplace I built as my CS50x final project. The idea came from a problem I deal with every semester as a university student in Bangladesh that there is simply no good way to hire a fellow student for a small task. Think about it: a CSE student who needs a logo designed and a Fine Arts student who has made thirty logos this semester are literally in the same building, but nothing connects them. Facebook groups are messy and full of ghosting. Fiverr needs international payment methods most of us don't have, and the minimum prices don't make sense for a 300 BDT translation job. WhatsApp groups get buried after two days. I wanted a platform where verified students can post small gigs, negotiate in real time, and actually get paid with a trust system that keeps people accountable. That's GigCampus.

## How It Works

The whole thing is a full-stack web app written in Python with Flask. The database is SQLite, and real-time chat runs on Flask-SocketIO (WebSockets). Every user has to upload a photo of their student ID when they register, and an admin has to manually approve it before the account goes live. This way, every single person on the platform is a real, currently-enrolled student. No fakes, no outsiders.

## Why Flask and SQLite

I went with Flask instead of Django because Flask is what CS50 teaches in Week 9, and honestly I just like how explicit it is. There's no hidden ORM magic or auto-generated admin panel where every route, every SQL query, every template is right there and readable. Django would have been overkill for this. Same reasoning for SQLite over PostgreSQL. SQLite is a single file, zero setup, and it's the database engine CS50 uses throughout the course. If this ever needed to scale to multiple universities, I could migrate to PostgreSQL through SQLAlchemy, but for a single-campus pilot SQLite does the job perfectly.

## Project Structure & Files

The codebase is organized into a pretty standard Flask layout. Here's what each file does:

**run.py** — The entry point. It's literally five lines: imports the app factory and starts the dev server with SocketIO. Nothing fancy.

**app.py** — The application factory. This is where I create the Flask app, register all eight blueprints, set up upload directories, initialize Flask-Login and Flask-SocketIO, and call the database init function. There's also a context processor that injects admin status and unread message counts into every template so the navbar can show notification badges.

**models.py** — All the database schema lives here, written as raw SQL with the cs50 library. I sketched the entity-relationship diagram on paper first, then wrote out every CREATE TABLE statement myself. There are eleven tables total: users, gigs, gig_images, orders, order_history, conversations, messages, reviews, wishlists, ghost_flags, and disputes. Each one has proper foreign key constraints and sensible defaults.

**helpers.py** — Shared utility stuff. The `login_required` decorator, a `verified_required` decorator (so unverified users can't post gigs), an `allowed_file` function that checks upload extensions, a `format_bdt` Jinja2 filter that turns 1500 into "1,500 BDT," and a `User` class that wraps database rows for Flask-Login compatibility. Nothing groundbreaking, but it keeps the route files clean.

**ghost_check.py** — This is probably the most unique part of the project, and I'll talk about it more below.

**seed_admin.py** — A one-time script to create the initial admin account so someone can actually verify the first batch of students.

## Routes (the routes/ directory)

I split the route logic into eight blueprint files:

**routes/auth.py** — Registration (with student ID upload), login with password verification using werkzeug's scrypt hashing, and logout. Registration enforces `.ac.bd` university email addresses only, and uploaded ID images get renamed with UUIDs so nobody can guess filenames.

**routes/gigs.py** — The gig browsing page with filters for category, max price, minimum rating, and keyword search. Also the gig detail view, the creation form with up to three portfolio image uploads, and a wishlist toggle endpoint that returns JSON for the AJAX heart button. Sellers can edit their own gigs (update title, description, pricing, images, etc.) or delete them entirely — though deleting is blocked if the gig has any active orders, so nothing gets nuked mid-transaction.

**routes/orders.py** — This is the part I'm most proud of. I built a state machine using a Python dictionary called `VALID_TRANSITIONS` that maps each order status to its allowed next statuses: `PENDING → ACCEPTED → IN_PROGRESS → DELIVERED → APPROVED`, plus paths to `CANCELLED` and `DISPUTED`. A helper function called `transition_order` validates every status change before executing it and logs every transition into the `order_history` table. This creates an append-only audit trail — both buyer and seller can see exactly what happened and when, which seriously cuts down on "he said she said" disputes.

**routes/chat.py** — Real-time messaging using Flask-SocketIO. When a buyer clicks "Message Seller" on a gig page, a conversation is created (or resumed if one already exists). Messages show up instantly without page refresh. The cool part: sellers can send special "offer" messages with a BDT amount attached, and if the buyer clicks "Accept," a formal order gets auto-created from that offer. The whole negotiation-to-order flow happens right inside the chat.

**routes/reviews.py** — After an order reaches APPROVED status, both buyer and seller can leave a 1–5 star review with an optional comment. The database enforces a UNIQUE constraint on (order_id, reviewer_id), so nobody can spam reviews.

**routes/dashboard.py** — A personal analytics page showing total BDT earned, BDT spent, active gigs, completed orders, completion rate, and average rating. It also serves the leaderboard, which ranks the top five sellers per skill category using a simple score: average rating × number of completed orders. Two JSON API endpoints power the homepage live counter (polled every 30 seconds) and the Chart.js skill-gap bar chart.

**routes/profile.py** — Public student profiles showing a user's gigs, reviews, stats, and — importantly — their ghost count.

**routes/admin.py** — The admin panel for verifying student IDs (approve or reject), resolving disputes (mark resolved or dismissed with an admin note), and full user management. The "All Users" tab lists every registered user in a searchable table — admins can edit any user's details (username, email, university, verification status, ghost count, even reset passwords) or delete accounts entirely. Deleting is blocked for admin accounts and users with active orders to prevent data loss mid-transaction.

## Ghost Detection

This is a feature I designed specifically for the student marketplace context. A "ghost" is a buyer who receives delivered work but then just... disappears. Never approves the delivery, never files a dispute, just goes silent. This happens all the time in informal student deals and it's incredibly frustrating for the seller.

My solution is `ghost_check.py`, which runs an APScheduler background job every hour. The job looks for orders stuck in DELIVERED status for more than 72 hours where the buyer hasn't approved OR filed a dispute. For each one, it creates a `ghost_flag` record and bumps the buyer's `ghost_count`. That count shows up publicly on their profile and on gig cards, so future sellers can judge the risk before taking an order from that person.

I picked 72 hours as the cutoff because it covers a full weekend — enough time for a buyer to realistically look over the work — but short enough that sellers aren't stuck waiting forever.

## Frontend

The frontend is Bootstrap 5 loaded from CDN, so I didn't need npm or any build tools. Chart.js (also CDN) draws the skill supply-vs-demand bar chart on the dashboard. All templates extend a base `layout.html` using Jinja2 inheritance, exactly like CS50 Week 9 and the Finance problem set taught us.

The JavaScript files are all vanilla JS, no React or anything:

- **static/js/chat.js** — Handles the SocketIO connection, message rendering, offer acceptance, and auto-scrolling in the chat window.
- **static/js/counter.js** — Polls the `/platform-stats` endpoint every 30 seconds and animates the homepage counters with a smooth count-up effect using `requestAnimationFrame`.
- **static/js/filters.js** — Auto-submits the gig filter form when you change a dropdown. Dead simple.

**static/css/style.css** — All custom styling: the hero gradient, gig card hover effects, chat bubble colors, order status badges, leaderboard layout, admin panel tabs, and responsive media queries.

## Design Decisions

A few decisions I want to call out:

- **Raw SQL over an ORM**: CS50 drills raw SQL into you, and I actually prefer it for a project this size. Every query is visible and debuggable. No hidden N+1 problems.
- **State machine for orders**: I could have just done if/else chains, but the dictionary-based state machine is cleaner, easier to extend, and impossible to accidentally bypass. Every transition is validated.
- **72-hour ghost window**: Long enough to be fair, short enough to be useful. I tested a few thresholds mentally and 72 hours felt right for the student schedule.
- **UUID filenames for uploads**: Prevents filename guessing and path traversal. A small security detail but an important one.

## AI Tools Disclosure

Per CS50's policy — I used GitHub Copilot as a helper throughout this project. Every file where I used it has an "AI Citation" comment at the top explaining exactly what I used it for (scaffolding the app factory pattern, reviewing SQL constraints, checking edge cases in the state machine, etc.). The core logic, database design, and architecture decisions are all mine. I sketched the ER diagram on paper, I designed the ghost detection system, I decided on the state machine approach for orders. Copilot helped me move faster on boilerplate and caught a couple of bugs I might have missed, but the thinking behind every feature is my own work.

## What I'd Add Next

If I keep working on this after CS50, the obvious next steps would be: bKash/Nagad payment integration (since that's what Bangladeshi students actually use), email notifications for order updates, a mobile-friendly PWA wrapper, and multi-university support with per-institution verification flows. But the current version already covers the full lifecycle — register, verify, post gigs, browse, chat, negotiate, order, deliver, review, and track trust — and I'm honestly pretty happy with how it turned out.
