# -*- coding: utf-8 -*-
"""从 kaikki.org Russian 转储提取精简离线词库。

输入：kaikki.org-dictionary-Russian.jsonl.gz
输出：local_dict.json.gz

结构：{ 去掉重音符号的词 : {"accent": 带重音拼写, "ipa": 音标, "audio": .ogg 文件名} }

要点：
- 主词条 + 所有变形词（forms 里带重音符号的 form）都作为查询键，解决变形词覆盖
- 重音符号为 U+0301（combining acute），与 Morpher.ru 一致
- IPA 去掉方括号，与 app.py 现有返回格式一致
"""
import gzip
import json
import re
import sys

ACCENT = "́"
RUS = re.compile(r"^[а-яёА-ЯЁ][а-яёА-ЯЁ\-]*$")


def strip_accent(s):
    return s.replace(ACCENT, "")


def main(src, out):
    word_map = {}
    count = 0
    skipped = 0
    with gzip.open(src, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                skipped += 1
                continue
            if d.get("lang") != "Russian":
                continue
            word = d.get("word") or ""
            clean_word = strip_accent(word).lower()
            if not clean_word or not RUS.match(clean_word):
                continue

            # IPA + audio（取第一个）
            ipa = None
            audio = None
            for s in d.get("sounds", []):
                if ipa is None and s.get("ipa"):
                    ipa = s["ipa"].strip("[]/")
                if audio is None and s.get("audio"):
                    a = s["audio"]
                    if isinstance(a, str) and a.endswith(".ogg"):
                        audio = a

            forms = d.get("forms", [])
            # 主词重音拼写：只接受"重音形式去重音后 == 词条本身"的形式。
            # 避免两类污染：
            #  1) 变形词词条的 canonical 指向词元（如 старому→ста́рый）
            #  2) 词元词条 forms 开头简化变形列表里的属格（如 зонт→зонта́、хлеб→хле́ба）
            accent = None
            # 1) word 本身带重音
            if ACCENT in word:
                accent = word
            # 2) 词元形式本身带重音的 form（去重音后 == 词条，即主格单数/动词不定式等）
            if accent is None:
                for form in forms:
                    fw = form.get("form") or ""
                    if ACCENT in fw and strip_accent(fw).lower() == clean_word:
                        accent = fw
                        break
            # 3) 俄语铁律：ё 永远重读。含 ё 的词未取到重音时，直接在 ё 上加。
            #    覆盖 Wiktionary 不标重音的含 ё 词（нёбо/ёжик/озёра…），占无重音词的 ~89%。
            if accent is None and "ё" in clean_word:
                accent = clean_word.replace("ё", "ё́", 1)
            # 清洗：只保留俄语字母/重音/连字符，统一小写（去空格、!、•、标点等）
            if accent:
                accent = re.sub(r"[^а-яёА-ЯЁ́\-]", "", accent).lower() or None

            # 主词写入
            entry = word_map.get(clean_word, {})
            if accent:
                entry["accent"] = accent
            if ipa:
                entry["ipa"] = ipa
            if audio:
                entry["audio"] = audio
            word_map[clean_word] = entry

            # 所有带重音的变形词写入（只补 accent）
            for form in forms:
                fw = form.get("form") or ""
                if ACCENT not in fw:
                    continue
                k = strip_accent(fw).lower()
                if k and k != clean_word and RUS.match(k):
                    e = word_map.get(k, {})
                    e.setdefault("accent", re.sub(r"[^а-яёА-ЯЁ́\-]", "", fw).lower())
                    word_map[k] = e

            count += 1
            if count % 50000 == 0:
                print(f"已处理 {count} 词条，词库 {len(word_map)} 键", file=sys.stderr)

    # 写入 gzip 压缩的 JSON
    with gzip.open(out, "wt", encoding="utf-8") as f:
        json.dump(word_map, f, ensure_ascii=False, separators=(",", ":"))
    print(f"完成：{count} 词条 -> {len(word_map)} 个查询键（跳过 {skipped} 行）", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
