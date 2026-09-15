import { apiFetch } from "../src/shell/api_client.js";
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
  sessionList: document.querySelector("#sessionList"),
  newChatBtn: document.querySelector("#newChatBtn"),
  sessionHistoryToggle: document.querySelector("#sessionHistoryToggle"),
  sessionDropdown: document.querySelector("#sessionDropdown"),
};

const CHAT_SESSIONS_KEY = "bharat-scout:assistant-chat-sessions";
const ACTIVE_SESSION_KEY = "bharat-scout:assistant-active-session";
const WELCOME_MESSAGE =
  "Hi! I can check your portfolio, run strategies, benchmark performance, and propose live trades for your review. What would you like to know?";

const history = [];
let chatSessions = [];
let activeSessionId = null;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function createSession(title = "New chat") {
  const id = globalThis.crypto?.randomUUID?.() ?? `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return {
    id,
    title,
    updatedAt: new Date().toISOString(),
    messages: [],
  };
}

function renderMarkdown(text) {
  const source = String(text ?? "");
  if (!source.trim()) return "";

  const parser = typeof window !== "undefined" ? window.marked : undefined;
  if (!parser) {
    return escapeHtml(source).replace(/\n/g, "<br>");
  }

  const html = parser.parse(source, { breaks: true, gfm: true });
  if (typeof window !== "undefined" && window.DOMPurify) {
    return window.DOMPurify.sanitize(html);
  }

  return html;
}

function addBubble(role, text, extraHtml = "") {
  const div = document.createElement("div");
  div.className = `chat-bubble ${role}`;
  const content = document.createElement("div");
  content.className = "chat-content";
  content.innerHTML = renderMarkdown(text);
  div.appendChild(content);
  if (extraHtml) {
    const meta = document.createElement("div");
    meta.className = "tools-used";
    meta.innerHTML = extraHtml;
    div.appendChild(meta);
  }
  elements.chatMessages.appendChild(div);
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function getActiveSession() {
  return chatSessions.find((session) => session.id === activeSessionId) ?? chatSessions[chatSessions.length - 1] ?? null;
}

async function saveSessionToServer(session) {
  if (!session?.id) return;
  try {
    await apiFetch(`/api/agent/sessions/${session.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: session.title || "New chat",
        messages: session.messages ?? [],
        metadata: { source: "web-ui" },
      }),
    });
  } catch (error) {
    console.warn("Failed to persist session to DB", error);
  }
}

function persistSessions() {
  localStorage.setItem(CHAT_SESSIONS_KEY, JSON.stringify(chatSessions));
  if (activeSessionId) {
    localStorage.setItem(ACTIVE_SESSION_KEY, activeSessionId);
  }
  const activeSession = getActiveSession();
  if (activeSession) {
    void saveSessionToServer(activeSession);
  }
}

async function loadSessions() {
  try {
    const res = await apiFetch("/api/agent/sessions");
    if (res.ok) {
      const data = await res.json();
      const sessions = Array.isArray(data.sessions) ? data.sessions : [];
      if (sessions.length) {
        chatSessions = sessions.map((session) => ({
          id: session.id,
          title: session.title || "New chat",
          updatedAt: session.updated_at || session.created_at || new Date().toISOString(),
          messages: Array.isArray(session.messages) ? session.messages : [],
        }));
        const savedActiveId = localStorage.getItem(ACTIVE_SESSION_KEY) || chatSessions[0].id;
        const activeSession = chatSessions.find((session) => session.id === savedActiveId) ?? chatSessions[0];
        activeSessionId = activeSession.id;
        history.splice(0, history.length, ...(activeSession.messages ?? []));
        persistSessions();
        return;
      }
    }
  } catch (error) {
    console.warn("Unable to load DB-backed chat sessions, falling back to local storage", error);
  }

  try {
    const raw = localStorage.getItem(CHAT_SESSIONS_KEY);
    chatSessions = raw ? JSON.parse(raw) : [];
  } catch {
    chatSessions = [];
  }

  if (!chatSessions.length) {
    const initialSession = createSession();
    chatSessions = [initialSession];
    activeSessionId = initialSession.id;
    persistSessions();
    return;
  }

  const savedActiveId = localStorage.getItem(ACTIVE_SESSION_KEY);
  const activeSession = chatSessions.find((session) => session.id === savedActiveId) ?? chatSessions[chatSessions.length - 1];
  activeSessionId = activeSession.id;
  history.splice(0, history.length, ...(activeSession.messages ?? []));
}

function getSessionPreview(session) {
  const messages = Array.isArray(session?.messages) ? session.messages : [];
  const latestText = [...messages].reverse().find((message) => message?.content)?.content ?? "";
  const trimmed = String(latestText).replace(/\s+/g, " ").trim();
  return trimmed ? trimmed.slice(0, 90) + (trimmed.length > 90 ? "…" : "") : "No messages yet";
}

function renderSessionList() {
  if (elements.sessionList) {
    const orderedSessions = [...chatSessions].sort((left, right) => new Date(right.updatedAt) - new Date(left.updatedAt));
    elements.sessionList.innerHTML = orderedSessions
      .map((session) => {
        const isActive = session.id === activeSessionId;
        const title = escapeHtml(session.title || "New chat");
        const preview = escapeHtml(getSessionPreview(session));
        const count = Array.isArray(session.messages) ? session.messages.length : 0;
        const date = new Date(session.updatedAt).toLocaleString([], {
          month: "short",
          day: "numeric",
          hour: "numeric",
          minute: "2-digit",
        });

        return `
          <div class="session-card ${isActive ? "active" : ""}">
            <button class="session-item ${isActive ? "active" : ""}" type="button" data-session-id="${escapeHtml(session.id)}">
              <span class="session-badge ${isActive ? "active" : ""}" aria-hidden="true"></span>
              <span class="session-body">
                <span class="session-title">${title}</span>
                <span class="session-preview">${preview}</span>
                <span class="session-meta-row">
                  <span class="session-meta">${escapeHtml(date)}</span>
                  <span class="session-count">${count} msgs</span>
                </span>
              </span>
            </button>
            <button class="session-delete" type="button" data-delete-session-id="${escapeHtml(session.id)}" aria-label="Delete chat session">
              Delete
            </button>
          </div>
        `;
      })
      .join("");

    elements.sessionList.querySelectorAll("[data-session-id]").forEach((button) => {
      button.addEventListener("click", () => {
        openSession(button.dataset.sessionId);
      });
    });

    elements.sessionList.querySelectorAll("[data-delete-session-id]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        const sessionId = button.dataset.deleteSessionId;
        if (!sessionId) return;
        const session = chatSessions.find((entry) => entry.id === sessionId);
        const label = session?.title ? `"${session.title}"` : "this chat";
        if (window.confirm(`Delete ${label}?`)) {
          deleteSession(sessionId);
        }
      });
    });
  }

  if (elements.sessionDropdown) {
    const orderedSessions = [...chatSessions].sort((left, right) => new Date(right.updatedAt) - new Date(left.updatedAt));
    elements.sessionDropdown.innerHTML = orderedSessions
      .map((session) => {
        const isActive = session.id === activeSessionId;
        const title = escapeHtml(session.title || "New chat");
        const preview = escapeHtml(getSessionPreview(session));
        const date = new Date(session.updatedAt).toLocaleString([], {
          month: "short",
          day: "numeric",
          hour: "numeric",
          minute: "2-digit",
        });

        return `
          <button class="session-menu-item ${isActive ? "active" : ""}" type="button" data-session-id="${escapeHtml(session.id)}">
            <span class="session-menu-title">${title}</span>
            <span class="session-menu-preview">${preview}</span>
            <span class="session-menu-meta">${escapeHtml(date)}</span>
          </button>
        `;
      })
      .join("");

    elements.sessionDropdown.querySelectorAll("[data-session-id]").forEach((button) => {
      button.addEventListener("click", () => {
        openSession(button.dataset.sessionId);
        closeSessionDropdown();
      });
    });
  }
}

function renderMessages() {
  elements.chatMessages.innerHTML = "";
  const activeSession = getActiveSession();
  const messages = activeSession?.messages ?? history;

  if (!messages.length) {
    addBubble("assistant", WELCOME_MESSAGE);
    return;
  }

  for (const message of messages) {
    const extra = message.role === "assistant" ? getMessageMeta(message) : "";
    addBubble(message.role, message.content, extra);
  }
}

function openSession(sessionId) {
  const session = chatSessions.find((entry) => entry.id === sessionId);
  if (!session) return;

  activeSessionId = sessionId;
  history.splice(0, history.length, ...(session.messages ?? []));
  persistSessions();
  renderSessionList();
  renderMessages();
}

function deleteSession(sessionId) {
  const index = chatSessions.findIndex((entry) => entry.id === sessionId);
  if (index === -1) return;

  chatSessions.splice(index, 1);
  if (activeSessionId === sessionId) {
    const fallback = chatSessions[0] ?? createSession("New chat");
    activeSessionId = fallback.id;
    history.splice(0, history.length, ...(fallback.messages ?? []));
  }

  if (chatSessions.length === 0) {
    const newSession = createSession("New chat");
    chatSessions.push(newSession);
    activeSessionId = newSession.id;
    history.splice(0, history.length);
  }

  persistSessions();
  renderSessionList();
  renderMessages();
}

function newChatSession() {
  const session = createSession("New chat");
  chatSessions.push(session);
  activeSessionId = session.id;
  history.splice(0, history.length);
  persistSessions();
  renderSessionList();
  renderMessages();
  closeSessionDropdown();
}

function toggleSessionDropdown() {
  if (!elements.sessionDropdown) return;
  const isOpen = elements.sessionDropdown.classList.contains("open");
  if (isOpen) {
    closeSessionDropdown();
    return;
  }
  elements.sessionDropdown.classList.add("open");
  elements.sessionHistoryToggle?.setAttribute("aria-expanded", "true");
}

function closeSessionDropdown() {
  if (!elements.sessionDropdown) return;
  elements.sessionDropdown.classList.remove("open");
  elements.sessionHistoryToggle?.setAttribute("aria-expanded", "false");
}

function syncActiveSession() {
  const activeSession = getActiveSession();
  if (!activeSession) return;

  activeSession.messages = [...history];
  activeSession.updatedAt = new Date().toISOString();

  const latestUserText = [...history].reverse().find((message) => message.role === "user")?.content;
  if (latestUserText) {
    activeSession.title = latestUserText.trim().replace(/\s+/g, " ").slice(0, 40) || "New chat";
  }

  persistSessions();
  renderSessionList();
}

function getMessageMeta(message) {
  if (!Array.isArray(message.toolsUsed) || !message.toolsUsed.length) {
    return "";
  }

  const toolsMeta = `Tools: ${message.toolsUsed.map((tool) => tool.tool).join(", ")}`;
  const proposalCard = proposalCardFromTools(message.toolsUsed);
  return [toolsMeta, proposalCard].filter(Boolean).join("");
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
    const res = await apiFetch("/api/agent/health");
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
  syncActiveSession();
  addBubble("user", text);

  elements.sendBtn.disabled = true;
  elements.chatInput.disabled = true;

  try {
    const res = await apiFetch("/api/agent/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const data = await res.json();
    const reply = data.reply || "No response.";
    const assistantMessage = {
      role: "assistant",
      content: reply,
      toolsUsed: data.tools_used || [],
    };
    history.push(assistantMessage);
    syncActiveSession();

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

elements.newChatBtn?.addEventListener("click", () => {
  newChatSession();
});

elements.sessionHistoryToggle?.addEventListener("click", (event) => {
  event.stopPropagation();
  toggleSessionDropdown();
});

document.addEventListener("click", (event) => {
  const toggle = elements.sessionHistoryToggle;
  const dropdown = elements.sessionDropdown;
  if (!toggle || !dropdown) return;
  if (!toggle.contains(event.target) && !dropdown.contains(event.target)) {
    closeSessionDropdown();
  }
});

loadSessions();
renderSessionList();
renderMessages();
renderCapabilityGroups();
loadHealth();
