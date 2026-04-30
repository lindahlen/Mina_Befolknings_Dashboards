@echo off
echo ==========================================
echo Uppdaterar Svensk Fotbollshistoria Dashboard
echo ==========================================
echo.
	
python data_pipeline\SkapaSerietabeller_Maraton.py

echo.
echo.
echo Allt klart! Du kan nu staenga detta fönster och oeffna/ladda om HTML-filen.
pause