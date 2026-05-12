"""Parsers and serialisers for Delft3D configuration files.

Two formats are supported:

* **``.mdu``** (D-Flow FM) — INI-style, with bracketed sections like
  ``[General]`` / ``[Geometry]`` / ``[Numerics]`` and ``key = value`` pairs.
* **``.mdf``** (Delft3D 4) — flat ``key = value`` (no sections), values can
  be free strings (often quoted with ``#`` delimiters), numbers or lists
  spanning multiple continuation lines.

Both parsers are best-effort but lossless for the typical input we expect:
order is preserved, comments are kept on the lines they appear on, and
re-serialising an unmodified document yields the same byte stream up to
trailing whitespace normalisation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum, unique
from pathlib import Path
from typing import Final


@unique
class ConfigFormat(StrEnum):
    """Supported configuration formats."""

    MDU = "mdu"
    """D-Flow FM (INI with sections)."""

    MDF = "mdf"
    """Delft3D 4 (flat ``key = value`` document)."""


# ---------------------------------------------------------------------------
# Document model
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ConfigEntry:
    """One ``key = value`` pair plus an optional inline comment."""

    key: str
    value: str
    comment: str = ""
    """Inline trailing comment (without the leading marker)."""


@dataclass(slots=True)
class ConfigSection:
    """A named section. For flat formats there is one default section."""

    name: str
    """Section name without the surrounding brackets, or ``""`` for default."""
    entries: list[ConfigEntry] = field(default_factory=list)
    leading_blank_lines: int = 0
    """Number of blank lines that precede the section header on output."""

    def get(self, key: str) -> ConfigEntry | None:
        """Return the first entry whose key matches (case-insensitively)."""
        lower = key.lower()
        return next((e for e in self.entries if e.key.lower() == lower), None)

    def set(self, key: str, value: str) -> None:
        """Update or append the entry for ``key``."""
        existing = self.get(key)
        if existing is not None:
            existing.value = value
        else:
            self.entries.append(ConfigEntry(key=key, value=value))


@dataclass(slots=True)
class ConfigDocument:
    """In-memory representation of a parsed configuration file."""

    path: Path
    format: ConfigFormat
    sections: list[ConfigSection] = field(default_factory=list)
    leading_comments: list[str] = field(default_factory=list)
    """Lines preceding any section / entry (verbatim, without trailing newline)."""

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------
    def section(self, name: str) -> ConfigSection | None:
        """Return the section whose name matches (case-insensitively)."""
        lower = name.lower()
        return next((s for s in self.sections if s.name.lower() == lower), None)

    def get(self, section: str, key: str) -> str | None:
        """Look up the (raw) value of ``section.key``, or ``None`` if absent."""
        sec = self.section(section)
        if sec is None:
            return None
        entry = sec.get(key)
        return entry.value if entry is not None else None

    def set(self, section: str, key: str, value: str) -> None:
        """Update (or insert) the value of ``section.key``."""
        sec = self.section(section)
        if sec is None:
            sec = ConfigSection(name=section)
            self.sections.append(sec)
        sec.set(key, value)

    # ------------------------------------------------------------------
    # I/O facade
    # ------------------------------------------------------------------
    @classmethod
    def load(cls, path: Path) -> ConfigDocument:
        """Read ``path`` and return a parsed :class:`ConfigDocument`."""
        path = Path(path).expanduser().resolve()
        fmt = detect_format(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        if fmt is ConfigFormat.MDU:
            return parse_mdu(text, path=path)
        return parse_mdf(text, path=path)

    def save(self, path: Path | None = None) -> Path:
        """Write the document back; optionally to a different ``path``."""
        target = Path(path) if path is not None else self.path
        payload = serialize_mdu(self) if self.format is ConfigFormat.MDU else serialize_mdf(self)
        target.write_text(payload, encoding="utf-8")
        return target


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


def detect_format(path: Path) -> ConfigFormat:
    """Detect format by extension."""
    suffix = path.suffix.lower()
    if suffix == ".mdu":
        return ConfigFormat.MDU
    if suffix == ".mdf":
        return ConfigFormat.MDF
    raise ValueError(f"Unsupported configuration extension: {suffix!r}")


# ---------------------------------------------------------------------------
# .mdu parser  (INI with sections)
# ---------------------------------------------------------------------------

_SECTION_RE: Final = re.compile(r"^\[\s*(?P<name>[^\]]+)\s*\]\s*$")
_KEY_VALUE_RE: Final = re.compile(r"^(?P<key>[^=#\[\s][^=#]*?)\s*=\s*(?P<value>.*?)\s*$")


def _split_value_comment(raw: str) -> tuple[str, str]:
    """Separate ``raw`` into ``(value, trailing comment)`` for ``.mdu`` lines."""
    raw = raw.strip()
    if not raw:
        return "", ""
    # Whole-value comment: a line like ``key =  # blah`` is value="" / comment="blah".
    if raw.startswith("#"):
        return "", raw[1:].strip()
    # Otherwise, only treat ``#`` as comment when preceded by whitespace, so
    # values containing ``#`` (e.g. Delft3D-style ``#path#`` strings) survive.
    for idx, ch in enumerate(raw):
        if ch == "#" and idx > 0 and raw[idx - 1].isspace():
            return raw[:idx].rstrip(), raw[idx + 1 :].strip()
    return raw, ""


def parse_mdu(text: str, *, path: Path | None = None) -> ConfigDocument:
    """Parse the textual content of a ``.mdu`` file."""
    doc = ConfigDocument(path=path or Path("untitled.mdu"), format=ConfigFormat.MDU)
    current: ConfigSection | None = None
    pending_blanks = 0

    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            pending_blanks += 1
            continue

        section_match = _SECTION_RE.match(stripped)
        if section_match:
            name = section_match.group("name").strip()
            current = ConfigSection(name=name, leading_blank_lines=pending_blanks)
            doc.sections.append(current)
            pending_blanks = 0
            continue

        if stripped.startswith(("#", "*")):
            if current is None:
                doc.leading_comments.append(raw.rstrip())
            else:
                # Preserve as a synthetic comment-only entry.
                current.entries.append(
                    ConfigEntry(key="", value="", comment=stripped.lstrip("#*").strip())
                )
            pending_blanks = 0
            continue

        kv = _KEY_VALUE_RE.match(stripped)
        if not kv:
            # Unrecognised content — keep verbatim as a comment-only entry.
            if current is None:
                doc.leading_comments.append(raw.rstrip())
            else:
                current.entries.append(ConfigEntry(key="", value="", comment=raw.rstrip()))
            pending_blanks = 0
            continue

        key = kv.group("key").strip()
        value, comment = _split_value_comment(kv.group("value"))

        if current is None:
            current = ConfigSection(name="", leading_blank_lines=pending_blanks)
            doc.sections.append(current)
        current.entries.append(ConfigEntry(key=key, value=value, comment=comment))
        pending_blanks = 0
    return doc


def serialize_mdu(doc: ConfigDocument) -> str:
    """Render a :class:`ConfigDocument` back to ``.mdu`` text."""
    lines: list[str] = []
    if doc.leading_comments:
        lines.extend(doc.leading_comments)

    longest_key = max(
        (len(e.key) for s in doc.sections for e in s.entries if e.key),
        default=0,
    )
    pad = max(longest_key, 16)

    for section in doc.sections:
        for _ in range(max(1, section.leading_blank_lines) if lines else 0):
            lines.append("")
        if section.name:
            lines.append(f"[{section.name}]")
        for entry in section.entries:
            if not entry.key:
                if entry.comment:
                    lines.append(entry.comment)
                continue
            line = f"{entry.key.ljust(pad)} = {entry.value}".rstrip()
            if entry.comment:
                line += f" # {entry.comment}"
            lines.append(line)
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# .mdf parser  (flat ``key = value``)
# ---------------------------------------------------------------------------


def parse_mdf(text: str, *, path: Path | None = None) -> ConfigDocument:
    """Parse the textual content of a ``.mdf`` file (flat, no sections)."""
    doc = ConfigDocument(path=path or Path("untitled.mdf"), format=ConfigFormat.MDF)
    section = ConfigSection(name="")
    doc.sections.append(section)

    last_entry: ConfigEntry | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            last_entry = None
            continue
        if line.lstrip().startswith("*"):
            section.entries.append(
                ConfigEntry(key="", value="", comment=line.lstrip().lstrip("*").strip())
            )
            last_entry = None
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            entry = ConfigEntry(key=key.strip(), value=value.strip(), comment="")
            section.entries.append(entry)
            last_entry = entry
        # Continuation line for the previous multi-value entry.
        elif last_entry is not None:
            last_entry.value = (last_entry.value + "\n" + line.strip()).strip()
        else:
            section.entries.append(ConfigEntry(key="", value="", comment=line.rstrip()))
    return doc


def serialize_mdf(doc: ConfigDocument) -> str:
    """Render a :class:`ConfigDocument` back to ``.mdf`` text."""
    if not doc.sections:
        return ""
    lines: list[str] = []
    section = doc.sections[0]
    longest_key = max((len(e.key) for e in section.entries if e.key), default=0)
    pad = max(longest_key, 7)

    for entry in section.entries:
        if not entry.key:
            if entry.comment:
                lines.append(f"* {entry.comment}")
            continue
        first, *rest = entry.value.splitlines() or [""]
        lines.append(f"{entry.key.ljust(pad)}= {first}".rstrip())
        for cont in rest:
            lines.append(" " * (pad + 2) + cont.strip())
    return "\n".join(lines).rstrip() + "\n"


__all__ = (
    "ConfigDocument",
    "ConfigEntry",
    "ConfigFormat",
    "ConfigSection",
    "detect_format",
    "parse_mdf",
    "parse_mdu",
    "serialize_mdf",
    "serialize_mdu",
)
