# Checks every derived fact in this repository against the artifact that owns it.
#
# A derived fact is anything one document holds only because another document already
# determined it. Restated by hand it drifts silently, in whichever direction nobody
# looked, which is the defect the register's sweep 2 names. The defect takes seven
# granularities, and they are one mistake, so they are one tool:
#
#   traces   the reference    every bookmark a trace cites, and the section it displays
#   names    the vocabulary   every R-, CJ-, A-, B- and P- id used, against its declarer
#   links    the pointer      every cross-document link and every §n.m a sentence names
#   views    the membership   what a derived view carries, checked in both directions
#   confers  the enumeration  every set closed by conferral, and the agenda for what it misses
#   counts   the cardinality  every figure any document asserts, against its artifact
#   compounds the arithmetic  the archetype band against the product of the rows beneath it
#
# Two further groups check what a document is made of rather than what it says, where a
# fault survives a rendered read because the render succeeds:
#
#   tables   the shape        every row against the width its header declares
#   glyphs   the characters   punctuation the house style forbids, and encoding damage
#
# Run with -Fix to rewrite the asserted counts, and the compounded product, from their
# artifacts. Every other finding has no mechanical repair: it is a person's edit,
# reported not guessed.
#
# Exit 0 clean, 1 on any finding. Run from the repository root.

[CmdletBinding()]
param([switch]$Fix)

$ErrorActionPreference = 'Stop'

$findings = 0
function Report([string]$Label, $Items, [string]$Ok = '', [string]$Pad = '') {
    # @($null).Count is 1, and an empty pipeline result is $null, so filter before counting
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
#
# Each document keeps its raw text beside its lines, plus a table of line-start
# offsets. The groups below scan the raw text once with one regex and resolve a hit
# back to its line by binary search, rather than walking every line once per group;
# the reports are the same, arrived at in one pass instead of many.

function Get-LineIndex([int[]]$Starts, [int]$Offset) {
    # the 0-based line containing a raw-text offset
    $i = [System.Array]::BinarySearch($Starts, $Offset)
    if ($i -lt 0) { $i = -$i - 2 }
    $i
}

# [^\S\r\n] is \s minus the line breaks, which on a single line is the same class;
# over the raw text it keeps ^ from drifting across a blank line onto the fence
$fenceRe = [regex]'(?m)^[^\S\r\n]*```'

$mdOpts = [System.IO.EnumerationOptions]::new()   # skips hidden and system, as the provider does
$mdOpts.RecurseSubdirectories = $true
$mdFiles = [System.IO.Directory]::GetFiles($PWD.Path, '*.md', $mdOpts)
[System.Array]::Sort($mdFiles)

# a submodule's markdown is upstream prose, not this corpus: every path .gitmodules books
# is a pinned start-from whose documents answer to their own repository, so the sweep
# excludes them wholesale rather than holding them to a house style they never saw;
# model/ is the same prose vendored rather than pinned, the curated tree M0.6a stands
# up from the sail-riscv blobs, so it is excluded on the same rationale
$subPaths = @(if (Test-Path (Join-Path $PWD.Path '.gitmodules')) {
    foreach ($m in [regex]::Matches([System.IO.File]::ReadAllText((Join-Path $PWD.Path '.gitmodules')), '(?m)^\s*path\s*=\s*(\S+)')) {
        [System.IO.Path]::GetFullPath((Join-Path $PWD.Path $m.Groups[1].Value)) + [System.IO.Path]::DirectorySeparatorChar
    }
})
$subPaths += [System.IO.Path]::GetFullPath((Join-Path $PWD.Path 'model')) + [System.IO.Path]::DirectorySeparatorChar
if ($subPaths.Count) {
    $mdFiles = @($mdFiles | Where-Object { $f = $_; -not @($subPaths | Where-Object { $f.StartsWith($_) }).Count })
}

$docs = @(foreach ($f in $mdFiles) {
    $raw   = [System.IO.File]::ReadAllText($f)
    $lines = [System.IO.File]::ReadAllLines($f)

    # one split hands back every segment with its terminator's length implied, so the
    # offsets accumulate without touching the text again
    $parts  = $raw.Split([char]10)
    $starts = New-Object 'int[]' $parts.Count
    $off = 0; $i = 0
    foreach ($p in $parts) { $starts[$i++] = $off; $off += $p.Length + 1 }

    # every fence marker toggles, so the odd-even pairs span the displayed lines,
    # markers included; an unclosed fence displays to the end of the file. The match
    # is ^-anchored, so its offset is a line start and the search is an exact hit.
    $fenced = New-Object 'bool[]' $lines.Count
    $marks  = @(foreach ($m in $fenceRe.Matches($raw)) { [System.Array]::BinarySearch($starts, $m.Index) })
    for ($k = 0; $k -lt $marks.Count; $k += 2) {
        $a = $marks[$k]
        $b = if ($k + 1 -lt $marks.Count) { $marks[$k + 1] } else { $lines.Count - 1 }
        for ($j = $a; $j -le $b; $j++) { $fenced[$j] = $true }
    }

    [pscustomobject]@{
        Name   = [System.IO.Path]::GetRelativePath($PWD.Path, $f) -replace '^\.[\\/]', '' -replace '\\', '/'
        Raw    = $raw
        Lines  = $lines
        Starts = $starts
        Fenced = $fenced
    }
})

$docByName = @{}
foreach ($d in $docs) { $docByName[$d.Name] = $d }

# --- the register: ids, where each sits, its body, and the trace it carries -------

$regLines   = $docByName['docs/requirements-register.md'].Lines
$ids        = [System.Collections.Generic.List[string]]::new()
$cjTargets  = [System.Collections.Generic.List[string]]::new()
$subsection = @{}          # id -> "15.4", the ### n.m it sits in, where there is one
$body       = @{}          # id -> the entry line itself
$traceOf    = @{}          # id -> its · Trace: line
$perSection = [ordered]@{} # section -> entry count, in document order
$confers    = @{}          # "Fail-closed"/"RoT-fresh" -> (id -> its conferral line)
$accepts    = @{}          # id -> how many conjunctive · Accept: lines it carries
$lateAccept = @()          # ids stating a criterion after a conferral or the trace
$dcsrRows   = 0

# every line kind this parse reads announces itself in its first character, so the
# dispatch below spends a regex only on the few lines whose kind it could be
$sec = $null; $sub = $null; $current = $null; $entry = $null
$sawTail = $false; $inDefects = $false
foreach ($line in $regLines) {
    if ($line.Length -eq 0) { continue }
    switch ($line[0]) {
        '#' {
            if ($line -match '^## §(\d+)') {
                $sec = $Matches[1]; $sub = $null
                if (-not $perSection.Contains($sec)) { $perSection[$sec] = 0 }
            }
            elseif ($line -match '^### (\d+\.\d+) ')       { $sub = $Matches[1] }
            elseif ($line -match '^## Extraction defects') { $inDefects = $true }
        }
        '*' {
            if ($line -match '^\*\*(R-\d\d-\d+[a-z]?)\*\* (IS|MUST NOT|MUST)') {
                $current = $Matches[1]
                $entry   = $current
                $sawTail = $false
                $ids.Add($current)
                $subsection[$current] = $sub
                $body[$current]       = $line
                $accepts[$current]    = 0
                if ($sec) { $perSection[$sec]++ }
            }
        }
        '·' {
            if ($entry -and $line -match '^· Accept:') {
                # criteria are conjunctive, and they come before the lines that follow them:
                # $entry outlives the trace where $current does not, so one written below the
                # trace is caught here rather than going uncounted
                $accepts[$entry]++
                if ($sawTail) { $lateAccept += $entry }
            } elseif ($current -and $line -match '^· (Fail-closed|RoT-fresh):') {
                # a property line conferring membership in a set some other entry collects
                $kind = $Matches[1]
                if (-not $confers.ContainsKey($kind)) { $confers[$kind] = [ordered]@{} }
                $confers[$kind][$current] = $line
                $sawTail = $true
            } elseif ($current -and $line -match '^· Trace:') {
                $traceOf[$current] = $line
                $current = $null
                $sawTail = $true
            }
        }
        '|' {
            if ($line -match '^\| `(CJ-[A-Z-]+)`')        { $cjTargets.Add($Matches[1]) }
            elseif ($inDefects -and $line -match '^\| `') { $dcsrRows++ }
        }
    }
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

$anchorRe   = [regex]'<a id="([^"]+)"'
$proseSecRe = [regex]'(?m)^## (\d+)\.'

foreach ($d in $docs) {
    $prose = $d.Name -eq 'docs/spec.md'
    $here  = @{}
    $starts = $d.Starts

    # the prose's section headings, by offset, so each anchor takes the §n of the
    # last heading above it; the heading match is ^-anchored, an exact line start
    $headOffs = $null; $headSecs = $null
    if ($prose) {
        $ho = [System.Collections.Generic.List[int]]::new()
        $hs = [System.Collections.Generic.List[string]]::new()
        foreach ($m in $proseSecRe.Matches($d.Raw)) {
            if ($d.Fenced[[System.Array]::BinarySearch($starts, $m.Index)]) { continue }
            $ho.Add($m.Index); $hs.Add($m.Groups[1].Value)
        }
        $headOffs = $ho.ToArray(); $headSecs = $hs
    }

    foreach ($m in $anchorRe.Matches($d.Raw)) {
        $i = [System.Array]::BinarySearch($starts, $m.Index)
        if ($i -lt 0) { $i = -$i - 2 }
        $id = $m.Groups[1].Value
        if ($d.Fenced[$i]) {
            $buried += "$($d.Name):$($i + 1) buries #$id in a fenced block, where it is text and not a bookmark"
            continue
        }
        $here[$id] = 1 + $here[$id]
        if ($here[$id] -eq 2) { $twiceHere += "$($d.Name) declares #$id more than once; a link to it resolves to whichever comes first" }
        if ($prose) {
            $anchorCount[$id] = 1 + $anchorCount[$id]
            if (-not $anchorSec.ContainsKey($id)) {
                $j = [System.Array]::BinarySearch($headOffs, $m.Index)
                if ($j -lt 0) { $j = -$j - 2 }
                $anchorSec[$id] = if ($j -ge 0) { $headSecs[$j] } else { $null }
            }
        }
    }
    $anchorsOf[$d.Name] = $here
}

# --- the counted artifacts: the inventory, the profile, the absence contract ------

$cj = $docByName['docs/crown-jewels.md'].Lines
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

$absenceIds = @($docByName['docs/absence-contract.md'].Lines |
                ForEach-Object { if ($_ -match '^\| \*\*(A-\d+)\*\*') { $Matches[1] } })

$openCsr = 0; $inOpen = $false
foreach ($line in $docByName['docs/isa-profile.md'].Lines) {
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
foreach ($line in $docByName['docs/coverage-matrix.md'].Lines) {
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
#
# The citation itself is now derived rather than written: a trace naming only its crown
# jewels cites #r-<id>, the bookmark its own requirement number gives. That closes the
# last place the register carried a derived fact by hand, and it is the counts group's
# rule applied to a reference instead of a figure, so the third property below is the
# one that keeps it closed: a trace written out where the derived form would do is a
# restatement, and is reported exactly as an unheld figure is.

"=== traces: the register's references against the prose ==="

$traceLinkRe = [regex]'\[§([\d.]+)\]\(spec\.md#([^)]+)\)'

$badTarget = @(); $wrongSec = @(); $restated = @()
foreach ($id in $ids) {
    $t = $traceOf[$id]
    if (-not $t) { continue }
    $derived = 'r-' + $id.Substring(2).ToLower()

    if (-not $t.Contains('[§')) {
        # the derived form: one citation, at the bookmark the id names
        if (-not $anchorCount.ContainsKey($derived)) {
            $badTarget += "$id derives #$derived, which is no bookmark in the prose"
        }
        continue
    }
    $links = $traceLinkRe.Matches($t)

    if ($links.Count -eq 0) {
        # '[§' present but not this reference's shape, so it is no citation at all
        if (-not $anchorCount.ContainsKey($derived)) {
            $badTarget += "$id derives #$derived, which is no bookmark in the prose"
        }
        continue
    }

    # written out, so it departs from the derived form and must say how
    foreach ($m in $links) {
        $anchor = $m.Groups[2].Value
        if (-not $anchorCount.ContainsKey($anchor)) { $badTarget += "$id cites #$anchor, which is no bookmark in the prose" }

        $shown  = ($m.Groups[1].Value -split '\.')[0]
        $actual = $anchorSec[$anchor]
        if ($actual -and $shown -ne $actual) {
            $wrongSec += "$id shows §$shown for #$anchor, which sits in §$actual"
        }
    }

    # a second citation, another requirement's bookmark, or a note after the link are the
    # three departures; anything else written out is the derived citation, spelled by hand
    $tail = $traceLinkRe.Replace($t, '')
    if ($links.Count -eq 1 -and $links[0].Groups[2].Value -eq $derived -and -not $tail.Contains(';')) {
        $restated += "$id writes out #$derived, which its id already derives"
    }
}
Report 'unresolvable trace target(s)' $badTarget 'every cited bookmark resolves'

Report 'trace(s) restating the derived citation:' $restated 'every trace is derived, or departs from the derived form'

Report 'bookmark(s) declared more than once in one document' $twiceHere 'every bookmark id is unique where it is declared'

Report 'bookmark(s) buried in a fenced block' $buried 'every bookmark is addressable where it is written'

Report 'requirement(s) with no trace' @(foreach ($id in $ids) { if (-not $traceOf.ContainsKey($id)) { $id } }) 'every requirement carries a trace'

# An entry with no criterion is an obligation nothing decides, which is the one thing
# this register is for; an entry whose criteria straddle its conferrals reads as though
# the lines below the first one were something other than the rest of the criterion.

Report 'requirement(s) with no acceptance criterion:' `
    @(foreach ($id in $ids) { if (-not $accepts[$id]) { "$id carries no · Accept: line" } }) `
    'every requirement carries at least one acceptance criterion'

Report 'requirement(s) whose criteria straddle a conferral or the trace:' `
    @($lateAccept | Select-Object -Unique | ForEach-Object { "$_ states a criterion below a line that must follow the criteria" }) `
    'every entry states its criteria before its conferrals and its trace'

# r-ss-nnn, r-ss-nnna (a letter-suffixed requirement) and r-ss-nnn-2 (the nth citation
# of one requirement) all resolve to the same register id.
$idSet = [System.Collections.Generic.HashSet[string]]::new($ids)
$orphans = @()
foreach ($id in $anchorCount.Keys) {
    if ($id -notmatch '^r-\d\d-\d') { continue }
    $reqId = 'R' + ($id -replace '^(r-\d\d-\d\d\d[a-z]?)-\d+$', '$1').Substring(1)
    if (-not $idSet.Contains($reqId)) { $orphans += "#${id}: no requirement $reqId in the register" }
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

$idTally = [ordered]@{}
foreach ($id in $ids) { $idTally[$id] = 1 + $idTally[$id] }
Report 'requirement id(s) the register declares twice:' `
       @(foreach ($k in $idTally.Keys) { if ($idTally[$k] -gt 1) { "$k, declared $($idTally[$k]) times" } }) `
       "all $($ids.Count) register ids are distinct"

$vocab = @(
    @{ Kind = 'requirement';        Token = 'R-\d\d-\d+[a-z]?'; Declared = $ids;        Home = 'the register' }
    @{ Kind = 'crown-jewel target'; Token = 'CJ-[A-Z][A-Z-]*';  Declared = $cjTargets;  Home = "the register's CJ- table" }
    @{ Kind = 'absence';            Token = 'A-\d+';            Declared = $absenceIds; Home = 'docs/absence-contract.md' }
    @{ Kind = 'boundary';           Token = 'B-\d+';            Declared = $cmBounds;   Home = 'docs/coverage-matrix.md' }
    @{ Kind = 'property';           Token = 'P-\d+';            Declared = $cmProps;    Home = 'docs/coverage-matrix.md' }
)

# the five tokens start with five different letters, so one alternation walks the
# corpus once and the first letter of each hit picks its vocabulary back out
$byInitial = @{}
foreach ($v in $vocab) {
    $v.DeclaredSet = [System.Collections.Generic.HashSet[string]]::new([string[]]@($v.Declared))
    $v.Unknown     = [System.Collections.Generic.List[string]]::new()
    $byInitial[[string]$v.Token[0]] = $v
}
$namesRe = [regex]::new('(?<![\w-])(?:' + (($vocab | ForEach-Object { $_.Token }) -join '|') + ')(?![\w-])', 'Compiled')

# a declared id is the overwhelming case and needs no line, so it is one set lookup;
# only an unknown id pays for finding its line, and a fenced one names nothing anyway
foreach ($d in $docs) {
    $starts = $d.Starts; $fenced = $d.Fenced
    foreach ($m in $namesRe.Matches($d.Raw)) {
        $v = $byInitial[[string]$m.Value[0]]
        if ($v.DeclaredSet.Contains($m.Value)) { continue }
        $i = [System.Array]::BinarySearch($starts, $m.Index)
        if ($i -lt 0) { $i = -$i - 2 }
        if ($fenced[$i]) { continue }
        $v.Unknown.Add("$($d.Name):$($i + 1) uses $($m.Value), which $($v.Home) does not declare")
    }
}

foreach ($v in $vocab) {
    Report "$($v.Kind) id(s) naming nothing:" $v.Unknown `
           "every $($v.Kind) id used names one of the $($v.DeclaredSet.Count) $($v.Home) declares"
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
# than one document's, because the numbering is shared: §5.2 is the register's
# subsection and the profile's CSR section, and which is meant is the sentence's
# business. What the check holds is the weaker property that closes the drift: a number
# no document carries at all is a reference to a section that has been renumbered away.

"=== links: every cross-reference against what it points at ==="

$headRe   = [regex]'(?m)^#{1,6}[ \t]+([^\r\n]+)'
$linkRe   = [regex]'\]\(([^)\s#]*)(?:#([^)\s]+))?\)'
$secRefRe = [regex]'§(\d+(?:\.\d+)*)'

$targets  = @{}   # file -> every id a link may name: its bookmarks and its heading slugs
$numbered = @{}   # "15.12" -> the number is carried by a heading somewhere
foreach ($d in $docs) {
    $set = [System.Collections.Generic.HashSet[string]]::new([string[]]@($anchorsOf[$d.Name].Keys))
    foreach ($m in $headRe.Matches($d.Raw)) {
        if ($d.Fenced[[System.Array]::BinarySearch($d.Starts, $m.Index)]) { continue }
        $heading = $m.Groups[1].Value
        # the slug rule: tags and backticks vanish, punctuation vanishes, spaces hyphenate
        [void]$set.Add((($heading -replace '<[^>]+>', '' -replace '`', '').Trim().ToLower() -replace '[^\w\s-]', '' -replace '\s+', '-'))
        if ($heading -match '^§?(\d+(?:\.\d+)*)[.:) ]') { $numbered[$Matches[1]] = $true }
    }
    $targets[$d.Name] = $set
}

# a link that resolves and a §n.m a heading carries are the overwhelming cases and
# report nothing, so each is judged before its line is looked up; only a would-be
# finding pays for the line, and one a fence displays is dropped there as text
$dead = @(); $unnumbered = [ordered]@{}; $exists = @{}
foreach ($d in $docs) {
    $starts = $d.Starts
    foreach ($m in $linkRe.Matches($d.Raw)) {
        $file = $m.Groups[1].Value -replace '^\./', ''
        $frag = $m.Groups[2].Value
        if ($file -match '^[a-z][a-z0-9+.-]*:') { continue }   # off the repository, not ours to hold
        # a relative target resolves against the document that carries it, not the root
        $file = if (-not $file) { $d.Name } else {
            $dir = [System.IO.Path]::GetDirectoryName($d.Name)
            [System.IO.Path]::GetRelativePath($PWD.Path,
                [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($PWD.Path, $dir, $file))) -replace '\\', '/'
        }
        if (-not $exists.ContainsKey($file)) {
            $abs = [System.IO.Path]::Combine($PWD.Path, $file)
            $exists[$file] = [System.IO.File]::Exists($abs) -or [System.IO.Directory]::Exists($abs)
        }
        $bad = if (-not $exists[$file]) {
                   "points at $file, which is not in the repository"
               } elseif ($frag -and $targets.ContainsKey($file) -and -not $targets[$file].Contains($frag)) {
                   "points at $file#$frag, which is no bookmark or heading there"
               }
        if (-not $bad) { continue }
        $i = [System.Array]::BinarySearch($starts, $m.Index)
        if ($i -lt 0) { $i = -$i - 2 }
        if ($d.Fenced[$i]) { continue }
        $dead += "$($d.Name):$($i + 1) $bad"
    }

    foreach ($m in $secRefRe.Matches($d.Raw)) {
        $n = $m.Groups[1].Value
        if ($numbered.Contains($n)) { continue }
        $i = [System.Array]::BinarySearch($starts, $m.Index)
        if ($i -lt 0) { $i = -$i - 2 }
        if ($d.Fenced[$i]) { continue }
        if (-not $unnumbered.Contains($n)) { $unnumbered[$n] = @() }
        $unnumbered[$n] += "$($d.Name):$($i + 1)"
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
    @{ File = 'docs/isa-profile.md'
       Governing = 'R-15-001a'
       Secs = '15.1','15.3','15.4','15.5','15.6','15.7','15.8','15.9','15.10','15.11','15.12' }
    @{ File = 'docs/absence-contract.md'
       Governing = 'R-15-100a'
       Secs = '15.14' }
    @{ File = 'docs/crown-jewels.md'
       Governing = 'R-17-016a'
       BodyPattern = 'crown.jewel spec'
       MustCiteTargets = $true }
    @{ File = 'docs/coverage-matrix.md'
       Governing = 'R-17-001b'
       MustCoverCells = $true }
)

$reqTokenRe = [regex]'R-\d\d-\d+[a-z]?'

"=== views: what each derived view carries, both directions ==="
foreach ($v in $views) {
    "$($v.File) (per $($v.Governing))"
    if (-not (Test-Path $v.File)) { "  FAIL: missing"; $findings++; continue }

    $cited = [System.Collections.Generic.HashSet[string]]::new()
    foreach ($m in $reqTokenRe.Matches($docByName[$v.File].Raw)) { [void]$cited.Add($m.Value) }

    if ($v.Secs) {
        $uncovered = @(foreach ($k in $subsection.Keys) {
            if ($subsection[$k] -in $v.Secs -and -not $cited.Contains($k)) { $k }
        }) | Sort-Object
        Report 'bearing requirement(s) not carried:' $uncovered 'all bearing requirements are carried' '  '
    } elseif ($v.BodyPattern) {
        $uncovered = @(foreach ($k in $body.Keys) {
            if ($body[$k] -match $v.BodyPattern -and -not $cited.Contains($k)) { $k }
        }) | Sort-Object
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
        $raw = $docByName[$v.File].Raw
        Report 'CJ- target(s) unaccounted for:' @($cjTargets | Where-Object { $raw -notmatch [regex]::Escape($_) }) `
               "all $($cjTargets.Count) CJ- targets accounted for" '  '
    }
}
""

# =================================================================================
# confers: every enumeration closed by conferral, and the agenda for what it misses
# =================================================================================
#
# Three sets here are enumerations of a judgment: the crown-jewel specifications, the
# fail-closed refusals, and the state the RoT counter keeps fresh. Each was first
# written as a list somebody believed complete on the day they wrote it, which is the
# failure R-17-016 was repaired for: a list restated anywhere is a list that silently
# stops being the set. The repair was not a better-maintained list but **conferral**,
# where membership is asserted by each requirement that has it and collected in exactly
# one place, so the two can be checked against each other instead of against a memory.
#
# What conferral closes is the collection's disagreement with the requirements, and
# that is all it closes. It cannot decide whether a requirement that *should* confer
# does, because *is a crown jewel*, *fails closed* and *needs freshness* are judgments
# and no tool holds them. Pretending otherwise would put the defect one level up, in a
# checker that certifies a set it cannot see the whole of.
#
# So each set carries a second instrument against that residue, and it is deliberately
# a weak one honestly described: the vocabulary of the judgment is over-approximated
# across every requirement body, and each entry the vocabulary catches must confer, be
# collected, or be dispositioned here by name with a reason. That is lexical and proves
# no totality. What it buys is that the totality claim is discharged against an agenda
# regenerated on every run rather than against a reading nobody repeats, and it is not
# hypothetical: run against the ten-seam fail-closed register it returned the detector
# class (R-17-030n), the entropy health test (R-17-030o), the display path (R-17-030p),
# and budget admission (R-17-030q), none of which any reading had found.
#
# A disposition is a decision, so it is recorded here beside the rule rather than as a
# marker in the prose. A marker would tax the vocabulary instead of the judgment, and
# an author who has to spend a word to avoid a finding rewords the sentence rather than
# making the decision, which is the check defeating its own purpose quietly.

"=== confers: every enumeration closed by conferral, both directions ==="

# --- the crown-jewel inventory: rows against the requirements conferring the status ---
#
# The views group above checks that every conferring requirement reaches the inventory,
# the direction where a row goes missing. This is the other one R-17-016 names, the
# direction where a row is *added*: a specification the view grants the status and the
# register never did. Conferral is the whole membership rule, so a row standing behind
# no conferring requirement is the view legislating, which a derived view may not do.
# Rows only: the theorem table is targets, not specifications.

$cjConfer = @(foreach ($k in $body.Keys) { if ($body[$k] -match 'crown.jewel spec') { $k } })
Report 'crown-jewel row(s) no requirement confers:' `
       @(foreach ($row in $cjRows) {
           $cites = @([regex]::Matches($row, 'R-\d\d-\d+[a-z]?') | ForEach-Object { $_.Value })
           if (-not @($cites | Where-Object { $_ -in $cjConfer }).Count) {
               "row $((($row -split '\|')[1]).Trim()): $((($row -split '\|')[2]).Trim())"
           }
       }) "every row cites one of the $($cjConfer.Count) requirements that confer the status"

# --- the fail-closed seam register: conferrals against the seams that collect them ----
#
# Here the collection is not a separate document but the R-17-030 seam entries, each
# naming the requirements whose refusal it composes (R-17-030r). Both directions are
# owed and they fail differently: a conferral no seam collects is a refusal booked
# correctly in its own section and absent from the composition, which R-03-008 already
# calls a review-gate finding and nothing enforced until now; a seam collecting no
# conferral is the register composing a refusal no requirement specifies.

$fcSeams  = @(foreach ($k in $body.Keys) { if ($body[$k] -match 'Fail-closed seam \*\*') { $k } })
$fcConfer = @(if ($confers.ContainsKey('Fail-closed')) { $confers['Fail-closed'].Keys })
$fcCited  = @{}
foreach ($s in $fcSeams) {
    foreach ($m in [regex]::Matches($body[$s], 'R-\d\d-\d+[a-z]?')) { $fcCited[$m.Value] = $s }
}

Report 'fail-closed conferral(s) no seam collects:' `
       @($fcConfer | Where-Object { -not $fcCited.ContainsKey($_) } |
         ForEach-Object { "$_ confers a refusal no R-17-030 seam names" }) `
       "all $($fcConfer.Count) conferred refusals reach the register"

Report 'fail-closed seam(s) no requirement confers:' `
       @(foreach ($s in $fcSeams) {
           $cites = @([regex]::Matches($body[$s], 'R-\d\d-\d+[a-z]?') | ForEach-Object { $_.Value })
           if (-not @($cites | Where-Object { $_ -in $fcConfer }).Count) {
               "$s composes a refusal no requirement confers"
           }
       }) "all $($fcSeams.Count) seams stand on a conferred refusal"

# --- the RoT-fresh enumeration: conferrals against the entry that collects them -------
#
# The collection here is one entry's prose enumeration rather than a row or a seam, so
# only the outbound direction is symbolic: every conferral names R-10-013. The inbound
# direction is the count claim below, which fails when a conferral is added and the
# enumeration it must join is not amended.

$rfConfer = @(if ($confers.ContainsKey('RoT-fresh')) { $confers['RoT-fresh'].Keys })
Report 'RoT-fresh conferral(s) not naming the enumeration:' `
       @($rfConfer | Where-Object { $confers['RoT-fresh'][$_] -notmatch 'R-10-013' } |
         ForEach-Object { "$_ confers freshness without citing R-10-013" }) `
       "all $($rfConfer.Count) conferred states name the enumeration"

# --- the agenda: what the vocabulary catches and the conferral did not ----------------

$agendas = @(
    @{ Set   = 'fail-closed'
       Vocab = 'fail-stop|fail-closed|fail closed|refuse|refuses|refused|refusal|denial of service|permanent DoS'
       Held  = @($fcConfer) + @($fcCited.Keys) + @($fcSeams)
       # the entries that state the set rather than belonging to it
       Ruling = 'R-03-008','R-03-009','R-17-030a','R-17-030l','R-17-030m','R-17-030r','R-17-030t'
       Disposition = [ordered]@{
           'R-03-003'  = 'threat scope, not a refusal: the refusals an EM adversary provokes are composed at R-17-030n'
           'R-05-051c' = 'a specification-time exclusion: the role is denied to a format when its descriptor is written, and no running unit stops'
           'R-05-118'  = 'an instance of the admission refusal composed at R-17-030e'
           'R-05-125'  = 'the same admission refusal, stated as the contrast with a runtime trap'
           'R-08-008'  = 'a denial priced out structurally, not a refusal the platform performs'
           'R-08-019'  = 'an instance of the budget refusal composed at R-17-030q'
           'R-10-013g' = 'states that the R-10-013e refusal survives the lever; specifies no refusal of its own'
           'R-12-093'  = 'a status vocabulary: its refused arm names the completion a server publishes, the capacity refusal itself conferred at R-12-095'
           'R-12-099'  = 'the teardown half of the ring contract: stale-generation refusal is the R-12-095-conferred discipline seen from restart, and its fail-stop is an instance of the §16 supervision policy'
           'R-13-014'  = 'the policy name for the admission refusal composed at R-17-030e'
           'R-14-010'  = 'a designed non-refusal, kept for the contrast: past the ceiling the browser evicts and the platform does not refuse'
           'R-15-155'  = 'the countermeasure, whose caught-fault path is the refusal composed at R-17-030n'
           'R-15-177a' = 'an instance of the uncorrectable-ECC fail-stop R-15-179 specifies, composed at R-17-030n'
           'R-17-013e' = 'a consent residual: the refusing party is the user on reflection, and the refused mechanisms are declined at specification time; no failure action, nothing stops'
           'R-17-034'  = 'the sharpest instance of the admission refusal composed at R-17-030e'
           'R-17-047'  = 'a tooling choice refused at specification time, with no runtime failure action'
           'R-17-058b' = 'the residual beyond the R-16-008f fault model behind R-17-030n detectors, not a refusal of its own'
       } }

    @{ Set   = 'RoT-fresh'
       Vocab = 'monotonic counter|monotonic anti-rollback|monotonic attempt counter|anti-rollback floor|freshness-protected'
       Held  = @($rfConfer)
       Ruling = 'R-10-013','R-10-013a'
       Disposition = [ordered]@{
           'R-06-005' = 'enforces the floor R-09-028 confers; places no further state under the counter'
           'R-06-022' = 'enforces the same floor from the untrusted side'
           'R-09-001' = 'provides the counter; places no state under it'
           'R-09-005' = 'checks the floor before executing a byte; places no state under it'
           'R-09-008' = 'provides the counter operations as a functional surface'
           'R-09-013' = 'a property of the counter, that it is not a clock'
           'R-09-030' = 'bounds bootability by the floor R-09-028 confers'
           'R-10-011' = 'the recorded exclusion R-10-013i requires: the mutable volume is deliberately outside the set'
           'R-10-013b' = 'classifies the state the counter carries; the class it names is placed under the counter by R-10-013c'
           'R-10-013d' = 'bounds the rate at which R-10-013c may advance the counter; places no state under it'
           'R-10-013f' = 'names the device fact R-10-011 excludes on; places no state under the counter and changes nothing until R-10-013g is met'
           'R-10-031' = 'selects a root within the floor; places no state under the counter'
           'R-11-002' = 'pins a root subject to the floor; places no state under the counter'
           'R-16-008' = 'the same pinning through the trusted transactor'
       } }
)

$dispositions = @($agendas | ForEach-Object { $_.Disposition.Count } | Measure-Object -Sum).Sum
$rotCases     = @($agendas | Where-Object { $_.Set -eq 'RoT-fresh' }).Disposition.Count

foreach ($a in $agendas) {
    $held = [System.Collections.Generic.HashSet[string]]::new([string[]](@($a.Held) + @($a.Ruling) + @($a.Disposition.Keys)))
    $open = @(foreach ($id in $ids) { if ($body[$id] -match $a.Vocab -and -not $held.Contains($id)) { $id } })
    Report "$($a.Set) candidate(s) neither conferred nor dispositioned:" `
           @($open | ForEach-Object { "$_ uses the vocabulary of $($a.Set) and is in no column" }) `
           "every $($a.Set) candidate is conferred, collected, or dispositioned"
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

$lettered = 0; foreach ($id in $ids) { if ($id -match '[a-z]$') { $lettered++ } }
$seams = 0; foreach ($k in $body.Keys) { if ($body[$k] -match ' Seam: \*\*') { $seams++ } }

$q = [ordered]@{
    'requirements'  = $ids.Count
    'lettered'      = $lettered
    'sections'      = $perSection.Count
    'cj-targets'    = $cjTargets.Count
    'dcsr-rows'     = $dcsrRows
    'open-csr-rows' = $openCsr
    'cj-specs'      = $cjRows.Count
    'cj-authored'   = @($cjRows | Where-Object { (Get-CjClass $_) -eq 'authored' }).Count
    'cj-partial'    = @($cjRows | Where-Object { (Get-CjClass $_) -eq 'partial' }).Count
    'cj-unauthored' = @($cjRows | Where-Object { (Get-CjClass $_) -eq 'unauthored' }).Count
    'cj-theorems'   = @($cj | Where-Object { $_ -match '^\| `CJ-[A-Z-]+` \|' }).Count
    'cj-conferring' = $cjConfer.Count
    'seams'         = $seams
    'fc-seams'      = $fcSeams.Count
    'fc-conferrals' = $fcConfer.Count
    'rot-fresh'     = $rfConfer.Count
    'dispositions'  = $dispositions
    'rot-cases'     = $rotCases
    'views'         = $views.Count
    'boundaries'    = $cmBounds.Count
    'properties'    = $cmProps.Count
    'cells'         = $cmCells.Count
    'absences'      = $absenceIds.Count
}

$claims = @(
    # the register states its own coverage
    @{ File = 'docs/requirements-register.md'; Q = 'sections';      Style = 'words';  Pattern = '[\w-]+(?= normative sections are extracted)' }
    @{ File = 'docs/requirements-register.md'; Q = 'requirements';  Style = 'digits'; Pattern = '(?<=extracted, at )[\d,]+(?= requirements)' }
    @{ File = 'docs/requirements-register.md'; Q = 'lettered';      Style = 'digits'; Pattern = '(?<=Counts include the )[\w,-]+(?= letter-suffixed entries)' }

    # the crown-jewel inventory states its own status ratio
    @{ File = 'docs/crown-jewels.md'; Q = 'cj-targets';    Style = 'digits'; Pattern = '[\d]+(?= entries, all used)' }
    @{ File = 'docs/crown-jewels.md'; Q = 'cj-theorems';   Style = 'words';  Pattern = '(?<=The remaining )[\w-]+(?= `CJ-` targets name)' }
    @{ File = 'docs/crown-jewels.md'; Q = 'cj-unauthored'; Style = 'words';  Pattern = '[\w-]+(?= of those [\w-]+ are not authored)' }
    @{ File = 'docs/crown-jewels.md'; Q = 'cj-specs';      Style = 'words';  Pattern = '(?<=of those )[\w-]+(?= are not authored)' }
    @{ File = 'docs/crown-jewels.md'; Q = 'cj-targets';    Style = 'digits'; Pattern = '[\d]+(?= targets, every one used)' }
    @{ File = 'docs/crown-jewels.md'; Q = 'cj-targets';    Style = 'digits'; Pattern = '[\d]+(?= coarse targets)' }
    @{ File = 'docs/crown-jewels.md'; Q = 'cj-specs';      Style = 'digits'; Pattern = '[\d]+(?= specifications, per-member)' }
    @{ File = 'docs/crown-jewels.md'; Q = 'cj-authored';   Style = 'words';  Pattern = '[\w-]+(?= of [\w-]+ are authored outright)' }
    @{ File = 'docs/crown-jewels.md'; Q = 'cj-specs';      Style = 'words';  Pattern = '(?<=of )[\w-]+(?= are authored outright)' }
    @{ File = 'docs/crown-jewels.md'; Q = 'cj-partial';    Style = 'words';  Pattern = '(?<=and )[\w-]+(?= more are partial)' }
    @{ File = 'docs/crown-jewels.md'; Q = 'cj-specs';      Style = 'words';  Pattern = '(?<=because these )[\w-]+(?= are \*named)' }
    @{ File = 'docs/crown-jewels.md'; Q = 'cj-unauthored'; Style = 'words';  Pattern = '[\w-]+(?= of them are not yet written)' }
    @{ File = 'docs/crown-jewels.md'; Q = 'cj-theorems';   Style = 'words';  Pattern = '(?<=the )[\w-]+(?= theorem targets above cannot start)' }
    @{ File = 'docs/crown-jewels.md'; Q = 'cj-conferring'; Style = 'words';  Pattern = '(?<=There are )[\w-]+(?= such entries)' }

    # the prose states the size of each seam register it carries
    @{ File = 'docs/spec.md'; Q = 'fc-seams'; Style = 'words'; Pattern = '[\w-]+(?= fail-closed seams are named with owners)' }

    # and the register states the shape of each enumeration it closes by conferral
    @{ File = 'docs/requirements-register.md'; Q = 'fc-conferrals'; Style = 'words'; Pattern = '[\w-]+(?= requirements confer a refusal)' }
    @{ File = 'docs/requirements-register.md'; Q = 'fc-seams';      Style = 'words'; Pattern = '(?<=and )[\w-]+(?= seams collect them)' }
    @{ File = 'docs/requirements-register.md'; Q = 'rot-fresh';     Style = 'words'; Pattern = '[\w-]+(?= requirements confer freshness)' }

    # the coverage matrix states the shape of its own product
    @{ File = 'docs/coverage-matrix.md'; Q = 'boundaries'; Style = 'words'; Pattern = '(?<=below are )[\w-]+(?= boundaries)' }
    @{ File = 'docs/coverage-matrix.md'; Q = 'properties'; Style = 'words'; Pattern = '(?<=boundaries and )[\w-]+(?= properties)' }
    @{ File = 'docs/coverage-matrix.md'; Q = 'cells';      Style = 'words'; Pattern = '(?<=carries all )[\w-]+(?= of their pairs)' }

    # the README summarizes them
    @{ File = 'README.md'; Q = 'views';         Style = 'words';  Pattern = '[\w-]+(?= \*\*derived views\*\* collect)' }
    @{ File = 'README.md'; Q = 'sections';      Style = 'words';  Pattern = '(?<=covers all )[\w-]+(?= normative sections)' }
    @{ File = 'README.md'; Q = 'requirements';  Style = 'digits'; Pattern = '(?<=sections as )[\d,]+(?= numbered requirements)' }
    @{ File = 'README.md'; Q = 'absences';      Style = 'words';  Pattern = '[\w-]+(?= enumerated absences)' }
    @{ File = 'README.md'; Q = 'cj-specs';      Style = 'words';  Pattern = '(?<=the )[\w-]+(?= specifications the review gate audits)' }
    @{ File = 'README.md'; Q = 'cj-theorems';   Style = 'words';  Pattern = '(?<=plus the )[\w-]+(?= theorem targets)' }

    # the gap catalogue argues from them
    @{ File = 'docs/critique.md'; Q = 'views';         Style = 'words';  Pattern = '(?<=register and the )[\w-]+(?= derived views)' }
    @{ File = 'docs/critique.md'; Q = 'fc-conferrals'; Style = 'words';  Pattern = '[\w-]+(?= conferrals against)' }
    @{ File = 'docs/critique.md'; Q = 'fc-seams';      Style = 'words';  Pattern = '(?<=conferrals against )[\w-]+(?= seams)' }
    @{ File = 'docs/critique.md'; Q = 'dispositions';  Style = 'words';  Pattern = '[\w-]+(?= candidates were dispositioned)' }
    @{ File = 'docs/critique.md'; Q = 'rot-cases';     Style = 'words';  Pattern = '(?<=[Tt]he )[\w-]+(?= on the RoT-fresh side)' }
    @{ File = 'docs/critique.md'; Q = 'cj-specs';      Style = 'words';  Pattern = '[\w-]+(?= crown-jewel specifications are named)' }
    @{ File = 'docs/critique.md'; Q = 'cj-theorems';   Style = 'words';  Pattern = '[\w-]+(?= theorem targets are named)' }
    @{ File = 'docs/critique.md'; Q = 'cj-specs';      Style = 'words';  Pattern = '(?<=of )[\w-]+(?= crown-jewel specifications, \*\*)' }
    @{ File = 'docs/critique.md'; Q = 'cj-authored';   Style = 'words';  Pattern = '(?<=are named; \*\*)[\w-]+(?=\*\* are authored)' }
    @{ File = 'docs/critique.md'; Q = 'cj-authored';   Style = 'words';  Pattern = '[\w-]+(?= are authored\*\* \(the frozen)' }
    @{ File = 'docs/critique.md'; Q = 'cj-partial';    Style = 'words';  Pattern = '(?<=machine-checked statement\), )[\w-]+(?= are partial)' }
    @{ File = 'docs/critique.md'; Q = 'cj-unauthored'; Style = 'words';  Pattern = '(?<=\*\*)[\w-]+(?= are not authored\*\*)' }
    @{ File = 'docs/critique.md'; Q = 'cj-theorems';   Style = 'words';  Pattern = '(?<=The )[\w-]+(?= theorem targets each depend)' }
    @{ File = 'docs/critique.md'; Q = 'cj-unauthored'; Style = 'words';  Pattern = '[\w-]+(?= of those premises do not exist)' }
    @{ File = 'docs/critique.md'; Q = 'cj-specs';      Style = 'words';  Pattern = '[\w-]+(?= crown jewels, each a small oracle)' }
    @{ File = 'docs/critique.md'; Q = 'requirements';  Style = 'digits'; Pattern = '(?<=of )[\d,]+(?= acceptance criteria)' }
    @{ File = 'docs/critique.md'; Q = 'requirements';  Style = 'digits'; Pattern = '(?<=of the )[\d,]+(?= requirements has yet been booked)' }
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

# A claim pattern opens with a character class or a lookbehind, which the regex engine
# retries at every offset of the file. Every claim also carries a long literal fragment
# it cannot match without, and match plus lookarounds sit on one line, so the fragment
# is found by ordinal IndexOf and the pattern runs only over the lines that carry it.
# A fragment the pattern outgrew falls back to the full scan, so the shortcut can only
# ever be faster, never blinder; hits come back as (Index, Length, Value) spans.
function Get-ClaimHits([string]$Raw, [string]$Pattern) {
    $lit = ''
    foreach ($frag in ($Pattern -split '[\\\[\](){}|?*+.^$<=!]')) {
        if ($frag.Length -gt $lit.Length) { $lit = $frag }
    }
    if ($lit.Length -lt 8) { return [regex]::Matches($Raw, $Pattern) }

    $hits = [System.Collections.Generic.List[object]]::new()
    $seen = [System.Collections.Generic.HashSet[int]]::new()
    $at   = $Raw.IndexOf($lit, [System.StringComparison]::Ordinal)
    while ($at -ge 0) {
        $from = $Raw.LastIndexOf([char]10, $at) + 1
        $to   = $Raw.IndexOf([char]10, $at + $lit.Length)
        if ($to -lt 0) { $to = $Raw.Length }
        foreach ($m in [regex]::Matches($Raw.Substring($from, $to - $from), $Pattern)) {
            if ($seen.Add($from + $m.Index)) {
                $hits.Add([pscustomobject]@{ Index = $from + $m.Index; Length = $m.Length; Value = $m.Value })
            }
        }
        $at = $Raw.IndexOf($lit, $at + 1, [System.StringComparison]::Ordinal)
    }
    if ($hits.Count -eq 0) { return [regex]::Matches($Raw, $Pattern) }
    $hits
}

"=== counts: every asserted figure against its artifact ==="

$fixedFiles = @{}
$claimSpans = @{}   # file -> every span a claim matched, kept for the loose-figure sweep
$countFindings = $findings
foreach ($c in $claims) {
    if (-not (Test-Path $c.File)) { "FAIL: $($c.File) missing"; $findings++; continue }
    $doc = $docByName[$c.File]
    $raw = if ($fixedFiles.ContainsKey($c.File)) { $fixedFiles[$c.File] }
           elseif ($doc) { $doc.Raw }
           else { Get-Content $c.File -Raw }
    $expected = Get-Expected $c.Q $c.Style
    $hits = @(Get-ClaimHits $raw $c.Pattern)
    if (-not $claimSpans.ContainsKey($c.File)) { $claimSpans[$c.File] = [System.Collections.Generic.List[object]]::new() }
    foreach ($h in $hits) { $claimSpans[$c.File].Add($h) }

    if ($hits.Count -eq 0) {
        $findings++
        "FAIL: $($c.File): no claim matches /$($c.Pattern)/, the wording moved; re-anchor the claim or drop it"
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

# one alternation over all the distinctive forms, longest first so a compound word
# form is never eaten by its own prefix; the hits are grouped back by form so the
# findings keep the per-form order the register of quantities gives them
$loose = @()
if ($distinct.Count) {
    $forms  = @($distinct.Keys | Sort-Object { $_.Length } -Descending)
    $formRe = [regex]::new('(?i)(?<![\w-])(?:' + (($forms | ForEach-Object { [regex]::Escape($_) }) -join '|') + ')(?![\w-])', 'Compiled')

    foreach ($d in $docs) {
        $file  = $d.Name
        $fixed = $fixedFiles.ContainsKey($file)
        $raw   = if ($fixed) { $fixedFiles[$file] } else { $d.Raw }
        if (-not $raw) { continue }

        # a fixed file's offsets moved, so its held spans are found again on the new
        # text; everywhere else the spans the claims loop already found are reused
        $held = if ($fixed) {
            @($claims | Where-Object { $_.File -eq $file } |
              ForEach-Object { [regex]::Matches($raw, $_.Pattern) } | ForEach-Object { $_ })
        } elseif ($claimSpans.ContainsKey($file)) { $claimSpans[$file] } else { @() }

        $byForm = @{}
        foreach ($m in $formRe.Matches($raw)) {
            $f = $m.Value.ToLower()
            if (-not $byForm.ContainsKey($f)) { $byForm[$f] = [System.Collections.Generic.List[object]]::new() }
            $byForm[$f].Add($m)
        }

        foreach ($form in $distinct.Keys) {
            if (-not $byForm.ContainsKey($form)) { continue }
            foreach ($m in $byForm[$form]) {
                $rest = $raw.Substring($m.Index, [math]::Min(80, $raw.Length - $m.Index)) -replace '(?s)\r?\n.*', ''
                if ($rest -notmatch $countedNoun) { continue }
                $covered = $false
                foreach ($s in $held) { if ($m.Index -ge $s.Index -and $m.Index -lt $s.Index + $s.Length) { $covered = $true; break } }
                if ($covered) { continue }
                $line = if ($fixed) { 1 + [regex]::Matches($raw.Substring(0, $m.Index), "`n").Count }
                        else        { 1 + (Get-LineIndex $d.Starts $m.Index) }
                $loose += "${file}:${line} states '$($m.Value)' where no claim holds it, for $($distinct[$form] -join ' or ')"
            }
        }
    }
}
Report 'unheld restatement(s) of a counted figure:' $loose 'every stated figure is held by a claim'

# --- the Coverage table is one row per section, with the right count ---------------

# The trailing lookahead keeps CRLF out of the match: .NET's (?m)$ sits before the \n,
# so an anchored \|$ never matches a CRLF file, and every row reads as missing.
$rowPattern = '(?m)^\| \*\*§(\d+) [^|]*\| \*\*extracted\*\* \| \*\*(\d+)\*\* \|(?=\r?$)'
$regRaw = if ($fixedFiles.ContainsKey('docs/requirements-register.md')) { $fixedFiles['docs/requirements-register.md'] } else { $docByName['docs/requirements-register.md'].Raw }
$rows = [regex]::Matches($regRaw, $rowPattern)

$listed = @($rows | ForEach-Object { $_.Groups[1].Value })
$mismatched = @()
$mismatched += @($perSection.Keys | Where-Object { $_ -notin $listed }  | ForEach-Object { "§$_ has no Coverage row" })
$mismatched += @($listed | Where-Object { $_ -notin $perSection.Keys } | ForEach-Object { "Coverage row §$_ names no section" })
Report 'Coverage row(s) not matching the section list:' $mismatched "$($rows.Count) Coverage rows, one per section"

$bad = @($rows | Where-Object { [int]$_.Groups[2].Value -ne $perSection[$_.Groups[1].Value] })
if ($bad.Count -and $Fix) {
    $fixedFiles['docs/requirements-register.md'] = [regex]::Replace($regRaw, $rowPattern, {
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
# compounds: the archetype band against the product of the rows it rests on
# =================================================================================
#
# The estimates carry two layers of figure and only one of them is anybody's artifact.
# A big-table row is scored against the baseline and moves when a lever lands in it;
# the archetype band beneath is a synthesis over those rows, restated by hand, and it
# moves when someone remembers. Nothing renders wrong when they part: the row reads
# correctly, the band reads correctly, and only the arithmetic between them is gone.
# That is the drift this group closes, and it has already happened once, a commit
# re-scoring the in-order row and leaving the static-prediction row it landed in the
# same paragraph as, so the two ends of one lever disagreed for a day.
#
# The product is the dominant terms only, and that is the whole of what makes it
# meaningful. Multiplying every applicable row runs past -90% and describes no workload
# that exists, because separate rows reach their worse ends on disjoint sub-workloads:
# the pointer-chase that empties the cache row is not the branchy dependent code that
# empties the in-order one. So the terms are declared here, four losses and two gains,
# each naming the row it reads and the range inside that row's figure, and each end's
# gains are taken at the end the same workload property drives them to.
#
# What the check cannot decide is the credit: the band's worse end stands a few points
# optimistic of the product for exactly the non-simultaneity above, and how many points
# that is worth is a judgment. So the document states it, the check recomputes the
# product from the rows, and the two are required to agree. A lever that tightens a row
# then has one of two consequences and no third: the credit absorbs it, or the band
# moves. Neither is silent.
#
# The document is regularized so that the two halves separate cleanly. The product is
# arithmetic over the rows and nobody's judgment, so -Fix rewrites it. The credit is
# the author's, and it has no repair: a row that moves changes the product under a
# credit that no longer matches it, and whether that spends the credit or moves the
# band is exactly the decision this group exists to force. Running -Fix therefore
# leaves the finding standing rather than absorbing it, which is the point.
#
# The band is stated once, in the archetype table, and the credit table does not restate
# it: with the product recomputed and the band read from its own row, the credit is the
# gap between them, and its sense follows from which side of the product the band sits.

"=== compounds: the archetype band against the product of the rows it rests on ==="

$perfName = 'docs/performance-estimates.md'
$perfDoc  = $docByName[$perfName]
$perfRaw  = if ($fixedFiles.ContainsKey($perfName)) { $fixedFiles[$perfName] } else { $perfDoc.Raw }

# each term names the big-table row it reads; the clock row states two ranges and only
# the sustained one enters, which is the whole of the variation between the six
$terms = @(
    [pscustomobject]@{ Row = 'In-order issue, no speculation/OoO'; Gain = $false; Tail = '' }
    [pscustomobject]@{ Row = 'Static-only branch prediction';      Gain = $false; Tail = '' }
    [pscustomobject]@{ Row = 'No hardware caches, flat SRAM';      Gain = $false; Tail = '' }
    [pscustomobject]@{ Row = 'Fixed modest clocks, no turbo';      Gain = $false; Tail = ' sustained' }
    [pscustomobject]@{ Row = 'No MMU / single address space';      Gain = $true;  Tail = '' }
    [pscustomobject]@{ Row = 'Macro-op fusion';                    Gain = $true;  Tail = '' }
)

$unread = @(); $ends = @()
foreach ($t in $terms) {
    $hit = @($perfDoc.Lines | Where-Object { $_.StartsWith('|') -and $_.Contains($t.Row) })
    if ($hit.Count -ne 1) { $unread += "'$($t.Row)': $($hit.Count) big-table row(s) match"; continue }
    $sign = if ($t.Gain) { '\+' } else { '−' }
    $m = [regex]::Match(($hit[0] -split '\|')[4], "$sign(\d+)% to $sign(\d+)%$($t.Tail)")
    if (-not $m.Success) { $unread += "'$($t.Row)': its figure states no $sign range$($t.Tail)"; continue }
    $ends += [pscustomobject]@{ Gain = $t.Gain; Min = [int]$m.Groups[1].Value; Max = [int]$m.Groups[2].Value }
}
Report 'dominant term(s) whose row or figure the big table no longer carries:' $unread `
       "all $($terms.Count) dominant terms read their own row"

# the band the archetype table states, and the credit table standing under the product
$bandM   = [regex]::Match($perfRaw, '(?m)^\| General scalar[^|]*\| \*\*−(\d+)% to −(\d+)%\*\*')
$creditRe = [regex]'(?m)^\| (Better|Worse) \| −(\d+)% \| (\d+) points (optimistic|conservative) \|'
$credits = @($creditRe.Matches($perfRaw))

if ($unread.Count) { }                       # reported above; without every term there is no product
elseif (-not $bandM.Success -or $credits.Count -ne 2) {
    $findings++
    "FAIL: the general-scalar band or its credit table is not in the form this check reads"
} else {
    # the better end takes every term's smaller figure and the worse end every term's
    # larger, gains included: the pairing rule, not a choice of which end to be kind at
    $product = @{}
    foreach ($end in 'Better', 'Worse') {
        $p = 1.0
        foreach ($e in $ends) {
            $v = if ($end -eq 'Better') { $e.Min } else { $e.Max }
            $p *= if ($e.Gain) { 1 + $v / 100 } else { 1 - $v / 100 }
        }
        $product[$end] = [int][math]::Round((1 - $p) * 100)
    }
    $band = @{ Better = [int]$bandM.Groups[1].Value; Worse = [int]$bandM.Groups[2].Value }

    $stale = @($credits | Where-Object { [int]$_.Groups[2].Value -ne $product[$_.Groups[1].Value] })
    if ($stale.Count -and $Fix) {
        $fixedFiles[$perfName] = $creditRe.Replace($perfRaw, {
            param($m)
            $end = $m.Groups[1].Value
            "| $end | −$($product[$end])% | $($m.Groups[3].Value) points $($m.Groups[4].Value) |"
        })
        $stale | ForEach-Object { "fixed: $($_.Groups[1].Value) product: $($_.Groups[2].Value)% -> $($product[$_.Groups[1].Value])%" }
    } else {
        Report 'product cell(s) disagreeing with the rows they compound:' `
               @($stale | ForEach-Object { "$($_.Groups[1].Value): the table says $($_.Groups[2].Value)%, the rows compound to $($product[$_.Groups[1].Value])%" }) `
               "the general-scalar band stands $($product['Better'])% to $($product['Worse'])% by its rows"
    }

    # the band is optimistic where it is nearer zero than the product and conservative
    # where it is further, so neither the gap nor its sense is free to state
    $miscredited = @(foreach ($c in $credits) {
        $end  = $c.Groups[1].Value
        $gap  = [math]::Abs($band[$end] - $product[$end])
        $want = if ($band[$end] -lt $product[$end]) { 'optimistic' } else { 'conservative' }
        if ([int]$c.Groups[3].Value -ne $gap -or $c.Groups[4].Value -ne $want) {
            "${end}: the table credits $($c.Groups[3].Value) points $($c.Groups[4].Value), the band stands $gap points $want of the product"
        }
    })
    Report 'credit(s) the band and the product do not support:' $miscredited `
           'every credit is the gap between the band and its product'
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

# only the rows are visited: the matcher hands back every pipe-led line with its
# offset, an offset is its line by exact search (the match is ^-anchored), and a run
# is rows on consecutive lines; a fenced row is display text, and the line it holds
# breaks the adjacency exactly as any prose line does
$rowRe = [regex]'(?m)^[^\S\r\n]*\|[^\r\n]*'

$ragged = @(); $ruleless = @()
foreach ($d in $docs) {
    $bad = @(); $width = 0; $startLi = 0; $rows = 0; $rule = $false; $prevLi = -2

    foreach ($m in $rowRe.Matches($d.Raw)) {
        $li = [System.Array]::BinarySearch($d.Starts, $m.Index)
        if ($d.Fenced[$li]) { continue }
        if ($rows -and $li -ne $prevLi + 1) {
            if (-not $rule) { $ruleless += "$($d.Name):$($startLi + 1), $rows row(s) with no header rule" }
            $rows = 0; $rule = $false
        }
        $line = $m.Value
        # an escaped pipe is a character inside a cell, not a wall between two
        $cells = ($line.TrimEnd() -replace '\\\|', '').Split('|').Count - 2
        if ($rows -eq 0)           { $startLi = $li; $width = $cells }
        elseif ($cells -ne $width) { $bad += $li + 1 }
        if ($line -match '^\s*\|[\s:|-]+\|\s*$') { $rule = $true }
        $rows++
        $prevLi = $li
    }
    if ($rows -and -not $rule) { $ruleless += "$($d.Name):$($startLi + 1), $rows row(s) with no header rule" }
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
# MUST <U+2014> obligation`) and its section headings (`## §n <U+2014> Title`), a delimiter
# and a title separator, one per requirement and one per section. Neither has a sentence
# whose meaning could be decided. Both were changed to ASCII (`MUST: ` and `## §n. `) rather
# than exempted here, because an exemption is a proviso that must itself be audited, and a
# rule with no carve-out is closed by construction: any U+2014 anywhere is a finding, and a
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
    $last = -1
    $pos = $d.Raw.IndexOf($emDash)
    while ($pos -ge 0) {
        $i = Get-LineIndex $d.Starts $pos
        if ($i -ne $last) { $em += $i + 1; $last = $i }
        $pos = $d.Raw.IndexOf($emDash, $pos + 1)
    }
    $last = -1
    foreach ($m in $mojibake.Matches($d.Raw)) {
        $i = Get-LineIndex $d.Starts $m.Index
        if ($i -ne $last) { $mb += $i + 1; $last = $i }
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
