(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.SabrinaContent = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function normalize(value) {
    const normalized = String(value || "")
      .normalize("NFKD")
      .toLowerCase()
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, " ")
      .trim()
      .replace(/\s+/g, " ");
    const aliases = {
      centre: "center", colour: "color", favour: "favor", favourite: "favorite",
      honour: "honor", labour: "labor", neighbour: "neighbor", organise: "organize",
      organised: "organized", organising: "organizing", realise: "realize",
      recognise: "recognize", theatre: "theater", travelling: "traveling",
    };
    return aliases[normalized] || normalized;
  }

  // Function words (articles, pronouns, auxiliaries, prepositions, conjunctions,
  // determiners) carry little study value on their own: "the/be/and/of/a" are the
  // highest-frequency words in the corpus but a learner already knows them. They are
  // deprioritised rather than removed, so they still appear once the content words of
  // the level are covered. Every shard is emitted by scripts/generate_content.py in
  // ascending min(bnc, frq) rank order, so array order is the frequency priority.
  const FUNCTION_WORDS = new Set((
    // articles, determiners, quantifiers
    "a an the this that these those each every either neither both all any some no none " +
    "another other others such same enough several many much more most less least few fewer " +
    // personal, possessive, reflexive, demonstrative, relative, interrogative pronouns
    "i me my mine myself we us our ours ourselves you your yours yourself yourselves " +
    "he him his himself she her hers herself it its itself they them their theirs themselves " +
    "who whom whose which what whatever whichever whoever whoever whenever wherever however " +
    "one oneself " +
    // primary auxiliaries, modals, copula and their contractions/negations
    "be am is are was were been being do does did done doing have has had having " +
    "will would shall should can could may might must ought need dare " +
    "cannot ain't aren't can't couldn't didn't doesn't don't hadn't hasn't haven't isn't " +
    "mustn't shan't shouldn't wasn't weren't won't wouldn't " +
    // prepositions
    "aboard about above across after against along amid amid amidst among amongst around as " +
    "at atop before behind below beneath beside besides between beyond but by concerning " +
    "despite down during except for from in inside into like near of off on onto opposite out " +
    "outside over past per regarding round since than through throughout till to toward towards " +
    "under underneath unlike until unto up upon versus via with within without " +
    // coordinating and subordinating conjunctions, complementisers
    "and or nor so yet because though although while whilst whereas unless if whether once " +
    "when whenever where wherever why how that " +
    // adverbs that only restate grammatical relations
    "not also too very just only even still already there here then than now thus hence therefore"
  ).split(/\s+/).filter(Boolean));

  function priorityOrder(items) {
    return Array.from(items || [])
      .map((entry, index) => ({ entry, index }))
      .sort((left, right) => {
        const leftFunction = FUNCTION_WORDS.has(normalize(itemTitle(left.entry))) ? 1 : 0;
        const rightFunction = FUNCTION_WORDS.has(normalize(itemTitle(right.entry))) ? 1 : 0;
        return leftFunction - rightFunction || left.index - right.index;
      })
      .map((candidate) => candidate.entry);
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
    if (value === "expression" || value === "expressions" || value === "common expressions") return "expressions";
    if (value === "pattern" || value === "patterns" || value === "sentence pattern") return "patterns";
    return value || null;
  }

  function legacyIdentity(entry) {
    if (!entry || typeof entry !== "object") return null;
    const mode = normalizedMode(entry.mode || itemMode(entry));
    const title = normalize(entry.title || itemTitle(entry));
    return mode && title ? `${mode}:${title}` : null;
  }

  function historyTime(entry) {
    const raw = entry && (entry.reviewedAt || entry.date || entry.learnedAt || entry.updatedAt);
    const value = raw ? Date.parse(raw) : 0;
    return Number.isFinite(value) ? value : 0;
  }

  function selectBatch({ items, history = [], batchSize, seed, cursor = 0 }) {
    // Unseen lessons follow frequency priority (shard order, function words last) so a
    // learner meets high-frequency content words first. Review rotation keeps the seeded
    // shuffle to spread revisited items.
    const ordered = priorityOrder(items);
    const shuffled = stableOrder(items, seed);
    const learnedIds = new Set(history.map((entry) => entry && entry.contentId).filter(Boolean));
    const learnedLegacy = new Set(history.map(legacyIdentity).filter(Boolean));
    const isUnseen = (entry) =>
      !learnedIds.has(entry.id) && !learnedLegacy.has(legacyIdentity(entry));
    const unseen = ordered.filter(isUnseen);
    const size = Math.max(1, Number(batchSize) || 1);
    if (unseen.length) {
      const start = ordered.length ? Math.max(0, Number(cursor) || 0) % ordered.length : 0;
      const batch = [];
      let visited = 0;
      while (visited < ordered.length && batch.length < size) {
        const position = (start + visited) % ordered.length;
        if (isUnseen(ordered[position])) batch.push(ordered[position]);
        visited += 1;
      }
      return { items: batch, nextCursor: (start + visited) % ordered.length, exhausted: false };
    }

    const lastSeen = new Map();
    for (const entry of history) {
      const identity = entry.contentId || legacyIdentity(entry);
      if (!identity) continue;
      lastSeen.set(identity, Math.max(lastSeen.get(identity) || 0, historyTime(entry)));
    }
    const review = shuffled
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

  return { load, stableOrder, priorityOrder, selectBatch, legacyIdentity, normalize };
});
