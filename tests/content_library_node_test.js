"use strict";

const assert = require("assert");
const crypto = require("crypto");
const SabrinaContent = require("../assets/content-library.js");

function item(id, word) {
  return { id, level: "A1", topic: "daily-life", word, translation: word };
}

function response(body, ok = true) {
  return { ok, text: async () => body };
}

async function testLoadAndIntegrity() {
  const shardText = JSON.stringify([item("v1:hello", "hello")]);
  const sha256 = crypto.createHash("sha256").update(shardText).digest("hex");
  const manifest = JSON.stringify({
    version: "test-v1",
    files: { "vocabulary-a1.json": { count: 1, sha256 } },
    counts: { vocabulary: 1, expressions: 0, patterns: 0 },
  });
  const fetchFn = async (url) => {
    if (url.endsWith("manifest.json")) return response(manifest);
    if (url.endsWith("vocabulary-a1.json")) return response(shardText);
    return response("", false);
  };
  const library = await SabrinaContent.load(fetchFn, "/content/");
  assert.equal(library.version, "test-v1");
  assert.equal(library.files["vocabulary-a1.json"][0].word, "hello");

  const badFetch = async (url) => response(url.endsWith("manifest.json") ? manifest : "[]");
  await assert.rejects(() => SabrinaContent.load(badFetch, "/content/"), /hash mismatch/);
}

function testStableOrderAndSelection() {
  const items = ["a", "b", "c", "d", "e", "f", "g"].map((word) => item(`v1:${word}`, word));
  assert.deepEqual(SabrinaContent.stableOrder(items, "owner"), SabrinaContent.stableOrder(items, "owner"));
  assert.notDeepEqual(SabrinaContent.stableOrder(items, "owner"), SabrinaContent.stableOrder(items, "sabrina"));

  const learned = [{ contentId: "v1:a", mode: "vocabulary", title: "a", date: "2026-10-15T10:00:00Z" }];
  const first = SabrinaContent.selectBatch({ items, history: learned, batchSize: 2, seed: "owner", cursor: 0 });
  assert.equal(first.items.length, 2);
  assert.equal(new Set(first.items.map((entry) => entry.id)).size, 2);
  assert(!first.items.some((entry) => entry.id === "v1:a"));
  const updatedHistory = learned.concat(first.items.map((entry) => ({
    contentId: entry.id,
    mode: "vocabulary",
    title: entry.word,
    date: "2026-10-16T10:00:00Z",
  })));
  const second = SabrinaContent.selectBatch({ items, history: updatedHistory, batchSize: 2, seed: "owner", cursor: first.nextCursor });
  assert.equal(second.items.length, 2);
  assert(!second.items.some((entry) => first.items.includes(entry)));
  // Unseen lessons come from a frequency-priority window, not a strict queue: every pick must stay
  // inside the leading window, and the two batches together must not repeat an item.
  const priority = SabrinaContent.priorityOrder(items);
  const seen = first.items.concat(second.items).map((entry) => entry.id);
  assert.equal(new Set(seen).size, seen.length);
  for (const id of seen) {
    const position = priority.findIndex((candidate) => candidate.id === id);
    assert.ok(position >= 0 && position < 6, `${id} left the priority window`);
  }
  const remainingIds = new Set(items.map((entry) => entry.id));
  for (const entry of updatedHistory) remainingIds.delete(entry.contentId);
  for (const entry of second.items) remainingIds.delete(entry.id);
  assert.equal(remainingIds.size, 2);
  assert.equal(second.exhausted, false);
}

function testLegacyAndExhaustion() {
  const items = [item("v1:hello", "Hello!"), item("v1:world", "world")];
  assert.equal(
    SabrinaContent.legacyIdentity({ mode: "vocabulary", title: " Hello! " }),
    "vocabulary:hello"
  );
  const legacy = [{ mode: "vocabulary", title: "hello", date: "2026-10-15T00:00:00Z" }];
  const unseen = SabrinaContent.selectBatch({ items, history: legacy, batchSize: 2, seed: "x", cursor: 0 });
  assert.deepEqual(unseen.items.map((entry) => entry.id), ["v1:world"]);

  const history = [
    { contentId: "v1:hello", mode: "vocabulary", title: "hello", date: "2026-01-01T00:00:00Z" },
    { contentId: "v1:world", mode: "vocabulary", title: "world", date: "2026-10-01T00:00:00Z" },
  ];
  const review = SabrinaContent.selectBatch({ items, history, batchSize: 1, seed: "x", cursor: 0 });
  assert.equal(review.exhausted, true);
  assert.equal(review.items[0].id, "v1:hello");
  const reviewedHistory = history.map((entry) => entry.contentId === "v1:hello"
    ? { ...entry, reviewedAt: "2026-11-01T00:00:00Z" }
    : entry);
  const nextReview = SabrinaContent.selectBatch({ items, history: reviewedHistory, batchSize: 1, seed: "x", cursor: 0 });
  assert.equal(nextReview.items[0].id, "v1:world");
  assert.equal(SabrinaContent.legacyIdentity({ mode: "Vocabulary", title: "colour" }), "vocabulary:color");

  const seven = ["a", "b", "c", "d", "e", "f", "g"].map((word) => item(`v1:${word}`, word));
  const wrapped = SabrinaContent.selectBatch({ items: seven, history: [], batchSize: 5, seed: "tail", cursor: 6 });
  assert.equal(wrapped.items.length, 5);
  assert.equal(new Set(wrapped.items.map((entry) => entry.id)).size, 5);
}

function testFrequencyPriority() {
  // Shard order is the generator's frequency order: content words first, function words last.
  const sample = ["the", "apple", "and", "banana", "of", "cherry"].map((word) => item(`v1:${word}`, word));
  assert.deepEqual(
    SabrinaContent.priorityOrder(sample).map((entry) => entry.word),
    ["apple", "banana", "cherry", "the", "and", "of"]
  );

  // A realistic shard: function words are interleaved early in the raw data, as they are in ECDICT
  // frequency order, and must still sink below the level's content words.
  const words = [
    "the", "make", "and", "know", "of", "see", "a", "take", "in", "think",
    "to", "come", "is", "give", "it", "look", "he", "want", "we", "use",
  ];
  const items = words.map((word) => item(`v1:${word}`, word));
  const contentWords = ["make", "know", "see", "take", "think", "come", "give", "look", "want", "use"];
  // A batch is drawn from the window at the cursor. Content words always outrank function words,
  // so a function word can only enter a batch once every content word ahead of it is taken.
  const priority = SabrinaContent.priorityOrder(items);
  const rankOf = (entry) => priority.findIndex((candidate) => candidate.id === entry.id);
  const fresh = SabrinaContent.selectBatch({ items, history: [], batchSize: 8, seed: "owner", cursor: 0 });
  assert.equal(fresh.items.length, 8);
  assert.equal(new Set(fresh.items.map((entry) => entry.id)).size, 8);
  const freshRanks = fresh.items.map(rankOf);
  assert.ok(freshRanks.every((rank) => rank >= 0 && rank < 18), `outside window: ${freshRanks}`);
  const firstFunctionRank = priority.findIndex((entry) => !contentWords.includes(entry.word));
  assert.ok(
    freshRanks.every((rank) => rank < firstFunctionRank),
    `took a function word while content words remained: ${freshRanks}`
  );

  // Draining the window pulls in the remaining content words first, then the head of the function
  // tier -- function words are ultimately reachable, never lost.
  const drained = SabrinaContent.selectBatch({ items, history: [], batchSize: 9, seed: "owner", cursor: 0 });
  assert.equal(drained.items.length, 9);
  assert.ok(drained.items.some((entry) => contentWords.includes(entry.word)));
  assert.ok(
    drained.items.every((entry) => rankOf(entry) < 19),
    `drained batch left its window: ${drained.items.map(rankOf)}`
  );

  // Selection is deterministic for a given profile and cursor.
  const again = SabrinaContent.selectBatch({ items, history: [], batchSize: 8, seed: "owner", cursor: 0 });
  assert.deepEqual(again.items.map((entry) => entry.id), fresh.items.map((entry) => entry.id));

  // Priority is a band, not a strict queue: a later batch starts deeper and stays below the head,
  // yet a batch's picks stay inside the window after its own cursor.
  const wide = Array.from({ length: 60 }, (_, index) => item(`v1:w${index}`, `w${index}`));
  const early = SabrinaContent.selectBatch({ items: wide, history: [], batchSize: 4, seed: "band", cursor: 0 });
  const later = SabrinaContent.selectBatch({ items: wide, history: [], batchSize: 4, seed: "band", cursor: 30 });
  const wideRank = (entry) => SabrinaContent.priorityOrder(wide).findIndex((c) => c.id === entry.id);
  const earlyRanks = early.items.map(wideRank);
  const laterRanks = later.items.map(wideRank);
  assert.ok(earlyRanks.every((rank) => rank >= 0 && rank < 14), `early batch left the leading window: ${earlyRanks}`);
  assert.ok(laterRanks.every((rank) => rank >= 30 && rank < 44), `later batch left its window: ${laterRanks}`);
  assert.ok(Math.max(...earlyRanks) < Math.min(...laterRanks), "later batch should rank below the early batch");

  // A custom array without any function word keeps its original order.
  const plain = ["zebra", "apple", "mango"].map((word) => item(`v1:${word}`, word));
  assert.deepEqual(
    SabrinaContent.priorityOrder(plain).map((entry) => entry.word),
    ["zebra", "apple", "mango"]
  );
}

function bookWord(word, extra = {}) {
  return { w: word, senses: [["n.", extra.gloss || word]], topic: extra.topic || "food", ...extra };
}

function testWordbookLessonPool() {
  const vocabulary = ["the", "menu", "apple", "banana", "fish"].map((word) => item(`v1:${word}`, word));
  const days = [
    { day: 1, words: [bookWord("menu"), bookWord("ham"), bookWord("main dish"), bookWord("menu")] },
    { day: 2, words: [bookWord("basketball"), bookWord("menu")] },
  ];

  // Without a wordbook the pool is the plain ECDICT shard, unchanged.
  const base = SabrinaContent.buildLessonPool({ vocabulary });
  assert.deepEqual(base.map((entry) => entry.id), vocabulary.map((entry) => entry.id));

  const pool = SabrinaContent.buildLessonPool({ vocabulary, wordbookDays: days });
  const book = pool.filter((entry) => entry.wordbookDay !== undefined);
  // 1969-entry scanned books repeat words across days; each word is taught once, at first sight.
  assert.deepEqual(book.map((entry) => entry.word), ["menu", "ham", "main dish", "basketball"]);
  assert.deepEqual(book.map((entry) => entry.id), ["wb:1:menu", "wb:1:ham", "wb:1:main dish", "wb:2:basketball"]);

  // Book words lead; a word present in both pools is served from the book only, with its gloss.
  assert.equal(pool[0].word, "menu");
  assert.equal(pool[0].translation, "menu");
  assert.equal(pool.filter((entry) => entry.word === "menu").length, 1);
  assert.ok(pool.slice(book.length).every((entry) => ["the", "apple", "banana", "fish"].includes(entry.word)));

  // Multi-word phrases keep their identity and have no invented phonetic.
  const phrase = pool.find((entry) => entry.word === "main dish");
  assert.equal(phrase.phonetic, "");
  assert.equal(phrase.wordbookDay, 1);

  // A KNOWN word leaves the pool; FUZZY stays eligible because it still needs practice.
  const knownPool = SabrinaContent.buildLessonPool({
    vocabulary,
    wordbookDays: days,
    wordbookEntries: { "1:ham": { level: 3, at: "2026-10-17T00:00:00Z" } },
  });
  assert.ok(!knownPool.some((entry) => entry.word === "ham"));
  const fuzzyPool = SabrinaContent.buildLessonPool({
    vocabulary,
    wordbookDays: days,
    wordbookEntries: { "1:ham": { level: 2, at: "2026-10-17T00:00:00Z" } },
  });
  assert.ok(fuzzyPool.some((entry) => entry.word === "ham"));

  // Book entries are served in book order, never shuffled by the frequency window.
  const batch = SabrinaContent.selectBatch({ items: pool, history: [], batchSize: 3, seed: "s", cursor: 0 });
  assert.deepEqual(batch.items.map((entry) => entry.word), ["menu", "ham", "main dish"]);
}

(async () => {
  await testLoadAndIntegrity();
  testStableOrderAndSelection();
  testLegacyAndExhaustion();
  testFrequencyPriority();
  testWordbookLessonPool();
  console.log("content library node tests: ok");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
