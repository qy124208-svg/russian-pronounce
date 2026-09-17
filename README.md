# 俄语单词发音查询工具

输入俄语单词，一键得到 **重音标注 + IPA 音标 + 标准发音 + 真人发音**，适合俄语学习者跟读练习。

## 功能

- 🔤 **重音标注**：自动标注重音（Morpher.ru），标出需要重读的元音
- 📖 **IPA 音标**：显示国际音标（ru.wiktionary.org 移动版直连解析）
- 🔊 **标准发音**：Edge-TTS 神经合成（男声 / 女声，语速可调）
- 🎙️ **真人发音**：俄语母语者录音（Wikimedia Commons `.ogg`）
- 🕘 **历史记录**：自动保存查过的单词，点击回填重新发音，方便复习
- 📱 **响应式界面**：手机 / 平板 / 电脑都能用

## 本地运行

```bash
pip install -r requirements.txt
python app.py
```

打开 http://127.0.0.1:5000（同一 WiFi 下的手机/平板可用局域网 IP 访问）。

Windows 也可直接双击 `启动.bat`。

## 部署到 Render（免费，拿永久网址）

本仓库已包含 `render.yaml`，可一键部署：

1. 把本仓库 push 到 GitHub
2. 注册 [render.com](https://render.com)（可用 GitHub 账号登录）
3. 控制台点 **New → Blueprint**，选择本仓库
4. Render 自动读取 `render.yaml` 完成部署，几分钟后得到 `https://xxx.onrender.com` 永久网址

> 手动部署也可：New → Web Service → 选仓库 → Runtime 选 Python → Build command 填 `pip install -r requirements.txt` → Start command 填 `gunicorn app:app --bind 0.0.0.0:$PORT` → 选 Free 套餐。

## 技术说明

- **无需代理**：所有外部源（重音、IPA、真人发音、TTS）在国内外普通网络均可直连
- 数据源：Morpher.ru（重音）、ru.wiktionary.org 移动版（IPA / .ogg 文件名）、Wikimedia Commons（真人发音文件）、Edge-TTS（合成音）
- `.ogg` 真人发音用文件名 MD5 构造直链，绕开被墙的 API

## 已知限制

- Render 免费实例闲置 15 分钟会休眠，首次访问需等约 30 秒冷启动
- 历史记录存在本地文件，免费实例重启后会清空（不影响核心查询功能）
- 生僻词可能没有 IPA 或真人发音，会自动降级（仍可用重音 + 合成发音）

## 目录结构

```
russian_pronounce/
├── app.py              # Flask 后端（重音 / IPA / 发音 / 历史）
├── templates/
│   └── index.html      # 前端页面
├── requirements.txt    # 依赖
├── render.yaml         # Render 部署配置
├── 启动.bat            # Windows 双击启动
└── README.md
```
