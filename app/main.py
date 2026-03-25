import uvicorn
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# استيراد ملفات قاعدة البيانات (سننشئها في الخطوة التالية)
try:
    from app.database import SessionLocal, engine
    from app import models
    # إنشاء الجداول تلقائياً عند التشغيل
    models.Base.metadata.create_all(bind=engine)
except ImportWarning:
    print("تنبيه: لم يتم إعداد قاعدة البيانات بعد.")

app = FastAPI(title="Gamal Store Backend")

# 1. ربط المجلدات الثابتة (القالب الخاص بك يستخدم assets و css و js)
# سنفترض أنك وضعتهم داخل مجلد static
app.mount("/static", StaticFiles(directory="static"), name="static")

# 2. إعداد Jinja2 للتعامل مع ملفات HTML الخاصة بك
templates = Jinja2Templates(directory="templates")

# دالة الحصول على قاعدة البيانات
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- المسارات (Routes) لربط صفحات القالب ---

@app.get("/")
async def home(request: Request):
    # ربط ملف index.html
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/cart")
async def view_cart(request: Request):
    # ربط ملف cart.html
    return templates.TemplateResponse("cart.html", {"request": request})

@app.get("/checkout")
async def checkout(request: Request):
    # ربط ملف checkout.html
    return templates.TemplateResponse("checkout.html", {"request": request})

@app.get("/category")
async def category(request: Request):
    # ربط ملف page-category.html
    return templates.TemplateResponse("page-category.html", {"request": request})

@app.get("/product/{id}")
async def product_detail(request: Request, id: int):
    # ربط ملف page-single.html
    return templates.TemplateResponse("page-single.html", {"request": request, "product_id": id})

# --- دالة الماين للتشغيل ---

if __name__ == "__main__":
    # تشغيل السيرفر
    # uvicorn.run("المجلد.الملف:اسم_التطبيق")
    uvicorn.run("app.main:app", port=8000, reload=False)
