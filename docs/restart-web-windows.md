# Windows PowerShell 一键更新与重启 Web UI

`scripts/restart_web.ps1` 是 Windows PowerShell 5.1 / PowerShell 7 版本的一键部署脚本。默认 `restart` 会依次完成 Git 更新、依赖检查、前端构建、旧进程回收、服务启动和 HTTP 健康检查。

该脚本不会注册 Windows Service，也不会配置开机自启。前后端是当前用户手动启动的普通进程，机器重启或用户登录后需要再次执行 `start` 或 `restart`。

## 最常用命令

Windows PowerShell 5.1：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\restart_web.ps1 restart
```

PowerShell 7：

```powershell
pwsh -File .\scripts\restart_web.ps1 restart
```

默认流程：

```text
检查 Git checkout、当前分支和已跟踪修改
  -> Git 强制使用 HTTP/1.1
  -> git fetch --prune + git pull --ff-only，默认最多重试 3 次
  -> auto 模式更新失败时继续使用本地代码
  -> 检查并安装 web,azure,deepseek,aidc 后端 extras
  -> 逐模块执行 Python import probe
  -> 检查并安装 npm 依赖
  -> npm run build
  -> 停止本仓库旧 Uvicorn/Vite
  -> 启动 Uvicorn 和 Vite
  -> GET /openapi.json 与 GET /
```

Git、pip、npm 或前端构建都发生在停止旧服务之前。

## Git 更新策略

默认值：

```text
GIT_PULL=auto
GIT_REMOTE=origin
GIT_BRANCH=<当前分支>
GIT_RETRIES=3
GIT_RETRY_DELAY=3
GIT_HTTP_VERSION=HTTP/1.1
```

每次网络尝试实际执行：

```powershell
git -c http.version=HTTP/1.1 fetch --prune origin
git -c http.version=HTTP/1.1 pull --ff-only origin <当前分支>
```

`HTTP/1.1` 用于减少某些代理、路由器或运营商环境下 GitHub HTTP/2 连接被 reset 的概率。

### `GIT_PULL=auto`

默认模式。最多重试三次；仍失败时给出警告，继续使用当前本地 commit 完成依赖检查和重启。

### 必须更新成功

```powershell
.\scripts\restart_web.ps1 restart -RequireGitPull
```

或：

```powershell
$env:GIT_PULL = "always"
.\scripts\restart_web.ps1 restart
```

更新失败时会退出，旧服务不会停止。

### 跳过 Git 更新

```powershell
.\scripts\restart_web.ps1 restart -SkipGitPull
```

适用于 GitHub 暂时不可达，但本地代码已经可用的情况。

### 固定部署分支

```powershell
$env:GIT_REMOTE = "origin"
$env:GIT_BRANCH = "main"
.\scripts\restart_web.ps1 restart
```

脚本仍会拒绝：

- detached HEAD；
- 当前分支与 `GIT_BRANCH` 不一致；
- 存在未提交的已跟踪修改；
- `--ff-only` 无法快进。

未跟踪文件本身不会阻止更新，但覆盖远端文件时 Git 会拒绝 pull。

## 后端依赖和导入诊断

默认 extras：

```text
web,azure,deepseek,aidc
```

等价命令：

```powershell
python -m pip install -e ".[web,azure,deepseek,aidc]"
```

安装完成后脚本不再只返回“无法导入”，而会逐项输出：

```text
python=C:\...\python.exe
version=3.x.x ...
[OK] fastapi -> ...
[OK] uvicorn -> ...
[FAIL] agents
Traceback (most recent call last):
...
```

检查目标会根据 extras 包含：

```text
fastapi
uvicorn
openai
azure.identity
dotenv
agents
pydantic
tsgo.web.app
tsgo.aidc_progress
```

因此可以直接看到失败的是第三方包、Python 环境，还是项目模块。

只执行诊断：

```powershell
.\scripts\restart_web.ps1 doctor
```

强制重新安装：

```powershell
.\scripts\restart_web.ps1 restart -ForceInstall
```

只启动基础 Web UI，临时排除 Agents SDK/Azure/DeepSeek：

```powershell
$env:BACKEND_EXTRAS = "web"
.\scripts\restart_web.ps1 restart -SkipGitPull -ForceInstall
```

恢复默认：

```powershell
Remove-Item Env:BACKEND_EXTRAS -ErrorAction SilentlyContinue
```

## 当前两个错误的处理

### `Recv failure: Connection was reset`

新版脚本会自动：

1. 使用 HTTP/1.1；
2. 重试三次；
3. 在默认 `auto` 模式继续使用本地 commit。

旧版脚本下可直接运行：

```powershell
.\scripts\restart_web.ps1 restart -SkipGitPull
```

也可以手工测试：

```powershell
git -c http.version=HTTP/1.1 fetch --prune origin
git -c http.version=HTTP/1.1 pull --ff-only origin main
```

### `后端依赖安装后仍无法导入`

旧版脚本隐藏了 traceback。可先手工执行：

```powershell
@'
import importlib
import sys
import traceback

modules = [
    "fastapi", "uvicorn", "openai", "azure.identity",
    "dotenv", "agents", "pydantic",
    "tsgo.web.app", "tsgo.aidc_progress",
]
print("python=", sys.executable)
print("version=", sys.version)
for name in modules:
    try:
        module = importlib.import_module(name)
        print("[OK]", name, getattr(module, "__file__", ""))
    except Exception:
        print("[FAIL]", name)
        traceback.print_exc()
'@ | python -
```

新版脚本会自动输出同类结果。

## 前端依赖和启动

`NPM_INSTALL=auto` 会检查：

- `web\node_modules`；
- `npm ls --depth=0`；
- `package-lock.json` / `package.json`；
- npm 版本。

有 lock 文件时执行 `npm ci`，否则执行 `npm install`。构建使用 `npm run build`。

服务启动直接调用：

```text
node.exe web\node_modules\vite\bin\vite.js
```

避免 `Start-Process + npm.cmd + 日志重定向` 的 Windows 兼容问题。

## 动作与开关

```powershell
.\scripts\restart_web.ps1 restart
.\scripts\restart_web.ps1 start
.\scripts\restart_web.ps1 stop
.\scripts\restart_web.ps1 status
.\scripts\restart_web.ps1 test
.\scripts\restart_web.ps1 logs
.\scripts\restart_web.ps1 install
.\scripts\restart_web.ps1 uninstall
.\scripts\restart_web.ps1 doctor
.\scripts\restart_web.ps1 help
```

开关：

```text
-SkipGitPull
-RequireGitPull
-ForceInstall
-ForceKillPorts
```

## 健康检查

默认：

```text
后端：http://127.0.0.1:8000/openapi.json
前端：http://127.0.0.1:5173/
```

覆盖方式：

```powershell
$env:BACKEND_HEALTH_PATH = "/openapi.json"
$env:FRONTEND_HEALTH_PATH = "/"
$env:STARTUP_TIMEOUT = "60"
```

前后端任一启动失败，脚本会清理另一端并显示日志。

只做一次简单可用性测试（不更新代码、不安装依赖、不构建）：

```powershell
.\scripts\restart_web.ps1 test
```

测试分别请求后端 `/openapi.json` 和前端 `/`；任一请求失败时命令返回退出码 `1`，适合手工验证或被其他脚本调用。

## 卸载

```powershell
.\scripts\restart_web.ps1 uninstall
```

卸载会：

- 只停止 PID 文件记录的本项目 Uvicorn/Vite 进程；
- 从当前 Python 环境卸载 `thought-state-graph-orchestration` 项目包；
- 删除 `web\node_modules`、`web\dist` 和 `%LOCALAPPDATA%\tsgo-web` 运行目录。

源码、`.env`、lock 文件和可能由其他项目共享的第三方 Python 包会保留。因为 Windows 版本不注册系统服务，所以不需要管理员权限或额外删除服务。

## 端口安全

发现无关进程占用 8000/5173 时默认退出，不直接杀进程。明确确认后才使用：

```powershell
.\scripts\restart_web.ps1 restart -ForceKillPorts
```

## 日志和运行目录

默认：

```text
%LOCALAPPDATA%\tsgo-web\backend.pid
%LOCALAPPDATA%\tsgo-web\frontend.pid
%LOCALAPPDATA%\tsgo-web\logs\backend.log
%LOCALAPPDATA%\tsgo-web\logs\backend.error.log
%LOCALAPPDATA%\tsgo-web\logs\frontend.log
%LOCALAPPDATA%\tsgo-web\logs\frontend.error.log
%LOCALAPPDATA%\tsgo-web\cache\*.sha256
```

查看日志：

```powershell
.\scripts\restart_web.ps1 logs
```

## Execution Policy

不修改系统策略：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\restart_web.ps1 restart
```

或仅为当前用户允许本地脚本：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
