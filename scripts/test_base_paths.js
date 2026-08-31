/**
 * Lightweight checks for GitHub Pages base-path resolution.
 * Run: node scripts/test_base_paths.js
 */

function detectBasePath(pathname) {
  const routes = [
    "portfolio",
    "approvals",
    "assistant",
    "screener",
    "compare",
    "tracker",
    "paper",
  ];

  const p = pathname || "/";
  for (const route of routes) {
    const marker = `/${route}/`;
    const idx = p.indexOf(marker);
    if (idx > 0) return p.slice(0, idx);
    if (idx === 0 || p === `/${route}`) return "";
  }

  const trimmed = p.replace(/\/+$/, "");
  return trimmed && trimmed !== "" ? trimmed : "";
}

function url(pathname, path) {
  const base = detectBasePath(pathname).replace(/\/+$/, "");
  if (!path || path === "/") {
    return base ? `${base}/` : "/";
  }
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalized}`;
}

const cases = [
  ["/stock-exp/", "", "/stock-exp/"],
  ["/stock-exp/portfolio/", "/approvals/", "/stock-exp/approvals/"],
  ["/portfolio/", "/portfolio/", "/portfolio/"],
  ["/", "/portfolio/", "/portfolio/"],
  ["/stock-exp", "/screener/", "/stock-exp/screener/"],
];

let failed = 0;
for (const [pathname, input, expected] of cases) {
  const got = url(pathname, input);
  if (got !== expected) {
    console.error(`FAIL ${pathname} + ${input}: expected ${expected}, got ${got}`);
    failed += 1;
  }
}

if (failed) {
  process.exit(1);
}

console.log(`All ${cases.length} base-path cases passed.`);
