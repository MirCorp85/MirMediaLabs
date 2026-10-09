# Waits until nobody is rendering, restarts the lab (so code changes go live), then resumes the preview batch.
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
function Idle { try { $s = Invoke-RestMethod http://127.0.0.1:5400/api/status -TimeoutSec 10; return -not $s.running -and -not $s.queued.Count } catch { return $false } }
$quiet = 0
while ($quiet -lt 3) { if (Idle) { $quiet++ } else { $quiet = 0 }; Start-Sleep 10 }   # 30 s with nothing running
Get-NetTCPConnection -LocalPort 5400 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
Start-Sleep 2
& "$root\Start-MirMediaLabs.bat" --server-only
Start-Sleep 10
"lab restarted $(Get-Date)"
& cmd /c "$root\tools\run_all_previews.cmd"
