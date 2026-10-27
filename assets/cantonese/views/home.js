// 今日: the daily plan.
import { getCourse, lessonTitle, shortUnit } from "../data.js";
import * as store from "../store.js";
import { cantoneseVoices, hasSpeech } from "../speech.js";
import { el, progressBar } from "../ui.js";

function nextLesson(course) {
  return course.lessons.find((l) => !store.isLessonDone(l.id));
}

function suggestDialogue(course, lesson) {
  const unitId = lesson ? lesson.u : "u9";
  const order = course.dialogues.filter((d) => d.u <= unitId || !lesson);
  const fresh = order.find((d) => !store.dialogueCount(d.id) && store.isLessonDone(lessonOfDialogue(course, d)));
  return fresh || order.sort((a, b) => store.dialogueCount(a.id) - store.dialogueCount(b.id))[0];
}

function lessonOfDialogue(course, d) {
  const s = course.sectionById[d.s];
  const idx = s.items.findIndex((i) => i.id === d.id);
  return s.lessons.find((l) => l.from <= idx && idx < l.to)?.id;
}

function task(done, title, detail, href, cta) {
  return el("li.task", { class: done ? "done" : undefined },
    el("span.check", { "aria-hidden": "true" }, done ? "✓" : ""),
    el("div", {}, el("b", {}, title), detail ? el("small", {}, detail) : null),
    href ? el("a.btn.small", { href, class: done ? "ghost" : undefined }, cta) : null);
}

export async function render(main) {
  const course = getCourse();
  const d = store.day();
  const due = store.dueIds().length;
  const lesson = nextLesson(course);
  const dlg = suggestDialogue(course, lesson);
  const learned = store.learnedIds().length;
  const doneLessons = course.lessons.filter((l) => store.isLessonDone(l.id)).length;
  const now = new Date();
  const dateStr = now.toLocaleDateString("zh-HK", { month: "long", day: "numeric", weekday: "long" });

  const tasks = el("ol.tasks", {},
    task(d.reviews > 0 && due === 0, "溫習卡片", due ? `有 ${due} 張到期` : learned ? "今日嘅卡已經溫完" : "完成第一課之後就有卡片",
      due ? "#cantonese/review" : null, "開始溫習"),
    lesson
      ? task(d.newLessons > 0, `新課：${lessonTitle(lesson)}`, shortUnit(course.unitById[lesson.u]).name, `#cantonese/lesson/${lesson.id}`, d.newLessons ? "再學一課" : "開始")
      : task(true, "全部課程已完成 🎉", "繼續溫習同對話練習就得", "#cantonese/course", "課程"),
    task(d.quiz[1] > 0, "小測 10 題", d.quiz[1] ? `今日答啱 ${d.quiz[0]}/${d.quiz[1]}` : "聽音、揀意思、揀粵拼", learned >= 4 ? "#cantonese/quiz" : null, "開始"),
    dlg ? task(d.dialogues.length > 0, `對話練習：${dlg.title}`, "跟讀或者角色扮演", `#cantonese/dialogue/${dlg.id}`, "練習") : null);

  const mins = Math.round(d.sec / 60);
  const totalSec = store.history().reduce((a, [, x]) => a + x.sec, 0);
  const totalHours = (totalSec / 3600).toFixed(1);

  main.append(
    el("section.ct-hero", {},
      el("p.date", {}, dateStr),
      el("h1", {}, "今日學乜？"),
      el("p.lead", {}, `今日已學 ${mins} 分鐘`)),
    el("section.card", {}, el("h2", {}, "今日任務"), tasks),
    el("section.card.stats", {},
      el("h2", {}, "進度"),
      el("div.statgrid", {},
        stat(`${doneLessons}/${course.lessons.length}`, "課"),
        stat(learned, "已學卡片"),
        stat(store.matureCount(), "已熟記"),
        stat(`${totalHours}h`, "總自修時間")),
      progressBar(doneLessons, course.lessons.length, "課程進度"),
      el("p.muted", {}, "教材建議自修 14.5 小時（課堂 30 小時）。")),
  );

  if (!learned) {
    main.append(el("section.card.intro", {},
      el("h2", {}, "點樣用"),
      el("ul", {},
        el("li", {}, "每日跟住「今日任務」做：溫習到期卡片 → 學一課新內容 → 做個小測。"),
        el("li", {}, "撳 🔊 聽廣東話讀音；上面嘅「粵拼／普通話」掣可以收埋提示，考吓自己。"),
        el("li", {}, "學完一課撳「完成本課」，入面嘅詞彙會自動加入溫習卡片。"),
        el("li", {}, "對話可以做角色扮演，仲可以錄低自己把聲同示範比較。")),
      el("a.btn", { href: "#cantonese/more/about" }, "睇課程簡介")));
  }

  if (!hasSpeech() || !(await cantoneseVoices()).length) {
    main.prepend(el("p.warn", {}, "呢部裝置未有廣東話（香港）語音，🔊 可能讀唔到。iPhone／Mac：設定 → 輔助使用 → 朗讀內容 → 聲音 → 中文（香港）下載一個聲音。"));
  }
}

const stat = (v, label) => el("div.stat", {}, el("b", {}, String(v)), el("small", {}, label));
