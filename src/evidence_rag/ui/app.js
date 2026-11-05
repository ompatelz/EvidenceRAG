(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const state = { document: null, units: new Map() };
  const modeNames = { bm25: "BM25", dense: "Dense", hybrid: "Hybrid RRF", reranked: "Hybrid + reranker" };

  function feedback(message, error = false) {
    $("feedback").textContent = message;
    $("feedback").classList.toggle("error", error);
  }

  async function request(url, options) {
    const response = await fetch(url, options);
    let body;
    try { body = await response.json(); } catch { body = {}; }
    if (!response.ok) {
      const detail = body.error?.message || body.detail || `Request failed (${response.status}).`;
      throw new Error(typeof detail === "string" ? detail : "The request could not be completed.");
    }
    return body;
  }

  function versionBase() {
    const doc = state.document;
    return `/api/v1/documents/${encodeURIComponent(doc.document_id)}/versions/${encodeURIComponent(doc.document_sha256)}`;
  }

  function node(tag, className, value) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (value !== undefined) element.textContent = value;
    return element;
  }

  function resetResults() {
    $("answer").replaceChildren();
    $("candidates").replaceChildren();
    $("timings-list").replaceChildren();
    $("page-stage").hidden = true;
    $("viewer").classList.remove("has-page");
    $("viewer-message").hidden = false;
    $("viewer-message").textContent = "Open a citation or retrieval result to inspect its page.";
    $("region-overlay").hidden = true;
    $("anchor-precision").textContent = "";
    $("page-label").textContent = "No page selected";
    $("source-text").textContent = "";
    $("mode-label").textContent = "No search yet";
    $("result-count").textContent = "";
  }

  async function openEvidence(evidenceId) {
    if (!state.document) return;
    feedback("Opening the source page…");
    try {
      const base = versionBase();
      const anchor = await request(`${base}/evidence/${encodeURIComponent(evidenceId)}/anchor`);
      const unit = state.units.get(evidenceId);
      if (!anchor.preview_asset_id) throw new Error("This citation has no available page preview.");
      const image = $("page-image");
      const url = `${base}/pages/${anchor.page_index}/preview`;
      await new Promise((resolve, reject) => {
        image.onload = resolve;
        image.onerror = () => reject(new Error("The source page image is missing or could not load."));
        image.src = url;
      });
      image.alt = `Source page ${anchor.page_index + 1} of the selected PDF`;
      $("page-stage").hidden = false;
      $("viewer").classList.add("has-page");
      $("viewer-message").hidden = true;
      $("page-label").textContent = `Page ${anchor.page_index + 1}`;
      const overlay = $("region-overlay");
      if (anchor.precision === "region" && anchor.display_bbox) {
        const b = anchor.display_bbox;
        overlay.style.left = `${b.x0 * 100}%`;
        overlay.style.top = `${b.y0 * 100}%`;
        overlay.style.width = `${(b.x1 - b.x0) * 100}%`;
        overlay.style.height = `${(b.y1 - b.y0) * 100}%`;
        overlay.hidden = false;
        $("anchor-precision").textContent = "Region highlight from stored source coordinates.";
      } else {
        overlay.hidden = true;
        $("anchor-precision").textContent = "Page-level citation. No precise region coordinates are available.";
      }
      $("source-text").textContent = unit?.text || "";
      $("source-title").scrollIntoView({ behavior: "smooth", block: "start" });
      feedback("Source page opened.");
    } catch (error) {
      $("page-stage").hidden = true;
      $("viewer-message").hidden = false;
      $("viewer-message").textContent = error.message;
      $("anchor-precision").textContent = "";
      feedback(error.message, true);
    }
  }

  function renderAnswer(result) {
    const box = $("answer");
    box.replaceChildren();
    box.className = `answer ${result.status === "answered" ? "answered" : "insufficient"}`;
    box.append(node("p", "result-label", result.status === "answered" ? "Cited answer" : "Insufficient evidence"));
    if (result.status === "answered") {
      box.append(node("h3", "", result.answer));
      const claims = node("ul");
      for (const claim of result.claims) {
        const item = node("li");
        item.append(document.createTextNode(claim.text));
        for (const citation of claim.citations) {
          const button = node("button", "citation-button", `Source · p. ${citation.page_index + 1}`);
          button.type = "button";
          button.addEventListener("click", () => openEvidence(citation.evidence_id));
          item.append(button);
        }
        claims.append(item);
      }
      box.append(claims);
      box.append(node("p", "helper", "Citation IDs and pages are checked. Claim support still needs human review."));
    } else {
      const reasons = {
        no_relevant_evidence: "No matching evidence was retrieved. Try a more specific question.",
        unsupported_question: "The available evidence does not support an answer to this question.",
        generator_unavailable: "Search results are available. Answer generation is not configured for this workspace.",
        generation_timeout: "Answer generation timed out. The retrieved evidence remains available below.",
        generation_failed: "Answer generation failed. The retrieved evidence remains available below.",
        malformed_response: "The answer response was invalid, so it was withheld.",
        invalid_citation: "An answer cited invalid source evidence, so it was withheld.",
        search_unavailable: "Search could not complete. Check the message beside the form and try again."
      };
      box.append(node("p", "", reasons[result.reason] || "No supported answer is available."));
    }
  }

  function formatScore(value) {
    return Number.isFinite(value) ? Number(value).toFixed(4) : "—";
  }

  function renderCandidates(hits) {
    const list = $("candidates");
    list.replaceChildren();
    $("result-count").textContent = `${hits.length} result${hits.length === 1 ? "" : "s"}`;
    for (const hit of hits) {
      const item = node("li", "candidate");
      const head = node("div", "candidate-head");
      head.append(node("span", "rank", String(hit.rank).padStart(2, "0")));
      const button = node("button", "candidate-button", `Open page ${hit.page_index + 1}`);
      button.type = "button";
      button.addEventListener("click", () => openEvidence(hit.evidence_id));
      head.append(button);
      item.append(head);
      const unit = state.units.get(hit.evidence_id);
      item.append(node("p", "candidate-text", unit?.text || "Evidence text unavailable."));
      const meta = node("div", "candidate-meta");
      const add = (value, className = "") => meta.append(node("span", className, value));
      add(`${unit?.element_type || "evidence"} · page ${hit.page_index + 1}`,
          unit?.element_type === "caption" || unit?.element_type === "figure" ? "modality" : "");
      if (hit.bm25_rank != null) add(`BM25 #${hit.bm25_rank} · ${formatScore(hit.bm25_score)}`);
      if (hit.dense_rank != null) add(`Dense #${hit.dense_rank} · ${formatScore(hit.dense_score)}`);
      if (hit.fusion_rank != null) add(`RRF #${hit.fusion_rank} · ${formatScore(hit.fusion_score)}`);
      else if (hit.bm25_rank != null || hit.dense_rank != null) add(`RRF #${hit.rank} · ${formatScore(hit.score)}`);
      else add(`${$("mode").value === "bm25" ? "BM25" : "Cosine"} · ${formatScore(hit.score)}`);
      if (hit.rerank_score != null) add(`Reranker · ${formatScore(hit.rerank_score)}`);
      if (unit?.element_type === "caption" || unit?.element_type === "figure") {
        add("Text or caption only; image content not interpreted.", "modality");
      }
      item.append(meta);
      list.append(item);
    }
  }

  function renderTimings(values) {
    const list = $("timings-list");
    list.replaceChildren();
    for (const [key, value] of Object.entries(values)) {
      list.append(node("dt", "", key.replaceAll("_", " ")));
      list.append(node("dd", "", `${Number(value).toFixed(2)} ms`));
    }
  }

  $("upload-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = $("pdf-file").files[0];
    if (!file || !$("permission").checked) return;
    $("upload-button").disabled = true;
    $("question").disabled = true;
    $("mode").disabled = true;
    $("query-button").disabled = true;
    state.document = null;
    state.units.clear();
    $("document-state").textContent = "Ingesting and preparing source pages…";
    feedback("");
    resetResults();
    try {
      const form = new FormData();
      form.append("file", file);
      const documentInfo = await request("/api/v1/ingestions", { method: "POST", body: form });
      if (documentInfo.state !== "ready") throw new Error("Ingestion did not finish. Check the document status and retry.");
      state.document = documentInfo;
      const artifact = await request(`${versionBase()}/evidence`);
      state.units = new Map(artifact.units.map((unit) => [unit.evidence_id, unit]));
      $("document-state").textContent = `${file.name} · ready · ${documentInfo.page_count} page${documentInfo.page_count === 1 ? "" : "s"}`;
      $("question").disabled = false;
      $("mode").disabled = false;
      $("query-button").disabled = false;
      feedback("Document ready. Ask a question or inspect a source result.");
    } catch (error) {
      state.document = null;
      state.units.clear();
      $("question").disabled = true;
      $("mode").disabled = true;
      $("query-button").disabled = true;
      $("document-state").textContent = `Ingestion failed: ${error.message}`;
      feedback(error.message, true);
    } finally {
      $("upload-button").disabled = false;
    }
  });

  $("query-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.document) return;
    $("query-button").disabled = true;
    feedback("Searching this document…");
    try {
      const response = await request("/api/v1/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: $("question").value.trim(), mode: $("mode").value,
          document_id: state.document.document_id,
          document_sha256: state.document.document_sha256
        })
      });
      renderAnswer(response.result);
      renderCandidates(response.retrieval);
      renderTimings(response.timings_ms);
      $("mode-label").textContent = modeNames[response.mode] || response.mode;
      feedback(response.retrieval_status === "reranked" || response.retrieval_status === "ok"
        ? "Search complete. Open a citation or result to inspect its source."
        : `Search complete with ${response.retrieval_status.replaceAll("_", " ")}.`);
    } catch (error) {
      feedback(error.message, true);
      $("candidates").replaceChildren();
      $("timings-list").replaceChildren();
      $("result-count").textContent = "";
      renderAnswer({ status: "insufficient_evidence", reason: "search_unavailable" });
    } finally {
      $("query-button").disabled = false;
    }
  });

  $("sample-button").addEventListener("click", () => {
    $("question").value = "What is the calibration sampling rate of the Atlas sensor?";
    $("question").focus();
  });

  request("/api/v1/capabilities").then((caps) => {
    $("sample-button").hidden = !caps.fixture_demo_answers;
  }).catch(() => {});
})();
