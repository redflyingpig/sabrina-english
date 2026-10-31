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

## 登录与邀请名单

网站不使用云服务登录，也不需要密码：打开 https://sabrina.redflyingpig.com/ → 输入名字 → 进入。同一台设备会记住登录（会话 90 天），下次直接进入学习空间。

规则只有三条：

1. **已有档案的名字**直接登录。
2. **新名字**只有在邀请名单里才会建立档案；不在名单里返回 `403 not_allowed`，界面提示「请让老师把名字加入名单」。
3. 名字不区分大小写、忽略多余空格（`Sabrina` / `sabrina` / `  SABRINA ` 视为同一个）。

每个名字对应一个学习档案。删除档案不会连带删除邀请名单里的名字。

**邀请名单是一个 Obsidian 笔记**（可以直接在手机或电脑的 Obsidian 里改）：

```
~/Sabrina Config/allowlist.md
```

Vault 名 `Sabrina Config`（直接放在家目录），里面只有这一个配置文件。**不要放到 iCloud Drive 或「文档」目录**：系统权限会拒绝后台服务读取（`Operation not permitted`），名单会变成空的。想同步到手机的话，可以在 Obsidian 里用同步插件或手动拷贝，而不是挪动这个文件夹。每行一个名字，`- 名字` 或裸名字都可以；`#` 开头是标题、`>` 开头是引用，都会被忽略。服务在**每次登录时重新读取**这个文件，所以改完立即生效，不需要重启。

```markdown
# 允许登录的名字

> 说明文字……

- Sabrina
- 同学的名字
```

也可以用命令维护同一份文件：

```sh
export SABRINA_DATA_DIR="$HOME/Library/Application Support/SabrinaEnglish"
python3 -m sabrina_backend.admin allow <名字>          # 写入名单
python3 -m sabrina_backend.admin unallow <名字>        # 移出名单（已建的档案不受影响）
python3 -m sabrina_backend.admin list-allowlist        # 查看当前名单与文件路径
python3 -m sabrina_backend.admin list-profiles         # 查看已有档案
```

文件名可以用环境变量 `SABRINA_ALLOWLIST` 指到别处；默认就是上面那个 vault。文件被 iCloud 收回或暂时读不到时，视为空名单——已有档案的人照样能登录，只是新名字会被拒绝。

**其他档案操作**：

```sh
python3 -m sabrina_backend.admin rename <旧名> <新名>
python3 -m sabrina_backend.admin delete-profile <档案名>   # 先备份！会连会话一起删除
```

**历史说明**：`profiles.email` 列是早期 Cloudflare Access 方案留下的，现在不再使用；Cloudflare Access 应用已删除，登录完全由本服务处理。如需重建，参考本文件历史版本。

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
