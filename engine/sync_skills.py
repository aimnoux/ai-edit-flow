#!/usr/bin/env python3
"""Generate portable Claude skill copies from the canonical .agents tree; --check never writes."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sync(root=ROOT, check=False):
    source, target = root / ".agents/skills", root / ".claude/skills"
    if not source.is_dir():
        raise ValueError("Missing canonical .agents/skills")
    if source.is_symlink() or any(p.is_symlink() for p in source.rglob("*")):
        raise ValueError("Canonical skills must be ordinary portable files/directories")
    if target.is_symlink():
        if check:
            raise ValueError("Generated skills must be ordinary files; run python engine/sync_skills.py")
        target.unlink()
    def files(path):
        return {p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()}
    expected, actual = files(source), files(target)
    changed = sorted(str(p) for p in expected.keys() | actual.keys() if expected.get(p) != actual.get(p))
    changed = sorted(set(changed) | {str(p.relative_to(target)) for p in target.rglob("*") if p.is_symlink()})
    if check:
        if changed:
            raise ValueError("Generated skills differ: " + ", ".join(changed) + "; run python engine/sync_skills.py")
    else:
        for path in target.rglob("*"):
            if path.is_symlink():
                path.unlink()  # Never write through a pre-existing compatibility symlink.
        for path in sorted(actual.keys() - expected.keys()):
            (target / path).unlink(missing_ok=True)
        for path, data in expected.items():
            destination = target / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.is_symlink():
                destination.unlink()
            if actual.get(path) != data or not destination.exists():
                destination.write_bytes(data)
        # Remove empty obsolete skill directories, never unrelated .claude configuration.
        for path in sorted(target.rglob("*"), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        changed = sync(check=args.check)
    except ValueError as exc:
        parser.exit(1, str(exc) + "\n")
    print("Skills match" if args.check else f"Synced {len(changed)} skill files")


if __name__ == "__main__":
    main()
