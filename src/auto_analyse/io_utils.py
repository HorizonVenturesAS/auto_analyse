"""Shared checks before any report or sidecar is written."""
from pathlib import Path


def validate_outputs(source: Path, outputs: list[Path], *, overwrite: bool = False) -> None:
    resolved = [path.resolve() for path in outputs]
    if len(set(resolved)) != len(resolved):
        raise ValueError("Rapport og sidefiler må ha forskjellige filbaner.")
    for path in outputs:
        if path.resolve() == source.resolve() or (path.exists() and path.samefile(source)):
            raise ValueError("Målfil kan ikke være råfilen, heller ikke med --overwrite.")
        if path.exists() and not overwrite:
            raise ValueError(f"Filen finnes allerede: {path}. Velg ny målfil eller bruk --overwrite.")
        if path.exists() and not path.is_file():
            raise ValueError(f"Målfilen er ikke en vanlig fil: {path}")
