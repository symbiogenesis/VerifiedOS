# Checks the register's traces against the prose bookmarks they cite.
#
# D-16 replaced line-number traces with `<a id="r-ss-nnn">` bookmarks, which cannot go
# stale — but can still be absent, misspelled, or duplicated, and a dangling Markdown
# anchor fails silently. D-16 booked four properties as mechanical, cheap, and held by
# no artifact. This is that artifact:
#
#   1. every bookmark a trace cites resolves exactly once in the prose
#   2. every requirement entry carries a trace at all
#   3. every r-* bookmark in the prose names a live requirement
#   4. the §n in a trace's display text is the section its bookmark sits in
#
# Properties 1 and 2 are not hypothetical: they are what found R-05-022 (no trace) and
# R-15-159 (a target inside a mermaid diagram) when the reference first became symbolic.
#
# Exit 0 clean, 1 on any finding. Run from the repository root.

$ErrorActionPreference = 'Stop'

$regFile   = 'requirements-register.md'
$proseFile = 'verification-maximal-os.md'

$reg   = Get-Content $regFile
$prose = Get-Content $proseFile

# --- prose side: bookmark -> occurrence count, and bookmark -> owning §n ------------
# A bookmark may be cited more than once from the prose only by taking a -2/-3 suffix;
# the base id it belongs to is what property 3 resolves against.
$anchorCount = @{}
$anchorSec   = @{}
$sec = $null
for ($i = 0; $i -lt $prose.Count; $i++) {
    if ($prose[$i] -match '^## (\d+)\.') { $sec = $Matches[1] }
    foreach ($m in [regex]::Matches($prose[$i], '<a id="([^"]+)"')) {
        $id = $m.Groups[1].Value
        $anchorCount[$id] = 1 + $anchorCount[$id]
        if (-not $anchorSec.ContainsKey($id)) { $anchorSec[$id] = $sec }
    }
}

# --- register side: requirement ids, and the trace line each entry carries ----------
$regIds  = [ordered]@{}
$traceOf = @{}
$current = $null
foreach ($line in $reg) {
    if ($line -match '^\*\*(R-\d\d-\d+[a-z]?)\*\* (IS|MUST NOT|MUST)') {
        $current = $Matches[1]
        $regIds[$current] = $true
    } elseif ($line -match '^· Trace:') {
        if ($current) { $traceOf[$current] = $line; $current = $null }
    }
}

$findings = 0
function Report($label, $items) {
    # @($null).Count is 1, and an empty pipeline result is $null — filter before counting
    $items = @($items) | Where-Object { $_ }
    if (@($items).Count) {
        $script:findings += @($items).Count
        "FAIL: $(@($items).Count) $label"
        $items | ForEach-Object { "       $_" }
    } else {
        "ok: $label — none"
    }
}

# --- 1. every cited bookmark resolves exactly once ---------------------------------
$badTarget = @()
$citedIds  = @{}
foreach ($id in $regIds.Keys) {
    $t = $traceOf[$id]
    if (-not $t) { continue }
    foreach ($m in [regex]::Matches($t, '\[§([\d.]+)\]\(verification-maximal-os\.md#([^)]+)\)')) {
        $anchor = $m.Groups[2].Value
        $citedIds[$anchor] = $true
        $n = [int]$anchorCount[$anchor]
        if ($n -eq 0)    { $badTarget += "$id cites #$anchor — no such bookmark in the prose" }
        elseif ($n -gt 1) { $badTarget += "$id cites #$anchor — $n bookmarks share that id" }
    }
}
"--- 1. cited bookmarks resolve exactly once ---"
Report "unresolvable or ambiguous trace target(s)" $badTarget
""

# --- 2. every requirement carries a trace ------------------------------------------
"--- 2. every requirement carries a trace ---"
$untraced = @($regIds.Keys | Where-Object { -not $traceOf.ContainsKey($_) })
Report "requirement(s) with no trace" $untraced
""

# --- 3. every r-* prose bookmark names a live requirement --------------------------
# r-ss-nnn, r-ss-nnna (a real letter-suffixed requirement), r-ss-nnn-2 (nth citation
# of the same requirement) all resolve to the same register ID.
"--- 3. prose r-* bookmarks name live requirements ---"
$orphanAnchors = @()
foreach ($id in $anchorCount.Keys) {
    if ($id -notmatch '^r-\d\d-\d') { continue }
    $base = ($id -replace '^(r-\d\d-\d\d\d[a-z]?)-\d+$', '$1')
    $reqId = 'R' + $base.Substring(1)
    if (-not $regIds.Contains($reqId)) { $orphanAnchors += "#$id — no requirement $reqId in the register" }
}
Report "prose bookmark(s) naming no live requirement" ($orphanAnchors | Sort-Object)
""

# --- 4. the §n in a trace's display text is the bookmark's actual section ----------
"--- 4. trace display section matches the bookmark's section ---"
$wrongSec = @()
foreach ($id in $regIds.Keys) {
    $t = $traceOf[$id]
    if (-not $t) { continue }
    foreach ($m in [regex]::Matches($t, '\[§([\d.]+)\]\(verification-maximal-os\.md#([^)]+)\)')) {
        $shown  = ($m.Groups[1].Value -split '\.')[0]
        $anchor = $m.Groups[2].Value
        $actual = $anchorSec[$anchor]
        if ($actual -and $shown -ne $actual) {
            $wrongSec += "$id shows §$shown for #$anchor, which sits in §$actual"
        }
    }
}
Report "trace(s) whose display section is wrong" $wrongSec
""

if ($findings) { "$findings finding(s)."; exit 1 }
"traces and prose bookmarks agree."
exit 0
