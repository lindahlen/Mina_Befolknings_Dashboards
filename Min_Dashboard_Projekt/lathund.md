# 🚀 Lathund: Uppdatera hemsidan via VS Code & GitHub

Denna lathund beskriver det snabbaste och säkraste sättet att uppdatera mina HTML-filer så att ändringarna syns live på min GitHub Pages-hemsida.

## 🌟 Gyllene Regeln innan du börjar
Öppna **alltid mappen** (`Min_Webb_Dashboard`), aldrig bara enstaka filer.
1. Öppna VS Code.
2. Välj **File > Open Folder...**
3. Leta upp din mapp och tryck på **Välj mapp**.

---

## 🔄 Det vanliga arbetsflödet

### 1. Koda och Spara
* Öppna den HTML-fil (t.ex. `sida2.html`) du vill uppdatera.
* Klistra in din nya iframe eller skriv in din text.
* Tryck **`Ctrl + S`** för att spara. *(Ett "M" för Modified dyker upp bredvid filnamnet i listan).*

### 2. Välj filer och Paketera (Commit)
* Klicka på ikonen för **Source Control** (nätverket med tre noder) i menyn till vänster.
* Klicka på **plustecknet (+)** bredvid de filer du vill skicka upp. (De flyttas nu till *Staged Changes* / Flyttkartongen).
* Filer du *inte* vill skicka upp låter du bara ligga kvar under *Changes*.
* Skriv en kort beskrivning i textrutan överst (t.ex. *"Uppdaterat iframes vecka 8"*).
* Klicka på den blå knappen **Commit**.

### 3. Skicka till webben (Sync)
* Klicka på den blå knappen som nu bytt namn till **Sync Changes**.
* Nere i hörnet snurrar en liten ikon i några sekunder. 
* **Klar!** Inom 1-2 minuter är din webbsida uppdaterad på internet.

---

## 🚑 Felsökning & Räddningsaktioner

### Problem 1: Knappen "Sync Changes" fastnar och snurrar i evighet
Lösning: Tvinga iväg uppladdningen via terminalen.
1. Välj **Terminal > New Terminal** i toppmenyn.
2. Skriv: `git push origin main` och tryck **Enter**.
3. Stäng terminalen med soptunnan (🗑️).

### Problem 2: Git vägrar ladda upp (Krock med ändringar på GitHub)
Om du har ändrat/raderat något direkt på GitHubs hemsida måste du dra ner de ändringarna först, annars blockeras din uppladdning.
1. Öppna terminalen.
2. Lägg dina ofärdiga filer i byrålådan: `git stash`
3. Hämta hem GitHubs uppdatering: `git pull origin main`
4. Lägg tillbaka dina ofärdiga filer på skrivbordet: `git stash pop`
5. Skjut upp ditt nya paket: `git push origin main`

### Problem 3: Fastnat i en konstig text-terminal ("Vim-fällan")
Ibland, särskilt vid en `pull`, öppnar Git ett uråldrigt textprogram i terminalen som saknar vanliga knappar. Det kan stå `Please enter a commit message to explain why this merge is necessary`.
**För att ta dig ut och spara:**
1. Klicka med musen inuti terminalen.
2. Tryck på **`Esc`** (längst upp till vänster på tangentbordet).
3. Skriv in exakt detta: **`:wq`** (Kolon, w, q).
4. Tryck på **Enter**. Fönstret stängs och processen fortsätter!