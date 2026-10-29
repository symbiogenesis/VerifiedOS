# Restore the retained WSL environment on another computer

The Q39/Q43 catalogs are metadata, not backups. Their native compiler objects,
sealed inputs, original helpers, installed libraries, switches and logs lived in
the old distribution. Preserve the whole distribution before trying to rebuild
anything. The contained compiler checkout also lived on Windows at
`C:\Users\symbi\source\repos\verifiedos-cheri-compcert`; a WSL export does not
copy that mounted Windows directory.

The commands below run in **PowerShell**. Replace `Ubuntu` with the old
distribution's exact name and `E:` with a transfer drive that has enough free
space. Finish active builds and stop applications using that distribution first.
The archive and private checkout stay outside the public repository.

## 1. Export on the old computer

[Microsoft's WSL command reference](https://learn.microsoft.com/en-us/windows/wsl/reference)
documents distribution export, import, termination and default selection.

```powershell
wsl --list --verbose
$oldDistro = 'Ubuntu'
$transfer = 'E:\VerifiedOS-transfer'
New-Item -ItemType Directory -Force -Path $transfer | Out-Null

wsl --distribution $oldDistro --user root -- uname -m |
    Set-Content -Encoding ascii -LiteralPath "$transfer\architecture.txt"
if ($LASTEXITCODE -ne 0) { throw 'Could not record the old architecture' }

wsl --terminate $oldDistro
if ($LASTEXITCODE -ne 0) { throw 'Could not stop the old distribution' }
wsl --export $oldDistro "$transfer\Ubuntu.tar"
if ($LASTEXITCODE -ne 0) { throw 'WSL export failed' }

(Get-FileHash -Algorithm SHA256 -LiteralPath "$transfer\Ubuntu.tar").Hash |
    Set-Content -Encoding ascii -LiteralPath "$transfer\Ubuntu.tar.sha256"
```

The export preserves the Linux filesystem, including `/root/build`,
`/root/.opam`, `/root/logs`, caches, home directories and `/etc` configuration.
It does not preserve running processes or resume an interrupted kernel audit.

Copy the two Windows repositories, including their hidden `.git`, worktrees and
ignored retained outputs. These commands copy into new transfer directories;
they do not mirror deletions. Robocopy exit codes below 8 indicate success.

```powershell
$oldRepos = 'C:\Users\symbi\source\repos'
foreach ($repoName in @('verifiedos-cheri-compcert', 'VerifiedOS')) {
    $source = Join-Path $oldRepos $repoName
    if (-not (Test-Path -LiteralPath $source -PathType Container)) {
        throw "Missing repository: $source"
    }
    robocopy $source "$transfer\WindowsRepos\$repoName" /E /COPY:DAT /DCOPY:DAT /XJ /R:2 /W:2
    if ($LASTEXITCODE -ge 8) { throw "Repository copy failed: $repoName" }
}
if (Test-Path -LiteralPath "$env:USERPROFILE\.wslconfig") {
    Copy-Item -LiteralPath "$env:USERPROFILE\.wslconfig" -Destination "$transfer\old.wslconfig"
}
```

Keep the old computer and its original directories until restoration is checked.
The saved `.wslconfig` is for comparison; its memory, processor and disk settings
may need adjustment for the new laptop. Junction targets excluded by `/XJ` need
their own backup if either repository uses them.

## 2. Check the transfer and architecture on the new computer

```powershell
$transfer = 'E:\VerifiedOS-transfer'
$expected = (Get-Content -LiteralPath "$transfer\Ubuntu.tar.sha256" -Raw).Trim()
if ((Get-FileHash -Algorithm SHA256 -LiteralPath "$transfer\Ubuntu.tar").Hash -ne $expected) {
    throw 'The transferred WSL archive hash differs'
}
Get-Content -LiteralPath "$transfer\architecture.txt"
wsl --list --verbose
wsl --distribution Ubuntu --user root -- uname -m
```

The new laptop inspected on 2026-10-29 reports `aarch64`. If the old machine also
reports `aarch64`, use the whole-distribution restore below. If it reports
`x86_64`, use the separate archive extraction instead: copying the filesystem
does not translate the old Linux executables into ARM64 executables.

## 3a. Matching architectures: restore the whole distribution

Import under a fresh name and directory. This keeps the new laptop's existing
Ubuntu distribution available. Imported distributions can be addressed explicitly
with `--distribution` and `--user root`; see
[Microsoft's custom-distribution guide](https://learn.microsoft.com/en-us/windows/wsl/use-custom-distro).

```powershell
wsl --import VerifiedOS-Restored C:\WSL\VerifiedOS-Restored "$transfer\Ubuntu.tar" --version 2
if ($LASTEXITCODE -ne 0) { throw 'WSL import failed' }
wsl --distribution VerifiedOS-Restored --user root -- ls -ld /root/build /root/.opam /root/logs
if ($LASTEXITCODE -ne 0) { throw 'Expected retained paths are missing' }
```

After checking the restored files, select it for the repository dispatcher,
which invokes the default distribution as root:

```powershell
wsl --set-default VerifiedOS-Restored
```

If the available backup is already an offline `ext4.vhdx` rather than a tar
export, use this alternative import into a fresh directory:

```powershell
wsl --import VerifiedOS-Restored C:\WSL\VerifiedOS-Restored E:\VerifiedOS-transfer\ext4.vhdx --vhd
```

## 3b. Different architectures: retain old files separately

Keep the current ARM64 Ubuntu distribution. Extract the export into a fresh
archive directory inside it, preserving the native environment:

```powershell
wsl --distribution Ubuntu --user root -- mkdir /root/old-wsl-snapshot
if ($LASTEXITCODE -ne 0) { throw 'Use a fresh snapshot directory' }
wsl --distribution Ubuntu --user root -- tar --numeric-owner --same-permissions -xpf /mnt/e/VerifiedOS-transfer/Ubuntu.tar -C /root/old-wsl-snapshot
if ($LASTEXITCODE -ne 0) { throw 'Snapshot extraction failed' }
wsl --distribution Ubuntu --user root -- ls -ld /root/old-wsl-snapshot/root/build /root/old-wsl-snapshot/root/.opam /root/old-wsl-snapshot/root/logs
```

Adjust `/mnt/e/VerifiedOS-transfer/Ubuntu.tar` when the transfer drive differs.
Do not overlay the old `/usr`, `/lib`, `/bin` or opam switch onto the ARM64
distribution. Retain the tar as the original backup. Toolchains must be rebuilt
for ARM64 under their locks, and compiled output must be regenerated where its
identity changes. Historical seals remain historical; the relocated snapshot
does not satisfy their original absolute-path and executable-identity checks.
No copied cache supplies a new Q39 qualification or a resumable checker state.
The repository's hosted-only installation and acceptance rules still apply.

## 4. Restore the private Windows source and preserve the old public checkout

Run this after copying the transfer drive to the new computer. Restore the
contained compiler to its original absolute path, with all its Git metadata.
Refuse an existing destination so a different checkout cannot be overwritten.

```powershell
$privateRepo = 'C:\Users\symbi\source\repos\verifiedos-cheri-compcert'
if (Test-Path -LiteralPath $privateRepo) { throw 'Private destination already exists; inspect it first' }
robocopy "$transfer\WindowsRepos\verifiedos-cheri-compcert" $privateRepo /E /COPY:DAT /DCOPY:DAT /XJ /R:2 /W:2
if ($LASTEXITCODE -ge 8) { throw 'Private repository restore failed' }

$oldPublicRepo = 'C:\Users\symbi\source\repos\VerifiedOS-old-snapshot'
if (Test-Path -LiteralPath $oldPublicRepo) { throw 'Public snapshot destination already exists' }
robocopy "$transfer\WindowsRepos\VerifiedOS" $oldPublicRepo /E /COPY:DAT /DCOPY:DAT /XJ /R:2 /W:2
if ($LASTEXITCODE -ge 8) { throw 'Public snapshot restore failed' }
```

Keep the current active `VerifiedOS` checkout in place. The old public snapshot
preserves ignored outputs and historical Git/worktree data for reconciliation;
its moved worktrees may still refer to their original locations. Matching WSL
architecture and paths permit a read-only validation attempt, not automatic
acceptance. Inspect the private repository's worktree locations, then use the
[retained compilation recipe](../docs/implementation/contracts/contained-compiler-reuse.md#retained-incomplete-compilation)
to revalidate exact input bytes before starting another qualification. Original
interrupted audit receipts retain their failed verdicts.
