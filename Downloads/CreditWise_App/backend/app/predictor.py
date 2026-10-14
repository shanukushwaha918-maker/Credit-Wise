"""Loads the models exported from credit_wise.ipynb and serves predictions.

Preprocessing mirrors the notebook exactly:
  LabelEncoder(Education_Level) -> OneHotEncoder(drop="first") on 6 columns
  -> column order of the training frame -> StandardScaler -> model.

Explanations are exact decompositions of each model's own decision, not a
separate surrogate model:
  * Gaussian Naive Bayes: log-odds = log prior ratio + sum of per-feature
    log-likelihood ratios  log N(x_i | approved) - log N(x_i | rejected).
  * Logistic Regression: log-odds = intercept + sum coef_i * scaled x_i.
  * KNN: the labels of the 5 nearest training applicants.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ARTIFACTS = Path(__file__).resolve().parents[2] / "model" / "artifacts"
DATASET = Path(__file__).resolve().parents[2] / "data" / "loan_approval_data.csv"

MODEL_LABELS = {
    "naive_bayes": "Gaussian Naive Bayes",
    "logistic_regression": "Logistic Regression",
    "knn": "K-Nearest Neighbors (k=5)",
}

FIELD_LABELS = {
    "Applicant_Income": "Applicant income",
    "Coapplicant_Income": "Co-applicant income",
    "Employment_Status": "Employment status",
    "Age": "Age",
    "Marital_Status": "Marital status",
    "Dependents": "Dependents",
    "Credit_Score": "Credit score",
    "Existing_Loans": "Existing loans",
    "DTI_Ratio": "Debt-to-income ratio",
    "Savings": "Savings",
    "Collateral_Value": "Collateral value",
    "Loan_Amount": "Loan amount",
    "Loan_Term": "Loan term",
    "Loan_Purpose": "Loan purpose",
    "Property_Area": "Property area",
    "Education_Level": "Education level",
    "Gender": "Gender",
    "Employer_Category": "Employer category",
}


class Predictor:
    def __init__(self, artifacts: Path = ARTIFACTS):
        pre = joblib.load(artifacts / "preprocessor.joblib")
        self.edu_le = pre["edu_label_encoder"]
        self.target_le = pre["target_label_encoder"]
        self.ohe = pre["onehot_encoder"]
        self.ohe_cols = pre["onehot_columns"]
        self.scaler = pre["scaler"]
        self.feature_order = pre["feature_order"]
        self.models = {name: joblib.load(artifacts / f"{name}.joblib") for name in MODEL_LABELS}
        self.meta = json.loads((artifacts / "model_meta.json").read_text())
        self.default_model = self.meta["default_model"]
        self.positive_idx = int(np.where(self.target_le.classes_ == "Yes")[0][0])

        # Map each model feature back to the form field it came from.
        self.feature_to_field = {}
        for f in self.feature_order:
            self.feature_to_field[f] = next((c for c in self.ohe_cols if f.startswith(c + "_")), f)

    # ------------------------------------------------------------ preprocess
    def transform(self, applicant: dict) -> np.ndarray:
        df = pd.DataFrame([applicant])
        df["Education_Level"] = self.edu_le.transform(df["Education_Level"])
        encoded = self.ohe.transform(df[self.ohe_cols])
        encoded_df = pd.DataFrame(encoded, columns=self.ohe.get_feature_names_out(self.ohe_cols), index=df.index)
        df = pd.concat([df.drop(columns=self.ohe_cols), encoded_df], axis=1)
        df = df[self.feature_order].astype(float)
        return self.scaler.transform(df)

    # --------------------------------------------------------------- explain
    def _group(self, per_feature: np.ndarray) -> dict:
        grouped = {}
        for f, v in zip(self.feature_order, per_feature):
            field = self.feature_to_field[f]
            grouped[field] = grouped.get(field, 0.0) + float(v)
        return grouped

    def _explain_nb(self, model, x: np.ndarray) -> dict:
        x = x[0]
        pos, neg = self.positive_idx, 1 - self.positive_idx
        # Gaussian log-density per feature for each class (exactly what GaussianNB uses).
        def logpdf(c):
            var = model.var_[c]
            return -0.5 * np.log(2 * np.pi * var) - 0.5 * (x - model.theta_[c]) ** 2 / var
        llr = logpdf(pos) - logpdf(neg)
        base = float(np.log(model.class_prior_[pos]) - np.log(model.class_prior_[neg]))
        return {"method": "naive_bayes_log_likelihood_ratio", "base": base, "contributions": self._group(llr)}

    def _explain_lr(self, model, x: np.ndarray) -> dict:
        sign = 1.0 if model.classes_[1] == self.positive_idx else -1.0
        contrib = sign * model.coef_[0] * x[0]
        base = float(sign * model.intercept_[0])
        return {"method": "logistic_regression_coefficients", "base": base, "contributions": self._group(contrib)}

    def _explain_knn(self, model, x: np.ndarray) -> dict:
        dist, idx = model.kneighbors(x)
        labels = model.classes_[model._y[idx[0]]]
        approved = int((labels == self.positive_idx).sum())
        return {"method": "knn_neighbours", "neighbours": int(len(labels)),
                "approved_neighbours": approved, "distances": [round(float(d), 4) for d in dist[0]]}

    # --------------------------------------------------------------- predict
    def predict(self, applicant: dict, model_name: str) -> dict:
        model = self.models[model_name]
        x = self.transform(applicant)
        proba = model.predict_proba(x)[0]
        pos_col = int(np.where(model.classes_ == self.positive_idx)[0][0])
        p_approve = float(proba[pos_col])
        pred = self.target_le.inverse_transform(model.predict(x))[0]

        if model_name == "naive_bayes":
            explanation = self._explain_nb(model, x)
        elif model_name == "logistic_regression":
            explanation = self._explain_lr(model, x)
        else:
            explanation = self._explain_knn(model, x)

        if "contributions" in explanation:
            items = sorted(explanation["contributions"].items(), key=lambda kv: abs(kv[1]), reverse=True)
            explanation["factors"] = [
                {"field": k, "label": FIELD_LABELS[k], "value": applicant[k], "impact": round(v, 4)}
                for k, v in items
            ]
            del explanation["contributions"]

        return {
            "model": model_name,
            "model_label": MODEL_LABELS[model_name],
            "approved": pred == "Yes",
            "prediction": pred,
            "probability_approved": p_approve,
            "explanation": explanation,
        }

    def sample_row(self, seed=None) -> dict:
        """A random dataset row with no missing values (rows used as-is, never synthesised)."""
        if not hasattr(self, "_complete_rows"):
            self._complete_rows = pd.read_csv(DATASET).dropna().reset_index(drop=True)
        row = self._complete_rows.sample(1, random_state=seed).iloc[0].to_dict()
        for k in ("Dependents", "Existing_Loans", "Loan_Term", "Applicant_ID"):
            row[k] = int(row[k])
        return row

    def data_context(self, applicant: dict) -> list:
        """How applicants with similar key values fared in the training dataset."""
        out = []
        ds = self.meta["dataset"]
        cs = applicant["Credit_Score"]
        for b in ds["credit_score_bins"]:
            lo, hi = (int(v) for v in b["label"].split("-"))
            if lo <= cs <= hi and b["total"]:
                out.append({"field": "Credit_Score", "label": f"Credit score {b['label']}",
                            "total": b["total"], "approved": b["approved"]})
        dti = applicant["DTI_Ratio"]
        for i, b in enumerate(ds["dti_bins"]):
            lo, hi = (float(v) for v in b["label"].split("-"))
            last = i == len(ds["dti_bins"]) - 1
            if (lo <= dti < hi or (last and lo <= dti <= hi)) and b["total"]:
                out.append({"field": "DTI_Ratio", "label": f"DTI ratio {b['label']}",
                            "total": b["total"], "approved": b["approved"]})
        for key, table in (("Employment_Status", "by_employment"), ("Loan_Purpose", "by_purpose")):
            for b in ds[table]:
                if b["label"] == applicant[key] and b["total"]:
                    out.append({"field": key, "label": f"{FIELD_LABELS[key]}: {b['label']}",
                                "total": b["total"], "approved": b["approved"]})
        return out
