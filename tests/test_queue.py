import io
from pathlib import Path

import pytest
from openpyxl import load_workbook

from invoice_desk import db, rules
from invoice_desk.app import create_app

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
OK = [{"rule": "x", "passed": True, "message": "ok"}]
BAD = [{"rule": "x", "passed": False, "message": "bad"}]


@pytest.fixture
def c(tmp_path):
    return db.connect(tmp_path / "t.db")


def test_auto_status(c):
    a = db.add(c, "a.pdf", {"invoice_number": "1"}, OK, "rules")
    b = db.add(c, "b.pdf", {"invoice_number": "2"}, BAD, "rules")
    assert db.get(c, a)["status"] == "approved" and db.get(c, b)["status"] == "in_review"


def test_approve_reject_and_audit(c):
    a = db.add(c, "a.pdf", {"invoice_number": "1"}, BAD, "rules")
    db.set_status(c, a, "approved", "ayse", "checked by phone")
    assert db.get(c, a)["status"] == "approved"
    actions = [x["action"] for x in db.audit(c, a)]
    assert actions == ["uploaded", "sent_to_review", "approved"]
    with pytest.raises(ValueError):  # already decided
        db.set_status(c, a, "rejected", "ayse", "x")
    b = db.add(c, "b.pdf", {"invoice_number": "2"}, BAD, "rules")
    with pytest.raises(ValueError):  # reason required
        db.set_status(c, b, "rejected", "ayse", "")
    db.set_status(c, b, "rejected", "ayse", "wrong supplier")
    assert db.get(c, b)["status"] == "rejected"


def test_correct_reruns_to_approved(c):
    f = {"invoice_number": "9", "invoice_date": "2026-10-01", "seller": "S", "subtotal": 100.0, "tax": 20.0,
         "total": 150.0, "line_items": [{"amount": 100.0}]}
    iid = db.add(c, "c.pdf", f, rules.check(f), "rules")
    assert db.get(c, iid)["status"] == "in_review"
    f2 = {**f, "total": 120.0}
    assert db.correct(c, iid, f2, rules.check(f2, db.numbers(c, exclude_id=iid)), "ayse") == "approved"
    assert "corrected" in [x["action"] for x in db.audit(c, iid)]


def test_duplicate_number_via_db(c):
    db.add(c, "a.pdf", {"invoice_number": "DUP"}, OK, "rules")
    assert not {r["rule"]: r for r in rules.check({"invoice_number": "DUP"}, db.numbers(c))}["duplicate_number"]["passed"]


def test_web_end_to_end(tmp_path):
    app = create_app(tmp_path, "", "")
    cl = app.test_client()
    for name in ["sliced-invoice-INV-3337.pdf", "acme-invoice-1002-bad-total.pdf"]:
        r = cl.post("/upload", data={"files": (open(SAMPLES / name, "rb"), name)}, content_type="multipart/form-data")
        assert r.status_code == 302
    page = cl.get("/").get_data(as_text=True)
    assert "INV-3337" in page and "ACME-1002" in page and "in review" in page
    r = cl.post("/invoice/2/decide", data={"action": "approve", "actor": "test", "note": "ok"})
    assert r.status_code == 302 and "approved" in cl.get("/invoice/2").get_data(as_text=True)
    wb = load_workbook(io.BytesIO(cl.get("/export.xlsx").data))
    assert wb["Invoices"].max_row == 3 and wb.sheetnames == ["Invoices", "Line items"]
    assert len(cl.get("/export.json").get_json()) == 2
