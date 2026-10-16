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

## 回滚确认

本次升级不改 SQLite schema。上一版可直接重新安装并继续读取现有数据；新增的 `contentId` 字段会被旧版安全忽略。回滚时必须让 `index.html`、`assets/content-library.js` 和整个 `content/` 来自同一提交，避免 manifest 与分片哈希不一致。

## 已知边界

ECDICT 的 A1–B2 分组是按频率和可用性生成的学习顺序，不是官方 CEFR 认证。词库适合个人日常学习和降低重复率；若未来要做考试级精确分级，应另引入有明确授权的 CEFR 标注数据源。
