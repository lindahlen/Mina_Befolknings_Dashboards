Manual: Uppdatering och publicering av SEI-kartor för Linköping

Denna guide beskriver hur du uppdaterar, genererar och publicerar de två interaktiva analytikerkartorna för Linköpings kommun:

SEI-karta Hela Kommunen (Linkoping_SEI_Map.py)

SEI-karta Staden (Linkoping_Staden_Karta.py)

Båda kartorna bygger på Python-skript som läser in lokal data (Excel, CSV, GeoJSON) och spottar ut snabba, komprimerade HTML-filer tillsammans med tillhörande JavaScript-datafiler.

1. Mappstruktur

För att skripten ska fungera felfritt måste följande mappstruktur upprätthållas. Skripten utgår från att de ligger i en undermapp (t.ex. data_pipeline) till huvudmappen.

📁 Huvudmapp (t.ex. Kartor)
 ├── 📁 data_pipeline          <-- Här ligger dina Python-skript (.py)
 │    ├── Linkoping_SEI_Map.py
 │    └── Linkoping_Staden_Karta.py
 │
 ├── 📁 excel_filer            <-- Här lägger du all tabell-data
 │    ├── SEI_utdrag.xlsx
 │    ├── befolkning_och_platser.xlsx
 │    └── BefKoord2025.csv     <-- Årets adresspunkter
 │
 ├── 📁 kart_filer             <-- Här lägger du all geografisk data
 │    ├── NYKO4v23.geojson
 │    ├── transportleder.geojson
 │    ├── vattendrag.geojson
 │    └── stangastadensomr.geojson
 │
 ├── 📁 kart_data              <-- AUTOGENERERAS av "Hela kommunen"-skriptet
 ├── 📁 kart_data_staden       <-- AUTOGENERERAS av "Staden"-skriptet
 ├── 📁 Img                    <-- Logotyper (t.ex. Linkopingsloggo.png)
 │
 ├── Linkoping_Analys_Nyko4.html  <-- AUTOGENERERAD slutprodukt 1
 └── Linkoping_SEI_Staden.html    <-- AUTOGENERERAD slutprodukt 2


2. Årlig uppdatering (Steg-för-steg)

När det är dags för ett nytt kalenderår och ny data har inkommit, följ dessa steg:

Steg 2.1: Uppdatera datakällorna i excel_filer

Byt ut adresspunkterna: Spara ner den nya CSV-filen med befolkningskoordinater (t.ex. BefKoord2026.csv). Se till att filen är semikolonavseparerad (;) och att teckenkodningen är korrekt (helst UTF-8).

Uppdatera Excel-filerna: Lägg in ny data i SEI_utdrag.xlsx och befolkning_och_platser.xlsx.

⚠️ VIKTIGT OM KOLUMNNAMN: Python-koden letar efter specifika rubriker. Ändra inte på kolumnnamn som Totalt_uppl, 19-64_år, Organisation, X_koordinat, Y_koordinat eller fliknamn (Basområden, Skolor, Vårdboende etc.) utan att också ändra i Python-koden.

Steg 2.2: Justera variabler i Python-kripten

Öppna båda Python-skripten (Linkoping_SEI_Map.py och Linkoping_Staden_Karta.py) i din kodredigerare.
Högst upp i koden hittar du avsnittet för inställningar:

# 🛑 ÄNDRA ÅRTAL OCH FILNAMN HÄR NÄSTA ÅR! 🛑
# --------------------------------------------------
GEOJSON_NYKO4_FILENAME = 'NYKO4v23.geojson' 
PUNKT_DATA_FILNAMN = 'BefKoord2026.csv'      # Ändra till det nya filnamnet
PUNKT_DATA_AR = "2026"                       # Ändra till det nya årtalet
EXCLUDE_146300 = True                        # Ändra till False om denna yta ska med
# --------------------------------------------------


Gör denna ändring i båda filerna.

Steg 2.3: Kör skripten

Kör Linkoping_SEI_Map.py.

Skriptet tuggar igenom all data, genererar JS-filerna i kart_data och skapar Linkoping_Analys_Nyko4.html.

Kör Linkoping_Staden_Karta.py.

Skriptet tuggar igenom all data (filtrerar på staden), genererar JS-filerna i kart_data_staden och skapar Linkoping_SEI_Staden.html.

3. Hantering av Geografin (Nyko & Områden)

Koordinatsystem: Både adresspunkterna (CSV) och GeoJSON-filerna bör vara i, eller automatiskt kunna tolkas från, SWEREF 99 TM (EPSG:3006) (Y-koordinat kring 530 000, X-koordinat kring 6.4 miljoner). Python sköter konverteringen till webb-standard (WGS84 / EPSG:4326) automatiskt.

Filtrering av Staden: Linkoping_Staden_Karta.py använder kolumnen SUBTYP ("Stadsdelar") i GeoJSON-filen, samt en manuell lista över KOD-nummer för att veta vad som är "Staden" och Malmslätt. Om Linköpings stadsgränser expanderar i framtiden måste KOD-listan i funktionen filter_staden_row() uppdateras.

Rita egna ytor: Om du drar ytor med ritverktyget och demografin verkar skev beror det oftast på att BefKoord-filen saknar adresspunkter just där, eller att koordinaterna i CSV-filen är felformaterade.

4. Publicering på Webb / GitHub

När skripten har körts och du har två färdiga HTML-filer är det dags att publicera dem (t.ex. via GitHub Pages eller en intern webbserver).

Eftersom kartorna är byggda med prestanda i åtanke laddas ingen data inuti HTML-filerna. Du måste ladda upp hela mappstrukturen för att kartan inte ska bli blank.

Följande filer/mappar MÅSTE laddas upp tillsammans:

Linkoping_Analys_Nyko4.html

Linkoping_SEI_Staden.html

Mappen kart_data/ (med allt dess innehåll)

Mappen kart_data_staden/ (med allt dess innehåll)

Mappen Img/ (för logotypen)

💡 Felsökning vid uppdatering

Ser du inte de nya siffrorna på webben, trots att du laddat upp nya filer?
Det beror på Cachning. Webbläsaren (Chrome/Edge) har sparat de gamla .js-filerna i minnet för att ladda snabbare.

Lösning: Tvinga webbläsaren att hämta de nya filerna genom att trycka Ctrl + F5 (eller Cmd + Shift + R på Mac) på webbsidan.


Tänk på vid publicering GitHub...
Efter att ha tryckt på knappen Commit 
skriv i terminalen in...
git push -u origin main