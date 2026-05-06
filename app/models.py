from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Text, Boolean, ForeignKey, DateTime, JSON
from app.database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    old_price = Column(Float, nullable=True) # لسعر العروض في page-offer.html
    image_url = Column(String(500)) # رابط الصورة داخل مجلد static/assets
    category = Column(String(100))
    is_active = Column(Boolean, default=True)

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(255))
    customer_phone = Column(String(20)) # مهم جداً للربط مع Vonage لاحقاً
    total_amount = Column(Float)
    status = Column(String(50), default="Pending") # Pending, Completed, Cancelled

class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(String(500), default="")
    is_active = Column(Boolean, default=True)

class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    picture_url = Column(String(500), default="")
    provider = Column(String(50), default="google")
    role = Column(String(50), default="admin")
    created_at = Column(DateTime, default=datetime.utcnow)

class StoreParticipant(Base):
    __tablename__ = "store_participants"

    id = Column(Integer, primary_key=True, index=True)
    session_key = Column(String(255), nullable=False, unique=True, index=True)
    display_name = Column(String(255), default="زائر المتجر")
    email = Column(String(255), default="")
    photo_url = Column(String(500), default="")
    firebase_uid = Column(String(255), default="", index=True)
    provider = Column(String(50), default="")
    phone = Column(String(50), default="")
    locale = Column(String(20), default="")
    subscribed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(Integer, ForeignKey("store_participants.id"), nullable=False)
    title = Column(String(255), default="محادثة جديدة")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class ChatMessageRecord(Base):
    __tablename__ = "chat_message_records"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id"), nullable=False)
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class ParticipantInsight(Base):
    __tablename__ = "participant_insights"

    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(Integer, ForeignKey("store_participants.id"), unique=True, index=True)
    summary = Column(Text, default="")
    interested_products = Column(Text, default="")
    interested_categories = Column(Text, default="")
    intents_seen = Column(Text, default="")
    message_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ContentTrainingDoc(Base):
    __tablename__ = "content_training_docs"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(20), nullable=False)   # 'file' | 'url'
    source_ref = Column(String(1000), default="")
    title = Column(String(500), default="")
    chunk_count = Column(Integer, default=0)
    word_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class ContentChunk(Base):
    __tablename__ = "content_chunks"

    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(Integer, ForeignKey("content_training_docs.id"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    keywords = Column(Text, default="")   # comma-separated top words
    position = Column(Integer, default=0)


class GeneratedContent(Base):
    __tablename__ = "generated_contents"

    id = Column(Integer, primary_key=True, index=True)
    content_type = Column(String(50), nullable=False)   # 'article' | 'post' | 'tweet'
    topic = Column(String(500), default="")
    language = Column(String(10), default="ar")         # 'ar' | 'en'
    tone = Column(String(50), default="professional")   # 'professional' | 'friendly' | 'inspiring'
    with_hashtags = Column(Boolean, default=False)
    length_hint = Column(String(20), default="medium")  # 'short' | 'medium' | 'long'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PublishSchedule(Base):
    __tablename__ = "publish_schedules"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), default="")
    base_content = Column(Text, nullable=False)
    status = Column(String(30), default="draft")   # draft | scheduled | published | cancelled
    scheduled_at = Column(DateTime, nullable=True)
    notes = Column(Text, default="")
    source_id = Column(Integer, nullable=True)     # GeneratedContent.id if imported
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class PublishTarget(Base):
    __tablename__ = "publish_targets"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("publish_schedules.id"), nullable=False, index=True)
    channel_slug = Column(String(50), nullable=False)
    channel_name = Column(String(100), default="")
    channel_icon = Column(String(20), default="📢")
    channel_color = Column(String(20), default="#64748b")
    customized_text = Column(Text, default="")     # empty = use base_content
    with_hashtags = Column(Boolean, default=False)
    hashtags = Column(String(500), default="")
    status = Column(String(20), default="pending")  # pending | published | failed | skipped
    published_at = Column(DateTime, nullable=True)
    error_msg = Column(Text, default="")


MARKET_CHANNELS = [
    {"slug": "whatsapp",  "name": "واتساب",     "icon": "💬", "color": "#25D366"},
    {"slug": "telegram",  "name": "تيليغرام",   "icon": "✈️", "color": "#2AABEE"},
    {"slug": "instagram", "name": "إنستغرام",   "icon": "📸", "color": "#E1306C"},
    {"slug": "tiktok",    "name": "تيك توك",    "icon": "🎵", "color": "#010101"},
    {"slug": "facebook",  "name": "فيسبوك",     "icon": "👍", "color": "#1877F2"},
    {"slug": "twitter",   "name": "تويتر / X",  "icon": "🐦", "color": "#1DA1F2"},
    {"slug": "youtube",   "name": "يوتيوب",     "icon": "▶️", "color": "#FF0000"},
    {"slug": "snapchat",  "name": "سناب شات",   "icon": "👻", "color": "#FFFC00"},
]


class MarketChannel(Base):
    __tablename__ = "market_channels"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    icon = Column(String(20), default="📊")
    color = Column(String(20), default="#64748b")
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketDataSnapshot(Base):
    __tablename__ = "market_data_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("market_channels.id"), nullable=False, index=True)
    source_type = Column(String(20), nullable=False)   # 'file' | 'url'
    source_ref = Column(String(1000), default="")      # filename or URL
    columns_json = Column(Text, default="[]")          # JSON array of column names
    rows_json = Column(Text, default="[]")             # JSON array of row arrays (max 500)
    summary = Column(Text, default="")
    row_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
