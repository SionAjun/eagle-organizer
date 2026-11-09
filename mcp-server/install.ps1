# Eagle MCP 一键安装：装 uv（没有的话）→ 装依赖 → 写入 Claude Desktop 配置 → 顺带注册 Claude Code / Codex
# 原生命令（uv/claude/codex）往 stderr 打进度，PS 5.1 下用 Stop 会误报错，所以用 Continue + 退出码判断
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
Write-Host ''
Write-Host '== Eagle MCP 安装 ==' -ForegroundColor Cyan

# 1. 代理：Clash 7897 开着就走代理
$proxy = $null
try {
    $tcp = New-Object Net.Sockets.TcpClient
    $tcp.Connect('127.0.0.1', 7897)
    $tcp.Close()
    $proxy = 'http://127.0.0.1:7897'
    $env:HTTP_PROXY = $proxy
    $env:HTTPS_PROXY = $proxy
    $env:NO_PROXY = 'localhost,127.0.0.1'
    [System.Net.WebRequest]::DefaultWebProxy = New-Object System.Net.WebProxy($proxy)
    Write-Host '[1/4] 检测到 Clash 7897，下载走代理'
} catch {
    Write-Host '[1/4] 没检测到 7897 代理，直连'
}
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# 2. uv
$uv = $null
$cmd = Get-Command uv -ErrorAction SilentlyContinue
if ($cmd) { $uv = $cmd.Source }
if (-not $uv) {
    $cand = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
    if (Test-Path $cand) { $uv = $cand }
}
if (-not $uv) {
    Write-Host '[2/4] 没找到 uv，用官方脚本安装...'
    try {
        Invoke-Expression (Invoke-RestMethod 'https://astral.sh/uv/install.ps1' -ErrorAction Stop)
    } catch {
        Write-Host "  下载 uv 安装脚本失败: $_"
    }
    $uv = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
    if (-not (Test-Path $uv)) { throw 'uv 安装失败，把这个窗口截图发给 Claude' }
}
Write-Host "[2/4] uv: $uv"

# 3. 依赖（第一次会自动下载 Python 3.13，几分钟）
Write-Host '[3/4] 安装依赖...'
& $uv --directory $here sync --frozen
if ($LASTEXITCODE -ne 0) { throw 'uv sync 失败，把这个窗口截图发给 Claude' }

# 4. 写配置
Write-Host '[4/4] 写入 Claude Desktop 配置...'
& $uv --directory $here run --frozen register_desktop.py $uv $here
if ($LASTEXITCODE -ne 0) { throw '写配置失败，把这个窗口截图发给 Claude' }

# 顺带：Claude Code / Codex（没装就跳过，失败不影响 Desktop）
$serverArgs = @('--directory', $here, 'run', '--frozen', 'main.py')
if (Get-Command claude -ErrorAction SilentlyContinue) {
    try {
        $null = & claude mcp remove eagle --scope user 2>&1
        & claude mcp add eagle --scope user -e PYTHONIOENCODING=utf-8 '--' $uv @serverArgs
        if ($LASTEXITCODE -eq 0) { Write-Host '  Claude Code: 已注册 eagle' } else { Write-Host '  Claude Code: 注册失败（跳过）' }
    } catch { Write-Host '  Claude Code: 注册失败（跳过）' }
}
if (Get-Command codex -ErrorAction SilentlyContinue) {
    try {
        $null = & codex mcp remove eagle 2>&1
        & codex mcp add eagle --env PYTHONIOENCODING=utf-8 '--' $uv @serverArgs
        if ($LASTEXITCODE -eq 0) { Write-Host '  Codex: 已注册 eagle' } else { Write-Host '  Codex: 注册失败（跳过）' }
    } catch { Write-Host '  Codex: 注册失败（跳过）' }
}

Write-Host ''
Write-Host '完成。最后一步：完全退出 Claude Desktop（托盘图标右键 Quit），再打开。' -ForegroundColor Green
