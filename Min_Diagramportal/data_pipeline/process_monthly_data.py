import os
import sys
import json
import pandas as pd
import numpy as np
from pyaxis import pyaxis

# ---------------------------------------------------------
# 1. ARBETSMILJÖ OCH SMART FIL-SÖKMOTOR
# ---------------------------------------------------------
print(f"Startar skript. VS Code Arbetsmapp är satt till: {os.getcwd()}")
print("-" * 50)

def hitta_fil(filnamn):
    """Söker igenom arbetsmappen och ALLA undermappar efter filen."""
    for root, dirs, files in os.walk(os.getcwd()):
        if filnamn in files:
            return os.path.join(root, filnamn)
    return filnamn 

html_sokvag = hitta_fil("manadsbarometern.html")
if html_sokvag != "manadsbarometern.html":
    spara_mapp = os.path.dirname(html_sokvag)
else:
    spara_mapp = os.getcwd()

# ---------------------------------------------------------
# 2. STANDARDKOD FÖR TEXTFIX 
# ---------------------------------------------------------
encoding_fix = {
    'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö',
    'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
    'Ã©': 'é', 'Ã¨': 'è', 'Ã‰': 'É',
    "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö" 
}
    
def fix_text(text):
    if not isinstance(text, str): return text
    for bad, good in encoding_fix.items():
        text = text.replace(bad, good)
    return text

month_map = {"Januari": 1, "Februari": 2, "Mars": 3, "April": 4, "Maj": 5, "Juni": 6, 
             "Juli": 7, "Augusti": 8, "September": 9, "Oktober": 10, "November": 11, "December": 12}

# ---------------------------------------------------------
# 3. LÄS IN STYRFIL (Endast Tillgängliga indikatorer)
# ---------------------------------------------------------
styrfil_path = hitta_fil("Styrfil_Manad.xlsx")
print(f"1. Laddar konfiguration från: {styrfil_path}")

try:
    df_styrning = pd.read_excel(styrfil_path, sheet_name="Styrning")
    df_styrning = df_styrning[df_styrning['Tillgänglig'] == 'Ja'].copy()
    df_styrning = df_styrning.replace(['-', '–', '—', '−'], 0).replace(['..', ' ', ''], np.nan)
except Exception as e:
    print(f"\n--- FEL VID INLÄSNING AV STYRFIL ---")
    print(f"Systemfel: {e}")
    sys.exit()

# ---------------------------------------------------------
# 4. LÄS IN RAW DATA (PX)
# ---------------------------------------------------------
print("2. Läser och tvättar PX-data (Grunduppgifter)...")
px_file_path = hitta_fil("ksi5555.px")

try:
    px_obj = pyaxis.parse(px_file_path, encoding='cp1252')
except Exception as e:
    print(f"Fel vid inläsning av {px_file_path}. Fel: {e}")
    sys.exit()
    
df_px = px_obj['DATA']
df_px = df_px[df_px['tabelluppgift'] == 'Grunduppgift'].copy()

df_px['År'] = df_px['tid'].astype(int)
df_px['Månad'] = df_px['månad'].map(month_map)
df_px['DATA'] = df_px['DATA'].replace(['-', '–', '—', '−'], 0).replace('..', np.nan)
df_px['DATA'] = pd.to_numeric(df_px['DATA'], errors='coerce')
df_px['indikator'] = df_px['indikator'].apply(fix_text)

df_lkpg = df_px[df_px['region'] == 'Linköping'].pivot_table(index=['År', 'Månad'], columns='indikator', values='DATA').reset_index()
df_riket = df_px[df_px['region'] == 'Riket'].pivot_table(index=['År', 'Månad'], columns='indikator', values='DATA').reset_index()
df_riket.columns = [f"Riket_{col}" if col not in ['År', 'Månad'] else col for col in df_riket.columns]

df_main = pd.merge(df_lkpg, df_riket, on=['År', 'Månad'], how='outer')
df_main = df_main.sort_values(['År', 'Månad']).reset_index(drop=True)

# ---------------------------------------------------------
# 5. LÄS IN PROGNOSER OCH TEXTER
# ---------------------------------------------------------
print("3. Läser in prognoser och kommentarer...")
prog_path = hitta_fil("Prognoser_Manad.xlsx")
inm_path = hitta_fil("Inmatning_Manad.xlsx")

try:
    df_prognos = pd.read_excel(prog_path)
    if 'Kvartal' in df_prognos.columns and 'Månad' not in df_prognos.columns:
        df_prognos = df_prognos.rename(columns={'Kvartal': 'Månad'})
    df_prognos = df_prognos.replace(['-', '–', '—', '−'], 0).replace(['..', ' ', ''], np.nan)
    df_main = pd.merge(df_main, df_prognos, on=['År', 'Månad'], how='left')
except Exception:
    pass

try:
    df_texter = pd.read_excel(inm_path, sheet_name=0)
    df_texter = df_texter.fillna('').replace(['..', '-', '–', '—', '−'], '')
    out_text_path = os.path.join(spara_mapp, "manadsbarometern_texter.csv")
    df_texter.to_csv(out_text_path, sep=';', index=False, encoding='cp1252')
except Exception:
    pass

# ---------------------------------------------------------
# 6. BERÄKNINGAR OCH VATTENFALLSMODELL
# ---------------------------------------------------------
print("4. Kör R12-beräkningar och vattenfallsmodell för mål...")

for index, row in df_styrning.iterrows():
    scb_namn = row['SCB_Namn_i_filen']
    dash_namn = row['Dashboard_Namn']
    if scb_namn not in df_main.columns: continue
        
    col_utfall = f"{dash_namn}_Manad"
    df_main[col_utfall] = df_main[scb_namn]
    col_riket = f"Riket_{dash_namn}_Manad"
    df_main[col_riket] = df_main[f"Riket_{scb_namn}"] if f"Riket_{scb_namn}" in df_main.columns else np.nan

    df_main[f"{dash_namn}_Manad_Pct_1M"] = df_main[col_utfall].pct_change(periods=1) * 100
    df_main[f"Riket_{dash_namn}_Manad_Pct_1M"] = df_main[col_riket].pct_change(periods=1) * 100
    df_main[f"{dash_namn}_Manad_Pct_12M"] = df_main[col_utfall].pct_change(periods=12) * 100
    df_main[f"Riket_{dash_namn}_Manad_Pct_12M"] = df_main[col_riket].pct_change(periods=12) * 100

    col_r12 = f"{dash_namn}_R12"
    regel = row['R12_Regel']
    # FIX: Tvingar R12 att bara rita värden när det faktiskt finns 12 månader att bygga på
    if regel == 'SUM':
        df_main[col_r12] = df_main[col_utfall].rolling(12, min_periods=12).sum()
        df_main[f"Riket_{col_r12}"] = df_main[col_riket].rolling(12, min_periods=12).sum()
    elif regel == 'SNITT':
        df_main[col_r12] = df_main[col_utfall].rolling(12, min_periods=12).mean()
        df_main[f"Riket_{col_r12}"] = df_main[col_riket].rolling(12, min_periods=12).mean()
    else: 
        df_main[col_r12] = df_main[col_utfall]
        df_main[f"Riket_{col_r12}"] = df_main[col_riket]

    historik_utfall = df_main[col_r12].shift(12) 
    riket_utfall_historik = df_main[f"Riket_{col_r12}"].shift(12)
    riket_utveckling_pct = (df_main[f"Riket_{col_r12}"] - riket_utfall_historik) / riket_utfall_historik

    prog_prio1_col = f"{dash_namn}_Prognos"
    prog_prio2_col = f"{dash_namn}_Egen_Utveckling"
    if prog_prio1_col not in df_main.columns: df_main[prog_prio1_col] = np.nan
    if prog_prio2_col not in df_main.columns: df_main[prog_prio2_col] = np.nan

    hist_years_raw = row.get('Mal_Historiskt_Snitt_Ar', np.nan)
    hist_years = np.nan
    prio4_series = pd.Series(np.nan, index=df_main.index)
    if pd.notna(hist_years_raw):
        try:
            hist_years = int(float(hist_years_raw))
            for i in range(len(df_main)):
                if i >= 12 * hist_years:
                    prio4_series.iloc[i] = df_main[col_r12].iloc[i-(12*hist_years) : i : 12].mean()
        except (ValueError, TypeError):
            pass

    conditions = [
        df_main[prog_prio1_col].notna(),
        df_main[prog_prio2_col].notna(),
        pd.notna(row.get('Standard_Utveckling_Procent', np.nan)),
        pd.notna(hist_years),
        pd.notna(row.get('Procentenheter_Over_Riket', np.nan))
    ]

    choices = [
        df_main[prog_prio1_col],
        historik_utfall * (1 + df_main[prog_prio2_col]),
        historik_utfall * (1 + (row.get('Standard_Utveckling_Procent', 0) if pd.notna(row.get('Standard_Utveckling_Procent', np.nan)) else 0)),
        prio4_series,
        historik_utfall * (1 + (riket_utveckling_pct + (row.get('Procentenheter_Over_Riket', 0) if pd.notna(row.get('Procentenheter_Over_Riket', np.nan)) else 0)))
    ]

    df_main[f"{dash_namn}_Prognos_Slutgiltig"] = np.select(conditions, choices, default=np.nan)
    df_main[f"{dash_namn}_Polaritet"] = row.get('Polaritet', np.nan)
    df_main[f"{dash_namn}_Troskel"] = row.get('Troskel', np.nan)
    df_main[f"{dash_namn}_Absolut_R12"] = row.get('Absolut_R12', np.nan)
    df_main[f"{dash_namn}_Minitabell"] = row.get('Minitabell_Kolumn', np.nan)
    df_main[f"{dash_namn}_Minitabell_Sort"] = row.get('Minitabell_Sortering', np.nan)
    df_main[f"{dash_namn}_Alternativ_rubrik"] = row.get('Alternativ_tabellrubrik', np.nan)

# ---------------------------------------------------------
# 7. STÄDA OCH EXPORTERA CSV
# ---------------------------------------------------------
print("5. Formaterar och exporterar CSV...")
scb_cols = [c for c in df_styrning['SCB_Namn_i_filen'].tolist() if c in df_main.columns]
riket_scb_cols = [f"Riket_{c}" for c in scb_cols if f"Riket_{c}" in df_main.columns]
df_main = df_main.drop(columns=scb_cols + riket_scb_cols)

def format_swedish_decimals(val):
    if pd.isna(val) or val == "" or val == "inf" or val == "-inf": return ""
    if isinstance(val, float): return f"{val:.2f}".replace('.', ',')
    return val

for col in df_main.columns:
    if col not in ['År', 'Månad'] and not col.endswith(('Polaritet', 'Troskel', 'Absolut_R12', 'Minitabell', 'Minitabell_Sort', 'Alternativ_rubrik')):
        df_main[col] = df_main[col].apply(format_swedish_decimals)

out_csv = os.path.join(spara_mapp, "manadsbarometern_data.csv")
df_main.to_csv(out_csv, sep=';', index=False, encoding='cp1252')

# ---------------------------------------------------------
# 8. SKAPA DIAGRAM-KONFIGURATION (JSON) MED DRILLDOWN-LOGIK
# ---------------------------------------------------------
print("6. Skapar konfigurationsfil för diagrammen...")
diagram_config = {"1": [], "2": [], "3": [], "4": []}

for index, row in df_styrning.iterrows():
    dash_namn = row['Dashboard_Namn']
    label = row.get('Alternativ_tabellrubrik', dash_namn)
    if pd.isna(label):
        label = str(dash_namn).replace('_', ' ')
    else:
        label = str(label).split('|')[0].strip()

    endast_drilldown = False
    if 'Drill_Down' in df_styrning.columns:
        if str(row['Drill_Down']).strip().lower() == 'ja':
            endast_drilldown = True
            
    drill_komp = []
    drill_farg = []
    
    if 'Drilldown_Komponenter' in df_styrning.columns and pd.notna(row['Drilldown_Komponenter']):
        komp_str = str(row['Drilldown_Komponenter']).split(',')
        drill_komp = [k.strip() for k in komp_str if k.strip()]
        
    if 'Drilldown_Farger' in df_styrning.columns and pd.notna(row['Drilldown_Farger']):
        farg_str = str(row['Drilldown_Farger']).split(',')
        drill_farg = [f.strip() for f in farg_str if f.strip()]

    drill_typ = "stapel" 
    typ_kolumn = next((col for col in df_styrning.columns if 'Drilldown_Typ' in str(col)), None)
    
    if typ_kolumn and pd.notna(row[typ_kolumn]):
        val = str(row[typ_kolumn]).strip().lower()
        if val != 'nan' and val != '':
            drill_typ = val

    ind_obj = {
        "id": dash_namn,
        "label": label,
        "drilldown_komponenter": drill_komp,
        "drilldown_farger": drill_farg,
        "drilldown_typ": drill_typ
    }

    if not endast_drilldown:
        for i in range(1, 5):
            col_name = f"Visas_i_Diagram_{i}"
            if col_name in df_styrning.columns and str(row[col_name]).strip().lower() == 'ja':
                diagram_config[str(i)].append(ind_obj)

out_json = os.path.join(spara_mapp, "diagram_config.json")
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(diagram_config, f, ensure_ascii=False, indent=4)

print(f"KLAR! All data processades och sparades till: {spara_mapp}")