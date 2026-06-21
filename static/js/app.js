/* DreamCatcher — light progressive-enhancement JS.
   Mobile menu, language dropdown, product gallery + lightbox. No dependencies. */
(function () {
  "use strict";

  // --- Mobile menu toggle ---
  var navToggle = document.querySelector(".nav-toggle");
  var mobileMenu = document.querySelector(".mobile-menu");
  if (navToggle && mobileMenu) {
    navToggle.addEventListener("click", function () {
      var open = mobileMenu.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // --- Language dropdown ---
  var langSwitch = document.querySelector(".lang-switch");
  var langBtn = langSwitch && langSwitch.querySelector(".lang-switch__btn");
  if (langSwitch && langBtn) {
    langBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = langSwitch.classList.toggle("open");
      langBtn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    document.addEventListener("click", function () {
      langSwitch.classList.remove("open");
      langBtn.setAttribute("aria-expanded", "false");
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") langSwitch.classList.remove("open");
    });
  }

  // --- Product gallery (swap main image from thumbs) ---
  var mainImg = document.querySelector("[data-gallery-main]");
  var thumbs = document.querySelectorAll("[data-gallery-thumb]");
  if (mainImg && thumbs.length) {
    thumbs.forEach(function (thumb) {
      thumb.addEventListener("click", function () {
        var full = thumb.getAttribute("data-full");
        var alt = thumb.getAttribute("data-alt") || "";
        if (full) {
          mainImg.src = full;
          mainImg.alt = alt;
        }
        thumbs.forEach(function (t) { t.setAttribute("aria-current", "false"); });
        thumb.setAttribute("aria-current", "true");
      });
    });
  }

  // --- Lightbox ---
  var lightbox = document.querySelector(".lightbox");
  if (lightbox) {
    var lightboxImg = lightbox.querySelector("img");
    var closeBtn = lightbox.querySelector(".lightbox__close");
    var open = function (src, alt) {
      lightboxImg.src = src;
      lightboxImg.alt = alt || "";
      lightbox.classList.add("open");
      lightbox.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
    };
    var close = function () {
      lightbox.classList.remove("open");
      lightbox.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
    };
    var trigger = document.querySelector("[data-lightbox-trigger]");
    if (trigger) {
      trigger.addEventListener("click", function () {
        open(mainImg ? mainImg.src : trigger.src, mainImg ? mainImg.alt : "");
      });
    }
    if (closeBtn) closeBtn.addEventListener("click", close);
    lightbox.addEventListener("click", function (e) {
      if (e.target === lightbox) close();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") close();
    });
  }

  // --- Dreamcatcher: cursor "pushes" it (spring-back via CSS transition) ---
  var hero = document.querySelector(".hero");
  var catcher = document.getElementById("dreamcatcher");
  var reduceMo = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (hero && catcher && !reduceMo) {
    hero.addEventListener("pointermove", function (e) {
      var r = catcher.getBoundingClientRect();
      var dx = (e.clientX - (r.left + r.width / 2)) / (r.width || 1);
      var rot = Math.max(-14, Math.min(14, dx * 26));
      catcher.style.transform = "rotate(" + rot.toFixed(2) + "deg)";
    });
    hero.addEventListener("pointerleave", function () {
      catcher.style.transform = "rotate(0deg)";
    });
  }

  // --- Scroll reveal (progressive enhancement; respects reduced-motion) ---
  var reveals = document.querySelectorAll("[data-reveal]");
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reveals.length && "IntersectionObserver" in window && !reduce) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -10% 0px", threshold: 0.08 });
    reveals.forEach(function (el) { io.observe(el); });
  } else {
    // No observer / reduced motion: show everything immediately.
    reveals.forEach(function (el) { el.classList.add("in"); });
  }

  // --- Cookie banner (essential cookies; consent stored locally) ---
  var banner = document.getElementById("cookie-banner");
  if (banner) {
    var KEY = "dc_cookie_ack";
    var acked;
    try { acked = window.localStorage.getItem(KEY); } catch (e) { acked = "1"; }
    if (!acked) {
      banner.hidden = false;
      var accept = document.getElementById("cookie-accept");
      if (accept) {
        accept.addEventListener("click", function () {
          try { window.localStorage.setItem(KEY, "1"); } catch (e) {}
          banner.hidden = true;
        });
      }
    }
  }

  // --- First-visit language chooser ---
  var langModal = document.getElementById("lang-modal");
  if (langModal) {
    var langChosen;
    try { langChosen = window.localStorage.getItem("dc_lang_choice"); } catch (e) { langChosen = "1"; }
    if (!langChosen) {
      langModal.hidden = false;
      langModal.querySelectorAll("[data-lang]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var l = btn.getAttribute("data-lang");
          try { window.localStorage.setItem("dc_lang_choice", l); } catch (e) {}
          document.cookie = "lang=" + l + ";path=/;max-age=31536000";
          var cur = langModal.getAttribute("data-cur");
          var path = langModal.getAttribute("data-path") || "";
          if (l !== cur) {
            window.location.href = "/" + l + (path || "/");
          } else {
            langModal.hidden = true;
          }
        });
      });
    }
  }

  // --- Cart: auto-submit quantity on change (no need to tap "Update") ---
  document.querySelectorAll(".cart-item__qty input[type=number]").forEach(function (inp) {
    inp.addEventListener("change", function () { if (inp.form) inp.form.submit(); });
  });

  // --- Checkout: live-update the summary when a shipping method is picked ---
  var summary = document.getElementById("checkout-summary");
  if (summary) {
    var subtotal = parseFloat(summary.dataset.subtotal) || 0;
    var rate = parseFloat(summary.dataset.rate) || 0;
    var loc = (summary.dataset.lang === "el") ? "el-GR" : "en-US";
    var money = new Intl.NumberFormat(loc, { style: "currency", currency: "EUR" });
    var shipEl = document.getElementById("sum-shipping");
    var vatEl = document.getElementById("sum-vat");
    var totEl = document.getElementById("sum-total");
    function recomputeSummary() {
      var sel = document.querySelector("input[name=shipping_method]:checked");
      var cost = sel ? (parseFloat(sel.dataset.cost) || 0) : 0;
      var total = subtotal + cost;
      var vat = rate ? total - total / (1 + rate / 100) : 0;
      if (shipEl) shipEl.textContent = money.format(cost);
      if (vatEl) vatEl.textContent = money.format(vat);
      if (totEl) totEl.textContent = money.format(total);
    }
    document.querySelectorAll("input[name=shipping_method]").forEach(function (r) {
      r.addEventListener("change", recomputeSummary);
    });
    recomputeSummary();
  }
})();
