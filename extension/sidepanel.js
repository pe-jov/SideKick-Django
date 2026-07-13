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

const withAuthToken = (baseUrl, path = "/") => {
  const url = new URL(path, `${normalizeBaseUrl(baseUrl)}/`);
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

const setConnectionState = (connected) => {
  document.body.classList.toggle("extension-connected", connected);
  document.body.classList.toggle("extension-disconnected", !connected);
};

const renderLoggedOut = () => {
  setConnectionState(false);
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
  setConnectionState(true);
  openWebButton.hidden = false;
  logoutButton.hidden = false;
  const nextSrc = withAuthToken(sessionState.baseUrl, "/");
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
      user: payload.user || sessionState.user || null,
    });
    renderLoggedIn();
  } catch {
    await clearSession();
    renderLoggedOut();
  }
};

openLoginTabButton.addEventListener("click", async () => {
  const baseUrl = normalizeBaseUrl(baseUrlInput.value);
  await chrome.tabs.create({ url: `${baseUrl}/` });
});

openWebButton.addEventListener("click", async () => {
  if (!sessionState?.baseUrl) return;
  await chrome.tabs.create({ url: withAuthToken(sessionState.baseUrl, "/") });
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
  sessionState = changes[STORAGE_KEY].newValue || null;
  if (sessionState?.token) {
    setFeedback("");
    await validateSession();
    return;
  }
  renderLoggedOut();
});

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "SIDEKICK_EXTENSION_CONNECTED") {
    const payload = message.payload || {};
    sessionState = {
      token: payload.token || sessionState?.token || "",
      baseUrl: normalizeBaseUrl(payload.baseUrl || sessionState?.baseUrl || baseUrlInput.value),
      user: payload.user || sessionState?.user || null,
    };
    setFeedback("");
    renderLoggedIn();
    return;
  }

  if (message?.type === "SIDEKICK_EXTENSION_DISCONNECTED") {
    sessionState = null;
    renderLoggedOut();
  }
});

appFrame.addEventListener("load", async () => {
  if (!sessionState?.token) return;
  window.setTimeout(async () => {
    await loadStoredSession();
    if (!sessionState?.token) {
      renderLoggedOut();
      return;
    }
    await validateSession();
  }, 80);
});

void (async () => {
  setConnectionState(false);
  await loadStoredSession();
  await validateSession();
})();
