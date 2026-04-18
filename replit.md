# Project Overview

Digital Space Store is a Python FastAPI web application using server-rendered Jinja2 templates, static assets, SQLAlchemy models, and a SQLite development database fallback at `store.db`.

# Project Structure

- `app/main.py` defines the FastAPI app, page routes, static file mounting, and startup database initialization.
- `app/database.py` configures SQLAlchemy using `DATABASE_URL` when present or SQLite locally.
- `app/models.py` contains Product and Order database models.
- `templates/` contains Jinja2 pages and partials.
- `static/` contains CSS and JavaScript assets.

# Replit Setup

- Run command: `uvicorn app.main:app --host 0.0.0.0 --port 5000`
- The web workflow serves the app on port 5000 for Replit preview.
- Deployment should run the same FastAPI app with Uvicorn on `0.0.0.0:5000`.