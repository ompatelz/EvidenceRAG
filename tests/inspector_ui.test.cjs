const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { test } = require("node:test");
const vm = require("node:vm");

test("inspector labels withheld evidence and sends the visual requirement", async () => {
  const elements = new Map();
  const createElement = () => ({
    children: [],
    handlers: {},
    classList: { toggle() {}, remove() {} },
    addEventListener(name, handler) { this.handlers[name] = handler; },
    append(...children) { this.children.push(...children); },
    replaceChildren() { this.children = []; }
  });
  const get = (id) => {
    if (!elements.has(id)) elements.set(id, createElement());
    return elements.get(id);
  };
  const read = (element) => [element.textContent, ...element.children.map(read)].join(" ");
  const buttons = (element) => [
    ...(element.className === "citation-button" ? [element.textContent] : []),
    ...element.children.flatMap(buttons)
  ];
  const conflict = {
    status: "insufficient_evidence",
    reason: "conflicting_evidence",
    claims: [{
      text: "The draft claim",
      citation_status: "valid",
      rule_support: "not_assessed",
      semantic_support: { conflicting: true },
      citations: [
        { evidence_id: "first", page_index: 0, semantic_support: "supported" },
        { evidence_id: "second", page_index: 1, semantic_support: "contradicted" }
      ]
    }]
  };
  let result = conflict;
  let query;
  async function fetch(url, options) {
    let body = {};
    if (url.endsWith("/ingestions")) {
      body = { state: "ready", document_id: "fixture", document_sha256: "hash", page_count: 2 };
    } else if (url.endsWith("/evidence")) {
      body = { units: [] };
    } else if (url.endsWith("/query")) {
      query = JSON.parse(options.body);
      body = { result, mode: "bm25", retrieval: [], retrieval_status: "ok", timings_ms: {} };
    }
    return { ok: true, json: async () => body };
  }
  vm.runInNewContext(readFileSync("src/evidence_rag/ui/app.js", "utf8"), {
    document: { getElementById: get, createElement },
    fetch,
    FormData: class { append() {} }
  });
  const event = { preventDefault() {} };
  get("pdf-file").files = [{ name: "fixture.pdf" }];
  get("permission").checked = true;
  await get("upload-form").handlers.submit(event);
  get("question").value = "Which source is correct?";
  get("mode").value = "bm25";
  get("requires-visual").checked = false;
  await get("query-form").handlers.submit(event);
  assert.match(read(get("answer")), /Withheld draft claims/);
  assert.deepEqual(buttons(get("answer")), ["Estimated support · p. 1", "Estimated contradiction · p. 2"]);
  assert.equal(query.requires_visual_evidence, false);

  result = {
    ...conflict,
    reason: "invalid_citation",
    claims: [{ ...conflict.claims[0], citation_status: "invalid" }]
  };
  await get("query-form").handlers.submit(event);
  assert.match(read(get("answer")), /invalid source evidence/);
  assert.deepEqual(buttons(get("answer")), []);

  result = { status: "insufficient_evidence", reason: "unsupported_modality", claims: [] };
  get("requires-visual").checked = true;
  await get("query-form").handlers.submit(event);
  assert.equal(query.requires_visual_evidence, true);
  assert.match(read(get("answer")), /requires inspecting pixels/);
});
