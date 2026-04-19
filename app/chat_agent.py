import os
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


def retrieve_context(message: str, documents: list[RetrievalDocument], limit: int = 5) -> list[RetrievalDocument]:
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


def build_store_context(documents: list[RetrievalDocument]) -> str:
    lines = ["=== معلومات المتجر والمنتجات ==="]
    products = [d for d in documents if d.source_type == "product"]
    knowledge = [d for d in documents if d.source_type == "knowledge"]

    if products:
        lines.append("\nالمنتجات المتاحة:")
        for p in products:
            meta = p.metadata
            price = meta.get("price", "")
            old_price = meta.get("old_price", "")
            category = meta.get("category", "")
            line = f"- {p.title}: سعر ${price}"
            if old_price:
                line += f" (كان ${old_price})"
            if category:
                line += f" | تصنيف: {category}"
            line += f" | رابط: {p.url}"
            lines.append(line)

    if knowledge:
        lines.append("\nمعلومات المتجر:")
        for k in knowledge:
            lines.append(f"- {k.title}: {k.content}")

    lines.append("\nروابط مهمة: الرئيسية(/), السلة(/cart), الدفع(/checkout), طلباتي(/orders), حسابي(/profile)")
    return "\n".join(lines)


def build_gemini_reply(message: str, history: list[dict], store_context: str) -> str | None:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        system_instruction = f"""أنت وكيل تسوق ذكي لمتجر "Digital Space Store". مهمتك مساعدة العملاء في:
- اكتشاف المنتجات والمقارنة بينها
- الإجابة على أسئلة المتجر بدقة
- توجيه العميل إلى السلة والدفع والطلبات
- تقديم اقتراحات مناسبة حسب احتياجات العميل

{store_context}

قواعد مهمة:
- أجب دائماً بنفس لغة السؤال (عربي أو إنجليزي)
- كن ودوداً وموجزاً وعملياً
- إذا ذكرت منتجاً، اذكر سعره ورابطه
- لا تخترع منتجات غير موجودة في القائمة
- اذكر الروابط المناسبة دائماً (مثل /cart أو /checkout)
"""

        contents = []
        for h in history[-10:]:
            role = "user" if h.get("role") == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=h.get("content", ""))]))
        contents.append(types.Content(role="user", parts=[types.Part(text=message)]))

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=1024,
                temperature=0.7,
            ),
        )
        return response.text.strip()
    except Exception as e:
        print(f"Gemini error: {e}")
        return None


def build_agent_response(message: str, db: Session, history: list[dict] | None = None) -> dict[str, Any]:
    if history is None:
        history = []

    documents = build_retrieval_documents(db)
    matches = retrieve_context(message, documents)
    products = [document for document in matches if document.source_type == "product"]
    intent = detect_intent(message)

    store_context = build_store_context(documents)
    gemini_reply = build_gemini_reply(message, history, store_context)

    actions = [action("تصفح المتجر", "/")]

    if intent == "cart":
        actions = [action("فتح السلة", "/cart"), action("إكمال الدفع", "/checkout")]
    elif intent == "checkout":
        actions = [action("فتح صفحة الدفع", "/checkout"), action("مراجعة السلة", "/cart")]
    elif intent == "orders":
        actions = [action("عرض الطلبات", "/orders"), action("حسابي", "/profile")]
    elif intent == "profile":
        actions = [action("فتح حسابي", "/profile"), action("عرض الطلبات", "/orders")]
    elif intent == "add_product":
        actions = [action("إضافة منتج", "/add-product")]
    elif intent == "capabilities":
        actions = [
            action("المنتجات", "/"),
            action("السلة", "/cart"),
            action("الدفع", "/checkout"),
            action("حسابي", "/profile"),
        ]
    elif intent == "product_search" or products:
        all_products = [d for d in documents if d.source_type == "product"]
        shown = (products or all_products)[:3]
        actions = [action(f"عرض {p.title}", p.url) for p in shown]
        actions.append(action("فتح السلة", "/cart"))
    else:
        actions = [
            action("تصفح المنتجات", "/"),
            action("السلة", "/cart"),
            action("الدفع", "/checkout"),
        ]

    if gemini_reply:
        reply = gemini_reply
    else:
        if intent == "cart":
            reply = "يمكنني توجيهك مباشرة إلى السلة لمراجعة المنتجات قبل الدفع."
        elif intent == "checkout":
            reply = "لإكمال الشراء، انتقل إلى صفحة الدفع بعد مراجعة السلة."
        elif intent == "orders":
            reply = "يمكنك متابعة طلباتك من صفحة الطلبات."
        elif intent == "profile":
            reply = "يمكنك إدارة بياناتك من صفحة الحساب."
        elif intent == "capabilities":
            reply = "أستطيع مساعدتك في البحث عن المنتجات، اقتراح خيارات، فتح السلة، الدفع، الطلبات، والحساب."
        elif intent == "product_search" or products:
            shown = (products or [d for d in documents if d.source_type == "product"])[:3]
            lines = [f"- {p.title}: بسعر ${p.metadata.get('price')} ضمن تصنيف {p.metadata.get('category') or 'عام'}." for p in shown]
            reply = "وجدت لك هذه الخيارات:\n" + "\n".join(lines)
        else:
            ctx = matches[0].content if matches else ""
            reply = f"أنا وكيل التسوق. {ctx} أخبرني بما تبحث عنه."

    return {
        "reply": reply,
        "intent": intent,
        "matches": [
            {"title": d.title, "source_type": d.source_type, "url": d.url, "metadata": d.metadata}
            for d in matches
        ],
        "actions": actions,
        "suggestions": ["اقترح لي منتجاً", "افتح السلة", "كيف أكمل الطلب؟"],
    }
