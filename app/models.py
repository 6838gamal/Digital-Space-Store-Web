from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Text, Boolean, ForeignKey, DateTime
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
