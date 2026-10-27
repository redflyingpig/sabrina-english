// One lesson: render its slice of a section, then "完成本課".
import { getCourse, lessonTitle, shortUnit } from "../data.js";
import * as store from "../store.js";
import { renderItem } from "../render.js";
import { el, toggleBar, toast } from "../ui.js";

export function render(main, id) {
  const course = getCourse();
  const lesson = course.lessonById[id];
  if (!lesson) {
    main.append(el("p.error", {}, "搵唔到呢一課。"), el("a.btn", { href: "#cantonese/course" }, "返課程"));
    return;
  }
  const unit = course.unitById[lesson.u];
  const section = course.sectionById[lesson.s];
  const items = section.items.slice(lesson.from, lesson.to);
  const cards = course.cardsByLesson[lesson.id] || [];
  const prev = course.lessons[lesson.index - 1];
  const next = course.lessons[lesson.index + 1];

  main.append(
    el("nav.crumbs", { "aria-label": "位置" }, el("a", { href: "#cantonese/course" }, "課程"), " › ", shortUnit(unit).name),
    el("header.lesson-head", {},
      el("h1", {}, lessonTitle(lesson)),
      el("p.muted", {}, `${unit.title}${cards.length ? ` · 完成後加入 ${cards.length} 張溫習卡` : ""}`),
      toggleBar()),
    el("div.items", {}, items.map((item, i) => renderItem(item, `${lesson.s}:${lesson.from + i}`))),
  );

  const doneBtn = el("button.btn.big", { type: "button" });
  const paint = () => {
    const done = store.isLessonDone(lesson.id);
    doneBtn.textContent = done ? "✓ 已完成（再撳取消）" : "完成本課";
    doneBtn.classList.toggle("ghost", done);
  };
  doneBtn.addEventListener("click", () => {
    if (store.isLessonDone(lesson.id)) {
      store.undoLesson(lesson.id);
    } else {
      store.completeLesson(lesson, cards.map((c) => c.id));
      toast(cards.length ? `已加入 ${cards.length} 張卡片` : "完成！");
      if (next) setTimeout(() => { location.hash = `#cantonese/lesson/${next.id}`; }, 900);
    }
    paint();
  });
  paint();

  main.append(el("footer.lesson-foot", {},
    doneBtn,
    el("div.pager", {},
      prev ? el("a.btn.ghost.small", { href: `#cantonese/lesson/${prev.id}` }, "‹ 上一課") : el("span"),
      cards.length ? el("a.btn.ghost.small", { href: `#cantonese/quiz/${lesson.id}` }, "考吓本課") : null,
      next ? el("a.btn.ghost.small", { href: `#cantonese/lesson/${next.id}` }, "下一課 ›") : el("span"))));
}
