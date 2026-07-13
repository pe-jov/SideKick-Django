const STORAGE_KEY = "sidekick-extension-session";

const isExtensionMode = () => document.body?.dataset.extensionMode === "true";
const isAuthenticated = () => document.body?.dataset.authenticated === "true";

const clearExtensionSession = async () => {
  await chrome.storage.local.remove(STORAGE_KEY);
};

const notifyExtension = (type, payload = {}) => {
  chrome.runtime.sendMessage({ type, payload }).catch(() => {});
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
    },
  });
  notifyExtension("SIDEKICK_EXTENSION_CONNECTED", {
    token: payload.token,
    baseUrl: payload.baseUrl,
    user: payload.user || null,
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
