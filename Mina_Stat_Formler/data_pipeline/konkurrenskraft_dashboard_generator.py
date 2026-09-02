import pandas as pd
import numpy as np
import os
import folium
import json

# ==========================================
# DEL 1: DATABEARBETNING (Din ursprungliga logik)
# ==========================================
def preparera_konkurrensdata():
    try:
        current_folder = os.path.dirname(os.path.abspath(__file__))
        os.chdir(current_folder)
        
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
        return None

    print("🔄 Läser in Excel-filen...")
    vikter_utfil = os.path.join(huvudmapp, "konkurrens_vikter2.csv")
    try:
        df_vikter = pd.read_excel(excel_fil, sheet_name="Standardvikt", dtype=str)
        
        for col in df_vikter.columns:
            df_vikter[col] = df_vikter[col].apply(lambda x: "" if pd.isna(x) or str(x).strip().lower() == "nan" else str(x).strip())
            
            if col not in ["Klartext", "Indikator", "Polaritet", "Beskrivning", "Karaktär"]:
                df_vikter[col] = df_vikter[col].apply(lambda val: "X" if val.upper() == "X" else val)

        df_vikter.to_csv(vikter_utfil, index=False, sep=";", encoding="utf-8-sig")
        print(f"✅ Sparade {vikter_utfil}")
    except Exception as e:
        print(f"❌ Kunde inte läsa fliken 'Standardvikt': {e}")
        return None

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

    print("\n🧮 Beräknar sammansatta indikatorer...")
    df_pivot = df_all.pivot_table(index=['Kommun', 'År'], columns='Indikator', values='Värde', aggfunc='first').reset_index()

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

    def calc_1(n):
        if 'Vuxen_bef' in df_pivot.columns and 'Folkmängd' in df_pivot.columns:
            df_pivot[n] = (df_pivot['Vuxen_bef'] / df_pivot['Folkmängd']) * 100
    def calc_2(n):
        if 'Inflyttning_annat_län' in df_pivot.columns and 'Utflyttning_annat_län' in df_pivot.columns:
            df_pivot[n] = df_pivot['Inflyttning_annat_län'] - df_pivot['Utflyttning_annat_län']
    def calc_3(n):
        if 'Inflytt_annat_län_30-59' in df_pivot.columns and 'Utflytt_annat_län_30-59' in df_pivot.columns:
            df_pivot[n] = df_pivot['Inflytt_annat_län_30-59'] - df_pivot['Utflytt_annat_län_30-59']
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
        if 'Inflytt_eget_län' in df_pivot.columns and 'Inflyttning_annat_län' in df_pivot.columns:
            sum_inflytt = df_pivot['Inflytt_eget_län'] + df_pivot['Inflyttning_annat_län']
            df_pivot[n] = (df_pivot['Inflytt_eget_län'] / sum_inflytt.replace(0, pd.NA)) * 100

    compute_indicator("Befolkning i åldern 30-59 år, andel av hela bef (%)", calc_1)
    compute_indicator("Nettoflyttning annat län, antal", calc_2)
    compute_indicator("Nettoflyttning annat län 30-59 år, antal", calc_3)
    compute_indicator("KIBS 15-74 år, andel av sysselsatta (%)", calc_4)
    compute_indicator("Inpendling över kommungräns 15-74 år, andel av dagbef (%)", calc_5)
    compute_indicator("Nettopendling, antal", calc_6)
    compute_indicator("Sysselsättning 15-74 år, förändring per år (%)", calc_7)
    compute_indicator("Befolkningsförändring per år (%)", calc_8)
    compute_indicator("Inflyttningsandel eget län av inrikes inflyttning", calc_9)

    df_final = df_pivot.melt(id_vars=['Kommun', 'År'], var_name='Indikator', value_name='Värde')
    df_final['Värde'] = pd.to_numeric(df_final['Värde'], errors='coerce')
    df_final = df_final.dropna(subset=['Värde'])

    data_utfil = os.path.join(huvudmapp, "analysplattform_data.csv")
    df_final.to_csv(data_utfil, index=False, sep=";", encoding="utf-8-sig")
    
    print(f"✅ Sparade {data_utfil} ({len(df_final)} rader)")
    return huvudmapp


# ==========================================
# DEL 2: INDEX-MOTOR (Harmoniserad & Relativ mot Riket)
# ==========================================
def berakna_index(huvudmapp, perspektiv="Standardvikt_kombination", target_year=None):
    print(f"\n📊 Beräknar harmoniserat index för {target_year} | Perspektiv: {perspektiv}...")
    
    # Texttvätt för åäö (enligt Master Config)
    encoding_fix = {
        'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
        'Ã©': 'é', 'Ã¨': 'è', 'Ã‰': 'É', "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö"
    }
    def fix_text(text):
        if not isinstance(text, str): return text
        for bad, good in encoding_fix.items():
            text = text.replace(bad, good)
        return text.strip()

    # Läs in data
    df = pd.read_csv(os.path.join(huvudmapp, "konkurrens_data.csv"), sep=";", encoding='utf-8-sig')
    vikter = pd.read_csv(os.path.join(huvudmapp, "konkurrens_vikter2.csv"), sep=";", encoding='utf-8-sig')

    # 💡 DYNAMISKT ÅRTAL: Hitta det senaste året automatiskt
    if target_year is None:
        target_year = df['År'].max()
        print(f"🔄 Inget årtal angivet. Använder senaste tillgängliga år: {target_year}")
    
    # Rensa namn och kolumner
    df['Kommun'] = df['Kommun'].apply(fix_text)
    df['Indikator'] = df['Indikator'].apply(fix_text)
    vikter['Indikator'] = vikter['Indikator'].apply(fix_text)
    vikter['Polaritet'] = vikter['Polaritet'].apply(fix_text)
    
    # --- INJICERA DE NYA STRATEGISKA INDEXEN (PCI, ECI, HCI) ---
    nya_index = {
        'Bostadspriser': {'PCI_Proxy': 0.35},
        'Nettoflyttning (Beräknad Inflytt_annat_län_30-59-Utflytt_annat_län_30-59)': {'PCI_Proxy': 0.25},
        'Bostadsbyggande': {'PCI_Proxy': 0.25},
        'Födda_1000_vuxna': {'PCI_Proxy': 0.15},
        
        'BRP': {'ECI_Proxy': 0.40},
        'Nettopendling (Beräknad Inpendling-Utpendling)': {'ECI_Proxy': 0.25},
        'Nettoinkomst_median': {'ECI_Proxy': 0.15},
        'Förvärvsinkomst_median': {'ECI_Proxy': 0.05},
        'Nyföretagande': {'ECI_Proxy': 0.15},
        
        'Lång_eftergymnasial_proc25': {'HCI_Proxy': 0.40},
        'KIBS (beräkning Sysselsatta)': {'HCI_Proxy': 0.30},
        'Sysselsättningsgrad': {'HCI_Proxy': 0.20},
        'Långtidsarbetslöshet': {'HCI_Proxy': 0.10}
    }
    
    for ind, weights in nya_index.items():
        if ind in vikter['Indikator'].values:
            idx = vikter.index[vikter['Indikator'] == ind].tolist()[0]
            for col, w in weights.items():
                if col not in vikter.columns: 
                    vikter[col] = pd.NA
                vikter.at[idx, col] = w

    # Hämta årets data
    df['År'] = pd.to_numeric(df['År'], errors='coerce')
    df_year = df[df['År'] == target_year].copy()
    
    if perspektiv not in vikter.columns:
        perspektiv = "Standardvikt_kombination"
        
    aktiva_vikter = vikter.dropna(subset=[perspektiv])
    aktiva_vikter = aktiva_vikter[aktiva_vikter[perspektiv] != '..']
    aktiva_vikter = aktiva_vikter[pd.to_numeric(aktiva_vikter[perspektiv], errors='coerce').notnull()]
    
    # Logik för att avgöra om volym behöver göras relativ per capita
    def requires_scaling(ind_name):
        name_lower = ind_name.lower()
        if "%" in name_lower or "andel" in name_lower or "kvot" in name_lower or "per capita" in name_lower or "per 1000" in name_lower or "median" in name_lower or "grad" in name_lower or "priser" in name_lower:
            return False
        return True

    def get_value(kommun, indikator):
        rad = df_year[(df_year['Kommun'] == kommun) & (df_year['Indikator'] == indikator)]
        if not rad.empty:
            try: return float(rad['Värde'].values[0])
            except: return np.nan
        return np.nan

    target_areas = ['Stockholm', 'Göteborg', 'Malmö', 'Uppsala', 'Linköping', 
                    'Västerås', 'Örebro', 'Helsingborg', 'Jönköping', 'Norrköping', 
                    'Umeå', 'Lund', 'Östergötlands län', 'Riket']
    
    resultat = []

    for kommun in target_areas:
        total_score = 0
        total_weight = 0
        detaljer = {}
        
        for _, rad in aktiva_vikter.iterrows():
            ind = rad['Indikator']
            vikt = float(rad[perspektiv])
            polaritet = str(rad['Polaritet']).strip().lower()
            
            kom_val = get_value(kommun, ind)
            riket_val = get_value('Riket', ind)
            
            if pd.isna(kom_val) or pd.isna(riket_val):
                continue
                
            # Om det är en absolut volym, räkna om till värde per 100 000 invånare
            if requires_scaling(ind):
                kom_pop = get_value(kommun, 'Folkmängd')
                riket_pop = get_value('Riket', 'Folkmängd')
                if pd.notna(kom_pop) and kom_pop > 0:
                    kom_val = (kom_val / kom_pop) * 100000
                if pd.notna(riket_pop) and riket_pop > 0:
                    riket_val = (riket_val / riket_pop) * 100000

            # Matematisk harmonisering: Index där Riket alltid är 100
            if riket_val != 0:
                kvot = kom_val / riket_val
                if polaritet == 'låg':
                    index_poäng = (2.0 - kvot) * 100
                else:
                    index_poäng = kvot * 100
            else:
                index_poäng = 100

            # Tak för extremvärden
            index_poäng = max(0, min(250, index_poäng))
            
            total_score += (index_poäng * vikt)
            total_weight += vikt
            detaljer[ind] = round(index_poäng, 1)
            
        if total_weight > 0:
            slutpoäng = total_score / total_weight
            resultat.append({
                'Kommun': kommun,
                'Total_Score': round(slutpoäng, 1),
                'Details': detaljer
            })
            
    return pd.DataFrame(resultat), vikter


# ==========================================
# DEL 3: VISUALISERING (Folium + Chart.js & Master Config UI)
# ==========================================
def skapa_dashboard(huvudmapp):
    print("🗺️ Bygger interaktiv karta med färgkodning och diagram...")
    
    # --- MASTER CONFIG 2.0: SÄKRA SÖKVÄGAR & ENCODING FIX ---
    import os, sys, json, ast
    try:
        current_folder = os.path.dirname(os.path.abspath(__file__))
        os.chdir(current_folder)
    except NameError:
        pass

    encoding_fix = {
        'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
        'Ã©': 'é', 'Ã¨': 'è', 'Ã‰': 'É', "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö"
    }
    def fix_text(text):
        if not isinstance(text, str): return text
        for bad, good in encoding_fix.items():
            text = text.replace(bad, good)
        return text.strip()

    perspektiv = "Standardvikt_kombination"
    df_index, vikter = berakna_index(huvudmapp, perspektiv=perspektiv, target_year=None)
    
    # Tvätta kommunnamnen så att de alltid matchar oavsett encoding
    df_index['Kommun'] = df_index['Kommun'].apply(fix_text)
    
    def get_data(kommun_namn):
        row = df_index[df_index['Kommun'] == kommun_namn]
        if not row.empty:
            score = round(row['Total_Score'].values[0], 1)
            details_raw = row['Details'].values[0]
            # Säkerställ att details blir en dictionary (dict)
            if isinstance(details_raw, str):
                try: 
                    # Ersätt ev. single quotes med double quotes för JSON
                    details_raw = json.loads(details_raw.replace("'", '"'))
                except: 
                    try: details_raw = ast.literal_eval(details_raw)
                    except: details_raw = {}
            return score, details_raw
        return 0, {}

    lkpg_score, lkpg_details = get_data('Linköping')
    
    coords = {
        'Stockholm': [59.3293, 18.0686], 'Göteborg': [57.7089, 11.9746],
        'Malmö': [55.6049, 13.0038], 'Uppsala': [59.8582, 17.6389],
        'Linköping': [58.4108, 15.6214], 'Västerås': [59.6111, 16.5448],
        'Örebro': [59.2741, 15.2066], 'Helsingborg': [56.0465, 12.6945],
        'Jönköping': [57.7826, 14.1618], 'Norrköping': [58.5877, 16.1924],
        'Umeå': [63.8258, 20.2630], 'Lund': [55.7047, 13.1910]
    }
    
    m = folium.Map(location=[59.0, 15.0], zoom_start=6, tiles='OpenStreetMap')
    
    # Z-index pane
    m.get_root().html.add_child(folium.Element("""
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                var map = Object.values(window).find(val => val && val.createPane);
                if(map) { map.createPane('highlightPane'); map.getPane('highlightPane').style.zIndex = 650; }
            });
        </script>
    """))

    # --- EXTREMT ROBUST SÖKFUNKTION FÖR DETAILS ---
    def get_score_from_details(details_dict, keywords):
        if not isinstance(details_dict, dict): return 0
        
        # Leta efter nyckelord i dictionaryns nycklar
        for key, val in details_dict.items():
            k_lower = str(key).lower()
            if any(kw in k_lower for kw in keywords):
                try:
                    num = float(val)
                    # Begränsa mellan 0 och 200 för att undvika att skalan i diagrammet sprängs
                    return min(max(num, 0), 200)
                except:
                    pass
        return 0

    def generate_chartjs_popup(city_name, city_score, city_details):
        # Exakta etiketter
        short_labels = ["Syss.grad", "Utbildning", "Bef.förändr.", "BRP"]
        labels_js = json.dumps(short_labels)
        
        # Hämta index-poängen via robusta och prioriterade sökord
        # Vi lägger in de exakta Excel-namnen först för att garantera rätt träff
        city_data = [
            get_score_from_details(city_details, ['sysselsättningsgrad', 'sysselsatt', 'sysselsätt']),
            get_score_from_details(city_details, ['lång_eftergymnasial', 'eftergymnasial', 'utbildning']),
            get_score_from_details(city_details, ['folkmängd', 'befolkning', 'förändring']),
            get_score_from_details(city_details, ['brp'])
        ]
        
        lkpg_data = [
            get_score_from_details(lkpg_details, ['sysselsättningsgrad', 'sysselsatt', 'sysselsätt']),
            get_score_from_details(lkpg_details, ['lång_eftergymnasial', 'eftergymnasial', 'utbildning']),
            get_score_from_details(lkpg_details, ['folkmängd', 'befolkning', 'förändring']),
            get_score_from_details(lkpg_details, ['brp'])
        ]
        
        city_data_js = json.dumps(city_data)
        lkpg_data_js = json.dumps(lkpg_data)
        
        diff = round(city_score - lkpg_score, 1)
        diff_color = "green" if diff > 0 else ("red" if diff < 0 else "gray")
        diff_sign = "+" if diff > 0 else ""
        
        html = f"""
        <!DOCTYPE html><html><head>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; margin: 0; padding: 10px; }}
                h3 {{ margin: 0 0 5px 0; color: #333; font-size: 16px; border-bottom: 2px solid #0056b3; padding-bottom: 5px; }}
                .score {{ font-size: 14px; font-weight: bold; margin-bottom: 10px; color: #444; }}
                .chart-container {{ position: relative; height: 180px; width: 100%; }}
            </style>
        </head><body>
            <h3>{city_name}</h3>
            <div class="score">
                Index: {city_score} 
                <span style="color:{diff_color}; font-size:12px;">({diff_sign}{diff} vs Lkpg)</span>
            </div>
            <div class="chart-container"><canvas id="chart_{city_name.replace(' ', '_')}"></canvas></div>
            <script>
                new Chart(document.getElementById('chart_{city_name.replace(' ', '_')}').getContext('2d'), {{
                    type: 'bar',
                    data: {{
                        labels: {labels_js},
                        datasets: [
                            {{ label: '{city_name}', data: {city_data_js}, backgroundColor: 'rgba(54, 162, 235, 0.8)' }},
                            {{ label: 'Linköping', data: {lkpg_data_js}, backgroundColor: 'rgba(54, 54, 54, 0.7)' }}
                        ]
                    }},
                    options: {{
                        responsive: true, maintainAspectRatio: false,
                        scales: {{ y: {{ beginAtZero: true, suggestedMax: 150, title: {{display: true, text: 'Indexpoäng (Relativt)'}} }} }},
                        plugins: {{ legend: {{ position: 'bottom', labels: {{ boxWidth: 10, font: {{size: 10}} }} }} }}
                    }}
                }});
            </script>
        </body></html>
        """
        return html

    for city, coord in coords.items():
        city_score, city_details = get_data(city)
        if city_score == 0: continue
            
        chart_html = generate_chartjs_popup(city, city_score, city_details)
        iframe = folium.IFrame(html=chart_html, width=380, height=290)
        popup = folium.Popup(iframe, max_width=380)
        
        # FÄRGKODNING OCH IKONER
        if city == 'Linköping':
            icon = folium.Icon(color='blue', icon='star', prefix='fa')
            tt = f"<b>{city}</b> - Primär referens (Index: {city_score})"
        else:
            diff = round(city_score - lkpg_score, 1)
            if diff > 0:
                marker_color = 'green'
                diff_text = f"Bättre än Lkpg (+{diff})"
                icon_symbol = 'arrow-up'
            else:
                marker_color = 'orange'
                diff_text = f"Sämre än Lkpg ({diff})"
                icon_symbol = 'arrow-down'
                
            icon = folium.Icon(color=marker_color, icon=icon_symbol, prefix='fa')
            tt = f"<b>{city}</b> (Index: {city_score})<br><i>{diff_text}</i>"
            
        folium.Marker(location=coord, popup=popup, tooltip=tt, icon=icon).add_to(m)

    # --- MASTER CONFIG V2.1: RESPONSIVT UI ---
    visnings_namn = perspektiv.replace('Standardvikt_', 'Index: ').replace('_', ' ').title()
    
    ui_html = f"""
    <style>
        .legend-container {{ position: fixed; bottom: 30px; right: 20px; z-index: 9998; display: flex; flex-direction: column; gap: 10px; pointer-events: none; max-height: 80vh; overflow-y: auto; }}
        .legend {{ position: relative !important; top: auto !important; right: auto !important; bottom: auto !important; pointer-events: auto; background: none; box-shadow: none; padding: 0; margin: 0; border: none; }}
        
        .custom-ui-panel {{ position: fixed; bottom: 60px; left: 50px; z-index: 9999; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 280px; max-height: 80vh; overflow-y: auto; font-family: 'Segoe UI', sans-serif; }}
        
        .panel-title {{ font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #ccc; padding-bottom: 5px; color: #333; font-size: 14px; }}
        .lkpg-stat {{ font-size: 14px; color: #0056b3; font-weight: bold; margin-bottom: 5px; }}
        .ui-text {{ font-size: 12px; color: #555; margin-bottom: 12px; line-height: 1.4; }}
        .ui-legend {{ font-size: 11px; color: #444; line-height: 1.5; }}

        @media (min-width: 1400px) {{
            .custom-ui-panel {{ width: 340px; padding: 20px; bottom: 80px; left: 80px; }}
            .panel-title {{ font-size: 18px; margin-bottom: 15px; }}
            .lkpg-stat {{ font-size: 18px; margin-bottom: 10px; }}
            .ui-text {{ font-size: 15px; margin-bottom: 18px; }}
            .ui-legend {{ font-size: 14px; line-height: 1.7; }}
        }}

        @media (max-width: 768px) {{
            .custom-ui-panel {{ bottom: 10px; left: 10px; width: 220px; padding: 10px; }}
            .legend-container {{ bottom: 10px; right: 10px; transform: scale(0.85); transform-origin: bottom right; }}
        }}
    </style>

    <div class="legend-container" id="legend-container"></div>

    <div class="custom-ui-panel">
        <div class="panel-title">Geografisk Analys</div>
        
        <div class="ui-text">
            <b>Aktivt mätetal:</b><br>{visnings_namn}
        </div>
        
        <div class="lkpg-stat">⭐ Linköping Index: {lkpg_score}</div>
        
        <hr style="border: 0; border-top: 1px solid #eee; margin: 10px 0;">
        <div class="ui-legend">
            🔵 <b>Blå stjärna</b> = Linköping (Referens)<br>
            🟢 <b>Grön pil</b> = Presterar bättre än Lkpg<br>
            🟠 <b>Orange pil</b> = Presterar sämre än Lkpg
        </div>
    </div>

    <script>
        window.addEventListener('load', function() {{
            var container = document.getElementById('legend-container');
            var legends = document.querySelectorAll('.legend');
            legends.forEach(function(leg) {{ container.appendChild(leg); }});
        }});
    </script>
    """
    m.get_root().html.add_child(folium.Element(ui_html))

    out_path = os.path.join(huvudmapp, 'konkurrenskraft_dashboard.html')
    m.save(out_path)
    print(f"🎉 Klar! Dashboard skapad: {out_path}")

# ==========================================
# DEL 5: DATADRIVEN KLUSTERANALYS (Originalberäkning + Strategisk Låsning)
# ==========================================
def generera_klusteranalys(huvudmapp, target_year=None):
    print("\n🤖 Startar datadriven klusteranalys (Matematik från igår + Låsta kluster)...")
    
    import os
    import pandas as pd
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA

    # 1. Läs den ursprungliga källfilen precis som igår
    data_path = os.path.join(huvudmapp, "konkurrens_data.csv")
    if not os.path.exists(data_path):
        print("⚠️ Hittade inte konkurrens_data.csv för klusteranalys.")
        return

    df = pd.read_csv(data_path, sep=';', encoding='utf-8-sig')
    
    target_cities = ['Stockholm', 'Göteborg', 'Malmö', 'Uppsala', 'Linköping', 
                     'Västerås', 'Örebro', 'Helsingborg', 'Jönköping', 'Norrköping', 
                     'Umeå', 'Lund']
    
    df['År'] = pd.to_numeric(df['År'], errors='coerce')
    
    # 2. Inkludera 2025 (vi filtrerar INTE bort något här, för att återskapa igårdagens matematik)
    if target_year is None:
        target_year = df['År'].max()
        
    df_year = df[(df['År'] == target_year) & (df['Kommun'].isin(target_cities))].copy()

    pivot_df = df_year.pivot(index='Kommun', columns='Indikator', values='Värde')
    pop_data = pivot_df['Folkmängd'].copy() if 'Folkmängd' in pivot_df.columns else None
    
    # 3. MATEMATIKEN FRÅN IGÅR: Denna per-capita omräkning är vad som håller 
    # Stockholm i schack så att plupparna stannar där de ska vara!
    for col in pivot_df.columns:
        if col != 'Folkmängd' and pd.api.types.is_numeric_dtype(pivot_df[col]) and pivot_df[col].mean() > 1000:
            if pop_data is not None:
                pivot_df[col] = (pivot_df[col] / pop_data) * 100000

    pivot_df = pivot_df.fillna(pivot_df.mean())
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(pivot_df)
    
    # 4. K-MEANS FRÅN IGÅR
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    pivot_df['Kluster_ID'] = kmeans.fit_predict(X_scaled)
    
    # ==========================================
    # 💡 STRATEGISK LÅSNING MED URSPRUNGLIGA NAMN
    # ==========================================
    # Vi använder EXAKT samma textsträngar som igår (utan emojis). 
    # Detta är nyckeln för att Dashboardens JavaScript ska hitta färgerna!
    def force_strategic_name(city_name):
        if city_name in ['Stockholm', 'Göteborg', 'Malmö']:
            return "Metropolerna (Giganterna)"
        elif city_name in ['Linköping', 'Lund', 'Uppsala', 'Umeå']:
            return "Kunskapsmotorerna (HCI-drivna)"
        else:
            return "Industri & Logistiknoder"

    # Skriv över det K-Means tyckte och tvinga städerna till rätt grupp
    pivot_df['Klusternamn'] = [force_strategic_name(city) for city in pivot_df.index]
    
    # 5. PCA (Ritar ut prickarna med perfekt avstånd exakt som igår)
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_scaled)
    pivot_df['PCA_X'] = X_pca[:, 0]
    pivot_df['PCA_Y'] = X_pca[:, 1]
    
    export_df = pivot_df[['Klusternamn', 'PCA_X', 'PCA_Y']].reset_index()
    export_path = os.path.join(huvudmapp, "konkurrens_clusters.csv")
    export_df.to_csv(export_path, sep=';', index=False, encoding='utf-8-sig')
    
    print(f"✅ Klusteranalys (Matematik återställd & färger räddade) exporterad till: {export_path}")

    # ==========================================
# DEL 6 & 7: MACHINE LEARNING - DRIVKRAFTER & SCENARIOMODELL
# ==========================================

# --- HJÄLPFUNKTION FÖR ATT BERÄKNA ÄKTA INDEX (Riket = 100) ---
def skapa_akta_index(pivot_df):
    import pandas as pd
    index_df = pd.DataFrame(index=pivot_df.index)
    
    for col in pivot_df.columns:
        riket_val = pivot_df.loc['Riket', col] if 'Riket' in pivot_df.index else pivot_df[col].mean()
        if riket_val == 0: riket_val = 0.001
        
        col_lower = col.lower()
        kvot = pivot_df[col] / riket_val
        
        # Samma skottsäkra logik som i JavaScript-dashboarden!
        if 'arbetslöshet' in col_lower or 'syssgrad_kvinnor-män' in col_lower:
            index_df[col] = (2.0 - kvot) * 100 # Inverterad (låg är bra)
        elif 'förändring' in col_lower:
            index_df[col] = 100 + ((pivot_df[col] - riket_val) * 0.1) # Differens för deltan
        elif 'nettopendling' in col_lower or 'nettoflyttning' in col_lower or 'inflyttning' in col_lower:
            index_df[col] = (1.0 + (pivot_df[col] / abs(riket_val))) * 100 # Nettovärden
        else:
            index_df[col] = kvot * 100 # Standard absolutvolym
            
        index_df[col] = index_df[col].clip(0, 250) # Håll poängen inom ramarna
        
    return index_df

    # ==========================================
# DEL 6: MACHINE LEARNING - FEATURE IMPORTANCE (RANDOM FOREST)
# ==========================================
def generera_ml_drivkrafter(huvudmapp, target_year=None):
    print("\n🌲 Startar Random Forest analys för att hitta drivkrafter (Feature Importance)...")
    
    import os
    import pandas as pd
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler

    # 💡 Läs från den NYA filen där 'Total BRP' redan är uträknad
    data_path = os.path.join(huvudmapp, "analysplattform_data.csv")
    if not os.path.exists(data_path):
        print("⚠️ Hittade inte analysplattform_data.csv för ML-analys.")
        return

    df = pd.read_csv(data_path, sep=';', encoding='utf-8-sig')
    
    target_cities = ['Stockholm', 'Göteborg', 'Malmö', 'Uppsala', 'Linköping', 
                     'Västerås', 'Örebro', 'Helsingborg', 'Jönköping', 'Norrköping', 
                     'Umeå', 'Lund']
    
    df['År'] = pd.to_numeric(df['År'], errors='coerce')
    
    # 💡 FIX 1: Filtrera bort 2025 för att förhindra nollvarians
    df = df[df['År'] < 2025]

    # Dynamiskt val av det senaste giltiga året (nu 2024)
    if target_year is None:
        target_year = df['År'].max()
        
    df_year = df[(df['År'] == target_year) & (df['Kommun'].isin(target_cities))].copy()

    # Pivotera rådata
    pivot_df = df_year.pivot(index='Kommun', columns='Indikator', values='Värde')
    
    # 💡 FIX 2: Ta bort gamla BRP så vi inte lurar algoritmen
    if 'BRP' in pivot_df.columns and 'Total BRP (Miljarder SEK)' in pivot_df.columns:
        pivot_df = pivot_df.drop(columns=['BRP'])

    pop_data = pivot_df['Folkmängd'].copy() if 'Folkmängd' in pivot_df.columns else None
    
    # Rensa och tvätta volymer
    for col in pivot_df.columns:
        if col != 'Folkmängd' and pd.api.types.is_numeric_dtype(pivot_df[col]) and pivot_df[col].mean() > 1000:
            if pop_data is not None:
                pivot_df[col] = (pivot_df[col] / pop_data) * 100000

    pivot_df = pivot_df.fillna(pivot_df.mean())

    # Skapa listor över vad som ingår i de olika indexen (för att träna modellerna)
    pci_targets = ['Bostadspriser', 'Nettoflyttning_annat_län', 'Bostadsbyggande', 'Födda_1000_vuxna']
    # 💡 FIX 3: Använd den nya BRP-variabeln i ECI
    eci_targets = ['Total BRP (Miljarder SEK)', 'Nettopendling', 'Nettoinkomst_median', 'Förvärvsinkomst_median', 'Nyföretagande']
    hci_targets = ['Lång_eftergymnasial_proc25', 'KIBS', 'Sysselsättningsgrad', 'Långtidsarbetslöshet']
    
    scaler = StandardScaler()
    scaled_df = pd.DataFrame(scaler.fit_transform(pivot_df), columns=pivot_df.columns, index=pivot_df.index)
    
    # Hjälpfunktion för att bygga en stabil RF-modell och extrahera feature importance
    def get_top_drivers(target_cols, all_cols, model_name):
        valid_targets = [c for c in target_cols if c in scaled_df.columns]
        if not valid_targets: return pd.DataFrame()
        
        y = scaled_df[valid_targets].mean(axis=1) 
        
        X_cols = [c for c in all_cols if c not in valid_targets]
       
        # SÄKERHETSSPÄRR: Låt inte Total BRP användas för att förutsäga ECI
        if model_name == 'ECI (Ekonomisk Motor)' and 'Total BRP (Miljarder SEK)' in X_cols:
            X_cols.remove('Total BRP (Miljarder SEK)')
            
        X = pivot_df[X_cols]
        
        rf = RandomForestRegressor(n_estimators=100, random_state=42)
        rf.fit(X, y)
        
        importances = rf.feature_importances_
        importances = (importances / importances.sum()) * 100
        
        results = pd.DataFrame({
            'Target_Index': model_name,
            'Indikator': X_cols,
            'Vikt_Procent': importances
        })
        
        return results.sort_values(by='Vikt_Procent', ascending=False).head(5)

    # Kör maskininlärningen
    results_list = []
    r_pci = get_top_drivers(pci_targets, pivot_df.columns, 'PCI (Platsattraktivitet)')
    r_eci = get_top_drivers(eci_targets, pivot_df.columns, 'ECI (Ekonomisk Motor)')
    r_hci = get_top_drivers(hci_targets, pivot_df.columns, 'HCI (Humankapital)')
    
    if not r_pci.empty: results_list.append(r_pci)
    if not r_eci.empty: results_list.append(r_eci)
    if not r_hci.empty: results_list.append(r_hci)
    
    if results_list:
        final_ml_df = pd.concat(results_list)
        export_path = os.path.join(huvudmapp, "konkurrens_ml_drivers.csv")
        final_ml_df.to_csv(export_path, sep=';', index=False, encoding='utf-8-sig')
        print(f"✅ Random Forest-drivkrafter exporterade till: {export_path}")

# ==========================================
# AUTOMATISK BERÄKNING: TOTAL BRP (Miljarder)
# ==========================================
def addera_total_brp(huvudmapp):
    import os
    import pandas as pd
    
    data_path_in = os.path.join(huvudmapp, "konkurrens_data.csv")
    data_path_out = os.path.join(huvudmapp, "analysplattform_data.csv")
    
    if not os.path.exists(data_path_in):
        print(f"⚠️ Hittade inte källfilen: {data_path_in}")
        return

    df = pd.read_csv(data_path_in, sep=';', encoding='utf-8-sig')
    
    df = df[df['Indikator'] != 'Total BRP (Miljarder SEK)']

    print("📊 Beräknar och lägger till Total BRP (Miljarder SEK)...")
    
    df_brp = df[df['Indikator'] == 'BRP'][['Kommun', 'År', 'Värde']].rename(columns={'Värde': 'brp_val'})
    df_pop = df[df['Indikator'] == 'Folkmängd'][['Kommun', 'År', 'Värde']].rename(columns={'Värde': 'pop_val'})
    
    merged = pd.merge(df_brp, df_pop, on=['Kommun', 'År'])
    
    if df_brp['brp_val'].mean() < 2000:
        merged['Värde'] = (merged['brp_val'] * 1000 * merged['pop_val']) / 1e9
    else:
        merged['Värde'] = (merged['brp_val'] * merged['pop_val']) / 1e9
        
    merged['Indikator'] = 'Total BRP (Miljarder SEK)'
    
    new_rows = merged[['Kommun', 'År', 'Indikator', 'Värde']]
    df_final = pd.concat([df, new_rows], ignore_index=True)
    
    df_final.to_csv(data_path_out, sep=';', index=False, encoding='utf-8-sig')
    print(f"✅ Total BRP beräknad! Ny, ren datafil skapad: analysplattform_data.csv")

# ==========================================
# DEL 7: MULTIPEL REGRESSION (SCENARIO-KALKYLATOR) - DYNAMISKA MODELLER
# ==========================================
def generera_scenario_kalkylator(huvudmapp):
    print("\n🔮 Startar Multipel Regression för Scenario-simulatorn (Dynamiska Modeller 1-5)...")
    import os
    import pandas as pd
    from sklearn.linear_model import LinearRegression # 💡 NYTT: Ridge förhindrar extrema koefficienter / byt till Ridge i stället för LinearRegression om behov uppstår
    from sklearn.preprocessing import StandardScaler

    data_path = os.path.join(huvudmapp, "analysplattform_data.csv")
    drivers_path = os.path.join(huvudmapp, "konkurrens_ml_drivers.csv")
    
    if not os.path.exists(data_path) or not os.path.exists(drivers_path):
        return

    df = pd.read_csv(data_path, sep=';', encoding='utf-8-sig')
    drivers_df = pd.read_csv(drivers_path, sep=';', encoding='utf-8-sig')
    
    target_cities = ['Stockholm', 'Göteborg', 'Malmö', 'Uppsala', 'Linköping', 
                     'Västerås', 'Örebro', 'Helsingborg', 'Jönköping', 'Norrköping', 
                     'Umeå', 'Lund']
    
    df['År'] = pd.to_numeric(df['År'], errors='coerce')
    df_target = df[df['Kommun'].isin(target_cities)].copy()
    
    df_target = df_target[df_target['År'] < 2025] # Filtrera bort 2025
    
    df_target = df_target.dropna(subset=['Värde'])
    latest_data = df_target.sort_values('År').groupby(['Kommun', 'Indikator']).tail(1)
    
    pivot_df = latest_data.pivot(index='Kommun', columns='Indikator', values='Värde')
    
    if 'BRP' in pivot_df.columns and 'Total BRP (Miljarder SEK)' in pivot_df.columns:
        pivot_df = pivot_df.drop(columns=['BRP'])
        
    pop_data = pivot_df['Folkmängd'].copy() if 'Folkmängd' in pivot_df.columns else None
    
    for col in pivot_df.columns:
        if col != 'Folkmängd' and pd.api.types.is_numeric_dtype(pivot_df[col]) and pivot_df[col].mean() > 1000:
            if pop_data is not None:
                pivot_df[col] = (pivot_df[col] / pop_data) * 100000
    
    pivot_df = pivot_df.fillna(pivot_df.mean()).fillna(0)

    pci_targets = ['Bostadspriser', 'Nettoflyttning_annat_län', 'Bostadsbyggande', 'Födda_1000_vuxna']
    eci_targets = ['Total BRP (Miljarder SEK)', 'Nettopendling', 'Nettoinkomst_median', 'Förvärvsinkomst_median', 'Nyföretagande']
    hci_targets = ['Lång_eftergymnasial_proc25', 'KIBS', 'Sysselsättningsgrad', 'Långtidsarbetslöshet']
    
    target_mappings = {
        'PCI (Platsattraktivitet)': pci_targets,
        'ECI (Ekonomisk Motor)': eci_targets,
        'HCI (Humankapital)': hci_targets
    }

    scaler = StandardScaler()
    scaled_df = pd.DataFrame(scaler.fit_transform(pivot_df), columns=pivot_df.columns, index=pivot_df.index)

    scenario_results = []

    for index_name, target_cols in target_mappings.items():
        valid_targets = [c for c in target_cols if c in scaled_df.columns]
        if not valid_targets: continue
        
        # Sanna indexpoängen för alla städer (snitt 100)
        y = (scaled_df[valid_targets].mean(axis=1) * 15) + 100
        
        top_drivers = drivers_df[drivers_df['Target_Index'] == index_name].head(5)['Indikator'].tolist()
        active_drivers = [d for d in top_drivers if pd.notna(d) and d in pivot_df.columns]
        
        for num_vars in range(1, len(active_drivers) + 1):
            current_features = active_drivers[:num_vars]
            X = pivot_df[current_features]
            
            # 💡 Använder Ridge för att stabilisera modellen (används inte längre)
            # model = Ridge(alpha=1.0)
            model = LinearRegression()
            model.fit(X, y)
            r2 = model.score(X, y)
            
            lkpg_vals = X.loc['Linköping'] if 'Linköping' in X.index else X.mean()
            true_lkpg_y = y['Linköping'] if 'Linköping' in y.index else model.predict([lkpg_vals])[0]

            # 💡 MATEMATISKT ANKARE: Tvingar interceptet att börja EXAKT på Linköpings sanna värde
            # Ekvation: Intercept = Y - (Summan av (Koefficient * Värde))
            anchored_intercept = true_lkpg_y - (model.coef_ * lkpg_vals).sum()

            res = {
                'Target_Index': index_name,
                'Model_Size': num_vars,
                'R2': r2, 
                'Intercept': anchored_intercept, # UI får det förankrade startvärdet
                'Lkpg_Baseline_Score': true_lkpg_y # UI får den absolut sanna baslinjen
            }
            
            for i in range(5):
                if i < num_vars:
                    res[f'Driver{i+1}'] = current_features[i]
                    res[f'Coef{i+1}'] = model.coef_[i]
                    res[f'Lkpg_Val{i+1}'] = lkpg_vals[i]
                else:
                    res[f'Driver{i+1}'] = None
                    res[f'Coef{i+1}'] = 0
                    res[f'Lkpg_Val{i+1}'] = 0

            scenario_results.append(res)

    export_df = pd.DataFrame(scenario_results)
    export_path = os.path.join(huvudmapp, "konkurrens_scenario_coefs.csv")
    export_df.to_csv(export_path, sep=';', index=False, encoding='utf-8-sig')
    print(f"✅ Multipel regression (Dynamiska modeller) exporterad till: {export_path}")

    # ==========================================
# DEL 8: SPATIAL EKONOMETRI (GRAVITY MODEL)
# ==========================================
def generera_gravity_analys(huvudmapp):
    import os
    import pandas as pd

    data_path = os.path.join(huvudmapp, "analysplattform_data.csv")
    if not os.path.exists(data_path):
        return

    print("\n🌍 Startar Spatial Ekonometri (Tyngdkraftsmodell för Linköping)...")
    
    df = pd.read_csv(data_path, sep=';', encoding='utf-8-sig')
    
    # Hämta det senaste BRP-värdet per kommun
    df_brp = df[df['Indikator'] == 'Total BRP (Miljarder SEK)'].dropna(subset=['Värde'])
    latest_brp = df_brp.sort_values('År').groupby('Kommun').tail(1).set_index('Kommun')['Värde'].to_dict()
    
    # Beräkna "Övriga Östergötland" om data för hela länet finns
    if 'Östergötlands län' in latest_brp and 'Linköping' in latest_brp and 'Norrköping' in latest_brp:
        omland_brp = latest_brp['Östergötlands län'] - (latest_brp['Linköping'] + latest_brp['Norrköping'])
        latest_brp['Övriga Östergötland'] = omland_brp if omland_brp > 0 else 0

    # Restider (Biltid i minuter) från uppladdad tabell
    travel_times_lkpg = {
        'Övriga Östergötland': 40, # Snitt från Mjölby, Motala, Finspång etc.
        'Norrköping': 35,
        'Jönköping': 85,
        'Örebro': 90,
        'Västerås': 135,
        'Stockholm': 135,
        'Göteborg': 180,
        'Uppsala': 180,
        'Helsingborg': 230,
        'Lund': 255,
        'Malmö': 270
    }

    gravity_results = []
    brp_lkpg = latest_brp.get('Linköping', 0)

    if brp_lkpg > 0:
        for city, tid in travel_times_lkpg.items():
            brp_city = latest_brp.get(city, 0)
            if brp_city > 0:
                # Tyngdkraftsformeln: (Massa 1 * Massa 2) / (Tid ^ 2)
                # Vi multiplicerar med 1000 för att få indexet i en läsbar skala
                gravity_score = ((brp_lkpg * brp_city) / (tid ** 2)) * 1000
                
                gravity_results.append({
                    'Destination': city,
                    'BRP_Miljarder': brp_city,
                    'Restid_Minuter': tid,
                    'Gravity_Index': round(gravity_score, 1)
                })
    
    # Spara resultatet
    df_gravity = pd.DataFrame(gravity_results).sort_values(by='Gravity_Index', ascending=False)
    export_path = os.path.join(huvudmapp, "konkurrens_gravity.csv")
    df_gravity.to_csv(export_path, sep=';', index=False, encoding='utf-8-sig')
    print(f"✅ Tyngdkraftsanalys exporterad till: {export_path}")

# ==========================================
# EXEKVERING
# ==========================================
if __name__ == "__main__":
    mapp = preparera_konkurrensdata()
    if mapp:
        addera_total_brp(mapp)           # <--- NY RAD: Räknar ut BRP-volymerna! / Skapar BRP och bygger analysplattform_data.csv
        skapa_dashboard(mapp)
        generera_klusteranalys(mapp)  # <--- NY KOD: Detta kör klustringen!
        generera_ml_drivkrafter(mapp) # <--- NY RAD: Kör ML-modellen / Nu finns BRP i filen och ML kan använda den!
        generera_scenario_kalkylator(mapp) # <--- NY RAD
        generera_gravity_analys(mapp) # <--- NYTT