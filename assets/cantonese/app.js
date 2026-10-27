// 廣東話 tab: mounted into #cantoneseView by index.html.
// index.html owns the hash router; it calls SabrinaCantoneseApp.render() whenever
// the hash starts with #cantonese, and reset() when the signed-in profile changes.
import { loadCourse, resetCourse, CourseUnavailable } from "./data.js";
import { addTime } from "./store.js";
import { stop } from "./speech.js";
import { host } from "./host.js";
import { el, applyToggles } from "./ui.js";
import * as home from "./views/home.js";
import * as course from "./views/course.js";
import * as lesson from "./views/lesson.js";
import * as review from "./views/review.js";
import * as quiz from "./views/quiz.js";
import * as dialogues from "./views/dialogues.js";
import * as more from "./views/more.js";

const ROUTES = [
  [/^$/, home, "home"],
  [/^course$/, course, "course"],
  [/^lesson\/(.+)$/, lesson, "course"],
  [/^review(?:\/(.+))?$/, review, "review"],
  [/^quiz(?:\/(.+))?$/, quiz, "review"],
  [/^dialogues$/, dialogues, "dialogues"],
  [/^dialogue\/(.+)$/, { render: dialogues.renderOne }, "dialogues"],
  [/^more(?:\/(.+))?$/, more, "more"],
];
const TABS = [["home", "", "今日"], ["course", "course", "課程"], ["review", "review", "溫習"],
  ["dialogues", "dialogues", "對話"], ["more", "more", "更多"]];

const root = document.getElementById("cantoneseView");
const nav = el("nav.ct-tabs", { "aria-label": "廣東話選單" },
  TABS.map(([key, path, label]) => el("a", { href: path ? `#cantonese/${path}` : "#cantonese", "data-tab": key }, label)));
const main = el("div.ct-main", { tabindex: "-1" });
root.replaceChildren(nav, main);

let cleanup = null;
let token = 0;
const visible = () => !root.hidden;

async function render() {
  const mine = ++token;
  stop();
  if (typeof cleanup === "function") cleanup();
  cleanup = null;
  const path = decodeURIComponent(location.hash.replace(/^#cantonese\/?/, ""));
  let match = [], view = home, tab = "home";
  for (const [re, v, t] of ROUTES) {
    const m = path.match(re);
    if (m) { match = m; view = v; tab = t; break; }
  }
  nav.querySelectorAll("a").forEach((a) => a.toggleAttribute("aria-current", a.dataset.tab === tab));
  if (!host().isSignedIn()) {
    main.replaceChildren(el("section.card.ct-empty", {},
      el("p", {}, "廣東話課程需要先登入。"),
      el("button.btn", { type: "button", onclick: () => host().requestLogin() }, "登入")));
    return;
  }
  main.replaceChildren(el("p.ct-loading", {}, "載入中…"));
  try {
    await loadCourse();
  } catch (err) {
    if (mine !== token) return;
    const msg = err instanceof CourseUnavailable ? "課程內容未安裝。"
      : err.status === 401 ? "登入已過期，請重新登入。" : "暫時載入唔到課程，請稍後再試。";
    main.replaceChildren(el("p.ct-error", {}, msg), el("button.btn.ghost", { type: "button", onclick: render }, "再試"));
    return;
  }
  if (mine !== token) return;
  main.replaceChildren();
  try {
    cleanup = await view.render(main, ...match.slice(1));
  } catch (err) {
    console.error(err);
    main.replaceChildren(el("p.ct-error", {}, `出錯了：${err.message}`));
  }
  applyToggles(root);
  main.focus({ preventScroll: true });
}

function reset() {
  resetCourse();
  if (visible()) render();
}

function hide() {
  stop();
  if (typeof cleanup === "function") cleanup();
  cleanup = null;
}

// Count study time while this tab is showing and the learner was active in the last 2 minutes.
let lastActive = Date.now();
["pointerdown", "keydown", "scroll", "touchstart"].forEach((e) =>
  window.addEventListener(e, () => { lastActive = Date.now(); }, { passive: true }));
setInterval(() => {
  if (visible() && host().isSignedIn() && document.visibilityState === "visible" && Date.now() - lastActive < 120000) addTime(15);
}, 15000);

window.SabrinaCantoneseApp = { render, reset, hide };
if (visible()) render();
