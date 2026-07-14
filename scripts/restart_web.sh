#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="${ROOT_DIR}/web"
RUNTIME_BASE="${XDG_RUNTIME_DIR:-/tmp}"
RUN_DIR="${TSGO_RUN_DIR:-${RUNTIME_BASE}/tsgo-web-${USER:-$(id -u)}}"
LOG_DIR="${TSGO_LOG_DIR:-${RUN_DIR}/logs}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
STARTUP_TIMEOUT="${STARTUP_TIMEOUT:-30}"
UVICORN_RELOAD="${UVICORN_RELOAD:-0}"
NPM_INSTALL="${NPM_INSTALL:-auto}"
SKIP_BUILD="${SKIP_BUILD:-0}"

BACKEND_PID_FILE="${RUN_DIR}/backend.pid"
FRONTEND_PID_FILE="${RUN_DIR}/frontend.pid"
BACKEND_LOG="${LOG_DIR}/backend.log"
FRONTEND_LOG="${LOG_DIR}/frontend.log"

mkdir -p "${RUN_DIR}" "${LOG_DIR}"

ts() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  printf '[%s] %s\n' "$(ts)" "$*"
}

fail() {
  log "ERROR: $*"
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "缺少命令：$1"
}

read_pid() {
  local pid_file="$1"
  [[ -f "${pid_file}" ]] || return 1
  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  [[ "${pid}" =~ ^[0-9]+$ ]] || return 1
  printf '%s\n' "${pid}"
}

stop_pid_file() {
  local name="$1"
  local pid_file="$2"
  local pid=""

  if pid="$(read_pid "${pid_file}")" && kill -0 "${pid}" 2>/dev/null; then
    log "停止 ${name}，PID=${pid}"
    kill "${pid}" 2>/dev/null || true
    for _ in {1..30}; do
      kill -0 "${pid}" 2>/dev/null || break
      sleep 0.2
    done
    if kill -0 "${pid}" 2>/dev/null; then
      log "${name} 未及时退出，发送 SIGKILL，PID=${pid}"
      kill -9 "${pid}" 2>/dev/null || true
    fi
  fi
  rm -f "${pid_file}"
}

kill_port_listener() {
  local name="$1"
  local port="$2"
  local pids=""

  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  elif command -v fuser >/dev/null 2>&1; then
    pids="$(fuser -n tcp "${port}" 2>/dev/null || true)"
  fi

  [[ -n "${pids//[[:space:]]/}" ]] || return 0
  log "清理占用 ${port} 端口的 ${name} 进程：${pids//$'\n'/ }"
  for pid in ${pids}; do
    [[ "${pid}" == "$$" ]] && continue
    kill "${pid}" 2>/dev/null || true
  done
  sleep 0.5
  for pid in ${pids}; do
    [[ "${pid}" == "$$" ]] && continue
    kill -0 "${pid}" 2>/dev/null && kill -9 "${pid}" 2>/dev/null || true
  done
}

stop_services() {
  stop_pid_file "前端" "${FRONTEND_PID_FILE}"
  stop_pid_file "后端" "${BACKEND_PID_FILE}"
  kill_port_listener "前端" "${FRONTEND_PORT}"
  kill_port_listener "后端" "${BACKEND_PORT}"
}

install_frontend_dependencies() {
  local should_install=0
  case "${NPM_INSTALL}" in
    1|true|yes) should_install=1 ;;
    0|false|no) should_install=0 ;;
    auto) [[ -d "${WEB_DIR}/node_modules" ]] || should_install=1 ;;
    *) fail "NPM_INSTALL 只能是 auto、1 或 0，当前值：${NPM_INSTALL}" ;;
  esac

  if (( should_install == 1 )); then
    log "安装前端依赖"
    if [[ -f "${WEB_DIR}/package-lock.json" ]]; then
      (cd "${WEB_DIR}" && npm ci)
    else
      (cd "${WEB_DIR}" && npm install)
    fi
  fi
}

build_frontend() {
  if [[ "${SKIP_BUILD}" == "1" ]]; then
    log "SKIP_BUILD=1，跳过前端构建"
    return 0
  fi
  install_frontend_dependencies
  log "构建前端"
  (cd "${WEB_DIR}" && npm run build)
}

start_backend() {
  local reload_args=()
  if [[ "${UVICORN_RELOAD}" == "1" ]]; then
    reload_args+=(--reload)
  fi

  : > "${BACKEND_LOG}"
  log "启动后端：http://127.0.0.1:${BACKEND_PORT}"
  (
    cd "${ROOT_DIR}"
    export PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
    nohup "${PYTHON_BIN}" -m uvicorn tsgo.web.app:app \
      --host "${BACKEND_HOST}" \
      --port "${BACKEND_PORT}" \
      "${reload_args[@]}" \
      >>"${BACKEND_LOG}" 2>&1 </dev/null &
    echo $! > "${BACKEND_PID_FILE}"
  )
}

start_frontend() {
  : > "${FRONTEND_LOG}"
  log "启动前端：http://127.0.0.1:${FRONTEND_PORT}"
  (
    cd "${WEB_DIR}"
    nohup npm run dev -- \
      --host "${FRONTEND_HOST}" \
      --port "${FRONTEND_PORT}" \
      >>"${FRONTEND_LOG}" 2>&1 </dev/null &
    echo $! > "${FRONTEND_PID_FILE}"
  )
}

wait_for_port() {
  local name="$1"
  local host="$2"
  local port="$3"
  local deadline=$((SECONDS + STARTUP_TIMEOUT))

  while (( SECONDS < deadline )); do
    if (echo > "/dev/tcp/${host}/${port}") >/dev/null 2>&1; then
      log "${name} 已就绪：${host}:${port}"
      return 0
    fi
    sleep 0.5
  done

  log "${name} 在 ${STARTUP_TIMEOUT}s 内未监听 ${host}:${port}"
  return 1
}

show_status() {
  local name pid_file port pid status
  for entry in "后端|${BACKEND_PID_FILE}|${BACKEND_PORT}" "前端|${FRONTEND_PID_FILE}|${FRONTEND_PORT}"; do
    IFS='|' read -r name pid_file port <<<"${entry}"
    pid="$(read_pid "${pid_file}" 2>/dev/null || true)"
    status="stopped"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      status="running"
    fi
    printf '%-6s status=%-7s pid=%-8s port=%s\n' "${name}" "${status}" "${pid:-none}" "${port}"
  done
  printf 'backend log:  %s\n' "${BACKEND_LOG}"
  printf 'frontend log: %s\n' "${FRONTEND_LOG}"
}

show_failure_logs() {
  printf '\n===== backend.log =====\n'
  tail -n 80 "${BACKEND_LOG}" 2>/dev/null || true
  printf '\n===== frontend.log =====\n'
  tail -n 80 "${FRONTEND_LOG}" 2>/dev/null || true
}

restart_services() {
  require_command "${PYTHON_BIN}"
  require_command npm
  [[ -d "${WEB_DIR}" ]] || fail "前端目录不存在：${WEB_DIR}"

  build_frontend
  stop_services
  start_backend
  start_frontend

  if ! wait_for_port "后端" 127.0.0.1 "${BACKEND_PORT}"; then
    show_failure_logs
    exit 1
  fi
  if ! wait_for_port "前端" 127.0.0.1 "${FRONTEND_PORT}"; then
    show_failure_logs
    exit 1
  fi

  log "重启完成"
  show_status
}

usage() {
  cat <<'USAGE'
用法：
  bash scripts/restart_web.sh [restart|stop|status|logs]

默认执行 restart：
  1. 必要时安装前端依赖
  2. npm run build
  3. 停止旧 Uvicorn/Vite 进程
  4. 启动后端和前端
  5. 检查 8000/5173 端口

可选环境变量：
  PYTHON_BIN=python3
  BACKEND_HOST=0.0.0.0
  BACKEND_PORT=8000
  FRONTEND_HOST=0.0.0.0
  FRONTEND_PORT=5173
  UVICORN_RELOAD=0
  NPM_INSTALL=auto   # auto/1/0
  SKIP_BUILD=0
  STARTUP_TIMEOUT=30
USAGE
}

main() {
  local action="${1:-restart}"
  case "${action}" in
    restart) restart_services ;;
    stop) stop_services; show_status ;;
    status) show_status ;;
    logs)
      touch "${BACKEND_LOG}" "${FRONTEND_LOG}"
      tail -n 100 -f "${BACKEND_LOG}" "${FRONTEND_LOG}"
      ;;
    -h|--help|help) usage ;;
    *) usage; fail "未知动作：${action}" ;;
  esac
}

main "$@"
