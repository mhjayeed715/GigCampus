# GigCampus Setup Guide

## Prerequisites
- Python 3.8+
- pip (Python package manager)

## Installation

1. **Clone or download the project**
   ```bash
   cd GigCampus
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the database**
   ```bash
   python -c "from app import create_app; app = create_app()"
   ```
   This creates `gigcampus.db` with all tables.

5. **Create an admin account**
   ```bash
   python seed_admin.py
   ```
   Follow the prompts to set up the first admin user.

## Running the Application

```bash
python run.py
```

The app will start at `http://localhost:5000`

## First Steps

1. **Log in as admin** using the credentials you created
2. **Go to Admin Panel** (top right menu)
3. **Verify some test student accounts** (if any exist)
4. **Create a student account** to test the platform
5. **Post a gig** and explore the marketplace

## Project Structure

- `app.py` — Flask application factory
- `models.py` — Database schema and initialization
- `helpers.py` — Shared utilities and decorators
- `ghost_check.py` — Background job for ghost detection
- `routes/` — Blueprint route handlers (auth, gigs, orders, chat, etc.)
- `templates/` — Jinja2 HTML templates
- `static/` — CSS, JavaScript, and uploaded files
- `requirements.txt` — Python dependencies

## Environment Variables (Optional)

Create a `.env` file in the project root:
```
SECRET_KEY=your-secret-key-here
RENDER=false  # Set to true if deploying on Render
```

If not set, the app uses safe defaults for development.

## Troubleshooting

**"ModuleNotFoundError: No module named 'flask'"**
- Make sure you've activated the virtual environment and run `pip install -r requirements.txt`

**"Database is locked"**
- SQLite can have concurrency issues. Restart the app.

**Chat not working**
- Make sure you're using a modern browser with WebSocket support
- Check browser console for errors

**Ghost checker not running**
- It only runs in production mode or when `WERKZEUG_RUN_MAIN=true`
- In development, you can manually test by checking the database

## Deployment

The project includes `render.yaml` for deployment on Render.com. See that file for production configuration.
