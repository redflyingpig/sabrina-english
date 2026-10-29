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

## 档案由用户自己建立

网站不限制档案数量，也没有预置用户名单。打开网站后在「学习用户名」里输入任意名字即可进入：

- 名字**第一次出现时自动建档**，返回 `created: true`；
- 之后输入**同一个名字**继续使用该档案，返回 `created: false`；
- 名字就是档案 ID，不是登录凭据：没有 PIN，也没有密码。

**重名规则**：`profiles.username_normalized` 上有唯一约束，比较前会去掉首尾空白、合并连续空格并转小写。因此 `Sabrina`、`sabrina`、`  SABRINA  ` 指向同一个档案，不会建出两个。名称长度限制 1–32 个字符，越界请求返回 `400 invalid_username`。

`init-profiles` 仍然可用，但只用于给 `Owner`、`Sabrina`、`Max` 预建档案，不再是进入网站的前提：

```sh
SABRINA_DATA_DIR="$HOME/Library/Application Support/SabrinaEnglish" /usr/bin/python3 -m sabrina_backend.admin init-profiles
```

数据库里的 `pin_salt` / `pin_hash` 列是历史遗留的 not null 字段；自动建档时写入一个随机、不对外透露的值，不参与任何认证流程。查看现有档案：

```sh
SABRINA_DATA_DIR="$HOME/Library/Application Support/SabrinaEnglish" /usr/bin/python3 -m sabrina_backend.admin list-profiles
```

**安全边界（已知取舍）**：既然名字只是 ID，任何知道某个同学名字的人都能进入该档案，看到并修改其学习记录。目前档案里只有学习进度，没有隐私内容；如果以后要放个人资料，需要重新引入凭据。

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
