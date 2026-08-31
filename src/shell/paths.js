/** Resolve internal URLs for GitHub Pages subpath hosting (e.g. /stock-exp/). */

const ROUTES = [
  "portfolio",
  "approvals",
  "assistant",
  "screener",
  "compare",
  "tracker",
  "paper",
];

/**
 * @returns {string} Base path without trailing slash, or "" at site root.
 */
export function getBasePath() {
  if (typeof window !== "undefined") {
    if (typeof window.__BASE_PATH__ === "string") {
      return window.__BASE_PATH__;
    }
    if (typeof window.BHARAT_SCOUT_BASE_PATH === "string") {
      return window.BHARAT_SCOUT_BASE_PATH;
    }
  }

  if (typeof window === "undefined") return "";

  const p = window.location.pathname || "/";
  for (const route of ROUTES) {
    const marker = `/${route}/`;
    const idx = p.indexOf(marker);
    if (idx > 0) return p.slice(0, idx);
    if (idx === 0 || p === `/${route}`) return "";
  }

  const trimmed = p.replace(/\/+$/, "");
  return trimmed && trimmed !== "" ? trimmed : "";
}

/**
 * @param {string} path Internal path starting with "/" (may include hash/query).
 * @returns {string}
 */
export function url(path) {
  const base = getBasePath().replace(/\/+$/, "");
  if (!path || path === "/") {
    return base ? `${base}/` : "/";
  }

  const hashIdx = path.indexOf("#");
  const queryIdx = path.indexOf("?");
  const splitIdx =
    hashIdx === -1
      ? queryIdx
      : queryIdx === -1
        ? hashIdx
        : Math.min(hashIdx, queryIdx);

  const pathname = splitIdx === -1 ? path : path.slice(0, splitIdx);
  const suffix = splitIdx === -1 ? "" : path.slice(splitIdx);
  const normalized = pathname.startsWith("/") ? pathname : `/${pathname}`;

  return `${base}${normalized}${suffix}`;
}

/**
 * Rewrite static root-absolute links/iframes for GitHub Pages subpaths.
 * @param {ParentNode} [root]
 */
export function rewriteStaticLinks(root = document) {
  root.querySelectorAll('a[href^="/"]').forEach((anchor) => {
    const href = anchor.getAttribute("href");
    if (!href || href.startsWith("//")) return;
    anchor.setAttribute("href", url(href));
  });

  root.querySelectorAll('iframe[src^="/"]').forEach((frame) => {
    const src = frame.getAttribute("src");
    if (!src) return;
    frame.setAttribute("src", url(src));
  });
}
