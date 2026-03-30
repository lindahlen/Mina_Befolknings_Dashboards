import os
import sys
import pandas as pd
import itertools
import re
import json

# ==========================================
# 1. GENERELL SETUP (Enligt Master Config v2.0)
# ==========================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
except NameError:
    pass 

# Standardkod för textfix (Fixar UTF-8 tolkad som ANSI)
encoding_fix = {
    'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
    'Ã©': 'é', 'Ã¨': 'è', 'Ã‰': 'É', "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö"
}

def fix_text(text):
    if not isinstance(text, str): return text
    for bad, good in encoding_fix.items():
        text = text.replace(bad, good)
    return text

# ==========================================
# 2. SKRÄDDARSYDD PX-PARSER FÖR SCB-DATA
# ==========================================
def read_px_file(filepath, value_col_name='Värde'):
    """
    Läser en .px-fil och returnerar en Pandas DataFrame.
    Hanterar dimensioner dynamiskt och mappar upp SCB-data korrekt.
    """
    if not os.path.exists(filepath):
        print(f"Varning: Hittade inte filen {filepath}")
        return pd.DataFrame()

    with open(filepath, 'r', encoding='ansi', errors='replace') as f:
        content = f.read()

    # Extrahera dimensionerna från STUB och HEADING
    stubs_match = re.search(r'STUB\s*=\s*([^;]+);', content)
    headings_match = re.search(r'HEADING\s*=\s*([^;]+);', content)
    
    stubs = [x.strip('"\n\r ') for x in stubs_match.group(1).split(',')] if stubs_match else []
    headings = [x.strip('"\n\r ') for x in headings_match.group(1).split(',')] if headings_match else []
    dimensions = stubs + headings

    # Läs in värdena för respektive dimension
    val_dict = {}
    for match in re.finditer(r'VALUES\("([^"]+)"\)\s*=\s*([^;]+);', content, re.DOTALL):
        dim = match.group(1)
        vals_str = match.group(2)
        vals = re.findall(r'"([^"]*)"', vals_str)
        val_dict[dim] = [fix_text(v) for v in vals]

    # Läs in den faktiska datan
    data_match = re.search(r'DATA\s*=\s*([^;]+);', content, re.DOTALL)
    if not data_match:
        print(f"Kunde inte hitta DATA i {filepath}")
        return pd.DataFrame()

    data_str = data_match.group(1).replace('\n', ' ').replace('\r', ' ')
    data_list = [x for x in data_str.split() if x.strip()]

    # Tvätta datan (SCB använder "-" för 0 och ".." för saknad uppgift)
    data_clean = []
    for val in data_list:
        if val in ['-', '..']:
            data_clean.append(0.0)
        else:
            try:
                data_clean.append(float(val))
            except ValueError:
                data_clean.append(0.0)

    # Skapa Cartesian product av alla dimensioner för att bygga tabellen
    dim_lists = [val_dict[dim] for dim in dimensions]
    combinations = list(itertools.product(*dim_lists))
    
    # Säkerhetskontroll ifall datalängden skiljer sig från matrix-kombinationerna
    min_len = min(len(combinations), len(data_clean))
    
    df = pd.DataFrame(combinations[:min_len], columns=dimensions)
    df[value_col_name] = data_clean[:min_len]
    
    return df

# ==========================================
# 3. VERKTYG FÖR 5-ÅRSKLASSER & SORTERING
# ==========================================
def aggregera_till_5ar(alder_str):
    """ Konverterar t.ex. '23 år' till '20-24 år' """
    if "Totalt" in alder_str: 
        return "Totalt"
    try:
        alder = int(re.search(r'\d+', alder_str).group())
        if alder >= 100:
            return "100+ år"
        lower = (alder // 5) * 5
        upper = lower + 4
        return f"{lower}-{upper} år"
    except:
        return alder_str

def extrahera_alder_numerisk(alder_str):
    """ Hjälpfunktion för att kunna sortera åldrar numeriskt istället för alfabetiskt """
    try:
        return int(re.search(r'\d+', str(alder_str)).group())
    except:
        return 999 # Lägger "Totalt" och liknande längst ner

def main():
    # ==========================================
    # 4. INLÄSNING OCH SAMMANSLAGNING AV DATA
    # ==========================================
    px_mapp = "px_filer"
    print(f"Läser in PC-Axis filer från mappen '{px_mapp}'...")

    # Läs in befolkning (tid, kön, ålder)
    df_pop = read_px_file(os.path.join(px_mapp, 'be01.px'), 'Befolkning')

    # Läs in inflyttade & utflyttade efter kön
    df_in = read_px_file(os.path.join(px_mapp, 'fl01in.px'), 'Inflyttade')
    df_ut = read_px_file(os.path.join(px_mapp, 'fl01ut.px'), 'Utflyttade')

    # Läs in döda (Avlidna under året)
    df_dead_raw = read_px_file(os.path.join(px_mapp, 'fd06b.px'), 'Döda')
    if not df_dead_raw.empty:
        df_dead = df_dead_raw[df_dead_raw['tabellinnehåll'] == 'Avlidna under året'].copy()
        df_dead.drop(columns=['tabellinnehåll'], inplace=True, errors='ignore')
    else:
        df_dead = pd.DataFrame()

    # Läs in TFR-data (Födda barn och kvinnor)
    df_tfr_raw = read_px_file(os.path.join(px_mapp, 'TFR82.px'), 'Värde')
    if not df_tfr_raw.empty:
        df_fodda = df_tfr_raw[df_tfr_raw['tabelluppgift'] == 'Födda barn'].copy()
        df_fodda.rename(columns={'Värde': 'Födda_barn'}, inplace=True)
        df_fodda['kön'] = 'Kvinnor' # Fäster födda barn på mödrarnas åldersrad
        df_fodda.drop(columns=['tabelluppgift'], inplace=True, errors='ignore')
        
        df_kvinnor_tfr = df_tfr_raw[df_tfr_raw['tabelluppgift'] == 'Antal kvinnor'].copy()
        df_kvinnor_tfr.rename(columns={'Värde': 'Kvinnor_TFR_fil'}, inplace=True)
        df_kvinnor_tfr['kön'] = 'Kvinnor'
        df_kvinnor_tfr.drop(columns=['tabelluppgift'], inplace=True, errors='ignore')
    else:
        df_fodda = pd.DataFrame()
        df_kvinnor_tfr = pd.DataFrame()

    # Läs in Detaljerad fruktsamhet efter barnets kön (fd04c.px)
    df_fd04c_raw = read_px_file(os.path.join(px_mapp, 'fd04c.px'), 'Värde')
    if not df_fd04c_raw.empty:
        df_pojkar = df_fd04c_raw[df_fd04c_raw['kön'] == 'Pojkar'].copy()
        df_pojkar.rename(columns={'Värde': 'Födda_Pojkar', 'moderns ålder': 'ålder'}, inplace=True)
        df_pojkar['kön'] = 'Kvinnor' 
        
        df_flickor = df_fd04c_raw[df_fd04c_raw['kön'] == 'Flickor'].copy()
        df_flickor.rename(columns={'Värde': 'Födda_Flickor', 'moderns ålder': 'ålder'}, inplace=True)
        df_flickor['kön'] = 'Kvinnor' 
    else:
        df_pojkar = pd.DataFrame()
        df_flickor = pd.DataFrame()

    # Läs in Flyttningsrelation (fl01vf) Inrikes/Utrikes
    df_flytt_rel_raw = read_px_file(os.path.join(px_mapp, 'fl01vf.px'), 'Värde')
    df_flytt_detalj = pd.DataFrame()

    if not df_flytt_rel_raw.empty:
        inf_utr = df_flytt_rel_raw[(df_flytt_rel_raw['riktning'] == 'Inflyttning') & (df_flytt_rel_raw['flyttningsrelation'] == 'Annat land')].copy()
        inf_utr.rename(columns={'Värde': 'Inflyttade_Utrikes'}, inplace=True)
        
        inf_inr = df_flytt_rel_raw[(df_flytt_rel_raw['riktning'] == 'Inflyttning') & (df_flytt_rel_raw['flyttningsrelation'] == 'Inrikes totalt')].copy()
        inf_inr.rename(columns={'Värde': 'Inflyttade_Inrikes'}, inplace=True)
        
        utf_utr = df_flytt_rel_raw[(df_flytt_rel_raw['riktning'] == 'Utflyttning') & (df_flytt_rel_raw['flyttningsrelation'] == 'Annat land')].copy()
        utf_utr.rename(columns={'Värde': 'Utflyttade_Utrikes'}, inplace=True)
        
        utf_inr = df_flytt_rel_raw[(df_flytt_rel_raw['riktning'] == 'Utflyttning') & (df_flytt_rel_raw['flyttningsrelation'] == 'Inrikes totalt')].copy()
        utf_inr.rename(columns={'Värde': 'Utflyttade_Inrikes'}, inplace=True)

        dfs_att_sla_ihop = [inf_utr[['tid', 'ålder', 'Inflyttade_Utrikes']], 
                            inf_inr[['tid', 'ålder', 'Inflyttade_Inrikes']],
                            utf_utr[['tid', 'ålder', 'Utflyttade_Utrikes']],
                            utf_inr[['tid', 'ålder', 'Utflyttade_Inrikes']]]
        
        df_flytt_detalj = dfs_att_sla_ihop[0]
        for d in dfs_att_sla_ihop[1:]:
            df_flytt_detalj = pd.merge(df_flytt_detalj, d, on=['tid', 'ålder'], how='outer')


    # Sammanställ Master DataFrame
    print("Aggregerar och slår samman databaser...")
    master_df = df_pop.copy()
    if not df_in.empty: master_df = pd.merge(master_df, df_in, on=['tid', 'ålder', 'kön'], how='outer')
    if not df_ut.empty: master_df = pd.merge(master_df, df_ut, on=['tid', 'ålder', 'kön'], how='outer')
    if not df_dead.empty: master_df = pd.merge(master_df, df_dead, on=['tid', 'ålder', 'kön'], how='outer')
    if not df_fodda.empty: master_df = pd.merge(master_df, df_fodda, on=['tid', 'ålder', 'kön'], how='outer')
    if not df_pojkar.empty: master_df = pd.merge(master_df, df_pojkar[['tid', 'ålder', 'kön', 'Födda_Pojkar']], on=['tid', 'ålder', 'kön'], how='outer')
    if not df_flickor.empty: master_df = pd.merge(master_df, df_flickor[['tid', 'ålder', 'kön', 'Födda_Flickor']], on=['tid', 'ålder', 'kön'], how='outer')
    if not df_kvinnor_tfr.empty: master_df = pd.merge(master_df, df_kvinnor_tfr, on=['tid', 'ålder', 'kön'], how='outer')

    if not df_flytt_detalj.empty:
        master_df = pd.merge(master_df, df_flytt_detalj, on=['tid', 'ålder'], how='left')

    master_df.fillna(0, inplace=True)
    master_df['Åldersgrupp_5år'] = master_df['ålder'].apply(aggregera_till_5ar)
    master_df['sort_age'] = master_df['ålder'].apply(extrahera_alder_numerisk)
    master_df.sort_values(by=['tid', 'kön', 'sort_age'], inplace=True)
    master_df.drop(columns=['sort_age'], inplace=True)

    cols_order = ['tid', 'kön', 'ålder', 'Åldersgrupp_5år', 'Befolkning', 'Inflyttade', 'Utflyttade', 'Döda', 
                  'Födda_barn', 'Födda_Pojkar', 'Födda_Flickor', 'Kvinnor_TFR_fil', 'Inflyttade_Inrikes', 'Inflyttade_Utrikes', 'Utflyttade_Inrikes', 'Utflyttade_Utrikes']
    cols = [c for c in cols_order if c in master_df.columns]
    master_df = master_df[cols]

    # ==========================================
    # 5. LÄS IN STYRFIL OCH SPARAR JSON
    # ==========================================
    ut_mapp = os.path.abspath(os.path.join(os.getcwd(), '..'))
    excel_path = os.path.join(ut_mapp, 'styrfil_prognoskalkylator.xlsx')
    if not os.path.exists(excel_path):
        excel_path = 'styrfil_prognoskalkylator.xlsx'
        
    if os.path.exists(excel_path):
        print(f"\nLäser in styrfil: {excel_path}...")
        try:
            df_alder = pd.read_excel(excel_path, sheet_name='Åldersgrupper').fillna("")
            df_tillvaxt = pd.read_excel(excel_path, sheet_name='Tillväxt').fillna(0)
            df_hushall = pd.read_excel(excel_path, sheet_name='Hushållsstorlek')
            df_fruktsam = pd.read_excel(excel_path, sheet_name='Fruktsam')
            df_bostad = pd.read_excel(excel_path, sheet_name='Färdigställda_bostäder')
            
            # --- Slå ihop "Färdigställda bostäder" ---
            if 'År' in df_bostad.columns:
                df_bostad['tid'] = df_bostad['År'].astype(str)
                df_bostad = df_bostad.drop(columns=['År'])
                if 'Färdigställda_bostäder' in master_df.columns:
                    master_df = master_df.drop(columns=['Färdigställda_bostäder'])
                master_df = pd.merge(master_df, df_bostad, on='tid', how='left')
            
            output_csv = os.path.join(ut_mapp, "historisk_demografi_linkoping.csv")
            master_df.to_csv(output_csv, index=False, encoding='utf-8-sig', sep=';')
            
            output_json = os.path.join(ut_mapp, "kalkylator_basdata.json")
            master_df.to_json(output_json, orient='records', force_ascii=False)
            
            # --- Bygg konfigurations-JSON ---
            config = {
                "age_groups": df_alder.to_dict(orient='records'),
                "household_sizes": dict(zip(df_hushall['Prognosår'].astype(str), df_hushall['Hushållsstorlek'])),
                "fruktsamhet_variabel": dict(zip(df_fruktsam['Prognosår'].astype(str), df_fruktsam['Fruktsamhet'])),
                "scenarios": {}
            }
            
            # NYTT: Läser in den officiella prognosen om den finns
            try:
                df_officiell = pd.read_excel(excel_path, sheet_name='Officiell_Prognos').fillna(0)
                config["officiell_prognos"] = df_officiell.to_dict(orient='records')
                print(" -> Hittade och lade till 'Officiell_Prognos'")
            except Exception as e:
                print(" -> (Ingen 'Officiell_Prognos' hittades eller kunde läsas in)")

            df_tillvaxt['Indikator'] = df_tillvaxt['Indikator'].astype(str).str.strip()
            
            for col in ['Bas', 'Hög tillväxt', 'Låg tillväxt', 'Stagnerande']:
                if col in df_tillvaxt.columns:
                    mapping = dict(zip(df_tillvaxt['Indikator'], df_tillvaxt[col]))
                    
                    if col == 'Bas': scen_key = 'base'
                    elif 'Hög' in col: scen_key = 'high'
                    elif 'Låg' in col: scen_key = 'low'
                    else: scen_key = 'stagnant'
                    
                    config["scenarios"][scen_key] = {
                        "tfr": mapping.get("Fruktsamhet", 1.6),
                        "mort": float(mapping.get("Dödlighet", 0)),
                        "inIn": float(mapping.get("Inrikes inflyttning", 0)),
                        "inUt": float(mapping.get("Inrikes utflyttning", 0)),
                        "utIn": float(mapping.get("Utrikes invandring", 0)),
                        "utUt": float(mapping.get("Utrikes utvandring", 0))
                    }
            
            output_config = os.path.join(ut_mapp, "styrfil_config.json")
            with open(output_config, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(" -> Sparade konfiguration till 'styrfil_config.json'")
            
        except Exception as e:
            print(f"Fel vid inläsning av Excel-styrfil: {e}")
    else:
        print(f"\nInfo: Hittade ingen '{excel_path}'. Kalkylatorn använder standardvärden.")
        output_json = os.path.join(ut_mapp, "kalkylator_basdata.json")
        master_df.to_json(output_json, orient='records', force_ascii=False)

    # ==========================================
    # 6. LÄS IN RIKETS BEFOLKNING (.px)
    # ==========================================
    px_path_riket = os.path.join(px_mapp, 'RiketsAlder.px')
    
    if os.path.exists(px_path_riket):
        print(f"\nLäser in Rikets fil: {px_path_riket}...")
        try:
            df_riket = read_px_file(px_path_riket, 'Befolkning')
            if not df_riket.empty:
                df_riket['Befolkning'] = df_riket['Befolkning'].astype(int)
                output_riket = os.path.join(ut_mapp, "riket_basdata.json")
                df_riket.to_json(output_riket, orient='records', force_ascii=False)
                print(f" -> Sparade riksdata till '{output_riket}'")
        except Exception as e:
            print(f"Fel vid konvertering av Rikets .px fil: {e}")
    else:
         print(f"\nInfo: Hittade ingen '{px_path_riket}'.")

    print("\nKlart! Databas och konfigurationer är uppdaterade. Du kan nu ladda om webbappen.")

if __name__ == "__main__":
    main()