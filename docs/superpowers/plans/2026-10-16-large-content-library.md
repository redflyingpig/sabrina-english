# Large Daily-English Content Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the embedded lesson arrays with a validated static library containing at least 4,000 A1–B2 daily-life words, 600 expressions, and 250 sentence patterns, with same-mode unseen batch continuation.

**Architecture:** Build and validate versioned JSON content at development time, then serve it from an explicit static whitelist. A small browser-compatible JavaScript module loads the manifest, creates deterministic per-profile orders, migrates old history identities, and selects unseen batches; SQLite and the sync API remain unchanged.

**Tech Stack:** Python 3.9 standard library, JSON, browser JavaScript, Node.js for pure selection tests, existing `unittest` suite and stdlib HTTP service.

**Spec:** `docs/superpowers/specs/2026-10-16-content-library-design.md`

## Global Constraints

- Runtime has no third-party dependencies, external content API, API key, or AI call.
- Content is daily-life English limited to CEFR A1, A2, B1, and B2.
- Ship at least 4,000 unique vocabulary entries, 600 unique expressions, and 250 unique sentence patterns.
- Preserve current SQLite schema, profile isolation, local-first writes, offline behavior, import/export, and existing learning history.
- Runtime content files are versioned static JSON; repository files outside the explicit public whitelist remain inaccessible.
- Definitions and examples must not copy proprietary dictionary text; record all upstream data licenses and pinned revisions.
- Same-mode batch sizes remain vocabulary 5, expressions 3, patterns 1.

## Review Focus

- Case, punctuation, inflection, and alternate spelling collisions must not create duplicate identities or repeat inside a batch; Task 1 tests normalization and uniqueness.
- A stale cached manifest combined with newer shard files must fail safely and retain local study data; Task 4 tests version/hash mismatch and retry UI state.
- Old history without `contentId` must suppress matching new content without deleting unmatched legacy entries; Task 4 tests both paths.
- A profile that has learned the complete pool must receive least-recently-learned review content, never an empty or crashing lesson; Task 4 tests exhaustion.
- A malformed single content record or missing shard must not expose files, blank the page, or erase state; Tasks 1, 3, and 5 test build rejection, HTTP denial, and UI fallback.

---

### Task 1: Content schema and validator

**Files:**
- Create: `scripts/validate_content.py`
- Create: `tests/test_content_library.py`
- Create: `content/ATTRIBUTION.md`

**Interfaces:**
- Produces: `validate_library(content_dir: pathlib.Path) -> list[str]`; empty list means valid.
- Produces: manifest keys `version`, `files`, `counts`, and per-file `sha256`.
- Consumes: JSON schemas defined in the spec (`id`, `level`, `topic`, and mode-specific learning fields).

- [ ] **Step 1: Write failing validator tests**

Add tests that build temporary libraries and assert rejection of duplicate normalized IDs/content, missing fields, invalid CEFR, non-string examples, wrong hashes, and counts below 4,000/600/250. Add a valid minimal-fixture test with count thresholds overridden only through the validator's explicit test parameters.

- [ ] **Step 2: Run the validator tests and verify RED**

Run: `python3 -m unittest -v tests.test_content_library`

Expected: import failure because `scripts.validate_content` does not exist.

- [ ] **Step 3: Implement the validator and manifest contract**

Implement `normalize_identity(value: str) -> str`, `validate_library(content_dir: Path, minimums: Optional[dict] = None) -> list[str]`, and `write_manifest(content_dir: Path, version: str) -> Path`. Hash canonical file bytes, accept only A1–B2, and emit every error rather than stopping at the first.

- [ ] **Step 4: Run Task 1 tests and verify GREEN**

Run: `python3 -m unittest -v tests.test_content_library`

Expected: all Task 1 tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add scripts/validate_content.py tests/test_content_library.py content/ATTRIBUTION.md
git commit -m "test: define content library contract"
```

### Task 2: Generate and curate the full library

**Files:**
- Create: `scripts/generate_content.py`
- Create: `scripts/example_templates.py`
- Create: `content/vocabulary-a1.json`
- Create: `content/vocabulary-a2.json`
- Create: `content/vocabulary-b1.json`
- Create: `content/vocabulary-b2.json`
- Create: `content/expressions.json`
- Create: `content/patterns.json`
- Create: `content/manifest.json`
- Modify: `content/ATTRIBUTION.md`
- Modify: `content/manifest.json`
- Test: `tests/test_content_library.py`

**Interfaces:**
- Consumes: pinned ECDICT `ecdict.csv` rows (`word`, `phonetic`, `translation`, `pos`, `bnc`, `frq`, `tag`) from a CLI path; source revision and SHA-256 are recorded in attribution.
- Produces: deterministic `generate_library(source_csv: Path, output_dir: Path) -> None` and the six runtime JSON files.
- Produces: vocabulary IDs `v1:<normalized-word>`, expression IDs `e1:<slug>`, pattern IDs `p1:<slug>`; published IDs never change meaning.

- [ ] **Step 1: Extend tests for production content quality**

Assert exact lower bounds (4,000/600/250), level distribution (800/1,200/1,200/800 vocabulary minimum targets), non-empty IPA/Chinese/examples, unique normalized identities, allowed daily-life topics, no control characters/HTML, and a deterministic stratified review sample of 25 words per level.

- [ ] **Step 2: Run production content tests and verify RED**

Run: `python3 -m unittest -v tests.test_content_library`

Expected: failures for missing content files and insufficient counts.

- [ ] **Step 3: Implement the deterministic generation pipeline**

Implement `load_ecdict`, `rank_daily_words`, `assign_level`, `assign_topic`, and `build_example`. Pin the ECDICT Git revision in `ATTRIBUTION.md`, filter proper names/technical/archaic/offensive entries, use original POS- and topic-aware sentence frames, and make output ordering stable. The generator is development-only; generated JSON is committed so production never downloads a source.

Download the pinned build input outside the repository:

```bash
mkdir -p /tmp/sabrina-content-source
curl --location --fail --output /tmp/sabrina-content-source/ecdict.csv \
  https://raw.githubusercontent.com/skywind3000/ECDICT/82c9872576b23118d7c42e920c11beb77f510ae2/ecdict.csv
shasum -a 256 /tmp/sabrina-content-source/ecdict.csv
```

Record the observed SHA-256 in `content/ATTRIBUTION.md`; the generator must refuse a different digest unless its pinned metadata is deliberately updated.

- [ ] **Step 4: Author expression and pattern catalogs**

Produce at least 600 natural daily expressions and 250 practical patterns across A1–B2 and the approved themes. Each item must carry an original Chinese explanation and example text; use the validator to reject duplicates and incomplete items.

- [ ] **Step 5: Generate files, validate, and inspect the stratified sample**

Run:

```bash
python3 scripts/generate_content.py --ecdict /tmp/sabrina-content-source/ecdict.csv --output content
python3 scripts/validate_content.py content
python3 -m unittest -v tests.test_content_library
```

Expected: counts meet or exceed 4,000/600/250, validation reports zero errors, tests pass, and the 100-word stratified review sample contains no obviously awkward translation/example pairs. Correct source rules or explicit overrides for any bad sample; never edit only the generated output.

- [ ] **Step 6: Commit Task 2**

```bash
git add scripts/generate_content.py scripts/example_templates.py content tests/test_content_library.py
git commit -m "feat: add 4000-word daily English library"
```

### Task 3: Serve only approved content assets

**Files:**
- Modify: `sabrina_backend/app.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `content/manifest.json` and the six filenames declared by the manifest.
- Produces: GET access to `/content/<approved-name>.json` with correct JSON MIME type and cache validation headers.
- Preserves: all other repository paths, dotfiles, scripts, and backend files return 404.

- [ ] **Step 1: Write failing static-asset security tests**

Test successful manifest/shard GET, conditional GET with ETag, rejection of an undeclared JSON file, encoded traversal, `.git`, `scripts/`, and `sabrina_backend/`.

- [ ] **Step 2: Run targeted tests and verify RED**

Run: `python3 -m unittest -v tests.test_app.AppTest.test_serves_only_approved_content_assets`

Expected: manifest currently returns 404.

- [ ] **Step 3: Implement the explicit static whitelist**

Add `approved_static_path(request_path: str) -> Optional[Path]`. Permit `/`, `/index.html`, `/assets/content-library.js`, manifest, and only manifest-declared JSON filenames; reject hidden segments and decoded traversal before file access.

- [ ] **Step 4: Run app tests and verify GREEN**

Run: `python3 -m unittest -v tests.test_app`

Expected: all app tests pass, including `.git` denial.

- [ ] **Step 5: Commit Task 3**

```bash
git add sabrina_backend/app.py tests/test_app.py
git commit -m "feat: serve versioned lesson content"
```

### Task 4: Deterministic unseen-content selector

**Files:**
- Create: `assets/content-library.js`
- Create: `tests/content_library_node_test.js`
- Create: `tests/test_content_logic.py`

**Interfaces:**
- Produces browser/Node API `SabrinaContent.load(fetchFn, baseUrl) -> Promise<Library>`.
- Produces `stableOrder(items, seed) -> Item[]`.
- Produces `selectBatch({items, history, batchSize, seed, cursor}) -> {items, nextCursor, exhausted}`.
- Produces `legacyIdentity(entry) -> string | null` for old records without `contentId`.

- [ ] **Step 1: Write failing Node behavior tests**

Cover deterministic order, different profile seeds, no duplicate batch items, learned `contentId` suppression, legacy title suppression, same-mode cursor continuation, partial remainder, total exhaustion choosing least-recently-learned content, and manifest/shard version or hash mismatch.

- [ ] **Step 2: Run the wrapper and verify RED**

Run: `python3 -m unittest -v tests.test_content_logic`

Expected: Node cannot load `assets/content-library.js`.

- [ ] **Step 3: Implement the pure module**

Use a browser/Node-compatible module with no DOM or storage access. Hash strings with a stable 32-bit algorithm, use Fisher–Yates with the seeded PRNG, match legacy items by normalized mode/title, and use history timestamps for least-recently-learned fallback.

- [ ] **Step 4: Run Task 4 tests and verify GREEN**

Run: `python3 -m unittest -v tests.test_content_logic`

Expected: all selection and loader tests pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add assets/content-library.js tests/content_library_node_test.js tests/test_content_logic.py
git commit -m "feat: select unseen lesson content"
```

### Task 5: Integrate the content library into the study UI

**Files:**
- Modify: `index.html`
- Modify: `tests/test_frontend_contract.py`

**Interfaces:**
- Consumes: `SabrinaContent.load`, `selectBatch`, and `legacyIdentity` from Task 4.
- Produces: existing `getDisplayItems`, `renderLesson`, `markLearned`, and `renderProgress` behavior backed by content IDs rather than embedded arrays.
- Preserves: same-mode “再学一组”, compact import/export, local-first sync, profile generation guards, review, favorites, speech, and responsive layout.

- [ ] **Step 1: Write failing frontend integration tests**

Assert the embedded 200/60/20 arrays are removed, the module is loaded before app initialization, loading/error/retry states exist, content IDs enter history, legacy entries remain visible, next batch calls the selector with unchanged mode, and import/export remain compact.

- [ ] **Step 2: Run frontend tests and verify RED**

Run: `python3 -m unittest -v tests.test_frontend_contract`

Expected: failures because the page still contains `lessonBank` and does not load manifest content.

- [ ] **Step 3: Implement asynchronous content initialization**

Load content before rendering lessons, map JSON fields into the existing card model, persist `contentId` in new history entries, show retry UI on load failure without clearing local state, and keep the current loaded batch usable if the network later goes offline.

- [ ] **Step 4: Implement same-mode continuation and migration**

Replace fixed-set indexing with `selectBatch`; current batch completion reveals “再学一组”, which advances only that mode. Use legacy identity matching to exclude old learned items while leaving unmatched historical snapshots untouched.

- [ ] **Step 5: Run frontend and full tests**

Run:

```bash
python3 -m unittest -v tests.test_frontend_contract tests.test_content_logic
python3 -m unittest discover -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 5**

```bash
git add index.html tests/test_frontend_contract.py
git commit -m "feat: load large lesson library"
```

### Task 6: Deploy and verify desktop/mobile production behavior

**Files:**
- Modify: `VOCABULARY-SOURCES.md`
- Modify: `OPERATIONS.md`
- Modify: `ACCEPTANCE-REPORT-2026-10-16.md`

**Interfaces:**
- Consumes: completed content files, selector, UI, and existing `deploy/install.sh`.
- Produces: production evidence for counts, hashes, desktop/mobile next-batch flow, offline behavior, sync, and static-file security.

- [ ] **Step 1: Update source and operations documentation**

Document the pinned ECDICT source/license, original enrichment policy, regeneration/validation commands, content versioning, and rollback procedure. Do not claim Oxford/Cambridge content was copied.

- [ ] **Step 2: Run pre-deployment verification**

Run:

```bash
python3 scripts/validate_content.py content
python3 -m unittest discover -v
git diff --check
```

Expected: zero validator errors, full suite passes, diff check is clean.

- [ ] **Step 3: Install and verify HTTP behavior**

Run `./deploy/install.sh`, then verify local/public health, manifest and one shard hashes, `.git`/scripts/backend return 404, and port 18880 listens only on `127.0.0.1`.

- [ ] **Step 4: Verify real desktop and mobile flows**

Using the public domain in separate desktop and 390×844 browser contexts, verify login, current lesson, completing a batch, “再学一组” staying in the same mode, no repeated IDs, sync to a second context, compact import/export, and offline learning followed by reconnect sync. Do not leave acceptance-only study records in production without explicit approval.

- [ ] **Step 5: Verify rollback and commit documentation**

Confirm the previous commit can still be reinstalled without schema migration, update the acceptance report with evidence paths and actual counts, then commit:

```bash
git add VOCABULARY-SOURCES.md OPERATIONS.md ACCEPTANCE-REPORT-2026-10-16.md
git commit -m "docs: document large content library"
```
