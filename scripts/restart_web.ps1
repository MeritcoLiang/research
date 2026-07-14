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

function Env([string]$Name, [string]$Default) {
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value.Trim()
}

function Is-True([string]$Value) {
    return @("1", "true", "yes", "on") -contains $Value.Trim().ToLowerInvariant()
}

function Install-Mode([string]$Value, [string]$Name) {
    switch ($Value.Trim().ToLowerInvariant()) {
        "auto" { return "auto" }
        { @("1", "true", "yes", "on", "always") -contains $_ } { return "always" }
        { @("0", "false", "no", "off", "never") -contains $_ } { return "never" }
        default { throw "$Name 只能是 auto、always/1 或 never/0，当前值：$Value" }
    }
}

function Log([string]$Message) {
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message)
}

function Warn([string]$Message) {
    Write-Host ("[{0}] WARN: {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message) -ForegroundColor Yellow
}

function Resolve-Command([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) { throw "缺少命令：$Name" }
    if (-not [string]::IsNullOrWhiteSpace([string]$command.Path)) { return $command.Path }
    if (-not [string]::IsNullOrWhiteSpace([string]$command.Source)) { return $command.Source }
    return $command.Name
}

$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$Web = Join-Path $Root "web"
$RunBase = Env "LOCALAPPDATA" (Env "TEMP" $Root)
$RunDir = Env "TSGO_RUN_DIR" (Join-Path $RunBase "tsgo-web")
$LogDir = Env "TSGO_LOG_DIR" (Join-Path $RunDir "logs")
$CacheDir = Env "TSGO_CACHE_DIR" (Join-Path $RunDir "cache")

$Python = Env "PYTHON_BIN" "python"
$Npm = Env "NPM_BIN" "npm.cmd"
$Node = Env "NODE_BIN" "node.exe"
$Git = Env "GIT_BIN" "git.exe"
$BackendHost = Env "BACKEND_HOST" "0.0.0.0"
$BackendPort = [int](Env "BACKEND_PORT" "8000")
$FrontendHost = Env "FRONTEND_HOST" "0.0.0.0"
$FrontendPort = [int](Env "FRONTEND_PORT" "5173")
$BackendCheckHost = Env "BACKEND_CHECK_HOST" "127.0.0.1"
$FrontendCheckHost = Env "FRONTEND_CHECK_HOST" "127.0.0.1"
$StartupTimeout = [int](Env "STARTUP_TIMEOUT" "45")
$BackendExtras = ((Env "BACKEND_EXTRAS" "web,azure,deepseek,aidc") -replace "\s", "").ToLowerInvariant()
$BackendInstall = if ($ForceInstall) { "always" } else { Env "BACKEND_INSTALL" "auto" }
$NpmInstall = if ($ForceInstall) { "always" } else { Env "NPM_INSTALL" "auto" }
$SkipBuild = Is-True (Env "SKIP_BUILD" "0")
$Reload = Is-True (Env "UVICORN_RELOAD" "0")
$AllowPortKill = $ForceKillPorts -or (Is-True (Env "FORCE_KILL_PORTS" "0"))
$GitPull = if ($SkipGitPull) { "never" } else { Env "GIT_PULL" "auto" }
$GitRemote = Env "GIT_REMOTE" "origin"
$GitBranch = Env "GIT_BRANCH" ""

$BackendPid = Join-Path $RunDir "backend.pid"
$FrontendPid = Join-Path $RunDir "frontend.pid"
$BackendLog = Join-Path $LogDir "backend.log"
$BackendErr = Join-Path $LogDir "backend.error.log"
$FrontendLog = Join-Path $LogDir "frontend.log"
$FrontendErr = Join-Path $LogDir "frontend.error.log"
$BackendStamp = Join-Path $CacheDir "backend-deps.stamp"
$FrontendStamp = Join-Path $CacheDir "frontend-deps.stamp"
$BackendUrl = "http://${BackendCheckHost}:${BackendPort}/openapi.json"
$FrontendUrl = "http://${FrontendCheckHost}:${FrontendPort}/"

@($RunDir, $LogDir, $CacheDir) | ForEach-Object {
    New-Item -ItemType Directory -Path $_ -Force | Out-Null
}

function Invoke-GitUpdate {
    $mode = Install-Mode $GitPull "GIT_PULL"
    if ($mode -eq "never") { Log "跳过 git pull"; return }
    if (-not (Test-Path (Join-Path $Root ".git"))) {
        if ($mode -eq "always") { throw "当前目录不是 Git checkout：$Root" }
        Warn "未发现 .git，跳过代码更新"
        return
    }

    $script:Git = Resolve-Command $Git
    Push-Location $Root
    try {
        $branch = (& $script:Git branch --show-current 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($branch)) {
            throw "当前处于 detached HEAD，拒绝自动 pull。"
        }
        if ($GitBranch -and $GitBranch -ne $branch) {
            throw "当前分支是 $branch，但 GIT_BRANCH=$GitBranch。"
        }
        $dirty = (& $script:Git status --porcelain --untracked-files=no 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { throw "无法检查 Git 工作树。" }
        if ($dirty) { throw "存在未提交的已跟踪修改，拒绝 git pull：`n$dirty" }

        $target = if ($GitBranch) { $GitBranch } else { $branch }
        Log "git fetch --prune $GitRemote"
        & $script:Git fetch --prune $GitRemote
        if ($LASTEXITCODE -ne 0) { throw "git fetch 失败；旧服务保持运行。" }
        Log "git pull --ff-only $GitRemote $target"
        & $script:Git pull --ff-only $GitRemote $target
        if ($LASTEXITCODE -ne 0) { throw "git pull --ff-only 失败；旧服务保持运行。" }
    }
    finally { Pop-Location }
}

function Test-BackendImports {
    $modules = @("fastapi", "uvicorn")
    $extras = ",$BackendExtras,"
    if ($extras.Contains(",azure,")) { $modules += @("openai", "azure.identity", "dotenv") }
    if ($extras.Contains(",deepseek,")) { $modules += @("openai", "dotenv") }
    if ($extras.Contains(",aidc,")) { $modules += @("agents", "pydantic", "azure.identity", "dotenv") }
    $modules = $modules | Select-Object -Unique

    $code = 'import importlib,sys; [importlib.import_module(x) for x in sys.argv[1:]]; importlib.import_module("tsgo.web.app"); importlib.import_module("tsgo.aidc_progress") if "agents" in sys.argv[1:] else None'
    $old = $env:PYTHONPATH
    $env:PYTHONPATH = if ($old) { (Join-Path $Root "src") + ";" + $old } else { Join-Path $Root "src" }
    try {
        & $Python -c $code @modules *> $null
        return $LASTEXITCODE -eq 0
    }
    finally { $env:PYTHONPATH = $old }
}

function Need-Install([string]$Mode, [string]$Stamp, [string[]]$Files, [scriptblock]$Check) {
    $normalized = Install-Mode $Mode "install mode"
    if ($normalized -eq "always") { return $true }
    if ($normalized -eq "never") { return $false }
    if (-not (& $Check)) { return $true }
    if (-not (Test-Path $Stamp)) { return $false }
    $stampTime = (Get-Item $Stamp).LastWriteTimeUtc
    foreach ($file in $Files) {
        if ((Test-Path $file) -and (Get-Item $file).LastWriteTimeUtc -gt $stampTime) { return $true }
    }
    return $false
}

function Install-Backend {
    $script:Python = Resolve-Command $Python
    & $script:Python -m pip --version *> $null
    if ($LASTEXITCODE -ne 0) { throw "Python 缺少 pip。" }
    $pyproject = Join-Path $Root "pyproject.toml"
    $need = Need-Install $BackendInstall $BackendStamp @($pyproject) { Test-BackendImports }
    if ($need) {
        Log "pip install -e '.[${BackendExtras}]'"
        Push-Location $Root
        try {
            & $script:Python -m pip install --disable-pip-version-check -e ".[${BackendExtras}]"
            if ($LASTEXITCODE -ne 0) { throw "后端依赖安装失败。" }
        }
        finally { Pop-Location }
    }
    if (-not (Test-BackendImports)) {
        throw "后端依赖不完整；运行 python -m pip install -e '.[${BackendExtras}]'。"
    }
    Set-Content $BackendStamp (Get-Date -Format o) -Encoding ASCII
}

function Test-FrontendDeps {
    if (-not (Test-Path (Join-Path $Web "node_modules"))) { return $false }
    Push-Location $Web
    try { & $Npm ls --depth=0 *> $null; return $LASTEXITCODE -eq 0 }
    finally { Pop-Location }
}

function Install-Frontend {
    $script:Npm = Resolve-Command $Npm
    $script:Node = Resolve-Command $Node
    $package = Join-Path $Web "package.json"
    $lock = Join-Path $Web "package-lock.json"
    $need = Need-Install $NpmInstall $FrontendStamp @($package, $lock) { Test-FrontendDeps }
    if ($need) {
        Log "安装前端依赖"
        Push-Location $Web
        try {
            if (Test-Path $lock) { & $script:Npm ci } else { & $script:Npm install }
            if ($LASTEXITCODE -ne 0) { throw "前端依赖安装失败。" }
        }
        finally { Pop-Location }
    }
    if (-not (Test-FrontendDeps)) { throw "前端依赖不完整。" }
    Set-Content $FrontendStamp (Get-Date -Format o) -Encoding ASCII
}

function Build-Frontend {
    if ($SkipBuild) { Warn "SKIP_BUILD=1，跳过前端构建"; return }
    Log "npm run build"
    Push-Location $Web
    try { & $Npm run build; if ($LASTEXITCODE -ne 0) { throw "前端构建失败。" } }
    finally { Pop-Location }
}

function Read-Pid([string]$Path) {
    if (-not (Test-Path $Path)) { return $null }
    $raw = Get-Content $Path -TotalCount 1 -ErrorAction SilentlyContinue
    $value = 0
    if ($null -ne $raw -and [int]::TryParse(([string]$raw).Trim(), [ref]$value)) { return $value }
    return $null
}

function Alive([int]$Id) { return $null -ne (Get-Process -Id $Id -ErrorAction SilentlyContinue) }

function Command-Line([int]$Id) {
    try { return [string](Get-CimInstance Win32_Process -Filter "ProcessId=$Id" -ErrorAction Stop).CommandLine }
    catch { return "" }
}

function Stop-Tree([int]$Id) {
    if (-not (Alive $Id)) { return }
    & taskkill.exe /PID $Id /T /F *> $null
}

function Stop-Recorded([string]$Name, [string]$PidFile, [string]$Expected) {
    $id = Read-Pid $PidFile
    if ($null -ne $id -and (Alive $id)) {
        $line = Command-Line $id
        if ($line.IndexOf($Expected, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
            Warn "$Name PID 文件已失效，拒绝终止 PID=$id"
        } else {
            Log "停止 $Name，PID=$id"
            Stop-Tree $id
        }
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

function Listener-Pids([int]$Port) {
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

function Release-Port([string]$Name, [int]$Port, [string]$Expected) {
    foreach ($id in (Listener-Pids $Port)) {
        $line = Command-Line $id
        $owned = $line.IndexOf($Root, [StringComparison]::OrdinalIgnoreCase) -ge 0
        if (-not $owned -and $Expected -eq "uvicorn tsgo.web.app:app") {
            $owned = $line.IndexOf($Expected, [StringComparison]::OrdinalIgnoreCase) -ge 0
        }
        if ($owned -or $AllowPortKill) {
            Warn "清理 $Name 端口 $Port，PID=$id"
            Stop-Tree $id
        } else {
            throw "端口 $Port 被其他进程占用：PID=$id command=$line；使用 -ForceKillPorts 才会强制终止。"
        }
    }
}

function Stop-Services {
    Stop-Recorded "前端" $FrontendPid "vite.js"
    Stop-Recorded "后端" $BackendPid "uvicorn tsgo.web.app:app"
    Release-Port "前端" $FrontendPort "vite"
    Release-Port "后端" $BackendPort "uvicorn tsgo.web.app:app"
}

function Start-Backend {
    Set-Content $BackendLog ""; Set-Content $BackendErr ""
    $args = @("-m", "uvicorn", "tsgo.web.app:app", "--host", $BackendHost, "--port", "$BackendPort")
    if ($Reload) { $args += "--reload" }
    $old = $env:PYTHONPATH
    $env:PYTHONPATH = if ($old) { (Join-Path $Root "src") + ";" + $old } else { Join-Path $Root "src" }
    try {
        $process = Start-Process $Python -ArgumentList $args -WorkingDirectory $Root -NoNewWindow -PassThru `
            -RedirectStandardOutput $BackendLog -RedirectStandardError $BackendErr
        Set-Content $BackendPid $process.Id -Encoding ASCII
    }
    finally { $env:PYTHONPATH = $old }
}

function Start-Frontend {
    Set-Content $FrontendLog ""; Set-Content $FrontendErr ""
    $vite = Join-Path $Web "node_modules\vite\bin\vite.js"
    if (-not (Test-Path $vite)) { throw "缺少 Vite：$vite" }
    $process = Start-Process $Node -ArgumentList @($vite, "--host", $FrontendHost, "--port", "$FrontendPort") `
        -WorkingDirectory $Web -NoNewWindow -PassThru -RedirectStandardOutput $FrontendLog -RedirectStandardError $FrontendErr
    Set-Content $FrontendPid $process.Id -Encoding ASCII
}

function Http-Ready([string]$Url) {
    try {
        $response = Invoke-WebRequest $Url -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 400
    }
    catch { return $false }
}

function Wait-Ready([string]$Name, [string]$Url, [string]$PidFile) {
    $until = (Get-Date).AddSeconds($StartupTimeout)
    while ((Get-Date) -lt $until) {
        $id = Read-Pid $PidFile
        if ($null -eq $id -or -not (Alive $id)) { return $false }
        if (Http-Ready $Url) { Log "$Name 健康检查通过：$Url"; return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Service-Status([string]$Name, [string]$PidFile, [string]$Expected, [string]$Url, [int]$Port) {
    $id = Read-Pid $PidFile
    $status = "stopped"; $health = "unavailable"
    if ($null -ne $id -and (Alive $id) -and (Command-Line $id).Contains($Expected)) {
        $status = "running"; $health = if (Http-Ready $Url) { "ready" } else { "starting" }
    }
    $pidText = if ($null -eq $id) { "none" } else { "$id" }
    Write-Host ("{0,-8} status={1,-7} health={2,-9} pid={3,-8} port={4}" -f $Name, $status, $health, $pidText, $Port)
}

function Status {
    Service-Status "后端" $BackendPid "uvicorn tsgo.web.app:app" $BackendUrl $BackendPort
    Service-Status "前端" $FrontendPid "vite.js" $FrontendUrl $FrontendPort
    Write-Host "logs: $LogDir"
}

function Show-Logs {
    $files = @($BackendLog, $BackendErr, $FrontendLog, $FrontendErr)
    $files | ForEach-Object { if (-not (Test-Path $_)) { New-Item -ItemType File $_ | Out-Null } }
    Get-Content $files -Tail 100 -Wait
}

function Preflight {
    $script:Python = Resolve-Command $Python
    $script:Npm = Resolve-Command $Npm
    $script:Node = Resolve-Command $Node
    if (-not (Test-Path (Join-Path $Root "pyproject.toml"))) { throw "缺少 pyproject.toml" }
    if (-not (Test-Path (Join-Path $Web "package.json"))) { throw "缺少 web\package.json" }
}

function Prepare-Runtime {
    Preflight
    Install-Backend
    Install-Frontend
    Build-Frontend
}

function Start-Services {
    Release-Port "前端" $FrontendPort "vite"
    Release-Port "后端" $BackendPort "uvicorn tsgo.web.app:app"
    Start-Backend
    Start-Frontend
    if (-not (Wait-Ready "后端" $BackendUrl $BackendPid)) { Stop-Services; throw "后端启动失败，查看 $BackendErr" }
    if (-not (Wait-Ready "前端" $FrontendUrl $FrontendPid)) { Stop-Services; throw "前端启动失败，查看 $FrontendErr" }
    Status
}

function Restart-Services {
    Invoke-GitUpdate
    Prepare-Runtime
    Stop-Services
    Start-Services
}

function Install-Dependencies {
    Invoke-GitUpdate
    Preflight
    Install-Backend
    Install-Frontend
}

function Doctor {
    $failed = $false
    foreach ($command in @($Git, $Python, $Npm, $Node)) {
        try { Log "$command -> $(Resolve-Command $command)" } catch { Warn $_.Exception.Message; $failed = $true }
    }
    if (-not (Test-BackendImports)) { Warn "后端依赖不可导入"; $failed = $true }
    if (-not (Test-FrontendDeps)) { Warn "前端依赖不完整"; $failed = $true }
    if (-not (Test-Path (Join-Path $Root ".env"))) { Warn "未发现 .env" }
    Status
    if ($failed) { throw "环境检查未通过" }
}

function Usage {
@"
用法：
  powershell -ExecutionPolicy Bypass -File .\scripts\restart_web.ps1 [restart|start|stop|status|logs|install|doctor]
  pwsh -File .\scripts\restart_web.ps1 [restart|start|stop|status|logs|install|doctor]

默认 restart：
  git fetch --prune + git pull --ff-only
  -> pip/npm 依赖检查
  -> npm run build
  -> 安全停止旧服务
  -> 启动 Uvicorn/Vite
  -> HTTP 健康检查

开关：
  -SkipGitPull    跳过 git pull
  -ForceInstall   强制安装 Python/npm 依赖
  -ForceKillPorts 允许终止无关端口进程

环境变量：
  GIT_PULL=auto | always | never
  GIT_REMOTE=origin
  GIT_BRANCH=main              # 可选；设置后要求当前分支一致
  PYTHON_BIN=python
  NPM_BIN=npm.cmd
  NODE_BIN=node.exe
  BACKEND_EXTRAS=web,azure,deepseek,aidc
  BACKEND_PORT=8000
  FRONTEND_PORT=5173
"@ | Write-Host
}

try {
    switch ($Action) {
        "restart" { Restart-Services }
        "start" { Invoke-GitUpdate; Prepare-Runtime; Start-Services }
        "stop" { Stop-Services; Status }
        "status" { Status }
        "logs" { Show-Logs }
        "install" { Install-Dependencies }
        "doctor" { Doctor }
        "help" { Usage }
    }
}
catch {
    Write-Host ("[{0}] ERROR: {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $_.Exception.Message) -ForegroundColor Red
    exit 1
}
