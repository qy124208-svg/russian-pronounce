# -*- coding: utf-8 -*-
"""把 local_dict.json.gz 按前两个字符分片成 docs/dict/<键>.json + manifest.json。

GitHub Pages 前端按需加载分片（docs/app.js 里 fetch "dict/" + 前两字符 + ".json"），
避免一次加载 90 万词的大 JSON。
"""
import gzip
import json
import os
import sys


def main(src, outdir):
    with gzip.open(src, "rt", encoding="utf-8") as f:
        word_map = json.load(f)

    shards = {}
    for k, v in word_map.items():
        key = k[:2] if len(k) >= 2 else k
        shards.setdefault(key, {})[k] = v

    os.makedirs(outdir, exist_ok=True)
    manifest = {}
    for key in sorted(shards):
        items = shards[key]
        with open(os.path.join(outdir, key + ".json"), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, separators=(",", ":"))
        manifest[key] = len(items)

    with open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(",", ":"))

    print(f"分片完成：{len(shards)} 个分片，共 {len(word_map)} 词条", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
