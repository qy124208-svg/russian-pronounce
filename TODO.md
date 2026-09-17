# 俄语发音查询工具 — 待办清单

## ✅ 已完成
- [x] Edge-TTS 俄语发音（男/女声、语速可调）
- [x] Morpher.ru 自动标注重音
- [x] Flask 网页界面
- [x] 双击启动脚本（启动.bat）
- [x] 局域网可访问（host 0.0.0.0 + 显示局域网 IP）
- [x] 历史查询记录（后端 + 前端展示/点击回填/清空）
- [x] IPA 音标显示（m.wiktionary 移动版页面直连解析）
- [x] 真人发音（Wiktionary .ogg，MD5 构造 Commons 直链）

## ⬜ 待办
- [ ] **桌面 GUI**（tkinter 输入框 + 按钮）
- [ ] **公网分享**（内网穿透 cloudflared/ngrok，局域网已可用）

## 备注
- 重音来源：Morpher.ru addstressmarks（免费，已验证）
- 发音来源：Edge-TTS（免费，已验证）
- IPA 来源：ru.m.wiktionary.org 移动版页面直连解析 `<span class="IPA">`（桌面版/API 被墙 403）
- 真人发音：Wiktionary .ogg，用文件名 MD5 构造 upload.wikimedia.org 直链（绕开被墙的 imageinfo API）
- 代理坑：requests 读 Windows 系统代理（127.0.0.1:7890），代理未开时 Morpher 报 ProxyError；已做「代理→直连」双通道 fallback + 降级返回原词
