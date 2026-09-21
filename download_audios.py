# -*- coding: utf-8 -*-
"""批量下载真人发音音频（Wikimedia Commons），串行 + 限速退避 + 断点续传。

Wikimedia 对出口 IP 限速约 1 请求/秒，并发会触发 429 惩罚。
这里用纯串行 + 请求间隔 + 429 长退避，稳定下载（慢但几乎不失败）。
"""
import gzip
import hashlib
import json
import os
import time
import urllib.parse

import requests

UA = {"User-Agent": "RussianPronounceDict/1.0 (personal offline dictionary; "
                    "https://github.com/qy124208-svg/russian-pronounce)"}

# Wikimedia 直连被墙，走本机 Clash 代理（端口 7890）。代理未开则下载失败。
PROXIES = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}

OUTDIR = "web/audios"

# 请求间隔（秒）。间隔 = 请求耗时 + 此值，保持 ~2s 以上避免 429。
REQUEST_GAP = 1.5
# 429 冷却时间（秒），触发限流后停这么久再继续。
COOLDOWN_429 = 30


def load_audio_list():
    d = json.load(gzip.open("local_dict.json.gz", "rt", encoding="utf-8"))
    audios = {}
    for w, v in d.items():
        if v.get("audio"):
            audios[v["audio"]] = w
    return audios


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    audios = load_audio_list()
    items = list(audios.keys())
    print("待下载音频数: %d" % len(items), flush=True)

    s = requests.Session()
    s.headers.update(UA)
    s.proxies.update(PROXIES)

    ok = skip = fail = 0
    for i, fn in enumerate(items, 1):
        out = os.path.join(OUTDIR, fn)
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            skip += 1
            continue

        # Wikimedia 的 URL hash 对「空格替换为下划线」的文件名计算
        fn2 = fn.replace(" ", "_")
        h = hashlib.md5(fn2.encode("utf-8")).hexdigest()
        url = ("https://upload.wikimedia.org/wikipedia/commons/%s/%s/%s"
               % (h[0], h[:2], urllib.parse.quote(fn2)))

        got = False
        for attempt in range(4):
            try:
                r = s.get(url, timeout=15)
                if r.status_code == 200 and len(r.content) > 1000:
                    with open(out, "wb") as f:
                        f.write(r.content)
                    ok += 1
                    got = True
                    break
                if r.status_code == 429:
                    time.sleep(COOLDOWN_429)
                    continue
                if r.status_code == 404:
                    # 文件不存在，不重试
                    got = True
                    break
                # 其他状态码重试
                time.sleep(3)
            except Exception:
                time.sleep(5)
        if not got:
            fail += 1

        time.sleep(REQUEST_GAP)
        if i % 100 == 0:
            print("进度 %d/%d  ok=%d skip=%d fail=%d"
                  % (i, len(items), ok, skip, fail), flush=True)

    print("完成: ok=%d skip=%d fail=%d (共 %d)"
          % (ok, skip, fail, len(items)), flush=True)


if __name__ == "__main__":
    main()
