"""Browser end-to-end test (drives the installed Google Chrome via Playwright).

Start the server with a throwaway history DB first, then:
    set CREDITWISE_DB=%TEMP%\\cw_test.db
    python -m uvicorn backend.app.main:app --port 8765
    python tests\\e2e_browser.py http://127.0.0.1:8765 [screenshot_dir]
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
SHOTS = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)

errors = []


def step(msg):
    print("  [ok]", msg)


def form_values(page):
    return page.evaluate("""() => {
        const o = {};
        document.querySelectorAll('#form-fields input, #form-fields select').forEach(i => {
            o[i.name] = i.tagName === 'SELECT' ? i.value : Number(i.value); });
        return o; }""")


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 960}, accept_downloads=True)
    page = ctx.new_page()
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("dialog", lambda d: d.accept())
    page.add_init_script("if (!sessionStorage.getItem('init')) { localStorage.setItem('cw-theme', 'light'); sessionStorage.setItem('init', '1'); }")

    # ------------------------------------------------------------ accounts
    email, password = f"e2e-{int(time.time())}@example.com", "Tester2026!"
    page.goto(BASE + "/#history")
    expect(page).to_have_url(BASE + "/#login")
    expect(page.locator("#login-form")).to_be_visible()
    expect(page.locator("#app-shell")).to_be_hidden()
    assert page.request.get(BASE + "/api/meta").status == 401
    page.screenshot(path=SHOTS / "00_login.png")
    page.locator("#login-btn").click()
    expect(page.locator('[data-afield="login-email"] .field-error')).to_have_text("Enter your email")
    page.fill("#login-email", "nobody@example.com")
    page.fill("#login-password", "wrongpass1")
    page.locator("#login-btn").click()
    expect(page.locator("#login-alert")).to_contain_text("Incorrect email or password")
    step("unauthenticated: deep link redirects to login, API returns 401, login validation + wrong credentials")

    page.locator('#login-form a[href="#signup"]').click()
    expect(page.locator("#signup-form")).to_be_visible()
    page.locator("#signup-btn").click()
    expect(page.locator("#signup-form .field.invalid")).to_have_count(4)
    page.fill("#signup-name", "E2E Tester")
    page.fill("#signup-email", "bad-email")
    page.fill("#signup-password", "abc")
    expect(page.locator("#pw-label")).to_have_text("Weak")
    expect(page.locator('#pw-rules [data-rule="letter"]')).to_have_class("ok")
    page.fill("#signup-password", password)
    expect(page.locator("#pw-label")).to_have_text("Good")
    expect(page.locator("#pw-rules li.ok")).to_have_count(3)
    page.fill("#signup-confirm", "different1")
    page.locator('.pw-toggle[data-target="signup-password"]').click()
    expect(page.locator("#signup-password")).to_have_attribute("type", "text")
    page.locator("#signup-btn").click()
    expect(page.locator('[data-afield="signup-email"] .field-error')).to_have_text("Enter a valid email address")
    expect(page.locator('[data-afield="signup-confirm"] .field-error')).to_have_text("Passwords don't match")
    page.screenshot(path=SHOTS / "00_signup.png")
    page.fill("#signup-email", email)
    page.fill("#signup-confirm", password)
    page.locator("#signup-btn").click()
    expect(page).to_have_url(BASE + "/#history")
    expect(page.locator("#app-shell")).to_be_visible()
    expect(page.locator("#sidebar-user-name")).to_have_text("E2E Tester")
    expect(page.locator("#topbar-avatar")).to_have_text("ET")
    step("signup: validation, strength meter + rules, show password, account created, lands on the deep-linked page")

    page.locator("#user-btn").click()
    expect(page.locator("#user-dropdown")).to_be_visible()
    expect(page.locator("#menu-user-email")).to_have_text(email)
    page.screenshot(path=SHOTS / "00_user_menu.png")
    page.locator("#user-dropdown [data-logout]").click()
    expect(page).to_have_url(BASE + "/#login")
    expect(page.locator("#login-form")).to_be_visible()
    assert page.request.get(BASE + "/api/meta").status == 401

    page.locator('#login-form a[href="#signup"]').click()
    page.fill("#signup-name", "Someone Else")
    page.fill("#signup-email", email.upper())
    page.fill("#signup-password", password)
    page.fill("#signup-confirm", password)
    page.locator("#signup-btn").click()
    expect(page.locator('[data-afield="signup-email"] .field-error')).to_contain_text("already exists")
    page.locator('#signup-form a[href="#login"]').click()
    page.fill("#login-email", email)
    page.fill("#login-password", password)
    page.locator("#login-remember").check(force=True)
    page.locator("#login-btn").click()
    expect(page.locator("#app-shell")).to_be_visible()
    expect(page).to_have_url(BASE + "/#dashboard")
    page.reload()
    expect(page.locator("#app-shell")).to_be_visible()
    expect(page.locator("#sidebar-user-name")).to_have_text("E2E Tester")
    step("user menu + logout (API locked again), duplicate email rejected, login with remember-me, session survives reload")

    page.request.delete(BASE + "/api/history")

    # ------------------------------------------------------------ navigation
    page.goto(BASE + "/")
    expect(page.locator("#api-status")).to_have_attribute("data-state", "ok")
    for view, title in [("models", "Model performance"), ("predict", "New prediction"),
                        ("history", "Prediction history"), ("dashboard", "Dashboard")]:
        page.locator(f'.nav-link[data-view="{view}"]').click()
        expect(page).to_have_url(f"{BASE}/#{view}")
        expect(page.locator("#view-title")).to_have_text(title)
        expect(page.locator("#crumb-current")).to_have_text(title)
        expect(page.locator(f"#view-{view}")).to_be_visible()
        expect(page.locator(f'.nav-link[data-view="{view}"]')).to_have_class("nav-link active")
    step("sidebar navigation: all 4 pages, titles, breadcrumb, active state")

    # ------------------------------------------------------------ dashboard
    expect(page.locator("#dash-kpis .kpi")).to_have_count(4)
    expect(page.locator("#dash-kpis .kpi-value").first).to_have_text("1,000")
    expect(page.locator("#dash-kpis .kpi-value").nth(2)).to_have_text("86.5%")
    expect(page.locator("#dash-kpis .kpi-foot").nth(2)).to_contain_text("173 of 200")
    expect(page.locator("#dash-insights .insight")).to_have_count(3)
    for cid in ("credit", "dti", "employment", "purpose"):
        expect(page.locator(f"#chart-{cid} svg path.mark:not([d=''])").first).to_be_visible()
    expect(page.locator("#chart-credit .threshold-tag")).to_have_text("650 cutoff")
    expect(page.locator(".mini-model")).to_have_count(3)
    expect(page.locator("#dash-recent")).to_contain_text("No predictions yet")
    page.locator("#chart-credit .hit").nth(6).hover()
    expect(page.locator("#tooltip")).to_be_visible()
    expect(page.locator("#tooltip")).to_contain_text("47 of 100")
    page.screenshot(path=SHOTS / "01_dashboard_light.png", full_page=True)
    page.mouse.move(5, 5)
    page.locator("#chart-credit .chart-toggle").click()
    expect(page.locator("#chart-credit table tbody tr")).to_have_count(10)
    page.locator("#chart-credit .chart-toggle").click()
    expect(page.locator("#chart-credit .chart svg")).to_be_visible()
    step("dashboard: KPIs from API, insights, 4 charts, cutoff marker, tooltip, table toggle, leaderboard, empty recent list")

    # ------------------------------------------------------------ theme
    page.locator("#theme-toggle").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(page.locator("#theme-toggle")).to_have_attribute("aria-checked", "true")
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(page.locator("#api-status")).to_have_attribute("data-state", "ok")
    page.wait_for_timeout(400)
    page.screenshot(path=SHOTS / "02_dashboard_dark.png", full_page=True)
    page.locator("#theme-toggle").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    step("theme toggle switches, sets aria-checked, persists across reload")

    # ------------------------------------------------------------ predict: validation
    page.locator('.page-actions a[href="#predict"]').click()
    expect(page.locator("#f-Credit_Score")).to_be_visible()
    expect(page.locator("#result")).to_contain_text("Ready to assess")
    page.locator("#predict-btn").click()
    expect(page.locator("#form-errors")).to_be_visible()
    expect(page.locator(".field.invalid")).to_have_count(18)
    page.fill("#f-Credit_Score", "1200")
    page.locator("#f-Credit_Score").blur()
    expect(page.locator("#f-Credit_Score-err")).to_contain_text("at most 900")
    page.fill("#f-Dependents", "1.5")
    page.locator("#f-Dependents").blur()
    expect(page.locator("#f-Dependents-err")).to_contain_text("whole number")
    expect(page.locator("#form-progress-text")).to_have_text("2/18")
    page.screenshot(path=SHOTS / "03_validation.png", full_page=True)
    step("validation: all 18 required, range + integer checks, progress counter")

    # ------------------------------------------------------------ predict: real applicant
    page.locator("#reset-btn").click()
    expect(page.locator("#form-progress-text")).to_have_text("0/18")
    page.locator('[data-action="sample"]').click()
    expect(page.locator("#sample-note")).to_contain_text("Recorded outcome")
    expect(page.locator("#form-progress-text")).to_have_text("18/18")
    expect(page.locator(".form-section.complete")).to_have_count(4)
    page.locator("#predict-btn").click()
    expect(page.locator(".result-hero")).to_be_visible()
    shown = page.locator(".gauge-value").inner_text()
    api = page.request.post(BASE + "/api/predict", data={"applicant": form_values(page), "model": "naive_bayes", "save": False}).json()
    assert shown == f"{api['probability_approved'] * 100:.1f}%", (shown, api["probability_approved"])
    expect(page.locator(".verdict")).to_have_text("Likely approved" if api["approved"] else "Likely rejected")
    expect(page.locator("#result .banner")).to_contain_text("actually")
    expect(page.locator("#factor-chart svg path.mark")).to_have_count(8)
    page.locator("#factors-all").click()
    expect(page.locator("#factor-chart svg path.mark")).to_have_count(18)
    page.locator('.tab[data-tab="compare"]').click()
    expect(page.locator(".compare-row")).to_have_count(3)
    for i, c in enumerate(api["comparison"]):
        expect(page.locator(".compare-row").nth(i)).to_contain_text(f"{round(c['probability_approved'] * 100)}%")
    page.locator('.tab[data-tab="context"]').click()
    expect(page.locator(".context-row").first).to_be_visible()
    page.locator('.tab[data-tab="explain"]').click()
    page.wait_for_timeout(1100)
    page.screenshot(path=SHOTS / "04_prediction.png", full_page=True)
    step(f"prediction: gauge shows {shown} = API; verdict, sample comparison, factors (8 -> 18), 3 tabs, comparison = API")

    # ------------------------------------------------------------ model switching
    page.locator('.model-option:has(input[value="logistic_regression"])').click()
    expect(page.locator("#sidebar-model-name")).to_have_text("Logistic Regression")
    page.locator("#predict-btn").click()
    expect(page.locator(".result-hero .badge").first).to_contain_text("Logistic Regression")
    page.locator('.model-option:has(input[value="knn"])').click()
    page.locator("#predict-btn").click()
    expect(page.locator(".neighbour")).to_have_count(5)
    page.wait_for_timeout(1100)
    page.screenshot(path=SHOTS / "05_prediction_knn.png")
    page.locator('.model-option:has(input[value="naive_bayes"])').click()
    step("model switching (sidebar updates): logistic regression, KNN neighbours")

    # ------------------------------------------------------------ warning, errors, loading
    page.fill("#f-Applicant_Income", "95000")
    expect(page.locator("#sample-note")).to_contain_text("no longer applies")
    page.locator("#predict-btn").click()
    expect(page.locator(".banner-warn")).to_contain_text("outside the training data range")

    page.route("**/api/predict", lambda route: route.abort())
    page.locator("#predict-btn").click()
    expect(page.locator(".result-error")).to_contain_text("Could not connect")
    expect(page.locator("#api-status")).to_have_attribute("data-state", "down")
    page.screenshot(path=SHOTS / "06_api_error.png")
    page.unroute("**/api/predict")

    def slow(route):
        page.wait_for_timeout(900)
        route.continue_()
    page.route("**/api/predict", slow)
    page.locator("#retry-btn").click()
    expect(page.locator(".result-loading")).to_be_visible()
    expect(page.locator("#predict-btn")).to_be_disabled()
    expect(page.locator("#predict-btn .btn-label")).to_have_text("Analysing…")
    expect(page.locator(".result-hero")).to_be_visible()
    expect(page.locator("#predict-btn")).to_be_enabled()
    expect(page.locator("#api-status")).to_have_attribute("data-state", "ok")
    page.unroute("**/api/predict")

    page.route("**/api/predict", lambda route: route.continue_(post_data=route.request.post_data.replace('"DTI_Ratio":', '"DTI_Ratio":5,"_x":')))
    page.locator("#predict-btn").click()
    expect(page.locator(".result-error")).to_contain_text("rejected some inputs")
    expect(page.locator('.field[data-field="DTI_Ratio"]')).to_have_class("field invalid")
    page.unroute("**/api/predict")
    step("extrapolation warning, network failure + retry, loading state, server 422 mapped to field")

    # ------------------------------------------------------------ dashboard refresh keeps form
    page.locator('.nav-link[data-view="dashboard"]').click()
    expect(page.locator("#dash-recent .recent-item")).to_have_count(5)
    page.locator('[data-action="refresh"]').click()
    expect(page.locator(".toast").last).to_contain_text("refreshed")
    page.locator('.nav-link[data-view="predict"]').click()
    assert page.input_value("#f-Applicant_Income") == "95000"
    step("dashboard recent list populated; Refresh keeps the user's form input")

    # ------------------------------------------------------------ history
    sample = page.request.get(BASE + "/api/sample?seed=1").json()["applicant"]
    for i in range(8):
        page.request.post(BASE + "/api/predict", data={"applicant": {**sample, "Credit_Score": 600 + i * 25}, "model": "logistic_regression"})
    page.locator('.nav-link[data-view="history"]').click()
    hist = page.request.get(BASE + "/api/history").json()["items"]
    total = len(hist)
    expect(page.locator("#history-count")).to_have_text(str(total))
    rows = page.locator("#history-body tbody tr")
    expect(rows).to_have_count(10)
    expect(page.locator("#history-foot")).to_contain_text(f"of {total}")
    page.locator('#history-foot [aria-label="Next page"]').click()
    expect(rows).to_have_count(total - 10)
    page.locator('#history-foot [aria-label="Previous page"]').click()
    page.screenshot(path=SHOTS / "07_history.png", full_page=True)
    page.select_option("#history-model", "knn")
    expect(rows).to_have_count(sum(1 for h in hist if h["model"] == "knn"))
    page.select_option("#history-model", "")
    page.select_option("#history-outcome", "No")
    expect(page.locator("#history-kpis .kpi-value").first).to_have_text(str(sum(1 for h in hist if h["prediction"] == "No")))
    page.select_option("#history-outcome", "")
    page.select_option("#history-sort", "prob-desc")
    page.wait_for_timeout(100)
    probs = [float(t.rstrip("%")) for t in page.locator("#history-body .prob-cell .num").all_inner_texts()]
    assert probs == sorted(probs, reverse=True), probs
    page.fill("#history-search", "zzz-no-match")
    expect(page.locator("#history-body")).to_contain_text("No matching predictions")
    page.locator("#history-reset").click()
    expect(rows).to_have_count(10)
    page.fill("#history-search", "knn")
    expect(rows).to_have_count(sum(1 for h in hist if h["model"] == "knn"))
    page.fill("#history-search", "")
    page.select_option("#history-sort", "newest")
    expect(rows).to_have_count(10)
    with page.expect_download() as dl:
        page.locator('[data-action="export"]').click()
    csv = Path(dl.value.path()).read_text(encoding="utf-8").splitlines()
    assert csv[0].startswith("id,created_at,model,prediction,probability_approved,Age"), csv[0]
    assert len(csv) == total + 1, len(csv)
    rows.first.locator("[data-delete]").click()
    expect(page.locator("#history-count")).to_have_text(str(total - 1))
    rows.first.locator("[data-rerun]").click()
    expect(page).to_have_url(BASE + "/#predict")
    assert page.input_value("#f-Credit_Score") != ""
    step(f"history: {total} rows, pagination, model/outcome filters, sort, search + no-match state, CSV export ({len(csv) - 1} rows), delete, re-open")

    page.route("**/api/history?limit=1000", lambda route: route.abort())
    page.locator('.nav-link[data-view="history"]').click()
    expect(page.locator("#history-body")).to_contain_text("Couldn't load history")
    page.unroute("**/api/history?limit=1000")
    page.locator("#history-retry").click()
    expect(rows.first).to_be_visible()
    page.locator('[data-action="clear"]').click()
    expect(page.locator("#history-body")).to_contain_text("No predictions yet")
    expect(page.locator('[data-action="export"]')).to_be_disabled()
    expect(page.locator("#history-count")).to_be_hidden()
    step("history error state + retry; clear all (confirm) -> empty state, export disabled")

    # ------------------------------------------------------------ models
    page.locator('.nav-link[data-view="models"]').click()
    expect(page.locator(".model-card")).to_have_count(3)
    expect(page.locator(".model-card").first).to_contain_text("86.5%")
    expect(page.locator(".model-card").first).to_contain_text("80.4%")
    expect(page.locator("#chart-models svg g.mark")).to_have_count(4)
    expect(page.locator("#chart-models .legend-item")).to_have_count(3)
    expect(page.locator(".cm-cell .v").first).to_have_text("128")
    page.select_option("#cm-model", "knn")
    expect(page.locator(".cm-cell .v").first).to_have_text("120")
    expect(page.locator(".cm-summary")).to_contain_text("152 / 200")
    page.select_option("#cm-model", "naive_bayes")
    page.locator("#chart-models .hit").nth(0).hover()
    expect(page.locator("#tooltip")).to_contain_text("80.4%")
    page.mouse.move(5, 5)
    page.screenshot(path=SHOTS / "08_models.png", full_page=True)
    step("model performance: 3 cards, grouped chart + legend + tooltip, confusion matrices = notebook")

    # ------------------------------------------------------------ responsive
    for name, vp in [("tablet", {"width": 820, "height": 1180}), ("mobile", {"width": 390, "height": 844})]:
        mctx = browser.new_context(viewport=vp, device_scale_factor=2, storage_state=ctx.storage_state())
        mctx.add_init_script("localStorage.setItem('cw-theme', 'light')")
        m = mctx.new_page()
        m.on("pageerror", lambda e: errors.append(str(e)))
        for view in ("dashboard", "predict", "history", "models"):
            m.goto(f"{BASE}/#{view}")
            expect(m.locator("#api-status")).to_have_attribute("data-state", "ok")
            m.wait_for_timeout(250)
            assert not m.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"), f"overflow {name}/{view}"
        m.goto(f"{BASE}/#dashboard")
        m.wait_for_timeout(300)
        m.screenshot(path=SHOTS / f"09_{name}_dashboard.png")
        m.locator("#menu-btn").click()
        expect(m.locator("#sidebar")).to_have_class("sidebar open")
        expect(m.locator("#scrim")).to_be_visible()
        m.screenshot(path=SHOTS / f"10_{name}_nav.png")
        m.locator('.nav-link[data-view="predict"]').click()
        expect(m.locator("#sidebar")).not_to_have_class("sidebar open")
        m.locator('[data-action="sample"]').click()
        expect(m.locator("#form-progress-text")).to_have_text("18/18")
        m.locator("#predict-btn").click()
        expect(m.locator(".result-hero")).to_be_visible()
        m.wait_for_timeout(1100)
        m.screenshot(path=SHOTS / f"11_{name}_result.png", full_page=True)
        mctx.close()
    step("tablet + mobile: no horizontal overflow on any page, nav drawer + scrim, prediction flow")

    page.request.delete(BASE + "/api/history")
    browser.close()

real_errors = [e for e in errors if "ERR_FAILED" not in e and "Failed to load resource" not in e]
if real_errors:
    print("Console errors:", *real_errors, sep="\n  ")
    sys.exit(1)
print(f"All browser checks passed. Screenshots in {SHOTS}")
