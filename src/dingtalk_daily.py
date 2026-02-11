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
    """
    Robust weather fetcher:
    1) Try wttr.in with multiple city candidates (Chinese/short name/English), several formats.
    2) If wttr.in fails or returns empty, try Open-Meteo geocoding + forecast API to build a compact one-line summary.
    Guarantees: returns a non-empty human-readable short line like "包头: ⛅️ +9°C 62% →16km/h" or empty string if completely fails.
    """
    import time
    import re

    # prepare candidate names
    candidates = [city, city.replace("市", ""), city.split()[-1]]
    en_map = {"包头": "Baotou", "上海": "Shanghai", "北京": "Beijing"}
    short = city.replace("市", "")
    if short in en_map:
        candidates.append(en_map[short])

    tried = set()
    # first: try wttr.in with multiple formats
    for name in candidates:
        if not name or name in tried:
            continue
        tried.add(name)
        q = urllib.parse.quote(name)
        urls = [
            f"https://wttr.in/{q}?format=%l:+%c+%t+%h+%w",
            f"https://wttr.in/{q}?format=%l:+%t+%w",
            f"https://wttr.in/{q}?format=%l:+%c+%t",
        ]
        for url in urls:
            try:
                with urllib.request.urlopen(url, timeout=8) as r:
                    txt = r.read().decode("utf-8").strip()
                    if txt and not txt.startswith("Unknown location"):
                        # normalize multiple spaces and commas
                        txt = re.sub(r"\s+", " ", txt)
                        return txt
            except Exception:
                time.sleep(0.5)

    # fallback: use Open-Meteo geocoding + forecast
    try:
        short_q = urllib.parse.quote(short)
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={short_q}&count=1"
        with urllib.request.urlopen(geo_url, timeout=8) as r:
            gj = json.loads(r.read().decode("utf-8"))
        if gj.get("results"):
            res = gj["results"][0]
            lat = res.get("latitude")
            lon = res.get("longitude")
            name_ret = res.get("name") or short
            # request current weather from Open-Meteo
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&hourly=relativehumidity_2m"
            with urllib.request.urlopen(weather_url, timeout=8) as r:
                wj = json.loads(r.read().decode("utf-8"))
            cur = wj.get("current_weather")
            humidity = None
            try:
                # hourly humidity requires matching time index; as a fallback leave blank
                hourly = wj.get("hourly", {})
                if hourly and "relativehumidity_2m" in hourly and "time" in hourly and cur:
                    # find index for current time
                    t = cur.get("time")
                    idx = hourly["time"].index(t) if t in hourly["time"] else None
                    if idx is not None:
                        humidity = hourly["relativehumidity_2m"][idx]
            except Exception:
                humidity = None
            temp = cur.get("temperature") if cur else None
            windspeed = cur.get("windspeed") if cur else None
            symbol = ""
            if temp is not None:
                if temp <= 0:
                    symbol = "❄️"
                elif temp < 10:
                    symbol = "🌥"
                elif temp < 20:
                    symbol = "⛅️"
                else:
                    symbol = "☀️"
            parts = [f"{name_ret}:", symbol]
            if temp is not None:
                parts.append(f"{int(round(temp))}°C")
            if humidity is not None:
                parts.append(f"{int(round(humidity))}%")
            if windspeed is not None:
                parts.append(f"→{int(round(windspeed))}km/h")
            line = " ".join([p for p in parts if p])
            if line:
                return line
    except Exception:
        pass

    # last resort: return empty string
    return ""


def parse_temp_c(weather_line: str) -> float:
    # extract like +8°C or -2°C
    import re
    m = re.search(r"([+-]?\d+)°C", weather_line)
    if not m:
        return None
    return float(m.group(1))

def llm_outfit_advice(weather_line: str, base_url: str, model: str, api_key: str | None) -> str:
    # Add retry and logging to better surface model responses; raise on unacceptable content
    import time

    # OpenAI-compatible chat.completions
    import json
    # Ensure the prompt includes the city explicitly and asks the LLM to use that city name in the output.
    prompt = (
        "你是穿衣搭配助手。根据下面的天气信息给出详细、可执行的穿衣建议，务必在回答开头标注城市名（例如：包头: ...）。"
        "建议应包含：外套/上衣/裤装/鞋子/配件，并对风力、湿度、降水和早晚温差给出具体的调整建议。\n"
        "要求：用中文写成 3–6 句连贯短文，不要使用列表，尽量给出场景（通勤/户外/运动）的小建议。请严格模仿下列输出示例的格式与详尽程度（包括城市标签、天气符号、温度、湿度、风速及详细搭配建议）：\n"
        "示例：包头: ⛅️ +9°C 62% →16km/h 穿衣建议：包头今天多云，气温9°C偏凉，湿度62%体感会有点冷，且有约16km/h的风，建议采用“防风+可增减”的穿法：外套选一件轻薄但防风的短款羽绒或带里衬的风衣外套，领口能扣紧更舒适；上衣内搭长袖打底（薄针织或保暖内衣）再加一件针织衫/卫衣，进室内方便脱一层避免闷；裤装穿厚一点的牛仔裤或加绒休闲裤，怕冷的话可加薄秋裤；鞋子选包脚的运动鞋或短靴，最好配中厚袜以防脚踝受风；配件带一条围巾或脖套来挡风，早晚可加帽子，湿度不算低可备一把折叠伞以防临时飘雨。\n"
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

    # try up to 2 retries if response is empty or too short
    last_resp = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                last_resp = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last_resp = {"error": str(e)}
        # extract content if possible
        content = None
        try:
            content = last_resp["choices"][0]["message"]["content"].strip()
        except Exception:
            try:
                content = last_resp["choices"][0]["text"].strip()
            except Exception:
                content = None
        # log raw response for debugging
        try:
            logdir = os.path.join(os.path.dirname(__file__), "..", "logs")
            os.makedirs(logdir, exist_ok=True)
            with open(os.path.join(logdir, "llm_responses.log"), "a", encoding="utf-8") as lf:
                from datetime import datetime
                lf.write(f"[{datetime.now().isoformat()}] attempt={attempt} model={model} resp={json.dumps(last_resp, ensure_ascii=False)}\n")
        except Exception:
            pass
        # accept if content is reasonably long
        if content and len(content) >= 40:
            break
        # otherwise retry (with small delay)
        time.sleep(0.5)
    # If still empty, raise an error so caller can handle/report it
    if not content:
        raise RuntimeError(f"LLM returned empty or invalid response: {json.dumps(last_resp, ensure_ascii=False)}")
    # Ensure city label present — if not, prepend city extracted from weather_line
    city_label = urllib.parse.unquote_plus(weather_line.split(':')[0])
    if not content.startswith(city_label):
        content = f"{city_label} {content}"
    return f"穿衣建议：{content}"


def check_openai_key(api_key: str, base_url: str) -> dict:
    """
    Verify OPENAI API key by calling GET {base_url}/models (if supported) or a lightweight chat completion.
    Returns the parsed JSON response (models list) or raises RuntimeError on failure.
    """
    if not api_key:
        raise RuntimeError("OPENAI API key not set in environment or --llm-api-key")
    url = base_url.rstrip("/") + "/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        # try a very small chat completion call as fallback
        url2 = base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }
        data = json.dumps(payload).encode("utf-8")
        req2 = urllib.request.Request(url2, data=data, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req2, timeout=10) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e2:
            raise RuntimeError(f"OpenAI key check failed: {e} | {e2}")


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
    ap.add_argument("--llm-base-url", default="http://127.0.0.1:4141/v1", help="OpenAI-compatible base URL (default: local copilot-api)")
    ap.add_argument("--llm-model", default="gpt-5-mini", help="Model id for LLM advice (optional)")
    ap.add_argument("--llm-api-key", default=os.getenv("OPENAI_API_KEY", ""), help="API key (optional)")
    ap.add_argument("--verify-key", action="store_true", help="Only verify OPENAI API key and exit")
    args = ap.parse_args()

    # If using OpenAI base URL, verify API key early
    if "api.openai.com" in args.llm_base_url:
        try:
            res = check_openai_key(args.llm_api_key or os.getenv("OPENAI_API_KEY", ""), args.llm_base_url)
            if args.verify_key:
                print("Key check OK. Sample response:")
                # if models list, print top few model ids
                if isinstance(res, dict) and res.get("data"):
                    print([m.get("id") for m in res.get("data")[:10]])
                else:
                    print(res)
                sys.exit(0)
        except Exception as e:
            print("OpenAI API key verification failed:", e)
            sys.exit(2)

    weather = fetch_weather(args.city)
    temp_c = parse_temp_c(weather)

    if args.llm_model:
        try:
            advice = llm_outfit_advice(weather, args.llm_base_url, args.llm_model, args.llm_api_key or None)
        except Exception as e:
            print("LLM call failed:", e)
            sys.exit(2)

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
