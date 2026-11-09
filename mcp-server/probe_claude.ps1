# probe
$log = Join-Path $PSScriptRoot "restart_log.txt"
"start $(Get-Date)" | Out-File $log -Encoding utf8
Get-Process | Where-Object { $_.ProcessName -like "*claude*" } | Select-Object Id, StartTime | Format-Table -AutoSize | Out-String -Width 200 | Out-File $log -Append -Encoding utf8
$uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
& $uv --directory $PSScriptRoot run --frozen probe_mcp.py
"done $(Get-Date)" | Out-File $log -Append -Encoding utf8
