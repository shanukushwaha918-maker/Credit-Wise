/* CreditWise frontend. Every number on screen comes from the FastAPI backend. */
(function () {
  "use strict";
  const C = window.CWCharts;
  const { esc, pct0, pct1 } = C;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const state = {
    meta: null, schema: null, selectedModel: null, lastRequest: null, sample: null,
    history: [], historyStatus: "idle", historyError: "",
    hq: { search: "", model: "", outcome: "", sort: "newest", page: 1 },
  };
  const PAGE_SIZE = 10;
  const SERIES = ["--series-1", "--series-2", "--series-3"];

  /* ============================================================== icons */
  const I = {
    check: '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
    x: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    warn: '<svg viewBox="0 0 24 24"><path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>',
    info: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>',
    trash: '<svg viewBox="0 0 24 24"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>',
    redo: '<svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v4h4"/></svg>',
    open: '<svg viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>',
    plus: '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>',
    arrow: '<svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
    refresh: '<svg viewBox="0 0 24 24"><path d="M21 12a9 9 0 0 1-15.5 6.2M3 12A9 9 0 0 1 18.5 5.8"/><path d="M21 4v5h-5M3 20v-5h5"/></svg>',
    download: '<svg viewBox="0 0 24 24"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg>',
    dice: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="8.5" cy="8.5" r="1.2" fill="currentColor"/><circle cx="15.5" cy="15.5" r="1.2" fill="currentColor"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/></svg>',
    users: '<svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M21.5 20a6.5 6.5 0 0 0-4-6"/></svg>',
    percent: '<svg viewBox="0 0 24 24"><path d="M19 5L5 19"/><circle cx="7" cy="7" r="2.5"/><circle cx="17" cy="17" r="2.5"/></svg>',
    target: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/></svg>',
    shield: '<svg viewBox="0 0 24 24"><path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/></svg>',
    history: '<svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v4h4"/><path d="M12 7v5l3 2"/></svg>',
    search: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>',
    chevL: '<svg viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6"/></svg>',
    chevR: '<svg viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></svg>',
    bolt: '<svg viewBox="0 0 24 24"><path d="M13 2L4 14h7l-1 8 9-12h-7z"/></svg>',
    trend: '<svg viewBox="0 0 24 24"><path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/></svg>',
    alert: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/></svg>',
  };

  /* ================================================================ API */
  class ApiError extends Error {
    constructor(message, status, errors) { super(message); this.status = status; this.errors = errors || []; }
  }
  async function api(path, { method = "GET", body, timeout = 15000 } = {}) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    let res;
    try {
      res = await fetch(path, {
        method, signal: ctrl.signal,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (e) {
      throw new ApiError(e.name === "AbortError" ? "The request timed out. Please try again." : "Could not connect to the CreditWise API. Is the server running?", 0);
    } finally { clearTimeout(timer); }
    let data = null;
    try { data = await res.json(); } catch (_) { /* non-JSON body */ }
    if (!res.ok) {
      const detail = data && typeof data.detail === "string" ? data.detail : `Request failed (HTTP ${res.status}).`;
      if (res.status === 401 && !path.startsWith("/api/auth/")) onSessionExpired();
      throw new ApiError(detail, res.status, data && data.errors);
    }
    return data;
  }

  /* ============================================================ helpers */
  const fmtNum = (v, d = 0) => Number(v).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d });
  const label = (f) => (state.meta && state.meta.field_labels[f]) || f;
  const modelInfo = (id) => state.meta.models.find((m) => m.id === id) || { label: id, metrics: {} };
  const modelLabel = (id) => modelInfo(id).label;
  const modelShort = (id) => ({ naive_bayes: "Naive Bayes", logistic_regression: "Logistic Regression", knn: "KNN (k=5)" }[id] || id);
  const modelColor = (id) => `var(${SERIES[Math.max(0, state.meta.models.findIndex((m) => m.id === id))]})`;
  const badge = (approved, sm) => approved
    ? `<span class="badge badge-yes ${sm ? "badge-sm" : ""}">${I.check}Approved</span>`
    : `<span class="badge badge-no ${sm ? "badge-sm" : ""}">${I.x}Rejected</span>`;
  const swatch = (id) => `<span class="legend-swatch" style="background:${modelColor(id)}"></span>`;
  const fmtDate = (iso) => new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  function fmtValue(field, v) {
    if (field === "DTI_Ratio") return Number(v).toFixed(2);
    if (field === "Loan_Term") return `${v} months`;
    if (field === "Age") return `${fmtNum(v)} yrs`;
    if (typeof v === "number") return fmtNum(v, Number.isInteger(v) ? 0 : 2);
    return String(v);
  }
  const fmtRange = (f, v) => (f === "DTI_Ratio" ? Number(v).toFixed(2) : fmtNum(v));

  function toast(msg, type = "ok") {
    const t = document.createElement("div");
    t.className = `toast ${type}`;
    t.innerHTML = `${type === "err" ? I.alert : I.check}<span>${esc(msg)}</span>`;
    $("#toasts").appendChild(t);
    setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 260); }, 2800);
  }

  /* ============================================================ routing */
  const VIEWS = ["dashboard", "predict", "history", "models"];
  const AUTH_VIEWS = ["login", "signup"];
  function currentView() { const v = location.hash.slice(1); return VIEWS.includes(v) ? v : "dashboard"; }
  function route() {
    const hash = location.hash.slice(1);
    if (!state.user) {
      if (!AUTH_VIEWS.includes(hash)) {
        if (VIEWS.includes(hash)) state.afterLogin = hash;
        location.replace("#login");
        return;
      }
      showAuth(hash);
      return;
    }
    if (AUTH_VIEWS.includes(hash)) { location.replace("#" + (state.afterLogin || "dashboard")); return; }
    closeUserMenu();
    const view = currentView();
    $$(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + view));
    $$(".nav-link").forEach((a) => {
      const on = a.dataset.view === view;
      a.classList.toggle("active", on);
      if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    const v = $("#view-" + view);
    $("#view-title").textContent = v.dataset.title;
    $("#view-subtitle").textContent = v.dataset.subtitle;
    $("#crumb-current").textContent = v.dataset.title;
    document.title = `${v.dataset.title} · CreditWise`;
    renderPageActions(view);
    closeSidebar();
    window.scrollTo({ top: 0 });
    if (view === "history" || view === "dashboard") loadHistory();
    requestAnimationFrame(() => C.redrawAll());
  }

  function renderPageActions(view) {
    const host = $("#page-actions");
    const actions = {
      dashboard: `<button type="button" class="btn btn-secondary" data-action="refresh">${I.refresh}Refresh</button>
                  <a class="btn btn-primary" href="#predict">${I.plus}New prediction</a>`,
      predict: `<button type="button" class="btn btn-secondary" data-action="sample">${I.dice}Load a real applicant</button>`,
      history: `<button type="button" class="btn btn-secondary" data-action="export">${I.download}Export CSV</button>
                <button type="button" class="btn btn-danger" data-action="clear">${I.trash}Clear all</button>`,
      models: `<a class="btn btn-secondary" href="/docs" target="_blank" rel="noopener">${I.open}API docs</a>
               <a class="btn btn-primary" href="#predict">${I.plus}New prediction</a>`,
    };
    host.innerHTML = actions[view] || "";
    syncHistoryActions();
  }
  function onPageAction(e) {
    const b = e.target.closest("[data-action]");
    if (!b) return;
    ({ refresh: refreshAll, sample: loadSample, export: exportCsv, clear: clearHistory }[b.dataset.action] || (() => {}))(b);
  }

  /* ============================================================ chrome */
  function initTheme() {
    const btns = $$(".theme-toggle");
    const sync = () => btns.forEach((b) => b.setAttribute("aria-checked", String(document.documentElement.dataset.theme === "dark")));
    sync();
    btns.forEach((btn) => btn.addEventListener("click", () => {
      const root = document.documentElement;
      root.classList.add("theme-switching");
      root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
      localStorage.setItem("cw-theme", root.dataset.theme);
      sync();
      C.redrawAll(true);
      renderConfusion();
      setTimeout(() => root.classList.remove("theme-switching"), 350);
    }));
  }
  function openSidebar() { $("#sidebar").classList.add("open"); $("#scrim").hidden = false; $("#menu-btn").setAttribute("aria-expanded", "true"); }
  function closeSidebar() { $("#sidebar").classList.remove("open"); $("#scrim").hidden = true; $("#menu-btn").setAttribute("aria-expanded", "false"); }

  function setApiStatus(ok, text) {
    const s = $("#api-status");
    s.dataset.state = ok === null ? "checking" : ok ? "ok" : "down";
    $(".api-text", s).textContent = text;
    $("#global-error").hidden = ok !== false;
  }
  function syncActiveModel() {
    if (!state.meta) return;
    const m = modelInfo(state.selectedModel);
    $("#sidebar-model-name").textContent = m.label;
    $("#sidebar-model-meta").textContent = `Accuracy ${pct1(m.metrics.accuracy)} · Precision ${pct1(m.metrics.precision)}`;
    const chip = $("#topbar-model");
    chip.innerHTML = `${swatch(state.selectedModel)}${esc(modelShort(state.selectedModel))}`;
    chip.hidden = false;
  }

  /* ============================================================== boot */
  async function boot() {
    setApiStatus(null, "Connecting…");
    try {
      const [health, meta, schema] = await Promise.all([api("/api/health"), api("/api/meta"), api("/api/schema/applicant")]);
      state.meta = meta;
      state.schema = schema;
      state.selectedModel = state.selectedModel || meta.default_model;
      setApiStatus(true, `API online · ${health.models_loaded.length} models`);
      syncActiveModel();
      renderDashboard();
      renderModels();
      if (!state.formBuilt) { buildForm(); renderResultEmpty(); state.formBuilt = true; }
      loadHistory();
    } catch (e) {
      setApiStatus(false, "API offline");
      $("#global-error-text").textContent = e.message;
      $("#dash-kpis").innerHTML = "";
    }
  }
  async function refreshAll(btn) {
    if (btn) btn.disabled = true;
    await boot();
    if (btn) btn.disabled = false;
    if (state.meta) toast("Data refreshed from the API");
  }

  /* ========================================================= dashboard */
  function rateRows(rows) {
    return rows.map((r) => ({
      label: r.label, value: r.total ? r.approved / r.total : 0,
      tip: [{ label: "Approval rate", value: r.total ? pct1(r.approved / r.total) : "—" },
            { label: "Approved", value: `${r.approved} of ${r.total}` }],
    }));
  }
  function rateTable(rows, first) {
    return { columns: [{ label: first }, { label: "Applicants", num: true }, { label: "Approved", num: true }, { label: "Approval rate", num: true }],
      rows: rows.map((r) => [r.label, r.total, r.approved, r.total ? pct1(r.approved / r.total) : "—"]) };
  }
  function kpi({ label: l, icon, value, foot, bar }) {
    return `<div class="kpi">
      <div class="kpi-top"><span class="kpi-label">${l}</span><span class="kpi-icon">${icon}</span></div>
      <div class="kpi-value">${value}</div>
      ${bar ? `<div class="bar bar-sm" role="presentation">${bar}</div>` : ""}
      <div class="kpi-foot">${foot}</div></div>`;
  }

  function renderDashboard() {
    const { dataset: d, default_model, test_size } = state.meta;
    const def = modelInfo(default_model);
    const [[tn, fp], [fn, tp]] = def.metrics.confusion_matrix;
    const rate = d.approved / d.labelled_rows;
    const labelled = d.labelled_rows / d.rows;
    $("#dash-kpis").innerHTML = [
      kpi({ label: "Applicants in dataset", icon: I.users, value: fmtNum(d.rows),
        bar: `<span style="width:${labelled * 100}%;background:var(--series-1)"></span>`,
        foot: `<strong>${fmtNum(d.labelled_rows)}</strong> with a recorded outcome · ${fmtNum(d.rows - d.labelled_rows)} without` }),
      kpi({ label: "Historical approval rate", icon: I.percent, value: pct1(rate),
        bar: `<span style="width:${rate * 100}%;background:var(--series-1)"></span>`,
        foot: `<strong>${fmtNum(d.approved)}</strong> approved · ${fmtNum(d.rejected)} rejected` }),
      kpi({ label: `${modelShort(default_model)} accuracy`, icon: I.target, value: pct1(def.metrics.accuracy),
        bar: `<span style="width:${def.metrics.accuracy * 100}%;background:var(--series-1)"></span>`,
        foot: `<strong>${tn + tp} of ${test_size}</strong> held-out applicants correct` }),
      kpi({ label: `${modelShort(default_model)} precision`, icon: I.shield, value: pct1(def.metrics.precision),
        bar: `<span style="width:${def.metrics.precision * 100}%;background:var(--series-1)"></span>`,
        foot: `<strong>${tp} of ${tp + fp}</strong> predicted approvals were right` }),
    ].join("");

    // Insights derived from the data, never hand-written.
    const insights = [];
    const cs = d.credit_score_bins;
    let lead = 0; while (lead < cs.length && cs[lead].total && cs[lead].approved === 0) lead++;
    let csT = null;
    if (lead > 0 && lead < cs.length) {
      const n = cs.slice(0, lead).reduce((a, b) => a + b.total, 0);
      csT = { afterIndex: lead - 1, cutoff: cs[lead].label.split("-")[0] };
      insights.push({ icon: I.shield, html: `No applicant with a credit score below <strong>${csT.cutoff}</strong> was approved <span class="num">(0 of ${n})</span>.` });
    }
    const dti = d.dti_bins;
    let trail = dti.length; while (trail > 0 && dti[trail - 1].total && dti[trail - 1].approved === 0) trail--;
    let dtiT = null;
    if (trail < dti.length && trail > 0) {
      const n = dti.slice(trail).reduce((a, b) => a + b.total, 0);
      dtiT = { afterIndex: trail - 1, cutoff: dti[trail].label.split("-")[0] };
      insights.push({ icon: I.percent, html: `No applicant with a debt-to-income ratio of <strong>${dtiT.cutoff} or more</strong> was approved <span class="num">(0 of ${n})</span>.` });
    }
    if (csT) {
      const above = cs.slice(lead), t = above.reduce((a, b) => a + b.total, 0), a = above.reduce((x, b) => x + b.approved, 0);
      insights.push({ icon: I.trend, html: `At a credit score of ${csT.cutoff}+, <strong>${pct0(a / t)}</strong> of applicants were approved <span class="num">(${a} of ${t})</span>.` });
    }
    $("#dash-insights").innerHTML = insights.map((i) => `<div class="insight"><span class="insight-icon">${i.icon}</span><div>${i.html}</div></div>`).join("");

    C.card($("#chart-credit"), {
      title: "Approval rate by credit score", subtitle: "Share of applicants approved in each 25-point band",
      draw: (el, w) => C.columns(el, w, { data: rateRows(cs), height: w > 560 ? 400 : 260, threshold: csT && { afterIndex: csT.afterIndex, label: `${csT.cutoff} cutoff` } }),
      table: rateTable(cs, "Credit score"),
    });
    C.card($("#chart-dti"), {
      title: "Approval rate by debt-to-income", subtitle: "Share of applicants approved in each DTI band",
      draw: (el, w) => C.columns(el, w, { data: rateRows(dti), threshold: dtiT && { afterIndex: dtiT.afterIndex, label: `${dtiT.cutoff} cutoff` } }),
      table: rateTable(dti, "DTI ratio"),
    });
    C.card($("#chart-employment"), {
      title: "Approval rate by employment", subtitle: "Recorded outcomes in the training dataset",
      draw: (el, w) => C.bars(el, w, { data: rateRows(d.by_employment) }),
      table: rateTable(d.by_employment, "Employment status"),
    });
    C.card($("#chart-purpose"), {
      title: "Approval rate by loan purpose", subtitle: "Recorded outcomes in the training dataset",
      draw: (el, w) => C.bars(el, w, { data: rateRows(d.by_purpose) }),
      table: rateTable(d.by_purpose, "Loan purpose"),
    });

    $("#dash-models").innerHTML = `
      <div class="card-head"><div><h3>Model leaderboard</h3><p>Accuracy on ${test_size} held-out applicants</p></div></div>
      <div class="mini-models">${state.meta.models.map((m) => `
        <div class="mini-model">
          <div class="mini-model-head">
            <span class="mini-model-name">${swatch(m.id)}${esc(modelShort(m.id))}
              ${m.id === default_model ? '<span class="badge badge-accent badge-sm">Notebook pick</span>' : ""}</span>
            <span class="mini-model-acc">${pct1(m.metrics.accuracy)}</span>
          </div>
          <div class="bar bar-xs"><span style="width:${m.metrics.accuracy * 100}%;background:${modelColor(m.id)}"></span></div>
          <div class="mini-model-stats">
            <span><b>${pct1(m.metrics.precision)}</b>Precision</span><span><b>${pct1(m.metrics.recall)}</b>Recall</span><span><b>${pct1(m.metrics.f1)}</b>F1</span>
          </div>
        </div>`).join("")}</div>
      <a class="link-row" href="#models">Full model performance ${I.arrow}</a>`;
    renderRecent();
  }

  function renderRecent() {
    const host = $("#dash-recent");
    if (!host || !state.meta) return;
    const head = `<div class="card-head"><div><h3>Recent predictions</h3><p>Latest assessments made in this app</p></div>
      <a class="btn btn-secondary btn-sm" href="#history">View all</a></div>`;
    if (state.historyStatus === "loading" && !state.history.length) {
      host.innerHTML = head + `<div class="recent-list">${Array.from({ length: 4 }, () => `<div class="recent-item"><div class="skeleton" style="width:36px;height:36px;border-radius:10px"></div><div><div class="skeleton sk-line" style="width:60%"></div></div><div></div><div></div></div>`).join("")}</div>`;
      return;
    }
    if (state.historyStatus === "error") {
      host.innerHTML = head + `<div class="state"><span class="state-icon err">${I.alert}</span><h3>Couldn't load predictions</h3><p>${esc(state.historyError)}</p></div>`;
      return;
    }
    const items = state.history.slice(0, 5);
    if (!items.length) {
      host.innerHTML = head + `<div class="state"><span class="state-icon">${I.history}</span><h3>No predictions yet</h3>
        <p>Assess an application and it will appear here.</p><a class="btn btn-primary" href="#predict">${I.plus}New prediction</a></div>`;
      return;
    }
    host.innerHTML = head + `<div class="recent-list">${items.map((h) => `
      <div class="recent-item">
        <span class="recent-avatar">#${h.id}</span>
        <div class="recent-main"><b>${esc(h.applicant.Loan_Purpose)} loan · ${fmtNum(h.applicant.Loan_Amount)}</b>
          <span>${esc(modelShort(h.model))} · credit ${fmtNum(h.applicant.Credit_Score)} · ${esc(fmtDate(h.created_at))}</span></div>
        <span class="recent-prob">${pct1(h.probability_approved)}</span>
        ${badge(h.prediction === "Yes", true)}
      </div>`).join("")}</div>`;
  }

  /* ============================================================ models */
  const METRICS = [["precision", "Precision"], ["recall", "Recall"], ["f1", "F1 score"], ["accuracy", "Accuracy"]];
  function renderModels() {
    const { models, test_size, train_size, default_model } = state.meta;
    const best = {};
    METRICS.forEach(([k]) => { best[k] = Math.max(...models.map((m) => m.metrics[k])); });

    $("#model-cards").innerHTML = models.map((m) => {
      const [[tn, fp], [fn, tp]] = m.metrics.confusion_matrix;
      const leads = METRICS.filter(([k]) => m.metrics[k] === best[k]).map(([, l]) => l);
      return `<article class="card model-card" style="--swatch:${modelColor(m.id)}">
        <div class="model-card-head">
          <span class="model-card-name">${swatch(m.id)}${esc(m.label)}</span>
          ${m.id === default_model ? '<span class="badge badge-accent">Notebook pick</span>' : ""}
        </div>
        <div class="model-card-big"><span class="v">${pct1(m.metrics.accuracy)}</span><span class="k">accuracy</span></div>
        <div class="metric-rows">${METRICS.slice(0, 3).map(([k, l]) => `
          <div class="metric-row"><span>${l}</span><div class="bar bar-sm"><span style="width:${m.metrics[k] * 100}%;background:${modelColor(m.id)}"></span></div><b>${pct1(m.metrics[k])}</b></div>`).join("")}
        </div>
        <div class="model-card-foot">
          <span class="badge badge-neutral badge-sm">TP ${tp}</span><span class="badge badge-neutral badge-sm">FP ${fp}</span>
          <span class="badge badge-neutral badge-sm">FN ${fn}</span><span class="badge badge-neutral badge-sm">TN ${tn}</span>
          ${leads.length ? `<span class="badge badge-yes badge-sm">${I.check}Best ${esc(leads.join(" · "))}</span>` : ""}
        </div>
      </article>`;
    }).join("");

    C.card($("#chart-models"), {
      title: "Metric comparison", subtitle: `All three models on the same ${test_size} test applicants`,
      legend: models.map((m) => ({ label: m.label, color: modelColor(m.id) })),
      draw: (el, w) => C.grouped(el, w, {
        categories: METRICS.map((k) => k[1]),
        series: models.map((m, i) => ({ name: m.label, color: C.css(SERIES[i]), values: METRICS.map((k) => m.metrics[k[0]]) })),
      }),
      table: { columns: [{ label: "Model" }, ...METRICS.map((k) => ({ label: k[1], num: true }))],
        rows: models.map((m) => [m.label, ...METRICS.map((k) => pct1(m.metrics[k[0]]))]) },
    });

    $("#chart-cm").innerHTML = `<div class="chart-head"><div><h3>Confusion matrix</h3><p>Where each model is right and wrong</p></div>
      <select class="select" id="cm-model" aria-label="Model for confusion matrix">${models.map((m) =>
        `<option value="${m.id}" ${m.id === default_model ? "selected" : ""}>${esc(modelShort(m.id))}</option>`).join("")}</select></div>
      <div id="cm-body"></div>`;
    $("#cm-model").addEventListener("change", renderConfusion);
    renderConfusion();

    $("#metrics-table").innerHTML = `<div class="table-wrap"><table><thead><tr><th>Model</th>${METRICS.map((k) => `<th class="num">${k[1]}</th>`).join("")}</tr></thead><tbody>
      ${models.map((m) => `<tr><td><span class="mini-model-name">${swatch(m.id)}${esc(m.label)}</span></td>
        ${METRICS.map(([k]) => `<td class="num">${m.metrics[k] === best[k] ? "<strong>" + pct1(m.metrics[k]) + "</strong>" : pct1(m.metrics[k])}</td>`).join("")}</tr>`).join("")}
      </tbody></table></div>`;
    $("#models-footnote").textContent =
      `Trained on ${train_size} and evaluated on ${test_size} applicants (train_test_split, test_size=0.2, random_state=42), reproduced exactly from credit_wise.ipynb. ` +
      `With ${test_size} test applicants, a 1-point difference is about 2 applicants. As in the notebook, the ${state.meta.dataset.rows - state.meta.dataset.labelled_rows} rows with no recorded outcome ` +
      `were filled with the most frequent label ("No") before training; dashboard figures use only rows with a recorded outcome.`;
  }
  function renderConfusion() {
    if (!state.meta || !$("#cm-model")) return;
    C.confusion($("#cm-body"), modelInfo($("#cm-model").value).metrics.confusion_matrix);
  }

  /* ============================================================== form */
  const SECTIONS = [
    { title: "Applicant profile", desc: "Who is applying", fields: ["Age", "Gender", "Marital_Status", "Dependents", "Education_Level", "Property_Area"] },
    { title: "Employment & income", desc: "Earnings and savings", fields: ["Employment_Status", "Employer_Category", "Applicant_Income", "Coapplicant_Income", "Savings"] },
    { title: "Credit profile", desc: "Creditworthiness and existing debt", fields: ["Credit_Score", "DTI_Ratio", "Existing_Loans", "Collateral_Value"] },
    { title: "Loan request", desc: "What is being requested", fields: ["Loan_Amount", "Loan_Term", "Loan_Purpose"] },
  ];
  const ALL_FIELDS = SECTIONS.flatMap((s) => s.fields);
  const SUFFIX = { Age: "years", Loan_Term: "months", DTI_Ratio: "ratio" };
  const STEP = { DTI_Ratio: "0.01", Age: "1" };
  const PLACEHOLDER = { DTI_Ratio: "e.g. 0.35", Credit_Score: "e.g. 700" };
  const fieldSchema = (f) => state.schema.properties[f];

  function buildForm() {
    const ranges = state.meta.numeric_ranges;
    $("#form-fields").innerHTML = SECTIONS.map((s, si) => `
      <div class="form-section" data-section="${si}">
        <div class="section-head">
          <span class="section-num">${si + 1}</span>
          <div><h3>${esc(s.title)}</h3><p class="muted small">${esc(s.desc)}</p></div>
          <span class="section-count" data-count="${si}">0/${s.fields.length}</span>
        </div>
        <div class="field-grid">${s.fields.map((f) => {
          const sc = fieldSchema(f), id = "f-" + f;
          if (sc.enum) {
            return `<div class="field" data-field="${f}"><label for="${id}">${esc(label(f))}</label>
              <select id="${id}" name="${f}" required><option value="">Select…</option>
              ${sc.enum.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`).join("")}</select>
              <span class="field-hint blank">&nbsp;</span><span class="field-error" id="${id}-err"></span></div>`;
          }
          const r = ranges[f];
          const step = STEP[f] || (sc.type === "integer" ? "1" : "any");
          const min = sc.minimum ?? sc.exclusiveMinimum ?? "";
          return `<div class="field" data-field="${f}"><label for="${id}">${esc(label(f))}</label>
            <div class="input-wrap ${SUFFIX[f] ? "has-suffix" : ""}">
              <input id="${id}" name="${f}" type="number" inputmode="decimal" step="${step}" min="${min}" max="${sc.maximum ?? ""}"
                placeholder="${PLACEHOLDER[f] || ""}" aria-describedby="${id}-hint ${id}-err" required>
              ${SUFFIX[f] ? `<span class="affix suffix">${SUFFIX[f]}</span>` : ""}</div>
            <span class="field-hint" id="${id}-hint">Training range ${fmtRange(f, r.min)} – ${fmtRange(f, r.max)}</span>
            <span class="field-error" id="${id}-err"></span></div>`;
        }).join("")}</div>
      </div>`).join("");

    $("#model-picker").innerHTML = state.meta.models.map((m) => `
      <label class="model-option">
        <input type="radio" name="model" value="${m.id}" ${m.id === state.selectedModel ? "checked" : ""}>
        <span class="model-option-card">
          <span class="model-option-head"><span class="model-option-name">${esc(m.label)}</span><span class="radio-dot"></span></span>
          <span class="model-option-stats"><span>Acc <b>${pct1(m.metrics.accuracy)}</b></span><span>Prec <b>${pct1(m.metrics.precision)}</b></span></span>
          ${m.id === state.meta.default_model ? '<span><span class="badge badge-accent badge-sm">Notebook pick</span></span>' : ""}
        </span>
      </label>`).join("");
    $$("#model-picker input").forEach((r) => r.addEventListener("change", () => { state.selectedModel = r.value; syncActiveModel(); }));

    $$("#form-fields input, #form-fields select").forEach((inp) => {
      const onChange = () => {
        clearFieldError(inp.name);
        $(`.field[data-field="${inp.name}"]`).classList.remove("valid");
        if (state.sample) markSampleEdited();
        updateProgress();
      };
      inp.addEventListener("input", onChange);
      inp.addEventListener("change", onChange);
      inp.addEventListener("blur", () => { if (inp.value !== "") validateField(inp.name); });
    });
    updateProgress();
  }

  function updateProgress() {
    if (!state.schema) return;
    let done = 0;
    SECTIONS.forEach((s, si) => {
      const n = s.fields.filter((f) => $("#f-" + f).value !== "").length;
      done += n;
      $(`[data-count="${si}"]`).textContent = `${n}/${s.fields.length}`;
      $(`.form-section[data-section="${si}"]`).classList.toggle("complete", n === s.fields.length);
    });
    const ring = $("#form-progress-ring");
    ring.querySelector(".value").style.strokeDashoffset = (97.4 * (1 - done / ALL_FIELDS.length)).toFixed(2);
    ring.classList.toggle("done", done === ALL_FIELDS.length);
    $("#form-progress-text").textContent = `${done}/${ALL_FIELDS.length}`;
  }

  function readForm() {
    const out = {};
    ALL_FIELDS.forEach((f) => {
      const inp = $("#f-" + f);
      out[f] = inp.tagName === "SELECT" ? inp.value : (inp.value === "" ? null : Number(inp.value));
    });
    return out;
  }

  function validateField(f) {
    const sc = fieldSchema(f), v = $("#f-" + f).value;
    let msg = "";
    if (v === "") msg = "This field is required";
    else if (sc.enum) { if (!sc.enum.includes(v)) msg = "Choose a valid option"; }
    else {
      const n = Number(v);
      const nice = (x) => fmtNum(x, 2).replace(/\.00$/, "");
      if (!Number.isFinite(n)) msg = "Enter a number";
      else if (sc.type === "integer" && !Number.isInteger(n)) msg = "Must be a whole number";
      else if (sc.minimum !== undefined && n < sc.minimum) msg = `Must be at least ${nice(sc.minimum)}`;
      else if (sc.exclusiveMinimum !== undefined && n <= sc.exclusiveMinimum) msg = `Must be greater than ${sc.exclusiveMinimum}`;
      else if (sc.maximum !== undefined && n > sc.maximum) msg = `Must be at most ${nice(sc.maximum)}`;
    }
    setFieldError(f, msg);
    $(`.field[data-field="${f}"]`).classList.toggle("valid", !msg);
    return !msg;
  }
  function setFieldError(f, msg) {
    const field = $(`.field[data-field="${f}"]`);
    if (!field) return;
    field.classList.toggle("invalid", !!msg);
    if (msg) field.classList.remove("valid");
    $(".field-error", field).textContent = msg;
    const inp = $("#f-" + f);
    if (msg) inp.setAttribute("aria-invalid", "true"); else inp.removeAttribute("aria-invalid");
  }
  function clearFieldError(f) { setFieldError(f, ""); }
  function showFormErrors(list) {
    const box = $("#form-errors");
    if (!list.length) { box.hidden = true; return; }
    box.innerHTML = `${I.alert}<div><strong>Please fix ${list.length} field${list.length > 1 ? "s" : ""}</strong><ul>${list.slice(0, 6).map((e) =>
      `<li>${esc(e.label || "Input")}: ${esc(e.message)}</li>`).join("")}${list.length > 6 ? `<li>…and ${list.length - 6} more</li>` : ""}</ul></div>`;
    box.hidden = false;
  }

  function fillForm(applicant) {
    Object.entries(applicant).forEach(([f, v]) => {
      const inp = $("#f-" + f);
      if (inp) { inp.value = v; clearFieldError(f); $(`.field[data-field="${f}"]`).classList.add("valid"); }
    });
    showFormErrors([]);
    updateProgress();
  }
  function setSampleNote(html) {
    const n = $("#sample-note");
    n.className = "banner banner-info sample-note";
    n.innerHTML = `${I.info}<div>${html}</div>`;
    n.hidden = false;
  }
  function markSampleEdited() {
    if (!state.sample || state.sample.edited) return;
    state.sample.edited = true;
    setSampleNote(`You edited dataset applicant <strong>#${state.sample.id}</strong>, so its recorded outcome no longer applies.`);
  }

  async function loadSample(btn) {
    if (!state.meta) { toast("The API is not connected yet.", "err"); return; }
    if (currentView() !== "predict") location.hash = "#predict";
    const b = btn && btn.tagName ? btn : $('[data-action="sample"]');
    if (b) b.disabled = true;
    try {
      const s = await api("/api/sample");
      fillForm(s.applicant);
      state.sample = { id: s.applicant_id, actual: s.actual_outcome, edited: false };
      setSampleNote(`Loaded applicant <strong>#${s.applicant_id}</strong> from the dataset. Recorded outcome:
        <strong>${s.actual_outcome === "Yes" ? "Approved" : "Rejected"}</strong>. Run a prediction to compare.`);
      toast(`Loaded dataset applicant #${s.applicant_id}`);
    } catch (e) {
      toast(e.message, "err");
    } finally { if (b) b.disabled = false; }
  }

  function resetForm() {
    $("#predict-form").reset();
    $$("#model-picker input").forEach((r) => { r.checked = r.value === state.selectedModel; });
    ALL_FIELDS.forEach((f) => { clearFieldError(f); $(`.field[data-field="${f}"]`).classList.remove("valid"); });
    showFormErrors([]);
    state.sample = null;
    $("#sample-note").hidden = true;
    updateProgress();
  }

  async function submit(e) {
    e.preventDefault();
    if (!state.meta) { toast("The API is not connected yet.", "err"); return; }
    const bad = ALL_FIELDS.filter((f) => !validateField(f));
    if (bad.length) {
      showFormErrors(bad.map((f) => ({ label: label(f), message: $(`#f-${f}-err`).textContent })));
      $("#f-" + bad[0]).focus();
      $("#f-" + bad[0]).scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    showFormErrors([]);
    const request = { applicant: readForm(), model: state.selectedModel };
    state.lastRequest = request;
    await runPrediction(request);
  }

  async function runPrediction(request) {
    const btn = $("#predict-btn");
    btn.disabled = true; btn.classList.add("loading");
    $(".btn-label", btn).textContent = "Analysing…";
    renderResultLoading();
    try {
      const result = await api("/api/predict", { method: "POST", body: request });
      setApiStatus(true, `API online · ${state.meta.models.length} models`);
      renderResult(result);
      const box = $("#result").getBoundingClientRect();
      if (box.top < 70 || box.top > window.innerHeight * 0.5) $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
      loadHistory();
    } catch (err) {
      if (err.status === 422 && err.errors.length) {
        err.errors.forEach((x) => x.field && setFieldError(x.field, x.message));
        showFormErrors(err.errors);
        renderResultError("The server rejected some inputs. Fix the highlighted fields and try again.", false);
      } else {
        if (err.status === 0) setApiStatus(false, "API offline");
        renderResultError(err.message, true);
      }
    } finally {
      btn.disabled = false; btn.classList.remove("loading");
      $(".btn-label", btn).textContent = "Predict approval";
    }
  }

  /* ============================================================ result */
  function renderResultEmpty() {
    $("#result").innerHTML = `<div class="result-empty">
      <svg class="empty-art" viewBox="0 0 140 90" fill="none" stroke-linecap="round">
        <path class="track" d="M14 78 A56 56 0 0 1 126 78" stroke-width="12"/>
        <path class="arc" d="M14 78 A56 56 0 0 1 92 26" stroke-width="12"/>
        <path class="needle" d="M70 78 L94 44" stroke-width="3"/><circle cx="70" cy="78" r="5" fill="currentColor" class="needle"/>
      </svg>
      <h3>Ready to assess</h3>
      <p>The approval probability, verdict and the reasons behind it will appear here.</p>
      <div class="empty-steps">
        <div><span>1</span>Fill in all 18 fields, or load a real applicant</div>
        <div><span>2</span>Choose one of the notebook's models</div>
        <div><span>3</span>Press <strong>Predict approval</strong></div>
      </div></div>`;
  }
  function renderResultLoading() {
    $("#result").innerHTML = `<div class="result-loading" aria-busy="true">
      <div class="skeleton gauge-sk"></div>
      <div class="skeleton sk-line" style="width:30%;margin:0 auto"></div>
      <div class="skeleton" style="height:34px;border-radius:12px;margin-top:10px"></div>
      <div class="skeleton" style="height:56px;border-radius:10px"></div>
      <div class="skeleton" style="height:56px;border-radius:10px"></div>
      <div class="skeleton" style="height:56px;border-radius:10px"></div>
      <p class="muted small" style="text-align:center">Running the model…</p></div>`;
  }
  function renderResultError(msg, retry) {
    $("#result").innerHTML = `<div class="result-error">
      <span class="err-icon">${I.warn}</span><h3>Prediction failed</h3><p>${esc(msg)}</p>
      ${retry ? `<button class="btn btn-secondary" type="button" id="retry-btn">${I.redo}Try again</button>` : ""}</div>`;
    if (retry) $("#retry-btn").addEventListener("click", () => state.lastRequest && runPrediction(state.lastRequest));
  }

  const sigmoid = (z) => 1 / (1 + Math.exp(-z));
  function strength(impact, total) {
    const share = Math.abs(impact) / total;
    return share > 0.3 ? "strongly " : share < 0.08 ? "slightly " : "";
  }

  function renderResult(r) {
    const p = r.probability_approved, ex = r.explanation;
    const color = r.approved ? C.css("--good") : C.css("--critical");
    const yesCount = r.comparison.filter((c) => c.approved).length;

    let pre = "";
    if (r.warnings.length) {
      pre += `<div class="banner banner-warn">${I.warn}<div><strong>Outside the training data</strong>
        <ul>${r.warnings.map((w) => `<li>${esc(w.message)}</li>`).join("")}</ul></div></div>`;
    }
    if (state.sample && !state.sample.edited) {
      const actualYes = state.sample.actual === "Yes", agree = actualYes === r.approved;
      pre += `<div class="banner ${agree ? "banner-info" : "banner-warn"}">${agree ? I.check : I.info}<div>Dataset applicant
        <strong>#${state.sample.id}</strong> was actually <strong>${actualYes ? "approved" : "rejected"}</strong>. The model
        <strong>${agree ? "agrees" : "disagrees"}</strong>.</div></div>`;
    }

    // ---- explanation tab
    let explain = "";
    if (ex.factors) {
      const total = ex.factors.reduce((a, f) => a + Math.abs(f.impact), 0) || 1;
      const pos = ex.factors.filter((f) => f.impact > 0).slice(0, 3);
      const neg = ex.factors.filter((f) => f.impact < 0).slice(0, 3);
      const reason = (f, dir) => `<li class="reason ${dir > 0 ? "pos" : "neg"}"><span class="reason-icon">${dir > 0 ? I.check : I.x}</span>
        <span><strong>${esc(f.label)}</strong> (${esc(fmtValue(f.field, f.value))}) ${strength(f.impact, total)}${dir > 0 ? "supports approval" : "points toward rejection"}.</span></li>`;
      const baseText = ex.method === "naive_bayes_log_likelihood_ratio"
        ? `Before looking at this applicant, the model starts from the approval rate in its training split, <strong>${pct1(sigmoid(ex.base))}</strong>.`
        : `For an applicant with average values on every input, the model would give <strong>${pct1(sigmoid(ex.base))}</strong>.`;
      const ordered = r.approved ? pos.map((f) => reason(f, 1)).concat(neg.map((f) => reason(f, -1)))
                                 : neg.map((f) => reason(f, -1)).concat(pos.map((f) => reason(f, 1)));
      explain = `<div class="sub-title">Key reasons</div>
        <ul class="reasons"><li class="reason base"><span class="reason-icon">${I.info}</span><span>${baseText}</span></li>${ordered.join("")}</ul>
        <div class="sub-title"><span>Factor contributions</span><button type="button" class="chart-toggle" id="factors-all">Show all ${ex.factors.length}</button></div>
        <div id="factor-chart"></div>
        <p class="muted small" style="margin-top:8px">${ex.method === "naive_bayes_log_likelihood_ratio"
          ? "Each bar is that input's log-likelihood ratio in the Naive Bayes model. With the starting rate, they add up exactly to the model's log-odds of approval."
          : "Each bar is coefficient × scaled input in the logistic regression. With the intercept, they add up exactly to the model's log-odds of approval."}</p>`;
    } else {
      explain = `<div class="sub-title">How KNN decided</div>
        <p class="muted">K-Nearest Neighbors predicts from the ${ex.neighbours} most similar applicants in the training set.
          <strong style="color:var(--text)">${ex.approved_neighbours} of ${ex.neighbours}</strong> of them were approved.</p>
        <div class="neighbours">${Array.from({ length: ex.neighbours }, (_, i) => i < ex.approved_neighbours
          ? `<span class="neighbour yes" title="Approved neighbour">${I.check}</span>`
          : `<span class="neighbour no" title="Rejected neighbour">${I.x}</span>`).join("")}</div>
        <p class="muted small">KNN doesn't break its decision down by feature. Choose Naive Bayes or Logistic Regression for a factor-by-factor breakdown.</p>`;
    }

    const compare = `<div class="sub-title">All notebook models on this applicant</div>
      <div class="compare">${r.comparison.map((c) => `<div class="compare-row ${c.model === r.model ? "current" : ""}">
        <span class="compare-name">${swatch(c.model)} ${esc(modelShort(c.model))}</span>
        <div class="bar bar-sm"><span style="width:${(c.probability_approved * 100).toFixed(1)}%;background:${c.approved ? "var(--good)" : "var(--critical)"}"></span></div>
        <span class="num small" style="text-align:right;font-weight:650">${pct0(c.probability_approved)}</span>
        ${badge(c.approved, true)}</div>`).join("")}</div>
      <p class="muted small" style="margin-top:14px">${yesCount === r.comparison.length ? "All three models predict approval."
        : yesCount === 0 ? "All three models predict rejection." : `${yesCount} of ${r.comparison.length} models predict approval.`}</p>`;

    const context = r.data_context.length ? `<div class="sub-title">Similar applicants in the dataset</div>
      <div class="context-list">${r.data_context.map((c) => `<div class="context-row"><span>${esc(c.label)}</span>
        <span class="num small muted">${c.approved} of ${c.total} approved · <strong style="color:var(--text)">${pct0(c.approved / c.total)}</strong></span>
        <div class="bar bar-xs"><span style="width:${(100 * c.approved / c.total).toFixed(1)}%;background:var(--series-1)"></span></div></div>`).join("")}</div>`
      : `<p class="muted">No matching groups in the dataset summaries.</p>`;

    $("#result").innerHTML = `
      <div class="result-hero ${r.approved ? "approved" : "rejected"}">
        <div class="result-hero-top">
          <span class="badge badge-neutral">${swatch(r.model)}${esc(modelShort(r.model))}</span>
          ${r.history ? `<span class="badge badge-neutral">Saved · #${r.history.id}</span>` : ""}
        </div>
        ${C.gauge(p, color)}
        <div class="gauge-readout"><div class="gauge-value">${pct1(p)}</div><div class="gauge-label">Probability of approval</div></div>
        <div class="verdict-line"><span class="verdict ${r.approved ? "approved" : "rejected"}"><span class="verdict-icon">${r.approved ? I.check : I.x}</span>${r.approved ? "Likely approved" : "Likely rejected"}</span></div>
        <div class="verdict-sub">Decision threshold 50% · ${yesCount} of ${r.comparison.length} models predict approval</div>
      </div>
      ${pre ? `<div class="result-body" style="padding-bottom:0">${pre}</div>` : ""}
      <div class="tabs" role="tablist" style="margin-top:18px">
        <button class="tab" role="tab" aria-selected="true" data-tab="explain">Explanation</button>
        <button class="tab" role="tab" aria-selected="false" data-tab="compare">Compare models</button>
        <button class="tab" role="tab" aria-selected="false" data-tab="context">Similar applicants</button>
      </div>
      <div class="tab-panel" data-panel="explain">${explain}</div>
      <div class="tab-panel" data-panel="compare" hidden>${compare}</div>
      <div class="tab-panel" data-panel="context" hidden>${context}</div>
      <div class="disclaimer">Statistical estimate from a model trained on ${state.meta.train_size} historical applications. It is not a lending decision.</div>`;
    C.animateGauges($("#result"));

    $$("#result .tab").forEach((t) => t.addEventListener("click", () => {
      $$("#result .tab").forEach((x) => x.setAttribute("aria-selected", String(x === t)));
      $$("#result .tab-panel").forEach((pnl) => { pnl.hidden = pnl.dataset.panel !== t.dataset.tab; });
      C.redrawAll();
    }));

    if (ex.factors) {
      let showAll = false;
      const draw = () => {
        const data = (showAll ? ex.factors : ex.factors.slice(0, 8)).map((f) => ({ label: f.label, sub: fmtValue(f.field, f.value), value: f.impact }));
        C.card($("#factor-chart"), {
          ariaLabel: "Factor contributions",
          draw: (el, w) => C.diverging(el, w, {
            data, posColor: C.css("--pos"), negColor: C.css("--neg"), posLabel: "Approval", negLabel: "Rejection",
            fmt: (v) => (v > 0 ? "+" : "") + v.toFixed(2) + " log-odds",
          }),
        });
      };
      draw();
      $("#factors-all").addEventListener("click", (e) => {
        showAll = !showAll;
        e.currentTarget.textContent = showAll ? "Show top 8" : `Show all ${ex.factors.length}`;
        draw();
      });
    }
  }

  /* =========================================================== history */
  async function loadHistory() {
    if (!state.meta) return;
    state.historyStatus = "loading";
    if (!state.history.length) { renderHistory(); renderRecent(); }
    try {
      const { items } = await api("/api/history?limit=1000");
      state.history = items;
      state.historyStatus = "ready";
    } catch (e) {
      state.historyStatus = "error";
      state.historyError = e.message;
    }
    renderHistory();
    renderRecent();
  }

  function filteredHistory() {
    const { search, model, outcome, sort } = state.hq;
    const q = search.trim().toLowerCase();
    let items = state.history.filter((h) => (!model || h.model === model) && (!outcome || h.prediction === outcome));
    if (q) {
      items = items.filter((h) => {
        const a = h.applicant;
        const hay = [`#${h.id}`, String(h.id), modelLabel(h.model), modelShort(h.model), h.prediction === "Yes" ? "approved" : "rejected",
          a.Loan_Purpose, a.Employment_Status, a.Employer_Category, a.Property_Area, a.Marital_Status, a.Education_Level, a.Gender,
          String(a.Credit_Score), fmtDate(h.created_at)].join(" ").toLowerCase();
        return q.split(/\s+/).every((tok) => hay.includes(tok));
      });
    }
    const by = {
      newest: (a, b) => b.id - a.id, oldest: (a, b) => a.id - b.id,
      "prob-desc": (a, b) => b.probability_approved - a.probability_approved, "prob-asc": (a, b) => a.probability_approved - b.probability_approved,
    }[sort];
    return items.sort(by);
  }

  function syncHistoryActions() {
    const has = state.history.length > 0;
    $$('[data-action="export"], [data-action="clear"]').forEach((b) => { b.disabled = !has; });
  }

  function renderHistory() {
    const sel = $("#history-model");
    if (state.meta && sel.options.length === 1) {
      state.meta.models.forEach((m) => sel.insertAdjacentHTML("beforeend", `<option value="${m.id}">${esc(modelShort(m.id))}</option>`));
    }
    const count = $("#history-count");
    count.textContent = state.history.length;
    count.hidden = state.history.length === 0;
    syncHistoryActions();

    const body = $("#history-body"), foot = $("#history-foot");
    if (state.historyStatus === "loading" && !state.history.length) {
      $("#history-kpis").innerHTML = Array.from({ length: 3 }, () => '<div class="kpi skeleton" style="min-height:120px"></div>').join("");
      body.innerHTML = `<div class="table-wrap"><table><tbody>${Array.from({ length: 5 }, () =>
        `<tr class="sk-row"><td colspan="9"><div class="skeleton sk-line"></div></td></tr>`).join("")}</tbody></table></div>`;
      foot.hidden = true;
      return;
    }
    if (state.historyStatus === "error") {
      $("#history-kpis").innerHTML = "";
      body.innerHTML = `<div class="state"><span class="state-icon err">${I.alert}</span><h3>Couldn't load history</h3><p>${esc(state.historyError)}</p>
        <button class="btn btn-secondary" type="button" id="history-retry">${I.redo}Retry</button></div>`;
      $("#history-retry").addEventListener("click", loadHistory);
      foot.hidden = true;
      return;
    }

    const items = filteredHistory();
    const filtered = !!(state.hq.search || state.hq.model || state.hq.outcome);
    const approved = items.filter((h) => h.prediction === "Yes").length;
    const avg = items.length ? items.reduce((a, h) => a + h.probability_approved, 0) / items.length : 0;
    $("#history-kpis").innerHTML = [
      kpi({ label: filtered ? "Matching predictions" : "Total predictions", icon: I.history, value: fmtNum(items.length),
        foot: filtered ? `of ${fmtNum(state.history.length)} saved` : "Saved to your account" }),
      kpi({ label: "Predicted approvals", icon: I.check, value: items.length ? pct0(approved / items.length) : "—",
        bar: items.length ? `<span style="width:${(approved / items.length) * 100}%;background:var(--good)"></span>` : "",
        foot: `<strong>${approved}</strong> approved · ${items.length - approved} rejected` }),
      kpi({ label: "Average approval probability", icon: I.target, value: items.length ? pct1(avg) : "—",
        bar: items.length ? `<span style="width:${avg * 100}%;background:var(--series-1)"></span>` : "",
        foot: "Across the predictions shown" }),
    ].join("");

    if (!state.history.length) {
      body.innerHTML = `<div class="state"><span class="state-icon">${I.history}</span><h3>No predictions yet</h3>
        <p>Every prediction you run is saved here with its inputs, so you can review, re-run or export it.</p>
        <a class="btn btn-primary" href="#predict">${I.plus}Make a prediction</a></div>`;
      foot.hidden = true;
      return;
    }
    if (!items.length) {
      body.innerHTML = `<div class="state"><span class="state-icon">${I.search}</span><h3>No matching predictions</h3>
        <p>Nothing matches the current search and filters.</p>
        <button class="btn btn-secondary" type="button" id="history-reset">Clear filters</button></div>`;
      $("#history-reset").addEventListener("click", resetHistoryFilters);
      foot.hidden = true;
      return;
    }

    const pages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
    state.hq.page = Math.min(state.hq.page, pages);
    const start = (state.hq.page - 1) * PAGE_SIZE;
    const page = items.slice(start, start + PAGE_SIZE);
    body.innerHTML = `<div class="table-wrap"><table><thead><tr>
      <th>ID</th><th>Application</th><th>Model</th><th class="num">Credit</th><th class="num">DTI</th>
      <th class="num">Loan amount</th><th>Outcome</th><th>Probability</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>
      ${page.map((h) => {
        const a = h.applicant;
        return `<tr>
          <td><span class="cell-main num">#${h.id}</span><div class="cell-sub">${esc(fmtDate(h.created_at))}</div></td>
          <td><span class="cell-main">${esc(a.Loan_Purpose)} loan</span><div class="cell-sub">${esc(a.Employment_Status)} · ${esc(a.Property_Area)}</div></td>
          <td><span class="mini-model-name" style="font-weight:500">${swatch(h.model)}${esc(modelShort(h.model))}</span></td>
          <td class="num">${fmtNum(a.Credit_Score)}</td><td class="num">${Number(a.DTI_Ratio).toFixed(2)}</td>
          <td class="num">${fmtNum(a.Loan_Amount)}</td>
          <td>${badge(h.prediction === "Yes", true)}</td>
          <td><span class="prob-cell"><span class="bar bar-sm"><span style="width:${(h.probability_approved * 100).toFixed(1)}%;background:${h.prediction === "Yes" ? "var(--good)" : "var(--critical)"}"></span></span>
            <span class="num small" style="font-weight:650;min-width:44px">${pct1(h.probability_approved)}</span></span></td>
          <td><div class="row-actions">
            <button class="icon-btn" type="button" data-rerun="${h.id}" title="Open in prediction form" aria-label="Open prediction ${h.id} in the form">${I.open}</button>
            <button class="icon-btn danger" type="button" data-delete="${h.id}" title="Delete" aria-label="Delete prediction ${h.id}">${I.trash}</button>
          </div></td></tr>`;
      }).join("")}</tbody></table></div>`;
    foot.hidden = false;
    foot.innerHTML = `<span>Showing <strong>${start + 1}–${start + page.length}</strong> of ${items.length}</span>
      <div class="pager">
        <button class="btn btn-secondary btn-sm" type="button" data-page="${state.hq.page - 1}" ${state.hq.page === 1 ? "disabled" : ""} aria-label="Previous page">${I.chevL}</button>
        <span class="num">Page ${state.hq.page} of ${pages}</span>
        <button class="btn btn-secondary btn-sm" type="button" data-page="${state.hq.page + 1}" ${state.hq.page === pages ? "disabled" : ""} aria-label="Next page">${I.chevR}</button>
      </div>`;
  }

  function resetHistoryFilters() {
    state.hq = { ...state.hq, search: "", model: "", outcome: "", page: 1 };
    $("#history-search").value = ""; $("#history-model").value = ""; $("#history-outcome").value = "";
    renderHistory();
  }

  async function onHistoryClick(e) {
    const del = e.target.closest("[data-delete]");
    const rerun = e.target.closest("[data-rerun]");
    const pg = e.target.closest("[data-page]");
    if (pg && !pg.disabled) { state.hq.page = Number(pg.dataset.page); renderHistory(); return; }
    if (del) {
      del.disabled = true;
      try { await api(`/api/history/${del.dataset.delete}`, { method: "DELETE" }); toast(`Prediction #${del.dataset.delete} deleted`); await loadHistory(); }
      catch (err) { del.disabled = false; toast(err.message, "err"); }
    } else if (rerun) {
      const h = state.history.find((x) => String(x.id) === rerun.dataset.rerun);
      if (!h) return;
      fillForm(h.applicant);
      state.sample = null; $("#sample-note").hidden = true;
      state.selectedModel = h.model;
      $$("#model-picker input").forEach((r) => { r.checked = r.value === h.model; });
      syncActiveModel();
      location.hash = "#predict";
      toast(`Loaded prediction #${h.id} into the form`);
    }
  }

  async function clearHistory() {
    if (!state.history.length) return;
    if (!confirm(`Delete all ${state.history.length} saved predictions? This can't be undone.`)) return;
    try { const r = await api("/api/history", { method: "DELETE" }); toast(`Deleted ${r.deleted} predictions`); await loadHistory(); }
    catch (err) { toast(err.message, "err"); }
  }

  function exportCsv() {
    const items = filteredHistory();
    if (!items.length) { toast("Nothing to export", "err"); return; }
    const cols = ["id", "created_at", "model", "prediction", "probability_approved", ...ALL_FIELDS];
    const cell = (v) => { const s = String(v ?? ""); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const rows = items.map((h) => [h.id, h.created_at, h.model, h.prediction, h.probability_approved.toFixed(6), ...ALL_FIELDS.map((f) => h.applicant[f])].map(cell).join(","));
    const blob = new Blob([cols.join(",") + "\n" + rows.join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `creditwise_history_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    toast(`Exported ${items.length} prediction${items.length > 1 ? "s" : ""}`);
  }

  /* ============================================================== auth */
  const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/;
  const initials = (name) => name.trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?";

  function showAuth(mode) {
    $("#boot").hidden = true;
    $("#app-shell").hidden = true;
    $("#auth-screen").hidden = false;
    const signup = mode === "signup";
    $("#login-form").hidden = signup;
    $("#signup-form").hidden = !signup;
    document.title = `${signup ? "Create account" : "Log in"} · CreditWise`;
    const first = signup ? $("#signup-name") : $("#login-email");
    setTimeout(() => { if (!first.value) first.focus(); }, 30);
  }

  function setUser(user) {
    state.user = user;
    const ini = initials(user.name);
    ["#sidebar-avatar", "#topbar-avatar", "#menu-avatar"].forEach((s) => { $(s).textContent = ini; });
    $("#sidebar-user-name").textContent = user.name;
    $("#menu-user-name").textContent = user.name;
    $("#sidebar-user-email").textContent = user.email;
    $("#menu-user-email").textContent = user.email;
    $("#menu-user-since").textContent = `Member since ${new Date(user.created_at).toLocaleDateString(undefined, { dateStyle: "medium" })}`;
    $("#user-btn").setAttribute("aria-label", `Account menu for ${user.name}`);
  }

  function enterApp(user) {
    if (state.loadedFor && state.loadedFor !== user.id) {
      // A different account: start from a clean page so no previous user's data lingers.
      location.hash = "#" + (state.afterLogin || "dashboard");
      location.reload();
      return;
    }
    setUser(user);
    state.loadedFor = user.id;
    $("#boot").hidden = true;
    $("#auth-screen").hidden = true;
    $("#app-shell").hidden = false;
    const target = state.afterLogin || "dashboard";
    state.afterLogin = null;
    if (location.hash !== "#" + target) location.hash = "#" + target; else route();
    boot();
  }

  async function checkSession() {
    try {
      const { user } = await api("/api/auth/me");
      enterApp(user);
    } catch (e) {
      state.user = null;
      route();
      if (e.status !== 401) showAuthAlert("login", e.message);
    }
  }

  function onSessionExpired() {
    if (!state.user) return;
    state.user = null;
    state.afterLogin = currentView();
    toast("Your session has ended. Please log in again.", "err");
    location.hash = "#login";
  }

  function showAuthAlert(form, msg) {
    const box = $(`#${form}-alert`);
    if (!msg) { box.hidden = true; return; }
    box.innerHTML = `${I.alert}<div>${esc(msg)}</div>`;
    box.hidden = false;
  }
  function setAuthError(id, msg) {
    const f = $(`[data-afield="${id}"]`);
    f.classList.toggle("invalid", !!msg);
    $(".field-error", f).textContent = msg || "";
    const inp = $("#" + id);
    if (msg) inp.setAttribute("aria-invalid", "true"); else inp.removeAttribute("aria-invalid");
    return !msg;
  }
  function setBusy(btn, busy, labelText) {
    btn.disabled = busy;
    btn.classList.toggle("loading", busy);
    $(".btn-label", btn).textContent = labelText;
  }

  async function onLogin(e) {
    e.preventDefault();
    showAuthAlert("login", "");
    const email = $("#login-email").value.trim(), password = $("#login-password").value;
    const ok = [
      setAuthError("login-email", !email ? "Enter your email" : !EMAIL_RE.test(email) ? "Enter a valid email address" : ""),
      setAuthError("login-password", password ? "" : "Enter your password"),
    ].every(Boolean);
    if (!ok) { $("#login-form [aria-invalid]").focus(); return; }
    const btn = $("#login-btn");
    setBusy(btn, true, "Logging in…");
    try {
      const { user } = await api("/api/auth/login", { method: "POST", body: { email, password, remember: $("#login-remember").checked } });
      $("#login-password").value = "";
      toast(`Welcome back, ${user.name.split(" ")[0]}`);
      enterApp(user);
    } catch (err) {
      showAuthAlert("login", err.message);
      if (err.status === 401) $("#login-password").select();
    } finally { setBusy(btn, false, "Log in"); }
  }

  function passwordChecks(pw) {
    return { len: pw.length >= 8, letter: /[A-Za-z]/.test(pw), digit: /\d/.test(pw) };
  }
  function updateStrength() {
    const pw = $("#signup-password").value;
    const c = passwordChecks(pw);
    Object.entries(c).forEach(([k, v]) => $(`#pw-rules [data-rule="${k}"]`).classList.toggle("ok", v));
    let score = 0;
    if (pw) {
      score = 1;
      if (c.len && c.letter && c.digit) score = 2;
      if (score === 2 && pw.length >= 12) score = 3;
      if (score >= 2 && /[a-z]/.test(pw) && /[A-Z]/.test(pw) && /[^A-Za-z0-9]/.test(pw)) score = Math.min(4, score + 1);
      if (score === 3 && pw.length >= 16) score = 4;
    }
    $("#pw-strength").dataset.score = score;
    $("#pw-label").textContent = [" ", "Weak", "Fair", "Good", "Strong"][score];
  }

  async function onSignup(e) {
    e.preventDefault();
    showAuthAlert("signup", "");
    const name = $("#signup-name").value.trim(), email = $("#signup-email").value.trim();
    const password = $("#signup-password").value, confirm = $("#signup-confirm").value;
    const c = passwordChecks(password);
    const ok = [
      setAuthError("signup-name", name.length < 2 ? "Enter your full name (at least 2 characters)" : name.length > 80 ? "Name is too long" : ""),
      setAuthError("signup-email", !email ? "Enter your email" : !EMAIL_RE.test(email) ? "Enter a valid email address" : ""),
      setAuthError("signup-password", !password ? "Choose a password" : !c.len ? "Use at least 8 characters"
        : !(c.letter && c.digit) ? "Include at least one letter and one number" : password.length > 128 ? "Password is too long" : ""),
      setAuthError("signup-confirm", !confirm ? "Confirm your password" : confirm !== password ? "Passwords don't match" : ""),
    ].every(Boolean);
    if (!ok) { $("#signup-form [aria-invalid]").focus(); return; }
    const btn = $("#signup-btn");
    setBusy(btn, true, "Creating account…");
    try {
      const { user } = await api("/api/auth/signup", { method: "POST", body: { name, email, password } });
      $("#signup-form").reset(); updateStrength();
      toast(`Account created. Welcome, ${user.name.split(" ")[0]}!`);
      enterApp(user);
    } catch (err) {
      const mapped = (err.errors || []).filter((x) => ["name", "email", "password"].includes(x.field));
      mapped.forEach((x) => setAuthError(`signup-${x.field}`, x.message));
      if (!mapped.length) showAuthAlert("signup", err.message);
    } finally { setBusy(btn, false, "Create account"); }
  }

  async function logout() {
    try {
      await api("/api/auth/logout", { method: "POST" });
      location.hash = "#login";
      location.reload();
    } catch (e) { toast(e.message, "err"); }
  }

  function closeUserMenu() {
    $("#user-dropdown").hidden = true;
    $("#user-btn").setAttribute("aria-expanded", "false");
  }

  function initAuth() {
    $("#login-form").addEventListener("submit", onLogin);
    $("#signup-form").addEventListener("submit", onSignup);
    $("#signup-password").addEventListener("input", updateStrength);
    $$(".auth-form input").forEach((inp) => inp.addEventListener("input", () => {
      const f = inp.closest("[data-afield]");
      if (f && f.classList.contains("invalid")) setAuthError(f.dataset.afield, "");
    }));
    $$(".pw-toggle").forEach((b) => b.addEventListener("click", () => {
      const inp = $("#" + b.dataset.target), show = inp.type === "password";
      inp.type = show ? "text" : "password";
      b.setAttribute("aria-pressed", String(show));
      b.setAttribute("aria-label", show ? "Hide password" : "Show password");
    }));
    $$("[data-logout]").forEach((b) => b.addEventListener("click", logout));
    $("#user-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      const open = $("#user-dropdown").hidden;
      $("#user-dropdown").hidden = !open;
      $("#user-btn").setAttribute("aria-expanded", String(open));
    });
    document.addEventListener("click", (e) => { if (!e.target.closest(".user-menu")) closeUserMenu(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeUserMenu(); });
  }

  /* ============================================================== init */
  function init() {
    initTheme();
    initAuth();
    window.addEventListener("hashchange", route);
    window.addEventListener("scroll", () => $(".topbar").classList.toggle("scrolled", window.scrollY > 4), { passive: true });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSidebar(); });
    $("#menu-btn").addEventListener("click", () => ($("#sidebar").classList.contains("open") ? closeSidebar() : openSidebar()));
    $("#scrim").addEventListener("click", closeSidebar);
    $("#global-retry").addEventListener("click", boot);
    $("#page-actions").addEventListener("click", onPageAction);
    $("#predict-form").addEventListener("submit", submit);
    $("#reset-btn").addEventListener("click", resetForm);
    $("#history-body").addEventListener("click", onHistoryClick);
    $("#history-foot").addEventListener("click", onHistoryClick);
    let t;
    $("#history-search").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { state.hq.search = e.target.value; state.hq.page = 1; renderHistory(); }, 150); });
    $("#history-model").addEventListener("change", (e) => { state.hq.model = e.target.value; state.hq.page = 1; renderHistory(); });
    $("#history-outcome").addEventListener("change", (e) => { state.hq.outcome = e.target.value; state.hq.page = 1; renderHistory(); });
    $("#history-sort").addEventListener("change", (e) => { state.hq.sort = e.target.value; renderHistory(); });
    checkSession();
  }
  init();
})();
