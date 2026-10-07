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

# ==========================================
# 3B. HANTERING AV SAKNADE VÄRDEN med "fill_nearest_year" (T.ex. 2025 års inkomst/sysselsättning)
# ==========================================

# 1. KRITISKT: Sortera alltid på basområde och tid först!
px_merged = px_merged.sort_values(by=['basområde', 'tid'])

# 2. Identifiera vilka kolumner som faktiskt ska fyllas (allt utom nycklarna)
fyll_kolumner = px_merged.columns.difference(['basområde', 'tid'])

# 3. 100% gruppsäker fyllning via transform (stjäl aldrig värden från grannen!)
# Lambda-funktionen körs strikt isolerat inom varje basområde.
px_merged[fyll_kolumner] = px_merged.groupby('basområde')[fyll_kolumner].transform(lambda x: x.ffill().bfill())

# 4. DEFRAGMENTERA MINNET FÖR ATT SLIPPA PERFORMANCE-VARNINGEN
# Detta "limmar ihop" tabellen i minnet innan vi skapar massa nya indexkolumner.
px_merged = px_merged.copy()

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

# ==============================================================================
# 4B. SKAPANDE AV INDEX: CNI-L OCH KRIS- & KLIMATSÅRBARHET (KKSI)
# ==============================================================================

print(" -> Beräknar CNI, KKSI och Äldreomsorgs-index...", flush=True)

# --- 0. RÄDDNINGSAKTION FÖR 2015 OCH 2016 (BACKFILL PÅ RÅDATA) ---
# Eftersom vissa HKT59special-variabler saknar data 2015-2016, fyller vi dem bakåt från 2017.
kolumner_att_radda = [
    '70+ år', '85+ år', 'Bostäder byggda före 1980', 'Bostäder', 
    'Hyresrätter', 'Nettoinkomst (tkr)', 'Utländsk bakgrund'
]
px_merged = px_merged.sort_values(by=['basområde', 'tid'])
for col in kolumner_att_radda:
    if col in px_merged.columns:
        # Fyller saknade värden för varje basområde (backfill och sedan forwardfill som säkerhet)
        px_merged[col] = px_merged.groupby('basområde')[col].transform(lambda x: x.bfill().ffill())

# 1. Vi beräknar de nya andelarna från HKT59special och multiplicerar med 100
# för att de ska få exakt samma procentskala (0-100) som variablerna från HKT58!
calc_if_exists(px_merged, 'Andel 0-4 år', lambda d: (d['0-4 år'] / d['Invånarantal'].replace(0, np.nan)) * 100, ['0-4 år', 'Invånarantal'])
calc_if_exists(px_merged, 'Andel 70+ år', lambda d: (d['70+ år'] / d['Invånarantal'].replace(0, np.nan)) * 100, ['70+ år', 'Invånarantal'])
calc_if_exists(px_merged, 'Andel 85+ år', lambda d: (d['85+ år'] / d['Invånarantal'].replace(0, np.nan)) * 100, ['85+ år', 'Invånarantal'])
calc_if_exists(px_merged, 'Andel ensamma 70+', lambda d: (d['70+ år ensamboende'] / d['Hushåll'].replace(0, np.nan)) * 100, ['70+ år ensamboende', 'Hushåll'])
calc_if_exists(px_merged, 'Andel ensamstående föräldrar', lambda d: (d['Ensamstående föräldrar'] / d['Hushåll'].replace(0, np.nan)) * 100, ['Ensamstående föräldrar', 'Hushåll'])
calc_if_exists(px_merged, 'Andel gamla hus', lambda d: (d['Bostäder byggda före 1980'] / d['Hushåll'].replace(0, np.nan)) * 100, ['Bostäder byggda före 1980', 'Hushåll'])
calc_if_exists(px_merged, 'Andel hyresrätt', lambda d: (d['Hyresrätter'] / d['Bostäder'].replace(0, np.nan)) * 100, ['Hyresrätter', 'Bostäder'])

# Kvarboende inverteras (100% minus nuvarande procentvärde)
calc_if_exists(px_merged, 'Hög omflyttning', lambda d: 100.0 - pd.to_numeric(d['Kvarboende minst ett år'].astype(str).str.replace(',', '.'), errors='coerce'), ['Kvarboende minst ett år'])

# (De färdiga variablerna Utländsk bakgrund, Utrikes födda, Förgymnasial utbildning och Inskrivna arbetslösa lämnas ifred och används direkt i listorna nedan)

# 2. Hjälpfunktion för att räkna ut Z-score för en kolumn (per år!)
def z_score(df, col):
    # 🚀 BOMBSÄKERT: Tvingar bort kommatecken och konverterar strängar till float innan matematiken körs
    saker_kolumn = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
    return saker_kolumn.groupby(df['tid']).transform(lambda x: (x - x.mean()) / (x.std() if x.std() != 0 else 1))

# 3. Bygg CNI-L (Care Need Index)
# Inkluderar nu Ensamstående föräldrar!
req_cni = ['Andel 0-4 år', 'Andel ensamma 70+', 'Andel ensamstående föräldrar', 'Förgymnasial utbildning', 'Inskrivna arbetslösa', 'Utrikes födda', 'Hög omflyttning']
if all(col in px_merged.columns for col in req_cni):
    px_merged['Index: Care Need (CNI)'] = (
        z_score(px_merged, 'Andel 0-4 år') +
        z_score(px_merged, 'Andel ensamma 70+') +
        z_score(px_merged, 'Andel ensamstående föräldrar') +
        z_score(px_merged, 'Förgymnasial utbildning') +
        z_score(px_merged, 'Inskrivna arbetslösa') +
        z_score(px_merged, 'Utrikes födda') +
        z_score(px_merged, 'Hög omflyttning')
    ).round(2)
    print(" ✅ Index: Care Need (CNI) skapat!")
else:
    print(" ⚠️️ Saknar variabler för CNI, hoppar över.")

# 4. Bygg KKSI (Kris- och Klimatsårbarhetsindex)
req_kksi = ['Andel 0-4 år', 'Andel 70+ år', 'Andel ensamma 70+', 'Andel gamla hus', 'Utländsk bakgrund', 'Andel hyresrätt', 'Inskrivna arbetslösa', 'Nettoinkomst (tkr)']
if all(col in px_merged.columns for col in req_kksi):
    px_merged['Index: Kris- & Sårbarhet (KKSI)'] = (
        z_score(px_merged, 'Andel 0-4 år') +
        z_score(px_merged, 'Andel 70+ år') +
        z_score(px_merged, 'Andel ensamma 70+') +
        z_score(px_merged, 'Andel gamla hus') +
        z_score(px_merged, 'Utländsk bakgrund') +
        z_score(px_merged, 'Andel hyresrätt') +
        z_score(px_merged, 'Inskrivna arbetslösa') - 
        z_score(px_merged, 'Nettoinkomst (tkr)') # Minus: låg inkomst = HÖG sårbarhet
    ).round(2)
    print(" ✅ Kris- & Sårbarhetsindex (KKSI) skapat!")
else:
    print(" ⚠️ Saknar variabler för KKSI, hoppar över.")

# 5. Bygg Äldreomsorgsbehov
# Kräver: 85+, 70+, Ensamma 70+, Gamla hus
req_aldre = ['Andel 85+ år', 'Andel 70+ år', 'Andel ensamma 70+', 'Andel gamla hus']
if all(col in px_merged.columns for col in req_aldre):
    px_merged['Index: Äldres Omsorgsbehov'] = (
        z_score(px_merged, 'Andel 85+ år') +
        z_score(px_merged, 'Andel 70+ år') +
        z_score(px_merged, 'Andel ensamma 70+') +
        z_score(px_merged, 'Andel gamla hus')
    ).round(2)
    print(" ✅ Index: Äldres Omsorgsbehov skapat!")

# ==========================================
# --- 4c. JÄMSTÄLLDHETSBERÄKNINGAR ---
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
        "pos": ["Utrikes födda", "Utländsk bakgrund", "Ensamstående hushåll"], "neg": []
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
    'Ohälsotal män 20-64 år', 'Ohälsotal kvinnor 20-64 år',
    'Total utb 20-64 kvinnor', 'Total utb 20-64 män', 
    'Förgymnasial utb kvinnor (%)', 'Förgymnasial utb män (%)', 
    'Lång eftergymn utb kvinnor (%)', 'Lång eftergymn utb män (%)',
# 🚀 NYA TILLÄGG: Bara fyll på listan med exakta namn (måste matcha stavningen i datan)
    'Utländsk bakgrund kvinnor', 'Utländsk bakgrund män',
    'Uppgift saknas utb', 'Diff: Ohälsotal 20-64 år', 'Diff: Sysselsättningsgrad', 'Diff: Lång eftergymn utb', 'Diff: Förgymnasial utb',
# 🚀 NYA TILLÄGG: Bara fyll på listan med exakta namn (måste matcha stavningen i datan)
    'AI_Kompass_X', 'AI_Kompass_Y',
# 🚀 NYA TILLÄGG: Rådata och Andelar för CNI & KKSI
    '0-4 år', '70+ år', '85+ år', '70+ år ensamboende', 'Ensamstående föräldrar', 'Bostäder byggda före 1980', # Absoluta tal
    'Andel 0-4 år', 'Andel 70+ år', 'Andel gamla hus', # Rå-andelar
    'Hög omflyttning', 'Andel hyresrätt', 'Andel 85+ år', # Andelar som beräknats explicit för Z-scores
]

# Drop-funktionen ignorerar kolumner som eventuellt inte existerar (felsäkert)
final_df = final_df.drop(columns=[col for col in ra_kolumner_att_dolja if col in final_df.columns])

# --- 8. SÄTT ALIAS / BYT NAMN PÅ VARIABLER ---
# Här döper vi om kolumner så de ser snyggare och tydligare ut i dashboarden.

alias_ordlista = {
    'Ohälsotal totalt 20-64 år': 'Ohälsotal 20-64 år',
    'Nettoinkomst, andel': 'Nettoinkomstens andel av kommunens nivå',
    'Andel ensamstående föräldrar': 'Ensamstående föräldrar',
    'Andel ensamma 70+': 'Ensamstående 70 år eller äldre'
    # Lägg till hur många du vill här...
}

# Applicera namnbytet på din dataframe (byt ut 'df' mot vad din dataframe heter)
final_df = final_df.rename(columns=alias_ordlista)

# ==========================================
# 8B. AI-KOMPASS (FRIKOPPLAD INLÄSNING - SÖKVÄGS-SMART)
# ==========================================
print("\n🧭 Startar AI-Kompassen (Söker efter filen)...", flush=True)

try:
    import pandas as pd
    import os
    
    # --- MASTER CONFIG: Regel 2B (Encoding Fix) ---
    encoding_fix = {
        'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
        'Ã©': 'é', 'Ã¨': 'è', 'Ã‰': 'É', "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö"
    }

    def fix_text(text):
        if not isinstance(text, str): return text
        for bad, good in encoding_fix.items():
            text = text.replace(bad, good)
        return text
    # ----------------------------------------------

    old_cols = [c for c in final_df.columns if 'AI_Kompass' in c]
    if old_cols:
        final_df = final_df.drop(columns=old_cols)

    # 💡 LÖSNINGEN: Leta i aktuell mapp OCH en mapp upp!
    filename = "ai_segregation_koordinater.csv"
    path_current = filename
    path_parent = os.path.join("..", filename)
    
    compass_file = None
    if os.path.exists(path_current):
        compass_file = path_current
    elif os.path.exists(path_parent):
        compass_file = path_parent
        
    if compass_file:
        print(f" -> [1/3] Hittade filen i sökvägen: {compass_file}", flush=True)
        
        try:
            df_coords = pd.read_csv(compass_file, sep=';', encoding='utf-8')
        except UnicodeDecodeError:
            df_coords = pd.read_csv(compass_file, sep=';', encoding='latin1')
        
        rename_dict = {}
        for col in df_coords.columns:
            fixed_col = fix_text(col)
            if 'basomr' in fixed_col.lower() or fixed_col.lower() == 'namn':
                rename_dict[col] = 'basområde'
            elif 'år' in fixed_col.lower() or 'tid' in fixed_col.lower():
                rename_dict[col] = 'tid'
            elif fixed_col != col:
                rename_dict[col] = fixed_col
                
        if rename_dict:
            df_coords = df_coords.rename(columns=rename_dict)
            
        print(" -> [2/3] Matchar datatyper och bakar ihop...", flush=True)
        
        if 'basområde' in df_coords.columns and 'AI_Kompass_X' in df_coords.columns:
            # Tvätta områdesnamnen i fall Excel förstört å/ä/ö
            df_coords['basområde'] = df_coords['basområde'].apply(fix_text)
            
            final_df['basområde'] = final_df['basområde'].astype(str)
            df_coords['basområde'] = df_coords['basområde'].astype(str)
            
            if 'tid' in df_coords.columns:
                final_df['tid'] = final_df['tid'].astype(str)
                df_coords['tid'] = df_coords['tid'].astype(str)
                final_df = pd.merge(final_df, df_coords[['basområde', 'tid', 'AI_Kompass_X', 'AI_Kompass_Y']], on=['basområde', 'tid'], how='left')
            else:
                final_df = pd.merge(final_df, df_coords[['basområde', 'AI_Kompass_X', 'AI_Kompass_Y']], on='basområde', how='left')
            
            # Eftersom vi vet att filen har punkter, konverterar vi direkt till nummer
            final_df['AI_Kompass_X'] = pd.to_numeric(final_df['AI_Kompass_X'], errors='coerce')
            final_df['AI_Kompass_Y'] = pd.to_numeric(final_df['AI_Kompass_Y'], errors='coerce')
            
            # Fyll NaN med 0.0 för att skydda den känsliga JavaScript-kartan
            final_df['AI_Kompass_X'] = final_df['AI_Kompass_X'].fillna(0.0)
            final_df['AI_Kompass_Y'] = final_df['AI_Kompass_Y'].fillna(0.0)
            
            # Kontrollutskrift!
            success_count = (final_df['AI_Kompass_X'] != 0.0).sum()
            print(f"✅ [3/3] Inbakat! {success_count} matchningar gjordes med master-filen.", flush=True)
            
        else:
            print("⚠️ Fel: Filen saknar nödvändiga kolumner (basområde och/eller AI_Kompass_X).", flush=True)
    else:
        print(f"⚠️ Filen '{filename}' hittades varken i mappen eller en mapp upp. Kompassen hoppas över.", flush=True)

except Exception as e:
    print(f"\n❌ ETT FEL UPPSTOD VID INLÄSNING AV KOMPASS: {e}")

# ==========================================
# 9. AVSLUT OCH SPARA
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