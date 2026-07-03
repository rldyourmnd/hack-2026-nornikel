from __future__ import annotations

import logging
import re
import shutil
import subprocess
import zipfile
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)

# Extensions worth pulling out of archives (everything the ingester handles).
INGESTIBLE_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".docm",
    ".doc",
    ".csv",
    ".md",
    ".markdown",
    ".txt",
    ".xlsx",
    ".xls",
}

_MULTIPART_RE = re.compile(r"^(?P<base>.+\.zip)\.(?P<part>\d{3})$", re.IGNORECASE)


def _sanitize_member_path(filename: str) -> Path | None:
    """Archive-relative path with traversal components stripped, or None.

    Preserves inner directories (so same-named files in different folders do
    not collide) while dropping absolute roots, drive letters, and `..`.
    """
    raw = filename.replace("\\", "/")
    parts = [
        part
        for part in Path(raw).parts
        if part not in ("", "/", "..") and ":" not in part
    ]
    if not parts:
        return None
    return Path(*parts)


def _collision_free(target_dir: Path, relative: Path) -> Path:
    """A destination under target_dir that never overwrites an existing file."""
    candidate = target_dir / relative
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    index = 1
    while True:
        candidate = candidate.with_name(f"{stem}__{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def _safe_extract_zip(archive_path: Path, target_dir: Path) -> list[Path]:
    """Extract ingestible members preserving inner paths, with a zip-slip guard.

    Inner directory structure is kept and same-basename collisions across
    folders are disambiguated — the corpus is year-partitioned, so flattening
    would silently overwrite (e.g. two `report.pdf` from different years).
    """
    extracted: list[Path] = []
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            relative = _sanitize_member_path(member.filename)
            if relative is None or relative.suffix.lower() not in INGESTIBLE_EXTENSIONS:
                continue
            destination = _collision_free(target_dir, relative)
            if not destination.resolve().is_relative_to(target_dir.resolve()):
                logger.warning("Zip-slip path skipped: %s", member.filename)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as sink:
                shutil.copyfileobj(source, sink)
            extracted.append(destination)
    return extracted


def _extract_rar(archive_path: Path, target_dir: Path) -> list[Path]:
    """Best-effort RAR extraction via bsdtar (libarchive); [] when unavailable."""
    bsdtar = shutil.which("bsdtar")
    if bsdtar is None:
        return []
    before = {path for path in target_dir.rglob("*") if path.is_file()}
    result = subprocess.run(
        [bsdtar, "-x", "-f", str(archive_path), "-C", str(target_dir)],
        capture_output=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        logger.warning(
            "bsdtar failed on %s: %s", archive_path.name, result.stderr.decode()[:200]
        )
    return [
        path
        for path in target_dir.rglob("*")
        if path.is_file()
        and path not in before
        and path.suffix.lower() in INGESTIBLE_EXTENSIONS
    ]


def expand_archives(files: list[Path], work_dir: Path) -> tuple[list[Path], Counter[str]]:
    """Expand .zip / multipart .zip.NNN / .rar archives into ingestible files.

    Multipart archives (7-Zip/WinZip byte splits «X.zip.001, X.zip.002, …»)
    are reassembled by simple concatenation in part order — verified against
    the real corpus. Returns (extracted file paths, expansion stats).
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    stats: Counter[str] = Counter()
    extracted: list[Path] = []

    multipart_groups: dict[str, list[Path]] = {}
    for path in files:
        match = _MULTIPART_RE.match(path.name)
        if match:
            multipart_groups.setdefault(str(path.parent / match.group("base")), []).append(path)

    for base_name, parts in sorted(multipart_groups.items()):
        parts.sort(key=lambda p: p.name)
        assembled = work_dir / Path(base_name).name
        try:
            with assembled.open("wb") as sink:
                for part in parts:
                    sink.write(part.read_bytes())
            members = _safe_extract_zip(assembled, work_dir)
            extracted.extend(members)
            stats["multipart_zip_expanded"] += 1
            stats["archive_members"] += len(members)
        except (zipfile.BadZipFile, OSError) as error:
            stats["archive_failed"] += 1
            logger.warning("Multipart zip failed %s: %r", Path(base_name).name, error)
        finally:
            assembled.unlink(missing_ok=True)

    for path in files:
        suffix = path.suffix.lower()
        if suffix == ".zip":
            try:
                members = _safe_extract_zip(path, work_dir)
                extracted.extend(members)
                stats["zip_expanded"] += 1
                stats["archive_members"] += len(members)
            except (zipfile.BadZipFile, OSError) as error:
                stats["archive_failed"] += 1
                logger.warning("Zip failed %s: %r", path.name, error)
        elif suffix == ".rar":
            members = _extract_rar(path, work_dir)
            if members:
                extracted.extend(members)
                stats["rar_expanded"] += 1
                stats["archive_members"] += len(members)
            else:
                stats["rar_skipped"] += 1
    return extracted, stats
