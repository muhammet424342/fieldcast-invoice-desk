"""Generate two synthetic test invoices (fictional companies) into samples/.
acme-invoice-1001.pdf  -> consistent totals
acme-invoice-1002-bad-total.pdf -> total deliberately wrong (should land in review)"""
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def make(path, number, date, items, tax_rate, total_override=None):
    c = canvas.Canvas(path, pagesize=A4)
    y = 800
    def line(t, x=50):
        nonlocal y
        c.drawString(x, y, t); y -= 18
    c.setFont("Helvetica-Bold", 16); line("INVOICE"); c.setFont("Helvetica", 11)
    line(f"Invoice Number {number}"); line(f"Invoice Date {date}"); y -= 6
    line("From:"); line("Acme Example Supplies Ltd (fictional)"); y -= 6
    line("To:"); line("Sample Customer GmbH (fictional)"); y -= 10
    line("Qty Description Unit Amount")
    sub = 0
    for q, d, p in items:
        amt = round(q * p, 2); sub += amt
        line(f"{q} {d} ${p:,.2f} ${amt:,.2f}")
    sub = round(sub, 2); tax = round(sub * tax_rate, 2)
    total = total_override if total_override is not None else round(sub + tax, 2)
    y -= 10
    line(f"Sub Total ${sub:,.2f}"); line(f"Tax {int(tax_rate*100)}% ${tax:,.2f}"); line(f"Total ${total:,.2f}")
    c.save()


if __name__ == "__main__":
    items = [(2, "Printer paper A4 box", 24.50), (1, "Toner cartridge", 89.90), (5, "Notebook", 3.20)]
    make("samples/acme-invoice-1001.pdf", "ACME-1001", "2026-10-15", items, 0.20)
    make("samples/acme-invoice-1002-bad-total.pdf", "ACME-1002", "2026-10-20", items, 0.20, total_override=250.00)
