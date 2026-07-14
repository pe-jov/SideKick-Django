// Autor: Milan Neskovic, 545/19
const STORAGE_KEY = "sidekick-extension-session";
const UI_STATE_KEYS = ["modal", "dialog", "preview", "mock", "authToken"];

const isExtensionMode = () => document.body?.dataset.extensionMode === "true";
const isAuthenticated = () => document.body?.dataset.authenticated === "true";

const clearExtensionSession = async () => {
  await chrome.storage.local.remove(STORAGE_KEY);
};

const notifyExtension = (type, payload = {}) => {
  chrome.runtime.sendMessage({ type, payload }).catch(() => {});
};

const getPersistedRoute = () => {
  const url = new URL(window.location.href);
  UI_STATE_KEYS.forEach((key) => url.searchParams.delete(key));
  const query = url.searchParams.toString();
  return `${url.pathname}${query ? `?${query}` : ""}`;
};

const syncExtensionRoute = async () => {
  if (!isExtensionMode() || !isAuthenticated()) return;

  const result = await chrome.storage.local.get(STORAGE_KEY);
  const currentSession = result[STORAGE_KEY];
  if (!currentSession?.token || !currentSession?.baseUrl) return;

  const nextState = {
    ...currentSession,
    lastPath: getPersistedRoute(),
  };

  await chrome.storage.local.set({ [STORAGE_KEY]: nextState });
  notifyExtension("SIDEKICK_EXTENSION_ROUTE", { lastPath: nextState.lastPath });
};

window.addEventListener("message", async (event) => {
  if (event.source !== window) return;
  if (event.origin !== window.location.origin) return;
  if (event.data?.type !== "SIDEKICK_CONNECT_EXTENSION") return;

  const payload = event.data.payload || {};
  if (!payload.token || !payload.baseUrl) return;

  await chrome.storage.local.set({
    [STORAGE_KEY]: {
      token: payload.token,
      baseUrl: payload.baseUrl,
      user: payload.user || null,
      lastPath: getPersistedRoute(),
    },
  });
  notifyExtension("SIDEKICK_EXTENSION_CONNECTED", {
    token: payload.token,
    baseUrl: payload.baseUrl,
    user: payload.user || null,
    lastPath: getPersistedRoute(),
  });

  window.postMessage({ type: "SIDEKICK_EXTENSION_CONNECTED" }, window.location.origin);
});

if (isExtensionMode() && !isAuthenticated()) {
  notifyExtension("SIDEKICK_EXTENSION_DISCONNECTED");
  void clearExtensionSession();
}

document.addEventListener("submit", (event) => {
  const form = event.target.closest("[data-extension-logout-form]");
  if (!form) return;
  notifyExtension("SIDEKICK_EXTENSION_DISCONNECTED");
  void clearExtensionSession();
}, true);

document.addEventListener("DOMContentLoaded", () => {
  void syncExtensionRoute();
});

window.addEventListener("pageshow", () => {
  void syncExtensionRoute();
});

window.addEventListener("popstate", () => {
  void syncExtensionRoute();
});

