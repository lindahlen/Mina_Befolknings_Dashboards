import os
import sys
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MiniMap
import json
import math
import numpy as np
import traceback
import datetime

print("Startar kartgenerering...")

# =====================================================================
# 0. ANPASSAD JSON ENCODER (Löser "Timestamp is not JSON serializable")
# =====================================================================
class NumpyPandasEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (pd.Timestamp, datetime.date, datetime.datetime)):
            return str(obj)
        return super(NumpyPandasEncoder, self).default(obj)

# =====================================================================
# 1. SKOTTSÄKER SETUP & MAPPSTRUKTUR
# =====================================================================
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = os.getcwd()

if os.path.basename(script_dir) == "data_pipeline":
    moder_mapp = os.path.dirname(script_dir)
else:
    moder_mapp = script_dir

kart_filer_dir = os.path.join(moder_mapp, 'kart_filer')
excel_filer_dir = os.path.join(moder_mapp, 'excel_filer')

print(f"✅ Modermapp identifierad: {moder_mapp}")

# --- FILNAMN FÖR VALKARTAN ---
GEOJSON_VAL_FILENAME = 'Valkarta2022.geojson'
OUT_HTML_NAME = 'Valdeltagande_2022.html'

encoding_fix = {
    'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
    'Ã©': 'é', 'Ã¨': 'è', 'Ã‰': 'É', "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö"
}

def fix_text(text):
    if not isinstance(text, str): return text
    for bad, good in encoding_fix.items():
        text = text.replace(bad, good)
    return text

def normalize_id(val):
    if pd.isna(val): return None
    if isinstance(val, float) and val.is_integer():
        val = int(val)
    s = str(val).replace('-', '').replace(' ', '').strip()
    
    if s.startswith('580'):
        s = '0' + s
    elif len(s) == 7 and not s.startswith('0'): 
        s = '0' + s
        
    return s

def safe_str(val, default='Information saknas'):
    if pd.isna(val): return default
    return str(val).strip()

def safe_num(val, default=0):
    try:
        if pd.isna(val): return default
        if isinstance(val, str):
            # Tvätta bort mellanslag (tusentalsavskiljare) och byt kommatecken mot punkt
            val = val.replace(' ', '').replace('\xa0', '').replace(',', '.')
        return float(val)
    except:
        return default

try:
    # =====================================================================
    # 2. LÄS IN GEOGRAFI OCH INFRASTRUKTUR
    # =====================================================================
    print("\nLaddar geografi...")

    valdistrikt_path = os.path.join(kart_filer_dir, GEOJSON_VAL_FILENAME)
    if os.path.exists(valdistrikt_path):
        valdistrikt_gdf = gpd.read_file(valdistrikt_path)
        if 'NAMN' in valdistrikt_gdf.columns:
            valdistrikt_gdf['NAMN'] = valdistrikt_gdf['NAMN'].apply(fix_text)
            
        geo_id_col = next((col for col in ['LKFV', 'lkfv', 'id', 'KOD', 'VALDISTRIKTSKOD'] if col in valdistrikt_gdf.columns), None)
        if geo_id_col:
            valdistrikt_gdf['MATCH_ID'] = valdistrikt_gdf[geo_id_col].apply(normalize_id)
        else:
            valdistrikt_gdf['MATCH_ID'] = valdistrikt_gdf.index.astype(str)
        print(f"✅ Valdistrikt inladdade ({len(valdistrikt_gdf)} st).")
    else:
        print(f"\n❌ KRITISKT FEL: Hittade inte '{GEOJSON_VAL_FILENAME}'!")
        valdistrikt_gdf = gpd.GeoDataFrame(columns=['NAMN', 'geometry', 'MATCH_ID'], geometry='geometry', crs="EPSG:4326")

    # --- LÄS IN EXTRA GEOGRAFI (Transportleder och Vattendrag) ---
    transport_path = os.path.join(kart_filer_dir, 'transportleder.geojson')
    if os.path.exists(transport_path):
        try:
            transport_geojson = gpd.read_file(transport_path).to_crs(4326).__geo_interface__
        except: transport_geojson = {"type": "FeatureCollection", "features": []}
    else: transport_geojson = {"type": "FeatureCollection", "features": []}
    transport_str = json.dumps(transport_geojson, cls=NumpyPandasEncoder)

    vatten_path = os.path.join(kart_filer_dir, 'vattendrag.geojson')
    if os.path.exists(vatten_path):
        try:
            vatten_geojson = gpd.read_file(vatten_path).to_crs(4326).__geo_interface__
        except: vatten_geojson = {"type": "FeatureCollection", "features": []}
    else: vatten_geojson = {"type": "FeatureCollection", "features": []}
    vatten_str = json.dumps(vatten_geojson, cls=NumpyPandasEncoder)

    # =====================================================================
    # 3. LÄS IN ADRESSPUNKTER OCH BEARBETA VALDATA
    # =====================================================================
    print("\nBearbetar valdata och adresspunkter...")
    gdf_merged = valdistrikt_gdf.copy()
    
    adress_file_xlsx = os.path.join(excel_filer_dir, 'adresspunkter_sept25.xlsx')
    adress_file_csv = os.path.join(excel_filer_dir, 'adresspunkter_sept25.csv')
    df_adress = None
    heat_data_list = []
    cluster_points = []
    trakt_list = []
    agg_rost = pd.DataFrame()

    if os.path.exists(adress_file_xlsx): df_adress = pd.read_excel(adress_file_xlsx)
    elif os.path.exists(adress_file_csv): df_adress = pd.read_csv(adress_file_csv)

    if df_adress is not None and not df_adress.empty:
        # Säkerställ koordinaterna genom kommateckentvätt
        df_adress['X'] = pd.to_numeric(df_adress.get('X', np.nan).astype(str).str.replace(',', '.').str.replace(' ', ''), errors='coerce')
        df_adress['Y'] = pd.to_numeric(df_adress.get('Y', np.nan).astype(str).str.replace(',', '.').str.replace(' ', ''), errors='coerce')
        df_adress = df_adress.dropna(subset=['X', 'Y'])
        
        # --- AGGREGERA PÅ TRAKT/KVARTER ---
        # Tvätta fastighet och antal_rostberattigade oavsett små/stora bokstäver
        c_map_adr = {str(c).strip().lower(): c for c in df_adress.columns}
        fast_col = next((c_map_adr[c] for c in ['fastighet', 'fastighetsbeteckning'] if c in c_map_adr), None)
        if fast_col:
            df_adress['fastighet_clean'] = df_adress[fast_col].apply(lambda x: fix_text(str(x)) if pd.notnull(x) else 'Okänd')
        else:
            df_adress['fastighet_clean'] = 'Okänd'
            
        rost_col = next((c_map_adr[c] for c in ['antal_rostberattigade', 'rostberattigade'] if c in c_map_adr), 'antal_rostberattigade')
        df_adress['rostberattigade_clean'] = pd.to_numeric(df_adress.get(rost_col, 0), errors='coerce').fillna(0)
        
        # Klipp av siffrorna från fastigheten för att få trakt ("Olofstorp 1:16" -> "Olofstorp")
        df_adress['trakt'] = df_adress['fastighet_clean'].astype(str).str.extract(r'^([^\d]+)')[0].str.strip()
        valid_adress = df_adress[df_adress['rostberattigade_clean'] > 0].copy()
        
        if not valid_adress.empty:
            trakt_agg = valid_adress.groupby('trakt').agg({'X': 'mean', 'Y': 'mean', 'rostberattigade_clean': 'sum'}).reset_index()
            trakt_gdf = gpd.GeoDataFrame(trakt_agg, geometry=gpd.points_from_xy(trakt_agg.X, trakt_agg.Y), crs="EPSG:3006").to_crs(4326)
            for idx, row in trakt_gdf.iterrows():
                if pd.notnull(row.geometry.y) and pd.notnull(row.geometry.x) and row['trakt'] and row['trakt'] != 'Okänd':
                    trakt_list.append([float(row.geometry.y), float(row.geometry.x), safe_str(row['trakt']), int(row['rostberattigade_clean'])])
        
        adress_gdf = gpd.GeoDataFrame(df_adress, geometry=gpd.points_from_xy(df_adress.X, df_adress.Y), crs="EPSG:3006")
        
        # SNABBFIX FÖR NÅBARHET: Koppla punkter till valdistrikt i Python istället för på-klick i JS
        if not valdistrikt_gdf.empty:
            vd_3006 = valdistrikt_gdf.to_crs(epsg=3006)
            joined = gpd.sjoin(adress_gdf, vd_3006, how="inner", predicate="within")
            agg_rost = joined.groupby('MATCH_ID')['rostberattigade_clean'].sum().reset_index()
            agg_rost.rename(columns={'rostberattigade_clean': 'Beraknad_Rostberattigade'}, inplace=True)
            
            joined_4326 = joined.to_crs(epsg=4326)
            joined_4326['rostberattigade_clean'] = pd.to_numeric(joined_4326['rostberattigade_clean'], errors='coerce')
            valid_points = joined_4326.dropna(subset=['geometry', 'rostberattigade_clean'])
            valid_points = valid_points[valid_points['rostberattigade_clean'] > 0]
            
            for idx, row in valid_points.iterrows():
                y, x = float(row.geometry.y), float(row.geometry.x)
                if not math.isnan(y) and not math.isnan(x):
                    # Lägg till MATCH_ID (index 3) i listan för supersnabb JS-filtrering!
                    heat_data_list.append([y, x, float(row.rostberattigade_clean), str(row.MATCH_ID)])
                    cluster_points.append([y, x, str(row.MATCH_ID)])
        else:
            adress_gdf_4326 = adress_gdf.to_crs(epsg=4326)
            adress_gdf_4326['rostberattigade_clean'] = pd.to_numeric(adress_gdf_4326['rostberattigade_clean'], errors='coerce')
            valid_points = adress_gdf_4326.dropna(subset=['geometry', 'rostberattigade_clean'])
            valid_points = valid_points[valid_points['rostberattigade_clean'] > 0]
            for idx, row in valid_points.iterrows():
                y, x = float(row.geometry.y), float(row.geometry.x)
                if not math.isnan(y) and not math.isnan(x):
                    heat_data_list.append([y, x, float(row.rostberattigade_clean), ""])
                    cluster_points.append([y, x, ""])

    heat_data_json_str = json.dumps(heat_data_list, cls=NumpyPandasEncoder)
    cluster_points_json_str = json.dumps(cluster_points, cls=NumpyPandasEncoder)
    trakt_json_str = json.dumps(trakt_list, cls=NumpyPandasEncoder)

    valdistrikt_excel_path = os.path.join(excel_filer_dir, 'Valdistrikt_valkrets.xlsx')
    df_lokaler = pd.DataFrame()
    df_poi = pd.DataFrame()
    df_hushall = pd.DataFrame()
    lokaler_list = []
    poi_list = []

    # Standardkolumner för hushållsdata
    col_hushall = 'Antal hushåll'
    col_hyres = 'Andel hyresrätt'
    col_ensam = 'Andel ensamstående'
    col_eftergym = 'Andel lång eftergymnasial utb'

    if os.path.exists(valdistrikt_excel_path):
        df_vd_2022 = pd.read_excel(valdistrikt_excel_path, sheet_name='Valdistrikt2022')
        df_valdeltagande = pd.read_excel(valdistrikt_excel_path, sheet_name='Valdeltagande')
        
        try: df_lokaler = pd.read_excel(valdistrikt_excel_path, sheet_name='Vallokaler2022')
        except Exception: pass
        try: df_poi = pd.read_excel(valdistrikt_excel_path, sheet_name='Ovriga_platser')
        except Exception: pass
        try: df_hushall = pd.read_excel(valdistrikt_excel_path, sheet_name='Hushåll_2022')
        except Exception: pass
        
        xl_id_col = next((col for col in ['LänKommunKod', 'Koden', 'VALDISTRIKTSKOD'] if col in df_vd_2022.columns), None)
        if xl_id_col: df_vd_2022['MATCH_ID'] = df_vd_2022[xl_id_col].apply(normalize_id)
        else: df_vd_2022['MATCH_ID'] = df_vd_2022.index.astype(str)

        # 1. KOORDINATEXTRAKTION AV VALLOKALER
        if not df_lokaler.empty:
            x_col = next((c for c in df_lokaler.columns if str(c).upper() in ['X', 'X_KOORD', 'LONG', 'LONGITUDE', 'LONGITUD']), None)
            y_col = next((c for c in df_lokaler.columns if str(c).upper() in ['Y', 'Y_KOORD', 'LAT', 'LATITUDE', 'LATITUD']), None)
            
            if x_col and y_col:
                df_lokaler['X_num'] = pd.to_numeric(df_lokaler[x_col].astype(str).str.replace(',', '.').str.replace(' ', ''), errors='coerce')
                df_lokaler['Y_num'] = pd.to_numeric(df_lokaler[y_col].astype(str).str.replace(',', '.').str.replace(' ', ''), errors='coerce')
                valid_lok = df_lokaler.dropna(subset=['X_num', 'Y_num']).copy()
                
                if not valid_lok.empty:
                    if valid_lok['Y_num'].mean() < 100:
                        lok_gdf = gpd.GeoDataFrame(valid_lok, geometry=gpd.points_from_xy(valid_lok['X_num'], valid_lok['Y_num']), crs="EPSG:4326")
                    else:
                        lok_gdf = gpd.GeoDataFrame(valid_lok, geometry=gpd.points_from_xy(valid_lok['X_num'], valid_lok['Y_num']), crs="EPSG:3006").to_crs(epsg=4326)
                    
                    df_lokaler.loc[lok_gdf.index, 'Lok_Lat'] = lok_gdf.geometry.y
                    df_lokaler.loc[lok_gdf.index, 'Lok_Lon'] = lok_gdf.geometry.x
        
        # 2. SAMMANSLAGNING AV EXCEL-FLIKAR
        gdf_merged = gdf_merged.merge(df_vd_2022, on='MATCH_ID', how='inner')
        
        valdeltagande_id_col = next((col for col in ['LänKommunKod', 'Koden'] if col in df_valdeltagande.columns), None)
        if valdeltagande_id_col:
            df_valdeltagande['MATCH_ID'] = df_valdeltagande[valdeltagande_id_col].apply(normalize_id)
            gdf_merged = gdf_merged.merge(df_valdeltagande, on='MATCH_ID', how='left', suffixes=('', '_hist'))

        if not df_lokaler.empty:
            namn_col = 'Namn' if 'Namn' in gdf_merged.columns else 'NAMN'
            if 'VALDISTRIKT' in df_lokaler.columns and namn_col in gdf_merged.columns:
                df_lokaler['match_namn'] = df_lokaler['VALDISTRIKT'].astype(str).str.strip().str.upper()
                gdf_merged['match_namn'] = gdf_merged[namn_col].astype(str).str.strip().str.upper()
                cols_to_drop = [c for c in ['LOKAL', 'ADRESS1', 'Lok_Lat', 'Lok_Lon'] if c in gdf_merged.columns]
                gdf_merged.drop(columns=cols_to_drop, inplace=True, errors='ignore')
                gdf_merged = gdf_merged.merge(df_lokaler, on='match_namn', how='left')
                gdf_merged.drop(columns=['match_namn'], inplace=True)
            else:
                lokal_id_col = next((col for col in ['LänKommunKod', 'Koden', 'VALDISTRIKTSKOD'] if col in df_lokaler.columns), None)
                if lokal_id_col:
                    df_lokaler['MATCH_ID'] = df_lokaler[lokal_id_col].apply(normalize_id)
                    gdf_merged = gdf_merged.merge(df_lokaler, on='MATCH_ID', how='left')
                    
        # --- ROBUST HANTERING AV HUSHÅLL_2022 ---
        if not df_hushall.empty:
            df_hushall.rename(columns=lambda x: str(x).strip(), inplace=True)
            col_map = {str(c).lower(): c for c in df_hushall.columns}
            hushall_id_col = next((col_map[c] for c in ['länkommunkod', 'koden', 'valdistriktskod', 'valdistriktkod', 'kod', 'lkfv', 'id'] if c in col_map), None)
            
            col_hushall = col_map.get('antal hushåll', col_hushall)
            col_hyres = col_map.get('andel hyresrätt', col_hyres)
            col_ensam = col_map.get('andel ensamstående', col_ensam)
            col_eftergym = col_map.get('andel lång eftergymnasial utb', col_eftergym)
            
            cols_to_keep = [col_hushall, col_hyres, col_ensam, col_eftergym]
            actual_cols_to_keep = [c for c in cols_to_keep if c in df_hushall.columns]
            
            merged_success = False
            if hushall_id_col:
                df_hushall['MATCH_ID'] = df_hushall[hushall_id_col].apply(normalize_id)
                test_merge = gdf_merged[['MATCH_ID']].merge(df_hushall[['MATCH_ID']], on='MATCH_ID', how='inner')
                if len(test_merge) > 0:
                    gdf_merged = gdf_merged.merge(df_hushall[['MATCH_ID'] + actual_cols_to_keep], on='MATCH_ID', how='left')
                    merged_success = True
            
            if not merged_success:
                hushall_name_col = next((col_map[c] for c in ['namn', 'område', 'valdistrikt'] if c in col_map), None)
                if hushall_name_col:
                    df_hushall['match_namn'] = df_hushall[hushall_name_col].astype(str).str.strip().str.upper()
                    namn_col_gdf = 'Namn' if 'Namn' in gdf_merged.columns else 'NAMN'
                    if namn_col_gdf in gdf_merged.columns:
                        gdf_merged['match_namn'] = gdf_merged[namn_col_gdf].astype(str).str.strip().str.upper()
                        gdf_merged = gdf_merged.merge(df_hushall[['match_namn'] + actual_cols_to_keep], on='match_namn', how='left')
                        gdf_merged.drop(columns=['match_namn'], inplace=True)
            
        # Extraktion av koordinater och POI-data
        if not df_poi.empty:
            x_col_poi = next((c for c in df_poi.columns if str(c).upper() in ['X', 'X_KOORD', 'LONG', 'LONGITUDE', 'LONGITUD']), None)
            y_col_poi = next((c for c in df_poi.columns if str(c).upper() in ['Y', 'Y_KOORD', 'LAT', 'LATITUDE', 'LATITUD']), None)
            
            if x_col_poi and y_col_poi:
                df_poi['X_num'] = pd.to_numeric(df_poi[x_col_poi], errors='coerce')
                df_poi['Y_num'] = pd.to_numeric(df_poi[y_col_poi], errors='coerce')
                valid_poi = df_poi.dropna(subset=['X_num', 'Y_num'])
                
                if not valid_poi.empty:
                    if valid_poi['Y_num'].mean() < 100:
                        poi_gdf = gpd.GeoDataFrame(valid_poi, geometry=gpd.points_from_xy(valid_poi['X_num'], valid_poi['Y_num']), crs="EPSG:4326")
                    else:
                        poi_gdf = gpd.GeoDataFrame(valid_poi, geometry=gpd.points_from_xy(valid_poi['X_num'], valid_poi['Y_num']), crs="EPSG:3006").to_crs(epsg=4326)
                    
                    for idx, row in poi_gdf.iterrows():
                        if pd.notnull(row.geometry.y) and pd.notnull(row.geometry.x):
                            namn = safe_str(row.get('Namn', row.get('Plats', 'Intressant Plats')))
                            funktion = safe_str(row.get('Funktion', row.get('Typ', '')))
                            fortidsroster = safe_str(row.get('Antal_förtidsröster_2022', row.get('Antal_fortidsroster_2022', safe_str(row.get('Antal_förtidsröster', '')))))
                            poi_list.append([row.geometry.y, row.geometry.x, namn, funktion, fortidsroster])

    if not agg_rost.empty:
        gdf_merged = gdf_merged.merge(agg_rost, on='MATCH_ID', how='left')

    if not gdf_merged.empty:
        for idx, row in gdf_merged.iterrows():
            if pd.notnull(row.get('Lok_Lat')) and pd.notnull(row.get('Lok_Lon')):
                lokaler_list.append([
                    float(row['Lok_Lat']), 
                    float(row['Lok_Lon']), 
                    safe_str(row.get('LOKAL', 'Vallokal')), 
                    safe_str(row.get('ADRESS1', '')),
                    safe_str(row.get('MATCH_ID', '')),
                    safe_str(row.get('Namn', row.get('NAMN', '')))
                ])

    lokaler_json_str = json.dumps(lokaler_list, cls=NumpyPandasEncoder)
    poi_json_str = json.dumps(poi_list, cls=NumpyPandasEncoder)

    # --- LÄS IN RIKTIG PARTIDATA FRÅN EXCEL OCH TVÄTTA ---
    partier = ['M', 'KD', 'L', 'C', 'S', 'V', 'MP', 'SD', 'LL']
    party_data_dict = {}
    party_results_path = os.path.join(excel_filer_dir, 'Partiernas_valresultat.xlsx')
    
    if os.path.exists(party_results_path):
        try:
            xls_parti = pd.ExcelFile(party_results_path)
            for p in partier:
                if p in xls_parti.sheet_names:
                    df_p = pd.read_excel(party_results_path, sheet_name=p)
                    c_map_p = {str(c).strip().upper(): c for c in df_p.columns}
                    p_id_col = next((c_map_p[c] for c in ['LÄNKOMMUNKOD', 'KODEN', 'LKFV', 'VALDISTRIKTSKOD'] if c in c_map_p), None)
                    val_col = next((c_map_p[c] for c in ['2022', 'VALRESULTAT 2022', 'ANDEL 2022', 'PROCENT', 'ANDEL', 'RESULTAT', 'RÖSTER (%)'] if c in c_map_p), None)
                    
                    if p_id_col and val_col:
                        df_p['MATCH_ID'] = df_p[p_id_col].apply(normalize_id)
                        for _, row_p in df_p.iterrows():
                            m_id = str(row_p['MATCH_ID'])
                            if m_id not in party_data_dict:
                                party_data_dict[m_id] = {pt: 0.0 for pt in partier}
                            
                            val_str = str(row_p[val_col]).replace(',', '.').replace('%', '').replace(' ', '').strip()
                            try:
                                v = float(val_str)
                                party_data_dict[m_id][p] = v
                            except:
                                pass
                                
            # Säkerhetscheck: Är värdena inmatade som t.ex. 0.25 istället för 25%?
            for m_id, p_data in party_data_dict.items():
                tot = sum(p_data.values())
                # Om summan av alla partier är under 1.5 betyder det att decimalformat används
                if 0 < tot <= 1.5:  
                    for pt in p_data:
                        party_data_dict[m_id][pt] = round(p_data[pt] * 100, 1)
                else:
                    for pt in p_data:
                        party_data_dict[m_id][pt] = round(p_data[pt], 1)
        except Exception as e:
            print(f"Kunde inte läsa in Partiernas valresultat: {e}")

    # --- BYGG DATADICTIONARY FÖR JAVASCRIPT ---
    val_data_dict = {}

    hist_years = ['1998', '2002', '2006', '2010', '2014', '2018', '2022']

    if not gdf_merged.empty:
        for idx, row in gdf_merged.iterrows():
            match_id = safe_str(row.get('MATCH_ID', 'Okänt'))
            
            hist_data = {}
            for y in hist_years:
                val = row.get(y, row.get(y + '_hist'))
                if pd.isna(val) and int(y) in row: val = row.get(int(y))
                if val is not None and not pd.isna(val):
                    try: hist_data[y] = round(float(str(val).replace(',', '.')), 1)
                    except: hist_data[y] = None
                else: 
                    hist_data[y] = None

            namn = safe_str(row.get('Namn', row.get('NAMN', f'Område_{idx}')))
            
            valdeltagande = round(safe_num(row.get('Valdeltagande', 0)), 1)
            
            # Säkerställ att 2022 kommer med i linjediagrammet
            if hist_data.get('2022') is None and valdeltagande > 0:
                hist_data['2022'] = valdeltagande
                
            rostberattigade = int(safe_num(row.get('Röstberättigade', 0))) 
            rostberattigade_2025 = int(safe_num(row.get('Beraknad_Rostberattigade', 0))) 
            
            rostande = int(safe_num(row.get('Röstande', 0)))
            forstagangs = round(safe_num(row.get('Andel förstagångsväljare', 0)), 1)
            utlandska = round(safe_num(row.get('Andel utländska medborgare', 0)), 1)
            ej_rostande = round(safe_num(row.get('Andel ej röstande', 0)), 1)
            
            antal_hushall = int(safe_num(row.get(col_hushall, 0)))
            andel_hyresratt = round(safe_num(row.get(col_hyres, 0)), 1)
            andel_ensamstaende = round(safe_num(row.get(col_ensam, 0)), 1)
            andel_eftergymnasial = round(safe_num(row.get(col_eftergym, 0)), 1)
            
            # --- DELTA BERÄKNING 2018 -> 2022 ---
            val_2018 = hist_data.get('2018')
            if val_2018 is None:
                val_2018 = safe_num(row.get('2018', valdeltagande))
            delta_valdeltagande = round(valdeltagande - val_2018, 1)

            lok_lat = row.get('Lok_Lat', None)
            lok_lon = row.get('Lok_Lon', None)

            # Dra in riktig partidata istället för random!
            p_data = party_data_dict.get(match_id, {pt: 0.0 for pt in partier})
            storsta_parti = max(p_data, key=p_data.get) if any(v > 0 for v in p_data.values()) else 'Saknas'

            val_data_dict[match_id] = {
                'NAMN': namn,
                'Valkrets': safe_str(row.get('Valkrets', 'Saknas')),
                'Vallokal': safe_str(row.get('LOKAL', 'Saknas')),
                'Adress': safe_str(row.get('ADRESS1', 'Saknas')),
                'Lok_Lat': lok_lat if pd.notnull(lok_lat) else None,
                'Lok_Lon': lok_lon if pd.notnull(lok_lon) else None,
                'Valdeltagande': valdeltagande,
                'Delta_Valdeltagande': delta_valdeltagande,
                'Rostberattigade': rostberattigade,
                'Rostberattigade_2025': rostberattigade_2025,
                'Rostande': rostande,
                'Andel_Ej_Rostande': ej_rostande,
                'Andel_Forstagangsvaljare': forstagangs,
                'Andel_Utlandska_Medborgare': utlandska,
                'Antal_hushall': antal_hushall,
                'Andel_hyresratt': andel_hyresratt,
                'Andel_ensamstaende': andel_ensamstaende,
                'Andel_eftergymnasial': andel_eftergymnasial,
                'Storsta_Parti': storsta_parti,
                'Partidata': p_data,
                'Historik_Valdeltagande': hist_data
            }
        val_data_json_str = json.dumps(val_data_dict, cls=NumpyPandasEncoder)
    else:
        val_data_json_str = "{}"

    for col in gdf_merged.columns:
        if col != 'geometry':
            if pd.api.types.is_datetime64_any_dtype(gdf_merged[col]):
                gdf_merged[col] = gdf_merged[col].astype(str)
            else:
                gdf_merged[col] = gdf_merged[col].apply(lambda x: str(x) if isinstance(x, (pd.Timestamp, datetime.datetime, datetime.date)) else x)

    # =====================================================================
    # 4. KARTBYGGE (HTML/JS Visualisering med Folium)
    # =====================================================================
    print("\nGenererar karta...")
    m = folium.Map(location=[58.4102, 15.6216], zoom_start=11, tiles=None)

    if not gdf_merged.empty:
        folium.GeoJson(
            gdf_merged, 
            name='Valdistriktsgränser', 
            style_function=lambda feature: {'fillColor': '#ffffff', 'color': '#2c3e50', 'weight': 2, 'fillOpacity': 0.6, 'className': 'polygon-layer valdistrikt-polygon'}
        ).add_to(m)

    minimap = MiniMap(toggleDisplay=True, position="topleft", zoomLevelOffset=-4, tile_layer="cartodbpositron")
    m.add_child(minimap)

    # =====================================================================
    # 5. INJICERA GYLLENE STANDARDMALL (Responsiv UI)
    # =====================================================================
    ui_html = f"""
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet-search/3.0.2/leaflet-search.min.css" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster/dist/MarkerCluster.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster/dist/MarkerCluster.Default.css" />
    <script src="https://unpkg.com/leaflet.markercluster/dist/leaflet.markercluster.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>
    <script src="https://unpkg.com/@turf/turf/turf.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet-search/3.0.2/leaflet-search.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://unpkg.com/leaflet.heat/dist/leaflet-heat.js"></script>

    <style>
        :root {{ --poi-scale: 1; }}
        
        /* HEADER / TITEL PANELEN */
        .header-panel {{ position: fixed; top: 20px; left: 50%; transform: translateX(-50%); z-index: 9999; background: rgba(255,255,255,0.95); padding: 10px 25px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); display: flex; align-items: center; font-family: sans-serif; white-space: nowrap; }}
        .header-panel img {{ height: 35px; margin-right: 15px; }}
        .header-panel h4 {{ margin: 0; font-weight: bold; color: #2c3e50; font-size: 20px; letter-spacing: 0.5px; }}
        
        /* VERKTYGSPANEL NERE TILL VÄNSTER */
        .tools-panel {{ position: fixed; bottom: 30px; left: 60px; z-index: 9999; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 330px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; transition: all 0.3s ease; }}
        
        /* KONTROLLPANEL UPPE TILL HÖGER */
        .layers-panel {{ position: fixed; top: 20px; right: 20px; z-index: 9999; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 340px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; }}
        
        /* INFO-PANEL BREDVID KONTROLLPANELEN */
        .info-panel {{ position: fixed; top: 20px; right: 370px; z-index: 9999; background: rgba(255,255,255,0.98); padding: 20px; border-radius: 8px; box-shadow: 0 0 20px rgba(0,0,0,0.3); width: 380px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; display: none; transition: all 0.3s ease; font-size: 14px; line-height: 1.5; }}
        .info-panel p {{ margin-bottom: 6px; }}
        
        .btn-custom {{ width: 100%; margin-bottom: 8px; text-align: left; font-size: 13px; padding: 6px 12px; }}
        .form-check-input {{ transform: scale(1.4); margin-top: 4px; margin-right: 10px; cursor: pointer; }}
        .form-check-label {{ cursor: pointer; font-size: 14px; }}
        
        .legend-container {{ position: fixed; bottom: 30px; left: 400px; z-index: 9998; display: flex; flex-direction: row; flex-wrap: wrap; align-items: flex-end; gap: 10px; pointer-events: none; max-width: calc(100vw - 400px); }}
        .variable-legend {{ pointer-events: auto; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.2); margin: 0; font-family: sans-serif; font-size: 12px; display: none; }}
        .legend-color-box {{ display: inline-block; width: 15px; height: 15px; margin-right: 5px; vertical-align: middle; border: 1px solid #ccc; }}
        
        .nav-tabs .nav-link {{ padding: 5px 10px; font-size: 13px; color: #495057; cursor: pointer; }}
        .nav-tabs .nav-link.active {{ font-weight: bold; color: #0570b0; }}
        .val-tooltip {{ background: rgba(255,255,255,0.98); border: 1px solid #ccc; box-shadow: 0 2px 10px rgba(0,0,0,0.2); border-radius: 4px; padding: 10px; color: #333; }}
        .custom-tooltip-wrapper {{ background: transparent; border: none; box-shadow: none; padding: 0; margin: 0; pointer-events: none; }}
        
        .leaflet-popup-content {{ margin: 10px 14px; line-height: 1.4; }}
        
        .border-polygon {{ pointer-events: none !important; }}
        
        /* RESPONSIVITET FÖR MINDRE SKÄRMAR */
        @media (max-width: 768px) {{
            .header-panel {{ top: 5px; padding: 6px 10px; width: auto; max-width: 90%; }}
            .header-panel img {{ height: 20px; margin-right: 8px; }}
            .header-panel h4 {{ font-size: 15px; }}
            .tools-panel {{ bottom: 10px; left: 10px; width: 220px; padding: 10px; max-height: 50vh; }}
            .layers-panel {{ top: 60px; right: 10px; width: 220px; padding: 10px; max-height: 50vh; }}
            .form-check-label {{ font-size: 12px; }}
            .btn-custom {{ font-size: 11px; margin-bottom: 4px; padding: 4px 8px; }}
            .info-panel {{ z-index: 10001; top: 60px; left: 50%; transform: translateX(-50%); width: 95%; max-height: 70vh; }}
            .legend-container {{ bottom: 10px; left: 240px; transform: scale(0.7); transform-origin: bottom left; }}
        }}
        @media (max-width: 576px) {{
            .tools-panel {{ width: 180px; }}
            .layers-panel {{ width: 180px; }}
            .legend-container {{ display: none !important; }} /* Gömmer legenden på jättesmå skärmar för att spara plats */
        }}
    </style>
    
    <!-- HEADER PANEL -->
    <div class="header-panel">
        <img src="Img/Linkopingsloggo.png" alt="Linköping Logotyp" onerror="this.style.display='none'">
        <h4>Valanalys Linköping 2022</h4>
    </div>

    <div class="legend-container" id="legend-container">
        <!-- Separata Legender -->
        <div id="legend-Valdeltagande" class="variable-legend"><h6 style="margin-bottom:5px;font-weight:bold;">Valdeltagande (%)</h6>
            <div><i class="legend-color-box" style="background:#023858"></i> &gt; 90%</div>
            <div><i class="legend-color-box" style="background:#0570b0"></i> 85 - 90%</div>
            <div><i class="legend-color-box" style="background:#74a9cf"></i> 80 - 85%</div>
            <div><i class="legend-color-box" style="background:#bdc9e1"></i> 75 - 80%</div>
            <div><i class="legend-color-box" style="background:#d0d1e6"></i> &lt; 75%</div>
        </div>
        <div id="legend-Rostande" class="variable-legend"><h6 style="margin-bottom:5px;font-weight:bold;">Antal Röstande</h6>
            <div><i class="legend-color-box" style="background:#006d2c"></i> &gt; 2000</div>
            <div><i class="legend-color-box" style="background:#31a354"></i> 1500 - 2000</div>
            <div><i class="legend-color-box" style="background:#74c476"></i> 1000 - 1500</div>
            <div><i class="legend-color-box" style="background:#bae4b3"></i> 500 - 1000</div>
            <div><i class="legend-color-box" style="background:#edf8e9"></i> &lt; 500</div>
        </div>
        <div id="legend-Rostberattigade" class="variable-legend"><h6 style="margin-bottom:5px;font-weight:bold;">Antal Röstberättigade</h6>
            <div><i class="legend-color-box" style="background:#006d2c"></i> &gt; 2000</div>
            <div><i class="legend-color-box" style="background:#31a354"></i> 1500 - 2000</div>
            <div><i class="legend-color-box" style="background:#74c476"></i> 1000 - 1500</div>
            <div><i class="legend-color-box" style="background:#bae4b3"></i> 500 - 1000</div>
            <div><i class="legend-color-box" style="background:#edf8e9"></i> &lt; 500</div>
        </div>
        <div id="legend-Andel_Forstagangsvaljare" class="variable-legend"><h6 style="margin-bottom:5px;font-weight:bold;">Förstagångsväljare (%)</h6>
            <div><i class="legend-color-box" style="background:#99000d"></i> &gt; 10%</div>
            <div><i class="legend-color-box" style="background:#cb181d"></i> 8 - 10%</div>
            <div><i class="legend-color-box" style="background:#ef3b2c"></i> 6 - 8%</div>
            <div><i class="legend-color-box" style="background:#fb6a4a"></i> 4 - 6%</div>
            <div><i class="legend-color-box" style="background:#fee0d2"></i> &lt; 4%</div>
        </div>
        <div id="legend-Andel_Utlandska_Medborgare" class="variable-legend"><h6 style="margin-bottom:5px;font-weight:bold;">Utländska Medborgare (%)</h6>
            <div><i class="legend-color-box" style="background:#4a1486"></i> &gt; 20%</div>
            <div><i class="legend-color-box" style="background:#6a51a3"></i> 15 - 20%</div>
            <div><i class="legend-color-box" style="background:#807dba"></i> 10 - 15%</div>
            <div><i class="legend-color-box" style="background:#bcbddc"></i> 5 - 10%</div>
            <div><i class="legend-color-box" style="background:#f2f0f7"></i> &lt; 5%</div>
        </div>
        <div id="legend-Andel_Ej_Rostande" class="variable-legend"><h6 style="margin-bottom:5px;font-weight:bold;">Ej Röstande (%)</h6>
            <div><i class="legend-color-box" style="background:#a63603"></i> &gt; 25%</div>
            <div><i class="legend-color-box" style="background:#e6550d"></i> 20 - 25%</div>
            <div><i class="legend-color-box" style="background:#fd8d3c"></i> 15 - 20%</div>
            <div><i class="legend-color-box" style="background:#fdbe85"></i> 10 - 15%</div>
            <div><i class="legend-color-box" style="background:#feedde"></i> &lt; 10%</div>
        </div>
        <div id="legend-Delta_Valdeltagande" class="variable-legend"><h6 style="margin-bottom:5px;font-weight:bold;">Δ Valdeltagande (18-22)</h6>
            <div><i class="legend-color-box" style="background:#006d2c"></i> &gt; +2 %-enh</div>
            <div><i class="legend-color-box" style="background:#31a354"></i> 0 till +2 %-enh</div>
            <div><i class="legend-color-box" style="background:#f7f7f7"></i> Oförändrat (±0)</div>
            <div><i class="legend-color-box" style="background:#fb6a4a"></i> 0 till -2 %-enh</div>
            <div><i class="legend-color-box" style="background:#de2d26"></i> &lt; -2 %-enh</div>
        </div>
        <div id="legend-Antal_hushall" class="variable-legend"><h6 style="margin-bottom:5px;font-weight:bold;">Hushåll (Antal)</h6>
            <div><i class="legend-color-box" style="background:#54278f"></i> &gt; 1500</div>
            <div><i class="legend-color-box" style="background:#756bb1"></i> 1000 - 1500</div>
            <div><i class="legend-color-box" style="background:#9e9ac8"></i> 500 - 1000</div>
            <div><i class="legend-color-box" style="background:#cbc9e2"></i> 250 - 500</div>
            <div><i class="legend-color-box" style="background:#dadaeb"></i> &lt; 250</div>
        </div>
        <div id="legend-Andel_hyresratt" class="variable-legend"><h6 style="margin-bottom:5px;font-weight:bold;">Hyresrätt (%)</h6>
            <div><i class="legend-color-box" style="background:#a63603"></i> &gt; 60%</div>
            <div><i class="legend-color-box" style="background:#e6550d"></i> 40 - 60%</div>
            <div><i class="legend-color-box" style="background:#fd8d3c"></i> 20 - 40%</div>
            <div><i class="legend-color-box" style="background:#fdbe85"></i> 10 - 20%</div>
            <div><i class="legend-color-box" style="background:#fdd0a2"></i> &lt; 10%</div>
        </div>
        <div id="legend-Andel_ensamstaende" class="variable-legend"><h6 style="margin-bottom:5px;font-weight:bold;">Ensamstående (%)</h6>
            <div><i class="legend-color-box" style="background:#006d2c"></i> &gt; 60%</div>
            <div><i class="legend-color-box" style="background:#2ca25f"></i> 50 - 60%</div>
            <div><i class="legend-color-box" style="background:#66c2a4"></i> 40 - 50%</div>
            <div><i class="legend-color-box" style="background:#b2e2e2"></i> 30 - 40%</div>
            <div><i class="legend-color-box" style="background:#ccece6"></i> &lt; 30%</div>
        </div>
        <div id="legend-Andel_eftergymnasial" class="variable-legend"><h6 style="margin-bottom:5px;font-weight:bold;">Lång eftergymnasial utb. (%)</h6>
            <div><i class="legend-color-box" style="background:#02818a"></i> &gt; 40%</div>
            <div><i class="legend-color-box" style="background:#3690c0"></i> 30 - 40%</div>
            <div><i class="legend-color-box" style="background:#67a9cf"></i> 20 - 30%</div>
            <div><i class="legend-color-box" style="background:#a6bddb"></i> 10 - 20%</div>
            <div><i class="legend-color-box" style="background:#d0d1e6"></i> &lt; 10%</div>
        </div>
    </div>

    <!-- VERKTYGSPANEL TILL VÄNSTER MED SÖKFUNKTION -->
    <div class="tools-panel">
        <h5 class="fw-bold mb-3 border-bottom pb-2">
            ⚙️ Analys & Verktyg
            <i class="fa-solid fa-circle-info ms-1 text-info" style="cursor:pointer; font-size:15px; float:right; margin-top:3px;" onclick="showGeneralInfo()" title="Information om verktygen"></i>
        </h5>
        
        <h6 class="fw-bold mb-1" style="font-size: 13px;">🔍 Sök Valdistrikt:</h6>
        <input type="text" id="searchDistrikt" list="distriktList" class="form-control mb-2" style="padding: 8px 10px; font-size: 14px;" placeholder="Skriv in namn...">
        <datalist id="distriktList"></datalist>
        <div id="searchResultBox" class="p-2 mb-3 bg-white border border-info rounded shadow-sm" style="display:none; font-size:13px; line-height:1.4;"></div>

        <h6 class="fw-bold mb-1" style="font-size: 13px;">📍 Filtrera på Valkrets:</h6>
        <select id="valkretsSelect" class="form-select form-select-sm mb-3" style="font-size: 12px;">
            <option value="ALLA">-- Visa hela Linköping --</option>
        </select>

        <h6 class="fw-bold mb-1" style="font-size: 13px;">⚡ Snabbfilter:</h6>
        <button id="btn-filter-utland" class="btn btn-outline-secondary btn-sm btn-custom mb-1" value="UTLAND">🌍 &gt; 8% Utländska medborgare</button>
        <button id="btn-filter-valdeltagande" class="btn btn-outline-secondary btn-sm btn-custom mb-1" value="VALDELTAGANDE">📉 &lt; 75% Valdeltagande</button>
        
        <div class="d-flex gap-2 mb-3">
            <button id="btn-filter-top10" class="btn btn-outline-secondary btn-sm flex-fill" style="font-size: 12px; padding: 4px;" value="TOP10">🏆 Topp 10</button>
            <button id="btn-filter-bottom10" class="btn btn-outline-secondary btn-sm flex-fill" style="font-size: 12px; padding: 4px;" value="BOTTOM10">🔽 Lägsta 10</button>
        </div>
        
        <button id="btn-zoom-selection" class="btn btn-outline-primary btn-sm btn-custom mb-3">🔍 Zooma till urval</button>
        
        <hr style="margin: 10px 0;">
        <h6 class="fw-bold mb-1" style="font-size: 13px; color:#e74c3c;">
            📡 Vita fläckar (Täckning)
            <i class="fa-solid fa-circle-info ms-1 text-info" style="cursor:pointer;" onclick="showCoverageInfo()" title="Information om verktyget"></i>
        </h6>
        <div class="d-flex gap-1 mb-3 align-items-center">
            <span style="font-size:12px;">Mer än</span>
            <input type="number" id="covMinutes" class="form-control form-control-sm" value="15" style="width: 60px;" min="1" max="60">
            <span style="font-size: 12px;">min med</span>
            <select id="covMode" class="form-select form-select-sm" style="width: 80px;">
                <option value="walk">🚶</option>
                <option value="bike">🚲</option>
                <option value="car">🚗</option>
            </select>
            <button id="btn-coverage" class="btn btn-primary btn-sm">Kör</button>
        </div>

        <hr style="margin: 10px 0;">
        <div class="p-2 mb-2 bg-light border border-secondary rounded shadow-sm">
            <div class="d-flex justify-content-between align-items-center mb-1">
                <label for="opacitySlider" class="form-label mb-0 fw-bold" style="font-size: 13px; color: #2c3e50;">Opacitet ytor:</label>
                <span id="opacityVal" class="badge bg-primary" style="font-size: 12px;">60%</span>
            </div>
            <input type="range" class="form-range" id="opacitySlider" min="0" max="1" step="0.05" value="0.60">
        </div>
        <button id="btn-measure" class="btn btn-outline-info btn-sm btn-custom mb-2">📍 Nåbarhet Vallokal (Klicka-i-distrikt)</button>
        <button id="btn-reset" class="btn btn-danger btn-sm btn-custom">🔄 Återställ karta helt</button>
    </div>

    <!-- KONTROLLPANEL TILL HÖGER -->
    <div class="layers-panel">
        <h5 class="fw-bold mb-3 border-bottom pb-2">🗂️ Kartlager</h5>
        
        <h6 class="fw-bold mb-2" style="font-size: 13px;">🗺️ Bakgrundskarta</h6>
        <select id="basemapSelect" class="form-select form-select-sm mb-3" style="font-size: 12px;">
            <option value="blek" selected>Karta: Blek (För tydlig analys)</option>
            <option value="farg">Karta: Färgstark (Detaljerad)</option>
            <option value="flyg">Karta: Flygfoto (Satellit)</option>
        </select>
        
        <hr style="margin: 10px 0;">
        <h6 class="fw-bold mb-2">📊 Valdata Ytor & Analys</h6>
        <div class="form-check mb-1">
            <input class="form-check-input var-toggle" type="radio" name="layerToggle" value="Valdeltagande" id="t_valdeltagande" checked>
            <label class="form-check-label" for="t_valdeltagande">🗳️ Valdeltagande 2022 (%)</label>
        </div>
        <div class="form-check mb-2" style="background:#f8f9fa; padding-top:2px; padding-bottom:2px; border-radius:4px;">
            <input class="form-check-input var-toggle" type="radio" name="layerToggle" value="Delta_Valdeltagande" id="t_delta">
            <label class="form-check-label text-danger fw-bold" for="t_delta">📉 Δ Valdeltagande (18-22)</label>
        </div>
        <div class="form-check mb-1">
            <input class="form-check-input var-toggle" type="radio" name="layerToggle" value="Rostande" id="t_rostande">
            <label class="form-check-label" for="t_rostande">👥 Röstande (Antal)</label>
        </div>
        <div class="form-check mb-1">
            <input class="form-check-input var-toggle" type="radio" name="layerToggle" value="Rostberattigade" id="t_rostberattigade">
            <label class="form-check-label" for="t_rostberattigade">📋 Röstberättigade (Antal)</label>
        </div>
        <div class="form-check mb-1">
            <input class="form-check-input var-toggle" type="radio" name="layerToggle" value="Andel_Forstagangsvaljare" id="t_forsta">
            <label class="form-check-label" for="t_forsta">🎓 Andel förstagångsväljare (%)</label>
        </div>
        <div class="form-check mb-1">
            <input class="form-check-input var-toggle" type="radio" name="layerToggle" value="Andel_Utlandska_Medborgare" id="t_utland">
            <label class="form-check-label" for="t_utland">🌍 Andel utländska medborgare (%)</label>
        </div>
        <div class="form-check mb-1">
            <input class="form-check-input var-toggle" type="radio" name="layerToggle" value="Andel_Ej_Rostande" id="t_ejrost">
            <label class="form-check-label" for="t_ejrost">🚫 Andel ej röstande (%)</label>
        </div>
        
        <hr style="margin: 10px 0;">
        <h6 class="fw-bold mb-2">🏘️ Hushållsdata (2022)</h6>
        <div class="form-check mb-1">
            <input class="form-check-input var-toggle" type="radio" name="layerToggle" value="Antal_hushall" id="t_hushall">
            <label class="form-check-label" for="t_hushall">🏠 Hushåll (Antal)</label>
        </div>
        <div class="form-check mb-1">
            <input class="form-check-input var-toggle" type="radio" name="layerToggle" value="Andel_hyresratt" id="t_hyresratt">
            <label class="form-check-label" for="t_hyresratt">🏢 Andel hyresrätt (%)</label>
        </div>
        <div class="form-check mb-1">
            <input class="form-check-input var-toggle" type="radio" name="layerToggle" value="Andel_ensamstaende" id="t_ensamstaende">
            <label class="form-check-label" for="t_ensamstaende">👤 Andel ensamstående (%)</label>
        </div>
        <div class="form-check mb-2">
            <input class="form-check-input var-toggle" type="radio" name="layerToggle" value="Andel_eftergymnasial" id="t_eftergymnasial">
            <label class="form-check-label" for="t_eftergymnasial">🎓 Andel lång eftergymnasial utb. (%)</label>
        </div>
        
        <div class="form-check mb-2">
            <input class="form-check-input var-toggle" type="radio" name="layerToggle" value="Granser" id="t_granser">
            <label class="form-check-label" for="t_granser">🔲 Endast gränser</label>
        </div>
        
        <hr style="margin: 10px 0;">
        <h6 class="fw-bold mb-2">📍 Platser & Infrastruktur</h6>
        <div class="form-check mb-1">
            <input class="form-check-input" type="checkbox" id="toggleVarmekarta">
            <label class="form-check-label" for="toggleVarmekarta">🔥 Värmekarta (Röstberättigade)</label>
        </div>
        <div class="form-check mb-1">
            <input class="form-check-input" type="checkbox" id="toggleKluster">
            <label class="form-check-label" for="toggleKluster">🏘️ Adresspunkter (Alla)</label>
        </div>
        <div class="form-check mb-1">
            <input class="form-check-input" type="checkbox" id="toggleTrakter">
            <label class="form-check-label fw-bold text-primary" for="toggleTrakter">🏘️ Trakter/Kvarter (Summerat)</label>
        </div>
        <div class="form-check mb-1">
            <input class="form-check-input" type="checkbox" id="toggleLokaler">
            <label class="form-check-label" for="toggleLokaler">📍 Vallokaler</label>
        </div>
        <div class="form-check mb-1">
            <input class="form-check-input" type="checkbox" id="togglePOI">
            <label class="form-check-label" for="togglePOI">⭐ Övriga platser</label>
        </div>
        <div class="form-check mb-1">
            <input class="form-check-input" type="checkbox" id="toggleTransport">
            <label class="form-check-label" for="toggleTransport">🛤️ Transportleder</label>
        </div>
        <div class="form-check mb-3">
            <input class="form-check-input" type="checkbox" id="toggleVatten">
            <label class="form-check-label" for="toggleVatten">💧 Sjöar & vattendrag</label>
        </div>
        
        <hr style="margin: 10px 0;">
        <div class="form-check mb-1">
            <input class="form-check-input" type="checkbox" id="toggleGraph" checked>
            <label class="form-check-label fw-bold" for="toggleGraph" style="font-size: 13px; color:#0570b0;">📈 Visa graf vid klick (Ytor)</label>
        </div>
    </div>

    <!-- INFO-PANEL TILL HÖGER (Bredvid kontrollpanelen) -->
    <div id="infoPanel" class="info-panel">
        <div class="d-flex justify-content-between align-items-center mb-2" style="border-bottom: 2px solid #ccc; padding-bottom: 8px;">
            <h5 class="fw-bold mb-0" id="panelTitle">📊 Valdistriktsfakta</h5>
            <button type="button" class="btn-close" onclick="closeInfoPanel()"></button>
        </div>
        
        <ul class="nav nav-tabs mb-3" id="infoTabs" role="tablist">
            <li class="nav-item"><button class="nav-link active" id="overview-tab" data-bs-toggle="tab" data-bs-target="#overview" type="button" role="tab">Översikt 2022</button></li>
            <li class="nav-item"><button class="nav-link" id="history-tab" data-bs-toggle="tab" data-bs-target="#history" type="button" role="tab">Historik (1998-)</button></li>
        </ul>
        
        <div class="tab-content" id="infoTabsContent">
            <div class="tab-pane fade show active" id="overview" role="tabpanel">
                <div id="overviewContent"></div>
                <div class="mt-3">
                    <p class="mb-1 fw-bold" style="font-size: 12px;">Partifördelning 2022:</p>
                    <div style="position: relative; height: 180px; width: 100%;">
                        <canvas id="partyChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="tab-pane fade" id="history" role="tabpanel">
                <p class="mb-1 fw-bold" style="font-size: 12px;">Historiskt Valdeltagande:</p>
                <div style="position: relative; height: 180px; width: 100%;">
                    <canvas id="historyChart"></canvas>
                </div>
            </div>
        </div>
    </div>

    <script>
        var valData = {val_data_json_str};
        var heatPoints = {heat_data_json_str};
        var clusterPoints = {cluster_points_json_str};
        var traktData = {trakt_json_str};
        var lokalerData = {lokaler_json_str};
        var poiData = {poi_json_str};
        var transportData = {transport_str};
        var vattenData = {vatten_str};
        
        var partyChartInstance = null;
        var historyChartInstance = null;
        var currentActiveVariable = 'Valdeltagande';
        var stadshusetLatlng = L.latLng(58.4109, 15.6216); 
        
        var currentValkrets = 'ALLA';
        var currentFilter = 'NONE';
        var showGraphOnClick = true;
        var currentBorderColor = '#2c3e50';

        var ptsByDistrikt = {{}};
        heatPoints.forEach(p => {{
            var distId = p[3];
            if(distId) {{
                if(!ptsByDistrikt[distId]) ptsByDistrikt[distId] = [];
                ptsByDistrikt[distId].push(p);
            }}
        }});

        // Toast med flexibel tidsinställning (duration)
        function showToast(msg, duration) {{
            duration = duration || 5000;
            var toast = document.createElement('div');
            toast.style.position = 'fixed';
            toast.style.top = '20px';
            toast.style.left = '50%';
            toast.style.transform = 'translateX(-50%)';
            toast.style.background = '#2c3e50';
            toast.style.color = 'white';
            toast.style.padding = '12px 24px';
            toast.style.borderRadius = '8px';
            toast.style.zIndex = '10000';
            toast.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
            toast.style.fontFamily = 'sans-serif';
            toast.style.fontSize = '14px';
            toast.innerHTML = msg;
            
            if(duration > 5000) {{
                toast.innerHTML += '<button type="button" class="btn-close btn-close-white btn-sm" style="position:absolute; top:8px; right:8px;" onclick="this.parentElement.remove()"></button>';
                toast.style.paddingRight = '35px';
            }}
            
            document.body.appendChild(toast);
            setTimeout(() => {{
                if(document.body.contains(toast)) {{
                    toast.style.transition = 'opacity 0.5s ease';
                    toast.style.opacity = '0';
                    setTimeout(() => {{ if(document.body.contains(toast)) toast.remove(); }}, 500);
                }}
            }}, duration);
        }}
        
        window.showGeneralInfo = function() {{
            showToast("ℹ️ <b>Analys & Verktyg:</b><br><br><b>Snabbfilter:</b> Kombinera Valkrets med t.ex. 'Topp 10' för att direkt se vilka områden som sticker ut mest i den variabel du valt i kartlagren (t.ex. Valdeltagande eller Hushåll).<br><br><b>Nåbarhet Vallokal:</b> Aktivera verktyget och klicka var som helst i ett valdistrikt för att se gång-, cykel- och bilavstånd till just dess vallokal, samt avståndet till Stadshuset.", 15000);
        }};

        window.showCoverageInfo = function() {{
            showToast("ℹ️ <b>Så fungerar Täckningsanalysen:</b><br><br>Verktyget ritar ut transparenta gröna zoner runt alla vallokaler baserat på vald restid och färdsätt.<br><br>Områden och röstberättigade som hamnar <b>utanför</b> dessa zoner markeras som en röd-gul värmekarta ('vita fläckar'). Detta hjälper er att direkt identifiera var i kommunen det saknas god närhet till en röstlokal.", 15000);
        }};

        document.addEventListener('DOMContentLoaded', function() {{
            var map_id = Object.keys(window).find(key => key.startsWith('map_'));
            var map = window[map_id];
            
            map.createPane('centroidPane'); map.getPane('centroidPane').style.zIndex = 650;
            map.createPane('topMarkersPane'); map.getPane('topMarkersPane').style.zIndex = 660; 
            
            window.valPolygons = {{}};
            
            var valkretsar = new Set();
            var distriktNames = [];
            
            Object.values(valData).forEach(function(d) {{
                if(d.Valkrets && d.Valkrets !== 'Saknas') valkretsar.add(d.Valkrets);
                if(d.NAMN && !distriktNames.includes(d.NAMN)) distriktNames.push(d.NAMN);
            }});
            
            var vkSelect = document.getElementById('valkretsSelect');
            Array.from(valkretsar).sort(function(a, b) {{ return a.localeCompare(b, 'sv'); }}).forEach(function(vk) {{
                var opt = document.createElement('option');
                opt.value = vk; opt.innerHTML = vk;
                vkSelect.appendChild(opt);
            }});
            
            // Fyll dropdown för den nya sökfunktionen en gång (sorterat)
            distriktNames.sort(function(a, b) {{ return a.localeCompare(b, 'sv'); }});
            var dList = document.getElementById('distriktList');
            distriktNames.forEach(function(namn) {{
                var opt = document.createElement('option');
                opt.value = namn;
                dList.appendChild(opt);
            }});
            
            var tileBlek, tileFarg, tileFlyg;
            try {{
                tileBlek = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{ attribution: '&copy; CARTO', crossOrigin: true }}).addTo(map);
                tileFarg = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ attribution: '&copy; OSM', crossOrigin: true }});
                tileFlyg = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ attribution: 'Tiles &copy; Esri', crossOrigin: true }});

                document.getElementById('basemapSelect').addEventListener('change', function(e) {{
                    map.removeLayer(tileBlek); map.removeLayer(tileFarg); map.removeLayer(tileFlyg);
                    var isFlyg = false;
                    if(e.target.value === 'blek') tileBlek.addTo(map); 
                    else if(e.target.value === 'farg') tileFarg.addTo(map);
                    else if(e.target.value === 'flyg') {{ tileFlyg.addTo(map); isFlyg = true; }}
                    
                    currentBorderColor = isFlyg ? '#ffffff' : '#2c3e50';
                    map.eachLayer(function(layer) {{
                        if (layer.options && layer.options.className && layer.options.className.includes('valdistrikt-polygon')) {{
                            if (layer.setStyle && !layer.filteredOut) {{ 
                                layer.setStyle({{color: currentBorderColor}}); 
                                layer.options.color = currentBorderColor; 
                                if (layer.defaultStyle) layer.defaultStyle.color = currentBorderColor; 
                            }}
                        }}
                    }});
                }});
            }} catch(e) {{ console.error("Fel vid laddning av bakgrundskartor:", e); }}

            try {{
                var container = document.getElementById('legend-container');
                var legends = document.querySelectorAll('.legend');
                legends.forEach(function(leg) {{ container.appendChild(leg); leg.style.display = 'block'; }});
            }} catch(e) {{ console.error("Fel vid hantering av teckenförklaring:", e); }}

            function getColor(val, variable) {{
                if (val === null || val === undefined) return 'transparent';
                if (variable === 'Valdeltagande') {{ return val > 90 ? '#023858' : val > 85 ? '#0570b0' : val > 80 ? '#74a9cf' : val > 75 ? '#bdc9e1' : '#d0d1e6';
                }} else if (variable === 'Delta_Valdeltagande') {{ return val > 2 ? '#006d2c' : val > 0 ? '#31a354' : val == 0 ? '#f7f7f7' : val > -2 ? '#fb6a4a' : '#de2d26';
                }} else if (variable === 'Rostande' || variable === 'Rostberattigade') {{ return val > 2000 ? '#006d2c' : val > 1500 ? '#31a354' : val > 1000 ? '#74c476' : val > 500 ? '#bae4b3' : '#edf8e9';
                }} else if (variable === 'Andel_Forstagangsvaljare') {{ return val > 10 ? '#99000d' : val > 8 ? '#cb181d' : val > 6 ? '#ef3b2c' : val > 4 ? '#fb6a4a' : '#fee0d2';
                }} else if (variable === 'Andel_Utlandska_Medborgare') {{ return val > 20 ? '#4a1486' : val > 15 ? '#6a51a3' : val > 10 ? '#807dba' : val > 5 ? '#bcbddc' : '#f2f0f7';
                }} else if (variable === 'Andel_Ej_Rostande') {{ return val > 25 ? '#a63603' : val > 20 ? '#e6550d' : val > 15 ? '#fd8d3c' : val > 10 ? '#fdbe85' : '#feedde';
                }} else if (variable === 'Antal_hushall') {{ return val > 1500 ? '#54278f' : val > 1000 ? '#756bb1' : val > 500 ? '#9e9ac8' : val > 250 ? '#cbc9e2' : '#dadaeb';
                }} else if (variable === 'Andel_hyresratt') {{ return val > 60 ? '#a63603' : val > 40 ? '#e6550d' : val > 20 ? '#fd8d3c' : val > 10 ? '#fdbe85' : '#fdd0a2';
                }} else if (variable === 'Andel_ensamstaende') {{ return val > 60 ? '#006d2c' : val > 50 ? '#2ca25f' : val > 40 ? '#66c2a4' : val > 30 ? '#b2e2e2' : '#ccece6';
                }} else if (variable === 'Andel_eftergymnasial') {{ return val > 40 ? '#02818a' : val > 30 ? '#3690c0' : val > 20 ? '#67a9cf' : val > 10 ? '#a6bddb' : '#d0d1e6'; }}
                return 'transparent';
            }}

            function getCleanTooltip(data, variable) {{
                var extraInfo = "";
                var varNames = {{
                    'Delta_Valdeltagande': ['Förändring valdeltagande (18-22):', ' %-enh'],
                    'Andel_Forstagangsvaljare': ['Förstagångsväljare:', ' %'],
                    'Andel_Utlandska_Medborgare': ['Utländska medb.:', ' %'],
                    'Andel_Ej_Rostande': ['Ej röstande:', ' %'],
                    'Rostande': ['Röstande:', ' st'],
                    'Antal_hushall': ['Hushåll (Antal):', ' st'],
                    'Andel_hyresratt': ['Andel hyresrätt:', ' %'],
                    'Andel_ensamstaende': ['Andel ensamstående:', ' %'],
                    'Andel_eftergymnasial': ['Lång eftergymnasial utb.:', ' %']
                }};
                
                if (varNames[variable]) {{
                    var prefix = (variable === 'Delta_Valdeltagande' && data[variable] > 0) ? '+' : '';
                    extraInfo = `<strong>${{varNames[variable][0]}}</strong> <span style="color:#e74c3c;">${{prefix}}${{data[variable] !== null ? data[variable].toLocaleString('sv-SE') : '?'}}${{varNames[variable][1]}}</span><br>`;
                }}

                return `
                    <div class="val-tooltip" style="font-size: 13px; line-height: 1.4;">
                        <div style="font-size: 15px; border-bottom: 1px solid #ccc; padding-bottom: 4px; margin-bottom: 4px; font-weight: bold; color: #0570b0;">
                            ${{data.NAMN}}
                        </div>
                        <strong>Valkrets:</strong> ${{data.Valkrets}}<br>
                        <strong>Vallokal:</strong> ${{data.Vallokal}}<br>
                        <span style="font-size: 11px; color: #555;">📍 ${{data.Adress}}</span><hr style="margin:4px 0;">
                        <strong>Valdeltagande:</strong> ${{data.Valdeltagande}} %<br>
                        <strong>Röstberättigade (2022):</strong> ${{data.Rostberattigade.toLocaleString('sv-SE')}} st <span style="font-size:11px; color:#777; font-weight:normal;">(Prel. 2025: ${{data.Rostberattigade_2025.toLocaleString('sv-SE')}} st)</span><br>
                        ${{extraInfo}}
                    </div>
                `;
            }}

            function applyFilters() {{
                var bounds = L.latLngBounds();
                var hasVisible = false;
                var top10Ids = [];
                
                if ((currentFilter === 'TOP10' || currentFilter === 'BOTTOM10') && currentActiveVariable !== 'Granser') {{
                    var sorted = Object.entries(valData)
                        .filter(entry => {{
                            var v = entry[1][currentActiveVariable];
                            return v !== null && v !== undefined && !isNaN(v);
                        }})
                        .sort((a, b) => {{
                            if (currentFilter === 'TOP10') return b[1][currentActiveVariable] - a[1][currentActiveVariable];
                            else return a[1][currentActiveVariable] - b[1][currentActiveVariable];
                        }})
                        .slice(0, 10);
                    top10Ids = sorted.map(entry => entry[0]);
                }}

                var currentOpacity = parseFloat(document.getElementById('opacitySlider').value);

                map.eachLayer(function(layer) {{
                    if (layer.options && layer.options.className && layer.options.className.includes('valdistrikt-polygon')) {{
                        if (layer.feature && layer.feature.properties && layer.feature.properties.MATCH_ID) {{
                            var matchId = layer.feature.properties.MATCH_ID;
                            var data = valData[matchId];
                            var isVisible = true;
                            
                            if (data) {{
                                if (currentValkrets !== 'ALLA' && data.Valkrets !== currentValkrets) isVisible = false;
                                if (currentFilter === 'UTLAND' && data.Andel_Utlandska_Medborgare !== null && data.Andel_Utlandska_Medborgare <= 8) isVisible = false;
                                if (currentFilter === 'VALDELTAGANDE' && data.Valdeltagande !== null && data.Valdeltagande >= 75) isVisible = false;
                                if (currentFilter === 'TOP10' || currentFilter === 'BOTTOM10') {{
                                    if (currentActiveVariable === 'Granser') isVisible = true; 
                                    else if (!top10Ids.includes(matchId)) isVisible = false;
                                }}
                            }} else {{
                                isVisible = false;
                            }}

                            layer.filteredOut = !isVisible;
                            
                            if (isVisible) {{
                                if (currentActiveVariable === 'Granser') {{
                                    layer.setStyle({{opacity: 1, fillOpacity: 0, color: currentBorderColor, weight: 2}});
                                    layer.defaultStyle = {{ weight: 2, color: currentBorderColor, fillOpacity: 0, fillColor: 'transparent' }};
                                }} else {{
                                    var newColor = getColor(data ? data[currentActiveVariable] : null, currentActiveVariable);
                                    layer.setStyle({{opacity: 1, fillColor: newColor, fillOpacity: currentOpacity, color: currentBorderColor, weight: 2}}); 
                                    layer.defaultStyle = {{ weight: 2, color: currentBorderColor, fillOpacity: currentOpacity, fillColor: newColor }};
                                }}
                                if (!analysisMode) layer.setTooltipContent(getCleanTooltip(data, currentActiveVariable));
                                bounds.extend(layer.getBounds());
                                hasVisible = true;
                            }} else {{
                                layer.setStyle({{opacity: 0, fillOpacity: 0, color: 'transparent', weight: 0}});
                                layer.closeTooltip();
                            }}
                        }}
                    }}
                }});
                
                document.querySelectorAll('.variable-legend').forEach(el => el.style.display = 'none');
                if (currentActiveVariable !== 'Granser') {{
                    var legendElement = document.getElementById('legend-' + currentActiveVariable);
                    if (legendElement) legendElement.style.display = 'block';
                }}
                
                return {{ bounds, hasVisible }};
            }}

            document.getElementById('valkretsSelect').addEventListener('change', function(e) {{
                currentValkrets = e.target.value;
                applyFilters();
            }});

            document.getElementById('toggleGraph').addEventListener('change', function(e) {{
                showGraphOnClick = this.checked;
            }});

            function setFilterBtnActive(btnId) {{
                ['btn-filter-utland', 'btn-filter-valdeltagande', 'btn-filter-top10', 'btn-filter-bottom10'].forEach(id => {{
                    var el = document.getElementById(id);
                    if(el) {{
                        el.classList.remove('btn-secondary');
                        el.classList.add('btn-outline-secondary');
                    }}
                }});
                if (btnId) {{
                    var btnEl = document.getElementById(btnId);
                    if(btnEl) {{
                        btnEl.classList.remove('btn-outline-secondary');
                        btnEl.classList.add('btn-secondary');
                    }}
                }}
            }}

            var filterUtland = document.getElementById('btn-filter-utland');
            if (filterUtland) {{
                filterUtland.addEventListener('click', function() {{
                    currentFilter = currentFilter === 'UTLAND' ? 'NONE' : 'UTLAND';
                    setFilterBtnActive(currentFilter === 'UTLAND' ? 'btn-filter-utland' : null);
                    applyFilters();
                }});
            }}

            var filterVald = document.getElementById('btn-filter-valdeltagande');
            if (filterVald) {{
                filterVald.addEventListener('click', function() {{
                    currentFilter = currentFilter === 'VALDELTAGANDE' ? 'NONE' : 'VALDELTAGANDE';
                    setFilterBtnActive(currentFilter === 'VALDELTAGANDE' ? 'btn-filter-valdeltagande' : null);
                    applyFilters();
                }});
            }}

            document.getElementById('btn-filter-top10').addEventListener('click', function() {{
                currentFilter = currentFilter === 'TOP10' ? 'NONE' : 'TOP10';
                setFilterBtnActive(currentFilter === 'TOP10' ? 'btn-filter-top10' : null);
                applyFilters();
            }});
            
            document.getElementById('btn-filter-bottom10').addEventListener('click', function() {{
                currentFilter = currentFilter === 'BOTTOM10' ? 'NONE' : 'BOTTOM10';
                setFilterBtnActive(currentFilter === 'BOTTOM10' ? 'btn-filter-bottom10' : null);
                applyFilters();
            }});

            document.getElementById('btn-zoom-selection').addEventListener('click', function() {{
                var result = applyFilters();
                if(result.hasVisible && result.bounds.isValid()) map.fitBounds(result.bounds, {{padding: [20, 20]}});
            }});

            document.querySelectorAll('.var-toggle').forEach(function(radio) {{
                radio.addEventListener('change', function() {{
                    if(this.checked) {{
                        currentActiveVariable = this.value;
                        applyFilters();
                    }}
                }});
            }});
            
            // Lyssna på sökfältet
            document.getElementById('searchDistrikt').addEventListener('input', function(e) {{
                var val = this.value.toLowerCase().trim();
                var box = document.getElementById('searchResultBox');
                if (!val) {{
                    box.style.display = 'none';
                    return;
                }}
                
                var matchId = null;
                var data = null;
                
                for (const [key, d] of Object.entries(valData)) {{
                    if (d.NAMN.toLowerCase() === val) {{
                        matchId = key;
                        data = d;
                        break;
                    }}
                }}

                if (data) {{
                    map.eachLayer(function(l) {{
                        if (l.feature && l.feature.properties && l.feature.properties.MATCH_ID === matchId) {{
                            if (l.options && l.options.className && l.options.className.includes('valdistrikt-polygon')) {{
                                map.fitBounds(l.getBounds(), {{padding: [50, 50], maxZoom: 14}});
                                
                                var origStyle = l.defaultStyle;
                                var blinks = 0;
                                var blinkInterval = setInterval(function() {{
                                    if (blinks % 2 === 0) {{
                                        l.setStyle({{ weight: 8, color: '#ffff00', fillOpacity: 0.9 }});
                                    }} else {{
                                        l.setStyle({{ weight: 8, color: '#ff0000', fillOpacity: 0.9 }});
                                    }}
                                    blinks++;
                                    if (blinks >= 6) {{
                                        clearInterval(blinkInterval);
                                        if(!l.filteredOut) l.setStyle({{ weight: origStyle.weight, color: origStyle.color, fillOpacity: origStyle.fillOpacity, fillColor: origStyle.fillColor }});
                                    }}
                                }}, 500);
                            }}
                        }}
                    }});

                    var sRost = data.Rostberattigade !== null ? `<b>Röstberättigade (2022):</b> ${{data.Rostberattigade.toLocaleString('sv-SE')}} st<br><span style="font-size:11px; color:#777;">(Prel. 2025: ${{data.Rostberattigade_2025.toLocaleString('sv-SE')}} st)</span><br>` : `<b>Röstberättigade (Prel. 2025):</b> ${{data.Rostberattigade_2025.toLocaleString('sv-SE')}} st<br>`;

                    box.innerHTML = `
                        <div style="display:flex; justify-content:space-between;">
                            <h6 style="color:#0570b0; font-weight:bold; margin-bottom:4px; font-size:13px;">${{data.NAMN}}</h6>
                            <button type="button" class="btn-close btn-sm" style="font-size:10px;" onclick="document.getElementById('searchResultBox').style.display='none'; document.getElementById('searchDistrikt').value='';"></button>
                        </div>
                        ${{sRost}}
                        <hr style="margin:4px 0;">
                        <b>Vallokal:</b> ${{data.Vallokal}}<br>
                        <span style="color:#555;">📍 ${{data.Adress}}</span>
                    `;
                    box.style.display = 'block';
                }} else {{
                    box.style.display = 'none';
                }}
            }});

            // -------------------------------------------------------------------
            // LAGER OCH EXTRAS
            // -------------------------------------------------------------------
            
            var heatDataForLeaflet = heatPoints.map(function(p) {{ return [p[0], p[1], p[2]]; }});
            var heatLayerObj = L.heatLayer(heatDataForLeaflet, {{radius: 12, blur: 15, maxZoom: 14}});
            
            var clusterLayerObj = L.markerClusterGroup({{disableClusteringAtZoom: 15, spiderfyOnMaxZoom: false}});
            clusterPoints.forEach(function(p) {{ clusterLayerObj.addLayer(L.circleMarker([p[0], p[1]], {{radius: 4, fillColor: '#3498db', color: 'white', weight: 1, fillOpacity: 0.8}})); }});

            // ================= NY FUNKTION: TRAKTER / KVARTER =================
            var traktLayerObj = L.markerClusterGroup({{maxClusterRadius: 40, disableClusteringAtZoom: 13}});
            traktData.forEach(function(t) {{
                var lat = t[0], lng = t[1], namn = t[2], rost = t[3];
                var html = "";
                var displayNum = "";
                
                // SEKRETESS: Visa inte exakt siffra om < 5 personer
                if (rost < 5) {{
                    html = `
                        <div class='val-tooltip' style='font-family:sans-serif; padding:5px; line-height: 1.4; text-align:center;'>
                            <b style='color:#2980b9; font-size:14px;'>📍 ${{namn}}</b>
                        </div>
                    `;
                    displayNum = ""; 
                }} else {{
                    html = `
                        <div class='val-tooltip' style='font-family:sans-serif; padding:5px; line-height: 1.4; text-align:center;'>
                            <b style='color:#2980b9; font-size:14px;'>📍 ${{namn}}</b><br>
                            <b>Röstberättigade (Prel 2025):</b> ${{rost.toLocaleString('sv-SE')}} st
                        </div>
                    `;
                    displayNum = rost >= 1000 ? (rost/1000).toFixed(1).replace('.0','') + 'k' : rost;
                }}
                
                var icon = L.divIcon({{
                    className: 'custom-div-icon',
                    html: `<div style='background-color:#3498db; color:white; border-radius:50%; border:2px solid white; width:28px; height:28px; display:flex; justify-content:center; align-items:center; font-size:10px; font-weight:bold; box-shadow: 0 0 5px rgba(0,0,0,0.5);'>${{displayNum}}</div>`,
                    iconSize: [28, 28],
                    iconAnchor: [14, 14]
                }});
                
                var marker = L.marker([lat, lng], {{icon: icon, pane: 'topMarkersPane'}}); 
                marker.bindTooltip(html, {{direction: 'top', className: 'custom-tooltip-wrapper', offset: [0, -10]}});
                traktLayerObj.addLayer(marker);
            }});

            var transportLayerObj = L.geoJSON(transportData, {{
                style: function(feature) {{ 
                    var props = feature.properties || {{}};
                    var railway = (props.railway || "").toString().toLowerCase();
                    var highway = (props.highway || "").toString().toLowerCase();

                    if (highway === 'motorway') return {{color: '#e31a1c', weight: 5, opacity: 0.9}}; 
                    if (railway === 'rail') return {{color: '#333333', weight: 3, opacity: 0.8, dashArray: '5,5'}}; 
                    if (highway === 'primary') return {{color: '#ffc107', weight: 4, opacity: 0.9}}; 
                    if (highway === 'secondary') return {{color: '#ffc107', weight: 2.5, opacity: 0.9}}; 
                    
                    return {{color: '#888888', weight: 2, opacity: 0.7}};
                }},
                interactive: false
            }});
            
            var vattenLayerObj = L.geoJSON(vattenData, {{
                style: function(feature) {{ return {{fillColor: '#85c1e9', color: '#2980b9', weight: 1, fillOpacity: 0.6}}; }},
                interactive: false
            }});

            var lokalerLayerObj = L.markerClusterGroup({{
                maxClusterRadius: 20, 
                spiderfyOnMaxZoom: true,
                spiderLegPolylineOptions: {{ weight: 2, color: '#333', opacity: 0.7 }}
            }});
            
            lokalerData.forEach(function(loc) {{
                var lat = loc[0]; var lon = loc[1]; var lokalNamn = loc[2]; var adress = loc[3]; var matchId = loc[4]; var distriktNamn = loc[5];
                var marker = L.circleMarker([lat, lon], {{radius: 9, fillColor: '#8e44ad', color: '#fff', weight: 3, fillOpacity: 0.9, pane: 'topMarkersPane'}});
                
                var ptLokal = turf.point([lon, lat]);
                var countUnder500 = 0, countOver2500 = 0;
                var distPts = ptsByDistrikt[matchId] || [];
                distPts.forEach(p => {{
                    var d = turf.distance(turf.point([p[1], p[0]]), ptLokal, {{units: 'kilometers'}});
                    if(d < 0.5) countUnder500 += p[2];
                    if(d > 2.5) countOver2500 += p[2];
                }});

                var tooltipHtml = `
                    <div class='val-tooltip' style='font-family:sans-serif; padding:5px; width: 170px;'>
                        <b style='font-size:13px;'>${{lokalNamn}}</b><br>
                        <span style='color:gray;font-size:11px;'>📍 ${{adress}}</span><br>
                        <span style='font-size:11px; color:#0570b0;'>Tillhör: ${{distriktNamn}}</span>
                        <hr style='margin:5px 0;'>
                        <span style='font-size:11px;'>
                            <b>&lt; 500m:</b> ${{countUnder500.toLocaleString('sv-SE')}} st<br>
                            <b>&gt; 2.5km:</b> ${{countOver2500.toLocaleString('sv-SE')}} st
                        </span>
                    </div>
                `;
                marker.bindTooltip(tooltipHtml, {{direction: 'top', className: 'custom-tooltip-wrapper'}});
                
                marker.on('click', function(e) {{
                    L.DomEvent.stopPropagation(e); 
                    
                    var distStadshus = turf.distance(ptLokal, turf.point([stadshusetLatlng.lng, stadshusetLatlng.lat]), {{units: 'kilometers'}});
                    var bikeStadshus = Math.round((distStadshus * 1.2) / 15 * 60);
                    var carStadshus = Math.round((distStadshus * 1.3) / 40 * 60);

                    var totalDist = 0, countWalk5 = 0, countBike5 = 0, countCar5 = 0;
                    
                    distPts.forEach(p => {{
                        totalDist += p[2];
                        var d = turf.distance(turf.point([p[1], p[0]]), ptLokal, {{units: 'kilometers'}});
                        if(d <= 0.32) countWalk5 += p[2]; 
                        if(d <= 1.0) countBike5 += p[2];  
                        if(d <= 2.5) countCar5 += p[2];   
                    }});

                    var pctWalk = totalDist > 0 ? Math.round((countWalk5/totalDist)*100) : 0;
                    var pctBike = totalDist > 0 ? Math.round((countBike5/totalDist)*100) : 0;
                    var pctCar = totalDist > 0 ? Math.round((countCar5/totalDist)*100) : 0;

                    var html = `
                        <div style='width:260px; font-family:sans-serif;'>
                            <h6 style='color:#8e44ad; font-weight:bold; margin-bottom:2px;'>${{lokalNamn}}</h6>
                            <span style='font-size:11px; color:#555;'>📍 ${{adress}} (Distrikt: ${{distriktNamn}})</span>
                            <hr style='margin:8px 0;'>
                            <b>Till Stadshuset (Fågelväg: ${{distStadshus.toFixed(2)}} km)</b><br>
                            <span style='font-size:12px;'>🚲 Cykel: ~${{bikeStadshus}} min | 🚗 Bil: ~${{carStadshus}} min</span>
                            <hr style='margin:8px 0;'>
                            <b>Röstberättigade (Prel 2025): (${{totalDist.toLocaleString('sv-SE')}} st)</b><br>
                            <table style='width:100%; font-size:12px; margin-top:4px;'>
                                <tr><td>&lt; 500m till lokal:</td><td style='text-align:right'><b>${{countUnder500.toLocaleString('sv-SE')}} st</b></td></tr>
                                <tr><td>&gt; 2.5km till lokal:</td><td style='text-align:right'><b>${{countOver2500.toLocaleString('sv-SE')}} st</b></td></tr>
                            </table>
                            <h5 style="color:#8e44ad;font-weight:bold;border-bottom:1px solid #ccc;padding-bottom:5px;margin-bottom:5px;font-size:16px;">⏱️ Nåbarhetsfångst (5 min)</h5>
                            <span style="font-size:11px;color:#555;">Av distriktets ${{totalDist.toLocaleString('sv-SE')}} röstberättigade (Prel. 2025) når:</span>
                            <table style="width:100%; margin-top:3px; font-size:13px;">
                                <tr><td>🚶 Gång:</td><td style="text-align:right;"><b>${{countWalk5.toLocaleString('sv-SE')}} st</b> (${{pctWalk}}%)</td></tr>
                                <tr><td>🚲 Cykel:</td><td style="text-align:right;"><b>${{countBike5.toLocaleString('sv-SE')}} st</b> (${{pctBike}}%)</td></tr>
                                <tr><td>🚗 Bil:</td><td style="text-align:right;"><b>${{countCar5.toLocaleString('sv-SE')}} st</b> (${{pctCar}}%)</td></tr>
                            </table>
                        </div>
                    `;
                    L.popup({{maxWidth: 320, offset: [0, -80], autoPanPadding: [50, 50]}}).setLatLng([lat, lon]).setContent(html).openOn(map);
                }});
                lokalerLayerObj.addLayer(marker);
            }});
            
            var poiLayerObj = L.markerClusterGroup({{maxClusterRadius: 20, spiderfyOnMaxZoom: true}});
            poiData.forEach(function(poi) {{
                var lat = poi[0], lon = poi[1], namn = poi[2], funktion = poi[3], rots = poi[4];
                
                var isStadshus = namn.toLowerCase().includes('stadshus');
                var marker = L.circleMarker([lat, lon], {{
                    radius: isStadshus ? 11 : 8, 
                    fillColor: isStadshus ? '#c0392b' : '#e67e22', 
                    color: isStadshus ? '#f1c40f' : '#fff', 
                    weight: isStadshus ? 3 : 2, 
                    fillOpacity: 0.9, 
                    pane: 'topMarkersPane'
                }});
                
                var tooltipHtml = "<b>" + namn + "</b>";
                if (funktion && funktion !== 'Information saknas') tooltipHtml += "<br><span style='font-size:11px;'>" + funktion + "</span>";
                marker.bindTooltip("<div class='val-tooltip' style='font-family:sans-serif; padding:5px;'>" + tooltipHtml + "</div>", {{direction: 'top', className: 'custom-tooltip-wrapper'}});
                
                marker.on('click', function(e) {{
                    L.DomEvent.stopPropagation(e);
                    var popupHtml = "<div style='width:180px;font-family:sans-serif;'><b>" + namn + "</b>";
                    if (funktion && funktion !== 'Information saknas') popupHtml += "<br><span style='color:#555;font-size:12px;'>" + funktion + "</span>";
                    
                    if (rots && rots !== 'Information saknas' && rots !== '0') {{
                        var rotsNum = parseInt(rots.replace(/\s/g, ''));
                        if(!isNaN(rotsNum)) rots = rotsNum.toLocaleString('sv-SE');
                        popupHtml += "<hr style='margin:5px 0;'><b>Förtidsröster:</b> " + rots + " st";
                    }}
                    popupHtml += "</div>";
                    L.popup({{offset: [0, -10]}}).setLatLng([lat, lon]).setContent(popupHtml).openOn(map);
                }});
                
                poiLayerObj.addLayer(marker);
            }});

            // Slå på lager när de klickas
            document.getElementById('toggleVarmekarta').addEventListener('change', function(e) {{ if(this.checked) map.addLayer(heatLayerObj); else map.removeLayer(heatLayerObj); }});
            document.getElementById('toggleKluster').addEventListener('change', function(e) {{ if(this.checked) map.addLayer(clusterLayerObj); else map.removeLayer(clusterLayerObj); }});
            document.getElementById('toggleTrakter').addEventListener('change', function(e) {{ if(this.checked) map.addLayer(traktLayerObj); else map.removeLayer(traktLayerObj); }});
            document.getElementById('toggleLokaler').addEventListener('change', function(e) {{ if(this.checked) map.addLayer(lokalerLayerObj); else map.removeLayer(lokalerLayerObj); }});
            document.getElementById('togglePOI').addEventListener('change', function(e) {{ if(this.checked) map.addLayer(poiLayerObj); else map.removeLayer(poiLayerObj); }});
            document.getElementById('toggleTransport').addEventListener('change', function(e) {{ if(this.checked) map.addLayer(transportLayerObj); else map.removeLayer(transportLayerObj); }});
            document.getElementById('toggleVatten').addEventListener('change', function(e) {{ if(this.checked) map.addLayer(vattenLayerObj); else map.removeLayer(vattenLayerObj); }});

            window.closeInfoPanel = function() {{ document.getElementById('infoPanel').style.display = 'none'; }}
            
            // Färgkodning för partier, inkl Linköpingslistan (LL)
            const partyColors = {{'S': '#E8112d', 'M': '#52BDEC', 'SD': '#DDDD00', 'C': '#009933', 'V': '#DA291C', 'KD': '#000077', 'L': '#006AB3', 'MP': '#83CF39', 'LL': '#FF9900'}};

            function showInfoPanel(matchId) {{
                let data = valData[matchId];
                if(!data) return;

                document.getElementById('panelTitle').innerText = data.NAMN;
                let htmlContent = `
                    <table class="table table-sm table-borderless mb-2">
                        <tr><td><strong>Valkrets:</strong></td><td class="text-end">${{data.Valkrets}}</td></tr>
                        <tr><td><strong>Vallokal:</strong></td><td class="text-end">${{data.Vallokal}}<br><span style="font-size: 11px; color: #777;">📍 ${{data.Adress}}</span></td></tr>
                        <tr><td><strong>Röstberättigade (2022):</strong></td><td class="text-end">${{data.Rostberattigade !== null ? data.Rostberattigade.toLocaleString('sv-SE') : '?'}} st</td></tr>
                        <tr><td><strong><span style="color:#777;">(Prel. 2025):</span></strong></td><td class="text-end"><span style="color:#777;">${{data.Rostberattigade_2025.toLocaleString('sv-SE')}} st</span></td></tr>
                        <tr><td><strong>Röstande:</strong></td><td class="text-end">${{data.Rostande !== null ? data.Rostande.toLocaleString('sv-SE') : '?'}} st</td></tr>
                        <tr><td><strong>Valdeltagande:</strong></td><td class="text-end fw-bold text-primary">${{data.Valdeltagande}} %</td></tr>
                    </table>
                `;
                document.getElementById('overviewContent').innerHTML = htmlContent;
                document.getElementById('infoPanel').style.display = 'block';
                
                var overviewTab = new bootstrap.Tab(document.querySelector('#overview-tab'));
                overviewTab.show();

                var ar = data.Party_Year || "2022";
                var st_parti_html = data.Storsta_Parti && data.Storsta_Parti !== 'Saknas' ? ` (Störst: <span style="color:${{partyColors[data.Storsta_Parti]}}">${{data.Storsta_Parti}}</span>)` : '';
                var titleEl = document.getElementById('partyChartTitle');
                if (titleEl) titleEl.innerHTML = "Partifördelning " + ar + ":" + st_parti_html;

                let ctxParty = document.getElementById('partyChart').getContext('2d');
                if (partyChartInstance) partyChartInstance.destroy(); 
                let pLabels = Object.keys(data.Partidata);
                let pValues = Object.values(data.Partidata);
                let bgColors = pLabels.map(p => partyColors[p] || '#888');
                partyChartInstance = new Chart(ctxParty, {{
                    type: 'bar',
                    data: {{ labels: pLabels, datasets: [{{ data: pValues, backgroundColor: bgColors, borderRadius: 3 }}] }},
                    options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ display: false }}, tooltip: {{callbacks: {{label: function(context) {{ return context.parsed.y + ' %'; }} }} }} }}, scales: {{ y: {{ beginAtZero: true, max: 60, title: {{ display: true, text: 'Röster (%)' }} }} }} }}
                }});

                let ctxHist = document.getElementById('historyChart').getContext('2d');
                if (historyChartInstance) historyChartInstance.destroy();
                let hLabels = Object.keys(data.Historik_Valdeltagande).sort();
                let hValues = hLabels.map(y => data.Historik_Valdeltagande[y]);
                historyChartInstance = new Chart(ctxHist, {{
                    type: 'line',
                    data: {{ labels: hLabels, datasets: [{{ label: 'Valdeltagande (%)', data: hValues, borderColor: '#0570b0', backgroundColor: 'rgba(5, 112, 176, 0.1)', borderWidth: 2, fill: true, tension: 0.3, spanGaps: false }}] }},
                    options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ min: 50, max: 100 }} }} }}
                }});
            }}

            var analysisMode = false;
            var analysisGroup = L.layerGroup().addTo(map);

            document.getElementById('btn-measure').addEventListener('click', function() {{
                analysisMode = !analysisMode;
                this.classList.toggle('btn-info');
                this.classList.toggle('btn-outline-info');
                if(analysisMode) {{
                    map._container.style.cursor = 'crosshair';
                    showToast("ℹ️ <b>Nåbarhetsanalys aktiv!</b><br>Klicka var som helst i ett valdistrikt för att analysera rutten till dess vallokal.", 10000);
                }} else {{
                    map._container.style.cursor = '';
                    analysisGroup.clearLayers();
                    applyFilters(); 
                }}
            }});

            // ================= NY TÄCKNINGSANALYS (VITA FLÄCKAR) =================
            var coverageGroup = L.layerGroup().addTo(map);
            var heatLayerOutside = null;
            
            document.getElementById('btn-coverage').addEventListener('click', function() {{
                coverageGroup.clearLayers();
                if(heatLayerOutside) map.removeLayer(heatLayerOutside);
                
                var minutes = parseFloat(document.getElementById('covMinutes').value);
                var mode = document.getElementById('covMode').value;
                if(isNaN(minutes) || minutes <= 0) return;
                
                var speed, factor;
                if(mode === 'walk') {{ speed = 5; factor = 1.3; }}
                else if(mode === 'bike') {{ speed = 15; factor = 1.2; }}
                else {{ speed = 40; factor = 1.3; }}
                
                var radiusKm = (minutes * speed) / (60 * factor);
                
                lokalerData.forEach(loc => {{
                    L.circle([loc[0], loc[1]], {{
                        radius: radiusKm * 1000,
                        color: '#27ae60',
                        fillColor: '#27ae60',
                        fillOpacity: 0.15,
                        weight: 1,
                        interactive: false
                    }}).addTo(coverageGroup);
                }});
                
                var ptsOutside = [];
                var totalVotersOutside = 0;
                
                heatPoints.forEach(p => {{
                    var pt = turf.point([p[1], p[0]]);
                    var isCovered = false;
                    for(var i=0; i<lokalerData.length; i++) {{
                        var locPt = turf.point([lokalerData[i][1], lokalerData[i][0]]);
                        if (turf.distance(pt, locPt, {{units: 'kilometers'}}) <= radiusKm) {{
                            isCovered = true;
                            break;
                        }}
                    }}
                    if (!isCovered) {{
                        ptsOutside.push([p[0], p[1], p[2]]);
                        totalVotersOutside += p[2];
                    }}
                }});
                
                if(ptsOutside.length > 0) {{
                    heatLayerOutside = L.heatLayer(ptsOutside, {{
                        radius: 12, 
                        blur: 15, 
                        maxZoom: 14, 
                        gradient: {{0.4: 'red', 0.6: 'yellow', 1: 'orange'}}
                    }}).addTo(coverageGroup);
                }}
                
                showToast(`<b>Täckningsanalys klar!</b><br>Kartan visar nu zoner som nås inom ${{minutes}} min. De röda områdena markerar de ca <b>${{totalVotersOutside.toLocaleString('sv-SE')}}</b> röstberättigade som har för långt till en vallokal.`, 20000);
            }});

            function runAccessibilityAnalysis(clickLatlng, matchId, layer) {{
                analysisGroup.clearLayers(); 
                var data = valData[matchId];
                
                if (!data || !data.Lok_Lat || !data.Lok_Lon || isNaN(data.Lok_Lat)) {{
                    L.popup({{offset: [0, -80], autoPanPadding: [50, 50]}}).setLatLng(clickLatlng).setContent("<div style='font-family:sans-serif;'>⚠️ Saknar koordinater för <b>" + (data ? data.Vallokal : "vallokalen") + "</b>.</div>").openOn(map);
                    return;
                }}
                
                var pollLatlng = L.latLng(data.Lok_Lat, data.Lok_Lon);
                var ptClick = turf.point([clickLatlng.lng, clickLatlng.lat]);
                var pt2 = turf.point([pollLatlng.lng, pollLatlng.lat]);
                
                var closestLokal = null;
                var closestDist = Infinity;
                lokalerData.forEach(function(loc) {{
                    var ptLoc = turf.point([loc[1], loc[0]]);
                    var d = turf.distance(ptClick, ptLoc, {{units: 'kilometers'}});
                    if(d < closestDist) {{ closestDist = d; closestLokal = loc; }}
                }});

                var fvKmNum = turf.distance(ptClick, pt2, {{units: 'kilometers'}});
                var closerInfoHtml = "";
                
                var currentLokalClean = (data.Vallokal || "").trim().toLowerCase();
                var closestLokalClean = (closestLokal ? closestLokal[2] : "").trim().toLowerCase();

                if (closestLokal && currentLokalClean !== closestLokalClean && closestDist < (fvKmNum - 0.05)) {{
                    closerInfoHtml = `<div style="font-size:12px; color:#e74c3c; margin-top:6px; margin-bottom:4px; line-height: 1.2; font-weight: bold;">(Observera: <b>${{closestLokal[2]}}</b> ligger närmare, endast ${{closestDist.toFixed(2)}} km bort)</div>`;
                }}
                
                L.polyline([clickLatlng, pollLatlng], {{color: '#2c3e50', weight: 3, dashArray: '5, 10', interactive: false}}).addTo(analysisGroup);
                L.circleMarker(clickLatlng, {{radius: 5, color: 'black', fillColor: 'white', fillOpacity: 1, interactive: false}}).addTo(analysisGroup);
                L.circleMarker(pollLatlng, {{radius: 8, color: 'white', fillColor: '#8e44ad', fillOpacity: 0.9, weight: 2, interactive: false}}).addTo(analysisGroup);
                
                var fvKm = fvKmNum.toFixed(2);
                var walkTime = Math.round((fvKmNum * 1.3) / 5 * 60);  
                var bikeTime = Math.round((fvKmNum * 1.2) / 15 * 60); 
                var carTime = Math.round((fvKmNum * 1.3) / 40 * 60);  
                
                var walkBuffer = turf.buffer(pt2, 0.32, {{units: 'kilometers'}}); 
                var bikeBuffer = turf.buffer(pt2, 1.0, {{units: 'kilometers'}});  
                var carBuffer = turf.buffer(pt2, 2.5, {{units: 'kilometers'}});   
                
                L.geoJSON(carBuffer, {{interactive: false, style: {{color: '#e74c3c', fillOpacity: 0.05, weight: 1, dashArray: '3,3'}}}}).addTo(analysisGroup);
                L.geoJSON(bikeBuffer, {{interactive: false, style: {{color: '#f39c12', fillOpacity: 0.1, weight: 1, dashArray: '3,3'}}}}).addTo(analysisGroup);
                L.geoJSON(walkBuffer, {{interactive: false, style: {{color: '#27ae60', fillOpacity: 0.15, weight: 1, dashArray: '3,3'}}}}).addTo(analysisGroup);
                
                var totalDist = 0, countWalk = 0, countBike = 0, countCar = 0;
                var distPts = ptsByDistrikt[matchId] || [];
                distPts.forEach(p => {{
                    totalDist += p[2];
                    var pt = turf.point([p[1], p[0]]);
                    if (turf.booleanPointInPolygon(pt, walkBuffer)) countWalk += p[2];
                    else if (turf.booleanPointInPolygon(pt, bikeBuffer)) countBike += p[2];
                    if (turf.booleanPointInPolygon(pt, carBuffer)) countCar += p[2];
                }});
                
                countBike += countWalk;
                
                var pctWalk = totalDist > 0 ? Math.round((countWalk/totalDist)*100) : 0;
                var pctBike = totalDist > 0 ? Math.round((countBike/totalDist)*100) : 0;
                var pctCar = totalDist > 0 ? Math.round((countCar/totalDist)*100) : 0;
                
                var shortDistriktNamn = data.NAMN.split('(')[0].trim();

                var html = `
                <div style="font-family:sans-serif; width: 280px; padding-top: 5px;">
                    <h6 style="color:#0570b0;font-weight:bold;border-bottom:1px solid #ccc;padding-bottom:5px; margin-bottom: 5px;">📍 Rutt till ${{data.Vallokal}} <br><span style="font-size:12px; font-weight:normal; color:#555;">(${{shortDistriktNamn}})</span></h6>
                    <b>Fågelvägen:</b> ${{fvKm}} km
                    ${{closerInfoHtml}}
                    <table style="width:100%; margin-top:8px; font-size:13px; margin-bottom: 10px;">
                        <tr><td>🚶 Gång (5 km/h):</td><td style="text-align:right; font-weight:bold; color:#27ae60;">~${{walkTime}} min</td></tr>
                        <tr><td>🚲 Cykel (15 km/h):</td><td style="text-align:right; font-weight:bold; color:#f39c12;">~${{bikeTime}} min</td></tr>
                        <tr><td>🚗 Bil (40 km/h):</td><td style="text-align:right; font-weight:bold; color:#e74c3c;">~${{carTime}} min</td></tr>
                    </table>
                    <h5 style="color:#8e44ad;font-weight:bold;border-bottom:1px solid #ccc;padding-bottom:5px;margin-bottom:5px;font-size:16px;">⏱️ Nåbarhetsfångst (5 min)</h5>
                    <span style="font-size:11px;color:#555;">Av distriktets ${{totalDist.toLocaleString('sv-SE')}} röstberättigade (Prel. 2025) når:</span>
                    <table style="width:100%; margin-top:3px; font-size:13px;">
                        <tr><td>🚶 Gång:</td><td style="text-align:right;"><b>${{countWalk.toLocaleString('sv-SE')}} st</b> (${{pctWalk}}%)</td></tr>
                        <tr><td>🚲 Cykel:</td><td style="text-align:right;"><b>${{countBike.toLocaleString('sv-SE')}} st</b> (${{pctBike}}%)</td></tr>
                        <tr><td>🚗 Bil:</td><td style="text-align:right;"><b>${{countCar.toLocaleString('sv-SE')}} st</b> (${{pctCar}}%)</td></tr>
                    </table>
                </div>`;
                
                L.popup({{maxWidth: 320, offset: [0, -80], autoPanPadding: [50, 50]}}).setLatLng(clickLatlng).setContent(html).openOn(map);
            }}

            try {{
                var drawnItems = new L.FeatureGroup(); map.addLayer(drawnItems);
                var drawControl = new L.Control.Draw({{ draw: {{ polyline: false, marker: false, circlemarker: false, circle: false, polygon: {{ shapeOptions: {{ color: '#9b59b6', weight: 2, fillOpacity: 0.3 }} }}, rectangle: {{ shapeOptions: {{ color: '#9b59b6', weight: 2, fillOpacity: 0.3 }} }} }}, edit: {{ featureGroup: drawnItems }} }});
                map.addControl(drawControl);

                var isDrawingMode = false;
                var drawTimeout;

                map.on('draw:drawstart', function (e) {{ 
                    isDrawingMode = true; 
                    clearTimeout(drawTimeout); 
                }});
                
                map.on('draw:drawstop', function (e) {{ 
                    drawTimeout = setTimeout(function() {{ isDrawingMode = false; }}, 500); 
                }});

                map.on(L.Draw.Event.CREATED, function (e) {{
                    var layer = e.layer;
                    drawnItems.addLayer(layer);

                    var ptsArray = heatPoints.map(p => turf.point([p[1], p[0]], {{count: p[2]}}));
                    var ptsCollection = turf.featureCollection(ptsArray);
                    
                    var poly = layer.toGeoJSON();
                    var ptsWithin = turf.pointsWithinPolygon(ptsCollection, poly);
                    
                    var totalCount = 0;
                    turf.propEach(ptsWithin, function (currentProperties) {{
                        totalCount += currentProperties.count;
                    }});
                    
                    var formattedCount = totalCount.toLocaleString('sv-SE');
                    layer.bindPopup("<div style='font-family:sans-serif; font-size:14px; padding:5px; text-align:center;'><b>Egenritat område</b><hr style='margin:5px 0;'><span style='color:#0570b0; font-size:18px; font-weight:bold;'>" + formattedCount + "</span><br>Röstberättigade personer 18+ år (Prel. 2025)</div>").openPopup();
                }});

                document.getElementById('opacitySlider').addEventListener('input', function(e) {{
                    var val = parseFloat(e.target.value);
                    document.getElementById('opacityVal').innerText = Math.round(val * 100) + '%';
                    applyFilters(); 
                }});

                function bindPolygonEvents() {{
                    // Låt inte gränslinjerna sno musklick!
                    map.eachLayer(function(layer) {{
                        if (layer.options && layer.options.className && layer.options.className.includes('border-polygon')) {{
                            if (layer._path) layer._path.style.pointerEvents = 'none'; 
                        }}
                    }});

                    // STARTA UPP KARTAN MED FILTER (som ritar ut allt i det kombinerade lagret)
                    applyFilters();

                    map.eachLayer(function(layer) {{
                        if (layer.feature && layer.feature.properties && layer.feature.properties.MATCH_ID) {{
                            if (layer.options && layer.options.className && layer.options.className.includes('valdistrikt-polygon')) {{
                                let matchId = layer.feature.properties.MATCH_ID;
                                let data = valData[matchId];
                                window.valPolygons[matchId] = layer.toGeoJSON();
                                
                                if (data && !layer.filteredOut) {{
                                    layer.bindTooltip(getCleanTooltip(data, currentActiveVariable), {{sticky: true, direction: 'auto', className: 'custom-tooltip-wrapper', opacity: 1.0}});
                                }}

                                layer.on('mouseover', function(e) {{
                                    if (isDrawingMode || analysisMode || layer.filteredOut) return; 
                                    
                                    if (analysisMode) {{
                                        layer.setTooltipContent(`<div class="val-tooltip" style="font-weight:bold; font-size:14px; padding:6px;">${{data.NAMN}}</div>`);
                                    }} else {{
                                        layer.setTooltipContent(getCleanTooltip(data, currentActiveVariable));
                                    }}

                                    var currentOpacity = parseFloat(document.getElementById('opacitySlider').value);
                                    var hoverOp = currentActiveVariable === 'Granser' ? 0.3 : Math.min(1.0, currentOpacity + 0.2);
                                    this.setStyle({{ weight: 5, color: '#ff0000', fillOpacity: hoverOp }});
                                    if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) this.bringToFront();
                                }});
                                
                                layer.on('mouseout', function(e) {{
                                    if (layer.filteredOut) return;
                                    this.setStyle({{ weight: layer.defaultStyle.weight, color: layer.defaultStyle.color, fillOpacity: layer.defaultStyle.fillOpacity }});
                                }});

                                layer.on('click', function(e) {{
                                    if (isDrawingMode || layer.filteredOut) return;
                                    
                                    if (analysisMode) {{
                                        runAccessibilityAnalysis(e.latlng, matchId, layer);
                                        return;
                                    }}
                                    
                                    if (showGraphOnClick) showInfoPanel(matchId);
                                    map.fitBounds(layer.getBounds(), {{padding: [50, 50], maxZoom: 14}});
                                }});
                            }}
                        }}
                    }});
                }}
                
                setTimeout(bindPolygonEvents, 1000);
                
                document.getElementById('btn-reset').addEventListener('click', function() {{ 
                    // 1. Återställ Kamera & Sökbox
                    map.setView([58.4102, 15.6216], 11); 
                    closeInfoPanel(); 
                    document.getElementById('searchDistrikt').value = '';
                    document.getElementById('searchResultBox').style.display = 'none';
                    
                    // 2. Töm Ritverktyg och Nåbarhet
                    drawnItems.clearLayers(); 
                    analysisMode = false; 
                    analysisGroup.clearLayers();
                    coverageGroup.clearLayers();
                    if(heatLayerOutside) map.removeLayer(heatLayerOutside);
                    map.closePopup(); 
                    document.getElementById('btn-measure').classList.remove('btn-info'); 
                    document.getElementById('btn-measure').classList.add('btn-outline-info'); 
                    map._container.style.cursor = ''; 
                    
                    // 3. Nollställ Dropdown och Snabbfilter
                    currentValkrets = 'ALLA';
                    document.getElementById('valkretsSelect').value = 'ALLA';
                    currentFilter = 'NONE';
                    setFilterBtnActive(null);
                    
                    // 4. Nollställ Opacitet till 60%
                    document.getElementById('opacitySlider').value = 0.60;
                    document.getElementById('opacityVal').innerText = '60%';
                    
                    // 5. Bocka ur alla Platser & Infrastruktur
                    var toggles = [
                        {{id: 'toggleVarmekarta', layer: heatLayerObj}},
                        {{id: 'toggleKluster', layer: clusterLayerObj}},
                        {{id: 'toggleTrakter', layer: traktLayerObj}},
                        {{id: 'toggleLokaler', layer: lokalerLayerObj}},
                        {{id: 'togglePOI', layer: poiLayerObj}},
                        {{id: 'toggleTransport', layer: transportLayerObj}},
                        {{id: 'toggleVatten', layer: vattenLayerObj}}
                    ];
                    toggles.forEach(t => {{
                        var el = document.getElementById(t.id);
                        if (el) el.checked = false;
                        if(map.hasLayer(t.layer)) map.removeLayer(t.layer);
                    }});
                    
                    // 6. Sätt standard bakgrundskarta (Blek)
                    document.getElementById('basemapSelect').value = 'blek';
                    map.addLayer(tileBlek);
                    map.removeLayer(tileFarg);
                    map.removeLayer(tileFlyg);
                    currentBorderColor = '#2c3e50';
                    
                    // 7. Sätt tillbaka till "Valdeltagande" som standardyta
                    var defBtn = document.getElementById('t_' + currentActiveVariable.toLowerCase()) || document.getElementById('t_valdeltagande') || document.getElementById('t_hushall');
                    if (defBtn) defBtn.checked = true;
                    
                    // 8. Tvinga kartan att rita om allt från grunden med våra nollställda värden
                    applyFilters();
                    
                    // Återställ tooltips (tvingad refresh)
                    map.eachLayer(function(layer) {{
                        if (layer.options && layer.options.className && layer.options.className.includes('valdistrikt-polygon')) {{
                            if (layer.feature && layer.feature.properties && layer.feature.properties.MATCH_ID) {{
                                let data = valData[layer.feature.properties.MATCH_ID];
                                if (data) layer.setTooltipContent(getCleanTooltip(data, currentActiveVariable));
                            }}
                        }}
                    }});
                }});
            }} catch(e) {{ console.error("Fel vid uppsättning av event listeners:", e); }}
        }});
    </script>
    """

    m.get_root().html.add_child(folium.Element(ui_html))
    html_out_path = os.path.join(moder_mapp, OUT_HTML_NAME)
    m.save(html_out_path)
    print(f"\n🎉 KLAR! Kartan sparades framgångsrikt som:\n➡️  {html_out_path}")
    print("\n💡 Om du startar Live Server nu, se till att du startar den från 'modermappen' och klickar på 'Valdeltagande_2022.html'!")

except Exception as e:
    print("\n❌ Ett fel inträffade under genereringen:")
    traceback.print_exc()