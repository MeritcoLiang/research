# Windows PowerShell 一键更新与重启 Web UI

`scripts/restart_web.ps1` 是 `scripts/restart_web.sh` 的 Windows 版本。默认 `restart` 会依次完成代码更新、依赖准备、前端构建、旧进程回收、服务启动和 HTTP 健康检查。

## 最常用命令

Windows PowerShell 5.1：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\restart_web.ps1 restart
```

PowerShell 7：

```powershell
pwsh -File .\scripts\restart_web.ps1 restart
```

在已经允许本地脚本执行的 PowerShell 中，也可以直接运行：

```powershell
.\scripts\restart_web.ps1
```

默认流程：

```text
检查 Git checkout、当前分支和已跟踪修改
  -> git fetch --prune origin
  -> git pull --ff-only origin <当前分支>
  -> 检查 pyproject/Python/pip/extras 指纹
  -> 必要时 pip install -e ".[web,azure,deepseek,aidc]"
  -> 检查 package-lock/package.json/npm 指纹
  -> 必要时 npm ci / npm install
  -> npm run build
  -> 停止本仓库旧 Uvicorn/Vite 进程
  -> 启动 Uvicorn
  -> 使用 node.exe 直接启动 Vite
  -> GET /openapi.json
  -> GET /
  -> status=running health=ready
```

`git pull`、依赖安装和前端构建全部发生在停止旧服务之前。因此更新、pip、npm 或 TypeScript 构建失败时，原来正在工作的 Web UI 不会先被关闭。

## Git pull 行为

默认配置：

```text
GIT_PULL=auto
GIT_REMOTE=origin
GIT_BRANCH=<当前分支>
```

实际执行：

```powershell
git fetch --prune origin
git pull --ff-only origin <当前分支>
```

使用 `--ff-only` 可以防止部署机器意外生成 merge commit。

脚本会在以下情况停止，而且不会关闭旧服务：

- 当前处于 detached HEAD；
- 当前分支与显式设置的 `GIT_BRANCH` 不一致；
- 存在未提交的已跟踪修改；
- `git fetch` 或 `git pull` 失败；
- 当前分支无法 fast-forward 到远端。

未跟踪文件不会单独阻止更新，但它们会覆盖远端文件时，Git 自身仍会拒绝 pull。

临时跳过更新：

```powershell
.\scripts\restart_web.ps1 restart -SkipGitPull
```

或：

```powershell
$env:GIT_PULL = "never"
.\scripts\restart_web.ps1 restart
```

部署机器固定使用 `origin/main`：

```powershell
$env:GIT_REMOTE = "origin"
$env:GIT_BRANCH = "main"
.\scripts\restart_web.ps1 restart
```

恢复默认：

```powershell
Remove-Item Env:GIT_PULL -ErrorAction SilentlyContinue
Remove-Item Env:GIT_REMOTE -ErrorAction SilentlyContinue
Remove-Item Env:GIT_BRANCH -ErrorAction SilentlyContinue
```

## 支持的动作

```powershell
.\scripts\restart_web.ps1 restart  # 更新代码、准备依赖、构建并重启
.\scripts\restart_web.ps1 start    # 更新代码、准备依赖、构建并启动
.\scripts\restart_web.ps1 stop     # 停止前后端
.\scripts\restart_web.ps1 status   # 显示 PID、端口和 HTTP health
.\scripts\restart_web.ps1 logs     # 持续查看 stdout/stderr
.\scripts\restart_web.ps1 install  # 更新代码并安装/检查依赖
.\scripts\restart_web.ps1 doctor   # 不修改环境，只做诊断
.\scripts\restart_web.ps1 help
```

命令行开关：

```text
-SkipGitPull     本次跳过 git pull
-ForceInstall    本次强制安装 Python/npm 依赖
-ForceKillPorts  明确允许终止无关端口进程
```

## 后端依赖

默认安装并验证：

```text
web,azure,deepseek,aidc
```

等价命令：

```powershell
python -m pip install -e ".[web,azure,deepseek,aidc]"
```

安装策略：

```powershell
$env:BACKEND_INSTALL = "auto"    # 默认，根据指纹和导入检查判断
$env:BACKEND_INSTALL = "always"  # 每次重新安装
$env:BACKEND_INSTALL = "never"   # 只检查，不安装
```

本次强制安装全部依赖：

```powershell
.\scripts\restart_web.ps1 restart -ForceInstall
```

只准备基础 Web UI：

```powershell
$env:BACKEND_EXTRAS = "web"
.\scripts\restart_web.ps1 restart
```

## 前端依赖和 Vite 启动

`NPM_INSTALL=auto` 会检查：

- `web\node_modules` 是否存在；
- `npm ls --depth=0` 是否通过；
- `package-lock.json` 或 `package.json` 是否变化；
- npm 版本是否变化。

有 lock 文件时使用 `npm ci`，否则使用 `npm install`。

```powershell
$env:NPM_INSTALL = "always"
.\scripts\restart_web.ps1 restart
```

依赖和构建仍由 npm 完成。服务启动阶段则直接执行：

```text
node.exe web\node_modules\vite\bin\vite.js
```

这样可以避免 Windows 上通过 `Start-Process` 启动 `npm.cmd` 并重定向日志时的兼容问题。

## 健康检查

默认检查：

```text
后端：http://127.0.0.1:8000/openapi.json
前端：http://127.0.0.1:5173/
```

可覆盖：

```powershell
$env:BACKEND_HEALTH_PATH = "/openapi.json"
$env:FRONTEND_HEALTH_PATH = "/"
$env:STARTUP_TIMEOUT = "60"
```

状态示例：

```text
后端     status=running health=ready     pid=1234     port=8000
前端     status=running health=ready     pid=5678     port=5173
```

前后端任一启动失败，脚本都会清理已经启动的另一端，并输出 stdout/stderr 日志位置。

## 端口安全

脚本通过 PID 文件、进程命令行和仓库路径识别自己的 Uvicorn/Vite 进程。发现无关服务占用 8000 或 5173 时默认停止操作，不会直接终止该进程。

只在明确确认端口可以被清理时使用：

```powershell
.\scripts\restart_web.ps1 restart -ForceKillPorts
```

或：

```powershell
$env:FORCE_KILL_PORTS = "1"
.\scripts\restart_web.ps1 restart
```

不要长期设置 `FORCE_KILL_PORTS=1`。

## 日志和运行文件

默认位置：

```text
%LOCALAPPDATA%\tsgo-web\backend.pid
%LOCALAPPDATA%\tsgo-web\frontend.pid
%LOCALAPPDATA%\tsgo-web\logs\backend.log
%LOCALAPPDATA%\tsgo-web\logs\backend.error.log
%LOCALAPPDATA%\tsgo-web\logs\frontend.log
%LOCALAPPDATA%\tsgo-web\logs\frontend.error.log
%LOCALAPPDATA%\tsgo-web\cache\backend-deps.sha256
%LOCALAPPDATA%\tsgo-web\cache\frontend-deps.sha256
```

可覆盖：

```powershell
$env:TSGO_RUN_DIR = "D:\runtime\tsgo-web"
$env:TSGO_LOG_DIR = "D:\logs\tsgo-web"
$env:TSGO_CACHE_DIR = "D:\cache\tsgo-web"
```

## Python、npm、Node 和 Git 路径

默认：

```text
PYTHON_BIN=python
NPM_BIN=npm.cmd
NODE_BIN=node.exe
GIT_BIN=git.exe
```

存在多个 Python 时可以指定虚拟环境：

```powershell
$env:PYTHON_BIN = "$PWD\.venv\Scripts\python.exe"
.\scripts\restart_web.ps1 restart
```

## Execution Policy

不修改系统策略的单次运行方式：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\restart_web.ps1 restart
```

也可以仅为当前用户允许本地脚本：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 排查

```powershell
.\scripts\restart_web.ps1 doctor
.\scripts\restart_web.ps1 status
.\scripts\restart_web.ps1 logs
```

跳过 Git 更新，单独排查本地代码：

```powershell
.\scripts\restart_web.ps1 restart -SkipGitPull
```

完全重装依赖：

```powershell
.\scripts\restart_web.ps1 restart -ForceInstall
```
