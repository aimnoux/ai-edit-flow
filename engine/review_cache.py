"""Content-addressed review inputs and integrity-checked, atomic manifests.

No timestamps participate in freshness. Unknown network/dynamic dependencies disable reuse.
A manifest attests generated evidence only; a human conclusion has its own hash and binding.
"""
import contextlib
import hashlib
import importlib.metadata
import json
import math
import os
import re
import tempfile
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import common

SCHEMA = 1
MANIFEST = "review-manifest.json"
CODE = ("review.py", "review_cache.py", "check.py", "common.py", "hf.mjs",
        "process_guard.py", "compare.py", "build.py", "vertical.py", "verify.py")
TEXT = {".html", ".css", ".js", ".mjs", ".svg"}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def browser_identity():
    path = Path(common.chrome()).resolve()
    # Managed shells live under a version/build directory. The binary content hash is
    # authoritative even for explicitly supplied shells with an uninformative dirname.
    return {"path": str(path), "version": path.parent.name, "sha256": digest(path)}



def runtime_identity():
    packages = {}
    for name in ("Pillow", "numpy", "scipy"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "not-installed"
    return {"python": sys.version, "platform": sys.platform,
            "machine": os.uname().machine if hasattr(os, "uname") else os.environ.get("PROCESSOR_ARCHITECTURE"),
            "packages": packages}


def normalize_chapter(chapter):
    if chapter is None:
        return None
    if len(chapter) != 2:
        raise ValueError("--chapter needs START END")
    a, b = map(float, chapter)
    if not math.isfinite(a) or not math.isfinite(b) or a < 0 or b <= a:
        raise ValueError("--chapter requires finite 0 <= START < END")
    return [a, b]


def review_name(cid, chapter):
    # repr is round-trip exact: unlike rounded integer names, nearby ranges cannot collide.
    return cid + ("-" + "-".join(repr(t) for t in chapter) if chapter else "")


def fingerprint(cid, chapter=None, video=None):
    here, root = common.HERE, common.ROOT
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", cid):
        raise ValueError("Invalid composition id")
    chapter = normalize_chapter(chapter)
    composition = here / f"{cid}.html"
    content = composition.read_text(encoding="utf-8")
    duration = re.search(r'id=["\']root["\'][^>]*data-duration=["\']([\d.]+)', content)
    if not duration or not math.isfinite(float(duration.group(1))) or float(duration.group(1)) <= 0:
        raise ValueError("Composition needs a positive root duration")
    if chapter and chapter[1] > float(duration.group(1)):
        raise ValueError("--chapter END exceeds composition duration")
    dependencies, pending, reasons = {}, [], []

    queued = set()

    def add(path, scan=True):
        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Review dependency missing: {path}")
        if path.is_dir():
            # Visit resolved directories once, including symlinked asset directories.
            if (path, scan) in visited_dirs:
                return
            visited_dirs.add((path, scan))
            for child in sorted(path.iterdir()):
                add(child, scan)
        elif path.is_file():
            if str(path) not in dependencies:
                dependencies[str(path)] = digest(path)
            if scan and path.suffix.lower() in TEXT and path not in queued:
                pending.append(path)
                queued.add(path)

    visited_dirs = set()
    add(composition)
    for name in CODE:
        add(here / name, scan=False)
    for name in ("lib", "template.html", "template-v.html", "hyperframes.json"):
        add(here / name, scan=False)
    add(root / "style", scan=False)
    add(root / ".agents" / "skills" / "review")
    add(root / "package.json")
    add(root / "requirements.txt")
    for lock in ("package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock"):
        if (root / lock).exists():
            add(root / lock)
    match = re.fullmatch(r"(.+)-(?:ch\d+|s\d+-[^/]+)", cid)
    project = match.group(1) if match else cid
    video_project = root / "videos" / project
    if video_project.exists():
        for p in sorted(video_project.rglob("*")):
            if p.is_file() and p.suffix.lower() in {".md", ".json"}:
                add(p)
    for p in (root / "vertical" / f"{project}.md", root / "vertical" / f"{project}.json"):
        if p.exists():
            add(p)
    if video is not None:
        add(Path(video).resolve())

    def known_avatar(origin):
        if origin != (here / "lib" / "vertical.js").resolve():
            return False
        try:
            assignment = re.search(r"window\.TIMING\s*=\s*", content)
            if not assignment:
                raise ValueError("missing TIMING JSON")
            timing, _ = json.JSONDecoder().raw_decode(content[assignment.end():])
            avatar = (timing.get("channel") or {}).get("avatar") or ""
            if not isinstance(avatar, str):
                raise ValueError("invalid avatar")
            if not avatar:
                return True
            parts = urlsplit(avatar)
            if parts.scheme or parts.netloc or avatar.startswith(("/", "\\")) or "\\" in avatar:
                raise ValueError("avatar must be a local path under lib")
            target = (here / "lib" / unquote(parts.path)).resolve()
            if not target.is_relative_to((here / "lib").resolve()):
                raise ValueError("avatar escapes lib")
            add(target)
            return True
        except (AttributeError, TypeError, ValueError) as exc:
            reasons.append(f"unresolved vertical avatar: {exc}")
            return True

    def reference(ref, base, origin):
        ref = ref.strip()
        if not ref or ref.startswith(("#", "data:", "about:")):
            return
        if "${" in ref:
            if ref == "lib/${ch.avatar}" and known_avatar(origin):
                return
            reasons.append(f"dynamic dependency in {base}: {ref}")
            return
        parts = urlsplit(ref)
        if parts.scheme or parts.netloc or ref.startswith("//"):
            reasons.append(f"external dependency: {ref}")
            return
        if ref.startswith(("/", "\\")):
            # file:// previews and the HyperFrames project server resolve / differently.
            reasons.append(f"ambiguous root-relative dependency; use a relative asset path: {ref}")
            return
        local = unquote(parts.path)
        if not local:
            return
        add((here if local.startswith("/") else base) / local.lstrip("/"))

    while pending:
        path = pending.pop()
        text = path.read_text(encoding="utf-8", errors="replace")
        # Commented font examples and documentation do not load dependencies.
        text = re.sub(r"<!--.*?-->|/\*.*?\*/", "", text, flags=re.S)
        # src/href and CSS in JS templates are document relative; CSS files are file relative.
        base = path.parent if path.suffix.lower() in {".css", ".html", ".svg"} else here
        for ref in re.findall(r"\b(?:src|href|poster)\s*=\s*[\"'`]([^\"'`]+)[\"'`]", text, re.I):
            reference(ref, base, path)
        # kit.svg(..., {href: "..."}) and other DOM-attribute object literals.
        for ref in re.findall(r"(?:[\"'`]?(?:href|src|poster)[\"'`]?)\s*:\s*[\"'`]([^\"'`]+)[\"'`]", text):
            reference(ref, here, path)
        if path.suffix.lower() != ".css" and re.search(r"[\"'`]?(?:href|src|poster)[\"'`]?\s*:\s*(?![\s\"'`])", text):
            reasons.append(f"unresolved object resource attribute: {path}")
        if re.search(r"[,{]\s*\[[^]\n]+\]\s*:", text):
            reasons.append(f"unresolved computed object attribute: {path}")
        for ref in re.findall(r"\burl\(\s*[\"'`]?([^\s)'\"`]+)", text, re.I):
            reference(ref, base, path)
        for ref in re.findall(r"(?:\bfrom\s+|\bimport(?:\s+|\s*\(\s*)|@import\s+)[\"'`]([^\"'`]+)[\"'`]", text):
            reference(ref, path.parent, path)
        for ref in re.findall(r"\bfetch\(\s*[\"'`]([^\"'`]+)[\"'`]", text):
            reference(ref, here, path)
        if re.search(r"\b(?:fetch|import)\(\s*(?![\s\"'`])", text):
            reasons.append(f"unresolved dynamic import/fetch: {path}")
        if re.search(r"\.(?:src|href)\s*=\s*(?![\s\"'`])", text):
            reasons.append(f"unresolved dynamic resource assignment: {path}")
        if re.search(r"\[\s*[\"'`](?:src|href|poster|srcset)[\"'`]\s*\]\s*=", text):
            reasons.append(f"unresolved bracket resource assignment: {path}")
        if re.search(r"\bsetAttributeNS\s*\(", text):
            reasons.append(f"unresolved namespaced resource attribute: {path}")
        if re.search(r"\bsetAttribute\s*\(\s*[\"'`](?:src|href|srcset|poster)[\"'`]", text, re.I):
            reasons.append(f"unresolved setAttribute resource: {path}")
        if re.search(r"\bsrcset\s*=", text, re.I):
            reasons.append(f"unresolved srcset: {path}")
        if re.search(r"\b(?:XMLHttpRequest|WebSocket|Worker|EventSource)\s*\(", text):
            reasons.append(f"unresolved resource loader: {path}")
    browser = browser_identity()
    payload = {"schema": SCHEMA, "cid": cid, "chapter": chapter,
               "video": str(Path(video).resolve()) if video is not None else None,
               "dependencies": dependencies, "browser": browser, "runtime": runtime_identity(),
               "unresolved": sorted(set(reasons))}
    key = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"fingerprint": key, "reusable": not reasons, "reasons": sorted(set(reasons)),
            "dependencies": dependencies, "browser": browser, "chapter": chapter}


@contextlib.contextmanager
def review_lock(out):
    """Kernel-owned lock: released on process death, persistent inode avoids lock races."""
    with (Path(out) / ".review-lock").open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError(f"Another review is using {out}; retry after it exits") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def atomic_json(path, data):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix=".review-manifest-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_manifest(out, current):
    try:
        manifest = json.loads((out / MANIFEST).read_text(encoding="utf-8"))
        if (not current["reusable"] or manifest["schema"] != SCHEMA
                or manifest["fingerprint"] != current["fingerprint"]):
            return None
        if (not isinstance(manifest.get("findings"), list)
                or not all(isinstance(line, str) for line in manifest["findings"])
                or not isinstance(manifest.get("runtime"), dict)
                or not isinstance(manifest["runtime"].get("scenes"), int)
                or not isinstance(manifest["runtime"].get("duration"), (int, float))
                or not math.isfinite(manifest["runtime"]["duration"])
                or manifest["runtime"]["duration"] <= 0
                or not isinstance(manifest["runtime"].get("vertical"), bool)
                or not isinstance(manifest.get("sheets"), list)
                or not all(isinstance(name, str) for name in manifest["sheets"])
                or not isinstance(manifest.get("artifacts"), dict)
                or not isinstance(manifest.get("conclusion"), (dict, type(None)))):
            return None
        artifacts = manifest["artifacts"]
        if ("REVIEW-INPUT.md" not in artifacts or not manifest["sheets"]
                or not all(name in artifacts for name in manifest["sheets"])):
            return None
        for name, expected in artifacts.items():
            path = out / name
            if Path(name).name != name or digest(path) != expected:
                return None
        return manifest
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def reviewer_verdict(text):
    verdicts = re.findall(r"^\s*Verdict:\s*(PASS|FAIL)\s*$", text, re.I | re.M)
    if len(verdicts) != 1:
        raise ValueError("Reviewer conclusion needs exactly one Verdict: PASS or Verdict: FAIL line")
    return verdicts[0].lower()


def reviewer_binding(text, fingerprint):
    matches = re.findall(r"^\s*Fingerprint:\s*([a-f0-9]{64})\s*$", text, re.I | re.M)
    if len(matches) != 1 or matches[0].lower() != fingerprint:
        raise ValueError("Reviewer conclusion needs the current Fingerprint: from REVIEW-INPUT.md")
    return reviewer_verdict(text)


def conclusion(out, manifest):
    binding = manifest.get("conclusion") or {}
    path = out / "REVIEW.md"
    try:
        if (binding.get("fingerprint") == manifest["fingerprint"] and binding.get("sha256")
                and path.read_text(encoding="utf-8").strip() and digest(path) == binding["sha256"]):
            return {"status": "current", "path": str(path.resolve()),
                    "verdict": reviewer_binding(path.read_text(encoding="utf-8"), manifest["fingerprint"])}
    except (OSError, ValueError):
        pass
    return {"status": "pending", "path": None, "verdict": None}
