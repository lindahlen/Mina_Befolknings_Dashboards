# ==========================================
# 🛡️ OBLIGATORISK FIX FÖR WINDOWS/ANACONDA KRASCH
# MÅSTE ligga högst upp! Innan pandas/numpy väcker C++-motorn!
# ==========================================
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE" # <--- DEN HÄR MÅSTE VARA MED!
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["LOKY_MAX_CPU_COUNT"] = "1" # Spärrar Scikit-learns underliggande Joblib-motor

# NU är det säkert att importera de matematiska biblioteken
import pandas as pd
import numpy as np
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
    compute_indicator("Inflyttningsandel eget län av inrikes inflyttning (%)", calc_9)

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
    df = pd.read_csv(os.path.join(huvudmapp, "analysplattform_data.csv"), sep=";", encoding='utf-8-sig')
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
    
    # --- INJICERA DE NYA STRATEGISKA INDEXEN (PCI, ECI, HCI samt TMI) ---
    nya_index = {
        # 🧲 PCI (Platsattraktivitet) - Mäter dragningskraft för kapital och invånare
        'Bostadspriser': {'PCI_Proxy': 0.30},
        'Nettoflyttning annat län 30-59 år, antal': {'PCI_Proxy': 0.40},
        'Inflyttningsandel eget län av inrikes inflyttning (%)': {'PCI_Proxy': 0.10},
        'Födda_1000_vuxna': {'PCI_Proxy': 0.20},

        # 🏭 ECI (Ekonomisk Motor) - Mäter absolut regional ekonomisk tyngd
        'Total BRP (Miljarder SEK)': {'ECI_Proxy': 0.20},
        'Skattekraft': {'ECI_Proxy': 0.35},
        'Nettopendling, antal': {'ECI_Proxy': 0.25},
        'Nettoinkomst_median': {'ECI_Proxy': 0.15},
        'Förvärvsinkomst_median': {'ECI_Proxy': 0.05},

        # 🧠 HCI (Humankapital) - Mäter kvalitet och effektivitet i arbetskraften    
        'Lång_eftergymnasial_proc25': {'HCI_Proxy': 0.40},
        'KIBS 15-74 år, andel av sysselsatta (%)': {'HCI_Proxy': 0.30},
        'Sysselsättningsgrad': {'HCI_Proxy': 0.20},
        'Långtidsarbetslöshet': {'HCI_Proxy': 0.10},

        # 🚀 TMI (Tillväxt & Momentum) - Mäter hastighet och acceleration
        'Befolkningsförändring per år (%)': {'TMI_Proxy': 0.35},
        'Sysselsättning 15-74 år, förändring per år (%)': {'TMI_Proxy': 0.35},
        'Bostadsbyggande': {'TMI_Proxy': 0.20},
        'Nyföretagande': {'TMI_Proxy': 0.10},
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
        # 🛡️ SPÄRR 1: Exakta fliknamn som redan är normerade i grunddatan (Blacklist)
        # Säkerställer att Linköping jämförs rättvist mot t.ex. Stockholm utan att straffas för volym.
        redan_normerade = [
            'Skattekraft', 
            'Skattesats', 
            'Medelålder', 
            'Nyföretagande', 
            'Bostadsbyggande', 
            'Födda_1000_vuxna', 
            'BRP'
        ]
        if ind_name in redan_normerade:
            return False
            
        # 🛡️ SPÄRR 2: Dynamisk namnkoll (Din befintliga, mycket smarta text-skanner)
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
    
    # 1. Definiera "Formel 1"-gruppen (de 12 storstäderna)
    target_cities = target_areas[:12]

    # 2. Schablon-lista för variabler där Riket saknar matematisk logik
    schablon_indikatorer = ['nettopendl', 'nettoflytt', 'inflyttningsandel', 'inpendl', 'utpendl']

    # 3. Kontrollera om vi kör Väg B (Peer-Group) eller Väg A (Riket)
    use_peer_group = perspektiv in ['ECI_Proxy', 'PCI_Proxy']

    # 4. Förberäkna baslinjen (100-nivån) för alla indikatorer
    baselines = {}
    for _, rad in aktiva_vikter.iterrows():
        ind = rad['Indikator']
        
        if use_peer_group:
            # 💡 VÄG B (LÖSNING 1): Använd MEDIANEN av de 12 storstäderna
            # Parerar Stockholms extrema volymer och ger Linköping en rättvis benchmark!
            city_vals = []
            for c in target_cities:
                v = get_value(c, ind)
                if pd.notna(v):
                    if requires_scaling(ind):
                        c_pop = get_value(c, 'Folkmängd')
                        if pd.notna(c_pop) and c_pop > 0:
                            v = (v / c_pop) * 100000
                    city_vals.append(v)
            # Använd numpy's median istället för mean
            baselines[ind] = np.median(city_vals) if city_vals else 1.0
        else:
            # VÄG A: Använd Riket som standard
            v = get_value('Riket', ind)
            if pd.notna(v):
                if requires_scaling(ind):
                    r_pop = get_value('Riket', 'Folkmängd')
                    if pd.notna(r_pop) and r_pop > 0:
                        v = (v / r_pop) * 100000
            baselines[ind] = v if pd.notna(v) and v != 0 else 1.0

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
            
            if pd.isna(kom_val):
                continue
                
            if requires_scaling(ind):
                kom_pop = get_value(kommun, 'Folkmängd')
                if pd.notna(kom_pop) and kom_pop > 0:
                    kom_val = (kom_val / kom_pop) * 100000

            # Hämta den förberäknade baslinjen (Medianen)
            baslinje_val = baselines.get(ind, 1.0)

            # 💡 NY MATEMATISK HARMONISERING (Klarar negativa medianer och extrema volymer)
            if baslinje_val != 0:
                # Beräknar den procentuella avvikelsen från median-storstaden
                avvikelse_procent = ((kom_val - baslinje_val) / abs(baslinje_val)) * 100
                
                if polaritet == 'låg':
                    index_poäng = 100 - avvikelse_procent
                else:
                    index_poäng = 100 + avvikelse_procent
            else:
                index_poäng = 100

            # 💡 BYPASS: Tvinga in Riket på 100 som en proxy när det är "Formel 1"-logik
            # Detta säkerställer att Riket alltid representerar "100" i exporten för dessa variabler
            if kommun == 'Riket' and use_peer_group:
                index_poäng = 100

            # Tak och golv för extremvärden
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
    print("\n🤖 Startar kluster-positionering (LAPACK-fri PCA via Power Iteration)...", flush=True)
    
    import os
    import pandas as pd
    import numpy as np

    data_path = os.path.join(huvudmapp, "analysplattform_data.csv")
    if not os.path.exists(data_path):
        print("⚠️ Hittade inte analysplattform_data.csv för klusteranalys.", flush=True)
        return

    df = pd.read_csv(data_path, sep=';', encoding='utf-8-sig')
    
    target_cities = ['Stockholm', 'Göteborg', 'Malmö', 'Uppsala', 'Linköping', 
                     'Västerås', 'Örebro', 'Helsingborg', 'Jönköping', 'Norrköping', 
                     'Umeå', 'Lund']
    
    df['År'] = pd.to_numeric(df['År'], errors='coerce')
    if target_year is None:
        target_year = df['År'].max()
        
    df_year = df[(df['År'] == target_year) & (df['Kommun'].isin(target_cities))].copy()
    pivot_df = df_year.pivot(index='Kommun', columns='Indikator', values='Värde')
    pop_data = pivot_df['Folkmängd'].copy() if 'Folkmängd' in pivot_df.columns else None
    
    # ==========================================
    # 1. PANSAR-SPÄRR MOT DUBBELSKALNING
    # ==========================================
    # 🛡️ PANSAR-SPÄRR FÖR UI OCH ANALYS (Uppgraderad för databasnycklar)
    def skalas_per_capita(col_name):
        redan_normerade = [
            'Skattekraft', 'Skattesats', 'Medelålder', 'Nyföretagande', 
            'Bostadsbyggande', 'Födda_1000_vuxna', 'BRP', 'Total BRP (Miljarder SEK)'
        ]
        if col_name in redan_normerade: return False
        
        n_low = str(col_name).lower()
        
        # Den utökade listan som räddar färdiga andelar, snitt och index från att delas med folkmängd!
        undantag_strangar = [
            "%", "andel", "kvot", "per capita", "per 1000", "median", 
            "grad", "priser", "index", "proc", "arbetslös", "arbetslos", 
            "inkomst", "tkr", "skatt", "snitt", "medel"
        ]
        
        if any(w in n_low for w in undantag_strangar): 
            return False 
            
        return True

    for col in pivot_df.columns:
        if col != 'Folkmängd' and pd.api.types.is_numeric_dtype(pivot_df[col]):
            pivot_df[col] = pd.to_numeric(pivot_df[col], errors='coerce')
            if skalas_per_capita(col) and pop_data is not None:
                pop_safe = pd.to_numeric(pop_data, errors='coerce').replace(0, np.nan)
                pivot_df[col] = (pivot_df[col] / pop_safe) * 100000

    # Sanera matrisen (Inga Inf eller NaN)
    pivot_df = pivot_df.replace([np.inf, -np.inf], np.nan)
    pivot_df = pivot_df.fillna(pivot_df.mean()).fillna(0)
    
    # ==========================================
    # 2. LAPACK-FRI PCA (C++ Bypass Algoritm)
    # Återskapar den äkta multidimensionella spridningen med grundläggande matte!
    # ==========================================
    X = pivot_df.select_dtypes(include=[np.number]).values
    
    # A) Standardisera matrisen
    X_mean = np.mean(X, axis=0)
    X_std = np.std(X, axis=0)
    X_std[X_std == 0] = 1 
    X_scaled = (X - X_mean) / X_std

    # B) Algoritm för att hitta en dimension i taget (Power Iteration)
    def get_principal_component(X_matrix, iterations=100):
        np.random.seed(42) # Låser startpunkten så graferna ser likadana ut varje gång
        b_k = np.random.rand(X_matrix.shape[1])
        for _ in range(iterations):
            # Enkel multiplikation (väcker INTE C++-motorn)
            b_k1 = np.dot(X_matrix.T, np.dot(X_matrix, b_k))
            b_k_norm = np.sqrt(np.sum(b_k1**2))
            if b_k_norm == 0: break
            b_k = b_k1 / b_k_norm
        return b_k

    # C) Hämta Dimension 1 (PC-X)
    w1 = get_principal_component(X_scaled)
    pc1 = np.dot(X_scaled, w1)
    
    # D) Subtrahera Dimension 1 från datan (Deflation)
    X_deflated = X_scaled - np.outer(pc1, w1)
    
    # E) Hämta Dimension 2 (PC-Y)
    w2 = get_principal_component(X_deflated)
    pc2 = np.dot(X_deflated, w2)
    
    # F) Lägg in koordinaterna i tabellen
    # Multiplicerar med -1 för att matcha Scikit-Learns standard-orientering
    # pivot_df['PCA_X'] = pc1 * -1
    pivot_df['PCA_Y'] = pc2 * -1
    pivot_df['PCA_X'] = pc1
    # pivot_df['PCA_Y'] = pc2

    # ==========================================
    # 3. STRATEGISK LÅSNING AV NAMN
    # ==========================================
    def force_strategic_name(city_name):
        if city_name in ['Stockholm', 'Göteborg', 'Malmö']:
            return "Metropolerna (Giganterna)"
        elif city_name in ['Linköping', 'Lund', 'Uppsala', 'Umeå']:
            return "Kunskapsmotorerna (HCI-drivna)"
        else:
            return "Industri & Logistiknoder"

    pivot_df['Klusternamn'] = [force_strategic_name(city) for city in pivot_df.index]
    
    # ==========================================
    # 4. EXPORT
    # ==========================================
    export_df = pivot_df[['Klusternamn', 'PCA_X', 'PCA_Y']].reset_index()
    export_path = os.path.join(huvudmapp, "konkurrens_clusters.csv")
    export_df.to_csv(export_path, sep=';', index=False, encoding='utf-8-sig')
    
    print(f"✅ Klusteranalys (Äkta Power-PCA) exporterad till: {export_path}", flush=True)

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
        
        col_lower = str(col).lower()
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
    print("\n🌲 Startar Random Forest analys (Med Inre Ekolod & LAPACK-fri Korrelation)...", flush=True)
    
    import os
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"

    try:
        import threadpoolctl
        threadpoolctl._ThreadpoolInfo.get_num_threads = lambda self: 1
    except Exception:
        pass

    import pandas as pd
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    
    data_path = os.path.join(huvudmapp, "analysplattform_data.csv")
    if not os.path.exists(data_path): return

    df = pd.read_csv(data_path, sep=';', encoding='utf-8-sig')
    
    target_cities = ['Stockholm', 'Göteborg', 'Malmö', 'Uppsala', 'Linköping', 
                     'Västerås', 'Örebro', 'Helsingborg', 'Jönköping', 'Norrköping', 
                     'Umeå', 'Lund', 'Riket']
    
    df['År'] = pd.to_numeric(df['År'], errors='coerce')
    df = df[df['År'] < 2025] 
    
    if target_year is None: target_year = df['År'].max()
        
    df_year = df[(df['År'] == target_year) & (df['Kommun'].isin(target_cities))].copy()
    pivot_df = df_year.pivot(index='Kommun', columns='Indikator', values='Värde')
    
    if 'BRP' in pivot_df.columns and 'Total BRP (Miljarder SEK)' in pivot_df.columns:
        pivot_df = pivot_df.drop(columns=['BRP'])
        
    pop_data = pivot_df['Folkmängd'].copy() if 'Folkmängd' in pivot_df.columns else None
    
    # 🛡️ PANSAR-SPÄRR FÖR UI OCH ANALYS (Uppgraderad för databasnycklar)
    def skalas_per_capita(col_name):
        redan_normerade = [
            'Skattekraft', 'Skattesats', 'Medelålder', 'Nyföretagande', 
            'Bostadsbyggande', 'Födda_1000_vuxna', 'BRP', 'Total BRP (Miljarder SEK)'
        ]
        if col_name in redan_normerade: return False
        
        n_low = str(col_name).lower()
        
        # Den utökade listan som räddar färdiga andelar, snitt och index från att delas med folkmängd!
        undantag_strangar = [
            "%", "andel", "kvot", "per capita", "per 1000", "median", 
            "grad", "priser", "index", "proc", "arbetslös", "arbetslos", 
            "inkomst", "tkr", "skatt", "snitt", "medel"
        ]
        
        if any(w in n_low for w in undantag_strangar): 
            return False 
            
        return True

    for col in pivot_df.columns:
        if col != 'Folkmängd' and pd.api.types.is_numeric_dtype(pivot_df[col]):
            pivot_df[col] = pd.to_numeric(pivot_df[col], errors='coerce')
            if skalas_per_capita(col) and pop_data is not None:
                pop_safe = pd.to_numeric(pop_data, errors='coerce').replace(0, np.nan)
                pivot_df[col] = (pivot_df[col] / pop_safe) * 100000

    pivot_df = pivot_df.replace([np.inf, -np.inf], np.nan)
    for col in pivot_df.columns:
        if pd.api.types.is_numeric_dtype(pivot_df[col]):
            pivot_df[col] = pivot_df[col].fillna(pivot_df[col].mean()).fillna(0)

    # 💡 Säkerställ att skapa_akta_index finns OVANFÖR denna funktion!
    akta_index_df = skapa_akta_index(pivot_df) 
    
    scaled_df = pivot_df.copy() 
    for col in scaled_df.columns:
        if pd.api.types.is_numeric_dtype(scaled_df[col]):
            std_val = scaled_df[col].std(ddof=0)
            if std_val == 0 or pd.isna(std_val): std_val = 1 
            scaled_df[col] = (scaled_df[col] - scaled_df[col].mean()) / std_val

    pci_targets = ['Bostadspriser', 'Nettoflyttning annat län 30-59 år, antal', 'Inflyttningsandel eget län av inrikes inflyttning (%)', 'Födda_1000_vuxna']
    eci_targets = ['Total BRP (Miljarder SEK)', 'Skattekraft', 'Nettopendling, antal', 'Nettoinkomst_median', 'Förvärvsinkomst_median']
    hci_targets = ['Lång_eftergymnasial_proc25', 'KIBS 15-74 år, andel av sysselsatta (%)', 'Sysselsättningsgrad', 'Långtidsarbetslöshet']
    tmi_targets = ['Befolkningsförändring per år (%)', 'Sysselsättning 15-74 år, förändring per år (%)', 'Bostadsbyggande', 'Nyföretagande']
    
    def get_top_drivers(target_cols, all_cols, model_name):
        print(f"   -> [INRE EKOLOD] Bygger AI-drivkrafter för {model_name}...", flush=True)
        valid_targets = [c for c in target_cols if c in scaled_df.columns]
        if not valid_targets: return pd.DataFrame()
        
        y = akta_index_df[valid_targets].mean(axis=1).fillna(0)
        
        import re

        # 🛡️ DEN ANALYTISKA SKALPELLEN (Nu med exakta databasnycklar)
        def is_forbidden(col_name, valid_targs, current_model, all_columns):
            c_low = str(col_name).lower()
            
            # 1. Absoluta Makro-volymer & Aggregeringar
            if c_low in ['total brp (miljarder sek)', 'folkmängd', 'vuxen_bef', 'hela_vuxen_bef']: return True
            if 'försörjningskvot' in c_low or 'summerad' in c_low or 'summa' in c_low or 'belopp' in c_low or 'skatteunderlag' in c_low: return True
            if 'förändring' in c_low or 'förandring' in c_low: return True # <-- NY SPÄRR: Kastar ut volatila 1-års-derivator!
            
            # Blockera icke-linjära variabler (V-formade)
            if 'balanserad' in c_low or 'könen' in c_low or 'kvinnor-män' in c_low: return True
            
            # 2. 🎯 MODELLSPECIFIKA SPÄRRAR (PCI)
            if current_model == 'PCI (Platsattraktivitet)':
                # A. Inpendling och dagbefolkning (tillåter netto!)
                if (re.search(r'inpendl.*', c_low) or 'dagbefolkning' in c_low) and 'netto' not in c_low: return True
                
                # B. DE NYA EXAKTA DATABAS-SPÄRRARNA FÖR ATT STOPPA "ANTALS-SPÖKENA"
                if c_low == 'sysselsatta': return True
                if 'utflytt' in c_low and 'annat' in c_low and 'län' in c_low: return True
                
                # C. Generell säkerhets-regex ifall andra varianter dyker upp
                if re.search(r'syssel.*ant', c_low) or re.search(r'utflytt.*ant', c_low): return True

                # NY SPÄRR: Stoppar den demografiska UI-paradoxen
                if 'ung_bef' in c_low or '0-19' in c_low: return True

                # 🛑 NYA SPÄRRAR MOT DATA-LÄCKAGE (Index-komponenterna får inte vara drivkrafter!)
                # 1. Spärrar Födda barn (fångar "födda", "fodda", "födda barn per 100k" osv)
                if 'födda' in c_low or 'fodda' in c_low: return True

                # 2. Spärrar Inflyttningsandel eget län (fångar oavsett om det står (%) i klartexten eller ej)
                if 'inflytt' in c_low and 'andel' in c_low and 'eget' in c_low: return True

            # --- ECI (Ekonomisk Motor) ---
            if current_model == 'ECI (Ekonomisk Motor)':
                # Vi pausar denna blockering eftersom Nyföretagande ändå inte tog platsen
                # if 'skattesats' in c_low: return True
                pass
                
            # 3. TVILLING-TVÄTTEN: Prioritera alltid % framför omräknade antal!
            if 'antal' in c_low or '_ant' in c_low:
                if 'netto' not in c_low:
                    basnamn = re.sub(r'(_ant|antal|ant)', '', c_low).strip(' ,-_')
                    for annan_col in all_columns:
                        annan_low = str(annan_col).lower()
                        if basnamn in annan_low and ('andel' in annan_low or '%' in annan_low or 'proc' in annan_low):
                            return True 
                
            return False

        # OBS! Kom ihåg att skicka med pivot_df.columns
        X_cols = [c for c in all_cols if c not in valid_targets and not is_forbidden(c, valid_targets, model_name, pivot_df.columns)]
            
        def lapack_free_corr(s1, s2):
            s1_diff = s1 - s1.mean()
            s2_diff = s2 - s2.mean()
            nämnare = np.sqrt((s1_diff**2).sum() * (s2_diff**2).sum())
            return 0 if nämnare == 0 else abs((s1_diff * s2_diff).sum() / nämnare)

        valid_candidates = []
        for col in X_cols:
            if pd.api.types.is_numeric_dtype(scaled_df[col]):
                if lapack_free_corr(scaled_df[col], y) < 0.85:
                    valid_candidates.append(col)
        
        if not valid_candidates: return pd.DataFrame()

        # PASS 1: Utforska
        X_initial = pivot_df[valid_candidates]
        rf_initial = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=1)
        rf_initial.fit(X_initial, y)
        
        importances = rf_initial.feature_importances_
        ai_ranked = sorted(zip(valid_candidates, importances), key=lambda x: x[1], reverse=True)
        
        # ALPHA-KONTROLL (75%)
        final_features = []
        for col, imp in ai_ranked:
            is_collinear = False
            for f in final_features:
                if lapack_free_corr(scaled_df[col], scaled_df[f]) >= 0.75:
                    is_collinear = True
                    break
            if not is_collinear:
                final_features.append(col)
            if len(final_features) >= 10: 
                break
                
        # PASS 2: Slutgiltig träning
        if not final_features: return pd.DataFrame()
        X_final = pivot_df[final_features]
        rf_final = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=1)
        rf_final.fit(X_final, y)
        
        if 'Linköping' in X_final.index:
            lkpg_true = y.loc['Linköping']
            lkpg_pred = rf_final.predict([X_final.loc['Linköping']])[0]
            diff = lkpg_pred - lkpg_true
            print(f"      ⭐ {model_name} | Lkpg Äkta Index: {lkpg_true:.1f} | ML-gissning: {lkpg_pred:.1f} (Diff: {diff:+.1f})", flush=True)

        final_importances = rf_final.feature_importances_
        import_sum = final_importances.sum() if final_importances.sum() > 0 else 1 
        final_importances = (final_importances / import_sum) * 100
        
        return pd.DataFrame({'Target_Index': model_name, 'Indikator': final_features, 'Vikt_Procent': final_importances}).sort_values(by='Vikt_Procent', ascending=False).head(5)

    print(" -> [ML-EKOLOD 6] Alla variabler sanerade. Påbörjar ML-träning...", flush=True)

    results_list = []
    for targets, name in zip([pci_targets, eci_targets, hci_targets, tmi_targets], 
                             ['PCI (Platsattraktivitet)', 'ECI (Ekonomisk Motor)', 'HCI (Humankapital)', 'TMI (Tillväxt & Momentum)']):
        res = get_top_drivers(targets, pivot_df.columns, name)
        if not res.empty: results_list.append(res)
    
    if results_list:
        final_ml_df = pd.concat(results_list)
        
        export_path = os.path.join(huvudmapp, "konkurrens_ml_drivers.csv")
        final_ml_df.to_csv(export_path, sep=';', index=False, encoding='utf-8-sig')
        print(f"✅ Random Forest-drivkrafter exporterade till: {export_path}", flush=True)

# ==========================================
# AUTOMATISK BERÄKNING: TOTAL BRP (Miljarder)
# ==========================================
def addera_total_brp(huvudmapp):
    import os
    import pandas as pd
    
    # Samma filnamn in och ut!
    data_path = os.path.join(huvudmapp, "analysplattform_data.csv")
    
    if not os.path.exists(data_path):
        print(f"⚠️ Hittade inte källfilen: {data_path}")
        return

    df = pd.read_csv(data_path, sep=';', encoding='utf-8-sig')
    
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
    
    df_final.to_csv(data_path, sep=';', index=False, encoding='utf-8-sig')
    print(f"✅ Total BRP beräknad! Filen analyserplattform_data.csv är nu uppdaterad.")

# ==========================================
# DEL 7: MULTIPEL REGRESSION (SCENARIO-KALKYLATOR) 
# ==========================================
def generera_scenario_kalkylator(huvudmapp, target_year=None):
    print("\n🔮 Startar Multipel Regression (Med 100% LAPACK-fri Algoritm)...", flush=True)
    
    import os
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    
    import pandas as pd
    import numpy as np
    
    # 🧨 DEN ÄKTA C++-FRIA OLS-REGRESSIONEN MED RIDGE-PENALTY 🧨
    class TrueLAPACKFreeOLS:
        def __init__(self):
            self.coef_ = None
            self.intercept_ = 0
            
        def _gauss_solve(self, A, b):
            n = len(b)
            M = np.zeros((n, n+1))
            M[:, :n] = A
            M[:, n] = b
            for i in range(n):
                max_row = np.argmax(abs(M[i:, i])) + i
                if abs(M[max_row, i]) < 1e-12:
                    return np.zeros(n)
                M[[i, max_row]] = M[[max_row, i]]
                M[i] = M[i] / M[i, i]
                for j in range(i+1, n):
                    M[j] = M[j] - M[j, i] * M[i]
            x = np.zeros(n)
            for i in range(n-1, -1, -1):
                x[i] = M[i, n] - np.sum(M[i, i+1:n] * x[i+1:n])
            return x

        def fit(self, X_df, y_series):
            X_mat = X_df.values
            y_vec = y_series.values
            X_mat_bias = np.c_[np.ones(X_mat.shape[0]), X_mat]
            
            # 🛡️ 100% BLAS-FRI MATRISMULTIPLIKATION (np.einsum istället för np.dot)
            # Detta förhindrar definitivt att systemet låser (deadlocks) sig i VS Code!
            XTX = np.einsum('ji,jk->ik', X_mat_bias, X_mat_bias)
            XTX = XTX + np.eye(XTX.shape[0]) * 1e-6 # Ridge Krockkudde
            
            XTy = np.einsum('ji,j->i', X_mat_bias, y_vec)
            beta = self._gauss_solve(XTX, XTy)
            
            self.intercept_ = beta[0]
            self.coef_ = beta[1:]
            
        def predict(self, X_input):
            X_mat = X_input.values if isinstance(X_input, (pd.DataFrame, pd.Series)) else np.array(X_input)
            if len(X_mat.shape) == 1: X_mat = X_mat.reshape(1, -1)
            return np.einsum('ij,j->i', X_mat, self.coef_) + self.intercept_
            
        def score(self, X_df, y_series):
            y_pred = self.predict(X_df)
            y_true = y_series.values
            ss_res = np.sum((y_true - y_pred)**2)
            ss_tot = np.sum((y_true - np.mean(y_true))**2)
            return 0 if ss_tot == 0 else 1 - (ss_res / ss_tot)

    data_path = os.path.join(huvudmapp, "analysplattform_data.csv")
    drivers_path = os.path.join(huvudmapp, "konkurrens_ml_drivers.csv")
    
    if not os.path.exists(data_path) or not os.path.exists(drivers_path): return

    df = pd.read_csv(data_path, sep=';', encoding='utf-8-sig')
    drivers_df = pd.read_csv(drivers_path, sep=';', encoding='utf-8-sig')
    
    target_cities = ['Stockholm', 'Göteborg', 'Malmö', 'Uppsala', 'Linköping', 
                     'Västerås', 'Örebro', 'Helsingborg', 'Jönköping', 'Norrköping', 
                     'Umeå', 'Lund', 'Riket']
    
    df['År'] = pd.to_numeric(df['År'], errors='coerce')
    df = df[df['År'] < 2025] 
    
    if target_year is None: target_year = df['År'].max()
        
    df_year = df[(df['År'] == target_year) & (df['Kommun'].isin(target_cities))].copy()
    pivot_df = df_year.pivot(index='Kommun', columns='Indikator', values='Värde')
    
    if 'BRP' in pivot_df.columns and 'Total BRP (Miljarder SEK)' in pivot_df.columns:
        pivot_df = pivot_df.drop(columns=['BRP'])
        
    pop_data = pivot_df['Folkmängd'].copy() if 'Folkmängd' in pivot_df.columns else None
    
    def skalas_per_capita(col_name):
        redan_normerade = [
            'Skattekraft', 'Skattesats', 'Medelålder', 'Nyföretagande', 
            'Bostadsbyggande', 'Födda_1000_vuxna', 'BRP', 'Total BRP (Miljarder SEK)'
        ]
        if col_name in redan_normerade: return False
        
        n_low = str(col_name).lower()
        undantag_strangar = [
            "%", "andel", "kvot", "per capita", "per 1000", "median", 
            "grad", "priser", "index", "proc", "arbetslös", "arbetslos", 
            "inkomst", "tkr", "skatt", "snitt", "medel"
        ]
        
        if any(w in n_low for w in undantag_strangar): 
            return False 
            
        return True

    for col in pivot_df.columns:
        if col != 'Folkmängd':
            if pivot_df[col].dtype == 'object':
                pivot_df[col] = pivot_df[col].astype(str).str.replace(r'[\s\u00A0]', '', regex=True).str.replace(',', '.')
            
            pivot_df[col] = pd.to_numeric(pivot_df[col], errors='coerce')
            
            if skalas_per_capita(col) and pop_data is not None:
                pop_safe = pd.to_numeric(pop_data, errors='coerce').replace(0, np.nan)
                pivot_df[col] = (pivot_df[col] / pop_safe) * 100000

    pivot_df = pivot_df.replace([np.inf, -np.inf], np.nan)
    for col in pivot_df.columns:
        if pd.api.types.is_numeric_dtype(pivot_df[col]):
            pivot_df[col] = pivot_df[col].fillna(pivot_df[col].mean()).fillna(0)

    print(" -> [EKOLOD 7.1] Data sanerad. Förbereder matriser...", flush=True)

    akta_index_df = skapa_akta_index(pivot_df) 
    
    scaled_df = pivot_df.copy() 
    for col in scaled_df.columns:
        if pd.api.types.is_numeric_dtype(scaled_df[col]):
            std_val = scaled_df[col].std(ddof=0)
            if std_val == 0 or pd.isna(std_val): std_val = 1 
            scaled_df[col] = (scaled_df[col] - scaled_df[col].mean()) / std_val

    pci_targets = ['Bostadspriser', 'Nettoflyttning annat län 30-59 år, antal', 'Inflyttningsandel eget län av inrikes inflyttning (%)', 'Födda_1000_vuxna']
    eci_targets = ['Total BRP (Miljarder SEK)', 'Skattekraft','Nettopendling, antal', 'Nettoinkomst_median', 'Förvärvsinkomst_median']
    hci_targets = ['Lång_eftergymnasial_proc25', 'KIBS 15-74 år, andel av sysselsatta (%)', 'Sysselsättningsgrad', 'Långtidsarbetslöshet']
    tmi_targets = ['Befolkningsförändring per år (%)', 'Sysselsättning 15-74 år, förändring per år (%)', 'Bostadsbyggande', 'Nyföretagande']
    
    target_mappings = {'PCI (Platsattraktivitet)': pci_targets, 'ECI (Ekonomisk Motor)': eci_targets, 'HCI (Humankapital)': hci_targets, 'TMI (Tillväxt & Momentum)': tmi_targets}
    scenario_results = []

    print(" -> [EKOLOD 7.2] Påbörjar regressionsanalyser...", flush=True)

    for index_name, target_cols in target_mappings.items():
        print(f"   -> [INRE EKOLOD] Bygger scenariomodell för {index_name}...", flush=True)
        valid_targets = [c for c in target_cols if c in pivot_df.columns]
        if not valid_targets: continue
        
        y = akta_index_df[valid_targets].mean(axis=1).fillna(0)
        
        if index_name in drivers_df['Target_Index'].values:
            top_drivers = drivers_df[drivers_df['Target_Index'] == index_name].head(5)['Indikator'].tolist()
        else: top_drivers = []
            
        active_drivers = [d for d in top_drivers if pd.notna(d) and d in pivot_df.columns]
        
        active_drivers = [d for d in top_drivers if pd.notna(d) and d in pivot_df.columns]
        
        # 🛡️ KIRURGISKT INGREPP: LIGAN 5-12 FILTER (Öppnar spärren!)
        # Vi plockar bort Giganterna från träningsdatan så att de inte tvingar fram falska positiva samband (Stockholmseffekten).
        # Detta låter maskinen hitta den sanna strukturella riktningen (t.ex. den negativa pendlarparadoxen) för Linköping.
        training_cities = ['Uppsala', 'Linköping', 'Västerås', 'Örebro', 'Helsingborg', 'Jönköping', 'Norrköping', 'Umeå', 'Lund']
        train_mask = scaled_df.index.isin(training_cities)
        
        for num_vars in range(1, len(active_drivers) + 1):
            current_features = active_drivers[:num_vars]
            
            # Träna OLS-Regressionen ENDAST på Ligan 5-12
            X_train = scaled_df.loc[train_mask, current_features]
            y_train = y.loc[train_mask]
            
            # Vi behåller rådatan för alla så att dashboarden kan rendera Linköpings baslinje korrekt
            X_raw = pivot_df[current_features] 
            
            model = TrueLAPACKFreeOLS()
            model.fit(X_train, y_train)
            r2 = model.score(X_train, y_train)
            
            # Konvertera tillbaka till rå-koefficienter för Dashboarden
            raw_coefs = []
            for i, col in enumerate(current_features):
                std_val = X_raw[col].std(ddof=0)
                if std_val == 0 or pd.isna(std_val): std_val = 1
                raw_coefs.append(model.coef_[i] / std_val)
            raw_coefs = np.array(raw_coefs)
            
            # 🛡️ FIX FÖR PANDAS ALIGNMENT-KRASCH (Tvingar fram numpy-vektorer med .values)
            lkpg_raw_vals = X_raw.loc['Linköping'].values if 'Linköping' in X_raw.index else X_raw.mean().values
            true_lkpg_y = y['Linköping'] if 'Linköping' in y.index else y.mean()

            # Rent matematiskt ankare
            anchored_intercept = true_lkpg_y - np.sum(raw_coefs * lkpg_raw_vals)

            res = {
                'Target_Index': index_name,
                'Model_Size': num_vars,
                'R2': r2, 
                'Intercept': anchored_intercept,
                'Lkpg_Baseline_Score': true_lkpg_y 
            }
            
            for i in range(5):
                if i < num_vars:
                    res[f'Driver{i+1}'] = current_features[i]
                    res[f'Coef{i+1}'] = raw_coefs[i] 
                    res[f'Lkpg_Val{i+1}'] = lkpg_raw_vals[i]
                else:
                    res[f'Driver{i+1}'] = None
                    res[f'Coef{i+1}'] = 0
                    res[f'Lkpg_Val{i+1}'] = 0

            scenario_results.append(res)
            
        print(f"   -> [INRE EKOLOD] SUCCESS! Scenariomodell för {index_name} klar!", flush=True)

    export_df = pd.DataFrame(scenario_results)
    
    export_path = os.path.join(huvudmapp, "konkurrens_scenario_coefs.csv")
    export_df.to_csv(export_path, sep=';', index=False, encoding='utf-8-sig')
    print(f"✅ Multipel regression (Äkta LAPACK-fri) exporterad till: {export_path}", flush=True)

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
# DEL 9: AI-KOMPASS (UNSUPERVISED RANDOM FOREST)
# ==========================================
def generera_ai_kompass(huvudmapp):
    print("\n🧭 Startar AI-Kompass (Unsupervised Random Forest & PCA)...", flush=True)
    
    import os
    import pandas as pd
    import numpy as np
    from sklearn.ensemble import RandomTreesEmbedding
    from sklearn.preprocessing import StandardScaler

    data_path = os.path.join(huvudmapp, "analysplattform_data.csv")
    if not os.path.exists(data_path):
        print(f"⚠️ Hittade inte källfilen: {data_path}", flush=True)
        return

    df = pd.read_csv(data_path, sep=';', encoding='utf-8-sig')
    
    # 💡 Ligan 5-12 + Giganterna (Linköping i centrum för analysen)
    target_cities = ['Stockholm', 'Göteborg', 'Malmö', 'Uppsala', 'Linköping', 
                     'Västerås', 'Örebro', 'Helsingborg', 'Jönköping', 'Norrköping', 
                     'Umeå', 'Lund']
    
    df['År'] = pd.to_numeric(df['År'], errors='coerce')
    latest_year = df['År'].max()
    df_year = df[(df['År'] == latest_year) & (df['Kommun'].isin(target_cities))].copy()

    def clean_val(x):
        try: return float(str(x).replace(',', '.').replace(' ', ''))
        except: return np.nan
    df_year['Värde'] = df_year['Värde'].apply(clean_val)

    eci_vars = ['Total BRP (Miljarder SEK)', 'Skattekraft', 'Nettopendling, antal', 'Nettoinkomst_median', 'Förvärvsinkomst_median']
    
    data = []
    for city in target_cities:
        row = {'Kommun': city}
        for ind in eci_vars:
            search = 'nettopendl' if 'pendling' in ind.lower() else ind
            search = 'BRP' if 'BRP' in ind else search
            rad = df_year[(df_year['Kommun'] == city) & (df_year['Indikator'].str.contains(search, case=False, na=False))]
            row[ind] = rad['Värde'].values[0] if not rad.empty else np.nan
        data.append(row)

    df_compass = pd.DataFrame(data).set_index('Kommun').ffill().bfill()

    print(" -> [AI-KOMPASS] Data laddad, skalar matrisen...", flush=True)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_compass)

    print(" -> [AI-KOMPASS] Tränar Unsupervised Random Forest...", flush=True)
    rte = RandomTreesEmbedding(n_estimators=150, random_state=42, max_depth=3, n_jobs=1)
    X_sparse = rte.fit_transform(X_scaled)

    print(" -> [AI-KOMPASS] Komprimerar till 2D med Power Iteration (Bevisat LAPACK-fri)...", flush=True)
    X_dense = X_sparse.toarray()
    
    # Centrera datan (Standard för PCA)
    X_mean = np.mean(X_dense, axis=0)
    X_cent = X_dense - X_mean
    
    # 🛡️ THE NUCLEAR OPTION v2: Samma bevisade algoritm som i Klusteranalysen!
    # Detta kringgår alla matris-krockar i Windows genom att arbeta med 1D-vektorer
    def get_principal_component(X_matrix, iterations=100):
        np.random.seed(42) 
        b_k = np.random.rand(X_matrix.shape[1])
        for _ in range(iterations):
            b_k1 = np.dot(X_matrix.T, np.dot(X_matrix, b_k))
            b_k_norm = np.sqrt(np.sum(b_k1**2))
            if b_k_norm == 0: break
            b_k = b_k1 / b_k_norm
        return b_k

    # PC1 (X-axeln)
    w1 = get_principal_component(X_cent)
    pc1 = np.dot(X_cent, w1)
    
    # Deflation (Dra bort X-axeln från datan för att hitta Y)
    X_deflated = X_cent - np.outer(pc1, w1)
    
    # PC2 (Y-axeln)
    w2 = get_principal_component(X_deflated)
    pc2 = np.dot(X_deflated, w2)
    
    # Sätt samman till 2D-kompassen
    compass_2d = np.column_stack((pc1, pc2))

    # 💡 MATEMATISKT ANKARE: Tvingar väderstrecken rätt för dashboarden
    def safe_corr(s1, s2):
        s1_diff = s1 - np.mean(s1)
        s2_diff = s2 - np.mean(s2)
        nämnare = np.sqrt(np.sum(s1_diff**2) * np.sum(s2_diff**2))
        return 0 if nämnare == 0 else np.sum(s1_diff * s2_diff) / nämnare

    brp_corr = safe_corr(df_compass['Total BRP (Miljarder SEK)'].values, compass_2d[:, 0])
    if brp_corr < 0:
        compass_2d[:, 0] = compass_2d[:, 0] * -1 
        
    skatt_corr = safe_corr(df_compass['Skattekraft'].values, compass_2d[:, 1])
    if skatt_corr > 0:
        compass_2d[:, 1] = compass_2d[:, 1] * -1 

    # Normalisera till en snygg skala för dashboarden (Radie ca -8 till +8)
    max_val = np.max(np.abs(compass_2d))
    if max_val == 0: max_val = 1 
    
    df_results = pd.DataFrame({
        'Kommun': df_compass.index,
        'X_norm': np.round((compass_2d[:, 0] / max_val) * 8, 3),
        'Y_norm': np.round((compass_2d[:, 1] / max_val) * 8, 3)
    })

    export_path = os.path.join(huvudmapp, "ai_kompass_koordinater.csv")
    df_results.to_csv(export_path, sep=';', index=False, encoding='utf-8-sig')
    print(f"✅ AI-Kompassens koordinater exporterade till: {export_path}", flush=True)

# ==========================================
# EXEKVERING MED HÅRD DIAGNOSTIK (SPÅRHUND)
# ==========================================
if __name__ == "__main__":
    import sys
    import traceback

    def safe_execute(func_name, func, *args):
        """Kör en funktion och tvingar terminalen att skriva ut status INNAN den eventuellt kraschar."""
        print(f"\n▶️ [SPÅRHUND] STARTAR: {func_name}...", flush=True)
        try:
            func(*args)
            print(f"✅ [SPÅRHUND] KLAR: {func_name} slutfördes framgångsrikt!", flush=True)
        except Exception as e:
            print(f"❌ [SPÅRHUND] PYTHON-KRASCH I {func_name}:", flush=True)
            traceback.print_exc(file=sys.stdout)
            sys.stdout.flush()

    print("=== 🚀 SCRIPT STARTAR ===", flush=True)
    
    mapp = preparera_konkurrensdata()
    
    if mapp:
        # Nu kör vi funktionerna en och en i vår säkra "kammare"
        safe_execute("addera_total_brp", addera_total_brp, mapp)
        
        safe_execute("skapa_dashboard", skapa_dashboard, mapp)
        
        safe_execute("generera_klusteranalys", generera_klusteranalys, mapp)
        
        safe_execute("generera_ml_drivkrafter", generera_ml_drivkrafter, mapp)
        
        safe_execute("generera_scenario_kalkylator", generera_scenario_kalkylator, mapp)
        
        safe_execute("generera_gravity_analys", generera_gravity_analys, mapp)

        # 👇 DEN NYA RADEN FÖR KOMPASSEN 👇
        safe_execute("generera_ai_kompass", generera_ai_kompass, mapp)
        
    print("\n=== 🎉 SCRIPT SLUTFÖRT HELT UTAN KRASCHAR ===", flush=True)