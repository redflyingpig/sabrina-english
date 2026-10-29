# Sabrina English 运维手册

## 安装与升级

在项目目录运行 `./deploy/install.sh`。脚本会安装网站服务和每日备份两个 macOS LaunchAgent；重复执行就是升级，不会覆盖数据库。

课程内容是仓库内 `content/` 的版本化静态 JSON。升级前可运行：

```sh
python3 scripts/validate_content.py content
python3 -m unittest discover -v
```

服务启动时从 `content/manifest.json` 建立公开文件白名单；新增或替换内容后必须重启服务。浏览器会校验每个分片的 SHA-256，校验失败时保留本机学习记录并显示重试入口。

## 廣東話课程内容

廣東話分页的程序在 `assets/cantonese/`（进 git）；课程内容取自 ERB 教材，有版权，不进 git，只放在数据目录：

```sh
install -m 600 course.json "$HOME/Library/Application Support/SabrinaEnglish/cantonese/course.json"
```

`course.json` 由 MacBook 上的 `~/projects/sabrina-cantonese` 运行 `python3 build/build.py` 生成。它只经 `/api/cantonese/course` 提供给已登录档案，替换后不必重启服务。学习进度存在档案的 `cantonese` 字段，随档案同步和备份。

## 账号与档案（Cloudflare Access + 邮箱验证码）

登录不再由网站自己做，而是交给 Cloudflare Access：打开 https://sabrina.redflyingpig.com/ → 输入邮箱 → 收取一次性验证码 → 进入。**没有白名单**，任何有效邮箱都能验证；会话 30 天，同一浏览器一个月内不需要重复验证。

- Access 应用名 `sabrina-english`，One-time PIN IdP，策略 `allow` + `include: everyone`，`session_duration=720h`，`auto_redirect_to_identity=true`。
- 隧道配置不需要改：`sabrina.redflyingpig.com -> http://127.0.0.1:18880` 已存在；Access 在边缘拦截，origin 仍然只听 `127.0.0.1`。
- 边缘验证通过后会把邮箱放在 `Cf-Access-Authenticated-User-Email` 头里透传给 origin。origin 只监听本机，所以伪造该头只能来自本机进程。

**身份模型**：邮箱 = 账号；一个账号可以拥有多个学习档案（共用 iPad 时在一个浏览器里选 Sabrina / Max / Alex，不需要重新收验证码）。用户名只是显示名，**只在首次建立档案时输入一次**，之后靠邮箱自动识别——因此不会再出现「打错名字就多出一个空档案」的问题。显示名仍然全局唯一，重名返回 `409 name_taken`。

**当前绑定**：

| 档案 | 邮箱 |
| --- | --- |
| Alex | `alex.yacao.wang@gmail.com` |
| Sabrina | `liangmanyi33@gmail.com` |
| Max | `alex.yacao.wang@gmail.com`（暂挂在 Alex 账号下共用设备；拿到 Max 自己的邮箱后可改绑） |

**运维命令**：

```sh
export SABRINA_DATA_DIR="$HOME/Library/Application Support/SabrinaEnglish"
python3 -m sabrina_backend.admin list-profiles
python3 -m sabrina_backend.admin bind-email <档案名> <邮箱>     # 把已有档案绑定到已验证邮箱
python3 -m sabrina_backend.admin rename <旧名> <新名>            # 改名（同时改唯一键）
python3 -m sabrina_backend.admin init-profiles
```

**本地开发**：设置 `SABRINA_DEV_EMAIL=you@example.com` 可模拟已验证身份（`GET /api/whoami` 会返回该邮箱名下的档案）。⚠️ **不要在生产 LaunchAgent 里设置这个变量**，否则所有请求都会被当成同一个邮箱。

**回退**：删除 Cloudflare Access 应用即可恢复公开访问；此时网站会退回旧的「输入用户名」登录（`POST /api/auth/login {username}` 仍然保留）。

## 健康检查

```sh
curl --fail http://127.0.0.1:18880/api/health
curl --fail https://sabrina.redflyingpig.com/api/health
```

## 日志

日志位于 `~/Library/Application Support/SabrinaEnglish/`：应用轮转日志 `sabrina.log`，以及 `service.log`、`service.err.log`、`backup.log` 和 `backup.err.log`。

## 备份

每天 03:15 自动备份并保留最近 30 份。手动备份：

```sh
SABRINA_DATA_DIR="$HOME/Library/Application Support/SabrinaEnglish" /usr/bin/python3 -m sabrina_backend.backup --keep 30
```

备份在 `~/Library/Application Support/SabrinaEnglish/backups/`。

每个备份都是一个自包含的 `sabrina-*.db` 文件：脚本结束前会关闭自己的连接、把 WAL 合并进备份文件并清理 sidecar，因此目录里不应出现 `.sabrina-*.tmp`、`*-shm` 或 `*-wal`。旧版本可能留下过这类残留文件，确认没有备份任务在运行后可以直接删除；保留策略只统计 `sabrina-*.db`，残留文件不影响备份数量。

## 恢复

先停止网站和备份任务，用 SQLite backup API 保存当前完整快照，再把主库及 WAL sidecar 一起隔离。不要直接覆盖正在使用的 `sabrina.db`，否则旧 WAL 可能被重放，出现“检查为 ok，但恢复的是旧数据”的假成功。

```sh
RESTORE_SOURCE="/path/to/backup.db"
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/ai.sabrina-english.site.plist"
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/ai.sabrina-english.backup.plist"
cp "$RESTORE_SOURCE" "$HOME/Library/Application Support/SabrinaEnglish/restore-staging.db"
sqlite3 "$HOME/Library/Application Support/SabrinaEnglish/restore-staging.db" 'PRAGMA integrity_check;'
SABRINA_DATA_DIR="$HOME/Library/Application Support/SabrinaEnglish" /usr/bin/python3 -m sabrina_backend.backup --keep 30
mkdir -p "$HOME/Library/Application Support/SabrinaEnglish/pre-restore"
mv "$HOME/Library/Application Support/SabrinaEnglish/sabrina.db"* "$HOME/Library/Application Support/SabrinaEnglish/pre-restore/"
mv "$HOME/Library/Application Support/SabrinaEnglish/restore-staging.db" "$HOME/Library/Application Support/SabrinaEnglish/sabrina.db"
sqlite3 "$HOME/Library/Application Support/SabrinaEnglish/sabrina.db" 'PRAGMA integrity_check;'
./deploy/install.sh
```

确认完整性检查输出 `ok`。把示例备份路径换成真实文件。

## Cloudflare Tunnel

公网路由应为 `sabrina.redflyingpig.com -> http://127.0.0.1:18880`。应用只监听 `127.0.0.1`，数据库不会暴露到公网。

## 回滚

安装脚本会把旧 plist 保存为 `.previous`。操作前先手动备份，然后把代码切回上一个可用提交并重新执行 `./deploy/install.sh`。本次内容升级没有数据库 schema 迁移，旧版本可以继续读取现有学习记录；新记录多出的 `contentId` 字段会被旧版本安全忽略。

只回滚内容时，应把 `content/`、`assets/content-library.js` 和 `index.html` 回到同一个提交，不能混搭 manifest 与分片，否则浏览器会因哈希不一致拒绝加载。

## 卸载

运行 `./deploy/uninstall.sh`。它只移除两个 LaunchAgent，不会删除数据库或备份。
