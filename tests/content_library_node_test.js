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
  const expectedOrder = SabrinaContent.stableOrder(items, "owner").filter((entry) => entry.id !== "v1:a");
  assert.deepEqual(first.items.concat(second.items), expectedOrder.slice(0, 4));
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
}

(async () => {
  await testLoadAndIntegrity();
  testStableOrderAndSelection();
  testLegacyAndExhaustion();
  console.log("content library node tests: ok");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
