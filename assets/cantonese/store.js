// 廣東話 progress, kept in this profile's localStorage key and synced to the
// Mac mini through the page's normal profile sync (host.changed()).
// Every write re-reads storage first, so a background profile sync that merged
// in progress from another device is never overwritten by a stale copy.
import { host } from "./host.js";

const C = globalThis.SabrinaCantonese;
const DEFAULT_SETTINGS = { jp: true, zh: true, rate: 0.9, voice: "", reviewCap: 60, autoSpeak: true };

function read() {
  try {
    return C.normalizeState(JSON.parse(localStorage.getItem(host().storageKey()) || "null"));
  } catch {
    return C.emptyState();
  }
}

function write(state, { sync = true } = {}) {
  localStorage.setItem(host().storageKey(), JSON.stringify(state));
  if (sync) host().changed();
}

function update(fn, opts) {
  const s = read();
  const result = fn(s);
  write(s, opts);
  return result;
}

export const today = () => C.dayNumber();

export function dateKey(d = new Date()) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const blankDay = () => ({ sec: 0, reviews: 0, newLessons: 0, quiz: [0, 0], dialogues: [] });
const dayOf = (s, key = dateKey()) => (s.days[key] ||= blankDay());

export const day = (key = dateKey()) => read().days[key] || blankDay();

export const settings = () => ({ ...DEFAULT_SETTINGS, ...read().settings });
export function setSetting(k, v) { update((s) => { s.settings[k] = v; }); }

// ---- lessons ---------------------------------------------------------------
export const isLessonDone = (id) => id in read().lessons;

export function completeLesson(lesson, cardIds) {
  update((s) => {
    if (!(lesson.id in s.lessons)) {
      s.lessons[lesson.id] = today();
      dayOf(s).newLessons += 1;
    }
    for (const id of cardIds) if (!s.cards[id]) s.cards[id] = C.newCard(today());
  });
  host().studied();
}

export function undoLesson(id) { update((s) => { delete s.lessons[id]; }); }

// ---- cards -----------------------------------------------------------------
export const cardState = (id) => read().cards[id];
export const learnedIds = () => Object.keys(read().cards);
export function dueIds() {
  const { cards } = read();
  const t = today();
  return Object.keys(cards).filter((id) => C.isDue(cards[id], t)).sort((a, b) => cards[a].due - cards[b].due);
}
export const matureCount = () => Object.values(read().cards).filter(C.isMature).length;

export function grade(id, g) {
  const next = update((s) => {
    s.cards[id] = C.schedule(s.cards[id] || C.newCard(today()), g, today());
    dayOf(s).reviews += 1;
    return s.cards[id];
  });
  host().studied();
  return next;
}

// ---- other activity --------------------------------------------------------
export function logQuiz(right, total) {
  update((s) => {
    const q = dayOf(s).quiz;
    q[0] += right;
    q[1] += total;
  });
  host().studied();
}

export function logDialogue(id) {
  update((s) => {
    s.dialogues[id] = (s.dialogues[id] || 0) + 1;
    const d = dayOf(s);
    if (!d.dialogues.includes(id)) d.dialogues.push(id);
  });
}
export const dialogueCount = (id) => read().dialogues[id] || 0;

// Study time ticks every 15s; only sync it every few minutes to keep PUTs rare.
let lastTimeSync = 0;
export function addTime(sec) {
  const sync = Date.now() - lastTimeSync > 180000;
  if (sync) lastTimeSync = Date.now();
  update((s) => { dayOf(s).sec += sec; }, { sync });
}

export const getAnswer = (k) => read().answers[k];
export function setAnswer(k, v) { update((s) => { s.answers[k] = String(v).slice(0, 300); }); }

export function history() {
  return Object.entries(read().days).sort(([a], [b]) => (a < b ? 1 : -1));
}

const active = (d) => d && (d.sec >= 60 || d.reviews || d.newLessons || (d.quiz && d.quiz[1]));

export function streak() {
  const { days } = read();
  let n = 0;
  const d = new Date();
  if (!active(days[dateKey(d)])) d.setDate(d.getDate() - 1); // today not started yet
  while (active(days[dateKey(d)])) { n += 1; d.setDate(d.getDate() - 1); }
  return n;
}
