import os
import sys
import pandas as pd
import numpy as np
import re

# ==========================================
# 1. GENERELL SETUP (Dynamiska absoluta sökvägar)
# ==========================================
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    csv_dir = os.path.join(project_root, "csv_filer")
    excel_dir = os.path.join(project_root, "excel_filer")
    
    if not os.path.exists(csv_dir): os.makedirs(csv_dir)
    if not os.path.exists(excel_dir): os.makedirs(excel_dir)

    print(f"📁 Skript körs från: {script_dir}")
    
except NameError:
    print("⚠️ Kunde inte sätta arbetsmapp via __file__.")
    csv_dir = "csv_filer"
    excel_dir = "excel_filer"

# ==========================================
# 2. HJÄLPFUNKTIONER: TEXT, NAMN OCH DATUM
# ==========================================
encoding_fix = {
    'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
    'Ã©': 'é', 'Ã¨': 'è', 'Ã‰': 'É', "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö"
}

def fix_text(text):
    if pd.isna(text) or not isinstance(text, str): return text
    for bad, good in encoding_fix.items():
        text = text.replace(bad, good)
    return text.strip()

def parse_name_column(name_string):
    """
    Extraherar målvaktsstatus, nationalitet och alias. 
    Hanterar extremfall som '-mv', '*USA/TOG*', '*SWE/LBR', '*R' och 'NGABU*COD*'.
    """
    if pd.isna(name_string):
        return pd.Series([np.nan, "Nej", "SWE", np.nan])
    
    original_name = str(name_string)
    
    # 1. Identifiera Målvakt (-mv eller mv inom parentes)
    is_gk = "Nej"
    if re.search(r'-\s*mv|\(\s*mv\s*\)', original_name, re.IGNORECASE):
        is_gk = "Ja"
        original_name = re.sub(r'-\s*mv|\(\s*mv\s*\)', '', original_name, flags=re.IGNORECASE)
    
    # 2. Extrahera nationalitet
    nat_match = re.search(r'\*([A-Za-z\s/]+)', original_name)
    nationality = "SWE"
    if nat_match:
        nationality = nat_match.group(1).strip().upper()
    
    # 3. Extrahera alias
    alias_match = re.search(r'\((.+)\)', original_name)
    alias = np.nan
    if alias_match:
        alias = alias_match.group(1).replace('(', '').replace(')', '').strip()
    
    # 4. Tvätta fram det rena namnet
    clean_name = original_name
    clean_name = re.sub(r'\*[A-Za-z\s/]+\*?', '', clean_name)
    clean_name = re.sub(r'\(.+\)', '', clean_name)
    
    # Slutputsning: ta bort ensamma stjärnor, plus-tecken och fixa dubbla mellanslag
    clean_name = clean_name.replace('*', '').replace('+', '').strip()
    
    # Ta bort avslutande kommatecken (t.ex. för brassar med artistnamn)
    clean_name = clean_name.rstrip(',')
    
    # Fixa dubbla mellanslag
    clean_name = re.sub(r'\s+', ' ', clean_name).strip()
    
    return pd.Series([clean_name, is_gk, nationality, alias])

def format_birth_date(date_str, tid_str):
    """
    Konverterar formatet YYMMDD till YYYY-MM-DD för FÖDELSEDATUM.
    Kikar på 'Tid' för att säkerställa att de var i rimlig fotbollsålder (12-65).
    """
    if pd.isna(date_str): return np.nan
    date_str = str(date_str).strip()
    
    if len(date_str) != 6 or not date_str.isdigit():
        return date_str
        
    yy, mm, dd = date_str[:2], date_str[2:4], date_str[4:]
    yy_int = int(yy)
    
    active_year = None
    if pd.notna(tid_str):
        match = re.search(r'\d{4}', str(tid_str))
        if match:
            active_year = int(match.group(0))
            
    if active_year:
        best_century = 1900
        for century in [1800, 1900, 2000]:
            birth_year = century + yy_int
            age = active_year - birth_year
            if 12 <= age <= 65:  # Utökad marginal för extremfall
                best_century = century
                break
        yyyy = str(best_century + yy_int)
    else:
        yyyy = "19" + yy if yy_int > 20 else "20" + yy
        
    return f"{yyyy}-{mm}-{dd}"

def format_death_date(date_str, birth_date_str, tid_str):
    """
    Konverterar formatet YYMMDD till YYYY-MM-DD för DÖDSDATUM.
    Kikar i första hand på Född-datumet för att hitta rätt århundrade (ska vara > 14 och < 115 år gammal).
    """
    if pd.isna(date_str): return np.nan
    date_str = str(date_str).strip()
    
    if len(date_str) != 6 or not date_str.isdigit():
        return date_str
        
    yy, mm, dd = date_str[:2], date_str[2:4], date_str[4:]
    yy_int = int(yy)
    
    # Utgå från födelseår om vi har det
    b_year = None
    if pd.notna(birth_date_str) and len(str(birth_date_str)) >= 4 and str(birth_date_str)[:4].isdigit():
        b_year = int(str(birth_date_str)[:4])
        
    # Som fallback, utgå från aktivt år
    active_year = None
    if pd.notna(tid_str):
        match = re.search(r'\d{4}', str(tid_str))
        if match:
            active_year = int(match.group(0))

    best_century = 1900
    for century in [1800, 1900, 2000]:
        death_year = century + yy_int
        
        if b_year:
            # Rimlig ålder för att dö om de spelat i Allsvenskan: 14 till 115 år
            if 14 <= (death_year - b_year) <= 115:
                best_century = century
                break
        elif active_year:
            # Fallback: dog troligen mellan (aktivt år - 5) och (aktivt år + 80)
            if -5 <= (death_year - active_year) <= 80:
                best_century = century
                break

    yyyy = str(best_century + yy_int)
    return f"{yyyy}-{mm}-{dd}"

# ==========================================
# 3. HUVUDPROCESS: DATATVÄTT
# ==========================================
def clean_allsvenskan_data(input_file, output_xlsx, output_csv):
    print(f"⏳ Läser in {input_file}...")
    try:
        df = pd.read_excel(input_file, dtype=str, engine='openpyxl')
    except FileNotFoundError:
        print(f"❌ Hittade inte filen:\n{input_file}\nDubbelkolla att den ligger i 'excel_filer'.")
        return

    print("🧹 Städning påbörjad...")

    # 1. Text-fix (Encoding)
    for col in ['Namn', 'Klubb', 'Tid', 'Anteckningar']:
        if col in df.columns:
            df[col] = df[col].apply(fix_text)

    # 2. SÄKER Forward Fill (Ny logik för att undvika smitta av dödsdatum)
    if 'Nr' in df.columns:
        df['Nr'] = df['Nr'].replace(r'^\s*$', np.nan, regex=True).ffill()
    if 'Namn' in df.columns:
        df['Namn'] = df['Namn'].replace(r'^\s*$', np.nan, regex=True).ffill()

    if 'Född' in df.columns:
        df['Född'] = df['Född'].replace(r'^\s*$', np.nan, regex=True)
        df['Född'] = df.groupby('Nr')['Född'].ffill()
        
    if 'Avled' in df.columns:
        df['Avled'] = df['Avled'].replace(r'^\s*$', np.nan, regex=True)
        df['Avled'] = df.groupby('Nr')['Avled'].ffill()

    # 3. Kasta bort alla summarader OCH "FEL"-rader (Kikar i både 'Klubb' och 'Tid')
    if 'Klubb' in df.columns:
        df = df[~df['Klubb'].str.lower().str.contains('summa', na=False)]
        # Kastar bort rader där klubb enbart är "FEL" (okänsligt för skiftläge och blanksteg)
        df = df[df['Klubb'].astype(str).str.strip().str.upper() != 'FEL']
    if 'Tid' in df.columns:
        df = df[~df['Tid'].str.lower().str.contains('summa', na=False)]

    df = df.drop_duplicates()

    # 4. Extrahera Namn, Målvakt, Nationalitet och Alias
    if 'Namn' in df.columns:
        df[['Rent_Namn', 'Målvakt', 'Nationalitet', 'Alias']] = df['Namn'].apply(parse_name_column)
        df = df.drop(columns=['Namn'])

    # 5. Smart Datumkonvertering (Nu med RÄTT separerade logiker)
    if 'Född' in df.columns and 'Tid' in df.columns:
        df['Född'] = df.apply(lambda row: format_birth_date(row['Född'], row['Tid']), axis=1)
        
    if 'Avled' in df.columns and 'Tid' in df.columns:
        # Viktigt: Vi skickar med det nu *formaterade* Född-datumet för att basera beräkningen på det
        if 'Född' in df.columns:
            df['Avled'] = df.apply(lambda row: format_death_date(row['Avled'], row['Född'], row['Tid']), axis=1)
        else:
            df['Avled'] = df.apply(lambda row: format_death_date(row['Avled'], None, row['Tid']), axis=1)

    # 6. Siffror till Numeriskt format
    df['Mat'] = pd.to_numeric(df['Mat'], errors='coerce').fillna(0).astype(int)
    df['Mål'] = pd.to_numeric(df['Mål'], errors='coerce').fillna(0).astype(int)

    # 7. Omorganisera kolumner
    cols = ['Nr', 'Rent_Namn', 'Målvakt', 'Nationalitet', 'Alias', 'Född', 'Avled', 'Klubb', 'Tid', 'Mat', 'Mål', 'Anteckningar']
    cols = [c for c in cols if c in df.columns]
    df = df[cols]

    # ==========================================
    # 4. EXPORT
    # ==========================================
    print("💾 Sparar filer...")
    df.to_excel(output_xlsx, index=False, engine='openpyxl')
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print(f"✅ Data framgångsrikt städad!")
    print(f"📊 {len(df)} rader exporterade.")

if __name__ == "__main__":
    input_file = os.path.join(excel_dir, "Allsv_spelare_basuttag.xlsx")
    out_excel = os.path.join(excel_dir, "Allsv_spelare_Tvattad_Databas.xlsx")
    out_csv = os.path.join(csv_dir, "Allsv_spelare_Tvattad_Databas.csv")
    
    clean_allsvenskan_data(input_file, out_excel, out_csv)