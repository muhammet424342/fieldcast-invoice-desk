"""SQLite storage: invoices + audit log. Status: approved | in_review | rejected."""
import json
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices(
  id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, invoice_number TEXT,
  fields TEXT, checks TEXT, status TEXT, engine TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id INTEGER, action TEXT,
  actor TEXT, note TEXT, at TEXT);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path):
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def log(c, invoice_id, action, actor="system", note=""):
    c.execute("INSERT INTO audit(invoice_id,action,actor,note,at) VALUES(?,?,?,?,?)",
              (invoice_id, action, actor, note, now()))


def numbers(c, exclude_id=None):
    q = "SELECT invoice_number FROM invoices WHERE invoice_number IS NOT NULL AND status!='rejected'"
    rows = c.execute(q + (" AND id!=?" if exclude_id else ""), (exclude_id,) if exclude_id else ()).fetchall()
    return [r[0] for r in rows]


def add(c, filename, fields, checks, engine):
    status = "approved" if all(x["passed"] for x in checks) else "in_review"
    cur = c.execute("INSERT INTO invoices(filename,invoice_number,fields,checks,status,engine,created_at,updated_at)"
                    " VALUES(?,?,?,?,?,?,?,?)", (filename, fields.get("invoice_number"), json.dumps(fields),
                                                 json.dumps(checks), status, engine, now(), now()))
    iid = cur.lastrowid
    failed = [x["rule"] for x in checks if not x["passed"]]
    log(c, iid, "uploaded", note=f"engine={engine}")
    log(c, iid, "auto_approved" if status == "approved" else "sent_to_review", note=", ".join(failed))
    c.commit()
    return iid


def get(c, iid):
    r = c.execute("SELECT * FROM invoices WHERE id=?", (iid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["fields"], d["checks"] = json.loads(d["fields"]), json.loads(d["checks"])
    return d


def all_invoices(c):
    return [get(c, r[0]) for r in c.execute("SELECT id FROM invoices ORDER BY id DESC")]


def set_status(c, iid, status, actor, note=""):
    inv = get(c, iid)
    if inv is None:
        raise KeyError(iid)
    if inv["status"] != "in_review":
        raise ValueError(f"invoice {iid} is {inv['status']}, only in_review can be decided")
    if status == "rejected" and not note.strip():
        raise ValueError("a rejection needs a reason")
    c.execute("UPDATE invoices SET status=?, updated_at=? WHERE id=?", (status, now(), iid))
    log(c, iid, status, actor, note)
    c.commit()


def correct(c, iid, new_fields, new_checks, actor, note=""):
    inv = get(c, iid)
    if inv is None:
        raise KeyError(iid)
    changed = {k: [inv["fields"].get(k), v] for k, v in new_fields.items() if inv["fields"].get(k) != v}
    status = "approved" if all(x["passed"] for x in new_checks) else "in_review"
    if inv["status"] == "rejected":
        status = "rejected"
    c.execute("UPDATE invoices SET fields=?, checks=?, invoice_number=?, status=?, updated_at=? WHERE id=?",
              (json.dumps(new_fields), json.dumps(new_checks), new_fields.get("invoice_number"), status, now(), iid))
    log(c, iid, "corrected", actor, (note + " " + json.dumps(changed)).strip())
    if status == "approved":
        log(c, iid, "auto_approved_after_correction", actor)
    c.commit()
    return status


def audit(c, iid):
    return [dict(r) for r in c.execute("SELECT * FROM audit WHERE invoice_id=? ORDER BY id", (iid,))]
