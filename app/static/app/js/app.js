// Author Petar Jovanovic
const root = document.documentElement;
const toggle = document.querySelector("[data-theme-toggle]");
const mockAuthKey = "sidekick-mock-auth";
const registeredEmailKey = "sidekick-mock-registered-emails";

const loginLink = document.querySelector("[data-login-link]");
const registerLink = document.querySelector("[data-register-link]");
const logoutButton = document.querySelector("[data-logout-button]");
const appTitle = document.querySelector("[data-app-title]");
const loginForm = document.querySelector("[data-mock-login-form]");
const loginFeedback = document.querySelector("[data-mock-login-feedback]");
const changePasswordForm = document.querySelector("[data-change-password-form]");
const passwordFeedback = document.querySelector("[data-password-feedback]");
const dropZone = document.querySelector("[data-drop-zone]");

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
  if (modal && closeLink) {
    window.location.href = closeLink.href;
  }
});

const readMockAuth = () => {
  try {
    return JSON.parse(localStorage.getItem(mockAuthKey) || "null");
  } catch {
    return null;
  }
};

const readRegisteredEmails = () => {
  try {
    return JSON.parse(localStorage.getItem(registeredEmailKey) || '["demo@sidekick.app"]');
  } catch {
    return ["demo@sidekick.app"];
  }
};

const writeRegisteredEmails = (emails) => {
  localStorage.setItem(registeredEmailKey, JSON.stringify(emails));
};

const validatePassword = (value) => {
  const firstFailure = passwordRules.find((rule) => !rule.test(value));
  return firstFailure ? firstFailure.message : "";
};

const syncMockAuthUi = () => {
  const mockAuth = readMockAuth();
  const signedIn = Boolean(mockAuth?.signedIn);

  if (loginLink) {
    loginLink.hidden = signedIn;
    loginLink.textContent = "Login";
  }

  if (registerLink) {
    registerLink.hidden = signedIn;
  }

  if (logoutButton) {
    logoutButton.hidden = !signedIn;
  }

  if (appTitle) {
    appTitle.textContent = signedIn ? "SIDEKICK" : "DEMO APP";
  }
};

syncMockAuthUi();

if (logoutButton) {
  logoutButton.addEventListener("click", () => {
    localStorage.removeItem(mockAuthKey);
    syncMockAuthUi();
  });
}

if (loginForm) {
  loginForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const formData = new FormData(loginForm);
    const email = String(formData.get("email") || "demo@sidekick.app").trim().toLowerCase();
    const name = String(formData.get("name") || "Demo User");
    const password = String(formData.get("password") || "");
    const confirmPassword = String(formData.get("confirm_password") || "");
    const isRegisterFlow = loginForm.querySelector('[name="confirm_password"]') !== null;

    if (isRegisterFlow) {
      const existingEmails = readRegisteredEmails();
      if (existingEmails.includes(email)) {
        if (loginFeedback) {
          loginFeedback.textContent = "That email is already registered. Try logging in instead.";
        }
        return;
      }

      const passwordIssue = validatePassword(password);
      if (passwordIssue) {
        if (loginFeedback) {
          loginFeedback.textContent = passwordIssue;
        }
        return;
      }

      if (password !== confirmPassword) {
        if (loginFeedback) {
          loginFeedback.textContent = "Passwords need to match before you can continue.";
        }
        return;
      }

      writeRegisteredEmails([...existingEmails, email]);
    }

    localStorage.setItem(
      mockAuthKey,
      JSON.stringify({
        signedIn: true,
        email,
        name,
      })
    );
    syncMockAuthUi();

    if (loginFeedback) {
      loginFeedback.textContent = "Preview sign-in complete.";
    }

    const closeUrl = loginForm.dataset.closeUrl;
    window.setTimeout(() => {
      if (closeUrl) {
        window.location.href = closeUrl;
      }
    }, 400);
  });
}

if (changePasswordForm && passwordFeedback) {
  changePasswordForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const formData = new FormData(changePasswordForm);
    const currentPassword = String(formData.get("current_password") || "");
    const newPassword = String(formData.get("new_password") || "");
    const confirmPassword = String(formData.get("confirm_password") || "");

    if (!currentPassword) {
      passwordFeedback.textContent = "Enter your current password first.";
      return;
    }

    const passwordIssue = validatePassword(newPassword);
    if (passwordIssue) {
      passwordFeedback.textContent = passwordIssue;
      return;
    }

    if (newPassword !== confirmPassword) {
      passwordFeedback.textContent = "New password confirmation does not match.";
      return;
    }

    passwordFeedback.textContent = "Password updated for the prototype flow.";
  });
}

if (dropZone) {
  ["dragenter", "dragover"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropZone.classList.add("drag-over");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropZone.classList.remove("drag-over");
    });
  });
}
