# Checks the register's derived views against requirements-register.md, both directions.
#
# A derived view (R-15-001a, R-15-100a) restates requirements that live in the register.
# That is the shape which produced D-03 and D-10 — the same set stated twice, with
# different membership — so agreement is checked mechanically rather than by care.
#
#   1. every requirement ID a view cites exists in the register
#   2. every requirement in a view's bearing subsections is cited by that view
#
# Check 2 is the one that earns its keep: on first run it found eight omissions in
# isa-profile.md, five of them the §15.12 timing contracts.
#
# Exit 0 clean, 1 on any finding. Run from the repository root.

$ErrorActionPreference = 'Stop'

$views = @(
    @{ File = 'isa-profile.md'
       Governing = 'R-15-001a'
       Secs = '15.1','15.3','15.4','15.5','15.6','15.7','15.8','15.9','15.10','15.11','15.12' }
    @{ File = 'absence-contract.md'
       Governing = 'R-15-100a'
       Secs = '15.14' }
)

$reg = Get-Content requirements-register.md
$regIds = $reg | Select-String -Pattern '^\*\*(R-\d\d-\d+[a-z]?)\*\*' -AllMatches |
          ForEach-Object { $_.Matches[0].Groups[1].Value }

# requirement id -> owning §15 subsection
$sec = $null; $owner = @{}
foreach ($line in $reg) {
    if ($line -match '^### (15\.\d+) ') { $sec = $Matches[1] }
    if ($line -match '^\*\*(R-15-\d+[a-z]?)\*\* (IS|MUST NOT|MUST)') { $owner[$Matches[1]] = $sec }
}

$findings = 0
foreach ($v in $views) {
    "--- $($v.File)  (per $($v.Governing)) ---"
    if (-not (Test-Path $v.File)) { "FAIL: missing"; $findings++; continue }

    $cited = Select-String -Path $v.File -Pattern 'R-\d\d-\d+[a-z]?' -AllMatches |
             ForEach-Object { $_.Matches } | ForEach-Object { $_.Value } | Sort-Object -Unique

    $dangling = $cited | Where-Object { $_ -notin $regIds }
    if ($dangling) {
        $findings += $dangling.Count
        "FAIL: $($dangling.Count) ID(s) cited but absent from the register:"
        $dangling | ForEach-Object { "       $_" }
    } else {
        "ok: all $($cited.Count) cited IDs resolve"
    }

    $uncovered = $owner.Keys | Where-Object { $owner[$_] -in $v.Secs -and $_ -notin $cited } | Sort-Object
    if ($uncovered) {
        $findings += @($uncovered).Count
        "FAIL: $(@($uncovered).Count) bearing requirement(s) not carried:"
        $uncovered | ForEach-Object { "       $_  [§$($owner[$_])]" }
    } else {
        "ok: all bearing requirements are carried"
    }
    ""
}

if ($findings) { "$findings finding(s)."; exit 1 }
"views and register agree."
exit 0
