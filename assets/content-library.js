(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.SabrinaContent = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function normalize(value) {
    return String(value || "")
      .normalize("NFKD")
      .toLowerCase()
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, " ")
      .trim()
      .replace(/\s+/g, " ");
  }

  function hashSeed(value) {
    let hash = 2166136261;
    for (const character of String(value)) {
      hash ^= character.codePointAt(0);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function randomGenerator(seed) {
    let state = hashSeed(seed) || 0x6d2b79f5;
    return function () {
      state += 0x6d2b79f5;
      let value = state;
      value = Math.imul(value ^ (value >>> 15), value | 1);
      value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
      return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
    };
  }

  function stableOrder(items, seed) {
    const ordered = Array.from(items || []);
    const random = randomGenerator(seed);
    for (let index = ordered.length - 1; index > 0; index -= 1) {
      const swapIndex = Math.floor(random() * (index + 1));
      [ordered[index], ordered[swapIndex]] = [ordered[swapIndex], ordered[index]];
    }
    return ordered;
  }

  function itemMode(item) {
    if (item && typeof item.word === "string") return "vocabulary";
    if (item && typeof item.expression === "string") return "expressions";
    if (item && typeof item.pattern === "string") return "patterns";
    return null;
  }

  function itemTitle(item) {
    return item && (item.word || item.expression || item.pattern || item.title);
  }

  function normalizedMode(mode) {
    const value = normalize(mode);
    if (value === "vocabulary" || value === "words" || value === "word") return "vocabulary";
    if (value === "expression" || value === "expressions") return "expressions";
    if (value === "pattern" || value === "patterns") return "patterns";
    return value || null;
  }

  function legacyIdentity(entry) {
    if (!entry || typeof entry !== "object") return null;
    const mode = normalizedMode(entry.mode || itemMode(entry));
    const title = normalize(entry.title || itemTitle(entry));
    return mode && title ? `${mode}:${title}` : null;
  }

  function historyTime(entry) {
    const raw = entry && (entry.date || entry.learnedAt || entry.updatedAt);
    const value = raw ? Date.parse(raw) : 0;
    return Number.isFinite(value) ? value : 0;
  }

  function selectBatch({ items, history = [], batchSize, seed, cursor = 0 }) {
    const ordered = stableOrder(items, seed);
    const learnedIds = new Set(history.map((entry) => entry && entry.contentId).filter(Boolean));
    const learnedLegacy = new Set(history.map(legacyIdentity).filter(Boolean));
    const isUnseen = (entry) =>
      !learnedIds.has(entry.id) && !learnedLegacy.has(legacyIdentity(entry));
    const unseen = ordered.filter(isUnseen);
    const size = Math.max(1, Number(batchSize) || 1);
    if (unseen.length) {
      const start = Math.max(0, Number(cursor) || 0);
      const batch = [];
      let position = start;
      while (position < ordered.length && batch.length < size) {
        if (isUnseen(ordered[position])) batch.push(ordered[position]);
        position += 1;
      }
      if (batch.length) return { items: batch, nextCursor: position, exhausted: false };
      let wrappedPosition = 0;
      while (wrappedPosition < start && batch.length < size) {
        if (isUnseen(ordered[wrappedPosition])) batch.push(ordered[wrappedPosition]);
        wrappedPosition += 1;
      }
      return { items: batch, nextCursor: wrappedPosition, exhausted: false };
    }

    const lastSeen = new Map();
    for (const entry of history) {
      const identity = entry.contentId || legacyIdentity(entry);
      if (!identity) continue;
      lastSeen.set(identity, Math.max(lastSeen.get(identity) || 0, historyTime(entry)));
    }
    const review = ordered
      .map((entry, index) => ({
        entry,
        index,
        time: lastSeen.get(entry.id) || lastSeen.get(legacyIdentity(entry)) || 0,
      }))
      .sort((left, right) => left.time - right.time || left.index - right.index)
      .slice(0, size)
      .map((candidate) => candidate.entry);
    return { items: review, nextCursor: 0, exhausted: true };
  }

  async function sha256(text) {
    if (!globalThis.crypto || !globalThis.crypto.subtle) {
      throw new Error("SHA-256 is unavailable in this browser");
    }
    const digest = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  }

  async function load(fetchFn, baseUrl) {
    const base = String(baseUrl || "/content/").replace(/\/?$/, "/");
    const manifestResponse = await fetchFn(`${base}manifest.json`, { cache: "no-cache" });
    if (!manifestResponse.ok) throw new Error("content manifest request failed");
    const manifestText = await manifestResponse.text();
    let manifest;
    try {
      manifest = JSON.parse(manifestText);
    } catch (_error) {
      throw new Error("content manifest is invalid JSON");
    }
    if (!manifest || typeof manifest.version !== "string" || !manifest.files) {
      throw new Error("content manifest is incomplete");
    }

    const files = {};
    for (const [name, metadata] of Object.entries(manifest.files)) {
      if (!/^[a-z0-9-]+\.json$/.test(name)) throw new Error(`unsafe content filename: ${name}`);
      const response = await fetchFn(`${base}${name}`, { cache: "no-cache" });
      if (!response.ok) throw new Error(`content request failed: ${name}`);
      const text = await response.text();
      if ((await sha256(text)) !== metadata.sha256) throw new Error(`content hash mismatch: ${name}`);
      let rows;
      try {
        rows = JSON.parse(text);
      } catch (_error) {
        throw new Error(`content JSON is invalid: ${name}`);
      }
      if (!Array.isArray(rows) || rows.length !== metadata.count) {
        throw new Error(`content count mismatch: ${name}`);
      }
      files[name] = rows;
    }
    const vocabulary = Object.keys(files)
      .filter((name) => name.startsWith("vocabulary-"))
      .sort()
      .flatMap((name) => files[name]);
    return {
      version: manifest.version,
      manifest,
      files,
      vocabulary,
      expressions: files["expressions.json"] || [],
      patterns: files["patterns.json"] || [],
    };
  }

  return { load, stableOrder, selectBatch, legacyIdentity, normalize };
});
