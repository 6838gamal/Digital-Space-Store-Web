import json
import os
import secrets
import uuid
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen

from fastapi import FastAPI, Request, Depends, Form, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.database import SessionLocal, engine
from app import models
from app.chat_agent import build_agent_response, ensure_default_knowledge

app = FastAPI(title="Gamal Store Backend")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "development-session-secret-change-before-production"),
)

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

        ensure_default_knowledge(db)
        db.close()
        print("✅ Database ready")

    except Exception as e:
        print(f"❌ DB Error: {e}")

# ---------------------------
# Routes
# ---------------------------

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    history: list[ChatMessage] = []
    conversation_id: int | None = None

class KnowledgeCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    content: str = Field(..., min_length=5)
    tags: str = ""

def get_or_create_participant(request: Request, db: Session) -> models.StoreParticipant:
    session_key = request.session.get("participant_session_key")
    if not session_key:
        session_key = str(uuid.uuid4())
        request.session["participant_session_key"] = session_key

    participant = db.query(models.StoreParticipant).filter(models.StoreParticipant.session_key == session_key).first()
    if participant:
        participant.last_seen_at = datetime.utcnow()
        db.commit()
        return participant

    participant = models.StoreParticipant(session_key=session_key)
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant

def get_current_admin(request: Request, db: Session):
    admin_id = request.session.get("admin_user_id")
    if not admin_id:
        return None
    return db.query(models.AdminUser).filter(models.AdminUser.id == admin_id).first()

def require_admin(request: Request, db: Session):
    admin = get_current_admin(request, db)
    if not admin:
        return None
    return admin

def redirect_to_admin_login():
    # Send unauthenticated users back to the store (modal opens there)
    return RedirectResponse(url="/?admin=1", status_code=302)

def render_admin_login(request: Request, message: str = ""):
    google_ready = bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))
    return templates.TemplateResponse(
        request=request,
        name="admin-login.html",
        context={
            "message": message,
            "google_ready": google_ready,
            "allow_demo": os.getenv("NODE_ENV") != "production",
        },
    )

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

@app.post("/api/chat")
def chat_api(request: Request, payload: ChatRequest, db: Session = Depends(get_db)):
    participant = get_or_create_participant(request, db)

    conversation = None
    if payload.conversation_id:
        conversation = db.query(models.ChatConversation).filter(
            models.ChatConversation.id == payload.conversation_id,
            models.ChatConversation.participant_id == participant.id,
        ).first()

    if not conversation:
        title = payload.message[:60] if payload.message else "محادثة جديدة"
        conversation = models.ChatConversation(participant_id=participant.id, title=title)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    user_message = models.ChatMessageRecord(
        conversation_id=conversation.id,
        role="user",
        content=payload.message,
    )
    db.add(user_message)

    response = build_agent_response(payload.message, db)
    assistant_message = models.ChatMessageRecord(
        conversation_id=conversation.id,
        role="assistant",
        content=response["reply"],
    )
    db.add(assistant_message)
    conversation.updated_at = datetime.utcnow()
    if conversation.title == "محادثة جديدة":
        conversation.title = payload.message[:60]
    db.commit()

    response["conversation_id"] = conversation.id
    response["conversation_title"] = conversation.title
    return response

@app.get("/api/chat/conversations")
def list_chat_conversations(request: Request, db: Session = Depends(get_db)):
    participant = get_or_create_participant(request, db)
    conversations = db.query(models.ChatConversation).filter(
        models.ChatConversation.participant_id == participant.id
    ).order_by(models.ChatConversation.updated_at.desc()).all()
    return [
        {
            "id": conversation.id,
            "title": conversation.title,
            "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else "",
        }
        for conversation in conversations
    ]

@app.post("/api/chat/conversations")
def create_chat_conversation(request: Request, db: Session = Depends(get_db)):
    participant = get_or_create_participant(request, db)
    conversation = models.ChatConversation(participant_id=participant.id, title="محادثة جديدة")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return {"id": conversation.id, "title": conversation.title}

@app.get("/api/chat/conversations/{conversation_id}")
def get_chat_conversation(request: Request, conversation_id: int, db: Session = Depends(get_db)):
    participant = get_or_create_participant(request, db)
    conversation = db.query(models.ChatConversation).filter(
        models.ChatConversation.id == conversation_id,
        models.ChatConversation.participant_id == participant.id,
    ).first()
    if not conversation:
        return {"id": None, "title": "", "messages": []}
    messages = db.query(models.ChatMessageRecord).filter(
        models.ChatMessageRecord.conversation_id == conversation.id
    ).order_by(models.ChatMessageRecord.created_at.asc()).all()
    return {
        "id": conversation.id,
        "title": conversation.title,
        "messages": [
            {"role": message.role, "content": message.content}
            for message in messages
        ],
    }

@app.get("/api/chat/capabilities")
def chat_capabilities():
    return {
        "capabilities": [
            "استرجاع معلومات المنتجات من قاعدة البيانات",
            "استرجاع معرفة المتجر القابلة للإضافة لاحقاً",
            "اقتراح منتجات وروابط تنقل داخلية",
            "توجيه المستخدم إلى السلة والدفع والطلبات والحساب",
        ],
        "rag_ready": True,
    }

@app.get("/api/knowledge")
def list_knowledge(db: Session = Depends(get_db)):
    items = db.query(models.KnowledgeItem).filter(models.KnowledgeItem.is_active == True).all()
    return [
        {
            "id": item.id,
            "title": item.title,
            "content": item.content,
            "tags": item.tags,
        }
        for item in items
    ]

@app.post("/api/knowledge")
def add_knowledge(payload: KnowledgeCreate, db: Session = Depends(get_db)):
    item = models.KnowledgeItem(
        title=payload.title,
        content=payload.content,
        tags=payload.tags,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "title": item.title,
        "content": item.content,
        "tags": item.tags,
    }

@app.get("/admin/login")
def admin_login(request: Request):
    # No standalone login page — redirect to store (admin modal opens there)
    return RedirectResponse(url="/", status_code=302)

@app.get("/admin/auth/google")
def admin_google_login(request: Request):
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return render_admin_login(request, "تسجيل Google غير مفعّل بعد. أضف بيانات OAuth لتفعيله.")
    state = secrets.token_urlsafe(24)
    request.session["google_oauth_state"] = state
    redirect_uri = str(request.url_for("admin_google_callback"))
    query = urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "state": state,
    })
    return RedirectResponse(url=f"https://accounts.google.com/o/oauth2/v2/auth?{query}", status_code=302)

@app.get("/admin/auth/google/callback")
def admin_google_callback(request: Request, code: str = "", state: str = "", db: Session = Depends(get_db)):
    expected_state = request.session.get("google_oauth_state")
    if not expected_state or expected_state != state:
        return render_admin_login(request, "تعذر التحقق من جلسة تسجيل الدخول.")

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = str(request.url_for("admin_google_callback"))
    token_payload = urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }).encode()
    token_request = UrlRequest(
        "https://oauth2.googleapis.com/token",
        data=token_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        token_data = json.loads(urlopen(token_request, timeout=15).read().decode())
        access_token = token_data["access_token"]
        profile_request = UrlRequest(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        profile = json.loads(urlopen(profile_request, timeout=15).read().decode())
    except Exception:
        return render_admin_login(request, "فشل تسجيل الدخول عبر Google. حاول مرة أخرى.")

    email = profile.get("email", "")
    name = profile.get("name") or email
    picture = profile.get("picture", "")
    if not email:
        return render_admin_login(request, "لم يتم استلام البريد الإلكتروني من Google.")

    admin = db.query(models.AdminUser).filter(models.AdminUser.email == email).first()
    if admin:
        admin.name = name
        admin.picture_url = picture
    else:
        admin = models.AdminUser(email=email, name=name, picture_url=picture)
        db.add(admin)
    db.commit()
    db.refresh(admin)
    request.session["admin_user_id"] = admin.id
    return RedirectResponse(url="/admin", status_code=302)

@app.post("/admin/demo-login")
async def admin_demo_login(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    email = str(form.get("admin_email", "")).strip() or "gamal@gmail.com"
    name  = str(form.get("admin_name",  "")).strip() or "مدير المتجر"

    admin = db.query(models.AdminUser).filter(models.AdminUser.email == email).first()
    if admin:
        admin.name = name
    else:
        admin = models.AdminUser(email=email, name=name, provider="firebase")
        db.add(admin)
    db.commit()
    db.refresh(admin)
    request.session["admin_user_id"] = admin.id
    return RedirectResponse(url="/admin", status_code=302)

@app.post("/admin/logout")
def admin_logout(request: Request):
    request.session.pop("admin_user_id", None)
    return RedirectResponse(url="/", status_code=302)

@app.get("/admin")
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return redirect_to_admin_login()
    products = db.query(models.Product).order_by(models.Product.id.desc()).all()
    knowledge_items = db.query(models.KnowledgeItem).order_by(models.KnowledgeItem.id.desc()).all()
    participants = db.query(models.StoreParticipant).order_by(models.StoreParticipant.last_seen_at.desc()).all()
    conversations = db.query(models.ChatConversation).order_by(models.ChatConversation.updated_at.desc()).limit(20).all()
    admins = db.query(models.AdminUser).order_by(models.AdminUser.created_at.desc()).all()
    response = templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "admin": admin,
            "products": products,
            "knowledge_items": knowledge_items,
            "participants": participants,
            "conversations": conversations,
            "admins": admins,
        },
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response

@app.post("/admin/products")
def admin_create_product(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    price: float = Form(...),
    old_price: str = Form(""),
    image_url: str = Form(""),
    category: str = Form(""),
    is_active: str = Form("on"),
    db: Session = Depends(get_db),
):
    admin = require_admin(request, db)
    if not admin:
        return redirect_to_admin_login()
    product = models.Product(
        name=name,
        description=description,
        price=price,
        old_price=float(old_price) if old_price else None,
        image_url=image_url,
        category=category,
        is_active=is_active == "on",
    )
    db.add(product)
    db.commit()
    return RedirectResponse(url="/admin#products", status_code=302)

@app.post("/admin/products/{product_id}")
def admin_update_product(
    request: Request,
    product_id: int,
    name: str = Form(...),
    description: str = Form(""),
    price: float = Form(...),
    old_price: str = Form(""),
    image_url: str = Form(""),
    category: str = Form(""),
    is_active: str = Form(""),
    db: Session = Depends(get_db),
):
    admin = require_admin(request, db)
    if not admin:
        return redirect_to_admin_login()
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if product:
        product.name = name
        product.description = description
        product.price = price
        product.old_price = float(old_price) if old_price else None
        product.image_url = image_url
        product.category = category
        product.is_active = is_active == "on"
        db.commit()
    return RedirectResponse(url="/admin#products", status_code=302)

@app.post("/admin/products/{product_id}/delete")
def admin_delete_product(request: Request, product_id: int, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return redirect_to_admin_login()
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if product:
        db.delete(product)
        db.commit()
    return RedirectResponse(url="/admin#products", status_code=302)

@app.post("/admin/knowledge")
def admin_create_knowledge(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    tags: str = Form(""),
    db: Session = Depends(get_db),
):
    admin = require_admin(request, db)
    if not admin:
        return redirect_to_admin_login()
    db.add(models.KnowledgeItem(title=title, content=content, tags=tags))
    db.commit()
    return RedirectResponse(url="/admin#rag", status_code=302)

@app.post("/admin/knowledge/{item_id}")
def admin_update_knowledge(
    request: Request,
    item_id: int,
    title: str = Form(...),
    content: str = Form(...),
    tags: str = Form(""),
    is_active: str = Form(""),
    db: Session = Depends(get_db),
):
    admin = require_admin(request, db)
    if not admin:
        return redirect_to_admin_login()
    item = db.query(models.KnowledgeItem).filter(models.KnowledgeItem.id == item_id).first()
    if item:
        item.title = title
        item.content = content
        item.tags = tags
        item.is_active = is_active == "on"
        db.commit()
    return RedirectResponse(url="/admin#rag", status_code=302)

@app.post("/admin/knowledge/{item_id}/delete")
def admin_delete_knowledge(request: Request, item_id: int, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return redirect_to_admin_login()
    item = db.query(models.KnowledgeItem).filter(models.KnowledgeItem.id == item_id).first()
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/admin#rag", status_code=302)

@app.post("/admin/rag/upload")
async def admin_upload_rag(
    request: Request,
    file: UploadFile = File(...),
    tags: str = Form("uploaded"),
    db: Session = Depends(get_db),
):
    admin = require_admin(request, db)
    if not admin:
        return redirect_to_admin_login()
    raw = await file.read()
    content = raw.decode("utf-8", errors="ignore").strip()
    if content:
        title = file.filename or "ملف تدريب"
        db.add(models.KnowledgeItem(title=title, content=content, tags=tags))
        db.commit()
    return RedirectResponse(url="/admin#rag", status_code=302)


# ---------------------------
# Health Check (لـ Render)
# ---------------------------
@app.get("/health")
def health():
    return {"status": "ok"}
