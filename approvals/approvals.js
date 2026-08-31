const API = window.AGENT_API_URL || "http://localhost:8000";

const listEl = document.querySelector("#proposalList");
const statusEl = document.querySelector("#approvalStatus");

function escapeHtml(v) {
  return String(v)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function formatProposal(p) {
  return `
    <article class="approval-card" data-id="${escapeHtml(p.id)}">
      <header>
        <h3>${escapeHtml(p.action.toUpperCase())} ${escapeHtml(p.side.toUpperCase())} ${escapeHtml(p.symbol)}</h3>
        <span class="source-tag">${escapeHtml(p.source)}</span>
      </header>
      <div class="approval-meta">
        <div>Qty: <strong>${Number(p.quantity).toFixed(2)}</strong> · Price: Rs ${Number(p.price || 0).toFixed(2)}</div>
        ${p.stop_price ? `<div>Stop: Rs ${Number(p.stop_price).toFixed(2)}</div>` : ""}
        ${p.strategy ? `<div>Strategy: ${escapeHtml(p.strategy)}</div>` : ""}
        <div>Reason: ${escapeHtml(p.reason || "—")}</div>
        <div>Created: ${escapeHtml(p.created_at)} · Expires: ${escapeHtml(p.expires_at)}</div>
        <div>ID: <code>${escapeHtml(p.id)}</code></div>
      </div>
      <div class="approval-actions">
        <button class="btn-approve" data-action="approve" data-id="${escapeHtml(p.id)}">Approve &amp; execute on Kite</button>
        <button class="btn-reject" data-action="reject" data-id="${escapeHtml(p.id)}">Reject</button>
      </div>
    </article>`;
}

async function loadProposals() {
  try {
    const res = await fetch(`${API}/api/approvals?status=pending`);
    const data = await res.json();
    statusEl.textContent = `${data.pending_count} pending · approval required before live trades`;

    if (!data.proposals?.length) {
      listEl.innerHTML =
        '<div class="empty-approvals"><p>No pending trade proposals.</p><p class="sub">Paper trading continues automatically. Live proposals from automation or the assistant will appear here.</p></div>';
      return;
    }

    listEl.innerHTML = data.proposals.map(formatProposal).join("");
  } catch (error) {
    listEl.innerHTML = `<p class="sub">Could not load proposals: ${escapeHtml(error.message)}. Start the agent API with python3 run_agent_api.py</p>`;
  }
}

async function handleAction(id, action) {
  if (action === "approve") {
    const ok = window.confirm(
      "Execute this trade on your live Zerodha Kite account? This cannot be undone from this screen."
    );
    if (!ok) return;

    const res = await fetch(`${API}/api/approvals/${id}/approve`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Approval failed");
      return;
    }
    alert(`Trade executed: ${data.execution?.status || "done"}`);
  } else {
    const res = await fetch(`${API}/api/approvals/${id}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: "Rejected by user" }),
    });
    if (!res.ok) {
      const data = await res.json();
      alert(data.detail || "Reject failed");
      return;
    }
  }
  loadProposals();
}

listEl.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-action]");
  if (!btn) return;
  handleAction(btn.dataset.id, btn.dataset.action);
});

loadProposals();
setInterval(loadProposals, 30000);
