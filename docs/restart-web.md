# Web UI 一键重启脚本

`scripts/restart_web.sh` 用于准备依赖、验证构建、停止旧服务、启动 FastAPI/Vite，并检查应用是否真正可用。

## 最常用命令

```bash
git pull origin main
bash scripts/restart_web.sh restart
```

也可以省略 `restart`：

```bash
bash scripts/restart_web.sh
```

默认流程：

```text
检查 Python/npm
  -> 检查 pyproject + Python + extras 指纹
  -> 必要时 pip install -e '.[web,azure,deepseek,aidc]'
  -> 检查 package-lock/package.json 指纹
  -> 必要时 npm ci / npm install
  -> npm run build
  -> 停止本仓库旧进程
  -> 启动 Uvicorn + Vite
  -> GET /openapi.json
  -> GET /
  -> status=running health=ready
```

依赖安装和前端构建发生在停止旧服务之前。因此依赖下载或 TypeScript 构建失败时，原有 Web UI 不会先被关闭。

## 动作

```bash
bash scripts/restart_web.sh restart  # 完整重启
bash scripts/restart_web.sh start    # 准备依赖并启动
bash scripts/restart_web.sh stop     # 停止前后端
bash scripts/restart_web.sh status   # PID、端口、HTTP health
bash scripts/restart_web.sh logs     # 持续查看日志
bash scripts/restart_web.sh install  # 只安装/检查依赖
bash scripts/restart_web.sh doctor   # 只诊断，不修改环境
```

## 后端依赖

默认安装：

```text
web
azure
deepseek
aidc
```

等价命令：

```bash
pip install -e '.[web,azure,deepseek,aidc]'
```

控制方式：

```bash
BACKEND_INSTALL=auto bash scripts/restart_web.sh restart
BACKEND_INSTALL=always bash scripts/restart_web.sh restart
BACKEND_INSTALL=never bash scripts/restart_web.sh restart
```

`auto` 会在以下情况下重新安装：

- 必需模块无法导入；
- `pyproject.toml` 变化；
- Python 或 pip 环境变化；
- `BACKEND_EXTRAS` 变化。

只启动基础 Web UI，不准备真实模型和 AIDC 依赖：

```bash
BACKEND_EXTRAS=web bash scripts/restart_web.sh restart
```

## 前端依赖

`NPM_INSTALL=auto` 会检查：

- `web/node_modules` 是否存在；
- `npm ls --depth=0` 是否通过；
- `package-lock.json` 或 `package.json` 是否变化。

有 lock 文件时使用 `npm ci`，否则使用 `npm install`。

```bash
NPM_INSTALL=always bash scripts/restart_web.sh restart
NPM_INSTALL=never bash scripts/restart_web.sh restart
```

## 健康检查

脚本不再以“端口可以建立 TCP 连接”作为成功条件。

默认检查：

```text
后端：http://127.0.0.1:8000/openapi.json
前端：http://127.0.0.1:5173/
```

可覆盖：

```bash
BACKEND_HEALTH_PATH=/openapi.json
FRONTEND_HEALTH_PATH=/
STARTUP_TIMEOUT=60
```

`status` 示例：

```text
后端 status=running health=ready pid=1234 port=8000
前端 status=running health=ready pid=1235 port=5173
```

## 端口安全

旧脚本会直接终止所有占用 8000/5173 的进程。新脚本默认只终止：

- PID 文件中且命令匹配的 Uvicorn/Vite 进程；
- 工作目录位于当前仓库中的遗留进程；
- 明确属于 `tsgo.web.app:app` 的后端进程。

发现无关进程时会停止操作并显示 PID 和命令。只有明确允许时才强制处理：

```bash
FORCE_KILL_PORTS=1 bash scripts/restart_web.sh restart
```

不要把该设置长期写入环境变量。

## 日志和运行文件

默认位置：

```text
/tmp/tsgo-web-$USER/backend.pid
/tmp/tsgo-web-$USER/frontend.pid
/tmp/tsgo-web-$USER/logs/backend.log
/tmp/tsgo-web-$USER/logs/frontend.log
/tmp/tsgo-web-$USER/cache/*.sha256
```

可覆盖：

```bash
TSGO_RUN_DIR=/var/run/user/$UID/tsgo-web
TSGO_LOG_DIR=/var/log/tsgo-web
TSGO_CACHE_DIR=$HOME/.cache/tsgo-web
```

## 常见排查

先运行：

```bash
bash scripts/restart_web.sh doctor
bash scripts/restart_web.sh status
```

查看日志：

```bash
bash scripts/restart_web.sh logs
```

强制重新安装依赖：

```bash
BACKEND_INSTALL=always NPM_INSTALL=always bash scripts/restart_web.sh restart
```

跳过前端构建仅适合临时诊断：

```bash
SKIP_BUILD=1 bash scripts/restart_web.sh restart
```
