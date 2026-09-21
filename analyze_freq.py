# -*- coding: utf-8 -*-
"""分析：俄语词频表(Top N) 与 本地词库 的交集，用于定预生成规模。"""
import gzip
import json
import sys
import itertools

sys.stdout.reconfigure(encoding="utf-8")

# 1. 词频表（词 频次）
freq = []
with open("ru_50k.txt", encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").rsplit(" ", 1)
        if len(p) == 2 and p[1].isdigit():
            freq.append((p[0], int(p[1])))
print(f"词频表总词数: {len(freq)}")

# 2. 词库 keys
print("加载词库 local_dict.json.gz ...")
with gzip.open("local_dict.json.gz", "rt", encoding="utf-8") as f:
    d = json.load(f)
keys = set(d.keys())
print(f"词库键数: {len(keys)}")

# key 大小写 / 重音样例
samples = list(itertools.islice(keys, 8))
print("词库 key 样例:", samples)

# 3. 交集统计
print("\n=== 交集统计 ===")
for n in (500, 1000, 2000, 3000, 5000, 10000, 20000, 50000):
    top = freq[:n]
    hit = sum(1 for w, _ in top if w in keys)
    miss_examples = [w for w, _ in top if w not in keys][:6]
    print(f"Top {n:>5}: 命中 {hit:>5}/{n} ({hit/n*100:5.1f}%)  未命中示例: {miss_examples}")
