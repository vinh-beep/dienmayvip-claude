"""Tổng kết link video YouTube / TikTok + mở tệp trong thư mục. Logic thuần, chỉ thư viện chuẩn, 0 token.

Dữ liệu vào (JSON hoặc CSV) mỗi video gồm: ma, ten, url, tep (đường dẫn tệp .mp4 trên PC),
trang_thai (cho-dang | dang-dang | da-dang | loi), tien_do (0-100), nen_tang (tùy chọn, tự nhận từ link).
Không chứa giá vốn / NCC / SĐT: chỉ link công khai và đường dẫn tệp.
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
import webbrowser
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

TRANG_THAI = ("cho-dang", "dang-dang", "da-dang", "loi")
NHAN_TRANG_THAI = {"cho-dang": "Chờ đăng", "dang-dang": "Đang đăng", "da-dang": "Đã đăng", "loi": "Lỗi"}
NEN_TANG = {"youtube": "YouTube", "tiktok": "TikTok", "khac": "Khác"}


@dataclass(frozen=True)
class Video:
    ma: str
    ten: str
    nen_tang: str          # youtube | tiktok | khac
    url: str               # rỗng nếu chưa có link
    tep: str               # rỗng nếu chưa có tệp
    trang_thai: str
    tien_do: int           # 0..100

    @property
    def nhan_nen_tang(self) -> str:
        return NEN_TANG.get(self.nen_tang, "Khác")

    @property
    def nhan_trang_thai(self) -> str:
        return NHAN_TRANG_THAI.get(self.trang_thai, self.trang_thai)


# ---------------------------------------------------------------- chuẩn hóa dữ liệu


def detect_platform(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com"):
        return "youtube"
    if host == "tiktok.com" or host.endswith(".tiktok.com"):
        return "tiktok"
    return "khac"


def clean_url(url: Any) -> str:
    """Chỉ nhận http/https (không bao giờ mở javascript:, file:, ...)."""
    text = str(url or "").strip()
    parsed = urlparse(text)
    return text if parsed.scheme in ("http", "https") and parsed.netloc else ""


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip().rstrip("%").replace(",", ".")))
    except (TypeError, ValueError):
        return default


def normalize(rec: dict[str, Any]) -> Video:
    url = clean_url(rec.get("url") or rec.get("link"))
    nen = str(rec.get("nen_tang") or "").strip().lower()
    if nen not in NEN_TANG:
        nen = detect_platform(url) if url else "khac"
    tien_do = max(0, min(100, _to_int(rec.get("tien_do"))))
    trang_thai = str(rec.get("trang_thai") or "").strip().lower()
    if trang_thai not in TRANG_THAI:
        trang_thai = "da-dang" if url and tien_do >= 100 else ("dang-dang" if tien_do > 0 else "cho-dang")
    if trang_thai == "da-dang":
        tien_do = 100
    return Video(
        ma=str(rec.get("ma") or "").strip(),
        ten=str(rec.get("ten") or "").strip(),
        nen_tang=nen,
        url=url,
        tep=str(rec.get("tep") or "").strip(),
        trang_thai=trang_thai,
        tien_do=tien_do,
    )


def load_videos(path: Path) -> list[Video]:
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".csv":
        records = list(csv.DictReader(text.splitlines()))
    else:
        data = json.loads(text)
        records = data["videos"] if isinstance(data, dict) else data
    return [normalize(r) for r in records]


# ---------------------------------------------------------------- tổng kết


def tong_ket(videos: list[Video], *, kiem_tep: bool = False) -> dict[str, Any]:
    tong = len(videos)
    da_dang = sum(v.trang_thai == "da-dang" for v in videos)
    theo_nen: dict[str, dict[str, int]] = {}
    for v in videos:
        d = theo_nen.setdefault(v.nen_tang, {"tong": 0, "da_dang": 0, "loi": 0, "thieu_link": 0})
        d["tong"] += 1
        d["da_dang"] += v.trang_thai == "da-dang"
        d["loi"] += v.trang_thai == "loi"
        d["thieu_link"] += not v.url
    out: dict[str, Any] = {
        "tong": tong,
        "da_dang": da_dang,
        "ti_le_da_dang": round(100 * da_dang / tong) if tong else 0,
        "tien_do_trung_binh": round(sum(v.tien_do for v in videos) / tong) if tong else 0,
        "theo_trang_thai": dict(Counter(v.trang_thai for v in videos)),
        "theo_nen_tang": theo_nen,
        "thieu_link": [v.ma for v in videos if not v.url],
        "thieu_tep": [v.ma for v in videos if not v.tep],
    }
    if kiem_tep:
        out["tep_khong_con"] = [v.ma for v in videos if v.tep and not os.path.exists(v.tep)]
    return out


def tom_tat_markdown(videos: list[Video]) -> str:
    s = tong_ket(videos)
    lines = [f"# Tổng kết video — đã đăng {s['da_dang']}/{s['tong']} ({s['ti_le_da_dang']}%)", ""]
    for nen, d in sorted(s["theo_nen_tang"].items()):
        lines.append(f"- **{NEN_TANG.get(nen, nen)}**: {d['da_dang']}/{d['tong']} đã đăng"
                     + (f", {d['loi']} lỗi" if d["loi"] else "") + (f", {d['thieu_link']} chưa có link" if d["thieu_link"] else ""))
    for nen in ("youtube", "tiktok", "khac"):
        items = [v for v in videos if v.nen_tang == nen and v.url]
        if not items:
            continue
        lines += ["", f"## {NEN_TANG[nen]}"]
        lines += [f"- {v.ma or '—'} · {v.ten or '(chưa đặt tên)'} · {v.nhan_trang_thai}: {v.url}" for v in items]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- mở tệp trong thư mục


def _hop_le(path: str) -> bool:
    return bool(path) and not re.search(r'["\r\n\x00]', path)


def open_in_folder(
    path: str,
    *,
    platform: str | None = None,
    runner: Callable[..., Any] = subprocess.Popen,
    exists: Callable[[str], bool] = os.path.exists,
    isdir: Callable[[str], bool] = os.path.isdir,
) -> tuple[bool, str]:
    """Hiện tệp trong thư mục chứa nó (chọn sẵn tệp). Không bao giờ chạy tệp. Trả (ok, thông báo)."""
    if not _hop_le(path):
        return False, "Đường dẫn tệp trống hoặc có ký tự không hợp lệ"
    platform = platform or sys.platform
    folder = os.path.dirname(path) or "."
    if exists(path):
        if platform.startswith("win"):
            runner(f'explorer /select,"{os.path.normpath(path)}"')  # chuỗi nguyên: explorer đòi đúng dạng này
        elif platform == "darwin":
            runner(["open", "-R", path])
        else:
            runner(["xdg-open", folder])
        return True, "Đã mở thư mục và chọn sẵn tệp"
    if isdir(folder):
        if platform.startswith("win"):
            runner(f'explorer "{os.path.normpath(folder)}"')
        elif platform == "darwin":
            runner(["open", folder])
        else:
            runner(["xdg-open", folder])
        return True, "Tệp không còn ở đó, đã mở thư mục chứa nó"
    return False, "Không thấy tệp lẫn thư mục (ổ đĩa hoặc thư mục đã đổi)"


def open_link(url: str, *, opener: Callable[[str], Any] = webbrowser.open) -> tuple[bool, str]:
    url = clean_url(url)
    if not url:
        return False, "Video này chưa có link hợp lệ"
    opener(url)
    return True, "Đã mở link trên trình duyệt"


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # console Windows cp1252 không in được tiếng Việt
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("Dùng: python video_links.py <so_video.json|csv>")
        return 1
    print(tom_tat_markdown(load_videos(Path(args[0]))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
