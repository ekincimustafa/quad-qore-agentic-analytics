"use strict";
(() => {
  const form = document.getElementById("question-form");
  const question = document.getElementById("question");
  const submit = document.getElementById("submit");
  const notice = document.getElementById("notice");
  const result = document.getElementById("result");
  const examples = [...document.querySelectorAll("[data-example]")];
  const clarification = document.getElementById("clarification");
  const clarificationMessage = document.getElementById("clarification-message");
  const clarificationYearField = document.getElementById("clarification-year-field");
  const clarificationYear = document.getElementById("clarification-year");
  const clarificationMetricField = document.getElementById("clarification-metric-field");
  const clarificationComplete = document.getElementById("clarification-complete");
  const clarificationDismiss = document.getElementById("clarification-dismiss");
  const clarificationError = document.getElementById("clarification-error");
  const clarificationMetrics = [...document.querySelectorAll('input[name="clarification-metric"]')];
  const offlinePreview = document.querySelector(".mode")?.textContent.includes("OFFLINE ÖNİZLEME");
  const MAX_QUESTION_LENGTH = 2000;
  const suffix = "[a-zçğıöşü]*";
  const monthNames = ["ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos", "eylül", "ekim", "kasım", "aralık"];
  const monthPattern = new RegExp(`(?<![a-zçğıöşü])(?:${monthNames.join("|")})(?![a-zçğıöşü])`, "gi");
  const quarterPattern = new RegExp(`(?:ilk|birinci|ikinci|üçüncü|dördüncü|son|[1-4]\\s*\\.)\\s+(?:çeyre${suffix}|üç\\s+ay${suffix})`, "i");
  const halfPattern = new RegExp(`(?:ilk|birinci|son|ikinci)\\s+(?:(?:altı|6)\\s+ay${suffix}|yarı${suffix})`, "i");
  const amountPattern = `(?:stok|bakiy|tutar|hac|miktar)${suffix}`;
  const creditPattern = new RegExp(`(?<![a-zçğıöşü])(?:(?:konut\\s+)?kredi${suffix}(?:\\s+${amountPattern})?|${amountPattern})(?![a-zçğıöşü])`, "gi");
  let clarificationContext = null;
  const number = value => value === null ? "—" : new Intl.NumberFormat("tr-TR", {maximumFractionDigits: 4}).format(value);
  const pct = value => value === null ? "—" : `%${number(value)}`;
  const pp = value => value === null ? "—" : `${value > 0 ? "+" : ""}${number(value)} yüzde puan`;
  const metricLabels = {
    interest_rate_change_pp: "Faiz değişimi",
    real_housing_loan_change_pct: "Reel konut kredisi değişimi",
    nominal_housing_loan_change_pct: "Nominal konut kredisi değişimi",
    housing_loan_interest_rate_pct: "Konut kredisi faiz seviyesi"
  };
  const operatorLabels = {lt: "<", lte: "≤", gt: ">", gte: "≥"};
  const unitLabels = {percentage_point: "yüzde puan", percent: "%"};
  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const say = (state, text) => { notice.dataset.state = state; notice.textContent = text; };
  const clear = () => {
    const charts = result.querySelectorAll(".chart");
    if (window.Plotly) charts.forEach(chart => window.Plotly.purge(chart));
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
    const filter = analysis.analysis_id === "housing_condition_filter";
    const comparison = analysis.analysis_id === "cpi_two_year_comparison";
    if (!housing && !filter && !comparison && analysis.analysis_id !== "cpi_inflation_summary") throw new Error("Unknown analysis");
    const heading = element("div", undefined, "result-heading");
    heading.append(element("h2", housing ? "Konut kredisi analizi" : filter ? "Koşullu konut filtresi" : comparison ? "İki yıl TÜFE karşılaştırması" : "TÜFE değişimleri"));
    heading.append(element("span", "Doğrulanmış yerel dosyalar", "badge")); result.append(heading);
    if (comparison) {
      const [first, second] = e.years;
      const firstRate = first.evidence.observations[first.evidence.observations.length - 1].annual_inflation_pct;
      const secondRate = second.evidence.observations[second.evidence.observations.length - 1].annual_inflation_pct;
      result.append(element("p", `${first.year} ve ${second.year} tam yılları incelendi. Aralık yıllık TÜFE: ${first.year} ${pct(firstRate)} · ${second.year} ${pct(secondRate)}. Fark (${second.year} − ${first.year}): ${pp(e.second_minus_first_december_annual_inflation_pp)}.`, "summary"));
    } else {
      result.append(element("p", housing
        ? `${e.period_start}–${e.period_end} dönemindeki ${e.observed_month_count} ayın ${e.matched_month_count} tanesinde faiz düşerken reel konut kredisi stoku artmadı.`
        : filter
          ? `${e.period_start}–${e.period_end} dönemindeki ${e.observed_month_count} aydan ${e.evaluable_month_count} tanesi değerlendirilebildi; ${e.matched_month_count} tanesi tüm koşulları sağladı.`
          : `${e.period_start}–${e.period_end} döneminde ${e.observed_month_count} ay incelendi. İlk aydan son aya TÜFE endeksi değişimi %${number(e.first_to_last_index_change_pct)}.`, "summary"));
    }
    const available = housing || filter ? coverage.housing : coverage.inflation;
    const scope = comparison
      ? `İncelenen yıllar: ${e.years[0].year} ve ${e.years[1].year} (her biri Ocak–Aralık)`
      : `İncelenen dönem: ${e.period_start}–${e.period_end}`;
    result.append(element("p", `Veri kapsamı: ${available.start_period}–${available.end_period} · ${scope}`, "meta"));
    result.append(element("p", housing
      ? "Kredi stoku: Milyon TL · Reel stok: 2025 fiyatları · Faiz: % · Faiz değişimi: yüzde puan · TÜFE: 2025=100 · KFE: 2023=100"
      : filter
        ? "Faiz değişimi: yüzde puan · Reel/nominal kredi değişimi: % · Faiz seviyesi: % · Koşullar yalnızca AND ile birleşir"
        : comparison
          ? "Genel TÜFE: TP.TUKFIY2025.GENEL · Endeks: 2025=100 · Aralık yıllık oran: % · Ocak–Aralık endeks değişimi: % · Fark: ikinci yıl − birinci yıl, yüzde puan"
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
    } else if (filter) {
      result.append(element("h3", "Koşullar (AND)"));
      table(["Metrik", "Karşılaştırma", "Eşik", "Birim"],
        e.conditions.map(condition => [
          metricLabels[condition.metric] || condition.metric,
          operatorLabels[condition.operator] || condition.operator,
          number(condition.threshold),
          unitLabels[condition.unit] || condition.unit
        ]));
      result.append(element("h3", `Eşleşen aylar (${e.matched_month_count})`));
      if (e.results.length) {
        table(["Ay", "Nominal (Milyon TL)", "Reel (2025 fiyatları)", "Nominal değişim (%)", "Reel değişim (%)", "Faiz (%)", "Faiz değişimi (puan)"],
          e.results.map(row => [row.period, ...[row.nominal_housing_loan_mn_try, row.real_housing_loan_2025_mn_try, row.nominal_housing_loan_change_pct, row.real_housing_loan_change_pct, row.housing_loan_interest_rate_pct, row.interest_rate_change_pp].map(number)]));
      } else {
        result.append(element("p", "Bu dönemde tüm koşulları sağlayan ay bulunamadı."));
      }
      result.append(element("p", "İlk ayın önceki ayı olmadığından değişim koşulları bu ayda değerlendirilemez. Grafik yalnız eski sabit konut analizinde gösterilir.", "meta"));
    } else if (comparison) {
      e.years.forEach((item, index) => {
        result.append(element("h3", `${item.year} · Ocak–Aralık (${index === 0 ? "birinci" : "ikinci"} yıl)`));
        result.append(element("p", `${item.year} Ocak–Aralık endeks değişimi: ${pct(item.evidence.first_to_last_index_change_pct)}. Bu, Aralık yıllık TÜFE oranı veya yüzde puan farkı değildir.`, "meta comparison-index-change"));
        table(["Ay", "TÜFE (2025=100)", "Aylık değişim (%)", "Yıllık değişim (%)"],
          item.evidence.observations.map(row => [row.period, ...[row.cpi_index, row.monthly_inflation_pct, row.annual_inflation_pct].map(number)]));
      });
      result.append(element("p", "—: Gerekli önceki Aralık verisi yoksa Aralık yıllık oran ve iki yıl farkı null kalır; sıfır veya tahmin üretilmez.", "meta"));
    } else {
      const chart = element("div", undefined, "chart");
      chart.setAttribute("aria-label", "TÜFE endeksi, aylık ve yıllık değişim grafiği");
      result.append(chart);
      const layout = {...analysis.chart.layout, autosize: true, width: undefined,
        title: {text: ""}};
      await window.Plotly.newPlot(chart, analysis.chart.data, layout, {responsive: true, displaylogo: false});
      result.append(element("h3", "Aylık ve yıllık TÜFE"));
      table(["Ay", "TÜFE (2025=100)", "Aylık değişim (%)", "Yıllık değişim (%)"], e.observations.map(row => [row.period, ...[row.cpi_index, row.monthly_inflation_pct, row.annual_inflation_pct].map(number)]));
      result.append(element("p", "—: Karşılaştırma için geçmiş ay yok. Yıllık oran, geçen yılın aynı ayına göredir; 12 aylık ortalama değildir.", "meta"));
    }
    result.append(element("h3", "Kaynaklar"));
    if (housing || filter) { sources("BDDK makbuz referansları", e.bddk_source_refs); sources("EVDS makbuz referansları", e.evds_source_refs); }
    else sources("TCMB EVDS · TÜFE makbuz referansları", e.source_ref.split("; "));
    const notes = element("div", undefined, "notes"); result.append(notes);
    list("Yöntem", e.methodology, notes);
    list("Sınırlamalar", e.limitations, notes);
    if (housing || filter) list("Veri kalitesi", e.data_quality_notes, notes);
  }
  const yearsIn = text => [...text.matchAll(/(?<!\d)((?:19|20)\d{2})(?!\d)/g)].map(match => match[1]);
  const comparisonRequested = text => /(?:karşılaştır|kıyasla)[a-zçğıöşü]*/i.test(text);
  const monthMatches = text => [...text.matchAll(monthPattern)];
  const clearClarificationError = () => { clarificationError.hidden = true; clarificationError.textContent = ""; };
  const showClarificationError = text => { clarificationError.textContent = text; clarificationError.hidden = false; };
  const closeClarification = () => {
    clarification.hidden = true;
    clarificationContext = null;
    clarificationYearField.hidden = true;
    clarificationMetricField.hidden = true;
    clarificationYear.value = "";
    clarificationMetrics.forEach(radio => { radio.checked = false; });
    clarificationComplete.disabled = false;
    clearClarificationError();
  };
  const appendClause = (text, clause) => /[.!?]\s*$/.test(text)
    ? text.replace(/([.!?]\s*)$/, ` ${clause}$1`)
    : `${text} ${clause}`;
  const completePeriod = (text, rawYears) => {
    const years = yearsIn(rawYears);
    const comparison = comparisonRequested(text);
    if (yearsIn(text).length) {
      return {error: "Soruda zaten bir tarih var. Eksik veya çelişkili dönemi ana soruyu düzenleyerek tamamla."};
    }
    if (comparison) {
      if (years.length !== 2 || new Set(years).size !== 2) {
        return {error: "Karşılaştırma için iki farklı tam yıl yaz (örneğin 2023 ve 2024)."};
      }
      if (monthMatches(text).length || quarterPattern.test(text) || halfPattern.test(text)) {
        return {error: "Kısmi dönem karşılaştırmasını güvenle tamamlayamıyorum. Lütfen ana soruyu düzenle."};
      }
      return {text: appendClause(text, `${years[0]} ve ${years[1]}`)};
    }
    if (years.length !== 1) {
      return {error: "Dört haneli tek bir yıl yaz (örneğin 2023)."};
    }
    if (
      /(?<!\d)(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})(?!\d)/.test(text)
      || new RegExp(`(?<![a-zçğıöşü])\\d{1,2}\\s+(?:${monthNames.join("|")})(?![a-zçğıöşü])`, "i").test(text)
      || /(?:itibaren|sonraki|sonrasında|başlayarak|bu\s+yana)/i.test(text)
      || /(?:geçen|bu|gelecek|önceki|sonraki)\s+yıl[a-zçğıöşü]*/i.test(text)
      || /son\s+(?:\d+|iki|üç)\s+yıl[a-zçğıöşü]*/i.test(text)
    ) {
      return {error: "Bu tarih ifadesini güvenle tamamlayamıyorum. Lütfen ana soruyu düzenle."};
    }
    const months = monthMatches(text);
    const quarter = quarterPattern.exec(text);
    const half = halfPattern.exec(text);
    if (months.length > 2 || (months.length && (quarter || half))) {
      return {error: "Birden çok dönem ifadesi var. Lütfen ana soruyu düzenle."};
    }
    if (months.length === 2) {
      const [first, second] = months;
      const separator = text.slice(first.index + first[0].length, second.index);
      const separatorPattern = /^\s*(?:[-–—]|['’](?:tan|ten|dan|den)|ay[a-zçğıöşü]*ndan|ay[a-zçğıöşü]*\s+(?:ile|ve)|(?:ile|ve))\s*$/i;
      if (!separatorPattern.test(separator)) {
        return {error: "Bu dönem ifadesini güvenle tamamlayamıyorum. Lütfen ana soruyu düzenle."};
      }
      const after = text.slice(second.index + second[0].length);
      if (
        /(?:^|\s)ve(?:\s|$)/i.test(separator)
        && !/^\s+(?:ay[a-zçğıöşü]*\s+)?(?:arası[a-zçğıöşü]*|aralı[a-zçğıöşü]*|kadar)(?![a-zçğıöşü])/i.test(after)
      ) {
        return {error: "Kesintili ay listesini güvenle tamamlayamıyorum. Lütfen ana soruyu düzenle."};
      }
      return {text: `${text.slice(0, first.index)}${years[0]} ${text.slice(first.index)}`};
    }
    if (months.length === 1) {
      return {text: `${text.slice(0, months[0].index)}${years[0]} ${text.slice(months[0].index)}`};
    }
    if (quarter) {
      return {text: `${text.slice(0, quarter.index)}${years[0]} yılının ${text.slice(quarter.index)}`};
    }
    if (half) {
      return {text: `${text.slice(0, half.index)}${years[0]} yılının ${text.slice(half.index)}`};
    }
    if (
      new RegExp(`(?:çeyrek|yarı)${suffix}`, "i").test(text)
      || new RegExp(`(?:altı|6)\\s+ay${suffix}`, "i").test(text)
    ) {
      return {error: "Bu dönem ifadesini güvenle tamamlayamıyorum. Lütfen ana soruyu düzenle."};
    }
    return {text: appendClause(text, `${years[0]} yılında`)};
  };
  const completeMetric = (text, metric) => {
    if (!metric) {
      return {error: "Reel veya Nominal seç."};
    }
    const candidates = [];
    for (const match of text.matchAll(creditPattern)) {
      const after = text.slice(match.index + match[0].length);
      if (/^\s*faiz/i.test(after) || /^\s*(?:reel|nominal)/i.test(after)) {
        continue;
      }
      const before = text.slice(Math.max(0, match.index - 40), match.index);
      if (
        /(?:reel(?:\s+olarak)?|nominal(?:\s+olarak)?|enflasyondan\s+arındırılmış|tüfe\s+ile\s+arındırılmış|enflasyona\s+göre\s+düzeltilmiş)\s*$/i.test(before)
        || /(?:reel|nominal)(?:\s+olarak)?\s+(?:olmayan|olmadığı|değil|hariç)\s*$/i.test(before)
      ) {
        return {error: "Mevcut veya çelişkili kredi ölçüsünü sessizce değiştirmiyorum. Lütfen ana soruyu düzenle."};
      }
      candidates.push(match);
    }
    if (candidates.length !== 1) {
      return {error: "İlgili kredi stoku/bakiyesi ifadesini güvenle bulamadım. Lütfen ana soruyu düzenle."};
    }
    const target = candidates[0];
    return {text: `${text.slice(0, target.index)}${metric} ${text.slice(target.index)}`};
  };
  const showClarification = body => {
    const reason = body.decision?.reason;
    const messages = {
      period_required: "Hangi dönemi inceleyelim? Başlangıç ve bitiş yılını/ayını veya karşılaştırılacak iki farklı tam yılı belirt.",
      metric_ambiguous: "Hangi ölçüyü inceleyelim? Reel/nominal konut kredisi, faiz seviyesi veya faiz değişimini belirt.",
      question_ambiguous: "Konut filtresi koşullarını mı, TÜFE değişimlerini mi, iki tam yılın TÜFE karşılaştırmasını mı inceleyelim?",
      outside_coverage: "İstenen dönem veri kapsamının dışında. Aşağıdaki mevcut döneme uygun bir soru yaz."
    };
    const ranges = Object.entries(body.available_periods).filter(([, value]) => value)
      .map(([key, value]) => `${key === "housing" ? "Konut" : "TÜFE"}: ${value.start_period}–${value.end_period}`).join(" · ");
    say(body.status, `${messages[reason] || messages.question_ambiguous} ${ranges}`);
    closeClarification();
    if (offlinePreview || (reason !== "period_required" && reason !== "metric_ambiguous")) {
      return;
    }
    clarificationContext = {question: question.value.trim(), reason};
    clarification.hidden = false;
    if (reason === "period_required") {
      if (yearsIn(clarificationContext.question).length) {
        clarificationMessage.textContent = "Soruda zaten bir tarih var. Eksik veya çelişkili dönemi ana soruyu düzenleyerek tamamla.";
        clarificationComplete.disabled = true;
      } else {
        clarificationMessage.textContent = comparisonRequested(clarificationContext.question)
          ? "Karşılaştırma için iki farklı tam yıl yaz. Kısmi dönem varsa ana soruyu düzenle."
          : "Dört haneli yıl yaz. Ay veya çeyrek gibi dar dönem korunur.";
        clarificationYearField.hidden = false;
        clarificationYear.focus();
      }
    } else {
      clarificationMessage.textContent = "Kredi stoku/bakiyesi için Reel veya Nominal seç. Seçim ilgili ifadeye uygulanır.";
      clarificationMetricField.hidden = false;
    }
  };
  const completeClarification = () => {
    if (!clarificationContext || submit.disabled) return;
    if (question.value.trim() !== clarificationContext.question) {
      closeClarification();
      return;
    }
    const metric = clarificationMetrics.find(radio => radio.checked)?.value;
    const result = clarificationContext.reason === "period_required"
      ? completePeriod(question.value, clarificationYear.value)
      : completeMetric(question.value, metric);
    if (result.error) {
      showClarificationError(result.error);
      return;
    }
    if (result.text.length > MAX_QUESTION_LENGTH) {
      showClarificationError("Tamamlanan soru 2000 karakter sınırını aşıyor. Lütfen ana soruyu kısalt.");
      return;
    }
    question.value = result.text;
    closeClarification();
    say("clarified", "Soru tamamlandı. Gerekirse düzenle, sonra Analiz et ile gönder.");
    question.focus();
  };
  clarificationComplete.addEventListener("click", completeClarification);
  clarificationDismiss.addEventListener("click", () => {
    closeClarification();
    say("idle", "Netleştirme kapatıldı. Soruyu düzenleyip yeniden gönderebilirsin.");
  });
  question.addEventListener("input", () => {
    if (clarificationContext && question.value.trim() !== clarificationContext.question) {
      closeClarification();
    }
  });
  examples.forEach(button => button.addEventListener("click", () => { closeClarification(); question.value = button.dataset.example; question.focus(); }));
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (submit.disabled) return;
    closeClarification();
    if (!question.value.trim()) { say("error", "Lütfen dönemini de belirterek bir soru yaz."); return; }
    clear(); busy(true); say("loading", "Veriler doğrulanıyor, soru planlanıyor ve analiz hazırlanıyor…");
    try {
      const response = await fetch("/analysis/economic/question/files", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({question: question.value.trim()})});
      const body = await response.json();
      if (!response.ok) {
        const messages = {economic_data_unavailable: "Sunucudaki veri paketi eksik veya doğrulanamadı. Dosya yapılandırmasının kontrol edilmesi gerekiyor.", question_planning_failed: "Model sağlayıcısından plan alınamadı. Sunucu model yapılandırmasını veya sağlayıcı erişimini kontrol edin.", invalid_question_plan: "Modelin planı güvenilir biçimde doğrulanamadı. Sorunu daha açık bir dönemle yeniden yazabilirsin.", invalid_economic_input: "Soru geçerli değil. En fazla 2000 karakterle bir analiz ve dönem belirt."};
        say("error", messages[body.detail?.code] || "İstek tamamlanamadı. Lütfen daha sonra yeniden dene."); return;
      }
      if (body.status === "clarification_required") { showClarification(body); return; }
      if (body.status === "unsupported") { say(body.status, "Bu sürüm parametreli konut koşullarını, TÜFE değişimlerini veya iki tam yılın TÜFE karşılaştırmasını inceleyebilir. OR, sıralama/top-N, ortalama, kısmi dönem, tahmin, nedensellik ve iki analizi birlikte isteyen sorular desteklenmiyor."); return; }
      if (body.status === "data_unavailable") { say("error", "İstenen analiz için kullanılabilir veri bulunmuyor."); return; }
      if (body.status !== "ok") throw new Error("Unknown result");
      await render(body); say("ok", "Analiz hazır. Sonuç, kaynaklar ve sınırlamalar aşağıda.");
    } catch (_) { clear(); say("error", "Sonuç alınamadı veya görüntülenemedi. Bağlantıyı kontrol edip yeniden dene."); }
    finally { busy(false); }
  });
})();
