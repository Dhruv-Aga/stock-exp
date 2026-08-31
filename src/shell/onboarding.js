/**
 * Setup checklist shown on Home when configuration is incomplete.
 * @param {HTMLElement} container
 * @param {object|null} summary from /api/trading/summary
 */
export function mountOnboarding(container, summary) {
  const setup = summary?.setup || {};
  const agent = summary?.agent || {};
  const steps = [
    {
      label: "Create .env from .env.example",
      ok: setup.env_file,
      hint: "cp .env.example .env",
    },
    {
      label: "Add GROQ_API_KEY for the assistant",
      ok: agent.groq_configured,
      hint: "Get a key at console.groq.com",
    },
    {
      label: "Add KITE_* keys for live portfolio (optional)",
      ok: agent.kite_configured,
      hint: "python3 run_kite_login.py",
      optional: true,
    },
    {
      label: "Run paper trading snapshot",
      ok: setup.paper_snapshot,
      hint: "./scripts/dev.sh paper",
    },
    {
      label: "Start local services",
      ok: setup.services_running,
      hint: "./scripts/dev.sh start",
    },
  ];

  const incomplete = steps.filter((s) => !s.ok && !s.optional);
  if (!incomplete.length) {
    container.replaceChildren();
    container.classList.add("hidden");
    return;
  }

  container.classList.remove("hidden");
  container.className = "shell-onboarding card";
  container.innerHTML = `
    <h2>Get started locally</h2>
    <p class="sub">One <code>.env</code> file and <code>./scripts/dev.sh</code> configure everything.</p>
    <ol class="onboarding-steps">
      ${steps
        .map(
          (step) => `
        <li class="${step.ok ? "done" : step.optional ? "optional" : "todo"}">
          <span class="step-icon">${step.ok ? "✓" : step.optional ? "○" : "•"}</span>
          <div>
            <strong>${step.label}</strong>
            ${!step.ok ? `<div class="step-hint"><code>${step.hint}</code></div>` : ""}
          </div>
        </li>`
        )
        .join("")}
    </ol>
    <p class="sub">Full guide: <code>LOCAL.md</code> · diagnostic: <code>python3 check_setup.py</code></p>
  `;
}
