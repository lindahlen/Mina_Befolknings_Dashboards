import os
import sys
import json
import pandas as pd
import numpy as np
import traceback
import re
import time

varningar = []

def hitta_fil(filnamn):
    """Söker igenom arbetsmappen och undermappar efter filen."""
    for root, dirs, files in os.walk(os.getcwd()):
        if filnamn in files:
            return os.path.join(root, filnamn)
    return filnamn 

def standardisera_tidskolumner(df):
    """Tvättar kolumnnamn för att säkerställa att vi hittar År och Månad oavsett stavning"""
    cols = {c: str(c).strip() for c in df.columns}
    df.rename(columns=cols, inplace=True)
    for c in df.columns:
        c_low = str(c).lower()
        if c_low == 'år': df.rename(columns={c: 'År'}, inplace=True)
        elif c_low == 'månad': df.rename(columns={c: 'Månad'}, inplace=True)
        elif c_low == 'år_månad' or c_low == 'år månad': df.rename(columns={c: 'År_månad'}, inplace=True)
    return df

def hantera_tid(df):
    """
    En smart funktion som läser av tidsformat ("2026M01", "202601" eller bara "2026").
    Om det bara är ett år (Årsprognos) så expanderas datan automatiskt till årets alla 12 månader!
    """
    if df.empty: return df
    
    if 'År_månad' in df.columns:
        df = df.dropna(subset=['År_månad'])
        period_str = df['År_månad'].astype(str).str.upper().str.strip()
        df['År'] = period_str.str[:4].astype(int)
        
        df['Månad'] = 0
        mask_monthly = period_str.str.len() > 4
        df.loc[mask_monthly, 'Månad'] = pd.to_numeric(period_str.loc[mask_monthly].str[-2:], errors='coerce').fillna(0)
        df['Månad'] = df['Månad'].astype(int)
        
        df = df.drop(columns=['År_månad'])
        
    elif 'År' in df.columns and 'Månad' not in df.columns:
        df['Månad'] = 0
        
    if 'År' in df.columns and 'Månad' in df.columns:
        df['Månad'] = df['Månad'].fillna(0).astype(int)
        
        annual_data = df[df['Månad'] == 0].copy()
        monthly_data = df[df['Månad'] != 0].copy()
        
        if not annual_data.empty:
            expanded = []
            for m in range(1, 13):
                temp = annual_data.copy()
                temp['Månad'] = m
                expanded.append(temp)
            df = pd.concat([monthly_data] + expanded, ignore_index=True)
        else:
            df = monthly_data
            
    return df

def main():
    global varningar
    print(f"Startar Befolknings-motorn. Arbetsmapp: {os.getcwd()}")
    print("-" * 50)

    excel_fil = hitta_fil("befolkningsbarometern_månadsstatistik.xlsx")
    excel_mapp = os.path.dirname(excel_fil) if os.path.dirname(excel_fil) else os.getcwd()

    spara_mapp = os.path.abspath(os.path.join(excel_mapp, "..", ".."))

    if not os.path.exists(excel_fil):
        print(f"FEL: Kunde inte hitta {excel_fil}. Kontrollera att filen finns i mappen.")
        return

    print(f"1. Läser in konfiguration och åldersgrupper från {excel_fil}...")

    # ---------------------------------------------------------
    # 1. LÄS IN KONFIGURATION
    # ---------------------------------------------------------
    xls = pd.ExcelFile(excel_fil)
    troskel_namn = next((s for s in xls.sheet_names if s.lower() == "tröskel_polaritet"), "Tröskel_Polaritet")
    
    df_troskel = pd.read_excel(excel_fil, sheet_name=troskel_namn)
    
    # Kasta bort 'Stöd_manuell' direkt så att den aldrig bearbetas eller exporteras
    if 'Stöd_manuell' in df_troskel.columns:
        df_troskel = df_troskel.drop(columns=['Stöd_manuell'])
    
    expected_cols = [
        'Ålder_Indikator', 'Kategori_i_Data', 'Polaritet', 'Tröskel', 'Absolut_R12', 
        'Minitabell_Kolumn', 'Minitabell_Sortering', 'Alternativ_tabellrubrik',
        'Drill_Down', 'Drilldown_Komponenter', 'Drilldown_Farger', 'Drilldown_Typ',
        'Visas_i_Diagram_1', 'Visas_i_Diagram_2', 'Visas_i_Diagram_3', 'Visas_i_Diagram_4',
        'Tillgänglig'
    ]
    
    new_cols = []
    for c in df_troskel.columns:
        c_norm = str(c).strip().replace(' ', '_').lower().replace('ä', 'a').replace('ö', 'o')
        match = next((exp for exp in expected_cols if exp.lower().replace('ä', 'a').replace('ö', 'o') == c_norm), str(c).strip())
        new_cols.append(match)
    df_troskel.columns = new_cols
    
    if 'Ålder_Indikator' not in df_troskel.columns:
        df_troskel.rename(columns={df_troskel.columns[0]: 'Ålder_Indikator'}, inplace=True)
        
    df_troskel = df_troskel[df_troskel['Ålder_Indikator'].notna()].copy()
    
    if 'Tillgänglig' in df_troskel.columns:
        df_troskel = df_troskel[df_troskel['Tillgänglig'].astype(str).str.strip().str.lower() == 'ja'].copy()
    
    alders_namn = next((s for s in xls.sheet_names if s.lower() == "åldersgrupper"), "Åldersgrupper")
    df_aldersgrupper = pd.read_excel(excel_fil, sheet_name=alders_namn)
    
    df_aldersgrupper.columns = [str(c).strip() for c in df_aldersgrupper.columns]
    
    for col in df_aldersgrupper.columns:
        if df_aldersgrupper[col].dtype == 'object':
            df_aldersgrupper[col] = df_aldersgrupper[col].str.strip()
            
    if 'Ålder' in df_aldersgrupper.columns:
        df_aldersgrupper['Ålder'] = df_aldersgrupper['Ålder'].astype(str).str.strip()

    # ---------------------------------------------------------
    # 2. FUNKTION FÖR ATT SMÄLTA OCH GRUPPERA ÅLDERSDATA
    # ---------------------------------------------------------
    def process_population_sheet(sheet_name, prefix=""):
        print(f"   -> Bearbetar flik: {sheet_name}")
        empty_df = pd.DataFrame(columns=['År', 'Månad'])
        
        try:
            df_raw = pd.read_excel(excel_fil, sheet_name=sheet_name)
            df_raw.columns = [str(c).strip() for c in df_raw.columns]
        except Exception:
            print(f"      Hittade ingen flik som heter {sheet_name}, hoppar över.")
            return empty_df

        if 'Ålder' in df_raw.columns:
            df_raw['Ålder'] = df_raw['Ålder'].astype(str).str.strip()
            df_melt = df_raw.melt(id_vars=['Ålder'], var_name='Period', value_name='Antal')
        else:
            time_cols = [c for c in df_raw.columns if str(c).lower() in ['period', 'år_månad', 'år månad', 'tid', 'månad']]
            if time_cols:
                time_col = time_cols[0]
                df_melt = df_raw.melt(id_vars=[time_col], var_name='Ålder', value_name='Antal')
                df_melt.rename(columns={time_col: 'Period'}, inplace=True)
            elif 'År' in df_raw.columns and 'Månad' in df_raw.columns:
                df_melt = df_raw.melt(id_vars=['År', 'Månad'], var_name='Ålder', value_name='Antal')
                df_melt['Period'] = df_melt['År'].astype(str) + "M" + df_melt['Månad'].astype(str).str.zfill(2)
            else:
                first_col = df_raw.columns[0]
                df_melt = df_raw.melt(id_vars=[first_col], var_name='Ålder', value_name='Antal')
                df_melt.rename(columns={first_col: 'Period'}, inplace=True)

        df_melt = df_melt.dropna(subset=['Period', 'Ålder'])
        df_melt = df_melt[~df_melt['Period'].astype(str).str.startswith('Unnamed')]
        
        df_melt['Antal'] = df_melt['Antal'].astype(str).str.replace(r'\s+', '', regex=True)
        df_melt['Antal'] = pd.to_numeric(df_melt['Antal'].replace(['..', '-', '–', 'nan'], np.nan), errors='coerce')
        
        period_str = df_melt['Period'].astype(str).str.upper().str.strip()
        df_melt['År'] = period_str.str[:4].astype(int)
        df_melt['Månad'] = 0
        mask_monthly = period_str.str.len() > 4
        df_melt.loc[mask_monthly, 'Månad'] = pd.to_numeric(period_str.loc[mask_monthly].str[-2:], errors='coerce').fillna(0)
        df_melt['Månad'] = df_melt['Månad'].astype(int)

        annual_data = df_melt[df_melt['Månad'] == 0].copy()
        monthly_data = df_melt[df_melt['Månad'] != 0].copy()
        
        if not annual_data.empty:
            expanded = []
            for m in range(1, 13):
                temp = annual_data.copy()
                temp['Månad'] = m
                expanded.append(temp)
            df_melt = pd.concat([monthly_data] + expanded, ignore_index=True)
        else:
            df_melt = monthly_data

        def clean_age(s):
            s = str(s).strip().lower()
            if s.endswith('.0'): s = s[:-2]
            return re.sub(r'[^\d\+\-]', '', s)

        df_melt['Ålder_match'] = df_melt['Ålder'].apply(clean_age)
        df_aldersgrupper['Ålder_match'] = df_aldersgrupper['Ålder'].apply(clean_age)

        df_merged = df_melt.merge(df_aldersgrupper.drop(columns=['Ålder']), on='Ålder_match', how='left')

        test_col = [c for c in df_aldersgrupper.columns if c not in ['Ålder', 'Ålder_match']][0]
        if df_merged[test_col].isna().all() and len(df_aldersgrupper.columns) > 2:
            msg = f"LARM i {sheet_name}: Ingen ålder i grunddatan matchade åldrarna i fliken 'Åldersgrupper'!"
            varningar.append(msg)
            print(f"      -> VARNING: {msg}")

        df_enskild = df_melt[['År', 'Månad', 'Ålder', 'Antal']].rename(columns={'Ålder': 'Indikator'})

        df_only_ages = df_melt[df_melt['Ålder_match'] != '']
        df_totalt = df_only_ages.groupby(['År', 'Månad'])['Antal'].sum().reset_index()
        df_totalt['Indikator'] = 'Totalt (Hela folkmängden)'

        group_dfs = []
        for col in df_aldersgrupper.columns:
            if col in ['Ålder', 'Ålder_match']: continue
            
            df_temp_tot = df_merged[df_merged[col].notna()].copy()
            if not df_temp_tot.empty:
                df_temp_tot['Indikator'] = col
                df_g_tot = df_temp_tot.groupby(['År', 'Månad', 'Indikator'])['Antal'].sum().reset_index()
                group_dfs.append(df_g_tot)
            
            df_temp_sub = df_merged[df_merged[col].notna()].copy()
            if not df_temp_sub.empty:
                df_g_sub = df_temp_sub.groupby(['År', 'Månad', col])['Antal'].sum().reset_index()
                df_g_sub = df_g_sub.rename(columns={col: 'Indikator'})
                group_dfs.append(df_g_sub)

        df_all = pd.concat([df_enskild, df_totalt] + group_dfs, ignore_index=True)
        df_all = df_all.dropna(subset=['Indikator'])
        df_all = df_all.drop_duplicates(subset=['År', 'Månad', 'Indikator'])
        
        if df_all.empty:
            return empty_df

        df_pivot = df_all.pivot_table(index=['År', 'Månad'], columns='Indikator', values='Antal').reset_index()

        if prefix:
            df_pivot.columns = [f"{prefix}_{c}" if c not in ['År', 'Månad'] else c for c in df_pivot.columns]

        return df_pivot

    # ---------------------------------------------------------
    # 3. KÖR BEARBETNINGEN OCH LÄS IN ALLA FLIKAR
    # ---------------------------------------------------------
    print("2. Smälter, grupperar och sammanställer data...")
    df_lkpg = process_population_sheet("Linköping")
    df_riket = process_population_sheet("Riket", prefix="Riket")
    df_prognos = process_population_sheet("Prognos", prefix="Prognos")
    
    # LÄSER IN FLIKARNA MÄN OCH KVINNOR (Nyhet)
    df_man = process_population_sheet("Män", prefix="Män")
    df_kvinna = process_population_sheet("Kvinnor", prefix="Kvinnor")

    vanliga_namn = {
        'Befolkningsförändringar': 'Befolkningsförändring',
        'Födda barn': 'Födda',
        'Födda levande': 'Födda',
        'Födda levande barn': 'Födda',
        'Döda personer': 'Döda',
        'Inflyttade': 'Inflyttning',
        'Utflyttade': 'Utflyttning'
    }

    def process_change_sheet(sheet_name):
        try:
            df_f = pd.read_excel(excel_fil, sheet_name=sheet_name)
            df_f.columns = [str(c).strip() for c in df_f.columns]
            df_f.rename(columns={c: str(c).strip() for c in df_f.columns}, inplace=True)
            for c in df_f.columns:
                c_low = str(c).lower()
                if c_low == 'år': df_f.rename(columns={c: 'År'}, inplace=True)
                elif c_low == 'månad': df_f.rename(columns={c: 'Månad'}, inplace=True)
                elif c_low in ['år_månad', 'år månad']: df_f.rename(columns={c: 'År_månad'}, inplace=True)
            
            df_f.rename(columns=vanliga_namn, inplace=True)
            
            if 'År_månad' in df_f.columns:
                df_f = df_f.dropna(subset=['År_månad'])
                period_str = df_f['År_månad'].astype(str).str.upper().str.strip()
                df_f['År'] = period_str.str[:4].astype(int)
                df_f['Månad'] = 0
                mask = period_str.str.len() > 4
                df_f.loc[mask, 'Månad'] = pd.to_numeric(period_str.loc[mask].str[-2:], errors='coerce').fillna(0)
                df_f['Månad'] = df_f['Månad'].astype(int)
                df_f = df_f.drop(columns=['År_månad'])
                
            if 'År' in df_f.columns and 'Månad' not in df_f.columns:
                df_f['Månad'] = 0
            
            if 'År' in df_f.columns and 'Månad' in df_f.columns:
                df_f['Månad'] = df_f['Månad'].fillna(0).astype(int)
                annual = df_f[df_f['Månad'] == 0].copy()
                monthly = df_f[df_f['Månad'] != 0].copy()
                if not annual.empty:
                    exp = []
                    for m in range(1, 13):
                        temp = annual.copy()
                        temp['Månad'] = m
                        exp.append(temp)
                    df_f = pd.concat([monthly] + exp, ignore_index=True)
            
            for col in df_f.columns:
                if col not in ['År', 'Månad']:
                    df_f[col] = df_f[col].astype(str).str.replace(r'\s+', '', regex=True)
                    df_f[col] = pd.to_numeric(df_f[col].replace(['..', '-', 'nan'], np.nan), errors='coerce')
            return df_f
        except Exception:
            return pd.DataFrame()

    df_forandring = process_change_sheet("Befolkningsförändringar")
    df_prog_forandring = process_change_sheet("Prognos_förändring")

    df_main = df_lkpg.copy()
    if 'År' not in df_main.columns or 'Månad' not in df_main.columns:
        df_main = pd.DataFrame(columns=['År', 'Månad'])

    if not df_riket.empty and 'År' in df_riket.columns:
        df_main = pd.merge(df_main, df_riket, on=['År', 'Månad'], how='outer')

    if not df_prognos.empty and 'År' in df_prognos.columns:
        df_prognos = df_prognos.rename(columns={col: col.replace('_Prognos', '').replace('Prognos_', '') + '_Prognos_Slutgiltig' for col in df_prognos.columns if col not in ['År', 'Månad']})
        df_main = pd.merge(df_main, df_prognos, on=['År', 'Månad'], how='outer')
        
    if not df_man.empty and 'År' in df_man.columns:
        df_main = pd.merge(df_main, df_man, on=['År', 'Månad'], how='outer')
        
    if not df_kvinna.empty and 'År' in df_kvinna.columns:
        df_main = pd.merge(df_main, df_kvinna, on=['År', 'Månad'], how='outer')

    if not df_forandring.empty and 'År' in df_forandring.columns:
        df_main = pd.merge(df_main, df_forandring, on=['År', 'Månad'], how='outer')

    if not df_prog_forandring.empty and 'År' in df_prog_forandring.columns:
        df_prog_forandring = df_prog_forandring.rename(columns={col: col.replace('_Prognos', '').replace('Prognos_', '') + '_Prognos_Slutgiltig' for col in df_prog_forandring.columns if col not in ['År', 'Månad']})
        df_main = pd.merge(df_main, df_prog_forandring, on=['År', 'Månad'], how='outer')

    df_main = df_main.sort_values(['År', 'Månad']).reset_index(drop=True)

    if 'Befolkningsförändring' not in df_main.columns and 'Totalt (Hela folkmängden)' in df_main.columns:
        df_main['Befolkningsförändring'] = df_main['Totalt (Hela folkmängden)'].diff()
    if 'Riket_Befolkningsförändring' not in df_main.columns and 'Riket_Totalt (Hela folkmängden)' in df_main.columns:
        df_main['Riket_Befolkningsförändring'] = df_main['Riket_Totalt (Hela folkmängden)'].diff()

    # ---------------------------------------------------------
    # 4. BYGG DASHBOARD-KOLUMNER (R12 etc)
    # ---------------------------------------------------------
    print("3. Bygger Månads- och R12-värden för dashboarden...")
    for index, row in df_troskel.iterrows():
        indikator = str(row['Ålder_Indikator']).strip()
        kategori = str(row.get('Kategori_i_Data', '')).strip().lower()
        
        if indikator not in df_main.columns:
            msg = f"Kunde inte hitta data för '{indikator}'. (Stavfel?)"
            varningar.append(msg)
            print(f"   -> VARNING: {msg}")
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
        
        if "förändring" in kategori or "flytt" in kategori.lower() or indikator in ['Födda', 'Döda', 'Inflyttning', 'Utflyttning', 'Befolkningsförändring']:
            df_main[col_r12] = df_main[col_utfall].rolling(12, min_periods=12).sum()
            df_main[f"Riket_{indikator}_R12"] = df_main[col_riket].rolling(12, min_periods=12).sum() if col_riket in df_main.columns else np.nan
            regel = 'SUM'
        else:
            df_main[col_r12] = df_main[col_utfall]
            df_main[f"Riket_{indikator}_R12"] = df_main[col_riket]
            regel = 'LATEST'

        # Skapa Månad och R12 för drilldown-komponenter i pyramiden m.fl.
        if pd.notna(row.get('Drilldown_Komponenter')):
            komps = [k.strip() for k in str(row['Drilldown_Komponenter']).split(',') if k.strip()]
            for k in komps:
                # Loopar igenom för Totalt, Män och Kvinnor
                for prefix in ["", "Män_", "Kvinnor_"]:
                    k_col = f"{prefix}{k}"
                    if k_col in df_main.columns:
                        col_utf = f"{k_col}_Manad"
                        col_r12_komp = f"{k_col}_R12"
                        if col_utf not in df_main.columns:
                            df_main[col_utf] = df_main[k_col]
                            if regel == 'SUM':
                                df_main[col_r12_komp] = df_main[col_utf].rolling(12, min_periods=12).sum()
                            else:
                                df_main[col_r12_komp] = df_main[col_utf]

        df_main[f"{indikator}_Polaritet"] = row.get('Polaritet', np.nan)
        df_main[f"{indikator}_Troskel"] = row.get('Tröskel', np.nan)
        df_main[f"{indikator}_Absolut_R12"] = row.get('Absolut_R12', np.nan)
        df_main[f"{indikator}_Minitabell"] = row.get('Minitabell_Kolumn', np.nan)
        df_main[f"{indikator}_Minitabell_Sort"] = row.get('Minitabell_Sortering', np.nan)
        df_main[f"{indikator}_Alternativ_rubrik"] = row.get('Alternativ_tabellrubrik', np.nan)

    # ---------------------------------------------------------
    # 5. GENERERA RAPPORTTEXT (BEFOLKNING OCH FLYTTNING)
    # ---------------------------------------------------------
    print("4. Kollar efter nya AI-fakta för begärda månader...")
    
    def safe_int(v):
        try:
            if pd.isna(v): return 0
            v_str = str(v).strip().upper()
            if v_str == "" or v_str == "NAN" or v_str == "..": return 0
            return int(float(v))
        except:
            return 0

    try:
        df_texter = pd.read_excel(excel_fil, sheet_name="Rapporttext")
        
        df_texter.columns = [str(c).strip() for c in df_texter.columns]
        
        if 'Stöd_manuell' in df_texter.columns:
            df_texter = df_texter.drop(columns=['Stöd_manuell'])
            
        df_texter = df_texter.loc[:, ~df_texter.columns.duplicated()]
        df_texter = df_texter.fillna('')
        
        for col in ['Autogenererad_Fakta', 'Färdig_Analystext', 'Robot_Fakta', 'Rapportvy']:
            if col not in df_texter.columns:
                df_texter[col] = ''
                
        manader_namn = ["Januari", "Februari", "Mars", "April", "Maj", "Juni", "Juli", "Augusti", "September", "Oktober", "November", "December"]
        
        robot_list = df_texter['Robot_Fakta'].astype(str).str.strip().str.upper()
        skapa_ny_csv = any(x in ['A', 'M'] for x in robot_list)
        
        if not skapa_ny_csv:
            print("      -> Inga nya markeringar för 'A' eller 'M' hittades.")
        else:
            print("      -> Hittade uppdateringar. Bearbetar och skapar en ny text-CSV...")
            for idx, row in df_texter.iterrows():
                try:
                    if str(row['År']).strip() == '' or str(row['Månad']).strip() == '': 
                        continue
                    
                    s_ar = int(float(row['År']))
                    s_manad = int(float(row['Månad']))
                    vy = str(row['Rapportvy']).strip()
                    robot = str(row['Robot_Fakta']).strip().upper()
                    if robot == 'NAN': robot = ''
                except (ValueError, TypeError):
                    continue
                    
                if robot == 'A':
                    
                    mask_nu = (df_main['År'] == s_ar) & (df_main['Månad'] == s_manad)
                    df_nu = df_main[mask_nu]
                    if df_nu.empty: 
                        continue 
                    rad_nu = df_nu.iloc[0]
                    
                    fg_ar_m = s_ar if s_manad > 1 else s_ar - 1
                    fg_manad_m = s_manad - 1 if s_manad > 1 else 12
                    mask_fg_m = (df_main['År'] == fg_ar_m) & (df_main['Månad'] == fg_manad_m)
                    df_fg_m = df_main[mask_fg_m]
                    rad_fg_m = df_fg_m.iloc[0] if not df_fg_m.empty else pd.Series(dtype=float)
                    
                    mask_fg_a = (df_main['År'] == s_ar - 1) & (df_main['Månad'] == s_manad)
                    df_fg_a = df_main[mask_fg_a]
                    rad_fg_a = df_fg_a.iloc[0] if not df_fg_a.empty else pd.Series(dtype=float)
                    
                    folk_nu = safe_int(rad_nu.get('Totalt (Hela folkmängden)_Manad', 0))
                    folk_fg_m = safe_int(rad_fg_m.get('Totalt (Hela folkmängden)_Manad', 0)) if not rad_fg_m.empty else 0
                    folk_fg_a = safe_int(rad_fg_a.get('Totalt (Hela folkmängden)_Manad', 0)) if not rad_fg_a.empty else 0
                    
                    fodda = safe_int(rad_nu.get('Födda_Manad', 0))
                    doda = safe_int(rad_nu.get('Döda_Manad', 0))
                    inflytt = safe_int(rad_nu.get('Inflyttning_Manad', 0))
                    utflytt = safe_int(rad_nu.get('Utflyttning_Manad', 0))
                    
                    diff_manad = folk_nu - folk_fg_m if not rad_fg_m.empty else 0
                    diff_ar = folk_nu - folk_fg_a if not rad_fg_a.empty else 0
                    flyttnetto = inflytt - utflytt
                    fodselnetto = fodda - doda
                    manad_namn = manader_namn[s_manad - 1]
                    
                    if vy == 'Befolkning':
                        fakta_text = (f"I {manad_namn.lower()} {s_ar} uppgick folkmängden i Linköping till {folk_nu:,}. "
                                      f"Det innebär en förändring med {diff_manad:+} personer jämfört med föregående månad, "
                                      f"och {diff_ar:+} personer jämfört med samma månad föregående år. "
                                      f"Under månaden föddes {fodda} barn och {doda} personer avled (födelsenetto {fodselnetto:+}). "
                                      f"Samtidigt var kommunens totala flyttnetto {flyttnetto:+} personer.").replace(',', ' ')
                        
                        df_texter.at[idx, 'Autogenererad_Fakta'] = fakta_text
                        df_texter.at[idx, 'Färdig_Analystext'] = fakta_text
                        
                    elif vy == 'Flyttning':
                        inflytt_fg_a = safe_int(rad_fg_a.get('Inflyttning_Manad', 0)) if not rad_fg_a.empty else 0
                        utflytt_fg_a = safe_int(rad_fg_a.get('Utflyttning_Manad', 0)) if not rad_fg_a.empty else 0
                        
                        diff_in = inflytt - inflytt_fg_a
                        diff_ut = utflytt - utflytt_fg_a
                        
                        fakta_text = (f"Under {manad_namn.lower()} {s_ar} registrerades {inflytt} inflyttningar till Linköping "
                                      f"och {utflytt} utflyttningar. Detta gav ett flyttnetto på {flyttnetto:+} personer för månaden. "
                                      f"Jämfört med samma månad föregående år innebär det en förändring av inflyttningen med {diff_in:+} "
                                      f"personer och utflyttningen med {diff_ut:+} personer.").replace(',', ' ')
                        
                        df_texter.at[idx, 'Autogenererad_Fakta'] = fakta_text
                        df_texter.at[idx, 'Färdig_Analystext'] = fakta_text

            def rensa_heltal(v):
                try:
                    if pd.isna(v): return ''
                    v_str = str(v).strip().upper()
                    if v_str == '' or v_str == 'NAN': return ''
                    return str(int(float(v)))
                except:
                    return str(v)
            
            if 'År' in df_texter.columns:
                df_texter['År'] = df_texter['År'].apply(rensa_heltal)
            if 'Månad' in df_texter.columns:
                df_texter['Månad'] = df_texter['Månad'].apply(rensa_heltal)
            
            for c in ['Robot_Fakta', 'Autogenererad_Fakta', 'Färdig_Analystext', 'Rapportvy']:
                if c in df_texter.columns:
                    df_texter[c] = df_texter[c].astype(str).replace(r'(?i)^nan$', '', regex=True)

            out_text_path = os.path.join(spara_mapp, "befolkning_texter.csv")
            df_texter.to_csv(out_text_path, sep=';', index=False, encoding='cp1252')
            print(f"      -> Filen sparades som {out_text_path}")
        
    except Exception as e:
        print(f"Ett fel uppstod vid textgenerering: {e}")

    # ---------------------------------------------------------
    # 6. EXPORTERA DATA FÖR WEBBSIDAN
    # ---------------------------------------------------------
    print("5. Exporterar data-CSV för webben...")
    scb_cols = [c for c in df_troskel['Ålder_Indikator'].tolist() if c in df_main.columns]
    riket_scb_cols = [f"Riket_{c}" for c in scb_cols if f"Riket_{c}" in df_main.columns]
    df_main = df_main.drop(columns=scb_cols + riket_scb_cols)

    def format_swedish_decimals(val):
        if pd.isna(val) or val == "" or val == "inf" or val == "-inf": return ""
        if isinstance(val, float): return f"{val:.2f}".replace('.', ',')
        return val

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
        if f"{dash_namn}_Manad" not in df_export.columns: continue
            
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
                actual_col = next((c for c in df_troskel.columns if str(c).lower() == col_name.lower()), None)
                if actual_col and str(row[actual_col]).strip().lower() == 'ja':
                    diagram_config[str(i)].append(ind_obj)

    out_json = os.path.join(spara_mapp, "befolkning_config.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(diagram_config, f, ensure_ascii=False, indent=4)

    print("\n" + "=" * 50)
    print("BEARBETNING KLAR!")
    
    if varningar:
        print("\n⚠️ VARNINGAR:")
        for v in varningar: print(f" - {v}")
        print("\nTryck på ENTER för att stänga fönstret...")
        input() 
    else:
        print("\n✅ Inga varningar. All data laddades in perfekt!")
        print("Stänger programmet om 2 sekunder...")
        time.sleep(2) 
    print("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n" + "="*50)
        print("ETT OVÄNTAT FEL INTRÄFFADE SOM FICK PROGRAMMET ATT KRASCHA:")
        traceback.print_exc()
        print("="*50)
        print("\nTryck på ENTER för att stänga fönstret...")
        input()