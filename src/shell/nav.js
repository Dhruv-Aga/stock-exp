/** Shared navigation for all Bharat Scout pages. */

export const NAV_ITEMS = [
  { id: "home", label: "Home", href: "/" },
  { id: "portfolio", label: "Portfolio", href: "/portfolio/" },
  { id: "screener", label: "Screener", href: "/screener/" },
  { id: "assistant", label: "Assistant", href: "/assistant/" },
  { id: "approvals", label: "Approvals", href: "/approvals/", badgeKey: "pending_proposals" },
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

  for (const item of NAV_ITEMS) {
    const a = document.createElement("a");
    a.href = item.href;
    a.textContent = item.label;
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
    nav.appendChild(a);
  }

  container.replaceChildren(nav);
}
