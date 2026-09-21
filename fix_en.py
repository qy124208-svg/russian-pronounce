# -*- coding: utf-8 -*-
"""修复 en 字段：kaikki 同名词条（不同词源）的英文释义应合并而非覆盖。

直接重算现有 local_dict.json.gz 的 en，保留 accent/ipa/audio/zh 不变。
"""
import gzip
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ACCENT = "́"
RUS = re.compile(r"^[а-яёА-ЯЁ][а-яёА-ЯЁ\-]*$")


def strip_accent(s):
    return s.replace(ACCENT, "")


def main(src_kaikki, dict_path):
    with gzip.open(dict_path, "rt", encoding="utf-8") as f:
        d = json.load(f)
    # 清空现有 en，重新提取
    for v in d.values():
        v.pop("en", None)

    updated = 0
    with gzip.open(src_kaikki, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("lang") != "Russian":
                continue
            word = e.get("word") or ""
            clean = strip_accent(word).lower()
            if not clean or not RUS.match(clean) or clean not in d:
                continue
            en = []
            for s in e.get("senses", []):
                for g in (s.get("glosses") or []):
                    g = (g or "").strip()
                    if g and g not in en:
                        en.append(g)
                if len(en) >= 3:
                    break
            if en:
                entry = d[clean]
                merged = entry.get("en", [])
                for g in en:
                    if g and g not in merged:
                        merged.append(g)
                entry["en"] = merged[:3]
                updated += 1

    with gzip.open(dict_path, "wt", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))

    print("更新 en 的词条: %d" % updated, file=sys.stderr)
    for k in ("вода", "собака", "замок", "лук", "мир", "ключ"):
        if k in d:
            print("  %-10s -> en: %s | zh: %s" % (k, d[k].get("en"), d[k].get("zh", [])[:2]), file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
