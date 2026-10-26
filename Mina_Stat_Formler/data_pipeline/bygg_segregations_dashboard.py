import os
import sys
import traceback  # <--- LÄGG TILL DENNA RAD!
import pandas as pd
import numpy as np
from pyaxis import pyaxis
# from sklearn.preprocessing import StandardScaler
# from sklearn.decomposition import PCA
import warnings
from pandas.errors import PerformanceWarning
warnings.filterwarnings('ignore', category=PerformanceWarning)

# Tystar Pandas framtidsvarningar för ffill/bfill
# pd.set_option('future.no_silent_downcasting', True)

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

    # 🚀 LÖSNING: Dynamisk hantering av geografisk nivå (basområde vs stadsdel)
    geo_col = 'basområde' if 'basområde' in df.columns else 'stadsdel'

    return df.pivot_table(index=[geo_col, 'tid'], columns=content_col, values='DATA', aggfunc='first').reset_index()

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
# Skapa de inverterade variablerna direkt från originalet!
calc_if_exists(px_merged, 'Kvarboende', lambda d: 100.0 - pd.to_numeric(d['Kvarboende minst ett år'].astype(str).str.replace(',', '.'), errors='coerce'), ['Kvarboende minst ett år'])
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
        "pos": ["Förgymnasial utbildning", "Ohälsotal"], "neg": ["Gymnasiebehörighet", "Inskrivna förskolebarn", "Valdeltagande"]
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
        cols_to_use = ['Namn', 'KodNyko4', 'Stadsdelskod_(Nyko3)', 'Stadsdel', 'Karaktär_bas', 'Karaktär_detalj', 'SEI_indikatorer16', 'Inkluderad', 'Områdestyp', 'Kommundelskluster']
        df_excel = df_excel[[c for c in cols_to_use if c in df_excel.columns]]
        final_df = pd.merge(px_merged, df_excel, left_on='basområde', right_on='Namn', how='left')
        if 'Namn' in final_df.columns: 
            final_df = final_df.drop(columns=['Namn'])
            
        # 🚀 FIX: Fyll tomma celler så JavaScript inte kraschar på "NaN"
        if 'Kommundelskluster' in final_df.columns:
            final_df['Kommundelskluster'] = final_df['Kommundelskluster'].fillna('Okänd')
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
    'AI_Kompass_X', 'AI_Kompass_Y', 'Kommundelskluster', 
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
    'Andel ensamma 70+': 'Ensamstående 70 år eller äldre',
    'Inskrivna förskolebarn': 'Inskrivna barn i förskolan', # 🚀 Döper om den i sista sekunden!
    # 🚀 Nya tillägg för att synka Nyko 3 och Nyko 4 i UI-rullistorna:
    'Behöriga gymnasiets yrkesprogram': 'Gymnasiebehörighet',
    'Kvm per person': 'Boyta per person',
    'Kvm per hushåll': 'Boyta per hushåll',
    
    # 🚀 Tydliggör den inverterade variabeln (ca 10%) enbart för rullistan
    'Kvarboende': 'Omflyttning (Hög)'
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
# 10. SKAPA NYKO 3 (STADSDEL) (HYBRID-METODEN)
# ==========================================
print("\n🏙️  Börjar aggregera data till Nyko 3 (Stadsdel)...")

try:
    # --- 10A. HÄMTA FULLSTÄNDIG DATA OCH MÄRK UPP VIA KLARTEXT & KODNYCKEL ---
    df_nyko4_full = px_merged.copy()

    if os.path.exists(file_excel):
        df_excel = pd.read_excel(file_excel)
        
        # 1. Säkra koderna och namnen i Excel
        df_excel['Stadsdelskod_(Nyko3)'] = df_excel['Stadsdelskod_(Nyko3)'].astype(str).str.replace('.0', '', regex=False).str.strip()
        df_excel['Stadsdel'] = df_excel['Stadsdel'].astype(str).apply(fix_text).str.strip()

        # 2. 🚀 HYBRID-LÖSNINGEN: Tvätta namnen i båda filerna så de matchar 100 %
        excel_namn_kolumn = 'Namn' # Kolumnen i Excel där ex "Malmskogen industriområde" står
        df_excel['Namn_match'] = df_excel[excel_namn_kolumn].astype(str).apply(fix_text).str.strip().str.lower()
        df_nyko4_full['basområde_match'] = df_nyko4_full['basområde'].astype(str).apply(fix_text).str.strip().str.lower()

        # 3. Skapa lexikon! (Basområdesnamn -> Stadsdelskod) & (Stadsdelskod -> Stadsdelsnamn)
        map_namn_till_n3_kod = df_excel.set_index('Namn_match')['Stadsdelskod_(Nyko3)'].to_dict()
        map_kod_till_n3_namn = df_excel.drop_duplicates('Stadsdelskod_(Nyko3)').set_index('Stadsdelskod_(Nyko3)')['Stadsdel'].to_dict()
        
        # 4. Applicera mappningen (Nyko 4 Namn -> Nyko 3 Kod -> Nyko 3 Namn)
        df_nyko4_full['Stadsdelskod_(Nyko3)'] = df_nyko4_full['basområde_match'].map(map_namn_till_n3_kod)
        df_nyko4_full['Stadsdel'] = df_nyko4_full['Stadsdelskod_(Nyko3)'].map(map_kod_till_n3_namn)
        
        # Sätt kluster temporärt
        df_nyko4_full['Kommundelskluster'] = 'Okänd' 
            
        lyckade = df_nyko4_full['Stadsdelskod_(Nyko3)'].notna().sum()
        print(f"🔍 Hybrid-matchning klar! Hittade stadsdelskod för {lyckade} av {len(df_nyko4_full)} rader.")
        
        # 🚨 DIAGNOSTIK: Vilka rader i SCB-datan saknade en matchning i Excel-filen?
        missade = df_nyko4_full[df_nyko4_full['Stadsdelskod_(Nyko3)'].isna()]['basområde'].unique()
        if len(missade) > 0:
            print(f"⚠️ VARNING: Följande områden matchade inte Excel-filen (Kolla stavningen!):")
            for m in sorted(missade):
                print(f" - {m}")

    else:
        raise FileNotFoundError(f"Saknar {file_excel}")

    # --- 10B. LÄS IN NYKO 3 PX-FILEN ---
    file_nyko3_px = os.path.join(px_dir, 'HKT59specNyko3.px')
    if os.path.exists(file_nyko3_px):
        df_px_n3 = process_px(file_nyko3_px)
        if 'basområde' in df_px_n3.columns: df_px_n3.rename(columns={'basområde': 'Stadsdel'}, inplace=True)
        elif 'stadsdel' in df_px_n3.columns: df_px_n3.rename(columns={'stadsdel': 'Stadsdel'}, inplace=True)
            
        # 🚀 FIX: Vi tvingar Nyko 3:s "Folkmängd" att heta "Invånarantal" så matematiken synkar!
        n3_px_rename = {
            'Behöriga gymnasiets yrkesprogram': 'Gymnasiebehörighet', 
            'Kvm per person': 'Boyta per person', 
            'Folkmängd': 'Invånarantal'
            # Vi låter 'Kvarboende minst ett år' vara ifred!
        }
        df_px_n3 = df_px_n3.rename(columns=n3_px_rename)
        
        df_px_n3['tid'] = pd.to_numeric(df_px_n3['tid'], errors='coerce')
        df_nyko4_full['tid'] = pd.to_numeric(df_nyko4_full['tid'], errors='coerce')

    # --- 10C. AGGREGERA ABSOLUTA ANTAL PÅ NYKO3-KOD ---
    df_nyko4_filtered = df_nyko4_full[df_nyko4_full['Stadsdelskod_(Nyko3)'].notna()].copy()
    
    # 🚀 Vi grupperar SÄKERT på koden och det officiella namnet från Excel!
    gruppering = ['Stadsdelskod_(Nyko3)', 'Stadsdel', 'tid']
    
    # Rensa bort textkolumner från Nyko 4 som sabbar aggregeringen
    cols_to_drop = [c for c in ['basområde', 'basområde_match', 'Karaktär_bas', 'Karaktär_detalj', 'Områdestyp'] if c in df_nyko4_filtered.columns]
    df_nyko4_filtered = df_nyko4_filtered.drop(columns=cols_to_drop)

    for col in df_nyko4_filtered.columns:
        if col not in gruppering:
            temp = df_nyko4_filtered[col].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.', regex=False)
            temp = temp.replace(['..', '.', '-', '', 'nan', 'NaN', '<NA>'], np.nan)
            df_nyko4_filtered[col] = pd.to_numeric(temp, errors='coerce')

    # 🚀 MAGIN: Här slås de absoluta talen (t.ex. 3062 + 88) ihop automatiskt!
    df_nyko3 = df_nyko4_filtered.groupby(gruppering).sum(numeric_only=True).reset_index()

    # =======================================================
    # 🚀 NY MAGI: Aggregera klustren snyggt och limma fast dem!
    # =======================================================
    if 'Kommundelskluster' in df_nyko4_filtered.columns:
        # Baka ihop unika kluster till en textsträng per stadsdel (ex: "Väst 1, Väst 2")
        kluster_agg = df_nyko4_filtered.groupby('Stadsdel')['Kommundelskluster'].apply(
            lambda x: ', '.join(sorted(set(str(v) for v in x.dropna() if str(v) != 'Okänd' and str(v) != 'nan')))
        ).reset_index()
        
        # Om strängen blev tom, döp den till Okänd
        kluster_agg['Kommundelskluster'] = kluster_agg['Kommundelskluster'].replace('', 'Okänd')
        
        # 🚀 FIX: Radera eventuell gammal kluster-kolumn för att undvika _x och _y krockar!
        if 'Kommundelskluster' in df_nyko3.columns:
            df_nyko3.drop(columns=['Kommundelskluster'], inplace=True)
            
        # Limma fast denna nya kolumn på df_nyko3
        df_nyko3 = pd.merge(df_nyko3, kluster_agg, on='Stadsdel', how='left')
    # =======================================================

    # 🚀 FIX: STÄDA BORT NONSENS-SUMMERINGAR
    # Rensa omedelbart bort procent- och indexkolumner som summerats felaktigt, 
    # så att de läses in från din Nyko 3 PX-fil istället, eller räknas om korrekt i 10F.
    ord_att_rensa = ['andel', '%', 'diff', 'index', 'kvot']
    kolumner_att_rensa = [c for c in df_nyko3.columns if any(o in c.lower() for o in ord_att_rensa)]
    
    # 🚀 NY FIX: Tvinga bort de kolumner som vi VET kommer som färdigt facit från Nyko3 PX-filen!
    # Eftersom de bytte namn i 10B överlevde de bulldozern, men nu dödar vi originalen här:
    ful_summeringar_att_radera = [
        'Kvm per person', 
        'Behöriga gymnasiets yrkesprogram', 
        'Kvarboende',        # Kasta felaktig summa från Nyko 4
        'Hög omflyttning'    # Kasta felaktig summa från Nyko 4
    ]
    kolumner_att_rensa.extend(ful_summeringar_att_radera)
    
    # Vi sparar undan de som vi vet ska viktas matematiskt korrekt i 10D
    cols_to_weight_keys = [
        'Kvot mellan in-och utflyttning totalt', 'Kvot mellan in- och utflyttning inom kommunen',
        'Kvot mellan inrikes in- och utflyttning av förvärvsarbetande', 'Kvot mellan in- och utflyttning inom kommunen av förvärvsarbetande',
        'SEIsnitt 16 indikatorer', 'SEIsnitt medel', 'Index: Samlat SEI (16 indikatorer)', 'SEI medel (2015-2024)',
        'Gymnasieexamen inom 3-5 år', 'Meritvärde grundskolan',
        'Försörjningskvot' # <-- LÄGG TILL HÄR!
    ]
    kolumner_att_rensa = [c for c in kolumner_att_rensa if c not in cols_to_weight_keys]
    
    df_nyko3.drop(columns=kolumner_att_rensa, inplace=True, errors='ignore')

    # --- 10D. BEFOLKNINGSVIKTADE MEDELVÄRDEN ---
    cols_to_weight = {
        'Inskrivna förskolebarn' : '0-4 år', 
        'Gymnasieexamen inom 3-5 år' : 'Befolkning 0-19 år',
        'Meritvärde grundskolan' : 'Befolkning 0-19 år',
        'Kvot mellan in-och utflyttning totalt' : 'Folkmängd',
        'Kvot mellan in- och utflyttning inom kommunen' : 'Folkmängd',
        'Kvot mellan inrikes in- och utflyttning av förvärvsarbetande' : 'Förvärvsarbetande nattbefolkning',
        'Kvot mellan in- och utflyttning inom kommunen av förvärvsarbetande' : 'Förvärvsarbetande nattbefolkning',
        'SEIsnitt 16 indikatorer' : 'Folkmängd',
        'SEIsnitt medel' : 'Folkmängd',
        'Index: Samlat SEI (16 indikatorer)' : 'Folkmängd',
        'SEI medel (2015-2024)' : 'Folkmängd',
        'Försörjningskvot': 'Befolkning 20-64 år' # Eller den nämnare som är mest relevant, ex '20-64 år'
    }
    
    df_nyko4_filtered = df_nyko4_filtered.copy()
    for val_col, wt_col in cols_to_weight.items():
        if val_col in df_nyko4_filtered.columns and wt_col in df_nyko4_filtered.columns:
            temp_col_name = f'TEMP_WT_{val_col}'
            df_nyko4_filtered.loc[:, temp_col_name] = df_nyko4_filtered[val_col] * df_nyko4_filtered[wt_col]
            grouped_sums = df_nyko4_filtered.groupby(gruppering)[[temp_col_name, wt_col]].sum(numeric_only=True).reset_index()
            weighted_result = np.where(grouped_sums[wt_col] == 0, np.nan, grouped_sums[temp_col_name] / grouped_sums[wt_col])
            
            if val_col in df_nyko3.columns: df_nyko3.drop(columns=[val_col], inplace=True)
                
            df_nyko3 = pd.merge(df_nyko3, pd.DataFrame({
                'Stadsdelskod_(Nyko3)': grouped_sums['Stadsdelskod_(Nyko3)'], 'Stadsdel': grouped_sums['Stadsdel'],
                'tid': grouped_sums['tid'], val_col: weighted_result
            }), on=gruppering, how='left')
            df_nyko4_filtered = df_nyko4_filtered.drop(columns=[temp_col_name])

    # --- 10E. 🚀 DEN HÄNSYNSLÖSA BULLDOZERN MED SCB NYKO 3 PX ---
    if 'df_px_n3' in locals():
        
        # 1. Tvätta SCB:s data så alla kommatecken blir punkter och tolkas som rena siffror
        for col in df_px_n3.columns:
            if col not in ['Stadsdel', 'tid', 'Match_Namn']:
                temp = df_px_n3[col].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.', regex=False)
                temp = temp.replace(['..', '.', '-', '', 'nan', 'NaN', '<NA>'], np.nan)
                df_px_n3[col] = pd.to_numeric(temp, errors='coerce')

        # 2. Skapa tvättade, småbokstavs-nycklar för att garantera perfekt matchning
        df_px_n3['Match_Namn'] = df_px_n3['Stadsdel'].astype(str).str.replace(r'^[\d\s]+', '', regex=True).str.split('(').str[0].str.strip().str.lower()
        df_nyko3['Match_Namn'] = df_nyko3['Stadsdel'].astype(str).str.replace(r'^[\d\s]+', '', regex=True).str.split('(').str[0].str.strip().str.lower()

        # 3. 🚀 KIRURGISK RADERING AV AGGREGERAT SKRÄP
        # Hämta namnen på alla kolumner (t.ex. färdiga procentsatser) som vi vet är korrekta i PX-filen
        px_facit_kolumner = [c for c in df_px_n3.columns if c not in ['Match_Namn', 'tid', 'Stadsdel']]
        
        # Hitta motsvarande kolumner i den aggregerade datan och kasta dem i papperskorgen!
        kolumner_att_radera = [c for c in px_facit_kolumner if c in df_nyko3.columns]
        df_nyko3.drop(columns=kolumner_att_radera, inplace=True, errors='ignore')

        # 4. Slå ihop datan! Eftersom vi raderade kolumnerna ovan, kommer pandas nu att 
        # importera de rena värdena direkt från PX-filen utan att försöka addera eller jämka dem.
        df_nyko3 = pd.merge(df_nyko3, df_px_n3.drop(columns=['Stadsdel']), on=['Match_Namn', 'tid'], how='left')
        
        # 5. Städa upp namnen
        df_nyko3['Stadsdel'] = df_nyko3['Match_Namn'].str.title()
        
        # Återställ specialnamn
        mask_hela = df_nyko3['Stadsdel'] == 'Hela Kommunen'
        df_nyko3.loc[mask_hela, 'Stadsdel'] = 'Hela kommunen'
        
        df_nyko3.drop(columns=['Match_Namn'], inplace=True, errors='ignore')

    # --- 10F. BERÄKNA ANDELAR OCH Z-SCORES (DIN INTAKTA KOD) ---

    # ==========================================
    # 🚀 MASTER-FIX: KVARBOENDE OCH HÖG OMFLYTTNING
    # ==========================================
    # 1. Hitta det faktiska värdet oavsett om det råkat byta namn
    if 'Kvarboende minst ett år' not in df_nyko3.columns and 'Kvarboende' in df_nyko3.columns:
        df_nyko3.rename(columns={'Kvarboende': 'Kvarboende minst ett år'}, inplace=True)
    
    if 'Kvarboende minst ett år' in df_nyko3.columns:
        # Säkerställ att det är rena siffror
        df_nyko3['Kvarboende minst ett år'] = pd.to_numeric(df_nyko3['Kvarboende minst ett år'].astype(str).str.replace(',', '.'), errors='coerce')
        
        # 2. Skyddsnät: Om värdet är < 50 så har en dubbel-invertering skett. Vi vänder tillbaka det!
        mask_felvand = df_nyko3['Kvarboende minst ett år'] < 50
        df_nyko3.loc[mask_felvand, 'Kvarboende minst ett år'] = 100.0 - df_nyko3.loc[mask_felvand, 'Kvarboende minst ett år']
        
        # 3. Tvinga fram de inverterade proxy-kolumnerna explicit (ca 10%)
        # Detta skriver över allt gammalt skräp som kan ha legat där från aggregeringen
        df_nyko3['Kvarboende'] = 100.0 - df_nyko3['Kvarboende minst ett år']
        df_nyko3['Hög omflyttning'] = 100.0 - df_nyko3['Kvarboende minst ett år']

    calc_if_exists(df_nyko3, 'Andel 0-4 år', lambda d: (d['0-4 år'] / d['Invånarantal'].replace(0, np.nan)) * 100, ['0-4 år', 'Invånarantal'])
    calc_if_exists(df_nyko3, 'Andel 70+ år', lambda d: (d['70+ år'] / d['Invånarantal'].replace(0, np.nan)) * 100, ['70+ år', 'Invånarantal'])
    calc_if_exists(df_nyko3, 'Andel 85+ år', lambda d: (d['85+ år'] / d['Invånarantal'].replace(0, np.nan)) * 100, ['85+ år', 'Invånarantal'])
    calc_if_exists(df_nyko3, 'Andel ensamma 70+', lambda d: (d['70+ år ensamboende'] / d['Hushåll'].replace(0, np.nan)) * 100, ['70+ år ensamboende', 'Hushåll'])
    calc_if_exists(df_nyko3, 'Andel ensamstående föräldrar', lambda d: (d['Ensamstående föräldrar'] / d['Hushåll'].replace(0, np.nan)) * 100, ['Ensamstående föräldrar', 'Hushåll'])
    calc_if_exists(df_nyko3, 'Andel gamla hus', lambda d: (d['Bostäder byggda före 1980'] / d['Hushåll'].replace(0, np.nan)) * 100, ['Bostäder byggda före 1980', 'Hushåll'])
    calc_if_exists(df_nyko3, 'Andel hyresrätt', lambda d: (d['Hyresrätter'] / d['Bostäder'].replace(0, np.nan)) * 100, ['Hyresrätter', 'Bostäder'])
    calc_if_exists(df_nyko3, 'Total utb 20-64 kvinnor', lambda d: d[utb_k_cols].sum(axis=1), utb_k_cols)
    calc_if_exists(df_nyko3, 'Total utb 20-64 män', lambda d: d[utb_m_cols].sum(axis=1), utb_m_cols)
    calc_if_exists(df_nyko3, 'Förgymnasial utb kvinnor (%)', lambda d: (d['Förgymnasial utb kvinnor'] / d['Total utb 20-64 kvinnor']) * 100, ['Förgymnasial utb kvinnor', 'Total utb 20-64 kvinnor'])
    calc_if_exists(df_nyko3, 'Förgymnasial utb män (%)', lambda d: (d['Förgymnasial utb män'] / d['Total utb 20-64 män']) * 100, ['Förgymnasial utb män', 'Total utb 20-64 män'])
    calc_if_exists(df_nyko3, 'Lång eftergymn utb kvinnor (%)', lambda d: (d['Lång eftergymnasial utb kvinnor'] / d['Total utb 20-64 kvinnor']) * 100, ['Lång eftergymnasial utb kvinnor', 'Total utb 20-64 kvinnor'])
    calc_if_exists(df_nyko3, 'Lång eftergymn utb män (%)', lambda d: (d['Lång eftergymnasial utb män'] / d['Total utb 20-64 män']) * 100, ['Lång eftergymnasial utb män', 'Total utb 20-64 män'])
    calc_if_exists(df_nyko3, 'Diff: Förgymnasial utb', lambda d: d['Förgymnasial utb kvinnor (%)'] - d['Förgymnasial utb män (%)'], ['Förgymnasial utb kvinnor (%)', 'Förgymnasial utb män (%)'])
    calc_if_exists(df_nyko3, 'Diff: Lång eftergymn utb', lambda d: d['Lång eftergymn utb kvinnor (%)'] - d['Lång eftergymn utb män (%)'], ['Lång eftergymn utb kvinnor (%)', 'Lång eftergymn utb män (%)'])
    calc_if_exists(df_nyko3, 'Diff: Ohälsotal 20-64 år', lambda d: d['Ohälsotal kvinnor 20-64 år'] - d['Ohälsotal män 20-64 år'], ['Ohälsotal kvinnor 20-64 år', 'Ohälsotal män 20-64 år'])
    calc_if_exists(df_nyko3, 'Diff: Sysselsättningsgrad', lambda d: d['Sysselsättningsgrad kvinnor'] - d['Sysselsättningsgrad män'], ['Sysselsättningsgrad kvinnor', 'Sysselsättningsgrad män'])
    
    def z_score_n3(df, col):
        if col not in df.columns: return 0
        saker_kolumn = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
        return saker_kolumn.groupby(df['tid']).transform(lambda x: (x - x.mean()) / (x.std() if x.std() != 0 else 1))

    if all(col in df_nyko3.columns for col in req_cni):
        df_nyko3['Index: Care Need (CNI)'] = sum(z_score_n3(df_nyko3, c) for c in req_cni).round(2)
    else: print(f"⚠️ VARNING: Kan inte beräkna CNI (Nyko 3). Saknar: {[c for c in req_cni if c not in df_nyko3.columns]}")
        
    if all(col in df_nyko3.columns for col in req_kksi):
         df_nyko3['Index: Kris- & Sårbarhet (KKSI)'] = (sum(z_score_n3(df_nyko3, c) for c in req_kksi if c != 'Nettoinkomst (tkr)') - z_score_n3(df_nyko3, 'Nettoinkomst (tkr)')).round(2)
    else: print(f"⚠️ VARNING: Kan inte beräkna KKSI (Nyko 3). Saknar: {[c for c in req_kksi if c not in df_nyko3.columns]}")

    if all(col in df_nyko3.columns for col in req_aldre):
        df_nyko3['Index: Äldres Omsorgsbehov'] = sum(z_score_n3(df_nyko3, c) for c in req_aldre).round(2)

    for idx_name, config in index_config.items():
        z_scores = pd.DataFrame(index=df_nyko3.index)
        valid_vars = 0
        saknade_motor = []
        for var in config["pos"]:
            col = get_col(df_nyko3, var)
            if col:
                z_scores[col] = df_nyko3.groupby('tid')[col].transform(lambda x: (x - x.mean()) / x.std(ddof=0))
                valid_vars += 1
            else: saknade_motor.append(var)
        for var in config["neg"]:
            col = get_col(df_nyko3, var)
            if col:
                z_scores[col] = df_nyko3.groupby('tid')[col].transform(lambda x: -1 * ((x - x.mean()) / x.std(ddof=0)))
                valid_vars += 1
            else: saknade_motor.append(var)
        if valid_vars > 0:
            df_nyko3[idx_name] = z_scores.sum(axis=1).round(3)
            if saknade_motor: print(f"⚠️ VARNING: {idx_name} (N3) beräknades, men saknar: {saknade_motor}")

    # --- 10G. STÄDA BORT RÅVARIABLER OCH DÖP OM TILL ALIAS ---
    df_nyko3.columns = [fix_text(str(c)) for c in df_nyko3.columns]
    df_nyko3.rename(columns={'Stadsdel': 'basområde'}, inplace=True) 
    df_nyko3 = df_nyko3.drop(columns=[col for col in ra_kolumner_att_dolja if col in df_nyko3.columns])
    df_nyko3 = df_nyko3.rename(columns=alias_ordlista)

    # 🚀 FIX: Döp om det inverterade värdet för UI-rullistan, EFTER att indexen räknats
    ui_rename = {'Kvarboende': 'Omflyttning (Hög)'}

    if 'Kvarboende' in px_merged.columns:
        px_merged.rename(columns=ui_rename, inplace=True)

    if 'Kvarboende' in df_nyko3.columns:
        df_nyko3.rename(columns=ui_rename, inplace=True)

    # ==========================================
    # 🚀 STEG 10H: PRE-EXPORT FILTRERING & RÄTT KARAKTÄR
    # ==========================================
    df_nyko3['Inkluderad'] = 1
    area_col = None
    for col in df_nyko3.columns:
        if col.lower().strip() in ['stadsdel', 'område', 'basområde']:
            area_col = col; break

    if area_col is not None:
        ogiltiga_ord = ['ej geografisk', 'restförda', 'utan känd', 'på kommunen skriven', 'å kommunen skrivna']
        mask_ogiltiga = df_nyko3[area_col].str.lower().str.contains('|'.join(ogiltiga_ord), na=False)
        df_nyko3.loc[mask_ogiltiga, 'Inkluderad'] = 0

        mask_djurgarden = (df_nyko3[area_col] == 'Djurgården') & (df_nyko3['tid'].astype(int) < 2025)
        df_nyko3.loc[mask_djurgarden, 'Inkluderad'] = 0

        mask_harvestad = (df_nyko3[area_col] == 'Harvestad') & (df_nyko3['tid'].astype(int) < 2021)
        df_nyko3.loc[mask_harvestad, 'Inkluderad'] = 0

        mask_stangebro = (df_nyko3[area_col] == 'Stångebro') & (df_nyko3['tid'].astype(int) < 2016)
        df_nyko3.loc[mask_stangebro, 'Inkluderad'] = 0

        mask_omland = (df_nyko3[area_col] == 'Linköpings norra omland') & (df_nyko3['tid'].astype(int) < 2040)
        df_nyko3.loc[mask_omland, 'Inkluderad'] = 0

        mask_kallerstad = (df_nyko3[area_col] == 'Kallerstad') & (df_nyko3['tid'].astype(int) < 2040)
        df_nyko3.loc[mask_kallerstad, 'Inkluderad'] = 0

        mask_mjardevi = (df_nyko3[area_col] == 'Mjärdevi') & (df_nyko3['tid'].astype(int) < 2040)
        df_nyko3.loc[mask_mjardevi, 'Inkluderad'] = 0
    
    # ==========================================
    # 🚀 RÄTTNING: Återskapa färgkodningen (Stad/Tätort/Landsbygd)
    # ==========================================
    if 'df_excel' in locals():
        # 1. Plocka fram de unika stadsdelarna först (73 rader)
        df_excel_unique = df_excel.drop_duplicates('Stadsdel').copy()
        
        # 2. Skapa den säkra ordlistan från den unika dataramen
        excel_karaktar_map = df_excel_unique.set_index(df_excel_unique['Stadsdel'].astype(str).str.lower().str.strip())['Karaktär_bas'].to_dict()
        
        # 3. Applicera karaktären på vår Nyko3 DataFrame!
        df_nyko3['Karaktär_bas'] = df_nyko3[area_col].astype(str).str.lower().str.strip().map(excel_karaktar_map)
        
        # Om någon specifik rad saknar data i Excel, sätt ett snyggt standardvärde
        df_nyko3['Karaktär_bas'] = df_nyko3['Karaktär_bas'].fillna('Okänd')
    else:
        df_nyko3['Karaktär_bas'] = 'Okänd'

    # Detaljnivå och Områdestyp inaktiverade vi ju i JS-rullistan, 
    # så dessa kan vi behålla som 'Stadsdel' för databasens skull
    df_nyko3['Karaktär_detalj'] = 'Stadsdel'
    df_nyko3['Områdestyp'] = 'Stadsdel/Omland'

    # ==========================================
    # 🚀 2. FLAGGNING FÖR STUDENT- OCH VERKSAMHETSOMRÅDEN (NYKO 3)
    # ==========================================
    df_nyko3['Is_Student_Verksamhet'] = 0

    # Ange alla stadsdelar som ska sorteras bort med filtret
    student_verksamhet_stadsdelar = [
        'Mjärdevi', 
        # 'Valla',           # Innehåller stora studentområden (Colonia/Flamman)
        # 'Ryd',            # Om Ryds studentområde ska kunna sorteras bort separat
        # 'Mörtlösa',        # Verksamhetsområde
        'Tornby',           # Handels-/verksamhetsområde
        'Kallerstad',        # Verksamhetsområde
        'Stångebro'        # Verksamhetsområde
    ]

    # Tvätta namnen och jämför
    stadsdelar_clean = [s.lower().strip() for s in student_verksamhet_stadsdelar]
    mask_student = df_nyko3[area_col].astype(str).str.lower().str.strip().isin(stadsdelar_clean)
        
    # Sätt flaggan till 1
    df_nyko3.loc[mask_student, 'Is_Student_Verksamhet'] = 1
        
    # Utskrift i terminalen för att verifiera!
    flagagda = df_nyko3[df_nyko3['Is_Student_Verksamhet'] == 1][area_col].unique()
    print(f"🎓 Flaggade följande stadsdelar som Student/Verksamhet: {list(flagagda)}")

    # Återställ Karaktär_bas från Excel om det finns
    if 'df_excel' in locals() and area_col is not None:
        df_excel_unique = df_excel.drop_duplicates('Stadsdel').copy()
        excel_karaktar_map = df_excel_unique.set_index(df_excel_unique['Stadsdel'].astype(str).str.lower().str.strip())['Karaktär_bas'].to_dict()
        df_nyko3['Karaktär_bas'] = df_nyko3[area_col].astype(str).str.lower().str.strip().map(excel_karaktar_map).fillna('Okänd')
    else:
        df_nyko3['Karaktär_bas'] = 'Okänd'

    df_nyko3['Karaktär_detalj'] = 'Stadsdel'
    df_nyko3['Områdestyp'] = 'Stadsdel/Omland'

    # --- 10I. EXPORT ---
    print("\n⏳ Fyller luckor och rensar dubbletter för Nyko 3...")
    
    # 🚀 SÄKERHETSÅTGÄRD: Om 'basområde' på något sätt smugit sig in, döp om den!
    if 'basområde' in df_nyko3.columns:
        df_nyko3.rename(columns={'basområde': 'Stadsdel'}, inplace=True)

    # 🚀 FIX: Nu sorterar och städar vi enbart på 'Stadsdel'
    df_nyko3 = df_nyko3.sort_values(by=['Stadsdel', 'tid'])
    
    cols_to_fill_n3 = [c for c in df_nyko3.columns if c not in ['Stadsdel', 'tid']]
    df_nyko3[cols_to_fill_n3] = df_nyko3.groupby('Stadsdel')[cols_to_fill_n3].transform(lambda x: x.ffill().bfill())
    df_nyko3 = df_nyko3.drop_duplicates(subset=['tid', 'Stadsdel'], keep='last')

    # Exportera
    output_nyko3 = os.path.join(stat_formler_dir, 'segregation_base_nyko3.csv')
    df_nyko3.to_csv(output_nyko3, index=False, encoding='utf-8-sig')
    print(f"✅ KLART! Nyko 3 databas sparad: {output_nyko3}")

except Exception as e:
    print(f"\n❌ ETT FEL UPPSTOD VID SKAPANDET AV NYKO 3:")
    import traceback
    traceback.print_exc()

print("\n🚀 Hela pipelinen är nu körd!")

# ==========================================
# 11. AVSLUT OCH SPARA
# ==========================================
print("\n⏳ Sorterar, fyller luckor och sparar master-filen...")
try:
    # 1. Sortera
    final_df = final_df.sort_values(by=['basområde', 'tid']).reset_index(drop=True)
    
    # 2. Fyll tomma celler per basområde
    cols_to_fill_n4 = [c for c in final_df.columns if c not in ['basområde', 'tid']]
    final_df[cols_to_fill_n4] = final_df.groupby('basområde')[cols_to_fill_n4].transform(lambda x: x.ffill().bfill())
    
    # 3. Radera dubbletter
    final_df = final_df.drop_duplicates(subset=['tid', 'basområde'], keep='last')

    # ==========================================
    # 🚀 FIX: EXAKT MATCHNING MOT SEI_karaktär.xlsx (Namn -> Kommundelskluster)
    # ==========================================
    if 'df_excel' in locals() and 'Namn' in df_excel.columns and 'Kommundelskluster' in df_excel.columns:
        
        # 1. Kasta tomma rader i SEI-filen
        valid_rows = df_excel.dropna(subset=['Kommundelskluster']).copy()
        
        # 2. Bygg en ren ordbok: Namn -> Kommundelskluster
        clean_map = {}
        for _, row in valid_rows.iterrows():
            area_name = str(row['Namn']).replace('\xa0', ' ').strip()
            v = row['Kommundelskluster']
            v_str = str(v).strip()
            
            # Tvätta siffran (t.ex. 1.0 -> 1 eller 21.0 -> 21)
            try: 
                v_clean = str(int(float(v_str.replace(',', '.'))))
            except ValueError: 
                v_clean = v_str
            
            if v_clean.lower() != 'nan' and v_clean != '':
                # Spara med exakt stavning
                clean_map[area_name] = v_clean
                # Spara med enbart små bokstäver som säkerhetsnät för osynliga tecken
                clean_map[area_name.lower()] = v_clean

        # 3. Skottsäker sökfunktion
        def fetch_cluster(omrade_namn):
            o_str = str(omrade_namn).replace('\xa0', ' ').strip()
            # Test 1: Exakt matchning
            if o_str in clean_map:
                return clean_map[o_str]
            # Test 2: Gemener
            if o_str.lower() in clean_map:
                return clean_map[o_str.lower()]
            return 'Okänd'

        # 4. Applicera på final_df
        final_df['Kommundelskluster'] = final_df['basområde'].apply(fetch_cluster)
        
        # --- 🕵️‍♂️ DIAGNOSTIK ---
        missade = final_df[final_df['Kommundelskluster'] == 'Okänd']['basområde'].unique()
        if len(missade) > 0:
            print(f"\n⚠️ VARNING: Följande {len(missade)} basområden saknar fortfarande kluster i SEI-filen:")
            print(missade)
        else:
            print("\n🎉 SUCCESS! Alla 2366 rader i Nyko 4 fick exakt rätt Kommundelskluster!")

    else:
        final_df['Kommundelskluster'] = 'Okänd'
        print("❌ VARNING: Kolumnerna 'Namn' eller 'Kommundelskluster' hittades inte i df_excel!")
    # ==========================================

    # 4. Exportera Master
    final_df.to_csv(csv_output_path, index=False, encoding='utf-8-sig')
    print(f"💾 KLART! Ny master-databas sparad: {csv_output_path}")

except PermissionError:
    print(f"\n❌ FEL: Kunde inte spara. Har du '{os.path.basename(csv_output_path)}' öppen i Excel?")
except Exception as e:
    print(f"\n❌ ETT OVÄNTAT FEL UPPSTOD VID SPARANDET:")
    import traceback
    traceback.print_exc()