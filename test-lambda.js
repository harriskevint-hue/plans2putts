// Test the Lambda handler by mocking global fetch and env.
const path = require('path');

function freshHandler(env) {
  // reset module cache so CONFIG re-reads env
  delete require.cache[require.resolve('./lambda-course-proxy.js')];
  Object.assign(process.env, env);
  return require('./lambda-course-proxy.js').handler;
}

let pass=0, fail=0;
function ok(n,c,x){ if(c){console.log("PASS",n);pass++;} else {console.log("FAIL",n, x!==undefined?JSON.stringify(x):"");fail++;} }

const greenRing = [
  {lat:47.7628,lng:-122.5301},{lat:47.7628,lng:-122.5299},
  {lat:47.7632,lng:-122.5299},{lat:47.7632,lng:-122.5301}
];
const fakeCourse = {
  course_name: "Mock National",
  tees: [{ tee_name:"Blue", total_yards:6500, holes:[400] }],
  holes: [{ number:1, par:4, handicap:5,
    teebox:{polygon:[{lat:47.7600,lng:-122.5300}]},
    green:{polygon:greenRing},
    hazards:[{surfacetype:"water", polygon:[{lat:47.7615,lng:-122.5300}]}] }]
};

(async function () {
  // 1) No API key -> 503 self-map fallback
  let h = freshHandler({ IGOLF_API_KEY: "" });
  let r = await h({ queryStringParameters: { q: "anything" } });
  let b = JSON.parse(r.body);
  ok("no key -> 503", r.statusCode === 503, r.statusCode);
  ok("no key -> fallback self-map", b.fallback === "self-map", b);

  // 2) With key + mocked fetch (search then course) -> 200 valid P2P
  global.fetch = async function (url) {
    if (url.indexOf("/search") !== -1) {
      return { ok:true, json: async()=>({ courses:[{id: 123}] }) };
    }
    return { ok:true, json: async()=> fakeCourse };
  };
  h = freshHandler({ IGOLF_API_KEY: "test-key", IGOLF_BASE_URL: "https://mock/connect/v1" });
  r = await h({ queryStringParameters: { q: "mock national" } });
  b = JSON.parse(r.body);
  ok("with key -> 200", r.statusCode === 200, r.statusCode);
  ok("source igolf", b.source === "igolf", b.source);
  ok("transformed course name", b.course && b.course.course === "Mock National", b.course && b.course.course);
  ok("hole par present", b.course.holes[0].par === 4, b.course.holes[0].par);
  ok("green center derived", !!b.course.holes[0].green.center);
  ok("water hazard kept", b.course.holes[0].hazards.length === 1 && b.course.holes[0].hazards[0].label.indexOf("water")===0, b.course.holes[0].hazards);
  ok("valid true", b.valid === true, b.issues);

  // 3) Direct id fetch path
  r = await h({ queryStringParameters: { id: "123" } });
  b = JSON.parse(r.body);
  ok("by id -> 200", r.statusCode === 200, r.statusCode);

  // 4) Provider error -> self-map fallback, not a hard crash
  global.fetch = async function(){ return { ok:false, status:500, text: async()=>"boom" }; };
  h = freshHandler({ IGOLF_API_KEY:"test-key" });
  r = await h({ queryStringParameters:{ q:"down" } });
  b = JSON.parse(r.body);
  ok("provider error -> fallback self-map", b.fallback === "self-map", b);

  // 5) Missing params -> 400
  r = await h({ queryStringParameters:{} });
  ok("no params -> 400", r.statusCode === 400, r.statusCode);

  console.log("\n"+pass+" passed, "+fail+" failed");
  process.exit(fail?1:0);
})();
