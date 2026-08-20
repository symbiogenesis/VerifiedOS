# The apex statement's Vocabulary record, read once and shared.
#
# proofs/ApexTheorem.v is the coverage checklist R-18-031(a) requires: every side-property
# some seam consumes or concludes is a Prop field of the record, and a field nothing
# instantiates is an uncovered obligation with exactly one name. Two tools ask the same
# question of it. tools/check.ps1 holds docs/field-bindings.md against the fields and
# their consumers; tools/blast-radius.ps1 answers what an edit re-opens. Parsed twice they
# would be one fact restated by hand, which is the defect both tools exist to catch, so
# the parse is here and neither carries a copy of it.
#
# Dot-source this file and call Get-ApexRecord with the .v's path.

function Get-ApexRecord([string]$Path) {
    $raw = [System.IO.File]::ReadAllText($Path)

    # comments strip innermost-first, so nesting unwinds; each pass removes at least
    # one balanced comment until none is left to match
    while ($true) {
        $stripped = [regex]::Replace($raw, '(?s)\(\*(?:(?!\(\*|\*\)).)*\*\)', '')
        if ($stripped -eq $raw) { break }
        $raw = $stripped
    }

    $recM   = [regex]::Match($raw, '(?s)Record Vocabulary : Type := \{(.*?)\}\.')
    $fields = @([regex]::Matches($recM.Groups[1].Value, '(?m)^\s*(\w+) : Prop\s*;?\s*$') |
                ForEach-Object { $_.Groups[1].Value })
    $set    = [System.Collections.Generic.HashSet[string]]::new([string[]]$fields)

    $consumers = [ordered]@{}   # field -> the definitions and coercions touching it
    foreach ($f in $fields) { $consumers[$f] = [System.Collections.Generic.List[string]]::new() }

    # a coercion field whose type cites Prop fields consumes them
    foreach ($m in [regex]::Matches($recM.Groups[1].Value, '(?m)^\s*(\w+) : ([\w>< -]+?);?\s*$')) {
        $name = $m.Groups[1].Value
        foreach ($w in [regex]::Matches($m.Groups[2].Value, '\w+')) {
            if ($set.Contains($w.Value) -and $w.Value -ne $name) { $consumers[$w.Value].Add($name) }
        }
    }

    # every Definition consuming a field through the record value: v.(field), in body order
    $defFields = [ordered]@{}
    foreach ($dm in [regex]::Matches($raw, '(?sm)^Definition (\w+)(.*?)(?=^(?:Definition|Lemma|Print|Record)\b|\z)')) {
        $dn    = $dm.Groups[1].Value
        $reads = [System.Collections.Generic.List[string]]::new()
        foreach ($fm in [regex]::Matches($dm.Groups[2].Value, 'v\.\((\w+)\)')) {
            $f = $fm.Groups[1].Value
            if ($set.Contains($f) -and -not $reads.Contains($f)) { $reads.Add($f) }
        }
        if ($reads.Count) {
            $defFields[$dn] = $reads
            foreach ($f in $reads) { $consumers[$f].Add($dn) }
        }
    }

    [pscustomobject]@{
        Fields    = $fields      # the Prop fields, in declaration order
        FieldSet  = $set
        Consumers = $consumers   # field -> what touches it
        DefFields = $defFields   # definition -> the fields it reads, in body order
    }
}
