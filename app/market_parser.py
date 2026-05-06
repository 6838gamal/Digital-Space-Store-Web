"""
Market data parser: CSV, XLSX, JSON, TXT, PDF, and URL.
Returns a normalized dict: { columns: [...], rows: [[...]], summary: "..." }
"""
import csv
import io
import json
import re
import urllib.request
from typing import Any


MAX_ROWS = 500


def _normalize(columns: list[str], rows: list[list[Any]]) -> dict:
    rows = rows[:MAX_ROWS]
    summary = _auto_summary(columns, rows)
    return {"columns": columns, "rows": rows, "row_count": len(rows), "summary": summary}


def _auto_summary(columns: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "لا توجد بيانات."
    parts = [f"عدد الصفوف: {len(rows)}، عدد الأعمدة: {len(columns)}"]
    parts.append(f"الأعمدة: {', '.join(str(c) for c in columns[:8])}")
    for i, col in enumerate(columns[:6]):
        vals = []
        for row in rows:
            if i < len(row) and row[i] is not None and str(row[i]).strip():
                try:
                    vals.append(float(str(row[i]).replace(",", "")))
                except ValueError:
                    pass
        if len(vals) >= 2:
            parts.append(f"{col}: min={min(vals):.1f}، max={max(vals):.1f}، avg={sum(vals)/len(vals):.1f}")
    return " | ".join(parts)


def parse_csv(data: bytes, encoding: str = "utf-8-sig") -> dict:
    try:
        text = data.decode(encoding)
    except Exception:
        text = data.decode("latin-1", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows_raw = list(reader)
    if not rows_raw:
        return _normalize([], [])
    columns = [str(c).strip() for c in rows_raw[0]]
    rows = [[str(cell).strip() for cell in r] for r in rows_raw[1:] if any(c.strip() for c in r)]
    return _normalize(columns, rows)


def parse_xlsx(data: bytes) -> dict:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.active
        all_rows = []
        for row in ws.iter_rows(values_only=True):
            all_rows.append([str(c).strip() if c is not None else "" for c in row])
        wb.close()
        if not all_rows:
            return _normalize([], [])
        columns = all_rows[0]
        rows = [r for r in all_rows[1:] if any(c for c in r)]
        return _normalize(columns, rows)
    except Exception as e:
        return {"columns": [], "rows": [], "row_count": 0, "summary": f"خطأ في قراءة XLSX: {e}"}


def parse_json(data: bytes) -> dict:
    try:
        text = data.decode("utf-8", errors="replace")
        obj = json.loads(text)
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            columns = list(obj[0].keys())
            rows = [[str(row.get(c, "")) for c in columns] for row in obj]
            return _normalize(columns, rows)
        if isinstance(obj, dict):
            columns = list(obj.keys())
            rows = [[str(obj[c]) for c in columns]]
            return _normalize(columns, rows)
        return {"columns": ["value"], "rows": [[str(obj)]], "row_count": 1, "summary": "بيانات JSON مفردة."}
    except Exception as e:
        return {"columns": [], "rows": [], "row_count": 0, "summary": f"خطأ في JSON: {e}"}


def parse_txt(data: bytes) -> dict:
    try:
        text = data.decode("utf-8", errors="replace")
        lines = [l.rstrip() for l in text.splitlines() if l.strip()]
        if not lines:
            return _normalize([], [])
        sample = lines[0]
        sep = None
        for s in ["\t", ";", "|", ","]:
            if s in sample:
                sep = s
                break
        if sep:
            reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=sep)
            raw = list(reader)
            if raw:
                columns = [c.strip() for c in raw[0]]
                rows = [[c.strip() for c in r] for r in raw[1:] if any(c.strip() for c in r)]
                return _normalize(columns, rows)
        kv_pairs = []
        for line in lines:
            m = re.match(r"^(.+?)[:=]\s*(.+)$", line)
            if m:
                kv_pairs.append([m.group(1).strip(), m.group(2).strip()])
        if kv_pairs:
            return _normalize(["المفتاح", "القيمة"], kv_pairs)
        rows = [[line] for line in lines]
        return _normalize(["النص"], rows)
    except Exception as e:
        return {"columns": [], "rows": [], "row_count": 0, "summary": f"خطأ في TXT: {e}"}


def parse_pdf(data: bytes) -> dict:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        text_parts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
        full_text = "\n".join(text_parts)
        return parse_txt(full_text.encode("utf-8"))
    except Exception as e:
        return {"columns": [], "rows": [], "row_count": 0, "summary": f"خطأ في PDF: {e}"}


def fetch_url(url: str) -> dict:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read(2 * 1024 * 1024)
            content_type = resp.headers.get("Content-Type", "")
        if "json" in content_type:
            return parse_json(data)
        if "csv" in content_type or url.lower().endswith(".csv"):
            return parse_csv(data)
        text = data.decode("utf-8", errors="replace")
        lines = [l.strip() for l in text.splitlines() if l.strip()][:200]
        return _normalize(["المحتوى"], [[l] for l in lines])
    except Exception as e:
        return {"columns": [], "rows": [], "row_count": 0, "summary": f"خطأ في جلب الرابط: {e}"}


def parse_upload(filename: str, data: bytes) -> dict:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return parse_csv(data)
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return parse_xlsx(data)
    if lower.endswith(".json"):
        return parse_json(data)
    if lower.endswith(".pdf"):
        return parse_pdf(data)
    return parse_txt(data)
