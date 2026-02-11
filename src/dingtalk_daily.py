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
    # Ensure the prompt includes the city explicitly and asks the LLM to use that city name in the output.
    prompt = (
        "你是穿衣搭配助手。根据下面的天气信息给出详细、可执行的穿衣建议，务必在回答开头标注城市名（例如：包头: ...）。"
        "建议应包含：外套/上衣/裤装/鞋子/配件，并对风力、湿度、降水和早晚温差给出具体的调整建议。\n"
        "要求：用中文写成 3–6 句连贯短文，不要使用列表，尽量给出场景（通勤/户外/运动）的小建议，输出示例风格见下：\n"
        "包头: ⛅️ +9°C 62% →16km/h 穿衣建议：具体内容...\n"
        f"天气：{weather_line}\n城市：{urllib.parse.unquote_plus(urllib.parse.quote(weather_line.split(':')[0]))}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是严谨且实用的生活助理，给出具体可执行的穿衣搭配建议"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 500,
    }
    url = base_url.rstrip("/") + "/chat/completions"
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        resp = json.loads(r.read().decode("utf-8"))
    # support different response formats: choices[0].message.content or choices[0].text
    content = None
    try:
        content = resp["choices"][0]["message"]["content"].strip()
    except Exception:
        try:
            content = resp["choices"][0]["text"].strip()
        except Exception:
            content = "注意根据体感温度与风力增减衣物。"
    # Ensure city label present — if not, prepend city extracted from weather_line
    if not content.startswith(urllib.parse.unquote_plus(weather_line.split(':')[0])):
        city_label = weather_line.split(':')[0]
        content = f"{city_label} {content}"
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
    ap.add_argument("--llm-model", default="github-copilot/gpt-5.2", help="Model id for LLM advice (optional)")
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
    # append send record to log for audit
    try:
        logdir = os.path.join(os.path.dirname(__file__), "..", "logs")
        os.makedirs(logdir, exist_ok=True)
        logpath = os.path.join(logdir, "dingtalk_daily.log")
        with open(logpath, "a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"[{datetime.now().isoformat()}] {text}\n\n")
    except Exception:
        pass
    print("Sent:", text)


if __name__ == "__main__":
    main()
