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

function Normalize-InstallMode {
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

function Require-Command {
    param([string]$Command)
    $resolved = Get-Command $Command -ErrorAction SilentlyContinue
    if ($null -eq $resolved) { throw "缺少命令：$Command" }
    return $resolved.Source
}

function Get-Sha256Text {
    param([string]$Text)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
        $hash = $sha.ComputeHash($bytes)
        return ([System.BitConverter]::ToString($hash)).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

$RootDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$WebDir = Join-Path $RootDir "web"
$DefaultRunBase = Get-EnvOrDefault "LOCALAPPDATA" (Get-EnvOrDefault "TEMP" $RootDir)
$RunDir = Get-EnvOrDefault "TSGO_RUN_DIR" (Join-Path $DefaultRunBase "tsgo-web")
$LogDir = Get-EnvOrDefault "TSGO_LOG_DIR" (Join-Path $RunDir "logs")
$CacheDir = Get-EnvOrDefault "TSGO_CACHE_DIR" (Join-Path $RunDir "cache")

$PythonBin = Get-EnvOrDefault "PYTHON_BIN" "python"
$NpmBin = Get-EnvOrDefault "NPM_BIN" "npm.cmd"
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
    $mode = Normalize-InstallMode $GitPullMode "GIT_PULL"
    if ($mode -eq "never") {
        Write-Log "GIT_PULL=$GitPullMode，跳过代码更新"
        return
    }

    $gitDirectory = Join-Path $RootDir ".git"
    if (-not (Test-Path $gitDirectory)) {
        if ($mode -eq "always") { throw "当前目录不是 Git checkout：$RootDir" }
        Write-WarnLog "未发现 .git，跳过 git pull"
        return
    }

    $script:GitBin = Require-Command $GitBin
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
        if (-not [string]::IsNullOrWhiteSpace($GitBranch) -and $currentBranch -ne $GitBranch) {
            throw "当前分支是 $currentBranch，但 GIT_BRANCH=$GitBranch；拒绝把其他分支拉入当前工作树。"
        }

        $dirty = (& $script:GitBin status --porcelain --untracked-files=no 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { throw "无法检查 Git 工作树：$dirty" }
        if (-not [string]::IsNullOrWhiteSpace($dirty)) {
            throw "存在未提交的已跟踪修改，拒绝 git pull；请先提交、暂存或恢复这些修改。`n$dirty"
        }

        $targetBranch = if ([string]::IsNullOrWhiteSpace($GitBranch)) { $currentBranch } else { $GitBranch }
        Write-Log "更新代码：git fetch --prune $GitRemote"
        & $script:GitBin fetch --prune $GitRemote
        if ($LASTEXITCODE -ne 0) { throw "git fetch 失败。" }

        Write-Log "更新代码：git pull --ff-only $GitRemote $targetBranch"
        & $script:GitBin pull --ff-only $GitRemote $targetBranch
        if ($LASTEXITCODE -ne 0) { throw "git pull --ff-only 失败；不会停止当前服务。" }
    }
    finally {
        Pop-Location
    }
}

function Get-BackendFingerprint {
    $pyproject = Join-Path $RootDir "pyproject.toml"
    $pythonVersion = (& $PythonBin --version 2>&1 | Out-String).Trim()
    $pipVersion = (& $PythonBin -m pip --version 2>&1 | Out-String).Trim()
    $content = (Get-Content $pyproject -Raw) + "`n$pythonVersion`n$pipVersion`n$BackendExtras"
    return Get-Sha256Text $content
}

function Get-FrontendFingerprint {
    $lockFile = Join-Path $WebDir "package-lock.json"
    $packageFile = Join-Path $WebDir "package.json"
    $dependencyFile = if (Test-Path $lockFile) { $lockFile } else { $packageFile }
    $npmVersion = (& $NpmBin --version 2>&1 | Out-String).Trim()
    return Get-Sha256Text ((Get-Content $dependencyFile -Raw) + "`n$npmVersion")
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

function Test-BackendImports {
    $extras = ",$BackendExtras,"
    $modules = New-Object System.Collections.Generic.List[string]
    $modules.Add("fastapi")
    $modules.Add("uvicorn")
    if ($extras.Contains(",azure,")) {
        @("openai", "azure.identity", "dotenv") | ForEach-Object { $modules.Add($_) }
    }
    if ($extras.Contains(",deepseek,")) {
        @("openai", "dotenv") | ForEach-Object { $modules.Add($_) }
    }
    if ($extras.Contains(",aidc,")) {
        @("agents", "pydantic", "azure.identity", "dotenv") | ForEach-Object { $modules.Add($_) }
    }

    $code = @'
import importlib
import sys

missing = []
for name in dict.fromkeys(sys.argv[1:]):
    try:
        importlib.import_module(name)
    except Exception as exc:
        missing.append(f"{name}: {exc}")
if missing:
    for item in missing:
        print(item, file=sys.stderr)
    raise SystemExit(1)
importlib.import_module("tsgo.web.app")
if "agents" in sys.argv[1:]:
    importlib.import_module("tsgo.aidc_progress")
'@

    $oldPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($oldPythonPath)) {
        Join-Path $RootDir "src"
    } else {
        (Join-Path $RootDir "src") + ";" + $oldPythonPath
    }
    try {
        $moduleArgs = $modules.ToArray()
        $output = & $PythonBin -c $code @moduleArgs 2>&1
        if ($LASTEXITCODE -ne 0) {
            $output | ForEach-Object { Write-WarnLog $_.ToString() }
            return $false
        }
        return $true
    }
    finally {
        $env:PYTHONPATH = $oldPythonPath
    }
}

function Install-BackendDependencies {
    $mode = Normalize-InstallMode $BackendInstall "BACKEND_INSTALL"
    $script:PythonBin = Require-Command $PythonBin
    & $script:PythonBin -m pip --version *> $null
    if ($LASTEXITCODE -ne 0) { throw "$PythonBin 缺少 pip。" }

    $pyproject = Join-Path $RootDir "pyproject.toml"
    if (-not (Test-Path $pyproject)) { throw "缺少 pyproject.toml：$pyproject" }

    $fingerprint = Get-BackendFingerprint
    $previous = Read-Stamp $BackendDepsStamp
    $shouldInstall = $mode -eq "always"
    if ($mode -eq "auto") {
        if (-not [string]::IsNullOrWhiteSpace($previous) -and $previous -ne $fingerprint) {
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
        finally {
            Pop-Location
        }
    }

    if (-not (Test-BackendImports)) {
        if ($mode -eq "never") {
            throw "后端依赖不完整；请运行 python -m pip install -e '.[${BackendExtras}]'，或设置 BACKEND_INSTALL=auto。"
        }
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
    finally {
        Pop-Location
    }
}

function Install-FrontendDependencies {
    $mode = Normalize-InstallMode $NpmInstall "NPM_INSTALL"
    $script:NpmBin = Require-Command $NpmBin
    $packageFile = Join-Path $WebDir "package.json"
    if (-not (Test-Path $packageFile)) { throw "缺少前端 package.json：$packageFile" }

    $fingerprint = Get-FrontendFingerprint
    $previous = Read-Stamp $FrontendDepsStamp
    $shouldInstall = $mode -eq "always"
    if ($mode -eq "auto") {
        if (-not (Test-Path (Join-Path $WebDir "node_modules"))) {
            $shouldInstall = $true
        }
        elseif (-not [string]::IsNullOrWhiteSpace($previous) -and $previous -ne $fingerprint) {
            Write-Log "package-lock/package.json 已变化，需要更新前端依赖"
            $shouldInstall = $true
        }
        elseif (-not (Test-FrontendDependencies)) {
            Write-Log "前端 node_modules 不完整"
            $shouldInstall = $true
        }
    }

    if ($shouldInstall) {
        Write-Log "安装前端依赖"
        Push-Location $WebDir
        try {
            if (Test-Path (Join-Path $WebDir "package-lock.json")) {
                & $script:NpmBin ci
            }
            else {
                & $script:NpmBin install
            }
            if ($LASTEXITCODE -ne 0) { throw "前端依赖安装失败。" }
        }
        finally {
            Pop-Location
        }
    }

    if (-not (Test-FrontendDependencies)) {
        if ($mode -eq "never") {
            throw "前端依赖不完整；请在 web 目录执行 npm install，或设置 NPM_INSTALL=auto。"
        }
        throw "前端依赖安装后仍不完整。"
    }
    Write-Stamp $FrontendDepsStamp $fingerprint
}

function Build-Frontend {
    if ($SkipBuild) {
        Write-Log "SKIP_BUILD=1，跳过前端 TypeScript/Vite 构建校验"
        return
    }
    Write-Log "构建并校验前端"
    Push-Location $WebDir
    try {
        & $NpmBin run build
        if ($LASTEXITCODE -ne 0) { throw "前端构建失败。" }
    }
    finally {
        Pop-Location
    }
}

function Read-PidFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $null }
    $raw = Get-Content $Path -TotalCount 1 -ErrorAction SilentlyContinue
    if ($null -eq $raw) { return $null }
    $value = ([string]$raw).Trim()
    $parsed = 0
    if ([int]::TryParse($value, [ref]$parsed)) { return $parsed }
    return $null
}

function Test-ProcessAlive {
    param([int]$ProcessId)
    return $null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Get-ProcessCommandLine {
    param([int]$ProcessId)
    try {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
        if ($null -eq $process) { return "" }
        return [string]$process.CommandLine
    }
    catch {
        return ""
    }
}

function Test-ProcessMatches {
    param([int]$ProcessId, [string]$Expected)
    $commandLine = Get-ProcessCommandLine $ProcessId
    return $commandLine.IndexOf($Expected, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Test-ProcessBelongsToRepo {
    param([int]$ProcessId, [string]$Expected)
    $commandLine = Get-ProcessCommandLine $ProcessId
    if ($commandLine.IndexOf($RootDir, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) { return $true }
    if ($Expected -eq "uvicorn tsgo.web.app:app" -and
        $commandLine.IndexOf($Expected, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) { return $true }
    return $false
}

function Stop-ProcessTree {
    param([int]$ProcessId)
    if (-not (Test-ProcessAlive $ProcessId)) { return }
    $taskkill = Get-Command taskkill.exe -ErrorAction SilentlyContinue
    if ($null -ne $taskkill) {
        & $taskkill.Source /PID $ProcessId /T /F *> $null
        return
    }

    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) { Stop-ProcessTree ([int]$child.ProcessId) }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

function Stop-PidFileProcess {
    param([string]$Name, [string]$PidFile, [string]$Expected)
    $processId = Read-PidFile $PidFile
    if ($null -ne $processId -and (Test-ProcessAlive $processId)) {
        if (-not (Test-ProcessMatches $processId $Expected)) {
            Write-WarnLog "$Name PID 文件指向其他进程，拒绝终止：PID=$processId command=$(Get-ProcessCommandLine $processId)"
            Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
            return
        }
        Write-Log "停止 $Name，PID=$processId"
        Stop-ProcessTree $processId
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

function Get-PortListenerPids {
    param([int]$Port)
    $pids = New-Object System.Collections.Generic.List[int]
    try {
        $connections = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop
        foreach ($connection in $connections) {
            if (-not $pids.Contains([int]$connection.OwningProcess)) {
                $pids.Add([int]$connection.OwningProcess)
            }
        }
        return $pids.ToArray()
    }
    catch {
        $lines = & netstat.exe -ano -p tcp 2>$null
        $pattern = "^\s*TCP\s+\S+:${Port}\s+\S+\s+LISTENING\s+(\d+)\s*$"
        foreach ($line in $lines) {
            if ($line -match $pattern) {
                $pidValue = [int]$Matches[1]
                if (-not $pids.Contains($pidValue)) { $pids.Add($pidValue) }
            }
        }
        return $pids.ToArray()
    }
}

function Test-TcpPort {
    param([string]$HostName, [int]$Port)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(500)) { return $false }
        $client.EndConnect($async)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Release-Port {
    param([string]$Name, [int]$Port, [string]$Expected)
    foreach ($processId in (Get-PortListenerPids $Port)) {
        if (Test-ProcessBelongsToRepo $processId $Expected) {
            Write-WarnLog "清理遗留的 $Name 监听进程：PID=$processId port=$Port"
            Stop-ProcessTree $processId
        }
        elseif ($AllowForceKillPorts) {
            Write-WarnLog "FORCE_KILL_PORTS=1，终止无关端口进程：PID=$processId port=$Port"
            Stop-ProcessTree $processId
        }
        else {
            throw "端口 $Port 已被其他进程占用：PID=$processId command=$(Get-ProcessCommandLine $processId)。请释放端口，或显式使用 -ForceKillPorts。"
        }
    }
    if (Test-TcpPort "127.0.0.1" $Port) {
        throw "端口 $Port 仍被占用，但无法安全识别监听进程。"
    }
}

function Stop-Services {
    Stop-PidFileProcess "前端" $FrontendPidFile "npm"
    Stop-PidFileProcess "后端" $BackendPidFile "uvicorn tsgo.web.app:app"
    Release-Port "前端" $FrontendPort "vite"
    Release-Port "后端" $BackendPort "uvicorn tsgo.web.app:app"
}

function Start-Backend {
    @($BackendLog, $BackendErrorLog) | ForEach-Object { Set-Content -Path $_ -Value "" -Encoding UTF8 }
    $arguments = @("-m", "uvicorn", "tsgo.web.app:app", "--host", $BackendHost, "--port", $BackendPort.ToString())
    if ($UvicornReload) { $arguments += "--reload" }

    Write-Log "启动后端：http://${BackendCheckHost}:${BackendPort}"
    $oldPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($oldPythonPath)) {
        Join-Path $RootDir "src"
    } else {
        (Join-Path $RootDir "src") + ";" + $oldPythonPath
    }
    try {
        $process = Start-Process -FilePath $PythonBin -ArgumentList $arguments -WorkingDirectory $RootDir `
            -RedirectStandardOutput $BackendLog -RedirectStandardError $BackendErrorLog -NoNewWindow -PassThru
        Set-Content -Path $BackendPidFile -Value $process.Id -Encoding ASCII
    }
    finally {
        $env:PYTHONPATH = $oldPythonPath
    }
}

function Start-Frontend {
    @($FrontendLog, $FrontendErrorLog) | ForEach-Object { Set-Content -Path $_ -Value "" -Encoding UTF8 }
    $arguments = @("run", "dev", "--", "--host", $FrontendHost, "--port", $FrontendPort.ToString())
    Write-Log "启动前端：http://${FrontendCheckHost}:${FrontendPort}"
    $process = Start-Process -FilePath $NpmBin -ArgumentList $arguments -WorkingDirectory $WebDir `
        -RedirectStandardOutput $FrontendLog -RedirectStandardError $FrontendErrorLog -NoNewWindow -PassThru
    Set-Content -Path $FrontendPidFile -Value $process.Id -Encoding ASCII
}

function Test-HttpReady {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 400
    }
    catch {
        return $false
    }
}

function Wait-ForHttp {
    param([string]$Name, [string]$Url, [string]$PidFile)
    $deadline = (Get-Date).AddSeconds($StartupTimeout)
    while ((Get-Date) -lt $deadline) {
        $processId = Read-PidFile $PidFile
        if ($null -eq $processId -or -not (Test-ProcessAlive $processId)) {
            Write-Log "$Name 进程已提前退出"
            return $false
        }
        if (Test-HttpReady $Url) {
            Write-Log "$Name 健康检查通过：$Url"
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    Write-Log "$Name 在 ${StartupTimeout}s 内未通过健康检查：$Url"
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
    $pidText = if ($null -eq $processId) { "none" } else { $processId.ToString() }
    Write-Host ("{0,-8} status={1,-7} health={2,-9} pid={3,-8} port={4}" -f $Name, $status, $health, $pidText, $Port)
}

function Show-Status {
    Show-ServiceStatus "后端" $BackendPidFile "uvicorn tsgo.web.app:app" $BackendHealthUrl $BackendPort
    Show-ServiceStatus "前端" $FrontendPidFile "npm" $FrontendHealthUrl $FrontendPort
    Write-Host "backend log:       $BackendLog"
    Write-Host "backend error log: $BackendErrorLog"
    Write-Host "frontend log:      $FrontendLog"
    Write-Host "frontend error log:$FrontendErrorLog"
    Write-Host "backend extras:    $BackendExtras"
}

function Show-FailureLogs {
    foreach ($path in @($BackendLog, $BackendErrorLog, $FrontendLog, $FrontendErrorLog)) {
        Write-Host "`n===== $path ====="
        if (Test-Path $path) { Get-Content $path -Tail 100 }
    }
}

function Preflight {
    $script:PythonBin = Require-Command $PythonBin
    $script:NpmBin = Require-Command $NpmBin
    if (-not (Test-Path $WebDir)) { throw "前端目录不存在：$WebDir" }
    if (-not (Test-Path (Join-Path $RootDir "pyproject.toml"))) { throw "pyproject.toml 不存在：$RootDir" }
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
    Start-Backend
    Start-Frontend

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
    # pull、依赖安装和前端构建都发生在停止旧服务之前。
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
    Write-Log "代码更新和依赖检查/安装完成"
}

function Invoke-Doctor {
    $failed = $false
    Write-Log "检查 Windows 运行环境"

    try {
        $resolvedGit = Get-Command $GitBin -ErrorAction Stop
        Write-Log "Git：$($resolvedGit.Source)"
        if (Test-Path (Join-Path $RootDir ".git")) {
            Push-Location $RootDir
            try {
                $branch = (& $resolvedGit.Source branch --show-current 2>&1 | Out-String).Trim()
                $dirty = (& $resolvedGit.Source status --porcelain --untracked-files=no 2>&1 | Out-String).Trim()
                Write-Log "Git branch：$branch"
                if (-not [string]::IsNullOrWhiteSpace($dirty)) { Write-WarnLog "存在未提交的已跟踪修改" }
            }
            finally { Pop-Location }
        }
    }
    catch {
        Write-WarnLog "缺少 Git：$GitBin"
        $failed = $true
    }

    try {
        $script:PythonBin = Require-Command $PythonBin
        & $script:PythonBin -m pip --version *> $null
        if ($LASTEXITCODE -ne 0) { throw "Python 缺少 pip" }
        if (-not (Test-BackendImports)) { throw "后端依赖不可导入" }
        Write-Log "后端依赖可导入"
    }
    catch {
        Write-WarnLog $_.Exception.Message
        $failed = $true
    }

    try {
        $script:NpmBin = Require-Command $NpmBin
        if (-not (Test-FrontendDependencies)) { throw "前端依赖不完整" }
        Write-Log "前端依赖完整"
    }
    catch {
        Write-WarnLog $_.Exception.Message
        $failed = $true
    }

    if (Test-Path (Join-Path $RootDir ".env")) {
        Write-Log "发现本地 .env"
    }
    else {
        Write-WarnLog "未发现 .env；Stage Flow 可运行，Azure/DeepSeek/AIDC 真实模型调用需要配置。"
    }

    Show-Status
    if ($failed) { throw "环境检查未通过。" }
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

默认 restart 流程：
  1. 检查 Git 工作树；存在未提交的已跟踪修改时安全失败
  2. git fetch --prune + git pull --ff-only
  3. 自动安装/校验后端 extras：web,azure,deepseek,aidc
  4. 自动安装/校验 npm 依赖并执行 npm run build
  5. 只停止本仓库的旧 Uvicorn/Vite 进程
  6. 启动后端和前端并执行 HTTP 健康检查

动作：
  restart  更新代码、准备依赖、构建并重启（默认）
  start    更新代码、准备依赖、构建并启动
  stop     停止前后端
  status   显示 PID、端口和 HTTP health
  logs     持续查看前后端 stdout/stderr
  install  更新代码并安装/校验依赖
  doctor   不修改环境，检查 Git、依赖、.env 和服务状态

开关：
  -SkipGitPull    本次不执行 git pull
  -ForceInstall   本次强制重装 Python/npm 依赖
  -ForceKillPorts 明确允许终止无关端口监听进程

常用环境变量：
  GIT_PULL=auto                 # auto / always / never
  GIT_REMOTE=origin
  GIT_BRANCH=                   # 默认当前分支；设置后要求当前分支一致
  PYTHON_BIN=python
  NPM_BIN=npm.cmd
  BACKEND_INSTALL=auto
  BACKEND_EXTRAS=web,azure,deepseek,aidc
  NPM_INSTALL=auto
  BACKEND_PORT=8000
  FRONTEND_PORT=5173
  STARTUP_TIMEOUT=45
  FORCE_KILL_PORTS=0
  TSGO_RUN_DIR=%LOCALAPPDATA%\tsgo-web
"@ | Write-Host
}

try {
    switch ($Action) {
        "restart" { Restart-Services }
        "start" {
            Invoke-GitUpdate
            Prepare-Runtime
            Start-Services
        }
        "stop" {
            Stop-Services
            Show-Status
        }
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
