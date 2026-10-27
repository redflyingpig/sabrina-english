// 課程: the course map.
import { getCourse, lessonSummary, shortUnit } from "../data.js";
import { isLessonDone } from "../store.js";
import { el, progressBar } from "../ui.js";

export function render(main) {
  const course = getCourse();
  const next = course.lessons.find((l) => !isLessonDone(l.id));
  main.append(el("h1", {}, "課程"));
  for (const [g, name] of Object.entries(course.groups)) {
    main.append(el("h2.group", {}, `(${g}) ${name}`));
    for (const u of course.units.filter((x) => x.group === g)) {
      const ls = course.lessons.filter((l) => l.u === u.id);
      const done = ls.filter((l) => isLessonDone(l.id)).length;
      const { num, name: uname } = shortUnit(u);
      const open = next ? next.u === u.id : false;
      main.append(el("details.unit", { open: open || undefined },
        el("summary", {},
          el("span.unum", {}, num),
          el("span.uname", {}, uname),
          el("small", {}, `${done}/${ls.length}${u.hours ? ` · 自修 ${u.hours.self}h` : ""}`),
          progressBar(done, ls.length, `${uname} 進度`)),
        u.sections.map((s) => el("div.sec", {},
          el("h3", {}, s.title.replace(/[：:]$/, "")),
          el("ol.lessons", {}, s.lessons.map((l) => el("li", {},
            el("a", {
              href: `#cantonese/lesson/${l.id}`,
              class: [isLessonDone(l.id) ? "done" : "", next && next.id === l.id ? "next" : ""].join(" ").trim() || undefined,
            },
              el("span.check", { "aria-hidden": "true" }, isLessonDone(l.id) ? "✓" : next && next.id === l.id ? "▶" : ""),
              el("span", {}, l.part[1] > 1 ? `第 ${l.part[0]} 部分` : "學習"),
              el("small", {}, lessonSummary(s, l)),
            )))))),
      ));
    }
  }
}
