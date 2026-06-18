# Codex Handoff: Sabrina English — Core App Enhancements

## Project Context

**Sabrina English** is a static HTML learning site for Sabrina to learn English vocabulary daily.

- **Live URL:** https://redflyingpig.github.io/sabrina-english/
- **GitHub repo:** `redflyingpig/sabrina-english`
- **Source file:** Single `index.html` (or `sabrina-english.html`) — everything in one file
- **Hosting:** GitHub Pages
- **Target user:** Sabrina, English level ~A1-A2

## Current Architecture

Single HTML file with embedded CSS + JS. No backend, no build step.

### `lessonBank` Object (hardcoded)
Three modes rotate daily based on date hash:

- **Mode A** — 7 sets × 5 vocabulary words: `{ word, phonetic, translation, example }`
- **Mode B** — 7 sets × 3 expressions: `{ expression, usage, example }`
- **Mode C** — 7 sentence patterns: `{ pattern, explanation, examples[] }`

### Daily Rotation Logic
```js
const mode = pickDailyMode(todayKey);  // hash date string → A/B/C
const lessonSet = getLessonSet(mode, dayOfYear);  // (dayOfYear-1) % sets.length
```

### Current Features
- 🔊 Pronunciation (Web Speech API)
- ✓ "Mark as Learned" → localStorage
- 📋 Learned History panel with Clear All
- 🌙 Dark theme, mobile-responsive

### Known Limitation
- localStorage only — progress doesn't sync across devices, clears on browser reset

## Requested Enhancements

From prior discussions, these are the features to build on top of the existing app:

### 1. Streak Counter 🔥
- Track consecutive days the user opens the site and marks at least one item learned
- Display prominently (like Duolingo's streak)
- Reset to 0 if a day is missed
- Store in localStorage (or better: see persistence below)

### 2. Daily Progress Bar
- Show completion status: "3/5 items learned today" with visual progress
- Display "今日完成 🎉" when all items for the day are marked

### 3. Review Mode (Spaced Repetition)
- Pull random items from Learned History
- Hide the Chinese translation/explanation — user tries to recall
- Tap/click to reveal the answer
- Pure frontend, no backend needed
- Suggest 5 items per review session

### 4. Favorites / Star System ⭐
- Let user star difficult items
- Separate "待复习" (to review) section for starred items
- Starred items appear more frequently in review mode

### 5. Cross-Device Persistence (if feasible without backend)
- Current: localStorage only (lost on clear, no sync)
- Options to explore:
  - URL-based state export/import (share a link with encoded progress)
  - Simple JSON export/import button
  - Or: lightweight free backend (Firebase free tier, Supabase, GitHub Gist API)
- At minimum: add Export/Import buttons so progress isn't completely lost

## Key Code References

**Mode selection:**
```js
function pickDailyMode(seed) {
  const modes = ["A", "B", "C"];
  return modes[Math.abs(hashString(seed)) % modes.length];
}
```

**Lesson cycling:**
```js
function getLessonSet(currentMode, dayNumber) {
  const sets = lessonBank[currentMode];
  return sets[(dayNumber - 1) % sets.length];
}
```

**Day of year:**
```js
function getDayOfYear(date) {
  const start = new Date(date.getFullYear(), 0, 0);
  const diff = date - start + (start.getTimezoneOffset() - date.getTimezoneOffset()) * 60000;
  return Math.floor(diff / 86400000);
}
```

## Constraints
- Keep it as a single HTML file (no build tools, no npm)
- Mobile-first — Sabrina primarily uses her phone
- Dark theme maintained
- A1-A2 English level content
- Chinese UI labels are fine (Sabrina reads Chinese natively)

## Priority Order
1. Streak counter (highest impact on retention)
2. Daily progress bar (quick win, visual satisfaction)
3. Review mode with reveal (most effective for learning)
4. Favorites/star
5. Export/import (nice to have)

## Files
- Source: the single HTML file in the `redflyingpig/sabrina-english` GitHub repo
