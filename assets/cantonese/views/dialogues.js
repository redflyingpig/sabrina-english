// 對話: list of all 24 workbook dialogues, and a practice page with 3 modes.
import { getCourse, shortUnit } from "../data.js";
import * as store from "../store.js";
import { speak, stop, canRecord, startRecording } from "../speech.js";
import { dialogueLines, playSequence } from "../render.js";
import { el, toggleBar, yue, jp } from "../ui.js";

export function render(main) {
  const course = getCourse();
  main.append(el("h1", {}, "對話練習"), el("p.muted", {}, "教材全部 24 段對話。可以聽全段、角色扮演，或者逐句跟讀錄音。"));
  let lastUnit = null;
  const list = el("ul.dlist");
  for (const d of course.dialogues) {
    if (d.u !== lastUnit) {
      lastUnit = d.u;
      list.append(el("li.dunit", {}, shortUnit(course.unitById[d.u]).name));
    }
    const n = store.dialogueCount(d.id);
    list.append(el("li", {}, el("a", { href: `#cantonese/dialogue/${d.id}` },
      el("span", {}, d.title.replace(/^對話\s*\d+\s*[-–]\s*/, "")),
      el("small", {}, `${d.roles.join("、")} · ${d.n} 句${n ? ` · 練咗 ${n} 次` : ""}`))));
  }
  main.append(list);
}

export function renderOne(main, id) {
  const course = getCourse();
  const item = course.dialogueById[id];
  if (!item) { main.append(el("p.error", {}, "搵唔到呢段對話。")); return; }
  const meta = course.dialogues.find((d) => d.id === id);
  const stage = el("div.dstage");
  const modes = el("div.modes", { role: "tablist" });
  const MODES = { listen: "聽全段", role: "角色扮演", shadow: "逐句跟讀" };
  let mode = "listen";

  const paint = () => {
    stop();
    modes.replaceChildren(...Object.entries(MODES).map(([k, label]) => el("button.mode", {
      type: "button", role: "tab", "aria-selected": String(k === mode),
      onclick: () => { mode = k; paint(); },
    }, label)));
    stage.replaceChildren(({ listen, role, shadow })[mode](item));
  };

  main.append(
    el("nav.crumbs", {}, el("a", { href: "#cantonese/dialogues" }, "對話"), " › ", shortUnit(course.unitById[meta.u]).name),
    el("h1", {}, item.title),
    toggleBar(), modes, stage);
  paint();
  store.logDialogue(id);
  return () => stop();
}

function listen(item) {
  const { list, rows } = dialogueLines(item);
  const play = el("button.btn", { type: "button" }, "▶ 播放全段");
  play.addEventListener("click", () => playSequence(item.lines.map((l) => l.t), rows, play));
  return el("div", {}, play, list);
}

// Pick a role; the app reads the other parts, and pauses on yours.
function role(item) {
  const box = el("div");
  const pickRole = (r) => {
    const { list, rows } = dialogueLines(item);
    rows.forEach((row, i) => { if (item.lines[i].s === r) row.classList.add("mine"); });
    let i = 0, running = false;
    const status = el("p.gstatus", { "aria-live": "polite" });
    const btn = el("button.btn.big", { type: "button" }, "▶ 開始");
    const step = async () => {
      running = true;
      while (i < item.lines.length) {
        rows.forEach((x) => x.classList.remove("now"));
        const row = rows[i], line = item.lines[i];
        row.classList.add("now");
        row.scrollIntoView({ block: "center", behavior: "smooth" });
        if (line.s === r) {
          row.classList.add("hidden-line");
          status.textContent = `輪到你（${r}）講，講完撳「下一句」`;
          btn.textContent = "下一句 ›";
          running = false;
          return;
        }
        status.textContent = `${line.s}：…`;
        await speak(line.t);
        i += 1;
      }
      status.textContent = "完成 👏 想再練就換另一個角色。";
      btn.textContent = "↺ 再嚟";
      running = false;
      i = item.lines.length + 1;
    };
    btn.addEventListener("click", () => {
      if (running) return;
      if (i > item.lines.length) { pickRole(r); return; }
      const row = rows[i];
      if (row?.classList.contains("hidden-line")) {
        row.classList.remove("hidden-line");
        speak(item.lines[i].t); // let her hear the model line after saying it
        i += 1;
        setTimeout(step, 400);
        return;
      }
      step();
    });
    box.replaceChildren(el("p", {}, `你做「${r}」。你嘅句子會先收埋，講完再睇答案同聽示範。`), btn, status, list);
  };
  box.append(el("p", {}, "揀你想做嘅角色："),
    el("div.opts", {}, item.roles.map((r) => el("button.opt", { type: "button", onclick: () => pickRole(r) }, r))));
  return box;
}

// One line at a time: hear it, record yourself, compare.
function shadow(item) {
  let i = 0;
  const box = el("div.shadow");
  let audioUrl = null;
  const show = () => {
    const line = item.lines[i];
    const player = el("div.player");
    const rec = el("button.btn", { type: "button", disabled: !canRecord() || undefined }, canRecord() ? "🎙 錄音" : "此瀏覽器不支援錄音");
    let stopFn = null;
    rec.addEventListener("click", async () => {
      if (stopFn) {
        audioUrl = await stopFn();
        stopFn = null;
        rec.textContent = "🎙 重錄";
        rec.classList.remove("rec");
        const a = el("audio", { controls: true, src: audioUrl });
        player.replaceChildren(el("small", {}, "你嘅錄音："), a);
        a.play();
        return;
      }
      try {
        stopFn = await startRecording();
        rec.textContent = "■ 停止";
        rec.classList.add("rec");
      } catch {
        rec.textContent = "未允許使用咪高峰";
      }
    });
    box.replaceChildren(
      el("p.muted", {}, `第 ${i + 1} / ${item.lines.length} 句`),
      el("div.face", {}, el("p.spk", {}, line.s), yue(line.t, "big"), line.jp ? jp(line.jp) : null),
      el("div.ct-actions", {},
        el("button.btn", { type: "button", onclick: () => speak(line.t) }, "🔊 示範"),
        el("button.btn.ghost", { type: "button", onclick: () => speak(line.t, { rate: 0.6 }) }, "🐢 慢速"),
        rec),
      player,
      el("div.pager", {},
        el("button.btn.ghost.small", { type: "button", disabled: i === 0 || undefined, onclick: () => { i -= 1; show(); } }, "‹ 上一句"),
        el("button.btn.ghost.small", { type: "button", disabled: i === item.lines.length - 1 || undefined, onclick: () => { i += 1; show(); } }, "下一句 ›")));
    speak(line.t);
  };
  show();
  return box;
}
