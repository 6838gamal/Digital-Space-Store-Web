import os
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app import models

app = FastAPI(title="Gamal Store Backend")

# ---------------------------
# Static Files (آمن للإنتاج)
# ---------------------------
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------------------
# Templates
# ---------------------------
templates = Jinja2Templates(directory="templates")

# ---------------------------
# Database Session
# ---------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------
# Startup Event (إنشاء الجداول)
# ---------------------------
@app.on_event("startup")
def on_startup():
    try:
        models.Base.metadata.create_all(bind=engine)
        print("✅ Database connected & tables ready")
    except Exception as e:
        print(f"❌ Database error: {e}")

# ---------------------------
# Routes
# ---------------------------

@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("index.html", {
        "request": request
    })

@app.get("/cart")
def view_cart(request: Request):
    return templates.TemplateResponse("cart.html", {
        "request": request
    })

@app.get("/checkout")
def checkout(request: Request):
    return templates.TemplateResponse("checkout.html", {
        "request": request
    })

@app.get("/category")
def category(request: Request):
    return templates.TemplateResponse("page-category.html", {
        "request": request
    })

@app.get("/product/{id}")
def product_detail(request: Request, id: int, db: Session = Depends(get_db)):
    return templates.TemplateResponse("page-single.html", {
        "request": request,
        "product_id": id
    })

# ---------------------------
# Health Check (مهم لـ Render)
# ---------------------------
@app.get("/health")
def health():
    return {"status": "ok"}
