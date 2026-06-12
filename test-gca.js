const { transformScorecard, validatePartial } = require('./gca-transform');
let pass=0, fail=0;
function ok(n,c,x){ if(c){console.log("PASS",n);pass++;} else {console.log("FAIL",n,x!==undefined?JSON.stringify(x):"");fail++;} }

// Fixture matching the EXACT documented schema from openapi.yml
const gcaResponse = {
  id: 99,
  club_name: "Murray Golf Club",
  course_name: "Course No. 1",
  location: { address:"124 Golf Course Lane", city:"Murray", state:"KY",
              country:"United States", latitude:39.621742, longitude:-80.34734 },
  tees: {
    male: [
      { tee_name:"Blue", course_rating:75.7, slope_rating:132, total_yards:6348,
        number_of_holes:18, par_total:72,
        holes:[ {par:4,yardage:484,handicap:9},{par:3,yardage:189,handicap:17},
                {par:5,yardage:587,handicap:2},{par:4,yardage:410,handicap:5},
                {par:4,yardage:401,handicap:7},{par:3,yardage:175,handicap:15},
                {par:4,yardage:430,handicap:3},{par:5,yardage:540,handicap:11},
                {par:4,yardage:395,handicap:13},{par:4,yardage:420,handicap:8},
                {par:3,yardage:195,handicap:16},{par:5,yardage:560,handicap:4},
                {par:4,yardage:415,handicap:6},{par:4,yardage:405,handicap:10},
                {par:3,yardage:180,handicap:18},{par:5,yardage:545,handicap:1},
                {par:4,yardage:425,handicap:12},{par:4,yardage:392,handicap:14} ] },
      { tee_name:"White", course_rating:72.1, slope_rating:124, total_yards:5900,
        number_of_holes:18, par_total:72,
        holes: Array.from({length:18}, (_,i)=>({par:[4,3,5,4,4,3,4,5,4,4,3,5,4,4,3,5,4,4][i], yardage:400-i, handicap:i+1})) }
    ],
    female: [
      { tee_name:"Red", course_rating:70.0, slope_rating:118, total_yards:5200,
        number_of_holes:18, par_total:72,
        holes: Array.from({length:18}, (_,i)=>({par:[4,3,5,4,4,3,4,5,4,4,3,5,4,4,3,5,4,4][i], yardage:350-i, handicap:i+1})) }
    ]
  }
};

const out = transformScorecard(gcaResponse);
ok("course name combines club+course", out.course === "Murray Golf Club — Course No. 1", out.course);
ok("18 holes", out.holes.length === 18);
ok("par from longest tee (Blue) hole1", out.holes[0].par === 4, out.holes[0].par);
ok("handicap carried hole3", out.holes[2].handicap === 2, out.holes[2].handicap);
ok("coords null (needs mapping)", out.holes[0].tee === null && out.holes[0].green.center === null);
ok("blue tee total", out.tees.blue.total === 6348, out.tees.blue && out.tees.blue.total);
ok("blue tee per-hole yardage", out.tees.blue.holes[2] === 587, out.tees.blue.holes[2]);
ok("blue rating/slope bonus", out.tees.blue.rating === 75.7 && out.tees.blue.slope === 132);
ok("white tee present", !!out.tees.white && out.tees.white.total === 5900);
ok("meta says coordinates none", out._meta.coordinates === "none");
ok("meta has property latlng", out._meta.property && Math.abs(out._meta.property.lat-39.621742)<1e-6);

// female tee selection
const outF = transformScorecard(gcaResponse, { gender:'female' });
ok("female selects Red set", !!outF.tees.red, Object.keys(outF.tees));

// validation
const v = validatePartial(out);
ok("scorecard valid", v.scorecardOk, v.issues);
ok("flagged needs mapping", v.needsMapping === true);
ok("pars filled count 18", v.parsFilled === 18, v.parsFilled);

// error path: a bare search hit (no tees) should throw clearly
let threw=false; try { transformScorecard({ id:34, club_name:"X" }); } catch(e){ threw = /missing tees/.test(e.message); }
ok("search-hit without tees throws clear error", threw);

console.log("\n"+pass+" passed, "+fail+" failed");
process.exit(fail?1:0);
