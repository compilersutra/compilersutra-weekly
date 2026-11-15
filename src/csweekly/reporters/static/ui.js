(function () {
  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function isMac() {
    return /Mac|iPhone|iPad|iPod/.test(navigator.platform || "");
  }

  function readingProgress() {
    var bar = document.getElementById("read-progress");
    var article = document.querySelector(".issue-article, .article-narrow, main");
    if (!bar || !article) return;
    bar.hidden = false;
    function update() {
      var rect = article.getBoundingClientRect();
      var total = article.scrollHeight - window.innerHeight;
      var scrolled = Math.min(Math.max(-rect.top, 0), Math.max(total, 1));
      var pct = total > 0 ? (scrolled / total) * 100 : 0;
      bar.style.width = pct.toFixed(2) + "%";
    }
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
  }

  function copyCodeButtons() {
    var blocks = document.querySelectorAll(".article pre, .code-panel, pre.code-block");
    blocks.forEach(function (pre) {
      if (pre.closest(".code-wrap")) return;
      var wrap = document.createElement("div");
      wrap.className = "code-wrap";
      pre.parentNode.insertBefore(wrap, pre);
      wrap.appendChild(pre);
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "copy-code";
      btn.textContent = "Copy";
      btn.setAttribute("aria-label", "Copy code");
      btn.addEventListener("click", function () {
        var text = pre.innerText || pre.textContent || "";
        function done() {
          btn.textContent = "Copied";
          setTimeout(function () {
            btn.textContent = "Copy";
          }, 1400);
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done).catch(function () {
            btn.textContent = "Failed";
          });
        } else {
          done();
        }
      });
      wrap.appendChild(btn);
    });
  }

  function tocActive() {
    var links = Array.prototype.slice.call(
      document.querySelectorAll('.toc a[href^="#"]')
    );
    if (!links.length) return;
    var map = {};
    links.forEach(function (a) {
      var id = decodeURIComponent(a.getAttribute("href").slice(1));
      var el = document.getElementById(id);
      if (el) map[id] = a;
    });
    var ids = Object.keys(map);
    if (!ids.length) return;
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          links.forEach(function (a) {
            a.classList.remove("is-active");
          });
          var a = map[entry.target.id];
          if (a) a.classList.add("is-active");
        });
      },
      { rootMargin: "-20% 0px -65% 0px", threshold: 0.01 }
    );
    ids.forEach(function (id) {
      observer.observe(document.getElementById(id));
    });
  }

  function searchPalette() {
    var openBtn = document.getElementById("search-open");
    var backdrop = document.getElementById("site-search");
    var input = document.getElementById("site-search-input");
    var list = document.getElementById("site-search-results");
    if (!backdrop || !input || !list) return;

    var index = [];
    try {
      var raw = document.getElementById("site-search-index");
      if (raw) index = JSON.parse(raw.textContent || "[]");
    } catch (e) {}

    document.querySelectorAll("h2[id], h3[id], .issue-section[id]").forEach(function (el) {
      var label =
        (el.querySelector("h2, h3") || el).textContent || el.getAttribute("id") || "";
      label = label.replace(/\s+/g, " ").trim();
      if (!label) return;
      index.push({
        label: label.slice(0, 120),
        href: "#" + el.id,
        hint: "On this page",
      });
    });

    var selected = 0;
    var filtered = [];

    function close() {
      backdrop.hidden = true;
      document.body.classList.remove("search-open");
      if (openBtn) openBtn.focus();
    }

    function open() {
      backdrop.hidden = false;
      document.body.classList.add("search-open");
      input.value = "";
      selected = 0;
      render("");
      setTimeout(function () {
        input.focus();
      }, 10);
    }

    function render(q) {
      var query = (q || "").toLowerCase().trim();
      filtered = index.filter(function (item) {
        if (!query) return true;
        return (
          (item.label || "").toLowerCase().indexOf(query) >= 0 ||
          (item.hint || "").toLowerCase().indexOf(query) >= 0
        );
      }).slice(0, 12);
      if (!filtered.length) {
        list.innerHTML = '<li class="search-empty">No matches. Try Explore or Change log.</li>';
        return;
      }
      list.innerHTML = filtered
        .map(function (item, i) {
          return (
            "<li><button type=\"button\" data-i=\"" +
            i +
            "\" aria-selected=\"" +
            (i === selected ? "true" : "false") +
            "\"><span>" +
            escapeHtml(item.label) +
            '</span><span class="hint">' +
            escapeHtml(item.hint || item.href) +
            "</span></button></li>"
          );
        })
        .join("");
      Array.prototype.forEach.call(list.querySelectorAll("button"), function (btn) {
        btn.addEventListener("click", function () {
          go(Number(btn.getAttribute("data-i")));
        });
      });
    }

    function escapeHtml(s) {
      return String(s || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function go(i) {
      var item = filtered[i];
      if (!item) return;
      close();
      if (item.href.charAt(0) === "#") {
        var el = document.getElementById(item.href.slice(1));
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
        history.replaceState(null, "", item.href);
      } else {
        window.location.href = item.href;
      }
    }

    if (openBtn) {
      openBtn.addEventListener("click", open);
      if (isMac()) {
        var kbd = openBtn.querySelector(".kbd");
        if (kbd) kbd.textContent = "⌘K";
      }
    }

    backdrop.addEventListener("click", function (e) {
      if (e.target === backdrop) close();
    });

    input.addEventListener("input", function () {
      selected = 0;
      render(input.value);
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        selected = Math.min(selected + 1, Math.max(filtered.length - 1, 0));
        render(input.value);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        selected = Math.max(selected - 1, 0);
        render(input.value);
      } else if (e.key === "Enter") {
        e.preventDefault();
        go(selected);
      } else if (e.key === "Escape") {
        e.preventDefault();
        close();
      }
    });

    document.addEventListener("keydown", function (e) {
      var meta = e.metaKey || e.ctrlKey;
      if (meta && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        if (backdrop.hidden) open();
        else close();
        return;
      }
      if (e.key === "Escape" && !backdrop.hidden) close();
    });
  }

  ready(function () {
    readingProgress();
    copyCodeButtons();
    tocActive();
    searchPalette();
  });
})();
