import json
import uuid
from pathlib import Path

from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from . import config, db, export, extract, rules


def create_app(data_dir=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = int(config.MAX_UPLOAD_MB * 1024 * 1024)
    data = Path(data_dir or config.DATA_DIR)
    uploads = data / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    dbpath = data / "invoice_desk.db"

    def conn():
        return db.connect(dbpath)

    @app.get("/health")
    def health():
        return {"ok": True, "llm_configured": bool(config.LLM_API_KEY and config.LLM_BASE_URL and config.LLM_MODEL)}

    @app.get("/")
    def index():
        c = conn()
        invs = db.all_invoices(c)
        counts = {s: sum(1 for i in invs if i["status"] == s) for s in ("approved", "in_review", "rejected")}
        return render_template("index.html", invoices=invs, counts=counts)

    @app.post("/upload")
    def upload():
        files = [f for f in request.files.getlist("files") if f and f.filename]
        if not files:
            flash("Choose at least one PDF.")
            return redirect(url_for("index"))
        c = conn()
        last = None
        for f in files:
            name = secure_filename(f.filename) or "invoice.pdf"
            if not name.lower().endswith(".pdf"):
                flash(f"{name}: only PDF files are accepted.")
                continue
            path = uploads / f"{uuid.uuid4().hex}_{name}"
            f.save(path)
            try:
                res = extract.extract(path)
            except Exception as e:
                flash(f"{name}: could not read PDF ({type(e).__name__}).")
                path.unlink(missing_ok=True)
                continue
            checks = rules.check(res["fields"], db.numbers(c))
            last = db.add(c, name, res["fields"], checks, f"{res['engine']}/{res['text_method']}")
        return redirect(url_for("detail", iid=last) if last and len(files) == 1 else url_for("index"))

    @app.get("/invoice/<int:iid>")
    def detail(iid):
        c = conn()
        inv = db.get(c, iid) or abort(404)
        return render_template("detail.html", inv=inv, audit=db.audit(c, iid))

    @app.post("/invoice/<int:iid>/decide")
    def decide(iid):
        c = conn()
        action = request.form.get("action")
        actor = request.form.get("actor", "").strip() or "reviewer"
        note = request.form.get("note", "")
        try:
            if action not in ("approve", "reject"):
                abort(400)
            db.set_status(c, iid, "approved" if action == "approve" else "rejected", actor, note)
        except ValueError as e:
            flash(str(e))
        except KeyError:
            abort(404)
        return redirect(url_for("detail", iid=iid))

    @app.post("/invoice/<int:iid>/correct")
    def correct(iid):
        c = conn()
        inv = db.get(c, iid) or abort(404)
        f = dict(inv["fields"])
        for k in ("invoice_number", "invoice_date", "seller", "buyer", "currency"):
            if k in request.form:
                f[k] = request.form[k].strip() or None
        for k in ("subtotal", "tax", "total"):
            if k in request.form:
                f[k] = extract.to_amount(request.form[k]) if request.form[k].strip() else None
        checks = rules.check(f, db.numbers(c, exclude_id=iid))
        st = db.correct(c, iid, f, checks, request.form.get("actor", "").strip() or "reviewer", request.form.get("note", ""))
        flash(f"Saved. Checks re-run; status is now {st}.")
        return redirect(url_for("detail", iid=iid))

    @app.get("/export.xlsx")
    def export_xlsx():
        invs = _filtered(conn())
        return Response(export.xlsx(invs), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": "attachment; filename=invoices.xlsx"})

    @app.get("/export.json")
    def export_json():
        invs = _filtered(conn())
        return Response(json.dumps(invs, indent=2, ensure_ascii=False), mimetype="application/json",
                        headers={"Content-Disposition": "attachment; filename=invoices.json"})

    def _filtered(c):
        invs = db.all_invoices(c)
        st = request.args.get("status")
        return [i for i in invs if i["status"] == st] if st else invs

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8010)
