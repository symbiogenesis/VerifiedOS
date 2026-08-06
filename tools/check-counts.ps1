# Checks every count the documents assert against the artifact it is derived from.
#
# A count is a derived fact: "954 requirements", "twenty-two crown-jewel specifications",
# "sixteen enumerated absences" are all restatements of something a table already holds.
# Restated by hand, they drift silently — which is the same defect class the register's
# sweep 2 names ("what does the register restate that nothing checks?") and the same one
# bookmarks fixed for traces and check-derived-views.ps1 fixed for membership. This is the
# cardinality half: no count is maintained by care, and none is stated in a second place
# without this script deciding the two agree.
#
#   1. every asserted count equals the artifact it derives from
#   2. every claim pattern still matches (a reworded claim fails loudly, never silently)
#   3. the register's Coverage table has exactly one row per normative section
#
# Run with -Fix to rewrite the asserted counts from the artifacts instead of reporting.
#
# Exit 0 clean, 1 on any finding. Run from the repository root.

[CmdletBinding()]
param([switch]$Fix)

$ErrorActionPreference = 'Stop'

# --- the quantities, computed from the artifacts that own them ---------------------

$reg = Get-Content requirements-register.md
$ids = @(); $perSection = [ordered]@{}; $sec = $null; $inDefects = $false; $dcsrRows = 0
foreach ($line in $reg) {
    if ($line -match '^## §(\d+)') {
        $sec = $Matches[1]
        if (-not $perSection.Contains($sec)) { $perSection[$sec] = 0 }
    }
    if ($line -match '^\*\*(R-\d\d-\d+[a-z]?)\*\* (IS|MUST NOT|MUST)') {
        $ids += $Matches[1]
        if ($sec) { $perSection[$sec]++ }
    }
    if ($line -match '^## Extraction defects') { $inDefects = $true }
    if ($inDefects -and $line -match '^\| `') { $dcsrRows++ }
}

$cj = Get-Content crown-jewels.md
$cjRows = @($cj | Where-Object { $_ -match '^\| \d+ \|' })
function Get-Status($row) { (($row -split '\|')[-2]).Trim() }

$isaProfile = Get-Content isa-profile.md
$openCsr = 0; $inOpen = $false
foreach ($line in $isaProfile) {
    if ($line -match '^### 5\.3 ') { $inOpen = $true; continue }
    if ($inOpen -and $line -match '^(##|---)') { $inOpen = $false }
    if ($inOpen -and $line -match '^\| `') { $openCsr++ }
}

$q = [ordered]@{
    'requirements'  = $ids.Count
    'lettered'      = @($ids | Where-Object { $_ -match '[a-z]$' }).Count
    'sections'      = $perSection.Count
    'cj-targets'    = @($reg | Where-Object { $_ -match '^\| `CJ-[A-Z-]+`' }).Count
    'dcsr-rows'     = $dcsrRows
    'open-csr-rows' = $openCsr
    'cj-specs'      = $cjRows.Count
    'cj-authored'   = @($cjRows | Where-Object { (Get-Status $_) -like '*authored*' -and (Get-Status $_) -notlike 'not authored*' -and (Get-Status $_) -notlike 'partial*' }).Count
    'cj-partial'    = @($cjRows | Where-Object { (Get-Status $_) -like 'partial*' }).Count
    'cj-unauthored' = @($cjRows | Where-Object { (Get-Status $_) -like 'not authored*' }).Count
    'cj-theorems'   = @($cj | Where-Object { $_ -match '^\| `CJ-[A-Z-]+` \|' }).Count
    'absences'      = @(Get-Content absence-contract.md | Where-Object { $_ -match '^\| \*\*A-\d+\*\*' }).Count
}

# --- the claims: where each quantity is asserted, and in which style ---------------
# A claim's pattern captures the number alone, so -Fix is a substitution of one token.

$claims = @(
    # the register states its own coverage
    @{ File = 'requirements-register.md'; Q = 'sections';      Style = 'words';  Pattern = '[\w-]+(?= normative sections are extracted)' }
    @{ File = 'requirements-register.md'; Q = 'requirements';  Style = 'digits'; Pattern = '(?<=extracted, at )[\d,]+(?= requirements)' }
    @{ File = 'requirements-register.md'; Q = 'lettered';      Style = 'words';  Pattern = '(?<=Counts include the )[\w-]+(?= letter-suffixed entries)' }
    @{ File = 'requirements-register.md'; Q = 'dcsr-rows';     Style = 'words';  Pattern = '(?<=one, with )[\w-]+(?= rows)' }

    # the crown-jewel inventory states its own status ratio
    @{ File = 'crown-jewels.md'; Q = 'cj-targets';    Style = 'digits'; Pattern = '[\d]+(?= entries, all used)' }
    @{ File = 'crown-jewels.md'; Q = 'cj-theorems';   Style = 'words';  Pattern = '(?<=The remaining )[\w-]+(?= `CJ-` targets name)' }
    @{ File = 'crown-jewels.md'; Q = 'cj-unauthored'; Style = 'words';  Pattern = '[\w-]+(?= of those [\w-]+ are not authored)' }
    @{ File = 'crown-jewels.md'; Q = 'cj-specs';      Style = 'words';  Pattern = '(?<=of those )[\w-]+(?= are not authored)' }
    @{ File = 'crown-jewels.md'; Q = 'cj-targets';    Style = 'digits'; Pattern = '[\d]+(?= targets, every one used)' }
    @{ File = 'crown-jewels.md'; Q = 'cj-targets';    Style = 'digits'; Pattern = '[\d]+(?= coarse targets)' }
    @{ File = 'crown-jewels.md'; Q = 'cj-specs';      Style = 'digits'; Pattern = '[\d]+(?= specifications, per-member)' }
    @{ File = 'crown-jewels.md'; Q = 'cj-authored';   Style = 'words';  Pattern = '[\w-]+(?= of [\w-]+ is authored outright)' }
    @{ File = 'crown-jewels.md'; Q = 'cj-specs';      Style = 'words';  Pattern = '(?<=of )[\w-]+(?= is authored outright)' }
    @{ File = 'crown-jewels.md'; Q = 'cj-partial';    Style = 'words';  Pattern = '(?<=and )[\w-]+(?= more are partial)' }
    @{ File = 'crown-jewels.md'; Q = 'cj-unauthored'; Style = 'words';  Pattern = '(?<=\. )[A-Z][\w-]+(?= are not authored\.)' }
    @{ File = 'crown-jewels.md'; Q = 'cj-specs';      Style = 'words';  Pattern = '(?<=because these )[\w-]+(?= are \*named)' }
    @{ File = 'crown-jewels.md'; Q = 'cj-unauthored'; Style = 'words';  Pattern = '[\w-]+(?= of them are not yet written)' }
    @{ File = 'crown-jewels.md'; Q = 'cj-theorems';   Style = 'words';  Pattern = '(?<=the )[\w-]+(?= theorem targets above cannot start)' }

    # the README summarizes them
    @{ File = 'README.md'; Q = 'sections';      Style = 'words';  Pattern = '(?<=covers all )[\w-]+(?= normative sections)' }
    @{ File = 'README.md'; Q = 'requirements';  Style = 'digits'; Pattern = '(?<=sections as )[\d,]+(?= numbered requirements)' }
    @{ File = 'README.md'; Q = 'dcsr-rows';     Style = 'words';  Pattern = '(?<=whose )[\w-]+(?= rows are surviving CSRs)' }
    @{ File = 'README.md'; Q = 'absences';      Style = 'words';  Pattern = '[\w-]+(?= enumerated absences)' }
    @{ File = 'README.md'; Q = 'cj-specs';      Style = 'words';  Pattern = '(?<=the )[\w-]+(?= specifications the §5 review gate audits)' }
    @{ File = 'README.md'; Q = 'cj-theorems';   Style = 'words';  Pattern = '(?<=plus the )[\w-]+(?= theorem targets)' }

    # the gap catalogue argues from them
    @{ File = 'critique.md'; Q = 'cj-specs';      Style = 'words';  Pattern = '[\w-]+(?= crown-jewel specifications are named)' }
    @{ File = 'critique.md'; Q = 'cj-theorems';   Style = 'words';  Pattern = '[\w-]+(?= theorem targets are named)' }
    @{ File = 'critique.md'; Q = 'cj-specs';      Style = 'words';  Pattern = '(?<=of )[\w-]+(?= crown-jewel specifications, \*\*)' }
    @{ File = 'critique.md'; Q = 'cj-partial';    Style = 'words';  Pattern = '(?<=\(the frozen ISA profile\), )[\w-]+(?= are partial)' }
    @{ File = 'critique.md'; Q = 'cj-unauthored'; Style = 'words';  Pattern = '(?<=\*\*)[\w-]+(?= are not authored\*\*)' }
    @{ File = 'critique.md'; Q = 'cj-theorems';   Style = 'words';  Pattern = '(?<=The )[\w-]+(?= theorem targets each depend)' }
    @{ File = 'critique.md'; Q = 'cj-unauthored'; Style = 'words';  Pattern = '[\w-]+(?= of those premises do not exist)' }
    @{ File = 'critique.md'; Q = 'dcsr-rows';     Style = 'words';  Pattern = '(?<=one defect with )[\w-]+(?= rows)' }
    @{ File = 'critique.md'; Q = 'dcsr-rows';     Style = 'words';  Pattern = '(?<=All )[\w-]+(?= rows are one class)' }
    @{ File = 'critique.md'; Q = 'cj-specs';      Style = 'words';  Pattern = '[\w-]+(?= crown jewels, each a small oracle)' }
    @{ File = 'critique.md'; Q = 'requirements';  Style = 'digits'; Pattern = '(?<=of )[\d,]+(?= acceptance criteria)' }
    @{ File = 'critique.md'; Q = 'requirements';  Style = 'digits'; Pattern = '(?<=of the )[\d,]+(?= requirements has yet been booked)' }
)

# --- number words, so a claim may read as prose without becoming unmaintainable ----

$ones = 'zero','one','two','three','four','five','six','seven','eight','nine','ten',
        'eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen','eighteen','nineteen'
$tens = @{ 2='twenty'; 3='thirty'; 4='forty'; 5='fifty'; 6='sixty'; 7='seventy'; 8='eighty'; 9='ninety' }

function ConvertTo-Words([int]$n) {
    if ($n -lt 20) { return $ones[$n] }
    if ($n -lt 100) {
        $t = $tens[[int][math]::Floor($n / 10)]
        if ($n % 10 -eq 0) { return $t }
        return "$t-$($ones[$n % 10])"
    }
    throw "no word form for $n; state it in digits"
}

function Get-Expected($quantity, $style) {
    $n = $q[$quantity]
    if ($null -eq $n) { throw "unknown quantity '$quantity'" }
    if ($style -eq 'words') { return ConvertTo-Words $n }
    return [string]$n
}

function Restore-Case([string]$found, [string]$expected) {
    if ($found -cmatch '^[A-Z]') { return $expected.Substring(0,1).ToUpper() + $expected.Substring(1) }
    $expected
}

# --- 1 and 2: every asserted count is found, and equals its artifact ---------------

$findings = 0
$fixedFiles = @{}

"--- 1. asserted counts against their artifacts ---"
foreach ($c in $claims) {
    if (-not (Test-Path $c.File)) { "FAIL: $($c.File) missing"; $findings++; continue }
    $raw = if ($fixedFiles.ContainsKey($c.File)) { $fixedFiles[$c.File] } else { Get-Content $c.File -Raw }
    $expected = Get-Expected $c.Q $c.Style
    $hits = [regex]::Matches($raw, $c.Pattern)

    if ($hits.Count -eq 0) {
        $findings++
        "FAIL: $($c.File): no claim matches /$($c.Pattern)/ — the wording moved; re-anchor the claim or drop it"
        continue
    }
    $wrong = @($hits | Where-Object { $_.Value.ToLower().Replace(',','') -ne $expected })
    if ($wrong.Count -eq 0) { continue }

    if ($Fix) {
        $fixedFiles[$c.File] = [regex]::Replace($raw, $c.Pattern, { param($m) Restore-Case $m.Value $expected })
        "fixed: $($c.File): $($c.Q) $($wrong[0].Value) -> $expected"
    } else {
        $findings += $wrong.Count
        "FAIL: $($c.File): $($c.Q) asserted as '$($wrong[0].Value)', artifact says '$expected'"
    }
}
if ($findings -eq 0 -and -not $Fix) { "ok: all $($claims.Count) asserted counts agree" }
""

# --- 3: the Coverage table is one row per section, with the right count ------------

"--- 3. the Coverage table against the register's own sections ---"
$rowPattern = '(?m)^\| \*\*§(\d+) [^|]*\| \*\*extracted\*\* \| \*\*(\d+)\*\* \|$'
$regRaw = if ($fixedFiles.ContainsKey('requirements-register.md')) { $fixedFiles['requirements-register.md'] } else { Get-Content requirements-register.md -Raw }
$rows = [regex]::Matches($regRaw, $rowPattern)

$listed = @($rows | ForEach-Object { $_.Groups[1].Value })
$missing = @($perSection.Keys | Where-Object { $_ -notin $listed })
$extra   = @($listed | Where-Object { $_ -notin $perSection.Keys })
if ($missing) { $findings += $missing.Count; "FAIL: section(s) with no Coverage row: $($missing -join ', ')" }
if ($extra)   { $findings += $extra.Count;   "FAIL: Coverage row(s) for no section: $($extra -join ', ')" }

$bad = @($rows | Where-Object { [int]$_.Groups[2].Value -ne $perSection[$_.Groups[1].Value] })
if ($bad.Count -and $Fix) {
    $fixedFiles['requirements-register.md'] = [regex]::Replace($regRaw, $rowPattern, {
        param($m) $m.Value -replace '\*\*\d+\*\* \|$', "**$($perSection[$m.Groups[1].Value])** |"
    })
    $bad | ForEach-Object { "fixed: Coverage §$($_.Groups[1].Value): $($_.Groups[2].Value) -> $($perSection[$_.Groups[1].Value])" }
} elseif ($bad.Count) {
    $findings += $bad.Count
    $bad | ForEach-Object { "FAIL: Coverage §$($_.Groups[1].Value) says $($_.Groups[2].Value), register holds $($perSection[$_.Groups[1].Value])" }
} elseif (-not $missing -and -not $extra) {
    "ok: $($rows.Count) rows, one per section, each matching the register"
}
""

# --- the register and the profile view must agree on the open CSR rows ------------

"--- 4. the D-CSR rows against the profile view that carries them ---"
if ($q['dcsr-rows'] -ne $q['open-csr-rows']) {
    $findings++
    "FAIL: the register books $($q['dcsr-rows']) D-CSR row(s); isa-profile.md §5.3 carries $($q['open-csr-rows'])"
} else {
    "ok: $($q['dcsr-rows']) open CSR rows in both"
}
""

if ($Fix) {
    foreach ($f in $fixedFiles.Keys) { Set-Content -Path $f -Value $fixedFiles[$f] -NoNewline }
    if ($fixedFiles.Count) { "rewrote $($fixedFiles.Count) file(s)." } else { "nothing to rewrite." }
}

if ($findings) { "$findings finding(s)."; exit 1 }
"counts and artifacts agree."
exit 0
