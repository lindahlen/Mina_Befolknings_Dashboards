import os
import pandas as pd

# ==========================================
# 1. GENERELL SETUP OCH SÖKVÄGAR
# ==========================================
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
except NameError:
    project_root = os.getcwd()
    pass 

def find_target_file(keyword, search_root):
    """
    Söker igenom hela modermappen och alla dess undermappar för att hitta en Excel-fil 
    som innehåller det angivna nyckelordet.
    """
    for root, dirs, files in os.walk(search_root):
        for filename in files:
            # Letar efter en fil som innehåller nyckelordet OCH är en .xlsx-fil (ignorerar öppna temp-filer)
            if keyword.lower() in filename.lower() and filename.lower().endswith(".xlsx") and not filename.startswith("~$"):
                return os.path.join(root, filename)
    return None

# ==========================================
# 2. TEXTHANTERING (Din standardfix)
# ==========================================
encoding_fix = {
    'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
    'Ã©': 'é', 'Ã¨': 'è', 'Ã‰': 'É', "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö"
}

def fix_text(text):
    """Åtgärdar UTF-8 tolkad som ANSI."""
    if not isinstance(text, str): return text
    for bad, good in encoding_fix.items():
        text = text.replace(bad, good)
    return text.strip() # Strip tar även bort smygande mellanslag på slutet

def clean_dataframe(df):
    """Applicerar textfix på alla string-kolumner i en dataframe."""
    if df is None: return None
    str_cols = df.select_dtypes(include=['object']).columns
    for col in str_cols:
        df[col] = df[col].apply(fix_text)
    return df

# ==========================================
# 3. DATABASMOTORN (Sammanslagning)
# ==========================================
def build_master_dataframe():
    """Laddar en Excel-fil, hämtar de 4 flikarna och slår ihop dem till en master-tabell."""
    print("\n--- STARTAR DATABASMOTORN ---")
    print(f"Söker efter Excel-fil i: {project_root}")
    
    # 1. Leta efter Excel-filen
    excel_path = find_target_file("Serietabellerna_samlade", project_root)
    
    if not excel_path:
        print("FEL: Kunde inte hitta någon Excel-fil som innehåller 'Serietabellerna_samlade'.")
        return None
        
    print(f"Laddar in data från: {os.path.basename(excel_path)}")
    print("Detta kan ta några sekunder beroende på filens storlek...")
    
    # 2. Läs in alla flikar från Excel-filen (kräver modulen 'openpyxl')
    try:
        excel_dict = pd.read_excel(excel_path, sheet_name=None, engine='openpyxl')
    except Exception as e:
        print(f"FEL vid inläsning: {e}")
        print("Tips: Se till att filen inte är öppen i Excel och att du har kört 'pip install openpyxl'.")
        return None

    # Hämta ut flikarna (Säkerställ att namnen matchar exakt dina Excel-flikar)
    df_tabeller = clean_dataframe(excel_dict.get('Tabeller'))
    df_lag_nr = clean_dataframe(excel_dict.get('Lag_nr'))
    df_lag_id = clean_dataframe(excel_dict.get('Lag_id'))
    df_serieniva = clean_dataframe(excel_dict.get('Serienivå'))
    
    if df_tabeller is None or df_lag_nr is None or df_lag_id is None or df_serieniva is None:
        print("FEL: Hittade inte alla nödvändiga flikar. Kontrollera att flikarna heter:")
        print("'Tabeller', 'Lag_nr', 'Lag_id', och 'Serienivå'")
        return None

    # --- KVALITETSKONTROLL STEG 1: Rensa Tabeller från irrelevanta tecken ---
    df_tabeller = df_tabeller.rename(columns={'Lag': 'Laget i tabell'}) 
    
    # --- SLÅ IHOP DATA ---
    print("\nKopplar ihop 'Tabeller' med 'Lag_nr' (Alias)...")
    # Vänster-join: Behåll allt i tabeller, fyll på med Lag_ID där det matchar namnet i Lag_nr
    master = pd.merge(
        df_tabeller, 
        df_lag_nr[['Laget', 'Lag_ID']], 
        left_on='Laget i tabell', 
        right_on='Laget', 
        how='left'
    )

    print("Kopplar på standardiserat lagnamn från 'Lag_id'...")
    master = pd.merge(
        master,
        df_lag_id[['Lag_ID', 'Lag', 'Distrikt', 'Kommun']],
        on='Lag_ID',
        how='left'
    ).rename(columns={'Lag': 'Standard_Lagnamn'})

    print("Kopplar på säsongsfakta (Poängsystem etc) från 'Serienivå'...")
    master = pd.merge(
        master,
        df_serieniva[['Säsnr', 'Poäng_seger']],
        on='Säsnr',
        how='left'
    )

    # --- KVALITETSKONTROLL STEG 2: Identifiera 'Föräldralösa rader' ---
    orphans = master[master['Lag_ID'].isna()]
    
    print("\n==========================================")
    print(" 🚨 KVALITETSKONTROLL: FÖRÄLDRALÖSA LAG ")
    print("==========================================")
    
    if len(orphans) > 0:
        print(f"Hittade {len(orphans)} rader i 'Tabeller' som inte kunde matchas mot något i 'Lag_nr'.")
        print("Här är de första 10 unika lagnamnen som saknar ett Alias:\n")
        
        unique_orphans = orphans['Laget i tabell'].unique()
        for i, lag in enumerate(unique_orphans[:10]):
            print(f" - '{lag}' (Finns ej i Lag_nr)")
            
        if len(unique_orphans) > 10:
            print(f"...och {len(unique_orphans) - 10} till. (Sparar en fellista som CSV!)")
            
        pd.DataFrame({'Saknade_namn_i_Lag_nr': unique_orphans}).to_csv("Fellista_Saknade_Lag_Alias.csv", index=False, sep=";", encoding="utf-8-sig")
        print("\n--> Exporterade 'Fellista_Saknade_Lag_Alias.csv' till modermappen.")
    else:
        print("✅ Perfekt! Alla lag i resultattabellen fick en träff mot ett Lag_ID i 'Lag_nr'.")

    # --- STÄDA UPP MASTER-DATAN INNAN RETURN ---
    if 'Poängjustering_Startpoäng' in master.columns:
        master['Poängjustering_Startpoäng'] = pd.to_numeric(master['Poängjustering_Startpoäng'], errors='coerce').fillna(0)
    
    master['Säsongsdel'] = 'Helår'
    if 'Anm' in master.columns:
         master.loc[master['Anm'].str.contains('höst', case=False, na=False), 'Säsongsdel'] = 'Höst'
         master.loc[master['Anm'].str.contains('vår', case=False, na=False), 'Säsongsdel'] = 'Vår'
         
    return master

# ==========================================
# 4. KÖRNING
# ==========================================
if __name__ == "__main__":
    master_df = build_master_dataframe()
    
    if master_df is not None:
        print("\n==========================================")
        print(" 📊 SYSTEMSTATUS ")
        print("==========================================")
        print(f"Master-tabellen innehåller nu {len(master_df)} matchrader.")
        print("Exempel på kolumner:", list(master_df.columns[:10]) + ["...", "Standard_Lagnamn", "Poäng_seger", "Säsongsdel"])