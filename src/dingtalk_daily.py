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


def send_dingtalk(webhook: str, text: str) -> None:
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
    ap.add_argument("--city", required=True, help="City name, e.g. Shanghai")
    args = ap.parse_args()

    weather = fetch_weather(args.city)
    temp_c = parse_temp_c(weather)
    advice = outfit_advice(temp_c)

    text = f"今日天气：{weather}\n{advice}"
    send_dingtalk(args.webhook, text)
    print("Sent:", text)


if __name__ == "__main__":
    main()
