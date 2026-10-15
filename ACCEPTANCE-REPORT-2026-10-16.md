# Sabrina English — Task 6 收尾验收报告

**TL;DR**
- ✅ **完成**：Task 6 剩余全部验收 —— 恢复演练、公网真实浏览器验收（桌面 1440×900 / 手机 390×844，A–D 共 28 项断言全过：真实登录、标记已学、收藏、复习、三档案隔离、双端同步、409 合并重试、离线续记与自动同步）、服务真实重启、最终审计；并修复 `backup.py` sidecar 残留 + 补 3 条测试（`43 tests OK`，工作区干净）。
- ⚠️ **未完成（2 项，都不影响线上使用）**：① 沙箱禁止写家目录，`backups/` 里 4 个旧残留文件删不掉（§8.1 一条命令即可清）；② 备份 LaunchAgent 的首次*定时*运行要等今晚 03:15（至今 `runs = 0`，第一份备份是上一轮手工跑的）。
- 🙋 **需要 Alex 做**：① 跑 §8.1 的残留清理命令；② 决定是否 `git push`（本地领先 `origin/main` 14 个 commit，未 push）；③ 早上瞄一眼 03:15 的首次定时备份是否干净（§8.2，两条命令）。

---

## 1. 本次范围与结论

只做 Task 6 收尾：恢复演练、真实验收、遗留修复、最终审计、交付报告。**没有加新功能**，没有碰其他服务（family-calendar / openclaw / hermes / dms / minecraft / cloudflared 配置一律未动），只在 `ai.sabrina-english.*` 范围内操作。

验收结论：**spec 的 7 条部署验收全部通过**（§6 逐条对照），其中第 5 条用「CDP 网络离线模拟」替代「真的停 API」，第 6 条用了真实的服务重启（`launchctl kickstart -k`，比预期能做得多）。

## 2. 环境与证据位置

| 项目 | 值 |
| --- | --- |
| 仓库 | `/Users/owllittle/projects/sabrina-english`，起点 `0978bc3`，收尾提交见 §7 |
| 服务 | `launchd ai.sabrina-english.site` → `127.0.0.1:18880`（仅回环，`lsof` 已证） |
| 公网 | `https://sabrina.redflyingpig.com/`（Cloudflare Tunnel，`cf-ray` 已证） |
| 数据 | `~/Library/Application Support/SabrinaEnglish/`（目录 700、库文件 600） |
| 运行环境 | `/usr/bin/python3` 3.9.6；Chrome 155 headless（`--headless=new --no-sandbox`，CDP 驱动，Node 26 内置 WebSocket） |
| 证据根目录 | `/tmp/sabrina-acceptance/`（`logs/` 命令日志、`shots/` 截图、`results-*.json` 结构化结果、`*.py`/`*.mjs` 脚本） |
| PIN | 存于 `/tmp/sabrina-acceptance/pins.txt`（600），**全程未打印明文**；未 reset |

证据目录（供 Alex 复核）：

```
/tmp/sabrina-acceptance/logs/task1-restore-drill.log
/tmp/sabrina-acceptance/logs/scenario-{a,b,c,d}.log        # 浏览器验收原始输出
/tmp/sabrina-acceptance/logs/scenario-e-sync-state.log     # 同步状态横幅补充截图
/tmp/sabrina-acceptance/logs/task3a-backup-fix.log
/tmp/sabrina-acceptance/logs/task3a-restore-from-fixed-backup.log
/tmp/sabrina-acceptance/logs/task4-runtime-status.log  task4-launchctl-detail.log
/tmp/sabrina-acceptance/logs/task4-live-restart.log    task4b-post-restart.log
/tmp/sabrina-acceptance/logs/task-restart-check.log
/tmp/sabrina-acceptance/logs/task5-final-audit.log
/tmp/sabrina-acceptance/results-{a,b,c,d}.json
/tmp/sabrina-acceptance/shots/*.png（26 张）
```

## 3. 逐项验收

### 3.1 恢复演练（Task 6 Step 3 尾项）— 通过

命令与输出摘录（`logs/task1-restore-drill.log`）：

```
$ cp "…/backups/sabrina-20261015T164034Z.db" /tmp/sabrina-acceptance/restore-test.db   # 源文件只读
$ shasum -a 256 …   9be36372193316b6a558ed8bdd7dbef03086e4396528af73571ef80a20b3b55b  (源与副本一致)
$ sqlite3 restore-test.db 'PRAGMA integrity_check;'   → ok
$ sqlite3 restore-test.db 'PRAGMA foreign_key_check;' → （空）
$ sqlite3 restore-test.db ".tables"                   → profiles  schema_version  sessions
$ sqlite3 restore-test.db "select * from schema_version;" → 1
$ sqlite3 restore-test.db "select count(*) from profiles;" → 3
1|owner|Owner|0|83|2026-10-15T16:39:54.540809+00:00
2|sabrina|Sabrina|0|83|2026-10-15T16:39:54.684442+00:00
3|max|Max|0|83|2026-10-15T16:39:54.829412+00:00
$ sqlite3 restore-test.db "select count(*) from sessions;" → 0
```

结构、schema 版本（1）、三档案行数与备份时间点（`state_version=0`，即真实验收前）完全一致；演练副本用完即删（`restore-test.db*` 已确认 0 残留）。**副产品发现**：该备份是 WAL 模式，`sqlite3 -readonly` 打不开（`unable to open database file`）——正是 §4.1 修复的动机之一。

### 3.2 公网桌面 + 手机真实浏览器验收（Step 4 之一）— 8/8 通过

真实 `https://sabrina.redflyingpig.com/`，真实登录页 + 真实 `loginProfile()`（PIN 用 CDP `Input.insertText` 真实输入，表单真实提交），Owner 档案：

| # | 检查 | 结果 |
| --- | --- | --- |
| A1 | 桌面 1440×900 真实登录 | PASS（`profileBar` 显示 Owner，token 已存 localStorage） |
| A2 | 会话令牌 + `已同步到 Mac mini` | PASS |
| A3 | 标记已学 → 本地写 + 服务端同步 | PASS（local 3 = server 3，`version 4→5`） |
| A4 | 收藏（待复习） | PASS（local 1 = server 1，`A:meeting`） |
| A5 | 复习流程（开始 → 查看答案 → 下一题） | PASS（`1 / 3` → `2 / 3`） |
| A6 | 连续天数 / 进度 / 导出+导入入口 | PASS（`1 天 🔥`、`3 / 5`） |
| A7 | **手机 390×844 独立上下文登录，看到桌面端的记录** | PASS（history 3、favorites 1，标题一致） |
| A8 | 手机再标记一条 → 服务端增长 | PASS（`3→4`，`version 6→7`） |

截图：`shots/a-desktop-0{1..5}-*.png`、`shots/a-mobile-0{1..3}-*.png`（手机截图为 390×844@3x）。

### 3.3 三档案数据隔离（Step 4 之二）— 8/8 通过

| # | 检查 | 结果 |
| --- | --- | --- |
| B1 | Sabrina 登录只看到自己的状态（Owner 已有数据） | PASS（UI 2 = server 2，与 Owner 4 条无交集） |
| B2 | **Sabrina 令牌无法读写 Owner** | PASS（`GET /api/profile?username=Owner&profile_id=1` → 仍返回 Sabrina；带 `profile_id=1,username=Owner` 的过期写入 → `409`，服务端解析出的仍是 Sabrina；Owner `state_version` 不变、无伪造条目落库） |
| B3 | 伪造 Bearer 令牌 | PASS（`401`） |
| B4 | Sabrina 标记一条 → 只有 Sabrina 变化 | PASS（`2→3`，`v2→3`，Owner 仍 v7） |
| B5 | 同一浏览器 Sabrina→Owner 切换，显示的是 Owner 自己的数据 | PASS（`ownerKeyHistory=4`、`sabrinaKeyHistory=3`，显示标题集合 = Owner 服务端集合） |
| B6 | 切回 Sabrina 仍是她自己的记录；旧令牌已失效 | PASS（旧令牌 `401`，证明 logout 真的删了会话） |
| B7 | Max 手机视口登录只看自己的状态 | PASS |
| B8 | Max 写入 → Owner / Sabrina 均不动（三方隔离） | PASS |

截图：`shots/b-0{1..6}-*.png`。补充：前端 localStorage 按 `sabrinaEnglish:<username>:history|favorites|streak` 分键存放，切换用户不串号（B5/B6 的 DOM 断言）。

### 3.4 同档案双浏览器上下文：同步 + 409 合并（Step 4 之三）— 8/8 通过

两个**互相隔离的 browser context**（= 两台设备），都用真实 UI 登录 Owner：

| # | 检查 | 结果 |
| --- | --- | --- |
| C1 | A 端点「清空」→ 空状态同步到服务端 | PASS（`history 3→0`，`version 15→16`，收藏保留） |
| C2 | B 端登录，hydrate 到同一起点 | PASS（两端 history=0，server v16） |
| C3 | A 标记一条 → 到服务端 | PASS（`history 0→1`，`v16→17`） |
| C4 | **B 端可见 A 的记录**（用 App 自己的 `visibilitychange` 刷新钩子） | PASS（B history=1，key 与 A 完全一致） |
| C5 | B 再标记一条 → 版本推进 | PASS（`1→2`，`v17→18`） |
| C6 | **人为用旧 `state_version` 写入 → 409**，且库不变 | PASS（`PUT state_version=16` → `HTTP 409 error=version_conflict current_version=18 current_profile=Owner`；服务端仍 v18/h2，伪造条目未落库） |
| C7 | **前端 409 → 合并 → 只重试一次，不丢数据** | PASS（页面内 `fetch` 序列 `[200,200,409,409,200]`＝A 首写、B 写、C6 探测 409、真实冲突 409、重试 200；服务端 `history 2→3`、`v18→19`；服务端标题集合 `["busy","meeting","office"]` **与 A 端本地完全一致**） |
| C8 | B 端看到合并后的并集 | PASS（B history=3，标题 = 服务端并集） |

截图：`shots/c-0{1..5}-*.png`（`c-04-after-merge.png` 可见三条记录 + 收藏仍在）。

### 3.5 离线路径（Step 5）— 4/4 通过

用 CDP `Network.emulateNetworkConditions(offline=true)` 断网（浏览器 `navigator.onLine` 真的变为 `false`，`window` 的 `online` 事件也由浏览器真实派发）：

| # | 检查 | 结果 |
| --- | --- | --- |
| D1 | 离线时页面显示离线状态，课程照常渲染 | PASS（`syncState="离线模式 · 稍后自动重试"`，5 张卡片仍在） |
| D2 | 离线学习动作写进 localStorage，**没有**发到服务端 | PASS（local `4→5`；服务端仍 h4/v20；`syncState="同步失败 · 记录仍保存在本机"`） |
| D3 | 恢复网络 → 自动同步成功 | PASS（浏览器派发 `online` → App `online` 钩子 → `GET 200` + `PUT 200`；服务端 `4→5`、`v20→21`） |
| D4 | 整页刷新 + 重新登录后记录仍在（会话也从 localStorage 自动恢复） | PASS（history=5，标题完整） |

截图：`shots/d-0{1..4}-*.png`，另有 `shots/e-01-sync-state-online.png`（`已同步到 Mac mini`）与 `shots/e-02-sync-state-offline.png`（`离线模式 · 稍后自动重试`，横幅在页面底部的档案栏里）。

### 3.6 服务重启 / LaunchAgent / Tunnel（Step 5 后半 + Step 6）— 通过

沙箱一开始被认为看不到 GUI 服务，实测 `launchctl print` / `kickstart` 可用，所以做成了**真实重启**：

```
$ launchctl print gui/501/ai.sabrina-english.site   → state = running, pid = 84251, runs = 2
$ launchctl kickstart -k gui/501/ai.sabrina-english.site   → exit 0
[01:49:03] recovered after 0.5s: agent={'state': 'running', 'pid': '96164', 'runs': '3'} loopback_health=200
[01:49:03] before fingerprint: Owner state_version=21 history=[office, meeting, busy, early, report] favorites=[A:meeting]
[01:49:03] after  fingerprint: 完全一致
$ curl -s --fail http://127.0.0.1:18880/api/health      → {"status":"ok","database":"ok"}
$ curl -sI https://sabrina.redflyingpig.com/            → HTTP/2 200, server: cloudflare, cf-ray: a4b0a8988f1fc6b8-HKG
$ curl -s --fail https://sabrina.redflyingpig.com/api/health → {"status":"ok","database":"ok"}
$ lsof -nP -iTCP:18880 -sTCP:LISTEN  → Python 96164 … TCP 127.0.0.1:18880 (LISTEN)   # 只绑回环
$ launchctl print gui/501/ai.sabrina-english.backup → state = not running, runs = 0, last exit code = (never exited)
```

另外做了进程级「重启—数据仍在」的独立复核（`logs/task-restart-check.log`）：把线上库用 SQLite backup API 快照到 `/tmp`，用同一份代码在 `127.0.0.1:18899` 起独立实例，**连起两轮**（kill → 起 → kill → 起），每轮拿到的 Owner 指纹与线上完全一致，退出后 `integrity_check=ok`、`profiles=3`。

> 说明：备份 Agent 的 `runs = 0` 是正常的——它是每天 03:15 的日历任务，部署至今还没到点；第一份备份是上一轮手工执行的。

## 4. 代码修复与新增测试

### 4.1 `backup.py` 临时 sidecar 残留 — 已修复

**现象**（`ls -la …/backups/`，修复前）：

```
.sabrina-20261015T164034Z.db.tmp-shm   32768   ← 备份例程留下
.sabrina-20261015T164034Z.db.tmp-wal       0   ← 备份例程留下
sabrina-20261015T164034Z.db            32768
sabrina-20261015T164034Z.db-shm        32768   ← 之后有人打开备份文件时留下
sabrina-20261015T164034Z.db-wal            0
```

**根因**（实测复现）：`with sqlite3.connect(...)` 只提交事务、**不关闭连接**；临时库继承了 WAL 模式，连接还开着就把 `.tmp` 改名成正式文件，于是 `.tmp-wal/-shm` 永远没人清理（进程直接退出时更明显）。另外成品备份是 WAL 模式，在没有可写目录/`-shm` 的情况下**只读打不开**（§3.1 已实测）。

**修复**（`sabrina_backend/backup.py`）：用 `contextlib.closing` 明确关闭每个连接；在临时文件上执行 `PRAGMA journal_mode = delete`，把 WAL 收进成品，使每个备份都是**自包含单文件**；`finally` 里清掉临时名与成品名的 `-wal/-shm` 残留。`OPERATIONS.md` 补充了「备份目录里应只有 `sabrina-*.db`」的说明。

**修复后验证**（真实子进程，`logs/task3a-backup-fix.log`）：

```
$ SABRINA_DATA_DIR=… python3 -m sabrina_backend.backup --keep 30
$ ls -A backups/   → sabrina-20261015T174716Z.db            （只有一个文件）
$ sqlite3 -readonly <backup> 'PRAGMA integrity_check;'  → ok     （只读可开，无需 -shm）
$ xxd -s 18 -l 2 <backup>  → 0101                                 （rollback journal）
$ 再跑一次 → sabrina-…4716.db  sabrina-…4717.db                   （无任何 sidecar）
```

并且**用修复后的备份真的恢复起服务**（`logs/task3a-restore-from-fixed-backup.log`）：还原成 `sabrina.db` → 健康检查 `{"status":"ok","database":"ok"}`、Owner `version 21`、5 条记录 + 1 收藏完整；服务启动时按设计把它切回 WAL。

**新增测试**（`tests/test_admin_backup.py`）：
- `test_backup_leaves_no_temporary_or_sidecar_files`（修复前 FAIL → 修复后 PASS）
- `test_backup_is_self_contained_for_read_only_readers`（修复前 `unable to open database file` ERROR → 修复后 PASS）

### 4.2 `0545308` 修复 2（staging 恢复顺序）— 补了行为测试

原提交只改了 `OPERATIONS.md` 的恢复步骤（先 `cp` 到 `restore-staging.db` 并校验，再隔离旧库、最后 `mv` 就位），属文档级契约。新增 `test_documented_restore_stages_before_replacing_live_database`：**直接抽取 `OPERATIONS.md` 里的那段 shell 逐步执行**（只把数据目录/备份路径/python 换成临时值，`launchctl` 与 `./deploy/install.sh` 用 stub，其余真跑），构造「备份之后主库又写了新数据、且 `-wal` 里有待重放的提交」的场景，断言：

1. 恢复后主库内容是**备份快照**（不是被 WAL 重放的旧数据）；
2. `restore-staging.db` 已被消费掉；
3. `pre-restore/` 里保留了恢复前的主库；
4. 恢复前脚本自己抓的**安全备份**里是「更新的那份状态」（可回退）；
5. 恢复后 `integrity_check = ok`，且脚本确实重新安装了服务。

修复前该测试因为沙箱不许写 `~/Library/LaunchAgents` 而失败（说明它真的在执行 runbook），改用临时「假项目目录」后稳定通过。

## 5. 最终审计（`logs/task5-final-audit.log`）

```
1) python3 -m unittest discover -v   → Ran 43 tests … OK        （基线 40 + 新增 3）
2) git diff --check                  → 干净；git status --short → 工作区无改动
3) 健康检查   loopback {"status":"ok","database":"ok"} ；public HTTP 200 {"status":"ok","database":"ok"}
4) 三档案隔离 Owner v21/h5/f1 ；Sabrina v3/h3 ；Max v3/h3；三者的「查询串伪造读取」均返回自己
5) 主库 integrity_check=ok、profiles=3；首份备份副本 integrity_check=ok、profiles=3
   权限：数据目录/备份目录 drwx------ (700)，sabrina.db -rw------- (600)
```

## 6. spec 的 7 条部署验收逐条对照

| # | spec 要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| 1 | Mac mini 本机健康检查成功 | ✅ | `curl 127.0.0.1:18880/api/health` → `{"status":"ok","database":"ok"}`（重启前后各一次） |
| 2 | 公网可访问 | ✅ | `curl -I` → HTTP/2 200 + `cf-ray`；桌面/手机截图全部走公网 URL |
| 3 | 三档案建立、记录互不串号 | ✅ | §3.3 B1–B8（UI 隔离 + 令牌伪造读写 + 非法令牌 401） |
| 4 | 手机与电脑登录同一档案，一端标记学习另一端可见 | ✅ | §3.2 A7/A8（手机看到桌面端记录并反向写入）；§3.4 C4/C8（两台「设备」双向可见） |
| 5 | 停止 API 后仍能记录，恢复后同步 | ✅（替代法） | §3.5 D1–D4：用 CDP 网络离线模拟代替真的 `bootout` 停服（停服会触发 KeepAlive 自动拉起，且沙箱风险高）；离线续记 + 自动补传均已证实 |
| 6 | 重启应用服务后网页、数据库与既有记录仍正常 | ✅ | §3.6 真实 `launchctl kickstart -k`：0.5s 恢复、pid 变更、指纹完全一致；另有独立实例两轮重启复核 |
| 7 | LaunchAgent 与 Cloudflare Tunnel 处于运行状态 | ✅ | `launchctl print` site = running/runs=3；backup = loaded（03:15 日历任务）；公网 200 + `cf-ray`；`lsof` 证明只监听 `127.0.0.1:18880` |

## 7. 改动文件与提交

改动文件（全部在仓库内，未提交任何数据库/备份/PIN/令牌）：

| 文件 | 改动 |
| --- | --- |
| `sabrina_backend/backup.py` | 关闭连接、成品备份自包含（合并 WAL）、清理 sidecar 残留 |
| `tests/test_admin_backup.py` | 新增 3 条测试（sidecar 残留、只读自包含、runbook 恢复顺序行为） |
| `OPERATIONS.md` | 备份目录应只有 `sabrina-*.db` 的说明 |
| `ACCEPTANCE-REPORT-2026-10-16.md` | 本报告 |
| `.superpowers/sdd/2026-10-15-mac-mini-sqlite-sync/progress.md` | Task 6 收尾状态（一行；本地 SDD 台账，被 `.gitignore` 忽略，不入提交） |

提交（本地，未 push）：

```
f44b813  fix: keep finished backups self-contained   ← 本次唯一的代码修复
7ef6c06  docs: add Task 6 acceptance report          ← 本报告首次提交
```

（其后还有一次纯文档微调，只回填了上面两个哈希与提交计数，`git log --oneline -3` 可见。）

`main` 现领先 `origin/main` **15 个 commit**（其中 12 个来自任务 1–5 与部署后修复，3 个来自本次收尾）。**没有 push、没有 force、没有改历史。**

## 8. 未完成项 / 待 Alex 处理（含命令）

### 8.1 清掉 `backups/` 里的旧残留（本次沙箱无写家目录权限）

```
ls -la "$HOME/Library/Application Support/SabrinaEnglish/backups/"   # 先确认 -wal 都是 0 字节
B="$HOME/Library/Application Support/SabrinaEnglish/backups"
rm -f "$B/.sabrina-20261015T164034Z.db.tmp-shm" "$B/.sabrina-20261015T164034Z.db.tmp-wal" \
      "$B/sabrina-20261015T164034Z.db-shm" "$B/sabrina-20261015T164034Z.db-wal"
```

修复后的备份例程不会再产生这类文件（§4.1 已实测两轮）；`sabrina-20261015T164034Z.db` 本身不要删（那是第一份 baseline 备份）。

### 8.2 确认首次*定时*备份（今晚 03:15）

```
launchctl print "gui/$(id -u)/ai.sabrina-english.backup" | grep -E "state|runs|last exit code"
ls -A "$HOME/Library/Application Support/SabrinaEnglish/backups/"     # 应出现新的 sabrina-*.db，且没有任何 -wal/-shm/.tmp
tail -5 "$HOME/Library/Application Support/SabrinaEnglish/backup.log" "$HOME/Library/Application Support/SabrinaEnglish/backup.err.log"
```

LaunchAgent 的 `WorkingDirectory` 就是本仓库，所以修复对它**自动生效，无需重装**。

### 8.3 可选：真正的「停 API → 离线记录 → 起 API → 补传」

本次用 CDP 离线模拟覆盖（§3.5）。若想按字面复现：

```
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/ai.sabrina-english.site.plist"
# 在已打开的浏览器里标记一条学习 → 应显示离线/同步失败，记录仍在本机
./deploy/install.sh          # 重新 bootstrap 服务
```
（注意：`bootout` 期间网站对外不可用；`KeepAlive` 不会在 bootout 状态下拉起，必须靠 `install.sh` 重新加载。）

## 9. 剩余风险与观察

1. **Cloudflare 会拦非浏览器客户端**：脚本用 python-urllib 直接 POST `/api/auth/login` 会得到 `403 error code: 1010`（UA 指纹），换成 Chrome/浏览器 UA 或走回环则正常。不是应用缺陷，但以后写脚本化检查和监控要注意（健康检查走 GET 不受影响）。
2. **验收数据是真实数据**：本次为验证功能，在三个档案里留下了真实点击产生的学习记录（Owner 5 条 + 1 收藏，Sabrina 3 条，Max 3 条，都是今天 Mode A 的单词；`state_version` 分别 21 / 3 / 3）。想清空：各自登录后点「清空」，或用「导入」空备份；不清也不影响使用。
3. **登录限流是内存级**（每 IP+用户名 5 次/10 分钟，重启清零）——按 spec 的取舍，可接受。
4. **备份在异地/Time Machine 之外**：spec 已声明本地备份不替代异地备份；Mac mini 若没开 Time Machine，建议把数据目录纳入。
5. **`.firecrawl/` 等仓库内既有未跟踪目录**未动；`sabrina-site.err.log`（215 KB，仓库内）是历史文件，本次未清理。
6. 本次所有脚本、日志、截图都在 `/tmp/sabrina-acceptance/`（重启会被系统清理，需要留存请自行复制）。PIN 文件 `pins.txt` 也在那里，读完可删。

## 10. 证据清单（截图）

| 场景 | 截图 |
| --- | --- |
| A 桌面登录/标记/收藏/复习 | `shots/a-desktop-01-logged-in.png` … `a-desktop-05-final.png` |
| A 手机视口登录/同步/标记 | `shots/a-mobile-01-login.png`、`a-mobile-02-synced.png`、`a-mobile-03-learned.png` |
| B 三档案隔离 | `shots/b-01-login-dialog.png` … `b-06-max-learned.png` |
| C 双端同步与 409 合并 | `shots/c-01-deviceA-cleared.png` … `c-05-deviceB-merged.png` |
| D 离线与恢复 | `shots/d-01-offline-banner.png` … `d-04-after-reload.png` |
| 同步状态横幅（页面底部档案栏） | `shots/e-01-sync-state-online.png`、`e-02-sync-state-offline.png` |

---

*报告由收尾会话（dsh）自动生成；全程未打印任何 PIN 明文，未 push，未改动本仓库以外的东西。*
