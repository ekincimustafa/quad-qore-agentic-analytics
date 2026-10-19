"use strict";
(() => {
  const form = document.getElementById("question-form");
  const question = document.getElementById("question");
  const submit = document.getElementById("submit");
  const notice = document.getElementById("notice");
  const result = document.getElementById("result");
  const examples = [...document.querySelectorAll("[data-example]")];
  const number = value => value === null ? "—" : new Intl.NumberFormat("tr-TR", {maximumFractionDigits: 4}).format(value);
  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const say = (state, text) => { notice.dataset.state = state; notice.textContent = text; };
  const clear = () => {
    const chart = result.querySelector(".chart");
    if (chart && window.Plotly) window.Plotly.purge(chart);
    result.replaceChildren(); result.hidden = true;
  };
  const busy = value => {
    form.setAttribute("aria-busy", String(value));
    submit.disabled = value; question.readOnly = value;
    examples.forEach(button => { button.disabled = value; });
    submit.textContent = value ? "Analiz ediliyor…" : "Analiz et ↗";
  };
  function list(title, values, parent = result) {
    parent.append(element("h3", title));
    const ul = element("ul");
    values.forEach(text => ul.append(element("li", text)));
    parent.append(ul);
  }
  function table(headers, rows) {
    const wrap = element("div", undefined, "table-wrap");
    const table = element("table");
    const thead = element("thead"); const tr = element("tr");
    headers.forEach(text => { const th = element("th", text); th.scope = "col"; tr.append(th); });
    thead.append(tr); table.append(thead);
    const tbody = element("tbody");
    rows.forEach(values => { const row = element("tr"); values.forEach(value => row.append(element("td", value))); tbody.append(row); });
    table.append(tbody); wrap.append(table); result.append(wrap);
  }
  function sources(title, values) {
    const details = element("details", undefined, "sources");
    details.append(element("summary", `${title} (${values.length})`));
    const ul = element("ul");
    values.forEach(value => { const li = element("li"); li.append(element("code", value)); ul.append(li); });
    details.append(ul); result.append(details);
  }
  async function render(body) {
    const {analysis, available_periods: coverage} = body;
    const e = analysis.evidence;
    const housing = analysis.analysis_id === "housing_rate_down_real_credit_not_up";
    if (!housing && analysis.analysis_id !== "cpi_inflation_summary") throw new Error("Unknown analysis");
    const heading = element("div", undefined, "result-heading");
    heading.append(element("h2", housing ? "Konut kredisi analizi" : "TÜFE değişimleri"));
    heading.append(element("span", "Doğrulanmış yerel dosyalar", "badge")); result.append(heading);
    result.append(element("p", housing
      ? `${e.period_start}–${e.period_end} dönemindeki ${e.observed_month_count} ayın ${e.matched_month_count} tanesinde faiz düşerken reel konut kredisi stoku artmadı.`
      : `${e.period_start}–${e.period_end} döneminde ${e.observed_month_count} ay incelendi. İlk aydan son aya TÜFE endeksi değişimi %${number(e.first_to_last_index_change_pct)}.`, "summary"));
    const available = housing ? coverage.housing : coverage.inflation;
    result.append(element("p", `Veri kapsamı: ${available.start_period}–${available.end_period} · İncelenen dönem: ${e.period_start}–${e.period_end}`, "meta"));
    result.append(element("p", housing
      ? "Kredi stoku: Milyon TL · Reel stok: 2025 fiyatları · Faiz: % · Faiz değişimi: yüzde puan · TÜFE: 2025=100 · KFE: 2023=100"
      : "Genel TÜFE: TP.TUKFIY2025.GENEL · Endeks: 2025=100 · Aylık/yıllık değişimler: %", "meta"));
    result.hidden = false;
    if (housing) {
      const chart = element("div", undefined, "chart"); chart.setAttribute("aria-label", "Konut kredisi, faiz ve endeks grafiği"); result.append(chart);
      const layout = {...analysis.chart.layout, autosize: true, width: undefined, height: 850,
        title: {text: ""}, margin: {...analysis.chart.layout.margin, t: 140, b: 65},
        legend: {...analysis.chart.layout.legend, y: 1.12, yanchor: "bottom"}};
      await window.Plotly.newPlot(chart, analysis.chart.data, layout, {responsive: true, displaylogo: false});
      result.append(element("h3", `Eşleşen aylar (${e.matched_month_count})`));
      if (e.results.length) table(["Ay", "Nominal (Milyon TL)", "Reel (2025 fiyatları)", "Faiz (%)", "Faiz farkı (puan)", "Reel değişim (%)"],
        e.results.map(row => [row.period, ...[row.nominal_housing_loan_mn_try, row.real_housing_loan_2025_mn_try, row.housing_loan_interest_rate_pct, row.interest_rate_change_pp, row.real_housing_loan_change_pct].map(number)]));
      else result.append(element("p", "Bu dönemde koşula uyan ay bulunamadı."));
      result.append(element("p", "Seçilen ilk ayın değişimleri null olduğundan bu ay eşleşmelere dahil edilmez.", "meta"));
    } else {
      result.append(element("h3", "Aylık ve yıllık TÜFE"));
      table(["Ay", "TÜFE (2025=100)", "Aylık değişim (%)", "Yıllık değişim (%)"], e.observations.map(row => [row.period, ...[row.cpi_index, row.monthly_inflation_pct, row.annual_inflation_pct].map(number)]));
      result.append(element("p", "—: Karşılaştırma için geçmiş ay yok. Yıllık oran, geçen yılın aynı ayına göredir; 12 aylık ortalama değildir.", "meta"));
    }
    result.append(element("h3", "Kaynaklar"));
    if (housing) { sources("BDDK makbuz referansları", e.bddk_source_refs); sources("EVDS makbuz referansları", e.evds_source_refs); }
    else sources("TCMB EVDS · TÜFE makbuz referansları", e.source_ref.split("; "));
    const notes = element("div", undefined, "notes"); result.append(notes);
    list("Yöntem", e.methodology, notes);
    list("Sınırlamalar", e.limitations, notes);
    if (housing) list("Veri kalitesi", e.data_quality_notes, notes);
  }
  examples.forEach(button => button.addEventListener("click", () => { question.value = button.dataset.example; question.focus(); }));
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (submit.disabled) return;
    if (!question.value.trim()) { say("error", "Lütfen dönemini de belirterek bir soru yaz."); return; }
    clear(); busy(true); say("loading", "Veriler doğrulanıyor, soru planlanıyor ve analiz hazırlanıyor…");
    try {
      const response = await fetch("/analysis/economic/question/files", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({question: question.value.trim()})});
      const body = await response.json();
      if (!response.ok) {
        const messages = {economic_data_unavailable: "Sunucudaki veri paketi eksik veya doğrulanamadı. Dosya yapılandırmasının kontrol edilmesi gerekiyor.", question_planning_failed: "Model sağlayıcısından plan alınamadı. Sunucu model yapılandırmasını veya sağlayıcı erişimini kontrol edin.", invalid_question_plan: "Modelin planı güvenilir biçimde doğrulanamadı. Sorunu daha açık bir dönemle yeniden yazabilirsin.", invalid_economic_input: "Soru geçerli değil. En fazla 2000 karakterle bir analiz ve dönem belirt."};
        say("error", messages[body.detail?.code] || "İstek tamamlanamadı. Lütfen daha sonra yeniden dene."); return;
      }
      if (body.status === "clarification_required") {
        const messages = {period_required: "Hangi dönemi inceleyelim? Başlangıç ve bitiş yılını/ayını belirt.", metric_ambiguous: "Hangi ölçüyü inceleyelim? Konut koşulunu veya TÜFE değişimini belirt.", question_ambiguous: "Konut kredisi koşulunu mu, TÜFE değişimlerini mi inceleyelim?", outside_coverage: "İstenen dönem veri kapsamının dışında. Aşağıdaki mevcut döneme uygun bir soru yaz."};
        const ranges = Object.entries(body.available_periods).filter(([,v]) => v).map(([k,v]) => `${k === "housing" ? "Konut" : "TÜFE"}: ${v.start_period}–${v.end_period}`).join(" · ");
        say(body.status, `${messages[body.decision.reason] || messages.question_ambiguous} ${ranges}`); return;
      }
      if (body.status === "unsupported") { say(body.status, "Bu sürüm konut kredisi koşulunu veya TÜFE değişimlerini inceleyebilir. Tahmin, nedensellik ve iki analizi birlikte isteyen sorular desteklenmiyor."); return; }
      if (body.status === "data_unavailable") { say("error", "İstenen analiz için kullanılabilir veri bulunmuyor."); return; }
      if (body.status !== "ok") throw new Error("Unknown result");
      await render(body); say("ok", "Analiz hazır. Sonuç, kaynaklar ve sınırlamalar aşağıda.");
    } catch (_) { clear(); say("error", "Sonuç alınamadı veya görüntülenemedi. Bağlantıyı kontrol edip yeniden dene."); }
    finally { busy(false); }
  });
})();
