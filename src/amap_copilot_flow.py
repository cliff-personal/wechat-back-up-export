#!/usr/bin/env python3
import os
import json
import urllib.request
import urllib.parse

AMAP_KEY = os.getenv('AMAP_KEY','')
LLM_BASE = os.getenv('LLM_BASE_URL','http://127.0.0.1:4141/v1')
LLM_KEY = os.getenv('LLM_API_KEY','')


def get_amap_weather(city: str) -> dict:
    """Call AMap weatherInfo (extensions=base) and return parsed dict."""
    if not AMAP_KEY:
        raise RuntimeError('AMAP_KEY not set')
    short = city.replace('市','')
    city_q = urllib.parse.quote(short)
    url = f"https://restapi.amap.com/v3/weather/weatherInfo?key={AMAP_KEY}&city={city_q}&extensions=base"
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read().decode('utf-8'))


def call_copilot(prompt: str) -> dict:
    """Call an OpenAI-compatible chat completion endpoint (local copilot-api) and return parsed JSON."""
    payload = {
        'model': os.getenv('LLM_MODEL','gpt-5-mini'),
        'messages': [{'role':'user','content': prompt}],
        'max_tokens': 200,
    }
    data = json.dumps(payload).encode('utf-8')
    url = LLM_BASE.rstrip('/') + '/chat/completions'
    headers = {'Content-Type':'application/json'}
    if LLM_KEY:
        headers['Authorization'] = f'Bearer {LLM_KEY}'
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode('utf-8'))


if __name__ == '__main__':
    city = os.getenv('CITY','包头市')
    print('Calling AMap for', city)
    aj = get_amap_weather(city)
    print('AMap raw response:')
    print(json.dumps(aj, ensure_ascii=False, indent=2))

    # build simple prompt from AMap raw
    prompt = f"请根据以下高德实时天气信息给出简短穿衣建议（中文，1段话）：\n{json.dumps(aj, ensure_ascii=False)}"
    print('Calling Copilot at', LLM_BASE)
    try:
        cj = call_copilot(prompt)
        print('Copilot response:')
        print(json.dumps(cj, ensure_ascii=False, indent=2))
    except Exception as e:
        print('Copilot call failed:', e)
