import json
import urllib
import pytest

from types import SimpleNamespace

import src.dingtalk_daily as dd

class DummyResp:
    def __init__(self, data: bytes):
        self._data = data
    def read(self):
        return self._data
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False


def test_fetch_weather_amap_success(monkeypatch, tmp_path, monkeypatchcontext=None):
    # simulate AMap response (lives)
    amap_json = {
        "status": "1",
        "lives": [{
            "province": "内蒙古",
            "city": "包头",
            "adcode": "150200",
            "weather": "多云",
            "temperature": "9",
            "winddirection": "西北",
            "windpower": "3",
            "humidity": "62",
        }]
    }
    def fake_urlopen(url, timeout=...):
        return DummyResp(json.dumps(amap_json).encode("utf-8"))
    monkeypatch.setattr(dd.urllib.request, 'urlopen', fake_urlopen)
    monkeypatch.setenv('AMAP_KEY', 'dummy-key')
    res = dd.fetch_weather('包头市')
    print('fetch_weather result:', res)
    assert '包头' in res
    assert '°C' in res or '风力' in res


def test_fetch_weather_wttr_fallback(monkeypatch):
    # Simulate AMap failure then wttr success
    def fake_urlopen_amap(url, timeout=...):
        raise Exception('amap unreachable')
    called = {'wttr': False}
    def fake_urlopen_wttr(url, timeout=...):
        if 'wttr.in' in url:
            called['wttr'] = True
            return DummyResp(b"\xe5\x8c\x85\xe5\xa4\xb4:+\xe2\x9b\xa5+9\xc2\xb0C+62%+\xe2\x86\x9216km/h")
        raise Exception('other')
    # first call (AMap) fails
    def dispatch(url, timeout=...):
        if 'restapi.amap.com' in url:
            return fake_urlopen_amap(url, timeout)
        return fake_urlopen_wttr(url, timeout)
    monkeypatch.setattr(dd.urllib.request, 'urlopen', dispatch)
    if 'AMAP_KEY' in dd.os.environ:
        monkeypatch.delenv('AMAP_KEY')
    res = dd.fetch_weather('包头市')
    assert called['wttr']
    assert '包头' in res or 'Baotou' in res
