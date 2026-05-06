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

from app.database import SessionLocal, engine, SQLALCHEMY_DATABASE_URL
from app import models
from app.chat_agent import build_agent_response, ensure_default_knowledge, update_participant_insight

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
def _migrate_participant_columns():
    """Add new columns to store_participants if missing (safe on PG and SQLite)."""
    from sqlalchemy import text
    new_cols = [
        ("photo_url",     "VARCHAR(500) DEFAULT ''"),
        ("firebase_uid",  "VARCHAR(255) DEFAULT ''"),
        ("provider",      "VARCHAR(50)  DEFAULT ''"),
        ("phone",         "VARCHAR(50)  DEFAULT ''"),
        ("locale",        "VARCHAR(20)  DEFAULT ''"),
        ("subscribed_at", "TIMESTAMP NULL"),
    ]
    is_pg = not SQLALCHEMY_DATABASE_URL.startswith("sqlite")
    with engine.begin() as conn:
        for col, ddl in new_cols:
            try:
                if is_pg:
                    conn.execute(text(f"ALTER TABLE store_participants ADD COLUMN IF NOT EXISTS {col} {ddl}"))
                else:
                    conn.execute(text(f"ALTER TABLE store_participants ADD COLUMN {col} {ddl}"))
            except Exception:
                # column already exists (sqlite path) — ignore
                pass
        # helpful index for lookups by Google uid
        try:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_store_participants_firebase_uid ON store_participants (firebase_uid)"))
        except Exception:
            pass


@app.on_event("startup")
def on_startup():
    try:
        models.Base.metadata.create_all(bind=engine)
        _migrate_participant_columns()

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

        # Seed market channels
        for ch in models.MARKET_CHANNELS:
            exists = db.query(models.MarketChannel).filter(models.MarketChannel.slug == ch["slug"]).first()
            if not exists:
                db.add(models.MarketChannel(**ch))
        db.commit()

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

    history_dicts = [{"role": m.role, "content": m.content} for m in payload.history]
    response = build_agent_response(payload.message, db, history=history_dicts)
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

    update_participant_insight(participant.id, payload.message, response, db)

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

class SubscribePayload(BaseModel):
    uid:      str  = Field(default="", max_length=255)
    email:    str  = Field(default="", max_length=255)
    name:     str  = Field(default="", max_length=255)
    photo:    str  = Field(default="", max_length=500)
    provider: str  = Field(default="google", max_length=50)
    phone:    str  = Field(default="", max_length=50)
    locale:   str  = Field(default="", max_length=20)


@app.post("/api/subscribe")
def api_subscribe(request: Request, payload: SubscribePayload, db: Session = Depends(get_db)):
    """Record a Google-signed-in subscriber so they appear in the admin dashboard."""
    if not (payload.uid or payload.email):
        return {"ok": False, "error": "missing_identity"}

    participant = get_or_create_participant(request, db)

    # Prefer matching by firebase uid (stable), then email
    existing = None
    if payload.uid:
        existing = db.query(models.StoreParticipant).filter(
            models.StoreParticipant.firebase_uid == payload.uid
        ).first()
    if not existing and payload.email:
        existing = db.query(models.StoreParticipant).filter(
            models.StoreParticipant.email == payload.email
        ).first()

    target = existing if (existing and existing.id != participant.id) else participant

    if payload.name:     target.display_name  = payload.name
    if payload.email:    target.email         = payload.email
    if payload.photo:    target.photo_url     = payload.photo
    if payload.uid:      target.firebase_uid  = payload.uid
    if payload.provider: target.provider      = payload.provider
    if payload.phone:    target.phone         = payload.phone
    if payload.locale:   target.locale        = payload.locale
    if not target.subscribed_at:
        target.subscribed_at = datetime.utcnow()
    target.last_seen_at = datetime.utcnow()

    db.commit()
    db.refresh(target)
    return {
        "ok": True,
        "participant_id": target.id,
        "email": target.email,
        "name":  target.display_name,
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

def build_google_redirect_uri(request: Request) -> str:
    uri = str(request.url_for("admin_google_callback"))
    if uri.startswith("http://"):
        uri = "https://" + uri[7:]
    return uri

@app.get("/admin/auth/google")
def admin_google_login(request: Request):
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return render_admin_login(request, "تسجيل Google غير مفعّل بعد. أضف بيانات OAuth لتفعيله.")
    state = secrets.token_urlsafe(24)
    request.session["google_oauth_state"] = state
    redirect_uri = build_google_redirect_uri(request)
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
    redirect_uri = build_google_redirect_uri(request)
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
    # Subscribers = participants who actually identified themselves (Google sign-in or email)
    subscribers = [
        p for p in participants
        if (p.email and p.email.strip()) or (getattr(p, "firebase_uid", "") or "").strip()
    ]
    subscribers.sort(
        key=lambda p: (getattr(p, "subscribed_at", None) or p.last_seen_at or p.created_at),
        reverse=True,
    )
    conversations = db.query(models.ChatConversation).order_by(models.ChatConversation.updated_at.desc()).limit(20).all()
    all_conv = db.query(models.ChatConversation).all()
    all_chat_participant_ids = {c.participant_id for c in all_conv}
    chat_participants = db.query(models.StoreParticipant).filter(
        models.StoreParticipant.id.in_(all_chat_participant_ids)
    ).order_by(models.StoreParticipant.last_seen_at.desc()).all()
    insights = db.query(models.ParticipantInsight).all()
    insights_map = {ins.participant_id: ins for ins in insights}
    response = templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "admin": admin,
            "products": products,
            "knowledge_items": knowledge_items,
            "participants": participants,
            "subscribers": subscribers,
            "conversations": conversations,
            "chat_participants": chat_participants,
            "insights_map": insights_map,
        },
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response

@app.get("/admin/participant/{participant_id}")
def admin_participant_detail(request: Request, participant_id: int, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    participant = db.query(models.StoreParticipant).filter(models.StoreParticipant.id == participant_id).first()
    if not participant:
        return {"error": "not found"}
    insight = db.query(models.ParticipantInsight).filter(
        models.ParticipantInsight.participant_id == participant_id
    ).first()
    convs = db.query(models.ChatConversation).filter(
        models.ChatConversation.participant_id == participant_id
    ).order_by(models.ChatConversation.updated_at.desc()).all()
    conv_data = []
    for conv in convs:
        msgs = db.query(models.ChatMessageRecord).filter(
            models.ChatMessageRecord.conversation_id == conv.id
        ).order_by(models.ChatMessageRecord.created_at.asc()).all()
        conv_data.append({
            "id": conv.id,
            "title": conv.title,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else "",
            "messages": [{"role": m.role, "content": m.content} for m in msgs],
        })
    return {
        "participant": {
            "id": participant.id,
            "name": participant.display_name,
            "email": participant.email,
            "phone": participant.phone,
            "photo_url": participant.photo_url,
            "provider": participant.provider,
            "created_at": participant.created_at.isoformat() if participant.created_at else "",
            "last_seen_at": participant.last_seen_at.isoformat() if participant.last_seen_at else "",
        },
        "insight": {
            "summary": insight.summary if insight else "",
            "interested_products": insight.interested_products if insight else "",
            "interested_categories": insight.interested_categories if insight else "",
            "intents_seen": insight.intents_seen if insight else "",
            "message_count": insight.message_count if insight else 0,
            "updated_at": insight.updated_at.isoformat() if insight and insight.updated_at else "",
        },
        "conversations": conv_data,
    }

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
# Voice Transcription API
# ---------------------------
@app.post("/api/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    lang: str = Form("en"),
):
    import tempfile
    from google import genai as gai
    from google.genai import types as gtypes

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return {"text": "", "error": "No Gemini API key"}

    try:
        raw = await audio.read()
        if not raw:
            return {"text": "", "error": "Empty audio"}

        client = gai.Client(api_key=api_key)

        suffix = ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name

        try:
            uploaded = client.files.upload(file=tmp_path, config={"mime_type": "audio/webm"})
            lang_name = "Arabic" if lang == "ar" else "English"
            prompt = (
                f"Transcribe this audio recording exactly as spoken in {lang_name}. "
                "Return only the transcribed text, nothing else."
            )
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[uploaded, prompt],
            )
            text = response.text.strip()
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        return {"text": text}
    except Exception as e:
        print(f"Transcribe error: {e}")
        return {"text": "", "error": str(e)}


# ============================================================
# PUBLISHING SCHEDULER — API routes
# ============================================================

PUBLISH_CHANNELS = [
    {"slug": "whatsapp",  "name": "واتساب",    "icon": "💬", "color": "#25D366"},
    {"slug": "telegram",  "name": "تيليغرام",  "icon": "✈️", "color": "#2AABEE"},
    {"slug": "instagram", "name": "إنستغرام",  "icon": "📸", "color": "#E1306C"},
    {"slug": "tiktok",    "name": "تيك توك",   "icon": "🎵", "color": "#1a1a1a"},
    {"slug": "facebook",  "name": "فيسبوك",    "icon": "👍", "color": "#1877F2"},
    {"slug": "twitter",   "name": "تويتر / X", "icon": "🐦", "color": "#1DA1F2"},
    {"slug": "youtube",   "name": "يوتيوب",    "icon": "▶️", "color": "#FF0000"},
    {"slug": "snapchat",  "name": "سناب شات",  "icon": "👻", "color": "#f5c518"},
    {"slug": "linkedin",  "name": "لينكدإن",   "icon": "💼", "color": "#0A66C2"},
    {"slug": "threads",   "name": "ثريدز",     "icon": "🧵", "color": "#101010"},
]


def _schedule_to_dict(s: models.PublishSchedule, targets: list) -> dict:
    return {
        "id": s.id,
        "title": s.title,
        "base_content": s.base_content,
        "status": s.status,
        "scheduled_at": s.scheduled_at.strftime("%Y-%m-%dT%H:%M") if s.scheduled_at else "",
        "scheduled_at_display": s.scheduled_at.strftime("%Y-%m-%d %H:%M") if s.scheduled_at else "—",
        "notes": s.notes,
        "source_id": s.source_id,
        "created_at": s.created_at.strftime("%Y-%m-%d %H:%M"),
        "updated_at": s.updated_at.strftime("%Y-%m-%d %H:%M"),
        "targets": [
            {
                "id": t.id,
                "channel_slug": t.channel_slug,
                "channel_name": t.channel_name,
                "channel_icon": t.channel_icon,
                "channel_color": t.channel_color,
                "customized_text": t.customized_text,
                "with_hashtags": t.with_hashtags,
                "hashtags": t.hashtags,
                "status": t.status,
                "published_at": t.published_at.strftime("%Y-%m-%d %H:%M") if t.published_at else "",
                "error_msg": t.error_msg,
            } for t in targets
        ],
    }


@app.get("/admin/api/publish/channels")
def publish_channels(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    return PUBLISH_CHANNELS


@app.get("/admin/api/publish/generated")
def publish_generated(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    items = db.query(models.GeneratedContent).order_by(models.GeneratedContent.created_at.desc()).limit(30).all()
    return [{"id": i.id, "topic": i.topic, "content_type": i.content_type, "content": i.content, "created_at": i.created_at.strftime("%Y-%m-%d %H:%M")} for i in items]


@app.post("/admin/api/publish/schedules")
async def publish_create(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    body = await request.json()

    base_content = (body.get("base_content") or "").strip()
    if not base_content:
        return {"error": "المحتوى مطلوب."}

    sched_str = (body.get("scheduled_at") or "").strip()
    sched_dt = None
    if sched_str:
        try:
            sched_dt = datetime.fromisoformat(sched_str)
        except Exception:
            pass

    status = body.get("status", "draft")
    if sched_dt and status == "draft":
        status = "scheduled"

    schedule = models.PublishSchedule(
        title=(body.get("title") or base_content[:80]),
        base_content=base_content,
        status=status,
        scheduled_at=sched_dt,
        notes=body.get("notes", ""),
        source_id=body.get("source_id"),
    )
    db.add(schedule)
    db.flush()

    targets_data = body.get("targets", [])
    created_targets = []
    for t in targets_data:
        slug = t.get("channel_slug", "")
        ch_info = next((c for c in PUBLISH_CHANNELS if c["slug"] == slug), {})
        target = models.PublishTarget(
            schedule_id=schedule.id,
            channel_slug=slug,
            channel_name=t.get("channel_name") or ch_info.get("name", slug),
            channel_icon=t.get("channel_icon") or ch_info.get("icon", "📢"),
            channel_color=t.get("channel_color") or ch_info.get("color", "#64748b"),
            customized_text=t.get("customized_text", ""),
            with_hashtags=bool(t.get("with_hashtags", False)),
            hashtags=t.get("hashtags", ""),
            status="pending",
        )
        db.add(target)
        created_targets.append(target)

    db.commit()
    db.refresh(schedule)
    for t in created_targets:
        db.refresh(t)

    return _schedule_to_dict(schedule, created_targets)


@app.get("/admin/api/publish/schedules")
def publish_list(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    schedules = db.query(models.PublishSchedule).order_by(models.PublishSchedule.created_at.desc()).all()
    result = []
    for s in schedules:
        targets = db.query(models.PublishTarget).filter(models.PublishTarget.schedule_id == s.id).all()
        result.append(_schedule_to_dict(s, targets))
    return result


@app.get("/admin/api/publish/stats")
def publish_stats(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    total = db.query(models.PublishSchedule).count()
    scheduled = db.query(models.PublishSchedule).filter(models.PublishSchedule.status == "scheduled").count()
    published = db.query(models.PublishSchedule).filter(models.PublishSchedule.status == "published").count()
    drafts = db.query(models.PublishSchedule).filter(models.PublishSchedule.status == "draft").count()
    targets_published = db.query(models.PublishTarget).filter(models.PublishTarget.status == "published").count()
    return {"total": total, "scheduled": scheduled, "published": published, "drafts": drafts, "targets_published": targets_published}


@app.put("/admin/api/publish/schedules/{sched_id}")
async def publish_update(request: Request, sched_id: int, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    s = db.query(models.PublishSchedule).filter(models.PublishSchedule.id == sched_id).first()
    if not s:
        return {"error": "not found"}
    body = await request.json()
    if "status" in body:
        s.status = body["status"]
    if "scheduled_at" in body:
        try:
            s.scheduled_at = datetime.fromisoformat(body["scheduled_at"]) if body["scheduled_at"] else None
        except Exception:
            pass
    if "notes" in body:
        s.notes = body["notes"]
    s.updated_at = datetime.utcnow()
    db.commit()
    targets = db.query(models.PublishTarget).filter(models.PublishTarget.schedule_id == sched_id).all()
    return _schedule_to_dict(s, targets)


@app.post("/admin/api/publish/targets/{target_id}/mark-published")
def publish_mark_target(request: Request, target_id: int, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    t = db.query(models.PublishTarget).filter(models.PublishTarget.id == target_id).first()
    if not t:
        return {"error": "not found"}
    t.status = "published"
    t.published_at = datetime.utcnow()
    # Check if all targets published
    all_targets = db.query(models.PublishTarget).filter(models.PublishTarget.schedule_id == t.schedule_id).all()
    if all(x.status == "published" for x in all_targets):
        s = db.query(models.PublishSchedule).filter(models.PublishSchedule.id == t.schedule_id).first()
        if s:
            s.status = "published"
            s.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "target_id": target_id}


@app.post("/admin/api/publish/targets/{target_id}/mark-failed")
async def publish_mark_failed(request: Request, target_id: int, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    body = await request.json()
    t = db.query(models.PublishTarget).filter(models.PublishTarget.id == target_id).first()
    if t:
        t.status = "failed"
        t.error_msg = body.get("error_msg", "")
        db.commit()
    return {"ok": True}


@app.delete("/admin/api/publish/schedules/{sched_id}")
def publish_delete(request: Request, sched_id: int, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    db.query(models.PublishTarget).filter(models.PublishTarget.schedule_id == sched_id).delete()
    db.query(models.PublishSchedule).filter(models.PublishSchedule.id == sched_id).delete()
    db.commit()
    return {"ok": True}


# ============================================================
# CONTENT GENERATION — API routes
# ============================================================
from app.content_gen import chunk_text, extract_keywords, generate_content as _generate_content
from app.market_parser import parse_upload as _mkt_parse_upload, fetch_url as _mkt_fetch_url


@app.post("/admin/api/content-gen/train")
async def content_gen_train(
    request: Request,
    db: Session = Depends(get_db),
    file: UploadFile | None = File(default=None),
    url: str = Form(default=""),
):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}

    parsed = None
    source_type = ""
    source_ref = ""

    if file and file.filename:
        raw = await file.read()
        parsed = _mkt_parse_upload(file.filename, raw)
        source_type = "file"
        source_ref = file.filename
    elif url.strip():
        parsed = _mkt_fetch_url(url.strip())
        source_type = "url"
        source_ref = url.strip()
    else:
        return {"error": "يرجى إرفاق ملف أو رابط."}

    rows = parsed.get("rows", [])
    cols = parsed.get("columns", [])
    if rows and cols:
        full_text = "\n".join(" | ".join(str(c) for c in row) for row in rows)
    else:
        full_text = parsed.get("summary", "")

    if not full_text.strip():
        return {"error": "لم يتم استخراج أي نص من الملف."}

    words = full_text.split()
    chunks = chunk_text(full_text)

    doc = models.ContentTrainingDoc(
        source_type=source_type,
        source_ref=source_ref,
        title=source_ref.split("/")[-1].split("?")[0][:200],
        chunk_count=len(chunks),
        word_count=len(words),
    )
    db.add(doc)
    db.flush()

    for i, chunk_text_val in enumerate(chunks):
        kw = extract_keywords(chunk_text_val, 30)
        db.add(models.ContentChunk(
            doc_id=doc.id,
            text=chunk_text_val,
            keywords=",".join(kw),
            position=i,
        ))
    db.commit()
    db.refresh(doc)

    return {
        "id": doc.id,
        "source_type": source_type,
        "source_ref": source_ref,
        "chunk_count": doc.chunk_count,
        "word_count": doc.word_count,
        "created_at": doc.created_at.strftime("%Y-%m-%d %H:%M"),
    }


@app.get("/admin/api/content-gen/docs")
def content_gen_docs(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    docs = db.query(models.ContentTrainingDoc).order_by(models.ContentTrainingDoc.created_at.desc()).all()
    total_chunks = db.query(models.ContentChunk).count()
    return {
        "docs": [
            {
                "id": d.id,
                "source_type": d.source_type,
                "source_ref": d.source_ref,
                "title": d.title,
                "chunk_count": d.chunk_count,
                "word_count": d.word_count,
                "created_at": d.created_at.strftime("%Y-%m-%d %H:%M"),
            } for d in docs
        ],
        "total_chunks": total_chunks,
    }


@app.delete("/admin/api/content-gen/docs/{doc_id}")
def content_gen_delete_doc(request: Request, doc_id: int, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    db.query(models.ContentChunk).filter(models.ContentChunk.doc_id == doc_id).delete()
    db.query(models.ContentTrainingDoc).filter(models.ContentTrainingDoc.id == doc_id).delete()
    db.commit()
    return {"ok": True}


@app.post("/admin/api/content-gen/generate")
async def content_gen_generate(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    body = await request.json()
    topic = (body.get("topic") or "").strip()
    content_type = body.get("content_type", "post")
    language = body.get("language", "ar")
    tone = body.get("tone", "professional")
    with_hashtags = bool(body.get("with_hashtags", False))
    length_hint = body.get("length_hint", "medium")

    if not topic:
        return {"error": "يرجى إدخال موضوع أو كلمات مفتاحية."}

    content = _generate_content(topic, content_type, language, tone, with_hashtags, length_hint, db)

    record = models.GeneratedContent(
        content_type=content_type,
        topic=topic,
        language=language,
        tone=tone,
        with_hashtags=with_hashtags,
        length_hint=length_hint,
        content=content,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "id": record.id,
        "content": content,
        "content_type": content_type,
        "topic": topic,
        "created_at": record.created_at.strftime("%Y-%m-%d %H:%M"),
    }


@app.get("/admin/api/content-gen/history")
def content_gen_history(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    items = db.query(models.GeneratedContent).order_by(models.GeneratedContent.created_at.desc()).limit(50).all()
    return [
        {
            "id": i.id,
            "content_type": i.content_type,
            "topic": i.topic,
            "language": i.language,
            "tone": i.tone,
            "with_hashtags": i.with_hashtags,
            "length_hint": i.length_hint,
            "content": i.content,
            "created_at": i.created_at.strftime("%Y-%m-%d %H:%M"),
        } for i in items
    ]


@app.delete("/admin/api/content-gen/history/{item_id}")
def content_gen_delete_history(request: Request, item_id: int, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    db.query(models.GeneratedContent).filter(models.GeneratedContent.id == item_id).delete()
    db.commit()
    return {"ok": True}


# ============================================================
# MARKET ANALYSIS — API routes
# ============================================================
from app.market_parser import parse_upload, fetch_url as market_fetch_url


@app.get("/admin/api/market/channels")
def market_channels(request: Request, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    channels = db.query(models.MarketChannel).all()
    result = []
    for ch in channels:
        latest = (
            db.query(models.MarketDataSnapshot)
            .filter(models.MarketDataSnapshot.channel_id == ch.id)
            .order_by(models.MarketDataSnapshot.created_at.desc())
            .first()
        )
        snap_count = db.query(models.MarketDataSnapshot).filter(
            models.MarketDataSnapshot.channel_id == ch.id
        ).count()
        result.append({
            "id": ch.id,
            "slug": ch.slug,
            "name": ch.name,
            "icon": ch.icon,
            "color": ch.color,
            "snap_count": snap_count,
            "latest_summary": latest.summary if latest else "",
            "latest_at": latest.created_at.strftime("%Y-%m-%d %H:%M") if latest else "",
        })
    return result


@app.get("/admin/api/market/{slug}")
def market_channel_detail(request: Request, slug: str, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    ch = db.query(models.MarketChannel).filter(models.MarketChannel.slug == slug).first()
    if not ch:
        return {"error": "channel not found"}
    snapshots = (
        db.query(models.MarketDataSnapshot)
        .filter(models.MarketDataSnapshot.channel_id == ch.id)
        .order_by(models.MarketDataSnapshot.created_at.desc())
        .all()
    )
    snaps_data = []
    for s in snapshots:
        snaps_data.append({
            "id": s.id,
            "source_type": s.source_type,
            "source_ref": s.source_ref,
            "row_count": s.row_count,
            "summary": s.summary,
            "created_at": s.created_at.strftime("%Y-%m-%d %H:%M"),
            "columns": json.loads(s.columns_json or "[]"),
            "rows": json.loads(s.rows_json or "[]"),
        })
    return {
        "channel": {"id": ch.id, "slug": ch.slug, "name": ch.name, "icon": ch.icon, "color": ch.color},
        "snapshots": snaps_data,
    }


@app.post("/admin/api/market/{slug}/upload")
async def market_upload(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
    file: UploadFile | None = File(default=None),
    url: str = Form(default=""),
):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    ch = db.query(models.MarketChannel).filter(models.MarketChannel.slug == slug).first()
    if not ch:
        return {"error": "channel not found"}

    parsed = None
    source_type = ""
    source_ref = ""

    if file and file.filename:
        raw = await file.read()
        parsed = parse_upload(file.filename, raw)
        source_type = "file"
        source_ref = file.filename
    elif url.strip():
        parsed = market_fetch_url(url.strip())
        source_type = "url"
        source_ref = url.strip()
    else:
        return {"error": "يرجى إرفاق ملف أو رابط."}

    snap = models.MarketDataSnapshot(
        channel_id=ch.id,
        source_type=source_type,
        source_ref=source_ref,
        columns_json=json.dumps(parsed.get("columns", []), ensure_ascii=False),
        rows_json=json.dumps(parsed.get("rows", [])[:500], ensure_ascii=False),
        summary=parsed.get("summary", ""),
        row_count=parsed.get("row_count", 0),
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)

    return {
        "id": snap.id,
        "source_type": source_type,
        "source_ref": source_ref,
        "row_count": snap.row_count,
        "summary": snap.summary,
        "created_at": snap.created_at.strftime("%Y-%m-%d %H:%M"),
        "columns": json.loads(snap.columns_json),
        "rows": json.loads(snap.rows_json),
    }


@app.delete("/admin/api/market/snapshot/{snap_id}")
def market_delete_snapshot(request: Request, snap_id: int, db: Session = Depends(get_db)):
    admin = require_admin(request, db)
    if not admin:
        return {"error": "unauthorized"}
    snap = db.query(models.MarketDataSnapshot).filter(models.MarketDataSnapshot.id == snap_id).first()
    if snap:
        db.delete(snap)
        db.commit()
    return {"ok": True}


# ---------------------------
# Health Check (لـ Render)
# ---------------------------
@app.get("/health")
def health():
    return {"status": "ok"}
