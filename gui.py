# -*- coding: utf-8 -*-
"""俄语单词发音查询工具 —— 桌面版（tkinter）

双击运行：输入俄语单词 → 看重音 + IPA → 听标准发音 / 真人发音。
复用 app.py 的核心函数（add_stress / fetch_wiktionary / get_ogg_url / synth_mp3）。

打包成单文件 EXE（发给朋友双击即用）：
    pip install pyinstaller pygame
    pyinstaller --onefile --windowed --name "俄语发音查询" gui.py
"""

import asyncio
import json
import os
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import requests

# 复用后端核心函数（与 app.py 同目录）
import app as core

# 音频播放库（缺失则回退系统默认播放器）
try:
    import pygame
    _HAS_PYGAME = True
except Exception:
    _HAS_PYGAME = False

# 历史记录文件（存用户目录，避免打包后写入只读的临时目录）
HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".russian_pronounce_history.json")

VOICE_KEYS = list(core.VOICES.keys())
VOICE_NAMES = [core.VOICES[k] for k in VOICE_KEYS]
RATE_OPTIONS = ["-30%", "-20%", "-10%", "+0%", "+10%", "+15%"]

# 临时音频文件，播放新音频前清理旧的
_TMP_AUDIO = []


def _cleanup_tmp():
    for p in _TMP_AUDIO:
        try:
            os.remove(p)
        except Exception:
            pass
    _TMP_AUDIO.clear()


def play_bytes(data, suffix):
    """播放音频字节：优先 pygame，失败回退系统默认播放器。"""
    _cleanup_tmp()
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    _TMP_AUDIO.append(path)

    if _HAS_PYGAME:
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            return
        except Exception:
            pass
    # Windows 用默认播放器兜底
    try:
        os.startfile(path)
    except Exception:
        pass


class App:
    def __init__(self, root):
        self.root = root
        root.title("俄语单词发音查询工具")
        root.geometry("560x540")
        root.minsize(480, 460)

        self.current = None  # 当前查询结果 dict
        self._history = []

        self._build_ui()
        self._load_history()
        self.entry.focus_set()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # 输入行
        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="俄语单词:").pack(side="left")
        self.entry = ttk.Entry(top, font=("Segoe UI", 13))
        self.entry.pack(side="left", fill="x", expand=True, padx=6)
        self.entry.bind("<Return>", lambda e: self.on_query())
        self.btn_query = ttk.Button(top, text="查询", command=self.on_query)
        self.btn_query.pack(side="left")

        # 选项行
        opts = ttk.Frame(self.root)
        opts.pack(fill="x", **pad)
        ttk.Label(opts, text="音色:").pack(side="left")
        self.voice_cb = ttk.Combobox(opts, values=VOICE_NAMES,
                                     state="readonly", width=16)
        self.voice_cb.pack(side="left", padx=(0, 12))
        self.voice_cb.current(0)
        ttk.Label(opts, text="语速:").pack(side="left")
        self.rate_cb = ttk.Combobox(opts, values=RATE_OPTIONS,
                                    state="readonly", width=6)
        self.rate_cb.pack(side="left")
        self.rate_cb.current(3)  # +0%

        # 结果区
        res = ttk.LabelFrame(self.root, text="查询结果")
        res.pack(fill="x", **pad)
        self.lbl_word = ttk.Label(res, text="—", font=("Segoe UI", 13), wraplength=480)
        self.lbl_word.pack(anchor="w", **pad)
        self.lbl_stress = ttk.Label(res, text="—", font=("Segoe UI", 14, "bold"),
                                    foreground="#0b5cad", wraplength=480)
        self.lbl_stress.pack(anchor="w", **pad)
        self.lbl_ipa = ttk.Label(res, text="—", font=("Segoe UI", 12),
                                 foreground="#6a1b9a", wraplength=480)
        self.lbl_ipa.pack(anchor="w", **pad)
        self.lbl_zh = ttk.Label(res, text="", font=("Microsoft YaHei", 11),
                                foreground="#b45309", wraplength=480, justify="left")
        self.lbl_zh.pack(anchor="w", **pad)
        self.lbl_en = ttk.Label(res, text="", font=("Segoe UI", 10),
                                foreground="#666", wraplength=480, justify="left")
        self.lbl_en.pack(anchor="w", **pad)

        btns = ttk.Frame(res)
        btns.pack(anchor="w", **pad)
        self.btn_tts = ttk.Button(btns, text="▶ 标准发音", command=self.on_play_tts,
                                  state="disabled")
        self.btn_tts.pack(side="left", padx=(0, 8))
        self.btn_native = ttk.Button(btns, text="▶ 真人发音", command=self.on_play_native,
                                     state="disabled")
        self.btn_native.pack(side="left")

        self.status = ttk.Label(self.root, text="", foreground="#666")
        self.status.pack(anchor="w", **pad)

        # 历史记录
        hist = ttk.LabelFrame(self.root, text="历史记录")
        hist.pack(fill="both", expand=True, **pad)
        self.hist_list = tk.Listbox(hist, font=("Segoe UI", 11))
        self.hist_list.pack(side="left", fill="both", expand=True, padx=(10, 4), pady=6)
        self.hist_list.bind("<Double-Button-1>", self._on_hist_double)
        hbar = ttk.Scrollbar(hist, command=self.hist_list.yview)
        hbar.pack(side="right", fill="y", pady=6)
        self.hist_list.config(yscrollcommand=hbar.set)
        hbtns = ttk.Frame(hist)
        hbtns.pack(side="right", fill="y", pady=6)
        ttk.Button(hbtns, text="回填", command=self._on_hist_fill).pack(side="top", pady=2)
        ttk.Button(hbtns, text="清空", command=self.clear_history).pack(side="top", pady=2)

    # ---------- 查询 ----------
    def on_query(self):
        word = self.entry.get().strip()
        if not word:
            messagebox.showinfo("提示", "请输入俄语单词")
            return
        self.btn_query.config(state="disabled")
        self.status.config(text="查询中…")
        threading.Thread(target=self._query_worker, args=(word,), daemon=True).start()

    def _query_worker(self, word):
        err = None
        result = None
        try:
            stressed = core.add_stress(word)
            wikt = core.fetch_wiktionary(word) or {}
            local = core._load_local_dict().get(core._strip_accent(word)) or {}
            result = {
                "word": word,
                "stressed": stressed,
                "has_stress": stressed != word,
                "ipa": wikt.get("ipa"),
                "ogg": wikt.get("ogg"),
                "zh": local.get("zh", []),
                "en": local.get("en", []),
            }
        except Exception as e:
            err = str(e)
        self.root.after(0, self._query_done, result, err)

    def _query_done(self, result, err):
        self.btn_query.config(state="normal")
        if err or not result:
            self.status.config(text="查询失败: %s" % (err or "未知错误"))
            return
        self.current = result
        self.lbl_word.config(text="单词:  " + result["word"])
        if result["has_stress"]:
            self.lbl_stress.config(text="重音:  " + result["stressed"])
        else:
            self.lbl_stress.config(text="重音:  (未标出) " + result["stressed"])
        if result["ipa"]:
            self.lbl_ipa.config(text="IPA:   /" + result["ipa"] + "/")
        else:
            self.lbl_ipa.config(text="IPA:   —")
        self.lbl_zh.config(text=("中文:  " + "；".join(result["zh"])) if result["zh"] else "")
        self.lbl_en.config(text=("英文:  " + "；".join(result["en"])) if result["en"] else "")
        self.btn_tts.config(state="normal")
        self.btn_native.config(state="normal" if result["ogg"] else "disabled")
        self.status.config(text="查询完成" + ("（含真人发音）" if result["ogg"] else ""))
        self._add_history(result["word"], result["stressed"])

    # ---------- 发音 ----------
    def _voice_key(self):
        idx = self.voice_cb.current()
        return VOICE_KEYS[idx] if 0 <= idx < len(VOICE_KEYS) else VOICE_KEYS[0]

    def on_play_tts(self):
        if not self.current:
            return
        word = self.current["stressed"]
        voice = self._voice_key()
        rate = self.rate_cb.get()
        self.btn_tts.config(state="disabled")
        self.status.config(text="正在合成发音…")
        threading.Thread(target=self._tts_worker, args=(word, voice, rate), daemon=True).start()

    def _tts_worker(self, word, voice, rate):
        err = None
        data = None
        try:
            buf = asyncio.run(core.synth_mp3(word, voice, rate))
            data = buf.read()
        except Exception as e:
            err = str(e)
        self.root.after(0, self._play_done, data, ".mp3", err)

    def on_play_native(self):
        if not self.current or not self.current.get("ogg"):
            return
        ogg = self.current["ogg"]
        self.btn_native.config(state="disabled")
        self.status.config(text="正在下载真人发音…")
        threading.Thread(target=self._native_worker, args=(ogg,), daemon=True).start()

    def _native_worker(self, ogg):
        err = None
        data = None
        try:
            path = core.get_native_audio_path(ogg)
            if path:
                with open(path, "rb") as f:
                    data = f.read()
            else:
                err = "本地未找到真人发音"
        except Exception as e:
            err = str(e)
        self.root.after(0, self._play_done, data, ".mp3", err)

    def _play_done(self, data, suffix, err):
        self.btn_tts.config(state="normal")
        if self.current:
            self.btn_native.config(state="normal" if self.current.get("ogg") else "disabled")
        if err or not data:
            self.status.config(text="播放失败: %s" % (err or "无数据"))
            return
        try:
            play_bytes(data, suffix)
            self.status.config(text="播放中…")
        except Exception as e:
            self.status.config(text="播放失败: %s" % str(e))

    # ---------- 历史记录 ----------
    def _load_history(self):
        try:
            with open(HISTORY_FILE, encoding="utf-8") as f:
                self._history = json.load(f)
        except Exception:
            self._history = []
        self._refresh_hist()

    def _add_history(self, word, stressed):
        self._history = [it for it in self._history if it.get("word") != word]
        self._history.insert(0, {"word": word, "stressed": stressed})
        self._history = self._history[:100]
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self._history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        self._refresh_hist()

    def _refresh_hist(self):
        self.hist_list.delete(0, "end")
        for it in self._history:
            self.hist_list.insert("end", "  " + it["word"] + "  →  " + it["stressed"])

    def clear_history(self):
        self._history = []
        try:
            os.remove(HISTORY_FILE)
        except Exception:
            pass
        self._refresh_hist()

    def _on_hist_fill(self):
        sel = self.hist_list.curselection()
        if not sel:
            return
        it = self._history[sel[0]]
        self.entry.delete(0, "end")
        self.entry.insert(0, it["word"])

    def _on_hist_double(self, event):
        self._on_hist_fill()
        self.on_query()


def main():
    if _HAS_PYGAME:
        try:
            pygame.mixer.init()
        except Exception:
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
