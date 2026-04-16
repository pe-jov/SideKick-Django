// Author Petar Jovanovic
const root = document.documentElement;
const toggle = document.querySelector("[data-theme-toggle]");

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
