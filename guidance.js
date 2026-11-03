/* Keep reviewed scope notes visible as the existing catalog search rerenders. */
(function () {
  "use strict";
  var payload = document.getElementById("catalog-scope-notes");
  if (!payload) return;
  var notes;
  try { notes = JSON.parse(payload.textContent); } catch (_) { return; }
  if (!notes || typeof notes !== "object" || Array.isArray(notes)) return;
  var container = document.getElementById("grid") || document.getElementById("board");
  if (!container) return;
  function annotate() {
    container.querySelectorAll("a[href]").forEach(function (anchor) {
      var url;
      try { url = new URL(anchor.getAttribute("href"), location.href); } catch (_) { return; }
      if (url.origin !== location.origin) return;
      var note = notes[url.pathname.replace(/\/$/, "")];
      if (typeof note !== "string" || !note) return;
      var target = anchor.closest("li") || anchor;
      if (target.querySelector(".catalog-scope-note")) return;
      var element = document.createElement("small");
      element.className = "catalog-scope-note";
      element.textContent = "Scope note: " + note;
      target.appendChild(element);
    });
  }
  annotate();
  if (typeof MutationObserver !== "undefined") {
    new MutationObserver(annotate).observe(container, {childList: true, subtree: true});
  }
})();
