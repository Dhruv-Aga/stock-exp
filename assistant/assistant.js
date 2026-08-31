import { agentUrl } from "../src/shell/config.js";
import { url } from "../src/shell/paths.js";

const CAPABILITY_GROUPS = [
  {
    title: "Portfolio",
    description: "Kite holdings, positions, margins, and paper status",
    tools: ["get_profile", "get_holdings", "get_positions", "get_margins", "get_paper_portfolio_status"],
  },
  {
    title: "Strategies",
    description: "Run mean-reversion, momentum, trend, or all signals",
    tools: [
      "run_mean_reversion_strategy",
      "run_momentum_breakout_strategy",
      "run_trend_following_strategy",
      "get_all_strategy_signals",
    ],
  },
  {
    title: "Benchmark",
    description: "Backtests and performance vs starting capital",
    tools: [
      "run_portfolio_backtest",
      "get_rolling_benchmark",
      "compare_portfolio_to_capital",
      "get_ticker_quote",
      "get_ticker_history",
    ],
  },
  {
    title: "Scripts & proposals",
    description: "Sandbox scripts and live trade proposals (review required)",
    tools: ["run_python_script", "run_node_script", "propose_trade", "list_trade_proposals"],
  },
];

const elements = {
  chatMessages: document.querySelector("#chatMessages"),
  chatForm: document.querySelector("#chatForm"),
  chatInput: document.querySelector("#chatInput"),
  sendBtn: document.querySelector("#sendBtn"),
  agentStatus: document.querySelector("#agentStatus"),
  capabilityGroups: document.querySelector("#capabilityGroups"),
};

const history = [];

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function addBubble(role, text, extraHtml = "") {
  const div = document.createElement("div");
  div.className = `chat-bubble ${role}`;
  const textNode = document.createElement("div");
  textNode.textContent = text;
  div.appendChild(textNode);
  if (extraHtml) {
    const meta = document.createElement("div");
    meta.className = "tools-used";
    meta.innerHTML = extraHtml;
    div.appendChild(meta);
  }
  elements.chatMessages.appendChild(div);
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function renderCapabilityGroups() {
  elements.capabilityGroups.innerHTML = CAPABILITY_GROUPS.map(
    (group) => `
    <div class="capability-group">
      <h3>${escapeHtml(group.title)}</h3>
      <p class="sub">${escapeHtml(group.description)}</p>
      <ul>${group.tools.map((t) => `<li><code>${escapeHtml(t)}</code></li>`).join("")}</ul>
    </div>`
  ).join("");
}

function proposalCardFromTools(toolsUsed) {
  for (const t of toolsUsed || []) {
    if (t.tool !== "propose_trade") continue;
    let parsed = t.result;
    if (!parsed && t.result_preview) {
      try {
        parsed = JSON.parse(t.result_preview);
      } catch {
        continue;
      }
    }
    const proposal = parsed?.proposal;
    if (!proposal?.id) continue;
    if (proposal.status === "executed") {
      return `<div class="proposal-inline-card">Trade auto-approved and executed. Proposal <code>${escapeHtml(proposal.id.slice(0, 8))}…</code></div>`;
    }
    return `<div class="proposal-inline-card">Trade proposed — <a href="${url("/approvals/")}">Review in Approvals →</a> (id: <code>${escapeHtml(proposal.id.slice(0, 8))}…</code>)</div>`;
  }
  return "";
}

async function loadHealth() {
  try {
    const res = await fetch(agentUrl("/api/agent/health"));
    const data = await res.json();
    const parts = [];
    parts.push(data.groq_configured ? "Groq ready" : "Groq not configured");
    parts.push(data.kite_configured ? "Kite ready" : "Kite not configured");
    parts.push(`${data.tools_count} tools`);
    elements.agentStatus.textContent = parts.join(" · ");
  } catch {
    elements.agentStatus.textContent = "Agent API offline — run: ./scripts/dev.sh start";
    addBubble(
      "system",
      "Agent API is not running. Start everything with: ./scripts/dev.sh start"
    );
  }
}

async function sendMessage(text) {
  history.push({ role: "user", content: text });
  addBubble("user", text);

  elements.sendBtn.disabled = true;
  elements.chatInput.disabled = true;

  try {
    const res = await fetch(agentUrl("/api/agent/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const data = await res.json();
    const reply = data.reply || "No response.";
    history.push({ role: "assistant", content: reply });

    const toolsMeta =
      data.tools_used?.length > 0
        ? `Tools: ${data.tools_used.map((t) => t.tool).join(", ")}`
        : "";
    const proposalCard = proposalCardFromTools(data.tools_used);
    const extra = [toolsMeta, proposalCard].filter(Boolean).join("");

    addBubble("assistant", reply, extra);
  } catch (error) {
    addBubble("system", `Error: ${error.message}`);
  } finally {
    elements.sendBtn.disabled = false;
    elements.chatInput.disabled = false;
    elements.chatInput.focus();
  }
}

elements.chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = elements.chatInput.value.trim();
  if (!text) return;
  elements.chatInput.value = "";
  sendMessage(text);
});

elements.chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.chatForm.requestSubmit();
  }
});

document.querySelector("#quickPrompts")?.addEventListener("click", (event) => {
  const chip = event.target.closest("[data-prompt]");
  if (!chip) return;
  sendMessage(chip.dataset.prompt);
});

addBubble(
  "assistant",
  "Hi! I can check your portfolio, run strategies, benchmark performance, and propose live trades for your review. What would you like to know?"
);

renderCapabilityGroups();
loadHealth();
