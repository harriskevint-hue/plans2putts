#!/usr/bin/env node
/**
 * GolfCourseAPI LIVE test — Windows-friendly version.
 *
 * Run on YOUR computer (Node 18+). Two ways to pass the key:
 *   node live-test.js YOURAPIKEY "white horse"
 *   (or set GCA_KEY env var and omit the key)
 *
 * It searches the term, fetches the first match's full course, prints the
 * scorecard, runs the P2P transform, reports whether per-hole coordinates
 * exist, and SAVES everything to gca-results.txt for easy sharing.
 */
'use strict';
const fs = require('fs');
const { transformScorecard, validatePartial } = require('./gca-transform');

// ---- arg parsing: optional key first, then search term ----
let args = process.argv.slice(2);
let KEY = process.env.GCA_KEY || '';
if (args[0] && /^[A-Z0-9]{20,}$/i.test(args[0])) { KEY = args[0]; args = args.slice(1); }
const term = args.join(' ').trim() || 'white horse';
if (!KEY) {
  console.error('No API key. Run:  node live-test.js YOURAPIKEY "course name"');
  process.exit(1);
}

const BASE = 'https://api.golfcourseapi.com';
const H = { 'Authorization': 'Key ' + KEY };

// capture all output to a results file too
const lines = [];
function out(s) { s = String(s); console.log(s); lines.push(s); }

async function main() {
  out('==================================================');
  out('GolfCourseAPI live test  ' + new Date().toISOString());
  out('Search term: "' + term + '"');
  out('==================================================');

  // 1) SEARCH
  const s = await fetch(BASE + '/v1/search?search_query=' + encodeURIComponent(term), { headers: H });
  if (!s.ok) { out('SEARCH FAILED: HTTP ' + s.status + ' ' + (await s.text()).slice(0,200)); return finish(1); }
  const sj = await s.json();
  const courses = sj.courses || [];
  out('\n[1] SEARCH RESULTS: ' + courses.length + ' match(es)');
  if (!courses.length) { out('No matches for "' + term + '". Course may not be in their database.'); return finish(0); }
  courses.slice(0, 5).forEach(function (c, i) {
    out('  [' + i + '] id=' + c.id + '  ' + (c.club_name || '') + ' / ' + (c.course_name || '') +
        '  — ' + ((c.location && c.location.city) || '?') + ', ' + ((c.location && c.location.state) || '?'));
  });

  // 2) FETCH full course (first match)
  const id = courses[0].id;
  out('\n[2] FETCHING full course id=' + id + ' ...');
  const r = await fetch(BASE + '/v1/courses/' + id, { headers: H });
  if (!r.ok) { out('FETCH FAILED: HTTP ' + r.status + ' ' + (await r.text()).slice(0,200)); return finish(1); }
  const raw = await r.json();
  const course = raw.course || raw;   // some responses wrap in {course:{...}}

  out('Top-level fields returned: ' + Object.keys(course).join(', '));
  if (course.location) out('Property location (ONE point, not per-hole): lat ' +
      course.location.latitude + ', lng ' + course.location.longitude);

  // 3) COORDINATE CHECK — the decisive question
  out('\n[3] PER-HOLE COORDINATE CHECK (the decisive question)');
  let hasCoords = false;
  const maleTees = (course.tees && course.tees.male) || [];
  if (maleTees[0] && maleTees[0].holes && maleTees[0].holes[0]) {
    const h1 = maleTees[0].holes[0];
    out('Hole 1 fields: ' + Object.keys(h1).join(', ') + '  ->  ' + JSON.stringify(h1));
    hasCoords = maleTees[0].holes.some(function (h) {
      return h.lat || h.latitude || h.green || h.coordinates || h.tee || h.polygon;
    });
  }
  out('Per-hole GPS coordinates present?  ' + (hasCoords ? 'YES (unexpected!)' : 'NO — scorecard data only, as documented'));

  // 4) TRANSFORM to P2P scorecard layer
  out('\n[4] TRANSFORM TO P2P (scorecard layer)');
  try {
    const p2p = transformScorecard(course);
    const v = validatePartial(p2p);
    out('Course name: ' + p2p.course);
    out('Holes: ' + p2p.holes.length + ' | pars filled: ' + v.parsFilled + '/' + p2p.holes.length);
    out('Pars:      ' + p2p.holes.map(function (h) { return h.par; }).join(','));
    out('Handicaps: ' + p2p.holes.map(function (h) { return h.handicap; }).join(','));
    Object.keys(p2p.tees).forEach(function (k) {
      const t = p2p.tees[k];
      out('Tee ' + t.label + ': total ' + t.total + 'y, rating ' + t.rating + ', slope ' + t.slope);
    });
    out('\nVERDICT:');
    out('  Scorecard layer: ' + (v.scorecardOk ? 'USABLE — can auto-fill pars/yardages/handicaps' : 'INCOMPLETE: ' + v.issues.join('; ')));
    out('  Distances/rangefinder: ' + (hasCoords ? 'POSSIBLE — re-evaluate!' : 'NOT possible from this API — coordinates must come from mapping or iGolf'));
  } catch (e) {
    out('Transform error: ' + e.message);
  }
  return finish(0);
}

function finish(code) {
  fs.writeFileSync('gca-results.txt', lines.join('\n') + '\n');
  out('\nSaved full results to gca-results.txt — upload that file back to Claude.');
  process.exit(code);
}

main().catch(function (e) { out('ERROR: ' + (e.message || e)); finish(1); });
