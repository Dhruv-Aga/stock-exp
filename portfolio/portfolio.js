const ANALYSIS_URL = "/paper/analysis.json";

const elements = {
  emptyState: document.querySelector("#emptyState"),
  errorState: document.querySelector("#errorState"),
  errorMessage: document.querySelector("#errorMessage"),
  trackerMain: document.querySelector("#trackerMain"),
  generatedAt: document.querySelector("#generatedAt"),
  kpiCards: document.querySelector("#kpiCards"),
  positionsBody: document.querySelector("#positionsBody"),
  noPositions: document.querySelector("#noPositions"),
  tradesBody: document.querySelector("#tradesBody"),
  noTrades: document.querySelector("#noTrades"),
  equityChart: document.querySelector("#equityChart"),
  refreshPaperBtn: document.querySelector("#refreshPaperBtn"),
};

let chartInstance = null;

function money(value) {
  const num = Number(value);
  if (Number.isNaN(num)) return "—";
  return `Rs ${num.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function pct(value) {
  const num = Number(value);
  if (Number.isNaN(num)) return "—";
  return `${num >= 0 ? "+" : ""}${num.toFixed(2)}%`;
}

function pnlClass(value) {
  const num = Number(value);
  if (num > 0) return "pnl-positive";
  if (num < 0) return "pnl-negative";
  return "";
}

function formatDate(value) {
  if (!value) return "—";
  const text = String(value);
  return text.length > 16 ? text.slice(0, 16) : text;
}

function show(el) {
  el.classList.remove("hidden");
}

function hide(el) {
  el.classList.add("hidden");
}

function renderKpis(analysis) {
  const cards = [
    {
      label: "Equity",
      value: money(analysis.equity),
      sub: `${pct(analysis.total_return_pct)} total return`,
    },
    {
      label: "Cash",
      value: money(analysis.cash),
      sub: `${(analysis.open_positions || []).length} open positions`,
    },
    {
      label: "Unrealized P&L",
      value: money(analysis.unrealized_pnl),
      sub: "mark-to-market",
      valueClass: pnlClass(analysis.unrealized_pnl),
    },
    {
      label: "Today",
      value: money(analysis.today_pnl),
      sub: "realized P&L",
      valueClass: pnlClass(analysis.today_pnl),
    },
    {
      label: "This week",
      value: money(analysis.week_pnl),
      sub: analysis.week_start ? `from ${analysis.week_start}` : "",
      valueClass: pnlClass(analysis.week_pnl),
    },
    {
      label: "This month",
      value: money(analysis.month_pnl),
      sub: analysis.month_start ? `from ${analysis.month_start}` : "",
      valueClass: pnlClass(analysis.month_pnl),
    },
  ];

  elements.kpiCards.innerHTML = cards
    .map(
      (card) => `
      <article class="tracker-kpi">
        <div class="label">${card.label}</div>
        <div class="value ${card.valueClass || ""}">${card.value}</div>
        ${card.sub ? `<div class="subvalue">${card.sub}</div>` : ""}
      </article>`
    )
    .join("");
}

function renderPositions(positions) {
  if (!positions.length) {
    elements.positionsBody.innerHTML = "";
    show(elements.noPositions);
    return;
  }

  hide(elements.noPositions);
  elements.positionsBody.innerHTML = positions
    .map(
      (p) => `
      <tr>
        <td>${escapeHtml(p.symbol || "")}</td>
        <td>${escapeHtml(p.side || "")}</td>
        <td>${money(p.entry_price)}</td>
        <td>${money(p.mark_price)}</td>
        <td>${Number(p.quantity || 0).toFixed(2)}</td>
        <td class="${pnlClass(p.unrealized_pnl)}">${money(p.unrealized_pnl)}</td>
      </tr>`
    )
    .join("");
}

function renderTrades(trades) {
  const recent = trades.slice(0, 10);
  if (!recent.length) {
    elements.tradesBody.innerHTML = "";
    show(elements.noTrades);
    return;
  }

  hide(elements.noTrades);
  elements.tradesBody.innerHTML = recent
    .map(
      (t) => `
      <tr>
        <td>${formatDate(t.exit_time)}</td>
        <td>${escapeHtml(t.symbol || "")}</td>
        <td>${escapeHtml(t.side || "")}</td>
        <td class="${pnlClass(t.pnl)}">${money(t.pnl)}</td>
        <td class="${pnlClass(t.return_pct)}">${pct(t.return_pct)}</td>
      </tr>`
    )
    .join("");
}

function renderEquityChart(dailyEquity) {
  const rows = (dailyEquity || []).filter((r) => r.equity != null).slice(-90);
  const labels = rows.map((r) => String(r.date || ""));
  const data = rows.map((r) => Number(r.equity));

  if (chartInstance) {
    chartInstance.destroy();
    chartInstance = null;
  }

  if (!data.length) return;

  chartInstance = new Chart(elements.equityChart, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Equity",
          data,
          borderColor: "#fb923c",
          backgroundColor: "rgba(251, 146, 60, 0.12)",
          tension: 0.25,
          fill: true,
          pointRadius: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: { color: "rgba(255,255,255,0.55)", maxTicksLimit: 8 },
          grid: { color: "rgba(255,255,255,0.06)" },
        },
        y: {
          ticks: { color: "rgba(255,255,255,0.55)" },
          grid: { color: "rgba(255,255,255,0.06)" },
        },
      },
    },
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function isEmptyAnalysis(analysis) {
  return (
    !analysis ||
    (Number(analysis.equity) === 0 &&
      !(analysis.open_positions || []).length &&
      !(analysis.recent_trades || []).length)
  );
}

async function loadPortfolio() {
  try {
    const response = await fetch(ANALYSIS_URL, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} loading ${ANALYSIS_URL}`);
    }

    const analysis = await response.json();

    if (isEmptyAnalysis(analysis)) {
      hide(elements.trackerMain);
      hide(elements.errorState);
      show(elements.emptyState);
      elements.generatedAt.textContent = "No portfolio snapshot available";
      return;
    }

    hide(elements.emptyState);
    hide(elements.errorState);
    show(elements.trackerMain);

    const generated = analysis.generated_at
      ? `Updated ${formatDate(analysis.generated_at)}`
      : "Portfolio snapshot loaded";
    elements.generatedAt.textContent = generated;

    renderKpis(analysis);
    renderPositions(analysis.open_positions || []);
    renderTrades(analysis.recent_trades || []);
    renderEquityChart(analysis.daily_equity || []);
  } catch (error) {
    hide(elements.trackerMain);
    hide(elements.emptyState);
    show(elements.errorState);
    elements.errorMessage.textContent = error.message || String(error);
    elements.generatedAt.textContent = "Failed to load portfolio data";
  }
}

function setTab(tabId) {
  document.querySelectorAll(".portfolio-tab").forEach((btn) => {
    const active = btn.dataset.tab === tabId;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  });
  document.querySelectorAll(".portfolio-panel").forEach((panel) => {
    panel.classList.toggle("hidden", panel.id !== `panel-${tabId}`);
  });
}

document.querySelectorAll(".portfolio-tab").forEach((btn) => {
  btn.addEventListener("click", () => setTab(btn.dataset.tab));
});

const params = new URLSearchParams(window.location.search);
if (params.get("tab") === "details" || window.location.hash === "#details") {
  setTab("details");
}

window.addEventListener("hashchange", () => {
  if (window.location.hash === "#details") {
    setTab("details");
  }
});

elements.refreshPaperBtn?.addEventListener("click", () => {
  loadPortfolio();
  const frame = document.querySelector("#paperFrame");
  if (frame) frame.src = "/paper/?t=" + Date.now();
});

loadPortfolio();
