# CreditWise: Loan Approval Web App

A web application built on the machine-learning work in **`credit_wise.ipynb`**.
A FastAPI backend serves predictions from the notebook's trained models, and a
responsive dashboard shows the predictions, explains them, compares the models
and keeps a prediction history.

---

## How the notebook's model is reused

The notebook never saved its trained models (they existed only inside the Jupyter
kernel). `model/export_model.py` therefore **replays the notebook's cells exactly**:
the same imputers, encoders, `train_test_split(test_size=0.2, random_state=42)`,
`StandardScaler` and model settings. It then **checks the result against the metrics
the notebook printed**. If any precision, recall, F1, accuracy or confusion-matrix
value differs, the export stops with an error. Every step is deterministic, so the
exported models are identical to the ones trained in the notebook.

| Notebook step | Re-used as |
|---|---|
| `SimpleImputer` (mean / most frequent) | Applied before training, as in the notebook. The app requires every field, so nothing is imputed at prediction time |
| `LabelEncoder` on `Education_Level` | `preprocessor.joblib` → `edu_label_encoder` |
| `OneHotEncoder(drop="first")` on 6 columns | `preprocessor.joblib` → `onehot_encoder` |
| Column order of `X` | `preprocessor.joblib` → `feature_order` |
| `StandardScaler` | `preprocessor.joblib` → `scaler` |
| `GaussianNB()` (the notebook's pick: "Best Model on the basis of Precision") | `naive_bayes.joblib`, the **default model** |
| `LogisticRegression()` | `logistic_regression.joblib` |
| `KNeighborsClassifier(n_neighbors=5)` | `knn.joblib` |

**Target:** `Loan_Approved` (Yes/No). **Inputs (18):** Applicant_Income, Coapplicant_Income,
Employment_Status, Age, Marital_Status, Dependents, Credit_Score, Existing_Loans, DTI_Ratio,
Savings, Collateral_Value, Loan_Amount, Loan_Term, Loan_Purpose, Property_Area,
Education_Level, Gender, Employer_Category.

Verified test-set results (200 applicants), identical to the notebook:

| Model | Precision | Recall | F1 | Accuracy |
|---|---|---|---|---|
| Gaussian Naive Bayes | 80.4% | 73.8% | 76.9% | 86.5% |
| Logistic Regression | 78.3% | 77.0% | 77.7% | 86.5% |
| KNN (k=5) | 62.7% | 52.5% | 57.1% | 76.0% |

**About the notebook's "Feature Engineering" section.** It is not exported. Its printed
results come from a kernel that still held an `Applicant_Income_log` column, but the line
that creates that column is commented out. Those numbers therefore can't be reproduced
from the notebook as written. Tell me which version you want, and it can be added as a
fourth model.

### How predictions are explained

The explanations come from each model's own calculation, not from a separate
approximating model:

- **Naive Bayes:** log-odds of approval = log prior ratio + Σ per-feature log-likelihood
  ratios. The factor chart shows those terms, grouped back to the 18 form fields.
- **Logistic Regression:** log-odds = intercept + Σ coefficient × scaled value.
- **KNN:** shows how many of the 5 nearest training applicants were approved.

The tests confirm that the factors add up to the model's own log-odds.

---

## Features

The interface is a navy/blue fintech-style dashboard: a navy sidebar, a sticky top bar
with breadcrumbs, and a page header with actions on every page.

- **Dashboard:** KPI cards with icons and progress bars, all computed from API data:
  - dataset size, with the share of rows that have a recorded outcome
  - historical approval rate
  - the default model's accuracy ("173 of 200 correct")
  - its precision ("45 of 56 predicted approvals were right")

  Below them:
  - insights computed from the data, such as "no applicant with a credit score below
    650 was approved"
  - approval-rate charts by credit score and DTI (with labelled cutoff markers), by
    employment status and by loan purpose
  - a model leaderboard and your 5 most recent predictions

  Every chart has a hover tooltip and a table view.
- **New prediction:** an 18-field form in four numbered sections, with per-section
  counters and an overall progress ring. Dropdown options come from the encoders, hints
  show the range seen in training, and fields are checked as you type. Choose the model
  from cards that show each model's metrics. **"Load a real applicant"** fills the form
  with a real dataset row and then shows whether the model agrees with the recorded
  outcome.
- **Result panel:** an animated probability gauge with the 50% decision threshold, the
  verdict, and three tabs:
  - **Explanation:** key reasons plus a factor-contribution chart
  - **Compare models:** all three models on the same applicant
  - **Similar applicants:** approval rates for similar applicants in the dataset

  It also warns when an input falls outside the training range.
- **History:** stored in SQLite (`backend/data/history.db`). The page has:
  - summary KPIs
  - search across ID, model, outcome, purpose, employment, area and date
  - filters by model and outcome, sorting by date or probability, and pagination
  - **CSV export** of the filtered rows with every input
  - delete, clear all, and re-open a prediction in the form

  Loading, error, empty and no-match states are all handled.
- **Model performance:** a comparison card for each model (accuracy, precision, recall,
  F1, confusion-matrix counts, best-in-class badges), a grouped metric chart, a
  confusion matrix with correct and misclassified totals, a metrics table, and a guide
  to reading the metrics.
- **Error handling:** inputs are checked in the browser and again on the server, using
  the same JSON schema. Server-side validation errors appear next to the field they
  belong to. Loading states, timeouts and offline API failures each get their own
  message with a Retry button. The API status indicator updates live.
- A light/dark theme switch that remembers your choice and follows your OS setting on
  first visit. The layout adapts to laptop, tablet (slide-out sidebar) and phone. No
  internet connection is needed (no CDN, fonts or libraries); the charts are
  hand-written SVG in `frontend/assets/charts.js`.

---

## Accounts and security

The app opens on a **login / sign-up** page. Every page and every data endpoint
requires an account; only `/api/health` is public.

- **Sign up** with a name, email and password. The password needs at least 8
  characters, with at least one letter and one number. A strength meter and a rule
  checklist update as you type. Signing up logs you straight in.
- **Log in** with "Keep me logged in for 30 days". Without it, the session ends when
  the browser closes (or after 12 hours).
- **Log out** from the account menu (top right) or the sidebar.
- If your session ends while you're using the app, you're sent back to the login page.
  After logging in again you return to the page you were on.
- **Prediction history is private.** Each user only sees, exports and deletes their own
  predictions.

How it's implemented (standard library only, no extra packages):

| Concern | Approach |
|---|---|
| Password storage | `scrypt` (n=2^14, r=8, p=1) with a random 16-byte salt per user, so passwords are never stored or logged in plain text |
| Sessions | 256-bit random token in an `HttpOnly`, `SameSite=Lax` cookie. Only a SHA-256 hash of the token is stored, and logout revokes it on the server |
| Brute force | 5 failed logins for an email lock further attempts for 60 seconds (HTTP 429) |
| Account enumeration | Unknown email and wrong password return the same message and take the same time |
| Cross-site requests | State-changing API calls from another origin are rejected (HTTP 403) |
| Storage | Tables `users`, `sessions` and `predictions` in `backend/data/history.db` |

If you deploy behind HTTPS, set `CREDITWISE_SECURE_COOKIES=1` so the session cookie is
marked `Secure`. There's no password-reset email flow, because the app has no mail
server. To reset a password locally, delete the user's row from the `users` table and
sign up again.

---

## Setup on Windows

Requires **Python 3.10+**. In Command Prompt or PowerShell:

```bat
cd "%USERPROFILE%\Downloads\CreditWise_App"
setup.bat
```

`setup.bat` creates a `.venv` virtual environment and installs `requirements.txt`.

<details><summary>Manual setup (equivalent)</summary>

```bat
cd "%USERPROFILE%\Downloads\CreditWise_App"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
</details>

## Run

```bat
run.bat
```

This starts the server and opens **http://127.0.0.1:8000** in your browser. Press `Ctrl+C`
to stop. To run it manually instead:

```bat
.venv\Scripts\activate
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Interactive API docs are at **http://127.0.0.1:8000/docs**.

## Re-exporting the model

The exported files are already in `model/artifacts/`. Re-export only if you change the
dataset or upgrade scikit-learn:

```bat
python model\export_model.py
```

> scikit-learn must be the same version when exporting and when serving (currently
> **1.9.0**; it is recorded in `model/artifacts/model_meta.json`). After changing the
> version, re-export.

---

## Tests

```bat
pip install -r requirements-dev.txt
python -m pytest -q
```

31 backend tests cover:
- the served models reproduce the notebook's confusion matrices on its exact test split
- explanations add up to the model log-odds
- validation (out-of-range values, wrong types, unknown categories, missing fields,
  unknown model)
- dataset samples are real rows
- the out-of-range warning
- the full history cycle (add, list, delete, 404 on a repeat delete)
- the frontend files are served
- accounts (`tests/test_auth.py`):
  - every data endpoint requires login
  - signup sets an HttpOnly cookie and passwords are stored hashed
  - duplicate emails are rejected regardless of letter case
  - validation messages
  - login, logout (with server-side token revocation) and remember-me cookie lifetimes
  - the failed-login lockout
  - history privacy between users
  - cross-site request blocking

**Browser end-to-end test.** This drives your installed Google Chrome. Start a server
with a throwaway history database first, so the test doesn't add entries to your real
history:

```bat
set CREDITWISE_DB=%TEMP%\cw_test.db
python -m uvicorn backend.app.main:app --port 8765
REM in a second terminal:
python tests\e2e_browser.py http://127.0.0.1:8765
```

It checks the account flows (redirect to login, validation, password strength, sign-up,
logout, duplicate email, login with remember-me), the dashboard, theme toggle, form validation, predictions with every model
(compared against the API value), the extrapolation warning, network-failure and retry
handling, server-side 422 errors, history actions, the model page and the mobile layout.
Screenshots are saved to `tests/screenshots/`.

---

## API

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/signup` | `{"name", "email", "password"}` → creates the account and logs in (public) |
| POST | `/api/auth/login` | `{"email", "password", "remember"}` → starts a session (public) |
| POST | `/api/auth/logout` | Ends the current session |
| GET | `/api/auth/me` | The logged-in user |
| GET | `/api/health` | Status and loaded models (public) |
| GET | `/api/meta` | Model metrics, category options, training ranges, dataset summaries |
| GET | `/api/schema/applicant` | JSON schema of an application (used for form validation) |
| POST | `/api/predict` | `{"applicant": {...18 fields}, "model": "naive_bayes" \| "logistic_regression" \| "knn", "save": true}` |
| GET | `/api/sample` | A real, complete applicant row from the dataset, with its recorded outcome |
| GET | `/api/history` | Saved predictions (newest first) |
| DELETE | `/api/history/{id}` · `/api/history` | Delete one saved prediction, or all of them |

All endpoints except those marked *public* return **401** without a valid session.

## Project layout

```
CreditWise_App/
├── data/loan_approval_data.csv     copy of your dataset (original left untouched)
├── model/
│   ├── export_model.py             replays the notebook and verifies the metrics
│   └── artifacts/                  preprocessor + 3 models + model_meta.json
├── backend/app/
│   ├── main.py                     FastAPI app, routes, error handling
│   ├── predictor.py                preprocessing, inference, explanations
│   ├── schemas.py                  input validation (applications, signup, login)
│   ├── auth.py                     accounts, password hashing, sessions, lockout
│   └── history.py                  per-user SQLite prediction history
├── frontend/                       index.html + assets (styles.css, auth.css, app.js, charts.js)
├── tests/                          pytest API tests + Playwright browser test
├── setup.bat · run.bat
└── requirements.txt · requirements-dev.txt
```

## Notes and limitations

- The dataset has 1,000 rows. With 200 test applicants, a 1-point metric difference is
  about 2 applicants, so the gaps between Naive Bayes and Logistic Regression are small.
- As in the notebook, 50 rows with no recorded outcome were filled with "No" before
  training. That is why the model's starting approval rate (29.6%) differs from the
  dashboard's historical rate (31.4%), which uses only rows with a recorded outcome.
- Gaussian Naive Bayes reacts strongly to values far outside the training range. For
  example, an income of 95,000 (training maximum 19,988) can push the approval
  probability close to 0%. The app warns whenever an input is out of range.
- `Gender` is one of the model's inputs because the notebook trained on it. In real
  lending this raises fairness and legal concerns.
- Predictions are statistical estimates, not lending decisions.
