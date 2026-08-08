# Checks every derived fact in this repository against the artifact that owns it.
#
# A derived fact is anything one document holds only because another document already
# determined it. Restated by hand it drifts silently, in whichever direction nobody
# looked, which is the defect the register's sweep 2 names. The defect takes five
# granularities, and they are one mistake, so they are one tool:
#
#   traces   the reference    every bookmark a trace cites, and the section it displays
#   names    the vocabulary   every R-, CJ-, A-, B- and P- id used, against its declarer
#   links    the pointer      every cross-document link and every §n.m a sentence names
#   views    the membership   what a derived view carries, checked in both directions
#   counts   the cardinality  every figure any document asserts, against its artifact
#
# Two further groups check what a document is made of rather than what it says, where a
# fault survives a rendered read because the render succeeds:
#
#   tables   the shape        every row against the width its header declares
#   glyphs   the characters   punctuation the house style forbids, and encoding damage
#
# Run with -Fix to rewrite the asserted counts from their artifacts. Every other finding
# has no mechanical repair: it is a person's edit, reported not guessed.
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

# --- every document, read once, and which of its lines a fence displays verbatim --
# A fenced block is shown as text, so an anchor inside one is not a bookmark, a link
# inside one is not a link, and an id inside one names nothing: the register's own
# entry template cites `#r-ss-nnn`, which must not read as a dangling trace. Every
# group that reads whole documents reads them through this, so the rule is stated
# once and every group inherits it.

$docs = @(foreach ($f in Get-ChildItem -Path . -Filter *.md -Recurse | Sort-Object FullName) {
    $lines  = [System.IO.File]::ReadAllLines($f.FullName)
    $fenced = New-Object 'bool[]' $lines.Count
    $open   = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^\s*```') { $fenced[$i] = $true; $open = -not $open }
        else                             { $fenced[$i] = $open }
    }
    [pscustomobject]@{
        Name   = (Resolve-Path -Relative $f.FullName) -replace '^\.[\\/]', ''
        Lines  = $lines
        Fenced = $fenced
    }
})

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

# --- every bookmark: where it is declared, how often, and the prose §n it sits in --
# A bookmark may be cited more than once from the prose only by taking a -2/-3 suffix;
# the base id it belongs to is what the third trace property resolves against. Ids are
# per-file, so two documents may carry the same one; within a file a repeat is a fault,
# and the link group needs the whole set, not the prose's alone.

$anchorCount = @{}         # prose bookmark -> how often the prose declares it
$anchorSec   = @{}         # prose bookmark -> the §n it sits in
$anchorsOf   = @{}         # file -> (bookmark -> count), the whole corpus
$buried      = @()         # anchors a fence displays instead of declaring
$twiceHere   = @()

$sec = $null
foreach ($d in $docs) {
    $prose = $d.Name -eq 'verification-maximal-os.md'
    $here  = @{}
    for ($i = 0; $i -lt $d.Lines.Count; $i++) {
        $line = $d.Lines[$i]
        if ($prose -and -not $d.Fenced[$i] -and $line -match '^## (\d+)\.') { $sec = $Matches[1] }
        foreach ($m in [regex]::Matches($line, '<a id="([^"]+)"')) {
            $id = $m.Groups[1].Value
            if ($d.Fenced[$i]) {
                $buried += "$($d.Name):$($i + 1) buries #$id in a fenced block, where it is text and not a bookmark"
                continue
            }
            $here[$id] = 1 + $here[$id]
            if ($here[$id] -eq 2) { $twiceHere += "$($d.Name) declares #$id more than once; a link to it resolves to whichever comes first" }
            if ($prose) {
                $anchorCount[$id] = 1 + $anchorCount[$id]
                if (-not $anchorSec.ContainsKey($id)) { $anchorSec[$id] = $sec }
            }
        }
    }
    $anchorsOf[$d.Name] = $here
}

# --- the counted artifacts: the inventory, the profile, the absence contract ------

$cj = Get-Content 'crown-jewels.md'
$cjRows = @($cj | Where-Object { $_ -match '^\| \d+ \|' })
function Get-Status($row) { (($row -split '\|')[-2]).Trim() }

# The status column is a closed vocabulary of three, and the counts below are taken by
# reading it. A status spelled a fourth way is counted by none of them, so the ratio
# quietly stops summing to the inventory and each figure remains individually true.
# One classifier, and the rows it classifies as nothing are the finding.
function Get-CjClass($row) {
    $s = Get-Status $row
    if ($s -like 'not authored*') { return 'unauthored' }
    if ($s -like 'partial*')      { return 'partial' }
    if ($s -like '*authored*')    { return 'authored' }
    $null
}

$absenceIds = @(Get-Content 'absence-contract.md' |
                ForEach-Object { if ($_ -match '^\| \*\*(A-\d+)\*\*') { $Matches[1] } })

$openCsr = 0; $inOpen = $false
foreach ($line in Get-Content 'isa-profile.md') {
    if ($line -match '^### 5\.3 ') { $inOpen = $true; continue }
    if ($inOpen -and $line -match '^(##|---)') { $inOpen = $false }
    if ($inOpen -and $line -match '^\| `') { $openCsr++ }
}

# --- the coverage matrix: two enumerations, and the cells over their product ------
# A definition row names one id and then prose; a matrix row names two ids. That is
# the whole difference, so one pass reads all three.

$cmBounds = [System.Collections.Generic.List[string]]::new()
$cmProps  = [System.Collections.Generic.List[string]]::new()
$cmCells  = [ordered]@{}
$cmTwice  = @()
foreach ($line in Get-Content 'coverage-matrix.md') {
    if     ($line -match '^\| `(B-\d\d)` \| `(P-\d)` \|') {
        $pair = "$($Matches[1]) by $($Matches[2])"
        if ($cmCells.Contains($pair)) { $cmTwice += "$pair has more than one cell" }
        $cmCells[$pair] = $line
    }
    elseif ($line -match '^\| `(B-\d\d)` \| [^`|]') { $cmBounds.Add($Matches[1]) }
    elseif ($line -match '^\| `(P-\d)` \| [^`|]')  { $cmProps.Add($Matches[1]) }
}

# =================================================================================
# traces: the register's references against the prose bookmarks they cite
# =================================================================================
#
# Bookmarks cannot go stale the way line numbers do, but they can be absent, misspelled,
# duplicated or buried, and a dangling Markdown anchor fails silently. The properties are
# not hypothetical: they found R-05-022 (no trace) and R-15-159 (a target inside a mermaid
# diagram) when the reference first became symbolic. The mermaid case is why a bookmark
# inside a fenced block is now a finding on its own: the fence displays the anchor rather
# than declaring it, so the trace that cites it points at nothing while the prose looks
# like it carries the target. That defect was repaired by hand once and nothing held it.

"=== traces: the register's references against the prose ==="

$badTarget = @(); $wrongSec = @()
foreach ($id in $ids) {
    $t = $traceOf[$id]
    if (-not $t) { continue }
    foreach ($m in [regex]::Matches($t, '\[§([\d.]+)\]\(verification-maximal-os\.md#([^)]+)\)')) {
        $anchor = $m.Groups[2].Value
        if (-not $anchorCount.ContainsKey($anchor)) { $badTarget += "$id cites #$anchor, which is no bookmark in the prose" }

        $shown  = ($m.Groups[1].Value -split '\.')[0]
        $actual = $anchorSec[$anchor]
        if ($actual -and $shown -ne $actual) {
            $wrongSec += "$id shows §$shown for #$anchor, which sits in §$actual"
        }
    }
}
Report 'unresolvable trace target(s)' $badTarget 'every cited bookmark resolves'

Report 'bookmark(s) declared more than once in one document' $twiceHere 'every bookmark id is unique where it is declared'

Report 'bookmark(s) buried in a fenced block' $buried 'every bookmark is addressable where it is written'

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
# names: every id a document uses, against the artifact that declares it
# =================================================================================
#
# Five vocabularies run across these documents: the register's R- requirements and its
# CJ- crown-jewel targets, the absence contract's A- absences, and the coverage matrix's
# B- boundaries and P- properties. Each is declared by exactly one artifact and cited
# from everywhere, which makes a citation a derived fact of the coarsest granularity,
# a whole id. Retire or renumber one and every sentence arguing from it still reads,
# and argues from nothing. IDs are permanent here (a retired requirement is struck,
# never reused), and that is what makes the check total rather than advisory: a name
# either resolves to something live or is an error, with no third case to adjudicate.

"=== names: every id used, against the artifact that declares it ==="

Report 'requirement id(s) the register declares twice:' `
       @($ids | Group-Object | Where-Object { $_.Count -gt 1 } | ForEach-Object { "$($_.Name), declared $($_.Count) times" }) `
       "all $($ids.Count) register ids are distinct"

$vocab = @(
    @{ Kind = 'requirement';        Token = 'R-\d\d-\d+[a-z]?'; Declared = $ids;        Home = 'the register' }
    @{ Kind = 'crown-jewel target'; Token = 'CJ-[A-Z][A-Z-]*';  Declared = $cjTargets;  Home = "the register's CJ- table" }
    @{ Kind = 'absence';            Token = 'A-\d+';            Declared = $absenceIds; Home = 'absence-contract.md' }
    @{ Kind = 'boundary';           Token = 'B-\d+';            Declared = $cmBounds;   Home = 'coverage-matrix.md' }
    @{ Kind = 'property';           Token = 'P-\d+';            Declared = $cmProps;    Home = 'coverage-matrix.md' }
)

foreach ($v in $vocab) {
    $declared = [System.Collections.Generic.HashSet[string]]::new([string[]]@($v.Declared))
    $pattern  = [regex]"(?<![\w-])$($v.Token)(?![\w-])"
    $unknown  = @()
    foreach ($d in $docs) {
        for ($i = 0; $i -lt $d.Lines.Count; $i++) {
            if ($d.Fenced[$i]) { continue }
            foreach ($m in $pattern.Matches($d.Lines[$i])) {
                if (-not $declared.Contains($m.Value)) {
                    $unknown += "$($d.Name):$($i + 1) uses $($m.Value), which $($v.Home) does not declare"
                }
            }
        }
    }
    Report "$($v.Kind) id(s) naming nothing:" $unknown `
           "every $($v.Kind) id used names one of the $($declared.Count) $($v.Home) declares"
}
""

# =================================================================================
# links: every cross-reference a document makes, against what it points at
# =================================================================================
#
# The traces group holds the register's citations of the prose. This holds every other
# pointer: the README to the views, the views to each other and back to the register, a
# heading cited by its slug, and the §n.m a sentence names without a link at all, which
# is the commonest cross-reference here and the only one Markdown cannot render as
# broken even in principle. A dead link renders as ordinary text and reads as a working
# reference, so nothing but a tool notices. Renaming a heading breaks every slug that
# cited it and renumbering a section breaks every §n.m that named it, both silently and
# both at a distance from the edit that caused them.
#
# The §n.m half resolves against the numbered headings of the whole repository rather
# than one document's, because the numbering is shared: §5.3 is the register's
# subsection and the profile's CSR section, and which is meant is the sentence's
# business. What the check holds is the weaker property that closes the drift: a number
# no document carries at all is a reference to a section that has been renumbered away.

"=== links: every cross-reference against what it points at ==="

function ConvertTo-Slug([string]$Heading) {
    (($Heading -replace '<[^>]+>', '' -replace '`', '').Trim().ToLower() -replace '[^\w\s-]', '' -replace '\s+', '-')
}

$targets  = @{}   # file -> every id a link may name: its bookmarks and its heading slugs
$numbered = @{}   # "15.12" -> the number is carried by a heading somewhere
foreach ($d in $docs) {
    $set = [System.Collections.Generic.HashSet[string]]::new([string[]]@($anchorsOf[$d.Name].Keys))
    for ($i = 0; $i -lt $d.Lines.Count; $i++) {
        if ($d.Fenced[$i] -or $d.Lines[$i] -notmatch '^#{1,6}\s+(.+)$') { continue }
        $heading = $Matches[1]
        [void]$set.Add((ConvertTo-Slug $heading))
        if ($heading -match '^§?(\d+(?:\.\d+)*)[.:) ]') { $numbered[$Matches[1]] = $true }
    }
    $targets[$d.Name] = $set
}

$dead = @(); $unnumbered = [ordered]@{}; $exists = @{}
foreach ($d in $docs) {
    for ($i = 0; $i -lt $d.Lines.Count; $i++) {
        if ($d.Fenced[$i]) { continue }
        $line = $d.Lines[$i]

        foreach ($m in [regex]::Matches($line, '\]\(([^)\s#]*)(?:#([^)\s]+))?\)')) {
            $file = $m.Groups[1].Value -replace '^\./', ''
            $frag = $m.Groups[2].Value
            if ($file -match '^[a-z][a-z0-9+.-]*:') { continue }   # off the repository, not ours to hold
            if (-not $file) { $file = $d.Name }
            if (-not $exists.ContainsKey($file)) { $exists[$file] = Test-Path $file }
            if (-not $exists[$file]) {
                $dead += "$($d.Name):$($i + 1) points at $file, which is not in the repository"
            } elseif ($frag -and $targets.ContainsKey($file) -and -not $targets[$file].Contains($frag)) {
                $dead += "$($d.Name):$($i + 1) points at $file#$frag, which is no bookmark or heading there"
            }
        }

        foreach ($m in [regex]::Matches($line, '§(\d+(?:\.\d+)*)')) {
            $n = $m.Groups[1].Value
            if ($numbered.Contains($n)) { continue }
            if (-not $unnumbered.Contains($n)) { $unnumbered[$n] = @() }
            $unnumbered[$n] += "$($d.Name):$($i + 1)"
        }
    }
}

Report 'dead link(s):' $dead 'every link resolves to a file, and every fragment to a bookmark or heading'

Report 'section reference(s) naming no numbered heading:' `
       @($unnumbered.Keys | ForEach-Object {
           $sites = $unnumbered[$_]
           $shown = if ($sites.Count -gt 4) { ($sites[0..3] -join ', ') + ", and $($sites.Count - 4) more" } else { $sites -join ', ' }
           "§$_ is named $($sites.Count) time(s) and numbered nowhere: $shown"
       }) 'every §n.m names a heading some document carries'
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
# That every id a view cites resolves is the names group's business, not this one's:
# a view is not a special case of the vocabulary, it is the only place membership is
# also owed in the other direction.

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
    @{ File = 'coverage-matrix.md'
       Governing = 'R-17-001b'
       MustCoverCells = $true }
)

"=== views: what each derived view carries, both directions ==="
foreach ($v in $views) {
    "$($v.File) (per $($v.Governing))"
    if (-not (Test-Path $v.File)) { "  FAIL: missing"; $findings++; continue }

    $cited = Select-String -Path $v.File -Pattern 'R-\d\d-\d+[a-z]?' -AllMatches |
             ForEach-Object { $_.Matches } | ForEach-Object { $_.Value } | Sort-Object -Unique

    if ($v.Secs) {
        $uncovered = $subsection.Keys | Where-Object { $subsection[$_] -in $v.Secs -and $_ -notin $cited } | Sort-Object
        Report 'bearing requirement(s) not carried:' $uncovered 'all bearing requirements are carried' '  '
    } elseif ($v.BodyPattern) {
        $uncovered = $body.Keys | Where-Object { $body[$_] -match $v.BodyPattern -and $_ -notin $cited } | Sort-Object
        Report 'bearing requirement(s) not carried:' $uncovered 'all bearing requirements are carried' '  '
    }

    # a matrix view is bearing over a product rather than a subsection: what it must
    # carry is every pair of its own two enumerations, each resting on a requirement
    if ($v.MustCoverCells) {
        $expected = @()
        foreach ($b in $cmBounds) { foreach ($p in $cmProps) { $expected += "$b by $p" } }
        $gaps  = @($expected | Where-Object { -not $cmCells.Contains($_) } | ForEach-Object { "$_ has no cell" })
        $gaps += @($cmCells.Keys | Where-Object { $_ -notin $expected } | ForEach-Object { "$_ names no enumerated boundary or property" })
        $gaps += $cmTwice
        Report 'uncovered or unaccounted cell(s):' $gaps "all $($cmBounds.Count) by $($cmProps.Count) cells present, exactly once" '  '

        Report 'cell(s) resting on no requirement:' `
               @($cmCells.Keys | Where-Object { $cmCells[$_] -notmatch 'R-\d\d-\d' }) `
               'every cell cites a requirement' '  '
    }

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
    'cj-authored'   = @($cjRows | Where-Object { (Get-CjClass $_) -eq 'authored' }).Count
    'cj-partial'    = @($cjRows | Where-Object { (Get-CjClass $_) -eq 'partial' }).Count
    'cj-unauthored' = @($cjRows | Where-Object { (Get-CjClass $_) -eq 'unauthored' }).Count
    'cj-theorems'   = @($cj | Where-Object { $_ -match '^\| `CJ-[A-Z-]+` \|' }).Count
    'cj-conferring' = @($body.Keys | Where-Object { $body[$_] -match 'crown.jewel spec' }).Count
    'seams'         = @($body.Keys | Where-Object { $body[$_] -match ' Seam: \*\*' }).Count
    'views'         = $views.Count
    'boundaries'    = $cmBounds.Count
    'properties'    = $cmProps.Count
    'cells'         = $cmCells.Count
    'absences'      = $absenceIds.Count
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

    # the coverage matrix states the shape of its own product
    @{ File = 'coverage-matrix.md'; Q = 'boundaries'; Style = 'words'; Pattern = '(?<=below are )[\w-]+(?= boundaries)' }
    @{ File = 'coverage-matrix.md'; Q = 'properties'; Style = 'words'; Pattern = '(?<=boundaries and )[\w-]+(?= properties)' }
    @{ File = 'coverage-matrix.md'; Q = 'cells';      Style = 'words'; Pattern = '(?<=carries all )[\w-]+(?= of their pairs)' }

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

# --- the status column is three classes, and every row is in one -------------------

Report 'crown-jewel row(s) whose status is in no class:' `
       @($cjRows | Where-Object { -not (Get-CjClass $_) } | ForEach-Object { "row $((($_ -split '\|')[1]).Trim()): $(Get-Status $_)" }) `
       "$($q['cj-specs']) rows partition into $($q['cj-authored']) authored, $($q['cj-partial']) partial, $($q['cj-unauthored']) not authored"

# --- a figure stated where no claim holds it ---------------------------------------
#
# The claims above are the whole mechanism, so a restatement nobody registered is not
# checked at all: right on the day it is written, drifting from then on, and under -Fix
# left alone while its neighbours are rewritten around it, which is worse than being
# unchecked, because the document then disagrees with itself. Nothing announces a new
# figure, so the trap is the value. A form distinctive enough not to collide with
# ordinary prose (a word form of eleven or more, or three digits and up) standing on
# the same line as a noun one of these quantities is counted in, and outside the span
# of every claim, is a figure that escaped the register. Rewording it out of the way
# is as good a repair as registering it; what is not available is leaving it unheld.

$countedNoun = 'requirement|acceptance criteri|normative section|crown.jewel|specification|' +
               'theorem target|`CJ-`|absence|boundar|propert|pair|cell|derived view|seam|' +
               'CSR|letter-suffixed|such entries'

$distinct = [ordered]@{}   # a distinctive form -> the quantities it could be stating
foreach ($k in $q.Keys) {
    $n    = $q[$k]
    $form = if ($n -ge 100) { [string]$n } elseif ($n -ge 11) { ConvertTo-Words $n } else { $null }
    if ($form) {
        if (-not $distinct.Contains($form)) { $distinct[$form] = @() }
        $distinct[$form] += $k
    }
}

$loose = @()
foreach ($file in $docs.Name) {
    $raw = if ($fixedFiles.ContainsKey($file)) { $fixedFiles[$file] } else { Get-Content $file -Raw }
    if (-not $raw) { continue }
    $held = @($claims | Where-Object { $_.File -eq $file } |
              ForEach-Object { [regex]::Matches($raw, $_.Pattern) } | ForEach-Object { $_ })

    foreach ($form in $distinct.Keys) {
        foreach ($m in [regex]::Matches($raw, "(?i)(?<![\w-])$form(?![\w-])")) {
            $rest = $raw.Substring($m.Index, [math]::Min(80, $raw.Length - $m.Index)) -replace '(?s)\r?\n.*', ''
            if ($rest -notmatch $countedNoun) { continue }
            if ($held | Where-Object { $m.Index -ge $_.Index -and $m.Index -lt $_.Index + $_.Length }) { continue }
            $line = 1 + [regex]::Matches($raw.Substring(0, $m.Index), "`n").Count
            $loose += "${file}:${line} states '$($m.Value)' where no claim holds it, for $($distinct[$form] -join ' or ')"
        }
    }
}
Report 'unheld restatement(s) of a counted figure:' $loose 'every stated figure is held by a claim'

# --- the Coverage table is one row per section, with the right count ---------------

# The trailing lookahead keeps CRLF out of the match: .NET's (?m)$ sits before the \n,
# so an anchored \|$ never matches a CRLF file, and every row reads as missing.
$rowPattern = '(?m)^\| \*\*§(\d+) [^|]*\| \*\*extracted\*\* \| \*\*(\d+)\*\* \|(?=\r?$)'
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

# A file plus the lines to visit, for the two groups whose findings are per-line and
# whose repair is always the same visit.
function Format-Sites([string]$File, [int[]]$Lines) {
    $shown = if ($Lines.Count -gt 12) { ($Lines[0..11] -join ', ') + ", and $($Lines.Count - 12) more" }
             else                     { $Lines -join ', ' }
    "${File}: $($Lines.Count) line(s): $shown"
}

# =================================================================================
# tables: every row against the width its header declares
# =================================================================================
#
# Nearly every counted artifact here is a table, and the counts above read one by column
# position: the crown-jewel status is the last cell, the Coverage total the third. A row
# short a cell does not fail, it renders short, and every field after the gap shifts one
# place left, so a column read at the end returns the neighbouring field and the count
# taken from it is wrong while still being computed. The header row decides the width;
# a row that disagrees is the finding, and only its author knows which cell is missing.
#
# A run of rows carrying no header rule is the second finding, and the coarser one. It
# is either a table whose `| --- |` was lost, which renders as a paragraph of pipes and
# is read by nothing, or a row pasted somewhere on its own, which renders as its own
# one-row table and is read by nothing either. Both are invisible in the source and
# obvious the moment anything looks for the rule.

"=== tables: every row against the width its header declares ==="

$ragged = @(); $ruleless = @()
foreach ($d in $docs) {
    $bad = @(); $width = 0; $start = 0; $rows = 0; $rule = $false

    for ($i = 0; $i -le $d.Lines.Count; $i++) {
        $line = if ($i -lt $d.Lines.Count -and -not $d.Fenced[$i]) { $d.Lines[$i] } else { '' }

        if ($line -match '^\s*\|') {
            # an escaped pipe is a character inside a cell, not a wall between two
            $cells = ($line.TrimEnd() -replace '\\\|', '').Split('|').Count - 2
            if ($rows -eq 0)           { $start = $i + 1; $width = $cells }
            elseif ($cells -ne $width) { $bad += $i + 1 }
            if ($line -match '^\s*\|[\s:|-]+\|\s*$') { $rule = $true }
            $rows++
        } elseif ($rows) {
            if (-not $rule) { $ruleless += "$($d.Name):$start, $rows row(s) with no header rule" }
            $rows = 0; $rule = $false
        }
    }
    if ($bad.Count) { $ragged += Format-Sites $d.Name $bad }
}

Report 'file(s) with a table row of the wrong width' $ragged 'every table row is the width its header declares'
Report 'run(s) of table rows carrying no header rule:' $ruleless 'every table row belongs to a table with a header rule'
""

# =================================================================================
# glyphs: punctuation the house style forbids, and the encoding damage that mimics it
# =================================================================================
#
# The groups above check what a document says. This one checks what it is made of,
# where two unrelated faults share one symptom, a wrong character, and neither survives
# a rendered read: the em-dash is against house style (the punctuation here is explicit,
# so a clause takes a comma, a colon, parentheses, or its own sentence), and mojibake is
# UTF-8 read as some single-byte encoding, which leaves a signature worth catching the
# moment it lands.
#
# Both are reported per file with the lines to visit, and neither is repaired. An em-dash
# is removed by deciding what the sentence meant; a mangled character can only be restored
# by whoever knows what it was.
#
# The rule is absolute, and that is a decision rather than an oversight. It stood failing
# across nine files for as long as it did because it conflated prose punctuation with two
# structural uses that no rewrite can reach: the register's entry header (`**R-nn-nnn**
# MUST — obligation`) and its section headings (`## §n — Title`), a delimiter and a title
# separator, one per requirement and one per section. Neither has a sentence whose meaning
# could be decided. Both were changed to ASCII (`MUST: ` and `## §n. `) rather than
# exempted here, because an exemption is a proviso that must itself be audited, and a rule
# with no carve-out is closed by construction: any U+2014 anywhere is a finding, and a
# table cell meaning *not applicable* is spelled `n/a` rather than left as a bare dash.

"=== glyphs: forbidden punctuation and encoding damage ==="

$emDash = [char]0x2014

# A lead byte of a multi-byte UTF-8 sequence, decoded as Latin-1 or CP1252, followed by a
# continuation byte decoded the same way. The second class is the whole high half of both
# encodings, so the mangling of any character is caught, not just the common ones.
$cp1252 = '\u0080-\u00BF\u0152\u0153\u0160\u0161\u017D\u017E\u0178\u0192\u02C6\u02DC' +
          '\u2013\u2014\u2018-\u201A\u201C-\u201E\u2020-\u2022\u2026\u2030\u2039\u203A\u20AC\u2122'
$mojibake = [regex]"[\u00C2\u00C3\u00E2\u00F0][$cp1252]|\uFFFD"

$emHits = @(); $mojibakeHits = @()
foreach ($d in $docs) {
    $em = @(); $mb = @()
    for ($i = 0; $i -lt $d.Lines.Count; $i++) {
        if ($d.Lines[$i].Contains($emDash))  { $em += $i + 1 }
        if ($mojibake.IsMatch($d.Lines[$i])) { $mb += $i + 1 }
    }
    if ($em.Count) { $emHits       += Format-Sites $d.Name $em }
    if ($mb.Count) { $mojibakeHits += Format-Sites $d.Name $mb }
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
