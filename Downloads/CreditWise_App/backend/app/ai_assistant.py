"""AI Financial Assistant Module.

Provides intelligent, contextual financial advice, answers loan and credit queries,
and generates personalized financial recommendations.

Supports:
1. Google Gemini API (GEMINI_API_KEY)
2. OpenAI API (OPENAI_API_KEY)
3. Built-in Financial Expert Engine (deterministic rule-based & NLP financial advisor
   that functions 100% offline without external credentials).

Respects user privacy: User profile context is ONLY passed when consent is explicitly granted.
"""
from datetime import datetime, timezone
import json
import logging
import os
import re
from typing import Optional

import httpx

from .db import Database

log = logging.getLogger("creditwise.assistant")

SYSTEM_PROMPT = """You are CreditWise AI, a certified, prudent FinTech financial advisor and credit analyst.
Your mission is to provide clear, actionable, accurate financial guidance on credit scores, loan affordability,
debt repayment strategies, and credit profile improvement.

Guiding Principles:
1. Simplicity: Explain financial concepts in clear, easy-to-understand language.
2. Objectivity: Explain mathematical facts (e.g., compounding interest, DTI limits, amortization).
3. Regulatory Clarity: Always clarify that bureau credit scores (like CIBIL, Experian) come from authorized bureaus,
   while CreditWise's index is an educational statistical estimate.
4. User Privacy: If user profile data is provided, use it constructively to give specific, personalized suggestions.
5. Actionability: Provide step-by-step guidance rather than vague generalities.
"""


def _generate_expert_response(question: str, profile_context: Optional[dict] = None) -> str:
    """Intelligent financial advice engine for offline or fallback operation."""
    q = question.lower()

    # Contextual profile summaries if user consented
    context_str = ""
    if profile_context:
        p = profile_context.get("profile", {})
        a = profile_context.get("analysis", {})
        income = p.get("monthly_income")
        emi = p.get("monthly_emi")
        util = p.get("credit_card_utilization")
        score = a.get("credit_health_index")
        category = a.get("category")
        context_str = (
            f"\n\n*Based on your active CreditWise Profile (Monthly Income: ₹{income:,.0f}, "
            f"EMI: ₹{emi:,.0f}, Card Utilization: {util}%, Credit Health Index: {score} ({category})):*"
        )

    # 1. Credit Score & Bureau questions
    if any(k in q for k in ["credit score", "cibil", "bureau", "experian", "equifax", "how is score calculated"]):
        resp = (
            "**Understanding Credit Scores:**\n\n"
            "A credit score is a 3-digit number (typically ranging from 300 to 900) that reflects your creditworthiness "
            "and likelihood of repaying borrowed money on time.\n\n"
            "**Key Scoring Pillars:**\n"
            "1. **Payment History (35%):** Timely payment of EMIs and credit card bills is the single most influential factor.\n"
            "2. **Credit Utilization Ratio (30%):** The percentage of your credit limit used. Keep it below 30% for optimal scores.\n"
            "3. **Credit History Length (15%):** Older, well-maintained accounts establish a reliable track record.\n"
            "4. **Credit Mix (10%):** A healthy blend of secured loans (home, auto) and unsecured credit (cards, personal loans).\n"
            "5. **New Credit Inquiries (10%):** Too many hard loan applications in a short span signal financial stress.\n\n"
            "> **Important Note:** Official scores are issued by authorized credit bureaus (such as TransUnion CIBIL, Experian, "
            "or Equifax) using your PAN and verified bank reports. The CreditWise Credit Health Index is an educational simulation "
            "to help you plan ahead."
        )
        if profile_context:
            a = profile_context.get("analysis", {})
            resp += f"{context_str}\nYour estimated index is **{a.get('credit_health_index')} ({a.get('category')})**. "
            if a.get("suggestions"):
                resp += f"Key step: {a['suggestions'][0]}"
        return resp

    # 2. Credit Utilization questions
    if any(k in q for k in ["utilization", "credit card limit", "card usage", "30% rule"]):
        resp = (
            "**What is Credit Card Utilization and Why Does it Matter?**\n\n"
            "Credit Utilization Ratio (CUR) is calculated as:\n"
            "`CUR = (Total Outstanding Credit Card Balance / Total Credit Limit) × 100`\n\n"
            "**Why 30% is the Golden Rule:**\n"
            "- Lenders view utilization above 30-40% as a sign of heavy debt reliance.\n"
            "- High utilization depresses your credit score even if you pay the full minimum due on time.\n\n"
            "**Pro Tips to Optimize Utilization:**\n"
            "1. **Pre-bill Payments:** Pay down card balances 2-3 days before the statement generation date so lower balances are reported to bureaus.\n"
            "2. **Request Limit Upgrades:** An increase in your credit limit without higher spending instantly reduces your CUR.\n"
            "3. **Spread Spending:** Divide expenses across multiple cards rather than maxing out a single card."
        )
        if profile_context:
            util = profile_context.get("profile", {}).get("credit_card_utilization", 0)
            resp += f"{context_str}\nYour reported utilization is **{util:.1f}%**. "
            if util > 30:
                resp += "Reducing this below 30% will produce an immediate positive boost in your credit health."
            else:
                resp += "Excellent job keeping your utilization in the recommended safe zone!"
        return resp

    # 3. Debt-to-Income & Loan Affordability
    if any(k in q for k in ["dti", "debt to income", "emi", "how much loan", "eligibility", "afford"]):
        resp = (
            "**Debt-to-Income (DTI) Ratio & Loan Eligibility:**\n\n"
            "Your Debt-to-Income (DTI) ratio measures what portion of your gross monthly earnings goes toward servicing debt:\n"
            "`DTI = (Total Monthly EMIs / Gross Monthly Income) × 100`\n\n"
            "**Lender Benchmarks:**\n"
            "- **Under 35% (Ideal):** Prime borrowing capacity, minimal default risk, and eligibility for lowest interest rates.\n"
            "- **35% – 50% (Moderate):** Manageable, but lenders will scrutinize discretionary expenses and savings buffers.\n"
            "- **Above 50% (High Risk):** Most banks will reject new unsecured applications or require co-borrowers.\n\n"
            "**How to Improve Affordability:**\n"
            "- Opt for longer tenures to reduce monthly EMI burden (though total interest paid will increase).\n"
            "- Clear small existing personal loans or credit card balances before submitting a major home or business loan application."
        )
        if profile_context:
            p = profile_context.get("profile", {})
            income = p.get("monthly_income", 1)
            emi = p.get("monthly_emi", 0)
            dti = (emi / income) * 100
            resp += f"{context_str}\nYour existing monthly commitments represent **{dti:.1f}% DTI**. "
            if dti > 40:
                resp += "We advise consolidating or reducing existing EMIs before taking on new major loan facilities."
        return resp

    # 4. Loan questions: Prepayment vs Tenure vs Interest
    if any(k in q for k in ["prepay", "foreclosure", "tenure", "interest", "fixed vs floating"]):
        return (
            "**Loan Optimization: Prepayment, Tenure & Interest Rates**\n\n"
            "1. **Fixed vs. Floating Rates:**\n"
            "   - **Fixed Rate:** Interest remains locked for the duration. Predictable payments, but usually 1-2% higher than floating.\n"
            "   - **Floating Rate:** Tied to external benchmarks (e.g., RBI repo rate). Adjusts with economic cycles. In India, floating home loans carry zero prepayment penalties by RBI mandate.\n\n"
            "2. **Tenure vs. Total Interest:**\n"
            "   - Longer tenures lower your monthly EMI, which helps pass lender DTI filters.\n"
            "   - However, longer tenures substantially increase cumulative interest. For example, a 20-year home loan at 8.5% costs almost double the borrowed principal in total interest!\n\n"
            "3. **The Power of Prepayments:**\n"
            "   - Paying just one additional EMI each year or increasing your monthly EMI by 5% annually can shorten a 20-year loan by 4-5 years and save lakhs in interest."
        )

    # 5. Financial improvement & Debt relief
    if any(k in q for k in ["improve", "boost", "repair", "suggestions", "how to improve", "tips"]):
        resp = (
            "**Actionable Strategy to Strengthen Your Credit Profile:**\n\n"
            "1. **Never Miss a Due Date:** Automate utility bills and credit payments via auto-debit. A single 30-day delay can drop scores by 50+ points.\n"
            "2. **Reduce Credit Card Balances:** Focus on paying revolving balances down to under 30% (ideally 10%) of your credit limit.\n"
            "3. **Keep Old Credit Accounts Open:** The age of your oldest active account proves long-term credit discipline. Avoid closing older cards.\n"
            "4. **Limit New Inquiries:** Avoid applying for multiple credit cards or instant loans within short windows.\n"
            "5. **Audit Bureau Reports:** Annually check your CIBIL/Experian report for clerical errors, identity fraud, or misreported late payments and file disputes promptly."
        )
        if profile_context:
            a = profile_context.get("analysis", {})
            if a.get("suggestions"):
                resp += f"{context_str}\n**Personalized Next Steps for You:**\n"
                for idx, sug in enumerate(a["suggestions"][:3], 1):
                    resp += f"{idx}. {sug}\n"
        return resp

    # Default general guidance
    resp = (
        f"**CreditWise Financial Advisory:**\n\n"
        f"Regarding your question about **{question.strip()}**:\n\n"
        "In sound financial planning, your decisions should prioritize three sequential tiers:\n"
        "1. **Liquidity & Protection:** Maintain a 3-6 month emergency fund in liquid deposits before aggressive debt pre-payment.\n"
        "2. **Debt Rationalization:** Eliminate high-cost revolving debt (credit cards, personal loans) before long-term low-cost secured debt (home loans).\n"
        "3. **Credit Discipline:** Maintain low credit utilization (<30%) and zero missed repayments to preserve access to prime lender rates."
    )
    if profile_context:
        a = profile_context.get("analysis", {})
        resp += f"{context_str}\nYour estimated Credit Health Index stands at **{a.get('credit_health_index')} ({a.get('category')})**."
    return resp


class AssistantStore:
    def __init__(self, target):
        self.db = Database(target)
        self.db.script([
            f"""CREATE TABLE IF NOT EXISTS chat_messages (
                    id {self.db.id_column},
                    user_id BIGINT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )""",
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages(user_id)",
        ])

    def get_history(self, user_id: int, limit: int = 50) -> list:
        rows = self.db.run(
            "SELECT id, role, content, created_at FROM chat_messages WHERE user_id = ? ORDER BY id ASC LIMIT ?",
            (user_id, limit),
            fetch="all",
        )
        return rows

    def add_message(self, user_id: int, role: str, content: str) -> dict:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        new_id = self.db.run(
            "INSERT INTO chat_messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, role, content, now),
            returning_id=True,
        )
        return {"id": new_id, "role": role, "content": content, "created_at": now}

    def clear(self, user_id: int) -> int:
        return self.db.run("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))


async def generate_assistant_response(
    question: str,
    profile_context: Optional[dict] = None,
    conversation_history: Optional[list] = None,
) -> dict:
    """Dispatches to LLM (Gemini / OpenAI) or built-in financial expert engine."""
    gemini_key = os.environ.get("GEMINI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    # Format profile context if consent was granted
    user_context_block = ""
    if profile_context:
        p = profile_context.get("profile", {})
        a = profile_context.get("analysis", {})
        user_context_block = f"""
USER'S CONSENTED FINANCIAL PROFILE:
- Monthly Income: ₹{p.get('monthly_income', 0):,.0f}
- Employment Type: {p.get('employment_type', 'N/A')}
- Existing Active Loans: {p.get('existing_loans', 0)}
- Monthly EMI Obligations: ₹{p.get('monthly_emi', 0):,.0f}
- Credit Card Utilization: {p.get('credit_card_utilization', 0)}%
- Repayment History: {p.get('repayment_history', 'N/A')}
- Active Credit Accounts: {p.get('active_accounts', 0)}
- Recent Enquiries (6m): {p.get('recent_enquiries', 0)}
- Calculated Credit Health Index: {a.get('credit_health_index', 'N/A')} ({a.get('category', 'N/A')})
- Calculated DTI Ratio: {a.get('dti_percent', 0)}%
"""

    # 1. Try Gemini API if key is configured
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            contents = []
            contents.append({"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n{user_context_block}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I am ready to advise you accurately as CreditWise AI."}]})
            if conversation_history:
                for msg in conversation_history[-6:]:
                    r = "user" if msg["role"] == "user" else "model"
                    contents.append({"role": r, "parts": [{"text": msg["content"]}]})
            contents.append({"role": "user", "parts": [{"text": question}]})

            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, json={"contents": contents})
                if res.status_code == 200:
                    data = res.json()
                    answer = data["candidates"][0]["content"]["parts"][0]["text"]
                    return {"answer": answer, "provider": "gemini", "status": "online"}
        except Exception as e:
            log.warning(f"Gemini API request failed, falling back to expert engine: {e}")

    # 2. Try OpenAI API if key is configured
    if openai_key:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n{user_context_block}"}]
            if conversation_history:
                for msg in conversation_history[-6:]:
                    messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": question})

            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, json={"model": "gpt-4o-mini", "messages": messages}, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    answer = data["choices"][0]["message"]["content"]
                    return {"answer": answer, "provider": "openai", "status": "online"}
        except Exception as e:
            log.warning(f"OpenAI API request failed, falling back to expert engine: {e}")

    # 3. Built-in Expert Engine (Always reliable, 0 downtime, handles questions & profile context)
    fallback_answer = _generate_expert_response(question, profile_context)
    return {
        "answer": fallback_answer,
        "provider": "creditwise_expert_engine",
        "status": "online",
        "note": "Powered by CreditWise FinTech Advisory Engine (Set GEMINI_API_KEY in environment for cloud LLM mode).",
    }
