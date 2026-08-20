# Holds tools/check.ps1 against the one property its own meta group cannot decide:
# that each rule it carries actually fires.
#
# The checker closes a great deal on itself. The meta group holds the rule registry and
# the code in agreement in both directions, and the floors group (K-46 through K-48)
# catches the reading that has emptied. What none of them reaches is the rule that still
# reads a populated set and has stopped deciding anything about it: a pattern that
# narrowed without emptying, an anchor that now matches a neighbouring construct, a
# branch made unreachable by an edit elsewhere. tools/check-rules.md names that residue
# in "What a passing run does not decide" and leaves it to a person. This closes the
# part of it a machine can have: for each rule, one document mutated so that the rule
# must report, and a run that says whether it did.
#
# The method is mutation testing and its guarantee is exactly the usual one. A rule that
# survives its mutant is dead surface, reported here. A rule that kills its mutant is
# live, which is not the same as correct: whether it decides the *right* property is
# still the registry's claim and a person's to audit. Nothing here re-states what a rule
# means. It states only that the rule bites.
#
# Every case runs against a sandbox built from the working tree, so the checker under
# test is the one on disk rather than the one at HEAD, and no case can touch the real
# repository. The sandbox is a git repository because check.ps1 reads its corpus from
# the index.
#
#   tools/check-selftest.ps1                # every case, roughly four minutes
#   tools/check-selftest.ps1 -Rule K-23     # one rule, while iterating on it
#   tools/check-selftest.ps1 -Keep          # leave the sandbox for inspection
#
# Exit 0 when every case kills its mutant and every registered rule is accounted for,
# 1 otherwise. Run from the repository root.

[CmdletBinding()]
param(
    [string]$Rule,
    [string]$Sandbox = (Join-Path ([System.IO.Path]::GetTempPath()) 'verifiedos-selftest'),
    [switch]$Keep
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path 'tools/check.ps1') -or -not (Test-Path '.git')) {
    throw "run this from the repository root: '$($PWD.Path)' carries no .git and tools/check.ps1"
}
$repo = $PWD.Path

# =================================================================================
# the sandbox, and the helpers a case edits it through
# =================================================================================

function Get-Doc([string]$rel) {
    [System.IO.File]::ReadAllText([System.IO.Path]::Combine($Sandbox, $rel))
}

# Writes, and says whether it wrote anything. A mutation that produced no change is the
# case that has stopped testing its rule, and it must be told apart from a rule that
# read a defect and said nothing: a null edit is refused rather than written, so a
# pattern that stopped matching cannot blank the document it was aimed at.
function Set-Doc([string]$rel, $text) {
    if ($null -eq $text) { return $false }
    $p   = [System.IO.Path]::Combine($Sandbox, $rel)
    $old = [System.IO.File]::ReadAllText($p)
    if ([string]$text -ceq $old) { return $false }
    [System.IO.File]::WriteAllText($p, [string]$text)
    $true
}

# A register entry is its normative line plus the property lines under it, ending where
# the next entry begins. Several cases need surgery inside exactly one entry and must
# not reach the next, so the span is computed once here.
function Set-Entry([string]$text, [string]$id, [scriptblock]$Edit) {
    $s = $text.IndexOf("**$id** ")
    if ($s -lt 0) { return $null }
    $e = $text.IndexOf("`n**R-", $s + 1)
    if ($e -lt 0) { $e = $text.Length }
    $new = & $Edit $text.Substring($s, $e - $s)
    if ($null -eq $new) { return $null }
    $text.Substring(0, $s) + $new + $text.Substring($e)
}

# Replace one literal, at or after an offset. The offset is how a case skips the
# register's entry template, which is fenced prose carrying every property line's
# shape and is not an entry at all.
function Set-Once([string]$text, [string]$find, [string]$repl, [int]$from = 0) {
    $i = $text.IndexOf($find, $from)
    if ($i -lt 0) { return $null }
    $text.Remove($i, $find.Length).Insert($i, $repl)
}

# the two characters the documents' own shapes are written in, named so that a case
# composing a pattern around one never has to do it inside a -replace, where a `+`
# joins into the operator's argument list instead of into the string
$mid = [char]0x00B7   # the bullet the register opens each property line with
$sec = [char]0x00A7   # the section sign a trace and a cross-reference display

function New-Sandbox {
    if (Test-Path $Sandbox) { Remove-Item -Recurse -Force $Sandbox }
    New-Item -ItemType Directory -Path $Sandbox | Out-Null

    # The working tree, not HEAD and not the index: the checker under test is the one
    # being edited, and so is every document it reads. Untracked files are copied for
    # the same reason. A document or a tool written but not yet staged is exactly the
    # thing most likely to be wrong, and a sandbox that omitted it would fail on the
    # links pointing at it rather than test it. Ignored files stay out, `.gitignore`
    # deciding that the same way it does everywhere else.
    #
    # A submodule's contents are not copied, because check.ps1 excludes upstream prose
    # from its corpus, but the directory itself is stood up: a link at a submodule is
    # resolved against the filesystem here, where the sandbox's own index carries no
    # gitlink to resolve it against instead. The placeholder is what makes the
    # directory survive the clean between cases, git having no way to track an empty
    # one.
    $tracked = @(& git -c core.quotepath=false ls-files --full-name) +
               @(& git -c core.quotepath=false ls-files --others --exclude-standard --full-name)
    if ($LASTEXITCODE -ne 0) { throw 'git ls-files failed in the repository' }
    $n = 0
    foreach ($rel in $tracked) {
        $src = [System.IO.Path]::Combine($repo, $rel)
        $dst = [System.IO.Path]::Combine($Sandbox, $rel)
        if ([System.IO.File]::Exists($src)) {
            $dir = [System.IO.Path]::GetDirectoryName($dst)
            if (-not [System.IO.Directory]::Exists($dir)) { [void][System.IO.Directory]::CreateDirectory($dir) }
            [System.IO.File]::Copy($src, $dst, $true)
            $n++
        } elseif ([System.IO.Directory]::Exists($src)) {
            [void][System.IO.Directory]::CreateDirectory($dst)
            [System.IO.File]::WriteAllText([System.IO.Path]::Combine($dst, '.selftest-submodule'),
                "a stand-in for the $rel submodule, so links at it resolve`n")
        }
    }

    Push-Location $Sandbox
    try {
        & git -c init.defaultBranch=main init -q 2>&1 | Out-Null
        & git add -A 2>&1 | Out-Null
        & git -c user.email=selftest@localhost -c user.name=selftest commit -q -m sandbox 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'could not commit the sandbox baseline' }
    } finally { Pop-Location }
    $n
}

# a case is undone rather than compensated for: the commit above is the baseline, so a
# modified, deleted, or newly created file all go back in one step
function Reset-Sandbox {
    Push-Location $Sandbox
    try {
        & git checkout -q -- . 2>&1 | Out-Null
        & git clean -qfd 2>&1 | Out-Null
    } finally { Pop-Location }
}

# the checker's own verdict, as the rule ids it reported, so a case asserts against
# what the run decided rather than against its prose
function Invoke-Checker([switch]$Fix) {
    $psArgs = @('-NoLogo', '-NoProfile', '-File', (Join-Path $Sandbox 'tools/check.ps1'))
    if ($Fix) { $psArgs += '-Fix' }
    Push-Location $Sandbox
    try { $out = & pwsh @psArgs 2>&1; $code = $LASTEXITCODE } finally { Pop-Location }
    [pscustomobject]@{
        Exit   = $code
        Out    = $out
        Failed = @($out | ForEach-Object { if ("$_" -match '^\s*FAIL (K-\d\d)') { $Matches[1] } } | Sort-Object -Unique)
    }
}

# =================================================================================
# the cases: one mutant per rule, each stating the defect it seeds
# =================================================================================
#
# A case is either a literal substitution or, where the defect is structural, a
# scriptblock over the sandbox. Several mutants trip more than one rule, which is
# expected and not a weakness: an id renamed in one artifact is genuinely wrong in
# every artifact that cites it. A case passes when its own rule is among those that
# reported, so collateral findings neither hide a miss nor manufacture a hit.
#
# A line-matching pattern here ends at `[^\r\n]*` and never at `$`. These documents
# are CRLF, .NET's `$` sits before the `\n` rather than before the `\r\n`, and an
# anchored line pattern therefore matches nothing at all. That is the same trap
# check.ps1's own Coverage-row pattern documents, and here it would be silent twice
# over: the mutation would not apply, and a case that does not apply is a rule
# reported live by a test that ran nothing.

$cases = @(
    @{ Rule = 'K-00'; What = 'a registered rule with its registry row retitled out of the table'
       Do = { Set-Doc 'tools/check-rules.md' (Set-Once (Get-Doc 'tools/check-rules.md') '| K-40 | glyphs' '| K-xx | glyphs') } }

    @{ Rule = 'K-01'; What = "a trace's derived bookmark renamed in the prose"
       Do = { Set-Doc 'docs/spec.md' (Set-Once (Get-Doc 'docs/spec.md') '<a id="r-01-001">' '<a id="moved-away">') } }

    @{ Rule = 'K-02'; What = 'a trace writing out the citation its own id derives'
       Do = { Set-Doc 'docs/requirements-register.md' (Set-Entry (Get-Doc 'docs/requirements-register.md') 'R-01-001' {
                param($b) $b -replace "$mid Trace: CJ-T", "$mid Trace: [${sec}1](spec.md#r-01-001)" }) } }

    @{ Rule = 'K-03'; What = 'one bookmark declared twice in the same document'
       Do = { Set-Doc 'docs/spec.md' (Set-Once (Get-Doc 'docs/spec.md') '<a id="r-01-002"></a>' '<a id="r-01-002"></a><a id="r-01-002"></a>') } }

    @{ Rule = 'K-04'; What = 'a bookmark buried in a fenced block, where it is text'
       Do = {
            $fence = '```'
            Set-Doc 'docs/critique.md' ((Get-Doc 'docs/critique.md') + "`n$fence`n<a id=`"seeded-in-a-fence`"></a>`n$fence`n") } }

    @{ Rule = 'K-05'; What = 'a requirement whose trace line stops being one'
       Do = { Set-Doc 'docs/requirements-register.md' (Set-Entry (Get-Doc 'docs/requirements-register.md') 'R-01-001' {
                param($b) $b -replace "$mid Trace:", "$mid Traced:" }) } }

    @{ Rule = 'K-06'; What = 'a requirement left with nothing to decide it'
       Do = { Set-Doc 'docs/requirements-register.md' (Set-Entry (Get-Doc 'docs/requirements-register.md') 'R-01-001' {
                param($b) $b -replace "$mid Accept:", "$mid Accepts:" }) } }

    @{ Rule = 'K-07'; What = 'a criterion stated below the trace that must follow it'
       Do = { Set-Doc 'docs/requirements-register.md' (Set-Entry (Get-Doc 'docs/requirements-register.md') 'R-01-001' {
                param($b) $b -replace "($mid Trace: [^\r\n]*)", "`$1`n$mid Accept: a criterion stated after the trace" }) } }

    @{ Rule = 'K-08'; What = 'a prose bookmark naming a requirement the register never declared'
       Do = { Set-Doc 'docs/spec.md' (Set-Once (Get-Doc 'docs/spec.md') '<a id="r-01-001">' '<a id="r-01-901">') } }

    @{ Rule = 'K-09'; What = 'a written-out trace displaying a section its bookmark does not sit in'
       Do = { Set-Doc 'docs/requirements-register.md' (Set-Entry (Get-Doc 'docs/requirements-register.md') 'R-01-001' {
                param($b) $b -replace "$mid Trace: CJ-T", "$mid Trace: [${sec}9](spec.md#r-01-001); and the crown jewel" }) } }

    @{ Rule = 'K-10'; What = 'one requirement id declared by two entries'
       Do = { Set-Doc 'docs/requirements-register.md' (Set-Once (Get-Doc 'docs/requirements-register.md') '**R-01-002** ' '**R-01-001** ') } }

    @{ Rule = 'K-11'; What = 'a requirement id that names nothing'
       File = 'docs/critique.md'; Find = "`n## "; Repl = "`nThe R-99-999 obligation applies here.`n`n## " }

    @{ Rule = 'K-12'; What = 'a link pointing at a file the repository does not carry'
       File = 'README.md'; Find = '](docs/'; Repl = '](docs/not-a-' }

    @{ Rule = 'K-13'; What = 'a section number no heading carries'
       File = 'docs/critique.md'; Find = "`n## "; Repl = "`nThis is settled at ${sec}99.7.`n`n## " }

    @{ Rule = 'K-14'; What = 'a bearing requirement its view stops carrying'
       Do = {
            # the id is read out of the register rather than named here, so the case
            # keeps working when the subsection is re-populated
            $reg = Get-Doc 'docs/requirements-register.md'
            $sub = [regex]::Match($reg, '(?ms)^### 15\.14 .*?(?=^### )')
            if (-not $sub.Success) { return $false }
            $ids = @([regex]::Matches($sub.Value, '(?m)^\*\*(R-\d\d-\d+[a-z]?)\*\* ') | ForEach-Object { $_.Groups[1].Value })
            $view = Get-Doc 'docs/absence-contract.md'
            foreach ($id in $ids) {
                if ($view.Contains($id)) {
                    # swapped for another live id, so only the membership is wrong
                    Set-Doc 'docs/absence-contract.md' ($view -replace [regex]::Escape($id), 'R-01-001')
                    return $true
                }
            }
            $false } }

    @{ Rule = 'K-15'; What = 'a matrix cell moved off its own pair, leaving a gap and a duplicate'
       File = 'docs/coverage-matrix.md'; Find = '| `B-01` | `P-1` |'; Repl = '| `B-02` | `P-1` |' }

    @{ Rule = 'K-16'; What = 'a matrix cell resting on no requirement'
       Do = {
            $t = Get-Doc 'docs/coverage-matrix.md'
            $m = [regex]::Match($t, '(?m)^\| `B-\d\d` \| `P-\d` \|[^\r\n]*')
            if (-not $m.Success) { return $false }
            Set-Doc 'docs/coverage-matrix.md' ($t.Remove($m.Index, $m.Length).Insert($m.Index,
                ($m.Value -replace 'R-\d\d-\d+[a-z]?', 'the register'))) } }

    @{ Rule = 'K-17'; What = 'a CJ- target the inventory does not account for'
       Do = { Set-Doc 'docs/requirements-register.md' (Set-Once (Get-Doc 'docs/requirements-register.md') '| `CJ-SAIL` |' '| `CJ-SAILX` |') } }

    @{ Rule = 'K-18'; What = 'an inventory row no requirement confers the status on'
       Do = {
            $t = Get-Doc 'docs/crown-jewels.md'
            $m = [regex]::Match($t, '(?m)^\| \d+ \|[^\r\n]*')
            if (-not $m.Success) { return $false }
            Set-Doc 'docs/crown-jewels.md' ($t.Remove($m.Index, $m.Length).Insert($m.Index,
                ($m.Value -replace 'R-\d\d-\d+[a-z]?', 'R-01-001'))) } }

    @{ Rule = 'K-19'; What = 'the crown-jewel status asserted in a criterion and on no entry line'
       Do = { Set-Doc 'docs/requirements-register.md' (Set-Entry (Get-Doc 'docs/requirements-register.md') 'R-01-001' {
                param($b) $b -replace "($mid Accept:)", '$1 the crown-jewel spec it names is authored, and' }) } }

    @{ Rule = 'K-20'; What = 'a conferred refusal no seam collects'
       Do = { Set-Doc 'docs/requirements-register.md' (Set-Entry (Get-Doc 'docs/requirements-register.md') 'R-01-001' {
                param($b) $b -replace "($mid Trace:)", "$mid Fail-closed: the seeded refusal stops the unit, and the stop costs a restart`n`$1" }) } }

    @{ Rule = 'K-21'; What = 'a seam composing a refusal no requirement confers'
       Do = {
            $t = Get-Doc 'docs/requirements-register.md'
            $m = [regex]::Match($t, '(?m)^\*\*R-\d\d-\d+[a-z]?\*\* [^\r\n]*Fail-closed seam \*\*[^\r\n]*')
            if (-not $m.Success) { return $false }
            Set-Doc 'docs/requirements-register.md' ($t.Remove($m.Index, $m.Length).Insert($m.Index,
                ($m.Value -replace '(?<!^\*\*)R-\d\d-\d+[a-z]?(?!\*\* )', 'R-01-001'))) } }

    @{ Rule = 'K-22'; What = 'a freshness conferral that stops naming the enumeration collecting it'
       Do = {
            $t = Get-Doc 'docs/requirements-register.md'
            $m = [regex]::Match($t, "(?m)^$mid RoT-fresh:[^\r\n]*R-10-013[^\r\n]*")
            if (-not $m.Success) { return $false }
            Set-Doc 'docs/requirements-register.md' ($t.Remove($m.Index, $m.Length).Insert($m.Index,
                ($m.Value -replace 'R-10-013[a-z]?', 'the enumeration'))) } }

    @{ Rule = 'K-23'; What = 'an entry speaking the vocabulary of refusal and standing in no column'
       Do = { Set-Doc 'docs/requirements-register.md' (Set-Entry (Get-Doc 'docs/requirements-register.md') 'R-01-001' {
                param($b) $b -replace '(?m)^(\*\*R-01-001\*\*[^\r\n]*)', '$1 The unit refuses rather than degrades.' }) } }

    @{ Rule = 'K-24'; What = 'an asserted count the artifact no longer gives'
       Do = {
            $t = Get-Doc 'docs/crown-jewels.md'
            $m = [regex]::Match($t, '\d+(?= coarse targets)')
            if (-not $m.Success) { return $false }
            Set-Doc 'docs/crown-jewels.md' ($t.Remove($m.Index, $m.Length).Insert($m.Index, '99')) } }

    @{ Rule = 'K-25'; What = 'an inventory status spelled outside the three declared classes'
       Do = {
            $t = Get-Doc 'docs/crown-jewels.md'
            $m = [regex]::Match($t, '(?m)^\| \d+ \|[^\r\n]*\| (not authored|partial[^|]*|[^|]*authored[^|]*) \|[^\r\n]*')
            if (-not $m.Success) { return $false }
            $row = $m.Value -replace '\| [^|]+ \|(\s*)$', '| in progress |$1'
            Set-Doc 'docs/crown-jewels.md' ($t.Remove($m.Index, $m.Length).Insert($m.Index, $row)) } }

    @{ Rule = 'K-26'; What = 'a counted figure restated where no claim holds it'
       Do = {
            # the form has to be one the tool actually counts, so it is read out of the
            # inventory rather than invented
            $n = @([regex]::Matches((Get-Doc 'docs/crown-jewels.md'), '(?m)^\| \d+ \|')).Count
            $words = 'zero','one','two','three','four','five','six','seven','eight','nine','ten',
                     'eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen','eighteen','nineteen'
            $tens  = @{ 2='twenty'; 3='thirty'; 4='forty'; 5='fifty' }
            $w = if ($n -lt 20) { $words[$n] } else { $tens[[int][math]::Floor($n / 10)] + $(if ($n % 10) { '-' + $words[$n % 10] } else { '' }) }
            Set-Doc 'docs/critique.md' (Set-Once (Get-Doc 'docs/critique.md') "`n## " "`nThere are $w crown-jewel specifications in view.`n`n## ") } }

    @{ Rule = 'K-27'; What = 'a Coverage row naming a section the register does not carry'
       Do = { Set-Doc 'docs/requirements-register.md' (Set-Once (Get-Doc 'docs/requirements-register.md') "| **${sec}5 " "| **${sec}55 ") } }

    @{ Rule = 'K-28'; What = 'a Coverage row whose count the register does not give'
       Do = {
            $t = Get-Doc 'docs/requirements-register.md'
            $m = [regex]::Match($t, "(?m)^\| \*\*$sec\d+ [^|]*\| \*\*extracted\*\* \| \*\*(\d+)\*\* \|")
            if (-not $m.Success) { return $false }
            $g = $m.Groups[1]
            Set-Doc 'docs/requirements-register.md' ($t.Remove($g.Index, $g.Length).Insert($g.Index, '999')) } }

    @{ Rule = 'K-29'; What = 'a CSR row resting on no requirement'
       Do = {
            $t = Get-Doc 'docs/isa-profile.md'
            $s = $t.IndexOf('### 5.1 ')
            if ($s -lt 0) { return $false }
            $m = [regex]::Match($t.Substring($s), '(?m)^\| `[^\r\n]*R-\d\d-\d+[^\r\n]*')
            if (-not $m.Success) { return $false }
            $i = $s + $m.Index
            Set-Doc 'docs/isa-profile.md' ($t.Remove($i, $m.Length).Insert($i,
                ($m.Value -replace 'R-\d\d-\d+[a-z]?', 'the profile'))) } }

    @{ Rule = 'K-30'; What = 'an estimate figure stated outside the column shape'
       Do = {
            $t = Get-Doc 'docs/performance-estimates.md'
            $m = [regex]::Match($t, '(?m)^\|[^\r\n]*In-order issue[^\r\n]*')
            if (-not $m.Success) { return $false }
            $cells = $m.Value -split '\|'
            $row = ($m.Value -replace [regex]::Escape($cells[4]), ' roughly a third off ')
            Set-Doc 'docs/performance-estimates.md' ($t.Remove($m.Index, $m.Length).Insert($m.Index, $row)) } }

    @{ Rule = 'K-31'; What = 'a dominant term whose big-table row is retitled out from under it'
       File = 'docs/performance-estimates.md'; Find = 'In-order issue, no speculation/OoO'; Repl = 'In-order issue, no speculation or OoO' }

    @{ Rule = 'K-32'; What = 'a compounded product the rows beneath it do not give'
       File = 'docs/performance-estimates.md'; Find = '| Better | ' + [char]0x2212 + '42% |'; Repl = '| Better | ' + [char]0x2212 + '11% |' }

    @{ Rule = 'K-33'; What = 'a credit the band and the product do not support'
       File = 'docs/performance-estimates.md'; Find = '| 3 points conservative |'; Repl = '| 9 points conservative |' }

    @{ Rule = 'K-34'; What = 'a checklist item whose estimate cell the document cannot read'
       Do = {
            $t = Get-Doc 'docs/implementation-checklist.md'
            $cell = " $mid [\d.,]+ h actual $mid [\d.]+%"
            $m = [regex]::Match($t, "(?m)^\* \[x\] \*\*[^*]+\*\*$cell")
            if (-not $m.Success) { return $false }
            $row = ($m.Value -replace $cell, ' (about half a day)')
            Set-Doc 'docs/implementation-checklist.md' ($t.Remove($m.Index, $m.Length).Insert($m.Index, $row)) } }

    @{ Rule = 'K-35'; What = 'an open midpoint that is not the mean of its own range'
       Do = {
            $t = Get-Doc 'docs/implementation-checklist.md'
            $m = [regex]::Match($t, '(?m)^\* \[ \] \*\*[^*]+\*\* ' + $mid + ' (?<h>[\d.,]+)(?= h, range )')
            if (-not $m.Success) { return $false }
            $g = $m.Groups['h']
            Set-Doc 'docs/implementation-checklist.md' ($t.Remove($g.Index, $g.Length).Insert($g.Index, '999')) } }

    @{ Rule = 'K-36'; What = 'a subtotal that no longer sums the items beneath it'
       Do = {
            $t = Get-Doc 'docs/implementation-checklist.md'
            $m = [regex]::Match($t, '(?m)^\*\*[^*]+ subtotal:\*\* (?<h>[\d.,]+)(?= h )')
            if (-not $m.Success) { return $false }
            $g = $m.Groups['h']
            Set-Doc 'docs/implementation-checklist.md' ($t.Remove($g.Index, $g.Length).Insert($g.Index, '999')) } }

    @{ Rule = 'K-37'; What = 'a restated grand total the items do not give'
       Do = {
            $t = Get-Doc 'docs/implementation-checklist.md'
            $m = [regex]::Match($t, '(?m)^\* Total estimate: (?<h>[\d.,]+)(?= h midpoint)')
            if (-not $m.Success) { return $false }
            $g = $m.Groups['h']
            Set-Doc 'docs/implementation-checklist.md' ($t.Remove($g.Index, $g.Length).Insert($g.Index, '999')) } }

    @{ Rule = 'K-38'; What = 'a table row of the wrong width'
       File = 'docs/coverage-matrix.md'; Find = '| `B-01` | `P-1` |'; Repl = '| seeded | `B-01` | `P-1` |' }

    @{ Rule = 'K-39'; What = 'a run of table rows carrying no header rule'
       File = 'docs/critique.md'; Find = "`n## "; Repl = "`n| a stray row | pasted on its own |`n`n## " }

    @{ Rule = 'K-40'; What = 'an em-dash, which the house style forbids'
       File = 'docs/critique.md'; Find = "`n## "; Repl = "`nA clause " + [char]0x2014 + " and its aside.`n`n## " }

    @{ Rule = 'K-41'; What = 'UTF-8 read as a single-byte encoding'
       File = 'docs/critique.md'; Find = "`n## "; Repl = "`nThe caf" + [char]0x00C3 + [char]0x00A9 + " problem.`n`n## " }

    @{ Rule = 'K-42'; What = 'a bindings row disagreeing with the apex record'
       File = 'docs/field-bindings.md'; Find = '| `spatial_safety` |'; Repl = '| `spatial_safetyx` |' }

    @{ Rule = 'K-43'; What = 'a consumer cell that no longer restates the statement'
       Do = {
            $t = Get-Doc 'docs/field-bindings.md'
            $m = [regex]::Match($t, '(?m)^\| `\w+` \| `(?<c>[^`]+)`')
            if (-not $m.Success) { return $false }
            $g = $m.Groups['c']
            Set-Doc 'docs/field-bindings.md' ($t.Remove($g.Index, $g.Length).Insert($g.Index, 'nothing_at_all')) } }

    @{ Rule = 'K-44'; What = 'an instantiation cell in no readable form'
       File = 'docs/field-bindings.md'; Find = '| none yet |'; Repl = '| soon |' }

    @{ Rule = 'K-45'; What = 'a disposition left standing over a requirement that was retired'
       Do = { Set-Doc 'docs/requirements-register.md' (Set-Once (Get-Doc 'docs/requirements-register.md') '**R-03-003** ' '**R-03-903** ') } }

    @{ Rule = 'K-46'; What = 'a computed quantity with no claim to notice it going to zero'
       Do = {
            $t = Get-Doc 'tools/check.ps1'
            $m = [regex]::Match($t, "(?m)^(\s*)@\{ File = 'README\.md'; Q = 'absences';")
            if (-not $m.Success) { return $false }
            Set-Doc 'tools/check.ps1' ($t.Remove($m.Index, $m.Length).Insert($m.Index, ($m.Value -replace '@\{', '# @{'))) } }

    @{ Rule = 'K-47'; What = 'an enumeration whose reading has moved off the heading it read'
       File = 'docs/isa-profile.md'; Find = '### 5.1 '; Repl = '### 5.9 ' }

    @{ Rule = 'K-48'; What = 'a view drawing its members from a subsection the register no longer carries'
       Do = {
            $t = Get-Doc 'tools/check.ps1'
            $m = [regex]::Match($t, "Secs = '15\.14'")
            if (-not $m.Success) { return $false }
            Set-Doc 'tools/check.ps1' ($t.Remove($m.Index, $m.Length).Insert($m.Index, "Secs = '15.94'")) } }

    @{ Rule = 'K-49'; What = 'a view the register obliges and the repository does not carry'
       Do = { Remove-Item (Join-Path $Sandbox 'docs/absence-contract.md') -Force; $true } }
)

# =================================================================================
# run
# =================================================================================

"building the sandbox at $Sandbox"
$copied = New-Sandbox
"copied $copied tracked file(s), committed as the baseline"
""

# Nothing below means anything against a sandbox that was already failing: a mutant
# would be reported killed by whatever was broken before it was introduced.
$base = Invoke-Checker
if ($base.Exit -ne 0) {
    'FAIL: the unmutated sandbox does not pass, so no case can decide anything:'
    $base.Out | Where-Object { "$_" -match '^\s*FAIL' } | ForEach-Object { "  $_" }
    if (-not $Keep) { Remove-Item -Recurse -Force $Sandbox }
    exit 1
}
'ok: the unmutated sandbox passes, so every finding below is the mutant'
''

$selected = if ($Rule) { @($cases | Where-Object { $_.Rule -eq $Rule }) } else { $cases }
if ($Rule -and -not $selected.Count) { throw "no case for rule '$Rule'" }

$survived = @(); $unseeded = @(); $ran = 0
foreach ($c in $selected) {
    Reset-Sandbox
    $applied = if ($c.Do) { @(& $c.Do)[-1] } else {
        Set-Doc $c.File (Set-Once (Get-Doc $c.File) $c.Find $c.Repl)
    }
    # a mutation that would not apply is the sharper finding of the two: the document
    # it was written against has moved, so the case has stopped testing anything and
    # would report the rule live for as long as nobody looked
    if (-not $applied) {
        $unseeded += "$($c.Rule): the mutant will not apply; the document it seeds has moved"
        '{0,-6} UNSEEDED  {1}' -f $c.Rule, $c.What
        continue
    }

    $ran++
    $r = Invoke-Checker
    if ($c.Rule -in $r.Failed) {
        '{0,-6} killed    {1}' -f $c.Rule, $c.What
    } else {
        # a run that reported nothing and a run that died before reporting look the same
        # from the rule's side and are repaired differently, so the exit code is stated
        $how = if ($r.Failed.Count) { "other rules fired: $($r.Failed -join ', ')" }
               elseif ($r.Exit -eq 0) { 'the run was green' }
               else { "the run exited $($r.Exit) with no finding, so the checker did not survive the mutant either" }
        $survived += "$($c.Rule): the mutant survived; the rule read the defect and reported nothing ($how)"
        '{0,-6} SURVIVED  {1}' -f $c.Rule, $c.What
    }
}
Reset-Sandbox
''

# --- the repair path, which a green tree never exercises ---------------------------
#
# -Fix rewrites the asserted counts, the compounded product, and the checklist's
# totals from their artifacts, and on a repository that already agrees it rewrites
# nothing, so the branch ships untested unless something breaks it on purpose. Three
# defects at once, one per repairable group, and the test is that the repair leaves a
# tree the checker then passes.
'--- the repair path ---'
$fixCases = @($cases | Where-Object { $_.Rule -in 'K-24', 'K-28', 'K-37' })
foreach ($c in $fixCases) { if ($c.Do) { [void](& $c.Do) } }
$before = Invoke-Checker
$fix    = Invoke-Checker -Fix
$after  = Invoke-Checker
$repair = @()
if ($before.Exit -eq 0) { $repair += 'the three seeded figures did not fail the checker, so the repair proves nothing' }
if ($after.Exit -ne 0) {
    $repair += '-Fix left findings standing:'
    $repair += @($after.Out | Where-Object { "$_" -match '^\s*FAIL' } | ForEach-Object { "    $_" })
}
if (-not @($fix.Out | Where-Object { "$_" -match '^fixed:' }).Count) {
    $repair += '-Fix reported no repair, so it did not recognize the seeded figures'
}
if ($repair.Count) { $repair | ForEach-Object { "  $_" } } else {
    "  ok: three seeded figures failed the checker, -Fix rewrote $(@($fix.Out | Where-Object { "$_" -match '^fixed:' }).Count), and the tree then passes"
}
Reset-Sandbox
''

# --- every registered rule is either seeded here or declared unseedable ------------
#
# The registry is the enumeration of the tool's reach; this is the enumeration of what
# is held about that reach, and the two are checked against each other for the same
# reason check.ps1's meta group checks the registry against the code. A rule with no
# case is not a defect, but it must be a decision.
$unseedable = [ordered]@{}

'--- coverage of the registry ---'
$registered = @([regex]::Matches((Get-Content 'tools/check-rules.md' -Raw), '(?m)^\| (K-\d\d) \|') |
                ForEach-Object { $_.Groups[1].Value })
$covered    = @($cases | ForEach-Object { $_.Rule })
$gaps  = @($registered | Where-Object { $_ -notin $covered -and -not $unseedable.Contains($_) } |
           ForEach-Object { "$_ is registered, has no case here, and is not declared unseedable" })
$gaps += @($covered | Where-Object { $_ -notin $registered } |
           ForEach-Object { "$_ has a case here and no registry row" })
if ($gaps.Count) { $gaps | ForEach-Object { "  $_" } }
else { "  ok: all $($registered.Count) registered rules carry a case" }
''

if (-not $Keep) { Remove-Item -Recurse -Force $Sandbox } else { "sandbox kept at $Sandbox" }

$findings = $survived.Count + $unseeded.Count + $repair.Count + $gaps.Count
if ($findings) {
    ''
    ($survived + $unseeded) | ForEach-Object { $_ }
    "$findings finding(s); $ran of $($selected.Count) case(s) ran."
    exit 1
}
"every one of $ran rule(s) killed its mutant, the repair path holds, and the registry is covered."
exit 0
