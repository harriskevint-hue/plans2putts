/**
 * iGolf Connect -> ShadesCaddie (P2P) course-data transform
 * ----------------------------------------------------------
 * Converts an iGolf Connect course response into the exact P2P course JSON the
 * rangefinder reads (same schema as the hand-mapped White Horse course).
 *
 * WHY config-driven: iGolf's real JSON field names are behind a partner login and
 * not public. Everything provider-specific lives in FIELD_MAP and the small
 * accessor helpers. When the real key arrives and we see the actual field names,
 * we edit FIELD_MAP only — the geometry/logic below does not change.
 *
 * The non-trivial part: iGolf supplies greens/hazards as POLYGONS (perimeter
 * point arrays). P2P needs green front/center/back POINTS. We derive those from
 * the green polygon plus the hole's line of play (tee -> green), which is exactly
 * how a rangefinder defines "front" (nearest edge) and "back" (farthest edge).
 */

'use strict';

/* ============================================================
 * FIELD MAP — the ONLY thing that should change for the real API.
 * Each entry lists candidate field names; the accessor picks the first present.
 * Update these once we see iGolf's actual response.
 * ============================================================ */
const FIELD_MAP = {
  course: {
    nameKeys:   ['courseName', 'course_name', 'name', 'CourseName'],
    clubKeys:   ['clubName', 'club_name', 'ClubName'],
    holesKeys:  ['holes', 'Holes', 'holeList'],
    teesKeys:   ['tees', 'teeBoxes', 'TeeBoxes', 'teeboxes']
  },
  hole: {
    numberKeys: ['number', 'hole', 'holeNumber', 'HoleNumber', 'num'],
    parKeys:    ['par', 'Par'],
    hcpKeys:    ['handicap', 'index', 'strokeIndex', 'Handicap', 'hcp'],
    // tee location: either a point, or a polygon we take the centroid of
    teePointKeys:   ['teeCoords', 'tee', 'teeLocation', 'teePoint'],
    teePolyKeys:    ['teeboxPolygon', 'teePolygon', 'teebox'],
    // green: polygon (perimeter) and/or an explicit center/flag point
    greenPolyKeys:  ['greenPolygon', 'green', 'greenPerimeter', 'greenGeo'],
    greenCenterKeys:['greenCenter', 'flagcoords', 'flag', 'pin', 'center'],
    // hazards: list of {type/surfacetype, polygon|point}
    hazardsKeys:    ['hazards', 'features', 'polygons', 'surfaces']
  },
  point: {
    latKeys: ['lat', 'latitude', 'Lat', 'Latitude', 'y'],
    lngKeys: ['lng', 'long', 'lon', 'longitude', 'Lng', 'Longitude', 'x']
  },
  polygon: {
    // a polygon may be the array itself, or wrapped under one of these keys
    pointsKeys: ['polygon', 'points', 'coordinates', 'perimeter', 'vectors', 'geo'],
    typeKeys:   ['surfacetype', 'type', 'surfaceType', 'featureType', 'kind']
  },
  tee: {
    nameKeys:  ['name', 'tee_name', 'teeName', 'color', 'label'],
    yardKeys:  ['yards', 'total_yards', 'totalYards', 'yardage', 'length'],
    holeYardKeys: ['holes', 'holeYards', 'yardages']
  }
};

// Which iGolf surface types we treat as "hazard" for P2P (we only surface real trouble).
const HAZARD_SURFACE_TYPES = ['bunker', 'sand', 'water', 'hazard', 'penalty', 'lake', 'creek', 'pond'];
// Surface types we ignore for hazard purposes (not trouble to call out).
// (fairway, rough, green, teebox, cartpath, tree handled elsewhere or skipped)

/* ============================================================
 * Small accessors — provider-agnostic via FIELD_MAP
 * ============================================================ */
function firstKey(obj, keys) {
  if (!obj) return undefined;
  for (const k of keys) {
    if (obj[k] !== undefined && obj[k] !== null) return obj[k];
  }
  return undefined;
}

function toPoint(raw) {
  // Accept {lat,lng}, {latitude,longitude}, {x,y}, or [lng,lat] / [lat,lng] arrays.
  if (!raw) return null;
  if (Array.isArray(raw) && raw.length >= 2 && typeof raw[0] === 'number') {
    // Ambiguous order. GeoJSON is [lng,lat]; iGolf unknown. Default GeoJSON, flag later.
    return { lat: raw[1], lng: raw[0] };
  }
  const lat = firstKey(raw, FIELD_MAP.point.latKeys);
  const lng = firstKey(raw, FIELD_MAP.point.lngKeys);
  if (typeof lat !== 'number' || typeof lng !== 'number') return null;
  return { lat: lat, lng: lng };
}

function polygonPoints(rawPoly) {
  // rawPoly may be an array of points, or an object wrapping the array.
  let arr = rawPoly;
  if (!Array.isArray(rawPoly)) {
    arr = firstKey(rawPoly, FIELD_MAP.polygon.pointsKeys);
  }
  if (!Array.isArray(arr)) return [];
  return arr.map(toPoint).filter(Boolean);
}

/* ============================================================
 * Geometry helpers
 * ============================================================ */
const R = 6371000; // earth radius m
function toRad(d) { return d * Math.PI / 180; }

function haversine(a, b) {
  const dLat = toRad(b.lat - a.lat), dLng = toRad(b.lng - a.lng);
  const s = Math.sin(dLat/2)**2 +
            Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng/2)**2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

function centroid(points) {
  if (!points.length) return null;
  let lat = 0, lng = 0;
  for (const p of points) { lat += p.lat; lng += p.lng; }
  return { lat: lat / points.length, lng: lng / points.length };
}

/**
 * Derive green front/center/back from the green polygon and the line of play.
 * - center = polygon centroid (or explicit center/flag point if provided)
 * - front  = polygon vertex NEAREST to the tee (along line of play)
 * - back   = polygon vertex FARTHEST from the tee
 * This matches how a rangefinder defines front/back: nearest/farthest green edge
 * from where the golfer is playing.
 */
function deriveGreen(greenPolyPts, explicitCenter, teePoint) {
  const center = explicitCenter || centroid(greenPolyPts);
  if (!center) return null;

  // Reference for "near/far": the tee if we have it, else fall back to centroid
  // projected — but without a tee we can't define front/back meaningfully, so we
  // return center for all three (still usable; front/back refine once tee known).
  if (!teePoint || !greenPolyPts.length) {
    return { front: center, center: center, back: center };
  }

  let front = greenPolyPts[0], back = greenPolyPts[0];
  let dMin = Infinity, dMax = -Infinity;
  for (const p of greenPolyPts) {
    const d = haversine(teePoint, p);
    if (d < dMin) { dMin = d; front = p; }
    if (d > dMax) { dMax = d; back = p; }
  }
  return { front: front, center: center, back: back };
}

/* ============================================================
 * Main transform
 * ============================================================ */
function transformCourse(igolf, opts) {
  opts = opts || {};
  const courseName =
    firstKey(igolf, FIELD_MAP.course.nameKeys) ||
    firstKey(igolf, FIELD_MAP.course.clubKeys) ||
    opts.fallbackName || 'Unknown Course';

  const rawHoles = firstKey(igolf, FIELD_MAP.course.holesKeys) || [];
  if (!Array.isArray(rawHoles) || !rawHoles.length) {
    throw new Error('transformCourse: no holes array found (check FIELD_MAP.course.holesKeys against real response)');
  }

  const holes = rawHoles.map(function (rh, i) {
    const number = firstKey(rh, FIELD_MAP.hole.numberKeys);
    const par = firstKey(rh, FIELD_MAP.hole.parKeys);
    const hcp = firstKey(rh, FIELD_MAP.hole.hcpKeys);

    // Tee point: explicit point preferred, else centroid of teebox polygon
    let tee = toPoint(firstKey(rh, FIELD_MAP.hole.teePointKeys));
    if (!tee) {
      const teePoly = firstKey(rh, FIELD_MAP.hole.teePolyKeys);
      if (teePoly) tee = centroid(polygonPoints(teePoly));
    }

    // Green: polygon + optional explicit center/flag
    const greenPolyPts = polygonPoints(firstKey(rh, FIELD_MAP.hole.greenPolyKeys));
    const explicitCenter = toPoint(firstKey(rh, FIELD_MAP.hole.greenCenterKeys));
    const green = deriveGreen(greenPolyPts, explicitCenter, tee) ||
                  { front: null, center: null, back: null };

    // Hazards: filter to trouble surface types, reduce each polygon to its centroid
    const hazards = [];
    const rawHazards = firstKey(rh, FIELD_MAP.hole.hazardsKeys) || [];
    if (Array.isArray(rawHazards)) {
      let bunkerN = 0, waterN = 0, otherN = 0;
      for (const hz of rawHazards) {
        const stype = String(firstKey(hz, FIELD_MAP.polygon.typeKeys) || '').toLowerCase();
        if (!HAZARD_SURFACE_TYPES.some(function (t) { return stype.indexOf(t) !== -1; })) continue;
        const pts = polygonPoints(hz);
        const c = pts.length ? centroid(pts) : toPoint(hz);
        if (!c) continue;
        let label;
        if (stype.indexOf('water') !== -1 || stype.indexOf('lake') !== -1 ||
            stype.indexOf('pond') !== -1 || stype.indexOf('creek') !== -1) {
          label = 'water ' + (++waterN);
        } else if (stype.indexOf('bunker') !== -1 || stype.indexOf('sand') !== -1) {
          label = 'bunker ' + (++bunkerN);
        } else {
          label = 'hazard ' + (++otherN);
        }
        hazards.push({ label: label, lat: c.lat, lng: c.lng });
      }
    }

    return {
      hole: (typeof number === 'number') ? number : (i + 1),
      par: (typeof par === 'number') ? par : null,
      handicap: (typeof hcp === 'number') ? hcp : null, // bonus: P2P files lacked this
      tee: tee || null,
      green: {
        front: green.front || null,
        center: green.center || null,
        back: green.back || null
      },
      hazards: hazards,
      dogleg: null,   // iGolf has center-line path; dogleg derivation is a later refinement
      layups: []
    };
  });

  // Tees (scorecard layer): name + total + per-hole yardages, mapped to P2P shape
  const out = { course: courseName, holes: holes };
  const rawTees = firstKey(igolf, FIELD_MAP.course.teesKeys);
  const tees = transformTees(rawTees);
  if (tees) out.tees = tees;

  return out;
}

function transformTees(rawTees) {
  if (!rawTees) return null;
  // rawTees may be an array of teebox objects, or an object keyed by tee.
  const list = Array.isArray(rawTees) ? rawTees : Object.values(rawTees);
  if (!list.length) return null;
  const out = {};
  list.forEach(function (t, idx) {
    const name = firstKey(t, FIELD_MAP.tee.nameKeys) || ('Tee ' + (idx + 1));
    const total = firstKey(t, FIELD_MAP.tee.yardKeys) || null;
    let holeYards = firstKey(t, FIELD_MAP.tee.holeYardKeys);
    // hole yardages may be array of numbers or array of {yardage}
    if (Array.isArray(holeYards)) {
      holeYards = holeYards.map(function (h) {
        return (typeof h === 'number') ? h : (firstKey(h, ['yardage','yards','length']) || null);
      });
    } else {
      holeYards = [];
    }
    const key = String(name).toLowerCase().replace(/[^a-z0-9]+/g, '') || ('tee' + idx);
    out[key] = { label: String(name), total: total, holes: holeYards };
  });
  return out;
}

/* ============================================================
 * Validation — never ship a course that would mislead a golfer
 * ============================================================ */
function validateCourse(p2p) {
  const issues = [];
  if (!p2p.course) issues.push('missing course name');
  if (!Array.isArray(p2p.holes) || !p2p.holes.length) issues.push('no holes');
  (p2p.holes || []).forEach(function (h) {
    if (h.par == null) issues.push('hole ' + h.hole + ': missing par');
    if (!h.green || !h.green.center) issues.push('hole ' + h.hole + ': missing green center (no distance possible)');
    if (!h.tee) issues.push('hole ' + h.hole + ': missing tee (front/back not reliable)');
  });
  return { ok: issues.length === 0, issues: issues };
}

module.exports = {
  transformCourse: transformCourse,
  validateCourse: validateCourse,
  // exported for unit tests / future tuning
  _internal: { deriveGreen, centroid, haversine, toPoint, polygonPoints, FIELD_MAP }
};
