import io

from openpyxl import Workbook
from openpyxl.styles import Font

COLS = ["id", "status", "invoice_number", "invoice_date", "seller", "buyer", "currency",
        "subtotal", "tax", "total", "failed_checks"]


def to_rows(invoices):
    rows = []
    for inv in invoices:
        f = inv["fields"]
        rows.append({"id": inv["id"], "status": inv["status"], **{k: f.get(k) for k in COLS[2:10]},
                     "failed_checks": ", ".join(c["rule"] for c in inv["checks"] if not c["passed"])})
    return rows


def xlsx(invoices):
    wb = Workbook()
    ws = wb.active
    ws.title = "Invoices"
    ws.append(COLS)
    for r in to_rows(invoices):
        ws.append([r[k] for k in COLS])
    li = wb.create_sheet("Line items")
    li.append(["invoice_id", "invoice_number", "qty", "description", "unit_price", "amount"])
    for inv in invoices:
        for it in inv["fields"].get("line_items") or []:
            li.append([inv["id"], inv["fields"].get("invoice_number"), it.get("qty"), it.get("description"),
                       it.get("unit_price"), it.get("amount")])
    for s in (ws, li):
        for c in s[1]:
            c.font = Font(bold=True)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
