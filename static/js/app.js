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

  // --- Living dreamcatcher: wind sway + beacon rays + drifting words --------
  // One rAF loop, delta-time driven; only transform + opacity are animated.
  (function () {
    var NS = "http://www.w3.org/2000/svg";
    var stage = document.getElementById("dreamcatcher");
    var catcher = document.getElementById("dc-catcher");
    var beam = document.getElementById("dc-beam");
    var wordsG = document.getElementById("dc-words");
    if (!stage || !catcher || !beam || !wordsG) return;

    var CFG = {
      center: { x: 120, y: 120 }, pivot: { x: 120, y: 2 },
      swayIdleDeg: 1.8, swayMaxDeg: 16, swayPeriodMs: 4200, tempoMax: 3.5,
      gustDeg: 5, cursorLeanDeg: 6,
      windIdle: 0.12, windMax: 1.05, windUpLerp: 0.045, windDownLerp: 0.035,
      beamSpeedIdle: 0.015, beamTempoMax: 9, rayLen: 118,
      wordRisePx: 42, wordLifeMs: 3600, wordEmitIdleMs: 1500, wordEmitMinMs: 450, wordMaxLive: 6
    };
    var cx = CFG.center.x, cy = CFG.center.y;
    function polar(r, deg) { var a = (deg - 90) * Math.PI / 180; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; }
    function lerp(a, b, t) { return a + (b - a) * t; }

    // Build soft beacon rays inside the (swaying) catcher group.
    [-10, 80, 170, 260].forEach(function (a) {
      var p1 = polar(CFG.rayLen, a - 11), p2 = polar(CFG.rayLen, a + 11);
      var ray = document.createElementNS(NS, "path");
      ray.setAttribute("d", "M" + cx + " " + cy + " L" + p1[0].toFixed(1) + " " + p1[1].toFixed(1) + " L" + p2[0].toFixed(1) + " " + p2[1].toFixed(1) + " Z");
      ray.setAttribute("fill", "url(#dc-ray)");
      beam.appendChild(ray);
    });

    // Strands (each swings on its own pivot, more than the ring).
    var strands = [];
    Array.prototype.slice.call(document.querySelectorAll(".dc-strand")).forEach(function (el, i) {
      strands.push({ el: el, px: parseFloat(el.dataset.px), py: parseFloat(el.dataset.py), phase: i * 1.3, amp: 0.6 + i * 0.5 });
    });

    var tokens = (stage.dataset.words || "").split(/\s+/).filter(Boolean);
    var wordIndex = 0, liveWords = [], nextEmit = 0;
    function emitWord(now) {
      if (!tokens.length || liveWords.length >= CFG.wordMaxLive) return;
      var t = document.createElementNS(NS, "text");
      t.setAttribute("class", "dc-word"); t.setAttribute("text-anchor", "middle");
      t.setAttribute("aria-hidden", "true");
      t.textContent = tokens[wordIndex % tokens.length]; wordIndex++;
      t.setAttribute("x", (cx + (Math.random() * 32 - 16)).toFixed(1));
      t.setAttribute("y", cy);
      wordsG.appendChild(t);
      liveWords.push({ el: t, born: now });
    }

    var dcReduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (dcReduce) { beam.setAttribute("opacity", "0.18"); return; } // static pose, no loop/words

    // Interaction: hold to intensify; pointer lean. Scoped to the dreamcatcher
    // (touch-action:none in CSS) so page scroll / buttons elsewhere still work.
    var holding = false, wind = CFG.windIdle, lean = 0, targetLean = 0;
    stage.addEventListener("pointerdown", function (e) { holding = true; try { stage.setPointerCapture(e.pointerId); } catch (err) {} });
    window.addEventListener("pointerup", function () { holding = false; });
    stage.addEventListener("pointermove", function (e) {
      var r = stage.getBoundingClientRect();
      targetLean = ((e.clientX - r.left) / r.width - 0.5) * 2 * CFG.cursorLeanDeg;
    });
    stage.addEventListener("pointerleave", function () { targetLean = 0; });

    var lastNow = performance.now(), swayPhase = 0, flutterPhase = 0, beamAngle = 0;
    function frame(now) {
      var dt = Math.min(now - lastNow, 50); lastNow = now;
      var target = holding ? CFG.windMax : CFG.windIdle;
      wind = lerp(wind, target, holding ? CFG.windUpLerp : CFG.windDownLerp);
      lean = lerp(lean, targetLean, 0.05);
      var windN = (wind - CFG.windIdle) / (CFG.windMax - CFG.windIdle);
      var speed = 1 + windN * (CFG.tempoMax - 1);

      swayPhase += (2 * Math.PI / CFG.swayPeriodMs) * speed * dt;
      var amp = CFG.swayIdleDeg + (CFG.swayMaxDeg - CFG.swayIdleDeg) * windN;
      var sway = Math.sin(swayPhase) * amp;
      var gust = Math.sin(now * 0.0007 + 1.3) * CFG.gustDeg * wind;
      catcher.setAttribute("transform", "rotate(" + (sway + gust + lean).toFixed(3) + " " + CFG.pivot.x + " " + CFG.pivot.y + ")");

      flutterPhase += 0.0026 * speed * dt;
      strands.forEach(function (s) {
        var flutter = Math.sin(flutterPhase + s.phase) * (4 + windN * 14) * s.amp;
        s.el.setAttribute("transform", "rotate(" + flutter.toFixed(3) + " " + s.px + " " + s.py + ")");
      });

      var beamSpeed = CFG.beamSpeedIdle * (1 + windN * CFG.beamTempoMax);
      beamAngle = (beamAngle + beamSpeed * dt) % 360;
      beam.setAttribute("transform", "rotate(" + beamAngle.toFixed(2) + " " + cx + " " + cy + ")");
      beam.setAttribute("opacity", (0.18 + windN * 0.5).toFixed(2));

      if (now > nextEmit) {
        emitWord(now);
        nextEmit = now + Math.max(CFG.wordEmitMinMs, CFG.wordEmitIdleMs - (CFG.wordEmitIdleMs - CFG.wordEmitMinMs) * windN);
      }
      for (var i = liveWords.length - 1; i >= 0; i--) {
        var w = liveWords[i], age = now - w.born;
        if (age > CFG.wordLifeMs) { wordsG.removeChild(w.el); liveWords.splice(i, 1); continue; }
        var p = age / CFG.wordLifeMs;
        var op = p < 0.25 ? p / 0.25 : (p > 0.7 ? (1 - p) / 0.3 : 1);
        w.el.setAttribute("y", (cy - p * CFG.wordRisePx).toFixed(1));
        w.el.setAttribute("opacity", Math.max(0, op).toFixed(2));
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  })();

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
