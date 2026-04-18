import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app import models


@dataclass
class RetrievalDocument:
    title: str
    content: str
    url: str
    source_type: str
    metadata: dict[str, Any]


STOP_WORDS = {
    "في", "من", "عن", "على", "الى", "إلى", "هل", "ما", "هو", "هي", "كيف", "انا",
    "أريد", "اريد", "ابغى", "عايز", "هذا", "هذه", "مع", "لي", "لدي", "عندي",
    "the", "a", "an", "and", "or", "to", "for", "with", "is", "are", "i", "want",
}


DEFAULT_KNOWLEDGE = [
    {
        "title": "مساعدة التسوق",
        "content": "يمكن للوكيل اقتراح المنتجات، فتح صفحة المنتج، توجيه المستخدم إلى السلة، الدفع، الطلبات، الحساب، وإضافة المنتجات.",
        "tags": "shopping navigation cart checkout orders profile",
    },
    {
        "title": "رحلة الشراء",
        "content": "رحلة الشراء تبدأ باختيار منتج مناسب، ثم مراجعة السلة، ثم الانتقال إلى صفحة الدفع لإكمال الطلب.",
        "tags": "checkout cart order purchase",
    },
    {
        "title": "الدعم داخل المتجر",
        "content": "إذا سأل المستخدم عن الطلبات أو الحساب أو الدعم، يمكن توجيهه إلى صفحة الطلبات أو الحساب أو الصفحة الرئيسية.",
        "tags": "support account profile orders",
    },
]


def ensure_default_knowledge(db: Session) -> None:
    if db.query(models.KnowledgeItem).count() > 0:
        return
    db.add_all([models.KnowledgeItem(**item) for item in DEFAULT_KNOWLEDGE])
    db.commit()


def build_retrieval_documents(db: Session) -> list[RetrievalDocument]:
    products = db.query(models.Product).filter(models.Product.is_active == True).all()
    knowledge_items = db.query(models.KnowledgeItem).filter(models.KnowledgeItem.is_active == True).all()

    documents: list[RetrievalDocument] = []
    for product in products:
        documents.append(
            RetrievalDocument(
                title=product.name,
                content=f"{product.name}. {product.description or ''}. السعر {product.price}. التصنيف {product.category or ''}.",
                url=f"/product/{product.id}",
                source_type="product",
                metadata={
                    "id": product.id,
                    "price": product.price,
                    "old_price": product.old_price,
                    "category": product.category,
                    "image_url": product.image_url,
                },
            )
        )

    for item in knowledge_items:
        documents.append(
            RetrievalDocument(
                title=item.title,
                content=f"{item.title}. {item.content}. {item.tags or ''}",
                url="",
                source_type="knowledge",
                metadata={"id": item.id, "tags": item.tags},
            )
        )

    return documents


def tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[\w\u0600-\u06FF]+", text.lower())
    return {token for token in tokens if len(token) > 1 and token not in STOP_WORDS}


def retrieve_context(message: str, documents: list[RetrievalDocument], limit: int = 4) -> list[RetrievalDocument]:
    query_tokens = tokenize(message)
    if not query_tokens:
        return documents[:limit]

    scored: list[tuple[int, RetrievalDocument]] = []
    for document in documents:
        haystack = f"{document.title} {document.content}".lower()
        document_tokens = tokenize(haystack)
        score = len(query_tokens & document_tokens)
        for token in query_tokens:
            if token in haystack:
                score += 1
        if score > 0:
            scored.append((score, document))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [document for _, document in scored[:limit]]


def detect_intent(message: str) -> str:
    text = message.lower()
    if any(word in text for word in ["سلة", "cart", "عربة"]):
        return "cart"
    if any(word in text for word in ["دفع", "checkout", "شراء", "اكمال", "إكمال"]):
        return "checkout"
    if any(word in text for word in ["طلب", "طلباتي", "orders", "تتبع"]):
        return "orders"
    if any(word in text for word in ["حساب", "profile", "بياناتي"]):
        return "profile"
    if any(word in text for word in ["اضافة", "إضافة", "منتج جديد", "add product"]):
        return "add_product"
    if any(word in text for word in ["منتج", "اقترح", "رشح", "أفضل", "افضل", "سعر", "product"]):
        return "product_search"
    if any(word in text for word in ["مساعدة", "help", "تقدر", "ماذا"]):
        return "capabilities"
    return "general"


def action(label: str, url: str) -> dict[str, str]:
    return {"label": label, "url": url}


def build_agent_response(message: str, db: Session) -> dict[str, Any]:
    documents = build_retrieval_documents(db)
    matches = retrieve_context(message, documents)
    products = [document for document in matches if document.source_type == "product"]
    intent = detect_intent(message)

    actions = [action("تصفح المتجر", "/")]
    suggestions = ["اقترح لي منتجاً مناسباً", "افتح السلة", "كيف أكمل الطلب؟"]

    if intent == "cart":
        reply = "يمكنني توجيهك مباشرة إلى السلة لمراجعة المنتجات قبل الدفع."
        actions = [action("فتح السلة", "/cart"), action("إكمال الدفع", "/checkout")]
    elif intent == "checkout":
        reply = "لإكمال الشراء، انتقل إلى صفحة الدفع بعد مراجعة السلة. إذا كنت تريد، أستطيع أيضاً اقتراح منتج قبل الدفع."
        actions = [action("فتح صفحة الدفع", "/checkout"), action("مراجعة السلة", "/cart")]
    elif intent == "orders":
        reply = "يمكنك متابعة طلباتك من صفحة الطلبات. لاحقاً يمكن ربط الوكيل بحالة الطلب الفعلية من قاعدة البيانات."
        actions = [action("عرض الطلبات", "/orders"), action("حسابي", "/profile")]
    elif intent == "profile":
        reply = "يمكنك إدارة بياناتك من صفحة الحساب، مثل الاسم والبريد ورقم الهاتف."
        actions = [action("فتح حسابي", "/profile"), action("عرض الطلبات", "/orders")]
    elif intent == "add_product":
        reply = "يمكنك إضافة منتج جديد من صفحة إضافة المنتجات. هذه نقطة مناسبة لاحقاً لربط إدارة المنتجات بالوكيل."
        actions = [action("إضافة منتج", "/add-product")]
    elif intent == "capabilities":
        reply = "أستطيع مساعدتك في البحث عن المنتجات، اقتراح خيارات حسب السعر أو التصنيف، فتح السلة، الدفع، الطلبات، الحساب، وتوجيهك داخل المتجر عبر الدردشة."
        actions = [
            action("المنتجات", "/"),
            action("السلة", "/cart"),
            action("الدفع", "/checkout"),
            action("حسابي", "/profile"),
        ]
    elif intent == "product_search" or products:
        if not products:
            products = [document for document in documents if document.source_type == "product"][:3]
        product_lines = []
        actions = []
        for product in products[:3]:
            price = product.metadata.get("price")
            category = product.metadata.get("category") or "عام"
            product_lines.append(f"- {product.title}: بسعر ${price} ضمن تصنيف {category}.")
            actions.append(action(f"عرض {product.title}", product.url))
        actions.append(action("فتح السلة", "/cart"))
        reply = "وجدت لك هذه الخيارات المناسبة:\n" + "\n".join(product_lines)
    else:
        context = matches[0].content if matches else ""
        reply = f"أنا وكيل التسوق داخل المتجر. {context} أخبرني بما تبحث عنه، السعر المناسب، أو القسم الذي تفضله وسأوجهك."
        actions = [
            action("تصفح المنتجات", "/"),
            action("السلة", "/cart"),
            action("الدفع", "/checkout"),
        ]

    return {
        "reply": reply,
        "intent": intent,
        "matches": [
            {
                "title": document.title,
                "source_type": document.source_type,
                "url": document.url,
                "metadata": document.metadata,
            }
            for document in matches
        ],
        "actions": actions,
        "suggestions": suggestions,
    }