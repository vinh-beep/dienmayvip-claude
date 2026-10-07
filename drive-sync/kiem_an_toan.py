"""Quét an toàn trước khi đẩy lên Drive. Chỉ dùng thư viện chuẩn.

Thứ tự kiểm: tên thư mục/tệp bị loại trừ → quá lớn / quá cũ / đang ghi dở → nội dung.
Tệp không quét được (PDF, zip, db...) bị CHẶN mặc định (đóng băng an toàn).
Không bao giờ ghi nội dung khớp ra log — chỉ ghi tên luật và số dòng.
"""
from __future__ import annotations

import fnmatch
import os
import re
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------- loại trừ theo tên

EXCLUDE_DIRS = {
    "venv", ".venv", "site-packages", "torch", "node_modules", ".git", "__pycache__",
    ".idea", ".vscode", "_config", "$recycle.bin", "system volume information",
}
EXCLUDE_NAME_GLOBS = [
    "~$*", "*.tmp", "*.pyc", "*.bak", "*.bak-*", "*.log", "thumbs.db", "desktop.ini", ".ds_store",
]
# Tên tệp gợi ý bí mật / giá vốn → chặn (fail-closed, có thể nhầm tệp lành, an toàn hơn lộ)
SECRET_NAME_GLOBS = [
    "*.env", "*.pem", "*.key", "*.pfx", "*.p12", "*.kdbx", "gmail_imap.txt",
    "*token*", "*secret*", "*credential*", "*password*", "*matkhau*", "*mat-khau*", "*mat_khau*", "*tkxt*",
    "*giavon*", "*gia-von*", "*gia_von*", "*gianhap*", "*gia-nhap*", "*gia_nhap*",
]

# ---------------------------------------------------------------- phân loại đuôi tệp

NO_SCAN_OK_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg", ".mp4", ".mp3", ".mov"}
CODE_EXT = {".py", ".ps1", ".bat", ".cmd", ".js", ".ts", ".sql", ".cs", ".sh", ".ini", ".cfg", ".toml",
            ".yml", ".yaml", ".psd1"}
DATA_EXT = {".json", ".csv", ".tsv", ".md", ".txt", ".xml", ".html", ".htm", ".xaml"}
OOXML_EXT = {".xlsx", ".xlsm", ".docx", ".pptx"}

MAX_TEXT_BYTES = 32 * 1024 * 1024
MAX_OOXML_UNCOMPRESSED = 64 * 1024 * 1024

# ---------------------------------------------------------------- luật nội dung

_SECRET_NAME = r"(?:[\w\-]*(?:api[_\-]?key|secret|passw(?:or)?d|token)|m[aậ]t[_\- ]?kh[aẩ]u)"
SECRET_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("khoa-api-google", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("khoa-gemini-moi", re.compile(r"\bAQ\.Ab8[\w\-]{20,}")),
    ("oauth-google", re.compile(r"\bya29\.[\w\-]{20,}")),
    ("khoa-sk", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}")),
    ("khoa-github", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("khoa-slack", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}")),
    ("khoa-rieng", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}")),
    ("gan-mat-khau-token", re.compile(
        _SECRET_NAME + r"[\"']?\s*[:=]\s*[\"']?"
        r"(?!os\.|<|\{|%|\$|self\.|getenv|input|none\b|null\b|true\b|false\b|\"\"|'')"
        r"[^\s\"',;)\]}]{8,}", re.IGNORECASE)),
]
DATA_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("gia-von-ncc", re.compile(
        r"gi[aá][_\- ]?v[oố]n|gi[aá][_\- ]?nh[aậ]p|\bncc[_\- ]?r[eẻ][_\- ]?nh[aấ]t|giasi[_\-]?renhat|"
        r"gi[aá][_\- ]?g[oợ]i[_\- ]?[yý][_\- ]?vip|giagoiy[_\-]?vip|vw[_\-]?bg[_\-]?tonghop|gi[aá][_\- ]?ncc",
        re.IGNORECASE)),
    ("so-dien-thoai-vn", re.compile(r"(?<!\d)(?:\+?84|0)[ .]?[35789](?:[ .]?\d){8}(?!\d)")),
    ("so-tai-khoan", re.compile(
        r"(?:s[oố][_\- ]?(?:tk|t[aà]i[_\- ]?kho[aả]n)|account[_\- ]?(?:no|number))[\"']?\s*[:=]?\s*[\"']?\d{8,16}",
        re.IGNORECASE)),
    ("cccd-cmnd", re.compile(r"(?:cccd|cmnd|c[aă]n c[uư][oớ]c)[^\n]{0,20}\d{9,12}", re.IGNORECASE)),
]


@dataclass(frozen=True)
class Verdict:
    ok: bool
    rule: str = ""
    line: int = 0

    def __str__(self) -> str:
        return "ok" if self.ok else (f"{self.rule}@{self.line}" if self.line else self.rule)


OK = Verdict(True)


def _first_match(text: str, rules) -> Verdict:
    for name, rx in rules:
        m = rx.search(text)
        if m:
            return Verdict(False, name, text.count("\n", 0, m.start()) + 1)
    return OK


def quet_van_ban(text: str, *, la_ma_nguon: bool) -> Verdict:
    text = unicodedata.normalize("NFC", text)
    v = _first_match(text, SECRET_RULES)
    if not v.ok or la_ma_nguon:
        return v
    return _first_match(text, DATA_RULES)


def _doc_ooxml(path: Path) -> str | Verdict:
    try:
        with zipfile.ZipFile(path) as z:
            total = sum(i.file_size for i in z.infolist())
            if total > MAX_OOXML_UNCOMPRESSED:
                return Verdict(False, "ooxml-qua-lon")
            parts = []
            for info in z.infolist():
                n = info.filename.lower()
                if n.endswith(".xml") and n.startswith(("xl/", "word/", "ppt/")):
                    raw = z.read(info).decode("utf-8", errors="replace")
                    parts.append(re.sub(r"<[^>]+>", " ", raw))
            return "\n".join(parts)
    except (zipfile.BadZipFile, OSError):
        return Verdict(False, "khong-doc-duoc-ooxml")


def kiem_noi_dung(path: Path, size: int, *, cho_phep_khong_quet: frozenset[str] = frozenset()) -> Verdict:
    ext = path.suffix.lower()
    if ext in NO_SCAN_OK_EXT or ext in cho_phep_khong_quet:
        return OK
    if ext in OOXML_EXT:
        got = _doc_ooxml(path)
        return got if isinstance(got, Verdict) else quet_van_ban(got, la_ma_nguon=False)
    if ext in CODE_EXT or ext in DATA_EXT:
        if size > MAX_TEXT_BYTES:
            return Verdict(False, "qua-lon-de-quet")
        try:
            text = path.read_bytes().decode("utf-8-sig", errors="replace")
        except OSError:
            return Verdict(False, "khong-doc-duoc")
        return quet_van_ban(text, la_ma_nguon=ext in CODE_EXT)
    return Verdict(False, "loai-tep-khong-quet-duoc")


def ten_bi_loai_tru(name: str) -> bool:
    low = name.lower()
    if low.startswith(("#", ";")):  # rclone --files-from coi là dòng chú thích
        return True
    return any(fnmatch.fnmatchcase(low, g) for g in EXCLUDE_NAME_GLOBS)


def ten_bi_chan(name: str) -> bool:
    low = name.lower()
    return any(fnmatch.fnmatchcase(low, g) for g in SECRET_NAME_GLOBS)


def _is_link(p: str) -> bool:
    isjunction = getattr(os.path, "isjunction", lambda _x: False)
    return os.path.islink(p) or isjunction(p)


@dataclass
class ScanResult:
    allowed: list[str] = field(default_factory=list)       # đường dẫn tương đối, dấu /
    allowed_bytes: int = 0
    blocked: dict[str, str] = field(default_factory=dict)  # đường dẫn → luật@dòng
    skipped: Counter = field(default_factory=Counter)
    seen: int = 0


def quet_thu_muc(
    root: Path,
    *,
    max_size: int,
    max_age_s: float | None,
    min_age_s: float,
    now: float,
    cho_phep_khong_quet: frozenset[str] = frozenset(),
) -> ScanResult:
    res = ScanResult()
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        kept = []
        for d in dirnames:
            full = os.path.join(dirpath, d)
            if d.lower() in EXCLUDE_DIRS:
                res.skipped["thu-muc-loai-tru"] += 1
            elif _is_link(full):
                res.skipped["lien-ket-thu-muc"] += 1
            else:
                kept.append(d)
        dirnames[:] = kept
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            res.seen += 1
            rel = Path(os.path.relpath(full, root)).as_posix()
            if ten_bi_loai_tru(fn):
                res.skipped["ten-loai-tru"] += 1
                continue
            if _is_link(full):
                res.skipped["lien-ket-tep"] += 1
                continue
            if ten_bi_chan(fn):
                res.blocked[rel] = "ten-nhay-cam"
                continue
            try:
                st = os.stat(full)
            except OSError:
                res.skipped["khong-doc-duoc"] += 1
                continue
            if st.st_size > max_size:
                res.skipped["qua-lon"] += 1
                continue
            age = now - st.st_mtime
            if max_age_s is not None and age > max_age_s:
                res.skipped["qua-cu"] += 1
                continue
            if age < min_age_s:
                res.skipped["dang-ghi-do"] += 1
                continue
            verdict = kiem_noi_dung(Path(full), st.st_size, cho_phep_khong_quet=cho_phep_khong_quet)
            if verdict.ok:
                res.allowed.append(rel)
                res.allowed_bytes += st.st_size
            else:
                res.blocked[rel] = str(verdict)
    res.allowed.sort()
    return res
