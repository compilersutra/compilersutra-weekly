/* CompilerSutra Weekly — Explore combined filters + shareable URL state */
(function () {
  window.CSW = window.CSW || {};

  function esc(t) {
    return String(t || "").replace(/[&<>"']/g, function (c) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[c];
    });
  }

  function readParams() {
    var p = new URLSearchParams(window.location.search);
    return {
      q: p.get("q") || "",
      stage: p.get("stage") || "",
      domain: p.get("domain") || "",
      area: p.get("area") || "",
      project: p.get("project") || "",
    };
  }

  function writeParams(state) {
    var p = new URLSearchParams();
    Object.keys(state).forEach(function (k) {
      if (state[k]) p.set(k, state[k]);
    });
    var qs = p.toString();
    var url = window.location.pathname + (qs ? "?" + qs : "") + window.location.hash;
    window.history.replaceState(null, "", url);
  }

  function mountExplore(items) {
    var q = document.getElementById("q");
    var stage = document.getElementById("stage");
    var domain = document.getElementById("domain");
    var area = document.getElementById("area");
    var project = document.getElementById("project");
    var results = document.getElementById("results");
    var countEl = document.getElementById("count");
    var chips = document.getElementById("active-filters");
    if (!q || !results) return;

    var projects = {};
    (items || []).forEach(function (it) {
      if (it.project) projects[it.project] = true;
    });
    Object.keys(projects)
      .sort()
      .forEach(function (p) {
        var o = document.createElement("option");
        o.value = p;
        o.textContent = p;
        project.appendChild(o);
      });

    var state = readParams();
    q.value = state.q;
    stage.value = state.stage;
    domain.value = state.domain;
    area.value = state.area;
    project.value = state.project;

    function clearChip(key) {
      return function () {
        state[key] = "";
        if (key === "q") q.value = "";
        if (key === "stage") stage.value = "";
        if (key === "domain") domain.value = "";
        if (key === "area") area.value = "";
        if (key === "project") project.value = "";
        render();
      };
    }

    function renderChips() {
      if (!chips) return;
      chips.innerHTML = "";
      var labels = [
        ["q", "Search", state.q],
        ["stage", "Stage", state.stage],
        ["domain", "Domain", state.domain],
        ["area", "Area", state.area],
        ["project", "Project", state.project],
      ];
      var any = false;
      labels.forEach(function (row) {
        if (!row[2]) return;
        any = true;
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "chip filter-chip";
        btn.textContent = row[1] + ": " + row[2] + " ×";
        btn.addEventListener("click", clearChip(row[0]));
        chips.appendChild(btn);
      });
      if (any) {
        var clear = document.createElement("button");
        clear.type = "button";
        clear.className = "chip filter-chip";
        clear.textContent = "Clear all";
        clear.addEventListener("click", function () {
          state = { q: "", stage: "", domain: "", area: "", project: "" };
          q.value = stage.value = domain.value = area.value = project.value = "";
          render();
        });
        chips.appendChild(clear);
      }
    }

    function render() {
      state = {
        q: (q.value || "").trim(),
        stage: stage.value || "",
        domain: domain.value || "",
        area: area.value || "",
        project: project.value || "",
      };
      writeParams(state);
      renderChips();
      var query = state.q.toLowerCase();
      var hits = (items || []).filter(function (s) {
        if (state.stage && (s.stages || []).indexOf(state.stage) < 0) return false;
        if (state.domain && (s.domains || []).indexOf(state.domain) < 0) return false;
        if (state.area && (s.areas || []).indexOf(state.area) < 0) return false;
        if (state.project && s.project !== state.project) return false;
        if (!query) return true;
        var blob = [
          s.title,
          s.why,
          s.what,
          s.project,
          (s.stages || []).join(" "),
          (s.domains || []).join(" "),
          (s.areas || []).join(" "),
        ]
          .join(" ")
          .toLowerCase();
        return blob.indexOf(query) >= 0;
      });
      countEl.textContent = hits.length + " curated stor" + (hits.length === 1 ? "y" : "ies");
      if (!hits.length) {
        results.innerHTML =
          '<p class="topic-empty">No stories match these filters. Clear a chip or broaden the search.</p>';
        return;
      }
      results.innerHTML = hits
        .slice(0, 120)
        .map(function (s) {
          var badges = (s.stages || [])
            .slice(0, 2)
            .concat((s.domains || []).slice(0, 2))
            .map(function (b) {
              return '<span class="badge">' + esc(b) + "</span>";
            })
            .join("");
          return (
            '<article class="story-card">' +
            "<h4><a href=\"" +
            esc(s.source) +
            '" rel="noopener noreferrer">' +
            esc(s.title) +
            "</a></h4>" +
            '<div class="badge-row">' +
            badges +
            "</div>" +
            "<p>" +
            esc((s.why || "").slice(0, 180)) +
            "</p>" +
            '<div class="meta">' +
            esc(s.change_type || "") +
            " · <a href=\"" +
            esc(s.href) +
            '">' +
            esc(s.issue) +
            "</a></div>" +
            "</article>"
          );
        })
        .join("");
    }

    [q, stage, domain, area, project].forEach(function (el) {
      el.addEventListener("input", render);
      el.addEventListener("change", render);
    });
    render();
  }

  window.CSW.mountExplore = mountExplore;
})();
