# loop.ps1 — outer loop for the Discovery PoC Orchestrator (Windows PowerShell)
#
# Usage: .\loops\loop.ps1
# Runs Bob Shell iterations until all tasks in IMPLEMENTATION_PLAN.md are done.

$ErrorActionPreference = "Stop"

# ── Resolve repo root ─────────────────────────────────────────────────────────
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot   = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$PlanFile   = Join-Path $RepoRoot "loops\IMPLEMENTATION_PLAN.md"
$MaxIter    = 20
$Iteration  = 0

Write-Host "======================================================"
Write-Host "  Discovery PoC Orchestrator — Agentic Build Loop"
Write-Host "======================================================"
Write-Host ""

# ── Setup Bob Shell (once, before the loop) ───────────────────────────────────
& (Join-Path $RepoRoot ".bob\skills\generate-loop\scripts\setup.ps1")

# ── Ensure we are on a feature branch ────────────────────────────────────────
$CurrentBranch = git -C $RepoRoot rev-parse --abbrev-ref HEAD 2>$null
if ($CurrentBranch -eq "main" -or $CurrentBranch -eq "master") {
    $BranchName = "feature/poc-orchestrator-loop"
    Write-Host "Creating branch: $BranchName"
    git -C $RepoRoot checkout -b $BranchName 2>$null
    if ($LASTEXITCODE -ne 0) {
        git -C $RepoRoot checkout $BranchName
    }
}

while ($true) {
    # ── DONE CHECK ────────────────────────────────────────────────────────────
    if (Test-Path $PlanFile) {
        $content = Get-Content $PlanFile -Raw
        if ($content -notmatch "- \[ \]") {
            Write-Host ""
            Write-Host "✅ All tasks complete — no remaining '- [ ]' items in $PlanFile"
            Write-Host "Discovery PoC Orchestrator build loop finished."
            break
        }
    }

    # ── MAX ITERATIONS CHECK ──────────────────────────────────────────────────
    if ($Iteration -ge $MaxIter) {
        Write-Host ""
        Write-Host "🛑 Reached max iterations: $MaxIter"
        Write-Host "Run the loop again to continue where it left off."
        break
    }

    Write-Host ""
    Write-Host "------ Iteration $Iteration ------"

    $IterScript = Join-Path $RepoRoot "loops\iteration.sh"
    bash $IterScript $Iteration

    $Iteration++
}
