#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Emit one JSON record of peak resident bytes and wall clock for one child process.

Usage: peak.py <label> [--cwd DIR] [--stdin FILE] -- <argv...>

Predicate: `ru_maxrss` from `os.wait4` on the child this invocation forked, which is
the kernel's high-water mark of that child's resident set and of any descendant the
child itself reaped, reported in kibibytes on Linux and multiplied by 1024 here. It is
deliberately not `/usr/bin/time -v`, whose figure is the running maximum over every
child the timed process has ever waited for, so a driver that forks a preprocessor and
an assembler reports the largest of the three under that instrument and the compiler
proper under this one. An act whose driver does fork is measured by forking nothing:
the caller preprocesses first and hands this script the single process it means.

`wall_s` is `time.monotonic` around the fork and the wait, so it carries whatever load
and power state the machine was under; those two conditions are the caller's to stamp
beside the record, and no field here corrects for either. `user_s` and `sys_s` are the
same rusage's CPU times, which are load-independent in a way `wall_s` is not.
"""
import json
import os
import shlex
import sys
import time


def main(argv: list[str]) -> int:
    if "--" not in argv:
        print(__doc__, file=sys.stderr)
        return 2
    split = argv.index("--")
    head, child = argv[:split], argv[split + 1:]
    if not head or not child:
        print(__doc__, file=sys.stderr)
        return 2
    label, options = head[0], head[1:]
    cwd, stdin_path = None, None
    while options:
        flag = options.pop(0)
        if flag == "--cwd":
            cwd = options.pop(0)
        elif flag == "--stdin":
            stdin_path = options.pop(0)
        else:
            print(f"unknown option: {flag}", file=sys.stderr)
            return 2

    started = time.monotonic()
    pid = os.fork()
    if pid == 0:
        try:
            if cwd:
                os.chdir(cwd)
            if stdin_path:
                fd = os.open(stdin_path, os.O_RDONLY)
                os.dup2(fd, 0)
            os.execvp(child[0], child)
        except OSError as exc:  # the exec failed; the parent still gets a record
            print(str(exc), file=sys.stderr)
        os._exit(127)  # noqa: SLF001
    _, status, usage = os.wait4(pid, 0)
    wall = time.monotonic() - started

    json.dump({
        "label": label,
        "argv": child,
        "command": shlex.join(child),
        "cwd": cwd or os.getcwd(),
        "exit": os.waitstatus_to_exitcode(status),
        "peak_rss_bytes": usage.ru_maxrss * 1024,
        "wall_s": round(wall, 3),
        "user_s": round(usage.ru_utime, 3),
        "sys_s": round(usage.ru_stime, 3),
        "minor_faults": usage.ru_minflt,
        "major_faults": usage.ru_majflt,
        "predicate": "os.wait4 ru_maxrss of the child this process forked, KiB times 1024",
    }, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
