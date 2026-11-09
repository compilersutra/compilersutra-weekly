(function () {
  var KEY = "csw-theme";
  function preferred() {
    try {
      var saved = localStorage.getItem(KEY);
      if (saved === "light" || saved === "dark") return saved;
    } catch (e) {}
    return window.matchMedia("(prefers-color-scheme: light)").matches
      ? "light"
      : "dark";
  }
  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    var btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.setAttribute("aria-pressed", theme === "light" ? "true" : "false");
      btn.textContent = theme === "light" ? "Dark" : "Light";
      btn.setAttribute(
        "aria-label",
        theme === "light" ? "Switch to dark theme" : "Switch to light theme"
      );
      btn.title = btn.getAttribute("aria-label") || "Theme";
    }
  }
  apply(preferred());
  document.addEventListener("DOMContentLoaded", function () {
    apply(preferred());
    var btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.addEventListener("click", function () {
        var next =
          document.documentElement.getAttribute("data-theme") === "light"
            ? "dark"
            : "light";
        try {
          localStorage.setItem(KEY, next);
        } catch (e) {}
        apply(next);
      });
    }
    var toggle = document.getElementById("nav-toggle");
    var panel = document.getElementById("mobile-nav");
    if (toggle && panel) {
      toggle.addEventListener("click", function () {
        var open = panel.hasAttribute("hidden");
        if (open) {
          panel.removeAttribute("hidden");
          panel.classList.add("open");
        } else {
          panel.setAttribute("hidden", "");
          panel.classList.remove("open");
        }
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }
  });
})();
