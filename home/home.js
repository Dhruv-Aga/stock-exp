import { agentUrl } from "../src/shell/config.js";

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

async function loadHome() {
  const kpiEl = document.querySelector("#homeKpis");
  const pendingEl = document.querySelector("#pendingBanner");

  let summary = null;
  try {
    const res = await fetch(agentUrl("/api/trading/summary"), { cache: "no-store" });
    if (res.ok) summary = await res.json();
  } catch {
    // offline — try static analysis only
  }

  if (!summary) {
    try {
      const res = await fetch("/paper/analysis.json", { cache: "no-store" });
      if (res.ok) {
        const analysis = await res.json();
        summary = { portfolio: analysis, agent: { online: false } };
      }
    } catch {
      /* empty */
    }
  }

  const portfolio = summary?.portfolio || {};
  const agent = summary?.agent || {};
  const pending = Number(agent.pending_proposals || 0);

  if (pending > 0 && pendingEl) {
    pendingEl.classList.remove("hidden");
    pendingEl.innerHTML = `<strong>${pending} trade proposal${pending === 1 ? "" : "s"}</strong> waiting for your approval. <a href="/approvals/">Review now →</a>`;
  }

  if (kpiEl) {
    kpiEl.innerHTML = `
      <article class="home-kpi">
        <div class="label">Equity</div>
        <div class="value">${money(portfolio.equity)}</div>
      </article>
      <article class="home-kpi">
        <div class="label">Return</div>
        <div class="value">${pct(portfolio.total_return_pct)}</div>
      </article>
      <article class="home-kpi">
        <div class="label">Open positions</div>
        <div class="value">${portfolio.open_positions ?? "—"}</div>
      </article>
      <article class="home-kpi">
        <div class="label">Mode</div>
        <div class="value">${agent.live_trading ? "Live" : "Paper"}</div>
      </article>
    `;
  }
}

loadHome();
