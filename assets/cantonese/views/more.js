// 更多: course intro, study log, resources, settings & backup.
import { getCourse } from "../data.js";
import * as store from "../store.js";
import { cantoneseVoices, speak } from "../speech.js";
import { renderItem } from "../render.js";
import { el } from "../ui.js";

const PAGES = { about: "課程簡介", log: "自修紀錄", links: "自修資源", settings: "設定及備份" };

export function render(main, page) {
  if (!page || !PAGES[page]) {
    main.append(el("h1", {}, "更多"),
      el("ul.menu", {}, Object.entries(PAGES).map(([k, v]) => el("li", {}, el("a", { href: `#cantonese/more/${k}` }, v)))));
    return;
  }
  main.append(el("nav.crumbs", {}, el("a", { href: "#cantonese/more" }, "更多"), " › ", PAGES[page]), el("h1", {}, PAGES[page]));
  return ({ about, log, links, settings })[page](main);
}

function about(main) {
  const c = getCourse();
  main.append(el("p.muted", {}, c.source), el("div.items", {}, c.intro.map((i) => i.type === "bullets"
    ? el("ul", {}, i.items.map((x) => el("li", {}, x)))
    : renderItem(i))));
  const rows = c.units.map((u) => el("tr", {}, el("td", {}, u.title), el("td", {}, u.hours?.class ?? ""), el("td", {}, u.hours?.self ?? "")));
  main.append(el("h2", {}, "建議學時"), el("table.simple", {},
    el("thead", {}, el("tr", {}, el("th", {}, "單元"), el("th", {}, "課時"), el("th", {}, "自修時數"))), el("tbody", {}, rows)));
}

// Mirrors the workbook's 自修活動紀錄表, filled in automatically.
function log(main) {
  const days = store.history().filter(([, d]) => d.sec || d.reviews || d.newLessons || d.quiz[1]);
  const total = days.reduce((a, [, d]) => a + d.sec, 0);
  main.append(el("p", {}, `總自修時間：${(total / 3600).toFixed(1)} 小時（教材建議 14.5 小時）`));
  if (!days.length) { main.append(el("p.muted", {}, "未有紀錄。")); return; }
  main.append(el("table.simple", {},
    el("thead", {}, el("tr", {}, el("th", {}, "日期"), el("th", {}, "時間"), el("th", {}, "活動"))),
    el("tbody", {}, days.map(([k, d]) => el("tr", {},
      el("td", {}, k),
      el("td", {}, `${Math.round(d.sec / 60)} 分鐘`),
      el("td", {}, [d.newLessons && `新課 ${d.newLessons}`, d.reviews && `溫習 ${d.reviews} 張`,
        d.quiz[1] && `小測 ${d.quiz[0]}/${d.quiz[1]}`, d.dialogues.length && `對話 ${d.dialogues.length} 段`].filter(Boolean).join("、")))))));
}

function links(main) {
  const c = getCourse();
  const groups = {};
  for (const r of c.resources) (groups[r.kind] ||= []).push(r);
  for (const [kind, rows] of Object.entries(groups)) {
    main.append(el("h2", {}, kind), el("ul.links", {}, rows.map((r) => el("li", {},
      r.url ? el("a", { href: r.url, target: "_blank", rel: "noopener" }, r.name) : el("b", {}, r.name),
      el("small", {}, r.desc), r.platform ? el("small", {}, `平台：${r.platform}`) : null))));
  }
  main.append(el("details", {}, el("summary", {}, "教材參考書目"), el("ul", {}, c.bibliography.map((b) => el("li", {}, b)))));
}

async function settings(main) {
  const s = store.settings();
  const voices = await cantoneseVoices();
  const voiceSel = el("select", { id: "voice" },
    el("option", { value: "" }, voices.length ? "自動" : "（未有廣東話語音）"),
    voices.map((v) => el("option", { value: v.name, selected: v.name === s.voice || undefined }, `${v.name} (${v.lang})`)));
  voiceSel.addEventListener("change", () => { store.setSetting("voice", voiceSel.value); speak("你好，歡迎學廣東話"); });

  const rate = el("input", { type: "range", id: "rate", min: 0.5, max: 1.2, step: 0.05, value: s.rate });
  const rateOut = el("output", { for: "rate" }, s.rate);
  rate.addEventListener("change", () => { store.setSetting("rate", Number(rate.value)); rateOut.textContent = rate.value; speak("今日天氣好好"); });

  const cap = el("input", { type: "number", id: "cap", min: 10, max: 500, value: s.reviewCap });
  cap.addEventListener("change", () => store.setSetting("reviewCap", Math.max(10, Number(cap.value) || 60)));

  const auto = el("input", { type: "checkbox", id: "auto", checked: s.autoSpeak || undefined });
  auto.addEventListener("change", () => store.setSetting("autoSpeak", auto.checked));

  main.append(el("form.settings", { onsubmit: (e) => e.preventDefault() },
    el("label", { for: "voice" }, "讀音聲音"), voiceSel,
    el("label", { for: "rate" }, "語速"), el("div", {}, rate, rateOut),
    el("label", { for: "cap" }, "每日最多溫習卡片"), cap,
    el("label.inline", { for: "auto" }, auto, " 溫習時自動讀出")),
    el("h2", {}, "同步及備份"),
    el("p.muted", {}, "進度會跟住你嘅登入自動同步到 Mac mini，換部機登入一樣睇到。「今日一課」頁底嘅備份匯出都會包埋廣東話進度。"));
}
