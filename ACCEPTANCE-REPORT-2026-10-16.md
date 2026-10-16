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

内容版本：`2026.10.16-1`。`python3 scripts/validate_content.py content` 输出 `content library: ok`。

## 自动化验证

- `python3 -m unittest discover -v`：58 项测试全部通过。
- 覆盖内容 schema、数量、唯一 ID、manifest SHA-256、静态文件白名单、ETag、选择器、旧历史兼容、同模式下一组、登录同步、备份和部署契约。
- `git diff --check`：通过。

## 部署与 HTTP 验证

- `./deploy/install.sh`：成功；没有覆盖数据库。
- 本机健康检查：`http://127.0.0.1:18880/api/health` 返回数据库正常。
- 公网健康检查：`https://sabrina.redflyingpig.com/api/health` 返回数据库正常。
- 公网、本机和仓库的 `content/manifest.json` SHA-256 一致：`bbc127718202eb93b1be1f98b54dfb902725be9511d51de80c39c566c177a66a`。
- 本机返回的 A1 分片与仓库 SHA-256 一致：`a14e74326204a5a0a487df31049c7894e7084806cc2062be1c5f9c971fcf3ddb`。
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

截图：

- `/tmp/sabrina-acceptance/shots/large-library-desktop.png`
- `/tmp/sabrina-acceptance/shots/large-library-desktop-next-batch.png`
- `/tmp/sabrina-acceptance/shots/large-library-mobile.png`

## 回滚确认

本次升级不改 SQLite schema。上一版可直接重新安装并继续读取现有数据；新增的 `contentId` 字段会被旧版安全忽略。回滚时必须让 `index.html`、`assets/content-library.js` 和整个 `content/` 来自同一提交，避免 manifest 与分片哈希不一致。

## 已知边界

ECDICT 的 A1–B2 分组是按频率和可用性生成的学习顺序，不是官方 CEFR 认证。词库适合个人日常学习和降低重复率；若未来要做考试级精确分级，应另引入有明确授权的 CEFR 标注数据源。
