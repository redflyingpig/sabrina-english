// 10天单词书：Sabrina English 里的闯关式背单词模块。
// 纯函数部分（merge / stats / quiz）可在 node 里测试；界面部分只在浏览器里运行。
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.SabrinaWordbook = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  // 掌握程度：0 未学，1 不认识，2 模糊，3 认识
  const LEVELS = { NEW: 0, UNKNOWN: 1, FUZZY: 2, KNOWN: 3 };
  const TABS = [
    ["study", "看图学"],
    ["flash", "闪卡"],
    ["quiz", "选择题"],
    ["spell", "拼写"],
    ["book", "原书练习"],
  ];

  function entryKey(day, word) {
    return `${day}:${word}`;
  }

  function emptyState() {
    return { entries: {} };
  }

  function normalizeState(state) {
    if (!state || typeof state !== "object" || !state.entries || typeof state.entries !== "object") {
      return emptyState();
    }
    return { entries: { ...state.entries } };
  }

  // 两端各自学习后合并：同一个词保留更新时间较晚的那一条。
  function merge(a, b) {
    const left = normalizeState(a).entries;
    const right = normalizeState(b).entries;
    const entries = { ...left };
    Object.keys(right).forEach((key) => {
      const mine = entries[key];
      const theirs = right[key];
      if (!mine || (theirs.at || "") > (mine.at || "")) entries[key] = theirs;
    });
    return { entries };
  }

  function dayStats(day, state) {
    const entries = normalizeState(state).entries;
    const stats = { total: day.words.length, known: 0, fuzzy: 0, unknown: 0 };
    day.words.forEach((word) => {
      const level = entries[entryKey(day.day, word.w)]?.level || 0;
      if (level === LEVELS.KNOWN) stats.known += 1;
      else if (level === LEVELS.FUZZY) stats.fuzzy += 1;
      else if (level === LEVELS.UNKNOWN) stats.unknown += 1;
    });
    return stats;
  }

  // 闯关：前一天掌握一半以上，下一天才点亮；Day 1 永远可学。也可以手动跳关。
  function dayUnlocked(days, index, state) {
    if (index === 0) return true;
    const previous = dayStats(days[index - 1], state);
    return previous.total > 0 && previous.known / previous.total >= 0.5;
  }

  function sensesText(word) {
    return word.senses.map(([pos, text]) => `${pos} ${text}`).join("　");
  }

  function shuffle(items, random = Math.random) {
    const copy = [...items];
    for (let index = copy.length - 1; index > 0; index -= 1) {
      const swapIndex = Math.floor(random() * (index + 1));
      [copy[index], copy[swapIndex]] = [copy[swapIndex], copy[index]];
    }
    return copy;
  }

  // 选择题：英选中、中选英交替；干扰项的释义不能和正确答案相同。
  function buildQuiz(words, count, random = Math.random) {
    return shuffle(words, random)
      .slice(0, Math.min(count, words.length))
      .map((word, index) => {
        const distractors = shuffle(
          words.filter((other) => other !== word && sensesText(other) !== sensesText(word)),
          random
        ).slice(0, 3);
        return { word, enToZh: index % 2 === 0, options: shuffle([word, ...distractors], random) };
      });
  }

  function spellingMatches(input, word) {
    return String(input || "").trim().toLowerCase().replace(/\s+/g, " ") === word.toLowerCase();
  }

  function maskWord(word, reveal) {
    return word
      .split("")
      .map((char, index) => (/[a-z]/i.test(char) ? (index < reveal ? char : "_") : char))
      .join("");
  }

  // ---------------- 界面 ----------------
  // host 由 index.html 提供：
  //   apiRequest(path, opts) / getState() / setLevel(day, word, level)
  //   addToReview(day, word) / speak(text) / toast(msg) / isSignedIn() / requestLogin()
  function mount(container, host) {
    let days = null;
    let loading = null;
    let keyHandler = null;
    const imageUrls = new Map();

    const esc = (value) =>
      String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
    const sensesHTML = (word) =>
      word.senses.map(([pos, text]) => `<span class="wb-pos">${esc(pos)}</span>${esc(text)}`).join("　");
    const levelOf = (day, word) => normalizeState(host.getState()).entries[entryKey(day, word.w)]?.level || 0;
    const speakButton = (word) =>
      `<button class="icon-btn wb-speak" type="button" data-speak="${esc(word)}" aria-label="朗读 ${esc(word)}">🔊</button>`;
    const pageName = (index) => `p${String(index).padStart(3, "0")}.jpg`;

    container.addEventListener("click", (event) => {
      const speak = event.target.closest("[data-speak]");
      if (speak) host.speak(speak.dataset.speak);
      const zoom = event.target.closest("[data-zoom]");
      if (zoom) openZoom(zoom.querySelector("img"));
    });
    document.addEventListener("keydown", (event) => {
      if (container.hidden || !keyHandler) return;
      if (event.target instanceof Element && event.target.closest("input, textarea, select")) return;
      keyHandler(event);
    });

    async function ensureData() {
      if (days) return days;
      if (!loading) {
        loading = host
          .apiRequest("/api/wordbook/data")
          .then((data) => {
            days = data;
            return data;
          })
          .finally(() => {
            loading = null;
          });
      }
      return loading;
    }

    // 扫描页需要登录才能取，所以用 fetch + Bearer 取回再转成 blob 地址。
    async function loadImages(scope) {
      const images = [...scope.querySelectorAll("img[data-page]")];
      for (const img of images) {
        const name = img.dataset.page;
        if (!imageUrls.has(name)) {
          imageUrls.set(
            name,
            host.fetchBlob(`/api/wordbook/pages/${name}`).then((blob) => URL.createObjectURL(blob))
          );
        }
        imageUrls
          .get(name)
          .then((url) => {
            img.src = url;
            img.closest(".wb-page-img")?.classList.add("loaded");
          })
          .catch(() => {
            imageUrls.delete(name);
            img.alt = "图片载入失败";
          });
      }
    }

    function openZoom(img) {
      if (!img || !img.src) return;
      const dialog = document.createElement("dialog");
      dialog.className = "wb-zoom";
      dialog.innerHTML = `<button class="icon-btn wb-zoom-close" type="button" aria-label="关闭">×</button><img alt="">`;
      dialog.querySelector("img").src = img.src;
      dialog.querySelector("img").alt = img.alt;
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog || event.target.closest(".wb-zoom-close")) dialog.close();
      });
      dialog.addEventListener("close", () => dialog.remove());
      document.body.appendChild(dialog);
      dialog.showModal();
    }

    async function render(route) {
      keyHandler = null;
      if (!host.isSignedIn()) {
        container.innerHTML = `
          <section class="panel wb-signin">
            <p class="eyebrow">10-Day Wordbook</p>
            <h2>登录后打开单词书</h2>
            <p class="empty">单词书是原书扫描内容，只给家里的学习档案使用。登录后进度会和今日一课一起同步。</p>
            <button class="primary-btn" type="button" id="wbLogin">登录学习档案</button>
          </section>`;
        container.querySelector("#wbLogin").addEventListener("click", host.requestLogin);
        return;
      }
      if (!days) {
        container.innerHTML = `<section class="panel"><p class="empty">正在打开单词书…</p></section>`;
        try {
          await ensureData();
        } catch (error) {
          container.innerHTML = `
            <section class="panel">
              <p class="empty">${error.status === 404 ? "单词书内容还没有安装到 Mac mini。" : "单词书暂时打不开，学习记录没有受影响。"}</p>
              <div class="wb-row wb-pad"><button class="small-btn" type="button" id="wbRetry">重试</button></div>
            </section>`;
          container.querySelector("#wbRetry").addEventListener("click", () => render(route));
          return;
        }
      }
      const day = route.day ? days.find((item) => item.day === route.day) : null;
      if (!day) return renderPath();
      const tab = TABS.some(([key]) => key === route.tab) ? route.tab : "study";
      ({ study: renderStudy, flash: renderFlashPicker, quiz: renderQuiz, spell: renderSpell, book: renderBook })[tab](day);
    }

    // ---------- 闯关路线 ----------
    function renderPath() {
      const state = host.getState();
      const totals = days.reduce(
        (sum, day) => {
          const stats = dayStats(day, state);
          sum.total += stats.total;
          sum.known += stats.known;
          sum.review += stats.fuzzy + stats.unknown;
          return sum;
        },
        { total: 0, known: 0, review: 0 }
      );
      const current = days.findIndex((day, index) => dayUnlocked(days, index, state) && dayStats(day, state).known < day.words.length);

      container.innerHTML = `
        <section class="panel wb-hero">
          <div>
            <p class="eyebrow">10-Day Wordbook</p>
            <h2>10天背完3000英语单词</h2>
            <p class="wb-sub">看图记词 → 闪卡自评 → 选择题 → 拼写。一天一个主题，掌握一半就点亮下一天。</p>
          </div>
          <div class="hero-stats wb-stats">
            <div class="stat-card"><span>已掌握</span><strong>${totals.known} / ${totals.total}</strong></div>
            <div class="stat-card"><span>待巩固</span><strong>${totals.review}</strong></div>
          </div>
        </section>
        <ol class="wb-path" aria-label="10 天闯关路线">
          ${days
            .map((day, index) => {
              const stats = dayStats(day, state);
              const unlocked = dayUnlocked(days, index, state);
              const done = stats.known === stats.total && stats.total > 0;
              const percent = stats.total ? Math.round((stats.known / stats.total) * 100) : 0;
              const status = done ? "done" : index === current ? "current" : unlocked ? "open" : "locked";
              const label = { done: "已完成", current: "进行中", open: "可以学", locked: "未点亮" }[status];
              return `
              <li class="wb-stop wb-${status}">
                <a href="#wordbook/day/${day.day}/study" class="wb-stop-link" aria-label="Day ${day.day} ${esc(day.title)}，${label}，掌握 ${percent}%">
                  <span class="wb-stop-dot" aria-hidden="true">${done ? "✓" : day.day}</span>
                  <span class="wb-stop-body">
                    <span class="wb-stop-day">DAY ${day.day} · ${label}</span>
                    <strong>${esc(day.title)}</strong>
                    <span class="progress-track wb-track" aria-hidden="true"><span class="progress-fill" style="width:${percent}%"></span></span>
                    <span class="wb-stop-meta">${stats.known} / ${stats.total} 词${stats.fuzzy + stats.unknown ? ` · ${stats.fuzzy + stats.unknown} 个待巩固` : ""}</span>
                  </span>
                </a>
              </li>`;
            })
            .join("")}
        </ol>`;
    }

    // ---------- 章节外框 ----------
    function frame(day, tab, body) {
      const stats = dayStats(day, host.getState());
      container.innerHTML = `
        <section class="panel wb-day">
          <div class="section-head">
            <div class="section-title">
              <span class="badge">${day.day}</span>
              <div>
                <a class="wb-back" href="#wordbook">← 闯关路线</a>
                <h2>Day ${day.day} · ${esc(day.title)}</h2>
              </div>
            </div>
            <div class="mode-name">掌握 ${stats.known} · 模糊 ${stats.fuzzy} · 不认识 ${stats.unknown} · 共 ${stats.total}</div>
          </div>
          <nav class="wb-tabs" aria-label="学习方式">
            ${TABS.map(([key, label]) => `<a href="#wordbook/day/${day.day}/${key}" ${key === tab ? 'aria-current="page"' : ""}>${label}</a>`).join("")}
          </nav>
          <div class="wb-body">${body}</div>
        </section>`;
      return container.querySelector(".wb-body");
    }

    function wordRow(day, word) {
      const level = levelOf(day, word);
      return `
        <li class="wb-word wb-lv-${level}" data-word="${esc(word.w)}">
          ${speakButton(word.w)}
          <div class="wb-word-copy"><strong>${esc(word.w)}</strong><span>${sensesHTML(word)}</span></div>
          <div class="wb-marks" role="group" aria-label="标记 ${esc(word.w)}">
            <button class="small-btn wb-mark-known" type="button" data-mark="3" aria-pressed="${level === 3}">认识</button>
            <button class="small-btn wb-mark-unknown" type="button" data-mark="1" aria-pressed="${level === 1}">不会</button>
          </div>
        </li>`;
    }

    function bindMarks(scope, day) {
      scope.addEventListener("click", (event) => {
        const button = event.target.closest("[data-mark]");
        if (!button) return;
        const row = button.closest(".wb-word");
        const word = day.words.find((item) => item.w === row.dataset.word);
        const wanted = Number(button.dataset.mark);
        const next = levelOf(day.day, word) === wanted ? 0 : wanted;
        host.setLevel(day.day, word, next);
        if (next === LEVELS.UNKNOWN) host.addToReview(day, word);
        row.className = `wb-word wb-lv-${next}`;
        row.querySelectorAll("[data-mark]").forEach((other) => other.setAttribute("aria-pressed", String(Number(other.dataset.mark) === next)));
      });
    }

    // ---------- 看图学 ----------
    function renderStudy(day) {
      const byPage = {};
      day.words.forEach((word) => (byPage[word.page] = byPage[word.page] || []).push(word));
      const pictures = day.pages.filter((page) => page.kind === "picture");
      const body = frame(
        day,
        "study",
        `<p class="wb-sub wb-pad">书里的建议：先看图把单词念一遍，尽量少看中文。点 🔊 听发音，点图片放大。</p>
        ${pictures
          .map(
            (page) => `
          <div class="wb-page">
            <button class="wb-page-img" type="button" data-zoom aria-label="放大原书插图">
              <img data-page="${pageName(page.index)}" alt="Day ${day.day} 插图：${esc(page.topics.join("、"))}">
            </button>
            <ul class="wb-words">${(byPage[page.index] || []).map((word) => wordRow(day.day, word)).join("")}</ul>
          </div>`
          )
          .join("")}
        <div class="wb-row wb-pad"><a class="primary-btn" href="#wordbook/day/${day.day}/flash">看完了，开始闪卡 →</a></div>`
      );
      bindMarks(body, day);
      loadImages(body);
    }

    // ---------- 闪卡 ----------
    function renderFlashPicker(day) {
      const body = frame(
        day,
        "flash",
        `<div class="wb-row wb-center wb-pad" role="group" aria-label="选择范围">
          <button class="secondary-btn" type="button" data-scope="all">全部 ${day.words.length} 词</button>
          <button class="secondary-btn" type="button" data-scope="new">只练没掌握的</button>
          <button class="secondary-btn" type="button" data-scope="20">随机 20 词</button>
        </div>
        <p class="wb-sub wb-center">快捷键：空格翻面 · 1 不认识 · 2 模糊 · 3 认识</p>
        <div class="wb-stage"></div>`
      );
      body.querySelector("[role=group]").addEventListener("click", (event) => {
        const button = event.target.closest("[data-scope]");
        if (!button) return;
        let words = day.words;
        if (button.dataset.scope === "new") words = words.filter((word) => levelOf(day.day, word) !== LEVELS.KNOWN);
        if (button.dataset.scope === "20") words = shuffle(words).slice(0, 20);
        body.querySelectorAll("[data-scope]").forEach((other) => other.classList.toggle("primary-btn", other === button));
        flashSession(body.querySelector(".wb-stage"), day, words);
      });
    }

    function flashSession(stage, day, words) {
      const deck = shuffle(words);
      const tally = { 1: 0, 2: 0, 3: 0 };
      let index = 0;
      let flipped = false;
      if (!deck.length) {
        stage.innerHTML = `<p class="empty">这一天的词都掌握了。</p>`;
        return;
      }

      function draw() {
        if (index >= deck.length) return finish();
        const word = deck[index];
        flipped = false;
        stage.innerHTML = `
          <p class="wb-count">${index + 1} / ${deck.length}</p>
          <button class="wb-flash" type="button" aria-label="翻转卡片，显示释义">
            <span class="wb-face wb-face-front"><strong>${esc(word.w)}</strong><small>点击或按空格查看释义</small></span>
            <span class="wb-face wb-face-back" aria-hidden="true">${word.senses.map(([pos, text]) => `<span><span class="wb-pos">${esc(pos)}</span>${esc(text)}</span>`).join("")}</span>
          </button>
          <div class="wb-row wb-center">${speakButton(word.w)}</div>
          <div class="wb-rate">
            <button class="secondary-btn wb-rate-1" type="button" data-rate="1">不认识 <kbd>1</kbd></button>
            <button class="secondary-btn wb-rate-2" type="button" data-rate="2">模糊 <kbd>2</kbd></button>
            <button class="secondary-btn wb-rate-3" type="button" data-rate="3">认识 <kbd>3</kbd></button>
          </div>`;
        host.speak(word.w);
      }
      function flip() {
        const card = stage.querySelector(".wb-flash");
        if (!card) return;
        flipped = !flipped;
        card.classList.toggle("flipped", flipped);
        card.querySelector(".wb-face-front").setAttribute("aria-hidden", String(flipped));
        card.querySelector(".wb-face-back").setAttribute("aria-hidden", String(!flipped));
      }
      function rate(level) {
        const word = deck[index];
        if (!word) return;
        host.setLevel(day.day, word, level);
        tally[level] += 1;
        if (level === LEVELS.UNKNOWN) {
          host.addToReview(day, word);
          // 不认识的词在这一轮稍后再出现一次
          if (!deck.slice(index + 1).includes(word)) {
            deck.splice(Math.min(deck.length, index + 4 + Math.floor(Math.random() * 3)), 0, word);
          }
        }
        index += 1;
        draw();
      }
      function finish() {
        keyHandler = null;
        stage.innerHTML = `
          <div class="wb-result">
            <h3>这一轮完成了</h3>
            <p>认识 ${tally[3]} · 模糊 ${tally[2]} · 不认识 ${tally[1]}</p>
            <div class="wb-row wb-center">
              <a class="primary-btn" href="#wordbook/day/${day.day}/quiz">去做选择题</a>
              <a class="secondary-btn" href="#wordbook">回到闯关路线</a>
            </div>
          </div>`;
      }
      stage.onclick = (event) => {
        if (event.target.closest(".wb-flash")) flip();
        const button = event.target.closest("[data-rate]");
        if (button) rate(Number(button.dataset.rate));
      };
      keyHandler = (event) => {
        if (event.key === " ") {
          event.preventDefault();
          flip();
        } else if (["1", "2", "3"].includes(event.key)) rate(Number(event.key));
      };
      draw();
    }

    // ---------- 选择题 ----------
    function renderQuiz(day) {
      const body = frame(day, "quiz", `<div class="wb-stage"></div>`);
      quizSession(body.querySelector(".wb-stage"), day);
    }

    function quizSession(stage, day) {
      if (day.words.length < 4) {
        stage.innerHTML = `<p class="empty">词太少，出不了题。</p>`;
        return;
      }
      const questions = buildQuiz(day.words, 15);
      const wrong = [];
      let index = 0;
      let score = 0;

      function draw() {
        if (index >= questions.length) return finish();
        const question = questions[index];
        stage.innerHTML = `
          <p class="wb-count">第 ${index + 1} / ${questions.length} 题 · 答对 ${score}</p>
          <div class="wb-question">
            <small>${question.enToZh ? "选出正确的中文意思" : "选出对应的英文单词"}</small>
            <strong>${question.enToZh ? esc(question.word.w) : sensesHTML(question.word)}</strong>
            ${question.enToZh ? `<div class="wb-row wb-center">${speakButton(question.word.w)}</div>` : ""}
          </div>
          <div class="wb-choices">
            ${question.options
              .map((option, optionIndex) => `<button class="wb-choice" type="button" data-choice="${optionIndex}">${optionIndex + 1}. ${question.enToZh ? sensesHTML(option) : esc(option.w)}</button>`)
              .join("")}
          </div>
          <p class="wb-feedback" aria-live="polite"></p>`;
        if (question.enToZh) host.speak(question.word.w);
      }
      function answer(choice) {
        const question = questions[index];
        const buttons = stage.querySelectorAll(".wb-choice");
        if (!question || !buttons.length || buttons[0].disabled || !question.options[choice]) return;
        const correct = question.options[choice] === question.word;
        buttons.forEach((button, buttonIndex) => {
          button.disabled = true;
          if (question.options[buttonIndex] === question.word) button.classList.add("right");
          else if (buttonIndex === choice) button.classList.add("wrong");
        });
        const feedback = stage.querySelector(".wb-feedback");
        if (correct) {
          score += 1;
          feedback.className = "wb-feedback ok";
          feedback.textContent = "答对了";
        } else {
          wrong.push(question.word);
          host.setLevel(day.day, question.word, LEVELS.UNKNOWN);
          host.addToReview(day, question.word);
          feedback.className = "wb-feedback no";
          feedback.textContent = `正确答案：${question.word.w} — ${sensesText(question.word)}`;
        }
        if (!question.enToZh) host.speak(question.word.w);
        setTimeout(() => {
          index += 1;
          draw();
        }, correct ? 800 : 2000);
      }
      function finish() {
        keyHandler = null;
        stage.innerHTML = resultHTML(score, questions.length, wrong, "答错的词已经放进「待复习」。", `#wordbook/day/${day.day}/spell`, "去练拼写");
        stage.querySelector("[data-again]").addEventListener("click", () => quizSession(stage, day));
      }
      stage.onclick = (event) => {
        const button = event.target.closest("[data-choice]");
        if (button) answer(Number(button.dataset.choice));
      };
      keyHandler = (event) => {
        if (["1", "2", "3", "4"].includes(event.key)) answer(Number(event.key) - 1);
      };
      draw();
    }

    function resultHTML(score, total, wrong, wrongNote, nextHref, nextLabel) {
      return `
        <div class="wb-result">
          <p class="wb-score">${score} / ${total}</p>
          <p>${wrong.length ? wrongNote : "全对，真棒。"}</p>
          ${wrong.length ? `<ul class="wb-words wb-wrong">${wrong.map((word) => `<li class="wb-word wb-lv-1">${speakButton(word.w)}<div class="wb-word-copy"><strong>${esc(word.w)}</strong><span>${sensesHTML(word)}</span></div></li>`).join("")}</ul>` : ""}
          <div class="wb-row wb-center">
            <button class="primary-btn" type="button" data-again>再来一组</button>
            <a class="secondary-btn" href="${nextHref}">${nextLabel}</a>
          </div>
        </div>`;
    }

    // ---------- 拼写 ----------
    function renderSpell(day) {
      const body = frame(day, "spell", `<div class="wb-stage"></div>`);
      spellSession(body.querySelector(".wb-stage"), day);
    }

    function spellSession(stage, day) {
      const questions = shuffle(day.words).slice(0, Math.min(10, day.words.length));
      const wrong = [];
      let index = 0;
      let score = 0;

      function draw() {
        if (index >= questions.length) return finish();
        const word = questions[index];
        let tries = 0;
        let reveal = 1;
        stage.innerHTML = `
          <p class="wb-count">第 ${index + 1} / ${questions.length} 题 · 拼对 ${score}</p>
          <div class="wb-question">
            <small>根据中文和发音拼出单词</small>
            <strong class="wb-question-zh">${sensesHTML(word)}</strong>
            <div class="wb-row wb-center">${speakButton(word.w)}</div>
            <p class="wb-mask" aria-label="字母提示">${esc(maskWord(word.w, reveal))}</p>
          </div>
          <form class="wb-spell" autocomplete="off">
            <label class="wb-sub" for="wbSpellInput">输入单词后按回车</label>
            <input id="wbSpellInput" class="wb-input" spellcheck="false" autocapitalize="off" autocorrect="off">
            <p class="wb-feedback" aria-live="polite"></p>
            <div class="wb-row wb-center">
              <button class="primary-btn" type="submit">提交</button>
              <button class="secondary-btn" type="button" data-hint>再给一个字母</button>
              <button class="secondary-btn" type="button" data-skip>不会，看答案</button>
            </div>
          </form>`;
        host.speak(word.w);
        const input = stage.querySelector("#wbSpellInput");
        const feedback = stage.querySelector(".wb-feedback");
        input.focus();
        stage.querySelector("[data-hint]").addEventListener("click", () => {
          reveal = Math.min(word.w.length, reveal + 1);
          stage.querySelector(".wb-mask").textContent = maskWord(word.w, reveal);
          input.focus();
        });
        stage.querySelector("[data-skip]").addEventListener("click", () => fail(word));
        stage.querySelector("form").addEventListener("submit", (event) => {
          event.preventDefault();
          if (!input.value.trim() || input.disabled) return;
          if (spellingMatches(input.value, word.w)) {
            score += 1;
            input.disabled = true;
            feedback.className = "wb-feedback ok";
            feedback.textContent = "拼对了";
            setTimeout(() => {
              index += 1;
              draw();
            }, 800);
          } else if (++tries < 2) {
            feedback.className = "wb-feedback no";
            feedback.textContent = "不太对，再试一次";
            input.select();
          } else fail(word);
        });
      }
      function fail(word) {
        const input = stage.querySelector("#wbSpellInput");
        if (input.disabled) return;
        input.disabled = true;
        wrong.push(word);
        host.setLevel(day.day, word, LEVELS.UNKNOWN);
        host.addToReview(day, word);
        const feedback = stage.querySelector(".wb-feedback");
        feedback.className = "wb-feedback no";
        feedback.textContent = `正确拼写：${word.w}`;
        host.speak(word.w);
        setTimeout(() => {
          index += 1;
          draw();
        }, 2200);
      }
      function finish() {
        stage.innerHTML = resultHTML(score, questions.length, wrong, "拼错的词已经放进「待复习」，书上建议多念多写几遍。", "#wordbook", "回到闯关路线");
        stage.querySelector("[data-again]").addEventListener("click", () => spellSession(stage, day));
      }
      if (!questions.length) {
        stage.innerHTML = `<p class="empty">没有可以拼写的词。</p>`;
        return;
      }
      draw();
    }

    // ---------- 原书练习页 ----------
    function renderBook(day) {
      const labels = { quiz: "单词测验", listen: "听力填空", try: "Try it! 看图写词", other: "其他" };
      const pages = [{ index: day.outlinePage, kind: "outline" }, ...day.pages.filter((page) => labels[page.kind])];
      const body = frame(
        day,
        "book",
        `<p class="wb-sub wb-pad">原书的测验、听力填空和 Try it! 练习页，可以在纸上作答。书里的 MP3 没有附在 PDF 里。</p>
        <div class="wb-gallery">
          ${pages
            .map((page) => {
              const label = page.kind === "outline" ? "单元大纲" : labels[page.kind];
              return `
            <figure>
              <button class="wb-page-img" type="button" data-zoom aria-label="放大 ${label}">
                <img data-page="${pageName(page.index)}" alt="Day ${day.day} ${label}">
              </button>
              <figcaption>${label}</figcaption>
            </figure>`;
            })
            .join("")}
        </div>`
      );
      loadImages(body);
    }

    return {
      render,
      reset() {
        days = null;
        imageUrls.forEach((promise) => promise.then((url) => URL.revokeObjectURL(url)).catch(() => {}));
        imageUrls.clear();
      },
    };
  }

  return { LEVELS, entryKey, emptyState, normalizeState, merge, dayStats, dayUnlocked, sensesText, buildQuiz, spellingMatches, maskWord, mount };
});
