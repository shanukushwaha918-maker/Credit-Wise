"""Credit Profile Analysis Module.

Provides financial health scoring, strength/risk identification, and
personalized improvement suggestions based on user-reported credit parameters.

IMPORTANT DISCLAIMER:
The Credit Health Index is an educational statistical estimate (300-850)
designed for financial planning and self-assessment. It is NOT an official
bureau credit score (such as CIBIL, Experian, Equifax, or CRIF High Mark),
which require authorized bureau access and verified trade-line reports.
"""
from datetime import datetime, timezone
from typing import Optional

from .db import Database


DISCLAIMER_TEXT = (
    "Educational Credit Health Index estimate. This is NOT an official credit bureau score "
    "(such as CIBIL, Experian, or Equifax). Bureau scores require authorized access to your "
    "verified banking credit files. Use this index exclusively for financial wellness and planning."
)


def calculate_credit_health(
    monthly_income: float,
    employment_type: str,
    existing_loans: int,
    monthly_emi: float,
    credit_card_utilization: float,
    repayment_history: str,
    active_accounts: int,
    recent_enquiries: int,
) -> dict:
    """Calculate Credit Health Index, identify strengths/risks, and generate suggestions."""
    # Safety checks
    income = max(1.0, float(monthly_income))
    emi = max(0.0, float(monthly_emi))
    utilization = max(0.0, min(100.0, float(credit_card_utilization)))
    dti_ratio = emi / income

    # 1. Repayment History (35% weight -> max 192.5 pts)
    history_lower = repayment_history.lower()
    if "on-time" in history_lower or "excellent" in history_lower or "no delay" in history_lower:
        hist_score = 192.5
        hist_note = "Flawless on-time repayment history across all accounts."
    elif "occasional" in history_lower or "minor" in history_lower:
        hist_score = 120.0
        hist_note = "Minor or occasional delayed payments reported."
    elif "frequent" in history_lower:
        hist_score = 55.0
        hist_note = "Frequent past payment delays significantly impacting credit standing."
    else:  # Default / Settlement
        hist_score = 10.0
        hist_note = "Severe delinquency or defaulted obligations recorded."

    # 2. Credit Card Utilization (30% weight -> max 165 pts)
    if utilization <= 10:
        util_score = 165.0
    elif utilization <= 30:
        util_score = 150.0
    elif utilization <= 50:
        util_score = 105.0
    elif utilization <= 75:
        util_score = 50.0
    else:
        util_score = 15.0

    # 3. Debt Burden / DTI (15% weight -> max 82.5 pts)
    if dti_ratio <= 0.20:
        dti_score = 82.5
    elif dti_ratio <= 0.35:
        dti_score = 70.0
    elif dti_ratio <= 0.50:
        dti_score = 40.0
    else:
        dti_score = 15.0

    # 4. Account Mix & Active Accounts (10% weight -> max 55 pts)
    if 2 <= active_accounts <= 6:
        mix_score = 55.0
    elif active_accounts == 1:
        mix_score = 40.0
    elif 7 <= active_accounts <= 10:
        mix_score = 35.0
    elif active_accounts > 10:
        mix_score = 20.0
    else:  # 0 accounts
        mix_score = 25.0

    # 5. Recent Enquiries (10% weight -> max 55 pts)
    if recent_enquiries == 0:
        enq_score = 55.0
    elif recent_enquiries <= 2:
        enq_score = 42.0
    elif recent_enquiries <= 4:
        enq_score = 25.0
    else:
        enq_score = 10.0

    # Total score (300 to 850)
    total_pts = hist_score + util_score + dti_score + mix_score + enq_score
    credit_health_index = int(round(300 + total_pts))
    credit_health_index = max(300, min(850, credit_health_index))

    # Rating & category
    if credit_health_index >= 750:
        category = "Excellent"
        summary = (
            "Outstanding financial profile. Your debt-to-income ratio, repayment habits, "
            "and credit management demonstrate prime creditworthiness for lending institutions."
        )
    elif credit_health_index >= 700:
        category = "Good"
        summary = (
            "Healthy credit standing. You qualify for competitive interest rates and favorable "
            "loan terms from most major banks and lenders."
        )
    elif credit_health_index >= 650:
        category = "Fair"
        summary = (
            "Moderate credit standing. While you are eligible for conventional borrowing, "
            "strengthening your utilization and paying down obligations will unlock better terms."
        )
    elif credit_health_index >= 550:
        category = "Needs Attention"
        summary = (
            "Constrained credit standing. Elevated debt burdens, late payments, or high utilization "
            "may trigger lender scrutiny or higher risk premiums."
        )
    else:
        category = "High Risk"
        summary = (
            "Substantial credit vulnerability. Urgent debt restructuring and disciplined repayment "
            "habits are required before seeking additional credit lines."
        )

    # Financial strengths
    strengths = []
    if "on-time" in history_lower or "excellent" in history_lower or "no delay" in history_lower:
        strengths.append("Punctual repayment record with zero reported defaults or write-offs.")
    if utilization <= 30:
        strengths.append(f"Low credit card utilization of {utilization:.1f}% remains well within recommended limits (below 30%).")
    if dti_ratio <= 0.35:
        strengths.append(f"Conservative debt-to-income ratio of {dti_ratio*100:.1f}%, leaving healthy disposable income.")
    if recent_enquiries <= 1:
        strengths.append(f"Minimal recent credit enquiries ({recent_enquiries} in last 6 months), signaling stable credit demand.")
    if 2 <= active_accounts <= 6:
        strengths.append(f"Well-balanced credit portfolio with {active_accounts} active credit facilities.")
    if employment_type in ("Salaried", "Business") and monthly_income >= 30000:
        strengths.append(f"Stable {employment_type.lower()} income source supporting ongoing obligations.")
    if not strengths:
        strengths.append("Active employment provides an underlying basis for structured financial rehabilitation.")

    # Potential risk factors
    risks = []
    if utilization > 40:
        risks.append(
            f"Credit card utilization is high at {utilization:.1f}%. Utilizing more than 30-40% of revolving credit penalizes credit scores."
        )
    if dti_ratio > 0.45:
        risks.append(
            f"Existing monthly EMI obligations absorb {dti_ratio*100:.1f}% of your monthly income, exceeding the recommended 40-50% ceiling."
        )
    if recent_enquiries >= 3:
        risks.append(
            f"{recent_enquiries} hard credit enquiries in the past 6 months may portray credit-seeking urgency to prospective lenders."
        )
    if "frequent" in history_lower or "default" in history_lower or "occasional" in history_lower:
        risks.append(f"Repayment record indicates payment irregularities ({repayment_history}).")
    if active_accounts > 7:
        risks.append(f"High number of active accounts ({active_accounts}) elevates exposure to unbudgeted credit liabilities.")
    if active_accounts == 0:
        risks.append("No active credit facilities ('thin credit file'), making creditworthiness harder for standard models to assess.")
    if not risks:
        risks.append("No major financial risk red flags identified in self-reported inputs.")

    # Personalized improvement suggestions
    suggestions = []
    if utilization > 30:
        suggestions.append(
            "Pay down credit card statement balances prior to billing cycles to bring revolving utilization under 30%."
        )
    if dti_ratio > 0.40:
        suggestions.append(
            "Prioritize pre-paying or consolidating high-interest short-term loans to reduce your monthly EMI burden."
        )
    if recent_enquiries >= 2:
        suggestions.append(
            "Pause applying for new credit cards or personal loans for the next 4-6 months to let hard enquiries age off."
        )
    if "on-time" not in history_lower and "excellent" not in history_lower:
        suggestions.append(
            "Set up automated standing instructions (auto-debit) on all EMI and utility payments to build a continuous on-time streak."
        )
    if active_accounts <= 1:
        suggestions.append(
            "Maintain a low-limit secured credit card and clear the balance in full each month to gradually build credit depth."
        )
    suggestions.append(
        "Build and preserve a 3-6 month liquid emergency fund to insulate debt repayments against unexpected income disruptions."
    )

    return {
        "credit_health_index": credit_health_index,
        "category": category,
        "summary": summary,
        "dti_ratio": round(dti_ratio, 4),
        "dti_percent": round(dti_ratio * 100, 1),
        "strengths": strengths,
        "risks": risks,
        "suggestions": suggestions,
        "factors": {
            "repayment_history": {"score": int(hist_score), "max": 192, "label": repayment_history, "note": hist_note},
            "credit_utilization": {"score": int(util_score), "max": 165, "value": f"{utilization:.1f}%"},
            "debt_burden": {"score": int(dti_score), "max": 83, "value": f"{dti_ratio*100:.1f}% DTI"},
            "account_mix": {"score": int(mix_score), "max": 55, "value": f"{active_accounts} accounts"},
            "enquiries": {"score": int(enq_score), "max": 55, "value": f"{recent_enquiries} enquiries"},
        },
        "disclaimer": DISCLAIMER_TEXT,
    }


class CreditProfileStore:
    def __init__(self, target):
        self.db = Database(target)
        self.db.script([
            f"""CREATE TABLE IF NOT EXISTS credit_profiles (
                    id {self.db.id_column},
                    user_id BIGINT UNIQUE NOT NULL,
                    monthly_income DOUBLE PRECISION NOT NULL,
                    employment_type TEXT NOT NULL,
                    existing_loans INTEGER NOT NULL,
                    monthly_emi DOUBLE PRECISION NOT NULL,
                    credit_card_utilization DOUBLE PRECISION NOT NULL,
                    repayment_history TEXT NOT NULL,
                    active_accounts INTEGER NOT NULL,
                    recent_enquiries INTEGER NOT NULL,
                    credit_health_index INTEGER NOT NULL,
                    health_category TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )""",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_profiles_user ON credit_profiles(user_id)",
        ])

    def get(self, user_id: int) -> Optional[dict]:
        row = self.db.run("SELECT * FROM credit_profiles WHERE user_id = ?", (user_id,), fetch="one")
        if not row:
            return None
        analysis = calculate_credit_health(
            monthly_income=row["monthly_income"],
            employment_type=row["employment_type"],
            existing_loans=row["existing_loans"],
            monthly_emi=row["monthly_emi"],
            credit_card_utilization=row["credit_card_utilization"],
            repayment_history=row["repayment_history"],
            active_accounts=row["active_accounts"],
            recent_enquiries=row["recent_enquiries"],
        )
        return {
            "profile": {
                "monthly_income": row["monthly_income"],
                "employment_type": row["employment_type"],
                "existing_loans": row["existing_loans"],
                "monthly_emi": row["monthly_emi"],
                "credit_card_utilization": row["credit_card_utilization"],
                "repayment_history": row["repayment_history"],
                "active_accounts": row["active_accounts"],
                "recent_enquiries": row["recent_enquiries"],
                "updated_at": row["updated_at"],
            },
            "analysis": analysis,
        }

    def save(self, user_id: int, profile_data: dict) -> dict:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        analysis = calculate_credit_health(
            monthly_income=profile_data["monthly_income"],
            employment_type=profile_data["employment_type"],
            existing_loans=profile_data["existing_loans"],
            monthly_emi=profile_data["monthly_emi"],
            credit_card_utilization=profile_data["credit_card_utilization"],
            repayment_history=profile_data["repayment_history"],
            active_accounts=profile_data["active_accounts"],
            recent_enquiries=profile_data["recent_enquiries"],
        )
        existing = self.db.run("SELECT id FROM credit_profiles WHERE user_id = ?", (user_id,), fetch="one")
        params = (
            profile_data["monthly_income"],
            profile_data["employment_type"],
            profile_data["existing_loans"],
            profile_data["monthly_emi"],
            profile_data["credit_card_utilization"],
            profile_data["repayment_history"],
            profile_data["active_accounts"],
            profile_data["recent_enquiries"],
            analysis["credit_health_index"],
            analysis["category"],
            now,
            user_id,
        )
        if existing:
            self.db.run(
                """UPDATE credit_profiles SET
                    monthly_income = ?, employment_type = ?, existing_loans = ?,
                    monthly_emi = ?, credit_card_utilization = ?, repayment_history = ?,
                    active_accounts = ?, recent_enquiries = ?, credit_health_index = ?,
                    health_category = ?, updated_at = ?
                   WHERE user_id = ?""",
                params,
            )
        else:
            self.db.run(
                """INSERT INTO credit_profiles (
                    monthly_income, employment_type, existing_loans, monthly_emi,
                    credit_card_utilization, repayment_history, active_accounts,
                    recent_enquiries, credit_health_index, health_category, updated_at, user_id
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                params,
            )
        return {"profile": {**profile_data, "updated_at": now}, "analysis": analysis}
