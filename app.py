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
import gzip
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

# 本地离线词库（kaikki.org Wiktionary 转储提取，含重音/IPA/真人发音文件名）
_LOCAL_DICT = None

# 在线接口（Morpher 重音 / Wiktionary IPA）可用性：进程级自动探测 + 缓存。
# 本机开代理时在线可用 → 本地 miss 时走在线补覆盖（短语/句子/低频词）；
# 朋友无代理时首次探测 3s 失败后缓存 False → 之后本地词库秒出，不再反复卡超时。
# None = 未探测；不影响 Edge-TTS 标准发音（其国内可直连，保持在线）。
_ONLINE_AVAILABLE = None


def _online_available():
    """探测在线接口是否可达（Morpher 快速请求，3s 超时），结果缓存。"""
    global _ONLINE_AVAILABLE
    if _ONLINE_AVAILABLE is not None:
        return _ONLINE_AVAILABLE
    try:
        r = requests.post(
            "https://ws3.morpher.ru/russian/addstressmarks",
            data="тест".encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8",
                     "User-Agent": UA["User-Agent"]},
            timeout=3,
        )
        _ONLINE_AVAILABLE = (r.status_code == 200)
    except Exception:
        _ONLINE_AVAILABLE = False
    return _ONLINE_AVAILABLE


def _resource_path(name):
    """定位打包进 EXE 的资源文件（兼容 PyInstaller 的 sys._MEIPASS）。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def _load_local_dict():
    """惰性加载本地词库到内存（一次性）。失败返回空 dict。"""
    global _LOCAL_DICT
    if _LOCAL_DICT is not None:
        return _LOCAL_DICT
    _LOCAL_DICT = {}
    path = _resource_path("local_dict.json.gz")
    if os.path.exists(path):
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                _LOCAL_DICT = json.load(f)
        except Exception:
            _LOCAL_DICT = {}
    return _LOCAL_DICT


def _strip_accent(word):
    """去掉重音符号（U+0301）并转小写，作为本地词库的查询键。

    必须转小写：词库 key 全小写，而手机输入法常自动首字母大写，
    不转会导致 miss 并误走被墙的在线接口。
    """
    return word.replace("́", "").lower()


def add_stress(word):
    """调用 Morpher.ru 给俄语单词/文本自动标注重音。失败时原样返回。

    先走系统代理（俄罗斯站经代理节点通常更快更稳），失败再直连，
    两条通道都不通则降级返回原词（发音仍可用，只是不标重音）。
    """
    if word in _STRESS_CACHE:
        return _STRESS_CACHE[word]
    # 本地词库优先（离线秒出，无需联网）
    local = _load_local_dict().get(_strip_accent(word))
    if local and local.get("accent"):
        _STRESS_CACHE[word] = local["accent"]
        return local["accent"]
    stressed = word
    if _online_available():
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
    # 本地词库优先（离线提供 IPA + 真人发音文件名）
    local = _load_local_dict().get(_strip_accent(word))
    if local and (local.get("ipa") or local.get("audio")):
        info = {"ipa": local.get("ipa"), "ogg": local.get("audio")}
        _WIKT_CACHE[word] = info
        return info
    info = None
    if _online_available():
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


def get_native_audio_path(ogg_filename):
    """返回本地真人发音 mp3 的绝对路径（不存在则返回 None）。

    优先 PyInstaller 打包目录(_MEIPASS/audios)，否则源码目录 docs/audios。
    .ogg 文件名转 .mp3（已在本地转码，绕开被墙的 Wikimedia CDN）。
    """
    mp3 = re.sub(r"\.ogg$", ".mp3", ogg_filename, flags=re.IGNORECASE)
    for base in (_resource_path("audios"),
                 os.path.join(BASE_DIR, "docs", "audios")):
        p = os.path.join(base, mp3)
        if os.path.exists(p):
            return p
    return None


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
    """返回本地真人发音 mp3（离线，不依赖被墙的 Wikimedia），无则 404。"""
    word = (request.args.get("word") or "").strip()
    if not word:
        return jsonify({"error": "请输入俄语单词"}), 400
    wikt = fetch_wiktionary(word)
    if not wikt or not wikt.get("ogg"):
        return jsonify({"error": "暂无真人发音"}), 404
    path = get_native_audio_path(wikt["ogg"])
    if not path:
        return jsonify({"error": "本地无该词真人发音文件"}), 404
    return send_file(path, mimetype="audio/mpeg")


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
