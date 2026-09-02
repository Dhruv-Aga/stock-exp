import { agentUrl } from "./config.js";
import { url } from "./paths.js";

function pill(label, ok, detail = "") {
  const cls = ok ? "status-pill ok" : "status-pill warn";
  const title = detail ? ` title="${detail.replace(/"/g, "&quot;")}"` : "";
  return `<span class="${cls}"${title}>${label}</span>`;
}

function money(value) {
  const num = Number(value);
  if (Number.isNaN(num)) return "—";
  return `Rs ${num.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

/**
 * @param {HTMLElement} container
 */
export async function mountStatusStrip(container) {
  container.className = "shell-status-strip is-collapsed";
  container.innerHTML = `<span class="status-pill loading">Checking services…</span>`;

  try {
    const res = await fetch(agentUrl("/api/trading/summary"), { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderStatus(container, data, true);
    return data;
  } catch {
    try {
      const analysisRes = await fetch(url("/paper/analysis.json"), { cache: "no-store" });
      const analysis = analysisRes.ok ? await analysisRes.json() : {};
      renderStatus(
        container,
        {
          agent: { online: false },
          portfolio: {
            equity: analysis.equity,
            open_positions: (analysis.open_positions || []).length,
          },
        },
        false
      );
    } catch {
      container.innerHTML = `${pill("Agent offline", false, "Run ./scripts/dev.sh start")} ${pill("Portfolio", false)}`;
    }
    return null;
  }
}

function renderStatus(container, data, agentOnline) {
  const agent = data.agent || {};
  const portfolio = data.portfolio || {};
  const parts = [];

  parts.push(
    pill(
      agentOnline ? "Agent online" : "Agent offline",
      agentOnline,
      agentOnline ? "" : "Run ./scripts/dev.sh start"
    )
  );

  if (agent.groq_configured === false) {
    parts.push(pill("Groq missing", false, "Add GROQ_API_KEY to .env"));
  }
  if (agent.kite_configured === false) {
    parts.push(pill("Kite missing", false, "Add KITE_* to .env"));
  }

  if (agent.auto_approve_trades) {
    parts.push(
      pill("Auto-approve ON", false, "AUTO_APPROVE_TRADES=true — live proposals execute immediately")
    );
  } else if (agent.require_trade_approval || Number(agent.pending_proposals || 0) > 0) {
    parts.push(pill("Approval required", true, "Human review required before execution"));
  }

  if (portfolio.equity != null) {
    const pos = Number(portfolio.open_positions || 0);
    parts.push(
      `<span class="status-pill neutral">Equity ${money(portfolio.equity)} · ${pos} open</span>`
    );
  }

  container.innerHTML = parts.join("");
}

export async function fetchSummary() {
  try {
    const res = await fetch(agentUrl("/api/trading/summary"), { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}
