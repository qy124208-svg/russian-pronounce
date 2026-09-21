# -*- coding: utf-8 -*-
"""对 local_dict.json.gz 做全面体检：重音(accent) + IPA 的各类潜在 bug。"""
import gzip
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

ACCENT = "́"
VOWELS = "аеёиоуыэюяАЕЁИОУЫЭЮЯ"


def strip(s):
    return s.replace(ACCENT, "")


def main(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        wm = json.load(f)
    total = len(wm)

    no_accent = 0
    polluted = 0
    len_mismatch = 0
    acc_space = 0
    acc_hyphen = 0
    acc_multi = 0
    acc_bad_vowel = 0
    no_ipa = 0
    ipa_bracket = 0
    ipa_space = 0
    ipa_stress_no_accent = 0

    polluted_s = []
    len_s = []
    hyphen_s = []
    multi_s = []
    badvowel_s = []
    ipa_bracket_s = []
    ipa_stress_s = []

    for k, v in wm.items():
        accent = v.get("accent")
        ipa = v.get("ipa")

        if not accent:
            no_accent += 1
        else:
            sk = strip(accent)
            if sk != k:
                polluted += 1
                if len(polluted_s) < 15:
                    polluted_s.append((k, accent))
            if len(sk) != len(k):
                len_mismatch += 1
                if len(len_s) < 10:
                    len_s.append((k, accent))
            if " " in accent:
                acc_space += 1
                if len(hyphen_s) < 10:
                    hyphen_s.append((k, accent))
            elif "-" in accent:
                acc_hyphen += 1
                if len(hyphen_s) < 10:
                    hyphen_s.append((k, accent))
            if accent.count(ACCENT) > 1:
                acc_multi += 1
                if len(multi_s) < 10:
                    multi_s.append((k, accent))
            for i, ch in enumerate(accent):
                if ch == ACCENT:
                    prev = accent[i - 1] if i > 0 else ""
                    if prev not in VOWELS:
                        acc_bad_vowel += 1
                        if len(badvowel_s) < 10:
                            badvowel_s.append((k, accent))

        if not ipa:
            no_ipa += 1
        else:
            if ipa[0] in "[/" or ipa[-1] in "]/":
                ipa_bracket += 1
                if len(ipa_bracket_s) < 10:
                    ipa_bracket_s.append((k, ipa))
            if " " in ipa:
                ipa_space += 1
            if ("ˈ" in ipa or "ˌ" in ipa) and not accent:
                ipa_stress_no_accent += 1
                if len(ipa_stress_s) < 15:
                    ipa_stress_s.append((k, ipa))

    print("=== 总键数 %d ===" % total)
    print()
    print("【重音 accent】")
    print("  无重音             %6d  (%5.1f%%)" % (no_accent, 100 * no_accent / total))
    print("  重音污染(strip!=key) %6d  (%5.1f%%)" % (polluted, 100 * polluted / total))
    print("  去重音后长度!=key    %6d" % len_mismatch)
    print("  重音含空格           %6d" % acc_space)
    print("  重音含连字符         %6d" % acc_hyphen)
    print("  多重音符号           %6d" % acc_multi)
    print("  重音不在元音上       %6d" % acc_bad_vowel)
    print()
    print("【IPA】")
    print("  无IPA                %6d  (%5.1f%%)" % (no_ipa, 100 * no_ipa / total))
    print("  IPA残留括号          %6d" % ipa_bracket)
    print("  IPA含空格            %6d" % ipa_space)
    print("  IPA有重音标记但accent空 %6d" % ipa_stress_no_accent)
    print()
    for title, samples in [
        ("污染样例", polluted_s), ("长度不匹配样例", len_s),
        ("连字符/空格样例", hyphen_s), ("多重音样例", multi_s),
        ("重音不在元音样例", badvowel_s), ("IPA括号残留样例", ipa_bracket_s),
        ("IPA有重音但accent空样例", ipa_stress_s),
    ]:
        if samples:
            print(title + ":", samples)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "local_dict.json.gz")
