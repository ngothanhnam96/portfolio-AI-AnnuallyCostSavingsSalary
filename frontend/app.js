"use strict";

const numberFormat = new Intl.NumberFormat("vi-VN");
const compactFormat = new Intl.NumberFormat("vi-VN", { notation: "compact", maximumFractionDigits: 1 });
const vnd = (amount) => `${numberFormat.format(amount)} ₫`;
const pct = (ratio) => (ratio === null || ratio === undefined ? "—" : `${Math.round(ratio * 100)}%`);

const GROUP_LABELS = { chi: "Chi", chi_ho: "Chi hộ", tiet_kiem: "Tiết kiệm", thu: "Thu" };
const SERIES = [
  { key: "thu", label: "Thu", color: "--series-thu" },
  { key: "chi", label: "Chi", color: "--series-chi" },
  { key: "tiet_kiem", label: "Tiết kiệm", color: "--series-tiet-kiem" },
];
const STATUS_LABELS = {
  critical: "Nghiêm trọng",
  warning: "Cảnh báo",
  info: "Gợi ý",
  ok: "Đúng kế hoạch",
  at_risk: "Có nguy cơ",
  over: "Vượt",
  none: "Chưa đặt",
};

const state = { month: "", categories: [], editingId: null, cuts: {}, trend: [] };
const $ = (selector) => document.querySelector(selector);

/** Local calendar date (toISOString would shift to UTC, i.e. the previous day before 7am in VN). */
function localIsoDate(date = new Date()) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Mirror of app.importer.parse_amount: 80k, 1.5tr, 1.234.000, 250000. */
function parseAmount(raw) {
  const text = raw.trim().toLowerCase().replace(/\s|₫|đ|vnd$/g, "");
  const match = text.match(/^(\d+(?:[.,]\d+)*)(k|tr|m)?$/);
  if (!match) return null;
  const [, number, suffix] = match;
  if (suffix) {
    const multiplier = suffix === "k" ? 1_000 : 1_000_000;
    return Math.round(parseFloat(number.replace(",", ".")) * multiplier);
  }
  return parseInt(number.replace(/[.,]/g, ""), 10);
}

let toastTimer;
function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { element.hidden = true; }, 4000);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = Array.isArray(body.detail) ? body.detail.map((item) => item.msg).join("; ") : body.detail;
    } catch { /* keep statusText */ }
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

// Rendering -------------------------------------------------------------------------------

function renderKpis(summary) {
  const { groups } = summary;
  const tiles = [
    { label: "Thu", value: groups.thu, edge: "--series-thu" },
    { label: "Chi", value: groups.chi, edge: "--series-chi", sub: `${pct(summary.spend_ratio)} thu nhập` },
    { label: "Chi hộ", value: groups.chi_ho, edge: "--tint-chi-ho" },
    { label: "Tiết kiệm", value: groups.tiet_kiem, edge: "--series-tiet-kiem" },
    { label: "Còn lại", value: summary.balance, edge: "--tint-balance", negative: summary.balance < 0 },
    { label: "Tỷ lệ tiết kiệm", text: pct(summary.savings_rate), edge: "--accent", sub: "mục tiêu ≥ 20%" },
  ];
  $("#kpis").innerHTML = tiles.map((tile) => `
    <div class="kpi${tile.negative ? " negative" : ""}" style="--kpi-edge: var(${tile.edge})">
      <div class="label">${tile.label}</div>
      <div class="value">${tile.text ?? vnd(tile.value)}</div>
      ${tile.sub ? `<div class="sub">${tile.sub}</div>` : ""}
    </div>`).join("");
}

function badge(status) {
  return `<span class="badge ${status}"><span class="dot" aria-hidden="true"></span>${STATUS_LABELS[status]}</span>`;
}

function renderInsights(insights) {
  $("#insights").innerHTML = insights.map((insight) => `
    <li class="insight">
      ${badge(insight.severity)}
      <span class="title">${escapeHtml(insight.title)}</span>
      <span class="detail">${escapeHtml(insight.detail)}</span>
      ${insight.annual_impact > 0 ? `<span class="impact">≈ ${vnd(insight.annual_impact)} / năm</span>` : ""}
    </li>`).join("");
}

function renderProjection(projection) {
  $("#projection-year").textContent = projection.year;
  const { projected, ytd, monthly_average: average } = projection;
  const cells = [
    { label: "Tiết kiệm dự kiến cả năm", value: vnd(projected.tiet_kiem) },
    { label: "Còn lại dự kiến", value: vnd(projected.balance) },
    { label: "Tỷ lệ tiết kiệm dự kiến", value: pct(projection.projected_savings_rate) },
    { label: "Đã tiết kiệm (YTD)", value: vnd(ytd.tiet_kiem) },
    { label: "Chi trung bình / tháng", value: vnd(average.chi) },
    { label: "Số tháng đã theo dõi", value: projection.tracked_months },
  ];
  $("#projection").innerHTML = `<div class="projection">${cells.map((cell) => `
    <div><div class="label">${cell.label}</div><div class="value">${cell.value}</div></div>`).join("")}</div>`;
}

function renderWhatIfControls() {
  const spending = state.categories.filter((category) => category.group === "chi");
  $("#what-if").innerHTML = spending.map((category) => `
    <label class="what-if-row">
      <span>${escapeHtml(category.label)}</span>
      <input type="range" min="0" max="50" step="5" value="${Math.round((state.cuts[category.id] || 0) * 100)}"
        data-category="${category.id}" aria-label="Giảm ${escapeHtml(category.label)} (%)">
      <output>${Math.round((state.cuts[category.id] || 0) * 100)}%</output>
    </label>`).join("");
}

let whatIfTimer;
function scheduleWhatIf() {
  clearTimeout(whatIfTimer);
  whatIfTimer = setTimeout(runWhatIf, 200);
}

async function runWhatIf() {
  const result = await api("/api/what-if", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cuts: state.cuts }),
  });
  $("#what-if-total").textContent = result.annual_gain
    ? `Tiết kiệm thêm ${vnd(result.monthly_gain)}/tháng ≈ ${vnd(result.annual_gain)}/năm`
    : "Kéo thanh trượt để xem số tiền tiết kiệm thêm mỗi năm.";
}

function renderSheet(sheet) {
  $("#sheet-month").textContent = sheet.month.split("-").reverse().join("/");
  const columns = sheet.columns;
  const groupSpans = [];
  for (const column of columns) {
    const last = groupSpans[groupSpans.length - 1];
    if (last && last.group === column.group) last.span += 1;
    else groupSpans.push({ group: column.group, span: 1 });
  }

  const head = `
    <thead>
      <tr class="group-row"><th colspan="2"></th>${groupSpans.map((group) =>
        `<th colspan="${group.span}" class="tint-${group.group}">${GROUP_LABELS[group.group]}</th>`).join("")}<th></th></tr>
      <tr><th>Ngày</th><th>Tên chi phí</th>${columns.map((column) =>
        `<th class="num">${escapeHtml(column.label)}</th>`).join("")}<th></th></tr>
    </thead>`;

  const body = sheet.rows.length ? sheet.rows.map((row) => `
    <tr data-id="${escapeHtml(row.id)}" class="${row.id === state.editingId ? "editing" : ""}">
      <td>${row.date.split("-").reverse().join("/")}</td>
      <td title="${escapeHtml(row.note)}">${escapeHtml(row.name)}</td>
      ${columns.map((column) => `<td class="num">${column.id === row.category ? numberFormat.format(row.amount) : ""}</td>`).join("")}
      <td>
        <button class="icon-button" data-action="edit" aria-label="Sửa">✎</button>
        <button class="icon-button" data-action="delete" aria-label="Xoá">✕</button>
      </td>
    </tr>`).join("")
    : `<tr><td class="empty" colspan="${columns.length + 3}">Chưa có giao dịch. Thêm ở form phía trên hoặc Import CSV / Excel.</td></tr>`;

  const totalRow = `<tr class="total-row"><td>Total</td><td></td>${columns.map((column) =>
    `<td class="num tint-${column.group}">${numberFormat.format(sheet.total[column.id])}</td>`).join("")}<td></td></tr>`;
  const allRow = `<tr class="all-row"><td>All</td><td></td>${groupSpans.map((group) =>
    `<td class="num tint-${group.group}" colspan="${group.span}">${numberFormat.format(sheet.all[group.group])}</td>`).join("")}
    <td class="num tint-balance" title="Còn lại = Thu − Chi − Chi hộ − Tiết kiệm">${numberFormat.format(sheet.all.balance)}</td></tr>`;

  $("#sheet").innerHTML = `${head}<tbody>${body}</tbody><tfoot>${totalRow}${allRow}</tfoot>`;
  state.rows = sheet.rows;
}

function renderBudgets(rows) {
  $("#budgets").innerHTML = rows.map((row) => {
    const used = row.used ?? 0;
    const fill = row.status === "over" ? "--critical" : row.status === "at_risk" ? "--warning" : "--good";
    return `
      <div class="budget-row">
        <div><strong>${escapeHtml(row.label)}</strong><div class="budget-meta">${vnd(row.spent)} đã chi</div></div>
        <input type="text" inputmode="numeric" value="${row.budget ? numberFormat.format(row.budget) : ""}"
          placeholder="Ngân sách" data-category="${row.category}" aria-label="Ngân sách ${escapeHtml(row.label)}">
        <div>
          <div class="bar" role="img" aria-label="Đã dùng ${pct(row.used)}">
            <span class="fill" style="width:${Math.min(used, 1) * 100}%; --fill: var(${fill})"></span>
            ${row.budget && row.pace < 1 && row.pace > 0 ? `<span class="pace" style="left:${row.pace * 100}%" title="Tiến độ tháng"></span>` : ""}
          </div>
          <div class="budget-meta">${!row.budget ? "" : row.remaining < 0 ? `${pct(row.used)} · vượt ${vnd(-row.remaining)}` : `${pct(row.used)} · còn ${vnd(row.remaining)}`}</div>
        </div>
        ${badge(row.status)}
      </div>`;
  }).join("");
}

// Trend chart: grouped bars, one axis, legend + hover tooltip + table view -----------------

function renderLegend() {
  $("#trend-legend").innerHTML = SERIES.map((series) =>
    `<span><i style="background: var(${series.color})"></i>${series.label}</span>`).join("");
}

function niceMax(value) {
  if (value <= 0) return 1_000_000;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].find((candidate) => candidate * magnitude >= value);
  return step * magnitude;
}

function renderTrend(rows) {
  state.trend = rows;
  const container = $("#trend-chart");
  const width = Math.max(container.clientWidth, 320);
  const height = 260;
  const margin = { top: 12, right: 8, bottom: 28, left: 52 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const max = niceMax(Math.max(...rows.flatMap((row) => SERIES.map((series) => row[series.key]))));
  const y = (value) => margin.top + plotHeight - (value / max) * plotHeight;
  const band = plotWidth / rows.length;
  const gap = 2;
  const barWidth = Math.max(3, Math.min(18, (band * 0.7 - gap * (SERIES.length - 1)) / SERIES.length));
  const groupWidth = barWidth * SERIES.length + gap * (SERIES.length - 1);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((fraction) => fraction * max);
  const labelEvery = width < 520 ? 2 : 1;

  const grid = ticks.map((tick) => `
    <line x1="${margin.left}" x2="${width - margin.right}" y1="${y(tick)}" y2="${y(tick)}" stroke="var(--grid)" />
    <text x="${margin.left - 6}" y="${y(tick) + 4}" text-anchor="end">${compactFormat.format(tick)}</text>`).join("");

  const bars = rows.map((row, index) => {
    const x0 = margin.left + index * band + (band - groupWidth) / 2;
    const marks = SERIES.map((series, seriesIndex) => {
      const value = row[series.key];
      const top = y(value);
      const barHeight = margin.top + plotHeight - top;
      if (barHeight <= 0) return "";
      const x = x0 + seriesIndex * (barWidth + gap);
      const radius = Math.min(4, barWidth / 2, barHeight);
      // Rounded data end, square baseline.
      return `<path fill="var(${series.color})" d="M${x},${top + barHeight} V${top + radius}
        Q${x},${top} ${x + radius},${top} H${x + barWidth - radius} Q${x + barWidth},${top} ${x + barWidth},${top + radius}
        V${top + barHeight} Z" />`;
    }).join("");
    const label = index % labelEvery === 0 || index === rows.length - 1
      ? `<text x="${margin.left + index * band + band / 2}" y="${height - 8}" text-anchor="middle">${row.month.slice(5)}/${row.month.slice(2, 4)}</text>`
      : "";
    const hit = `<rect class="hit" data-index="${index}" x="${margin.left + index * band}" y="${margin.top}"
      width="${band}" height="${plotHeight}" fill="transparent" />`;
    return marks + label + hit;
  }).join("");

  container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Thu, chi và tiết kiệm 12 tháng gần nhất">
    ${grid}
    <line x1="${margin.left}" x2="${width - margin.right}" y1="${y(0)}" y2="${y(0)}" stroke="var(--text-2)" />
    ${bars}
  </svg>`;

  $("#trend-table").innerHTML = `<table>
    <thead><tr><th>Tháng</th>${SERIES.map((series) => `<th class="num">${series.label}</th>`).join("")}<th class="num">Còn lại</th></tr></thead>
    <tbody>${rows.map((row) => `<tr><td>${row.month}</td>${SERIES.map((series) =>
      `<td class="num">${numberFormat.format(row[series.key])}</td>`).join("")}<td class="num">${numberFormat.format(row.balance)}</td></tr>`).join("")}</tbody>
  </table>`;
}

function showTrendTooltip(event) {
  const hit = event.target.closest(".hit");
  const tooltip = $("#tooltip");
  if (!hit) { tooltip.hidden = true; return; }
  const row = state.trend[Number(hit.dataset.index)];
  tooltip.innerHTML = `<strong>Tháng ${row.month.slice(5)}/${row.month.slice(0, 4)}</strong>
    ${SERIES.map((series) => `<div class="row"><span><i style="background: var(${series.color})"></i>${series.label}</span><span>${vnd(row[series.key])}</span></div>`).join("")}
    <div class="row"><span>Còn lại</span><span>${vnd(row.balance)}</span></div>`;
  tooltip.hidden = false;
  const { innerWidth } = window;
  const left = Math.min(event.clientX + 14, innerWidth - tooltip.offsetWidth - 8);
  tooltip.style.left = `${Math.max(8, left)}px`;
  tooltip.style.top = `${event.clientY + 14}px`;
}

// Data flow -------------------------------------------------------------------------------

async function loadMonth() {
  const month = state.month;
  $("#export-link").href = `/api/months/${month}/export.csv`;
  const [summary, sheet, budgets, insights, trend, projection] = await Promise.all([
    api(`/api/months/${month}/summary`),
    api(`/api/months/${month}/sheet`),
    api(`/api/months/${month}/budgets`),
    api(`/api/months/${month}/insights`),
    api(`/api/trend?end=${month}&months=12`),
    api(`/api/projection?year=${month.slice(0, 4)}`),
  ]);
  renderKpis(summary);
  renderSheet(sheet);
  renderBudgets(budgets);
  renderInsights(insights);
  renderTrend(trend);
  renderProjection(projection);
  await runWhatIf();
}

function resetForm() {
  const form = $("#tx-form");
  form.reset();
  state.editingId = null;
  const today = localIsoDate();
  form.date.value = today.startsWith(state.month) ? today : `${state.month}-01`;
  $("#tx-submit").textContent = "Thêm";
  $("#tx-cancel").hidden = true;
  document.querySelectorAll(".sheet tr.editing").forEach((row) => row.classList.remove("editing"));
}

async function submitTransaction(event) {
  event.preventDefault();
  const form = event.target;
  const amount = parseAmount(form.amount.value);
  if (!amount || amount <= 0) {
    toast("Số tiền không hợp lệ. Ví dụ: 80k, 1.5tr, 250000");
    form.amount.focus();
    return;
  }
  const payload = {
    date: form.date.value,
    name: form.name.value,
    category: form.category.value,
    amount,
    note: form.note.value,
  };
  const editing = state.editingId;
  try {
    await api(editing ? `/api/transactions/${encodeURIComponent(editing)}` : "/api/transactions", {
      method: editing ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    toast(editing ? "Đã cập nhật" : `Đã thêm ${vnd(amount)}`);
    const keepCategory = form.category.value;
    resetForm();
    form.category.value = keepCategory;
    const month = payload.date.slice(0, 7);
    if (month !== state.month) setMonth(month);
    else await loadMonth();
    form.name.focus();
  } catch (error) {
    toast(`Lỗi: ${error.message}`);
  }
}

async function onSheetClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const id = button.closest("tr").dataset.id;
  const row = state.rows.find((item) => item.id === id);
  if (button.dataset.action === "edit") {
    const form = $("#tx-form");
    state.editingId = id;
    form.date.value = row.date;
    form.name.value = row.name;
    form.category.value = row.category;
    form.amount.value = numberFormat.format(row.amount);
    form.note.value = row.note;
    $("#tx-submit").textContent = "Lưu";
    $("#tx-cancel").hidden = false;
    document.querySelectorAll(".sheet tr.editing").forEach((tr) => tr.classList.remove("editing"));
    button.closest("tr").classList.add("editing");
    form.scrollIntoView({ behavior: "smooth", block: "center" });
    form.name.focus();
  } else if (button.dataset.action === "delete") {
    if (button.dataset.confirm !== "1") {
      // Two-step delete instead of confirm(): first click arms, second click deletes.
      button.dataset.confirm = "1";
      button.textContent = "Xoá?";
      setTimeout(() => { button.dataset.confirm = ""; button.textContent = "✕"; }, 3000);
      return;
    }
    await api(`/api/transactions/${encodeURIComponent(id)}`, { method: "DELETE" });
    if (state.editingId === id) resetForm();
    toast(`Đã xoá "${row.name}"`);
    await loadMonth();
  }
}

async function onBudgetChange(event) {
  const input = event.target.closest("input[data-category]");
  if (!input) return;
  const amount = input.value.trim() ? parseAmount(input.value) : 0;
  if (amount === null) {
    toast("Ngân sách không hợp lệ");
    return;
  }
  await api(`/api/months/${state.month}/budgets/${input.dataset.category}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ amount }),
  });
  toast("Đã lưu ngân sách");
  await loadMonth();
}

async function onImport(event) {
  const file = event.target.files[0];
  event.target.value = "";
  if (!file) return;
  try {
    const result = await api("/api/import", {
      method: "POST",
      // Raw bytes: the server detects CSV vs .xlsx from the content itself.
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
    });
    const notes = [];
    if (result.duplicates) notes.push(`${result.duplicates} trùng`);
    if (result.skipped.length) notes.push(`${result.skipped.length} dòng lỗi (dòng ${result.skipped.map((row) => (row.sheet ? `${row.sheet}!${row.line}` : row.line)).join(", ")})`);
    if (result.unknown_columns.length) notes.push(`bỏ qua cột: ${result.unknown_columns.join(", ")}`);
    toast(`Đã import ${result.imported} giao dịch${notes.length ? ` · ${notes.join(" · ")}` : ""}`);
    await loadMonth();
  } catch (error) {
    toast(`Import lỗi: ${error.message}`);
  }
}

function setMonth(month) {
  state.month = month;
  $("#month").value = month;
  history.replaceState(null, "", `#${month}`);
  resetForm();
  loadMonth().catch((error) => toast(`Lỗi tải dữ liệu: ${error.message}`));
}

async function init() {
  const { categories } = await api("/api/categories");
  state.categories = categories;
  const groups = Object.keys(GROUP_LABELS);
  $("#category-select").innerHTML = groups.map((group) => `
    <optgroup label="${GROUP_LABELS[group]}">
      ${categories.filter((category) => category.group === group).map((category) =>
        `<option value="${category.id}">${escapeHtml(category.label)}</option>`).join("")}
    </optgroup>`).join("");

  renderLegend();
  renderWhatIfControls();

  $("#month").addEventListener("change", (event) => event.target.value && setMonth(event.target.value));
  $("#tx-form").addEventListener("submit", submitTransaction);
  $("#tx-cancel").addEventListener("click", resetForm);
  $("#sheet").addEventListener("click", onSheetClick);
  $("#budgets").addEventListener("change", onBudgetChange);
  $("#import-file").addEventListener("change", onImport);
  $("#what-if").addEventListener("input", (event) => {
    const input = event.target.closest("input[data-category]");
    if (!input) return;
    state.cuts[input.dataset.category] = Number(input.value) / 100;
    input.nextElementSibling.textContent = `${input.value}%`;
    scheduleWhatIf();
  });
  const chart = $("#trend-chart");
  chart.addEventListener("pointermove", showTrendTooltip);
  chart.addEventListener("pointerleave", () => { $("#tooltip").hidden = true; });
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => state.trend.length && renderTrend(state.trend), 150);
  });

  const fromHash = location.hash.slice(1);
  setMonth(/^\d{4}-\d{2}$/.test(fromHash) ? fromHash : localIsoDate().slice(0, 7));
}

init().catch((error) => toast(`Không tải được ứng dụng: ${error.message}`));
