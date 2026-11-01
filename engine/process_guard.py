#!/usr/bin/env python3
"""Reap one owned POSIX process group when its launcher closes the pipe or dies.

Internal helper: stdin is a private pipe from the launcher, argv[1] its child's group id.
Never scans processes or matches names, and never receives a desktop browser's pid.
"""
import os
import signal
import sys


def main():
    group = int(sys.argv[1])
    if group <= 1 or group == os.getpgrp():
        sys.exit("Refusing to signal a non-owned process group")
    sys.stdin.buffer.read()
    try:
        os.killpg(group, signal.SIGKILL)
    except ProcessLookupError:
        pass


if __name__ == "__main__":
    main()
