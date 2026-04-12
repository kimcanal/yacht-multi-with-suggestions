#!/usr/bin/env bash
set -euo pipefail

APP_UNIT="yacht-web.service"
TUNNEL_UNIT="cloudflared-yacht.service"
LOCAL_HEALTH_URL="http://127.0.0.1:8000/health"
PUBLIC_HEALTH_URL="https://app.yatch-game.cloud/health"

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

show_status() {
  echo
  echo "[service]"
  echo "  app       : $(service_state "$APP_UNIT")"
  echo "  tunnel    : $(service_state "$TUNNEL_UNIT")"
  echo "  autostart : app=$(service_enabled "$APP_UNIT"), tunnel=$(service_enabled "$TUNNEL_UNIT")"

  echo
  echo "[health]"
  if curl -fsS --max-time 3 "$LOCAL_HEALTH_URL" >/dev/null 2>&1; then
    echo "  local     : ok ($LOCAL_HEALTH_URL)"
  else
    echo "  local     : down ($LOCAL_HEALTH_URL)"
  fi
  if curl -fsS --max-time 5 "$PUBLIC_HEALTH_URL" >/dev/null 2>&1; then
    echo "  public    : ok ($PUBLIC_HEALTH_URL)"
  else
    echo "  public    : down ($PUBLIC_HEALTH_URL)"
  fi
  echo
}

start_hosting() {
  echo "Starting app service..."
  systemctl --user start "$APP_UNIT"
  if ! wait_for_url "$LOCAL_HEALTH_URL" 25 1; then
    echo "로컬 앱이 8000 포트에서 올라오지 않았습니다."
    show_status
    exit 1
  fi

  echo "Starting Cloudflare tunnel..."
  systemctl --user start "$TUNNEL_UNIT"
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
  echo "Restarting app service..."
  systemctl --user restart "$APP_UNIT"
  if ! wait_for_url "$LOCAL_HEALTH_URL" 25 1; then
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
1) 호스팅 켜기
2) 호스팅 끄기
3) 호스팅 재시작
4) 상태 확인
5) 로그인 시 자동 시작 켜기
6) 로그인 시 자동 시작 끄기
0) 종료

EOF
}

run_choice() {
  case "${1:-}" in
    1|start) start_hosting ;;
    2|stop) stop_hosting ;;
    3|restart) restart_hosting ;;
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
    run_choice "$1"
    exit 0
  fi

  while true; do
    show_menu
    read -r -p "번호 입력: " choice
    run_choice "$choice"
  done
}

main "$@"
