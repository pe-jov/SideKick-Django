// Autor: Petar Jovanovic, 276/20
const root = document.documentElement;
const mainContent = document.querySelector(".main-content");
const messageStack = document.querySelector(".message-stack");
const toggle = document.querySelector("[data-theme-toggle]");
const changePasswordForm = document.querySelector("[data-change-password-form]");
const passwordFeedback = document.querySelector("[data-password-feedback]");
const spaceCaptureSurface = document.querySelector("[data-space-capture-surface]");
const spaceCaptureOverlay = document.querySelector("[data-space-capture-overlay]");
const dropZone = document.querySelector("[data-drop-zone]");
const spaceUploadForm = document.querySelector("[data-space-upload-form]");
const itemContextMenu = document.querySelector("[data-item-context-menu]");
const itemContextAction = document.querySelector("[data-item-context-action]");
const itemCardsWithMenu = [...document.querySelectorAll(".item-card[data-delete-url]")];
const memberRowsWithMenu = [...document.querySelectorAll(".collaborator-row[data-member-remove-url]")];
const previewableItemCards = [...document.querySelectorAll(".item-card[data-preview-url]")];
const draggableItemCards = [...document.querySelectorAll(".item-card[data-can-drag='true'][data-item-id]")];
const spaceDropTargets = [...document.querySelectorAll(".space-card[data-drop-space-id]")];
const spaceCards = [...document.querySelectorAll(".space-card")];
const appShell = document.querySelector(".app-shell");
const connectExtensionForm = document.querySelector("[data-connect-extension-form]");
const realtimeSpaceScope = document.querySelector("[data-realtime-space-id]");
let clientPreviewOverlay = null;

// Space cards stay click-only so the inbox move flow never treats them as draggable content.
spaceCards.forEach((card) => {
  card.draggable = false;
  card.addEventListener("dragstart", (event) => {
    event.preventDefault();
  });
});

// Extension auth should only propagate when the page is actually rendered in extension mode.
const isExtensionMode = () => (
  document.body?.dataset.extensionMode === "true"
  || root.dataset.extensionMode === "true"
);

// Read the extension token from server-rendered data first and fall back to the URL only in extension mode.
const getExtensionAuthToken = () => (
  isExtensionMode()
    ? (
      document.body?.dataset.authToken
      || root.dataset.authToken
      || new URL(window.location.href).searchParams.get("authToken")
      || ""
    )
    : ""
);

// Keep internal navigation extension-aware without touching normal web navigation.
const appendExtensionAuth = (value) => {
  const authToken = getExtensionAuthToken();
  if (!authToken || !value) return value;

  try {
    const targetUrl = new URL(value, window.location.href);
    if (targetUrl.origin !== window.location.origin) return value;
    targetUrl.searchParams.set("authToken", authToken);
    return targetUrl.toString();
  } catch {
    return value;
  }
};

// Normalize links after render so extension pages preserve their auth token across in-app navigation.
const normalizeInternalAnchors = (scope = document) => {
  if (!getExtensionAuthToken()) return;
  scope.querySelectorAll("a[href]").forEach((anchor) => {
    const href = anchor.getAttribute("href");
    if (!href || href.startsWith("#") || href.startsWith("javascript:")) return;
    anchor.href = appendExtensionAuth(anchor.href);
  });
};

// POST forms need the same token propagation path when they are submitted from the extension shell.
const ensureAuthField = (form) => {
  const authToken = getExtensionAuthToken();
  if (!authToken || !form) return;
  form.action = appendExtensionAuth(form.action || window.location.href);
  let field = form.querySelector('input[name="authToken"]');
  if (!field) {
    field = document.createElement("input");
    field.type = "hidden";
    field.name = "authToken";
    form.appendChild(field);
  }
  field.value = authToken;
};

// AJAX requests reuse the same token contract as form submissions.
const appendAuthToFormData = (formData) => {
  const authToken = getExtensionAuthToken();
  if (!authToken) return formData;
  formData.set("authToken", authToken);
  return formData;
};

const getCurrentMessageStack = () => document.querySelector(".message-stack");

const LINK_BRAND_COLORS = {
  apple: "#a1a1aa",
  behance: "#1769ff",
  dribbble: "#ea4c89",
  figma: "#7b61ff",
  github: "#24292f",
  instagram: "#e4405f",
  medium: "#121212",
  notion: "#111111",
  openai: "#10a37f",
  pinterest: "#e60023",
  reddit: "#ff4500",
  substack: "#ff6719",
  tiktok: "#111111",
  twitter: "#1d9bf0",
  vimeo: "#1ab7ea",
  youtube: "#ff0033",
};

const normalizeDomainKey = (value) => {
  const cleaned = String(value || "")
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/^www\./, "")
    .split("/")[0]
    .split(":")[0];
  const parts = cleaned.split(".").filter(Boolean);
  if (parts.length === 0) return "";
  if (parts.length === 1) return parts[0];
  return parts[parts.length - 2];
};

const colorFromDomain = (value) => {
  const key = normalizeDomainKey(value);
  if (!key) return "#5b6cfa";
  if (LINK_BRAND_COLORS[key]) return LINK_BRAND_COLORS[key];

  let hash = 0;
  for (let index = 0; index < key.length; index += 1) {
    hash = ((hash << 5) - hash) + key.charCodeAt(index);
    hash |= 0;
  }

  const hue = Math.abs(hash) % 360;
  return `hsl(${hue} 68% 54%)`;
};

const applyLinkCardAccents = (scope = document) => {
  scope.querySelectorAll(".item-card[data-type='link']").forEach((card) => {
    const accent = colorFromDomain(card.dataset.domain || card.dataset.externalUrl || card.dataset.title);
    card.style.setProperty("--item-accent", accent);
  });
};

const MOBILE_ITEM_MASONRY_BREAKPOINT = 640;
const WIDE_ITEM_MASONRY_BREAKPOINT = 980;

const getOrderedItemMasonryColumnCount = (target) => {
  const width = Math.max(window.innerWidth, target?.clientWidth || 0);
  if (width <= MOBILE_ITEM_MASONRY_BREAKPOINT) return 2;
  if (width >= WIDE_ITEM_MASONRY_BREAKPOINT) return 3;
  return 2;
};

const ensureOrderedItemMasonry = (target) => {
  if (!target?.matches?.("[data-filter-target='items']")) return;

  const cards = [...target.querySelectorAll(".item-card")];
  cards.forEach((card, index) => {
    if (!card.dataset.mobileOrder) {
      card.dataset.mobileOrder = String(index);
    }
  });

  const orderedCards = [...cards].sort(
    (left, right) => Number(left.dataset.mobileOrder || 0) - Number(right.dataset.mobileOrder || 0),
  );

  target.querySelectorAll(".item-masonry-column").forEach((column) => column.remove());
  orderedCards.forEach((card) => target.appendChild(card));

  const visibleCards = orderedCards.filter((card) => !card.hidden);
  if (visibleCards.length === 0) {
    target.classList.remove("item-masonry--ordered");
    target.style.removeProperty("--item-masonry-columns");
    return;
  }

  const columnCount = getOrderedItemMasonryColumnCount(target);
  target.classList.add("item-masonry--ordered");
  target.style.setProperty("--item-masonry-columns", String(columnCount));

  const columns = Array.from({ length: columnCount }, (_value, index) => {
    const column = document.createElement("div");
    column.className = "item-masonry-column";
    column.dataset.itemMasonryColumn = String(index);
    target.appendChild(column);
    return column;
  });

  visibleCards.forEach((card, index) => {
    columns[index % columnCount].appendChild(card);
  });
};

const refreshOrderedItemMasonry = (scope = document) => {
  scope.querySelectorAll("[data-filter-target='items']").forEach((target) => {
    ensureOrderedItemMasonry(target);
  });
};

const clearDynamicOverlays = () => {
  document.querySelectorAll("[data-overlay-kind]").forEach((node) => node.remove());
};

const closeDynamicOverlay = (node) => {
  const overlay = node?.closest?.("[data-overlay-kind]");
  if (!overlay) return false;
  overlay.remove();
  return true;
};

const closeClientPreview = () => {
  clientPreviewOverlay?.remove();
  clientPreviewOverlay = null;
  document.body.classList.remove("modal-scroll-locked");
};

const insertDynamicOverlays = (doc) => {
  if (!appShell) return;
  const overlays = [...doc.querySelectorAll("[data-overlay-kind]")];
  const bottomNav = appShell.querySelector(".bottom-nav");
  const insertBefore = bottomNav || appShell.querySelector(".item-context-menu");
  overlays.forEach((overlay) => {
    if (insertBefore) {
      appShell.insertBefore(overlay, insertBefore);
    } else {
      appShell.appendChild(overlay);
    }
  });
  normalizeInternalAnchors(appShell);
  initializeDynamicForms(appShell);
  applyLinkCardAccents(appShell);
};

const syncMessagesFromDocument = (doc) => {
  const current = getCurrentMessageStack();
  const incoming = doc.querySelector(".message-stack");
  if (incoming && current) {
    current.replaceWith(incoming);
    return;
  }
  if (incoming && !current) {
    const currentMain = document.querySelector(".main-content");
    currentMain?.prepend(incoming);
    return;
  }
  if (!incoming && current) {
    current.remove();
  }
};

const isLocalUiStateUrl = (value) => {
  try {
    const targetUrl = new URL(value, window.location.href);
    if (targetUrl.origin !== window.location.origin) return false;
    if (targetUrl.pathname !== window.location.pathname) return false;
    const params = targetUrl.searchParams;
    return ["modal", "dialog", "preview", "mock"].some((key) => params.has(key));
  } catch {
    return false;
  }
};

const loadUiState = async (url, { pushHistory = false } = {}) => {
  try {
    if (itemContextMenu) {
      itemContextMenu.hidden = true;
    }
    const targetUrl = appendExtensionAuth(url);
    const response = await fetch(targetUrl, {
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
    });
    if (!response.ok) {
      window.location.href = url;
      return;
    }

    const html = await response.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, "text/html");
    clearDynamicOverlays();
    insertDynamicOverlays(doc);
    syncMessagesFromDocument(doc);
    if (pushHistory) {
      window.history.pushState({ uiState: true }, "", targetUrl);
    }
  } catch {
    window.location.href = appendExtensionAuth(url);
  }
};

const passwordRules = [
  { test: (value) => value.length >= 8, message: "Use at least 8 characters." },
  { test: (value) => /[a-z]/.test(value), message: "Add a lowercase letter." },
  { test: (value) => /[A-Z]/.test(value), message: "Add an uppercase letter." },
  { test: (value) => /\d/.test(value), message: "Add a number." },
  { test: (value) => /[^A-Za-z0-9]/.test(value), message: "Add a special character." },
];

if (toggle) {
  toggle.addEventListener("click", () => {
    root.classList.toggle("dark");
    localStorage.setItem("sidekick-theme", root.classList.contains("dark") ? "dark" : "light");
  });
}

normalizeInternalAnchors(document);

document.addEventListener("submit", (event) => {
  ensureAuthField(event.target);
}, true);

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const modal = document.querySelector("[data-modal-backdrop]");
  if (itemContextMenu) {
    itemContextMenu.hidden = true;
  }
  if (clientPreviewOverlay) {
    closeClientPreview();
    return;
  }
  if (modal && closeDynamicOverlay(modal)) {
    return;
  }
});

document.addEventListener("click", (event) => {
  if (clientPreviewOverlay && event.target === clientPreviewOverlay) {
    event.preventDefault();
    closeClientPreview();
    return;
  }

  const backdrop = event.target.closest("[data-modal-backdrop][data-close-url]");
  if (backdrop && event.target === backdrop) {
    event.preventDefault();
    closeDynamicOverlay(backdrop);
    return;
  }

  const overlayCloseButton = event.target.closest("[data-overlay-kind] .close-button");
  if (overlayCloseButton) {
    event.preventDefault();
    if (closeDynamicOverlay(overlayCloseButton)) {
      return;
    }
  }

  const link = event.target.closest("a[href]");
  if (!link) return;
  if (event.defaultPrevented) return;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  if (link.target && link.target !== "_self") return;
  if (!isLocalUiStateUrl(link.href)) return;
  event.preventDefault();
  loadUiState(link.href, { pushHistory: false });
});

window.addEventListener("popstate", () => {
  const hasUiState = ["modal", "dialog", "preview", "mock"].some(
    (key) => new URL(window.location.href).searchParams.has(key),
  );
  if (!hasUiState) {
    clearDynamicOverlays();
    syncMessagesFromDocument(document);
    return;
  }
  loadUiState(window.location.href, { pushHistory: false });
});

const validatePassword = (value) => {
  const firstFailure = passwordRules.find((rule) => !rule.test(value));
  return firstFailure ? firstFailure.message : "";
};

const showInlineMessage = (message, level = "info") => {
  if (!mainContent) return;

  const stack = getCurrentMessageStack() || (() => {
    const created = document.createElement("div");
    created.className = "message-stack";
    mainContent.prepend(created);
    return created;
  })();

  const notice = document.createElement("div");
  notice.className = `flash-message flash-message--${level} flash-message--floating`;
  notice.textContent = message;
  stack.prepend(notice);

  window.setTimeout(() => {
    notice.remove();
    if (!messageStack && stack.children.length === 0) {
      stack.remove();
    }
  }, 3200);
};

const scheduleFlashDismissal = () => {
  const stack = getCurrentMessageStack();
  if (!stack) return;

  [...stack.querySelectorAll(".flash-message")].forEach((notice, index) => {
    notice.classList.add("flash-message--floating");
    window.setTimeout(() => {
      notice.remove();
      if (stack.children.length === 0) {
        stack.remove();
      }
    }, 2800 + (index * 120));
  });
};

const syncVisibleSpaceItemCount = () => {
  const countLabel = document.querySelector("[data-space-item-count]");
  const itemTarget = document.querySelector("[data-filter-scope='space-items'] [data-filter-target='items']");
  if (!countLabel || !itemTarget) return;

  const count = itemTarget.querySelectorAll(".item-card").length;
  const role = countLabel.dataset.spaceRole || "";
  const itemLabel = count === 1 ? "Item" : "Items";
  countLabel.textContent = role ? `${role} • ${count} ${itemLabel}` : `${count} ${itemLabel}`;
};

const reconcileItemCollectionState = (scope) => {
  if (!scope) return;

  const target = scope.querySelector("[data-filter-target='items']");
  const cards = [...scope.querySelectorAll(".item-card")];
  const baseEmptyState = scope.querySelector(".empty-state--inbox, .empty-state--space");
  const filteredEmptyState = scope.querySelector("[data-filter-empty-state]");

  if (cards.length === 0) {
    filteredEmptyState?.remove();
    target?.remove();
    if (!baseEmptyState) {
      const emptyState = document.createElement("div");
      if (scope.classList.contains("home-inbox-section")) {
        emptyState.className = "empty-state empty-state--inbox";
        emptyState.innerHTML = "<p>Inbox empty</p>";
      } else {
        emptyState.className = "empty-state empty-state--space";
        emptyState.innerHTML = "<p>This space is empty</p>";
      }
      scope.appendChild(emptyState);
    }
    syncVisibleSpaceItemCount();
    return;
  }

  baseEmptyState?.remove();
  applyClientFilters(scope);
  refreshOrderedItemMasonry(scope);
  syncVisibleSpaceItemCount();
};

const normalizeRealtimeItem = (item) => {
  if (!item) return null;
  return {
    id: item.id,
    type: item.type,
    src: item.src || item.imagePath || "",
    content: item.content || "",
    title: item.title || "",
    domain: item.domain || "",
    sourceUrl: item.sourceUrl || "",
    capturedUrl: item.capturedUrl || "",
    externalUrl: item.externalUrl || item.capturedUrl || item.sourceUrl || "",
    pageTitle: item.pageTitle || "",
    addedBy: item.addedBy || item.addedByName || "",
    addedById: item.addedById || "",
  };
};

const canDeleteRealtimeItem = (item) => {
  if (!realtimeSpaceScope || !item) return false;

  const role = String(realtimeSpaceScope.dataset.realtimeSpaceRole || "").toLowerCase();
  if (role === "owner") return true;

  const currentUserId = String(realtimeSpaceScope.dataset.realtimeUserId || "");
  return role === "collaborator" && currentUserId && currentUserId === String(item.addedById || "");
};

const ensureRealtimeItemTarget = () => {
  if (!realtimeSpaceScope) return null;

  let target = realtimeSpaceScope.querySelector("[data-filter-target='items']");
  if (target) return target;

  target = document.createElement("div");
  target.className = "item-masonry";
  target.dataset.filterTarget = "items";
  realtimeSpaceScope.appendChild(target);
  return target;
};

const buildRealtimeItemCard = (rawItem) => {
  const item = normalizeRealtimeItem(rawItem);
  if (!item?.id) return null;

  const article = document.createElement("article");
  article.className = "item-card";
  article.dataset.type = item.type || "text";
  article.dataset.itemId = String(item.id);
  if (item.src) article.dataset.src = item.src;
  if (item.content) article.dataset.content = item.content;
  if (item.title) article.dataset.title = item.title;
  if (item.domain) article.dataset.domain = item.domain;
  if (item.pageTitle) article.dataset.pageTitle = item.pageTitle;
  if (item.addedBy) article.dataset.addedBy = item.addedBy;
  if (item.addedById) article.dataset.addedById = String(item.addedById);
  if (item.externalUrl) article.dataset.externalUrl = item.externalUrl;
  if (canDeleteRealtimeItem(item)) {
    article.dataset.deleteUrl = appendExtensionAuth(`?dialog=delete-item&item=${encodeURIComponent(String(item.id))}`);
  }
  article.tabIndex = 0;

  if (item.type === "image" && item.src) {
    const image = document.createElement("img");
    image.className = "item-image";
    image.src = item.src;
    image.alt = "Saved item";
    image.referrerPolicy = "no-referrer";
    image.draggable = false;
    article.appendChild(image);
    return article;
  }

  if (item.type === "link") {
    const wrapper = document.createElement("div");
    wrapper.className = "item-content square-card item-content--link";
    wrapper.draggable = false;

    const topline = document.createElement("div");
    topline.className = "item-link-topline";
    if (item.externalUrl) {
      const favicon = document.createElement("img");
      favicon.className = "item-link-favicon";
      favicon.src = `https://www.google.com/s2/favicons?sz=128&domain_url=${encodeURIComponent(item.externalUrl)}`;
      favicon.alt = "";
      favicon.referrerPolicy = "no-referrer";
      topline.appendChild(favicon);
    } else {
      const label = document.createElement("span");
      label.className = "small-icon";
      label.textContent = "Link";
      topline.appendChild(label);
    }

    const copy = document.createElement("div");
    copy.className = "item-link-copy";

    const title = document.createElement("h3");
    title.className = "item-title";
    title.textContent = item.title || item.pageTitle || "Saved link";

    const domain = document.createElement("p");
    domain.className = "muted item-domain";
    domain.textContent = item.domain || "";

    copy.append(title, domain);
    wrapper.append(topline, copy);
    article.appendChild(wrapper);
    article.style.setProperty("--item-accent", colorFromDomain(item.domain || item.externalUrl || item.title));
    return article;
  }

  const wrapper = document.createElement("div");
  wrapper.className = "item-content square-card item-content--text";
  wrapper.draggable = false;

  const text = document.createElement("p");
  text.className = "item-text";
  text.textContent = item.content || "";

  wrapper.appendChild(text);
  article.appendChild(wrapper);
  return article;
};

const prependRealtimeItem = (rawItem) => {
  const item = normalizeRealtimeItem(rawItem);
  if (!item?.id || !realtimeSpaceScope) return;

  const existingCard = document.querySelector(`.item-card[data-item-id='${String(item.id)}']`);
  if (existingCard) return;

  const target = ensureRealtimeItemTarget();
  if (!target) return;

  const card = buildRealtimeItemCard(item);
  if (!card) return;

  target.prepend(card);
  reconcileItemCollectionState(realtimeSpaceScope);
};

const removeRealtimeItemCard = (itemId) => {
  if (!realtimeSpaceScope || !itemId) return;

  realtimeSpaceScope.querySelectorAll(`.item-card[data-item-id='${String(itemId)}']`).forEach((card) => card.remove());
  reconcileItemCollectionState(realtimeSpaceScope);
};

const waitForExtensionBridgeAck = (timeoutMs = 1800) => new Promise((resolve) => {
  let settled = false;
  const timer = window.setTimeout(() => {
    if (settled) return;
    settled = true;
    window.removeEventListener("message", onMessage);
    resolve(false);
  }, timeoutMs);

  const onMessage = (event) => {
    if (event.source !== window) return;
    if (event.data?.type !== "SIDEKICK_EXTENSION_CONNECTED") return;
    if (settled) return;
    settled = true;
    window.clearTimeout(timer);
    window.removeEventListener("message", onMessage);
    resolve(true);
  };

  window.addEventListener("message", onMessage);
});

if (connectExtensionForm) {
  connectExtensionForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitButton = connectExtensionForm.querySelector("[data-connect-extension-button]");
    const csrfToken = connectExtensionForm.querySelector('input[name="csrfmiddlewaretoken"]')?.value || "";
    if (!csrfToken) {
      showInlineMessage("Could not prepare extension connection.", "error");
      return;
    }

    submitButton?.setAttribute("disabled", "disabled");
    try {
      const response = await fetch(connectExtensionForm.action, {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": csrfToken,
        },
        credentials: "same-origin",
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok || !payload?.token || !payload?.baseUrl) {
        showInlineMessage(payload?.error?.message || "Extension connection failed.", "error");
        return;
      }

      const ackPromise = waitForExtensionBridgeAck();
      window.postMessage(
        {
          type: "SIDEKICK_CONNECT_EXTENSION",
          payload: {
            token: payload.token,
            baseUrl: payload.baseUrl,
            user: payload.user || null,
          },
        },
        window.location.origin,
      );
      const connected = await ackPromise;
      if (connected) {
        showInlineMessage("Extension connected.", "success");
      } else {
        showInlineMessage("Open the SideKick extension, then press Connect extension again.", "info");
      }
    } catch {
      showInlineMessage("Extension connection failed.", "error");
    } finally {
      submitButton?.removeAttribute("disabled");
    }
  });
}

scheduleFlashDismissal();

document.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-delete-item-form]");
  if (!form) return;

  event.preventDefault();

  const itemId = form.dataset.itemId || form.querySelector('input[name="item_id"]')?.value;
  if (!itemId) {
    showInlineMessage("This item could not be deleted.", "error");
    return;
  }

  const submitButton = form.querySelector('button[type="submit"]');
  const formData = new FormData(form);
  appendAuthToFormData(formData);
  const csrfToken = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || "";

  submitButton?.setAttribute("disabled", "disabled");

  try {
    const response = await fetch(appendExtensionAuth(form.action), {
      method: "POST",
      body: formData,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
      },
      credentials: "same-origin",
    });

    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      showInlineMessage(payload?.error?.message || "This item could not be deleted.", "error");
      submitButton?.removeAttribute("disabled");
      return;
    }

    document.querySelectorAll(`.item-card[data-item-id='${String(itemId)}']`).forEach((card) => card.remove());
    const scope = document.querySelector("[data-filter-scope='space-items'], [data-filter-scope='home-inbox']");
    closeDynamicOverlay(form);
    reconcileItemCollectionState(scope);
    showInlineMessage("Item deleted.", "success");
  } catch {
    showInlineMessage("This item could not be deleted.", "error");
  } finally {
    submitButton?.removeAttribute("disabled");
  }
}, true);

const filterValueMatches = (key, filterValue, card) => {
  if (filterValue === "All") return true;

  if (key === "space-role") {
    const role = (card.dataset.spaceRole || "").toLowerCase();
    if (filterValue === "Owned") return role === "owner";
    if (filterValue === "Shared") return role === "collaborator" || role === "viewer";
  }

  if (key === "item-type") {
    const type = (card.dataset.type || "").toLowerCase();
    if (filterValue === "Images") return type === "image";
    if (filterValue === "Links") return type === "link";
    if (filterValue === "Text") return type === "text";
  }

  if (key === "added-by") {
    return (card.dataset.addedBy || "") === filterValue;
  }

  return true;
};

const applyClientFilters = (scope) => {
  const rows = [...scope.querySelectorAll(".filter-row[data-filter-key]")];
  const target = scope.querySelector("[data-filter-target]");
  if (!target || rows.length === 0) return;

  const cards = [...target.querySelectorAll(".space-card, .item-card")];
  const isItemCollection = cards.some((card) => card.classList.contains("item-card"));
  cards.forEach((card) => {
    const visible = rows.every((row) => {
      const active = row.querySelector(".pill.active");
      const filterValue = active?.dataset.filterValue || "All";
      return filterValueMatches(row.dataset.filterKey, filterValue, card);
    });
    card.hidden = !visible;
  });

  if (!isItemCollection) return;

  const visibleItems = cards.filter((card) => card.classList.contains("item-card") && !card.hidden);
  let emptyState = scope.querySelector("[data-filter-empty-state]");
  if (visibleItems.length > 0) {
    emptyState?.remove();
    ensureOrderedItemMasonry(target);
    return;
  }

  const typeRow = rows.find((row) => row.dataset.filterKey === "item-type");
  const activeType = typeRow?.querySelector(".pill.active")?.dataset.filterValue || "All";
  const message = activeType !== "All"
    ? `No ${activeType.toLowerCase()}`
    : "No items for this filter";

  if (!emptyState) {
    emptyState = document.createElement("div");
    emptyState.className = "empty-state empty-state--filtered";
    emptyState.dataset.filterEmptyState = "true";
    target.insertAdjacentElement("afterend", emptyState);
  }
  emptyState.innerHTML = `<p>${message}</p>`;
  ensureOrderedItemMasonry(target);
};

document.querySelectorAll("[data-filter-scope]").forEach((scope) => {
  const rows = [...scope.querySelectorAll(".filter-row[data-filter-key]")];
  if (rows.length === 0) return;

  rows.forEach((row) => {
    const buttons = [...row.querySelectorAll(".pill[data-filter-value]")];
    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        buttons.forEach((candidate) => candidate.classList.toggle("active", candidate === button));
        applyClientFilters(scope);
      });
    });
  });

  applyClientFilters(scope);
});

applyLinkCardAccents();
refreshOrderedItemMasonry();

window.addEventListener("resize", () => {
  refreshOrderedItemMasonry();
});

const createClientPreviewMarkup = (card) => {
  const type = card.dataset.type || "text";
  const externalUrl = card.dataset.externalUrl || "";
  const escapedExternalUrl = externalUrl.replace(/"/g, "&quot;");
  const faviconUrl = externalUrl
    ? `https://www.google.com/s2/favicons?sz=128&domain_url=${encodeURIComponent(externalUrl)}`
    : "";

  if (type === "image") {
    return `
      <section class="item-preview-card item-preview-card--image" role="dialog" aria-modal="true">
        <button class="button close-button item-preview-close" type="button" data-client-preview-close aria-label="Close preview">×</button>
        <img class="item-preview-image" src="${card.dataset.src || ""}" alt="Saved image" referrerpolicy="no-referrer">
      </section>
    `;
  }

  if (type === "link") {
    return `
      <section class="modal-card item-preview-card" role="dialog" aria-modal="true">
        <button class="button close-button item-preview-close" type="button" data-client-preview-close aria-label="Close preview">×</button>
        <div class="item-preview-body">
          <div class="link-preview-shell">
            <div class="link-preview-content">
              <div class="link-preview-topline">
                ${faviconUrl ? `<img class="link-preview-favicon" src="${faviconUrl}" alt="" referrerpolicy="no-referrer">` : ""}
                <p class="link-preview-domain">${card.dataset.domain || "Saved link"}</p>
              </div>
              <h3 class="link-preview-title">${card.dataset.title || card.dataset.pageTitle || "Saved link"}</h3>
              ${externalUrl ? `<p class="link-preview-url">${externalUrl}</p>` : ""}
              ${externalUrl ? `<div class="modal-actions"><a class="button invite-button" href="${escapedExternalUrl}" target="_blank" rel="noreferrer">Open Link</a></div>` : ""}
            </div>
          </div>
        </div>
      </section>
    `;
  }

  return `
    <section class="modal-card item-preview-card" role="dialog" aria-modal="true">
      <button class="button close-button item-preview-close" type="button" data-client-preview-close aria-label="Close preview">×</button>
      <div class="item-preview-body">
        <div class="item-preview-text">
          <p class="item-preview-quote">${card.dataset.content || ""}</p>
        </div>
      </div>
    </section>
  `;
};

const openClientPreview = (card) => {
  closeClientPreview();
  clientPreviewOverlay = document.createElement("div");
  clientPreviewOverlay.className = "modal-backdrop item-preview-backdrop";
  clientPreviewOverlay.dataset.clientPreview = "true";
  clientPreviewOverlay.innerHTML = createClientPreviewMarkup(card);
  appShell?.appendChild(clientPreviewOverlay);
  document.body.classList.add("modal-scroll-locked");
  clientPreviewOverlay.querySelector("[data-client-preview-close]")?.addEventListener("click", closeClientPreview);
};

if (changePasswordForm && passwordFeedback) {
  changePasswordForm.addEventListener("submit", (event) => {
    const formData = new FormData(changePasswordForm);
    const currentPassword = String(formData.get("current_password") || "");
    const newPassword = String(formData.get("new_password") || "");
    const confirmPassword = String(formData.get("confirm_password") || "");

    if (!currentPassword) {
      event.preventDefault();
      passwordFeedback.textContent = "Enter your current password first.";
      return;
    }

    const passwordIssue = validatePassword(newPassword);
    if (passwordIssue) {
      event.preventDefault();
      passwordFeedback.textContent = passwordIssue;
      return;
    }

    if (newPassword !== confirmPassword) {
      event.preventDefault();
      passwordFeedback.textContent = "New password confirmation does not match.";
      return;
    }

    passwordFeedback.textContent = "";
  });
}

if (dropZone && spaceCaptureSurface) {
  const directUploadEnabled = spaceCaptureSurface.dataset.directUpload === "true";
  const directUploadUrl = spaceCaptureSurface.dataset.saveUrl;
  const directUploadSpaceId = spaceCaptureSurface.dataset.spaceId;
  const csrfField = spaceUploadForm?.querySelector('input[name="csrfmiddlewaretoken"]');
  const csrfToken = csrfField?.value || "";
  let dragDepth = 0;

  const setCaptureState = (isActive) => {
    dropZone.classList.toggle("drag-over", isActive);
    if (spaceCaptureOverlay) {
      spaceCaptureOverlay.hidden = !isActive;
    }
  };

  const isInternalItemDrag = (event) => {
    const types = [...(event.dataTransfer?.types || [])];
    return types.includes("application/x-sidekick-item");
  };

  const dragContainsTransferData = (event) => {
    const types = [...(event.dataTransfer?.types || [])];
    return ["Files", "text/plain", "text/uri-list"].some((type) => types.includes(type));
  };

  const uploadDirectItem = async ({
    itemType = "image",
    file = null,
    imageUrl = "",
    sourceUrl = "",
    contentText = "",
    title = "",
  }) => {
    if (!directUploadEnabled || !directUploadUrl || !directUploadSpaceId || !csrfToken) return false;

    const formData = new FormData();
    appendAuthToFormData(formData);
    formData.append("csrfmiddlewaretoken", csrfToken);
    formData.append("space_id", directUploadSpaceId);
    formData.append("item_type", itemType);
    if (itemType === "image") {
      formData.append("image_title", title);
    }

    if (file && itemType === "image") {
      formData.append("image_file", file, file.name || "pasted-image.png");
    } else if (imageUrl) {
      formData.append("image_source_url", imageUrl);
    } else if (itemType === "link" && sourceUrl) {
      formData.append("source_url", sourceUrl);
    } else if (itemType === "text" && contentText) {
      formData.append("content_text", contentText);
    } else {
      return false;
    }

    setCaptureState(true);
    spaceCaptureSurface.dataset.busy = "true";

    try {
      const response = await fetch(appendExtensionAuth(directUploadUrl), {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
      });
      if (!response.ok) {
        return false;
      }
      const payload = await response.json().catch(() => null);
      if (
        realtimeSpaceScope
        && String(realtimeSpaceScope.dataset.realtimeSpaceId || "") === String(directUploadSpaceId)
      ) {
        if (payload?.item) {
          prependRealtimeItem(payload.item);
        }
        showInlineMessage("Item saved.", "success");
        return true;
      }
      const activeItemFilter = new URL(window.location.href).searchParams.get("item_filter") || "All";
      const typeFilterMap = {
        image: "Images",
        link: "Links",
        text: "Text",
      };
      const createdFilter = typeFilterMap[itemType] || "All";
      if (
        window.location.pathname === "/"
        && activeItemFilter !== "All"
        && activeItemFilter !== createdFilter
      ) {
        const nextUrl = new URL(window.location.href);
        nextUrl.searchParams.delete("item_filter");
        window.location.href = nextUrl.toString();
        return true;
      }
      window.location.reload();
      return true;
    } catch {
      return false;
    } finally {
      setCaptureState(false);
      dragDepth = 0;
      delete spaceCaptureSurface.dataset.busy;
    }
  };

  const getImageUrlFromTransfer = (transfer) => {
    const urlList = transfer?.getData("text/uri-list") || transfer?.getData("text/plain") || "";
    const candidate = urlList.trim().split("\n").find(Boolean) || "";
    if (!candidate) return "";
    if (!/^https?:\/\//i.test(candidate)) return "";
    if (!/\.(png|jpe?g|gif|webp|svg)(\?.*)?$/i.test(candidate)) return "";
    return candidate;
  };

  const isLikelyUrl = (value) => /^https?:\/\//i.test(value.trim()) || /^[\w.-]+\.[A-Za-z]{2,}/.test(value.trim());

  const normalizeUrl = (value) => (/^https?:\/\//i.test(value) ? value : `https://${value}`);

  const getLinkUrlFromTransfer = (transfer) => {
    const uriList = (transfer?.getData("text/uri-list") || "")
      .split(/\r?\n/)
      .map((entry) => entry.trim())
      .find((entry) => entry && !entry.startsWith("#"));
    if (uriList && isLikelyUrl(uriList)) {
      return normalizeUrl(uriList);
    }

    const plainText = transfer?.getData("text/plain") || "";
    const candidates = plainText.match(/https?:\/\/[^\s]+|(?:^|\s)([\w.-]+\.[A-Za-z]{2,}[^\s]*)/g) || [];
    const matched = candidates
      .map((entry) => entry.trim())
      .find((entry) => isLikelyUrl(entry));
    if (matched) {
      return normalizeUrl(matched);
    }

    return "";
  };

  const getLinkTitle = (value) => {
    try {
      return new URL(normalizeUrl(value)).hostname.replace(/^www\./, "");
    } catch {
      return "Saved link";
    }
  };

  const captureTextPayload = async (rawText) => {
    const value = (rawText || "").trim();
    if (!value) return false;

    if (isLikelyUrl(value)) {
      const normalized = normalizeUrl(value);
      return uploadDirectItem({
        itemType: "link",
        sourceUrl: normalized,
      });
    }

    return uploadDirectItem({
      itemType: "text",
      contentText: value,
    });
  };

  const showViewerRestriction = () => {
    showInlineMessage("You cannot add items in this space with viewer access.", "info");
  };

  if (directUploadEnabled) {
    document.addEventListener("dragenter", (event) => {
      if (isInternalItemDrag(event)) return;
      if (!dragContainsTransferData(event)) return;
      event.preventDefault();
      dragDepth += 1;
      setCaptureState(true);
    });

    document.addEventListener("dragover", (event) => {
      if (isInternalItemDrag(event)) return;
      if (!dragContainsTransferData(event)) return;
      event.preventDefault();
      setCaptureState(true);
    });

    document.addEventListener("dragleave", (event) => {
      if (isInternalItemDrag(event)) return;
      if (!dragContainsTransferData(event)) return;
      dragDepth = Math.max(0, dragDepth - 1);
      if (dragDepth === 0) {
        setCaptureState(false);
      }
    });

    document.addEventListener("drop", async (event) => {
      if (isInternalItemDrag(event)) return;
      if (!dragContainsTransferData(event)) return;
      if (event.target?.closest("input, textarea, [contenteditable='true']")) return;
      event.preventDefault();
      dragDepth = 0;
      setCaptureState(false);

      const files = [...(event.dataTransfer?.files || [])];
      const imageFile = files.find((file) => file.type.startsWith("image/"));
      if (imageFile) {
        await uploadDirectItem({ itemType: "image", file: imageFile, title: imageFile.name });
        return;
      }

      const imageUrl = getImageUrlFromTransfer(event.dataTransfer);
      if (imageUrl) {
        const title = imageUrl.split("/").pop()?.split("?")[0] || "Dropped image";
        await uploadDirectItem({ itemType: "image", imageUrl, title });
        return;
      }

      const droppedLink = getLinkUrlFromTransfer(event.dataTransfer);
      if (droppedLink) {
        await uploadDirectItem({
          itemType: "link",
          sourceUrl: droppedLink,
        });
        return;
      }

      const droppedText = (
        event.dataTransfer?.getData("text/plain")
        || ""
      ).trim();
      if (!droppedText) return;

      await captureTextPayload(droppedText);
    });

    document.addEventListener("paste", async (event) => {
      if (event.target?.closest("input, textarea, [contenteditable='true']")) return;
      if (spaceCaptureSurface.dataset.busy === "true") return;

      const clipboardItems = [...(event.clipboardData?.items || [])];
      const imageItem = clipboardItems.find((item) => item.type.startsWith("image/"));
      const blob = imageItem?.getAsFile();
      if (blob) {
        event.preventDefault();
        const extension = blob.type.split("/")[1] || "png";
        const file = new File([blob], `clipboard-image.${extension}`, { type: blob.type });
        await uploadDirectItem({ itemType: "image", file, title: file.name });
        return;
      }

      const pastedText = (event.clipboardData?.getData("text/plain") || "").trim();
      if (!pastedText) return;

      event.preventDefault();
      await captureTextPayload(pastedText);
    });

    document.addEventListener("keydown", async (event) => {
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "v") return;
      if (event.target?.closest("input, textarea, [contenteditable='true']")) return;
      if (spaceCaptureSurface.dataset.busy === "true") return;
      if (!navigator.clipboard?.readText) return;

      try {
        const clipboardText = await navigator.clipboard.readText();
        const trimmedText = clipboardText.trim();
        if (!trimmedText) return;
        event.preventDefault();
        await captureTextPayload(trimmedText);
      } catch {
        // Fall back to the standard paste event if the Clipboard API is unavailable.
      }
    });
  } else {
    document.addEventListener("paste", (event) => {
      if (event.target?.closest("input, textarea, [contenteditable='true']")) return;

      const clipboardItems = [...(event.clipboardData?.items || [])];
      const pastedText = (event.clipboardData?.getData("text/plain") || "").trim();
      const hasImage = clipboardItems.some((item) => item.type.startsWith("image/"));
      if (!hasImage && !pastedText) return;

      event.preventDefault();
      showViewerRestriction();
    });

    document.addEventListener("drop", (event) => {
      if (isInternalItemDrag(event)) return;
      if (!dragContainsTransferData(event)) return;
      if (event.target?.closest("input, textarea, [contenteditable='true']")) return;
      event.preventDefault();
      showViewerRestriction();
    });

    document.addEventListener("keydown", async (event) => {
      if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "v") return;
      if (event.target?.closest("input, textarea, [contenteditable='true']")) return;
      showViewerRestriction();
    });
  }
}

if (draggableItemCards.length > 0 && spaceDropTargets.length > 0 && spaceUploadForm) {
  const csrfField = spaceUploadForm.querySelector('input[name="csrfmiddlewaretoken"]');
  const csrfToken = csrfField?.value || "";
  const moveItemUrl = spaceCaptureSurface?.dataset.moveUrl || "";
  const inboxSection = document.querySelector(".home-inbox-section");
  const inboxItemsTarget = inboxSection?.querySelector("[data-filter-target='items']");
  const DRAG_THRESHOLD = 8;
  let dragState = null;
  let suppressClickUntil = 0;

  const clearDropTargets = () => {
    spaceDropTargets.forEach((target) => target.classList.remove("drag-target"));
    spaceCards.forEach((card) => card.classList.remove("drag-invalid"));
    if (dragState) {
      dragState.invalidTarget = null;
    }
  };

  const moveItemToSpace = async (itemId, targetSpaceId) => {
    if (!csrfToken || !moveItemUrl) return false;

    const formData = new FormData();
    appendAuthToFormData(formData);
    formData.append("csrfmiddlewaretoken", csrfToken);
    formData.append("item_id", itemId);
    formData.append("target_space_id", targetSpaceId);

    const response = await fetch(appendExtensionAuth(moveItemUrl), {
      method: "POST",
      body: formData,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
    });

    if (!response.ok) {
      showInlineMessage("This item could not be moved into that space.", "error");
      return false;
    }

    return true;
  };

  const ensureInboxEmptyState = () => {
    if (!inboxSection || !inboxItemsTarget) return;
    const visibleItems = inboxItemsTarget.querySelectorAll(".item-card");
    if (visibleItems.length > 0) return;
    if (inboxSection.querySelector(".empty-state--inbox")) return;

    const emptyState = document.createElement("div");
    emptyState.className = "empty-state empty-state--inbox";
    emptyState.innerHTML = "<p>Inbox empty</p>";
    inboxItemsTarget.remove();
    inboxSection.appendChild(emptyState);
  };

  const clearDragState = () => {
    if (!dragState) return;
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
    window.removeEventListener("pointercancel", onPointerCancel);
    dragState.card.classList.remove("is-dragging");
    dragState.card.style.removeProperty("pointer-events");
    dragState.ghost?.remove();
    document.body.classList.remove("is-sorting-items");
    spaceCards.forEach((card) => card.classList.remove("drag-disabled"));
    clearDropTargets();
    dragState = null;
  };

  const updatePointerTarget = (clientX, clientY) => {
    const element = document.elementFromPoint(clientX, clientY);
    const hoveredSpaceCard = element?.closest(".space-card") || null;
    const nextTarget = hoveredSpaceCard?.matches("[data-drop-space-id]") ? hoveredSpaceCard : null;
    const nextInvalidTarget = hoveredSpaceCard?.matches("[data-drop-disabled='true']") ? hoveredSpaceCard : null;
    if (dragState?.target === nextTarget && dragState?.invalidTarget === nextInvalidTarget) return;
    clearDropTargets();
    if (dragState) {
      dragState.target = nextTarget;
      dragState.invalidTarget = nextInvalidTarget;
    }
    nextTarget?.classList.add("drag-target");
    nextInvalidTarget?.classList.add("drag-invalid");
  };

  const positionGhost = (clientX, clientY) => {
    if (!dragState?.ghost) return;
    dragState.ghost.style.transform = `translate3d(${clientX - dragState.offsetX}px, ${clientY - dragState.offsetY}px, 0)`;
  };

  function beginCustomDrag(clientX, clientY) {
    if (!dragState || dragState.started) return;
    dragState.started = true;
    dragState.card.classList.add("is-dragging");
    dragState.card.style.pointerEvents = "none";
    document.body.classList.add("is-sorting-items");
    spaceCards.forEach((card) => {
      if (!card.matches("[data-drop-space-id]")) {
        card.classList.add("drag-disabled");
      }
    });

    const ghost = dragState.card.cloneNode(true);
    ghost.classList.add("item-drag-ghost");
    ghost.classList.remove("is-dragging");
    ghost.removeAttribute("tabindex");
    ghost.style.width = `${dragState.rect.width}px`;
    ghost.style.height = `${dragState.rect.height}px`;
    appShell?.appendChild(ghost);
    dragState.ghost = ghost;

    positionGhost(clientX, clientY);
    updatePointerTarget(clientX, clientY);
  }

  function onPointerMove(event) {
    if (!dragState || event.pointerId !== dragState.pointerId) return;
    dragState.lastX = event.clientX;
    dragState.lastY = event.clientY;

    if (!dragState.started) {
      const deltaX = event.clientX - dragState.startX;
      const deltaY = event.clientY - dragState.startY;
      if (Math.hypot(deltaX, deltaY) < DRAG_THRESHOLD) return;
      beginCustomDrag(event.clientX, event.clientY);
    }

    event.preventDefault();
    positionGhost(event.clientX, event.clientY);
    updatePointerTarget(event.clientX, event.clientY);
  }

  async function onPointerUp(event) {
    if (!dragState || event.pointerId !== dragState.pointerId) return;

    const currentDrag = dragState;
    const started = currentDrag.started;
    const targetSpaceId = currentDrag.target?.dataset.dropSpaceId;
    const itemId = currentDrag.card.dataset.itemId;
    const invalidTarget = currentDrag.invalidTarget;

    if (!started) {
      clearDragState();
      return;
    }

    suppressClickUntil = window.performance.now() + 400;
    clearDragState();

    if (invalidTarget) {
      showInlineMessage("You cannot move inbox items into spaces where you only have viewer access. Only owners or collaborators can add items.", "info");
      return;
    }
    if (invalidTarget) return;
    if (!itemId || !targetSpaceId) return;

    const moved = await moveItemToSpace(itemId, targetSpaceId);
    if (!moved) return;

    currentDrag.card.remove();
    ensureInboxEmptyState();
  }

  function onPointerCancel(event) {
    if (!dragState || event.pointerId !== dragState.pointerId) return;
    clearDragState();
  }

  draggableItemCards.forEach((card) => {
    card.addEventListener("dragstart", (event) => {
      event.preventDefault();
    });

    card.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      if (event.target.closest("a, button, input, textarea, select")) return;
      event.preventDefault();
      if (dragState) {
        clearDragState();
      }

      const rect = card.getBoundingClientRect();
      dragState = {
        card,
        rect,
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        lastX: event.clientX,
        lastY: event.clientY,
        offsetX: event.clientX - rect.left,
        offsetY: event.clientY - rect.top,
        started: false,
        target: null,
        invalidTarget: null,
        ghost: null,
      };

      card.setPointerCapture?.(event.pointerId);
      window.addEventListener("pointermove", onPointerMove);
      window.addEventListener("pointerup", onPointerUp);
      window.addEventListener("pointercancel", onPointerCancel);
    });

    card.addEventListener("click", (event) => {
      if (window.performance.now() > suppressClickUntil) return;
      event.preventDefault();
      event.stopPropagation();
    }, true);
  });
}

function initializeItemForm(itemForm) {
  if (!itemForm || itemForm.dataset.initialized === "true") return;
  itemForm.dataset.initialized = "true";

  const captureField = itemForm.querySelector("[data-item-capture-field]");
  const capturePanel = itemForm.querySelector("[data-capture-panel]");
  const uploadState = itemForm.querySelector("[data-upload-state]");
  const uploadFilename = itemForm.querySelector("[data-upload-filename]");
  const uploadPreviewImage = itemForm.querySelector("[data-upload-preview-image]");
  const uploadTrigger = itemForm.querySelector("[data-upload-trigger]");
  const fileInput = itemForm.querySelector("[data-image-file-input]");
  const itemTypeHidden = itemForm.querySelector("[data-item-type-hidden]");
  const contentHidden = itemForm.querySelector("[data-content-hidden]");
  const sourceHidden = itemForm.querySelector("[data-source-hidden]");
  const linkTitleHidden = itemForm.querySelector("[data-link-title-hidden]");
  const formFeedback = itemForm.querySelector("[data-item-form-feedback]");
  const captureStatus = itemForm.querySelector("[data-capture-status]");
  const captureStatusLabel = itemForm.querySelector("[data-capture-status-label]");
  let captureMode = "text";

  const isLikelyUrl = (value) => /^https?:\/\//i.test(value.trim()) || /^[\w.-]+\.[A-Za-z]{2,}/.test(value.trim());
  const normalizeUrl = (value) => (/^https?:\/\//i.test(value) ? value : `https://${value}`);

  const setCaptureMode = (mode) => {
    captureMode = mode;
    capturePanel?.setAttribute("data-capture-mode", mode);
    if (captureField) {
      captureField.hidden = mode === "image";
      captureField.placeholder = mode === "link"
        ? "Paste a link"
        : "Start typing, paste text, or press Ctrl+V.";
    }
    if (uploadState) {
      uploadState.hidden = mode !== "image";
    }
    if (captureStatus) {
      captureStatus.textContent = mode === "image" ? "Image" : mode === "link" ? "Link" : "Text";
    }
    if (captureStatusLabel) {
      captureStatusLabel.textContent = mode === "image" ? "image" : mode === "link" ? "link" : "text";
    }
  };

  const clearImageSelection = () => {
    if (fileInput) {
      fileInput.value = "";
    }
    if (uploadPreviewImage) {
      uploadPreviewImage.removeAttribute("src");
    }
    if (uploadFilename) {
      uploadFilename.textContent = "No file chosen";
    }
  };

  const setSelectedFile = (file) => {
    if (!file || !fileInput) return;
    try {
      const transfer = new DataTransfer();
      transfer.items.add(file);
      fileInput.files = transfer.files;
    } catch {
      // Ignore assignment failures and rely on the existing file input state.
    }
    if (uploadFilename) {
      uploadFilename.textContent = file.name || "Pasted image";
    }
    if (uploadPreviewImage) {
      const previewUrl = URL.createObjectURL(file);
      uploadPreviewImage.src = previewUrl;
      uploadPreviewImage.onload = () => URL.revokeObjectURL(previewUrl);
    }
    if (captureField) {
      captureField.value = "";
    }
    setCaptureMode("image");
    if (formFeedback) {
      formFeedback.textContent = "";
    }
  };

  const syncModeFromText = (rawValue) => {
    const value = (rawValue || "").trim();
    if (!value) {
      setCaptureMode("text");
      return;
    }
    setCaptureMode(!/\s/.test(value) && isLikelyUrl(value) ? "link" : "text");
  };

  uploadTrigger?.addEventListener("click", () => {
    fileInput?.click();
  });

  captureField?.addEventListener("focus", () => {
    if (captureMode === "image") {
      clearImageSelection();
      setCaptureMode("text");
    }
  });

  captureField?.addEventListener("input", () => {
    clearImageSelection();
    syncModeFromText(captureField.value);
    if (formFeedback) {
      formFeedback.textContent = "";
    }
  });

  const handleClipboardImage = (event) => {
    const clipboardItems = [...(event.clipboardData?.items || [])];
    const imageItem = clipboardItems.find((item) => item.type.startsWith("image/"));
    const blob = imageItem?.getAsFile();
    if (!blob) return false;
    event.preventDefault();
    const extension = blob.type.split("/")[1] || "png";
    const file = new File([blob], `clipboard-image.${extension}`, { type: blob.type });
    setSelectedFile(file);
    return true;
  };

  captureField?.addEventListener("paste", (event) => {
    if (handleClipboardImage(event)) return;

    const pastedText = (event.clipboardData?.getData("text/plain") || "").trim();
    if (!pastedText) return;
    if (!/\s/.test(pastedText) && isLikelyUrl(pastedText)) {
      event.preventDefault();
      clearImageSelection();
      captureField.value = normalizeUrl(pastedText);
      setCaptureMode("link");
      if (formFeedback) {
        formFeedback.textContent = "";
      }
      return;
    }
    requestAnimationFrame(() => syncModeFromText(captureField.value));
  });

  itemForm.addEventListener("paste", (event) => {
    if (event.target === captureField) return;
    handleClipboardImage(event);
  });

  fileInput?.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    setSelectedFile(file);
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    itemForm.addEventListener(eventName, (event) => {
      if (!event.dataTransfer?.types?.includes("Files")) return;
      event.preventDefault();
      itemForm.classList.add("drag-over");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    itemForm.addEventListener(eventName, (event) => {
      if (eventName === "dragleave" && itemForm.contains(event.relatedTarget)) return;
      event.preventDefault();
      itemForm.classList.remove("drag-over");
    });
  });

  itemForm.addEventListener("drop", (event) => {
    const file = [...(event.dataTransfer?.files || [])].find((candidate) => candidate.type.startsWith("image/"));
    if (!file) return;
    setSelectedFile(file);
  });

  itemForm.addEventListener("submit", (event) => {
    const captureValue = (captureField?.value || "").trim();
    itemTypeHidden.value = "text";
    contentHidden.value = "";
    sourceHidden.value = "";
    linkTitleHidden.value = "";

    if (captureMode === "image") {
      if (!fileInput?.files?.length) {
        event.preventDefault();
        if (formFeedback) {
          formFeedback.textContent = "Choose an image to upload first.";
        }
        return;
      }
      itemTypeHidden.value = "image";
      return;
    }

    if (!captureValue) {
      event.preventDefault();
      if (formFeedback) {
        formFeedback.textContent = "Paste a link, upload an image, or enter text first.";
      }
      return;
    }

    if (captureMode === "link") {
      itemTypeHidden.value = "link";
      sourceHidden.value = normalizeUrl(captureValue);
      linkTitleHidden.value = "";
      return;
    }

    itemTypeHidden.value = "text";
    contentHidden.value = captureValue;
  });

  setCaptureMode("text");
  captureField?.focus();
}

function initializeDynamicForms(rootNode = document) {
  rootNode.querySelectorAll("[data-item-form]").forEach(initializeItemForm);
}

initializeDynamicForms(document);

if (previewableItemCards.length > 0) {
  const openItemPreview = (card) => {
    if (card.dataset.type === "link" && card.dataset.externalUrl) {
      window.open(card.dataset.externalUrl, "_blank", "noopener,noreferrer");
      return;
    }
    openClientPreview(card);
  };

  previewableItemCards.forEach((card) => {
    card.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      openItemPreview(card);
    });

    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        event.stopPropagation();
        openItemPreview(card);
      }
    });
  });
}

const dismissibleBackdrops = [...document.querySelectorAll("[data-modal-backdrop][data-close-url]")];

if (dismissibleBackdrops.length > 0) {
  dismissibleBackdrops.forEach((backdrop) => {
    backdrop.addEventListener("click", (event) => {
      if (event.target !== backdrop) return;
      closeDynamicOverlay(backdrop);
    });
  });
}

if (itemContextMenu && itemContextAction && (itemCardsWithMenu.length > 0 || memberRowsWithMenu.length > 0)) {
  const hideItemContextMenu = () => {
    itemContextMenu.hidden = true;
  };

  const showItemContextMenu = (event, actionUrl, actionLabel) => {
    itemContextAction.href = actionUrl;
    itemContextAction.textContent = actionLabel;
    itemContextMenu.hidden = false;

    const menuWidth = 168;
    const menuHeight = 52;
    const x = Math.min(event.clientX, window.innerWidth - menuWidth - 12);
    const y = Math.min(event.clientY, window.innerHeight - menuHeight - 12);

    itemContextMenu.style.left = `${Math.max(12, x)}px`;
    itemContextMenu.style.top = `${Math.max(12, y)}px`;
  };

  itemCardsWithMenu.forEach((card) => {
    card.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const deleteUrl = card.dataset.deleteUrl;
      if (!deleteUrl) return;
      showItemContextMenu(event, deleteUrl, "Delete item");
    });
  });

  memberRowsWithMenu.forEach((row) => {
    row.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const removeUrl = row.dataset.memberRemoveUrl;
      if (!removeUrl) return;
      showItemContextMenu(event, removeUrl, "Remove person");
    });
  });

  document.addEventListener("click", (event) => {
    if (!itemContextMenu.contains(event.target)) {
      hideItemContextMenu();
    }
  });

  itemContextAction.addEventListener("click", () => {
    hideItemContextMenu();
  });

  window.addEventListener("scroll", hideItemContextMenu, true);
  window.addEventListener("resize", hideItemContextMenu);
}

const openDynamicItemPreview = (card) => {
  if (!card) return;
  if (card.dataset.type === "link" && card.dataset.externalUrl) {
    window.open(card.dataset.externalUrl, "_blank", "noopener,noreferrer");
    return;
  }
  openClientPreview(card);
};

document.addEventListener("click", (event) => {
  const card = event.target.closest(".item-card[data-item-id]");
  if (!card || previewableItemCards.includes(card)) return;
  if (event.defaultPrevented) return;
  if (event.target.closest("a, button, input, textarea, select")) return;

  event.preventDefault();
  event.stopPropagation();
  openDynamicItemPreview(card);
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;

  const card = event.target.closest(".item-card[data-item-id]");
  if (!card || previewableItemCards.includes(card)) return;

  event.preventDefault();
  event.stopPropagation();
  openDynamicItemPreview(card);
});

document.addEventListener("contextmenu", (event) => {
  if (!itemContextMenu || !itemContextAction) return;

  const card = event.target.closest(".item-card[data-item-id]");
  if (!card || itemCardsWithMenu.includes(card)) return;

  const deleteUrl = card.dataset.deleteUrl;
  if (!deleteUrl) return;

  event.preventDefault();
  event.stopPropagation();
  itemContextAction.href = deleteUrl;
  itemContextAction.textContent = "Delete item";
  itemContextMenu.hidden = false;

  const menuWidth = 168;
  const menuHeight = 52;
  const x = Math.min(event.clientX, window.innerWidth - menuWidth - 12);
  const y = Math.min(event.clientY, window.innerHeight - menuHeight - 12);

  itemContextMenu.style.left = `${Math.max(12, x)}px`;
  itemContextMenu.style.top = `${Math.max(12, y)}px`;
});

// Realtime subscriptions run for the active live-updated collection and share the same behavior across views.
if (realtimeSpaceScope && typeof window.io === "function") {
  const realtimeSpaceId = Number(realtimeSpaceScope.dataset.realtimeSpaceId || 0);
  if (realtimeSpaceId) {
    let realtimeWarningShown = false;
    const authToken = getExtensionAuthToken();
    const socket = window.io({
      auth: authToken ? { authToken } : undefined,
    });

    const showRealtimeWarning = (message = "Live updates are temporarily unavailable.") => {
      if (realtimeWarningShown) return;
      realtimeWarningShown = true;
      showInlineMessage(message, "info");
    };

    const joinRealtimeSpace = () => {
      socket.timeout(5000).emit("space:join", { spaceId: realtimeSpaceId }, (error, response) => {
        if (error || !response?.ok) {
          showRealtimeWarning("Live updates could not join this space.");
        }
      });
    };

    socket.on("connect", () => {
      realtimeWarningShown = false;
      joinRealtimeSpace();
    });

    socket.on("connect_error", () => {
      showRealtimeWarning();
    });

    socket.on("error", () => {
      showRealtimeWarning();
    });

    socket.on("space:item_created", (payload) => {
      if (Number(payload?.spaceId || 0) !== realtimeSpaceId) return;
      prependRealtimeItem(payload?.item);
    });

    socket.on("space:item_removed", (payload) => {
      if (Number(payload?.spaceId || 0) !== realtimeSpaceId) return;
      removeRealtimeItemCard(payload?.itemId);
    });

    window.addEventListener("beforeunload", () => {
      socket.disconnect();
    });
  }
}

