// 溫習: spaced-repetition flashcards. Front = Cantonese (heard + read), back = jyutping + meaning.
import { getCourse } from "../data.js";
import * as store from "../store.js";
import { GRADES, intervalLabel } from "../core.js";
import { speak } from "../speech.js";
import { el, jp, zh, yue, progressBar } from "../ui.js";

const KIND = { word: "詞彙", phrase: "短句", sentence: "句子", particle: "助詞", tone: "變調",
  near: "近音字", mono: "單音節詞", translate: "粵普轉換" };

function front(card) {
  // 粵普轉換 and 普通話-only cards are asked from Mandarin; everything else from Cantonese.
  if (card.kind === "translate") return el("div.face", {}, el("p.ask", {}, "用廣東話講："), zh(card.zh));
  return el("div.face", {}, yue(card.yue, "big"), card.hint && card.kind !== "particle" ? el("p.hint", {}, card.hint) : null);
}

function back(card) {
  return el("div.face.back", {},
    card.kind === "translate" ? yue(card.yue, "big") : null,
    card.jp ? jp(card.jp) : null,
    card.zh && card.kind !== "translate" ? zh(card.zh) : null,
    card.kind === "particle" ? el("p.hint", {}, card.hint) : null,
    card.note ? el("p.note", {}, card.note) : null);
}

export function render(main, mode) {
  const course = getCourse();
  const today = store.today();
  let queue;
  if (mode === "all") queue = store.learnedIds();
  else queue = store.dueIds().slice(0, store.settings().reviewCap);
  queue = queue.filter((id) => course.cardById[id]);
  const total = queue.length;
  let done = 0;

  main.append(el("h1", {}, "溫習"));
  if (!total) {
    const learned = store.learnedIds().length;
    main.append(el("section.card.ct-empty", {},
      el("p", {}, learned ? "今日嘅卡片已經溫完 👏" : "未有卡片。完成一課之後，課入面嘅詞彙會變成溫習卡片。"),
      learned ? el("a.btn.ghost", { href: "#cantonese/review/all" }, `額外溫習全部 ${learned} 張`) : el("a.btn", { href: "#cantonese" }, "返今日"),
      learned >= 4 ? el("a.btn.ghost", { href: "#cantonese/quiz" }, "做小測") : null));
    return;
  }

  const bar = el("div.revbar");
  const stage = el("section.flash");
  main.append(bar, stage);

  const onKey = (e) => {
    if (e.target.closest("input,textarea")) return;
    const k = e.key;
    if (k === " " || k === "Enter") { e.preventDefault(); stage.querySelector(".show-btn")?.click(); }
    const map = { 1: "again", 2: "hard", 3: "good", 4: "easy" };
    if (map[k]) stage.querySelector(`[data-g="${map[k]}"]`)?.click();
    if (k === "r") stage.querySelector(".replay")?.click();
  };
  document.addEventListener("keydown", onKey);

  const next = () => {
    bar.replaceChildren(el("span", {}, `${done} / ${total}`), progressBar(done, total, "溫習進度"));
    if (!queue.length) {
      stage.replaceChildren(el("div.face", {}, el("p.big", {}, "完成 🎉"), el("p", {}, `今日溫咗 ${store.day().reviews} 張`)),
        el("div.ct-actions", {}, el("a.btn", { href: "#cantonese" }, "返今日"), el("a.btn.ghost", { href: "#cantonese/quiz" }, "做小測")));
      return;
    }
    const id = queue.shift();
    const card = course.cardById[id];
    const st = store.cardState(id) || { due: today, ivl: 0, ease: 2.5, reps: 0, lapses: 0 };
    const sayText = card.yue;
    const replay = el("button.btn.ghost.small.replay", { type: "button", onclick: () => speak(sayText) }, "🔊 讀音");
    const showBtn = el("button.btn.big.show-btn", { type: "button" }, "睇答案");
    const lessonLink = el("a.small.muted", { href: `#cantonese/lesson/${card.lesson}` }, "去返課文");
    stage.replaceChildren(
      el("p.kind", {}, KIND[card.kind] || ""),
      front(card),
      card.kind !== "translate" ? replay : null,
      showBtn);
    if (card.kind !== "translate" && store.settings().autoSpeak) speak(sayText);

    showBtn.addEventListener("click", () => {
      if (card.kind === "translate") speak(sayText);
      const grades = el("div.grades", {}, [
        ["again", "唔記得", GRADES.again], ["hard", "難", GRADES.hard], ["good", "記得", GRADES.good], ["easy", "好易", GRADES.easy],
      ].map(([key, label, g]) => el("button.grade", {
        type: "button", "data-g": key, class: key,
        onclick: () => {
          store.grade(id, g);
          if (g === GRADES.again) queue.splice(Math.min(queue.length, 4), 0, id); // see it again soon
          else done += 1;
          next();
        },
      }, el("b", {}, label), el("small", {}, intervalLabel(st, g, today)))));
      showBtn.replaceWith(back(card), card.kind === "translate" ? replay : null, grades, lessonLink);
    });
  };
  next();
  return () => document.removeEventListener("keydown", onKey);
}
