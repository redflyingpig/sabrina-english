// Renders one lesson item (vocab table, dialogue, particle …) to DOM.
import { el, speakBtn, yue, jp, zh } from "./ui.js";
import { speak, stop } from "./speech.js";
import * as ex from "./exercises.js";

let playToken = 0;

// Read a list of lines aloud one after another, highlighting each row.
export async function playSequence(lines, rows, btn) {
  const token = ++playToken;
  if (btn?.classList.contains("on")) { stop(); btn.classList.remove("on"); return; }
  btn?.classList.add("on");
  for (let i = 0; i < lines.length; i++) {
    if (token !== playToken) break;
    rows[i]?.classList.add("now");
    rows[i]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    await speak(lines[i]);
    rows[i]?.classList.remove("now");
  }
  if (token === playToken) btn?.classList.remove("on");
}

const sub = (item) => el("h3.sub", {}, item.text);
const text = (item) => el("p.text", {}, item.text);
const note = (item) => el("aside.note", {}, el("b", {}, "解釋　"), item.text);

function vocab(item) {
  const head = item.part ? el("p.part", {}, `第 ${item.part[0]} / ${item.part[1]} 部分`) : null;
  const rows = item.rows.map((r) =>
    el("li.vrow", {},
      r.n ? el("span.num", {}, r.n) : null,
      el("div.vmain", {}, yue(r.yue), jp(r.jp)),
      r.zh ? zh(r.zh) : null,
      speakBtn(r.yue)));
  return el("div.vocab", {}, head, el("ol.vlist", {}, rows));
}

function pairs(item) {
  return el("div.pairs", {}, item.rows.map((r) => {
    const segs = r.yue.map((y, i) => el("div.pair", {},
      el("div.pline", {}, yue(y), speakBtn(y)),
      r.zh[i] ? zh(r.zh[i]) : null));
    const extra = r.zh.slice(r.yue.length).map((z) => zh(z));
    return el("div.pblock", {}, segs, extra);
  }));
}

function particle(item) {
  return el("section.particle", {},
    el("header", {}, el("span.pword", { lang: "zh-HK" }, item.p), item.jp ? jp(item.jp) : null, speakBtn(item.p.split("/")[0])),
    el("p", {}, item.desc),
    item.ex.map((e) => el("div.pair", {}, el("div.pline", {}, yue(e.yue), speakBtn(e.yue)), zh(e.zh))));
}

export function dialogueLines(item, { compact = false } = {}) {
  const rows = item.lines.map((l) => el("li.dline", {},
    el("span.spk", {}, l.s),
    el("div.dtext", {}, yue(l.t), l.jp ? jp(l.jp) : null),
    speakBtn(l.t)));
  const list = el("ol.dlines", { class: compact ? "compact" : undefined }, rows);
  return { list, rows };
}

function dialogue(item) {
  const { list, rows } = dialogueLines(item);
  const play = el("button.btn.small", { type: "button" }, "▶ 全段播放");
  play.addEventListener("click", () => playSequence(item.lines.map((l) => l.t), rows, play));
  return el("section.dialogue", {},
    el("header", {}, el("h3", {}, item.title),
      el("div.ct-actions", {}, play, el("a.btn.small.ghost", { href: `#cantonese/dialogue/${item.id}` }, "角色扮演 →"))),
    list);
}

function tones(item) {
  return el("ul.tones", {}, item.rows.map((r) => el("li", {},
    el("div.tcell", {}, yue(r.base.yue), jp(r.base.jp), speakBtn(r.base.yue)),
    el("span.arrow", { "aria-hidden": "true" }, "→"),
    el("div.tcell.changed", {}, yue(r.changed.yue), jp(r.changed.jp), speakBtn(r.changed.yue)))));
}

const chip = (t, extra) => el("button.chipbtn", { type: "button", lang: "zh-HK", onclick: () => speak(t) }, t, extra ? el("small", {}, extra) : null);

function phon(item) {
  return el("div.phon", { class: item.kind },
    item.cells.map((c) => el("div.pcell", {}, el("b.letter", {}, c.l), el("div", {}, c.ex.map((x) => chip(x))))));
}

function tonechart(item) {
  return el("table.tonechart", {},
    el("thead", {}, el("tr", {}, el("th", {}, ""), item.header.map((h) => el("th", { scope: "col" }, `第${h}聲`)))),
    el("tbody", {}, item.rows.map((r) => el("tr", {}, el("th", { scope: "row" }, r[0]),
      r.slice(1).map((c) => el("td", {}, /[a-z]\d/.test(c) ? jp(c) : chip(c)))))));
}

function poem(item) {
  const lines = [item.title, ...item.lines];
  const rows = lines.map((l, i) => el("li", { class: i ? undefined : "ptitle" }, yue(l.yue), jp(l.jp)));
  const play = el("button.btn.small", { type: "button" }, "▶ 朗讀全詩");
  play.addEventListener("click", () => playSequence(lines.map((l) => l.yue), rows, play));
  return el("section.poem", {}, el("ol", {}, rows), play);
}

function links(item) {
  return el("ul.links", {}, item.rows.map((r) => el("li", {},
    r.url ? el("a", { href: r.url, target: "_blank", rel: "noopener" }, r.name) : el("span", {}, r.name),
    r.desc ? el("small", {}, r.desc) : null)));
}

const mono = (item) => el("div.chips", {}, item.rows.map((r) => chip(r.yue, r.zh)));
const chips = (item) => el("div.chips", {}, item.cells.map((c) => chip(c)));

const RENDER = { sub, text, note, vocab, pairs, particle, dialogue, tones, phon, tonechart, poem, links, mono, chips,
  near: ex.near, jp2char: ex.jp2char, fill: ex.fill, pick: ex.pick, translate: ex.translate };

export function renderItem(item, key) {
  const fn = RENDER[item.type];
  return fn ? fn(item, key) : el("pre", {}, JSON.stringify(item, null, 1));
}
