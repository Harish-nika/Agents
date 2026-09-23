const STORAGE_KEY = "trip_guide_session_id";
const THEME_KEY = "trip_guide_theme";
const THREAD_KEY = "trip_guide_thread";
const LAST_USER_KEY = "trip_guide_last_user";

const thread = document.getElementById("thread");
const form = document.getElementById("chatForm");
const input = document.getElementById("message");
const sendBtn = document.getElementById("sendBtn");
const stopBtn = document.getElementById("stopBtn");
const regenBtn = document.getElementById("regenBtn");
const statusBar = document.getElementById("statusBar");
const statusText = document.getElementById("statusText");
const runtimeChip = document.getElementById("runtimeChip");
const newTripBtn = document.getElementById("newTrip");
const settingsBtn = document.getElementById("settingsBtn");
const settingsModal = document.getElementById("settingsModal");
const settingsForm = document.getElementById("settingsForm");
const settingsStatus = document.getElementById("settingsStatus");
const keyBanner = document.getElementById("keyBanner");
const geminiInput = document.getElementById("googleApiKey");
const mapsInput = document.getElementById("mapsApiKey");
const groqInput = document.getElementById("groqApiKey");
const ollamaBaseInput = document.getElementById("ollamaApiBase");
const ollamaModelInput = document.getElementById("ollamaModel");
const ollamaFallbacksInput = document.getElementById("ollamaFallbacks");
const runtimeModeSelect = document.getElementById("runtimeMode");
const runtimeModeHint = document.getElementById("runtimeModeHint");
const geminiHint = document.getElementById("geminiHint");
const mapsHint = document.getElementById("mapsHint");
const groqHint = document.getElementById("groqHint");
const ollamaBaseHint = document.getElementById("ollamaBaseHint");
const ollamaModelHint = document.getElementById("ollamaModelHint");
const ollamaFallbacksHint = document.getElementById("ollamaFallbacksHint");
const spineList = document.getElementById("spineList");
const spineDates = document.getElementById("spineDates");
const spineNotes = document.getElementById("spineNotes");
const spinePrefs = document.getElementById("spinePrefs");
const mapEmpty = document.getElementById("mapEmpty");
const mapHud = document.getElementById("mapHud");
const tripSummary = document.getElementById("tripSummary");
const summaryBody = document.getElementById("summaryBody");
const aboutBtn = document.getElementById("aboutBtn");
const aboutModal = document.getElementById("aboutModal");
const prefsModal = document.getElementById("prefsModal");
const editPrefsBtn = document.getElementById("editPrefsBtn");
const prefsForm = document.getElementById("prefsForm");
const themeToggle = document.getElementById("themeToggle");
const shell = document.querySelector(".shell");

let streamAbort = null;
let lastUserMessage = "";
let streamingBodyEl = null;

const tripState = {
  origin: "",
  stops: [],
  routeStops: [],
  startDate: "",
  endDate: "",
  notes: "",
  weatherByStop: {},
  weatherCards: [],
  placesLinks: [],
  lodgingLinks: [],
  pois: [],
  mapCards: [],
  geometry: null,
};

const tripPrefs = {
  budget: "",
  pace: "",
  interests: [],
  companions: "",
  vibe: "",
  notes: "",
};

let map;
let markersLayer;
let placesLayer;
let routeLayer;
let geometryTimer = null;
let placesTimer = null;
let markerByIndex = [];
let activeSummaryTab = "overview";
let placeGeoCache = {};

const ACTIVITY_SOURCES = [
  { match: /climate|weather/i, source: "Open-Meteo", key: "climate" },
  { match: /places|attractions|sightseeing/i, source: "DuckDuckGo", key: "places" },
  { match: /food|stays|lodging|hotel/i, source: "DuckDuckGo", key: "stays" },
  { match: /route|map|direction|geometry|driving/i, source: "OSRM", key: "route" },
];

function prefsStorageKey() {
  const sid = getSessionId();
  return sid ? `trip_guide_prefs_${sid}` : "trip_guide_prefs_anon";
}

function loadPrefsFromStorage() {
  try {
    const raw = sessionStorage.getItem(prefsStorageKey());
    if (!raw) return;
    const data = JSON.parse(raw);
    Object.assign(tripPrefs, {
      budget: data.budget || "",
      pace: data.pace || "",
      interests: Array.isArray(data.interests) ? data.interests : [],
      companions: data.companions || "",
      vibe: data.vibe || "",
      notes: data.notes || "",
    });
  } catch {
    /* ignore */
  }
}

function savePrefsToStorage() {
  try {
    sessionStorage.setItem(prefsStorageKey(), JSON.stringify(tripPrefs));
  } catch {
    /* ignore */
  }
}

function resetTripPrefs() {
  tripPrefs.budget = "";
  tripPrefs.pace = "";
  tripPrefs.interests = [];
  tripPrefs.companions = "";
  tripPrefs.vibe = "";
  tripPrefs.notes = "";
  try {
    sessionStorage.removeItem(prefsStorageKey());
  } catch {
    /* ignore */
  }
  renderPrefs();
}

function renderPrefs() {
  if (!spinePrefs) return;
  const bits = [
    tripPrefs.budget,
    tripPrefs.pace,
    tripPrefs.vibe,
    tripPrefs.companions,
    ...(tripPrefs.interests || []),
  ].filter(Boolean);
  if (!bits.length) {
    spinePrefs.hidden = true;
    spinePrefs.textContent = "";
    return;
  }
  spinePrefs.hidden = false;
  spinePrefs.textContent = bits.join(" · ");
}

function getSessionId() {
  return localStorage.getItem(STORAGE_KEY);
}

function setSessionId(id) {
  const prev = getSessionId();
  localStorage.setItem(STORAGE_KEY, id);
  if (prev !== id) {
    loadPrefsFromStorage();
    renderPrefs();
  }
}

function clearSession() {
  localStorage.removeItem(STORAGE_KEY);
}

function weekdayShort(iso) {
  try {
    return new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function fmtTemp(v) {
  if (v == null || Number.isNaN(Number(v))) return "–";
  return `${Math.round(Number(v))}°`;
}

function formatDistanceKm(meters) {
  if (meters == null || Number.isNaN(Number(meters))) return null;
  const km = Number(meters) / 1000;
  if (km < 10) return `${km.toFixed(1)} km`;
  return `${Math.round(km).toLocaleString()} km`;
}

function formatDurationHours(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return null;
  const h = Number(seconds) / 3600;
  if (h < 1) return `${Math.max(1, Math.round(Number(seconds) / 60))} min`;
  if (h < 10) return `${h.toFixed(1)} h`;
  return `${Math.round(h)} h`;
}

function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  const theme = saved === "light" ? "light" : "dark";
  document.body.setAttribute("data-theme", theme);
}

function toggleTheme() {
  const next =
    document.body.getAttribute("data-theme") === "light" ? "dark" : "light";
  document.body.setAttribute("data-theme", next);
  localStorage.setItem(THEME_KEY, next);
}

function bumpMapSize() {
  if (!map) return;
  try {
    map.invalidateSize({ animate: false });
  } catch {
    /* ignore */
  }
}

function initMap() {
  if (map) {
    bumpMapSize();
    return;
  }
  if (typeof L === "undefined") {
    if (mapEmpty) {
      mapEmpty.classList.remove("hidden");
      mapEmpty.textContent =
        "Map library failed to load. Hard-refresh the page; if it persists, restart the Trip Guide server.";
    }
    return;
  }
  const el = document.getElementById("map");
  if (!el) return;

  map = L.map(el, { zoomControl: true, attributionControl: true }).setView(
    [15.0, 75.5],
    6
  );
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);
  markersLayer = L.layerGroup().addTo(map);
  placesLayer = L.layerGroup().addTo(map);
  routeLayer = L.layerGroup().addTo(map);
  // Layout often settles after first paint — resize a few times
  bumpMapSize();
  requestAnimationFrame(bumpMapSize);
  setTimeout(bumpMapSize, 100);
  setTimeout(bumpMapSize, 400);
}

function numberIcon(n, weatherIcon) {
  const wx = weatherIcon
    ? `<em class="wx" title="Weather">${weatherIcon}</em>`
    : "";
  return L.divIcon({
    className: "num-marker",
    html: `<span class="num-bubble"><b>${n}</b>${wx}</span>`,
    iconSize: [32, 40],
    iconAnchor: [16, 20],
  });
}

function placeIcon(kind) {
  const k = kind || "places";
  const emoji = k === "food" ? "🍽️" : k === "lodging" ? "🛏️" : "📍";
  return L.divIcon({
    className: `place-marker kind-${k}`,
    html: `<span class="place-pin" title="${k}">${emoji}</span>`,
    iconSize: [28, 28],
    iconAnchor: [14, 26],
  });
}

function weatherForStopName(name) {
  if (!name) return null;
  const key = String(name).toLowerCase();
  if (tripState.weatherByStop[key]) return tripState.weatherByStop[key];
  // Fuzzy: "Gokarna Beach" ↔ "gokarna"
  for (const [k, v] of Object.entries(tripState.weatherByStop)) {
    if (key.includes(k) || k.includes(key)) return v;
  }
  return null;
}

function placesNearStop(stopName) {
  const key = String(stopName || "").toLowerCase();
  const fromPois = (tripState.pois || []).filter((p) => {
    if (!key) return true;
    const near = String(p.near || "").toLowerCase();
    const name = String(p.name || "").toLowerCase();
    return near.includes(key) || key.includes(near) || name.includes(key);
  });
  if (fromPois.length) {
    return fromPois.slice(0, 5).map((p) => ({
      title: `${p.icon || "📍"} ${p.name}`,
      url: p.osm_url || "",
      snippet: `${p.category || p.kind || ""}${p.distance_km != null ? ` · ${p.distance_km} km` : ""}`,
    }));
  }
  if (!key) return tripState.placesLinks.slice(0, 4);
  const hits = tripState.placesLinks.filter((link) => {
    const blob = `${link.title || ""} ${link.snippet || ""}`.toLowerCase();
    return blob.includes(key);
  });
  return (hits.length ? hits : tripState.placesLinks).slice(0, 4);
}

function stopPopupHtml(stop) {
  const name = stop.label || stop.name || "Stop";
  const wx = weatherForStopName(name);
  let weatherBlock = "";
  if (wx) {
    const days = (wx.days || []).slice(0, 3)
      .map(
        (d) =>
          `<li>${escapeHtml(d.icon || "")} ${escapeHtml(d.date || "")}: `
          + `${escapeHtml(String(d.temp_min_c ?? "?"))}–${escapeHtml(String(d.temp_max_c ?? "?"))}°C `
          + `(${escapeHtml(d.label || "")})</li>`
      )
      .join("");
    weatherBlock = `
      <div class="map-pop-section">
        <strong>${escapeHtml(wx.icon || "🌡️")} Weather</strong>
        <div class="map-pop-muted">${escapeHtml(wx.label || wx.summary || "")}</div>
        ${days ? `<ul class="map-pop-list">${days}</ul>` : ""}
      </div>`;
  }
  const places = placesNearStop(name);
  let placesBlock = "";
  if (places.length) {
    const items = places
      .map((p) => {
        const title = escapeHtml(p.title || "Place");
        const url = (p.url || "").trim();
        if (url) {
          return `<li><a href="${escapeAttr(url)}" target="_blank" rel="noopener">${title}</a></li>`;
        }
        return `<li>${title}</li>`;
      })
      .join("");
    placesBlock = `
      <div class="map-pop-section">
        <strong>Top places</strong>
        <ul class="map-pop-list">${items}</ul>
      </div>`;
  }
  return `
    <div class="map-popup">
      <div class="map-pop-title">${escapeHtml(name)}</div>
      ${weatherBlock || '<div class="map-pop-muted">Ask in chat for climate at this stop.</div>'}
      ${placesBlock || ""}
    </div>`;
}

function routeLineColor() {
  return document.body.getAttribute("data-theme") === "light"
    ? "#0f6b5c"
    : "#3b82f6";
}

function resetTripState() {
  tripState.origin = "";
  tripState.stops = [];
  tripState.routeStops = [];
  tripState.startDate = "";
  tripState.endDate = "";
  tripState.notes = "";
  tripState.weatherByStop = {};
  tripState.weatherCards = [];
  tripState.placesLinks = [];
  tripState.lodgingLinks = [];
  tripState.pois = [];
  tripState.mapCards = [];
  tripState.geometry = null;
  placeGeoCache = {};
  resetTripPrefs();
  renderSpine();
  clearMapLayers();
  updateMapHud(null);
  if (mapEmpty) mapEmpty.classList.remove("hidden");
  renderTripSummary();
}

function clearMapLayers() {
  if (markersLayer) markersLayer.clearLayers();
  if (placesLayer) placesLayer.clearLayers();
  if (routeLayer) routeLayer.clearLayers();
  markerByIndex = [];
}

function updateMapHud(geometry) {
  if (!mapHud) return;
  const route = geometry && geometry.route;
  const dist = formatDistanceKm(route && route.distance_m);
  const dur = formatDurationHours(route && route.duration_s);
  if (!dist && !dur) {
    mapHud.classList.add("hidden");
    mapHud.textContent = "";
    return;
  }
  const parts = [];
  if (dist) parts.push(`~${dist}`);
  if (dur) parts.push(`~${dur}`);
  mapHud.textContent = parts.join(" · ");
  mapHud.classList.remove("hidden");
}

function renderSpine() {
  const stops = tripState.routeStops.length
    ? tripState.routeStops
    : tripState.stops;
  if (tripState.startDate || tripState.endDate) {
    spineDates.textContent = [tripState.startDate, tripState.endDate]
      .filter(Boolean)
      .join(" → ");
  } else {
    spineDates.textContent = "Dates appear as you chat";
  }
  spineNotes.textContent = tripState.notes || "";

  spineList.innerHTML = "";
  if (!stops.length) {
    const li = document.createElement("li");
    li.className = "spine-empty";
    li.textContent = "Your stops will line up here.";
    spineList.appendChild(li);
    return;
  }

  stops.forEach((name, i) => {
    const li = document.createElement("li");
    li.dataset.index = String(i);
    const weather = tripState.weatherByStop[name.toLowerCase()];
    const meta = weather
      ? `${weather.icon || "🌡️"} ${weather.label || "Weather"}`
      : i === 0 && tripState.origin
        ? "Start"
        : i === stops.length - 1 && tripState.origin
          ? "Return"
          : "Stop";
    li.innerHTML = `
      <span class="idx">${i + 1}</span>
      <div class="stop-name">${name}</div>
      <div class="stop-meta">${meta}</div>
    `;
    li.addEventListener("click", () => focusStop(i));
    spineList.appendChild(li);
  });
}

function focusStop(index) {
  spineList.querySelectorAll("li").forEach((el) => el.classList.remove("active"));
  const li = spineList.querySelector(`li[data-index="${index}"]`);
  if (li) li.classList.add("active");
  const marker = markerByIndex[index];
  if (marker && map) {
    map.panTo(marker.getLatLng(), { animate: true });
    marker.openPopup();
  }
}

function scheduleGeometryRefresh() {
  clearTimeout(geometryTimer);
  geometryTimer = setTimeout(refreshGeometry, 320);
}

/** Expand "A → B → C" spine mistakes before calling geometry API. */
function expandStopNames(stops) {
  const out = [];
  const splitRe = /\s*(?:,|\/|;|\||→|->|–|—|\bto\b|\bthen\b)\s*/i;
  for (const raw of stops || []) {
    const name = String(raw || "").trim();
    if (!name) continue;
    const parts = name.split(splitRe).map((p) => p.trim()).filter((p) => p.length > 1);
    const list = parts.length > 1 ? parts : [name];
    for (const p of list) {
      if (out.length && out[out.length - 1].toLowerCase() === p.toLowerCase()) continue;
      out.push(p);
    }
  }
  return out;
}

async function refreshGeometry() {
  const stops = expandStopNames(
    tripState.routeStops.length ? tripState.routeStops : tripState.stops
  );
  if (stops.length >= 2) {
    tripState.routeStops = stops;
  }
  if (stops.length < 1) {
    clearMapLayers();
    updateMapHud(null);
    if (mapEmpty) mapEmpty.classList.remove("hidden");
    renderTripSummary();
    return;
  }

  try {
    const res = await fetch("/api/trip/geometry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stops: stops.map((name) => ({ name })) }),
    });
    const data = await res.json();
    tripState.geometry = data;
    drawGeometry(data);
    updateMapHud(data);
    renderTripSummary();
  } catch (err) {
    console.warn("geometry failed", err);
  }
}

function drawGeometry(data) {
  initMap();
  if (!map || !markersLayer || typeof L === "undefined") return;

  clearMapLayers();
  const stops = data.stops || [];
  const usable = stops.filter((s) => s.lat != null && s.lon != null);
  if (!usable.length) {
    if (mapEmpty) {
      mapEmpty.classList.remove("hidden");
      mapEmpty.textContent = "Could not place stops on the map (geocode failed).";
    }
    return;
  }
  if (mapEmpty) mapEmpty.classList.add("hidden");

  usable.forEach((s, i) => {
    const fullIndex = stops.indexOf(s);
    const idx = fullIndex >= 0 ? fullIndex : i;
    const wx = weatherForStopName(s.label || s.name);
    const marker = L.marker([s.lat, s.lon], {
      icon: numberIcon(idx + 1, wx && wx.icon),
    }).bindPopup(stopPopupHtml(s), {
      maxWidth: 280,
      className: "trip-map-popup",
    });
    marker.addTo(markersLayer);
    markerByIndex[idx] = marker;
  });

  const routeCoords = data.route && data.route.coordinates;
  if (routeCoords && routeCoords.length > 1) {
    const line = L.polyline(routeCoords, {
      color: routeLineColor(),
      weight: 4,
      opacity: 0.85,
    }).addTo(routeLayer);
    map.fitBounds(line.getBounds().pad(0.18));
  } else {
    const group = L.featureGroup(Object.values(markerByIndex).filter(Boolean));
    if (group.getLayers().length) {
      map.fitBounds(group.getBounds().pad(0.25));
    }
  }
  bumpMapSize();
  requestAnimationFrame(() => {
    bumpMapSize();
    if (routeCoords && routeCoords.length > 1) {
      try {
        map.fitBounds(L.polyline(routeCoords).getBounds().pad(0.18));
      } catch {
        /* ignore */
      }
    }
  });
  setTimeout(bumpMapSize, 250);
  schedulePlacesOnMap();
}

function mergeLinks(target, links) {
  if (!Array.isArray(links)) return;
  const seen = new Set(target.map((l) => (l.url || l.title || "").toLowerCase()));
  for (const link of links) {
    const key = (link.url || link.title || "").toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    target.push(link);
  }
}

function schedulePlacesOnMap() {
  clearTimeout(placesTimer);
  placesTimer = setTimeout(refreshPlacesOnMap, 450);
}

function stopCoordsList() {
  const geoStops = (tripState.geometry && tripState.geometry.stops) || [];
  return geoStops.filter((s) => s.lat != null && s.lon != null);
}

function nearAnyStop(lat, lon, maxKm = 180) {
  const stops = stopCoordsList();
  if (!stops.length) return true;
  for (const s of stops) {
    const dlat = (lat - s.lat) * 111;
    const dlon = (lon - s.lon) * 111 * Math.cos((s.lat * Math.PI) / 180);
    const km = Math.sqrt(dlat * dlat + dlon * dlon);
    if (km <= maxKm) return true;
  }
  return false;
}

/** Approx distance to OSRM polyline (for on-the-way midway POIs). */
function nearRouteLine(lat, lon, maxKm = 45) {
  const coords =
    tripState.geometry &&
    tripState.geometry.route &&
    tripState.geometry.route.coordinates;
  if (!coords || coords.length < 2) return false;
  const step = Math.max(1, Math.floor(coords.length / 80));
  let best = Infinity;
  for (let i = 0; i < coords.length; i += step) {
    const c = coords[i];
    if (!c || c.length < 2) continue;
    const dlat = (lat - c[0]) * 111;
    const dlon = (lon - c[1]) * 111 * Math.cos((c[0] * Math.PI) / 180);
    const km = Math.sqrt(dlat * dlat + dlon * dlon);
    if (km < best) best = km;
    if (best <= maxKm) return true;
  }
  return best <= maxKm;
}

function keepPoiOnMap(p) {
  if (p.lat == null || p.lon == null) return false;
  if (p.along_route || p.on_the_way) {
    return nearAnyStop(p.lat, p.lon, 280) || nearRouteLine(p.lat, p.lon, 50);
  }
  return nearAnyStop(p.lat, p.lon, 200);
}

async function refreshPlacesOnMap() {
  initMap();
  if (!map || !placesLayer || typeof L === "undefined") return;
  placesLayer.clearLayers();

  // Prefer OSM POIs with real coordinates
  const osmPois = (tripState.pois || []).filter(
    (p) => p && p.lat != null && p.lon != null
  );
  for (const p of osmPois.slice(0, 28)) {
    if (!keepPoiOnMap(p)) continue;
    const url = (p.osm_url || "").trim();
    const where = p.on_the_way
      ? `On the way · ${p.near || ""}`
      : p.near
        ? `near ${p.near}`
        : "";
    const html = `
      <div class="map-popup">
        <div class="map-pop-title">${escapeHtml(p.icon || "📍")} ${escapeHtml(p.name || "Place")}</div>
        <div class="map-pop-muted">${escapeHtml(p.category || p.kind || "")}${
          where ? ` · ${escapeHtml(where)}` : ""
        }${p.distance_km != null ? ` · ${escapeHtml(String(p.distance_km))} km` : ""}</div>
        ${
          url
            ? `<a class="map-pop-link" href="${escapeAttr(url)}" target="_blank" rel="noopener">OpenStreetMap</a>`
            : ""
        }
      </div>`;
    L.marker([p.lat, p.lon], { icon: placeIcon(p.kind) })
      .bindPopup(html, { maxWidth: 260, className: "trip-map-popup" })
      .addTo(placesLayer);
  }

  // Fallback: geocode DuckDuckGo titles when no OSM pois
  if (osmPois.length) return;
  const links = (tripState.placesLinks || []).slice(0, 8);
  if (!links.length) return;

  const names = links.map((l) => (l.title || "").trim()).filter(Boolean);
  const missing = names.filter((n) => !placeGeoCache[n.toLowerCase()]);
  if (missing.length) {
    try {
      const res = await fetch("/api/geocode/places", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ names: missing }),
      });
      const data = await res.json();
      for (const p of data.places || []) {
        placeGeoCache[(p.query || p.name || "").toLowerCase()] = p;
        if (p.name) placeGeoCache[p.name.toLowerCase()] = p;
      }
    } catch (err) {
      console.warn("place geocode failed", err);
    }
  }

  for (const link of links) {
    const title = (link.title || "").trim();
    if (!title) continue;
    const geo =
      placeGeoCache[title.toLowerCase()] ||
      placeGeoCache[title.split(" - ")[0].trim().toLowerCase()];
    if (!geo || geo.lat == null || geo.lon == null) continue;
    if (!nearAnyStop(geo.lat, geo.lon)) continue;
    const url = (link.url || "").trim();
    const snip = (link.snippet || "").trim();
    const html = `
      <div class="map-popup">
        <div class="map-pop-title">📍 ${escapeHtml(geo.name || title)}</div>
        ${snip ? `<div class="map-pop-muted">${escapeHtml(snip.slice(0, 140))}</div>` : ""}
        ${
          url
            ? `<a class="map-pop-link" href="${escapeAttr(url)}" target="_blank" rel="noopener">Open reference</a>`
            : ""
        }
      </div>`;
    L.marker([geo.lat, geo.lon], { icon: placeIcon("places") })
      .bindPopup(html, { maxWidth: 260, className: "trip-map-popup" })
      .addTo(placesLayer);
  }
}

function ingestCards(cards) {
  if (!cards || !cards.length) return;
  let dirty = false;
  for (const card of cards) {
    if (card.type === "trip_board") {
      tripState.origin = card.origin || tripState.origin;
      tripState.stops = Array.isArray(card.stops) ? card.stops : tripState.stops;
      tripState.routeStops = Array.isArray(card.route_stops)
        ? card.route_stops
        : tripState.routeStops;
      tripState.startDate = card.start_date || tripState.startDate;
      tripState.endDate = card.end_date || tripState.endDate;
      tripState.notes = card.notes || tripState.notes;
      dirty = true;
    }
    if (card.type === "trip_prefs") {
      tripPrefs.budget = card.budget || tripPrefs.budget;
      tripPrefs.pace = card.pace || tripPrefs.pace;
      tripPrefs.companions = card.companions || tripPrefs.companions;
      tripPrefs.vibe = card.vibe || tripPrefs.vibe;
      tripPrefs.notes = card.notes || tripPrefs.notes;
      if (Array.isArray(card.interests) && card.interests.length) {
        tripPrefs.interests = card.interests;
      }
      savePrefsToStorage();
      renderPrefs();
    }
    if (card.type === "weather") {
      tripState.weatherCards.push(card);
      const title = card.title || "";
      const m = title.match(/Weather\s*[—\-]\s*(.+)$/i);
      const place = (m ? m[1] : "").split("(")[0].trim();
      if (place) {
        const day0 = (card.days && card.days[0]) || {};
        tripState.weatherByStop[place.toLowerCase()] = {
          icon: day0.icon || "🌡️",
          label: day0.label || card.summary || "Climate",
          days: card.days || [],
          summary: card.summary || "",
        };
        dirty = true;
      }
    }
    if (card.type === "places" && Array.isArray(card.links)) {
      mergeLinks(tripState.placesLinks, card.links);
    }
    if (card.type === "lodging" && Array.isArray(card.links)) {
      mergeLinks(tripState.lodgingLinks, card.links);
    }
    if (
      (card.type === "places" || card.type === "lodging") &&
      Array.isArray(card.pois) &&
      card.pois.length
    ) {
      const seen = new Set(
        (tripState.pois || []).map(
          (p) => `${(p.name || "").toLowerCase()}|${p.lat}|${p.lon}`
        )
      );
      for (const p of card.pois) {
        if (!p || p.lat == null || p.lon == null) continue;
        const key = `${(p.name || "").toLowerCase()}|${p.lat}|${p.lon}`;
        if (seen.has(key)) continue;
        seen.add(key);
        tripState.pois.push(p);
      }
      schedulePlacesOnMap();
      if (tripState.geometry) drawGeometry(tripState.geometry);
    } else if (card.type === "places" && Array.isArray(card.links)) {
      schedulePlacesOnMap();
      if (tripState.geometry) drawGeometry(tripState.geometry);
    }
    if (card.type === "map") {
      tripState.mapCards.push(card);
      if (card.origin && card.destination) {
        const route = [card.origin, card.destination];
        if (!tripState.routeStops.length) {
          tripState.routeStops = route;
          dirty = true;
        }
      }
    }
  }
  if (dirty) {
    renderSpine();
    scheduleGeometryRefresh();
  }
  renderTripSummary();
}

function hasSummaryContent() {
  const stops = tripState.routeStops.length
    ? tripState.routeStops
    : tripState.stops;
  return (
    stops.length > 0 ||
    tripState.weatherCards.length > 0 ||
    tripState.placesLinks.length > 0 ||
    tripState.lodgingLinks.length > 0 ||
    (tripState.pois && tripState.pois.length > 0) ||
    tripState.mapCards.length > 0 ||
    (tripState.geometry && tripState.geometry.route)
  );
}

function renderLinkList(links) {
  if (!links.length && !(tripState.pois || []).length) {
    return '<p class="summary-empty">Nothing here yet — ask in chat.</p>';
  }
  let html = "";
  if ((tripState.pois || []).length) {
    const pois = tripState.pois
      .slice(0, 12)
      .map((p) => {
        const title = escapeHtml(`${p.icon || "📍"} ${p.name || "Place"}`);
        const meta = escapeHtml(
          [
            p.on_the_way ? "on the way" : "",
            p.category || p.kind,
            p.near,
            p.distance_km != null ? `${p.distance_km} km` : "",
          ]
            .filter(Boolean)
            .join(" · ")
        );
        const url = (p.osm_url || "").trim();
        if (url) {
          return `<li><a href="${escapeAttr(url)}" target="_blank" rel="noopener noreferrer">${title}</a><span class="card-link-snippet">${meta}</span></li>`;
        }
        return `<li>${title}<span class="card-link-snippet">${meta}</span></li>`;
      })
      .join("");
    html += `<p class="summary-label">Along the route (OpenStreetMap)</p><ol class="card-links">${pois}</ol>`;
  }
  if (links.length) {
    const items = links
      .slice(0, 12)
      .map((link) => {
        const title = (link.title || link.url || "Link").trim();
        const url = (link.url || "").trim();
        const sn = link.snippet
          ? `<span class="card-link-snippet">${escapeHtml(link.snippet)}</span>`
          : "";
        if (url) {
          return `<li><a href="${escapeAttr(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(title)}</a>${sn}</li>`;
        }
        return `<li>${escapeHtml(title)}${sn}</li>`;
      })
      .join("");
    html += `<p class="summary-label">Web references</p><ol class="card-links">${items}</ol>`;
  }
  return html;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/'/g, "&#39;");
}

function renderOverviewTab() {
  const stops = tripState.routeStops.length
    ? tripState.routeStops
    : tripState.stops;
  const route = tripState.geometry && tripState.geometry.route;
  const dist = formatDistanceKm(route && route.distance_m);
  const dur = formatDurationHours(route && route.duration_s);
  const chips = [];
  if (stops.length) chips.push(`${stops.length} stop${stops.length === 1 ? "" : "s"}`);
  if (dist) chips.push(dist);
  if (dur) chips.push(dur);
  if (tripPrefs.budget) chips.push(tripPrefs.budget);
  if (tripPrefs.pace) chips.push(tripPrefs.pace);
  if (tripPrefs.vibe) chips.push(tripPrefs.vibe);

  const bullets = [];
  if (tripState.origin) bullets.push(`From <strong>${escapeHtml(tripState.origin)}</strong>`);
  if (stops.length) bullets.push(`Stops: ${stops.map(escapeHtml).join(" → ")}`);
  if (tripState.startDate || tripState.endDate) {
    bullets.push(
      `Dates: ${escapeHtml([tripState.startDate, tripState.endDate].filter(Boolean).join(" → "))}`
    );
  }
  if (tripPrefs.interests && tripPrefs.interests.length) {
    bullets.push(`Interests: ${tripPrefs.interests.map(escapeHtml).join(", ")}`);
  }
  if (tripState.notes) bullets.push(escapeHtml(tripState.notes));

  const chipHtml = chips.length
    ? `<div class="summary-overview-bits">${chips
        .map((c) => `<span class="summary-chip">${escapeHtml(c)}</span>`)
        .join("")}</div>`
    : "";
  const listHtml = bullets.length
    ? `<ul>${bullets.map((b) => `<li>${b}</li>`).join("")}</ul>`
    : '<p class="summary-empty">Plan details will appear as the agent fills the board.</p>';
  return chipHtml + listHtml;
}

function renderWeatherTab() {
  const entries = Object.entries(tripState.weatherByStop);
  if (!entries.length && !tripState.weatherCards.length) {
    return '<p class="summary-empty">No weather yet — ask for climate at your stops.</p>';
  }
  if (entries.length) {
    return `<ul>${entries
      .map(
        ([place, w]) =>
          `<li><strong>${escapeHtml(place)}</strong> — ${escapeHtml(w.icon || "")} ${escapeHtml(w.label || w.summary || "Climate")}</li>`
      )
      .join("")}</ul>`;
  }
  return `<ul>${tripState.weatherCards
    .map(
      (c) =>
        `<li><strong>${escapeHtml(c.title || "Weather")}</strong>${c.summary ? ` — ${escapeHtml(c.summary)}` : ""}</li>`
    )
    .join("")}</ul>`;
}

function renderRouteTab() {
  const route = tripState.geometry && tripState.geometry.route;
  const dist = formatDistanceKm(route && route.distance_m);
  const dur = formatDurationHours(route && route.duration_s);
  const parts = [];
  if (dist || dur) {
    parts.push(
      `<p><strong>Driving estimate</strong> · ${[dist && `~${dist}`, dur && `~${dur}`]
        .filter(Boolean)
        .join(" · ")} <em>(OSRM)</em></p>`
    );
  }
  for (const card of tripState.mapCards.slice(-3)) {
    if (card.summary) parts.push(`<p>${escapeHtml(card.summary)}</p>`);
    if (card.maps_url) {
      parts.push(
        `<p><a href="${escapeAttr(card.maps_url)}" target="_blank" rel="noopener noreferrer">Open in Google Maps</a></p>`
      );
    }
  }
  if (!parts.length) {
    return '<p class="summary-empty">Route stats appear when the map has a driving line.</p>';
  }
  return parts.join("");
}

function renderTripSummary() {
  if (!tripSummary || !summaryBody) return;
  if (!hasSummaryContent()) {
    tripSummary.classList.add("hidden");
    return;
  }
  tripSummary.classList.remove("hidden");
  let html = "";
  switch (activeSummaryTab) {
    case "weather":
      html = renderWeatherTab();
      break;
    case "places":
      html = renderLinkList(tripState.placesLinks);
      break;
    case "stays":
      html = renderLinkList(tripState.lodgingLinks);
      break;
    case "route":
      html = renderRouteTab();
      break;
    default:
      html = renderOverviewTab();
  }
  summaryBody.innerHTML = html;
}

function renderMarkdown(text) {
  let s = escapeHtml(text || "");
  s = s.replace(/```([\s\S]*?)```/g, (_, code) => `<pre><code>${code}</code></pre>`);
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/(^|\n)### (.+)/g, "$1<h4>$2</h4>");
  s = s.replace(/(^|\n)## (.+)/g, "$1<h3>$2</h3>");
  s = s.replace(/(^|\n)# (.+)/g, "$1<h3>$2</h3>");
  s = s.replace(/(^|\n)- (.+)/g, "$1<li>$2</li>");
  s = s.replace(/(?:<li>.*<\/li>\n?)+/g, (block) => `<ul>${block}</ul>`);
  s = s.replace(
    /\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>'
  );
  s = s.replace(/\n{2,}/g, "</p><p>");
  s = s.replace(/\n/g, "<br>");
  return `<p>${s}</p>`;
}

function saveThreadSnapshot() {
  try {
    const msgs = [];
    thread.querySelectorAll(".msg").forEach((el) => {
      if (el.classList.contains("thinking")) return;
      const role = el.classList.contains("user")
        ? "user"
        : el.classList.contains("system")
          ? "system"
          : "assistant";
      const body = el.querySelector(".msg-body");
      const text = body ? body.innerText || body.textContent || "" : "";
      if (text) msgs.push({ role, text });
    });
    localStorage.setItem(
      THREAD_KEY,
      JSON.stringify({
        session_id: getSessionId(),
        messages: msgs.slice(-40),
        tripState,
        tripPrefs,
      })
    );
    if (lastUserMessage) localStorage.setItem(LAST_USER_KEY, lastUserMessage);
  } catch {
    /* ignore */
  }
}

function restoreThreadSnapshot() {
  try {
    const raw = localStorage.getItem(THREAD_KEY);
    if (!raw) return false;
    const data = JSON.parse(raw);
    if (data.session_id) setSessionId(data.session_id);
    if (data.tripState) Object.assign(tripState, data.tripState);
    if (data.tripPrefs) Object.assign(tripPrefs, data.tripPrefs);
    lastUserMessage = localStorage.getItem(LAST_USER_KEY) || "";
    thread.innerHTML = "";
    for (const m of data.messages || []) {
      appendMessage(m.role, m.text, [], { persist: false });
    }
    if (regenBtn) regenBtn.hidden = !lastUserMessage;
    renderSpine();
    renderPrefs();
    renderTripSummary();
    return (data.messages || []).length > 0;
  } catch {
    return false;
  }
}

function setRuntimeChip(data) {
  if (!runtimeChip) return;
  const mode = (data && data.runtime_mode) || "auto";
  const label =
    (data && data.runtime_mode_label) ||
    (mode === "local"
      ? "Local GPU"
      : mode === "cloud"
        ? "Cloud"
        : "Auto");
  runtimeChip.textContent = label;
  runtimeChip.dataset.mode = mode;
}

function setBusy(busy) {
  sendBtn.disabled = busy;
  if (stopBtn) stopBtn.hidden = !busy;
  if (regenBtn) regenBtn.hidden = busy || !lastUserMessage;
  if (statusBar) statusBar.classList.toggle("hidden", !busy);
}

function setStatusLabel(label) {
  if (statusText) statusText.textContent = label || "Working…";
  if (statusBar) statusBar.classList.remove("hidden");
}

function appendMessage(role, text, cards = [], opts = {}) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;

  if (text) {
    const body = document.createElement("div");
    body.className = "msg-body";
    if (role === "assistant") {
      body.innerHTML = renderMarkdown(text);
    } else {
      body.textContent = text;
    }
    el.appendChild(body);
  }

  if (cards && cards.length) {
    const wrap = document.createElement("div");
    wrap.className = "cards";
    for (const card of cards) {
      if (card.type === "trip_board" || card.type === "trip_prefs") continue;
      wrap.appendChild(renderCard(card));
    }
    if (wrap.childNodes.length) el.appendChild(wrap);
    ingestCards(cards);
  }

  thread.appendChild(el);
  thread.scrollTop = thread.scrollHeight;
  if (opts.persist !== false) saveThreadSnapshot();
  return el;
}

function ensureStreamingMessage() {
  if (streamingBodyEl && streamingBodyEl.isConnected) return streamingBodyEl;
  const el = document.createElement("div");
  el.className = "msg assistant";
  el.id = "streamingMsg";
  const body = document.createElement("div");
  body.className = "msg-body streaming";
  body.innerHTML = "";
  el.appendChild(body);
  thread.appendChild(el);
  streamingBodyEl = body;
  return body;
}

function resolveActivity(label) {
  for (const item of ACTIVITY_SOURCES) {
    if (item.match.test(label)) return item;
  }
  return { source: "Agent", key: label.toLowerCase().slice(0, 24) };
}

function showThinking() {
  const el = document.createElement("div");
  el.className = "msg assistant thinking";
  el.id = "thinkingMsg";
  el.innerHTML = `
    <div class="thinking-row">
      <span class="thinking-dots" aria-hidden="true"><i></i><i></i><i></i></span>
      <span class="thinking-label">Thinking…</span>
    </div>
    <ul class="activity-list"></ul>
  `;
  thread.appendChild(el);
  thread.scrollTop = thread.scrollHeight;
  return el;
}

function updateThinking(label) {
  const el = document.getElementById("thinkingMsg");
  if (!el) return;
  const labelEl = el.querySelector(".thinking-label");
  if (labelEl) labelEl.textContent = label;
  const list = el.querySelector(".activity-list");
  if (list && label && label !== "Thinking…") {
    const meta = resolveActivity(label);
    const existing = list.querySelector(`[data-activity-key="${meta.key}"]`);
    if (existing) {
      const lab = existing.querySelector(".activity-label");
      if (lab) lab.textContent = label;
    } else {
      const li = document.createElement("li");
      li.className = "activity-card";
      li.dataset.activityKey = meta.key;
      li.innerHTML = `
        <span class="activity-label">${escapeHtml(label)}</span>
        <span class="activity-source">${escapeHtml(meta.source)}</span>
      `;
      list.appendChild(li);
    }
  }
  thread.scrollTop = thread.scrollHeight;
}

function removeThinking() {
  const el = document.getElementById("thinkingMsg");
  if (el) el.remove();
}

function renderCard(card) {
  const box = document.createElement("div");
  box.className = `card card-${card.type || "generic"}`;

  const title = document.createElement("h3");
  title.textContent = card.title || card.type || "Update";
  box.appendChild(title);

  if (card.subtitle) {
    const sub = document.createElement("p");
    sub.className = "card-sub";
    sub.textContent = card.subtitle;
    box.appendChild(sub);
  }

  if (card.type === "weather" && Array.isArray(card.days) && card.days.length) {
    const timeline = document.createElement("div");
    timeline.className = "weather-timeline";
    for (const day of card.days.slice(0, 8)) {
      const cell = document.createElement("div");
      cell.className = "weather-day";
      const precip = day.precipitation_mm != null ? Number(day.precipitation_mm) : 0;
      cell.innerHTML = `
        <div class="w-date">${weekdayShort(day.date)}</div>
        <div class="w-icon" title="${day.label || ""}">${day.icon || "🌡️"}</div>
        <div class="w-label">${day.label || ""}</div>
        <div class="w-temp"><span class="hi">${fmtTemp(day.temp_max_c)}</span>
          <span class="lo">${fmtTemp(day.temp_min_c)}</span></div>
        <div class="w-rain">${precip > 0 ? `💧 ${precip}mm` : "Dry"}</div>
      `;
      timeline.appendChild(cell);
    }
    box.appendChild(timeline);
    if (card.source) {
      const src = document.createElement("p");
      src.className = "card-sub";
      src.textContent = `Source: ${card.source}`;
      box.appendChild(src);
    }
    return box;
  }

  if (
    card.summary &&
    card.type !== "weather" &&
    card.type !== "map" &&
    !(card.links && card.links.length)
  ) {
    const p = document.createElement("p");
    p.textContent = card.summary;
    box.appendChild(p);
  }

  if (
    (card.type === "places" || card.type === "lodging") &&
    Array.isArray(card.links) &&
    card.links.length
  ) {
    const list = document.createElement("ol");
    list.className = "card-links";
    for (const link of card.links.slice(0, 6)) {
      const url = (link.url || "").trim();
      const linkTitle = (link.title || url || "Source").trim();
      if (!url && !linkTitle) continue;
      const li = document.createElement("li");
      if (url) {
        const a = document.createElement("a");
        a.href = url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = linkTitle;
        li.appendChild(a);
      } else {
        li.textContent = linkTitle;
      }
      if (link.snippet) {
        const sn = document.createElement("span");
        sn.className = "card-link-snippet";
        sn.textContent = link.snippet;
        li.appendChild(sn);
      }
      list.appendChild(li);
    }
    if (list.children.length) box.appendChild(list);
  }

  if (card.type === "map") {
    if (card.summary) {
      const p = document.createElement("p");
      p.className = "card-sub";
      p.textContent = card.summary;
      box.appendChild(p);
    }
    if (Array.isArray(card.steps) && card.steps.length) {
      const ul = document.createElement("ol");
      ul.className = "map-steps";
      for (const step of card.steps.slice(0, 8)) {
        const li = document.createElement("li");
        const bits = [step.instruction];
        if (step.distance) bits.push(step.distance);
        li.textContent = bits.filter(Boolean).join(" · ");
        ul.appendChild(li);
      }
      box.appendChild(ul);
    }
    if (card.maps_url) {
      const a = document.createElement("a");
      a.href = card.maps_url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.className = "map-link";
      a.textContent = "Open full route in Google Maps";
      box.appendChild(a);
    }
    return box;
  }

  return box;
}

function welcome() {
  appendMessage(
    "system",
    "Tell me where you’re going and which dates. I’ll update the plan and map on the sides as we go."
  );
}

function openSettings() {
  settingsModal.classList.remove("hidden");
  settingsModal.setAttribute("aria-hidden", "false");
  loadSettings();
}

function closeSettings() {
  settingsModal.classList.add("hidden");
  settingsModal.setAttribute("aria-hidden", "true");
  settingsStatus.textContent = "";
}

function openAbout() {
  aboutModal.classList.remove("hidden");
  aboutModal.setAttribute("aria-hidden", "false");
}

function closeAbout() {
  aboutModal.classList.add("hidden");
  aboutModal.setAttribute("aria-hidden", "true");
}

function openPrefs() {
  document.getElementById("prefBudget").value = tripPrefs.budget || "";
  document.getElementById("prefPace").value = tripPrefs.pace || "";
  document.getElementById("prefVibe").value = tripPrefs.vibe || "";
  document.getElementById("prefInterests").value = (tripPrefs.interests || []).join(", ");
  document.getElementById("prefCompanions").value = tripPrefs.companions || "";
  prefsModal.classList.remove("hidden");
  prefsModal.setAttribute("aria-hidden", "false");
}

function closePrefs() {
  prefsModal.classList.add("hidden");
  prefsModal.setAttribute("aria-hidden", "true");
}

async function loadSettings() {
  try {
    const res = await fetch("/api/settings");
    const data = await res.json();
    geminiHint.textContent = data.google_api_key_set
      ? `Saved (${data.google_api_key_hint}) — paste a new key to replace`
      : "Not set yet";
    if (groqHint) {
      groqHint.textContent = data.groq_api_key_set
        ? `Saved (${data.groq_api_key_hint}) — used in Cloud / Auto`
        : "Optional — paste your Groq gsk_ key";
    }
    if (runtimeModeSelect) {
      runtimeModeSelect.value = data.runtime_mode || "auto";
    }
    if (runtimeModeHint) {
      const cands = (data.model_candidates || []).slice(0, 4).join(" → ");
      runtimeModeHint.textContent = cands
        ? `Active order: ${cands}${(data.model_candidates || []).length > 4 ? "…" : ""}`
        : data.runtime_mode_label || "";
    }
    if (ollamaBaseInput) {
      ollamaBaseInput.value = data.ollama_api_base || "";
    }
    if (ollamaModelInput) {
      ollamaModelInput.value = data.ollama_model || "";
    }
    if (ollamaFallbacksInput) {
      ollamaFallbacksInput.value = data.ollama_model_fallbacks || "";
    }
    if (ollamaBaseHint) {
      ollamaBaseHint.textContent = data.ollama_configured
        ? "Ollama ready for Local / Auto fallback"
        : "Set URL + model for local GPU";
    }
    if (ollamaModelHint) {
      ollamaModelHint.textContent = data.ollama_model
        ? "Prefer a tool-capable tag (e.g. llama3-groq-tool-use)"
        : "Example: ollama/llama3-groq-tool-use:latest";
    }
    if (ollamaFallbacksHint) {
      ollamaFallbacksHint.textContent = data.ollama_model_fallbacks
        ? "Tried if the primary Ollama model fails"
        : "Optional comma-separated list";
    }
    mapsHint.textContent = data.google_maps_api_key_set
      ? `Saved (${data.google_maps_api_key_hint}) — paste a new key to replace`
      : "Optional — without it you still get an Open-in-Maps link";
    setRuntimeChip(data);
    updateKeyBanner(data);
  } catch (err) {
    geminiHint.textContent = "Could not load settings";
  }
}

function updateKeyBanner(data) {
  const mode = data.runtime_mode || "auto";
  const hasCloud = data.google_api_key_set || data.groq_api_key_set;
  const hasLocal = data.ollama_configured;
  let ok = true;
  let msg = "";
  if (mode === "local" && !hasLocal) {
    ok = false;
    msg = "Local mode needs Ollama URL + model in Settings.";
  } else if (mode === "cloud" && !hasCloud) {
    ok = false;
    msg = "Cloud mode needs a Gemini or Groq key in Settings.";
  } else if (!hasCloud && !hasLocal) {
    ok = false;
    msg =
      "Add a Gemini / Groq key or configure Ollama in Settings before chatting.";
  }
  if (!ok) {
    keyBanner.classList.remove("hidden");
    keyBanner.innerHTML = msg;
  } else {
    keyBanner.classList.add("hidden");
    keyBanner.textContent = "";
  }
}

settingsBtn.addEventListener("click", openSettings);
settingsModal.querySelectorAll("[data-close]").forEach((el) => {
  el.addEventListener("click", closeSettings);
});

if (aboutBtn && aboutModal) {
  aboutBtn.addEventListener("click", openAbout);
  aboutModal.querySelectorAll("[data-close-about]").forEach((el) => {
    el.addEventListener("click", closeAbout);
  });
}

if (editPrefsBtn && prefsModal) {
  editPrefsBtn.addEventListener("click", openPrefs);
  prefsModal.querySelectorAll("[data-close-prefs]").forEach((el) => {
    el.addEventListener("click", closePrefs);
  });
}

if (prefsForm) {
  prefsForm.addEventListener("submit", (event) => {
    event.preventDefault();
    tripPrefs.budget = document.getElementById("prefBudget").value.trim();
    tripPrefs.pace = document.getElementById("prefPace").value.trim();
    tripPrefs.vibe = document.getElementById("prefVibe").value.trim();
    tripPrefs.companions = document.getElementById("prefCompanions").value.trim();
    const interestRaw = document.getElementById("prefInterests").value.trim();
    tripPrefs.interests = interestRaw
      ? interestRaw.split(",").map((s) => s.trim()).filter(Boolean)
      : [];
    savePrefsToStorage();
    renderPrefs();
    renderTripSummary();
    closePrefs();

    const bits = [
      tripPrefs.budget && `budget ${tripPrefs.budget}`,
      tripPrefs.pace && `${tripPrefs.pace} pace`,
      tripPrefs.vibe && `${tripPrefs.vibe} vibe`,
      tripPrefs.companions && `traveling ${tripPrefs.companions}`,
      tripPrefs.interests.length && `interested in ${tripPrefs.interests.join(", ")}`,
    ].filter(Boolean);
    if (bits.length && input) {
      input.value = `Please remember my trip prefs: ${bits.join("; ")}.`;
      input.focus();
    }
  });
}

if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    toggleTheme();
    if (tripState.geometry) drawGeometry(tripState.geometry);
  });
}

document.querySelectorAll(".summary-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    activeSummaryTab = btn.dataset.tab || "overview";
    document.querySelectorAll(".summary-tab").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    renderTripSummary();
  });
});

settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {};
  const gemini = geminiInput.value.trim();
  const maps = mapsInput.value.trim();
  const groq = groqInput ? groqInput.value.trim() : "";
  const ollamaBase = ollamaBaseInput ? ollamaBaseInput.value.trim() : "";
  const ollamaModel = ollamaModelInput ? ollamaModelInput.value.trim() : "";
  const ollamaFallbacks = ollamaFallbacksInput
    ? ollamaFallbacksInput.value.trim()
    : "";
  if (gemini) payload.google_api_key = gemini;
  if (maps) payload.google_maps_api_key = maps;
  if (groq) payload.groq_api_key = groq;
  if (runtimeModeSelect) payload.runtime_mode = runtimeModeSelect.value;
  if (ollamaBaseInput) payload.ollama_api_base = ollamaBase;
  if (ollamaModelInput) payload.ollama_model = ollamaModel;
  if (ollamaFallbacksInput) payload.ollama_model_fallbacks = ollamaFallbacks;
  if (
    !payload.google_api_key &&
    !payload.google_maps_api_key &&
    !payload.groq_api_key &&
    !payload.runtime_mode &&
    !ollamaBaseInput &&
    !ollamaModelInput
  ) {
    settingsStatus.textContent = "Change a setting to save.";
    return;
  }

  settingsStatus.textContent = "Saving…";
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      settingsStatus.textContent = data.detail || "Save failed.";
      return;
    }
    geminiInput.value = "";
    mapsInput.value = "";
    if (groqInput) groqInput.value = "";
    settingsStatus.textContent = "Saved.";
    await loadSettings();
  } catch (err) {
    settingsStatus.textContent = `Error: ${err.message}`;
  }
});

newTripBtn.addEventListener("click", () => {
  clearSession();
  try {
    localStorage.removeItem(THREAD_KEY);
    localStorage.removeItem(LAST_USER_KEY);
  } catch (_) {}
  lastUserMessage = "";
  streamingBodyEl = null;
  thread.innerHTML = "";
  resetTripState();
  welcome();
  if (regenBtn) regenBtn.hidden = true;
});

async function stopChat() {
  const sid = getSessionId();
  if (streamAbort) {
    try {
      streamAbort.abort();
    } catch (_) {}
  }
  if (sid) {
    try {
      await fetch("/api/chat/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sid }),
      });
    } catch (_) {}
  }
  setBusy(false);
  removeThinking();
  setStatusLabel("Stopped");
  if (statusBar) setTimeout(() => statusBar.classList.add("hidden"), 800);
}

async function sendViaStream(message) {
  const stops = (tripState.routeStops.length
    ? tripState.routeStops
    : tripState.stops
  ).filter(Boolean);
  const trip_context = {
    origin: tripState.origin || "",
    stops,
    route_stops: stops,
    start_date: tripState.startDate || "",
    end_date: tripState.endDate || "",
    prefs: {
      budget: tripPrefs.budget || "",
      pace: tripPrefs.pace || "",
      vibe: tripPrefs.vibe || "",
      companions: tripPrefs.companions || "",
      interests: tripPrefs.interests || [],
    },
  };

  showThinking();
  setBusy(true);
  setStatusLabel("Thinking…");
  streamingBodyEl = null;
  streamAbort = new AbortController();
  let streamedText = "";
  let gotDone = false;

  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal: streamAbort.signal,
    body: JSON.stringify({
      message,
      session_id: getSessionId(),
      trip_context,
    }),
  });

  if (!res.ok) {
    removeThinking();
    setBusy(false);
    let detail = "Something went wrong.";
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch (_) {}
    appendMessage("assistant", detail);
    if (res.status === 503) openSettings();
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) {
      const line = chunk
        .split("\n")
        .map((l) => l.trim())
        .find((l) => l.startsWith("data:"));
      if (!line) continue;
      let event;
      try {
        event = JSON.parse(line.slice(5).trim());
      } catch {
        continue;
      }
      if (event.session_id) setSessionId(event.session_id);
      if (event.type === "status") {
        updateThinking(event.label || "Working…");
        setStatusLabel(event.label || "Working…");
      } else if (event.type === "card" && event.card) {
        ingestCards([event.card]);
      } else if (event.type === "token") {
        removeThinking();
        streamedText += event.text || "";
        const body = ensureStreamingMessage();
        body.innerHTML = renderMarkdown(streamedText);
        thread.scrollTop = thread.scrollHeight;
      } else if (event.type === "done") {
        gotDone = true;
        removeThinking();
        const finalReply = event.reply || streamedText || "";
        const existing = document.getElementById("streamingMsg");
        if (existing) existing.remove();
        streamingBodyEl = null;
        appendMessage("assistant", finalReply, event.cards || []);
      }
    }
  }
  removeThinking();
  if (!gotDone) {
    const existing = document.getElementById("streamingMsg");
    if (existing) existing.remove();
    streamingBodyEl = null;
    if (streamedText) {
      appendMessage("assistant", streamedText);
    } else {
      appendMessage(
        "assistant",
        "The connection closed before the trip reply finished. " +
          "Send the same message again — places search is now fail-fast if Overpass is slow."
      );
    }
  }
  setBusy(false);
  if (statusBar) statusBar.classList.add("hidden");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  lastUserMessage = message;
  appendMessage("user", message);
  input.value = "";

  try {
    await sendViaStream(message);
  } catch (err) {
    removeThinking();
    setBusy(false);
    if (err && err.name === "AbortError") {
      appendMessage("assistant", "Stopped.");
    } else {
      const msg = (err && err.message) || String(err) || "unknown";
      appendMessage(
        "assistant",
        `Connection dropped while the agent was working (${msg}). ` +
          "Often Overpass/search was slow — send the same message again, " +
          "or switch Runtime to Local in Settings."
      );
    }
  } finally {
    setBusy(false);
    input.focus();
  }
});

if (stopBtn) {
  stopBtn.addEventListener("click", () => {
    stopChat();
  });
}

if (regenBtn) {
  regenBtn.addEventListener("click", async () => {
    if (!lastUserMessage || sendBtn.disabled) return;
    appendMessage("user", lastUserMessage);
    try {
      await sendViaStream(lastUserMessage);
    } catch (err) {
      removeThinking();
      setBusy(false);
      if (err && err.name === "AbortError") {
        appendMessage("assistant", "Stopped.");
      } else {
        appendMessage(
          "assistant",
          `Connection dropped (${(err && err.message) || "network"}). Try again.`
        );
      }
    }
  });
}
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const panel = btn.dataset.panel;
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    shell.classList.remove("show-spine", "show-chat", "show-map");
    if (panel === "spine") shell.classList.add("show-spine");
    if (panel === "chat") shell.classList.add("show-chat");
    if (panel === "map") {
      shell.classList.add("show-map");
      setTimeout(() => {
        initMap();
        if (map) map.invalidateSize();
      }, 50);
    }
  });
});

initTheme();
shell.classList.add("show-chat");
initMap();
loadPrefsFromStorage();
renderSpine();
renderPrefs();
renderTripSummary();
if (!restoreThreadSnapshot()) {
  welcome();
}
loadSettings();
input.focus();

// Keep Leaflet sized when the side panel resizes
const mapPanelEl = document.getElementById("mapPanel");
if (mapPanelEl && typeof ResizeObserver !== "undefined") {
  const ro = new ResizeObserver(() => bumpMapSize());
  ro.observe(mapPanelEl);
}
window.addEventListener("resize", bumpMapSize);
