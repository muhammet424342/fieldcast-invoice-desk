"""Validation rules. Each returns dict(rule, passed, message)."""
from datetime import date

from . import config

REQUIRED = ["invoice_number", "invoice_date", "seller", "total"]


def _r(rule, passed, message):
    return {"rule": rule, "passed": bool(passed), "message": message}


def check(fields, existing_numbers=(), today=None, tolerance=None, threshold=None):
    tol = config.TOLERANCE if tolerance is None else tolerance
    thr = config.AMOUNT_THRESHOLD if threshold is None else threshold
    today = today or date.today()
    res = []

    missing = [f for f in REQUIRED if fields.get(f) in (None, "")]
    res.append(_r("required_fields", not missing,
                  "All required fields present." if not missing else f"Missing required field(s): {', '.join(missing)}."))

    items = fields.get("line_items") or []
    sub = fields.get("subtotal")
    if items and sub is not None:
        s = round(sum(float(i.get("amount") or 0) for i in items), 2)
        ok = abs(s - float(sub)) <= tol
        res.append(_r("line_items_sum", ok, f"Line items sum {s:.2f} {'matches' if ok else 'does NOT match'} subtotal {float(sub):.2f} (tolerance {tol})."))
    else:
        res.append(_r("line_items_sum", False, "Cannot check: line items or subtotal missing."))

    tax, total = fields.get("tax"), fields.get("total")
    if sub is not None and total is not None:
        exp = round(float(sub) + float(tax or 0), 2)
        ok = abs(exp - float(total)) <= tol
        res.append(_r("subtotal_plus_tax", ok, f"Subtotal + tax = {exp:.2f}; total is {float(total):.2f} → {'OK' if ok else 'MISMATCH of %.2f' % (float(total) - exp)}."))
    else:
        res.append(_r("subtotal_plus_tax", False, "Cannot check: subtotal or total missing."))

    num = fields.get("invoice_number")
    dup = bool(num) and num in set(existing_numbers)
    res.append(_r("duplicate_number", not dup, f"Invoice number {num} already exists in the desk." if dup else "Invoice number not seen before."))

    d = fields.get("invoice_date")
    try:
        dd = date.fromisoformat(d) if d else None
    except (TypeError, ValueError):
        dd = None
    if dd is None:
        res.append(_r("valid_date", False, f"Invoice date missing or unparseable ({fields.get('invoice_date_raw') or d})."))
    elif dd > today:
        res.append(_r("valid_date", False, f"Invoice date {dd} is in the future."))
    else:
        res.append(_r("valid_date", True, f"Invoice date {dd} is valid."))

    big = total is not None and float(total) > thr
    res.append(_r("amount_threshold", not big, f"Total {total} exceeds review threshold {thr}." if big else f"Total below review threshold {thr}."))
    return res
