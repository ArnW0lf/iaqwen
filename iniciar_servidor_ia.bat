@echo off
title Servidor IA MiClub (Qwen 2.5)
echo ==============================================
echo   Iniciando Servidor de IA MiClub (Qwen 2.5)
echo   Puerto: http://localhost:8000
echo ==============================================
cd /d "%~dp0"
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
