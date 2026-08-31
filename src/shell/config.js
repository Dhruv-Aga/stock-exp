/**
 * Shared local configuration for all frontend pages.
 * Override at runtime: window.AGENT_API_URL = "http://..."
 */

import { url } from "./paths.js";

const host = window.location.hostname || "localhost";

export const CONFIG = {
  agentApiUrl: window.AGENT_API_URL || `http://${host}:8000`,
  frontendPort: 8080,
  agentPort: 8000,
  kiteProxyPort: 3000,
  get analysisUrl() {
    return url("/paper/analysis.json");
  },
};

export function agentUrl(path) {
  const base = CONFIG.agentApiUrl.replace(/\/+$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${base}${p}`;
}
