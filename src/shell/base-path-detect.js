/**
 * Synchronous base-path detection for GitHub Pages project sites.
 * Sets window.__BASE_PATH__ before module scripts run.
 */
(function () {
  if (typeof window.__BASE_PATH__ === "string") return;

  if (typeof window.BHARAT_SCOUT_BASE_PATH === "string") {
    window.__BASE_PATH__ = window.BHARAT_SCOUT_BASE_PATH;
    return;
  }

  var p = window.location.pathname || "/";
  var routes = [
    "portfolio",
    "approvals",
    "assistant",
    "screener",
    "compare",
    "tracker",
    "paper",
  ];

  for (var i = 0; i < routes.length; i++) {
    var route = routes[i];
    var marker = "/" + route + "/";
    var idx = p.indexOf(marker);
    if (idx > 0) {
      window.__BASE_PATH__ = p.slice(0, idx);
      return;
    }
    if (idx === 0 || p === "/" + route) {
      window.__BASE_PATH__ = "";
      return;
    }
  }

  var trimmed = p.replace(/\/+$/, "");
  window.__BASE_PATH__ = trimmed && trimmed !== "" ? trimmed : "";
})();
