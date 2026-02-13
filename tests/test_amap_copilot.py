import os
import json
import pytest
from src import amap_copilot_flow as ac


def test_amap_call_and_print():
    # This test will call real AMap if AMAP_KEY is set in env; otherwise it will be skipped.
    if not os.getenv('AMAP_KEY'):
        pytest.skip('AMAP_KEY not set; skipping real AMap call')
    res = ac.get_amap_weather('包头市')
    print('AMAP RESPONSE:', json.dumps(res, ensure_ascii=False))
    assert isinstance(res, dict)


def test_copilot_call_and_print():
    # This will attempt to call local copilot endpoint; skip if unreachable
    prompt = '测试：请根据天气生成一句中文穿衣建议。'
    base = os.getenv('LLM_BASE_URL','http://127.0.0.1:4141/')
    # try a quick connectivity check
    try:
        cj = ac.call_copilot(prompt)
    except Exception as e:
        pytest.skip(f'Copilot endpoint unreachable: {e}')
    print('COPILOT RESPONSE:', json.dumps(cj, ensure_ascii=False))
    assert isinstance(cj, dict)
