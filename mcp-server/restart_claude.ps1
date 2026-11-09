# Restart Claude Desktop so it picks up new MCP servers
$log = Join-Path $PSScriptRoot "restart_log.txt"
"restart start $(Get-Date)" | Out-File $log -Encoding utf8
try {
  Start-Sleep -Seconds 8
  $app = Get-StartApps | Where-Object { $_.AppID -like "Claude_*" } | Select-Object -First 1
  "app: $($app.AppID)" | Out-File $log -Append -Encoding utf8
  Get-Process -Name "claude" -ErrorAction Stop | Stop-Process -Force -ErrorAction Stop
  "killed $(Get-Date)" | Out-File $log -Append -Encoding utf8
  Start-Sleep -Seconds 4
  Start-Process ("shell:AppsFolder\" + $app.AppID)
  "relaunched $(Get-Date)" | Out-File $log -Append -Encoding utf8
} catch { "ERROR $_" | Out-File $log -Append -Encoding utf8 }
