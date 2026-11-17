// Filters on list pages and the search page. Everything works without this file except filtering and search.
(function () {
  function fold(s) { return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }

  // ---- list filters ----
  document.querySelectorAll(".filter").forEach(function (box) {
    var items = Array.prototype.slice.call(document.querySelectorAll(box.dataset.target));
    var input = box.querySelector("input");
    var shown = box.querySelector(".shown");
    var state = {};
    function heads() {
      // hide headings whose following list is empty
      document.querySelectorAll("h2").forEach(function (h) {
        var n = h.nextElementSibling;
        if (n && (n.matches("ul.plist,ul.fgrid,ul.slist"))) {
          var any = n.querySelector("li:not(.hide)");
          h.classList.toggle("hide", !any);
          n.classList.toggle("hide", !any);
        }
      });
    }
    function apply() {
      var q = fold(input && input.value.trim());
      var n = 0;
      items.forEach(function (li) {
        var text = fold(li.dataset.n || li.textContent);
        var ok = !q || text.indexOf(q) >= 0;
        Object.keys(state).forEach(function (k) {
          var want = state[k];
          if (!want.length) return;
          var have = (li.dataset[k] || "").split(" ");
          if (!want.some(function (w) { return have.indexOf(w) >= 0; })) ok = false;
        });
        li.classList.toggle("hide", !ok);
        if (ok) n++;
      });
      heads();
      var active = q || Object.keys(state).some(function (k) { return state[k].length; });
      if (shown) shown.textContent = active ? n + " of " + items.length + " shown" : "";
      var az = document.querySelector(".az");
      if (az && box.dataset.target.indexOf("plist") >= 0) az.classList.toggle("hide", !!active);
      try {
        var u = new URL(location.href);
        if (q) u.searchParams.set("q", input.value.trim()); else u.searchParams.delete("q");
        Object.keys(state).forEach(function (k) { if (state[k].length) u.searchParams.set(k, state[k].join(",")); else u.searchParams.delete(k); });
        history.replaceState(null, "", u);
      } catch (e) {}
    }
    box.querySelectorAll("button.chip").forEach(function (b) {
      var key = Object.keys(b.dataset)[0];
      state[key] = state[key] || [];
      b.addEventListener("click", function () {
        var v = b.dataset[key];
        var on = b.getAttribute("aria-pressed") === "true";
        b.setAttribute("aria-pressed", on ? "false" : "true");
        if (on) state[key] = state[key].filter(function (x) { return x !== v; }); else state[key].push(v);
        apply();
      });
    });
    var map = { y: "years", t: "topics", g: "g", k: "kind", s: "short" };
    // dataset key on items: buttons use short keys; map to the item attribute names
    items.forEach(function (li) {
      if (li.dataset.years && !li.dataset.y) li.dataset.y = li.dataset.years;
      if (li.dataset.topics && !li.dataset.t) li.dataset.t = li.dataset.topics;
      if (li.dataset.kind !== undefined && !li.dataset.k) li.dataset.k = li.dataset.kind;
      if (li.dataset.short !== undefined && !li.dataset.s) li.dataset.s = li.dataset.short;
    });
    if (input) input.addEventListener("input", apply);
    try {
      var p = new URL(location.href).searchParams;
      if (p.get("q") && input) input.value = p.get("q");
      Object.keys(state).forEach(function (k) {
        (p.get(k) || "").split(",").filter(Boolean).forEach(function (v) {
          var b = box.querySelector('button[data-' + k + '="' + v + '"]');
          if (b) { b.setAttribute("aria-pressed", "true"); state[k].push(v); }
        });
      });
      if (p.toString()) apply();
    } catch (e) {}
  });

  // ---- search ----
  var sq = document.getElementById("sq");
  if (sq) {
    var res = document.getElementById("results"), info = document.getElementById("sinfo"), data = null;
    var base = { p: "people/", f: "films/", s: "sessions/", t: "topics/", o: "orgs/" };
    var label = { p: "People", f: "Films", s: "Sessions", t: "Topics", o: "Organisations" };
    function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
    function run() {
      var q = fold(sq.value.trim());
      try { var u = new URL(location.href); if (q) u.searchParams.set("q", sq.value.trim()); else u.searchParams.delete("q"); history.replaceState(null, "", u); } catch (e) {}
      if (!q || !data) { res.innerHTML = ""; info.textContent = data ? "" : "Loading…"; return; }
      var words = q.split(/\s+/);
      var groups = { p: [], f: [], s: [], t: [], o: [] };
      data.forEach(function (r) {
        var title = fold(r[2]), all = title + " " + fold(r[3]);
        if (!words.every(function (w) { return all.indexOf(w) >= 0; })) return;
        var score = (title === q ? 0 : title.indexOf(q) === 0 ? 1 : title.indexOf(q) >= 0 ? 2 : 3);
        groups[r[0]].push([score, r]);
      });
      var html = "", total = 0;
      ["p", "f", "s", "t", "o"].forEach(function (k) {
        var g = groups[k].sort(function (a, b) { return a[0] - b[0] || a[1][2].localeCompare(b[1][2]); });
        if (!g.length) return;
        total += g.length;
        html += "<h2>" + label[k] + " <span class=count>" + g.length + "</span></h2><ul>" + g.slice(0, 80).map(function (x) {
          var r = x[1];
          return '<li><a href="' + base[k] + encodeURIComponent(r[1]) + '.html">' + esc(r[2]) + "</a><span class=sub>" + esc(r[4] || "") + "</span></li>";
        }).join("") + (g.length > 80 ? "<li class=note>… and " + (g.length - 80) + " more. Add a word to narrow it down.</li>" : "") + "</ul>";
      });
      res.innerHTML = html || "<p>No matches.</p>";
      info.textContent = total + " result" + (total === 1 ? "" : "s");
    }
    sq.addEventListener("input", run);
    try { var q0 = new URL(location.href).searchParams.get("q"); if (q0) sq.value = q0; } catch (e) {}
    fetch("search.json").then(function (r) { return r.json(); }).then(function (d) { data = d; run(); sq.focus(); });
  }
})();
