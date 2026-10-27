// 小測: 10 mixed multiple-choice questions drawn from learned cards (or one lesson's cards).
import { getCourse } from "../data.js";
import * as store from "../store.js";
import { GRADES } from "../core.js";
import { speak } from "../speech.js";
import { el, jp, yue, zh, sample, shuffle, progressBar } from "../ui.js";

const N = 10;

// Question types. Each returns null when the card can't support it.
const TYPES = {
  listen: (card, pool) => ({
    prompt: el("div", {}, el("p.ask", {}, "聽讀音，揀啱嘅寫法")),
    say: card.yue,
    answer: card.yue,
    options: distract(card, pool, (c) => c.yue),
    render: (o) => yue(o),
  }),
  meaning: (card, pool) => card.zh && card.kind !== "translate" ? {
    prompt: el("div", {}, el("p.ask", {}, "呢句廣東話即係普通話嘅…"), yue(card.yue, "big")),
    say: card.yue,
    answer: card.zh,
    options: distract(card, pool.filter((c) => c.zh), (c) => c.zh),
    render: (o) => zh(o),
  } : null,
  reverse: (card, pool) => card.zh ? {
    prompt: el("div", {}, el("p.ask", {}, "用廣東話點講？"), zh(card.zh)),
    answer: card.yue,
    options: distract(card, pool.filter((c) => c.zh), (c) => c.yue),
    render: (o) => yue(o),
    sayAfter: card.yue,
  } : null,
  jyutping: (card, pool) => card.jp && card.yue.length <= 8 ? {
    prompt: el("div", {}, el("p.ask", {}, "揀啱嘅粵拼"), yue(card.yue, "big")),
    answer: card.jp,
    options: distract(card, pool.filter((c) => c.jp), (c) => c.jp, true),
    render: (o) => jp(o),
    sayAfter: card.yue,
  } : null,
};

// Prefer distractors of the same kind and similar length.
function distract(card, pool, key, similarJp = false) {
  const right = key(card);
  const cands = pool.filter((c) => c.id !== card.id && key(c) && key(c) !== right);
  const score = (c) => (c.kind === card.kind ? 0 : 2) + Math.abs(key(c).length - right.length) / 4 + Math.random() * 1.5;
  let picks = cands.sort((a, b) => score(a) - score(b)).map(key);
  if (similarJp) {
    // tone/near-sound distractors: same letters, different tone digits
    const toneSwap = right.replace(/\d/, (d) => String((Number(d) % 6) + 1));
    picks = [toneSwap, ...picks];
  }
  const uniq = [...new Set(picks)].filter((x) => x !== right).slice(0, 3);
  return shuffle([right, ...uniq]);
}

export function render(main, lessonId) {
  const course = getCourse();
  const scoped = lessonId ? course.cardsByLesson[lessonId] || [] : null;
  const pool = (scoped || store.learnedIds().map((id) => course.cardById[id]).filter(Boolean));
  const distractPool = pool.length >= 8 ? pool : course.cards;
  main.append(el("h1", {}, lessonId ? "本課小測" : "小測"));
  if (pool.length < 4) {
    main.append(el("section.card.ct-empty", {}, el("p", {}, "學多幾課，有足夠詞彙先可以做小測。"), el("a.btn", { href: "#cantonese" }, "返今日")));
    return;
  }
  // weight towards cards that are due or were forgotten
  const weighted = shuffle(pool).sort((a, b) => (store.cardState(b.id)?.lapses || 0) - (store.cardState(a.id)?.lapses || 0));
  const chosen = sample(weighted.slice(0, Math.max(N * 2, 20)), Math.min(N, pool.length));
  const qs = chosen.map((card) => {
    const types = shuffle(Object.keys(TYPES));
    for (const t of types) {
      const q = TYPES[t](card, distractPool);
      if (q && q.options.length >= 3) return { ...q, card };
    }
    return null;
  }).filter(Boolean);

  let i = 0, right = 0;
  const bar = el("div.revbar");
  const stage = el("section.flash.quiz");
  main.append(bar, stage);

  const show = () => {
    bar.replaceChildren(el("span", {}, `${i} / ${qs.length}`), progressBar(i, qs.length, "小測進度"));
    if (i >= qs.length) {
      store.logQuiz(right, qs.length);
      const pct = Math.round((right / qs.length) * 100);
      stage.replaceChildren(el("div.face", {}, el("p.big", {}, `${right} / ${qs.length}`),
        el("p", {}, pct >= 80 ? "好叻！" : pct >= 50 ? "唔錯，繼續努力。" : "唔緊要，答錯嘅卡片會早啲再出現。")),
        el("div.ct-actions", {}, el("button.btn", { type: "button", onclick: () => { main.replaceChildren(); render(main, lessonId); } }, "再做一次"),
          el("a.btn.ghost", { href: "#cantonese" }, "返今日")));
      return;
    }
    const q = qs[i];
    const fb = el("p.gstatus", { "aria-live": "polite" });
    const opts = el("div.opts.col", {}, q.options.map((o) => el("button.opt", {
      type: "button",
      onclick: (e) => {
        if (opts.dataset.done) return;
        opts.dataset.done = "1";
        const ok = o === q.answer;
        if (ok) right += 1;
        else if (store.cardState(q.card.id)) store.grade(q.card.id, GRADES.again);
        e.currentTarget.classList.add(ok ? "is-right" : "is-wrong");
        [...opts.children].forEach((b) => { if (b.dataset.v === q.answer) b.classList.add("is-right"); });
        fb.replaceChildren(ok ? "✓ 啱！" : "✗ 正確答案已標出", " ", yue(q.card.yue), q.card.jp ? jp(q.card.jp) : null);
        if (q.sayAfter || !ok) speak(q.card.yue);
        stage.append(el("button.btn.big", { type: "button", onclick: () => { i += 1; show(); } }, i + 1 < qs.length ? "下一題" : "睇結果"));
      },
      "data-v": o,
    }, q.render(o))));
    stage.replaceChildren(q.prompt, q.say ? el("button.btn.ghost.small", { type: "button", onclick: () => speak(q.say) }, "🔊 再聽") : null, opts, fb);
    if (q.say) speak(q.say);
  };
  show();
}
