# Checks isa-profile.md against requirements-register.md in both directions.
#
# The profile is a derived VIEW of the register (R-15-001a). Divergence between the
# two is the failure mode that produced D-03 and D-10 — the same set stated twice
# with different membership — so it is checked mechanically rather than by care.
#
#   1. every requirement ID the profile cites exists in the register
#   2. every requirement in a profile-bearing subsection is cited by the profile
#
# Exit 0 clean, 1 on any finding.  Run from the repository root.

$ErrorActionPreference = 'Stop'
$profileSecs = '15.1','15.3','15.4','15.5','15.6','15.7','15.8','15.9','15.10','15.11','15.12'

$reg = Get-Content requirements-register.md
$regIds = $reg | Select-String -Pattern '^\*\*(R-\d\d-\d+[a-z]?)\*\*' -AllMatches |
          ForEach-Object { $_.Matches[0].Groups[1].Value }

$cited = Select-String -Path isa-profile.md -Pattern 'R-\d\d-\d+[a-z]?' -AllMatches |
         ForEach-Object { $_.Matches } | ForEach-Object { $_.Value } | Sort-Object -Unique

$findings = 0

$dangling = $cited | Where-Object { $_ -notin $regIds }
if ($dangling) {
    $findings += $dangling.Count
    "FAIL: $($dangling.Count) ID(s) cited by the profile but absent from the register:"
    $dangling | ForEach-Object { "       $_" }
} else {
    "ok: all $($cited.Count) cited IDs resolve"
}

$sec = $null; $rows = @()
foreach ($line in $reg) {
    if ($line -match '^### (15\.\d+) ') { $sec = $Matches[1] }
    if ($line -match '^\*\*(R-15-\d+[a-z]?)\*\* (IS|MUST NOT|MUST)') {
        $rows += [pscustomobject]@{ Id = $Matches[1]; Sec = $sec }
    }
}
$uncovered = $rows | Where-Object { $_.Sec -in $profileSecs -and $_.Id -notin $cited }
if ($uncovered) {
    $findings += $uncovered.Count
    "FAIL: $($uncovered.Count) profile-bearing requirement(s) the profile does not carry:"
    $uncovered | ForEach-Object { "       $($_.Id)  [§$($_.Sec)]" }
} else {
    "ok: all profile-bearing requirements are carried"
}

if ($findings) { "`n$findings finding(s)."; exit 1 }
"`nprofile and register agree."
exit 0
