#!/bin/sh
set -eu

LAUNCH_AGENTS_DIR=${SABRINA_LAUNCH_AGENTS_DIR:-"$HOME/Library/LaunchAgents"}
SERVICE_PLIST="$LAUNCH_AGENTS_DIR/ai.sabrina-english.site.plist"
BACKUP_PLIST="$LAUNCH_AGENTS_DIR/ai.sabrina-english.backup.plist"
DOMAIN_TARGET="gui/$(id -u)"

if [ "${SABRINA_SKIP_LAUNCHCTL:-0}" != "1" ]; then
  launchctl bootout "$DOMAIN_TARGET" "$SERVICE_PLIST" 2>/dev/null || true
  launchctl bootout "$DOMAIN_TARGET" "$BACKUP_PLIST" 2>/dev/null || true
fi

rm -f "$SERVICE_PLIST" "$BACKUP_PLIST"
echo "LaunchAgent 已卸载。数据库和备份未删除。"
