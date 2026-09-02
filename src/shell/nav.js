/** Shared navigation for all Bharat Scout pages. */

import { url } from "./paths.js";

export const NAV_ITEMS = [
  { id: "home", label: "Home", href: "/" },
  { id: "portfolio", label: "Portfolio", href: "/portfolio/" },
  { id: "compare", label: "Compare", href: "/compare/" },
  { id: "approvals", label: "Review", href: "/approvals/", badgeKey: "pending_proposals" },
  { id: "assistant", label: "Ask", href: "/assistant/" },
  { id: "screener", label: "Research", href: "/screener/", secondary: true },
];

/**
 * @param {HTMLElement} container
 * @param {string} currentId
 * @param {{ pending_proposals?: number }} badges
 */
export function mountNav(container, currentId, badges = {}) {
  const nav = document.createElement("nav");
  nav.className = "site-nav";
  nav.setAttribute("aria-label", "Main");

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "nav-toggle";
  toggle.setAttribute("aria-label", "Toggle navigation");
  toggle.setAttribute("aria-expanded", "false");
  toggle.innerHTML = '<span></span><span></span><span></span>';

  const statusToggle = document.createElement("button");
  statusToggle.type = "button";
  statusToggle.className = "status-toggle";
  statusToggle.setAttribute("aria-label", "Toggle status strip");
  statusToggle.setAttribute("aria-expanded", "false");
  statusToggle.textContent = "Status";

  const links = document.createElement("div");
  links.className = "nav-links";

  for (const item of NAV_ITEMS) {
    const a = document.createElement("a");
    a.href = url(item.href);
    a.textContent = item.label;
    if (item.secondary) {
      a.classList.add("nav-secondary");
    }
    if (item.id === currentId) {
      a.setAttribute("aria-current", "page");
    }
    const count = item.badgeKey ? Number(badges[item.badgeKey] || 0) : 0;
    if (count > 0) {
      const badge = document.createElement("span");
      badge.className = "nav-badge";
      badge.textContent = String(count);
      a.appendChild(badge);
    }
    links.appendChild(a);
  }

  toggle.addEventListener("click", () => {
    const isOpen = nav.classList.toggle("nav-open");
    toggle.setAttribute("aria-expanded", String(isOpen));
  });

  statusToggle.addEventListener("click", () => {
    const statusStrip = document.querySelector("#shell-status");
    if (!statusStrip) return;
    const isOpen = statusStrip.classList.toggle("is-open");
    statusToggle.setAttribute("aria-expanded", String(isOpen));
  });

  nav.appendChild(toggle);
  nav.appendChild(links);
  nav.appendChild(statusToggle);
  container.replaceChildren(nav);
}
