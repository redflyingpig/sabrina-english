// 廣東話 tab: progress state, merge and spaced-repetition scheduling.
// Pure functions, loaded as a classic script so index.html can merge profile state
// synchronously, and testable in node (tests/cantonese_node_test.js).
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.SabrinaCantonese = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const SECTIONS = ["lessons", "cards", "days", "dialogues", "answers", "settings"];
  const GRADES = { again: 0, hard: 1, good: 2, easy: 3 };

  const isObj = (x) => !!x && typeof x === "object" && !Array.isArray(x);

  function emptyState() {
    return { lessons: {}, cards: {}, days: {}, dialogues: {}, answers: {}, settings: {} };
  }

  function normalizeState(state) {
    const out = emptyState();
    if (!isObj(state)) return out;
    for (const key of SECTIONS) if (isObj(state[key])) out[key] = state[key];
    return out;
  }

  function isEmpty(state) {
    const s = normalizeState(state);
    return !Object.keys(s.lessons).length && !Object.keys(s.cards).length && !Object.keys(s.days).length;
  }

  // ---- merge (phone + laptop, or local + server) --------------------------
  function newerCard(a, b) {
    if (!isObj(a)) return b;
    if (!isObj(b)) return a;
    if ((a.at || 0) !== (b.at || 0)) return (a.at || 0) > (b.at || 0) ? a : b;
    return (a.reps || 0) >= (b.reps || 0) ? a : b;
  }

  function mergeDay(a, b) {
    if (!isObj(a)) return b;
    if (!isObj(b)) return a;
    const qa = Array.isArray(a.quiz) ? a.quiz : [0, 0];
    const qb = Array.isArray(b.quiz) ? b.quiz : [0, 0];
    return {
      sec: Math.max(a.sec || 0, b.sec || 0),
      reviews: Math.max(a.reviews || 0, b.reviews || 0),
      newLessons: Math.max(a.newLessons || 0, b.newLessons || 0),
      quiz: qa[1] >= qb[1] ? qa : qb,
      dialogues: [...new Set([...(a.dialogues || []), ...(b.dialogues || [])])],
    };
  }

  function eachKey(a, b, fn) {
    const out = {};
    for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) out[k] = fn(a[k], b[k]);
    return out;
  }

  function merge(cloud, local) {
    const c = normalizeState(cloud);
    const l = normalizeState(local);
    return {
      lessons: eachKey(c.lessons, l.lessons, (x, y) => (x === undefined ? y : y === undefined ? x : Math.min(x, y))),
      cards: eachKey(c.cards, l.cards, newerCard),
      days: eachKey(c.days, l.days, mergeDay),
      dialogues: eachKey(c.dialogues, l.dialogues, (x, y) => Math.max(x || 0, y || 0)),
      answers: { ...c.answers, ...l.answers },
      settings: { ...c.settings, ...l.settings },
    };
  }

  // ---- spaced repetition (simplified SM-2); `due` is a local day number ----
  function dayNumber(date) {
    const d = date || new Date();
    return Math.floor((d.getTime() - d.getTimezoneOffset() * 60000) / 86400000);
  }

  function newCard(today) {
    return { due: today, ivl: 0, ease: 2.5, reps: 0, lapses: 0, at: Date.now() };
  }

  function schedule(state, grade, today) {
    const s = { ...state, at: Date.now() };
    if (grade === GRADES.again) {
      s.lapses += 1;
      s.reps = 0;
      s.ivl = 0;
      s.ease = Math.max(1.3, s.ease - 0.2);
      s.due = today;
      return s;
    }
    s.reps += 1;
    if (grade === GRADES.hard) s.ease = Math.max(1.3, s.ease - 0.15);
    if (grade === GRADES.easy) s.ease = Math.min(3.0, s.ease + 0.15);
    let ivl;
    if (s.reps === 1) ivl = grade === GRADES.easy ? 3 : 1;
    else if (s.reps === 2) ivl = grade === GRADES.hard ? 2 : grade === GRADES.good ? 3 : 6;
    else ivl = Math.round(s.ivl * (grade === GRADES.hard ? 1.2 : grade === GRADES.good ? s.ease : s.ease * 1.3));
    s.ivl = Math.max(1, ivl, grade === GRADES.hard ? 1 : s.ivl + 1);
    s.due = today + s.ivl;
    return s;
  }

  const isDue = (state, today) => isObj(state) && state.due <= today;
  const isMature = (state) => isObj(state) && state.ivl >= 21;

  function intervalLabel(state, grade, today) {
    const n = schedule(state, grade, today).due - today;
    if (n <= 0) return "今日";
    if (n < 30) return `${n}日`;
    if (n < 365) return `${Math.round(n / 30)}個月`;
    return `${(n / 365).toFixed(1)}年`;
  }

  return { GRADES, emptyState, normalizeState, isEmpty, merge, dayNumber, newCard, schedule, isDue, isMature, intervalLabel };
});
