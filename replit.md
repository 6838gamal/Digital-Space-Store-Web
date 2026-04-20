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
requirements.txt   - Python dependencies (cleaned, no duplicates)
Dockerfile         - Docker image build instructions
docker-compose.yml - App + PostgreSQL orchestration
.env.example       - Environment variables template
.dockerignore      - Docker build exclusions
```

## Docker Deployment
Copy `.env.example` to `.env`, fill in your values, then run:
```bash
docker compose up -d --build
```
The app will be available at `http://localhost:5000`.
PostgreSQL data is persisted in the `postgres_data` Docker volume.

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

## UI / UX Features
- **Flutter-style Drawers**: Both the store sidebar and AI chat use slide-in drawers with overlay
  - Store drawer: `#mySidenav.store-drawer` (opens from left; RTL: from right)
  - Chat drawer: conversation history (opens from left)
  - Close via ×, overlay click, or Escape key
- **Dark / Light Mode**: Full CSS variable system in `static/css/theme.css` (loads last; overrides all)
  - `:root` = light mode variables; `[data-theme="dark"]` overrides all colors
  - Persisted in `localStorage` key `dsTheme`
- **Bilingual (AR/EN)**: RTL/LTR switching on `<html dir>`, language persisted in `dsLang`
  - `data-en` / `data-ar` attributes + `data-trans` keys for dynamic content
- **Bottom nav bar**: Theme-aware via CSS variables (`--bar-bg`, `--bar-text`, `--bar-text-act`)
  - Overrides footer.css hardcoded colors in theme.css with `!important`
- **Admin modal**: Password `111`, slides in from top with shake animation on error
- **FAB**: Robot icon links to `/chat`, always above bottom bar

## Key CSS Architecture
- `static/css/theme.css` — master theme file (CSS vars + all component overrides)
  - Classes: `.store-drawer`, `.sd-item`, `.sd-section-label`, `.sd-admin-btn`, `.store-header-wrap`, `.store-top-bar`, `.store-main-header`, `.store-menu-btn`, `.store-action-btn`
  - Bottom bar: `.bottom-bar`, `.nav-item` — fully theme-aware
- `templates/banner.html` — store header + drawer HTML
- `templates/chat.html` — full-screen chat with its own drawer for history
- `templates/footer.html` — bottom bar + FAB
- `templates/base.html` — translations, theme/lang JS, admin modal, `openNav()`/`closeNav()`

## Dependencies
All installed via pip: fastapi, uvicorn, sqlalchemy, python-dotenv, jinja2, psycopg2-binary, itsdangerous, python-multipart
