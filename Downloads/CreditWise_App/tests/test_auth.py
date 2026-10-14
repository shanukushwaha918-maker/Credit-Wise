"""Account, session and access-control tests."""
import sqlite3

from fastapi.testclient import TestClient

from backend.app.main import DB_PATH, app

APPLICANT = {
    "Applicant_Income": 12000, "Coapplicant_Income": 4000, "Employment_Status": "Salaried", "Age": 35,
    "Marital_Status": "Married", "Dependents": 1, "Credit_Score": 720, "Existing_Loans": 1, "DTI_Ratio": 0.25,
    "Savings": 15000, "Collateral_Value": 30000, "Loan_Amount": 15000, "Loan_Term": 48, "Loan_Purpose": "Home",
    "Property_Area": "Urban", "Education_Level": "Graduate", "Gender": "Female", "Employer_Category": "MNC",
}


def new_user(email, password="secret123", name="Test User"):
    c = TestClient(app)
    r = c.post("/api/auth/signup", json={"name": name, "email": email, "password": password})
    assert r.status_code == 201, r.text
    return c


def errors_for(r):
    return {e["field"]: e["message"] for e in r.json().get("errors", [])}


def test_protected_endpoints_require_login():
    anon = TestClient(app)
    assert anon.get("/api/health").status_code == 200
    assert anon.get("/").status_code == 200
    for method, path in [("get", "/api/meta"), ("get", "/api/history"), ("get", "/api/sample"),
                         ("get", "/api/schema/applicant"), ("delete", "/api/history"), ("get", "/api/auth/me")]:
        assert getattr(anon, method)(path).status_code == 401, path
    assert anon.post("/api/predict", json={"applicant": APPLICANT}).status_code == 401


def test_signup_logs_in_and_hides_password():
    c = TestClient(app)
    r = c.post("/api/auth/signup", json={"name": "  Asha Verma ", "email": "asha@example.com", "password": "secret123"})
    assert r.status_code == 201
    user = r.json()["user"]
    assert user["name"] == "Asha Verma" and user["email"] == "asha@example.com"
    assert "password" not in str(r.json())
    cookie = r.headers["set-cookie"].lower()
    assert "cw_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert c.get("/api/auth/me").json()["user"]["email"] == "asha@example.com"
    assert c.get("/api/meta").status_code == 200


def test_passwords_are_stored_hashed():
    new_user("hash-check@example.com", password="plaintext99")
    row = sqlite3.connect(DB_PATH).execute(
        "SELECT password_hash FROM users WHERE email = ?", ("hash-check@example.com",)).fetchone()
    assert row[0].startswith("scrypt$") and "plaintext99" not in row[0]


def test_duplicate_email_is_rejected_case_insensitively():
    new_user("dup@example.com")
    r = TestClient(app).post("/api/auth/signup", json={"name": "Other", "email": "DUP@example.com", "password": "secret123"})
    assert r.status_code == 409
    assert "already exists" in errors_for(r)["email"]


def test_signup_validation_messages():
    c = TestClient(app)
    r = c.post("/api/auth/signup", json={"name": "A", "email": "not-an-email", "password": "short"})
    assert r.status_code == 422
    errs = errors_for(r)
    assert set(errs) == {"name", "email", "password"}
    assert errs["email"] == "Enter a valid email address"
    r = c.post("/api/auth/signup", json={"name": "Valid Name", "email": "v@example.com", "password": "lettersonly"})
    assert errors_for(r)["password"] == "Password must contain at least one letter and one number"


def test_login_logout_and_remember_me():
    new_user("login@example.com", password="correct123")
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": "login@example.com", "password": "wrong-pass1"})
    assert r.status_code == 401 and r.json()["detail"] == "Incorrect email or password."
    r = c.post("/api/auth/login", json={"email": "nobody@example.com", "password": "whatever1"})
    assert r.status_code == 401 and r.json()["detail"] == "Incorrect email or password."

    r = c.post("/api/auth/login", json={"email": "LOGIN@example.com", "password": "correct123"})
    assert r.status_code == 200
    assert "max-age" not in r.headers["set-cookie"].lower()  # browser-session cookie by default
    token = c.cookies.get("cw_session")
    assert c.get("/api/auth/me").status_code == 200

    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/auth/me").status_code == 401
    replay = TestClient(app, cookies={"cw_session": token})
    assert replay.get("/api/auth/me").status_code == 401  # token revoked server-side

    r = c.post("/api/auth/login", json={"email": "login@example.com", "password": "correct123", "remember": True})
    assert "max-age=2592000" in r.headers["set-cookie"].lower()  # 30 days


def test_failed_logins_are_rate_limited():
    new_user("locked@example.com", password="right1234")
    c = TestClient(app)
    for _ in range(5):
        assert c.post("/api/auth/login", json={"email": "locked@example.com", "password": "bad12345"}).status_code == 401
    r = c.post("/api/auth/login", json={"email": "locked@example.com", "password": "right1234"})
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_history_is_private_per_user():
    a = new_user("alice@example.com")
    b = new_user("bob@example.com")
    item = a.post("/api/predict", json={"applicant": APPLICANT}).json()["history"]["id"]
    assert [h["id"] for h in a.get("/api/history").json()["items"]] == [item]
    assert b.get("/api/history").json()["items"] == []
    assert b.delete(f"/api/history/{item}").status_code == 404
    assert b.delete("/api/history").json()["deleted"] == 0
    assert len(a.get("/api/history").json()["items"]) == 1


def test_cross_site_writes_are_blocked():
    c = new_user("csrf@example.com")
    r = c.post("/api/predict", json={"applicant": APPLICANT}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = c.post("/api/predict", json={"applicant": APPLICANT, "save": False}, headers={"Origin": "http://testserver"})
    assert r.status_code == 200
