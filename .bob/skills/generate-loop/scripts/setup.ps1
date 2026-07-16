# setup.ps1 — Bob Shell setup script (Windows PowerShell)
# Usage: .\setup.ps1 [-EnvFile <path>]   (default env file: .env in cwd)
param(
    [string]$EnvFile = ".env"
)
$ErrorActionPreference = "Stop"

# ── Colour helpers ─────────────────────────────────────────────────────────────
function Info  { param([string]$Msg) Write-Host "[setup] $Msg" -ForegroundColor Green }
function Warn  { param([string]$Msg) Write-Host "[setup] $Msg" -ForegroundColor Yellow }
function Err   { param([string]$Msg) Write-Error "[setup] ERROR: $Msg" }

# ── Load .env ──────────────────────────────────────────────────────────────────
$envVars = @{}
if (Test-Path $EnvFile) {
    Info "Loading environment from $EnvFile"
    # Strip leading non-printable / escape characters (e.g. VS Code shell-integration sequences)
    # before parsing, mirroring the sed strip in setup.sh.
    Get-Content $EnvFile | ForEach-Object { $_ -replace '^[^A-Za-z#]*([A-Za-z])', '$1' } |
        Where-Object { $_ -match '^[A-Za-z_][A-Za-z0-9_]*=' } | ForEach-Object {
        $parts = $_ -split '=', 2
        $key   = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"')
        $envVars[$key] = $value
        [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
} else {
    Warn ".env file not found at '$EnvFile'. Continuing without it."
}

# ── Fall back to git config for GIT_USER_EMAIL / GIT_USER_NAME ────────────────
function Get-GitConfig { param([string]$Key)
    try { $v = & git config --global $Key 2>$null; if (-not $v) { $v = & git config $Key 2>$null }; return $v } catch { return "" }
}
if (-not [System.Environment]::GetEnvironmentVariable("GIT_USER_EMAIL")) {
    $val = Get-GitConfig "user.email"
    if ($val) { [System.Environment]::SetEnvironmentVariable("GIT_USER_EMAIL", $val, "Process"); Info "GIT_USER_EMAIL read from git config: $val" }
}
if (-not [System.Environment]::GetEnvironmentVariable("GIT_USER_NAME")) {
    $val = Get-GitConfig "user.name"
    if ($val) { [System.Environment]::SetEnvironmentVariable("GIT_USER_NAME", $val, "Process"); Info "GIT_USER_NAME read from git config: $val" }
}

# ── Validate required env vars ─────────────────────────────────────────────────
$required = @("BOBSHELL_API_KEY")
$missing  = @()
foreach ($var in $required) {
    if (-not [System.Environment]::GetEnvironmentVariable($var)) { $missing += $var }
}
if (-not [System.Environment]::GetEnvironmentVariable("GIT_USER_EMAIL")) { $missing += "GIT_USER_EMAIL (not set in .env and not found in git config)" }
if (-not [System.Environment]::GetEnvironmentVariable("GIT_USER_NAME"))  { $missing += "GIT_USER_NAME (not set in .env and not found in git config)" }
if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "[setup] ERROR: The following required values are missing:" -ForegroundColor Red
    foreach ($v in $missing) { Write-Host "    * $v" -ForegroundColor Red }
    Write-Host ""
    Write-Host "  Copy the template and fill in the missing values:"
    Write-Host "    copy .bob\skills\generate-loop\assets\.env-template .env"
    Write-Host "  Then re-run: .\setup.ps1"
    exit 1
}
Info "All required environment variables are present."

# ── Required minimum version ───────────────────────────────────────────────────
$RequiredVersion = "1.0.6"

# ── Helper: get current installed bob version ──────────────────────────────────
function Get-BobVersion {
    try {
        $raw = & bob --version 2>&1 | Select-String -Pattern '\d+\.\d+\.\d+' | Select-Object -First 1
        if ($raw) { return ($raw -replace '.*?(\d+\.\d+\.\d+).*', '$1') }
    } catch {}
    return ""
}

# ── Install bob ────────────────────────────────────────────────────────────────
function Install-Bob {
    Info "Installing Bob Shell …"
    powershell -ep Bypass 'irm -Uri "https://bob.ibm.com/download/bobshell.ps1" | iex'
}

$currentVersion = Get-BobVersion
if ($currentVersion -eq "") {
    Install-Bob
} elseif ($currentVersion -ne $RequiredVersion) {
    Warn "Found bob $currentVersion, required $RequiredVersion. Re-installing …"
    Install-Bob
} else {
    Info "bob $currentVersion is already installed and up to date."
}

# ── Final verification ─────────────────────────────────────────────────────────
$finalVersion = Get-BobVersion
if ($finalVersion -ne $RequiredVersion) {
    Err "Installation failed — expected bob $RequiredVersion, got '$finalVersion'."
    exit 1
}

$gitEmail = [System.Environment]::GetEnvironmentVariable("GIT_USER_EMAIL")
$gitName  = [System.Environment]::GetEnvironmentVariable("GIT_USER_NAME")
Info "✅ Bob Shell $RequiredVersion is ready."
Info "   BOBSHELL_API_KEY is configured. GIT_USER_EMAIL=$gitEmail, GIT_USER_NAME=$gitName"
