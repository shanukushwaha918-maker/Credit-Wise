"""Tests for FinTech platform modules: Credit Profile, Loan Affordability, AI Assistant, and Dashboard."""
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.credit_profile import calculate_credit_health
from backend.app.loan_calculator import calculate_loan_affordability


def test_credit_health_calculation_logic():
    # Prime applicant
    prime = calculate_credit_health(
        monthly_income=100000,
        employment_type="Salaried",
        existing_loans=1,
        monthly_emi=15000,
        credit_card_utilization=15.0,
        repayment_history="On-time / No delays",
        active_accounts=3,
        recent_enquiries=0,
    )
    assert 750 <= prime["credit_health_index"] <= 850
    assert prime["category"] in ("Excellent", "Good")
    assert len(prime["strengths"]) > 0
    assert len(prime["suggestions"]) > 0
    assert "NOT an official credit bureau score" in prime["disclaimer"]

    # Stressed applicant
    stressed = calculate_credit_health(
        monthly_income=30000,
        employment_type="Self-employed",
        existing_loans=4,
        monthly_emi=22000,
        credit_card_utilization=85.0,
        repayment_history="Frequent delays (30+ days)",
        active_accounts=8,
        recent_enquiries=6,
    )
    assert 300 <= stressed["credit_health_index"] <= 550
    assert stressed["category"] in ("Needs Attention", "High Risk")
    assert len(stressed["risks"]) > 0


def test_loan_affordability_mathematical_precision():
    # Test standard mortgage: 1,000,000 at 10% per annum for 60 months (5 years)
    res = calculate_loan_affordability(
        monthly_income=80000,
        existing_emi=10000,
        loan_amount=1000000,
        interest_rate=10.0,
        tenure_months=60,
    )
    # Expected EMI ~ 21,247.04
    assert res["estimated_emi"] == pytest.approx(21247.04, abs=1.0)
    assert res["total_repayment"] == pytest.approx(21247.04 * 60, abs=60.0)
    assert res["total_interest"] == pytest.approx(res["total_repayment"] - 1000000, abs=1.0)
    assert len(res["amortization_schedule"]) == 5
    assert res["amortization_schedule"][-1]["ending_balance"] == pytest.approx(0.0, abs=10.0)
    assert "Estimated calculations are for informational" in res["disclaimer"]


def test_credit_profile_endpoints():
    c = TestClient(app)
    # Register a new user
    c.post("/api/auth/signup", json={"name": "Pooja Sharma", "email": "pooja@example.com", "password": "password123"})

    # Check empty profile initially
    get_res = c.get("/api/profile")
    assert get_res.status_code == 200
    assert get_res.json()["has_profile"] is False

    # Save credit profile
    profile_payload = {
        "monthly_income": 85000,
        "employment_type": "Salaried",
        "existing_loans": 1,
        "monthly_emi": 12000,
        "credit_card_utilization": 22.5,
        "repayment_history": "On-time / No delays",
        "active_accounts": 3,
        "recent_enquiries": 1,
    }
    put_res = c.put("/api/profile", json=profile_payload)
    assert put_res.status_code == 200
    data = put_res.json()["data"]
    assert data["profile"]["monthly_income"] == 85000
    assert data["analysis"]["credit_health_index"] >= 700

    # Retrieve saved profile
    get_res2 = c.get("/api/profile")
    assert get_res2.status_code == 200
    assert get_res2.json()["has_profile"] is True
    assert get_res2.json()["data"]["profile"]["credit_card_utilization"] == 22.5


def test_loan_assessment_endpoints():
    c = TestClient(app)
    c.post("/api/auth/signup", json={"name": "Rahul Verma", "email": "rahul@example.com", "password": "password123"})

    payload = {
        "monthly_income": 70000,
        "existing_emi": 8000,
        "loan_amount": 500000,
        "interest_rate": 11.5,
        "tenure_months": 36,
        "save": True,
    }
    res = c.post("/api/loan-assessment", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["estimated_emi"] > 0
    assert "id" in data

    # Check history
    hist = c.get("/api/loan-assessment/history")
    assert hist.status_code == 200
    assert len(hist.json()["items"]) >= 1


def test_ai_assistant_flow():
    c = TestClient(app)
    c.post("/api/auth/signup", json={"name": "Karan Singhal", "email": "karan@example.com", "password": "password123"})

    # Send a query
    res = c.post("/api/assistant/chat", json={"message": "How does credit card utilization affect my credit score?"})
    assert res.status_code == 200
    data = res.json()
    assert "reply" in data
    assert "utilization" in data["reply"].lower()

    # Verify history
    history = c.get("/api/assistant/history")
    assert history.status_code == 200
    msgs = history.json()["messages"]
    assert len(msgs) >= 2  # user and assistant messages

    # Clear history
    clear_res = c.delete("/api/assistant/history")
    assert clear_res.status_code == 200
    assert c.get("/api/assistant/history").json()["messages"] == []


def test_dashboard_summary_endpoint():
    c = TestClient(app)
    c.post("/api/auth/signup", json={"name": "Ananya Roy", "email": "ananya@example.com", "password": "password123"})

    res = c.get("/api/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["email"] == "ananya@example.com"
    assert "dataset_stats" in data
    assert data["dataset_stats"]["total_applicants"] == 1000
