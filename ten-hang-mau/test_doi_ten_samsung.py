# Chay: python -m pytest ten-hang-mau  (hoac python test_doi_ten_samsung.py)
from doi_ten_samsung import tach_ma, tach_ten, lap


def _hang(ten, mhcode, sku='', ton=1, mhid='x'):
    return {'Hang': 'SAMSUNG', 'Ton': ton, 'MHTEN': ten, 'MHCODE': mhcode, 'SKU': sku, 'MHID': mhid}


def test_tach_ma():
    assert tach_ma('SM-A076BLVBXXV') == ('SM-A076BLVBXXV', 'LV')
    assert tach_ma('x SM-A185GZKKXXV') == ('SM-A185GZKKXXV', 'ZK')
    assert tach_ma('SM-A085FDBDXXV') == ('SM-A085FDBDXXV', 'DB')
    assert tach_ma('SM-A075F') == ('SM-A075F', None)
    assert tach_ma('8931000111118') == (None, None)


def test_vi_du_chu_shop():
    ra = lap([_hang('ĐTDĐ SAMSUNG A07 5G 4GB 128GB Tím Violet SM-A076BLVBXXV', 'SAMSUNG A07 5G 4GB 128GB Tím')], [])
    assert ra['ngay'][0]['TEN_MOI'] == 'ĐTDĐ SAMSUNG A07 5G 4GB 128GB Tím Light Violet SM-A076BLVBXXV'


def test_ten_don_nhieu_mau_lay_theo_ma_hang():
    ban_do = [{'MHID': 'm1', 'SKU': 'SM-A077FZGDXXV'}]
    ra = lap([_hang('ĐTDĐ SAMSUNG A07S 4GB 64GB TÍM NHẠT ĐEN XANH LÁ', 'SAMSUNG A07S 4GB 64GB XANH LÁ', mhid='m1')], ban_do)
    assert ra['xac_nhan'][0]['TEN_MOI'] == 'ĐTDĐ SAMSUNG A07S 4GB 64GB XANH LÁ Green SM-A077FZGDXXV'


def test_giu_ten_tiep_thi_va_thieu_ma():
    ra = lap([_hang('ĐTDĐ SAMSUNG S24 FE 8GB 128GB Đen Graphite SM-S721BZKBXXV', 'SAMSUNG S24 FE 8GB 128GB Đen Graphite'),
              _hang('ĐTDĐ SAMSUNG A17 4GB 128GB XÁM SM-A175F', 'SAMSUNG A17 4GB 128GB XÁM'),
              _hang('ĐTDĐ SAMSUNG A17 4GB 128GB XÁM', 'x', ton=0)], [])
    assert ra['ngay'][0]['TEN_MOI'] == 'ĐTDĐ SAMSUNG S24 FE 8GB 128GB Đen Graphite Black SM-S721BZKBXXV'
    assert len(ra['thieu_ma']) == 1   # dong het ton bi bo qua


def test_bay_5g_khong_lam_lech_ram_rom():
    # Bay da gap 23/10 (phien PC): '5G 4GB' bi doc nham la RAM 5 / ROM 4. O day lay so bo nho CUOI cung.
    dau, mau = tach_ten('ĐTDĐ SAMSUNG A06 5G 4GB 128GB Xanh Kem SM-A066BLGGXXV')
    assert dau[-3:] == ['5G', '4GB', '128GB'] and mau == ['Xanh', 'Kem']
    dau, mau = tach_ten('ĐTDĐ SAMSUNG A17 5G 4G 128G XÁM KHÓI')
    assert dau[-1] == '128G' and mau == ['XÁM', 'KHÓI']


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
    print('OK')
