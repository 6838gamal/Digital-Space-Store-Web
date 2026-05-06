"""
Content Generation Engine — RAG + Gemini (or rule-based fallback).
Supports article, social post, and tweet generation from training data.
"""
import re
import os
from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

# ── Arabic & English stopwords ──
_STOP_AR = {
    'في','من','إلى','على','عن','مع','هذا','هذه','التي','الذي','وهو','وهي',
    'أن','إن','كان','كانت','قد','لا','ولا','هو','هي','أو','أي','أم','لم',
    'لن','ما','لكن','ثم','لقد','عند','بعد','قبل','حتى','كل','بين','أيضا',
    'وأن','وكان','هذا','ذلك','تلك','هؤلاء','عليه','عليها','منه','منها',
    'له','لها','لهم','وهذا','وهذه','كما','إذا','وإذا','وقد','وكان','وكانت',
    'وكانوا','وهم','وهن','حين','حيث','يكون','تكون','يكن','وفي','وعلى',
    'وعن','ومن','وإلى','وهو','أو','ومع','عبر','خلال','حول','نحو',
    'بين','ضد','رغم','نفس','ذات','كلا','بعض','غير','لدى','دون',
}
_STOP_EN = {
    'the','a','an','and','or','but','in','on','at','to','for','of','with','by',
    'from','is','was','are','were','be','been','have','has','had','do','does',
    'did','will','would','could','should','may','might','can','this','that',
    'these','those','it','its','not','no','so','if','as','what','which','who',
    'how','when','where','there','their','they','we','our','you','your','my','me',
    'him','her','his','she','he','i','am','been','being','into','about','than',
    'then','only','very','also','just','each','both','few','more','most','other',
    'some','such','up','out','over','under','again','further','once','same',
}
_STOPWORDS = _STOP_AR | _STOP_EN


def extract_keywords(text: str, top_n: int = 40) -> list[str]:
    words = re.findall(r'\b[\u0600-\u06FFa-zA-Z]{3,}\b', text)
    words = [w.lower() for w in words if w.lower() not in _STOPWORDS]
    counter = Counter(words)
    return [w for w, _ in counter.most_common(top_n)]


def chunk_text(text: str, chunk_size: int = 350) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r'\n{2,}|\n', text) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in paragraphs:
        words = para.split()
        if current_len + len(words) > chunk_size and current:
            chunks.append(' '.join(current))
            current = []
            current_len = 0
        current.extend(words)
        current_len += len(words)
    if current:
        chunks.append(' '.join(current))
    return chunks or [text[:3000]]


def keyword_score(query_keywords: set[str], chunk_keywords: str) -> int:
    chunk_set = set(chunk_keywords.split(','))
    return len(query_keywords & chunk_set)


def retrieve_chunks(topic: str, db: Session, top_k: int = 6) -> list[str]:
    from app import models
    query_kw = set(extract_keywords(topic, 30))
    all_chunks = db.query(models.ContentChunk).all()
    if not all_chunks:
        return []
    scored = [(keyword_score(query_kw, c.keywords), c.text) for c in all_chunks]
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [text for score, text in scored[:top_k] if score >= 0]
    if not top:
        top = [c.text for c in all_chunks[:top_k]]
    return top


def _length_words(length_hint: str, content_type: str) -> int:
    base = {'article': {'short': 200, 'medium': 450, 'long': 800},
            'post':    {'short': 60,  'medium': 120, 'long': 220},
            'tweet':   {'short': 40,  'medium': 60,  'long': 80}}
    return base.get(content_type, base['post']).get(length_hint, 150)


def generate_with_gemini(
    topic: str, content_type: str, language: str,
    tone: str, with_hashtags: bool, length_hint: str,
    context_chunks: list[str], api_key: str,
) -> str:
    from google import genai
    from google.genai import types

    type_labels = {
        'article': 'مقالة تفصيلية' if language == 'ar' else 'detailed article',
        'post':    'منشور لوسائل التواصل الاجتماعي' if language == 'ar' else 'social media post',
        'tweet':   'تغريدة (أقل من 280 حرف)' if language == 'ar' else 'tweet (under 280 characters)',
    }
    tone_labels_ar = {'professional': 'احترافي ورسمي', 'friendly': 'ودود وغير رسمي', 'inspiring': 'ملهم وتحفيزي'}
    tone_labels_en = {'professional': 'professional and formal', 'friendly': 'friendly and informal', 'inspiring': 'inspiring and motivational'}
    tone_label = tone_labels_ar.get(tone, 'احترافي') if language == 'ar' else tone_labels_en.get(tone, 'professional')
    word_target = _length_words(length_hint, content_type)

    context = '\n\n---\n\n'.join(context_chunks[:5]) if context_chunks else ''
    hashtag_line = ('أضف هاشتاغات مناسبة (5-8 هاشتاغ) في سطر منفصل في نهاية المحتوى.'
                    if (with_hashtags and language == 'ar')
                    else ('Add relevant hashtags (5-8) on a separate line at the end.'
                          if with_hashtags else ''))

    if language == 'ar':
        prompt = f"""أنت كاتب محتوى رقمي محترف. استلهم أسلوبك ومعلوماتك من النص المرجعي التالي.

النص المرجعي:
{context[:4000]}

المطلوب: اكتب {type_labels.get(content_type, 'منشور')} باللغة العربية عن: "{topic}"
- الأسلوب: {tone_label}
- الطول التقريبي: {word_target} كلمة
{hashtag_line}

اكتب المحتوى مباشرة بدون أي مقدمة أو شرح أو ملاحظة."""
    else:
        prompt = f"""You are a professional digital content writer. Draw your style and knowledge from the reference text below.

Reference text:
{context[:4000]}

Write a {type_labels.get(content_type, 'post')} in English about: "{topic}"
- Tone: {tone_label}
- Approximate length: {word_target} words
{hashtag_line}

Write the content directly without any introduction, explanation, or notes."""

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
        config=types.GenerateContentConfig(max_output_tokens=1800, temperature=0.85),
    )
    return (response.text or '').strip()


def generate_fallback(
    topic: str, content_type: str, language: str,
    tone: str, with_hashtags: bool, length_hint: str,
    context_chunks: list[str],
) -> str:
    all_text = ' '.join(context_chunks)
    kw_list = extract_keywords(all_text + ' ' + topic, 20)
    topic_kw = extract_keywords(topic, 10)

    sentences: list[str] = []
    for chunk in context_chunks[:4]:
        sents = re.split(r'[.!?؟،\n]+', chunk)
        for s in sents:
            s = s.strip()
            if 15 < len(s) < 300:
                sentences.append(s)

    unique_sents = list(dict.fromkeys(sentences))[:12]

    if language == 'ar':
        if content_type == 'tweet':
            body = f"#{topic.replace(' ','_')} | " if with_hashtags else ''
            body += unique_sents[0] if unique_sents else f"محتوى متعلق بـ {topic}."
            if with_hashtags:
                tags = ' '.join(f'#{w}' for w in kw_list[:6])
                body += f"\n\n{tags}"
            return body[:280]

        if content_type == 'post':
            intro = f"📌 {topic}\n\n"
            paras = unique_sents[:4]
            body = '\n\n'.join(paras) if paras else f"اكتشف كل ما يتعلق بـ {topic}."
            hashtags = '\n\n' + ' '.join(f'#{w}' for w in kw_list[:8]) if with_hashtags else ''
            return intro + body + hashtags

        # article
        title = f"## {topic}\n\n"
        intro = unique_sents[0] if unique_sents else f"يتناول هذا المقال موضوع {topic}."
        sections = ''
        for i, sent in enumerate(unique_sents[1:7], 1):
            sections += f"\n\n**{i}.** {sent}"
        conclusion = f"\n\n---\n\n*خلاصة القول:* {unique_sents[-1]}." if len(unique_sents) > 2 else ''
        hashtags = '\n\n' + ' '.join(f'#{w}' for w in kw_list[:8]) if with_hashtags else ''
        return title + intro + sections + conclusion + hashtags
    else:
        if content_type == 'tweet':
            body = unique_sents[0] if unique_sents else f"Content about {topic}."
            if with_hashtags:
                tags = ' '.join(f'#{w}' for w in kw_list[:5])
                body += f"\n\n{tags}"
            return body[:280]

        if content_type == 'post':
            intro = f"📌 {topic}\n\n"
            body = '\n\n'.join(unique_sents[:4]) if unique_sents else f"Discover everything about {topic}."
            hashtags = '\n\n' + ' '.join(f'#{w}' for w in kw_list[:8]) if with_hashtags else ''
            return intro + body + hashtags

        title = f"## {topic}\n\n"
        intro = unique_sents[0] if unique_sents else f"This article covers {topic}."
        sections = ''
        for i, sent in enumerate(unique_sents[1:7], 1):
            sections += f"\n\n**{i}.** {sent}"
        conclusion = f"\n\n---\n\n*In summary:* {unique_sents[-1]}." if len(unique_sents) > 2 else ''
        hashtags = '\n\n' + ' '.join(f'#{w}' for w in kw_list[:8]) if with_hashtags else ''
        return title + intro + sections + conclusion + hashtags


def generate_content(
    topic: str,
    content_type: str,
    language: str,
    tone: str,
    with_hashtags: bool,
    length_hint: str,
    db: Session,
) -> str:
    context_chunks = retrieve_chunks(topic, db, top_k=6)
    api_key = os.getenv('GEMINI_API_KEY', '')
    if api_key:
        try:
            return generate_with_gemini(topic, content_type, language, tone, with_hashtags, length_hint, context_chunks, api_key)
        except Exception as e:
            print(f"Gemini content-gen error: {e}")
    return generate_fallback(topic, content_type, language, tone, with_hashtags, length_hint, context_chunks)
