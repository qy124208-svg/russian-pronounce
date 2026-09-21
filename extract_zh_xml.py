# -*- coding: utf-8 -*-
"""从中文 Wiktionary 原始 XML 转储提取俄语词条的中文释义。

输入：zhwiktionary-latest-pages-articles.xml.bz2（dumps.wikimedia.org，MediaWiki dump）
输出：zh_map.json（{ 俄语词(小写): [中文释义, ...] }）

要点：
- 流式解析（iterparse），284MB 压缩 / 解压后 1GB+，不能整读进内存
- 只取 ns==0 的正文页，title 为纯俄语词（西里尔字母/连字符）
- 定位「==俄語== / ==俄语== / ==俄文==」二级语言章节，取章节内的 # 释义行
- 释义行清洗：去模板 {{..}}（含嵌套）、链接 [[..]]、加粗 '''、ref 引用、HTML 标签
"""
import bz2
import gzip
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ACCENT = "́"
RUS = re.compile(r"^[а-яёА-ЯЁ][а-яёА-ЯЁ\- ]*$")
# 二级语言章节标题：==俄語== / ==俄语== / ==俄文==
RU_SECTION = re.compile(r"^==\s*(俄[語语]|俄文)\s*==\s*$")
# 任意二级标题（用于判断俄语章节结束）
ANY_L2 = re.compile(r"^==\s*[^=].*?\s*==\s*$")


def strip_templates(s):
    """去掉 {{...}} 模板（处理嵌套），返回剩余文本。"""
    out = []
    depth = 0
    i = 0
    n = len(s)
    while i < n:
        if s[i:i + 2] == "{{":
            depth += 1
            i += 2
            continue
        if s[i:i + 2] == "}}":
            depth -= 1
            i += 2
            continue
        if depth == 0:
            out.append(s[i])
        i += 1
    return "".join(out)


def clean_gloss(raw):
    """清洗一条 # 释义行，返回干净的中文释义文本（空则返回 None）。"""
    s = raw.strip()
    if not s:
        return None
    # 去掉开头的 # 及其后空格
    s = re.sub(r"^#+\s*", "", s)
    # 去 HTML 注释
    s = re.sub(r"<!--.*?-->", "", s, flags=re.DOTALL)
    # 去 ref 引用
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.DOTALL)
    s = re.sub(r"<[^>]+>", "", s)
    # 去模板（含嵌套）
    s = strip_templates(s)
    # 去链接 [[a|b]] -> b, [[a]] -> a
    s = re.sub(r"\[\[(?:[^\[\]|]*\|)?([^\[\]]*)\]\]", r"\1", s)
    # 去加粗/斜体
    s = s.replace("'''", "").replace("''", "")
    # 去行内多余空白
    s = re.sub(r"\s+", " ", s).strip(" ,、;；:：。")
    # 过滤纯符号/无中文字符或拉丁词元的残骸
    if not s or len(s) < 1:
        return None
    if not re.search(r"[一-鿿]", s):
        return None
    return s


def extract_ru_glosses(text):
    """从页面 wikitext 提取俄语章节的中文释义（最多取 6 条）。"""
    if not text or "俄" not in text:
        return []
    glosses = []
    in_ru = False
    for line in text.splitlines():
        s = line.strip()
        if RU_SECTION.match(s):
            in_ru = True
            continue
        if in_ru and ANY_L2.match(s):
            # 遇到下一个二级语言章节，退出俄语区
            in_ru = False
            continue
        if in_ru and s.startswith("#"):
            g = clean_gloss(s)
            if g and g not in glosses:
                glosses.append(g)
                if len(glosses) >= 6:
                    break
    return glosses


def main(src, out="zh_map.json"):
    zh_map = {}
    pages = 0
    ru_pages = 0
    with_zh = 0
    samples = []

    # 支持 .bz2 / .gz / 裸 XML
    if src.endswith(".bz2"):
        opener = bz2.open(src, "rt", encoding="utf-8", errors="replace")
    elif src.endswith(".gz"):
        opener = gzip.open(src, "rt", encoding="utf-8", errors="replace")
    else:
        opener = open(src, "rt", encoding="utf-8", errors="replace")

    with opener as f:
        import xml.etree.ElementTree as ET
        title = None
        text = None
        ns = None
        for event, elem in ET.iterparse(f, events=("end",)):
            if not elem.tag.endswith("page"):
                continue
            # 取 title / ns / revision.text
            title = text = ns = None
            for child in elem:
                tag = child.tag.rsplit("}", 1)[-1]
                if tag == "title":
                    title = child.text or ""
                elif tag == "ns":
                    ns = child.text or ""
                elif tag == "revision":
                    for r in child:
                        if r.tag.rsplit("}", 1)[-1] == "text":
                            text = r.text or ""
                            break
            elem.clear()  # 释放内存

            if ns != "0" or not title:
                continue
            pages += 1
            w = title.strip()
            if not RUS.match(w):
                continue
            ru_pages += 1
            key = w.replace(ACCENT, "").lower()
            glosses = extract_ru_glosses(text)
            if glosses:
                with_zh += 1
                zh_map[key] = glosses
                if len(samples) < 10:
                    samples.append((key, glosses[:4]))
            if pages % 200000 == 0:
                print("已扫描 %d 页，俄语词条 %d，有中文释义 %d"
                      % (pages, ru_pages, with_zh), file=sys.stderr)

    print("=" * 50, file=sys.stderr)
    print("总页数: %d" % pages, file=sys.stderr)
    print("俄语词条: %d" % ru_pages, file=sys.stderr)
    print("有中文释义: %d" % len(zh_map), file=sys.stderr)
    print("样例:", file=sys.stderr)
    for w, g in samples:
        print("  %-14s -> %s" % (w, g), file=sys.stderr)

    with open(out, "w", encoding="utf-8") as fo:
        json.dump(zh_map, fo, ensure_ascii=False, separators=(",", ":"))
    print("已写入 %s（%d 词）" % (out, len(zh_map)), file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "zh_map.json")
