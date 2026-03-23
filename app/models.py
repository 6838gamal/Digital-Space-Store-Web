from sqlalchemy import Column, Integer, String, Float, Text, Boolean, ForeignKey
from .database import Base

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
