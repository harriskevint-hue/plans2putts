const { transformCourse, validateCourse, _internal } = require('./igolf-transform');
const { haversine, deriveGreen } = _internal;

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { console.log("PASS", name); pass++; }
  else { console.log("FAIL", name, extra !== undefined ? "-> "+JSON.stringify(extra) : ""); fail++; }
}

// ---- Build a synthetic iGolf-shaped course ----
// A short par-3 playing roughly NORTH: tee south, green north.
// Green polygon is a small ring; the SOUTH edge should become "front" (nearest tee),
// the NORTH edge should become "back".
const tee = { lat: 47.7600, lng: -122.5300 };
// green centered ~ north of tee
const gC = { lat: 47.7630, lng: -122.5300 };
const greenRing = [
  { lat: 47.7628, lng: -122.5301 }, // south-ish (front, nearer tee)
  { lat: 47.7628, lng: -122.5299 },
  { lat: 47.7632, lng: -122.5299 }, // north-ish (back, farther)
  { lat: 47.7632, lng: -122.5301 }
];
const bunker = [
  { lat: 47.7625, lng: -122.5302 },
  { lat: 47.7626, lng: -122.5302 },
  { lat: 47.7626, lng: -122.5301 }
];

const igolfCourse = {
  course_name: "Test Pines GC",
  tees: [
    { tee_name: "Blue", total_yards: 3100, holes: [165, 0,0,0,0,0,0,0,0] },
    { tee_name: "White", total_yards: 2900, holes: [150, 0,0,0,0,0,0,0,0] }
  ],
  holes: [
    {
      number: 1, par: 3, handicap: 7,
      teebox: { polygon: [ {lat:47.7599,lng:-122.5301},{lat:47.7601,lng:-122.5299} ] },
      green: { polygon: greenRing },
      hazards: [
        { surfacetype: "bunker", polygon: bunker },
        { surfacetype: "fairway", polygon: [ {lat:47.7610,lng:-122.5300} ] } // should be ignored
      ]
    }
  ]
};

// ---- Run transform ----
const out = transformCourse(igolfCourse);

ok("course name", out.course === "Test Pines GC", out.course);
ok("one hole", out.holes.length === 1);
const h = out.holes[0];
ok("par carried", h.par === 3, h.par);
ok("handicap carried (bonus)", h.handicap === 7, h.handicap);
ok("tee derived from teebox polygon centroid", h.tee && Math.abs(h.tee.lat - 47.7600) < 0.001, h.tee);
ok("green center present", !!h.green.center);

// Geometry: front must be nearer to tee than back
const dFront = haversine(h.tee, h.green.front);
const dBack  = haversine(h.tee, h.green.back);
ok("front nearer than back (line-of-play geometry)", dFront < dBack, {dFront: Math.round(dFront), dBack: Math.round(dBack)});
ok("center between front and back", (function(){
  const dC = haversine(h.tee, h.green.center);
  return dC > dFront - 5 && dC < dBack + 5;
})());

// Hazards: only the bunker should survive, fairway ignored
ok("one hazard (bunker kept, fairway dropped)", h.hazards.length === 1, h.hazards);
ok("hazard labeled bunker", h.hazards[0].label.indexOf("bunker") === 0, h.hazards[0].label);

// Tees mapped
ok("tees mapped", out.tees && out.tees.blue && out.tees.blue.total === 3100, out.tees);
ok("tee per-hole yardage", out.tees.blue.holes[0] === 165, out.tees && out.tees.blue.holes[0]);

// Validation should flag nothing fatal here
const v = validateCourse(out);
ok("validation ok", v.ok, v.issues);

// ---- Edge case: no tee point -> front/center/back all center, no crash ----
const noTee = transformCourse({
  course_name: "Edge GC",
  holes: [ { number:1, par:4, green:{ polygon: greenRing } } ]
});
ok("no-tee hole: green center still set", !!noTee.holes[0].green.center);
ok("no-tee hole: validation flags missing tee", !validateCourse(noTee).ok);

// ---- Edge case: alternate field names (simulate different real API) ----
const altShape = transformCourse({
  name: "Alt Fields GC",
  Holes: [ { holeNumber:1, Par:5, flag:{latitude:47.7630,longitude:-122.5300},
             green:{ coordinates: greenRing },
             teePoint:{latitude:47.7600,longitude:-122.5300} } ]
});
ok("alt field names: name", altShape.course === "Alt Fields GC", altShape.course);
ok("alt field names: par", altShape.holes[0].par === 5, altShape.holes[0].par);
ok("alt field names: explicit flag used as center", 
   Math.abs(altShape.holes[0].green.center.lat - 47.7630) < 0.0001, altShape.holes[0].green.center);

console.log("\n" + pass + " passed, " + fail + " failed");
process.exit(fail ? 1 : 0);
