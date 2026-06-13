import pdfplumber
import pandas as pd
import re
import os
import csv
import logging

# Tysta onödiga font-varningar från pdfminer som spammar terminalen
logging.getLogger("pdfminer").setLevel(logging.ERROR)

# =========================================================
# SÄKERSTÄLL RÄTT ARBETSKATALOG (Fix för VS Code)
# =========================================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
    print(f"📁 Arbetskatalog satt till: {os.getcwd()}")
except NameError:
    pass

# Inställningar
PDF_FILE = "SquadLists-English2026WC.pdf"
CSV_OUTPUT = "trupper_2026.csv"

def clean_str(val):
    """Säker sanering av all text för att undvika CSV-krascher."""
    if val is None:
        return ""
    s = str(val)
    s = s.replace('\x00', '') # Tar bort NUL-bytes som kraschar CSV
    s = "".join(c for c in s if c.isprintable()) # Tar bort dolda kontrolltecken
    s = re.sub(r'\s+', ' ', s) # Normaliserar alla spaces/radbrytningar
    return s.strip()

def parse_fifa_squads(pdf_path, output_csv):
    """
    Läser in FIFAs officiella Squad List (PDF) och extraherar all data.
    Använder datum-ankare och unik-ord-sortering för att parera trasiga kolumner.
    """
    if not os.path.exists(pdf_path):
        print(f"❌ Hittar inte filen {pdf_path}. Se till att den ligger i samma mapp som skriptet.")
        return

    print(f"📖 Läser in sidor från {pdf_path} (Detta kan ta en liten stund)...")
    
    data = []
    current_country = "Okänt Land"
    
    # Öppna PDF:en
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            
            # 1. Hitta Landsnamnet på sidan
            if text:
                for line in text.split('\n'):
                    if '(' in line and ')' in line and "WORLD CUP" not in line and "SQUAD LIST" not in line:
                        cmatch = re.search(r'([A-Za-z\s\-\']+)\s\([A-Z]{3}\)', line)
                        if cmatch:
                            current_country = cmatch.group(1).strip()
                            break

            # 2. Extrahera tabellerna
            tables = page.extract_tables()
            if not tables:
                continue
                
            for table in tables:
                for row in table:
                    if not row: continue
                    
                    # 3. Tokrensa raden från skräptecken direkt
                    clean_row = [clean_str(c) for c in row]
                    clean_row = [c for c in clean_row if c] # Ta bort tomma celler
                    
                    if len(clean_row) < 3:
                        continue
                        
                    # Avbryt om vi når coach-sektionen i slutet av ett lag
                    if any("COACH" in c.upper() for c in clean_row[:2]):
                        continue
                        
                    # 4. HITTA ANKARET: Födelsedatumet (DD/MM/YYYY)
                    dob_idx = -1
                    dob_val = ""
                    for idx, cell in enumerate(clean_row):
                        match = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', cell)
                        if match:
                            dob_val = match.group(1)
                            dob_idx = idx
                            break
                            
                    # Om det inte är en spelarrad (inget datum hittades) hoppar vi över den
                    if dob_idx == -1:
                        continue
                        
                    # 5. Mappa Klubben
                    club = ""
                    # Om klubben sitter ihop med datumet i samma cell
                    if len(clean_row[dob_idx]) > 10:
                        club = clean_row[dob_idx].replace(dob_val, '').strip()
                    # Annars är klubben i cellen efter datumet
                    elif dob_idx + 1 < len(clean_row):
                        club = clean_row[dob_idx+1]
                        
                    club = re.sub(r'\s\d{1,3}\s*$', '', club).strip() # Rensa bort hängande siffror från slutet
                    
                    # 6. Bearbeta Namn, Position och Nummer (allt innan datumet)
                    prefix = " ".join(clean_row[:dob_idx])
                    
                    # Hitta och ta bort position
                    pos_match = re.search(r'\b(GK|DF|MF|FW)\b', prefix, flags=re.IGNORECASE)
                    pos = pos_match.group(1).upper() if pos_match else ""
                    prefix = re.sub(r'\b(GK|DF|MF|FW)\b', '', prefix, flags=re.IGNORECASE)
                    
                    # Hitta och ta bort tröjnummer
                    num_match = re.search(r'\b([1-9]|1[0-9]|2[0-6])\b', prefix)
                    trojnr = num_match.group(1) if num_match else ""
                    prefix = re.sub(r'\b([1-9]|1[0-9]|2[0-6])\b', '', prefix)
                    
                    # Rensa upp namnet: ta bort upprepade ord (t.ex. "MANDI Aissa Aissa MANDI")
                    words = prefix.split()
                    unique_words = []
                    for w in words:
                        if w not in unique_words:
                            unique_words.append(w)
                            
                    final_name = " ".join(unique_words)
                    
                    # FIFAs PDF har ofta Efternamnet i STORA BOKSTÄVER. Vi drar nytta av det!
                    last_names = [w for w in unique_words if w.isupper() and len(w) > 1]
                    first_names = [w for w in unique_words if not (w.isupper() and len(w) > 1)]
                    
                    if last_names:
                        last_name = " ".join(last_names)
                        first_name = " ".join(first_names)
                    else:
                        # Fallback om inga stora bokstäver hittades
                        last_name = unique_words[0] if unique_words else ""
                        first_name = " ".join(unique_words[1:]) if len(unique_words) > 1 else ""

                    anm = "mv" if pos == "GK" else ""
                    fodelsear = dob_val[-4:] if dob_val else ""

                    # Spara endast om vi hittade ett tröjnummer (bekräftar att det är en spelare)
                    if trojnr:
                        data.append({
                            "Land": current_country,
                            "Tröjnr": trojnr,
                            "Namn": final_name,
                            "Förnamn": first_name,
                            "Efternamn": last_name,
                            "Klubb": club,
                            "Födelseår": fodelsear,
                            "Födelsedatum": dob_val,
                            "Anm": anm
                        })
                        
    # 7. Skapa och Spara CSV-filen (Med inbyggda CSV-modulen för total stabilitet)
    with open(output_csv, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = ["Land", "Tröjnr", "Namn", "Förnamn", "Efternamn", "Klubb", "Födelseår", "Födelsedatum", "Anm"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(data)
        
    print(f"✅ Klar! Extraherade {len(data)} spelare och sparade till {output_csv}.")

if __name__ == "__main__":
    parse_fifa_squads(PDF_FILE, CSV_OUTPUT)