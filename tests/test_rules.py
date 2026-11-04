from datetime import date

from invoice_desk import rules

GOOD = {"invoice_number": "A-1", "invoice_date": "2026-10-01", "seller": "S", "buyer": "B",
        "subtotal": 100.0, "tax": 20.0, "total": 120.0,
        "line_items": [{"amount": 60.0}, {"amount": 40.0}]}
TODAY = date(2026, 11, 4)


def by_rule(res):
    return {r["rule"]: r for r in res}


def run(f, **kw):
    return by_rule(rules.check(f, today=TODAY, tolerance=0.02, threshold=10000, **kw))


def test_all_pass():
    r = run(GOOD)
    assert all(x["passed"] for x in r.values())
    assert all(x["message"] for x in r.values())


def test_line_sum_mismatch():
    r = run({**GOOD, "line_items": [{"amount": 60.0}]})
    assert not r["line_items_sum"]["passed"] and "does NOT match" in r["line_items_sum"]["message"]


def test_total_mismatch_and_tolerance():
    assert not run({**GOOD, "total": 125.0})["subtotal_plus_tax"]["passed"]
    assert run({**GOOD, "total": 120.01})["subtotal_plus_tax"]["passed"]


def test_missing_required():
    r = run({**GOOD, "seller": None, "invoice_number": ""})
    assert not r["required_fields"]["passed"]
    assert "seller" in r["required_fields"]["message"] and "invoice_number" in r["required_fields"]["message"]


def test_duplicate():
    assert not run(GOOD, existing_numbers=["A-1"])["duplicate_number"]["passed"]


def test_future_and_invalid_date():
    assert not run({**GOOD, "invoice_date": "2027-01-01"})["valid_date"]["passed"]
    assert not run({**GOOD, "invoice_date": None, "invoice_date_raw": "31/31/2026"})["valid_date"]["passed"]


def test_threshold():
    f = {**GOOD, "subtotal": 20000.0, "tax": 0, "total": 20000.0, "line_items": [{"amount": 20000.0}]}
    assert not run(f)["amount_threshold"]["passed"]
