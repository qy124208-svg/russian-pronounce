# -*- coding: utf-8 -*-
"""把 local_dict.json.gz 里中文释义（zh 字段）繁体转简体（OpenCC t2s）。"""
import gzip
import json
import sys

from opencc import OpenCC

sys.stdout.reconfigure(encoding="utf-8")


def main(path):
    cc = OpenCC("t2s")
    with gzip.open(path, "rt", encoding="utf-8") as f:
        d = json.load(f)

    n = 0
    changed = 0
    for k, v in d.items():
        zh = v.get("zh")
        if not zh:
            continue
        new = []
        for g in zh:
            g2 = cc.convert(g)
            if g2 and g2 not in new:
                new.append(g2)
        if new != zh:
            changed += 1
        v["zh"] = new
        n += 1

    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))

    print("有中文释义的词: %d，发生繁简变化的词: %d" % (n, changed), file=sys.stderr)
    # 抽样
    samples = [("вода", "水"), ("собака", "狗"), ("книга", "书")]
    for k, hint in samples:
        if k in d and d[k].get("zh"):
            print("  %-10s -> %s" % (k, d[k]["zh"][:3]), file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1])
