"""CreditWise FastAPI backend.

Run from the project root:
    python -m uvicorn backend.app.main:app --port 8000
then open http://127.0.0.1:8000
"""
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .auth import AuthStore, EmailTaken, LockedOut
from .history import HistoryStore
from .predictor import FIELD_LABELS, MODEL_LABELS, Predictor
from .schemas import Applicant, LoginRequest, PredictRequest, SignupRequest

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
DB_PATH = Path(os.environ.get("CREDITWISE_DB", ROOT / "backend" / "data" / "history.db"))
SECURE_COOKIES = os.environ.get("CREDITWISE_SECURE_COOKIES") == "1"  # set to 1 when served over HTTPS
COOKIE = "cw_session"

log = logging.getLogger("creditwise")

app = FastAPI(title="CreditWise API", version="1.1.0",
              description="Loan approval predictions served from the models trained in credit_wise.ipynb.")

predictor = Predictor()
history = HistoryStore(DB_PATH)
auth = AuthStore(DB_PATH)

AUTH_LABELS = {"name": "Full name", "email": "Email", "password": "Password", "remember": "Remember me"}


# --------------------------------------------------------------- errors
def _friendly(field: str | None, err: dict) -> str:
    if field == "email" and err["type"] == "string_pattern_mismatch":
        return "Enter a valid email address"
    msg = err["msg"]
    return msg[len("Value error, "):] if msg.startswith("Value error, ") else msg


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    """Return validation errors keyed by field so the form can highlight them."""
    errors = []
    for e in exc.errors():
        loc = [str(p) for p in e["loc"] if p not in ("body", "applicant")]
        field = loc[-1] if loc else None
        errors.append({"field": field, "label": FIELD_LABELS.get(field) or AUTH_LABELS.get(field, field),
                       "message": _friendly(field, e)})
    return JSONResponse(status_code=422, content={"detail": "Invalid input", "errors": errors})


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": "Internal server error while processing the request."})


@app.middleware("http")
async def same_origin_writes(request: Request, call_next):
    """CSRF defence: state-changing API calls must come from this site's own pages."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse(status_code=403, content={"detail": "Cross-site request blocked."})
    return await call_next(request)


# ----------------------------------------------------------------- auth
def current_user(request: Request) -> dict:
    user = auth.user_for_token(request.cookies.get(COOKIE))
    if not user:
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    return user


def _start_session(response: Response, user: dict, remember: bool):
    token, max_age = auth.create_session(user["id"], remember)
    response.set_cookie(COOKIE, token, max_age=max_age, httponly=True, samesite="lax",
                        secure=SECURE_COOKIES, path="/")


@app.post("/api/auth/signup", status_code=201)
def signup(req: SignupRequest, response: Response):
    try:
        user = auth.create_user(req.name, req.email, req.password)
    except EmailTaken:
        return JSONResponse(status_code=409, content={
            "detail": "An account with this email already exists.",
            "errors": [{"field": "email", "label": "Email", "message": "An account with this email already exists"}]})
    _start_session(response, user, remember=False)
    return {"user": user}


@app.post("/api/auth/login")
def login(req: LoginRequest, response: Response):
    try:
        user = auth.authenticate(req.email, req.password)
    except LockedOut as e:
        return JSONResponse(status_code=429, headers={"Retry-After": str(e.retry_after)}, content={
            "detail": f"Too many failed attempts. Try again in {e.retry_after} seconds."})
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Incorrect email or password."})
    _start_session(response, user, req.remember)
    return {"user": user}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    auth.delete_session(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="lax", secure=SECURE_COOKIES)
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    return {"user": user}


# ------------------------------------------------------------------ API
def range_warnings(applicant: dict) -> list:
    """Flag values outside what the model saw in training (predictions there are extrapolations)."""
    out = []
    for field, r in predictor.meta["numeric_ranges"].items():
        v = applicant[field]
        if v < r["min"] or v > r["max"]:
            out.append({"field": field, "label": FIELD_LABELS[field],
                        "message": f"{FIELD_LABELS[field]} {v:g} is outside the training data range "
                                   f"({r['min']:g} – {r['max']:g}); treat this prediction with caution."})
    return out


@app.get("/api/health")
def health():
    return {"status": "ok", "models_loaded": list(predictor.models)}


api = APIRouter(prefix="/api", dependencies=[Depends(current_user)])


@api.get("/meta")
def meta():
    m = predictor.meta
    return {
        "default_model": m["default_model"],
        "models": [{"id": k, "label": v, "metrics": m["metrics"][k]} for k, v in MODEL_LABELS.items()],
        "test_size": m["test_size"],
        "train_size": m["train_size"],
        "categories": m["categories"],
        "numeric_ranges": m["numeric_ranges"],
        "field_labels": FIELD_LABELS,
        "dataset": m["dataset"],
        "sklearn_version": m["sklearn_version"],
        "exported_at": m["exported_at"],
    }


@api.post("/predict")
def predict(req: PredictRequest, user: dict = Depends(current_user)):
    applicant = req.applicant.model_dump()
    model_name = req.model or predictor.default_model
    result = predictor.predict(applicant, model_name)
    # Every notebook model on the same input, for side-by-side comparison.
    result["comparison"] = [
        {k: r[k] for k in ("model", "model_label", "prediction", "approved", "probability_approved")}
        for r in (predictor.predict(applicant, name) if name != model_name else result
                  for name in MODEL_LABELS)
    ]
    result["data_context"] = predictor.data_context(applicant)
    result["warnings"] = range_warnings(applicant)
    if req.save:
        result["history"] = history.add(user["id"], model_name, result["prediction"], result["probability_approved"], applicant)
    return result


@api.get("/history")
def list_history(limit: int = Query(200, ge=1, le=1000), user: dict = Depends(current_user)):
    return {"items": history.list(user["id"], limit)}


@api.delete("/history/{item_id}")
def delete_history(item_id: int, user: dict = Depends(current_user)):
    if not history.delete(user["id"], item_id):
        raise HTTPException(status_code=404, detail="History entry not found.")
    return {"deleted": item_id}


@api.delete("/history")
def clear_history(user: dict = Depends(current_user)):
    return {"deleted": history.clear(user["id"])}


@api.get("/sample")
def sample(seed: int | None = None):
    """A real, complete applicant row from the dataset, with its recorded outcome."""
    row = predictor.sample_row(seed)
    return {"applicant_id": row.pop("Applicant_ID"), "actual_outcome": row.pop("Loan_Approved"), "applicant": row}


@api.get("/schema/applicant")
def applicant_schema():
    return Applicant.model_json_schema()


app.include_router(api)


# ------------------------------------------------------------- frontend
app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND / "index.html")
