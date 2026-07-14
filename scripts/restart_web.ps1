[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("restart", "start", "stop", "status", "logs", "install", "doctor", "help")]
    [string]$Action = "restart",
    [switch]$SkipGitPull,
    [switch]$ForceInstall,
    [switch]$ForceKillPorts
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function Get-EnvOrDefault {
    param([string]$Name, [string]$Default)
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value.Trim()
}

function ConvertTo-Bool {
    param([string]$Value)
    return @("1", "true", "yes", "on") -contains $Value.Trim().ToLowerInvariant()
}

function Normalize-Mode {
    param([string]$Value, [string]$Name)
    switch ($Value.Trim().ToLowerInvariant()) {
        "auto" { return "auto" }
        { @("1", "true", "yes", "on", "always") -contains $_ } { return "always" }
        { @("0", "false", "no", "off", "never") -contains $_ } { return "never" }
        default { throw "$Name 只能是 auto、always/1 或 never/0，当前值：$Value" }
    }
}

function Write-Log {
    param([string]$Message)
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message)
}

function Write-WarnLog {
    param([string]$Message)
    Write-Host ("[{0}] WARN: {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message) -ForegroundColor Yellow
}

function Resolve-CommandPath {
    param([string]$Name)
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) { throw "缺少命令：$Name" }
    if (-not [string]::IsNullOrWhiteSpace([string]$command.Path)) { return $command.Path }
    if (-not [string]::IsNullOrWhiteSpace([string]$command.Source)) { return $command.Source }
    return $command.Name
}

function Get-Sha256Text {
    param([string]$Text)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
        return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
    }
    finally { $sha.Dispose() }
}

$RootDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$WebDir = Join-Path $RootDir "web"
$DefaultRunBase = Get-EnvOrDefault "LOCALAPPDATA" (Get-EnvOrDefault "TEMP" $RootDir)
$RunDir = Get-EnvOrDefault "TSGO_RUN_DIR" (Join-Path $DefaultRunBase "tsgo-web")
$LogDir = Get-EnvOrDefault "TSGO_LOG_DIR" (Join-Path $RunDir "logs")
$CacheDir = Get-EnvOrDefault "TSGO_CACHE_DIR" (Join-Path $RunDir "cache")

$PythonBin = Get-EnvOrDefault "PYTHON_BIN" "python"
$NpmBin = Get-EnvOrDefault "NPM_BIN" "npm.cmd"
$NodeBin = Get-EnvOrDefault "NODE_BIN" "node.exe"
$GitBin = Get-EnvOrDefault "GIT_BIN" "git.exe"
$BackendHost = Get-EnvOrDefault "BACKEND_HOST" "0.0.0.0"
$BackendPort = [int](Get-EnvOrDefault "BACKEND_PORT" "8000")
$FrontendHost = Get-EnvOrDefault "FRONTEND_HOST" "0.0.0.0"
$FrontendPort = [int](Get-EnvOrDefault "FRONTEND_PORT" "5173")
$BackendCheckHost = Get-EnvOrDefault "BACKEND_CHECK_HOST" "127.0.0.1"
$FrontendCheckHost = Get-EnvOrDefault "FRONTEND_CHECK_HOST" "127.0.0.1"
$BackendHealthPath = Get-EnvOrDefault "BACKEND_HEALTH_PATH" "/openapi.json"
$FrontendHealthPath = Get-EnvOrDefault "FRONTEND_HEALTH_PATH" "/"
$StartupTimeout = [int](Get-EnvOrDefault "STARTUP_TIMEOUT" "45")
$UvicornReload = ConvertTo-Bool (Get-EnvOrDefault "UVICORN_RELOAD" "0")
$BackendInstall = if ($ForceInstall) { "always" } else { Get-EnvOrDefault "BACKEND_INSTALL" "auto" }
$BackendExtras = ((Get-EnvOrDefault "BACKEND_EXTRAS" "web,azure,deepseek,aidc") -replace "\s", "").ToLowerInvariant()
$NpmInstall = if ($ForceInstall) { "always" } else { Get-EnvOrDefault "NPM_INSTALL" "auto" }
$SkipBuild = ConvertTo-Bool (Get-EnvOrDefault "SKIP_BUILD" "0")
$AllowForceKillPorts = $ForceKillPorts -or (ConvertTo-Bool (Get-EnvOrDefault "FORCE_KILL_PORTS" "0"))
$GitPullMode = if ($SkipGitPull) { "never" } else { Get-EnvOrDefault "GIT_PULL" "auto" }
$GitRemote = Get-EnvOrDefault "GIT_REMOTE" "origin"
$GitBranch = Get-EnvOrDefault "GIT_BRANCH" ""

$BackendPidFile = Join-Path $RunDir "backend.pid"
$FrontendPidFile = Join-Path $RunDir "frontend.pid"
$BackendLog = Join-Path $LogDir "backend.log"
$BackendErrorLog = Join-Path $LogDir "backend.error.log"
$FrontendLog = Join-Path $LogDir "frontend.log"
$FrontendErrorLog = Join-Path $LogDir "frontend.error.log"
$BackendDepsStamp = Join-Path $CacheDir "backend-deps.sha256"
$FrontendDepsStamp = Join-Path $CacheDir "frontend-deps.sha256"
$BackendHealthUrl = "http://${BackendCheckHost}:${BackendPort}${BackendHealthPath}"
$FrontendHealthUrl = "http://${FrontendCheckHost}:${FrontendPort}${FrontendHealthPath}"

@($RunDir, $LogDir, $CacheDir) | ForEach-Object {
    if (-not (Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}

function Invoke-GitUpdate {
    $mode = Normalize-Mode $GitPullMode "GIT_PULL"
    if ($mode -eq "never") {
        Write-Log "GIT_PULL=$GitPullMode，跳过代码更新"
        return
    }
    if (-not (Test-Path (Join-Path $RootDir ".git"))) {
        if ($mode -eq "always") { throw "当前目录不是 Git checkout：$RootDir" }
        Write-WarnLog "未发现 .git，跳过 git pull"
        return
    }

    $script:GitBin = Resolve-CommandPath $GitBin
    Push-Location $RootDir
    try {
        $topLevel = (& $script:GitBin rev-parse --show-toplevel 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { throw "无法确认 Git 仓库：$topLevel" }
        if ([System.IO.Path]::GetFullPath($topLevel).TrimEnd('\') -ne $RootDir.TrimEnd('\')) {
            throw "脚本目录与 Git 根目录不一致：script=$RootDir git=$topLevel"
        }

        $currentBranch = (& $script:GitBin branch --show-current 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($currentBranch)) {
            throw "当前处于 detached HEAD，拒绝自动 pull。"
        }
        if ($GitBranch -and $currentBranch -ne $GitBranch) {
            throw "当前分支是 $currentBranch，但 GIT_BRANCH=$GitBranch。"
        }

        $dirty = (& $script:GitBin status --porcelain --untracked-files=no 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { throw "无法检查 Git 工作树：$dirty" }
        if ($dirty) { throw "存在未提交的已跟踪修改，拒绝 git pull：`n$dirty" }

        $targetBranch = if ($GitBranch) { $GitBranch } else { $currentBranch }
        Write-Log "更新代码：git fetch --prune $GitRemote"
        & $script:GitBin fetch --prune $GitRemote
        if ($LASTEXITCODE -ne 0) { throw "git fetch 失败；旧服务保持运行。" }
        Write-Log "更新代码：git pull --ff-only $GitRemote $targetBranch"
        & $script:GitBin pull --ff-only $GitRemote $targetBranch
        if ($LASTEXITCODE -ne 0) { throw "git pull --ff-only 失败；旧服务保持运行。" }
    }
    finally { Pop-Location }
}

function Read-Stamp {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return "" }
    return (Get-Content $Path -Raw).Trim()
}

function Write-Stamp {
    param([string]$Path, [string]$Value)
    Set-Content -Path $Path -Value $Value -Encoding ASCII
}

function Get-BackendFingerprint {
    $pyproject = Join-Path $RootDir "pyproject.toml"
    $pythonVersion = (& $PythonBin --version 2>&1 | Out-String).Trim()
    $pipVersion = (& $PythonBin -m pip --version 2>&1 | Out-String).Trim()
    return Get-Sha256Text ((Get-Content $pyproject -Raw) + "`n$pythonVersion`n$pipVersion`n$BackendExtras")
}

function Get-FrontendFingerprint {
    $lockFile = Join-Path $WebDir "package-lock.json"
    $packageFile = Join-Path $WebDir "package.json"
    $dependencyFile = if (Test-Path $lockFile) { $lockFile } else { $packageFile }
    $npmVersion = (& $NpmBin --version 2>&1 | Out-String).Trim()
    return Get-Sha256Text ((Get-Content $dependencyFile -Raw) + "`n$npmVersion")
}

function Test-BackendImports {
    $extras = ",$BackendExtras,"
    $modules = @("fastapi", "uvicorn")
    if ($extras.Contains(",azure,")) { $modules += @("openai", "azure.identity", "dotenv") }
    if ($extras.Contains(",deepseek,")) { $modules += @("openai", "dotenv") }
    if ($extras.Contains(",aidc,")) { $modules += @("agents", "pydantic", "azure.identity", "dotenv") }
    $modules = $modules | Select-Object -Unique

    $code = @'
import importlib
import sys
for name in dict.fromkeys(sys.argv[1:]):
    importlib.import_module(name)
importlib.import_module("tsgo.web.app")
if "agents" in sys.argv[1:]:
    importlib.import_module("tsgo.aidc_progress")
'@
    $oldPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = if ($oldPythonPath) { (Join-Path $RootDir "src") + ";" + $oldPythonPath } else { Join-Path $RootDir "src" }
    try {
        & $PythonBin -c $code @modules *> $null
        return $LASTEXITCODE -eq 0
    }
    catch { return $false }
    finally { $env:PYTHONPATH = $oldPythonPath }
}

function Install-BackendDependencies {
    $mode = Normalize-Mode $BackendInstall "BACKEND_INSTALL"
    $script:PythonBin = Resolve-CommandPath $PythonBin
    & $script:PythonBin -m pip --version *> $null
    if ($LASTEXITCODE -ne 0) { throw "$PythonBin 缺少 pip。" }

    $fingerprint = Get-BackendFingerprint
    $previous = Read-Stamp $BackendDepsStamp
    $shouldInstall = $mode -eq "always"
    if ($mode -eq "auto") {
        if ($previous -and $previous -ne $fingerprint) {
            Write-Log "pyproject/Python/extras 已变化，需要更新后端依赖"
            $shouldInstall = $true
        }
        elseif (-not (Test-BackendImports)) {
            Write-Log "检测到缺失的后端依赖"
            $shouldInstall = $true
        }
    }

    if ($shouldInstall) {
        Write-Log "安装后端依赖：pip install -e '.[${BackendExtras}]'"
        Push-Location $RootDir
        try {
            & $script:PythonBin -m pip install --disable-pip-version-check -e ".[${BackendExtras}]"
            if ($LASTEXITCODE -ne 0) { throw "后端依赖安装失败。" }
        }
        finally { Pop-Location }
    }
    if (-not (Test-BackendImports)) {
        if ($mode -eq "never") { throw "后端依赖不完整；设置 BACKEND_INSTALL=auto 或手工安装 extras。" }
        throw "后端依赖安装后仍无法导入。"
    }
    Write-Stamp $BackendDepsStamp $fingerprint
}

function Test-FrontendDependencies {
    if (-not (Test-Path (Join-Path $WebDir "node_modules"))) { return $false }
    Push-Location $WebDir
    try {
        & $NpmBin ls --depth=0 *> $null
        return $LASTEXITCODE -eq 0
    }
    finally { Pop-Location }
}

function Install-FrontendDependencies {
    $mode = Normalize-Mode $NpmInstall "NPM_INSTALL"
    $script:NpmBin = Resolve-CommandPath $NpmBin
    $script:NodeBin = Resolve-CommandPath $NodeBin
    $lockFile = Join-Path $WebDir "package-lock.json"
    $fingerprint = Get-FrontendFingerprint
    $previous = Read-Stamp $FrontendDepsStamp
    $shouldInstall = $mode -eq "always"
    if ($mode -eq "auto") {
        if (-not (Test-Path (Join-Path $WebDir "node_modules"))) { $shouldInstall = $true }
        elseif ($previous -and $previous -ne $fingerprint) {
            Write-Log "package-lock/package.json/npm 已变化，需要更新前端依赖"
            $shouldInstall = $true
        }
        elseif (-not (Test-FrontendDependencies)) { $shouldInstall = $true }
    }

    if ($shouldInstall) {
        Write-Log "安装前端依赖"
        Push-Location $WebDir
        try {
            if (Test-Path $lockFile) { & $script:NpmBin ci } else { & $script:NpmBin install }
            if ($LASTEXITCODE -ne 0) { throw "前端依赖安装失败。" }
        }
        finally { Pop-Location }
    }
    if (-not (Test-FrontendDependencies)) {
        if ($mode -eq "never") { throw "前端依赖不完整；设置 NPM_INSTALL=auto。" }
        throw "前端依赖安装后仍不完整。"
    }
    Write-Stamp $FrontendDepsStamp $fingerprint
}

function Build-Frontend {
    if ($SkipBuild) { Write-WarnLog "SKIP_BUILD=1，跳过前端构建"; return }
    Write-Log "构建并校验前端"
    Push-Location $WebDir
    try {
        & $NpmBin run build
        if ($LASTEXITCODE -ne 0) { throw "前端构建失败。" }
    }
    finally { Pop-Location }
}

function Read-PidFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $null }
    $raw = Get-Content $Path -TotalCount 1 -ErrorAction SilentlyContinue
    $parsed = 0
    if ($null -ne $raw -and [int]::TryParse(([string]$raw).Trim(), [ref]$parsed)) { return $parsed }
    return $null
}

function Test-ProcessAlive {
    param([int]$ProcessId)
    return $null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Get-ProcessCommandLine {
    param([int]$ProcessId)
    try {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction Stop
        if ($null -eq $process) { return "" }
        return [string]$process.CommandLine
    }
    catch { return "" }
}

function Test-ProcessMatches {
    param([int]$ProcessId, [string]$Expected)
    return (Get-ProcessCommandLine $ProcessId).IndexOf($Expected, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Stop-ProcessTree {
    param([int]$ProcessId)
    if (-not (Test-ProcessAlive $ProcessId)) { return }
    & taskkill.exe /PID $ProcessId /T /F *> $null
}

function Stop-PidFileProcess {
    param([string]$Name, [string]$PidFile, [string]$Expected)
    $processId = Read-PidFile $PidFile
    if ($null -ne $processId -and (Test-ProcessAlive $processId)) {
        if (-not (Test-ProcessMatches $processId $Expected)) {
            Write-WarnLog "$Name PID 文件指向其他进程，拒绝终止：PID=$processId"
        }
        else {
            Write-Log "停止 $Name，PID=$processId"
            Stop-ProcessTree $processId
        }
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

function Get-PortListenerPids {
    param([int]$Port)
    try {
        return @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop | Select-Object -ExpandProperty OwningProcess -Unique)
    }
    catch {
        $result = @()
        foreach ($line in (& netstat.exe -ano -p tcp 2>$null)) {
            if ($line -match "^\s*TCP\s+\S+:${Port}\s+\S+\s+LISTENING\s+(\d+)\s*$") { $result += [int]$Matches[1] }
        }
        return @($result | Select-Object -Unique)
    }
}

function Release-Port {
    param([string]$Name, [int]$Port, [string]$Expected)
    foreach ($processId in (Get-PortListenerPids $Port)) {
        $commandLine = Get-ProcessCommandLine $processId
        $owned = $commandLine.IndexOf($RootDir, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
        if (-not $owned -and $Expected -eq "uvicorn tsgo.web.app:app") {
            $owned = $commandLine.IndexOf($Expected, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
        }
        if ($owned -or $AllowForceKillPorts) {
            Write-WarnLog "清理 $Name 端口 $Port，PID=$processId"
            Stop-ProcessTree $processId
        }
        else {
            throw "端口 $Port 被其他进程占用：PID=$processId command=$commandLine；使用 -ForceKillPorts 才会强制终止。"
        }
    }
}

function Stop-Services {
    Stop-PidFileProcess "前端" $FrontendPidFile "vite.js"
    Stop-PidFileProcess "后端" $BackendPidFile "uvicorn tsgo.web.app:app"
    Release-Port "前端" $FrontendPort "vite"
    Release-Port "后端" $BackendPort "uvicorn tsgo.web.app:app"
}

function Start-Backend {
    Set-Content $BackendLog "" -Encoding UTF8
    Set-Content $BackendErrorLog "" -Encoding UTF8
    $arguments = @("-m", "uvicorn", "tsgo.web.app:app", "--host", $BackendHost, "--port", "$BackendPort")
    if ($UvicornReload) { $arguments += "--reload" }
    $oldPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = if ($oldPythonPath) { (Join-Path $RootDir "src") + ";" + $oldPythonPath } else { Join-Path $RootDir "src" }
    try {
        $process = Start-Process $PythonBin -ArgumentList $arguments -WorkingDirectory $RootDir -NoNewWindow -PassThru `
            -RedirectStandardOutput $BackendLog -RedirectStandardError $BackendErrorLog
        Set-Content $BackendPidFile $process.Id -Encoding ASCII
    }
    finally { $env:PYTHONPATH = $oldPythonPath }
}

function Start-Frontend {
    Set-Content $FrontendLog "" -Encoding UTF8
    Set-Content $FrontendErrorLog "" -Encoding UTF8
    $vitePath = Join-Path $WebDir "node_modules\vite\bin\vite.js"
    if (-not (Test-Path $vitePath)) { throw "缺少 Vite：$vitePath" }
    $quotedVitePath = '"' + $vitePath + '"'
    $arguments = @($quotedVitePath, "--host", $FrontendHost, "--port", "$FrontendPort")
    $process = Start-Process $NodeBin -ArgumentList $arguments -WorkingDirectory $WebDir -NoNewWindow -PassThru `
        -RedirectStandardOutput $FrontendLog -RedirectStandardError $FrontendErrorLog
    Set-Content $FrontendPidFile $process.Id -Encoding ASCII
}

function Test-HttpReady {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 400
    }
    catch { return $false }
}

function Wait-ForHttp {
    param([string]$Name, [string]$Url, [string]$PidFile)
    $deadline = (Get-Date).AddSeconds($StartupTimeout)
    while ((Get-Date) -lt $deadline) {
        $processId = Read-PidFile $PidFile
        if ($null -eq $processId -or -not (Test-ProcessAlive $processId)) { return $false }
        if (Test-HttpReady $Url) {
            Write-Log "$Name 健康检查通过：$Url"
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Show-ServiceStatus {
    param([string]$Name, [string]$PidFile, [string]$Expected, [string]$Url, [int]$Port)
    $processId = Read-PidFile $PidFile
    $status = "stopped"
    $health = "unavailable"
    if ($null -ne $processId -and (Test-ProcessAlive $processId) -and (Test-ProcessMatches $processId $Expected)) {
        $status = "running"
        $health = if (Test-HttpReady $Url) { "ready" } else { "starting" }
    }
    $pidText = if ($null -eq $processId) { "none" } else { "$processId" }
    Write-Host ("{0,-8} status={1,-7} health={2,-9} pid={3,-8} port={4}" -f $Name, $status, $health, $pidText, $Port)
}

function Show-Status {
    Show-ServiceStatus "后端" $BackendPidFile "uvicorn tsgo.web.app:app" $BackendHealthUrl $BackendPort
    Show-ServiceStatus "前端" $FrontendPidFile "vite.js" $FrontendHealthUrl $FrontendPort
    Write-Host "backend log:       $BackendLog"
    Write-Host "backend error log: $BackendErrorLog"
    Write-Host "frontend log:      $FrontendLog"
    Write-Host "frontend error log:$FrontendErrorLog"
}

function Show-FailureLogs {
    foreach ($path in @($BackendLog, $BackendErrorLog, $FrontendLog, $FrontendErrorLog)) {
        Write-Host "`n===== $path ====="
        if (Test-Path $path) { Get-Content $path -Tail 100 }
    }
}

function Preflight {
    $script:PythonBin = Resolve-CommandPath $PythonBin
    $script:NpmBin = Resolve-CommandPath $NpmBin
    $script:NodeBin = Resolve-CommandPath $NodeBin
    if (-not (Test-Path (Join-Path $RootDir "pyproject.toml"))) { throw "缺少 pyproject.toml" }
    if (-not (Test-Path (Join-Path $WebDir "package.json"))) { throw "缺少 web\package.json" }
}

function Prepare-Runtime {
    Preflight
    Install-BackendDependencies
    Install-FrontendDependencies
    Build-Frontend
}

function Start-Services {
    Release-Port "前端" $FrontendPort "vite"
    Release-Port "后端" $BackendPort "uvicorn tsgo.web.app:app"
    try {
        Start-Backend
        Start-Frontend
    }
    catch {
        Stop-Services
        throw
    }
    if (-not (Wait-ForHttp "后端" $BackendHealthUrl $BackendPidFile)) {
        Show-FailureLogs
        Stop-Services
        throw "后端启动失败。"
    }
    if (-not (Wait-ForHttp "前端" $FrontendHealthUrl $FrontendPidFile)) {
        Show-FailureLogs
        Stop-Services
        throw "前端启动失败。"
    }
    Write-Log "启动完成"
    Show-Status
}

function Restart-Services {
    # 更新、安装和构建失败时，旧服务不会先被停止。
    Invoke-GitUpdate
    Prepare-Runtime
    Stop-Services
    Start-Services
    Write-Log "重启完成"
}

function Install-Dependencies {
    Invoke-GitUpdate
    Preflight
    Install-BackendDependencies
    Install-FrontendDependencies
    Write-Log "代码更新和依赖检查完成"
}

function Invoke-Doctor {
    $failed = $false
    Write-Log "检查 Windows 运行环境"
    foreach ($command in @($GitBin, $PythonBin, $NpmBin, $NodeBin)) {
        try { Write-Log "$command -> $(Resolve-CommandPath $command)" }
        catch { Write-WarnLog $_.Exception.Message; $failed = $true }
    }
    if (-not (Test-BackendImports)) { Write-WarnLog "后端依赖不可导入"; $failed = $true }
    if (-not (Test-FrontendDependencies)) { Write-WarnLog "前端依赖不完整"; $failed = $true }
    if (-not (Test-Path (Join-Path $RootDir ".env"))) { Write-WarnLog "未发现 .env" }
    Show-Status
    if ($failed) { throw "环境检查未通过" }
    Write-Log "环境检查通过"
}

function Show-Logs {
    $paths = @($BackendLog, $BackendErrorLog, $FrontendLog, $FrontendErrorLog)
    foreach ($path in $paths) {
        if (-not (Test-Path $path)) { New-Item -ItemType File -Path $path -Force | Out-Null }
    }
    Write-Host "按 Ctrl+C 退出日志跟踪。"
    Get-Content -Path $paths -Tail 100 -Wait
}

function Show-Usage {
@"
用法：
  powershell -ExecutionPolicy Bypass -File .\scripts\restart_web.ps1 [restart|start|stop|status|logs|install|doctor]
  pwsh -File .\scripts\restart_web.ps1 [restart|start|stop|status|logs|install|doctor]

默认 restart：
  1. 检查已跟踪修改并执行 git fetch --prune + git pull --ff-only
  2. 自动安装/校验后端 extras：web,azure,deepseek,aidc
  3. 自动安装/校验 npm 依赖并执行 npm run build
  4. 只停止本仓库旧 Uvicorn/Vite 进程
  5. 启动后端和前端并执行 HTTP 健康检查

开关：
  -SkipGitPull    跳过 git pull
  -ForceInstall   强制安装 Python/npm 依赖
  -ForceKillPorts 允许终止无关端口进程

环境变量：
  GIT_PULL=auto | always | never
  GIT_REMOTE=origin
  GIT_BRANCH=main
  PYTHON_BIN=python
  NPM_BIN=npm.cmd
  NODE_BIN=node.exe
  BACKEND_EXTRAS=web,azure,deepseek,aidc
  BACKEND_PORT=8000
  FRONTEND_PORT=5173
  BACKEND_HEALTH_PATH=/openapi.json
  FRONTEND_HEALTH_PATH=/
  STARTUP_TIMEOUT=45
"@ | Write-Host
}

try {
    switch ($Action) {
        "restart" { Restart-Services }
        "start" { Invoke-GitUpdate; Prepare-Runtime; Start-Services }
        "stop" { Stop-Services; Show-Status }
        "status" { Show-Status }
        "logs" { Show-Logs }
        "install" { Install-Dependencies }
        "doctor" { Invoke-Doctor }
        "help" { Show-Usage }
    }
}
catch {
    Write-Host ("[{0}] ERROR: {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $_.Exception.Message) -ForegroundColor Red
    exit 1
}
