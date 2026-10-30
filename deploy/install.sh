#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=${SABRINA_PROJECT_DIR:-$(dirname "$SCRIPT_DIR")}
DATA_DIR=${SABRINA_DATA_DIR:-"$HOME/Library/Application Support/SabrinaEnglish"}
LAUNCH_AGENTS_DIR=${SABRINA_LAUNCH_AGENTS_DIR:-"$HOME/Library/LaunchAgents"}
PYTHON_BIN=${SABRINA_PYTHON_BIN:-/usr/bin/python3}
SERVICE_PLIST="$LAUNCH_AGENTS_DIR/ai.sabrina-english.site.plist"
BACKUP_PLIST="$LAUNCH_AGENTS_DIR/ai.sabrina-english.backup.plist"
DOMAIN_TARGET="gui/$(id -u)"

mkdir -p "$DATA_DIR" "$DATA_DIR/backups" "$LAUNCH_AGENTS_DIR"
chmod 700 "$DATA_DIR" "$DATA_DIR/backups"

render_plist() {
  template=$1
  destination=$2
  if [ -f "$destination" ]; then
    cp "$destination" "$destination.previous"
  fi
  sed \
    -e "s|__PYTHON_BIN__|$PYTHON_BIN|g" \
    -e "s|__PROJECT_DIR__|$PROJECT_DIR|g" \
    -e "s|__DATA_DIR__|$DATA_DIR|g" \
    "$template" > "$destination"
  chmod 600 "$destination"
  plutil -lint "$destination" >/dev/null
}

render_plist "$SCRIPT_DIR/ai.sabrina-english.site.plist.template" "$SERVICE_PLIST"
render_plist "$SCRIPT_DIR/ai.sabrina-english.backup.plist.template" "$BACKUP_PLIST"

SABRINA_DATA_DIR="$DATA_DIR" "$PYTHON_BIN" -m sabrina_backend.admin list-profiles >/dev/null

if [ "${SABRINA_SKIP_LAUNCHCTL:-0}" = "1" ]; then
  echo "已安装配置（跳过 launchctl）。"
  exit 0
fi

launchctl bootout "$DOMAIN_TARGET" "$SERVICE_PLIST" 2>/dev/null || true
launchctl bootout "$DOMAIN_TARGET" "$BACKUP_PLIST" 2>/dev/null || true
launchctl bootstrap "$DOMAIN_TARGET" "$SERVICE_PLIST"
launchctl bootstrap "$DOMAIN_TARGET" "$BACKUP_PLIST"
launchctl kickstart -k "$DOMAIN_TARGET/ai.sabrina-english.site"

attempt=0
while [ "$attempt" -lt 20 ]; do
  if curl --fail --silent http://127.0.0.1:18880/api/health >/dev/null; then
    echo "Sabrina's Study Room 已运行：http://127.0.0.1:18880"
    exit 0
  fi
  attempt=$((attempt + 1))
  sleep 1
done

echo "服务未通过健康检查，请查看 $DATA_DIR/service.err.log" >&2
exit 1
