"""Loan Eligibility & Affordability Calculator Module.

Performs exact mathematical amortization, debt-to-income analysis,
repayment forecasts, and lender eligibility thresholds.

IMPORTANT DISCLAIMER:
Calculations are mathematical estimates for planning purposes.
Actual loan approval, sanctioned amounts, processing fees, and interest rates
are subject to formal lender credit appraisal and underwriting policies.
"""
from datetime import datetime, timezone
import math
from typing import Optional

from .db import Database


LOAN_DISCLAIMER = (
    "Estimated calculations are for informational and financial planning purposes only. "
    "Actual loan sanctions, interest rates, processing fees, and eligibility are determined "
    "exclusively by the financial institution upon formal application verification."
)


def calculate_loan_affordability(
    monthly_income: float,
    existing_emi: float,
    loan_amount: float,
    interest_rate: float,
    tenure_months: int,
) -> dict:
    """Calculate exact EMI, DTI impact, interest breakdown, and affordability verdict."""
    income = max(1.0, float(monthly_income))
    exist_emi = max(0.0, float(existing_emi))
    principal = max(1.0, float(loan_amount))
    rate_annual = max(0.01, float(interest_rate))
    tenure = max(1, int(tenure_months))

    # Monthly interest rate
    r = (rate_annual / 100.0) / 12.0

    # Exact EMI formula: P * r * (1+r)^n / ((1+r)^n - 1)
    if r == 0:
        emi = principal / tenure
    else:
        emi = principal * (r * math.pow(1 + r, tenure)) / (math.pow(1 + r, tenure) - 1)

    total_repayment = emi * tenure
    total_interest = total_repayment - principal

    # DTI ratios
    existing_dti = exist_emi / income
    new_total_emi = exist_emi + emi
    new_dti = new_total_emi / income

    # Safe borrowing capacity (Standard banking benchmark: total EMI <= 50% of income)
    max_safe_total_emi = income * 0.50
    available_emi_capacity = max(0.0, max_safe_total_emi - exist_emi)

    # Maximum loan amount affordable at available capacity
    if r == 0:
        max_affordable_loan = available_emi_capacity * tenure
    else:
        max_affordable_loan = available_emi_capacity * (math.pow(1 + r, tenure) - 1) / (r * math.pow(1 + r, tenure))

    # Affordability verdict & explanation
    if new_dti <= 0.35:
        affordability_status = "Comfortably Affordable"
        risk_level = "Low"
        explanation = (
            f"Your projected total EMI (₹{new_total_emi:,.0f}) will constitute {new_dti*100:.1f}% of your monthly income. "
            "This is within the ideal 35% financial ceiling, leaving a substantial cushion for living expenses and savings. "
            "Lenders consider this profile low risk."
        )
    elif new_dti <= 0.50:
        affordability_status = "Manageable with Budgeting"
        risk_level = "Moderate"
        explanation = (
            f"Your projected total EMI (₹{new_total_emi:,.0f}) will consume {new_dti*100:.1f}% of monthly earnings. "
            "While most banks approve up to a 50% DTI, your discretionary spending will be tight. "
            "Consider extending tenure or increasing down payment to reduce monthly commitments."
        )
    else:
        affordability_status = "High Financial Burden"
        risk_level = "High"
        explanation = (
            f"Projected total obligations (₹{new_total_emi:,.0f}) absorb {new_dti*100:.1f}% of income, "
            "exceeding standard lending guidelines (50% DTI). Most lenders may decline or require a creditworthy co-borrower. "
            f"Recommended safe loan amount at this tenure is ₹{max_affordable_loan:,.0f}."
        )

    # Annual amortization breakdown (for charts and tables)
    amortization_schedule = []
    balance = principal
    monthly_balance = principal
    years = max(1, math.ceil(tenure / 12))

    for y in range(1, years + 1):
        year_principal = 0.0
        year_interest = 0.0
        months_in_year = min(12, tenure - (y - 1) * 12)

        for _ in range(months_in_year):
            month_interest = monthly_balance * r
            month_principal = emi - month_interest
            if month_principal > monthly_balance:
                month_principal = monthly_balance
                emi_actual = month_principal + month_interest
            else:
                emi_actual = emi
            monthly_balance = max(0.0, monthly_balance - month_principal)
            year_principal += month_principal
            year_interest += month_interest

        amortization_schedule.append({
            "year": y,
            "principal_paid": round(year_principal, 2),
            "interest_paid": round(year_interest, 2),
            "total_paid": round(year_principal + year_interest, 2),
            "ending_balance": round(monthly_balance, 2),
        })

    return {
        "monthly_income": round(income, 2),
        "existing_emi": round(exist_emi, 2),
        "loan_amount": round(principal, 2),
        "interest_rate": round(rate_annual, 2),
        "tenure_months": tenure,
        "estimated_emi": round(emi, 2),
        "total_interest": round(total_interest, 2),
        "total_repayment": round(total_repayment, 2),
        "existing_dti_percent": round(existing_dti * 100, 1),
        "new_total_emi": round(new_total_emi, 2),
        "new_dti_percent": round(new_dti * 100, 1),
        "affordability_status": affordability_status,
        "risk_level": risk_level,
        "explanation": explanation,
        "max_affordable_loan": round(max_affordable_loan, 2),
        "max_safe_emi": round(available_emi_capacity, 2),
        "amortization_schedule": amortization_schedule,
        "disclaimer": LOAN_DISCLAIMER,
    }


class LoanAssessmentStore:
    def __init__(self, target):
        self.db = Database(target)
        self.db.script([
            f"""CREATE TABLE IF NOT EXISTS loan_assessments (
                    id {self.db.id_column},
                    user_id BIGINT NOT NULL,
                    monthly_income DOUBLE PRECISION NOT NULL,
                    existing_emi DOUBLE PRECISION NOT NULL,
                    loan_amount DOUBLE PRECISION NOT NULL,
                    interest_rate DOUBLE PRECISION NOT NULL,
                    tenure_months INTEGER NOT NULL,
                    estimated_emi DOUBLE PRECISION NOT NULL,
                    total_interest DOUBLE PRECISION NOT NULL,
                    total_repayment DOUBLE PRECISION NOT NULL,
                    new_dti DOUBLE PRECISION NOT NULL,
                    affordability_status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )""",
            "CREATE INDEX IF NOT EXISTS idx_loan_assessments_user ON loan_assessments(user_id)",
        ])

    def save(self, user_id: int, assessment: dict) -> int:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        new_id = self.db.run(
            """INSERT INTO loan_assessments (
                user_id, monthly_income, existing_emi, loan_amount, interest_rate,
                tenure_months, estimated_emi, total_interest, total_repayment,
                new_dti, affordability_status, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                assessment["monthly_income"],
                assessment["existing_emi"],
                assessment["loan_amount"],
                assessment["interest_rate"],
                assessment["tenure_months"],
                assessment["estimated_emi"],
                assessment["total_interest"],
                assessment["total_repayment"],
                assessment["new_dti_percent"],
                assessment["affordability_status"],
                now,
            ),
            returning_id=True,
        )
        return new_id

    def list(self, user_id: int, limit: int = 10) -> list:
        return self.db.run(
            "SELECT * FROM loan_assessments WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
            fetch="all",
        )
