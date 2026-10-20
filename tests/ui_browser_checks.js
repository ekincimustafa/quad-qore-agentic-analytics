"use strict";
(async () => {
  const checks = [];
  const assert = (condition, label) => { if (!condition) throw Error(label); checks.push(label); };
  const form = document.getElementById("question-form"), field = document.getElementById("question"), button = document.getElementById("submit"), notice = document.getElementById("notice"), result = document.getElementById("result");
  const originalFetch = window.fetch;
  const requests = [];
  window.fetch = (url, options) => { requests.push({url, body: JSON.parse(options.body)}); return originalFetch(url, options); };
  async function send(question) {
    field.value = question;
    form.dispatchEvent(new Event("submit", {cancelable: true}));
    assert(button.disabled && form.getAttribute("aria-busy") === "true", "waiting disables resubmission");
    form.dispatchEvent(new Event("submit", {cancelable: true}));
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(Error("UI response timeout")), 10000);
      const observer = new MutationObserver(() => {
        if (!button.disabled) { observer.disconnect(); clearTimeout(timeout); resolve(); }
      });
      observer.observe(form, {attributes: true, subtree: true});
    });
    assert(form.getAttribute("aria-busy") === "false", "controls recover");
  }
  try {
    assert(notice.dataset.state === "idle" && result.hidden, "initial page has no request or result");
    document.querySelector("[data-example]").click();
    assert(field.value.includes("2021-2025") && requests.length === 0, "example fills without submitting");
    await send("2021 Ocak-Şubat faiz düşerken reel konut kredisi stokunun artmadığı ayları göster.");
    assert(notice.dataset.state === "ok" && !result.hidden, "physical package housing succeeds");
    assert(result.querySelector(".js-plotly-plot")?.data.length === 6, "existing six-trace Plotly chart rendered");
    assert(result.textContent.includes("koşula uyan ay bulunamadı"), "empty match state");
    assert(result.textContent.includes("2025 fiyatları") && result.textContent.includes("unverified"), "units and quality visible");
    await send("2021 Ocak-Şubat TÜFE değişimleri");
    assert(notice.dataset.state === "ok" && result.querySelectorAll("tbody tr").length === 2, "CPI table uses actual API rows");
    assert(result.querySelector("tbody").textContent.includes("—"), "missing CPI history is not zero");
    assert(!result.querySelector(".chart") && result.textContent.includes("TÜFE makbuz"), "CPI sources without stale housing chart");
    await send('<img src=x onerror="window.UI_XSS=true">');
    assert(notice.dataset.state === "clarification_required" && result.hidden, "clarification hides stale result");
    assert(!window.UI_XSS && field.value.startsWith("<img"), "user text never executes");
    await send("unsupported");
    assert(notice.dataset.state === "unsupported", "unsupported decision shown");
    await send("provider");
    assert(notice.dataset.state === "error" && !document.body.textContent.includes("PRIVATE-PROVIDER-RESPONSE"), "provider body remains private");
    assert(requests.length === 5 && requests.every(r => r.url === "/analysis/economic/question/files" && Object.keys(r.body).join() === "question"), "one request each with only question");
    window.fetch = async () => new Response(JSON.stringify({detail: {code: "economic_data_unavailable", message: "PRIVATE-PATH"}}), {status: 503, headers: {"Content-Type": "application/json"}});
    await send("missing data");
    assert(notice.textContent.includes("veri paketi") && !document.body.textContent.includes("PRIVATE-PATH"), "safe missing-data state");
    window.fetch = async () => { throw Error("PRIVATE-NETWORK"); };
    await send("network");
    assert(notice.dataset.state === "error" && !document.body.textContent.includes("PRIVATE-NETWORK"), "network recovery state");
    const matched = __MATCHED_PAYLOAD__;
    matched.analysis.evidence.bddk_source_refs = ['<img src=x onerror="window.UI_XSS=true">'];
    window.fetch = async () => new Response(JSON.stringify(matched), {headers: {"Content-Type": "application/json"}});
    await send("matched response");
    assert(result.querySelectorAll("tbody tr").length === 1 && result.querySelector("tbody tr td").textContent === "2021-02", "match table displays calculated evidence row");
    assert(result.textContent.includes("3 ayın 1 tanesinde"), "summary reads evidence counters");
    assert(!result.querySelector("img") && !window.UI_XSS && result.textContent.includes("<img src=x"), "source text is inert text, not HTML");
    const marker = document.createElement("pre"); marker.id = "ui-test-result"; marker.textContent = JSON.stringify({ok: true, checks: checks.length}); document.body.append(marker);
  } catch (error) {
    const marker = document.createElement("pre"); marker.id = "ui-test-result"; marker.textContent = JSON.stringify({ok: false, checks, error: String(error)}); document.body.append(marker);
  }
})();
