// Loads the course once per signed-in session (login-only: /api/cantonese/course) and indexes it.
import { host } from "./host.js";

let course = null;
let loading = null;

export class CourseUnavailable extends Error {}

export function resetCourse() {
  course = null;
  loading = null;
}

export async function loadCourse() {
  if (course) return course;
  if (!loading) {
    loading = host().apiRequest("/api/cantonese/course")
      .then((data) => { course = index(data); return course; })
      .catch((err) => {
        loading = null;
        if (err.payload?.error === "cantonese_unavailable") throw new CourseUnavailable(err.message);
        throw err;
      });
  }
  return loading;
}

function index(c) {
  c.unitById = {};
  c.sectionById = {};
  c.lessonById = {};
  c.cardById = {};
  c.cardsByLesson = {};
  c.dialogueById = {};
  for (const u of c.units) {
    c.unitById[u.id] = u;
    for (const s of u.sections) {
      c.sectionById[s.id] = s;
      for (const item of s.items) if (item.type === "dialogue") c.dialogueById[item.id] = item;
    }
  }
  c.lessons.forEach((l, i) => {
    l.index = i;
    c.lessonById[l.id] = l;
  });
  for (const card of c.cards) {
    c.cardById[card.id] = card;
    (c.cardsByLesson[card.lesson] ||= []).push(card);
  }
  return c;
}

export const getCourse = () => course;

export function lessonTitle(lesson) {
  const s = course.sectionById[lesson.s];
  const part = lesson.part[1] > 1 ? `（${lesson.part[0]}/${lesson.part[1]}）` : "";
  return `${s.title.replace(/[：:]$/, "")}${part}`;
}

// e.g. "20 個詞句 · 2 段對話"
export function lessonSummary(section, lesson) {
  const items = section.items.slice(lesson.from, lesson.to);
  const n = (t) => items.filter((i) => i.type === t);
  const parts = [];
  const words = n("vocab").reduce((a, i) => a + i.rows.length, 0);
  if (words) parts.push(`${words} 個詞句`);
  if (n("pairs").length) parts.push(`${n("pairs").length} 個情景`);
  if (n("particle").length) parts.push(`${n("particle").length} 個助詞`);
  if (n("dialogue").length) parts.push(`${n("dialogue").length} 段對話`);
  const qs = ["fill", "pick", "jp2char", "translate"].reduce((a, t) => a + n(t).reduce((b, i) => b + i.qs.length, 0), 0);
  if (qs) parts.push(`${qs} 條練習`);
  if (n("tones").length) parts.push(`${n("tones").reduce((a, i) => a + i.rows.length, 0)} 個變調`);
  if (n("near").length) parts.push("近音字");
  if (n("phon").length) parts.push("聲母韻母表");
  if (n("poem").length) parts.push("詩詞朗讀");
  if (n("links").length && !parts.length) parts.push("參考資料");
  if (n("chips").length + n("mono").length && !parts.length) parts.push("詞彙差異");
  return parts.join(" · ");
}

export function shortUnit(u) {
  const [num, name] = u.title.split("：");
  return { num, name };
}
