import pandas as pd
import os

def preparera_konkurrensdata():
    # 1. SÄKERSTÄLL RÄTT MAPP OCH ABSOLUTA SÖKVÄGAR
    try:
        # Sätt aktuell mapp till där skriptet ligger (t.ex. /data_pipeline)
        current_folder = os.path.dirname(os.path.abspath(__file__))
        os.chdir(current_folder)
        
        # Definiera var Excel-filen ligger (i undermappen excel_filer)
        excel_mapp = os.path.join(current_folder, "excel_filer")
        excel_fil = os.path.join(excel_mapp, "konkurrenskraft_index.xlsx")
        
        # Definiera var utfilerna ska sparas (en nivå upp, i huvudmappen)
        huvudmapp = os.path.dirname(current_folder)
        
        print(f"Skriptet körs från: {current_folder}")
        print(f"Letar efter Excel-fil i: {excel_mapp}")
        print(f"Sparar utdata i: {huvudmapp}\n")
    except NameError:
        current_folder = os.getcwd()
        huvudmapp = current_folder
        excel_fil = "konkurrenskraft_index.xlsx"

    if not os.path.exists(excel_fil):
        print(f"❌ Hittar inte filen: {excel_fil}")
        print("Kontrollera att mappen 'excel_filer' finns och innehåller filen.")
        return

    print("🔄 Läser in Excel-filen...")
    
    # 2. Läs in Styrfliken (Standardvikt)
    vikter_utfil = os.path.join(huvudmapp, "konkurrens_vikter.csv")
    try:
        df_vikter = pd.read_excel(excel_fil, sheet_name="Standardvikt")
        # Spara ner vikterna som en egen CSV som webbsidan kan läsa för att bygga reglagen
        df_vikter.to_csv(vikter_utfil, index=False, sep=";", encoding="utf-8-sig")
        print(f"✅ Sparade {vikter_utfil}")
    except Exception as e:
        print(f"❌ Kunde inte läsa fliken 'Standardvikt': {e}")
        return

    # Hämta alla fliknamn från Excel-filen
    xls = pd.ExcelFile(excel_fil)
    flikar = xls.sheet_names

    alla_data = []

    # 3. Loopa igenom alla dataflikar
    for flik in flikar:
        if flik == "Standardvikt":
            continue # Hoppa över styrfliken
            
        print(f"Laddar data från: {flik}")
        df = pd.read_excel(excel_fil, sheet_name=flik)
        
        # Säkerställ att första kolumnen heter 'Kommun'
        if df.columns[0] != 'Kommun':
            df.rename(columns={df.columns[0]: 'Kommun'}, inplace=True)
            
        # Smält (Melt) tabellen från bred (år som kolumner) till lång (databasformat)
        # Undanta 'Kommun'-kolumnen, resten antas vara årtal
        ar_kolumner = [col for col in df.columns if str(col).isdigit() or (isinstance(col, str) and col.isnumeric())]
        
        df_melted = df.melt(id_vars=['Kommun'], value_vars=ar_kolumner, var_name='År', value_name='Värde')
        df_melted['Indikator'] = flik # Lägg till namnet på indikatorn
        
        # Rensa bort ogiltiga värden (tomma celler, punkter etc)
        df_melted['Värde'] = pd.to_numeric(df_melted['Värde'].astype(str).str.replace(',', '.').replace(['..', '', 'nan'], pd.NA), errors='coerce')
        df_melted = df_melted.dropna(subset=['Värde'])
        
        alla_data.append(df_melted)

    # 4. Slå ihop all data till en stor tabell och spara
    df_final = pd.concat(alla_data, ignore_index=True)
    
    data_utfil = os.path.join(huvudmapp, "konkurrens_data.csv")
    df_final.to_csv(data_utfil, index=False, sep=";", encoding="utf-8-sig")
    
    print(f"\n✅ Sparade {data_utfil}")
    print(f"Klart! Totalt {len(df_final)} datapunkter processades.")

if __name__ == "__main__":
    preparera_konkurrensdata()