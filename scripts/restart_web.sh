#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="${ROOT_DIR}/web"
RUNTIME_BASE="${XDG_RUNTIME_DIR:-/tmp}"
RUN_DIR="${TSGO_RUN_DIR:-${RUNTIME_BASE}/tsgo-web-${USER:-$(id -u)}}"
LOG_DIR="${TSGO_LOG_DIR:-${RUN_DIR}/logs}"
CACHE_DIR="${TSGO_CACHE_DIR:-${RUN_DIR}/cache}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_CHECK_HOST="${BACKEND_CHECK_HOST:-127.0.0.1}"
FRONTEND_CHECK_HOST="${FRONTEND_CHECK_HOST:-127.0.0.1}"
BACKEND_HEALTH_PATH="${BACKEND_HEALTH_PATH:-/openapi.json}"
FRONTEND_HEALTH_PATH="${FRONTEND_HEALTH_PATH:-/}"
STARTUP_TIMEOUT="${STARTUP_TIMEOUT:-45}"
UVICORN_RELOAD="${UVICORN_RELOAD:-0}"
BACKEND_INSTALL="${BACKEND_INSTALL:-auto}"
BACKEND_EXTRAS="${BACKEND_EXTRAS:-web,azure,deepseek,aidc}"
BACKEND_EXTRAS_NORMALIZED="${BACKEND_EXTRAS//[[:space:]]/}"
NPM_INSTALL="${NPM_INSTALL:-auto}"
SKIP_BUILD="${SKIP_BUILD:-0}"
FORCE_KILL_PORTS="${FORCE_KILL_PORTS:-0}"

BACKEND_PID_FILE="${RUN_DIR}/backend.pid"
FRONTEND_PID_FILE="${RUN_DIR}/frontend.pid"
BACKEND_LOG="${LOG_DIR}/backend.log"
FRONTEND_LOG="${LOG_DIR}/frontend.log"
BACKEND_DEPS_STAMP="${CACHE_DIR}/backend-deps.sha256"
FRONTEND_DEPS_STAMP="${CACHE_DIR}/frontend-deps.sha256"

mkdir -p "${RUN_DIR}" "${LOG_DIR}" "${CACHE_DIR}"

BACKEND_HEALTH_URL="http://${BACKEND_CHECK_HOST}:${BACKEND_PORT}${BACKEND_HEALTH_PATH}"
FRONTEND_HEALTH_URL="http://${FRONTEND_CHECK_HOST}:${FRONTEND_PORT}${FRONTEND_HEALTH_PATH}"


ts() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  printf '[%s] %s\n' "$(ts)" "$*"
}

warn() {
  log "WARN: $*"
}

fail() {
  log "ERROR: $*"
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "缺少命令：$1"
}

is_true() {
  case "${1,,}" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

normalize_install_mode() {
  case "${1,,}" in
    auto) printf 'auto\n' ;;
    1|true|yes|on|always) printf 'always\n' ;;
    0|false|no|off|never) printf 'never\n' ;;
    *) fail "$2 只能是 auto、always/1 或 never/0，当前值：$1" ;;
  esac
}

hash_stream() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 | awk '{print $1}'
  else
    "${PYTHON_BIN}" -c 'import hashlib, sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())'
  fi
}

backend_fingerprint() {
  {
    printf 'root=%s\nextras=%s\n' "${ROOT_DIR}" "${BACKEND_EXTRAS}"
    "${PYTHON_BIN}" --version 2>&1
    "${PYTHON_BIN}" -m pip --version 2>&1
    cat "${ROOT_DIR}/pyproject.toml"
  } | hash_stream
}

frontend_fingerprint() {
  {
    printf 'root=%s\n' "${ROOT_DIR}"
    npm --version 2>&1
    if [[ -f "${WEB_DIR}/package-lock.json" ]]; then
      cat "${WEB_DIR}/package-lock.json"
    else
      cat "${WEB_DIR}/package.json"
    fi
  } | hash_stream
}

read_stamp() {
  local path="$1"
  [[ -f "${path}" ]] || return 1
  tr -d '[:space:]' < "${path}"
}

write_stamp() {
  local path="$1"
  local value="$2"
  printf '%s\n' "${value}" > "${path}"
}

backend_import_check() {
  local extras=",${BACKEND_EXTRAS_NORMALIZED},"
  local modules=(fastapi uvicorn)

  [[ "${extras}" == *",azure,"* ]] && modules+=(openai azure.identity dotenv)
  [[ "${extras}" == *",deepseek,"* ]] && modules+=(openai dotenv)
  [[ "${extras}" == *",aidc,"* ]] && modules+=(agents pydantic azure.identity dotenv)

  PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}" \
    "${PYTHON_BIN}" - "${modules[@]}" <<'PY'
import importlib
import sys

missing = []
for name in dict.fromkeys(sys.argv[1:]):
    try:
        importlib.import_module(name)
    except Exception as exc:
        missing.append(f"{name}: {exc}")

if missing:
    print("后端依赖检查失败：", file=sys.stderr)
    for item in missing:
        print(f"  - {item}", file=sys.stderr)
    raise SystemExit(1)

importlib.import_module("tsgo.web.app")
if "agents" in sys.argv[1:]:
    importlib.import_module("tsgo.aidc_progress")
PY
}

install_backend_dependencies() {
  local mode fingerprint previous should_install=0
  mode="$(normalize_install_mode "${BACKEND_INSTALL}" BACKEND_INSTALL)"
  require_command "${PYTHON_BIN}"
  "${PYTHON_BIN}" -m pip --version >/dev/null 2>&1 || fail "${PYTHON_BIN} 缺少 pip。"
  [[ -f "${ROOT_DIR}/pyproject.toml" ]] || fail "缺少 pyproject.toml：${ROOT_DIR}/pyproject.toml"

  fingerprint="$(backend_fingerprint)"
  previous="$(read_stamp "${BACKEND_DEPS_STAMP}" 2>/dev/null || true)"

  case "${mode}" in
    always) should_install=1 ;;
    never) should_install=0 ;;
    auto)
      if [[ -n "${previous}" && "${previous}" != "${fingerprint}" ]]; then
        log "pyproject/Python/extras 已变化，需要更新后端依赖"
        should_install=1
      elif ! backend_import_check >/dev/null 2>&1; then
        log "检测到缺失的后端依赖"
        should_install=1
      fi
      ;;
  esac

  if (( should_install == 1 )); then
    log "安装后端依赖：pip install -e '.[${BACKEND_EXTRAS_NORMALIZED}]'"
    (
      cd "${ROOT_DIR}"
      "${PYTHON_BIN}" -m pip install --disable-pip-version-check -e ".[${BACKEND_EXTRAS_NORMALIZED}]"
    )
  fi

  if ! backend_import_check; then
    if [[ "${mode}" == "never" ]]; then
      fail "后端依赖不完整；请运行 pip install -e '.[${BACKEND_EXTRAS_NORMALIZED}]'，或设置 BACKEND_INSTALL=auto。"
    fi
    fail "后端依赖安装后仍无法导入，请查看上方错误。"
  fi
  write_stamp "${BACKEND_DEPS_STAMP}" "${fingerprint}"
}

frontend_dependency_check() {
  [[ -d "${WEB_DIR}/node_modules" ]] || return 1
  (cd "${WEB_DIR}" && npm ls --depth=0 >/dev/null 2>&1)
}

install_frontend_dependencies() {
  local mode fingerprint previous should_install=0
  mode="$(normalize_install_mode "${NPM_INSTALL}" NPM_INSTALL)"
  [[ -f "${WEB_DIR}/package.json" ]] || fail "缺少前端 package.json：${WEB_DIR}/package.json"

  fingerprint="$(frontend_fingerprint)"
  previous="$(read_stamp "${FRONTEND_DEPS_STAMP}" 2>/dev/null || true)"

  case "${mode}" in
    always) should_install=1 ;;
    never) should_install=0 ;;
    auto)
      if [[ ! -d "${WEB_DIR}/node_modules" ]]; then
        should_install=1
      elif [[ -n "${previous}" && "${previous}" != "${fingerprint}" ]]; then
        log "package-lock/package.json 已变化，需要更新前端依赖"
        should_install=1
      elif ! frontend_dependency_check; then
        log "前端 node_modules 不完整"
        should_install=1
      fi
      ;;
  esac

  if (( should_install == 1 )); then
    log "安装前端依赖"
    if [[ -f "${WEB_DIR}/package-lock.json" ]]; then
      (cd "${WEB_DIR}" && npm ci)
    else
      (cd "${WEB_DIR}" && npm install)
    fi
  fi

  if ! frontend_dependency_check; then
    if [[ "${mode}" == "never" ]]; then
      fail "前端依赖不完整；请在 web 目录执行 npm install，或设置 NPM_INSTALL=auto。"
    fi
    fail "前端依赖安装后仍不完整。"
  fi
  write_stamp "${FRONTEND_DEPS_STAMP}" "${fingerprint}"
}

build_frontend() {
  if is_true "${SKIP_BUILD}"; then
    log "SKIP_BUILD=${SKIP_BUILD}，跳过前端 TypeScript/Vite 构建校验"
    return 0
  fi
  log "构建并校验前端"
  (cd "${WEB_DIR}" && npm run build)
}

read_pid() {
  local pid_file="$1"
  [[ -f "${pid_file}" ]] || return 1
  local pid
  pid="$(head -n 1 "${pid_file}" 2>/dev/null | tr -d '[:space:]' || true)"
  [[ "${pid}" =~ ^[0-9]+$ ]] || return 1
  printf '%s\n' "${pid}"
}

process_args() {
  ps -p "$1" -o args= 2>/dev/null || true
}

process_matches() {
  local pid="$1"
  local expected="$2"
  [[ "$(process_args "${pid}")" == *"${expected}"* ]]
}

process_cwd() {
  local pid="$1"
  if [[ -L "/proc/${pid}/cwd" ]]; then
    readlink "/proc/${pid}/cwd" 2>/dev/null || true
  elif command -v lsof >/dev/null 2>&1; then
    lsof -a -p "${pid}" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1
  fi
}

process_belongs_to_repo() {
  local pid="$1"
  local expected="$2"
  local cwd args
  cwd="$(process_cwd "${pid}")"
  args="$(process_args "${pid}")"

  [[ -n "${cwd}" && "${cwd}" == "${ROOT_DIR}"* ]] && return 0
  [[ "${args}" == *"${ROOT_DIR}"* ]] && return 0
  # Uvicorn 的 app 路径足够具体，可作为无法读取 cwd 时的后端兜底；
  # `vite` 太通用，不能仅凭进程名认定属于本仓库。
  [[ "${expected}" == "uvicorn tsgo.web.app:app" && "${args}" == *"${expected}"* ]]
}

collect_descendants() {
  local parent="$1"
  local child
  command -v pgrep >/dev/null 2>&1 || return 0
  while read -r child; do
    [[ "${child}" =~ ^[0-9]+$ ]] || continue
    collect_descendants "${child}"
    printf '%s\n' "${child}"
  done < <(pgrep -P "${parent}" 2>/dev/null || true)
}

terminate_process_tree() {
  local pid="$1"
  local descendants=()
  local child
  if command -v pgrep >/dev/null 2>&1; then
    while read -r child; do
      [[ "${child}" =~ ^[0-9]+$ ]] && descendants+=("${child}")
    done < <(collect_descendants "${pid}")
  fi

  if ((${#descendants[@]} > 0)); then
    kill "${descendants[@]}" 2>/dev/null || true
  fi
  kill "${pid}" 2>/dev/null || true

  for _ in {1..30}; do
    kill -0 "${pid}" 2>/dev/null || break
    sleep 0.2
  done

  for child in "${descendants[@]}"; do
    kill -0 "${child}" 2>/dev/null && kill -9 "${child}" 2>/dev/null || true
  done
  kill -0 "${pid}" 2>/dev/null && kill -9 "${pid}" 2>/dev/null || true
}

stop_pid_file() {
  local name="$1"
  local pid_file="$2"
  local expected="$3"
  local pid=""

  if pid="$(read_pid "${pid_file}")" && kill -0 "${pid}" 2>/dev/null; then
    if ! process_matches "${pid}" "${expected}"; then
      warn "${name} PID 文件指向了其他进程，拒绝终止：PID=${pid} args=$(process_args "${pid}")"
      rm -f "${pid_file}"
      return 0
    fi
    log "停止 ${name}，PID=${pid}"
    terminate_process_tree "${pid}"
  fi
  rm -f "${pid_file}"
}

port_listener_pids() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
  elif command -v fuser >/dev/null 2>&1; then
    fuser -n tcp "${port}" 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+$' || true
  fi
}

tcp_ready() {
  local host="$1"
  local port="$2"
  (echo > "/dev/tcp/${host}/${port}") >/dev/null 2>&1
}

release_port() {
  local name="$1"
  local port="$2"
  local expected="$3"
  local pid pids=()

  while read -r pid; do
    [[ "${pid}" =~ ^[0-9]+$ ]] && pids+=("${pid}")
  done < <(port_listener_pids "${port}")

  for pid in "${pids[@]}"; do
    if process_belongs_to_repo "${pid}" "${expected}"; then
      warn "清理遗留的 ${name} 监听进程：PID=${pid} port=${port}"
      terminate_process_tree "${pid}"
    elif is_true "${FORCE_KILL_PORTS}"; then
      warn "FORCE_KILL_PORTS=${FORCE_KILL_PORTS}，终止无关端口进程：PID=${pid} port=${port}"
      terminate_process_tree "${pid}"
    else
      fail "端口 ${port} 已被其他进程占用：PID=${pid} args=$(process_args "${pid}")。请释放端口，或明确设置 FORCE_KILL_PORTS=1。"
    fi
  done

  if tcp_ready 127.0.0.1 "${port}"; then
    fail "端口 ${port} 仍被占用，但无法安全识别监听进程；请安装 lsof/fuser 后检查。"
  fi
}

stop_services() {
  stop_pid_file "前端" "${FRONTEND_PID_FILE}" "npm run dev"
  stop_pid_file "后端" "${BACKEND_PID_FILE}" "uvicorn tsgo.web.app:app"
  release_port "前端" "${FRONTEND_PORT}" "vite"
  release_port "后端" "${BACKEND_PORT}" "uvicorn tsgo.web.app:app"
}

start_backend() {
  local reload_args=()
  if is_true "${UVICORN_RELOAD}"; then
    reload_args+=(--reload)
  fi

  : > "${BACKEND_LOG}"
  log "启动后端：http://${BACKEND_CHECK_HOST}:${BACKEND_PORT}"
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
  log "启动前端：http://${FRONTEND_CHECK_HOST}:${FRONTEND_PORT}"
  (
    cd "${WEB_DIR}"
    nohup npm run dev -- \
      --host "${FRONTEND_HOST}" \
      --port "${FRONTEND_PORT}" \
      >>"${FRONTEND_LOG}" 2>&1 </dev/null &
    echo $! > "${FRONTEND_PID_FILE}"
  )
}

http_ready() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsS --max-time 2 "${url}" >/dev/null 2>&1
  else
    "${PYTHON_BIN}" - "${url}" >/dev/null 2>&1 <<'PY'
import sys
import urllib.request

with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
    if not 200 <= response.status < 400:
        raise SystemExit(1)
PY
  fi
}

wait_for_http() {
  local name="$1"
  local url="$2"
  local pid_file="$3"
  local deadline=$((SECONDS + STARTUP_TIMEOUT))
  local pid=""

  while (( SECONDS < deadline )); do
    pid="$(read_pid "${pid_file}" 2>/dev/null || true)"
    if [[ -z "${pid}" ]] || ! kill -0 "${pid}" 2>/dev/null; then
      log "${name} 进程已提前退出"
      return 1
    fi
    if http_ready "${url}"; then
      log "${name} 健康检查通过：${url}"
      return 0
    fi
    sleep 0.5
  done

  log "${name} 在 ${STARTUP_TIMEOUT}s 内未通过健康检查：${url}"
  return 1
}

service_status() {
  local name="$1"
  local pid_file="$2"
  local expected="$3"
  local url="$4"
  local port="$5"
  local pid status health

  pid="$(read_pid "${pid_file}" 2>/dev/null || true)"
  status="stopped"
  health="unavailable"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null && process_matches "${pid}" "${expected}"; then
    status="running"
    health="starting"
    http_ready "${url}" && health="ready"
  fi
  printf '%-6s status=%-7s health=%-9s pid=%-8s port=%s\n' \
    "${name}" "${status}" "${health}" "${pid:-none}" "${port}"
}

show_status() {
  service_status "后端" "${BACKEND_PID_FILE}" "uvicorn tsgo.web.app:app" "${BACKEND_HEALTH_URL}" "${BACKEND_PORT}"
  service_status "前端" "${FRONTEND_PID_FILE}" "npm run dev" "${FRONTEND_HEALTH_URL}" "${FRONTEND_PORT}"
  printf 'backend log:  %s\n' "${BACKEND_LOG}"
  printf 'frontend log: %s\n' "${FRONTEND_LOG}"
  printf 'backend extras: %s\n' "${BACKEND_EXTRAS}"
}

show_failure_logs() {
  printf '\n===== backend.log =====\n'
  tail -n 100 "${BACKEND_LOG}" 2>/dev/null || true
  printf '\n===== frontend.log =====\n'
  tail -n 100 "${FRONTEND_LOG}" 2>/dev/null || true
}

preflight() {
  require_command "${PYTHON_BIN}"
  require_command npm
  [[ -d "${WEB_DIR}" ]] || fail "前端目录不存在：${WEB_DIR}"
  [[ -f "${ROOT_DIR}/pyproject.toml" ]] || fail "pyproject.toml 不存在：${ROOT_DIR}/pyproject.toml"
}

prepare_runtime() {
  preflight
  install_backend_dependencies
  install_frontend_dependencies
  build_frontend
}

start_services() {
  release_port "前端" "${FRONTEND_PORT}" "vite"
  release_port "后端" "${BACKEND_PORT}" "uvicorn tsgo.web.app:app"
  start_backend
  start_frontend

  if ! wait_for_http "后端" "${BACKEND_HEALTH_URL}" "${BACKEND_PID_FILE}"; then
    show_failure_logs
    stop_services
    exit 1
  fi
  if ! wait_for_http "前端" "${FRONTEND_HEALTH_URL}" "${FRONTEND_PID_FILE}"; then
    show_failure_logs
    stop_services
    exit 1
  fi

  log "启动完成"
  show_status
}

restart_services() {
  # 先完成依赖安装和前端编译；失败时保留仍在工作的旧服务。
  prepare_runtime
  stop_services
  start_services
  log "重启完成"
}

install_dependencies() {
  preflight
  install_backend_dependencies
  install_frontend_dependencies
  log "依赖检查/安装完成"
}

doctor() {
  local failed=0
  log "检查运行环境"

  if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    warn "缺少 Python：${PYTHON_BIN}"
    failed=1
  elif ! "${PYTHON_BIN}" -m pip --version >/dev/null 2>&1; then
    warn "${PYTHON_BIN} 缺少 pip"
    failed=1
  elif ! backend_import_check; then
    failed=1
  else
    log "后端依赖可导入"
  fi

  if ! command -v npm >/dev/null 2>&1; then
    warn "缺少 npm"
    failed=1
  elif ! frontend_dependency_check; then
    warn "前端依赖不完整"
    failed=1
  else
    log "前端依赖完整"
  fi

  if [[ -f "${ROOT_DIR}/.env" ]]; then
    log "发现本地 .env"
  else
    warn "未发现 .env；Stage Flow 可运行，Azure/DeepSeek/AIDC 真实模型调用需要配置。"
  fi

  show_status
  (( failed == 0 )) || return 1
  log "环境检查通过"
}

usage() {
  cat <<'USAGE'
用法：
  bash scripts/restart_web.sh [restart|start|stop|status|logs|install|doctor]

默认执行 restart：
  1. 检查 Python/npm
  2. 自动安装/校验后端 extras：web,azure,deepseek,aidc
  3. 根据 package-lock/package.json 自动安装/校验前端依赖
  4. npm run build，先验证 TypeScript/Vite；失败时不停止旧服务
  5. 只停止本仓库的旧 Uvicorn/Vite 进程
  6. 启动后端和前端
  7. 通过 HTTP endpoint 而不是仅检查端口判断服务就绪

动作：
  restart  准备依赖、构建、停止旧服务并重新启动（默认）
  start    准备依赖、构建并启动；端口已有服务时安全失败
  stop     停止本仓库记录或识别出的前后端进程
  status   显示 PID、端口和 HTTP health
  logs     持续查看前后端日志
  install  只安装/校验 Python 和 npm 依赖
  doctor   不修改环境，检查依赖、.env 和服务状态

常用环境变量：
  PYTHON_BIN=python3
  BACKEND_INSTALL=auto       # auto / always(1) / never(0)
  BACKEND_EXTRAS=web,azure,deepseek,aidc
  NPM_INSTALL=auto           # auto / always(1) / never(0)
  SKIP_BUILD=0
  BACKEND_HOST=0.0.0.0
  BACKEND_PORT=8000
  FRONTEND_HOST=0.0.0.0
  FRONTEND_PORT=5173
  BACKEND_CHECK_HOST=127.0.0.1
  FRONTEND_CHECK_HOST=127.0.0.1
  STARTUP_TIMEOUT=45
  UVICORN_RELOAD=0
  FORCE_KILL_PORTS=0         # 默认不终止无关端口进程；明确设为 1 才强制终止
  TSGO_RUN_DIR=/tmp/tsgo-web-$USER
  TSGO_LOG_DIR=<run-dir>/logs
  TSGO_CACHE_DIR=<run-dir>/cache
USAGE
}

main() {
  local action="${1:-restart}"
  case "${action}" in
    restart) restart_services ;;
    start) prepare_runtime; start_services ;;
    stop) stop_services; show_status ;;
    status) show_status ;;
    install) install_dependencies ;;
    doctor) doctor ;;
    logs)
      touch "${BACKEND_LOG}" "${FRONTEND_LOG}"
      tail -n 100 -f "${BACKEND_LOG}" "${FRONTEND_LOG}"
      ;;
    -h|--help|help) usage ;;
    *) usage; fail "未知动作：${action}" ;;
  esac
}

main "$@"
