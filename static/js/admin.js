/* DreamCatcher admin — language tabs on the product form. */
(function () {
  "use strict";
  var tabButtons = document.querySelectorAll(".tab-btn");
  if (!tabButtons.length) return;

  tabButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var target = btn.getAttribute("data-tab");
      document.querySelectorAll(".tab-btn").forEach(function (b) { b.classList.remove("active"); });
      document.querySelectorAll(".tab-panel").forEach(function (p) { p.classList.remove("active"); });
      btn.classList.add("active");
      var panel = document.getElementById(target);
      if (panel) panel.classList.add("active");
    });
  });
})();
