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

/* ---------- 标准发音（Edge-TTS，微软接口，国内直连可用）---------- */
const EDGE_VOICE = "ru-RU-SvetlanaNeural";
const EDGE_FMT = "audio-24khz-48kbitrate-mono-mp3";

function uuid() {
  return (crypto.randomUUID && crypto.randomUUID()) || (Date.now() + "-" + Math.random());
}

function escXml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// 通过 Edge-TTS WebSocket 合成语音，成功回调 Blob(mp3)，失败回调 onError
function edgeTTS(text, onBlob, onError) {
  const wsUrl = "wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1" +
    "?TrustedClientToken=6A5AA1D4EAFF4E9FB37E23D68491D6F4&ConnectionId=" + uuid();
  let ws;
  try {
    ws = new WebSocket(wsUrl);
  } catch (e) {
    onError();
    return;
  }
  ws.binaryType = "arraybuffer";
  const chunks = [];
  let ended = false;
  const now = () => new Date().toISOString();

  ws.onopen = () => {
    const cfg = "X-Timestamp:" + now() + "\r\nContent-Type:application/json; charset=utf-8\r\nPath:speech.config\r\n\r\n" +
      '{"context":{"synthesis":{"audio":{"metadataoptions":{"sentenceBoundaryEnabled":"false","wordBoundaryEnabled":"false"},"outputFormat":"' + EDGE_FMT + '"}}}}';
    ws.send(cfg);
    const ssml = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='ru-RU'>" +
      "<voice name='" + EDGE_VOICE + "'><prosody pitch='+0Hz' rate='+0%' volume='+0%'>" +
      escXml(text) + "</prosody></voice></speak>";
    const msg = "X-RequestId:" + uuid() + "\r\nContent-Type:application/ssml+xml\r\nX-Timestamp:" + now() + "Path:ssml\r\n\r\n" + ssml;
    ws.send(msg);
  };

  ws.onmessage = (e) => {
    if (ended) return;
    if (typeof e.data === "string") {
      if (e.data.indexOf("Path:turn.end") >= 0) {
        ended = true;
        ws.close();
        if (chunks.length) onBlob(new Blob(chunks, { type: "audio/mpeg" }));
        else onError();
      }
      return;
    }
    const bytes = new Uint8Array(e.data);
    let sep = -1;
    for (let i = 0; i < bytes.length - 3; i++) {
      if (bytes[i] === 13 && bytes[i + 1] === 10 && bytes[i + 2] === 13 && bytes[i + 3] === 10) {
        sep = i + 4;
        break;
      }
    }
    if (sep > 0 && sep < bytes.length) {
      const head = new TextDecoder().decode(bytes.slice(0, sep));
      if (head.indexOf("Path:audio") >= 0) {
        chunks.push(bytes.slice(sep));
      }
    }
  };

  ws.onerror = () => {
    if (!ended) {
      ended = true;
      onError();
    }
  };
}

function speak(text) {
  setStatus("正在生成标准发音…");
  edgeTTS(text, (blob) => {
    const url = URL.createObjectURL(blob);
    const a = new Audio(url);
    a.onended = () => { try { URL.revokeObjectURL(url); } catch (e) {} };
    a.play().then(() => setStatus("正在播放标准发音…")).catch(() => setStatus("标准发音播放失败"));
  }, () => {
    // Edge-TTS 失败兜底：退回浏览器 TTS（部分环境可能无声）
    if (!("speechSynthesis" in window)) {
      setStatus("标准发音生成失败");
      return;
    }
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "ru-RU";
    speechSynthesis.speak(u);
  });
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
