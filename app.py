# -*- coding: utf-8 -*-
"""俄语单词发音查询工具

功能：
  1. Morpher.ru 自动标注重音（ударение，U+0301）
  2. Edge-TTS 用带重音的版本合成标准俄语发音（男/女声、可调语速）
  3. 历史查询记录（本地 history.json，支持复习跟读）
  4. 局域网可访问（手机/平板用同一 WiFi 访问）

启动：python app.py  →  浏览器打开 http://127.0.0.1:5000
"""
import asyncio
import datetime
import hashlib
import io
import json
import os
import re
import socket
import sys
import urllib.parse

import edge_tts
import requests
from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
HISTORY_MAX = 200  # 最多保留条数

# 俄语神经语音（Azure / Edge-TTS）
VOICES = {
    "ru-RU-DmitryNeural": "男声 Dmitry",
    "ru-RU-SvetlanaNeural": "女声 Svetlana",
    "ru-RU-DariyaNeural": "女声 Dariya",
}

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}

# 重音查询缓存，避免重复请求 Morpher.ru
_STRESS_CACHE = {}

# Wiktionary（移动版）抓取缓存，避免重复请求
_WIKT_CACHE = {}


def add_stress(word):
    """调用 Morpher.ru 给俄语单词/文本自动标注重音。失败时原样返回。

    先走系统代理（俄罗斯站经代理节点通常更快更稳），失败再直连，
    两条通道都不通则降级返回原词（发音仍可用，只是不标重音）。
    """
    if word in _STRESS_CACHE:
        return _STRESS_CACHE[word]
    stressed = word
    # proxies=None 走 requests 默认（读系统代理）；None 直连作为兜底
    for proxies in (None, {"http": None, "https": None}):
        try:
            r = requests.post(
                "https://ws3.morpher.ru/russian/addstressmarks",
                data=word.encode("utf-8"),
                headers={"Content-Type": "text/plain; charset=utf-8",
                         "User-Agent": UA["User-Agent"]},
                timeout=6,
                proxies=proxies,
            )
            if r.status_code == 200:
                m = re.search(r"<string>(.*?)</string>", r.text, re.DOTALL)
                if m:
                    stressed = m.group(1).strip()
                    break
        except Exception:
            continue
    _STRESS_CACHE[word] = stressed
    return stressed


def fetch_wiktionary(word):
    """抓取 ru.m.wiktionary.org 移动版页面，提取 IPA 音标 + 真人发音 .ogg 文件名。

    桌面版/API 会被墙（403），但移动版页面和文件 CDN 直连可用。
    返回 {"ipa": str|None, "ogg": str|None}，失败返回 None。
    """
    if word in _WIKT_CACHE:
        return _WIKT_CACHE[word]
    info = None
    try:
        r = requests.get(
            "https://ru.m.wiktionary.org/wiki/" + urllib.parse.quote(word),
            headers=UA,
            timeout=10,
        )
        if r.status_code == 200:
            html = r.text
            ipa = None
            m = re.search(r'<span class="IPA"[^>]*>([^<]+)</span>', html)
            if m:
                ipa = m.group(1)
            ogg = None
            m = re.search(r'([A-Za-z-]+-[а-яёА-ЯЁ0-9_-]+\.ogg)', html)
            if m:
                ogg = m.group(1)
            if ipa or ogg:
                info = {"ipa": ipa, "ogg": ogg}
    except Exception:
        pass
    _WIKT_CACHE[word] = info
    return info


def get_ogg_url(filename):
    """用文件名 MD5 构造 Wikimedia Commons 直链（绕开被墙的 imageinfo API）。"""
    h = hashlib.md5(filename.encode("utf-8")).hexdigest()
    return ("https://upload.wikimedia.org/wikipedia/commons/%s/%s/%s"
            % (h[0], h[:2], urllib.parse.quote(filename)))


async def synth_mp3(word, voice, rate):
    """Edge-TTS 合成，返回内存中的 MP3 BytesIO"""
    tts = edge_tts.Communicate(word, voice, rate=rate)
    buf = io.BytesIO()
    async for chunk in tts.stream():
        if chunk.get("type") == "audio":
            buf.write(chunk["data"])
    buf.seek(0)
    return buf


def get_lan_ip():
    """获取本机局域网 IP（供手机/平板访问）"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ---------- 历史记录 ----------
def _load_history():
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_history(items):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def record_history(word, stressed):
    """记录查询历史（同一单词去重，只留最新，最多 200 条）"""
    items = [it for it in _load_history() if it.get("word") != word]
    items.insert(0, {
        "word": word,
        "stressed": stressed,
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save_history(items[:HISTORY_MAX])


# ---------- 路由 ----------
@app.route("/")
def index():
    return render_template("index.html", voices=VOICES)


@app.route("/api/pronounce")
def pronounce():
    word = (request.args.get("word") or "").strip()
    if not word:
        return jsonify({"error": "请输入俄语单词"}), 400
    voice = request.args.get("voice") or "ru-RU-DmitryNeural"
    if voice not in VOICES:
        voice = "ru-RU-DmitryNeural"
    rate = (request.args.get("rate") or "+0%").strip()
    if not re.fullmatch(r"[+-]\d+%", rate):
        rate = "+0%"

    stressed = add_stress(word)
    try:
        buf = asyncio.run(synth_mp3(stressed, voice, rate))
    except Exception as e:
        return jsonify({"error": "合成失败: %s" % str(e)[:120]}), 500
    return send_file(buf, mimetype="audio/mpeg", as_attachment=False,
                     download_name=word + ".mp3")


@app.route("/api/lookup")
def lookup():
    word = (request.args.get("word") or "").strip()
    if not word:
        return jsonify({"error": "请输入俄语单词"}), 400
    stressed = add_stress(word)
    record_history(word, stressed)
    wikt = fetch_wiktionary(word) or {}
    return jsonify({
        "word": word,
        "stressed": stressed,
        "has_stress": stressed != word,
        "ipa": wikt.get("ipa"),
        "has_native": bool(wikt.get("ogg")),
    })


@app.route("/api/native-audio")
def native_audio():
    """返回真人发音 .ogg（Wikimedia Commons 直链），无则 404。"""
    word = (request.args.get("word") or "").strip()
    if not word:
        return jsonify({"error": "请输入俄语单词"}), 400
    wikt = fetch_wiktionary(word)
    if not wikt or not wikt.get("ogg"):
        return jsonify({"error": "暂无真人发音"}), 404
    try:
        r = requests.get(get_ogg_url(wikt["ogg"]), headers=UA, timeout=15)
        if r.status_code != 200:
            return jsonify({"error": "真人发音下载失败"}), 404
    except Exception:
        return jsonify({"error": "真人发音下载失败"}), 500
    return send_file(io.BytesIO(r.content), mimetype="audio/ogg",
                     download_name=wikt["ogg"])


@app.route("/api/history")
def history():
    return jsonify(_load_history())


@app.route("/api/history/clear", methods=["POST"])
def history_clear():
    _save_history([])
    return jsonify({"ok": True})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    port = int(os.environ.get("PORT", 5000))
    lan_ip = get_lan_ip()
    print("=" * 52)
    print("  俄语单词发音查询工具")
    print("  本机访问:  http://127.0.0.1:%d" % port)
    print("  局域网访问: http://%s:%d  (手机/平板同 WiFi)" % (lan_ip, port))
    print("=" * 52)
    app.run(debug=False, host="0.0.0.0", port=port)
