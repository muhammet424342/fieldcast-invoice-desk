import base64

from invoice_desk.app import create_app


def hdr(u, p):
    return {"Authorization": "Basic " + base64.b64encode(f"{u}:{p}".encode()).decode()}


def test_auth_required(tmp_path):
    cl = create_app(tmp_path, "admin", "s3cret-test").test_client()
    r = cl.get("/")
    assert r.status_code == 401 and "Basic" in r.headers["WWW-Authenticate"]
    assert cl.get("/", headers=hdr("admin", "wrong")).status_code == 401
    assert cl.get("/", headers=hdr("other", "s3cret-test")).status_code == 401
    assert cl.get("/", headers=hdr("admin", "s3cret-test")).status_code == 200
    assert cl.get("/export.json").status_code == 401
    assert cl.post("/invoice/1/decide", data={"action": "approve"}).status_code == 401


def test_health_open(tmp_path):
    cl = create_app(tmp_path, "admin", "s3cret-test").test_client()
    assert cl.get("/health").status_code == 200


def test_warning_when_unset(tmp_path, capsys):
    cl = create_app(tmp_path, "", "").test_client()
    assert "WARNING" in capsys.readouterr().err
    assert cl.get("/").status_code == 200
