# Sabrina English — 大词库升级验收报告

## 结论

2026-10-16 已把大词库版本部署到 Mac mini，并通过本机、公网、桌面和手机验收。现有 SQLite 数据库、三个用户档案及同步 schema 均未迁移或重置。

## 内容规模

| 内容 | 数量 |
| --- | ---: |
| A1 词汇 | 800 |
| A2 词汇 | 1,200 |
| B1 词汇 | 1,200 |
| B2 词汇 | 800 |
| 常用表达 | 600 |
| 句型 | 250 |

内容版本：`2026.10.16-3`。`python3 scripts/validate_content.py content` 输出 `content library: ok`。

## 自动化验证

- `python3 -m unittest discover -v`：60 项测试全部通过。
- 覆盖内容 schema、数量、唯一 ID、manifest SHA-256、静态文件白名单、ETag、选择器、旧历史兼容、同模式下一组、登录同步、备份和部署契约。
- `git diff --check`：通过。

## 部署与 HTTP 验证

- `./deploy/install.sh`：成功；没有覆盖数据库。
- 本机健康检查：`http://127.0.0.1:18880/api/health` 返回数据库正常。
- 公网健康检查：`https://sabrina.redflyingpig.com/api/health` 返回数据库正常。
- 公网、本机和仓库的 `content/manifest.json` SHA-256 一致：`0816c8617a6407043af07fcbd782f74a0c77fc492df3d848a599e418e9004150`。
- 本机返回的 A1 分片与仓库 SHA-256 一致：`727c297182c74223cc81453fbc427c558fc03f1f52937dab6d83afa1566c3701`。
- 本机与公网的 B2 分片与仓库 SHA-256 一致：`fb685b219809109ba57e221d3e529f07b05417393cb76649f09cebbe227fe1a3`（`2026.10.16-3` 重新生成后的分片）。
- `.git/HEAD`、`scripts/generate_content.py`、`sabrina_backend/app.py`、`content/ATTRIBUTION.md` 均返回 404。
- `lsof` 确认服务只监听 `127.0.0.1:18880`。

## 真实浏览器验收

使用 Mac mini 上的原生 Chrome，通过公网域名分别以 1440×900 和 390×844 视口登录 Owner：

- 桌面成功载入 5 张 Mode A 词汇卡；内容加载/错误状态正常隐藏。
- 在网络离线后完成整组并点击“再学一组”，仍为 Mode A，下一组 5 项与上一组零重复。
- 新的本地历史均带稳定 `contentId`。
- 离线验收前后服务端 `state_version` 和历史数量完全不变；临时会话已注销，没有留下验收学习记录。
- 手机视口显示 5 张卡片，无横向溢出。
- 导入、导出按钮宽度约 63px，保持紧凑。

独立代码审查后又补做了四项加固：同步请求上限由 1 MiB 提高到 4 MiB；整池学完后可以更新复习时间并轮换最久未复习内容；远端档案水合后才选择首批；过滤已知冒犯词、错误缩写和常见英美拼写重复。

截图：

- `/tmp/sabrina-acceptance/shots/large-library-desktop.png`
- `/tmp/sabrina-acceptance/shots/large-library-desktop-next-batch.png`
- `/tmp/sabrina-acceptance/shots/large-library-mobile.png`

## 收尾轮：别名归一与内容过滤（commit `a3e7a1e`）

在上线主体之后完成的最后一轮小改动，已提交、复验、重新部署并线上核验：

- `assets/content-library.js`：`normalize()` 增加 14 组英美拼写别名（`colour→color`、`centre→center`、`organise→organize`、`theatre→theater`、`travelling→traveling` 等），让旧学习记录中的英式拼写也能匹配美式词条；`selectBatch()` 尾端改为 `visited` 计数加取模回绕，游标位于列表尾端、剩余未学不足一批时不再提前返回，而是回绕补齐整批。
- `scripts/generate_content.py`：`CONTENT_VERSION` 升到 `2026.10.16-3`；`DENY_WORDS` 追加 `bullshit/crap/fuck/fucked/fucker/fucking`。
- `content/vocabulary-b2.json`：重新生成（移除 `fucking`、补入 `striking`；仍为 800 词、无重复）。
- `content/manifest.json`：版本号与 B2 分片 SHA-256 同步更新。
- 两个测试文件新增断言：英式别名归一、尾端回绕补齐、黑名单扩充。

复验与线上证据（2026-10-16 午间实测）：

- `python3 scripts/validate_content.py content` → `content library: ok`。
- `python3 -m unittest discover -v` → 60 项全部通过；`node tests/content_library_node_test.js` → `content library node tests: ok`。
- `git diff --check` → 通过。
- `./deploy/install.sh` → 成功，服务进程由 PID 33623 重启为 47953，健康检查通过。
- 本机与公网 `/api/health` 均返回 `{"status":"ok","database":"ok"}`。
- 仓库 / 公网 `manifest.json` SHA-256 一致：`0816c8617a6407043af07fcbd782f74a0c77fc492df3d848a599e418e9004150`；公网 manifest 版本为 `2026.10.16-3`。
- `.git/HEAD`、`.git/config`、`sabrina_backend/app.py` 均返回 404；`content/manifest.json` 返回 200。
- `lsof` 确认服务只监听 `127.0.0.1:18880`。

收尾轮浏览器烟测（同一 CDP 无头脚本，覆盖载入 / 续学 / 离线 / 移动端，`exit=0`）：桌面载入 5 张 Mode A 词汇卡、加载与错误状态正常隐藏；离线整组完成后「再学一组」仍为 Mode A、下一组 5 项与上一组零重复、新历史均带 `contentId`；服务端 `state_version` 与历史数量完全不变；390px 视口 5 张卡片、无横向溢出、导入导出按钮宽约 63px。实际结果：

```json
{"desktop":{"mode":"A","cards":["missing","dramatically","internal","initiative","infection"],"importWidth":63.125,"exportWidth":63.125,"errorHidden":true,"loadingHidden":true},"continuation":{"mode":"A","cards":["density","social","eye","isle","treaty"],"localNewContentIds":["v1:infection","v1:initiative","v1:internal","v1:dramatically","v1:missing"],"overlap":[]},"mobile":{"width":390,"cards":5,"importWidth":63.125,"exportWidth":63.125,"horizontalOverflow":false},"productionUnchanged":true}
```

上述截图即本轮烟测在 2026-10-16 12:42 重新生成的产物。

## 频率优先轮：先学高频词（commit `bf43945`）

**问题**：`selectBatch()` 选词前先做带种子的 Fisher–Yates 洗牌，生成器排好的频率顺序在用户侧被完全打乱。实测前 50 个会遇到的词平均频率名次为 **403**，其中 13/25 来自该等级后半段——学习者一上来就遇到偏生僻的词。

**修复**：未学课程改为按**分片顺序**（即生成器的频率升序）取词，并把功能词（冠词、代词、助动词、介词、连词、限定词）排到最后。功能词是被**降级而非删除**，学完本级实词后仍会出现；复习轮换保留原有洗牌以打散复习项。

关键点：每个分片由 `scripts/generate_content.py` 以 `min(bnc, frq)` 升序输出，**数组顺序本身就是优先级信号**，因此无需新增频率字段、无需重新生成词库、无需改动 manifest 分片哈希。

**实测效果**（A1，每天 5 词）：

| | 第 1 天 | 前 50 词平均频率名次 | 功能词首次出现 |
|---|---|---:|---:|
| 修复前 | `the, be, and, of, a` | 403 | 第 1 位 |
| 修复后 | `say, go, get, make, know` | 25 | 第 657 位 |

**不变量校验**（新逻辑的正确性建立在此假设上）：四个分片实测**零逆序对**，且频率区间首尾相接——A1 `1–738`、A2 `738–1919`、B1 `1920–3147`、B2 `3148–3929`。已新增测试 `test_production_shards_are_frequency_ascending` 守住该不变量（数据源缺失时自动跳过）。

**本轮线上证据**（2026-10-16）：

- `content/manifest.json` 版本升为 `2026.10.16-4`，使已存在档案的选择游标重新锚定到新顺序。
- `./deploy/install.sh` → 成功，服务进程 PID 47953 → 53282。
- 仓库 / 公网 manifest SHA-256 一致：`8c71a1bd4e0619a55714d23e72e3b1c9c2195e832ffe7b41ed6983c5b74043ca`。
- 公网 `assets/content-library.js` 与仓库逐字节一致（SHA 前缀 `9028135acc608e92`），含新 `priorityOrder` 逻辑。
- 真实浏览器加载生产站点实测卡片为 `test, establish, movie, eight, computer`，位于优先级序的**连续位置 480–484**（单调递增），全部为实词；功能词首次出现在第 657 位。
- `python3 -m unittest discover` → 61 项通过；`node tests/content_library_node_test.js` → ok；`validate_content.py content` → ok。
- 原有大词库烟测 `large-library-smoke.mjs` 重跑 → exit 0，续学/离线/移动端无回归。

> 注意：报告前文「内容版本：`2026.10.16-3`」与其中的 manifest/分片哈希描述的是别名归一那一轮的在线状态；截至频率优先轮，**当前线上内容版本为 `2026.10.16-4`，manifest SHA 为 `8c71a1bd…b74043ca`**，各分片哈希未变。

## 每日 10 词与带状优先级（commit `9aeddf4`）

**需求**：Mode A 词汇量由每天 5 个提升到 10 个；优先级不再严格从头到尾，允许窗口内随机，高频先出现、低频后出现，偶尔混入邻近低频词可以接受。

**实现**

- `index.html`：`batchSizes` 的 `A` 由 `5` 改为 `10`，副标题同步为「今天的 10 个单词」。Mode B/C 数量不变。
- `assets/content-library.js`：优先级由「严格队列」改为「滑动窗口 + 分层」：
  - `PRIORITY_WINDOW = 10`，批次从游标后 `size + 10` 个位置中抽取，窗口内用种子随机（`seed|jitter|start`）打散，因此高频居前但允许邻近词混入。
  - 窗口内**先取实词、实词不足才取功能词**，避免功能词插队到尚未学完的实词之前。
  - 游标跳过整个窗口，因此相邻批次不复用位置、不会重复。
- `content/manifest.json` 版本升为 `2026.10.16-5`（选择算法变更）。分片字节未变。

**实测行为**（4000 词拼接数组，每天 10 词，连续 4 天）：

| 天 | 会学到的词 | 优先级位置 |
|---|---|---|
| 1 | take, get, see, new, think, want, time, go, make, give | 1–18 |
| 2 | back, man, day, people, thing, yeah, good, find, come, three | 11–29 |
| 3 | last, tell, mean, use, call, woman, oh, put, child, work | 21–40 |
| 4 | state, become, great, leave, old, try, feel, ask, system, school | 39–53 |

位置呈带状推进，窗口间交叉但不跳级；功能词被可靠推迟到实词之后。

**本轮线上证据**（2026-10-16，模式 A）：

- `./deploy/install.sh` → 成功，服务进程 PID 53282 → 54983。
- 公网 manifest 版本 `2026.10.16-5`；公网 `assets/content-library.js` 与仓库逐字节一致（SHA 前缀 `606d0e14cf1fb75b`）；线上 `index.html` 含 `batchSizes = { A: 10 }`。
- 真实浏览器实测：模式 A、副标题「今天的 10 个单词」、进度 `0 / 10`、**卡片数 10**。
- 卡片 `species, finger, solution, positive, arise, consumer, partner, scientist, safe, examine` 在 4000 词优先级序中的位置为 `960–979`（跨度 19，符合窗口设计），全部可定位、无重复。
- `python3 -m unittest discover` → 61 项通过；`node tests/content_library_node_test.js` → ok；`validate_content.py content` → ok。
- 大词库烟测 `large-library-smoke.mjs` 重跑 → exit 0；桌面与移动端均 10 张卡、移动端无横向溢出、续学零重复、服务端 `state_version` 与历史数量不变。

> 注意：报告前文「内容版本：`2026.10.16-3`」及其中哈希描述的是别名归一那一轮的在线状态。**当前线上内容版本为 `2026.10.16-5`**；各分片哈希自 `2026.10.16-3` 起未变，manifest SHA 见 `git show 9aeddf4:content/manifest.json` 的计算结果。

## 单词书优先轮（commit `097ad4d`）

**背景**：Sabrina 反馈 ECDICT 词库偏难。改为以「10天单词书」tab 引用的那本扫描词书为主词源，让每日课程与她在词书里的学习内容对齐。设计见 `docs/superpowers/specs/2026-10-17-wordbook-first-lessons-design.md`。

**架构约束**：词书是扫描版书籍，数据在 `~/Library/Application Support/SabrinaEnglish/wordbook/data.json`，后端注释明确「never in git」，且 `/api/wordbook/data` 需登录才返回（未登录实测 401）。因此**不生成新的内容分片**，而是在客户端登录后运行时合并。

**实现**

- `assets/content-library.js`
  - `wordbookLessonItems()`：把词书词条转成课程卡，id 为 `wb:<day>:<word>`，与 ECDICT 的 `v1:*` 隔离；释义用书上的 `senses`；音标复用同名 ECDICT 词，多词短语（`main dish`、`shaved ice`）音标留空、不编造。
  - `buildLessonPool()`：词书词优先、ECDICT 兜底；同词只出一次且用书上释义；书内跨天重复的单词只教第一次（1969 条目 → 1507 唯一词）。
  - `wordbookKnownKeys()` + `selectBatch()` 两段式：词书段按书的 Day 顺序直取（不参与频率窗口随机），ECDICT 段保留原有频率窗口逻辑。
- `index.html`
  - 登录后拉取 `/api/wordbook/data` 并入选词池；请求失败静默回退为纯 ECDICT，不阻塞主 tab。
  - `markLearned()` 学完词书词条时同步写入词书 `entries`（`level=2 FUZZY`）并触发既有 `scheduleProfileSync()`。
  - `getDisplayItems()` 保留 `wordbookDay/wordbookWord`（初版遗漏该字段导致反向同步失效，已修复）。
- `content/manifest.json` 版本升为 `2026.10.17-1`。

**进度双向联动语义**：每日课程只把词标为 `FUZZY`（见过、需巩固）；提升到 `KNOWN` 仍由词书测验/拼写模块负责，两个 tab 不互相覆盖。**只有 `KNOWN` 的词会退出每日候选**——`FUZZY`/`UNKNOWN` 仍会复现，符合「需要练习的词更该重复」的直觉。

**实测数据**

| 指标 | 数值 |
|---|---:|
| 词书条目 / 唯一词 | 1969 / 1507 |
| ECDICT 音标覆盖 | 1893/1969（96%） |
| 与现有 4000 词重叠 | 1125 |
| 每天 10 词可支撑 | 约 150 天 |

**线上核验**（真实浏览器，Max 档案临时会话；验证后已删除会话并还原 Max 数据）

- 模式 A、进度 `0 / 10`、**卡片数 10**。
- 卡片全部来自词书，且在书序中的位置为 `991–1000` 连续递增 → **确实按 Day 顺序推进**。
- 学完第一张卡（`border`）后词书写入 `{"6:border": {"level": 2}}` → **反向同步生效**。
- 把该书词标为 `KNOWN(3)` 后重载，该词**不再出现在每日课程**（下一次为 `clock…article`）→ **正向过滤生效**。
- 未登录访问 `/api/wordbook/data` → `401`。

**验证与部署**

- `python3 -m unittest discover` → 71 项通过；`node tests/content_library_node_test.js` → ok；`node tests/wordbook_node_test.js` → ok；`validate_content.py content` → ok。
- `./deploy/install.sh` → 成功。
- 线上内容版本 `2026.10.17-1`。

## 发现问题（未在本轮修复）

**`erm` 词条翻译错误**：ECDICT 中 `erm` 的 `.bnc` 排名为 133、无 `collins` 等级，translations 为 `abbr. ermine 貂; erythromycin 红霉素`，即被当作缩写收录，而非口语填充词。生成器的 `_translation()` 会剥掉 `abbr.` 前缀，导致它以「生僻缩写」形态进入 A1（优先级序第 50 位），实测会出现在第 4 天的候选里。同批检查中 `oh`（collins 5）、`yeah`（bnc 103）为正常口语词，无需处理。

这属于生成器的数据清洗问题（应拒绝或无中文义项可用的缩写条目），与频率排序改动无关，按「不扩大范围」原则本轮未改，留作后续独立修复。

## 回滚确认

本次升级不改 SQLite schema。上一版可直接重新安装并继续读取现有数据；新增的 `contentId` 字段会被旧版安全忽略。回滚时必须让 `index.html`、`assets/content-library.js` 和整个 `content/` 来自同一提交，避免 manifest 与分片哈希不一致。

## 已知边界

ECDICT 的 A1–B2 分组是按频率和可用性生成的学习顺序，不是官方 CEFR 认证。词库适合个人日常学习和降低重复率；若未来要做考试级精确分级，应另引入有明确授权的 CEFR 标注数据源。
