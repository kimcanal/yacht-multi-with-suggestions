#!/usr/bin/env bash
set -euo pipefail

APP_UNIT="yacht-web.service"
TUNNEL_UNIT="cloudflared-yacht.service"
APP_SERVICE_FILE="${HOME}/.config/systemd/user/${APP_UNIT}"
TUNNEL_CONFIG_FILE="${HOME}/.cloudflared/config.yml"
PUBLIC_HEALTH_URL="https://app.yatch-game.cloud/health"
DEFAULT_PORT="8000"
PORT_CHANGED=0

need_user_systemd() {
  if ! systemctl --user show-environment >/dev/null 2>&1; then
    echo "user systemd 세션을 찾지 못했습니다. VDI 로그인 세션에서 다시 실행해 주세요."
    exit 1
  fi
}

service_state() {
  local unit="$1"
  systemctl --user is-active "$unit" 2>/dev/null || true
}

service_enabled() {
  local unit="$1"
  systemctl --user is-enabled "$unit" 2>/dev/null || true
}

configured_port() {
  local port=""

  if [[ -f "$APP_SERVICE_FILE" ]]; then
    port="$(sed -n 's/^Environment=YACHT_PORT=\([0-9][0-9]*\)$/\1/p' "$APP_SERVICE_FILE" | head -n 1)"
    if [[ -z "$port" ]]; then
      port="$(sed -n 's/.*--bind 0\.0\.0\.0:\([0-9][0-9]*\).*/\1/p' "$APP_SERVICE_FILE" | head -n 1)"
    fi
  fi

  if [[ -z "$port" && -f "$TUNNEL_CONFIG_FILE" ]]; then
    port="$(sed -n 's#^[[:space:]]*service:[[:space:]]*http://\(localhost\|127\.0\.0\.1\):\([0-9][0-9]*\)$#\2#p' "$TUNNEL_CONFIG_FILE" | head -n 1)"
  fi

  echo "${port:-$DEFAULT_PORT}"
}

local_health_url() {
  local port="${1:-$(configured_port)}"
  echo "http://127.0.0.1:${port}/health"
}

wait_for_url() {
  local url="$1"
  local tries="${2:-20}"
  local delay="${3:-1}"
  local i
  for ((i=1; i<=tries; i++)); do
    if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

validate_port() {
  local port="${1:-}"
  [[ "$port" =~ ^[0-9]+$ ]] || return 1
  (( port >= 1 && port <= 65535 ))
}

prompt_for_port() {
  local default_port="$1"
  local input=""

  while true; do
    read -r -p "포트 번호 입력 [${default_port}]: " input
    input="${input:-$default_port}"
    if validate_port "$input"; then
      echo "$input"
      return 0
    fi
    echo "1~65535 사이 숫자를 입력해 주세요."
  done
}

resolve_port() {
  local requested="${1:-}"
  local current_port
  current_port="$(configured_port)"

  if [[ -n "$requested" ]]; then
    if ! validate_port "$requested"; then
      echo "잘못된 포트 번호입니다: $requested" >&2
      exit 1
    fi
    echo "$requested"
    return 0
  fi

  if [[ -t 0 ]]; then
    prompt_for_port "$current_port"
    return 0
  fi

  echo "$current_port"
}

update_app_service_port() {
  local port="$1"

  if [[ ! -f "$APP_SERVICE_FILE" ]]; then
    echo "앱 서비스 파일을 찾지 못했습니다: $APP_SERVICE_FILE" >&2
    exit 1
  fi

  sed -i -E \
    -e "s/^Environment=YACHT_PORT=.*/Environment=YACHT_PORT=${port}/" \
    -e "s/--bind 0\\.0\\.0\\.0:[0-9]+/--bind 0.0.0.0:${port}/" \
    "$APP_SERVICE_FILE"

  if ! grep -q "^Environment=YACHT_PORT=${port}$" "$APP_SERVICE_FILE"; then
    echo "앱 서비스의 YACHT_PORT 값을 ${port}로 바꾸지 못했습니다." >&2
    exit 1
  fi
  if ! grep -q -- "--bind 0.0.0.0:${port}" "$APP_SERVICE_FILE"; then
    echo "앱 서비스의 bind 포트를 ${port}로 바꾸지 못했습니다." >&2
    exit 1
  fi
}

update_tunnel_port() {
  local port="$1"

  if [[ ! -f "$TUNNEL_CONFIG_FILE" ]]; then
    echo "Cloudflare 설정 파일을 찾지 못했습니다: $TUNNEL_CONFIG_FILE" >&2
    exit 1
  fi

  sed -i -E \
    "s#^([[:space:]]*service:[[:space:]]*http://)(localhost|127\\.0\\.0\\.1):[0-9]+\$#\\1localhost:${port}#" \
    "$TUNNEL_CONFIG_FILE"

  if ! grep -Eq "^[[:space:]]*service:[[:space:]]*http://localhost:${port}$" "$TUNNEL_CONFIG_FILE"; then
    echo "Cloudflare 터널 포트를 ${port}로 바꾸지 못했습니다." >&2
    exit 1
  fi
}

configure_port() {
  local requested_port="$1"
  local current_port
  current_port="$(configured_port)"
  PORT_CHANGED=0

  if [[ "$requested_port" == "$current_port" ]]; then
    return 0
  fi

  echo "포트를 ${current_port}에서 ${requested_port}로 변경합니다."
  update_app_service_port "$requested_port"
  update_tunnel_port "$requested_port"
  systemctl --user daemon-reload
  PORT_CHANGED=1
}

show_status() {
  local port
  local local_url
  port="$(configured_port)"
  local_url="$(local_health_url "$port")"

  echo
  echo "[service]"
  echo "  app       : $(service_state "$APP_UNIT")"
  echo "  tunnel    : $(service_state "$TUNNEL_UNIT")"
  echo "  autostart : app=$(service_enabled "$APP_UNIT"), tunnel=$(service_enabled "$TUNNEL_UNIT")"
  echo "  port      : $port"

  echo
  echo "[health]"
  if curl -fsS --max-time 3 "$local_url" >/dev/null 2>&1; then
    echo "  local     : ok ($local_url)"
  else
    echo "  local     : down ($local_url)"
  fi
  if curl -fsS --max-time 5 "$PUBLIC_HEALTH_URL" >/dev/null 2>&1; then
    echo "  public    : ok ($PUBLIC_HEALTH_URL)"
  else
    echo "  public    : down ($PUBLIC_HEALTH_URL)"
  fi
  echo
}

start_app_service() {
  local port="$1"

  if (( PORT_CHANGED )) && [[ "$(service_state "$APP_UNIT")" == "active" ]]; then
    echo "Restarting app service on port ${port}..."
    systemctl --user restart "$APP_UNIT"
    return 0
  fi

  echo "Starting app service on port ${port}..."
  systemctl --user start "$APP_UNIT"
}

start_tunnel_service() {
  if (( PORT_CHANGED )) && [[ "$(service_state "$TUNNEL_UNIT")" == "active" ]]; then
    echo "Restarting Cloudflare tunnel..."
    systemctl --user restart "$TUNNEL_UNIT"
    return 0
  fi

  echo "Starting Cloudflare tunnel..."
  systemctl --user start "$TUNNEL_UNIT"
}

start_hosting() {
  local port
  local local_url
  port="$(resolve_port "${1:-}")"
  configure_port "$port"
  local_url="$(local_health_url "$port")"

  start_app_service "$port"
  if ! wait_for_url "$local_url" 25 1; then
    echo "로컬 앱이 ${port} 포트에서 올라오지 않았습니다."
    show_status
    exit 1
  fi

  start_tunnel_service
  if ! wait_for_url "$PUBLIC_HEALTH_URL" 25 1; then
    echo "공개 도메인 연결이 아직 준비되지 않았습니다."
    show_status
    exit 1
  fi

  echo "호스팅이 켜졌습니다."
  show_status
}

stop_hosting() {
  echo "Stopping Cloudflare tunnel..."
  systemctl --user stop "$TUNNEL_UNIT" || true
  echo "Stopping app service..."
  systemctl --user stop "$APP_UNIT" || true
  echo "호스팅을 껐습니다."
  show_status
}

restart_hosting() {
  local port
  local local_url
  port="$(resolve_port "${1:-}")"
  configure_port "$port"
  local_url="$(local_health_url "$port")"

  echo "Restarting app service on port ${port}..."
  systemctl --user restart "$APP_UNIT"
  if ! wait_for_url "$local_url" 25 1; then
    echo "로컬 앱 재시작 확인에 실패했습니다."
    show_status
    exit 1
  fi

  echo "Restarting Cloudflare tunnel..."
  systemctl --user restart "$TUNNEL_UNIT"
  if ! wait_for_url "$PUBLIC_HEALTH_URL" 25 1; then
    echo "공개 도메인 재연결 확인에 실패했습니다."
    show_status
    exit 1
  fi

  echo "호스팅을 재시작했습니다."
  show_status
}

enable_autostart() {
  systemctl --user enable "$APP_UNIT" "$TUNNEL_UNIT"
  echo "로그인 시 자동 시작을 켰습니다."
  show_status
}

disable_autostart() {
  systemctl --user disable "$APP_UNIT" "$TUNNEL_UNIT"
  echo "로그인 시 자동 시작을 껐습니다."
  show_status
}

show_menu() {
  cat <<'EOF'

=== Yacht Hosting Control ===
1) 호스팅 켜기 (포트 입력)
2) 호스팅 끄기
3) 호스팅 재시작 (포트 입력)
4) 상태 확인
5) 로그인 시 자동 시작 켜기
6) 로그인 시 자동 시작 끄기
0) 종료

EOF
}

run_choice() {
  case "${1:-}" in
    1|start) start_hosting "${2:-}" ;;
    2|stop) stop_hosting ;;
    3|restart) restart_hosting "${2:-}" ;;
    4|status) show_status ;;
    5|enable) enable_autostart ;;
    6|disable) disable_autostart ;;
    0|q|quit|exit) exit 0 ;;
    *) echo "알 수 없는 선택입니다: ${1:-}" ; exit 1 ;;
  esac
}

main() {
  need_user_systemd

  if [[ $# -gt 0 ]]; then
    run_choice "$@"
    exit 0
  fi

  while true; do
    show_menu
    read -r -p "번호 입력: " choice
    run_choice "$choice"
  done
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
