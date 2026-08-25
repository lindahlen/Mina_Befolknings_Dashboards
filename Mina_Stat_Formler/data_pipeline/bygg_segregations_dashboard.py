import os
import sys
import traceback  # <--- LÄGG TILL DENNA RAD!
import pandas as pd
import numpy as np
from pyaxis import pyaxis
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

# --- 1. SÖKVÄGAR & MILJÖ ---
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
    print(f"1. Arbetskatalog satt till: {current_folder}")
except NameError:
    pass

stat_formler_dir = os.path.dirname(current_folder)
kartor_dir = os.path.join(stat_formler_dir, 'Kartor')
px_dir = os.path.join(kartor_dir, 'px_filer')
excel_dir = os.path.join(kartor_dir, 'excel_filer')

file_hkt58 = os.path.join(px_dir, 'HKT58.px')
file_hkt59 = os.path.join(px_dir, 'HKT59special.px')
file_excel = os.path.join(excel_dir, 'SEI_karaktär.xlsx')
csv_output_path = os.path.join(stat_formler_dir, 'segregation_base.csv')

# --- 2. TEXTFIX & ENCODING ---
encoding_fix = {
    'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
    'Ã©': 'é', 'Ã¨': 'è', 'Ã‰': 'É', "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö"
}

def fix_text(text):
    if not isinstance(text, str): return text
    for bad, good in encoding_fix.items():
        text = text.replace(bad, good)
    return text

# --- 3. INLÄSNING OCH DATATVÄTT ---
def process_px(file_path):
    if not os.path.exists(file_path):
        print(f"FEL: Hittade inte filen {os.path.basename(file_path)}")
        sys.exit(1)
    px = pyaxis.parse(file_path, encoding='ANSI')
    df = px['DATA']
    for col in df.columns:
        df[col] = df[col].apply(fix_text)
    df['DATA'] = pd.to_numeric(df['DATA'].replace(['..', '-'], np.nan), errors='coerce')
    df = df.dropna(subset=['DATA'])
    content_col = 'tabellinnehåll' if 'tabellinnehåll' in df.columns else 'tabelluppgift'
    return df.pivot_table(index=['basområde', 'tid'], columns=content_col, values='DATA', aggfunc='first').reset_index()

print("--- Startar Data Pipeline v2.2 (Inkl. AI/PCA) ---")

df_58 = process_px(file_hkt58)
df_59 = process_px(file_hkt59)

px_merged = pd.merge(df_58, df_59, on=['basområde', 'tid'], how='outer')

# Korrigera stavfel och byta namn på SEI-snittet för snyggare gruppering!
rename_dict = {
    'Inflytting inom länet': 'Inflyttning inom länet',
    'Utflytting inom länet': 'Utflyttning inom länet',
    'Utfyttning': 'Utflyttning',
    'SEIsnitt 16 indikatorer': 'Index: Samlat SEI (16 indikatorer)',
    'SEIsnitt medel': 'SEI medel (2015-2024)'
}
px_merged.rename(columns={k: v for k, v in rename_dict.items() if k in px_merged.columns and v not in px_merged.columns}, inplace=True)

def fill_nearest_year(group):
    return group.ffill().bfill()
px_merged = px_merged.groupby('basområde', group_keys=False).apply(fill_nearest_year)

# --- 4. BERÄKNINGAR ---
def calc_if_exists(df, new_col, calc_func, required_cols):
    if all(col in df.columns for col in required_cols):
        df[new_col] = calc_func(df)

calc_if_exists(px_merged, 'Försörjningskvot', lambda d: ((d['Befolkning 0-19 år'] + d['Befolkning 65+ år']) / d['Befolkning 20-64 år']).round(3), ['Befolkning 0-19 år', 'Befolkning 65+ år', 'Befolkning 20-64 år'])
calc_if_exists(px_merged, 'Nettopendling', lambda d: d['Förvärvsarbetande dagbefolkning'] - d['Förvärvsarbetande nattbefolkning'], ['Förvärvsarbetande dagbefolkning', 'Förvärvsarbetande nattbefolkning'])
calc_if_exists(px_merged, 'Inrikes inflyttning', lambda d: d['Inflyttning inom länet'] + d['Inflyttning annat län'], ['Inflyttning inom länet', 'Inflyttning annat län'])
calc_if_exists(px_merged, 'Inrikes utflyttning', lambda d: d['Utflyttning inom länet'] + d['Utflyttning annat län'], ['Utflyttning inom länet', 'Utflyttning annat län'])
calc_if_exists(px_merged, 'Flyttningsnetto', lambda d: d['Inflyttning'] - d['Utflyttning'], ['Inflyttning', 'Utflyttning'])
calc_if_exists(px_merged, 'Flyttningsnetto inom kommunen', lambda d: d['Inflyttning egen kommun'] - d['Utflyttning egen kommun'], ['Inflyttning egen kommun', 'Utflyttning egen kommun'])
calc_if_exists(px_merged, 'Inrikes flyttningsnetto', lambda d: d['Inrikes inflyttning'] - d['Inrikes utflyttning'], ['Inrikes inflyttning', 'Inrikes utflyttning'])
calc_if_exists(px_merged, 'Migrationsnetto', lambda d: d['Invandring'] - d['Utvandring'], ['Invandring', 'Utvandring'])
calc_if_exists(px_merged, 'Födelseöverskott', lambda d: d['Födda'] - d['Döda'], ['Födda', 'Döda'])
calc_if_exists(px_merged, 'Nettoflyttning förvärvsarbetande', lambda d: d['Inflyttning av förvärvsarbetande från annat basområde'] - d['Utflyttning av förvärvsarbetande till annat basområde'], ['Inflyttning av förvärvsarbetande från annat basområde', 'Utflyttning av förvärvsarbetande till annat basområde'])

# ==========================================
# --- 4B. JÄMSTÄLLDHETSBERÄKNINGAR ---
# ==========================================

# 1. Skapa nämnare (Total befolkning 20-64 per kön) genom att summera utbildningskategorierna
utb_k_cols = ['Förgymnasial utb kvinnor', 'Gymnasial utb kvinnor', 'Kort eftergymnasial utb kvinnor', 'Lång eftergymnasial utb kvinnor', 'Uppgift saknas utb kvinnor']
calc_if_exists(px_merged, 'Total utb 20-64 kvinnor', lambda d: d[utb_k_cols].sum(axis=1), utb_k_cols)

utb_m_cols = ['Förgymnasial utb män', 'Gymnasial utb män', 'Kort eftergymnasial utb män', 'Lång eftergymnasial utb män', 'Uppgift saknas utb män']
calc_if_exists(px_merged, 'Total utb 20-64 män', lambda d: d[utb_m_cols].sum(axis=1), utb_m_cols)

# 2. Räkna om till andelar (%)
calc_if_exists(px_merged, 'Förgymnasial utb kvinnor (%)', lambda d: (d['Förgymnasial utb kvinnor'] / d['Total utb 20-64 kvinnor']) * 100, ['Förgymnasial utb kvinnor', 'Total utb 20-64 kvinnor'])
calc_if_exists(px_merged, 'Förgymnasial utb män (%)', lambda d: (d['Förgymnasial utb män'] / d['Total utb 20-64 män']) * 100, ['Förgymnasial utb män', 'Total utb 20-64 män'])

calc_if_exists(px_merged, 'Lång eftergymn utb kvinnor (%)', lambda d: (d['Lång eftergymnasial utb kvinnor'] / d['Total utb 20-64 kvinnor']) * 100, ['Lång eftergymnasial utb kvinnor', 'Total utb 20-64 kvinnor'])
calc_if_exists(px_merged, 'Lång eftergymn utb män (%)', lambda d: (d['Lång eftergymnasial utb män'] / d['Total utb 20-64 män']) * 100, ['Lång eftergymnasial utb män', 'Total utb 20-64 män'])

# 3. Klyftorna (Alltid: Kvinnor minus Män) 
# Ett plusvärde = Kvinnor har högre siffra. Minusvärde = Män har högre.
calc_if_exists(px_merged, 'Diff: Förgymnasial utb', lambda d: d['Förgymnasial utb kvinnor (%)'] - d['Förgymnasial utb män (%)'], ['Förgymnasial utb kvinnor (%)', 'Förgymnasial utb män (%)'])
calc_if_exists(px_merged, 'Diff: Lång eftergymn utb', lambda d: d['Lång eftergymn utb kvinnor (%)'] - d['Lång eftergymn utb män (%)'], ['Lång eftergymn utb kvinnor (%)', 'Lång eftergymn utb män (%)'])

# Ohälsotal är redan en färdig kvot/dagar per person, så vi tar differensen direkt
calc_if_exists(px_merged, 'Diff: Ohälsotal 20-64 år', lambda d: d['Ohälsotal kvinnor 20-64 år'] - d['Ohälsotal män 20-64 år'], ['Ohälsotal kvinnor 20-64 år', 'Ohälsotal män 20-64 år'])

# Sysselsättning (om du har dessa kolumner sedan tidigare)
calc_if_exists(px_merged, 'Diff: Sysselsättningsgrad', lambda d: d['Sysselsättningsgrad kvinnor'] - d['Sysselsättningsgrad män'], ['Sysselsättningsgrad kvinnor', 'Sysselsättningsgrad män'])

# --- 5. Z-SCORE INDEX MOTOR ---
def get_col(df, substring):
    for c in df.columns:
        if substring.lower() in c.lower(): return c
    return None

index_config = {
    "Index: Ekonomisk Utsatthet": {
        "pos": ["Långvarigt ekonomiskt bistånd", "Inskrivna arbetslösa", "Låg ekonomisk standard", "Ej självförsörjande", "UVAS"], "neg": []
    },
    "Index: Socialt & Humankapital": {
        "pos": ["Förgymnasial utbildning", "Ohälsotal"], "neg": ["Gymnasiebehörighet", "Inskrivna barn i förskolan", "Valdeltagande"]
    },
    "Index: Fysisk Bostadssegregation": {
        "pos": ["Trångbodda", "Små bostäder", "Hyresrätt"], "neg": ["Boyta per person", "Bilinnehav", "Kvarboende"]
    },
    "Index: Demografisk Koncentration": {
        "pos": ["Utrikes födda", "Utländsk bakgrund"], "neg": []
    },
    "Index: Strukturell Ojämlikhet": {
        # POS: Saker som ofta drabbar kvinnor hårdast och driver Ojämlikhet (högt värde = sämre jämställdhet)
        "pos": ["Diff: Ohälsotal 20-64 år"], 
        # NEG: Saker som bygger kvinnors självständighet och motverkar ojämlikheten (Sänker indexets negativa poäng)
        "neg": [
            "Kvinnors andel nettoinkomst", 
            "Kvinnors andel förvärvsinkomst", 
            "Diff: Sysselsättningsgrad", 
            "Diff: Lång eftergymn utb"
        ]
    }
}

for idx_name, config in index_config.items():
    z_scores = pd.DataFrame(index=px_merged.index)
    valid_vars = 0
    for var in config["pos"]:
        col = get_col(px_merged, var)
        if col:
            z_scores[col] = px_merged.groupby('tid')[col].transform(lambda x: (x - x.mean()) / x.std(ddof=0))
            valid_vars += 1
    for var in config["neg"]:
        col = get_col(px_merged, var)
        if col:
            z_scores[col] = px_merged.groupby('tid')[col].transform(lambda x: -1 * ((x - x.mean()) / x.std(ddof=0)))
            valid_vars += 1
    if valid_vars > 0:
        px_merged[idx_name] = z_scores.sum(axis=1).round(3)

# --- 5B. DEFINIERA GRUNDVARIABLER FÖR DRIVKRAFTSANALYS ---
# Här skapar vi en lista som enbart innehåller "rena" variabler, 
# så att Index och SEI-samlingsmått aldrig visas som drivkrafter till varandra.

alla_numeriska = px_merged.select_dtypes(include=['float64', 'int64']).columns.tolist()

grundvariabler = [
    col for col in alla_numeriska 
    if not str(col).startswith("Index:") 
    and col != "SEI medel (2015-2024)"
    and col not in ['basområde', 'tid', 'OBJECTID'] # Lägg till ev. andra ID-kolumner här
]

# (Om din kod längre ner använder en specifik variabel, t.ex. 'features' eller 'analys_kolumner' 
# för att bygga Tornado-diagrammet eller korrelationsmatrisen, 
# se till att den nu pekar på 'grundvariabler' istället för alla kolumner).

# --- 6. EXCEL METADATA ---
if os.path.exists(file_excel):
    df_excel = pd.read_excel(file_excel)
    if 'Namn' in df_excel.columns:
        df_excel['Namn'] = df_excel['Namn'].astype(str).str.strip()
        cols_to_use = ['Namn', 'KodNyko4', 'Stadsdelskod_(Nyko3)', 'Stadsdel', 'Karaktär_bas', 'Karaktär_detalj', 'SEI_indikatorer16', 'Inkluderad', 'Områdestyp']
        df_excel = df_excel[[c for c in cols_to_use if c in df_excel.columns]]
        final_df = pd.merge(px_merged, df_excel, left_on='basområde', right_on='Namn', how='left')
        if 'Namn' in final_df.columns: final_df = final_df.drop(columns=['Namn'])
    else:
        final_df = px_merged
else:
    final_df = px_merged

# --- 7 STÄDNING AV RÅDATA FÖR JÄMSTÄLLDHET ---
# Vi tar bort de grundvariabler som enbart användes för att räkna ut klyftorna, 
# så att de inte skräpar ner dashboardens gränssnitt.

ra_kolumner_att_dolja = [
    'Förgymnasial utb män', 'Gymnasial utb män', 'Kort eftergymnasial utb män', 'Lång eftergymnasial utb män', 'Uppgift saknas utb män',
    'Förgymnasial utb kvinnor', 'Gymnasial utb kvinnor', 'Kort eftergymnasial utb kvinnor', 'Lång eftergymnasial utb kvinnor', 'Uppgift saknas utb kvinnor',
    'Ohälsotal totalt 20-64 år', 'Ohälsotal män 20-64 år', 'Ohälsotal kvinnor 20-64 år',
    'Total utb 20-64 kvinnor', 'Total utb 20-64 män', 
    'Förgymnasial utb kvinnor (%)', 'Förgymnasial utb män (%)', 
    'Lång eftergymn utb kvinnor (%)', 'Lång eftergymn utb män (%)'
]

# Drop-funktionen ignorerar kolumner som eventuellt inte existerar (felsäkert)
final_df = final_df.drop(columns=[col for col in ra_kolumner_att_dolja if col in final_df.columns])

# ==========================================
# 8. AVSLUT OCH SPARA
# ==========================================
print("\n⏳ Sorterar och sparar master-filen...")
try:
    final_df = final_df.sort_values(by=['basområde', 'tid']).reset_index(drop=True)
    final_df.to_csv(csv_output_path, index=False, encoding='utf-8')
    print(f"💾 KLART! Ny master-databas sparad: {csv_output_path}")
except PermissionError:
    print(f"\n❌ FEL: Kunde inte spara. Har du '{os.path.basename(csv_output_path)}' öppen i Excel?")
except Exception as e:
    print(f"\n❌ ETT OVÄNTAT FEL UPPSTOD VID SPARANDET:")
    traceback.print_exc()