# Answers, before work starts, what an edit re-opens in the apex statement.
#
#   tools/blast-radius.ps1 -Field composed_schedulability
#   tools/blast-radius.ps1 -Artifact proofs/SomeWorkstream.v
#   tools/blast-radius.ps1                # lists every field with its consumers
#
# The mechanical facts come from proofs/ApexTheorem.v alone, through the one parse
# tools/apex-record.ps1 holds, which tools/check.ps1's bindings group also reads, so
# the answer here and the checked view in docs/field-bindings.md cannot disagree. The
# artifact form reads that view's Instantiated-by column to find which fields an
# artifact discharges.
#
# The honest scope of the answer: a change to what a field *states* re-opens the
# definitions that consume it, and nothing else. The downstream trail printed
# after is conditional and labeled as such: a re-proved seam re-opens its
# consumers only if its conclusion's statement had to change too. And every seam
# sits under composition_meta_lemma, the R-18-031(b) linking theorem, which is
# always the last thing re-opened and is listed once rather than per line.

[CmdletBinding()]
param(
    [string]$Field,
    [string]$Artifact
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent

# --- the statement, through the parse the checker also reads -----------------------

. (Join-Path $PSScriptRoot 'apex-record.ps1')

$apex       = Get-ApexRecord (Join-Path $root 'proofs/ApexTheorem.v')
$propFields = $apex.Fields
$propSet    = $apex.FieldSet
$consumers  = $apex.Consumers
$defFields  = $apex.DefFields

# a seam's conclusion is the field after its implication arrow, which body order
# makes the last one read; everything else a seam reads is a premise
$seamConcl = @{}
foreach ($dn in $defFields.Keys) {
    if ($dn -like 'seam_*') { $seamConcl[$dn] = $defFields[$dn][$defFields[$dn].Count - 1] }
}

function Show-Field([string]$f) {
    "field $f"
    "  consumed by:"
    foreach ($c in $consumers[$f]) {
        $role = if ($seamConcl.ContainsKey($c)) { if ($seamConcl[$c] -eq $f) { ' (its conclusion)' } else { ' (a premise)' } } else { '' }
        "    $c$role"
    }
    # the conditional trail: premise-consuming seams conclude fields with their own consumers
    $trail = [System.Collections.Generic.List[string]]::new()
    $seen  = [System.Collections.Generic.HashSet[string]]::new(); [void]$seen.Add($f)
    $queue = [System.Collections.Generic.Queue[string]]::new(); $queue.Enqueue($f)
    while ($queue.Count) {
        $cur = $queue.Dequeue()
        foreach ($c in $consumers[$cur]) {
            if (-not $seamConcl.ContainsKey($c) -or $seamConcl[$c] -eq $cur) { continue }
            $g = $seamConcl[$c]
            if ($seen.Add($g)) {
                $trail.Add("    $c concludes $g")
                $queue.Enqueue($g)
            }
        }
    }
    if ($trail.Count) {
        "  downstream, only if a re-proved seam's conclusion statement must change:"
        $trail
    }
    "  and last, always: composition_meta_lemma, the R-18-031(b) linking theorem"
}

if ($Field) {
    if (-not $propSet.Contains($Field)) {
        "no Prop field '$Field' in the Vocabulary record; the fields are:"
        $propFields | ForEach-Object { "  $_" }
        exit 1
    }
    Show-Field $Field
    exit 0
}

if ($Artifact) {
    $bindPath = Join-Path $root 'docs/field-bindings.md'
    $hits = @()
    foreach ($line in [System.IO.File]::ReadAllLines($bindPath)) {
        if ($line -match '^\| ``?(\w+)``? \|') {
            $cells = $line -split '\|'
            if ($cells[4] -match [regex]::Escape($Artifact)) { $hits += ($cells[1].Trim() -replace '`', '') }
        }
    }
    if (-not $hits.Count) {
        "docs/field-bindings.md binds no field to an artifact matching '$Artifact'"
        exit 1
    }
    "artifact $Artifact instantiates: $($hits -join ', ')"
    ""
    foreach ($f in $hits) { Show-Field $f; "" }
    exit 0
}

"the Vocabulary record's Prop fields and their consumers:"
foreach ($f in $propFields) { "  $f  <=  $($consumers[$f] -join ', ')" }
"query one with -Field <name>, or an instantiating artifact with -Artifact <path>"
