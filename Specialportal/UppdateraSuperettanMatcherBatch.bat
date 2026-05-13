@echo off
chcp 65001 > nul
title Skapar Superettans Match-Dashboard...

echo ========================================================
echo   Kör Matchdata Dashboard Generator...
echo   Laddar Anaconda-miljon 'gis-env' och bygger HTML.
echo ========================================================
echo.

:: Kör python-skriptet som ligger i undermappen data_pipeline
python data_pipeline\views_superettan.py

echo.
echo ========================================================
echo   Klar! HTML-filen bor nu vara uppdaterad.
echo ========================================================
echo.
pause