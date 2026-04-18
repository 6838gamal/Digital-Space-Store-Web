import os
from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app import models

app = FastAPI(title="Gamal Store Backend")

# ---------------------------
# Static Files
# ---------------------------
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
if os.path.isdir("static/images"):
    app.mount("/images", StaticFiles(directory="static/images"), name="images")

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
# Startup (إنشاء الجداول + بيانات تجريبية)
# ---------------------------
@app.on_event("startup")
def on_startup():
    try:
        models.Base.metadata.create_all(bind=engine)

        db = SessionLocal()

        # إضافة منتج تجريبي إذا لا يوجد بيانات
        if db.query(models.Product).count() == 0:
            sample_products = [
                models.Product(
                    name="Smart Routine System",
                    description="نظام ذكي لتنظيم حياتك اليومية",
                    price=25.0,
                    old_price=40.0,
                    image_url="/static/images/product1.jpg",
                    category="Productivity"
                ),
                models.Product(
                    name="Digital Store Kit",
                    description="كل ما تحتاجه لبدء متجرك الرقمي",
                    price=19.0,
                    image_url="/static/images/product2.jpg",
                    category="Business"
                )
            ]

            db.add_all(sample_products)
            db.commit()

        db.close()
        print("✅ Database ready")

    except Exception as e:
        print(f"❌ DB Error: {e}")

# ---------------------------
# Routes
# ---------------------------

@app.get("/", name="home")
def home(request: Request, tab: str = "home", db: Session = Depends(get_db)):
    products = db.query(models.Product).filter(models.Product.is_active == True).all()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "products": products,
            "active_tab": tab
        }
    )

@app.get("/cart", name="view_cart")
def view_cart(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="cart.html",
        context={}
    )

@app.get("/orders", name="orders")
def orders(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="orders.html",
        context={}
    )

@app.get("/checkout", name="checkout")
def checkout(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="checkout.html",
        context={}
    )

@app.get("/category", name="category")
def category(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="page-category.html",
        context={}
    )

@app.get("/product/{id}", name="product_detail")
def product_detail(request: Request, id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == id).first()
    return templates.TemplateResponse(
        request=request,
        name="page-single.html",
        context={"product": product}
    )

@app.get("/profile", name="profile")
def profile(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={}
    )

@app.get("/add-product", name="add_product")
def add_product(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="add-product.html",
        context={}
    )

@app.get("/logout", name="logout")
def logout():
    return RedirectResponse(url="/", status_code=302)

@app.get("/index.html")
def legacy_index():
    return RedirectResponse(url="/", status_code=302)

@app.get("/fashion.html")
def legacy_fashion():
    return RedirectResponse(url="/?tab=fashion", status_code=302)

@app.get("/electronic.html")
def legacy_electronic():
    return RedirectResponse(url="/?tab=electronic", status_code=302)

@app.get("/jewellery.html")
def legacy_jewellery():
    return RedirectResponse(url="/?tab=jewellery", status_code=302)

@app.get("/chat", name="chat")
def chat(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={}
    )


# ---------------------------
# Health Check (لـ Render)
# ---------------------------
@app.get("/health")
def health():
    return {"status": "ok"}
