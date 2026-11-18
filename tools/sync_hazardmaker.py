#!/usr/bin/env python3
"""Bring a released version of SR-HazardMaker into the ShakeReady site.

SR-HazardMaker lives in its own repository (https://github.com/TRG-UCLA/SR-HazardMaker). This site
does not keep a private copy of its code: it takes the tool's browser files and its Python package
from a tagged release, unchanged, and records which release and which checksums.

Usage, from the repository root:
    python3 tools/sync_hazardmaker.py /path/to/SR-HazardMaker [tag-or-commit]

Then run the site's checks and `python3 tools/build_provenance.py`, and commit.
"""
import datetime, hashlib, json, os, shutil, subprocess, sys

WEB = ["sr-hazard.js", "converters.js", "app.js", "app.css"]


def git(repo, *args):
    return subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True, check=True).stdout.strip()


def main(src, ref="HEAD"):
    commit = git(src, "rev-parse", ref + "^{commit}")       # the commit itself, also when ref is an annotated tag
    tags = git(src, "tag", "--points-at", commit).split()
    dirty = git(src, "status", "--porcelain")
    if dirty:
        sys.exit("SR-HazardMaker has uncommitted changes. Commit or stash them first, so the copy matches a real commit.")
    files = {}
    os.makedirs("hazardmaker/lib", exist_ok=True)
    for name in WEB:
        text = git(src, "show", f"{commit}:docs/{name}") + "\n"
        with open(os.path.join("hazardmaker/lib", name), "w", encoding="utf-8", newline="") as f:
            f.write(text)
        files["hazardmaker/lib/" + name] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    dest = "tools/vendor/sr_hazardmaker"
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    for name in git(src, "ls-tree", "--name-only", f"{commit}:src/sr_hazardmaker").split("\n"):
        if name.endswith(".py"):
            text = git(src, "show", f"{commit}:src/sr_hazardmaker/{name}") + "\n"
            with open(os.path.join(dest, name), "w", encoding="utf-8", newline="") as f:
                f.write(text)
            files[f"{dest}/{name}"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    version = {"tool": "SR-HazardMaker", "repository": "https://github.com/TRG-UCLA/SR-HazardMaker", "tag": tags[0] if tags else None, "commit": commit,
               "synced_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "files": files}
    with open("hazardmaker/lib/VERSION.json", "w", encoding="utf-8") as f:
        json.dump(version, f, indent=1)
    print(f"SR-HazardMaker {version['tag'] or commit[:7]} copied: {len(files)} files")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(*sys.argv[1:3])
