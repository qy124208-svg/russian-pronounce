# -*- coding: utf-8 -*-
"""预生成俄语高频词的标准发音 mp3（Edge-TTS）。

流程：
  1. 读词频表 ru_50k.txt（词 频次，降序）
  2. 加载词库 local_dict.json.gz，过滤出「词库内存在」的词（只生成查词能命中的词，省时省空间）
  3. 用 edge_tts 生成 mp3 → docs/tts/{词}.mp3（断点续传，已存在跳过）
  4. 并发 + 失败重试

用法：
  python generate_tts.py --top 20000      # 生成 Top 20000
  python generate_tts.py --top 20         # 小批量验证
  python generate_tts.py --top 20000 --concurrency 5
"""
import asyncio
import gzip
import json
import os
import sys
import time

import edge_tts

sys.stdout.reconfigure(encoding="utf-8")

VOICE = "ru-RU-SvetlanaNeural"  # 与 docs/app.js 保持一致
OUT_DIR = os.path.join("docs", "tts")


def load_freq(top):
    freq = []
    with open("ru_50k.txt", encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").rsplit(" ", 1)
            if len(p) == 2 and p[1].isdigit():
                freq.append(p[0])
    return freq[:top]


def load_dict_keys():
    with gzip.open("local_dict.json.gz", "rt", encoding="utf-8") as f:
        return set(json.load(f).keys())


async def gen_one(word, sem, retries=3):
    """生成单个词，成功返回 (word, 'ok')，失败返回 (word, err)。"""
    out = os.path.join(OUT_DIR, word + ".mp3")
    if os.path.exists(out) and os.path.getsize(out) > 500:
        return (word, "skip")
    async with sem:
        for attempt in range(retries):
            try:
                com = edge_tts.Communicate(word, VOICE)
                await com.save(out)
                if os.path.getsize(out) > 500:
                    return (word, "ok")
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                if attempt < retries - 1:
                    await asyncio.sleep(1.5 * (attempt + 1))
                else:
                    return (word, err)
    return (word, "fail")


async def main(top, concurrency):
    freq = load_freq(top)
    keys = load_dict_keys()
    words = [w for w in freq if w in keys]
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"词频 Top {top} -> 命中词库 {len(words)} 词，将生成到 {OUT_DIR}/")

    sem = asyncio.Semaphore(concurrency)
    done = skip = fail = 0
    fails = []
    t0 = time.time()

    # 分批跑，每 200 个打印一次进度
    BATCH = 200
    for i in range(0, len(words), BATCH):
        chunk = words[i:i + BATCH]
        results = await asyncio.gather(*(gen_one(w, sem) for w in chunk))
        for w, status in results:
            if status == "ok":
                done += 1
            elif status == "skip":
                skip += 1
            else:
                fail += 1
                fails.append((w, status))
        elapsed = time.time() - t0
        n = i + len(chunk)
        rate = n / elapsed if elapsed > 0 else 0
        print(f"[{n}/{len(words)}] 新生成 {done} 跳过 {skip} 失败 {fail}  速度 {rate:.2f} 词/s 已用 {elapsed/60:.1f} 分")

    print(f"\n完成：新生成 {done}，跳过(已存在) {skip}，失败 {fail}")
    if fails:
        with open("tts_fail.txt", "w", encoding="utf-8") as f:
            for w, e in fails:
                f.write(f"{w}\t{e}\n")
        print(f"失败清单已写 tts_fail.txt（{len(fails)} 条），可重跑本脚本续传")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20000)
    ap.add_argument("--concurrency", type=int, default=5)
    args = ap.parse_args()
    asyncio.run(main(args.top, args.concurrency))
