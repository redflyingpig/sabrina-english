// Interactive workbook exercises. Answers typed by the learner are saved.
import { el, speakBtn, yue, jp, zh, sample, shuffle } from "./ui.js";
import { speak } from "./speech.js";
import { getAnswer, setAnswer } from "./store.js";

const norm = (s) => String(s || "").replace(/[\s，。！？、,.!?「」]/g, "");
const accepts = (answer) => String(answer).split(/[／/]/).map(norm).filter(Boolean);

function reveal(label, ...content) {
  const box = el("div.answer", { hidden: true }, content);
  const btn = el("button.btn.small.ghost", { type: "button", "aria-expanded": "false" }, label);
  btn.addEventListener("click", () => {
    box.hidden = !box.hidden;
    btn.setAttribute("aria-expanded", String(!box.hidden));
  });
  return [btn, box];
}

// 近音字: chips to hear, plus a "which one did you hear?" game.
export function near(item) {
  const groups = item.groups.filter((g) => g.length > 1);
  const list = el("div.near", {}, item.groups.map((g) => el("div.ngroup", {},
    g.map((w) => el("button.nword", { type: "button", onclick: () => speak(w.yue) }, yue(w.yue), jp(w.jp))))));
  const game = el("div.game");
  const status = el("p.gstatus", { "aria-live": "polite" });
  let score = 0, total = 0;
  const round = () => {
    const g = sample(groups, 1)[0];
    const target = sample(g, 1)[0];
    game.replaceChildren(
      el("p", {}, "聽讀音，揀出聽到嘅詞語："),
      el("button.btn", { type: "button", onclick: () => speak(target.yue) }, "🔊 再聽一次"),
      el("div.opts", {}, shuffle(g).map((w) => el("button.opt", {
        type: "button",
        onclick: (e) => {
          total += 1;
          const ok = w.yue === target.yue;
          if (ok) score += 1;
          e.currentTarget.classList.add(ok ? "is-right" : "is-wrong");
          status.textContent = `${ok ? "啱！" : `唔啱，係「${target.yue}」${target.jp}`}　${score}/${total}`;
          setTimeout(round, ok ? 700 : 1800);
        },
      }, w.yue))));
    speak(target.yue);
  };
  const start = el("button.btn", { type: "button", onclick: round }, "▶ 開始聽音小測");
  game.append(start);
  return el("section", {}, list, el("div.gamebox", {}, game, status));
}

// 拼音讀寫練習: read the jyutping, write the word.
export function jp2char(item, key) {
  return el("ol.qs", {}, item.qs.map((q) => {
    const k = `${key}:${q.n}`;
    const input = el("input", { type: "text", lang: "zh-HK", "aria-label": `${q.jp} 的廣東話`, value: getAnswer(k) || "" });
    const fb = el("span.fb", { "aria-live": "polite" });
    const check = () => {
      setAnswer(k, input.value);
      const ok = accepts(q.a).includes(norm(input.value));
      fb.textContent = input.value ? (ok ? "✓" : "✗") : "";
      fb.className = `fb ${ok ? "is-right" : "is-wrong"}`;
    };
    input.addEventListener("change", check);
    const [btn, box] = reveal("答案", yue(q.a), speakBtn(q.a));
    return el("li.q", {}, jp(q.jp), input, fb, btn, box);
  }));
}

// 填普通話詞語
export function fill(item, key) {
  return el("ol.qs", {}, item.qs.map((q) => {
    if (q.example) return el("li.q.is-example", {}, "例：", yue(q.q), " → ", zh(q.a));
    const k = `${key}:${q.n}`;
    const input = el("input", { type: "text", "aria-label": `${q.q} 的普通話`, value: getAnswer(k) || "" });
    const fb = el("span.fb", { "aria-live": "polite" });
    input.addEventListener("change", () => {
      setAnswer(k, input.value);
      const ok = accepts(q.a).includes(norm(input.value));
      fb.textContent = input.value ? (ok ? "✓" : "參考") : "";
      fb.className = `fb ${ok ? "is-right" : "is-wrong"}`;
    });
    const [btn, box] = reveal("參考答案", zh(q.a));
    return el("li.q", {}, yue(q.q), speakBtn(q.q), input, fb, btn, box);
  }));
}

// 圈出廣東話所選用的單字
export function pick(item) {
  return el("div.picks", {}, item.qs.map((q) => {
    const fb = el("span.fb", { "aria-live": "polite" });
    const chars = [...q.q];
    const good = [q.a, q.also].filter(Boolean);
    const btns = chars.map((c) => el("button.opt", {
      type: "button", lang: "zh-HK",
      onclick: (e) => {
        const ok = good.includes(c);
        e.currentTarget.classList.add(ok ? "is-right" : "is-wrong");
        fb.textContent = ok ? `✓ 粵語講「${q.a}」` : `參考：「${q.a}」`;
        speak(q.a);
      },
    }, c));
    return el("div.pickq", { class: q.example ? "is-example" : undefined },
      el("span.num", {}, q.example ? "例" : q.n), el("div.opts", {}, btns), fb);
  }));
}

// 普通話 → 廣東話 sentence conversion, self-checked.
export function translate(item, key) {
  return el("ol.qs.translate", {}, item.qs.map((q) => {
    const k = `${key}:${q.n}`;
    const area = el("textarea", { rows: 2, lang: "zh-HK", "aria-label": `把「${q.zh}」改寫成廣東話` }, getAnswer(k) || "");
    area.addEventListener("change", () => setAnswer(k, area.value));
    const [btn, box] = reveal("參考答案",
      el("div.pline", {}, yue(q.yue), speakBtn(q.yue)), jp(q.jp), q.tip ? el("p.tip", {}, q.tip) : null);
    return el("li.q", {}, zh(q.zh), area, btn, box);
  }));
}
