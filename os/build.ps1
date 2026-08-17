# ===========================================================================
# build.ps1 - Karen OS build launcher for Windows
# Works with: WSL2 (if available) OR VirtualBox VM OR cloud (GitHub Actions)
# ===========================================================================
$ErrorActionPreference = "Stop"
$project = (Get-Location).Path
$script = "$project\os\scripts\build-in-vm.sh"

Write-Host ""
Write-Host "  ==================================================" -ForegroundColor Red
Write-Host "   KAREN OS - ISO BUILDER (Windows launcher)" -ForegroundColor White
Write-Host "  ==================================================" -ForegroundColor Red
Write-Host ""

# --- 1) try WSL2 --------------------------------------------------------------
$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if ($wsl) {
    $sysd = wsl -- bash -c "test -d /run/systemd/system && echo YES || echo NO" 2>$null | Select-Object -Last 1
    if ($sysd -eq "YES") {
        Write-Host "==> WSL2 found with systemd. Building inside WSL..." -ForegroundColor Green
        wsl -- bash -c "bash /mnt/$($project -replace '\\','/' -replace '^[A-Z]:','' | ForEach-Object { $_.ToLower() })/os/scripts/build-in-vm.sh"
        exit $LASTEXITCODE
    } else {
        Write-Host "==> WSL found but no systemd (needed by mkarchiso)." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "No usable WSL on this machine (Optimum 11 strips the WSL payload)." -ForegroundColor Yellow
Write-Host "Choose one of these instead:"
Write-Host ""
Write-Host "  [1] VirtualBox VM  (free, easy)  -> docs/VM-BUILD.md"
Write-Host "  [2] GitHub Actions cloud build    -> README.md section 'Cloud build'"
Write-Host "  [3] WSL repair from Win11 ISO     -> docs/OPTIMUM11-WSL-FIX.md"
Write-Host ""
Write-Host "All OS sources are ready in .\os\  — no files missing." -ForegroundColor Green