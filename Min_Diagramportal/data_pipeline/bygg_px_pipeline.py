import os
import pandas as pd
from pyaxis import pyaxis

pd.set_option('future.no_silent_downcasting', True)

LKP_ANDEL_AV_RIKET = 0.0159 

FIL_MAPPNING = {
    'Befolkning': {'px_fil': 'ksi2242.px', 'utfil': 'Data_Diagram_PX1.csv'},
    'Sysselsättning': {'px_fil': 'ksi2242.px', 'utfil': 'Data_Diagram_PX2.csv'},
    'Bostadsbyggande': {'px_fil': 'ksi2242.px', 'utfil': 'Data_Diagram_PX3.csv'},
    'Arbetslöshet': {'px_fil': 'ksi2242.px', 'utfil': 'Data_Diagram_PX4.csv'}
}

# Ny, robust söklogik: Letar efter antingen koden ELLER namnet i regionkolumnen
JAMFORELSE_REGEX = {
    '0180': r'\b0180\b|Stockholm',
    '0380': r'\b0380\b|Uppsala',
    '0581': r'\b0581\b|Norrköping',
    '0680': r'\b0680\b|Jönköping',
    '1280': r'\b1280\b|Malmö',
    '1281': r'\b1281\b|Lund',
    '1283': r'\b1283\b|Helsingborg',
    '1480': r'\b1480\b|Göteborg',
    '1880': r'\b1880\b|Örebro',
    '1980': r'\b1980\b|Västerås',
    '2480': r'\b2480\b|Umeå',
    '05': r'\b05\b|Östergötland', 
    'Riket': r'\b00\b|Riket|Sverige',
    '2700': r'2700|plus\s*12',
    '2701': r'2701|plus\s*11',
    '2703': r'2703|plus\s*9',
    '2707': r'2707|plus\s*5',
    '2709': r'2709|plus\s*4',
    '3105': r'3105|länet.*exkl.*linköping' # Skyddad för att inte sno Plus 11
}

try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
    huvudmapp = os.path.dirname(current_folder) if os.path.basename(current_folder).lower() == "data_pipeline" else current_folder
except NameError:
    current_folder = os.getcwd()
    huvudmapp = current_folder

def kor_master_pipeline():
    print("🚀 Startar Master Controller för PX-filer (Kommunjämförelser)...\n")

    styrfil_path = "Styrfil_Indikatorer.xlsx"
    if not os.path.exists(styrfil_path):
        print(f"❌ Kritiskt fel: Hittar inte {styrfil_path}.")
        return
        
    try:
        df_styr = pd.read_excel(styrfil_path, sheet_name="Styrning")
        df_styr = df_styr.dropna(subset=['Område', 'SCB_Namn i filen', 'Dashboard_Namn'])
    except Exception as e:
        print(f"❌ Fel vid läsning av Styrfilen: {e}")
        return

    omraden = df_styr['Område'].unique()
    
    for omrade in omraden:
        if omrade not in FIL_MAPPNING:
            continue
            
        print(f"\n--- BEARBETAR OMRÅDE: {omrade} ---")
        config = FIL_MAPPNING[omrade]
        df_omrade = df_styr[df_styr['Område'] == omrade]
        
        px_sokvag = os.path.join("px_filer", config['px_fil'])
        if not os.path.exists(px_sokvag):
            print(f"⚠️ Hittar inte filen {config['px_fil']}. Hoppar över.")
            continue

        try:
            px_data = pyaxis.parse(px_sokvag, encoding='cp1252') 
            df_raw = px_data['DATA']
            
            # Gör om till text och rensa mellanslag
            df_raw['DATA'] = df_raw['DATA'].astype(str).str.strip()
            
            # Fånga alla tänkbara varianter av bindestreck och tankstreck från SCB
            df_raw.loc[df_raw['DATA'].isin(['-', '–', '—', '−']), 'DATA'] = '0'
            
            # Nu gör vi om det till siffror (allt annat ogiltigt blir NaN)
            df_raw['DATA'] = pd.to_numeric(df_raw['DATA'], errors='coerce')
            df_raw = df_raw.dropna(subset=['DATA'])
        except Exception as e:
            print(f"❌ Fel vid PX-läsning: {e}")
            continue

        df_raw['År'] = df_raw['tid'].astype(int)
        df_raw['Kvartal'] = df_raw['kvartal'].astype(str).str.extract(r'(\d+)').astype(int)

        # 1. IDENTIFIERA REGION-KOLUMNEN
        region_col = None
        for col in df_raw.columns:
            if df_raw[col].astype(str).str.contains(r'\b0580\b|Linköping|\b00\b|Sverige|Riket', case=False, regex=True).any():
                region_col = col
                break
        if not region_col:
            region_col = 'kommun' if 'kommun' in df_raw.columns else df_raw.columns[2]

        # 2. RENSNING AV EXTRA-KOLUMNER (Om de finns)
        kanda_kolumner = ['tid', 'kvartal', 'indikator', 'DATA', 'År', 'Kvartal', 'tabellinnehåll', region_col]
        extra_kolumner = [col for col in df_raw.columns if col not in kanda_kolumner]
        for extra_col in extra_kolumner:
            unika_varden = df_raw[extra_col].astype(str).str.lower().unique()
            totalt_ord = ['totalt', 'samtliga', 'båda könen', 'alla åldrar', 'summa']
            totalt_varden = [v for v in unika_varden if any(ord in v for ord in totalt_ord)]
            if totalt_varden:
                df_raw = df_raw[df_raw[extra_col].astype(str).str.lower().isin(totalt_varden)]

        # Skapa en gemensam mask för "exkl" för att skydda Linköping och Länssnittet
        mask_exkl = df_raw[region_col].astype(str).str.contains('exkl', case=False, na=False)

        # 3. FILTRERA UT LINKÖPING (Huvudlinjen)
        mask_linkoping = df_raw[region_col].astype(str).str.contains(r'\b0580\b|Linköping', case=False, regex=True, na=False)
        df_linkoping = df_raw[mask_linkoping & ~mask_exkl].copy()

        if df_linkoping.empty:
             print("⚠️ Hittade ingen data för Linköping i detta område!")
        else:
             print(f"   -> Huvudlinje (Linköping) skapad.")

        # 4. FILTRERA UT ALLA JÄMFÖRELSEKOMMUNER
        df_compare_dict = {}
        for csv_kod, regex_pattern in JAMFORELSE_REGEX.items():
            mask = df_raw[region_col].astype(str).str.contains(regex_pattern, case=False, regex=True, na=False)
            
            # Specialskydd för Östergötlands Län så vi inte drar in exklusive-gruppen
            if csv_kod == '05':
                mask = mask & ~mask_exkl
                
            df_temp = df_raw[mask].copy()
            if not df_temp.empty:
                df_compare_dict[csv_kod] = df_temp
            else:
                pass # Tyst fail om kommunen saknas i just denna PX-fil

        # 5. PIVOTERA LINKÖPING (Uppdaterad för att förhindra falska nollor)
        if not df_linkoping.empty:
            pivot_link = df_linkoping.pivot_table(index=['År', 'Kvartal'], columns='indikator', values='DATA', aggfunc=lambda x: x.sum(min_count=1)).reset_index()
            
            mappning = {}
            for _, row in df_omrade.iterrows():
                scb_namn = row['SCB_Namn i filen'].strip()
                dash_namn = row['Dashboard_Namn'].strip()
                mappning[scb_namn] = f"{dash_namn}_Kvartal"
            pivot_link.rename(columns=mappning, inplace=True, errors='ignore')
            
            # Behåll ENDAST de kolumner som vi faktiskt definierat i styrfilen
            behalla_kolumner = ['År', 'Kvartal'] + [v for v in mappning.values() if v in pivot_link.columns]
            df_radata = pivot_link[behalla_kolumner].copy()
        else:
             df_radata = pd.DataFrame(columns=['År', 'Kvartal'])

        # 6. PIVOTERA OCH SLÅ IHOP ALLA JÄMFÖRELSEKOMMUNER (Uppdaterad för att förhindra falska nollor)
        for kod, df_comp in df_compare_dict.items():
            pivot_comp = df_comp.pivot_table(index=['År', 'Kvartal'], columns='indikator', values='DATA', aggfunc=lambda x: x.sum(min_count=1)).reset_index()
            mappning_comp = {}
            for _, row in df_omrade.iterrows():
                scb_namn = row['SCB_Namn i filen'].strip()
                dash_namn = row['Dashboard_Namn'].strip()
                mappning_comp[scb_namn] = f"{dash_namn}_Kvartal_{kod}"
            pivot_comp.rename(columns=mappning_comp, inplace=True, errors='ignore')
            
            # Behåll ENDAST de kolumner som vi faktiskt definierat
            behalla_kolumner_comp = ['År', 'Kvartal'] + [v for v in mappning_comp.values() if v in pivot_comp.columns]
            pivot_comp = pivot_comp[behalla_kolumner_comp]

            df_radata = pd.merge(df_radata, pivot_comp, on=['År', 'Kvartal'], how='left')

        # 7. RÄKNA UT RULLANDE 12 (R12) - Nu med SNITT!
        for _, row in df_omrade.iterrows():
            dash_namn = row['Dashboard_Namn'].strip()
            regel = row['R12_Regel'].strip().upper() if pd.notnull(row['R12_Regel']) else 'SUM'
            
            # Beräkna för Linköping
            kvartal_col = f"{dash_namn}_Kvartal"
            r12_col = f"{dash_namn}_R12"
            if kvartal_col in df_radata.columns:
                if regel == 'SUM': 
                    df_radata[r12_col] = df_radata[kvartal_col].rolling(window=4).sum()
                elif regel == 'SNITT': 
                    df_radata[r12_col] = df_radata[kvartal_col].rolling(window=4).mean().round(2)
                elif regel == 'SISTA': 
                    df_radata[r12_col] = df_radata[kvartal_col]

            # Beräkna för ALLA Jämförelsekommuner
            for kod in df_compare_dict.keys():
                comp_kvartal_col = f"{dash_namn}_Kvartal_{kod}"
                comp_r12_col = f"{dash_namn}_R12_{kod}"
                if comp_kvartal_col in df_radata.columns:
                    if regel == 'SUM': 
                        df_radata[comp_r12_col] = df_radata[comp_kvartal_col].rolling(window=4).sum()
                    elif regel == 'SNITT': 
                        df_radata[comp_r12_col] = df_radata[comp_kvartal_col].rolling(window=4).mean().round(2)
                    elif regel == 'SISTA': 
                        df_radata[comp_r12_col] = df_radata[comp_kvartal_col]

        # 8. LÄS IN MANUELLA MÅL OCH PROGNOSER
        mal_fil = "mal_och_prognoser.xlsx" if os.path.exists("mal_och_prognoser.xlsx") else "mal_ochprognoser.xlsx"
        try:
            try: df_mal = pd.read_excel(mal_fil, sheet_name=omrade)
            except: df_mal = pd.read_excel(mal_fil, sheet_name='Befolkningsförändringar')
            df_mal.columns = df_mal.columns.str.strip()
        except: df_mal = pd.DataFrame(columns=['År', 'Kvartal'])

        df_kombinerad = pd.merge(df_radata, df_mal, on=['År', 'Kvartal'], how='left')
        df_kombinerad = df_kombinerad.sort_values(by=['År', 'Kvartal']).reset_index(drop=True)
        
        # 9. PROGNOS-VATTENFALL
        for _, row in df_omrade.iterrows():
            dash_namn = row['Dashboard_Namn'].strip()
            std_pol = str(row['Polaritet']).strip() if 'Polaritet' in df_omrade.columns and pd.notnull(row['Polaritet']) else 'Hög'
            std_troskel = str(row['Troskel']).strip() if 'Troskel' in df_omrade.columns and pd.notnull(row['Troskel']) else ''
            
            polaritet_col = f"{dash_namn}_Polaritet"
            troskel_col = f"{dash_namn}_Troskel"
            if polaritet_col not in df_kombinerad.columns: df_kombinerad[polaritet_col] = ""
            if troskel_col not in df_kombinerad.columns: df_kombinerad[troskel_col] = ""
            df_kombinerad[polaritet_col] = df_kombinerad[polaritet_col].replace(["", pd.NA, None], std_pol)
            df_kombinerad[troskel_col] = df_kombinerad[troskel_col].replace(["", pd.NA, None], std_troskel)

            prog_col = f"{dash_namn}_Prognos"
            utv_prog_col = f"{dash_namn}_UtvecklingsPrognos"
            r12_col = f"{dash_namn}_R12"
            riket_r12_col = f"{dash_namn}_R12_Riket"

            # Normalisera och läs in befintliga mål. Omvandlar '..' och liknande till NaN så att vattenfallet triggas!
            if prog_col not in df_kombinerad.columns: 
                df_kombinerad[prog_col] = pd.NA
            else: 
                df_kombinerad[prog_col] = pd.to_numeric(df_kombinerad[prog_col].astype(str).str.replace(',', '.').replace(['', 'nan', '..'], pd.NA), errors='coerce')

            hist_r12 = pd.Series(dtype=float)
            if r12_col in df_kombinerad.columns: hist_r12 = pd.to_numeric(df_kombinerad[r12_col], errors='coerce').shift(4)

            # Prio 2
            if utv_prog_col in df_kombinerad.columns:
                p2_vals = pd.to_numeric(df_kombinerad[utv_prog_col].astype(str).str.replace(',', '.'), errors='coerce')
                mask_p2 = df_kombinerad[prog_col].isna() & p2_vals.notna() & hist_r12.notna()
                df_kombinerad.loc[mask_p2, prog_col] = hist_r12[mask_p2] * (1 + (p2_vals[mask_p2] / 100.0))

            # Prio 3: Mal_Egen_Utveckling_Procent
            p3_val = row.get('Mal_Egen_Utveckling_Procent', pd.NA)
            if pd.notna(p3_val) and str(p3_val).strip() != "":
                try:
                    p3_float = float(str(p3_val).replace(',', '.'))
                    mask_p3 = df_kombinerad[prog_col].isna() & hist_r12.notna()
                    df_kombinerad.loc[mask_p3, prog_col] = hist_r12[mask_p3] * (1 + (p3_float / 100.0))
                except ValueError: pass

            # Prio 4: Historiskt Genomsnitt över X år
            p4_snitt = row.get('Mal_Historiskt_Snitt_Ar', pd.NA)
            if pd.notna(p4_snitt) and str(p4_snitt).strip() != "":
                try:
                    num_years = int(float(str(p4_snitt).replace(',', '.')))
                    if num_years > 0:
                        snitt_sum = pd.Series(0.0, index=df_kombinerad.index)
                        snitt_count = pd.Series(0, index=df_kombinerad.index)
                        
                        r12_numeric = pd.to_numeric(df_kombinerad[r12_col], errors='coerce')
                        
                        # Loopa tillbaka X år och summera utfallen
                        for y in range(1, num_years + 1):
                            shifted = r12_numeric.shift(4 * y) # Hoppa bakåt 4 kvartal per år
                            snitt_sum = snitt_sum.add(shifted.fillna(0))
                            snitt_count = snitt_count.add(shifted.notna().astype(int))
                            
                        # Räkna ut det faktiska snittet
                        historiskt_snitt = snitt_sum / snitt_count.replace(0, pd.NA)
                        
                        # KRÄV att vi har historik för ALLA efterfrågade år
                        mask_p4_snitt = df_kombinerad[prog_col].isna() & historiskt_snitt.notna() & (snitt_count == num_years)
                        df_kombinerad.loc[mask_p4_snitt, prog_col] = historiskt_snitt[mask_p4_snitt]
                except ValueError: pass

            # Prio 5: Mal_Riket_Procent
            p5_val = row.get('Mal_Riket_Procent', pd.NA)
            if pd.notna(p5_val) and str(p5_val).strip() != "":
                try:
                    p5_float = float(str(p5_val).replace(',', '.'))
                    if riket_r12_col in df_kombinerad.columns:
                        riket_vals = pd.to_numeric(df_kombinerad[riket_r12_col], errors='coerce')
                        mask_p5 = df_kombinerad[prog_col].isna() & riket_vals.notna()
                        df_kombinerad.loc[mask_p5, prog_col] = riket_vals[mask_p5] * LKP_ANDEL_AV_RIKET * (1 + (p5_float / 100.0))
                except ValueError: pass

            # Avrundning: 1 decimal för procent, 0 decimaler för antal
            if prog_col in df_kombinerad.columns:
                is_procent = '%' in dash_namn or 'andel' in dash_namn.lower()
                decimals = 1 if is_procent else 1
                df_kombinerad[prog_col] = pd.to_numeric(df_kombinerad[prog_col], errors='coerce').round(decimals)

        df_kombinerad = df_kombinerad.astype(object).fillna("")
        utfil_absolut = os.path.join(huvudmapp, config['utfil'])
        df_kombinerad.to_csv(utfil_absolut, sep=";", index=False, encoding="cp1252", decimal=",")
        print(f"✅ Klar med {omrade} -> {config['utfil']}")

if __name__ == "__main__":
    kor_master_pipeline()