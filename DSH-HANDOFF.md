# DSH Handoff — Sabrina English 上线收尾（原 ChatGPT/Codex 任务的续作）

生成：Copilot（MacBook）· 2026-10-16 凌晨 HKT · 读者：接手的 dsh 会话（Alex 也在看）
原任务：ChatGPT（Codex 远程任务）
- 线程：`评估 Sabrina English 并恢复开发`（id `01a14030-4095-7d12-a251-81ea683e7e72`）
- Goal id：`3cb8f02f-04e4-4591-ac6b-8cac0409d342`
- 中断：2026-10-16 00:51:42，ChatGPT 用量额度耗尽（status `usage_limited`），停在「Task 6 最终验收」尾声，最终报告未产出、最后由 Alex 的审查代理提出的两处小修刚提交完。

## 你要做的事（一句话）

按 `docs/superpowers/plans/2026-10-15-mac-mini-sqlite-sync.md` 的 **Task 6**，把剩余的验收证据补齐、修复遗留问题，并向 Alex 交付中文总结。**已完成的任务 1–5 不要重做。**

## 背景

把 Sabrina English（家庭个人英语学习站点）从被暂停的 Supabase 方案，迁到 Mac mini 原生 Python + SQLite + Cloudflare Tunnel：Owner / Sabrina / Max 三人用「用户名 + PIN」登录，学习记录存 Mac mini、跨设备同步。手机上也能随时打开。

- Spec（含 7 条部署验收）：`docs/superpowers/specs/2026-10-15-mac-mini-sqlite-sync-design.md`
- 执行台账：`.superpowers/sdd/2026-10-15-mac-mini-sqlite-sync/progress.md`
- 运维手册：`OPERATIONS.md`（安装/升级/备份/恢复/reset-pin/PIN 重置）

## 已完成的（已核实，可直接引用）

- 任务 1–5 全部实现并提交：`4b6366c..d923bc3`（SQLite 存储层 → HTTP API → admin+备份 → 前端替换 Supabase → 部署产物/OPERATIONS）。
- 部署后修复：`a6d1cd7`、`afa8400`、`0c835da`、`0545308`（含最终 review 提出的两处小修：状态条目 `history` 日期/键类型更严格校验；恢复流程先 staging、不先轮转备份）。
- 线上服务运行中：launchd `ai.sabrina-english.site`（127.0.0.1:18880，KeepAlive）+ `ai.sabrina-english.backup`（每天 03:15，保留 30 份）。
- 三个档案已初始化（2026-10-15 16:39:54Z）。初始 PIN 只在初始化时输出过一次（见原会话 `init-profiles` 那步的工具输出，约在会话后段；没保存就用 OPERATIONS.md 的 reset-pin 重设）。
- 第一份备份已生成：`~/Library/Application Support/SabrinaEnglish/backups/sabrina-20261015T164034Z.db`，完整性 `ok`；主库 `PRAGMA integrity_check` = `ok`。
- 公网：`https://sabrina.redflyingpig.com/` → 200（标题 Sabrina English Daily Lesson）；`/api/health` → `{"status":"ok","database":"ok"}`（Mac mini 与 MacBook 两侧均验证）。
- 自动化基线（@ `0545308`）：`python3 -m unittest discover -v` → **40 tests OK**；`git diff --check` 干净；工作区无未提交改动。
- 部分真实证据：Chrome headless 截图暂存于 `/private/tmp/sabrina-desktop.png`、`/private/tmp/sabrina-mobile.png`（及 `sabrina-chrome-mobile*` 目录；/private/tmp 会被系统清理，别当长期证据）。
- 权限：数据目录/备份目录 700，数据库文件 600，符合要求。
- 仓库 `main` 领先 `origin/main` 11 个 commit（**未 push**；push 与否先问 Alex）。

## 遗留待办（Task 6 Step 3–6 收尾）

1. **Step 3 尾项**：把第一份备份恢复到临时数据库做「恢复演练」（restore drill），给命令+结果证据。
2. **Step 4 真实验收（核心，未证实）**：桌面 + 手机视口打开公网站：
   - 三个档案分别登录、状态互不串号；
   - 同一档案两个浏览器上下文：一端标记学习 → 另一端可见；故意制造旧 `state_version` 写入 → 409 合并后不丢数据；
   - 以上在**公网路径**上验证（不只是 loopback）。
3. **Step 5 故障恢复（未证实）**：停服务 → 已打开页面继续记录（本地保留、显示离线）→ 起服务 → 自动同步；再重启一次 LaunchAgent，确认既有数据还在。
4. **复核 `0545308` 两处修复**：检查是否有针对性测试覆盖；缺什么补什么。
5. **Step 6 最终审计 + 交付**：重跑完整套件/健康检查/隔离/同步/备份/launchd+tunnel 状态；给 Alex 一份中文总结（7 条验收逐条对照、PIN 说明、剩余风险、改动文件清单）。

## 约束（硬性）

- 只改本仓库 + 只动 `ai.sabrina-english.*` 两个 LaunchAgent。Mac mini 上的其他服务（family-calendar、openclaw、hermes、dms、minecraft 等）**一律不碰**。
- 不把数据库/备份/PIN/token 提交进 git，也不要在输出里明文打印任何 secret。
- 保持克制：本阶段只做 Task 6 收尾，**不加新功能**。Alex 原话：「这不是什么复杂的项目。」
- 全程中文；先给「理解确认 + 简短计划」，等 Alex 回复后再动手。
- 每项验收给真实命令与输出（真证据）；改了哪些文件要列清楚。
- 环境注意：服务与测试都用系统 `/usr/bin/python3`（3.9.6，无 `scrypt`，因此实现里用 PBKDF2——这是已定的 ruling，别改）。

## 环境速查

- 仓库：`/Users/owllittle/projects/sabrina-english`（先 `git log -15` 感受上下文）
- 运行数据：`~/Library/Application Support/SabrinaEnglish/`（勿删；备份在其 `backups/`）
- 端口：127.0.0.1:18880；域名路由：sabrina.redflyingpig.com（Cloudflare Tunnel `mac-mini-hermes`）
- 健康检查：`curl --fail http://127.0.0.1:18880/api/health` / `curl --fail https://sabrina.redflyingpig.com/api/health`
- 参考资料（可选）：原 ChatGPT 任务的完整对话记录在 `~/.codex/sessions/2026/10/15/rollout-2026-10-15T23-31-06-*.jsonl`（含一次性 PIN 输出——仅供本地查阅，勿外传/打印）。

## 开场 Prompt（Alex 直接粘给 dsh 用）

> 仓库在 /Users/owllittle/projects/sabrina-english。你是接手一个被中断任务的收尾：先通读 DSH-HANDOFF.md、docs/superpowers/specs/2026-10-15-mac-mini-sqlite-sync-design.md、docs/superpowers/plans/2026-10-15-mac-mini-sqlite-sync.md（重点 Task 6）、.superpowers/sdd/2026-10-15-mac-mini-sqlite-sync/progress.md 和 OPERATIONS.md。不要重做已完成部分（任务 1–5 已完成，服务已在跑）。先向我汇报你对现状、剩余验收项的理解和一个简短计划，我确认后再开始。全程中文，每项验收给真实证据。
