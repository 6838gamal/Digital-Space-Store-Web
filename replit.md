# Project Overview

Digital Space Store is a Python FastAPI web application using server-rendered Jinja2 templates, static assets, SQLAlchemy models, and a SQLite development database fallback at `store.db`.

# Project Structure

- `app/main.py` defines the FastAPI app, page routes, static file mounting, and startup database initialization.
- `app/chat_agent.py` contains the shopping assistant logic, retrieval over products/store knowledge, intent detection, and navigation actions.
- `app/database.py` configures SQLAlchemy using `DATABASE_URL` when present or SQLite locally.
- `app/models.py` contains Product, Order, and KnowledgeItem database models.
- `templates/` contains Jinja2 pages and partials.
- `static/` contains CSS and JavaScript assets.

# Chat/RAG Setup

- `/chat` is the shopping assistant screen opened by the floating button.
- `/api/chat` accepts chat messages and returns an Arabic assistant reply, relevant retrieval matches, suggestions, and navigation actions.
- `/api/knowledge` can list or add active store knowledge snippets for retrieval. This makes the assistant RAG-ready: product data and knowledge snippets are already separated from the response layer so embeddings/LLM generation can be added later.

# Replit Setup

- Run command: `uvicorn app.main:app --host 0.0.0.0 --port 5000`
- The web workflow serves the app on port 5000 for Replit preview.
- Deployment should run the same FastAPI app with Uvicorn on `0.0.0.0:5000`.