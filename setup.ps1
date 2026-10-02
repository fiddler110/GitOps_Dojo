# Guided Windows setup for GitOps Dojo.
#
# The stack runs in Linux containers and run.sh is a bash script, so on Windows
# it is used from inside WSL2 with Ubuntu. This script gets you that far:
#   1. checks WSL2 and an Ubuntu distro are installed (offers to install them),
#   2. makes sure the repo is cloned inside Ubuntu's Linux home (not on C:),
#   3. runs ./setup.sh there, which installs podman (or docker) and the rest.
# It asks before every change. Run it from PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1

$ErrorActionPreference = 'Stop'

function Step($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "  [ok] $m" -ForegroundColor Green }
function Bad($m)  { Write-Host "  [!!] $m" -ForegroundColor Red }
function Ask($q, $default = 'n') {
    $hint = if ($default -eq 'y') { '[Y/n]' } else { '[y/N]' }
    $r = Read-Host "$q $hint"
    if ([string]::IsNullOrWhiteSpace($r)) { $r = $default }
    return $r -match '^(y|yes)$'
}

Step 'GitOps Dojo Windows setup'

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    Bad 'wsl.exe not found. WSL needs Windows 10 (2004+) or Windows 11.'
    exit 1
}

# wsl.exe prints UTF-16; strip the NULs so the names compare properly.
function Get-Distros {
    $raw = & wsl.exe -l -q 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $raw) { return @() }
    return @($raw | ForEach-Object { ($_ -replace "`0", '').Trim() } | Where-Object { $_ })
}

$distros = Get-Distros
$ubuntu = $distros | Where-Object { $_ -like 'Ubuntu*' } | Select-Object -First 1

if (-not $ubuntu) {
    Bad 'No Ubuntu distro in WSL.'
    Write-Host '  Installing it needs an Administrator PowerShell and usually a reboot:'
    Write-Host '      wsl --install -d Ubuntu' -ForegroundColor DarkGray
    if (Ask '  Run that now?') {
        & wsl.exe --install -d Ubuntu
        Write-Host ''
        Write-Host '  Reboot if Windows asks, open "Ubuntu" from the Start menu once to create your Linux user,' -ForegroundColor Yellow
        Write-Host '  then run this script again.' -ForegroundColor Yellow
    } else {
        Write-Host '  Nothing changed. Install Ubuntu yourself, then run this script again.'
    }
    exit 1
}
Ok "WSL distro: $ubuntu"

# Which repo URL to clone inside Ubuntu? Reuse this checkout's origin if it has one.
$repoDir = 'GitOps_Dojo'
$url = ''
if (Get-Command git.exe -ErrorAction SilentlyContinue) {
    $url = (& git.exe -C $PSScriptRoot remote get-url origin 2>$null)
}

$exists = & wsl.exe -d $ubuntu -- bash -c "test -x ~/$repoDir/setup.sh && echo yes"
if ($exists -match 'yes') {
    Ok "Repo already in Ubuntu at ~/$repoDir"
} else {
    if (-not $url) { $url = Read-Host '  Git URL of this repo (to clone inside Ubuntu)' }
    Write-Host "  The repo must live in Ubuntu's Linux home (~/$repoDir), not under C:\ or /mnt/c:" -ForegroundColor Yellow
    Write-Host '  bind mounts and file permissions break on the Windows drive.' -ForegroundColor Yellow
    if (-not (Ask "  Clone $url into ~/$repoDir in $ubuntu now?" 'y')) {
        Write-Host '  Nothing changed. Clone it inside Ubuntu, run ./setup.sh there.'
        exit 1
    }
    & wsl.exe -d $ubuntu -- bash -c "git clone '$url' ~/$repoDir"
    if ($LASTEXITCODE -ne 0) {
        Bad 'Clone failed (is git installed in Ubuntu: sudo apt-get install -y git? private repo needs credentials).'
        exit 1
    }
}

Step 'Container engine inside Ubuntu'
# One line per tool: "name ok|missing". Same rule as run.sh: podman + podman-compose win, docker is the fallback.
# --exec skips the distro shell (which would expand $c early). No double quotes inside: Windows PowerShell 5.1 strips them when handing the string to wsl.exe.
$probe = & wsl.exe -d $ubuntu --exec bash -c 'for c in podman podman-compose docker; do command -v $c >/dev/null 2>&1 && echo $c ok || echo $c missing; done; docker compose version >/dev/null 2>&1 && echo docker-compose ok || echo docker-compose missing; podman-compose version >/dev/null 2>&1 && echo podman-compose-usable ok || echo podman-compose-usable missing'
$has = @{}
foreach ($l in $probe) { $p = ($l -replace "`0", '').Trim() -split ' '; if ($p.Count -eq 2) { $has[$p[0]] = ($p[1] -eq 'ok') } }
if ($has['podman'] -and $has['podman-compose-usable']) {
    Ok 'podman + podman-compose are installed and usable; run.sh will use podman'
} elseif ($has['docker'] -and $has['docker-compose']) {
    Ok 'docker + compose plugin are installed and usable; run.sh will use docker'
} elseif ($has['podman'] -or $has['docker']) {
    Bad 'An engine is installed but its compose tool is missing or broken. setup.sh will offer to fix it.'
} else {
    Bad 'Neither podman nor docker is installed in Ubuntu. setup.sh will recommend podman + podman-compose.'
}

Step 'Handing over to setup.sh inside Ubuntu (answer its questions here)'
& wsl.exe -d $ubuntu --cd "~/$repoDir" -- bash ./setup.sh --os wsl
exit $LASTEXITCODE
