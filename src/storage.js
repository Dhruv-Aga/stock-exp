const NAMESPACE = "bharat-scout";

export function loadSetting(key, fallback) {
  try {
    const value = localStorage.getItem(`${NAMESPACE}:${key}`);
    return value === null ? fallback : JSON.parse(value);
  } catch {
    return fallback;
  }
}

export function saveSetting(key, value) {
  localStorage.setItem(`${NAMESPACE}:${key}`, JSON.stringify(value));
}
