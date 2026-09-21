# -*- coding: utf-8 -*-
"""多线程分段下载 kaikki 俄语转储（服务器支持 Range，单线程慢，分段并行提速）。"""
import os
import sys
import threading
import urllib.request

URL = "https://kaikki.org/dictionary/Russian/kaikki.org-dictionary-Russian.jsonl.gz"
OUT = "kaikki_ru.jsonl.gz"
THREADS = 8
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def get_size():
    req = urllib.request.Request(URL, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers.get("Content-Length", 0))


def download_range(start, end, idx, results):
    try:
        req = urllib.request.Request(URL, headers={**UA, "Range": "bytes=%d-%d" % (start, end)})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        with open(OUT + ".part%d" % idx, "wb") as f:
            f.write(data)
        results[idx] = len(data)
        print("  段%d 完成 %d 字节" % (idx, len(data)), file=sys.stderr)
    except Exception as e:
        results[idx] = -1
        print("  段%d 失败: %s" % (idx, e), file=sys.stderr)


def main():
    size = get_size()
    if not size:
        print("无法获取文件大小", file=sys.stderr)
        return
    print("总大小 %d 字节，%d 线程下载..." % (size, THREADS), file=sys.stderr)

    chunk = size // THREADS
    threads = []
    results = [0] * THREADS
    for i in range(THREADS):
        start = i * chunk
        end = size - 1 if i == THREADS - 1 else (i + 1) * chunk - 1
        t = threading.Thread(target=download_range, args=(start, end, i, results))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    if any(r < 0 for r in results):
        print("有分段下载失败，请重试", file=sys.stderr)
        return

    with open(OUT, "wb") as out:
        for i in range(THREADS):
            with open(OUT + ".part%d" % i, "rb") as p:
                out.write(p.read())
            os.remove(OUT + ".part%d" % i)
    print("下载完成：%d 字节" % os.path.getsize(OUT), file=sys.stderr)


if __name__ == "__main__":
    main()
