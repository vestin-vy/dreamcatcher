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
    var holdZone = document.querySelector(".hero__art") || stage; // press anywhere here
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
      // Words rise as a single spaced column; speed scales with wind.
      wordRiseSpeed: 0.030, wordRiseTempo: 2.2, wordMaxRisePx: 100,
      wordFadeInPx: 18, wordFadeOutPx: 36, wordMinGapPx: 34,
      wordEmitIdleMs: 1500, wordEmitMinMs: 320, wordMaxLive: 5
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
      var t = document.createElement("span");
      t.className = "dc-word";
      t.textContent = tokens[wordIndex % tokens.length]; wordIndex++;
      t.style.left = (50 + (Math.random() * 8 - 4)).toFixed(0) + "%"; // slight organic jitter
      t.style.top = "58%";
      t.style.transform = "translate(-50%,0)";
      wordsG.appendChild(t);
      liveWords.push({ el: t, y: 0 }); // y = px risen so far
    }

    var dcReduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (dcReduce) { beam.setAttribute("opacity", "0.18"); return; } // static pose, no loop/words

    // Interaction: hold to intensify; pointer lean. Scoped to the dreamcatcher
    // (touch-action:none in CSS) so page scroll / buttons elsewhere still work.
    var holding = false, wind = CFG.windIdle, lean = 0, targetLean = 0;
    holdZone.addEventListener("pointerdown", function (e) {
      holding = true;
      // Capture only the mouse; capturing touch would fight the browser's scroll.
      if (e.pointerType === "mouse") { try { holdZone.setPointerCapture(e.pointerId); } catch (err) {} }
    });
    window.addEventListener("pointerup", function () { holding = false; });
    // When the browser takes the gesture for scrolling, it cancels the pointer.
    window.addEventListener("pointercancel", function () { holding = false; });
    holdZone.addEventListener("pointermove", function (e) {
      var r = holdZone.getBoundingClientRect();
      targetLean = ((e.clientX - r.left) / r.width - 0.5) * 2 * CFG.cursorLeanDeg;
    });
    holdZone.addEventListener("pointerleave", function () { targetLean = 0; });

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

      // Emit only when the last word has risen at least minGap -> guarantees no overlap.
      var newest = liveWords[liveWords.length - 1];
      if (now > nextEmit && (!newest || newest.y >= CFG.wordMinGapPx)) {
        emitWord();
        nextEmit = now + Math.max(CFG.wordEmitMinMs, CFG.wordEmitIdleMs - (CFG.wordEmitIdleMs - CFG.wordEmitMinMs) * windN);
      }
      var riseSpeed = CFG.wordRiseSpeed * (1 + windN * CFG.wordRiseTempo);
      for (var i = liveWords.length - 1; i >= 0; i--) {
        var w = liveWords[i];
        w.y += riseSpeed * dt;
        if (w.y > CFG.wordMaxRisePx) { wordsG.removeChild(w.el); liveWords.splice(i, 1); continue; }
        var op = w.y < CFG.wordFadeInPx ? w.y / CFG.wordFadeInPx
               : (w.y > CFG.wordMaxRisePx - CFG.wordFadeOutPx ? (CFG.wordMaxRisePx - w.y) / CFG.wordFadeOutPx : 1);
        w.el.style.transform = "translate(-50%, " + (-w.y).toFixed(1) + "px)";
        w.el.style.opacity = Math.max(0, op).toFixed(2);
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

/* --- Featured carousel ---------------------------------------------------- */
/* Desktop: auto-advances one card every few seconds and gets ← → arrows; when it
   reaches the end it rewinds to the start. Mobile: a plain native swipe carousel
   — NO JS scroll-writes there, since stepping scrollLeft fought touch momentum
   and made the row jitter. Respects prefers-reduced-motion (no auto-advance). */
(function () {
  "use strict";
  var track = document.querySelector(".grid--carousel");
  if (!track) return;
  var cards = track.querySelectorAll(".card");
  if (cards.length <= 1) return;

  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var desktop = window.matchMedia ? window.matchMedia("(min-width: 769px)") : { matches: true, addEventListener: function () {} };
  var lang = (document.documentElement.lang || "el").slice(0, 2);
  var T = lang === "el"
    ? { prev: "Προηγούμενα", next: "Επόμενα" }
    : { prev: "Previous", next: "Next" };

  // Wrap the track so the absolutely-positioned arrows can sit over its edges.
  var wrap = document.createElement("div");
  wrap.className = "carousel";
  track.parentNode.insertBefore(wrap, track);
  wrap.appendChild(track);

  var CHEV = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="%P%"/></svg>';
  function makeBtn(dir, label, path) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "carousel__nav carousel__nav--" + dir;
    b.setAttribute("aria-label", label);
    b.innerHTML = CHEV.replace("%P%", path);
    wrap.appendChild(b);
    return b;
  }

  function cardStep() {
    var c = track.querySelector(".card");
    if (!c) return 0;
    var gap = parseFloat(getComputedStyle(track).columnGap || getComputedStyle(track).gap) || 0;
    return c.getBoundingClientRect().width + gap;
  }
  function maxScroll() { return track.scrollWidth - track.clientWidth; }

  function next() {
    if (track.scrollLeft >= maxScroll() - 4) {
      track.scrollTo({ left: 0, behavior: "smooth" });       // rewind at the end
    } else {
      track.scrollBy({ left: cardStep(), behavior: "smooth" });
    }
  }
  function prev() {
    if (track.scrollLeft <= 4) {
      track.scrollTo({ left: maxScroll(), behavior: "smooth" });
    } else {
      track.scrollBy({ left: -cardStep(), behavior: "smooth" });
    }
  }

  var prevBtn = makeBtn("prev", T.prev, "m15 18-6-6 6-6");
  var nextBtn = makeBtn("next", T.next, "m9 18 6-6-6-6");
  prevBtn.addEventListener("click", prev);
  nextBtn.addEventListener("click", next);

  var paused = false;
  var timer = null;
  function startAuto() {
    if (timer || reduce) return;
    timer = window.setInterval(function () {
      // Only meaningful while there's something to scroll.
      if (!paused && !document.hidden && maxScroll() > 4) next();
    }, 4000);
  }
  function stopAuto() { if (timer) { window.clearInterval(timer); timer = null; } }
  function apply() {
    // Auto-advance only on desktop; mobile stays a clean native swipe.
    if (!reduce && desktop.matches) startAuto(); else stopAuto();
  }
  if (desktop.addEventListener) desktop.addEventListener("change", apply);
  apply();

  // Pause auto-advance while the user is interacting.
  track.addEventListener("mouseenter", function () { paused = true; });
  track.addEventListener("mouseleave", function () { paused = false; });
  track.addEventListener("focusin", function () { paused = true; });
  track.addEventListener("focusout", function () { paused = false; });
})();
