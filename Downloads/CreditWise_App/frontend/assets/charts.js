/* CreditWise chart kit: dependency-free, responsive SVG charts.
 * Thin marks, 4px rounded data ends anchored to the baseline, hairline grid,
 * hover band + tooltip on every mark, and a table view of the same data. */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const registry = new Set();

  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const pct0 = (v) => Math.round(v * 100) + "%";
  const pct1 = (v) => (v * 100).toFixed(1) + "%";

  function el(tag, attrs = {}, parent) {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  }
  function text(parent, x, y, str, attrs = {}) {
    const t = el("text", { x, y, ...attrs }, parent);
    t.textContent = str;
    return t;
  }

  /* Bar paths: rounded (r) at the data end, square at the baseline. */
  function vBar(x, y, w, h, r = 4) {
    if (h <= 0.5) return "";
    r = Math.min(r, h, w / 2);
    return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
  }
  function hBar(x, y, w, h, r = 4, leftward = false) {
    if (w <= 0.5) return "";
    r = Math.min(r, w, h / 2);
    if (leftward) return `M${x + w},${y}H${x + r}Q${x},${y} ${x},${y + r}V${y + h - r}Q${x},${y + h} ${x + r},${y + h}H${x + w}Z`;
    return `M${x},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h - r}Q${x + w},${y + h} ${x + w - r},${y + h}H${x}Z`;
  }

  /* ------------------------------------------------------------ tooltip */
  const tipEl = () => document.getElementById("tooltip");
  function showTip(evt, html) {
    const t = tipEl();
    t.innerHTML = html;
    t.hidden = false;
    const pad = 14, r = t.getBoundingClientRect();
    let x = evt.clientX + pad, y = evt.clientY + pad;
    if (x + r.width > window.innerWidth - 8) x = evt.clientX - r.width - pad;
    if (y + r.height > window.innerHeight - 8) y = evt.clientY - r.height - pad;
    t.style.left = Math.max(8, x) + "px";
    t.style.top = Math.max(8, y) + "px";
  }
  function hideTip() { tipEl().hidden = true; }
  function tipHTML(title, rows) {
    return `<div class="tt-title">${esc(title)}</div>` + rows.map((r) =>
      `<div class="tt-row">${r.color ? `<span class="legend-swatch" style="background:${r.color}"></span>` : ""}${esc(r.label)}<b>${esc(r.value)}</b></div>`).join("");
  }
  function bindHover(chartEl, marks, hit, html, band) {
    const list = Array.isArray(marks) ? marks : [marks];
    const on = (e) => {
      chartEl.classList.add("hovering");
      list.forEach((m) => m.classList.add("hot"));
      if (band) band.classList.add("hot-band");
      showTip(e, html());
    };
    const off = () => {
      chartEl.classList.remove("hovering");
      list.forEach((m) => m.classList.remove("hot"));
      if (band) band.classList.remove("hot-band");
      hideTip();
    };
    hit.addEventListener("mousemove", on);
    hit.addEventListener("mouseleave", off);
    hit.addEventListener("touchstart", (e) => on(e.touches[0]), { passive: true });
    hit.addEventListener("touchend", off);
  }

  /* --------------------------------------------------------- chart card */
  const TABLE_ICON = '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 10v10"/></svg>';
  const CHART_ICON = '<svg viewBox="0 0 24 24"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>';
  /* opts: { title, subtitle, legend:[{label,color}], actions (html), draw(chartEl, width), table:{columns, rows} } */
  function card(host, opts) {
    host.innerHTML = `
      ${opts.title !== undefined ? `<div class="chart-head">
        <div><h3>${esc(opts.title)}</h3>${opts.subtitle ? `<p>${esc(opts.subtitle)}</p>` : ""}</div>
        <div class="card-head-actions">${opts.actions || ""}${opts.table ? `<button type="button" class="chart-toggle" aria-pressed="false">${TABLE_ICON}<span>Table</span></button>` : ""}</div>
      </div>` : ""}
      ${opts.legend && opts.legend.length > 1 ? `<div class="legend">${opts.legend.map((l) =>
        `<span class="legend-item"><span class="legend-swatch" style="background:${l.color}"></span>${esc(l.label)}</span>`).join("")}</div>` : ""}
      <div class="chart" role="img" aria-label="${esc(opts.title || opts.ariaLabel || "Chart")}"></div>
      <div class="table-wrap chart-table" hidden></div>`;
    const chartEl = host.querySelector(".chart");
    const tableEl = host.querySelector(".chart-table");
    if (opts.table) {
      tableEl.innerHTML = table(opts.table.columns, opts.table.rows);
      const btn = host.querySelector(".chart-toggle");
      btn.addEventListener("click", () => {
        const showTable = tableEl.hidden;
        tableEl.hidden = !showTable;
        chartEl.hidden = showTable;
        btn.innerHTML = showTable ? `${CHART_ICON}<span>Chart</span>` : `${TABLE_ICON}<span>Table</span>`;
        btn.setAttribute("aria-pressed", String(showTable));
      });
    }
    const entry = {
      draw() {
        if (!chartEl.isConnected) { registry.delete(entry); return; }
        if (chartEl.hidden || !chartEl.offsetParent) return; // not visible: draw when shown
        const w = Math.floor(chartEl.clientWidth);
        if (w > 0 && w !== entry.w) { entry.w = w; chartEl.innerHTML = ""; opts.draw(chartEl, w); }
      },
      force() { entry.w = 0; entry.draw(); },
    };
    registry.add(entry);
    entry.draw();
    return entry;
  }

  function table(columns, rows) {
    return `<table><thead><tr>${columns.map((c) => `<th class="${c.num ? "num" : ""}">${esc(c.label)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr>${r.map((v, i) => `<td class="${columns[i].num ? "num" : ""}">${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  }

  function thresholdTag(g, x, label) {
    const w = label.length * 6.6 + 14;
    el("rect", { x: x - w / 2, y: -22, width: w, height: 18, rx: 9, class: "threshold-bg" }, g);
    text(g, x, -9, label, { "text-anchor": "middle", class: "threshold-tag", "font-size": "11", "font-weight": "600" });
  }

  /* ------------------------------------------- vertical columns (1 series) */
  function columns(chartEl, width, { data, color, threshold, height = 260, yMax = 1, fmt = pct0, labelExtreme = true }) {
    const m = { t: 30, r: 6, b: 34, l: 40 };
    const iw = width - m.l - m.r, ih = height - m.t - m.b;
    const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, width, height }, chartEl);
    const g = el("g", { transform: `translate(${m.l},${m.t})` }, svg);
    [0, 0.25, 0.5, 0.75, 1].forEach((t) => {
      const y = ih - t * ih;
      el("line", { x1: 0, x2: iw, y1: y, y2: y, class: t === 0 ? "baseline" : "gridline" }, g);
      text(g, -10, y + 4, fmt(t * yMax), { "text-anchor": "end" });
    });
    const band = iw / data.length;
    const bw = Math.min(26, band * 0.56);
    const maxIdx = data.reduce((best, d, i) => (d.value > data[best].value ? i : best), 0);
    const longest = Math.max(...data.map((d) => String(d.label).length));
    const thin = band < longest * 6.8 + 8;
    data.forEach((d, i) => {
      const hb = el("rect", { x: band * i + 2, y: 0, width: band - 4, height: ih, rx: 8, class: "hover-band" }, g);
      const x = band * i + (band - bw) / 2;
      const h = (d.value / yMax) * ih;
      const mark = el("path", { d: vBar(x, ih - h, bw, h), fill: color || css("--series-1"), class: "mark" }, g);
      if (!thin || i % 2 === 0) text(g, band * i + band / 2, ih + 20, d.label, { "text-anchor": "middle" });
      if (labelExtreme && i === maxIdx && d.value > 0) text(g, band * i + band / 2, ih - h - 8, fmt(d.value), { "text-anchor": "middle", class: "label-strong" });
      const hit = el("rect", { x: band * i, y: -m.t, width: band, height: ih + m.t + 24, class: "hit" }, g);
      bindHover(chartEl, mark, hit, () => tipHTML(d.label, d.tip || [{ label: "Value", value: fmt(d.value) }]), hb);
    });
    if (threshold) {
      const x = band * (threshold.afterIndex + 1);
      el("line", { x1: x, x2: x, y1: -4, y2: ih, class: "threshold" }, g);
      thresholdTag(g, x, threshold.label);
    }
  }

  /* --------------------------------------------- horizontal bars (1 series) */
  function bars(chartEl, width, { data, color, fmt = pct0, max = 1 }) {
    const rowH = 38, m = { t: 2, r: 52, b: 2, l: Math.min(120, width * 0.34) };
    const height = m.t + m.b + rowH * data.length;
    const iw = width - m.l - m.r;
    const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, width, height }, chartEl);
    const g = el("g", { transform: `translate(${m.l},${m.t})` }, svg);
    data.forEach((d, i) => {
      const y = i * rowH, bh = Math.min(16, rowH * 0.5);
      const hb = el("rect", { x: -m.l + 4, y: y + 2, width: width - 8, height: rowH - 4, rx: 8, class: "hover-band" }, g);
      el("rect", { x: 0, y: y + (rowH - bh) / 2, width: iw, height: bh, rx: 4, fill: css("--sunk") }, g);
      const w = (d.value / max) * iw;
      const mark = el("path", { d: hBar(0, y + (rowH - bh) / 2, w, bh), fill: color || css("--series-1"), class: "mark" }, g);
      text(g, -12, y + rowH / 2 + 4, d.label, { "text-anchor": "end", class: "label-secondary" });
      text(g, iw + 10, y + rowH / 2 + 4, fmt(d.value), { class: "label-strong" });
      const hit = el("rect", { x: -m.l, y, width, height: rowH, class: "hit" }, g);
      bindHover(chartEl, mark, hit, () => tipHTML(d.label, d.tip || [{ label: "Value", value: fmt(d.value) }]), hb);
    });
    el("line", { x1: 0, x2: 0, y1: 0, y2: rowH * data.length, class: "baseline" }, g);
  }

  /* -------------------------------------------------- grouped columns */
  function grouped(chartEl, width, { categories, series, height = 290, yMax = 1, fmt = pct0, tipFmt = pct1 }) {
    const m = { t: 14, r: 6, b: 34, l: 40 };
    const iw = width - m.l - m.r, ih = height - m.t - m.b;
    const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, width, height }, chartEl);
    const g = el("g", { transform: `translate(${m.l},${m.t})` }, svg);
    const scale = (v) => ih - (v / yMax) * ih;
    for (let i = 0; i <= 4; i++) {
      const t = (i / 4) * yMax, y = scale(t);
      el("line", { x1: 0, x2: iw, y1: y, y2: y, class: i === 0 ? "baseline" : "gridline" }, g);
      text(g, -10, y + 4, fmt(t), { "text-anchor": "end" });
    }
    const band = iw / categories.length;
    const gap = 2;
    const bw = Math.min(24, (band * 0.66 - gap * (series.length - 1)) / series.length);
    const groupW = series.length * bw + (series.length - 1) * gap;
    categories.forEach((c, ci) => {
      const hb = el("rect", { x: band * ci + 4, y: 0, width: band - 8, height: ih, rx: 8, class: "hover-band" }, g);
      const x0 = band * ci + (band - groupW) / 2;
      const grp = el("g", { class: "mark" }, g);
      series.forEach((s, si) => {
        const y = scale(s.values[ci]);
        el("path", { d: vBar(x0 + si * (bw + gap), y, bw, ih - y), fill: s.color }, grp);
      });
      text(g, band * ci + band / 2, ih + 21, c, { "text-anchor": "middle", class: "label-secondary" });
      const hit = el("rect", { x: band * ci, y: 0, width: band, height: ih + 24, class: "hit" }, g);
      bindHover(chartEl, grp, hit, () => tipHTML(c, series.map((s) => ({ label: s.name, value: tipFmt(s.values[ci]), color: s.color }))), hb);
    });
  }

  /* ------------------------------------------------- diverging bars */
  function diverging(chartEl, width, { data, posColor, negColor, posLabel, negLabel, fmt }) {
    const rowH = 34, m = { t: 24, r: 10, b: 4, l: Math.min(170, width * 0.4) };
    const height = m.t + m.b + rowH * data.length;
    const iw = width - m.l - m.r;
    const max = Math.max(...data.map((d) => Math.abs(d.value)), 1e-9);
    const mid = iw / 2;
    const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, width, height }, chartEl);
    const g = el("g", { transform: `translate(${m.l},${m.t})` }, svg);
    text(g, mid - 8, -10, "← " + negLabel, { "text-anchor": "end" });
    text(g, mid + 8, -10, posLabel + " →");
    data.forEach((d, i) => {
      const y = i * rowH, bh = Math.min(16, rowH * 0.5), w = (Math.abs(d.value) / max) * (mid - 4);
      const pos = d.value >= 0;
      const hb = el("rect", { x: -m.l + 2, y: y + 1, width: width - 4, height: rowH - 2, rx: 8, class: "hover-band" }, g);
      const mark = el("path", {
        d: pos ? hBar(mid, y + (rowH - bh) / 2, w, bh) : hBar(mid - w, y + (rowH - bh) / 2, w, bh, 4, true),
        fill: pos ? posColor : negColor, class: "mark",
      }, g);
      text(g, -12, y + rowH / 2 - 1, d.label, { "text-anchor": "end", class: "label-strong" });
      if (d.sub !== undefined) text(g, -12, y + rowH / 2 + 12, d.sub, { "text-anchor": "end" });
      const hit = el("rect", { x: -m.l, y, width, height: rowH, class: "hit" }, g);
      bindHover(chartEl, mark, hit, () => tipHTML(d.label, [
        { label: "Your value", value: d.sub },
        { label: pos ? "Toward approval" : "Toward rejection", value: fmt(d.value), color: pos ? posColor : negColor },
      ]), hb);
    });
    el("line", { x1: mid, x2: mid, y1: -2, y2: rowH * data.length, class: "baseline" }, g);
  }

  /* ------------------------------------------------- semicircle gauge */
  function gauge(p, color) {
    const cx = 120, cy = 116, r = 96, sw = 16;
    const pt = (t, rr = r) => {
      const a = Math.PI * (1 - t);
      return [cx + rr * Math.cos(a), cy - rr * Math.sin(a)];
    };
    const arc = (t0, t1) => {
      const [x0, y0] = pt(t0), [x1, y1] = pt(t1);
      return `M${x0.toFixed(2)},${y0.toFixed(2)} A${r},${r} 0 0 1 ${x1.toFixed(2)},${y1.toFixed(2)}`;
    };
    const len = Math.PI * r;
    const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => {
      const [a, b] = pt(t, r - sw / 2 - 4), [c, d] = pt(t, r - sw / 2 - (t === 0.5 ? 14 : 9));
      return `<line class="g-tick" x1="${a}" y1="${b}" x2="${c}" y2="${d}" stroke-width="${t === 0.5 ? 2 : 1.4}" stroke-linecap="round"/>`;
    }).join("");
    const [lx, ly] = pt(0.5, r - sw / 2 - 24);
    return `<svg class="gauge" viewBox="0 0 240 132" role="img" aria-label="Approval probability ${pct1(p)}">
      <path class="g-track" d="${arc(0, 1)}" fill="none" stroke-width="${sw}" stroke-linecap="round"/>
      <path class="g-value" d="${arc(0, 1)}" fill="none" stroke="${color}" stroke-width="${sw}" stroke-linecap="round"
        stroke-dasharray="${len}" stroke-dashoffset="${len}" data-target="${(len * (1 - p)).toFixed(2)}"
        style="transition:stroke-dashoffset 1s cubic-bezier(.2,.8,.2,1)"/>
      ${ticks}
      <text class="g-tick-text" x="${lx}" y="${ly + 2}" text-anchor="middle">50%</text>
      <text class="g-tick-text" x="${cx - r}" y="${cy + 14}" text-anchor="middle">0%</text>
      <text class="g-tick-text" x="${cx + r}" y="${cy + 14}" text-anchor="middle">100%</text>
    </svg>`;
  }
  function animateGauges(root) {
    requestAnimationFrame(() => requestAnimationFrame(() => {
      root.querySelectorAll(".g-value").forEach((p) => { p.style.strokeDashoffset = p.dataset.target; });
    }));
  }

  /* ------------------------------------------------- confusion matrix */
  function confusion(host, cm) {
    const [[tn, fp], [fn, tp]] = cm;
    const max = Math.max(tn, fp, fn, tp);
    const steps = ["--seq-1", "--seq-2", "--seq-3", "--seq-4", "--seq-5"];
    const dark = document.documentElement.dataset.theme === "dark";
    const cell = (v, k) => {
      const idx = Math.min(4, Math.floor((v / max) * 4.999));
      const ink = dark ? (idx >= 3 ? "#0b1220" : "#e9eef8") : (idx >= 2 ? "#ffffff" : "#0f1b33");
      return `<div class="cm-cell" style="background:var(${steps[idx]});color:${ink}" title="${esc(k)}: ${v}"><span class="v">${v}</span><span class="k">${esc(k)}</span></div>`;
    };
    const total = tn + fp + fn + tp;
    host.innerHTML = `
      <div class="cm">
        <div></div><div class="cm-axis">Predicted rejected</div><div class="cm-axis">Predicted approved</div>
        <div class="cm-axis row">Actually rejected</div>${cell(tn, "True negatives")}${cell(fp, "False positives")}
        <div class="cm-axis row">Actually approved</div>${cell(fn, "False negatives")}${cell(tp, "True positives")}
      </div>
      <div class="cm-summary">
        <div><b>${tn + tp} / ${total}</b>classified correctly</div>
        <div><b>${fp + fn}</b>misclassified (${fp} FP · ${fn} FN)</div>
      </div>
      <div class="cm-caption"><span>Darker cell = more applicants</span><span>${total} test applicants</span></div>`;
  }

  let resizeTimer;
  window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(redrawAll, 120); });
  function redrawAll(force) { registry.forEach((e) => (force ? e.force() : e.draw())); }

  window.CWCharts = { card, columns, bars, grouped, diverging, gauge, animateGauges, confusion, table, tipHTML, showTip, hideTip, pct0, pct1, css, esc, redrawAll };
})();
