import { agentUrl } from "../src/shell/config.js";

const listEl = document.querySelector("#proposalList");
const statusEl = document.querySelector("#approvalStatus");
const bannerEl = document.querySelector(".approval-banner");

const SOURCE_LABELS = {
  paper_shadow: "Paper shadow previews",
  automation: "Strategy automation",
  assistant: "Assistant proposals",
};

const SOURCE_ORDER = ["paper_shadow", "automation", "assistant"];

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

function groupProposals(proposals) {
  const groups = new Map();
  for (const p of proposals) {
    const key = p.source || "other";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(p);
  }

  const ordered = [];
  for (const key of SOURCE_ORDER) {
    if (groups.has(key)) {
      ordered.push([key, groups.get(key)]);
      groups.delete(key);
    }
  }
  for (const [key, items] of groups) {
    ordered.push([key, items]);
  }
  return ordered;
}

function renderGrouped(proposals) {
  const groups = groupProposals(proposals);
  return groups
    .map(
      ([source, items]) => `
      <div class="proposal-group">
        <h3>${escapeHtml(SOURCE_LABELS[source] || source)}</h3>
        ${items.map(formatProposal).join("")}
      </div>`
    )
    .join("");
}

async function loadProposals() {
  try {
    const healthRes = await fetch(agentUrl("/api/agent/health"));
    if (healthRes.ok) {
      const health = await healthRes.json();
      if (health.auto_approve_trades && bannerEl) {
        bannerEl.innerHTML = `
          <strong>Auto-approve enabled</strong>
          <p>
            <code>AUTO_APPROVE_TRADES=true</code> — live proposals from automation and the assistant
            execute immediately. Paper shadow previews still appear here for review.
          </p>`;
      }
    }

    const res = await fetch(agentUrl("/api/approvals?status=pending"));
    const data = await res.json();
    statusEl.textContent = `${data.pending_count} pending · approval required before live trades`;

    if (!data.proposals?.length) {
      listEl.innerHTML = `
        <div class="empty-approvals">
          <p>No pending trade proposals.</p>
          <p class="sub">Paper is running — shadow and live proposals appear here when strategies signal.</p>
          <p class="sub"><a href="/">← Back to Trading Home</a> · <a href="/portfolio/">View portfolio</a></p>
        </div>`;
      return;
    }

    listEl.innerHTML = renderGrouped(data.proposals);
  } catch (error) {
    listEl.innerHTML = `<p class="sub">Could not load proposals: ${escapeHtml(error.message)}. Run <code>./scripts/dev.sh start</code></p>`;
  }
}

async function handleAction(id, action) {
  if (action === "approve") {
    const ok = window.confirm(
      "Execute this trade on your live Zerodha Kite account? This cannot be undone from this screen."
    );
    if (!ok) return;

    const res = await fetch(agentUrl(`/api/approvals/${id}/approve`), { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Approval failed");
      return;
    }
    alert(`Trade executed: ${data.execution?.status || "done"}`);
  } else {
    const res = await fetch(agentUrl(`/api/approvals/${id}/reject`), {
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
