import os
import sys
import re

# ==========================================
# 0. MILJÖ-KONTROLL (Fångar fel med Conda-miljön)
# ==========================================
try:
    import requests
    import pandas as pd
    import numpy as np
    import folium
    import geopandas as gpd
    import branca.colormap as cm
except ModuleNotFoundError as e:
    print("\n" + "="*70)
    print(f"[MILJÖ-FEL] Paketet saknas: {e}")
    print("="*70)
    print("Du kör just nu koden med FEL Python-miljö.")
    print(f"Den Python som försöker köra koden ligger här:\n{sys.executable}")
    print("\nGÖR SÅ HÄR FÖR ATT LÖSA DET I VS CODE:")
    print("1. Titta längst ner till höger i VS Code-fönstret.")
    print("2. Klicka på Python-versionen (t.ex. '3.11.x' eller 'Python').")
    print("3. Välj din Conda-miljö ('gis-env') i listan som dyker upp där uppe.")
    print("4. Kör koden igen!")
    print("="*70 + "\n")
    sys.exit(1)

# ==========================================
# 1. GENERELL SETUP (Gyllene Regeln)
# ==========================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
except NameError:
    current_folder = os.getcwd()

# --- MAPPSTRUKTUR ---
# current_folder är "data_pipeline"
parent_folder = os.path.dirname(current_folder) # "Mina_Stat_Formler"
px_folder = os.path.join(current_folder, "px_filer")
kart_folder = os.path.join(parent_folder, "kart_filer") # Parallell mapp
img_folder = os.path.join(parent_folder, "Img") # Parallell mapp för loggor

# Skapa undermappar automatiskt om de inte finns
os.makedirs(px_folder, exist_ok=True)
os.makedirs(kart_folder, exist_ok=True)
os.makedirs(img_folder, exist_ok=True)

# ==========================================
# 2. DATAHANTERING & ENCODING FIX
# ==========================================
encoding_fix = {
    'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
    'Ã©': 'é', 'Ã¨': 'è', 'Ã‰': 'É', "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö"
}

def fix_text(text):
    if not isinstance(text, str): return text
    for bad, good in encoding_fix.items():
        text = text.replace(bad, good)
    return text

# NYCKEL 1: Extraherar sifferkod (t.ex. "111 Centrum" -> "111")
def extract_nyko_code(text):
    match = re.search(r'\b(\d{1,3})\b', str(text))
    if match:
        return match.group(1).zfill(3)
    return None # Returnerar None om inga siffror finns

# NYCKEL 2: Extraherar textnamn (t.ex. "111 Centrum" -> "centrum")
def extract_nyko_name(text):
    if pd.isna(text): return ""
    cleaned = re.sub(r'\d+', '', str(text)) # Ta bort siffror
    cleaned = cleaned.lower()
    cleaned = re.sub(r'[-_/,.]', ' ', cleaned) # Byt ut specialtecken mot mellanslag
    cleaned = re.sub(r'\s+', ' ', cleaned).strip() # Städa dubbla mellanslag
    return cleaned

# ==========================================
# 3. HÄMTA DATA FRÅN SCB API (SJÄLVLÄKANDE)
# ==========================================
def fetch_scb_employment_linkoping():
    print("--- STEG 1: HÄMTAR HISTORISK DATA FRÅN SCB ---")
    url = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0207/AM0207Z/DagSektAldKN"
    
    meta_response = requests.get(url)
    if meta_response.status_code != 200:
        print(f"Kunde inte hämta metadata. HTTP {meta_response.status_code}")
        return None
        
    metadata = meta_response.json()
    query_params = []
    
    for var in metadata.get('variables', []):
        code = var['code']
        if code == 'Region':
            query_params.append({"code": code, "selection": {"filter": "item", "values": ["0580"]}}) # 0580 = Linköping
        elif code == 'Alder':
            vals = var['values']
            if '15-74' in vals: selected = ['15-74']
            elif '16-74' in vals: selected = ['16-74']
            elif 'tot' in [str(v).lower() for v in vals]: selected = [v for v in vals if 'tot' in str(v).lower()]
            else: selected = vals
            query_params.append({"code": code, "selection": {"filter": "item", "values": selected}})
        elif code == 'Kon':
            vals = var['values']
            if '1+2' in vals: selected = ['1+2']
            else: selected = vals
            query_params.append({"code": code, "selection": {"filter": "item", "values": selected}})
        else:
            query_params.append({"code": code, "selection": {"filter": "item", "values": var['values']}})

    query = {"query": query_params, "response": {"format": "json"}}
    response = requests.post(url, json=query)
    
    if response.status_code == 200:
        data = response.json()
        columns = [col['code'] for col in data['columns']]
        
        records = []
        for item in data['data']:
            row_data = item['key'] + item['values']
            row_dict = dict(zip(columns, row_data))
            records.append(row_dict)
            
        df = pd.DataFrame(records)
        
        if 'Tid' in df.columns: df.rename(columns={'Tid': 'År'}, inplace=True)
        value_cols = [c for c in df.columns if c not in ['Region', 'Alder', 'Kon', 'År', 'ArbetsstSekt']]
        if value_cols: df.rename(columns={value_cols[0]: 'Sysselsatta'}, inplace=True)
            
        if 'Sysselsatta' in df.columns:
            df['Sysselsatta'] = pd.to_numeric(df['Sysselsatta'].replace('..', '0'), errors='coerce').fillna(0).astype(int)
        df['År'] = pd.to_numeric(df['År'], errors='coerce')
        
        df_total = df.groupby("År")["Sysselsatta"].sum().reset_index().sort_values(by="År")
        print(f"Data hämtad! Sysselsatta senaste året ({df_total['År'].iloc[-1]}): {df_total['Sysselsatta'].iloc[-1]} st.\n")
        
        csv_output = os.path.join(parent_folder, "sysselsatta_linkoping_historik.csv")
        df_total.to_csv(csv_output, index=False, encoding="utf-8-sig")
        print(f"[INFO] Sparade historisk SCB-data till: {csv_output}")
        
        return df_total
    else:
        print(f"Fel vid API-anrop: HTTP {response.status_code}")
        return None

# ==========================================
# 4. KOMPETENSMODELL (ANALYSVERKTYGET)
# ==========================================
class CompetenceScenarioModel:
    def __init__(self, region_name="Linköping", historical_df=None):
        self.region = region_name
        self.historical_df = historical_df
        self.baseline_growth = 0
        
        self.excel_filename = "branschparametrar.xlsx"
        self.industry_profiles = self._load_or_create_excel()
        
        if "Generell (Snitt)" in self.industry_profiles:
            self.current_industry = "Generell (Snitt)"
        else:
            self.current_industry = list(self.industry_profiles.keys())[0]
            
        self.params = self.industry_profiles[self.current_industry]
        
        if self.historical_df is not None and len(self.historical_df) >= 6:
            recent_data = self.historical_df.tail(6)
            total_growth = recent_data.iloc[-1]['Sysselsatta'] - recent_data.iloc[0]['Sysselsatta']
            years = recent_data.iloc[-1]['År'] - recent_data.iloc[0]['År']
            self.baseline_growth = int(total_growth / years)

    def _load_or_create_excel(self):
        if os.path.exists(self.excel_filename):
            print(f"[INFO] Läser branschprofiler från styrfilen: {self.excel_filename}")
            df = pd.read_excel(self.excel_filename)
            df.set_index("Bransch", inplace=True)
            return df.to_dict(orient="index")
        else:
            print(f"[INFO] Hittade ingen styrfil. Skapar mallen: {self.excel_filename}")
            default_profiles = {
                "IT & Mjukvara (IKT)": {
                    'lokal_examen_per_ar': 600, 'andel_kvar_i_kommunen': 0.35, 'naturlig_pensionsavgång_ar': 150,
                    'inpendling_potential_ar': 50, 'nationell_ledig_pool': 4500, 'linkoping_attraktionskraft': 0.08
                },
                "Försvarsindustri": {
                    'lokal_examen_per_ar': 300, 'andel_kvar_i_kommunen': 0.40, 'naturlig_pensionsavgång_ar': 100,
                    'inpendling_potential_ar': 30, 'nationell_ledig_pool': 2000, 'linkoping_attraktionskraft': 0.15
                },
                "Vård & Omsorg": {
                    'lokal_examen_per_ar': 450, 'andel_kvar_i_kommunen': 0.60, 'naturlig_pensionsavgång_ar': 250,
                    'inpendling_potential_ar': 100, 'nationell_ledig_pool': 8000, 'linkoping_attraktionskraft': 0.03
                },
                "Generell (Snitt)": {
                    'lokal_examen_per_ar': 500, 'andel_kvar_i_kommunen': 0.40, 'naturlig_pensionsavgång_ar': 200,
                    'inpendling_potential_ar': 50, 'nationell_ledig_pool': 5000, 'linkoping_attraktionskraft': 0.05
                }
            }
            df = pd.DataFrame.from_dict(default_profiles, orient="index")
            df.index.name = "Bransch"
            df.reset_index(inplace=True)
            df.to_excel(self.excel_filename, index=False)
            return default_profiles

    def set_industry(self, industry_name):
        if industry_name in self.industry_profiles:
            self.current_industry = industry_name
            self.params = self.industry_profiles[industry_name]
            print(f"\n[INFO] ---> Bytte analysprofil till: {industry_name} <---")
        else:
            print(f"\n[FEL] Branschen '{industry_name}' saknas. Använder nuvarande profil.")

    def simulate_expansion(self, required_new_jobs, years=5, scenario_name="Expansion"):
        print(f"--- SCENARIO: {scenario_name} ---")
        print(f"Bransch: {self.current_industry}")
        print(f"Behov: {required_new_jobs} nya jobb inom {years} år i {self.region}")
        
        lokalt_utbildade = (self.params['lokal_examen_per_ar'] * self.params['andel_kvar_i_kommunen']) * years
        pensionsavgångar = self.params['naturlig_pensionsavgång_ar'] * years
        pendlingstillskott = self.params['inpendling_potential_ar'] * years
        
        lokalt_netto_tillskott = max(0, lokalt_utbildade + pendlingstillskott - pensionsavgångar)
        print(f"Lokal kapacitet (LiU + Pendling - Pension): {int(lokalt_netto_tillskott)} personer")
        
        gap_efter_lokalt = required_new_jobs - lokalt_netto_tillskott
        
        if gap_efter_lokalt <= 0:
            print("Slutsats: Expansionen kan hanteras helt med lokalt överskott och pendling.\n")
            return
            
        print(f"Bristsiffra att fylla med inflyttning: {int(gap_efter_lokalt)} personer")
        
        max_inrikes_flyttning = self.params['nationell_ledig_pool'] * self.params['linkoping_attraktionskraft']
        inrikes_rekryterade = min(gap_efter_lokalt, max_inrikes_flyttning)
        rest_gap = gap_efter_lokalt - inrikes_rekryterade
        
        print(f"Potentiell inrikes inflyttning (Nationell rekrytering): {int(inrikes_rekryterade)} personer")
        
        if rest_gap > 0:
            print(f"VARNING: Expansionen överskrider den nationella tillgången för denna bransch.")
            print(f"Slutsats: Det krävs en internationell arbetskraftsinvandring på minst {int(rest_gap)} personer.\n")
        else:
            print(f"Slutsats: Expansionen kan hanteras inrikes. ({int(inrikes_rekryterade)} inflyttade från övriga Sverige).\n")
            
        data = {
            "Källa": ["Lokal kompetens & Pendling", "Inrikes Inflyttning", "Utrikes Arbetskraftsinv."],
            "Antal": [int(lokalt_netto_tillskott), int(inrikes_rekryterade), int(rest_gap)]
        }
        return pd.DataFrame(data)

# ==========================================
# 5. GEOGRAFISK VISUALISERING (FOLIUM)
# ==========================================
class GeographicVisualizer:
    def __init__(self):
        # Linköpings koordinater för startvy
        self.center_lat = 58.4108
        self.center_lon = 15.6214
        
    def generate_nyko_map(self, geojson_filename="NYKO3v23.geojson", data_filename="FO01.px"):
        print("\n--- STEG 2: GENERERAR FOLIUM-KARTA ÖVER ARBETSPLATSER ---")
        
        geojson_path = os.path.join(kart_folder, geojson_filename)
        data_path = os.path.join(px_folder, data_filename)
        
        m = folium.Map(location=[self.center_lat, self.center_lon], zoom_start=11, tiles="CartoDB positron")
        
        if os.path.exists(geojson_path) and os.path.exists(data_path):
            try:
                # 1. Läs GeoJSON
                gdf = gpd.read_file(geojson_path)
                
                # Sätt upp yta (ifall det behövs senare)
                gdf = gdf.to_crs(epsg=3006)
                gdf['Area_km2'] = gdf.geometry.area / 10**6
                gdf = gdf.to_crs(epsg=4326)
                
                # 2. Läs lokal data (.px)
                print(f"[INFO] Bearbetar {data_filename} med pyaxis...")
                from pyaxis import pyaxis
                px_data = pyaxis.parse(uri=data_path, encoding='ISO-8859-1')
                df_data = px_data['DATA']
                
                # 3. Dynamisk städning av PX-datan
                # Hitta områdes-kolumnen (inkluderar 'stadsdel')
                area_col = next((col for col in df_data.columns if any(x in col.lower() for x in ['område', 'region', 'nyko', 'stadsdel'])), df_data.columns[0])
                time_col = next((col for col in df_data.columns if any(x in col.lower() for x in ['år', 'tid', 'period'])), None)
                val_col = 'DATA' if 'DATA' in df_data.columns else df_data.columns[-1]
                
                # --- EXAKT ÖVERSÄTTNING FRÅN METADATA ---
                # Vi bygger en "Lexikon"-bok som översätter "Askeby" till "651"
                name_to_code_map = {}
                try:
                    meta = px_data['METADATA']
                    print(f"[INFO] Skannar PX-filens metadata efter de dolda sifferkoderna...")
                    for key in meta.keys():
                        if key.startswith('CODES'):
                            codes_list = meta[key]
                            val_key = key.replace('CODES', 'VALUES')
                            if val_key in meta:
                                vals_list = meta[val_key]
                                
                                # Om de av misstag är strängar, gör till listor
                                if isinstance(codes_list, str): codes_list = [codes_list]
                                if isinstance(vals_list, str): vals_list = [vals_list]
                                
                                if len(codes_list) == len(vals_list):
                                    for c, v in zip(codes_list, vals_list):
                                        # Spara allt som gemener för stensäker matchning
                                        name_to_code_map[str(v).strip().lower()] = str(c).strip()
                                        
                    if name_to_code_map:
                        print(f"[INFO] Succé! Extraherade {len(name_to_code_map)} koder.")
                        # Kolla om Askeby och Ryd finns med och skriv ut som bevis:
                        if 'askeby' in name_to_code_map:
                            print(f"       -> Bevis: 'Askeby' översätts till '{name_to_code_map['askeby']}'")
                        if 'ryd' in name_to_code_map:
                            print(f"       -> Bevis: 'Ryd' översätts till '{name_to_code_map['ryd']}'")
                except Exception as e:
                    print(f"[VARNING] Kunde inte läsa koder från PX-metadata: {e}")
                
                df_data[val_col] = df_data[val_col].astype(str)
                df_data[val_col] = df_data[val_col].replace(['..', '.', '-', '–'], '0') 
                df_data[val_col] = df_data[val_col].str.replace(r'\s+', '', regex=True) 
                df_data[val_col] = pd.to_numeric(df_data[val_col], errors='coerce').fillna(0)
                
                if time_col:
                    latest_year = df_data[time_col].max()
                    df_latest = df_data[df_data[time_col] == latest_year].copy()
                    print(f"[INFO] Filtrerar kartan för senaste året i px-filen: {latest_year}")
                else:
                    df_latest = df_data.copy()
                    
                age_col = next((col for col in df_latest.columns if any(x in col.lower() for x in ['ålder', 'alder'])), None)
                if age_col:
                    unique_ages = df_latest[age_col].unique()
                    chosen_age = unique_ages[0]
                    for age in unique_ages:
                        if '16-74' in str(age) or '15-74' in str(age) or 'tot' in str(age).lower():
                            chosen_age = age
                            break
                    df_latest = df_latest[df_latest[age_col] == chosen_age]
                    
                df_grouped = df_latest.groupby(area_col)[val_col].sum().reset_index()
                df_grouped.rename(columns={val_col: 'DATA'}, inplace=True)
                
                # NY SMART MATCHNINGSLOGIK (Använder vårt Lexikon)
                df_grouped['NameKey'] = df_grouped[area_col].apply(extract_nyko_name)
                
                def get_code(val):
                    clean_val = str(val).strip().lower()
                    if clean_val in name_to_code_map:
                        return extract_nyko_code(name_to_code_map[clean_val])
                    return extract_nyko_code(val)
                    
                df_grouped['CodeKey'] = df_grouped[area_col].apply(get_code)
                
                best_match_type = None
                best_geo_col = None
                max_overlap = 0
                
                px_codes = set(df_grouped['CodeKey'].dropna())
                px_names = set([n for n in df_grouped['NameKey'].dropna() if n != ""])
                
                for col in gdf.columns:
                    if col not in ['geometry', 'Area_km2']:
                        geo_codes = set(gdf[col].apply(extract_nyko_code).dropna())
                        geo_names = set([n for n in gdf[col].apply(extract_nyko_name).dropna() if n != ""])
                        
                        # Testa om koder ger en bra matchning
                        if px_codes and geo_codes:
                            overlap_code = len(px_codes.intersection(geo_codes))
                            if overlap_code > max_overlap:
                                max_overlap = overlap_code
                                best_match_type = 'code'
                                best_geo_col = col
                                
                        # Testa om namn ger en bättre matchning (används om koder saknas)
                        if px_names and geo_names:
                            overlap_name = len(px_names.intersection(geo_names))
                            if overlap_name > max_overlap:
                                max_overlap = overlap_name
                                best_match_type = 'name'
                                best_geo_col = col
                                
                print(f"\n[INFO] -- KONTROLL AV MATCHNING --")
                if max_overlap > 0:
                    print(f"Hittade bästa matchning via: {best_match_type.upper()} i kolumnen '{best_geo_col}' i GeoJSON.")
                    print(f"Antal matchande områden: {max_overlap}")
                    
                    if best_match_type == 'code':
                        gdf['MatchKey'] = gdf[best_geo_col].apply(extract_nyko_code)
                        df_grouped['MatchKey'] = df_grouped['CodeKey']
                    else:
                        gdf['MatchKey'] = gdf[best_geo_col].apply(extract_nyko_name)
                        df_grouped['MatchKey'] = df_grouped['NameKey']
                        
                    geo_key_col = best_geo_col
                else:
                    print("[VARNING] Kunde inte hitta någon överlappning mellan PX-fil och Kart-fil!")
                    gdf['MatchKey'] = gdf.index.astype(str)
                    df_grouped['MatchKey'] = "NO_MATCH"
                    geo_key_col = gdf.columns[0]
                    
                print(f"------------------------------------\n")
                
                # 4. Slå ihop geometrin med statistiken
                merged_gdf = gdf.merge(df_grouped, on='MatchKey', how='left')
                merged_gdf['DATA'] = merged_gdf['DATA'].fillna(0).astype(int) # Fyll områden med 0 och gör till heltal
                
                # --- SKAPA SNYGGA KOLUMNER FÖR TOOLTIP (HOVER) ---
                # Leta efter en namngiven kolumn i GeoJSON om PX-filens namn saknas
                geo_name_col = next((col for col in gdf.columns if col.lower() in ['namn', 'name', 'område', 'omrade', 'stadsdel', 'text']), None)
                
                def get_hover_name(row):
                    if pd.notna(row.get(area_col)): return str(row[area_col])
                    if geo_name_col and pd.notna(row.get(geo_name_col)): return str(row[geo_name_col])
                    return "Okänt område"
                    
                def get_hover_code(row):
                    if pd.notna(row.get('CodeKey')): return str(row['CodeKey'])
                    extracted = extract_nyko_code(row.get(geo_key_col, ""))
                    return extracted if extracted else "---"

                merged_gdf['Hover_Namn'] = merged_gdf.apply(get_hover_name, axis=1)
                merged_gdf['Hover_Kod'] = merged_gdf.apply(get_hover_code, axis=1)
                # ------------------------------------------------
                
                # 5. Skapa Färgskala (Colormap)
                vmax_val = merged_gdf['DATA'].max() if merged_gdf['DATA'].max() > 0 else 1
                colormap = cm.LinearColormap(
                    colors=['#ffeda0', '#feb24c', '#f03b20'], 
                    vmin=merged_gdf['DATA'].min(), 
                    vmax=vmax_val,
                    caption='Antal Sysselsatta (Dagbefolkning)'
                )
                
                # 6. Rita ut på kartan med färg och Hover-Tooltips
                folium.GeoJson(
                    merged_gdf,
                    name="Dagbefolkning per NYKO3",
                    style_function=lambda feature: {
                        'fillColor': colormap(feature['properties']['DATA']),
                        'color': 'black',
                        'weight': 1,
                        'fillOpacity': 0.75
                    },
                    tooltip=folium.GeoJsonTooltip(
                        fields=['Hover_Kod', 'Hover_Namn', 'DATA'],
                        aliases=['NYKO-kod:', 'Område:', 'Sysselsatta:'],
                        localize=True, # Sätter snygga tusentalsavskiljare
                        style="background-color: white; color: #333; font-family: arial; font-size: 12px; padding: 10px;"
                    )
                ).add_to(m)
                
                colormap.add_to(m)
                print(f"[INFO] Karta genererad framgångsrikt med geografi och data!")
                
            except ImportError:
                print("[VARNING] 'pyaxis' saknas i din Python-miljö. Kör: pip install pyaxis")
            except Exception as e:
                print(f"[FEL] Vid tolkning av datan: {e}")
        else:
            print(f"[INFO] Lokala filer ({geojson_filename} eller {data_filename}) saknas.")
            print("[INFO] Genererar en responsiv baskarta redo för data-injektion.")
            
            folium.Marker(
                [self.center_lat, self.center_lon], 
                popup=f"Lägg till {geojson_filename} i 'kart_filer' och {data_filename} i 'px_filer'.",
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)

        # --- GYLLENE STANDARDMALL: RESPONSIVT FOLIUM UI ---
        ui_html = f"""
        <style>
            .legend-container {{ position: fixed; bottom: 30px; right: 20px; z-index: 9998; display: flex; flex-direction: column; gap: 10px; pointer-events: none; max-height: 80vh; overflow-y: auto; }}
            .legend {{ position: relative !important; top: auto !important; right: auto !important; bottom: auto !important; pointer-events: auto; background: none; box-shadow: none; padding: 0; margin: 0; border: none; }}
            
            .custom-ui-panel {{ position: fixed; bottom: 50px; left: 50px; z-index: 9999; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 280px; max-height: 80vh; overflow-y: auto; }}
            
            @media (max-width: 768px) {{
                .custom-ui-panel {{ bottom: 10px; left: 10px; width: 220px; padding: 10px; }}
                .custom-ui-panel button {{ font-size: 11px !important; padding: 6px !important; margin-bottom: 5px !important; }}
                .legend-container {{ bottom: 10px; right: 10px; transform: scale(0.85); transform-origin: bottom right; }}
            }}
        </style>

        <div class="legend-container" id="legend-container"></div>

        <div class="custom-ui-panel">
            <img src="Img/Linkopingsloggo.png" alt="Linköping Logotyp" style="max-width: 140px; margin-bottom: 15px; display: block;">
            <div id="ui-buttons-and-sliders">
                <h4 style="margin-top: 0; margin-bottom: 8px; color: #333;">Linköpings Arbetsmarknad</h4>
                <p style="font-size: 12px; margin-bottom: 0; color: #555;">Visar sysselsatta (dagbefolkning) per NYKO3-område.</p>
                <p style="font-size: 11px; margin-bottom: 0; color: #888; margin-top: 4px;">Källa: {data_filename}</p>
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
        
        output_file = os.path.join(parent_folder, "nyko_arbetsplatser_karta.html")
        m.save(output_file)
        print(f"[SUCCÉ] Kartan har sparats som '{output_file}'. Öppna den i din webbläsare!")

# ==========================================
# 6. KÖR PROGRAMMET
# ==========================================
if __name__ == "__main__":
    # 1. Hämta data och kör kompetensmodell
    historisk_data = fetch_scb_employment_linkoping()
    
    if historisk_data is not None:
        model = CompetenceScenarioModel("Linköpings kommun", historical_df=historisk_data)
        
        print("--- HISTORISK TRENDANALYS (HELA ARBETSMARKNADEN) ---")
        print(f"SCB-data visar att Linköping i snitt har växt med {model.baseline_growth} sysselsatta per år (senaste 5 åren).")
        print("Vi använder denna grund för att stresstesta olika specifika branscher nedan.\n")
        
        model.set_industry("IT & Mjukvara (IKT)")
        model.simulate_expansion(required_new_jobs=3000, years=5, scenario_name="IT-Boom i Mjärdevi")
        
    # 2. Generera Geografisk Karta
    visualizer = GeographicVisualizer()
    visualizer.generate_nyko_map(geojson_filename="NYKO3v23.geojson", data_filename="FO01.px")