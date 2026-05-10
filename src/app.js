import { fetchQuotes } from "./api.js";
import { DEFAULT_WATCHLIST, FUNDAMENTALS } from "./data.js";
import { loadSetting, saveSetting } from "./storage.js";

const elements = {
  addForm: document.querySelector("#addForm"),
  autoBtn: document.querySelector("#autoBtn"),
  backendUrl: document.querySelector("#backendUrl"),
  clearBackendBtn: document.querySelector("#clearBackendBtn"),
  emptyState: document.querySelector("#emptyState"),
  exportBtn: document.querySelector("#exportBtn"),
  loadingSpinner: document.querySelector("#loadingSpinner"),
  maxPE: document.querySelector("#maxPE"),
  minROE: document.querySelector("#minROE"),
  refreshBtn: document.querySelector("#refreshBtn"),
  saveBackendBtn: document.querySelector("#saveBackendBtn"),
  searchBox: document.querySelector("#searchBox"),
  sortSelect: document.querySelector("#sortSelect"),
  status: document.querySelector("#status"),
  stockInput: document.querySelector("#stockInput"),
  symbolSuggestions: document.querySelector("#symbolSuggestions"),
  tableBody: document.querySelector("#tableBody"),
  toastRegion: document.querySelector("#toastRegion"),
  watchlist: document.querySelector("#watchlist"),
  lastUpdated: document.querySelector("#lastUpdated"),
};

const state = {
  autoRefresh: false,
  backendUrl: loadSetting("backendUrl", ""),
  intervalId: null,
  liveData: {},
  rows: [],
  watchlist: loadSetting("watchlist", DEFAULT_WATCHLIST),
};

function sanitizeSymbol(value) {
  return value.toUpperCase().replace(/[^A-Z0-9-]/g, "").trim();
}

function formatCurrency(value) {
  return Number.isFinite(Number(value)) ? `₹${Number(value).toLocaleString("en-IN")}` : "—";
}

function formatPercent(value) {
  return Number.isFinite(Number(value)) ? `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(2)}%` : "—";
}

function calculateScore(stock) {
  let score = 0;
  if (stock.pe) score += Math.max(0, 40 - stock.pe);
  if (stock.roe) score += stock.roe;
  if (stock.margin) score += stock.margin;
  return Math.min(100, Math.max(0, Math.round(score)));
}

function setLoading(isLoading) {
  elements.loadingSpinner.classList.toggle("hidden", !isLoading);
  elements.refreshBtn.disabled = isLoading;
}

function setStatus(label, variant = "disconnected") {
  elements.status.textContent = label;
  elements.status.className = `status-badge ${variant}`;
}

function toast(message, variant = "success") {
  const node = document.createElement("div");
  node.className = `toast ${variant}`;
  node.textContent = message;
  elements.toastRegion.appendChild(node);
  setTimeout(() => node.remove(), 4500);
}

function saveWatchlist() {
  saveSetting("watchlist", state.watchlist);
}

function renderSuggestions() {
  elements.symbolSuggestions.innerHTML = Object.entries(FUNDAMENTALS)
    .map(([symbol, data]) => `<option value="${symbol}">${data.name}</option>`)
    .join("");
}

function renderWatchlist() {
  elements.watchlist.innerHTML = "";

  state.watchlist.forEach((symbol) => {
    const pill = document.createElement("div");
    pill.className = "pill";

    const label = document.createElement("span");
    label.className = "mono";
    label.textContent = symbol;

    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("aria-label", `Remove ${symbol}`);
    button.textContent = "✕";
    button.addEventListener("click", () => removeStock(symbol));

    pill.append(label, button);
    elements.watchlist.appendChild(pill);
  });
}

function buildRows() {
  return state.watchlist.map((symbol) => {
    const fundamentals = FUNDAMENTALS[symbol] || {};
    const quote = state.liveData[symbol] || {};

    return {
      symbol,
      name: fundamentals.name || symbol,
      pe: fundamentals.pe || 0,
      roe: fundamentals.roe || 0,
      margin: fundamentals.margin || 0,
      ltp: quote.ltp,
      change: Number(quote.change),
      score: calculateScore(fundamentals),
      source: quote.source || "pending",
    };
  });
}

function getFilteredRows() {
  const search = elements.searchBox.value.toLowerCase();
  const minROE = Number(elements.minROE.value || 0);
  const maxPE = Number(elements.maxPE.value || Number.MAX_SAFE_INTEGER);
  const sort = elements.sortSelect.value;

  const rows = buildRows().filter(
    (row) =>
      (row.symbol.toLowerCase().includes(search) || row.name.toLowerCase().includes(search)) &&
      row.roe >= minROE &&
      (row.pe === 0 || row.pe <= maxPE),
  );

  rows.sort((a, b) => {
    if (sort === "score") return b.score - a.score;
    if (sort === "change") return b.change - a.change;
    if (sort === "roe") return b.roe - a.roe;
    if (sort === "pe") return (a.pe || Number.MAX_SAFE_INTEGER) - (b.pe || Number.MAX_SAFE_INTEGER);
    return a.symbol.localeCompare(b.symbol);
  });

  return rows;
}

function renderTable() {
  state.rows = getFilteredRows();
  elements.tableBody.innerHTML = "";

  const fragment = document.createDocumentFragment();
  state.rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="mono">${row.symbol}</td>
      <td>${row.name}</td>
      <td>${formatCurrency(row.ltp)}</td>
      <td class="${row.change >= 0 ? "pos" : "neg"}">${formatPercent(row.change)}</td>
      <td>${row.pe || "—"}</td>
      <td>${row.roe ? `${row.roe}%` : "—"}</td>
      <td>${row.margin ? `${row.margin}%` : "—"}</td>
      <td>
        <div class="score">
          <div class="bar"><div class="fill" style="width:${row.score}%"></div></div>
          <span>${row.score}</span>
        </div>
      </td>
    `;
    fragment.appendChild(tr);
  });

  elements.tableBody.appendChild(fragment);
  elements.emptyState.classList.toggle("hidden", state.rows.length > 0);
}

function removeStock(symbol) {
  state.watchlist = state.watchlist.filter((item) => item !== symbol);
  delete state.liveData[symbol];
  saveWatchlist();
  renderWatchlist();
  renderTable();
  toast(`${symbol} removed from watchlist.`);
}

function addStock(symbol) {
  const cleanSymbol = sanitizeSymbol(symbol);
  if (!cleanSymbol) return;
  if (state.watchlist.includes(cleanSymbol)) {
    toast(`${cleanSymbol} is already in the watchlist.`, "error");
    return;
  }

  state.watchlist = [...state.watchlist, cleanSymbol];
  saveWatchlist();
  renderWatchlist();
  renderTable();
  elements.stockInput.value = "";
  toast(`${cleanSymbol} added. Refresh to fetch its latest quote.`);
}

async function refreshData({ silent = false } = {}) {
  setLoading(true);
  try {
    const result = await fetchQuotes({ backendUrl: state.backendUrl, symbols: state.watchlist });
    state.liveData = result.quotes;
    renderTable();

    const now = new Date().toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "medium" });
    if (result.source === "kite") {
      setStatus("Kite Live", "connected");
      elements.lastUpdated.textContent = `Live quotes updated ${now}`;
    } else {
      setStatus("Demo", "disconnected");
      elements.lastUpdated.textContent = `Demo prices updated ${now}`;
    }

    if (!silent) toast("Watchlist refreshed.");
  } catch (error) {
    setStatus("Backend Error", "error");
    elements.lastUpdated.textContent = "Refresh failed. Check backend URL and server logs.";
    toast(error.message, "error");
  } finally {
    setLoading(false);
  }
}

function toggleAutoRefresh() {
  state.autoRefresh = !state.autoRefresh;
  elements.autoBtn.textContent = state.autoRefresh ? "⚡ Auto Refresh ON" : "⚡ Auto Refresh OFF";

  if (state.autoRefresh) {
    refreshData({ silent: true });
    state.intervalId = setInterval(() => refreshData({ silent: true }), 30000);
  } else {
    clearInterval(state.intervalId);
  }
}

function exportCsv() {
  const header = ["Symbol", "Company", "LTP", "Change %", "P/E", "ROE", "Margin", "Score"];
  const rows = state.rows.map((row) => [row.symbol, row.name, row.ltp ?? "", row.change ?? "", row.pe || "", row.roe || "", row.margin || "", row.score]);
  const csv = [header, ...rows]
    .map((line) => line.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `bharat-scout-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function applyPreset(preset) {
  document.querySelectorAll(".tag").forEach((button) => button.classList.toggle("active", button.dataset.preset === preset));
  if (preset === "value") {
    elements.minROE.value = 10;
    elements.maxPE.value = 35;
    elements.sortSelect.value = "score";
  }
  if (preset === "profitable") {
    elements.minROE.value = 15;
    elements.maxPE.value = 100;
    elements.sortSelect.value = "roe";
  }
  if (preset === "quality") {
    elements.minROE.value = 20;
    elements.maxPE.value = 45;
    elements.sortSelect.value = "score";
  }
  renderTable();
}

function bindEvents() {
  elements.addForm.addEventListener("submit", (event) => {
    event.preventDefault();
    addStock(elements.stockInput.value);
  });
  elements.refreshBtn.addEventListener("click", () => refreshData());
  elements.autoBtn.addEventListener("click", toggleAutoRefresh);
  elements.exportBtn.addEventListener("click", exportCsv);
  elements.saveBackendBtn.addEventListener("click", () => {
    state.backendUrl = elements.backendUrl.value.trim();
    saveSetting("backendUrl", state.backendUrl);
    toast(state.backendUrl ? "Backend URL saved." : "Demo mode enabled.");
    refreshData();
  });
  elements.clearBackendBtn.addEventListener("click", () => {
    state.backendUrl = "";
    elements.backendUrl.value = "";
    saveSetting("backendUrl", "");
    refreshData();
  });
  [elements.minROE, elements.maxPE, elements.searchBox, elements.sortSelect].forEach((element) => {
    element.addEventListener("input", renderTable);
  });
  document.querySelectorAll(".tag").forEach((button) => {
    button.addEventListener("click", () => applyPreset(button.dataset.preset));
  });
}

function init() {
  elements.backendUrl.value = state.backendUrl;
  renderSuggestions();
  renderWatchlist();
  bindEvents();
  refreshData({ silent: true });
}

init();
