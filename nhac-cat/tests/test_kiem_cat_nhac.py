import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import kiem_cat_nhac as kn  # noqa: E402


def wav(path: Path, seconds: float, rate: int = 8000) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return path


def test_do_dai_wav_dung(tmp_path):
    assert kn.do_dai_wav(wav(tmp_path / "a.wav", 60)) == pytest.approx(60, abs=0.01)
    (tmp_path / "x.wav").write_bytes(b"khong phai wav")
    assert kn.do_dai_wav(tmp_path / "x.wav") is None


def test_ke_hoach_dat(tmp_path):
    f = wav(tmp_path / "suno" / "a04.wav", 60) if (tmp_path / "suno").mkdir() is None else None
    m = kn.kiem_mot({"sku": "A04", "tep": str(f), "doan_mo_giay": 2.5, "nhac_tu": 30, "tong_giay": 18}, goc_ban_quyen=[])
    assert m["dat"], m["loi"]
    assert m["cao_trao_giay"] == 17.85 and m["nhac_den"] == 47.85 and m["ban_quyen_ro"]


def test_cat_vuot_do_dai_bai(tmp_path):
    f = wav(tmp_path / "suno-b.wav", 40)
    m = kn.kiem_mot({"sku": "B", "tep": str(f), "doan_mo_giay": 1, "nhac_tu": 30, "tong_giay": 18}, goc_ban_quyen=[])
    assert not m["dat"] and any("vượt độ dài" in l for l in m["loi"])


@pytest.mark.parametrize("muc,chua", [
    ({"doan_mo_giay": 4, "nhac_tu": 0, "tong_giay": 18}, "đoạn mở"),
    ({"doan_mo_giay": 1, "nhac_tu": 0, "tong_giay": 30}, "15–20 s"),
    ({"doan_mo_giay": 1, "nhac_tu": -1, "tong_giay": 18}, "nhac_tu âm"),
    ({"doan_mo_giay": "x", "nhac_tu": 0, "tong_giay": 18}, "không hợp lệ"),
])
def test_luat_tung_truong(tmp_path, muc, chua):
    f = wav(tmp_path / "suno-c.wav", 60)
    m = kn.kiem_mot({"sku": "C", "tep": str(f), **muc}, goc_ban_quyen=[])
    assert not m["dat"] and any(chua in l for l in m["loi"])


def test_ban_quyen_theo_thu_muc_hoac_ten(tmp_path):
    g = tmp_path / "MP3"
    g.mkdir()
    ok = wav(g / "bai.wav", 60)
    la = wav(tmp_path / "khac" / "bai.wav", 60) if (tmp_path / "khac").mkdir() is None else None
    assert kn.ban_quyen_ro(ok, [g]) and not kn.ban_quyen_ro(la, [g])
    m = kn.kiem_mot({"sku": "D", "tep": str(la), "doan_mo_giay": 1, "nhac_tu": 0, "tong_giay": 18}, goc_ban_quyen=[g])
    assert any("bản quyền" in l for l in m["loi"])


def test_mot_bai_cho_nhieu_sp_bi_bao(tmp_path):
    f = wav(tmp_path / "suno-e.wav", 60)
    kq = kn.kiem([{"sku": "E1", "tep": str(f), "doan_mo_giay": 1, "nhac_tu": 0, "tong_giay": 18},
                  {"sku": "E2", "tep": str(f), "doan_mo_giay": 1, "nhac_tu": 0, "tong_giay": 18}], goc_ban_quyen=[])
    assert kq["hong"] == 2 and all("nhiều SP" in l for m in kq["muc"] for l in m["loi"])


def test_tep_thieu_hoac_khong_phai_nhac(tmp_path):
    m = kn.kiem_mot({"sku": "F", "tep": str(tmp_path / "suno-khong-co.mp3"), "doan_mo_giay": 1, "nhac_tu": 0, "tong_giay": 18},
                    goc_ban_quyen=[], do_dai_fn=lambda p: None)
    assert any("độ dài" in l for l in m["loi"])
    m2 = kn.kiem_mot({"sku": "G", "tep": str(tmp_path / "suno.txt"), "doan_mo_giay": 1, "nhac_tu": 0, "tong_giay": 18}, goc_ban_quyen=[])
    assert any("đuôi tệp" in l for l in m2["loi"])


def test_ffprobe_duoc_goi_cho_mp3(tmp_path):
    calls = []
    f = tmp_path / "x.mp3"
    f.write_bytes(b"ID3")
    assert kn.do_dai(f, ffprobe=lambda p: calls.append(p) or 12.0) == 12.0
    assert calls == [f]
    assert kn.do_dai(tmp_path / "khong-co.mp3", ffprobe=lambda p: 1.0) is None


def test_main_va_cp1252(tmp_path):
    f = wav(tmp_path / "suno-h.wav", 60)
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps([{"sku": "H", "tep": str(f), "doan_mo_giay": 2, "nhac_tu": 10, "tong_giay": 16}]), encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    proc = subprocess.run([sys.executable, str(Path(kn.__file__)), "--ke-hoach", str(plan), "--ra", str(tmp_path / "ra")],
                          capture_output=True, env=env, timeout=60)
    assert b"Traceback" not in proc.stderr and proc.returncode == 0, proc.stderr
    assert json.loads((tmp_path / "ra" / "kiem-cat-nhac.json").read_text(encoding="utf-8"))["dat"] == 1
    assert kn.main(["--ke-hoach", str(tmp_path / "khong.json"), "--ra", str(tmp_path / "r2")]) == 1
