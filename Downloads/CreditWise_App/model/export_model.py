"""
Export the models trained in credit_wise.ipynb.

The notebook never saved its trained objects (they only lived in the Jupyter
kernel), so this script replays the notebook's cells *verbatim* -- same
imputers, encoders, split (random_state=42), scaler and model hyper-parameters --
and then checks that the resulting test-set metrics are identical to the ones
printed in the notebook. If they do not match, the export aborts.

Nothing about the model logic is changed. Every fitted object is persisted so
the web backend can reproduce the exact preprocessing at inference time.

Usage:
    python model/export_model.py [path/to/loan_approval_data.csv]
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score)
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "loan_approval_data.csv"
OUT = ROOT / "model" / "artifacts"

# Metrics exactly as printed in credit_wise.ipynb ("Train & Evaluate Models").
NOTEBOOK_METRICS = {
    "logistic_regression": {"precision": 0.7833333333333333, "recall": 0.7704918032786885,
                            "f1": 0.7768595041322314, "accuracy": 0.865,
                            "confusion_matrix": [[126, 13], [14, 47]]},
    "knn": {"precision": 0.6274509803921569, "recall": 0.5245901639344263,
            "f1": 0.5714285714285714, "accuracy": 0.76,
            "confusion_matrix": [[120, 19], [29, 32]]},
    "naive_bayes": {"precision": 0.8035714285714286, "recall": 0.7377049180327869,
                    "f1": 0.7692307692307693, "accuracy": 0.865,
                    "confusion_matrix": [[128, 11], [16, 45]]},
}

# ---------------------------------------------------------------- notebook cells
df = pd.read_csv(DATA)
raw_df = df.copy()

# Handle Missing Values
categorical_cols = df.select_dtypes(include=["object"]).columns
numerical_cols = df.select_dtypes(include=["number"]).columns

num_imp = SimpleImputer(strategy="mean")
df[numerical_cols] = num_imp.fit_transform(df[numerical_cols])

cat_imp = SimpleImputer(strategy="most_frequent")
df[categorical_cols] = cat_imp.fit_transform(df[categorical_cols])

# Remove Applicant Id
df = df.drop("Applicant_ID", axis=1)

# Encoding (the notebook reuses one LabelEncoder; we keep one per column so both
# fitted mappings survive -- LabelEncoder is deterministic, so the result is identical)
edu_le = LabelEncoder()
df["Education_Level"] = edu_le.fit_transform(df["Education_Level"])
target_le = LabelEncoder()
df["Loan_Approved"] = target_le.fit_transform(df["Loan_Approved"])

cols = ["Employment_Status", "Marital_Status", "Loan_Purpose", "Property_Area", "Gender", "Employer_Category"]
ohe = OneHotEncoder(drop="first", sparse_output=False, handle_unknown="ignore")
encoded = ohe.fit_transform(df[cols])
encoded_df = pd.DataFrame(encoded, columns=ohe.get_feature_names_out(cols), index=df.index)
df = pd.concat([df.drop(columns=cols), encoded_df], axis=1)

# Train-Test-Split + Feature Scaling
X = df.drop("Loan_Approved", axis=1)
y = df["Loan_Approved"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Train & Evaluate Models
models = {
    "logistic_regression": LogisticRegression(),
    "knn": KNeighborsClassifier(n_neighbors=5),
    "naive_bayes": GaussianNB(),
}
# ------------------------------------------------------------ end notebook cells

metrics = {}
for name, model in models.items():
    model.fit(X_train_scaled, y_train)
    y_pred = model.predict(X_test_scaled)
    metrics[name] = {
        "precision": float(precision_score(y_test, y_pred)),
        "recall": float(recall_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred)),
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
    }

# ------------------------------------------------ verify against the notebook
mismatches = []
for name, expected in NOTEBOOK_METRICS.items():
    got = metrics[name]
    for key, val in expected.items():
        same = got[key] == val if key == "confusion_matrix" else np.isclose(got[key], val, atol=1e-12)
        if not same:
            mismatches.append(f"{name}.{key}: notebook={val} replay={got[key]}")
if mismatches:
    print("ERROR: replayed models do not match the notebook output:")
    print("\n".join("  " + m for m in mismatches))
    sys.exit(1)
print("Verified: all 3 models reproduce the notebook metrics exactly.")

# ------------------------------------------------------------------- persist
OUT.mkdir(parents=True, exist_ok=True)
joblib.dump({
    "edu_label_encoder": edu_le,
    "target_label_encoder": target_le,
    "onehot_encoder": ohe,
    "onehot_columns": cols,
    "scaler": scaler,
    "feature_order": list(X.columns),
}, OUT / "preprocessor.joblib")
for name, model in models.items():
    joblib.dump(model, OUT / f"{name}.joblib")

# Allowed values for the form = the categories the encoders were fitted on.
categories = {c: [str(v) for v in cats] for c, cats in zip(cols, ohe.categories_)}
categories["Education_Level"] = [str(v) for v in edu_le.classes_]

numeric_features = ["Applicant_Income", "Coapplicant_Income", "Age", "Dependents", "Credit_Score",
                    "Existing_Loans", "DTI_Ratio", "Savings", "Collateral_Value", "Loan_Amount", "Loan_Term"]
# Observed ranges in the raw dataset (used for input validation / form hints).
ranges = {c: {"min": float(raw_df[c].min()), "max": float(raw_df[c].max()),
              "mean": float(raw_df[c].mean())} for c in numeric_features}

# Dataset summaries for the dashboard (computed from raw rows with a known label).
labelled = raw_df.dropna(subset=["Loan_Approved"])
approved = labelled["Loan_Approved"] == "Yes"
bins = list(range(550, 801, 25))
cs = labelled.dropna(subset=["Credit_Score"])
cs_bin = pd.cut(cs["Credit_Score"], bins=bins, right=False, include_lowest=True)
dti = labelled.dropna(subset=["DTI_Ratio"])
dti_bins = [0.1, 0.2, 0.3, 0.4, 0.5, 0.61]
dti_bin = pd.cut(dti["DTI_Ratio"], bins=dti_bins, right=False)

def rate_table(frame, key):
    g = frame.groupby(key, observed=False)["Loan_Approved"]
    return [{"label": str(k), "total": int(len(v)), "approved": int((v == "Yes").sum())} for k, v in g]

dataset_stats = {
    "rows": int(len(raw_df)),
    "labelled_rows": int(len(labelled)),
    "missing_cells": int(raw_df.isnull().sum().sum()),
    "approved": int(approved.sum()),
    "rejected": int((~approved).sum()),
    "credit_score_bins": [{"label": f"{int(i.left)}-{int(i.right) - 1}", "total": int(len(v)),
                           "approved": int((v == "Yes").sum())}
                          for i, v in cs.groupby(cs_bin, observed=False)["Loan_Approved"]],
    "dti_bins": [{"label": f"{i.left:.1f}-{min(i.right, 0.6):.1f}", "total": int(len(v)),
                  "approved": int((v == "Yes").sum())}
                 for i, v in dti.groupby(dti_bin, observed=False)["Loan_Approved"]],
    "by_employment": rate_table(labelled.dropna(subset=["Employment_Status"]), "Employment_Status"),
    "by_purpose": rate_table(labelled.dropna(subset=["Loan_Purpose"]), "Loan_Purpose"),
}

meta = {
    "exported_at": datetime.now(timezone.utc).isoformat(),
    "sklearn_version": sklearn.__version__,
    "source_notebook": "credit_wise.ipynb",
    "default_model": "naive_bayes",  # notebook: "Best Model on the basis of Precision => Naive Bayes"
    "positive_class": "Yes",
    "test_size": int(len(y_test)),
    "train_size": int(len(y_train)),
    "metrics": metrics,
    "categories": categories,
    "numeric_ranges": ranges,
    "dataset": dataset_stats,
}
(OUT / "model_meta.json").write_text(json.dumps(meta, indent=2))
print(f"Saved artifacts to {OUT}")
