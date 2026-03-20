import os
import sys
import json
import pandas as pd
import numpy as np

print(f"Startar Befolknings-motorn. Arbetsmapp: {os.getcwd()}")
print("-" * 50)

def hitta_fil(filnamn):
    """Söker igenom arbetsmappen och undermappar efter filen."""
    for root, dirs, files in os.walk(os.getcwd()):
        if filnamn in files:
            return os.path.join(root, filnamn)
    return filnamn 

excel_fil = hitta_fil("befolkningsbarometern_månadsstatistik.xlsx")
excel_mapp = os.path.dirname(excel_fil) if os.path.dirname(excel_fil) else os.getcwd()

# Hoppa två mappar upp från Excel-filens plats för att spara publiceringsfilerna
spara_mapp = os.path.abspath(os.path.join(excel_mapp, "..", ".."))

if not os.path.exists(excel_fil):
    print(f"FEL: Kunde inte hitta {excel_fil}. Kontrollera att filen finns i mappen.")
    sys.exit()

print(f"1. Läser in konfiguration och åldersgrupper från {excel_fil}...")
print(f"   -> Resultatfilerna kommer att sparas i: {spara_mapp}")

# ---------------------------------------------------------
# 1. LÄS IN KONFIGURATION
# ---------------------------------------------------------
try:
    xls = pd.ExcelFile(excel_fil)
    troskel_namn = next((s for s in xls.sheet_names if s.lower() == "tröskel_polaritet"), "Tröskel_Polaritet")
    
    df_troskel = pd.read_excel(excel_fil, sheet_name=troskel_namn)
    df_troskel.columns = df_troskel.columns.str.strip() 
    df_troskel.rename(columns={df_troskel.columns[0]: 'Ålder_Indikator'}, inplace=True)
    df_troskel = df_troskel[df_troskel['Ålder_Indikator'].notna()].copy()
    
    alders_namn = next((s for s in xls.sheet_names if s.lower() == "åldersgrupper"), "Åldersgrupper")
    df_aldersgrupper = pd.read_excel(excel_fil, sheet_name=alders_namn)
    df_aldersgrupper.columns = df_aldersgrupper.columns.str.strip()
except Exception as e:
    print(f"Fel vid inläsning av konfigurationsflikar: {e}")
    sys.exit()

# ---------------------------------------------------------
# 2. FUNKTION FÖR ATT SMÄLTA OCH GRUPPERA ÅLDERSDATA
# ---------------------------------------------------------
def process_population_sheet(sheet_name, prefix=""):
    print(f"   -> Bearbetar flik: {sheet_name}")
    try:
        df_raw = pd.read_excel(excel_fil, sheet_name=sheet_name)
    except Exception:
        print(f"      Hittade ingen flik som heter {sheet_name}, hoppar över.")
        return pd.DataFrame()

    df_melt = df_raw.melt(id_vars=['Ålder'], var_name='Period', value_name='Antal')
    df_melt['Antal'] = pd.to_numeric(df_melt['Antal'].replace(['..', '-', '–'], np.nan), errors='coerce')
    
    df_melt['År'] = df_melt['Period'].str[:4].astype(int)
    df_melt['Månad'] = df_melt['Period'].str[-2:].astype(int)

    df_merged = df_melt.merge(df_aldersgrupper, on='Ålder', how='left')

    df_enskild = df_melt[['År', 'Månad', 'Ålder', 'Antal']].rename(columns={'Ålder': 'Indikator'})

    df_totalt = df_melt.groupby(['År', 'Månad'])['Antal'].sum().reset_index()
    df_totalt['Indikator'] = 'Totalt (Hela folkmängden)'

    group_dfs = []
    for col in df_aldersgrupper.columns:
        if col == 'Ålder': continue
        df_g = df_merged.groupby(['År', 'Månad', col])['Antal'].sum().reset_index()
        df_g = df_g.rename(columns={col: 'Indikator'})
        group_dfs.append(df_g)

    df_all = pd.concat([df_enskild, df_totalt] + group_dfs, ignore_index=True)
    df_all = df_all.dropna(subset=['Indikator'])

    df_pivot = df_all.pivot_table(index=['År', 'Månad'], columns='Indikator', values='Antal').reset_index()

    if prefix:
        df_pivot.columns = [f"{prefix}_{c}" if c not in ['År', 'Månad'] else c for c in df_pivot.columns]

    return df_pivot

# ---------------------------------------------------------
# 3. KÖR BEARBETNINGEN (MED BÅDA PROGNOSFLIKARNA)
# ---------------------------------------------------------
print("2. Smälter, grupperar och sammanställer data...")
df_lkpg = process_population_sheet("Linköping")
df_riket = process_population_sheet("Riket", prefix="Riket")
df_prognos = process_population_sheet("Prognos", prefix="Prognos")

try:
    df_forandring = pd.read_excel(excel_fil, sheet_name="Befolkningsförändringar")
    df_forandring['År'] = df_forandring['År_månad'].str[:4].astype(int)
    df_forandring['Månad'] = df_forandring['År_månad'].str[-2:].astype(int)
    df_forandring = df_forandring.drop(columns=['År_månad'])
    
    for col in df_forandring.columns:
        if col not in ['År', 'Månad']:
            df_forandring[col] = pd.to_numeric(df_forandring[col].replace(['..', '-'], np.nan), errors='coerce')
except Exception as e:
    df_forandring = pd.DataFrame(columns=['År', 'Månad'])

try:
    df_prog_forandring = pd.read_excel(excel_fil, sheet_name="Prognos_förändring")
    df_prog_forandring['År'] = df_prog_forandring['År_månad'].str[:4].astype(int)
    df_prog_forandring['Månad'] = df_prog_forandring['År_månad'].str[-2:].astype(int)
    df_prog_forandring = df_prog_forandring.drop(columns=['År_månad'])
    
    for col in df_prog_forandring.columns:
        if col not in ['År', 'Månad']:
            df_prog_forandring[col] = pd.to_numeric(df_prog_forandring[col].replace(['..', '-'], np.nan), errors='coerce')
except Exception as e:
    print("Ingen Prognos_förändring hittades (eller fel format).", e)
    df_prog_forandring = pd.DataFrame(columns=['År', 'Månad'])

# Slå ihop alla flikar
df_main = df_lkpg.copy()
if not df_riket.empty:
    df_main = pd.merge(df_main, df_riket, on=['År', 'Månad'], how='outer')

if not df_prognos.empty:
    # Döper om kolumnerna från "Prognos_Totalt" till "Totalt_Prognos_Slutgiltig"
    prognos_renames = {col: col.replace('Prognos_', '') + '_Prognos_Slutgiltig' for col in df_prognos.columns if col not in ['År', 'Månad']}
    df_prognos = df_prognos.rename(columns=prognos_renames)
    df_main = pd.merge(df_main, df_prognos, on=['År', 'Månad'], how='outer')

if not df_forandring.empty:
    df_main = pd.merge(df_main, df_forandring, on=['År', 'Månad'], how='outer')

if not df_prog_forandring.empty:
    # Döper om kolumnerna från "Födda" till "Födda_Prognos_Slutgiltig"
    prog_for_renames = {col: col + '_Prognos_Slutgiltig' for col in df_prog_forandring.columns if col not in ['År', 'Månad']}
    df_prog_forandring = df_prog_forandring.rename(columns=prog_for_renames)
    df_main = pd.merge(df_main, df_prog_forandring, on=['År', 'Månad'], how='outer')

df_main = df_main.sort_values(['År', 'Månad']).reset_index(drop=True)

# ---------------------------------------------------------
# 4. BYGG DASHBOARD-KOLUMNER (R12 etc)
# ---------------------------------------------------------
print("3. Bygger Månads- och R12-värden för dashboarden...")
for index, row in df_troskel.iterrows():
    indikator = str(row['Ålder_Indikator']).strip()
    kategori = str(row.get('Kategori_i_Data', '')).strip().lower()
    
    if indikator not in df_main.columns:
        continue
    
    col_utfall = f"{indikator}_Manad"
    df_main[col_utfall] = df_main[indikator]
    
    col_riket = f"Riket_{indikator}_Manad"
    df_main[col_riket] = df_main[f"Riket_{indikator}"] if f"Riket_{indikator}" in df_main.columns else np.nan

    df_main[f"{indikator}_Manad_Pct_1M"] = df_main[col_utfall].pct_change(periods=1) * 100
    df_main[f"Riket_{indikator}_Manad_Pct_1M"] = df_main[col_riket].pct_change(periods=1) * 100
    df_main[f"{indikator}_Manad_Pct_12M"] = df_main[col_utfall].pct_change(periods=12) * 100
    df_main[f"Riket_{indikator}_Manad_Pct_12M"] = df_main[col_riket].pct_change(periods=12) * 100

    col_r12 = f"{indikator}_R12"
    
    if "förändring" in kategori or "flytt" in kategori.lower() or indikator in ['Födda', 'Döda', 'Inflyttning', 'Utflyttning']:
        df_main[col_r12] = df_main[col_utfall].rolling(12, min_periods=12).sum()
        df_main[f"Riket_{indikator}_R12"] = df_main[col_riket].rolling(12, min_periods=12).sum() if col_riket in df_main.columns else np.nan
    else:
        df_main[col_r12] = df_main[col_utfall]
        df_main[f"Riket_{indikator}_R12"] = df_main[col_riket]

    df_main[f"{indikator}_Polaritet"] = row.get('Polaritet', np.nan)
    df_main[f"{indikator}_Troskel"] = row.get('Tröskel', np.nan)
    df_main[f"{indikator}_Absolut_R12"] = row.get('Absolut_R12', np.nan)
    df_main[f"{indikator}_Minitabell"] = row.get('Minitabell_Kolumn', np.nan)
    df_main[f"{indikator}_Minitabell_Sort"] = row.get('Minitabell_Sortering', np.nan)
    df_main[f"{indikator}_Alternativ_rubrik"] = row.get('Alternativ_tabellrubrik', np.nan)

# ---------------------------------------------------------
# 5. GENERERA RAPPORTTEXT & AI-FAKTA
# ---------------------------------------------------------
print("4. Genererar robot-fakta för senaste månaden...")
try:
    df_texter = pd.read_excel(excel_fil, sheet_name="Rapporttext")
    
    df_valid = df_main[df_main['Totalt (Hela folkmängden)_Manad'].notna()]
    if not df_valid.empty:
        senaste_raden = df_valid.iloc[-1]
        s_ar = int(senaste_raden['År'])
        s_manad = int(senaste_raden['Månad'])
        
        folk_nu = senaste_raden['Totalt (Hela folkmängden)_Manad']
        
        folk_fg_manad = np.nan
        fg_rad = df_valid[(df_valid['År'] == (s_ar if s_manad > 1 else s_ar - 1)) & (df_valid['Månad'] == (s_manad - 1 if s_manad > 1 else 12))]
        if not fg_rad.empty: folk_fg_manad = fg_rad.iloc[-1]['Totalt (Hela folkmängden)_Manad']
        
        folk_fg_ar = np.nan
        fg_ar_rad = df_valid[(df_valid['År'] == s_ar - 1) & (df_valid['Månad'] == s_manad)]
        if not fg_ar_rad.empty: folk_fg_ar = fg_ar_rad.iloc[-1]['Totalt (Hela folkmängden)_Manad']
        
        fodda = senaste_raden.get('Födda_Manad', 0)
        doda = senaste_raden.get('Döda_Manad', 0)
        inflytt = senaste_raden.get('Inflyttning_Manad', 0)
        utflytt = senaste_raden.get('Utflyttning_Manad', 0)
        
        diff_manad = folk_nu - folk_fg_manad if pd.notna(folk_fg_manad) else 0
        diff_ar = folk_nu - folk_fg_ar if pd.notna(folk_fg_ar) else 0
        flyttnetto = inflytt - utflytt
        fodselnetto = fodda - doda
        
        manader = ["Januari", "Februari", "Mars", "April", "Maj", "Juni", "Juli", "Augusti", "September", "Oktober", "November", "December"]
        manad_namn = manader[s_manad - 1]
        
        fakta_text = (f"I {manad_namn.lower()} {s_ar} uppgick folkmängden i Linköping till {int(folk_nu):,}. "
                      f"Det innebär en förändring med {int(diff_manad):+} personer jämfört med föregående månad, "
                      f"och {int(diff_ar):+} personer jämfört med samma månad föregående år. "
                      f"Under månaden föddes {int(fodda)} barn och {int(doda)} personer avled (födelsenetto {int(fodselnetto):+}). "
                      f"Samtidigt var kommunens totala flyttnetto {int(flyttnetto):+} personer.").replace(',', ' ')
        
        idx = df_texter[(df_texter['År'] == s_ar) & (df_texter['Månad'] == s_manad) & (df_texter['Rapportvy'] == 'Befolkning')].index
        if not idx.empty:
            df_texter.loc[idx[0], 'Autogenererad_Fakta'] = fakta_text
            if df_texter.loc[idx[0], 'Robot_Fakta'] == 'A':
                df_texter.loc[idx[0], 'Färdig_Analystext'] = fakta_text
        else:
            ny_rad = pd.DataFrame([{'År': s_ar, 'Månad': s_manad, 'Rapportvy': 'Befolkning', 'Autogenererad_Fakta': fakta_text, 'Robot_Fakta': 'A', 'Färdig_Analystext': fakta_text}])
            df_texter = pd.concat([df_texter, ny_rad], ignore_index=True)
            
    out_text_path = os.path.join(spara_mapp, "befolkning_texter.csv")
    df_texter.to_csv(out_text_path, sep=';', index=False, encoding='cp1252')
except Exception as e:
    print(f"Gick inte att generera rapporttexter: {e}")

# ---------------------------------------------------------
# 6. STÄDA OCH EXPORTERA DATA FÖR WEBBSIDAN
# ---------------------------------------------------------
print("5. Exporterar CSV för webben...")
def format_swedish_decimals(val):
    if pd.isna(val) or val == "" or val == "inf" or val == "-inf": return ""
    if isinstance(val, float): return f"{val:.2f}".replace('.', ',')
    return val

# Se till att _Prognos_Slutgiltig finns med i behåll_kolumner!
behåll_kolumner = ['År', 'Månad'] + [c for c in df_main.columns if c.endswith(('_Manad', '_R12', '_Polaritet', '_Troskel', '_Absolut_R12', '_Minitabell', '_Minitabell_Sort', '_Alternativ_rubrik', '_Pct_1M', '_Pct_12M', '_Prognos_Slutgiltig'))]
df_export = df_main[behåll_kolumner].copy()

for col in df_export.columns:
    if col not in ['År', 'Månad'] and not col.endswith(('_Polaritet', '_Troskel', '_Absolut_R12', '_Minitabell', '_Minitabell_Sort', '_Alternativ_rubrik')):
        df_export[col] = df_export[col].apply(format_swedish_decimals)

out_csv = os.path.join(spara_mapp, "befolkning_data.csv")
df_export.to_csv(out_csv, sep=';', index=False, encoding='cp1252')

# ---------------------------------------------------------
# 7. SKAPA DIAGRAM-KONFIGURATION (JSON)
# ---------------------------------------------------------
print("6. Skapar JSON-konfiguration...")
diagram_config = {"1": [], "2": [], "3": [], "4": []}

for index, row in df_troskel.iterrows():
    dash_namn = str(row['Ålder_Indikator']).strip()
    if dash_namn not in df_main.columns: continue
        
    endast_drilldown = str(row.get('Drill_Down', '')).strip().lower() == 'ja'
            
    drill_komp = []
    drill_farg = []
    if pd.notna(row.get('Drilldown_Komponenter')):
        drill_komp = [k.strip() for k in str(row['Drilldown_Komponenter']).split(',') if k.strip()]
    if pd.notna(row.get('Drilldown_Farger')):
        drill_farg = [f.strip() for f in str(row['Drilldown_Farger']).split(',') if f.strip()]

    drill_typ = "stapel" 
    if pd.notna(row.get('Drilldown_Typ')):
        val = str(row['Drilldown_Typ']).strip().lower()
        if val not in ['nan', '']: drill_typ = val

    label = row.get('Alternativ_tabellrubrik', dash_namn)
    if pd.isna(label):
        label = str(dash_namn).replace('_', ' ')
    else:
        label = str(label).split('|')[0].strip()

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
            if col_name in df_troskel.columns and str(row[col_name]).strip().lower() == 'ja':
                diagram_config[str(i)].append(ind_obj)

out_json = os.path.join(spara_mapp, "befolkning_config.json")
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(diagram_config, f, ensure_ascii=False, indent=4)

print(f"KLAR! All befolkningsdata processades och sparades till: {spara_mapp}")