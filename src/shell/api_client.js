/**
 * Authenticated fetch wrapper for the agent API.
 * Stores BHARAT_SCOUT_API_KEY in sessionStorage (cleared when browser closes).
 */

import { agentUrl } from "./config.js";

const STORAGE_KEY = "bharat_scout_api_key";

export function getApiKey() {
  return sessionStorage.getItem(STORAGE_KEY) || "";
}

export function setApiKey(key) {
  const trimmed = (key || "").trim();
  if (trimmed) {
    sessionStorage.setItem(STORAGE_KEY, trimmed);
  } else {
    sessionStorage.removeItem(STORAGE_KEY);
  }
}

export function clearApiKey() {
  sessionStorage.removeItem(STORAGE_KEY);
}

function authHeaders(extra = {}) {
  const headers = { ...extra };
  const key = getApiKey();
  if (key) {
    headers["X-Bharat-Scout-Key"] = key;
  }
  return headers;
}

/**
 * Fetch from the agent API with optional API key header.
 * On 401, prompts once for the key (if auth_required).
 */
export async function apiFetch(path, options = {}) {
  const headers = authHeaders(options.headers || {});
  let res = await fetch(agentUrl(path), { ...options, headers });

  if (res.status === 401) {
    let body = {};
    try {
      body = await res.clone().json();
    } catch {
      /* ignore */
    }
    if (body.auth_required && !getApiKey()) {
      const entered = window.prompt(
        "Enter your Bharat Scout API key (from .env BHARAT_SCOUT_API_KEY):"
      );
      if (entered) {
        setApiKey(entered);
        const retryHeaders = authHeaders(options.headers || {});
        res = await fetch(agentUrl(path), { ...options, headers: retryHeaders });
      }
    }
  }

  return res;
}
