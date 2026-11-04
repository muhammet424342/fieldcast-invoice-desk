"""Invoice field extraction: pdfplumber text -> rule-based parser; optional OCR and LLM."""
import json
import re
from datetime import datetime

import pdfplumber

from . import config

FIELDS = ["invoice_number", "invoice_date", "seller", "buyer", "currency",
          "subtotal", "tax", "total", "line_items"]

MONEY = r"[-]?[$€£₺]?\s?\d[\d,]*\.\d{2}"


def to_amount(s):
    if s is None:
        return None
    s = re.sub(r"[^\d.\-]", "", str(s))
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def pdf_text(path):
    """Text layer via pdfplumber; OCR fallback (pytesseract) if almost empty and available."""
    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    method = "pdfplumber"
    if len(text.strip()) < 20:
        try:
            import pytesseract  # optional
            with pdfplumber.open(path) as pdf:
                text = "\n".join(pytesseract.image_to_string(p.to_image(resolution=300).original)
                                 for p in pdf.pages)
            method = "ocr"
        except Exception:
            method = "none"
    return text, method


def _find(pattern, text, flags=re.I | re.M):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def rule_based(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = {k: None for k in FIELDS}
    out["invoice_number"] = _find(r"Invoice (?:Number|No\.?|#)\s*:?\s*([A-Z0-9][\w\-/]*)", text)
    raw_date = _find(r"Invoice Date\s*:?\s*([A-Za-z]+ \d{1,2}, \d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}[./]\d{1,2}[./]\d{4})", text)
    out["invoice_date_raw"] = raw_date
    out["invoice_date"] = parse_date(raw_date)
    # seller: first line after "From:"; buyer: first line after "To:" / "Bill To:"
    for key, label in (("seller", r"^From:?$"), ("buyer", r"^(?:Bill )?To:?$")):
        for i, l in enumerate(lines):
            if re.match(label, l, re.I) and i + 1 < len(lines):
                val = re.split(r"\s+(?:Order Number|Invoice Date|Due Date)\b", lines[i + 1])[0]
                out[key] = val.strip()
                break
    if "$" in text:
        out["currency"] = "USD"
    elif "€" in text or "EUR" in text:
        out["currency"] = "EUR"
    elif "₺" in text or " TRY" in text:
        out["currency"] = "TRY"
    out["subtotal"] = to_amount(_find(r"^Sub\s?Total\s*:?\s*(" + MONEY + r")\s*$", text))
    out["tax"] = to_amount(_find(r"^(?:Tax|VAT|KDV)\b.*?(" + MONEY + r")\s*$", text))
    out["total"] = to_amount(_find(r"^Total\s*:?\s*(" + MONEY + r")\s*$", text))
    # line items: "<qty> ... <amount>" ; description is the line itself or the line above
    items = []
    for i, l in enumerate(lines):
        m = re.match(r"^(\d+(?:\.\d+)?)\s+(.*?)\s*(" + MONEY + r")$", l)
        if not m or re.match(r"^(Sub|Total|Tax)", l, re.I):
            continue
        middle = m.group(2)
        nums = re.findall(MONEY, middle)
        desc = re.sub(MONEY + r"|\d+\.\d+%", "", middle).strip()
        if not re.search(r"[A-Za-z]", desc) and i > 0:
            desc = lines[i - 1]
        items.append({"qty": float(m.group(1)), "description": desc,
                      "unit_price": to_amount(nums[0]) if nums else None,
                      "amount": to_amount(m.group(3))})
    out["line_items"] = items
    return out


def llm_extract(text):
    """Optional: OpenAI-compatible endpoint configured only via .env. Returns dict or None."""
    if not (config.LLM_BASE_URL and config.LLM_API_KEY and config.LLM_MODEL):
        return None
    import requests
    prompt = ("Extract these invoice fields as JSON: " + ", ".join(FIELDS) +
              ". line_items = list of {qty, description, unit_price, amount}. "
              "Dates as YYYY-MM-DD. Amounts as numbers. Use null if absent; never invent.\n\n" + text[:15000])
    r = requests.post(config.LLM_BASE_URL.rstrip("/") + "/chat/completions",
                      headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
                      json={"model": config.LLM_MODEL, "temperature": 0,
                            "messages": [{"role": "user", "content": prompt}]}, timeout=60)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    content = content[content.find("{"): content.rfind("}") + 1]
    return json.loads(content)


def extract(path):
    text, method = pdf_text(path)
    fields = rule_based(text)
    engine = "rules"
    try:
        llm = llm_extract(text)
    except Exception as e:  # fall back silently to rules, record the reason
        llm, engine = None, f"rules (llm error: {type(e).__name__})"
    if llm:
        for k in FIELDS:
            if llm.get(k) not in (None, "", []):
                fields[k] = llm[k]
        engine = "llm+rules"
    return {"fields": fields, "text_method": method, "engine": engine, "text": text}
