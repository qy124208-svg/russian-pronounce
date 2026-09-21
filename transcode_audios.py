# -*- coding: utf-8 -*-
"""把下载的 .ogg 真人发音批量转码成 32k mp3（单词发音足够），并删除原 .ogg 省空间。"""
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

AUDIO_DIR = "web/audios"


def transcode(fn):
    if not fn.endswith(".ogg"):
        return "skip"
    src = os.path.join(AUDIO_DIR, fn)
    dst = os.path.join(AUDIO_DIR, fn[:-4] + ".mp3")
    if os.path.exists(dst) and os.path.getsize(dst) > 500:
        try:
            os.remove(src)
        except Exception:
            pass
        return "skip"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-b:a", "32k", dst],
            check=True, timeout=30, capture_output=True,
        )
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            os.remove(src)
            return "ok"
        return "fail"
    except Exception:
        return "fail"


def main():
    files = [f for f in os.listdir(AUDIO_DIR) if f.endswith(".ogg")]
    print("待转码 ogg: %d" % len(files), flush=True)
    ok = skip = fail = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(transcode, f): f for f in files}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            if r == "ok":
                ok += 1
            elif r == "skip":
                skip += 1
            else:
                fail += 1
            if i % 500 == 0:
                print("转码 %d/%d ok=%d fail=%d" % (i, len(files), ok, fail), flush=True)
    print("转码完成: ok=%d skip=%d fail=%d" % (ok, skip, fail), flush=True)
    mp3 = [f for f in os.listdir(AUDIO_DIR) if f.endswith(".mp3")]
    total = sum(os.path.getsize(os.path.join(AUDIO_DIR, f)) for f in mp3)
    print("mp3 总数 %d, 总大小 %.1f MB" % (len(mp3), total / 1024 / 1024), flush=True)


if __name__ == "__main__":
    main()
