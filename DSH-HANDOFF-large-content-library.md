# DSH Handoff — Sabrina English「大词库」收尾（第二轮交接）

- 生成：Copilot（MacBook）· 2026-10-16 午间 HKT · 读者：接手的 dsh 会话（Alex 也在看）
- 原任务：ChatGPT 桌面版 Codex 远程任务（执行机 = 本 Mac mini），「评估 Sabrina English 并恢复开发」的后续扩展
- 中断：2026-10-16 上午，ChatGPT 额度再次用尽，停在**最后一步**（提交 + 部署）之前；仓库工作区留有**已改好、已自测、但未提交**的改动
- ⚠️ 本任务**必须在 Mac mini 上执行**（路径 `/Users/owllittle/…`；仓库、服务、数据库都在这里）。不要在 MacBook 的副本上跑。
- 上一轮交接：`DSH-HANDOFF.md`（SQLite 迁移收尾，**已完成**，留档参考）

## 一句话任务

把工作区里未提交的最后一轮「别名归一 + 内容过滤」改动**复核 → 提交 → 复验 → 部署 → 补报告**，然后向 Alex 交付中文总结。
**不要重做大词库主体（已完成并已上线）。**

## 当前真实状态（2026-10-16 中午由 Copilot 实测）

- HEAD：`b1fd7b8 docs: record review fixes and production evidence`；工作区 6 个未提交文件：
  1. `assets/content-library.js` — ①`normalize()` 增加 14 组英美拼写别名（colour→color 等），让旧学习记录里的英式拼写也能匹配美式词条；②修复 `selectBatch` 尾端回绕：游标在列表尾端、剩余未学不足一批时，不再提前返回，回绕补齐一批。
  2. `scripts/generate_content.py` — `CONTENT_VERSION` 升到 `2026.10.16-3`；`DENY_WORDS` 追加 `bullshit/crap/fuck/fucked/fucker/fucking`。
  3. `content/vocabulary-b2.json` — 重新生成（移除 `fucking`、补入 `striking`；仍 800 词）。
  4. `content/manifest.json` — 版本号与 B2 分片 SHA-256 更新。
  5. `tests/test_content_library.py`、`tests/content_library_node_test.js` — 对应新增断言（别名归一、回绕补齐、黑名单扩充）。
- 已跑验证（当前工作区）：`python3 -m unittest discover -v` → **60/60 通过**；`python3 scripts/validate_content.py content` → **ok**；`git diff --check` 干净。
- 线上服务**直接从仓库工作区读文件**（`--root-dir` 指向仓库），所以这轮未提交改动其实**已经在线生效**；但未提交 = 没有回滚依据，必须完成提交与复验。
  - 已核实：本机与公网 `/content/manifest.json` 与工作区文件 SHA-256 一致（`0816c8617a6407043af07fcbd782f74a0c77fc492df3d848a599e418e9004150`）。
- 健康检查：本机 + 公网 `/api/health` 均 ok。
- 大词库主体（已完成、已提交、已上线，勿重做）：≥4000 词（A1–B2）+ 600 表达 + 250 句型、独立 JSON + manifest 哈希白名单、未学优先 / 同模式「再学一组」。
  - commits：`891b55d`/`cec965a`（设计/计划）、`63d8d00..4da2ed1`（Task 1–6）、`c09b219`（审查后加固：4 MiB 同步上限、复习轮换、先水合远端再选首批、过滤冒犯词）、`b1fd7b8`（报告）。

## 收尾步骤（按序执行；每步给真实输出）

1. **复核 diff**：`git diff`（上述 6 个文件）。确认改动与描述一致；如发现问题做最小修正并注明。
2. **提交**（保持本地，勿 push）：
   ```
   git add assets/content-library.js scripts/generate_content.py content/vocabulary-b2.json content/manifest.json tests/test_content_library.py tests/content_library_node_test.js
   git commit -m "fix: normalize aliases and content filters"
   ```
3. **全量复验**：`python3 scripts/validate_content.py content && python3 -m unittest discover -v && git diff --check`
   - 提示：普通 ssh 会话 fd 上限可能只有 256；若报 “Too many open files”，先 `ulimit -n 10240` 再跑。
4. **部署刷新**：`./deploy/install.sh`（重建 LaunchAgent 并 kickstart；自带 20 秒健康检查轮询）。
5. **线上核验**：
   - `curl -fsS http://127.0.0.1:18880/api/health` 与 `curl -fsS https://sabrina.redflyingpig.com/api/health`；
   - `shasum -a 256 content/manifest.json` 与 `curl -fsS https://sabrina.redflyingpig.com/content/manifest.json | shasum -a 256` 一致；
   - 白名单抽查：`curl -s -o /dev/null -w "%{http_code}" https://sabrina.redflyingpig.com/.git/HEAD` → 404；
   - `lsof -nP -iTCP:18880 -sTCP:LISTEN` 仅监听 127.0.0.1。
6. **浏览器烟测**：`node /tmp/sabrina-acceptance/large-library-smoke.mjs`（CDP 无头浏览器，覆盖载入/续学/离线/移动端；若脚本已丢失，按 `ACCEPTANCE-REPORT-2026-10-16.md` 的方法重建）。
   通过后**更新验收报告**：内容版本改为 `2026.10.16-3`、补新 manifest SHA-256 与本轮证据；向 `.superpowers/sdd/2026-10-16-large-content-library/progress.md` 追加一行记录；然后
   ```
   git add ACCEPTANCE-REPORT-2026-10-16.md .superpowers/sdd/2026-10-16-large-content-library/progress.md
   git commit -m "docs: record final alias-filter evidence"
   ```
7. **汇报**：commit 列表 + 关键命令输出摘要（中文）。

## 硬约束

- **不要 git push**；提交留在本地（push 与否由 Alex 定）。
- 只碰本仓库 + `ai.sabrina-english.*` 两个 LaunchAgent；mini 上其它服务（family-calendar、openclaw、hermes、minecraft、dms 等）一律不碰。
- **不重置 / 不打印任何 PIN 或密钥**；不把数据库、备份、token 提交进 git。
- 不加新功能；只做上述收尾。遇到边缘问题记录并汇报，别顺手扩大范围。
- 沙箱注意：只在本仓库与 `/tmp` 里操作；写用户家目录其他位置可能被沙箱拒绝。
- 全程中文。

## 环境速查

- 仓库：`/Users/owllittle/projects/sabrina-english`
- 服务：launchd `ai.sabrina-english.site`（127.0.0.1:18880）+ `ai.sabrina-english.backup`（每日 03:15，保留 30）；域名 `sabrina.redflyingpig.com`（Cloudflare Tunnel）
- 数据：`~/Library/Application Support/SabrinaEnglish/`（勿动，恢复流程见 `OPERATIONS.md`）
- 参考文档：`docs/superpowers/specs/2026-10-16-content-library-design.md`、`docs/superpowers/plans/2026-10-16-large-content-library.md`、`.superpowers/sdd/2026-10-16-large-content-library/progress.md`、`ACCEPTANCE-REPORT-2026-10-16.md`、`OPERATIONS.md`、`VOCABULARY-SOURCES.md`、`DSH-HANDOFF.md`（上一轮）

## 开场 Prompt（Alex 直接粘给 dsh 用）

> 仓库在 /Users/owllittle/projects/sabrina-english（Mac mini 上）。你是接手一个大词库项目的收尾：先通读 DSH-HANDOFF-large-content-library.md，再按它的「收尾步骤」执行——复核未提交 diff → 提交 → 全量验证 → 部署 → 线上核验 → 烟测 → 更新验收报告。不要重做已完成的大词库主体。先向我汇报你对现状与计划的理解，我确认后再动手；全程中文、每步给真实证据。
