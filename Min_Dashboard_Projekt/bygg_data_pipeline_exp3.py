import os
import pandas as pd

# ==========================================
# 1. SÄKERSTÄLL RÄTT MAPP OCH ABSOLUTA SÖKVÄGAR
# ==========================================
try:
    # current_folder blir den mapp där detta skript ligger
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
    
    # SMART SÖKVÄGSHANTERING:
    # Om du har skapat undermappen "data_pipeline" och lagt skriptet där, går vi upp ett steg.
    # Om skriptet ligger direkt i din huvudmapp sparar vi CSV-filerna i samma mapp.
    if os.path.basename(current_folder).lower() == "data_pipeline":
        huvudmapp = os.path.dirname(current_folder)
    else:
        huvudmapp = current_folder
        
    print(f"Skriptet körs från: {current_folder}")
    print(f"Filer kommer att sparas i: {huvudmapp}\n")
except NameError:
    current_folder = os.getcwd()
    huvudmapp = current_folder

# ==========================================
# 2. STÖDKONTROLL FÖR R12-BERÄKNING
# ==========================================
R12_REGLER = {
    'Befolkningsförändring': 'SUM',
    'Födda_barn': 'SUM',
    'Döda': 'SUM',
    'Inflyttning': 'SUM',
    'Utflyttning': 'SUM',
    'Befolkning': 'SISTA', 
    
    'Sysselsatta': 'SISTA',
    'Tillverkning': 'SISTA',
    'Handel': 'SISTA',
    'IKT': 'SISTA',
    'Utbildning': 'SISTA',
    'Vård_Omsorg': 'SISTA',
    'Offentlig_förvaltning': 'SISTA',
    
    'Färdigställda_bostäder': 'SUM',
    'Färdigställda_småhus': 'SUM',
    'Färdigställda_flerbostadshus': 'SUM',
    'Påbörjade_bostäder': 'SUM',
    'Påbörjade_småhus': 'SUM',
    'Påbörjade_flerbostadshus': 'SUM',
    
    'Inskrivna_arbetslösa': 'SISTA',
    'Inskrivna_arbetslösa_%': 'SISTA',
    'Inrikes_födda_arbetslösa': 'SISTA',
    'Utrikes_födda_arbetslösa': 'SISTA',
    'Ungdomar_arbetslösa': 'SISTA',
    'Långtidsarbetslösa': 'SISTA'
}

# Vi tog bort "../" härifrån och sköter det med absolut sökväg längre ner
FLIK_TILL_FIL = {
    'Befolkningsförändring': 'Data_Diagram31.csv',
    'Sysselsättning': 'Data_Diagram32.csv',
    'Bostadsbyggande': 'Data_Diagram33.csv',
    'Arbetslöshet': 'Data_Diagram34.csv'
}

def bygg_alla_diagram_exp3():
    print("🚀 Startar Experiment 3 Pipeline...\n")
    
    radata_fil = "KvartalsstatistikExperimentRiket.xlsx"
    mal_fil = "mal_och_prognoser.xlsx" # Ändra till "mal_ochprognoser.xlsx" om det är så din fil heter!
    
    # ---------------------------------------------------------
    # FELSÖKNING: Kontrollera att mål-filen faktiskt existerar
    # ---------------------------------------------------------
    if not os.path.exists(mal_fil):
        print(f"⚠️ Kritiskt: Hittar inte filen '{mal_fil}' i {current_folder}.")
        print("Kontrollera om filnamnet stämmer (t.ex. 'mal_ochprognoser.xlsx' istället för 'mal_och_prognoser.xlsx')")
        print("Mål och prognoser kommer att bli tomma tills filnamnet i koden stämmer med filen på datorn.\n")
    
    for flik_namn, utfil_namn in FLIK_TILL_FIL.items():
        print(f"--- Bearbetar flik: {flik_namn} ---")
        
        # ==========================================
        # 3. LÄS IN RÅDATA OCH STÄDA BORT GAMLA BERÄKNINGAR
        # ==========================================
        try:
            df_radata = pd.read_excel(radata_fil, sheet_name=flik_namn)
            df_radata.columns = df_radata.columns.str.strip()
        except Exception as e:
            print(f"❌ Kunde inte läsa fliken '{flik_namn}' i {radata_fil}: {e}")
            try:
                # Skriv ut vilka flikar som faktiskt finns för att underlätta felsökning
                xls = pd.ExcelFile(radata_fil)
                print(f"Flikar som finns i Excel-filen: {xls.sheet_names}")
            except:
                pass
            print("Hoppar över denna flik.\n")
            continue

        kolumner_att_behalla = ['År', 'Kvartal']
        indikatorer_i_flik = [] 
        
        for col in df_radata.columns:
            if col.endswith('_Kvartal') or col.endswith('_Kvartal_Riket'):
                if col not in kolumner_att_behalla:
                    kolumner_att_behalla.append(col)
                if col.endswith('_Kvartal'):
                    indikatorer_i_flik.append(col.replace('_Kvartal', ''))
                    
        df_radata = df_radata[kolumner_att_behalla].copy()

        # ==========================================
        # 4. RÄKNA UT R12 MED STÖDKONTROLLEN
        # ==========================================
        for ind in indikatorer_i_flik:
            regel = R12_REGLER.get(ind, 'SUM')
            
            # Kommunen
            if regel == 'SUM':
                df_radata[f'{ind}_R12'] = df_radata[f'{ind}_Kvartal'].rolling(window=4).sum()
            elif regel == 'SISTA':
                df_radata[f'{ind}_R12'] = df_radata[f'{ind}_Kvartal']
            elif regel == 'MEDEL':
                df_radata[f'{ind}_R12'] = df_radata[f'{ind}_Kvartal'].rolling(window=4).mean()

            # Riket
            riket_col = f'{ind}_Kvartal_Riket'
            if riket_col in df_radata.columns:
                if regel == 'SUM':
                    df_radata[f'{ind}_R12_Riket'] = df_radata[riket_col].rolling(window=4).sum()
                elif regel == 'SISTA':
                    df_radata[f'{ind}_R12_Riket'] = df_radata[riket_col]
                elif regel == 'MEDEL':
                    df_radata[f'{ind}_R12_Riket'] = df_radata[riket_col].rolling(window=4).mean()

        print(f"✅ R12 beräknat för {len(indikatorer_i_flik)} indikatorer.")

        # ==========================================
        # 5. LÄS IN MÅL OCH PROGNOSER
        # ==========================================
        try:
            df_mal = pd.read_excel(mal_fil, sheet_name=flik_namn)
            df_mal.columns = df_mal.columns.str.strip()
            for col in df_mal.select_dtypes(include=['object']).columns:
                df_mal[col] = df_mal[col].apply(lambda x: str(x).strip() if pd.notnull(x) else "")
            print(f"✅ Mål inlästa från fliken '{flik_namn}'.")
        except Exception as e:
            print(f"⚠️ Hittade inga mål för fliken '{flik_namn}'.")
            if os.path.exists(mal_fil):
                try:
                    xls_mal = pd.ExcelFile(mal_fil)
                    print(f"💡 Tips: Flikarna i din fil {mal_fil} heter: {xls_mal.sheet_names}")
                except:
                    pass
            print("Skapar en tom mål-struktur för denna flik.")
            df_mal = pd.DataFrame(columns=['År', 'Kvartal'])

        # ==========================================
        # 6. MERGE OCH EXPORT
        # ==========================================
        df_kombinerad = pd.merge(df_radata, df_mal, on=['År', 'Kvartal'], how='left')
        df_kombinerad.fillna("", inplace=True)
        
        # Skapa den absoluta sökvägen till din huvudmapp
        utfil_absolut = os.path.join(huvudmapp, utfil_namn)
        
        df_kombinerad.to_csv(utfil_absolut, sep=";", index=False, encoding="cp1252", decimal=",")
        print(f"✅ Klar! Filen sparades på den exakta sökvägen:\n   {utfil_absolut}\n")

if __name__ == "__main__":
    bygg_alla_diagram_exp3()