import os
import pandas as pd

# ==========================================
# 1. SÄKERSTÄLL RÄTT MAPP
# ==========================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
    print(f"Arbetskatalog satt till: {current_folder}")
except NameError:
    pass 

def bygg_diagram21_steg_for_steg():
    print("Steg 1: Beräknar R12 och slår ihop med mål...")

    # ==========================================
    # 2. LÄS IN RÅDATA OCH RENSA BORT GAMLA MÅL/R12
    # ==========================================
    # Vi använder din befintliga fil, men vi ska strax be Python strunta i de kolumner
    # som har med Mål, Prognoser och gamla R12 att göra.
    radata_fil = "KvartalsstatistikExperimentRiket.xlsx" 
    
    try:
        df_radata = pd.read_excel(radata_fil)
        df_radata.columns = df_radata.columns.str.strip()
        print(f"✅ Läst in Rådata: {len(df_radata)} rader.")
    except Exception as e:
        print(f"❌ Kunde inte läsa {radata_fil}: {e}")
        return

    # Vi väljer ut *enbart* de kolumner som är historiskt utfall (rådata)
    kolumner_att_behalla = [
        'År', 'Kvartal', 
        'Befolkningsförändring_Kvartal', 'Befolkningsförändring_Kvartal_Riket',
        'Födda_barn_Kvartal', 'Födda_barn_Kvartal_Riket',
        'Döda_Kvartal', 'Döda_Kvartal_Riket',
        'Inflyttning_Kvartal', 'Inflyttning_Kvartal_Riket',
        'Utflyttning_Kvartal', 'Utflyttning_Kvartal_Riket',
        'Befolkning_Kvartal', 'Befolkning_Kvartal_Riket'
    ]
    df_radata = df_radata[kolumner_att_behalla].copy()
    print("✅ Raderat gamla Prognoser, Trösklar och manuella R12 från minnet.")

    # ==========================================
    # 3. LÅT PYTHON RÄKNA UT R12 (Rullande 12 månader)
    # ==========================================
    # Nu beräknar Python R12 helt automatiskt för alla indikatorer!
    indikatorer = ['Befolkningsförändring', 'Födda_barn', 'Döda', 'Inflyttning', 'Utflyttning', 'Befolkning']
    
    for ind in indikatorer:
        # Räkna ut R12 för Linköping (.rolling(4).sum() summerar de 4 senaste raderna)
        df_radata[f'{ind}_R12'] = df_radata[f'{ind}_Kvartal'].rolling(window=4).sum()
        # Räkna ut R12 för Riket
        df_radata[f'{ind}_R12_Riket'] = df_radata[f'{ind}_Kvartal_Riket'].rolling(window=4).sum()
        
    print("✅ R12 färdigberäknat av Python för alla indikatorer.")

    # ==========================================
    # 4. LÄS IN DINA MÅL OCH PROGNOSER
    # ==========================================
    mal_fil = "mal_och_prognoser.xlsx"
    try:
        df_mal = pd.read_excel(mal_fil)
        df_mal.columns = df_mal.columns.str.strip()
        print(f"✅ Läst in Mål/Prognoser: {len(df_mal)} rader.")
    except Exception as e:
        print(f"❌ Kunde inte läsa {mal_fil}: {e}")
        return

    # Tvätta texten (för att slippa osynliga mellanslag i t.ex. "Hög")
    for col in df_mal.select_dtypes(include=['object']).columns:
        df_mal[col] = df_mal[col].apply(lambda x: str(x).strip() if pd.notnull(x) else "")

    # ==========================================
    # 5. MERGE: SLÅ IHOP RÅDATA MED MÅL
    # ==========================================
    # 'how="left"' betyder att vi utgår från rådatan (åren och kvartalen där), 
    # och klistrar på mål där 'År' och 'Kvartal' matchar.
    df_kombinerad = pd.merge(df_radata, df_mal, on=['År', 'Kvartal'], how='left')
    
    # Byt ut eventuella "NaN" (Not a Number) mot tomma fält
    df_kombinerad.fillna("", inplace=True)
    print("✅ Rådata och Prognoser har slagits ihop framgångsrikt.")

    # ==========================================
    # 6. EXPORTERA TILL DASHBOARDEN
    # ==========================================
    utfil_sokvag = "../Data_Diagram28.csv"
    
    # Spara med svensk standard (cp1252 och decimal=",") för att matcha dashboarden perfekt
    df_kombinerad.to_csv(utfil_sokvag, sep=";", index=False, encoding="cp1252", decimal=",")
    print(f"✅ Klar! Filen sparades som: {utfil_sokvag}")

if __name__ == "__main__":
    bygg_diagram21_steg_for_steg()