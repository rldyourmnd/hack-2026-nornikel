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
    ".pptx",
    ".csv",
    ".md",
    ".markdown",
    ".txt",
    ".text",
    ".xlsx",
    ".xls",
}

# Archives found INSIDE an archive must be extracted too (and then re-expanded),
# so nested archives are never lost.
_ARCHIVE_EXTENSIONS = {".zip", ".rar"}
_EXTRACTABLE = INGESTIBLE_EXTENSIONS | _ARCHIVE_EXTENSIONS

_MULTIPART_ZIP_RE = re.compile(r"^(?P<base>.+\.zip)\.(?P<part>\d{3})$", re.IGNORECASE)
_MULTIPART_RAR_RE = re.compile(r"^(?P<base>.+)\.part(?P<part>\d+)\.rar$", re.IGNORECASE)

# Guards: archives can nest and can be decompression bombs.
_MAX_ARCHIVE_DEPTH = 8
_MAX_TOTAL_MEMBERS = 200_000
# Decompression-bomb byte guards (per-archive; nested archives each get their own).
_MAX_MEMBER_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
_MAX_TOTAL_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
_MAX_COMPRESSION_RATIO = 200
_COPY_CHUNK = 1024 * 1024


def _is_secondary_rar_part(name: str) -> bool:
    """True for X.part2.rar, X.part3.rar, … — bsdtar reads the whole multipart
    set from X.part1.rar, so the later volumes must not be processed again."""
    match = _MULTIPART_RAR_RE.match(name)
    return match is not None and int(match.group("part")) >= 2


def _should_extract(name: str) -> bool:
    """Whether an archive member is worth extracting: an ingestible document, a
    nested archive, or a multipart-zip volume."""
    if Path(name).suffix.lower() in _EXTRACTABLE:
        return True
    return bool(_MULTIPART_ZIP_RE.match(name))


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
    """Extract ingestible members + nested archives, preserving inner paths, with
    a zip-slip guard.

    Inner directory structure is kept and same-basename collisions across
    folders are disambiguated — the corpus is year-partitioned, so flattening
    would silently overwrite (e.g. two `report.pdf` from different years).
    """
    extracted: list[Path] = []
    total_bytes = 0
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            relative = _sanitize_member_path(member.filename)
            if relative is None or not _should_extract(relative.name):
                continue
            # Decompression-bomb guards, applied BEFORE writing to disk.
            if member.file_size > _MAX_MEMBER_UNCOMPRESSED_BYTES:
                logger.warning(
                    "Oversized zip member skipped: %s (%d bytes)",
                    member.filename,
                    member.file_size,
                )
                continue
            if (
                member.compress_size
                and member.file_size / member.compress_size > _MAX_COMPRESSION_RATIO
            ):
                logger.warning("Suspicious compression ratio skipped: %s", member.filename)
                continue
            if total_bytes + member.file_size > _MAX_TOTAL_UNCOMPRESSED_BYTES:
                logger.warning(
                    "Zip cumulative uncompressed cap reached at %s; stopping",
                    member.filename,
                )
                break
            destination = _collision_free(target_dir, relative)
            if not destination.resolve().is_relative_to(target_dir.resolve()):
                logger.warning("Zip-slip path skipped: %s", member.filename)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Byte-limited copy guards a spoofed header (real data > declared size).
            written = 0
            hard_cap = member.file_size + _COPY_CHUNK
            with archive.open(member) as source, destination.open("wb") as sink:
                while True:
                    chunk = source.read(_COPY_CHUNK)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > hard_cap:
                        break
                    sink.write(chunk)
            if written > hard_cap:
                destination.unlink(missing_ok=True)
                logger.warning("Zip member exceeded declared size, dropped: %s", member.filename)
                continue
            total_bytes += written
            extracted.append(destination)
    return extracted


def _rar_command(tool: str, exe: str, archive_path: Path, target_dir: Path) -> list[str]:
    if tool == "unar":
        return [exe, "-force-overwrite", "-output-directory", str(target_dir), str(archive_path)]
    if tool == "unrar":
        return [exe, "x", "-y", "-o+", str(archive_path), f"{target_dir}/"]
    if tool in ("7z", "7za", "7zz"):
        return [exe, "x", "-y", f"-o{target_dir}", str(archive_path)]
    return [exe, "-x", "-f", str(archive_path), "-C", str(target_dir)]  # bsdtar


def _extract_rar(archive_path: Path, target_dir: Path) -> list[Path]:
    """Extract a RAR (incl. multipart X.partN.rar) with the best available tool.

    Prefers unrar / 7z, which handle multi-volume RAR correctly; falls back to
    bsdtar (libarchive) for single-volume RARs. Files are returned ONLY when the
    tool reports success — bsdtar silently truncates multipart RARs, so a failed
    extraction yields nothing rather than a corrupt (truncated) document.
    """
    before = {path for path in target_dir.rglob("*") if path.is_file()}
    for tool in ("unar", "unrar", "7z", "7za", "7zz", "bsdtar"):
        exe = shutil.which(tool)
        if exe is None:
            continue
        result = subprocess.run(
            _rar_command(tool, exe, archive_path, target_dir),
            capture_output=True,
            timeout=600,
            check=False,
        )
        if result.returncode == 0:
            new_files = [
                path
                for path in target_dir.rglob("*")
                if path.is_file() and path not in before and _should_extract(path.name)
            ]
            total = sum(path.stat().st_size for path in new_files)
            if total > _MAX_TOTAL_UNCOMPRESSED_BYTES:
                logger.warning(
                    "RAR %s exceeded uncompressed cap (%d bytes); dropped",
                    archive_path.name,
                    total,
                )
                for path in target_dir.rglob("*"):
                    if path.is_file() and path not in before:
                        path.unlink(missing_ok=True)
                return []
            return new_files
        logger.warning(
            "%s failed on %s: %s", tool, archive_path.name, result.stderr.decode()[:200]
        )
    return []


def _dispatch(
    members: list[Path],
    work_dir: Path,
    ingestible: list[Path],
    stats: Counter[str],
    depth: int,
) -> None:
    """Route freshly-extracted members: ingestible documents are kept; nested
    archives are expanded recursively (depth/bomb guarded)."""
    nested: list[Path] = []
    for member in members:
        if member.suffix.lower() in _ARCHIVE_EXTENSIONS or _MULTIPART_ZIP_RE.match(member.name):
            nested.append(member)
        else:
            ingestible.append(member)
    if not nested:
        return
    if stats["archive_members"] > _MAX_TOTAL_MEMBERS:
        stats["archive_bomb_guard_tripped"] += 1
        logger.warning("Archive member cap reached; stopping nested expansion")
        return
    deeper, sub_stats = expand_archives(nested, work_dir, _depth=depth + 1)
    ingestible.extend(deeper)
    stats.update(sub_stats)
    stats["nested_archives_expanded"] += len(nested)


def expand_archives(
    files: list[Path], work_dir: Path, *, _depth: int = 0
) -> tuple[list[Path], Counter[str]]:
    """Expand .zip / multipart .zip.NNN / .rar / multipart .partN.rar archives
    into ingestible files, RECURSING into archives nested inside archives.

    Nested archives (an archive extracted from another archive) are themselves
    expanded, up to `_MAX_ARCHIVE_DEPTH`, so nothing is lost. Multipart archives
    are reassembled (zip) or read from the first volume (rar). A member cap
    guards against decompression bombs. Returns (ingestible file paths, stats).
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    stats: Counter[str] = Counter()
    ingestible: list[Path] = []
    if _depth > _MAX_ARCHIVE_DEPTH:
        stats["archive_depth_exceeded"] += 1
        logger.warning("Max archive nesting depth %d exceeded", _MAX_ARCHIVE_DEPTH)
        return ingestible, stats

    handled: set[Path] = set()

    # Multipart ZIP volumes (X.zip.001, X.zip.002, …) reassembled by concatenation.
    multipart_groups: dict[str, list[Path]] = {}
    for path in files:
        match = _MULTIPART_ZIP_RE.match(path.name)
        if match:
            multipart_groups.setdefault(str(path.parent / match.group("base")), []).append(path)

    for base_name, parts in sorted(multipart_groups.items()):
        parts.sort(key=lambda part: part.name)
        handled.update(parts)
        assembled = work_dir / f"__reassembled_{Path(base_name).name}"
        try:
            with assembled.open("wb") as sink:
                for part in parts:
                    sink.write(part.read_bytes())
            members = _safe_extract_zip(assembled, work_dir)
            stats["multipart_zip_expanded"] += 1
            stats["archive_members"] += len(members)
            _dispatch(members, work_dir, ingestible, stats, _depth)
        except (zipfile.BadZipFile, OSError) as error:
            stats["archive_failed"] += 1
            logger.warning("Multipart zip failed %s: %r", Path(base_name).name, error)
        finally:
            assembled.unlink(missing_ok=True)

    for path in files:
        if path in handled:
            continue
        suffix = path.suffix.lower()
        if suffix == ".zip":
            try:
                members = _safe_extract_zip(path, work_dir)
                stats["zip_expanded"] += 1
                stats["archive_members"] += len(members)
                _dispatch(members, work_dir, ingestible, stats, _depth)
            except (zipfile.BadZipFile, OSError) as error:
                stats["archive_failed"] += 1
                logger.warning("Zip failed %s: %r", path.name, error)
        elif suffix == ".rar":
            if _is_secondary_rar_part(path.name):
                # part2+ of a multipart RAR — bsdtar reads the whole set from part1.
                continue
            members = _extract_rar(path, work_dir)
            if members:
                stats["rar_expanded"] += 1
                stats["archive_members"] += len(members)
                _dispatch(members, work_dir, ingestible, stats, _depth)
            else:
                stats["rar_skipped"] += 1

    return ingestible, stats
