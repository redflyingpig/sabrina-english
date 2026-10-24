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

  // Frequency priority is a band, not a strict queue: a batch is drawn from a sliding window of the
  // next PRIORITY_WINDOW unlearned positions, so high-frequency words surface first while a few
  // nearby lower-frequency words can appear early. Ties inside the window are broken by the seeded
  // generator, keeping selection stable for a given profile and content version.
  const PRIORITY_WINDOW = 10;

  // Wordbook entries become lessons of their own: "wb:<day>:<word>" ids keep them disjoint from the
  // "v1:*" ECDICT ids, and the book supplies its own Chinese gloss. Phonetics are reused from a
  // matching ECDICT row when one exists; multi-word phrases such as "main dish" have none and must
  // stay blank rather than be invented.
  function wordbookLessonItems(days, options = {}) {
    const vocabulary = Array.isArray(options.vocabulary) ? options.vocabulary : [];
    const phoneticByWord = new Map();
    for (const entry of vocabulary) {
      const word = itemTitle(entry);
      if (word && entry.phonetic) phoneticByWord.set(normalize(word), entry.phonetic);
    }
    const levelLabels = new Map();
    const items = [];
    for (const day of Array.isArray(days) ? days : []) {
      if (!day || !Array.isArray(day.words)) continue;
      const label = `Day ${day.day}`;
      levelLabels.set(day.day, label);
      for (const word of day.words) {
        const title = word && typeof word.w === "string" ? word.w.trim() : "";
        if (!title) continue;
        const senses = Array.isArray(word.senses) ? word.senses : [];
        const translation = senses
          .map((sense) => (Array.isArray(sense) ? sense[1] : ""))
          .filter(Boolean)
          .join("；")
          .slice(0, 120);
        const phonetic = phoneticByWord.get(normalize(title)) || "";
        items.push({
          id: `wb:${day.day}:${title}`,
          level: label,
          topic: word.topic || "daily-life",
          word: title,
          phonetic,
          translation: translation || "",
          example: `I learned the word “${title}” in today's wordbook practice.`,
          wordbookDay: day.day,
          wordbookWord: title,
        });
      }
    }
    return items;
  }

  // A word only leaves the daily lesson pool once the wordbook marks it KNOWN (mastered). Entries at
  // UNKNOWN or FUZZY are still eligible: marking a word fuzzy means "seen, needs practice", which is
  // exactly when daily repetition helps rather than hurts.
  const WORDBOOK_KNOWN_LEVEL = 3;

  function wordbookKnownKeys(entries) {
    const known = new Set();
    for (const [key, entry] of Object.entries(entries || {})) {
      const level = Number(entry && entry.level);
      if (Number.isFinite(level) && level >= WORDBOOK_KNOWN_LEVEL) known.add(key);
    }
    return known;
  }

  function buildLessonPool({ vocabulary = [], wordbookDays = [], wordbookEntries = {} } = {}) {
    const base = Array.from(vocabulary || []);
    const book = wordbookLessonItems(wordbookDays, { vocabulary: base });
    if (!book.length) return base;
    const known = wordbookKnownKeys(wordbookEntries);
    const bookSeen = new Set();
    const bookWords = new Set();
    // The scanned book lists some words on several days (1969 entries, 1507 distinct words), so a
    // word is taught once, at its first appearance, rather than resurfacing as a new lesson.
    const eligible = book.filter((entry) => {
      const key = `${entry.wordbookDay}:${entry.wordbookWord}`;
      const word = normalize(entry.word);
      if (bookSeen.has(key) || bookWords.has(word) || known.has(key)) return false;
      bookSeen.add(key);
      bookWords.add(word);
      return true;
    });
    // Book words take the lead; ECDICT backfills once the book is worked through. A word that
    // exists in both pools is served from the book only, using the book's own gloss.
    const backfill = base.filter(
      (entry) => !bookWords.has(normalize(itemTitle(entry)))
    );
    return eligible.concat(backfill);
  }

  function isBookEntry(entry) {
    return Boolean(entry && entry.wordbookDay !== undefined && entry.wordbookWord !== undefined);
  }

  function priorityOrder(items) {
    // Wordbook lessons keep the book's Day-by-Day teaching order and are never re-sorted or
    // shuffled. Only the ECDICT backfill is ordered by frequency band with function words last.
    const list = Array.from(items || []);
    const book = list.filter(isBookEntry);
    const backfill = list
      .map((entry, index) => ({ entry, index }))
      .filter((candidate) => !isBookEntry(candidate.entry))
      .sort((left, right) => {
        const leftFunction = FUNCTION_WORDS.has(normalize(itemTitle(left.entry))) ? 1 : 0;
        const rightFunction = FUNCTION_WORDS.has(normalize(itemTitle(right.entry))) ? 1 : 0;
        return leftFunction - rightFunction || left.index - right.index;
      })
      .map((candidate) => candidate.entry);
    return book.concat(backfill);
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
    // Two segments: wordbook lessons keep the book's teaching order and are served straight through;
    // the ECDICT backfill keeps the frequency-priority window with nearby-word mixing. Review
    // rotation keeps the seeded shuffle to spread revisited items.
    const ordered = priorityOrder(items);
    const shuffled = stableOrder(items, seed);
    const learnedIds = new Set(history.map((entry) => entry && entry.contentId).filter(Boolean));
    const learnedLegacy = new Set(history.map(legacyIdentity).filter(Boolean));
    const isUnseen = (entry) =>
      !learnedIds.has(entry.id) && !learnedLegacy.has(legacyIdentity(entry));
    const unseen = ordered.filter(isUnseen);
    const size = Math.max(1, Number(batchSize) || 1);
    if (unseen.length) {
      const bookCount = ordered.filter(isBookEntry).length;
      const backfill = ordered.slice(bookCount);
      const total = ordered.length;
      const start = total ? Math.max(0, Number(cursor) || 0) % total : 0;
      let batch = [];
      let nextCursor = start;
      if (start < bookCount) {
        // Wordbook segment: take the next unlearned book entries in book order.
        let index = start;
        while (index < bookCount && batch.length < size) {
          if (isUnseen(ordered[index])) batch.push(ordered[index]);
          index += 1;
        }
        nextCursor = index < total ? index : start;
      }
      if (batch.length < size && backfill.length) {
        const backfillStart = start >= bookCount ? start - bookCount : 0;
        const span = Math.min(backfill.length, size + Math.max(0, Number(PRIORITY_WINDOW) || 0));
        const positions = [];
        for (let offset = 0; offset < span; offset += 1) {
          positions.push((backfillStart + offset) % backfill.length);
        }
        const random = randomGenerator(`${seed}|jitter|${backfillStart}`);
        const shuffle = (list) => {
          for (let index = list.length - 1; index > 0; index -= 1) {
            const swapIndex = Math.floor(random() * (index + 1));
            [list[index], list[swapIndex]] = [list[swapIndex], list[index]];
          }
          return list;
        };
        // Take window content words before window function words so a grammar word never jumps
        // ahead of a still-unlearned content word in the same window.
        const contentPositions = [];
        const functionPositions = [];
        for (const position of positions) {
          const entry = backfill[position];
          if (FUNCTION_WORDS.has(normalize(itemTitle(entry)))) functionPositions.push(position);
          else contentPositions.push(position);
        }
        shuffle(functionPositions);
        let visited = 0;
        for (const group of [shuffle(contentPositions), functionPositions]) {
          for (const position of group) {
            visited += 1;
            if (isUnseen(backfill[position])) batch.push(backfill[position]);
            if (batch.length === size) break;
          }
          if (batch.length === size) break;
        }
        nextCursor = bookCount + ((backfillStart + visited) % backfill.length);
      }
      return { items: batch, nextCursor: nextCursor % total, exhausted: false };
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

  return {
    load,
    stableOrder,
    priorityOrder,
    selectBatch,
    legacyIdentity,
    normalize,
    wordbookLessonItems,
    wordbookKnownKeys,
    buildLessonPool,
  };
});
