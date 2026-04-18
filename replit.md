# Digital Space Store (Gamal Store Backend)

## Overview
A FastAPI-based e-commerce web application featuring a customer-facing storefront, an admin dashboard, and an integrated AI Chat Agent for product discovery. The app supports Arabic and English.

## Tech Stack
- **Backend**: Python 3.12 + FastAPI + Uvicorn
- **Database**: SQLAlchemy ORM with SQLite (default) or PostgreSQL (production)
- **Templating**: Jinja2 server-side rendered HTML
- **Frontend**: Bootstrap 4, jQuery
- **Auth**: Session-based (itsdangerous) + optional Google OAuth2 for admins

## Project Structure
```
app/
  main.py          - FastAPI app, all routes and startup logic
  models.py        - SQLAlchemy ORM models
  database.py      - DB connection and session management
  chat_agent.py    - AI chat agent (intent detection + RAG)
templates/         - Jinja2 HTML templates
static/            - CSS, JS, images
requirements.txt   - Python dependencies
```

## Running the App
The app starts via the "Start application" workflow:
```
uvicorn app.main:app --host 0.0.0.0 --port 5000
```

## Key Routes
- `GET /` — Storefront home page
- `GET /admin` — Admin dashboard (login required)
- `GET /admin/login` — Admin login page (demo login available in non-production)
- `POST /api/chat` — AI chat agent endpoint
- `GET /health` — Health check

## Environment Variables
- `SESSION_SECRET` — Secret key for session middleware (required for production)
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — Optional, enables Google OAuth for admin login
- `NODE_ENV` — Set to `production` to disable demo admin login

## Database
- Defaults to SQLite (`store.db`) for development
- Supports PostgreSQL via `DATABASE_URL` environment variable
- Tables and seed data are created automatically on startup

## Dependencies
All installed via pip: fastapi, uvicorn, sqlalchemy, python-dotenv, jinja2, psycopg2-binary, itsdangerous, python-multipart
