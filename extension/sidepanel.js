// Autor: Milan Neskovic, 545/19
const STORAGE_KEY = "sidekick-extension-session";
const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

const baseUrlInput = document.querySelector("[data-base-url]");
const appFrame = document.querySelector("[data-app-frame]");
const openLoginTabButton = document.querySelector("[data-open-login-tab]");
const openWebButton = document.querySelector("[data-open-web]");
const logoutButton = document.querySelector("[data-logout]");

let sessionState = null;

const normalizeBaseUrl = (value) => {
  const trimmed = String(value || "").trim().replace(/\/+$/, "");
  return trimmed || DEFAULT_BASE_URL;
};

const normalizeAppPath = (value) => {
  const raw = String(value || "").trim();
  if (!raw) return "/";

  try {
    const url = new URL(raw, `${normalizeBaseUrl(sessionState?.baseUrl || baseUrlInput?.value || DEFAULT_BASE_URL)}/`);
    ["modal", "dialog", "preview", "mock", "authToken"].forEach((key) => url.searchParams.delete(key));
    const query = url.searchParams.toString();
    return `${url.pathname}${query ? `?${query}` : ""}`;
  } catch {
    return raw.startsWith("/") ? raw : `/${raw}`;
  }
};

const withAuthToken = (baseUrl, path = "/") => {
  const url = new URL(normalizeAppPath(path), `${normalizeBaseUrl(baseUrl)}/`);
  if (sessionState?.token) {
    url.searchParams.set("authToken", sessionState.token);
  }
  return url.toString();
};

const storeSession = async (nextState) => {
  sessionState = nextState;
  await chrome.storage.local.set({ [STORAGE_KEY]: nextState });
};

const clearSession = async () => {
  sessionState = null;
  await chrome.storage.local.remove(STORAGE_KEY);
};

const setFeedback = (_message = "") => {};

// Keep the panel in a neutral boot state until we know whether a saved extension session exists.
const setConnectionState = (state) => {
  document.body.classList.remove("extension-booting", "extension-connected", "extension-disconnected");
  document.body.classList.add(`extension-${state}`);
};

const renderLoggedOut = () => {
  setConnectionState("disconnected");
  openWebButton.hidden = true;
  logoutButton.hidden = true;
  appFrame.removeAttribute("src");
  setFeedback("Open the app, log in, then press Connect extension in the header.");
  baseUrlInput.value = normalizeBaseUrl(sessionState?.baseUrl || baseUrlInput.value);
};

const renderLoggedIn = () => {
  if (!sessionState?.token) {
    renderLoggedOut();
    return;
  }
  setConnectionState("connected");
  openWebButton.hidden = false;
  logoutButton.hidden = false;
  const nextSrc = withAuthToken(sessionState.baseUrl, sessionState.lastPath || "/");
  if (appFrame.src !== nextSrc) {
    appFrame.src = nextSrc;
  }
};

const loadStoredSession = async () => {
  const result = await chrome.storage.local.get(STORAGE_KEY);
  sessionState = result[STORAGE_KEY] || null;
  baseUrlInput.value = normalizeBaseUrl(sessionState?.baseUrl || DEFAULT_BASE_URL);
};

const apiRequest = async (path, options = {}, baseUrlOverride = "") => {
  const baseUrl = normalizeBaseUrl(baseUrlOverride || sessionState?.baseUrl || baseUrlInput.value);
  const response = await fetch(new URL(path, `${baseUrl}/`), options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json().catch(() => ({})) : {};
  if (!response.ok) {
    const message = payload?.error?.message || "Request failed.";
    throw new Error(message);
  }
  return { payload, baseUrl, response };
};

const validateSession = async (baseUrlOverride = "") => {
  const baseUrl = normalizeBaseUrl(baseUrlOverride || sessionState?.baseUrl || baseUrlInput.value);
  if (!sessionState?.token) {
    renderLoggedOut();
    return;
  }

  try {
    const { payload } = await apiRequest("/api/me/", {
      headers: {
        Authorization: `Bearer ${sessionState.token}`,
      },
    }, baseUrl);

    await storeSession({
      ...sessionState,
      baseUrl,
      lastPath: normalizeAppPath(sessionState?.lastPath || "/"),
      user: payload.user || sessionState.user || null,
    });
    renderLoggedIn();
  } catch {
    await clearSession();
    renderLoggedOut();
  }
};

const bootstrapPanel = async () => {
  setConnectionState("booting");
  await loadStoredSession();

  if (!sessionState?.token) {
    renderLoggedOut();
    return;
  }

  renderLoggedIn();
  void validateSession();
};

openLoginTabButton.addEventListener("click", async () => {
  const baseUrl = normalizeBaseUrl(baseUrlInput.value);
  await chrome.tabs.create({ url: `${baseUrl}/` });
});

openWebButton.addEventListener("click", async () => {
  if (!sessionState?.baseUrl) return;
  await chrome.tabs.create({ url: withAuthToken(sessionState.baseUrl, sessionState.lastPath || "/") });
});

logoutButton.addEventListener("click", async () => {
  if (sessionState?.token) {
    try {
      await apiRequest("/api/logout/", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${sessionState.token}`,
        },
      });
    } catch {
      // Clear extension storage even if the token was already invalidated.
    }
  }

  await clearSession();
  renderLoggedOut();
});

chrome.storage.onChanged.addListener(async (changes, areaName) => {
  if (areaName !== "local" || !changes[STORAGE_KEY]) return;
  const nextState = changes[STORAGE_KEY].newValue || null;
  const currentSerialized = JSON.stringify(sessionState || null);
  const nextSerialized = JSON.stringify(nextState || null);
  if (currentSerialized === nextSerialized) return;

  const credentialsChanged = (
    nextState?.token !== sessionState?.token
    || normalizeBaseUrl(nextState?.baseUrl || "") !== normalizeBaseUrl(sessionState?.baseUrl || "")
  );

  sessionState = nextState;
  baseUrlInput.value = normalizeBaseUrl(sessionState?.baseUrl || DEFAULT_BASE_URL);

  if (!sessionState?.token) {
    renderLoggedOut();
    return;
  }

  setFeedback("");
  renderLoggedIn();
  if (credentialsChanged) {
    await validateSession();
  }
});

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "SIDEKICK_EXTENSION_CONNECTED") {
    const payload = message.payload || {};
    sessionState = {
      token: payload.token || sessionState?.token || "",
      baseUrl: normalizeBaseUrl(payload.baseUrl || sessionState?.baseUrl || baseUrlInput.value),
      user: payload.user || sessionState?.user || null,
      lastPath: normalizeAppPath(payload.lastPath || sessionState?.lastPath || "/"),
    };
    setFeedback("");
    renderLoggedIn();
    return;
  }

  if (message?.type === "SIDEKICK_EXTENSION_ROUTE") {
    const payload = message.payload || {};
    if (!sessionState?.token) return;
    sessionState = {
      ...sessionState,
      lastPath: normalizeAppPath(payload.lastPath || sessionState.lastPath || "/"),
    };
    void storeSession(sessionState);
    return;
  }

  if (message?.type === "SIDEKICK_EXTENSION_DISCONNECTED") {
    sessionState = null;
    renderLoggedOut();
  }
});
void (async () => {
  await bootstrapPanel();
})();

