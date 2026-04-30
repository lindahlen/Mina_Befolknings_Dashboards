@echo off
chcp 65001 > nul
title Skapar Allsvensk Match-Dashboard...

echo ========================================================
echo   Kör Matchdata Dashboard Generator...
echo   Laddar Anaconda-miljon 'gis-env' och bygger HTML.
echo ========================================================
echo.

:: Aktivera Anaconda-miljön (gis-env)
call conda activate gis-env

:: Kör python-skriptet som ligger i undermappen data_pipeline
python data_pipeline\views_matchdata.py

echo.
echo ========================================================
echo   Klar! HTML-filen bor nu vara uppdaterad.
echo ========================================================
echo.
pause