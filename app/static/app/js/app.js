// Author Petar Jovanovic
const root = document.documentElement;
const toggle = document.querySelector("[data-theme-toggle]");
const changePasswordForm = document.querySelector("[data-change-password-form]");
const passwordFeedback = document.querySelector("[data-password-feedback]");
const spaceCaptureSurface = document.querySelector("[data-space-capture-surface]");
const spaceCaptureOverlay = document.querySelector("[data-space-capture-overlay]");
const dropZone = document.querySelector("[data-drop-zone]");
const spaceUploadForm = document.querySelector("[data-space-upload-form]");
const itemForm = document.querySelector("[data-item-form]");
const itemTypeSelect = document.querySelector("[data-item-type-select]");
const quickCaptureField = document.querySelector("[data-quick-capture]");
const imageFileInput = document.querySelector("[data-image-file-input]");
const itemContextMenu = document.querySelector("[data-item-context-menu]");
const itemContextAction = document.querySelector("[data-item-context-action]");
const itemCardsWithMenu = [...document.querySelectorAll(".item-card[data-delete-url]")];
const previewableItemCards = [...document.querySelectorAll(".item-card[data-preview-url]")];

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

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const modal = document.querySelector("[data-modal-backdrop]");
  const closeLink = document.querySelector(".close-button");
  if (itemContextMenu) {
    itemContextMenu.hidden = true;
  }
  if (modal && closeLink) {
    window.location.href = closeLink.href;
  }
});

const validatePassword = (value) => {
  const firstFailure = passwordRules.find((rule) => !rule.test(value));
  return firstFailure ? firstFailure.message : "";
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
    formData.append("csrfmiddlewaretoken", csrfToken);
    formData.append("space_id", directUploadSpaceId);
    formData.append("item_type", itemType);
    if (itemType === "image") {
      formData.append("image_title", title);
    } else if (itemType === "link") {
      formData.append("link_title", title);
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
      const response = await fetch(directUploadUrl, {
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
        title: getLinkTitle(normalized),
      });
    }

    return uploadDirectItem({
      itemType: "text",
      contentText: value,
    });
  };

  if (directUploadEnabled) {
    document.addEventListener("dragenter", (event) => {
      if (!dragContainsTransferData(event)) return;
      event.preventDefault();
      dragDepth += 1;
      setCaptureState(true);
    });

    document.addEventListener("dragover", (event) => {
      if (!dragContainsTransferData(event)) return;
      event.preventDefault();
      setCaptureState(true);
    });

    document.addEventListener("dragleave", (event) => {
      if (!dragContainsTransferData(event)) return;
      dragDepth = Math.max(0, dragDepth - 1);
      if (dragDepth === 0) {
        setCaptureState(false);
      }
    });

    document.addEventListener("drop", async (event) => {
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

      const droppedText = (
        event.dataTransfer?.getData("text/plain")
        || event.dataTransfer?.getData("text/uri-list")
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
  }
}

if (itemForm && itemTypeSelect) {
  const itemFieldGroups = [...itemForm.querySelectorAll("[data-item-fields]")];
  const textField = itemForm.querySelector('[name="content_text"]');
  const linkField = itemForm.querySelector('[name="source_url"]');
  const linkTitleField = itemForm.querySelector('[name="link_title"]');
  const imageUrlField = itemForm.querySelector('[name="image_source_url"]');
  const imageTitleField = itemForm.querySelector('[name="image_title"]');

  const syncItemFields = () => {
    const selectedType = itemTypeSelect.value;
    itemFieldGroups.forEach((group) => {
      group.hidden = group.dataset.itemFields !== selectedType;
    });
  };

  const isLikelyUrl = (value) => /^https?:\/\//i.test(value.trim()) || /^[\w.-]+\.[A-Za-z]{2,}/.test(value.trim());

  const fillFromCapture = (rawValue) => {
    const value = rawValue.trim();
    if (!value) return;

    if (isLikelyUrl(value)) {
      const normalized = /^https?:\/\//i.test(value) ? value : `https://${value}`;
      if (/\.(png|jpe?g|gif|webp|svg)(\?.*)?$/i.test(normalized)) {
        itemTypeSelect.value = "image";
        syncItemFields();
        if (imageUrlField) imageUrlField.value = normalized;
        if (imageTitleField && !imageTitleField.value) {
          imageTitleField.value = normalized.split("/").pop()?.split("?")[0] || "";
        }
        return;
      }
      itemTypeSelect.value = "link";
      syncItemFields();
      if (linkField) linkField.value = normalized;
      if (linkTitleField && !linkTitleField.value) {
        try {
          const { hostname } = new URL(normalized);
          linkTitleField.value = hostname.replace(/^www\./, "");
        } catch {
          linkTitleField.value = "";
        }
      }
      return;
    }

    itemTypeSelect.value = "text";
    syncItemFields();
    if (textField) textField.value = value;
  };

  itemTypeSelect.addEventListener("change", syncItemFields);

  if (quickCaptureField) {
    quickCaptureField.addEventListener("paste", (event) => {
      const pasted = event.clipboardData?.getData("text");
      if (pasted) {
        requestAnimationFrame(() => fillFromCapture(pasted));
      }
    });

    quickCaptureField.addEventListener("blur", () => {
      if (quickCaptureField.value.trim()) {
        fillFromCapture(quickCaptureField.value);
      }
    });
  }

  if (imageFileInput) {
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
      const files = event.dataTransfer?.files;
      if (!files || files.length === 0) return;
      imageFileInput.files = files;
      itemTypeSelect.value = "image";
      syncItemFields();
    });
  }

  syncItemFields();
}

if (previewableItemCards.length > 0) {
  const openItemPreview = (card) => {
    const previewUrl = card.dataset.previewUrl;
    if (previewUrl) {
      window.location.href = previewUrl;
    }
  };

  previewableItemCards.forEach((card) => {
    card.addEventListener("click", () => {
      openItemPreview(card);
    });

    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
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
      const closeUrl = backdrop.dataset.closeUrl;
      if (closeUrl) {
        window.location.href = closeUrl;
      }
    });
  });
}

if (itemContextMenu && itemContextAction && itemCardsWithMenu.length > 0) {
  const hideItemContextMenu = () => {
    itemContextMenu.hidden = true;
  };

  const showItemContextMenu = (event, deleteUrl) => {
    itemContextAction.href = deleteUrl;
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
      showItemContextMenu(event, deleteUrl);
    });
  });

  document.addEventListener("click", (event) => {
    if (!itemContextMenu.contains(event.target)) {
      hideItemContextMenu();
    }
  });

  window.addEventListener("scroll", hideItemContextMenu, true);
  window.addEventListener("resize", hideItemContextMenu);
}
