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

/* Confirm-before-submit for destructive forms (data-confirm attribute).
   Delegated so it works for every current and future form; replaces inline
   onsubmit= handlers, which the CSP (app/main.py) forbids. */
(function () {
  "use strict";
  document.addEventListener("submit", function (e) {
    var form = e.target;
    var msg = form && form.getAttribute && form.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) e.preventDefault();
  });
})();

/* Price is required unless "price on request" is ticked. */
(function () {
  "use strict";
  var price = document.getElementById("price");
  var onReq = document.querySelector('input[name="price_on_request"]');
  if (!price || !onReq) return;
  function sync() {
    if (onReq.checked) {
      price.required = false;
      price.disabled = true;
    } else {
      price.required = true;
      price.disabled = false;
    }
  }
  onReq.addEventListener("change", sync);
  sync();
})();
