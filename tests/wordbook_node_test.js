"use strict";

const assert = require("assert");
const W = require("../assets/wordbook.js");

function word(w, zh, page = 1) {
  return { w, senses: [["n.", zh]], topic: "t", page };
}

function day(n, words) {
  return { day: n, title: `Day ${n}`, words, pages: [], topics: [], outlinePage: 0 };
}

function seeded(seed) {
  let value = seed;
  return () => {
    value = (value * 9301 + 49297) % 233280;
    return value / 233280;
  };
}

function testMergeKeepsNewestPerWord() {
  const cloud = { entries: { "1:apple": { level: 3, at: "2026-10-16T01:00:00Z" }, "1:pear": { level: 1, at: "2026-10-16T05:00:00Z" } } };
  const local = { entries: { "1:apple": { level: 1, at: "2026-10-16T02:00:00Z" }, "1:pear": { level: 3, at: "2026-10-16T04:00:00Z" }, "2:cat": { level: 2, at: "x" } } };
  const merged = W.merge(cloud, local);
  assert.equal(merged.entries["1:apple"].level, 1, "newer local apple wins");
  assert.equal(merged.entries["1:pear"].level, 1, "newer cloud pear wins");
  assert.equal(merged.entries["2:cat"].level, 2, "local-only entry kept");
  assert.deepEqual(W.merge(undefined, null), { entries: {} });
  assert.deepEqual(W.merge({ entries: "bad" }, local).entries, local.entries);
}

function testStatsAndUnlocking() {
  const d1 = day(1, [word("apple", "苹果"), word("pear", "梨"), word("plum", "李子"), word("fig", "无花果")]);
  const d2 = day(2, [word("cat", "猫")]);
  const days = [d1, d2];
  const state = { entries: { "1:apple": { level: 3 }, "1:pear": { level: 2 }, "1:plum": { level: 1 } } };
  assert.deepEqual(W.dayStats(d1, state), { total: 4, known: 1, fuzzy: 1, unknown: 1 });
  assert.equal(W.dayUnlocked(days, 0, W.emptyState()), true, "day 1 always open");
  assert.equal(W.dayUnlocked(days, 1, state), false, "25% known keeps day 2 locked");
  state.entries["1:fig"] = { level: 3 };
  assert.equal(W.dayUnlocked(days, 1, state), true, "50% known unlocks day 2");
}

function testQuizOptions() {
  const words = ["one", "two", "three", "four", "five", "six"].map((w, i) => word(w, `义${i}`));
  words.push(word("uno", "义0"));
  const quiz = W.buildQuiz(words, 5, seeded(7));
  assert.equal(quiz.length, 5);
  quiz.forEach((question, index) => {
    assert.equal(question.options.length, 4);
    assert.ok(question.options.includes(question.word), "answer is an option");
    assert.equal(new Set(question.options).size, 4, "options are distinct");
    const sameMeaning = question.options.filter((o) => o !== question.word && W.sensesText(o) === W.sensesText(question.word));
    assert.equal(sameMeaning.length, 0, "no distractor shares the answer's meaning");
    assert.equal(question.enToZh, index % 2 === 0);
  });
  assert.equal(W.buildQuiz(words.slice(0, 2), 10, seeded(1)).length, 2, "never more questions than words");
}

function testSpellingAndMask() {
  assert.ok(W.spellingMatches("  Ice   Cream ", "ice cream"));
  assert.ok(!W.spellingMatches("icecream", "ice cream"));
  assert.ok(!W.spellingMatches("", "ice"));
  assert.equal(W.maskWord("ice cream", 1), "i__ _____");
  assert.equal(W.maskWord("T-shirt", 3), "T-s____");
}

testMergeKeepsNewestPerWord();
testStatsAndUnlocking();
testQuizOptions();
testSpellingAndMask();
console.log("wordbook node tests: ok");
