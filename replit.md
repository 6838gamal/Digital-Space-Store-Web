# Digital Space Store (Gamal Store Backend)

A FastAPI-based e-commerce web application with a customer storefront, admin dashboard, and AI chat agent for product discovery. Supports Arabic and English.

## Run & Operate
- **Start**: `uv run uvicorn app.main:app --host 0.0.0.0 --port 5000`
- **Required env vars**: `SESSION_SECRET` (set), `DATABASE_URL` (PostgreSQL, auto-provisioned)
- **Optional env vars**: `GEMINI_API_KEY` (enables Gemini AI replies in chat), `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` (enables Google OAuth for admin login)

## Stack
- **Backend**: Python 3.12 + FastAPI + Uvicorn
- **Database**: SQLAlchemy ORM with PostgreSQL (Replit-provisioned) or SQLite fallback
- **Templating**: Jinja2 server-side rendered HTML
- **Frontend**: Bootstrap 4, jQuery
- **Auth**: Cookie-based sessions (itsdangerous/SessionMiddleware) + optional Google OAuth2 for admins
- **AI**: Google Gemini via `google-genai` (optional; chat works in fallback mode without it)

## Where things live
- `app/main.py` — FastAPI app, all routes and startup logic
- `app/models.py` — SQLAlchemy ORM tables (products, orders, knowledge_items, admin_users, participants, chat, market)
- `app/database.py` — DB engine/session, reads `DATABASE_URL`
- `app/chat_agent.py` — AI chat agent (intent detection + RAG + Gemini)
- `app/market_parser.py` — File/URL parser (CSV, XLSX, JSON, TXT, PDF)
- `templates/` — Jinja2 HTML templates
- `static/` — CSS, JS, images (Bootstrap, jQuery, custom)
- `requirements.txt` — Python dependencies

## Architecture decisions
- **PostgreSQL by default on Replit**: `DATABASE_URL` is auto-provisioned; SQLite is only used if `DATABASE_URL` is unset
- **Session-based auth (no JWT)**: Admin login stored in server-side session cookie; no external auth provider required
- **Demo admin login**: Available in non-production (`NODE_ENV != production`) — enter any email/name at `/?admin=1`
- **Chat fallback**: If `GEMINI_API_KEY` is absent, the agent returns rule-based responses using intent detection
- **Startup migrations**: `on_startup()` creates tables and runs safe `ALTER TABLE` column additions automatically

## Product
- Customer storefront with products organized by category (fashion, electronics, jewellery)
- AI-powered chat agent for product discovery and navigation
- Admin dashboard to manage products, knowledge base, participants, and chat history
- Customer insights: per-participant summary of interests extracted automatically from chat
- Market analysis: per-channel dashboards (WhatsApp/Telegram/Instagram/TikTok/Facebook/X/YouTube/Snapchat) with file/URL upload, Chart.js charts, data tables, and archive
- Dark/light mode and bilingual (Arabic/English) support

## User preferences
- No changes: preserve existing code structure and dependencies

## Gotchas
- `GEMINI_API_KEY` must be added as a Secret for full AI chat functionality
- Google OAuth for admins requires `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` Secrets
- The admin modal password on the storefront is `111`
- Bottom nav bar and theme overrides live in `static/css/theme.css` (loads last, uses `!important`)

## Pointers
- Workflows skill: `.local/skills/workflows/SKILL.md`
- Environment secrets skill: `.local/skills/environment-secrets/SKILL.md`
