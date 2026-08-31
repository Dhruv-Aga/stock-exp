import { agentUrl } from "../src/shell/config.js";

const els = {
  subtitle: document.getElementById("compareSubtitle"),
  empty: document.getElementById("emptyState"),
  error: document.getElementById("errorState"),
  errorMsg: document.getElementById("errorMessage"),
  main: document.getElementById("compareMain"),
  kpis: document.getElementById("kpiCards"),
  paperActions: document.getElementById("paperActions"),
  liveActions: document.getElementById("liveActions"),
  divergenceBody: document.getElementById("divergenceBody"),
  noDivergences: document.getElementById("noDivergences"),
  planDetails: document.getElementById("planDetails"),
  refreshBtn: document.getElementById("refreshCompareBtn"),
};

function fmtRs(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return `Rs${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function parityClass(score) {
  if (score >= 0.95) return "good";
  if (score >= 0.75) return "warn";
  return "bad";
}

function renderKpis(data) {
  const summary = data.summary || {};
  const sameBook = data.same_book_comparison || {};
  const paper = sameBook.paper || {};
  const live = sameBook.live_shadow || {};
  const score = summary.parity_score ?? 0;

  els.kpis.innerHTML = `
    <div class="compare-kpi ${parityClass(score)}">
      <div class="label">Parity score</div>
      <div class="value">${(score * 100).toFixed(1)}%</div>
    </div>
    <div class="compare-kpi">
      <div class="label">Paper equity (after)</div>
      <div class="value">${fmtRs(paper.equity)}</div>
    </div>
    <div class="compare-kpi">
      <div class="label">Live shadow equity</div>
      <div class="value">${fmtRs(live.equity)}</div>
    </div>
    <div class="compare-kpi">
      <div class="label">Equity delta</div>
      <div class="value">${fmtRs(summary.equity_delta_same_book)}</div>
    </div>
    <div class="compare-kpi">
      <div class="label">Exit / entry intents</div>
      <div class="value">${summary.exit_intents ?? 0} / ${summary.entry_intents ?? 0}</div>
    </div>
    <div class="compare-kpi">
      <div class="label">Data source</div>
      <div class="value" style="font-size:1rem">${data.data_source || "—"}</div>
    </div>
  `;
}

function renderActions(listEl, actions) {
  listEl.innerHTML = "";
  if (!actions?.length) {
    const li = document.createElement("li");
    li.textContent = "No actions projected.";
    listEl.appendChild(li);
    return;
  }
  for (const action of actions) {
    const li = document.createElement("li");
    li.textContent = action;
    listEl.appendChild(li);
  }
}

function renderDivergences(divergences) {
  els.divergenceBody.innerHTML = "";
  if (!divergences?.length) {
    els.noDivergences.classList.remove("hidden");
    return;
  }
  els.noDivergences.classList.add("hidden");
  for (const d of divergences) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${d.index}</td>
      <td>${d.paper || "—"}</td>
      <td>${d.live_shadow || "—"}</td>
    `;
    els.divergenceBody.appendChild(tr);
  }
}

function showError(msg) {
  els.empty.classList.add("hidden");
  els.main.classList.add("hidden");
  els.error.classList.remove("hidden");
  els.errorMsg.textContent = msg;
}

function render(data) {
  els.empty.classList.add("hidden");
  els.error.classList.add("hidden");
  els.main.classList.remove("hidden");

  const generated = data.generated_at ? new Date(data.generated_at).toLocaleString() : "";
  els.subtitle.textContent = generated
    ? `Last run: ${generated} · ${data.data_source || "yfinance"}`
    : "A/B parity check on the same session plan";

  renderKpis(data);
  const sameBook = data.same_book_comparison || {};
  renderActions(els.paperActions, sameBook.paper?.actions);
  renderActions(els.liveActions, sameBook.live_shadow?.actions);
  renderDivergences(sameBook.divergences);
  els.planDetails.textContent = JSON.stringify(data.plan || {}, null, 2);
}

async function fetchComparison(refresh = false) {
  els.refreshBtn.disabled = true;
  els.refreshBtn.textContent = "Running…";
  try {
    const url = agentUrl(`/api/trading/ab-comparison${refresh ? "?refresh=true" : ""}`);
    const res = await fetch(url, refresh ? { method: "POST" } : { cache: "no-store" });
    if (!res.ok) {
      throw new Error(`API returned ${res.status}`);
    }
    const data = await res.json();
    render(data);
  } catch (err) {
    showError(err.message || "Failed to load comparison. Is the agent API running?");
  } finally {
    els.refreshBtn.disabled = false;
    els.refreshBtn.textContent = "↻ Run comparison";
  }
}

els.refreshBtn?.addEventListener("click", () => fetchComparison(true));
fetchComparison(false);
