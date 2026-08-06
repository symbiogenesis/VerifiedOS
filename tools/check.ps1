# Checks every derived fact in this repository against the artifact that owns it.
#
# A derived fact is anything one document holds only because another document already
# determined it. Restated by hand it drifts silently, in whichever direction nobody
# looked, which is the defect the register's sweep 2 names. The defect takes three
# granularities, and they are one mistake, so they are one tool:
#
#   traces   the reference    every bookmark a trace cites, and the section it displays
#   views    the membership   what a derived view carries, checked in both directions
#   counts   the cardinality  every figure any document asserts, against its artifact
#
# A fourth group checks what a document is made of rather than what it says:
#
#   glyphs   the characters   punctuation the house style forbids, and encoding damage
#
# Run with -Fix to rewrite the asserted counts from their artifacts. Trace, view and
# glyph findings have no mechanical repair: they are a person's edit, reported not
# guessed.
#
# Exit 0 clean, 1 on any finding. Run from the repository root.

[CmdletBinding()]
param([switch]$Fix)

$ErrorActionPreference = 'Stop'

$findings = 0
function Report([string]$Label, $Items, [string]$Ok = '', [string]$Pad = '') {
    # @($null).Count is 1, and an empty pipeline result is $null — filter before counting
    $found = @(@($Items) | Where-Object { $_ })
    if ($found.Count) {
        $script:findings += $found.Count
        "${Pad}FAIL: $($found.Count) $Label"
        $found | ForEach-Object { "$Pad       $_" }
    } else {
        "${Pad}ok: $(if ($Ok) { $Ok } else { $Label })"
    }
}

# =================================================================================
# The artifacts, each parsed once
# =================================================================================

# --- the register: ids, where each sits, its body, and the trace it carries -------

$regLines   = Get-Content 'requirements-register.md'
$ids        = [System.Collections.Generic.List[string]]::new()
$cjTargets  = [System.Collections.Generic.List[string]]::new()
$subsection = @{}          # id -> "15.4", the ### n.m it sits in, where there is one
$body       = @{}          # id -> the entry line itself
$traceOf    = @{}          # id -> its · Trace: line
$perSection = [ordered]@{} # section -> entry count, in document order
$dcsrRows   = 0

$sec = $null; $sub = $null; $current = $null; $inDefects = $false
foreach ($line in $regLines) {
    if ($line -match '^## §(\d+)') {
        $sec = $Matches[1]; $sub = $null
        if (-not $perSection.Contains($sec)) { $perSection[$sec] = 0 }
    }
    if ($line -match '^### (\d+\.\d+) ')       { $sub = $Matches[1] }
    if ($line -match '^## Extraction defects') { $inDefects = $true }

    if ($line -match '^\*\*(R-\d\d-\d+[a-z]?)\*\* (IS|MUST NOT|MUST)') {
        $current = $Matches[1]
        $ids.Add($current)
        $subsection[$current] = $sub
        $body[$current]       = $line
        if ($sec) { $perSection[$sec]++ }
    } elseif ($current -and $line -match '^· Trace:') {
        $traceOf[$current] = $line
        $current = $null
    }

    if ($line -match '^\| `(CJ-[A-Z-]+)`')        { $cjTargets.Add($Matches[1]) }
    elseif ($inDefects -and $line -match '^\| `') { $dcsrRows++ }
}

# --- the prose: bookmark -> occurrence count, and bookmark -> owning §n -----------
# A bookmark may be cited more than once from the prose only by taking a -2/-3 suffix;
# the base id it belongs to is what the third trace property resolves against.

$anchorCount = @{}
$anchorSec   = @{}
$sec = $null
foreach ($line in Get-Content 'verification-maximal-os.md') {
    if ($line -match '^## (\d+)\.') { $sec = $Matches[1] }
    foreach ($m in [regex]::Matches($line, '<a id="([^"]+)"')) {
        $id = $m.Groups[1].Value
        $anchorCount[$id] = 1 + $anchorCount[$id]
        if (-not $anchorSec.ContainsKey($id)) { $anchorSec[$id] = $sec }
    }
}

# --- the counted artifacts: the inventory, the profile, the absence contract ------

$cj = Get-Content 'crown-jewels.md'
$cjRows = @($cj | Where-Object { $_ -match '^\| \d+ \|' })
function Get-Status($row) { (($row -split '\|')[-2]).Trim() }

$openCsr = 0; $inOpen = $false
foreach ($line in Get-Content 'isa-profile.md') {
    if ($line -match '^### 5\.3 ') { $inOpen = $true; continue }
    if ($inOpen -and $line -match '^(##|---)') { $inOpen = $false }
    if ($inOpen -and $line -match '^\| `') { $openCsr++ }
}

# =================================================================================
# traces: the register's references against the prose bookmarks they cite
# =================================================================================
#
# Bookmarks cannot go stale the way line numbers do, but they can be absent, misspelled
# or duplicated, and a dangling Markdown anchor fails silently. Properties 1 and 2 are
# not hypothetical: they found R-05-022 (no trace) and R-15-159 (a target inside a
# mermaid diagram) when the reference first became symbolic.

"=== traces: the register's references against the prose ==="

$badTarget = @(); $wrongSec = @()
foreach ($id in $ids) {
    $t = $traceOf[$id]
    if (-not $t) { continue }
    foreach ($m in [regex]::Matches($t, '\[§([\d.]+)\]\(verification-maximal-os\.md#([^)]+)\)')) {
        $anchor = $m.Groups[2].Value
        $n = [int]$anchorCount[$anchor]
        if ($n -eq 0)     { $badTarget += "$id cites #$anchor — no such bookmark in the prose" }
        elseif ($n -gt 1) { $badTarget += "$id cites #$anchor — $n bookmarks share that id" }

        $shown  = ($m.Groups[1].Value -split '\.')[0]
        $actual = $anchorSec[$anchor]
        if ($actual -and $shown -ne $actual) {
            $wrongSec += "$id shows §$shown for #$anchor, which sits in §$actual"
        }
    }
}
Report 'unresolvable or ambiguous trace target(s)' $badTarget 'every cited bookmark resolves exactly once'

Report 'requirement(s) with no trace' @($ids | Where-Object { -not $traceOf.ContainsKey($_) }) 'every requirement carries a trace'

# r-ss-nnn, r-ss-nnna (a letter-suffixed requirement) and r-ss-nnn-2 (the nth citation
# of one requirement) all resolve to the same register id.
$orphans = @()
foreach ($id in $anchorCount.Keys) {
    if ($id -notmatch '^r-\d\d-\d') { continue }
    $reqId = 'R' + ($id -replace '^(r-\d\d-\d\d\d[a-z]?)-\d+$', '$1').Substring(1)
    if (-not $ids.Contains($reqId)) { $orphans += "#$id — no requirement $reqId in the register" }
}
Report 'prose bookmark(s) naming no live requirement' ($orphans | Sort-Object) 'every prose r-* bookmark names a live requirement'

Report "trace(s) whose display section is wrong" $wrongSec "every trace displays the section its bookmark sits in"
""

# =================================================================================
# views: what each derived view carries, in both directions
# =================================================================================
#
# A derived view restates requirements that live in the register. That is the shape
# which produced D-03 and D-10, the same set stated twice with different membership.
# The reverse direction is the one that earns its keep: on first run it found eight
# omissions in isa-profile.md, five of them the §15.12 timing contracts.
#
# A view declares what it must carry, either by owning §15 subsection (Secs) or by a
# pattern matched against requirement bodies anywhere in the register (BodyPattern).

$views = @(
    @{ File = 'isa-profile.md'
       Governing = 'R-15-001a'
       Secs = '15.1','15.3','15.4','15.5','15.6','15.7','15.8','15.9','15.10','15.11','15.12' }
    @{ File = 'absence-contract.md'
       Governing = 'R-15-100a'
       Secs = '15.14' }
    @{ File = 'crown-jewels.md'
       Governing = 'R-17-016a'
       BodyPattern = 'crown.jewel spec'
       MustCiteTargets = $true }
)

"=== views: what each derived view carries, both directions ==="
foreach ($v in $views) {
    "$($v.File) (per $($v.Governing))"
    if (-not (Test-Path $v.File)) { "  FAIL: missing"; $findings++; continue }

    $cited = Select-String -Path $v.File -Pattern 'R-\d\d-\d+[a-z]?' -AllMatches |
             ForEach-Object { $_.Matches } | ForEach-Object { $_.Value } | Sort-Object -Unique

    Report 'ID(s) cited but absent from the register:' @($cited | Where-Object { $_ -notin $ids }) `
           "all $($cited.Count) cited IDs resolve" '  '

    if ($v.Secs) {
        $uncovered = $subsection.Keys | Where-Object { $subsection[$_] -in $v.Secs -and $_ -notin $cited } | Sort-Object
    } else {
        $uncovered = $body.Keys | Where-Object { $body[$_] -match $v.BodyPattern -and $_ -notin $cited } | Sort-Object
    }
    Report 'bearing requirement(s) not carried:' $uncovered 'all bearing requirements are carried' '  '

    # a view standing in for the CJ- vocabulary must account for every target
    if ($v.MustCiteTargets) {
        $raw = Get-Content $v.File -Raw
        Report 'CJ- target(s) unaccounted for:' @($cjTargets | Where-Object { $raw -notmatch [regex]::Escape($_) }) `
               "all $($cjTargets.Count) CJ- targets accounted for" '  '
    }
}
""

# =================================================================================
# counts: every figure any document asserts, against the artifact it derives from
# =================================================================================
#
# "954 requirements", "twenty-two crown-jewel specifications", "sixteen enumerated
# absences" are all restatements of something a table already holds. Each quantity is
# computed here; each claim says where it is asserted and in which style, and captures
# the number alone, so -Fix is the substitution of a single token.

$q = [ordered]@{
    'requirements'  = $ids.Count
    'lettered'      = @($ids | Where-Object { $_ -match '[a-z]$' }).Count
    'sections'      = $perSection.Count
    'cj-targets'    = $cjTargets.Count
    'dcsr-rows'     = $dcsrRows
    'open-csr-rows' = $openCsr
    'cj-specs'      = $cjRows.Count
    'cj-authored'   = @($cjRows | Where-Object { (Get-Status $_) -like '*authored*' -and (Get-Status $_) -notlike 'not authored*' -and (Get-Status $_) -notlike 'partial*' }).Count
    'cj-partial'    = @($cjRows | Where-Object { (Get-Status $_) -like 'partial*' }).Count
    'cj-unauthored' = @($cjRows | Where-Object { (Get-Status $_) -like 'not authored*' }).Count
    'cj-theorems'   = @($cj | Where-Object { $_ -match '^\| `CJ-[A-Z-]+` \|' }).Count
    'cj-conferring' = @($body.Keys | Where-Object { $body[$_] -match 'crown.jewel spec' }).Count
    'seams'         = @($body.Keys | Where-Object { $body[$_] -match ' Seam: \*\*' }).Count
    'views'         = $views.Count
    'absences'      = @(Get-Content 'absence-contract.md' | Where-Object { $_ -match '^\| \*\*A-\d+\*\*' }).Count
}

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
    @{ File = 'crown-jewels.md'; Q = 'cj-conferring'; Style = 'words';  Pattern = '(?<=There are )[\w-]+(?= such entries)' }

    # the README summarizes them
    @{ File = 'README.md'; Q = 'views';         Style = 'words';  Pattern = '[\w-]+(?= \*\*derived views\*\* collect)' }
    @{ File = 'README.md'; Q = 'sections';      Style = 'words';  Pattern = '(?<=covers all )[\w-]+(?= normative sections)' }
    @{ File = 'README.md'; Q = 'requirements';  Style = 'digits'; Pattern = '(?<=sections as )[\d,]+(?= numbered requirements)' }
    @{ File = 'README.md'; Q = 'dcsr-rows';     Style = 'words';  Pattern = '(?<=whose )[\w-]+(?= rows are surviving CSRs)' }
    @{ File = 'README.md'; Q = 'absences';      Style = 'words';  Pattern = '[\w-]+(?= enumerated absences)' }
    @{ File = 'README.md'; Q = 'cj-specs';      Style = 'words';  Pattern = '(?<=the )[\w-]+(?= specifications the §5 review gate audits)' }
    @{ File = 'README.md'; Q = 'cj-theorems';   Style = 'words';  Pattern = '(?<=plus the )[\w-]+(?= theorem targets)' }

    # the gap catalogue argues from them
    @{ File = 'critique.md'; Q = 'requirements';  Style = 'digits'; Pattern = '(?<=requirements-register\.md\), )[\d,]+(?= numbered requirements)' }
    @{ File = 'critique.md'; Q = 'views';         Style = 'words';  Pattern = '(?<=register and the )[\w-]+(?= derived views)' }
    @{ File = 'critique.md'; Q = 'views';         Style = 'words';  Pattern = '[\w-]+(?= derived views and `tools/check\.ps1`)' }
    @{ File = 'critique.md'; Q = 'seams';         Style = 'words';  Pattern = '[\w-]+(?= hardware seams are named with owners)' }
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

"=== counts: every asserted figure against its artifact ==="

$fixedFiles = @{}
$countFindings = $findings
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
if ($findings -eq $countFindings -and -not $Fix) { "ok: all $($claims.Count) asserted counts agree" }

# --- the Coverage table is one row per section, with the right count ---------------

$rowPattern = '(?m)^\| \*\*§(\d+) [^|]*\| \*\*extracted\*\* \| \*\*(\d+)\*\* \|$'
$regRaw = if ($fixedFiles.ContainsKey('requirements-register.md')) { $fixedFiles['requirements-register.md'] } else { Get-Content 'requirements-register.md' -Raw }
$rows = [regex]::Matches($regRaw, $rowPattern)

$listed = @($rows | ForEach-Object { $_.Groups[1].Value })
$mismatched = @()
$mismatched += @($perSection.Keys | Where-Object { $_ -notin $listed }  | ForEach-Object { "§$_ has no Coverage row" })
$mismatched += @($listed | Where-Object { $_ -notin $perSection.Keys } | ForEach-Object { "Coverage row §$_ names no section" })
Report 'Coverage row(s) not matching the section list:' $mismatched "$($rows.Count) Coverage rows, one per section"

$bad = @($rows | Where-Object { [int]$_.Groups[2].Value -ne $perSection[$_.Groups[1].Value] })
if ($bad.Count -and $Fix) {
    $fixedFiles['requirements-register.md'] = [regex]::Replace($regRaw, $rowPattern, {
        param($m) $m.Value -replace '\*\*\d+\*\* \|$', "**$($perSection[$m.Groups[1].Value])** |"
    })
    $bad | ForEach-Object { "fixed: Coverage §$($_.Groups[1].Value): $($_.Groups[2].Value) -> $($perSection[$_.Groups[1].Value])" }
} else {
    Report 'Coverage row(s) disagreeing with the register:' `
           @($bad | ForEach-Object { "§$($_.Groups[1].Value) says $($_.Groups[2].Value), register holds $($perSection[$_.Groups[1].Value])" }) `
           'every Coverage row matches the register'
}

# --- the register and the profile view must agree on the open CSR rows ------------

if ($q['dcsr-rows'] -ne $q['open-csr-rows']) {
    $findings++
    "FAIL: the register books $($q['dcsr-rows']) D-CSR row(s); isa-profile.md §5.3 carries $($q['open-csr-rows'])"
} else {
    "ok: $($q['dcsr-rows']) open CSR rows in both the register and the profile"
}
""

# =================================================================================
# glyphs: punctuation the house style forbids, and the encoding damage that mimics it
# =================================================================================
#
# The three groups above check what a document says. This one checks what it is made of,
# where two unrelated faults share one symptom, a wrong character, and neither survives
# a rendered read: the em-dash is house style (the punctuation here is explicit, so a
# clause takes a comma, a colon, or its own sentence), and mojibake is UTF-8 read as some
# single-byte encoding, which leaves a signature worth catching the moment it lands.
#
# Both are reported per file with the lines to visit, and neither is repaired. An em-dash
# is removed by deciding what the sentence meant; a mangled character can only be restored
# by whoever knows what it was.

function Format-GlyphHits([string]$File, [int[]]$Lines) {
    $shown = if ($Lines.Count -gt 12) { ($Lines[0..11] -join ', ') + ", and $($Lines.Count - 12) more" }
             else                     { $Lines -join ', ' }
    "${File}: $($Lines.Count) line(s): $shown"
}

"=== glyphs: forbidden punctuation and encoding damage ==="

$emDash = [char]0x2014

# A lead byte of a multi-byte UTF-8 sequence, decoded as Latin-1 or CP1252, followed by a
# continuation byte decoded the same way. The second class is the whole high half of both
# encodings, so the mangling of any character is caught, not just the common ones.
$cp1252 = '\u0080-\u00BF\u0152\u0153\u0160\u0161\u017D\u017E\u0178\u0192\u02C6\u02DC' +
          '\u2013\u2014\u2018-\u201A\u201C-\u201E\u2020-\u2022\u2026\u2030\u2039\u203A\u20AC\u2122'
$mojibake = [regex]"[\u00C2\u00C3\u00E2\u00F0][$cp1252]|\uFFFD"

$emHits = @(); $mojibakeHits = @()
foreach ($doc in Get-ChildItem -Path . -Filter *.md -Recurse | Sort-Object FullName) {
    $name  = (Resolve-Path -Relative $doc.FullName) -replace '^\.[\\/]', ''
    $lines = [System.IO.File]::ReadAllLines($doc.FullName)

    $em = @(); $mb = @()
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].Contains($emDash))  { $em += $i + 1 }
        if ($mojibake.IsMatch($lines[$i])) { $mb += $i + 1 }
    }
    if ($em.Count) { $emHits       += Format-GlyphHits $name $em }
    if ($mb.Count) { $mojibakeHits += Format-GlyphHits $name $mb }
}

Report 'file(s) carrying an em-dash (U+2014)' $emHits 'no em-dash in any document'
Report 'file(s) carrying mojibake or a replacement character' $mojibakeHits 'no encoding damage in any document'
""

if ($Fix) {
    foreach ($f in $fixedFiles.Keys) { Set-Content -Path $f -Value $fixedFiles[$f] -NoNewline }
    if ($fixedFiles.Count) { "rewrote $($fixedFiles.Count) file(s)." } else { "nothing to rewrite." }
}

if ($findings) { "$findings finding(s)."; exit 1 }
"every derived fact agrees with its artifact."
exit 0
