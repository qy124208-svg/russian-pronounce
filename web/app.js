"use strict";

/* ---------- 工具 ---------- */
const $ = (id) => document.getElementById(id);

function stripAccent(s) {
  return s.replace(/́/g, "").toLowerCase();
}

/* ---------- 查词 ---------- */
let current = null; // { word, stressed, ipa, audio }

async function lookup(word) {
  const w = stripAccent(word);
  if (!w) return null;
  // 取前两个字母作为分片键
  const k2 = w.slice(0, 2);
  try {
    const res = await fetch("dict/" + encodeURIComponent(k2) + ".json");
    if (!res.ok) return null;
    const data = await res.json();
    return data[w] || null;
  } catch (e) {
    return null;
  }
}

/* ---------- 标准发音（浏览器 TTS）---------- */
let ruVoice = null;
function loadVoices() {
  const vs = speechSynthesis.getVoices();
  ruVoice =
    vs.find((v) => v.lang === "ru-RU") ||
    vs.find((v) => v.lang.toLowerCase().startsWith("ru")) ||
    null;
}
if ("speechSynthesis" in window) {
  loadVoices();
  speechSynthesis.onvoiceschanged = loadVoices;
}

function speak(text) {
  if (!("speechSynthesis" in window)) {
    setStatus("当前浏览器不支持语音合成");
    return;
  }
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "ru-RU";
  if (ruVoice) u.voice = ruVoice;
  u.rate = 0.9;
  speechSynthesis.speak(u);
}

/* ---------- 真人发音 ---------- */
function playNative(audio) {
  // audio 形如 "Ru-привет.ogg"，转码后为 "Ru-привет.mp3"
  const mp3 = audio.replace(/\.ogg$/i, ".mp3");
  const url = "audios/" + encodeURIComponent(mp3);
  const a = new Audio(url);
  a.onerror = () => setStatus("真人发音加载失败");
  a.play().catch(() => setStatus("真人发音播放失败"));
  setStatus("正在播放真人发音…");
}

/* ---------- UI ---------- */
function setStatus(msg) {
  $("status").textContent = msg;
}

function showResult(entry, rawWord) {
  current = entry;
  $("resultCard").style.display = "block";
  $("word").textContent = "单词： " + rawWord;
  if (entry.accent) {
    $("stress").textContent = "重音： " + entry.accent;
  } else {
    $("stress").textContent = "重音： （未标出）" + rawWord;
  }
  $("ipa").textContent = entry.ipa ? "IPA： /" + entry.ipa + "/" : "IPA： —";
  $("btnTts").disabled = false;
  $("btnNative").disabled = !entry.audio;
  if (entry.audio) {
    setStatus("查询完成（含真人发音）");
  } else {
    setStatus("查询完成（无真人发音，可用标准发音）");
  }
}

async function onQuery() {
  const raw = $("input").value.trim();
  if (!raw) {
    setStatus("请输入俄语单词");
    return;
  }
  $("btn").disabled = true;
  setStatus("查询中…");
  try {
    const entry = await lookup(raw);
    if (entry) {
      showResult(entry, raw);
      addHistory(raw, entry.accent || raw);
    } else {
      $("resultCard").style.display = "none";
      setStatus("未收录该词，试试其他拼写");
    }
  } catch (e) {
    setStatus("查询出错");
  } finally {
    $("btn").disabled = false;
  }
}

/* ---------- 历史记录 ---------- */
const HIST_KEY = "russian_pronounce_history";

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HIST_KEY)) || [];
  } catch (e) {
    return [];
  }
}

function addHistory(word, stressed) {
  let h = loadHistory();
  h = h.filter((it) => it.word !== word);
  h.unshift({ word, stressed });
  h = h.slice(0, 50);
  localStorage.setItem(HIST_KEY, JSON.stringify(h));
  renderHistory();
}

function renderHistory() {
  const h = loadHistory();
  const box = $("hist");
  box.innerHTML = "";
  h.forEach((it) => {
    const div = document.createElement("div");
    div.className = "item";
    div.innerHTML =
      '<span class="w">' + it.word + "</span>" +
      '<span class="s">' + it.stressed + "</span>";
    div.onclick = () => {
      $("input").value = it.word;
      onQuery();
    };
    box.appendChild(div);
  });
}

/* ---------- 事件绑定 ---------- */
$("btn").addEventListener("click", onQuery);
$("input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") onQuery();
});
$("btnTts").addEventListener("click", () => {
  if (current) speak(current.accent || $("input").value);
});
$("btnNative").addEventListener("click", () => {
  if (current && current.audio) playNative(current.audio);
});
$("clearBtn").addEventListener("click", () => {
  localStorage.removeItem(HIST_KEY);
  renderHistory();
});

renderHistory();
$("input").focus();
