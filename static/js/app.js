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
})();
