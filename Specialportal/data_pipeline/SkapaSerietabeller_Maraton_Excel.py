import os
import pandas as pd
import numpy as np

# ==========================================
# 1. ANVÄNDARINSTÄLLNINGAR FÖR VYER
# ==========================================
# Styr vilka år som ska inkluderas i Maratontabellen (sätt till None för att ta med allt)
VALD_STARTAR = 2000   # Exempel: Visa bara maratontabell från och med år 2000
VALD_SLUTAR = 2025    # Till och med år 2025

# Styr vilken enskild säsong som ska få en egen flik
VALD_ENSKILD_SASONG = "2024" 

# Styr vilken serienivå maratontabellen ska beräknas för (Sätt None för att slå ihop alla nivåer)
VALD_SERIENIVA = 1    # 1 = Allsvenskan, 2 = Superettan etc. None = Hela seriesystemet.

# ==========================================
# 2. GENERELL SETUP OCH DATA-LADDNING
# ==========================================
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
except NameError:
    project_root = os.getcwd()
    pass 

def find_target_file(keyword, search_root):
    for root, dirs, files in os.walk(search_root):
        for filename in files:
            if keyword.lower() in filename.lower() and filename.lower().endswith(".xlsx") and not filename.startswith("~$"):
                return os.path.join(root, filename)
    return None

def fix_text(text):
    encoding_fix = {
        'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
        'Ã©': 'é', 'Ã¨': 'è', 'Ã‰': 'É', "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö"
    }
    if not isinstance(text, str): return text
    for bad, good in encoding_fix.items():
        text = text.replace(bad, good)
    return text.strip()

def clean_dataframe(df):
    if df is None: return None
    str_cols = df.select_dtypes(include=['object']).columns
    for col in str_cols:
        df[col] = df[col].apply(fix_text)
    return df

def get_master_data():
    """Hämtar och förbereder master-datan (samma motor som tidigare)."""
    excel_path = find_target_file("Serietabellerna_samlade", project_root)
    if not excel_path:
        print("FEL: Hittade inte filen Serietabellerna_samlade.")
        return None, None
        
    print(f"Laddar databasen från: {os.path.basename(excel_path)}...")
    excel_dict = pd.read_excel(excel_path, sheet_name=None, engine='openpyxl')
    
    df_tabeller = clean_dataframe(excel_dict.get('Tabeller'))
    df_lag_nr = clean_dataframe(excel_dict.get('Lag_nr'))
    df_lag_id = clean_dataframe(excel_dict.get('Lag_id'))
    df_serieniva = clean_dataframe(excel_dict.get('Serienivå'))
    
    df_tabeller = df_tabeller.rename(columns={'Lag': 'Laget i tabell'}) 
    
    # Slå ihop allt
    master = pd.merge(df_tabeller, df_lag_nr[['Laget', 'Lag_ID']], left_on='Laget i tabell', right_on='Laget', how='left')
    master = pd.merge(master, df_lag_id[['Lag_ID', 'Lag', 'Distrikt', 'Kommun']], on='Lag_ID', how='left').rename(columns={'Lag': 'Standard_Lagnamn'})
    master = pd.merge(master, df_serieniva[['Säsnr', 'Poäng_seger']], on='Säsnr', how='left')
    
    # Rensa och förbereda uträkningar
    master['Analys_Lagnamn'] = master['Standard_Lagnamn'].fillna(master['Laget i tabell'])
    
    # Extrahera startår som ett rent nummer för filtrering (t.ex. "1924/25" -> 1924.0)
    master['Startår_Numerisk'] = master['Säsong'].astype(str).str.extract(r'^(\d{4})').astype(float)
    
    # Konvertera poängjustering och säkerställ att BARA minuspoäng räknas
    if 'Poängjustering_Startpoäng' in master.columns:
        master['Poängjustering_Startpoäng'] = pd.to_numeric(master['Poängjustering_Startpoäng'], errors='coerce').fillna(0)
        # Sätt alla värden > 0 till 0 (behåll endast bestraffningar/minuspoäng)
        master['Giltig_Poängavdrag'] = master['Poängjustering_Startpoäng'].apply(lambda x: x if x < 0 else 0)
    else:
        master['Giltig_Poängavdrag'] = 0

    # Matchdata till siffror
    for col in ['Sp', 'V', 'O', 'F', 'Gjorda', 'Insl']:
        master[col] = pd.to_numeric(master[col], errors='coerce').fillna(0)

    # 3-poängssystem rakt över (ink poängavdrag)
    master['Maratonpoäng'] = (master['V'] * 3) + (master['O'] * 1) + master['Giltig_Poängavdrag']
    master['Målskillnad'] = master['Gjorda'] - master['Insl']
    
    return master, df_tabeller

# ==========================================
# 3. VY-GENERATORER
# ==========================================
def create_marathon_view(df, start_year, end_year, level=None):
    """Skapar en maratontabell baserad på angivna år och eventuell serienivå."""
    temp_df = df.copy()
    
    # Filtrera på år
    if start_year is not None:
        temp_df = temp_df[temp_df['Startår_Numerisk'] >= start_year]
    if end_year is not None:
        temp_df = temp_df[temp_df['Startår_Numerisk'] <= end_year]
        
    # Filtrera på nivå
    if level is not None:
        temp_df = temp_df[temp_df['Nivå'] == level]
        
    if temp_df.empty:
        return pd.DataFrame({'Info': ['Ingen data för valda filter']})

    grouped = temp_df.groupby('Analys_Lagnamn').agg(
        Säsonger=('Startår_Numerisk', 'nunique'),
        Spelade_matcher=('Sp', 'sum'),
        Vunna=('V', 'sum'),
        Oavgjorda=('O', 'sum'),
        Förlorade=('F', 'sum'),
        Gjorda_mål=('Gjorda', 'sum'),
        Insläppta_mål=('Insl', 'sum'),
        Målskillnad=('Målskillnad', 'sum'),
        Poängavdrag=('Giltig_Poängavdrag', 'sum'),
        Poäng=('Maratonpoäng', 'sum')
    ).reset_index()
    
    # Sortera enligt gängse praxis
    grouped = grouped.sort_values(by=['Poäng', 'Målskillnad', 'Gjorda_mål'], ascending=[False, False, False]).reset_index(drop=True)
    grouped.index = grouped.index + 1
    
    return grouped

def create_season_view(df, season_str):
    """Skapar en vy för en enskild säsong, där man får de faktiska poängen."""
    # Sök på textsträngen (t.ex. "2024" eller "1924/25")
    season_df = df[df['Säsong'].astype(str).str.contains(season_str, na=False)].copy()
    
    if season_df.empty:
        return pd.DataFrame({'Info': [f'Hittade ingen data för säsong {season_str}']})
        
    # Sortera snyggt på Division, Serie och Placering
    season_df = season_df.sort_values(by=['Nivå', 'Serie', 'Plac'])
    
    # Välj ut relevanta kolumner att visa
    display_cols = ['Nivå', 'Division', 'Serie', 'Plac', 'Analys_Lagnamn', 'Sp', 'V', 'O', 'F', 'Gjorda', 'Insl', 'P', 'Poängjustering_Startpoäng']
    
    # Filtrera bort kolumner som inte finns
    display_cols = [c for c in display_cols if c in season_df.columns]
    
    return season_df[display_cols]

def create_admin_view(df):
    """Skapar en administrationsvy med diagnostik."""
    orphans = df[df['Lag_ID'].isna()]['Laget i tabell'].unique()
    
    admin_data = [
        {"Kategori": "Databasens hälsa", "Nyckeltal": "Totalt antal matchrader", "Värde": len(df)},
        {"Kategori": "Databasens hälsa", "Nyckeltal": "Unika Standard-lagnamn", "Värde": df['Standard_Lagnamn'].nunique()},
        {"Kategori": "Databasens hälsa", "Nyckeltal": "Antal föräldralösa lag (Saknar ID)", "Värde": len(orphans)},
        {"Kategori": "Poänghantering", "Nyckeltal": "Antal lag med utdömda minuspoäng", "Värde": len(df[df['Giltig_Poängavdrag'] < 0])},
        {"Kategori": "Poänghantering", "Nyckeltal": "Antal lag med bonuspoäng (som ignorerats)", "Värde": len(df[df['Poängjustering_Startpoäng'] > 0])}
    ]
    
    admin_df = pd.DataFrame(admin_data)
    
    # Lägg till en sektion för de föräldralösa lagen i samma flik
    if len(orphans) > 0:
        orphan_df = pd.DataFrame({'Kategori': 'ÅTGÄRD KRÄVS', 'Nyckeltal': 'Saknat Alias (Länka i Lag_nr)', 'Värde': orphans})
        admin_df = pd.concat([admin_df, orphan_df], ignore_index=True)
        
    return admin_df

# ==========================================
# 4. EXPORT
# ==========================================
def export_views(df):
    print("\n--- GENERERAR VYER ---")
    
    # 1. Bygg vyerna
    marathon_all = create_marathon_view(df, VALD_STARTAR, VALD_SLUTAR, level=None)
    marathon_niva = create_marathon_view(df, VALD_STARTAR, VALD_SLUTAR, level=VALD_SERIENIVA)
    season_view = create_season_view(df, VALD_ENSKILD_SASONG)
    admin_view = create_admin_view(df)
    
    # 2. Exportera till Excel
    output_path = os.path.join(project_root, "Fotbollsanalys_Vyer.xlsx")
    print(f"Exporterar till: {output_path}")
    
    try:
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            
            # Flik 1: Maratontabell (Totalen)
            fliknamn_all = f"Maraton_Alla_{VALD_STARTAR}-{VALD_SLUTAR}" if VALD_STARTAR else "Maratontabell_Totalt"
            marathon_all.to_excel(writer, sheet_name=fliknamn_all[:31], index=True, index_label='Plac')
            
            # Flik 2: Maratontabell (Enskild Nivå)
            if VALD_SERIENIVA:
                fliknamn_niva = f"Maraton_Nivå{VALD_SERIENIVA}_{VALD_STARTAR}-{VALD_SLUTAR}"
                marathon_niva.to_excel(writer, sheet_name=fliknamn_niva[:31], index=True, index_label='Plac')
                
            # Flik 3: Enskild Säsong
            season_view.to_excel(writer, sheet_name=f"Säsong_{VALD_ENSKILD_SASONG}"[:31], index=False)
            
            # Flik 4: Administration
            admin_view.to_excel(writer, sheet_name="Administration", index=False)
            
        print("Klar! Öppna 'Fotbollsanalys_Vyer.xlsx' i Excel för att se resultatet.")
        
    except PermissionError:
        print("\nFEL: Kunde inte spara filen. Är 'Fotbollsanalys_Vyer.xlsx' redan öppen i Excel? Stäng den och försök igen!")

if __name__ == "__main__":
    master_df, _ = get_master_data()
    if master_df is not None:
        export_views(master_df)