// Small DOM helpers shared by every view.
import { speak } from "./speech.js";
import { settings, setSetting } from "./store.js";
import { host } from "./host.js";

export function el(tag, attrs = {}, ...children) {
  const [name, ...classes] = tag.split(".");
  const node = document.createElement(name || "div");
  if (classes.length) node.className = classes.join(" ");
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") node.className += (node.className ? " " : "") + v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (k === "html") node.innerHTML = v;
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat(Infinity)) {
    if (c === undefined || c === null || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

export function speakBtn(text, label = "播放讀音") {
  const b = el("button.say", { type: "button", "aria-label": `${label}：${text}`, title: label }, "🔊");
  b.addEventListener("click", async (e) => {
    e.stopPropagation();
    b.classList.add("on");
    await speak(text);
    b.classList.remove("on");
  });
  return b;
}

// Cantonese text you can tap to hear.
export function yue(text, cls = "") {
  return el("span.yue", { class: cls || undefined, lang: "zh-HK" }, text);
}

export const jp = (text) => el("span.jp", { lang: "yue-Latn" }, text);
export const zh = (text) => el("span.zh", { lang: "zh-Hans-CN" }, text);

export const toast = (msg) => host().toast(msg);

// Global show/hide switches for jyutping and Mandarin lines.
export function applyToggles(root = document.getElementById("cantoneseView")) {
  root.classList.toggle("hide-jp", !settings().jp);
  root.classList.toggle("hide-zh", !settings().zh);
}

export function toggleBar() {
  const mk = (key, label) => {
    const b = el("button.chip-toggle", { type: "button", "aria-pressed": String(settings()[key]) }, label);
    b.addEventListener("click", () => {
      setSetting(key, !settings()[key]);
      b.setAttribute("aria-pressed", String(settings()[key]));
      applyToggles();
    });
    return b;
  };
  return el("div.toggles", { role: "group", "aria-label": "顯示" }, mk("jp", "粵拼"), mk("zh", "普通話"));
}

export function progressBar(done, total, label) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  return el("div.progress", { role: "progressbar", "aria-valuenow": pct, "aria-valuemin": 0, "aria-valuemax": 100, "aria-label": label },
    el("span", { style: `width:${pct}%` }));
}

export function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export const sample = (arr, n) => shuffle(arr).slice(0, n);
