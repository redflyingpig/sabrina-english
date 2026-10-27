"use strict";

const assert = require("assert");
const C = require("../assets/cantonese-core.js");

function testNormalize() {
  assert.deepEqual(C.normalizeState(null), C.emptyState());
  assert.deepEqual(C.normalizeState({ cards: [], lessons: { a: 1 } }).cards, {}, "array sections dropped");
  assert.equal(C.normalizeState({ lessons: { a: 1 } }).lessons.a, 1);
  assert.equal(C.isEmpty(undefined), true);
  assert.equal(C.isEmpty({ settings: { rate: 1 } }), true, "settings alone is not progress");
  assert.equal(C.isEmpty({ lessons: { a: 1 } }), false);
}

function testMergeKeepsWorkFromBothDevices() {
  const cloud = {
    lessons: { l1: 10, l2: 12 },
    cards: { c1: { due: 20, reps: 3, at: 200 }, c2: { due: 11, reps: 1, at: 100 } },
    days: { "2026-10-26": { sec: 300, reviews: 5, newLessons: 1, quiz: [3, 5], dialogues: ["d1"] } },
    dialogues: { d1: 2 },
    answers: { q1: "cloud" },
  };
  const local = {
    lessons: { l1: 11, l3: 13 },
    cards: { c1: { due: 15, reps: 1, at: 150 }, c3: { due: 14, reps: 0, at: 10 } },
    days: { "2026-10-26": { sec: 120, reviews: 8, newLessons: 0, quiz: [9, 10], dialogues: ["d2"] } },
    dialogues: { d1: 1, d2: 1 },
    answers: { q1: "local", q2: "x" },
  };
  const m = C.merge(cloud, local);
  assert.deepEqual(Object.keys(m.lessons).sort(), ["l1", "l2", "l3"]);
  assert.equal(m.lessons.l1, 10, "earliest completion day kept");
  assert.equal(m.cards.c1.at, 200, "newer review wins");
  assert.ok(m.cards.c2 && m.cards.c3, "cards from both sides kept");
  const d = m.days["2026-10-26"];
  assert.equal(d.sec, 300);
  assert.equal(d.reviews, 8);
  assert.deepEqual(d.quiz, [9, 10]);
  assert.deepEqual(d.dialogues.sort(), ["d1", "d2"]);
  assert.equal(m.dialogues.d1, 2);
  assert.equal(m.answers.q1, "local", "this device's typed answer wins");
  assert.deepEqual(C.merge(undefined, null), C.emptyState());
}

function testSchedule() {
  const t = 1000;
  let s = C.newCard(t);
  assert.ok(C.isDue(s, t));
  s = C.schedule(s, C.GRADES.good, t);
  assert.equal(s.due, t + 1);
  s = C.schedule(s, C.GRADES.good, t + 1);
  assert.equal(s.due, t + 4);
  const longer = C.schedule(s, C.GRADES.good, t + 4);
  assert.ok(longer.ivl > s.ivl, "interval grows");
  const lapsed = C.schedule(longer, C.GRADES.again, t + 10);
  assert.equal(lapsed.due, t + 10);
  assert.equal(lapsed.lapses, 1);
  assert.ok(lapsed.ease < longer.ease);
  assert.equal(C.schedule(C.newCard(t), C.GRADES.easy, t).due, t + 3);
  assert.equal(C.intervalLabel(C.newCard(t), C.GRADES.again, t), "今日");
  assert.equal(C.isMature({ ivl: 30 }), true);
}

testNormalize();
testMergeKeepsWorkFromBothDevices();
testSchedule();
console.log("cantonese node tests: ok");
