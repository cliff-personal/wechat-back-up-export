#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Send daily weather + outfit suggestions to DingTalk via robot webhook.

Usage:
  python src/dingtalk_daily.py \
    --webhook "https://oapi.dingtalk.com/robot/send?access_token=..." \
    --city "Shanghai"
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


def fetch_weather(city: str) -> str:
    # wttr.in compact format
    q = urllib.parse.quote(city)
    url = f"https://wttr.in/{q}?format=%l:+%c+%t+%h+%w"
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.read().decode("utf-8").strip()


def parse_temp_c(weather_line: str) -> float:
    # extract like +8°C or -2°C
    import re
    m = re.search(r"([+-]?\d+)°C", weather_line)
    if not m:
        return None
    return float(m.group(1))


def outfit_advice(temp_c: float) -> str:
    if temp_c is None:
        return "穿衣建议：注意根据体感温度与风力增减衣物。"
    if temp_c <= 0:
        return "穿衣建议：羽绒服/厚外套 + 保暖内衣 + 手套/围巾。"
    if temp_c <= 8:
        return "穿衣建议：厚外套/羊毛大衣 + 毛衣。"
    if temp_c <= 15:
        return "穿衣建议：夹克/风衣 + 长袖。"
    if temp_c <= 22:
        return "穿衣建议：薄外套/卫衣 + 长袖或薄毛衣。"
    if temp_c <= 28:
        return "穿衣建议：短袖为主，早晚可备薄外套。"
    return "穿衣建议：短袖 + 注意防晒与补水。"


def llm_outfit_advice(weather_line: str, base_url: str, model: str, api_key: str | None) -> str:
    # OpenAI-compatible chat.completions
    import json
    prompt = (
        "你是穿衣搭配助手。根据天气信息给出具体、可执行的穿衣建议。"
        "建议应包含外套/上衣/裤装/鞋子/配件，并考虑风力与湿度。"
        "输出一段中文短文，不要列表。\n"
        f"天气：{weather_line}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是严谨的生活助理"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": 200,
    }
    url = base_url.rstrip("/") + "/chat/completions"
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        resp = json.loads(r.read().decode("utf-8"))
    content = resp["choices"][0]["message"]["content"].strip()
    return f"穿衣建议：{content}"


def sign_webhook(webhook: str, secret: str) -> str:
    import base64
    import hashlib
    import hmac
    import time

    ts = str(int(time.time() * 1000))
    string_to_sign = f"{ts}\n{secret}".encode("utf-8")
    h = hmac.new(secret.encode("utf-8"), string_to_sign, hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(h))

    sep = "&" if "?" in webhook else "?"
    return f"{webhook}{sep}timestamp={ts}&sign={sign}"


def send_dingtalk(webhook: str, text: str, secret: str | None = None) -> None:
    if secret:
        webhook = sign_webhook(webhook, secret)
    payload = {
        "msgtype": "text",
        "text": {"content": text}
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        resp = r.read().decode("utf-8")
    if '"errcode":0' not in resp:
        print("DingTalk response:", resp)
        sys.exit(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--webhook", required=True, help="DingTalk robot webhook URL")
    ap.add_argument("--secret", default="", help="DingTalk robot secret for Additional Signature (optional)")
    ap.add_argument("--city", required=True, help="City name, e.g. Shanghai")
    ap.add_argument("--llm-base-url", default="http://127.0.0.1:4141/v1", help="OpenAI-compatible base URL (copilot-api default)")
    ap.add_argument("--llm-model", default="github-copilot/gpt-5-mini", help="Model id for LLM advice (optional)")
    ap.add_argument("--llm-api-key", default=os.getenv("OPENAI_API_KEY", ""), help="API key (optional)")
    args = ap.parse_args()

    weather = fetch_weather(args.city)
    temp_c = parse_temp_c(weather)

    if args.llm_model:
        try:
            advice = llm_outfit_advice(weather, args.llm_base_url, args.llm_model, args.llm_api_key or None)
        except Exception:
            advice = outfit_advice(temp_c)
    else:
        advice = outfit_advice(temp_c)

    text = f"今日天气：{weather}\n{advice}"
    send_dingtalk(args.webhook, text, secret=args.secret or None)
    print("Sent:", text)


if __name__ == "__main__":
    main()
