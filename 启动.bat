@echo off
chcp 65001 >nul
cd /d %~dp0
echo ==========================================
echo   俄语单词发音查询工具
echo   启动后自动打开 http://127.0.0.1:5000
echo   关闭本窗口即停止服务
echo ==========================================
start "" /min cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:5000"
python app.py
pause
