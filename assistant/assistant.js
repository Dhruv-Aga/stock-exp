const AGENT_API = window.AGENT_API_URL || "http://localhost:8000";

const elements = {
  chatMessages: document.querySelector("#chatMessages"),
  chatForm: document.querySelector("#chatForm"),
  chatInput: document.querySelector("#chatInput"),
  sendBtn: document.querySelector("#sendBtn"),
  agentStatus: document.querySelector("#agentStatus"),
  toolList: document.querySelector("#toolList"),
};

const history = [];

function addBubble(role, text, extra = "") {
  const div = document.createElement("div");
  div.className = `chat-bubble ${role}`;
  div.textContent = text;
  if (extra) {
    const meta = document.createElement("div");
    meta.className = "tools-used";
    meta.textContent = extra;
    div.appendChild(meta);
  }
  elements.chatMessages.appendChild(div);
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

async function loadHealth() {
  try {
    const res = await fetch(`${AGENT_API}/api/agent/health`);
    const data = await res.json();
    const parts = [];
    parts.push(data.groq_configured ? "Groq ready" : "Groq not configured");
    parts.push(data.kite_configured ? "Kite ready" : "Kite not configured");
    parts.push(`${data.tools_count} tools`);
    elements.agentStatus.textContent = parts.join(" · ");
  } catch {
    elements.agentStatus.textContent = "Agent API offline — start with: python3 run_agent_api.py";
    addBubble(
      "system",
      "Agent API is not running. Start it with: python3 run_agent_api.py (port 8000)"
    );
  }
}

async function loadTools() {
  try {
    const res = await fetch(`${AGENT_API}/api/agent/tools`);
    const data = await res.json();
    elements.toolList.innerHTML = (data.tools || [])
      .map((t) => `<li><strong>${escapeHtml(t.name)}</strong>${escapeHtml(t.description)}</li>`)
      .join("");
  } catch {
    elements.toolList.innerHTML = "<li>Tools unavailable — start agent API</li>";
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

async function sendMessage(text) {
  history.push({ role: "user", content: text });
  addBubble("user", text);

  elements.sendBtn.disabled = true;
  elements.chatInput.disabled = true;

  try {
    const res = await fetch(`${AGENT_API}/api/agent/chat`, {
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

    addBubble("assistant", reply, toolsMeta);
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

addBubble(
  "assistant",
  "Hi! I can check your Kite portfolio, run trading strategies on your tickers, benchmark performance, and run custom scripts. What would you like to know?"
);

loadHealth();
loadTools();
