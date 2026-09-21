# -*- coding: utf-8 -*-
"""把 zh_map.json 的中文释义合并进 local_dict 词库的 zh 字段。

输入：local_dict.json.gz.new（含 accent/ipa/audio/en）+ zh_map.json（俄语词 -> 中文释义）
输出：local_dict.json.gz（含 zh 字段）
"""
import gzip
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")


def main(dict_path, zh_path, out_path):
    with gzip.open(dict_path, "rt", encoding="utf-8") as f:
        d = json.load(f)
    with open(zh_path, encoding="utf-8") as f:
        zh = json.load(f)

    n = 0
    skip = 0
    for k, glosses in zh.items():
        if k in d:
            d[k]["zh"] = glosses
            n += 1
        else:
            skip += 1
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))

    print("词库键: %d" % len(d), file=sys.stderr)
    print("合并中文释义: %d 词（未命中词库: %d）" % (n, skip), file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
