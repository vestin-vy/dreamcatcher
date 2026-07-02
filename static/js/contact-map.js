/* Contact-page Leaflet map. Lives in its own file (not inline) so the CSP can stay
   strict (script-src without 'unsafe-inline'). Reads coords from #map data-attributes. */
(function () {
  "use strict";
  var el = document.getElementById("map");
  if (!el || typeof L === "undefined") return;
  var lat = parseFloat(el.dataset.lat), lng = parseFloat(el.dataset.lng);
  if (isNaN(lat) || isNaN(lng)) return;
  var map = L.map(el, { scrollWheelZoom: false }).setView([lat, lng], 15);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap", maxZoom: 19
  }).addTo(map);
  L.marker([lat, lng]).addTo(map).bindPopup(el.dataset.label);
})();
