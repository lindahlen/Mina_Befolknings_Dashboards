import pandas as pd
import os

def preparera_konkurrensdata():
    try:
        # Sätt aktuell mapp till där skriptet ligger
        current_folder = os.path.dirname(os.path.abspath(__file__))
        os.chdir(current_folder)
        
        # Säkerställ att vi pekar på rätt mappar
        if os.path.basename(current_folder).lower() == "data_pipeline":
            huvudmapp = os.path.dirname(current_folder)
            excel_mapp = os.path.join(current_folder, "excel_filer")
        else:
            huvudmapp = current_folder
            excel_mapp = os.path.join(current_folder, "excel_filer")
            
        excel_fil = os.path.join(excel_mapp, "konkurrenskraft_index.xlsx")
    except NameError:
        current_folder = os.getcwd()
        huvudmapp = current_folder
        excel_fil = "konkurrenskraft_index.xlsx"

    if not os.path.exists(excel_fil):
        print(f"❌ Hittar inte filen: {excel_fil}")
        return

    print("🔄 Läser in Excel-filen...")
    
    # 1. LÄS IN STYRFLIKEN SOM TEXT
    vikter_utfil = os.path.join(huvudmapp, "konkurrens_vikter.csv")
    try:
        # dtype=str tvingar Pandas att läsa in precis allt som text. 
        df_vikter = pd.read_excel(excel_fil, sheet_name="Standardvikt", dtype=str)
        
        for col in df_vikter.columns:
            # Tvätta bort "nan" (som pandas skapat från tomma celler)
            df_vikter[col] = df_vikter[col].apply(lambda x: "" if pd.isna(x) or str(x).strip().lower() == "nan" else str(x).strip())
            
            # Formatera 'x' så det alltid blir ett stort 'X' i listorna.
            # VIKTIGT: Vi hoppar över "Beskrivning" och "Karaktär" så vi inte förstör klartext där!
            if col not in ["Klartext", "Indikator", "Polaritet", "Beskrivning", "Karaktär"]:
                df_vikter[col] = df_vikter[col].apply(lambda val: "X" if val.upper() == "X" else val)

        df_vikter.to_csv(vikter_utfil, index=False, sep=";", encoding="utf-8-sig")
        print(f"✅ Sparade {vikter_utfil}")
    except Exception as e:
        print(f"❌ Kunde inte läsa fliken 'Standardvikt': {e}")
        return

    # 2. LÄS IN OCH KOMBINERA DATAFLIKARNA
    xls = pd.ExcelFile(excel_fil)
    flikar = xls.sheet_names
    alla_data = []

    for flik in flikar:
        if flik == "Standardvikt":
            continue
            
        print(f"Laddar data från: {flik}")
        try:
            df = pd.read_excel(excel_fil, sheet_name=flik)
            
            if df.columns[0] != 'Kommun':
                df.rename(columns={df.columns[0]: 'Kommun'}, inplace=True)
                
            ar_kolumner = [col for col in df.columns if str(col).isdigit() or (isinstance(col, str) and col.isnumeric())]
            
            df_melted = df.melt(id_vars=['Kommun'], value_vars=ar_kolumner, var_name='År', value_name='Värde')
            df_melted['Indikator'] = flik
            
            df_melted['Värde'] = pd.to_numeric(df_melted['Värde'].astype(str).str.replace(',', '.').replace(['..', '', 'nan', '-'], pd.NA), errors='coerce')
            df_melted = df_melted.dropna(subset=['Värde'])
            
            alla_data.append(df_melted)
        except Exception as e:
            print(f"⚠️ Kunde inte bearbeta flik {flik}: {e}")

    df_all = pd.concat(alla_data, ignore_index=True)

    # ==========================================
    # 3. BERÄKNA DE NYA SAMMANSATTA INDIKATORERNA
    # ==========================================
    print("\n🧮 Beräknar sammansatta indikatorer...")
    
    # Skapa en pivottabell för att enkelt kunna multiplicera kolumner mot varandra
    df_pivot = df_all.pivot_table(index=['Kommun', 'År'], columns='Indikator', values='Värde', aggfunc='first').reset_index()

    # Hjälpfunktion för att hämta RÄTT internt namn (Indikator) från Excel-filens Klartext
    def get_ind_name(klartext_str):
        mask = df_vikter['Klartext'].str.strip() == klartext_str
        if mask.any():
            return df_vikter.loc[mask, 'Indikator'].values[0]
        return None

    def compute_indicator(klartext_str, calc_func):
        n = get_ind_name(klartext_str)
        if n:
            calc_func(n)
            print(f"   -> Beräknade: {klartext_str}")
        else:
            print(f"   ⚠️ Hittade inte '{klartext_str}' i styrfliken. Hoppar över beräkning.")

    # -- Matematiken för varje specifik indikator --
    def calc_1(n):
        if 'Vuxen_bef' in df_pivot.columns and 'Folkmängd' in df_pivot.columns:
            df_pivot[n] = (df_pivot['Vuxen_bef'] / df_pivot['Folkmängd']) * 100
    
    def calc_2(n):
        if 'Inflyttning_annat_län' in df_pivot.columns and 'Utflyttning_annat_län' in df_pivot.columns:
            df_pivot[n] = df_pivot['Inflyttning_annat_län'] - df_pivot['Utflyttning_annat_län']

    def calc_3(n):
        in_col = 'Inflytt_annat_län_30-59'
        ut_col = 'Utflytt_annat_län_30-59'
        if in_col in df_pivot.columns and ut_col in df_pivot.columns:
            df_pivot[n] = df_pivot[in_col] - df_pivot[ut_col]

    def calc_4(n):
        if 'KIBS' in df_pivot.columns and 'Sysselsatta' in df_pivot.columns:
            df_pivot[n] = (df_pivot['KIBS'] / df_pivot['Sysselsatta']) * 100

    def calc_5(n):
        if 'Inpendling' in df_pivot.columns and 'Sysselsatta' in df_pivot.columns:
            df_pivot[n] = (df_pivot['Inpendling'] / df_pivot['Sysselsatta']) * 100

    def calc_6(n):
        if 'Inpendling' in df_pivot.columns and 'Utpendling' in df_pivot.columns:
            df_pivot[n] = df_pivot['Inpendling'] - df_pivot['Utpendling']

    def calc_7(n):
        if 'Sysselsatta' in df_pivot.columns:
            df_pivot.sort_values(['Kommun', 'År'], inplace=True)
            df_pivot[n] = df_pivot.groupby('Kommun')['Sysselsatta'].pct_change() * 100
            df_pivot[n] = df_pivot[n].replace([float('inf'), float('-inf')], pd.NA)

    def calc_8(n):
        if 'Folkmängd' in df_pivot.columns:
            df_pivot.sort_values(['Kommun', 'År'], inplace=True)
            df_pivot[n] = df_pivot.groupby('Kommun')['Folkmängd'].pct_change() * 100
            df_pivot[n] = df_pivot[n].replace([float('inf'), float('-inf')], pd.NA)

    def calc_9(n):
        c1 = 'Inflytt_eget_län'
        c2 = 'Inflyttning_annat_län'
        if c1 in df_pivot.columns and c2 in df_pivot.columns:
            sum_inflytt = df_pivot[c1] + df_pivot[c2]
            # Dividera och multiplicera med 100 för procent (replace skyddar mot division med noll)
            df_pivot[n] = (df_pivot[c1] / sum_inflytt.replace(0, pd.NA)) * 100

    # Utför alla beställda beräkningar
    compute_indicator("Befolkning i åldern 30-59 år, andel av hela bef (%)", calc_1)
    compute_indicator("Nettoflyttning annat län, antal", calc_2)
    compute_indicator("Nettoflyttning annat län 30-59 år, antal", calc_3)
    compute_indicator("KIBS 15-74 år, andel av sysselsatta (%)", calc_4)
    compute_indicator("Inpendling över kommungräns 15-74 år, andel av dagbef (%)", calc_5)
    compute_indicator("Nettopendling, antal", calc_6)
    compute_indicator("Sysselsättning 15-74 år, förändring per år (%)", calc_7)
    compute_indicator("Befolkningsförändring per år (%)", calc_8)
    compute_indicator("Inflyttningsandel eget län av inrikes inflyttning", calc_9)

    # 4. SMÄLT TILLBAKA TILL ETT RAKTDATABAS-FORMAT
    df_final = df_pivot.melt(id_vars=['Kommun', 'År'], var_name='Indikator', value_name='Värde')
    df_final['Värde'] = pd.to_numeric(df_final['Värde'], errors='coerce')
    df_final = df_final.dropna(subset=['Värde'])

    # 5. SPARA TILL HUVUDMAPPEN
    data_utfil = os.path.join(huvudmapp, "konkurrens_data.csv")
    df_final.to_csv(data_utfil, index=False, sep=";", encoding="utf-8-sig")
    
    print(f"\n✅ Sparade {data_utfil}")
    print(f"Klart! Totalt {len(df_final)} datapunkter processades.")

if __name__ == "__main__":
    preparera_konkurrensdata()