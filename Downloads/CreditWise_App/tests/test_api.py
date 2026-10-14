"""End-to-end API tests. Run from the project root:  python -m pytest -q
(conftest.py points the app at a throwaway database.)"""
import math
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.impute import SimpleImputer
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split

from backend.app.main import app, predictor

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)
# All data endpoints require a logged-in user; the session cookie stays on this client.
assert client.post("/api/auth/signup", json={"name": "API Tester", "email": "api-tester@example.com",
                                             "password": "testpass123"}).status_code == 201

APPLICANT = {
    "Applicant_Income": 12000, "Coapplicant_Income": 4000, "Employment_Status": "Salaried", "Age": 35,
    "Marital_Status": "Married", "Dependents": 1, "Credit_Score": 720, "Existing_Loans": 1, "DTI_Ratio": 0.25,
    "Savings": 15000, "Collateral_Value": 30000, "Loan_Amount": 15000, "Loan_Term": 48, "Loan_Purpose": "Home",
    "Property_Area": "Urban", "Education_Level": "Graduate", "Gender": "Female", "Employer_Category": "MNC",
}


def notebook_test_split():
    """The notebook's imputed frame and test split (random_state=42), as raw applicant rows."""
    df = pd.read_csv(ROOT / "data" / "loan_approval_data.csv")
    cat = df.select_dtypes(include=["object"]).columns
    num = df.select_dtypes(include=["number"]).columns
    df[num] = SimpleImputer(strategy="mean").fit_transform(df[num])
    df[cat] = SimpleImputer(strategy="most_frequent").fit_transform(df[cat])
    df = df.drop("Applicant_ID", axis=1)
    _, test = train_test_split(df, test_size=0.2, random_state=42)
    return test


# ------------------------------------------------------------- model fidelity
@pytest.mark.parametrize("model", ["naive_bayes", "logistic_regression", "knn"])
def test_served_model_reproduces_notebook_confusion_matrix(model):
    test = notebook_test_split()
    preds = [predictor.predict(row.drop("Loan_Approved").to_dict(), model)["prediction"] for _, row in test.iterrows()]
    cm = confusion_matrix(test["Loan_Approved"], preds, labels=["No", "Yes"]).tolist()
    assert cm == predictor.meta["metrics"][model]["confusion_matrix"]


def test_metrics_match_notebook_output():
    m = predictor.meta["metrics"]
    assert m["naive_bayes"]["precision"] == pytest.approx(0.8035714285714286)
    assert m["logistic_regression"]["accuracy"] == pytest.approx(0.865)
    assert m["knn"]["confusion_matrix"] == [[120, 19], [29, 32]]


@pytest.mark.parametrize("model", ["naive_bayes", "logistic_regression"])
def test_explanation_sums_to_model_log_odds(model):
    r = client.post("/api/predict", json={"applicant": APPLICANT, "model": model, "save": False}).json()
    p = r["probability_approved"]
    total = r["explanation"]["base"] + sum(f["impact"] for f in r["explanation"]["factors"])
    assert total == pytest.approx(math.log(p / (1 - p)), abs=1e-2)
    assert {f["field"] for f in r["explanation"]["factors"]} == set(APPLICANT)


# ------------------------------------------------------------------ endpoints
def test_health_and_meta():
    assert client.get("/api/health").json()["status"] == "ok"
    meta = client.get("/api/meta").json()
    assert meta["default_model"] == "naive_bayes"
    assert len(meta["models"]) == 3
    assert meta["dataset"]["rows"] == 1000


def test_predict_default_model_and_comparison():
    r = client.post("/api/predict", json={"applicant": APPLICANT, "save": False})
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "naive_bayes"
    assert 0 <= body["probability_approved"] <= 1
    assert body["prediction"] in ("Yes", "No")
    assert body["approved"] == (body["prediction"] == "Yes")
    assert {c["model"] for c in body["comparison"]} == {"naive_bayes", "logistic_regression", "knn"}
    assert body["warnings"] == []
    assert "history" not in body


def test_knn_explanation_lists_neighbours():
    body = client.post("/api/predict", json={"applicant": APPLICANT, "model": "knn", "save": False}).json()
    ex = body["explanation"]
    assert ex["neighbours"] == 5
    assert body["probability_approved"] == pytest.approx(ex["approved_neighbours"] / 5)


def test_low_credit_score_is_rejected_like_training_data():
    bad = {**APPLICANT, "Credit_Score": 580, "DTI_Ratio": 0.55}
    body = client.post("/api/predict", json={"applicant": bad, "save": False}).json()
    assert body["prediction"] == "No"


def test_sample_returns_real_dataset_row():
    s = client.get("/api/sample", params={"seed": 7}).json()
    df = pd.read_csv(ROOT / "data" / "loan_approval_data.csv")
    row = df[df["Applicant_ID"] == s["applicant_id"]].iloc[0]
    assert row["Loan_Approved"] == s["actual_outcome"]
    for k, v in s["applicant"].items():
        assert row[k] == v
    assert client.post("/api/predict", json={"applicant": s["applicant"], "save": False}).status_code == 200


# ----------------------------------------------------------------- validation
@pytest.mark.parametrize("patch,field", [
    ({"Credit_Score": 1200}, "Credit_Score"),
    ({"DTI_Ratio": 1.5}, "DTI_Ratio"),
    ({"Age": 12}, "Age"),
    ({"Gender": "Other"}, "Gender"),
    ({"Loan_Amount": 0}, "Loan_Amount"),
    ({"Dependents": 1.5}, "Dependents"),
    ({"Applicant_Income": "abc"}, "Applicant_Income"),
])
def test_invalid_inputs_return_422_with_field(patch, field):
    r = client.post("/api/predict", json={"applicant": {**APPLICANT, **patch}, "save": False})
    assert r.status_code == 422
    assert field in [e["field"] for e in r.json()["errors"]]


def test_missing_field_and_unknown_model():
    incomplete = {k: v for k, v in APPLICANT.items() if k != "Savings"}
    r = client.post("/api/predict", json={"applicant": incomplete})
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "Savings"
    r = client.post("/api/predict", json={"applicant": APPLICANT, "model": "random_forest"})
    assert r.status_code == 422


def test_out_of_training_range_warns():
    body = client.post("/api/predict", json={"applicant": {**APPLICANT, "Applicant_Income": 90000}, "save": False}).json()
    assert [w["field"] for w in body["warnings"]] == ["Applicant_Income"]


# -------------------------------------------------------------------- history
def test_history_lifecycle():
    client.delete("/api/history")
    r = client.post("/api/predict", json={"applicant": APPLICANT, "model": "logistic_regression"}).json()
    hid = r["history"]["id"]
    items = client.get("/api/history").json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == hid
    assert items[0]["model"] == "logistic_regression"
    assert items[0]["probability_approved"] == pytest.approx(r["probability_approved"])
    assert items[0]["applicant"] == {**APPLICANT, **{k: float(v) for k, v in APPLICANT.items()
                                                    if isinstance(v, (int, float)) and k not in
                                                    ("Dependents", "Existing_Loans", "Loan_Term")}}
    assert client.delete(f"/api/history/{hid}").status_code == 200
    assert client.delete(f"/api/history/{hid}").status_code == 404
    assert client.get("/api/history").json()["items"] == []


def test_frontend_is_served():
    r = client.get("/")
    assert r.status_code == 200 and "CreditWise" in r.text
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/assets/styles.css").status_code == 200
