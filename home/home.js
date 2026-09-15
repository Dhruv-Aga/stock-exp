import { apiFetch } from "../src/shell/api_client.js";
import { url } from "../src/shell/paths.js";

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

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function signalClass(label) {
  const s = String(label || "").toLowerCase();
  if (s === "long") return "signal-long";
  if (s === "short") return "signal-short";
  return "signal-flat";
}

function formatDate(value) {
  if (!value) return "—";
  return String(value).slice(0, 16);
}

function renderSignals(signals, generatedAt) {
  const tableEl = document.querySelector("#signalsTable");
  const updatedEl = document.querySelector("#signalsUpdated");
  if (!tableEl) return;

  updatedEl.textContent = generatedAt
    ? `From paper snapshot · ${formatDate(generatedAt)}`
    : "From latest paper snapshot";

  if (!signals?.length) {
    tableEl.innerHTML = '<p class="sub">No signals yet. Run <code>./scripts/dev.sh paper</code>.</p>';
    return;
  }

  const rows = signals
    .map(
      (s) => `
    <tr>
      <td>${escapeHtml(s.name || s.symbol || "")}</td>
      <td>${escapeHtml(s.strategy || "")}</td>
      <td class="${signalClass(s.signal_label)}">${escapeHtml((s.signal_label || "flat").toUpperCase())}</td>
      <td>${money(s.price)}</td>
      <td>${s.has_position ? escapeHtml(s.position_side || "yes") : "—"}</td>
      <td class="sub">${escapeHtml(s.entry_reason_text || "")}</td>
    </tr>`
    )
    .join("");

  tableEl.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Market</th>
          <th>Strategy</th>
          <th>Signal</th>
          <th>Price</th>
          <th>Position</th>
          <th>Reason</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

async function loadHome() {
  const kpiEl = document.querySelector("#homeKpis");
  const pendingEl = document.querySelector("#pendingBanner");
  const offlineEl = document.querySelector("#offlineBanner");
  const subtitleEl = document.querySelector("#homeSubtitle");

  let summary = null;
  let agentOnline = false;

  try {
    const res = await apiFetch("/api/trading/summary", { cache: "no-store" });
    if (res.ok) {
      summary = await res.json();
      agentOnline = true;
    }
  } catch {
    /* offline */
  }

  if (!summary) {
    offlineEl?.classList.remove("hidden");
    try {
      const res = await fetch(url("/paper/analysis.json"), { cache: "no-store" });
      if (res.ok) {
        const analysis = await res.json();
        summary = {
          portfolio: analysis,
          signals: analysis.signals || [],
          agent: { online: false, live_trading: false },
        };
      }
    } catch {
      /* empty */
    }
  } else {
    offlineEl?.classList.add("hidden");
  }

  const portfolio = summary?.portfolio || {};
  const agent = summary?.agent || {};
  const signals = summary?.signals || [];
  const pending = Number(agent.pending_proposals || 0);
  const mode = agent.live_trading ? "Live (guarded)" : "Paper";

  if (subtitleEl) {
    subtitleEl.textContent = `${mode} · ${formatDate(portfolio.generated_at) || "no snapshot yet"}`;
  }

  if (pending > 0 && pendingEl) {
    pendingEl.classList.remove("hidden");
    pendingEl.innerHTML = `
      <strong>Action required:</strong> ${pending} trade proposal${pending === 1 ? "" : "s"}
      waiting for review. <a href="${url("/approvals/")}">Go to Review →</a>`;
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
        <div class="value">${mode}</div>
      </article>
      <article class="home-kpi">
        <div class="label">Agent</div>
        <div class="value">${agentOnline ? "Online" : "Offline"}</div>
      </article>
    `;
  }

  renderSignals(signals, portfolio.generated_at);
}

loadHome();
