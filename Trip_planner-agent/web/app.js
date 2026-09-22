const STORAGE_KEY = "trip_guide_session_id";
const THEME_KEY = "trip_guide_theme";

const thread = document.getElementById("thread");
const form = document.getElementById("chatForm");
const input = document.getElementById("message");
const sendBtn = document.getElementById("sendBtn");
const newTripBtn = document.getElementById("newTrip");
const settingsBtn = document.getElementById("settingsBtn");
const settingsModal = document.getElementById("settingsModal");
const settingsForm = document.getElementById("settingsForm");
const settingsStatus = document.getElementById("settingsStatus");
const keyBanner = document.getElementById("keyBanner");
const geminiInput = document.getElementById("googleApiKey");
const mapsInput = document.getElementById("mapsApiKey");
const groqInput = document.getElementById("groqApiKey");
const geminiHint = document.getElementById("geminiHint");
const mapsHint = document.getElementById("mapsHint");
const groqHint = document.getElementById("groqHint");
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
let routeLayer;
let geometryTimer = null;
let markerByIndex = [];
let activeSummaryTab = "overview";

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
  routeLayer = L.layerGroup().addTo(map);
  // Layout often settles after first paint — resize a few times
  bumpMapSize();
  requestAnimationFrame(bumpMapSize);
  setTimeout(bumpMapSize, 100);
  setTimeout(bumpMapSize, 400);
}

function numberIcon(n) {
  return L.divIcon({
    className: "num-marker",
    html: `<span>${n}</span>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
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
  tripState.mapCards = [];
  tripState.geometry = null;
  resetTripPrefs();
  renderSpine();
  clearMapLayers();
  updateMapHud(null);
  if (mapEmpty) mapEmpty.classList.remove("hidden");
  renderTripSummary();
}

function clearMapLayers() {
  if (markersLayer) markersLayer.clearLayers();
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

async function refreshGeometry() {
  const stops = (tripState.routeStops.length
    ? tripState.routeStops
    : tripState.stops
  ).filter(Boolean);
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
    const marker = L.marker([s.lat, s.lon], {
      icon: numberIcon(fullIndex >= 0 ? fullIndex + 1 : i + 1),
    }).bindPopup(`<strong>${s.label || s.name}</strong>`);
    marker.addTo(markersLayer);
    markerByIndex[fullIndex >= 0 ? fullIndex : i] = marker;
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
    tripState.mapCards.length > 0 ||
    (tripState.geometry && tripState.geometry.route)
  );
}

function renderLinkList(links) {
  if (!links.length) {
    return '<p class="summary-empty">Nothing here yet — ask in chat.</p>';
  }
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
  return `<ol class="card-links">${items}</ol>`;
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

function appendMessage(role, text, cards = []) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;

  if (text) {
    const body = document.createElement("div");
    body.className = "msg-body";
    body.textContent = text;
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
  return el;
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
        ? `Saved (${data.groq_api_key_hint}) — used when Gemini is busy`
        : "Optional — paste your Groq gsk_ key (also read from grok_key in .env)";
    }
    mapsHint.textContent = data.google_maps_api_key_set
      ? `Saved (${data.google_maps_api_key_hint}) — paste a new key to replace`
      : "Optional — without it you still get an Open-in-Maps link";
    updateKeyBanner(data);
  } catch (err) {
    geminiHint.textContent = "Could not load settings";
  }
}

function updateKeyBanner(data) {
  if (!data.google_api_key_set && !data.groq_api_key_set) {
    keyBanner.classList.remove("hidden");
    keyBanner.innerHTML =
      'Add a <strong>Gemini</strong> and/or <strong>Groq</strong> key in Settings before chatting.';
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
  if (gemini) payload.google_api_key = gemini;
  if (maps) payload.google_maps_api_key = maps;
  if (groq) payload.groq_api_key = groq;
  if (!payload.google_api_key && !payload.google_maps_api_key && !payload.groq_api_key) {
    settingsStatus.textContent = "Paste at least one key to save.";
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
  thread.innerHTML = "";
  resetTripState();
  welcome();
});

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
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: getSessionId(),
      trip_context,
    }),
  });

  if (!res.ok) {
    removeThinking();
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
      if (event.type === "status") {
        if (event.session_id) setSessionId(event.session_id);
        updateThinking(event.label || "Working…");
      } else if (event.type === "done") {
        removeThinking();
        if (event.session_id) setSessionId(event.session_id);
        appendMessage("assistant", event.reply || "", event.cards || []);
      }
    }
  }
  removeThinking();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  appendMessage("user", message);
  input.value = "";
  sendBtn.disabled = true;

  try {
    await sendViaStream(message);
  } catch (err) {
    removeThinking();
    appendMessage("assistant", `Network error: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
});

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
welcome();
loadSettings();
input.focus();

// Keep Leaflet sized when the side panel resizes
const mapPanelEl = document.getElementById("mapPanel");
if (mapPanelEl && typeof ResizeObserver !== "undefined") {
  const ro = new ResizeObserver(() => bumpMapSize());
  ro.observe(mapPanelEl);
}
window.addEventListener("resize", bumpMapSize);
