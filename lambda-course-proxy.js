/**
 * ShadesCaddie course-data Lambda (Tier 2 proxy)
 * ----------------------------------------------
 * Sits between the app and iGolf Connect. Responsibilities:
 *   1. Keep iGolf credentials server-side (NEVER in the client).
 *   2. Call iGolf Connect for a requested course.
 *   3. Transform the response into P2P course JSON (igolf-transform.js).
 *   4. Validate, cache, and return — or return a clear "needs mapping" signal
 *      so the app falls through to Tier 3 (self-mapping) per COURSE-DATA-STRATEGY.
 *
 * Deploy: Node 18+ Lambda behind API Gateway (GET /course?id=... or ?q=...).
 * Credentials come from environment variables / Secrets Manager — not code.
 *
 * NOTE: the exact iGolf request URL, auth scheme (header key vs. AWS SigV4), and
 * field names are confirmed once we have a partner key. Those live in the clearly
 * marked CONFIG block and FIELD_MAP (in igolf-transform.js) — edit there only.
 */

'use strict';

const { transformCourse, validateCourse } = require('./igolf-transform');

// ---- CONFIG: adjust to iGolf's real API once credentials/docs are in hand ----
const CONFIG = {
  igolfBaseUrl: process.env.IGOLF_BASE_URL || 'https://api.igolf.example/connect/v1',
  // Auth style: 'header' (simple API key) or 'sigv4' (AWS-style signing).
  // iGolf Connect docs will tell us; default to header until confirmed.
  authStyle: process.env.IGOLF_AUTH_STYLE || 'header',
  apiKeyHeaderName: process.env.IGOLF_KEY_HEADER || 'Authorization',
  // Endpoint path templates — adjust to real iGolf routes.
  searchPath: '/courses/search?q={q}',
  coursePath: '/courses/{id}',
  // Simple in-memory cache TTL (Lambda warm-container reuse). DynamoDB cache is Phase 4+.
  cacheTtlMs: 1000 * 60 * 60 // 1 hour
};

// Secrets pulled from env (set via Lambda config / Secrets Manager).
const IGOLF_API_KEY = process.env.IGOLF_API_KEY || '';

// Tiny warm-container cache (best-effort; not durable).
const _cache = new Map();
function cacheGet(k) {
  const e = _cache.get(k);
  if (!e) return null;
  if (Date.now() - e.t > CONFIG.cacheTtlMs) { _cache.delete(k); return null; }
  return e.v;
}
function cacheSet(k, v) { _cache.set(k, { v: v, t: Date.now() }); }

function resp(status, bodyObj) {
  return {
    statusCode: status,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',          // tighten to ShadesCaddie.com in prod
      'Cache-Control': 'public, max-age=3600'
    },
    body: JSON.stringify(bodyObj)
  };
}

async function callIgolf(path) {
  const url = CONFIG.igolfBaseUrl + path;
  const headers = {};
  if (CONFIG.authStyle === 'header') {
    headers[CONFIG.apiKeyHeaderName] = IGOLF_API_KEY;
  }
  // NOTE: if iGolf requires AWS SigV4 (like Golfbert did), swap this fetch for a
  // signed request here. Isolated to this function on purpose.
  const r = await fetch(url, { headers: headers });
  if (!r.ok) {
    const text = await r.text().catch(function () { return ''; });
    const err = new Error('iGolf ' + r.status + ': ' + text.slice(0, 200));
    err.status = r.status;
    throw err;
  }
  return r.json();
}

exports.handler = async function (event) {
  try {
    const qs = (event && event.queryStringParameters) || {};
    const id = qs.id;
    const q = qs.q;

    if (!id && !q) {
      return resp(400, { error: 'Provide ?id=<courseId> or ?q=<searchText>' });
    }

    const cacheKey = id ? ('id:' + id) : ('q:' + q.toLowerCase());
    const cached = cacheGet(cacheKey);
    if (cached) return resp(200, Object.assign({ cached: true }, cached));

    if (!IGOLF_API_KEY) {
      // No key configured yet — be explicit so the app falls to Tier 3 (mapping).
      return resp(503, {
        error: 'course-data provider not configured',
        fallback: 'self-map',   // app should open the mapper
        message: 'No API credentials set; use Tier 3 self-mapping.'
      });
    }

    // 1) Resolve to a course id if only a search term was given.
    let courseId = id;
    if (!courseId && q) {
      const searchPath = CONFIG.searchPath.replace('{q}', encodeURIComponent(q));
      const search = await callIgolf(searchPath);
      const list = search.courses || search.results || search;
      if (!Array.isArray(list) || !list.length) {
        return resp(404, { error: 'no match', q: q, fallback: 'self-map' });
      }
      courseId = list[0].id || list[0].courseId || list[0].course_id;
    }

    // 2) Fetch the full course and transform.
    const coursePath = CONFIG.coursePath.replace('{id}', encodeURIComponent(courseId));
    const raw = await callIgolf(coursePath);
    const p2p = transformCourse(raw, { fallbackName: q || ('Course ' + courseId) });

    // 3) Validate. If greens/tees are missing, tell the app to self-map.
    const v = validateCourse(p2p);
    const payload = { course: p2p, source: 'igolf', valid: v.ok, issues: v.issues };
    if (!v.ok) payload.fallback = 'self-map';

    cacheSet(cacheKey, payload);
    return resp(200, payload);

  } catch (e) {
    const status = e.status === 401 ? 502 : (e.status || 500);
    // On any provider failure, signal self-map so the subscriber is never stuck.
    return resp(status, {
      error: String(e.message || e),
      fallback: 'self-map'
    });
  }
};
