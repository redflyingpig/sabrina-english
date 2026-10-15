# Sabrina English 运维手册

## 安装与升级

在项目目录运行 `./deploy/install.sh`。脚本会安装网站服务和每日备份两个 macOS LaunchAgent；重复执行就是升级，不会覆盖数据库。

## 初始化三个档案

```sh
SABRINA_DATA_DIR="$HOME/Library/Application Support/SabrinaEnglish" /usr/bin/python3 -m sabrina_backend.admin init-profiles
```

这会创建 `Owner`、`Sabrina`、`Max`。初始 PIN 只显示一次，请立即存入密码管理器。

## 重置 PIN

```sh
SABRINA_DATA_DIR="$HOME/Library/Application Support/SabrinaEnglish" /usr/bin/python3 -m sabrina_backend.admin reset-pin Sabrina
```

末尾名字也可以换成 `Owner` 或 `Max`。

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

安装脚本会把旧 plist 保存为 `.previous`。代码回滚到上一个可用提交后重新执行 `./deploy/install.sh`；操作前先手动备份。

## 卸载

运行 `./deploy/uninstall.sh`。它只移除两个 LaunchAgent，不会删除数据库或备份。
