@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Instalando dependencias (so na primeira vez demora)...
python -m pip install -q -r requirements.txt
echo Abrindo o app...
python -m streamlit run app.py
pause
