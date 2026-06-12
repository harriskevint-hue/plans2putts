/**
 * GolfCourseAPI -> ShadesCaddie (P2P) SCORECARD-LAYER transform
 * ------------------------------------------------------------
 * Built against the documented OpenAPI schema (openapi.yml the user uploaded).
 *
 * IMPORTANT: GolfCourseAPI has NO per-hole green/tee/hazard coordinates — only
 * one property-level lat/lng, plus scorecard data (par, yardage, handicap) and
 * tee ratings. So this transform produces a PARTIAL P2P course: pars + tee
 * yardages + handicaps filled in, but coordinates left null for the mapper.
 *
 * This is exactly the "Tier 2 partial / scorecard-filler" role: it cuts manual
 * data entry roughly in half (no typing pars/yardages/handicaps), and the
 * subscriber only maps coordinates.
 *
 * Documented schema (from openapi.yml):
 *   Course { id, club_name, course_name, location{address,city,state,country,latitude,longitude},
 *            tees { male:[TeeBox], female:[TeeBox] } }
 *   TeeBox { tee_name, course_rating, slope_rating, total_yards, number_of_holes,
 *            par_total, holes:[ {par, yardage, handicap} ] }
 */
'use strict';

function pickTee(tees, prefer) {
  // tees = { male:[...], female:[...] }. Prefer male set by default; allow override.
  if (!tees) return null;
  var set = (prefer === 'female') ? tees.female : tees.male;
  if (!set || !set.length) set = tees.male || tees.female || [];
  return set;
}

/**
 * Transform a GolfCourseAPI Course object into a partial P2P course.
 * @param {object} gca  - the Course response
 * @param {object} opts - { gender:'male'|'female', teeIndex:int }
 */
function transformScorecard(gca, opts) {
  opts = opts || {};
  if (!gca || !gca.tees) throw new Error('transformScorecard: missing tees (need a full /v1/courses/{id} response, not a search hit)');

  var name = gca.course_name || gca.club_name || 'Unknown Course';
  if (gca.club_name && gca.course_name && gca.club_name !== gca.course_name) {
    name = gca.club_name + ' — ' + gca.course_name;
  }

  var teeSet = pickTee(gca.tees, opts.gender);
  if (!teeSet || !teeSet.length) throw new Error('no tee boxes found');

  // Use the requested tee (or the longest as a sensible default) to define hole pars.
  var primary = (typeof opts.teeIndex === 'number' && teeSet[opts.teeIndex])
    ? teeSet[opts.teeIndex]
    : teeSet.slice().sort(function (a,b){ return (b.total_yards||0)-(a.total_yards||0); })[0];

  var holeCount = (primary.holes && primary.holes.length) || primary.number_of_holes || 18;

  var holes = [];
  for (var i = 0; i < holeCount; i++) {
    var hr = (primary.holes && primary.holes[i]) || {};
    holes.push({
      hole: i + 1,
      par: (typeof hr.par === 'number') ? hr.par : null,
      handicap: (typeof hr.handicap === 'number') ? hr.handicap : null,
      tee: null,                                  // <-- coordinates: must be mapped
      green: { front: null, center: null, back: null },
      hazards: [],
      dogleg: null,
      layups: []
    });
  }

  // Build P2P tees{} from every tee box (label, total, per-hole yardages).
  var tees = {};
  teeSet.forEach(function (tb, idx) {
    var label = tb.tee_name || ('Tee ' + (idx+1));
    var key = String(label).toLowerCase().replace(/[^a-z0-9]+/g,'') || ('tee'+idx);
    var yards = (tb.holes || []).map(function (h){ return (typeof h.yardage==='number')?h.yardage:null; });
    tees[key] = {
      label: label,
      total: tb.total_yards || null,
      holes: yards,
      rating: tb.course_rating || null,   // bonus scorecard data
      slope: tb.slope_rating || null
    };
  });

  var out = {
    course: name,
    holes: holes,
    tees: tees,
    _meta: {
      source: 'golfcourseapi',
      coordinates: 'none',                 // explicit: needs Tier-3 mapping
      property: gca.location ? { lat: gca.location.latitude, lng: gca.location.longitude } : null,
      note: 'Scorecard layer only. Map green/tee/hazard coordinates to enable distances.'
    }
  };
  return out;
}

function validatePartial(p2p) {
  var issues = [];
  if (!p2p.course) issues.push('missing course name');
  if (!p2p.holes || !p2p.holes.length) issues.push('no holes');
  var parsFilled = (p2p.holes||[]).filter(function(h){ return h.par!=null; }).length;
  if (parsFilled === 0) issues.push('no pars filled');
  // Coordinates intentionally absent — this is a partial. Always needs self-map.
  return { scorecardOk: issues.length === 0, needsMapping: true, issues: issues, parsFilled: parsFilled };
}

module.exports = { transformScorecard: transformScorecard, validatePartial: validatePartial, pickTee: pickTee };
