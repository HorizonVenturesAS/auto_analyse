"""Read-only check for private data in share candidates and reachable Git history."""
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import subprocess

if __package__:
    from .generate_demo_data import ROOT, demo_files
else:
    from generate_demo_data import ROOT, demo_files

ARTIFACT_SUFFIXES = (".csv", ".csv.gz", ".tsv", ".xlsx", ".xls", ".xlsm", ".zip", ".sqlite", ".db", ".json", ".jsonl", ".pdf", ".png", ".jpg", ".jpeg", ".log", ".pem", ".key")
PLACEHOLDERS = {"data/inbox/.gitkeep", "data/inbox/brands/.gitkeep", "outputs/.gitkeep"}
SOURCE_DIRS = {"src", "tests", "scripts", "config", "docs", "examples", ".agents", ".github"}


def private_path(path: str) -> bool:
    path = path.replace("\\", "/")
    if path in PLACEHOLDERS or path in demo_files():
        return False
    return (path.startswith(("data/", "outputs/", "examples/"))
            or path.lower().endswith(ARTIFACT_SUFFIXES)
            or PurePosixPath(path).name.startswith(".env")
            or ".sqlite-" in path.lower())


def git(root: Path, *args: str, input: bytes | None = None) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def check(root: Path = ROOT, *, working_tree_only: bool = False) -> tuple[list[str], bool]:
    expected = demo_files()
    errors = []
    try:
        git(root, "rev-parse", "--git-dir")
        has_git = True
    except (RuntimeError, FileNotFoundError):
        has_git = False
    if has_git:
        candidates = set(git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").decode("utf-8").split("\0")) - {""}
    else:
        # A source-only download has no index/history. Never traverse local environments.
        candidates = {p.name for p in root.iterdir() if p.is_file()}
        for name in SOURCE_DIRS:
            directory = root / name
            if directory.is_dir():
                candidates.update(p.relative_to(root).as_posix() for p in directory.rglob("*") if p.is_file() and "__pycache__" not in p.parts and not p.is_symlink())
    for name in sorted(candidates):
        if (root / name).is_file() and private_path(name):
            errors.append("Privat data/artefakt i delingsutvalget: " + name)
    for name, content in expected.items():
        path = root / name
        if not path.is_file() or path.read_bytes() != content:
            errors.append("Demo mangler eller avviker fra syntetisk generator: " + name)
    if has_git:
        staged = git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").decode("utf-8").split("\0")
        for name in filter(None, staged):
            if private_path(name):
                errors.append("Privat data/artefakt staged i Git: " + name)
            if name in expected and git(root, "show", ":" + name) != expected[name]:
                errors.append("Staged demo er ikke generatorens syntetiske data: " + name)
        if not working_tree_only:
            objects = git(root, "rev-list", "--objects", "--all").decode("utf-8").splitlines()
            identifiers = [line.split(" ", 1)[0] for line in objects]
            types = dict(line.split() for line in git(root, "cat-file", "--batch-check=%(objectname) %(objecttype)", input=("\n".join(identifiers) + "\n").encode()).decode().splitlines()) if identifiers else {}
            for line in objects:
                object_id, separator, name = line.partition(" ")
                if types.get(object_id) != "blob":
                    continue
                if separator and private_path(name):
                    errors.append("Privat data/artefakt i Git-historikken: " + name)
                elif separator and name in expected and git(root, "cat-file", "blob", object_id) != expected[name]:
                    errors.append("Historisk demo avviker fra dagens syntetiske generator: " + name)
    elif not working_tree_only:
        errors.append("Git-historikk kunne ikke kontrolleres. Kjør full kontroll i repoet som skal pushes.")
    return sorted(set(errors)), has_git


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working-tree-only", action="store_true", help="Utviklingskontroll uten Git-historikk; ikke klarsignal til push.")
    args = parser.parse_args()
    try:
        errors, _ = check(working_tree_only=args.working_tree_only)
    except (OSError, RuntimeError) as error:
        parser.exit(1, str(error) + "\n")
    if errors:
        print("DELING BLOKKERT:")
        for error in errors:
            print("- " + error)
        print("Se docs/development.md. Ingen filer eller Git-referanser er endret.")
        return 1
    print("OK: " + ("arbeidsfiler og staged filer kontrollert; historikk er IKKE kontrollert." if args.working_tree_only else "delingsutvalg, staged filer og tilgjengelig Git-historikk kontrollert."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
