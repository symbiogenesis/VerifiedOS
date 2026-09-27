# SPDX-License-Identifier: Apache-2.0
"""Scalar effects boundaries and native storage controls; target runs are separate."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import asm, kernel_effects, toolenv
from vos.corpus import find_root


def emit_controls() -> None:
    for defect in ('none', 'missing-save', 'tagless-save', 'lost-bootstrap',
                   'missing-scrub', 'stale-save', 'stale-frame'):
        assembler = asm.Assembler(kernel_effects.source(defect), defect)
        assembler.assemble()
        ensure(assembler.symbols['vos_trap_save_begin'] < assembler.symbols['vos_trap_save_end'],
               'empty save boundary')
    for bad in (-8, 1, 2048):
        try:
            kernel_effects.emit_save(offset=bad)
        except ValueError:
            continue
        raise AssertionError('invalid save extent accepted')
    adapter = kernel_effects.emit_retire_adapter() + kernel_effects.emit_wait_adapter()
    stubs = '\n'.join(f'{name}:\n ret' for name in (
        'vos_kernel_retirement_mask', 'vos_kernel_publication', 'vos_kernel_retire',
        'vos_kernel_wait_sample', 'vos_kernel_wait'))
    asm.Assembler('.text\n' + adapter + stubs, 'adapters').assemble()


def no_trace_no_evidence() -> None:
    assembler = asm.Assembler(kernel_effects.source(), 'empty')
    assembler.assemble()
    ensure(not any(kernel_effects.observations([], assembler.symbols).values()),
           'empty trace supplied trap evidence')


def owned_storage_controls() -> None:
    cc = shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
    ensure(cc is not None, 'native scalar effect tests require a C compiler')
    if cc is None:
        raise RuntimeError('no native C compiler')
    root = find_root()
    work = toolenv.environment(root, sys.platform).parent / "kernel-effects-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='kernel-effects-', dir=work) as directory:
        executable = Path(directory) / 'effects'
        sources = ('kernel/src/effects.c', 'kernel/src/context.c',
                   'supervisor/src/supervisor.c', 'supervisor/src/effects.c',
                   'supervisor/src/manifest.c', 'kernel/test/effects.c')
        result = subprocess.run([cc, '-std=c11', '-O1', '-Wall', '-Wextra', '-Werror',
            '-pedantic', '-DVOS_HOST_MODEL', '-I' + str(root / 'kernel/include'),
            '-I' + str(root / 'supervisor/include'), *(str(root / name) for name in sources),
            '-o', str(executable)], capture_output=True, text=True, check=False)
        ensure(result.returncode == 0, result.stderr)
        result = subprocess.run([str(executable)], capture_output=True, text=True,
                                timeout=30, check=False)
        ensure(result.returncode == 0, result.stderr)
        ensure('ok scalar effects ' in result.stderr, 'native effects controls not reached')


def cases() -> list[Case]:
    return [
        Case('scalar save and trusted adapters assemble', emit_controls),
        Case('missing trace supplies no scalar effects evidence', no_trace_no_evidence),
        Case('bounded owned-storage and effect ticket controls', owned_storage_controls, lane='guest'),
    ]
