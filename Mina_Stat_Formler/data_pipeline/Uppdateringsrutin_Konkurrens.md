LATHUND: Årlig uppdatering av Konkurrenskraftsindex

Denna rutin beskriver steg för steg hur du uppdaterar indexkalkylatorn med ny statistik för ett nytt år. Hela processen tar bara några minuter om datan är förberedd.

📁 Inblandade filer

Källdata: excel_filer/konkurrenskraft_index.xlsx

Motor: bygg_konkurrens_data.py

Systemfiler (genereras auto): konkurrens_data.csv och konkurrens_vikter.csv

Gränssnitt: konkurrens_index.html

STEG 1: Uppdatera källdatan i Excel

Öppna källfilen konkurrenskraft_index.xlsx.

Gå igenom flik för flik (indikator för indikator).

Lägg till en ny kolumn längst till höger för det nya året (t.ex. 2025).

Klistra in den nya statistiken för kommunerna och Riket.

Viktigt: Lämna cellen tom, eller skriv .. om data saknas för en specifik kommun det året.

Fliken "Standardvikt": Om du vill ändra någon standardvikt i mallarna, lägga till en beskrivning eller ändra kategori, gör du det här.

Spara och stäng Excel-filen.

STEG 2: Kör Python-skriptet (Bygg om databasen)

Gränssnittet på webben kan inte läsa Excel direkt, så vi måste låta Python bygga om datan till webbanpassade CSV-filer.

Öppna mappen i Visual Studio Code (VS Code).

Öppna filen bygg_konkurrens_data.py.

Kör skriptet (klicka på "Play"-knappen högst upp till höger, eller högerklicka och välj "Run Python File in Terminal").

Kolla i terminalen (längst ner i VS Code). Du ska se meddelanden som:

✅ Sparade konkurrens_vikter.csv

✅ Sparade konkurrens_data.csv

Klart! Totalt X datapunkter processades.

STEG 3: Kontrollera lokalt (Kvalitetssäkring)

Innan vi skickar ut detta på nätet ska vi se att allt ser bra ut.

Öppna konkurrens_index.html i din webbläsare (dubbelklicka på filen i Utforskaren, eller använd Live Server i VS Code).

Kolla filtren: Finns det nya året med i rullistorna "Visa graf från år" och "Till år"?

Kolla grafen: Ser linjerna rimliga ut för det nya året? Inga plötsliga spikar som tyder på felinmatad data i Excel?

Testa extrapolering: Klicka på knappen "🚀 Extrapolera" för att se att systemet kan räkna fram prognosen korrekt med det nya datat.

STEG 4: Publicera till GitHub

När allt ser bra ut lokalt är det dags att uppdatera webbversionen.

Gå till fliken Source Control (Källhantering) i VS Code (ikonen med tre noder).

Titta under "Changes" (Ändringar). Du ska se minst dessa filer:

konkurrenskraft_index.xlsx (M)

konkurrens_data.csv (M)

konkurrens_vikter.csv (M)

(Tips: Om CSV-filerna INTE syns trots att du kört Python-skriptet, stäng ner VS Code helt och starta om det. Det tvingar programmet att hitta de nya filerna).

Skriv ett meddelande i rutan "Message", t.ex.: Årlig datauppdatering för 2025 inlagd.

Klicka på Commit.

Klicka på Sync Changes (eller Push) för att skicka ändringarna till GitHub.

Klart! Efter några minuter är den nya datan live på den publika länken.


Kompletterande steg vid behov. 
Ta fram ”New terminal” i VS Code
…och klistra in nedanstående kod i terminalrutan
git push -u origin main
