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
import re

print("Startar kartgenerering för Gränsanalys 2022 vs 2026...")

# =====================================================================
# 0. ANPASSAD JSON ENCODER
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
# 1. SETUP & MAPPSTRUKTUR
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

OUT_HTML_NAME = 'Valanalys_Intern_2026.html'

def fix_text(text):
    if not isinstance(text, str): return text
    
    # 1. Försök rädda text som felaktigt tolkats som latin-1 istället för utf-8
    try:
        text = text.encode('latin1').decode('utf-8')
    except Exception:
        pass
        
    # 2. Hårdkodad fallback för vanliga Windows/Excel-fel
    encoding_fix = {
        'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 
        'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö', 
        'Ã©': 'é', 'Ã‰': 'É', 
        '\xc3\xa5': 'å', '\xc3\xa4': 'ä', '\xc3\xb6': 'ö',
        '\xc3\x85': 'Å', '\xc3\x84': 'Ä', '\xc3\x96': 'Ö',
        '\xc3\xa9': 'é', '\xc3\x89': 'É'
    }
    for bad, good in encoding_fix.items():
        text = text.replace(bad, good)
        
    return text.strip()

def normalize_id(val):
    if pd.isna(val): return 'UNKNOWN'
    if isinstance(val, float) and val.is_integer():
        val = int(val)
    s = str(val).replace('.0', '').replace('-', '').replace(' ', '').strip()
    s = ''.join(filter(str.isdigit, s)) # Tvinga fram enbart siffror
    if len(s) == 7 and s.startswith('58'):
        s = '0' + s
    return s if s else 'UNKNOWN'

def safe_str(val, default='Information saknas'):
    if pd.isna(val): return default
    return str(val).strip()

def safe_num(val, default=0):
    try:
        if pd.isna(val): return default
        if isinstance(val, str):
            val = val.replace(' ', '').replace('\xa0', '').replace(',', '.')
        return float(val)
    except:
        return default

# Hjälpfunktioner för att stenhårt tvinga fram rätt kolumner (case-insensitive & osynliga mellanslag)
def find_column(df, possible_names):
    cols_upper = {str(c).strip().upper(): c for c in df.columns}
    for name in possible_names:
        if name in cols_upper:
            return cols_upper[name]
    return None

def get_exact_namn_col(df):
    return find_column(df, ['NAMN', 'VALDISTRIKT', 'VALDISTRIKTSNAMN'])

def get_id_col(df):
    return find_column(df, ['VD_KOD', 'VDKOD', 'VALDISTRIKTSKOD', 'VALDISTRIKTKOD', 'KODEN', 'KOD', 'LÄNKOMMUNKOD', 'LKFV', 'ID', 'OBJECTID'])

def get_geo_namn_col(df):
    # Prioritera riktiga distriktsnamn över generiska 'NAMN' i kartfiler för att slippa få med Valkrets
    return find_column(df, ['VD_NAMN', 'VDNAMN', 'VALDISTRIKTSNAMN', 'VALDISTRIKT', 'NAMN'])

def get_coord_col(df, is_x):
    cands = ['X', 'X_KOORD', 'X-KOORD', 'LONG', 'LONGITUDE', 'LONGITUD', 'LNG'] if is_x else ['Y', 'Y_KOORD', 'Y-KOORD', 'LAT', 'LATITUDE', 'LATITUD']
    col = find_column(df, cands)
    if not col:
        # Fallback partial match
        for c in df.columns:
            c_up = str(c).strip().upper()
            if is_x and ('LONG' in c_up or c_up.startswith('X')): return c
            if not is_x and ('LAT' in c_up or c_up.startswith('Y')): return c
    return col

def clean_for_match(s):
    if not isinstance(s, str): return ''
    s = s.upper().replace(' ', '').replace('-', '')
    return s

# Intelligent namn-matchning för "Ulrika" vs "Ulrika (Ulrika)"
def fuzzy_name_match(geo_name, excel_names_dict):
    if not isinstance(geo_name, str): return np.nan
    x_up = geo_name.strip().upper()
    x_clean = clean_for_match(x_up)
    
    # 1. Exakt matchning
    if x_up in excel_names_dict: return excel_names_dict[x_up]
    
    for ex_up, ex_real in excel_names_dict.items():
        ex_clean = clean_for_match(ex_up)
        
        # 2. Ignorera felaktiga mellanslag och bindestreck
        if x_clean == ex_clean:
            return ex_real
        # 3. Ignorera parentestillägg i Excel ("ULRIKA" vs "ULRIKA (ULRIKA)")
        if ex_clean.startswith(x_clean + "(") or x_clean.startswith(ex_clean + "("):
            return ex_real
            
    return np.nan

try:
    # =====================================================================
    # 2. LÄS IN GEOGRAFI 2022 OCH 2026 OCH SÄKRA KOLUMNNAMN FRÅN EXCEL
    # =====================================================================
    print("\nLaddar geografi för 2022 och 2026...")

    vd_path_22 = os.path.join(kart_filer_dir, 'Valkarta2022.geojson')
    vd_path_26 = os.path.join(kart_filer_dir, 'Valkarta2026.geojson')

    # Tvingar utf-8 inläsning för att undvika att svenska tecken blir korrupta i Windows
    gdf_22 = gpd.read_file(vd_path_22, encoding='utf-8') if os.path.exists(vd_path_22) else gpd.GeoDataFrame()
    gdf_26 = gpd.read_file(vd_path_26, encoding='utf-8') if os.path.exists(vd_path_26) else gpd.GeoDataFrame()

    for gdf in [gdf_22, gdf_26]:
        if not gdf.empty:
            name_col = get_geo_namn_col(gdf)
            gdf['GEO_NAMN'] = gdf[name_col].apply(fix_text) if name_col else 'Okänt distrikt i kartan'
            
            id_col = get_id_col(gdf)
            gdf['MATCH_ID'] = gdf[id_col].apply(normalize_id) if id_col else gdf.index.astype(str)

    print("\nHämtar officiella namn från Excel (tvingar kolumn: 'Namn')...")
    valdistrikt_excel_path = os.path.join(excel_filer_dir, 'Valdistrikt_valkrets.xlsx')
    df_vd_2022 = pd.DataFrame()
    df_vd_2026 = pd.DataFrame()
    
    if os.path.exists(valdistrikt_excel_path):
        xls = pd.ExcelFile(valdistrikt_excel_path)
        sheet_22 = next((s for s in xls.sheet_names if '2022' in s and 'DISTRIKT' in s.upper()), 'Valdistrikt2022')
        sheet_26 = next((s for s in xls.sheet_names if '2026' in s and 'DISTRIKT' in s.upper()), 'Valdistrikt2026')
        
        try: df_vd_2022 = pd.read_excel(valdistrikt_excel_path, sheet_name=sheet_22)
        except: pass
        try: df_vd_2026 = pd.read_excel(valdistrikt_excel_path, sheet_name=sheet_26)
        except: pass

    # ================= Mappa in RÄTT namn för 2022 =================
    dict_namn_22 = {}
    if not df_vd_2022.empty:
        id_col_22 = get_id_col(df_vd_2022)
        namn_col_22 = get_exact_namn_col(df_vd_2022)
        if id_col_22 and namn_col_22:
            df_vd_2022['MATCH_ID'] = df_vd_2022[id_col_22].apply(normalize_id)
            df_vd_2022['OFFICIELLT_NAMN_22'] = df_vd_2022[namn_col_22].apply(fix_text)
            dict_namn_22 = dict(zip(df_vd_2022['MATCH_ID'], df_vd_2022['OFFICIELLT_NAMN_22']))

    if not gdf_22.empty:
        gdf_22['OFFICIELLT_NAMN_22'] = gdf_22['MATCH_ID'].map(dict_namn_22)
        
        # Fuzzy fallback om ID-match misslyckas (Matcha GEO_NAMN mot OFFICIELLT_NAMN_22 via Fuzzy-funktion)
        dict_excel_names_upper_22 = {v.upper(): v for k, v in dict_namn_22.items()}
        missing_mask_22 = gdf_22['OFFICIELLT_NAMN_22'].isna()
        if missing_mask_22.any():
            gdf_22.loc[missing_mask_22, 'OFFICIELLT_NAMN_22'] = gdf_22.loc[missing_mask_22, 'GEO_NAMN'].apply(lambda x: fuzzy_name_match(x, dict_excel_names_upper_22))
            
        gdf_22['OFFICIELLT_NAMN_22'] = gdf_22['OFFICIELLT_NAMN_22'].fillna(gdf_22['GEO_NAMN'])

    # ================= Mappa in RÄTT namn för 2026 =================
    dict_namn_26 = {}
    if not df_vd_2026.empty:
        id_col_26 = get_id_col(df_vd_2026)
        namn_col_26 = get_exact_namn_col(df_vd_2026)
        if id_col_26 and namn_col_26:
            df_vd_2026['MATCH_ID'] = df_vd_2026[id_col_26].apply(normalize_id)
            df_vd_2026['OFFICIELLT_NAMN_26'] = df_vd_2026[namn_col_26].apply(fix_text)
            dict_namn_26 = dict(zip(df_vd_2026['MATCH_ID'], df_vd_2026['OFFICIELLT_NAMN_26']))

    if not gdf_26.empty:
        gdf_26['OFFICIELLT_NAMN_26'] = gdf_26['MATCH_ID'].map(dict_namn_26)
        
        dict_excel_names_upper_26 = {v.upper(): v for k, v in dict_namn_26.items()}
        missing_mask_26 = gdf_26['OFFICIELLT_NAMN_26'].isna()
        if missing_mask_26.any():
            gdf_26.loc[missing_mask_26, 'OFFICIELLT_NAMN_26'] = gdf_26.loc[missing_mask_26, 'GEO_NAMN'].apply(lambda x: fuzzy_name_match(x, dict_excel_names_upper_26))
            
        gdf_26['OFFICIELLT_NAMN_26'] = gdf_26['OFFICIELLT_NAMN_26'].fillna(gdf_26['GEO_NAMN'])

    # Läs in transport & vatten
    transport_path = os.path.join(kart_filer_dir, 'transportleder.geojson')
    transport_geojson = gpd.read_file(transport_path).to_crs(4326).__geo_interface__ if os.path.exists(transport_path) else {"type": "FeatureCollection", "features": []}
    transport_str = json.dumps(transport_geojson, cls=NumpyPandasEncoder)

    vatten_path = os.path.join(kart_filer_dir, 'vattendrag.geojson')
    vatten_geojson = gpd.read_file(vatten_path).to_crs(4326).__geo_interface__ if os.path.exists(vatten_path) else {"type": "FeatureCollection", "features": []}
    vatten_str = json.dumps(vatten_geojson, cls=NumpyPandasEncoder)

    # =====================================================================
    # 3. KORSKÖR ADRESSPUNKTER MED BÅDA KARTORNA OCH BYGG VERKTYGSTOOLTIPS
    # =====================================================================
    print("\nUtför geografisk korskörning av adresser mellan 22 och 26...")
    
    adress_file_xlsx = os.path.join(excel_filer_dir, 'adresspunkter_sept25.xlsx')
    adress_file_csv = os.path.join(excel_filer_dir, 'adresspunkter_sept25.csv')
    df_adress = pd.read_excel(adress_file_xlsx) if os.path.exists(adress_file_xlsx) else (pd.read_csv(adress_file_csv) if os.path.exists(adress_file_csv) else pd.DataFrame())

    changed_addresses_list = []
    cluster_points = []
    trakt_list = []
    agg_rost_26 = pd.DataFrame()

    if not df_adress.empty and not gdf_22.empty and not gdf_26.empty:
        # Tvätta koordinater stenhårt
        x_col_adr = get_coord_col(df_adress, True)
        y_col_adr = get_coord_col(df_adress, False)
        if x_col_adr and y_col_adr:
            df_adress['X'] = pd.to_numeric(df_adress[x_col_adr].astype(str).str.replace(',', '.').str.replace(' ', ''), errors='coerce')
            df_adress['Y'] = pd.to_numeric(df_adress[y_col_adr].astype(str).str.replace(',', '.').str.replace(' ', ''), errors='coerce')
            
        df_adress = df_adress.dropna(subset=['X', 'Y'])
        
        # Säkra beladress och fastighet oavsett skiftläge och applicera tecken-tvätten
        df_adress['beladress_clean'] = df_adress.get('beladress', df_adress.get('BELADRESS', df_adress.get('Adress', 'Okänd'))).apply(lambda x: fix_text(str(x)) if pd.notnull(x) else 'Okänd')
        df_adress['fastighet_clean'] = df_adress.get('fastighet', df_adress.get('FASTIGHET', df_adress.get('Fastighet', 'Okänd'))).apply(lambda x: fix_text(str(x)) if pd.notnull(x) else 'Okänd')
        df_adress['rostberattigade_clean'] = pd.to_numeric(df_adress.get('antal_rostberattigade', df_adress.get('ANTAL_ROSTBERATTIGADE', 0)), errors='coerce')
        
        # ================= NY FUNKTION: Aggregera på Trakt/Kvarter =================
        # Regex för att klippa av fastighetsnamnet FÖRE första siffran. "Olofstorp 1:16" -> "Olofstorp"
        df_adress['trakt'] = df_adress['fastighet_clean'].astype(str).str.extract(r'^([^\d]+)')[0].str.strip()
        valid_adress = df_adress[df_adress['rostberattigade_clean'] > 0].copy()
        
        # Summera röstberättigade och ta ut mittpunkten per trakt
        if not valid_adress.empty:
            trakt_agg = valid_adress.groupby('trakt').agg({'X': 'mean', 'Y': 'mean', 'rostberattigade_clean': 'sum'}).reset_index()
            trakt_gdf = gpd.GeoDataFrame(trakt_agg, geometry=gpd.points_from_xy(trakt_agg.X, trakt_agg.Y), crs="EPSG:3006").to_crs(4326)
            for idx, row in trakt_gdf.iterrows():
                if pd.notnull(row.geometry.y) and pd.notnull(row.geometry.x) and row['trakt'] and row['trakt'] != 'Okänd':
                    trakt_list.append([
                        float(row.geometry.y), float(row.geometry.x), 
                        safe_str(row['trakt']), int(row['rostberattigade_clean'])
                    ])
        
        adress_gdf = gpd.GeoDataFrame(df_adress, geometry=gpd.points_from_xy(df_adress.X, df_adress.Y), crs="EPSG:3006")
        
        # Spatial join 2022 (Direkt med det säkrade Excel-namnet OFFICIELLT_NAMN_22)
        vd_22_3006 = gdf_22.to_crs(epsg=3006)
        join_22 = gpd.sjoin(adress_gdf, vd_22_3006, how="inner", predicate="within")
        join_22 = join_22[['beladress_clean', 'fastighet_clean', 'rostberattigade_clean', 'MATCH_ID', 'OFFICIELLT_NAMN_22']].rename(columns={'MATCH_ID': 'ID_22', 'OFFICIELLT_NAMN_22': 'NAMN_22'})
        
        # Spatial join 2026 (Direkt med det säkrade Excel-namnet OFFICIELLT_NAMN_26)
        vd_26_3006 = gdf_26.to_crs(epsg=3006)
        join_26 = gpd.sjoin(adress_gdf, vd_26_3006, how="inner", predicate="within")
        join_26 = join_26[['MATCH_ID', 'OFFICIELLT_NAMN_26', 'geometry']].rename(columns={'MATCH_ID': 'ID_26', 'OFFICIELLT_NAMN_26': 'NAMN_26'})
        
        # Aggregera Röstberättigade per 2026-distrikt
        agg_rost_26 = join_26.join(df_adress['rostberattigade_clean']).groupby('ID_26')['rostberattigade_clean'].sum().reset_index()
        agg_rost_26.rename(columns={'ID_26': 'MATCH_ID', 'rostberattigade_clean': 'Beraknad_Rostberattigade'}, inplace=True)
        
        # Sätt ihop och jämför PÅ NAMN för att identifiera ändringar
        diff_df = join_22.join(join_26, how='inner')
        diff_df['rostberattigade_clean'] = diff_df['rostberattigade_clean'].fillna(0)
        
        diff_df['NAMN_22_CMP'] = diff_df['NAMN_22'].astype(str).str.strip().str.upper()
        diff_df['NAMN_26_CMP'] = diff_df['NAMN_26'].astype(str).str.strip().str.upper()
        
        # Kontrollera om de har bytt namn
        changed_mask = diff_df['NAMN_22_CMP'] != diff_df['NAMN_26_CMP']
        changed_df = diff_df[changed_mask].copy()
        
        # Förbered adresser för CSV (Endast de ändrade)
        if not changed_df.empty:
            changed_df_4326 = gpd.GeoDataFrame(changed_df, geometry='geometry', crs="EPSG:3006").to_crs(4326)
            for idx, row in changed_df_4326.iterrows():
                if row['rostberattigade_clean'] > 0:
                    changed_addresses_list.append({
                        'lat': float(row.geometry.y),
                        'lng': float(row.geometry.x),
                        'adress': safe_str(row['beladress_clean']),
                        'fastighet': safe_str(row['fastighet_clean']),
                        'rostberattigade': int(row['rostberattigade_clean']),
                        'fran_distrikt': safe_str(row['NAMN_22']),
                        'till_distrikt': safe_str(row['NAMN_26'])
                    })

        # Bygg generella adresser för kartan (Nu med full tooltip för ALLA)
        valid_diff = diff_df[diff_df['rostberattigade_clean'] > 0]
        if not valid_diff.empty:
            valid_diff_4326 = gpd.GeoDataFrame(valid_diff, geometry='geometry', crs="EPSG:3006").to_crs(4326)
            for idx, row in valid_diff_4326.iterrows():
                y, x = float(row.geometry.y), float(row.geometry.x)
                if not math.isnan(y) and not math.isnan(x):
                    cluster_points.append([
                        y, x, str(row['ID_26']), 
                        safe_str(row['beladress_clean']), 
                        safe_str(row['fastighet_clean']), 
                        int(row['rostberattigade_clean']),
                        safe_str(row['NAMN_22']),
                        safe_str(row['NAMN_26'])
                    ])

    changed_json_str = json.dumps(changed_addresses_list, cls=NumpyPandasEncoder)
    cluster_points_json_str = json.dumps(cluster_points, cls=NumpyPandasEncoder)
    trakt_json_str = json.dumps(trakt_list, cls=NumpyPandasEncoder)

    # =====================================================================
    # 4. SAMMANSTÄLL POI, VALLOKALER OCH HUVUDKARTAN (2026)
    # =====================================================================
    gdf_merged = gdf_26.copy()
    
    df_lokaler = pd.DataFrame()
    df_poi = pd.DataFrame()
    lokaler_list = []
    poi_list = []

    if os.path.exists(valdistrikt_excel_path):
        try: df_lokaler = pd.read_excel(valdistrikt_excel_path, sheet_name='Vallokaler2026')
        except Exception: pass
        try: df_poi = pd.read_excel(valdistrikt_excel_path, sheet_name='Ovriga_platser')
        except Exception: pass
        
        # Bygg Vallokaler - FRISTÅENDE från ytorna så att ingen försvinner!
        if not df_lokaler.empty:
            x_col = get_coord_col(df_lokaler, True)
            y_col = get_coord_col(df_lokaler, False)
            if x_col and y_col:
                df_lokaler['X_num'] = pd.to_numeric(df_lokaler[x_col].astype(str).str.replace(',', '.').str.replace(' ', ''), errors='coerce')
                df_lokaler['Y_num'] = pd.to_numeric(df_lokaler[y_col].astype(str).str.replace(',', '.').str.replace(' ', ''), errors='coerce')
                valid_lok = df_lokaler.dropna(subset=['X_num', 'Y_num']).copy()
                
                if not valid_lok.empty:
                    if valid_lok['Y_num'].mean() < 100:
                        lok_gdf = gpd.GeoDataFrame(valid_lok, geometry=gpd.points_from_xy(valid_lok['X_num'], valid_lok['Y_num']), crs="EPSG:4326")
                    else:
                        lok_gdf = gpd.GeoDataFrame(valid_lok, geometry=gpd.points_from_xy(valid_lok['X_num'], valid_lok['Y_num']), crs="EPSG:3006").to_crs(epsg=4326)
                    
                    lokal_id_col = get_id_col(df_lokaler)
                    lokal_namn_col = get_exact_namn_col(df_lokaler)
                    
                    for idx, row in valid_lok.iterrows():
                        y = lok_gdf.loc[idx].geometry.y
                        x = lok_gdf.loc[idx].geometry.x
                        if not math.isnan(y) and not math.isnan(x):
                            m_id = normalize_id(row.get(lokal_id_col)) if lokal_id_col else ''
                            dist_namn = dict_namn_26.get(m_id)
                            if not dist_namn and lokal_namn_col:
                                dist_namn = safe_str(row.get(lokal_namn_col))
                            if not dist_namn:
                                dist_namn = safe_str(row.get('VALDISTRIKT', 'Okänt distrikt'))
                                
                            lokaler_list.append([
                                float(y), float(x),
                                safe_str(row.get('LOKAL', row.get('Vallokal', 'Vallokal'))),
                                safe_str(row.get('ADRESS1', row.get('Adress', ''))),
                                m_id,
                                dist_namn
                            ])

        # POI - TVÄTTAD från svenska kommatecken och med lagad Förtidsröst-hämtning
        if not df_poi.empty:
            x_col_poi = get_coord_col(df_poi, True)
            y_col_poi = get_coord_col(df_poi, False)
            if x_col_poi and y_col_poi:
                df_poi['X_num'] = pd.to_numeric(df_poi[x_col_poi].astype(str).str.replace(',', '.').str.replace(' ', ''), errors='coerce')
                df_poi['Y_num'] = pd.to_numeric(df_poi[y_col_poi].astype(str).str.replace(',', '.').str.replace(' ', ''), errors='coerce')
                valid_poi = df_poi.dropna(subset=['X_num', 'Y_num'])
                if not valid_poi.empty:
                    if valid_poi['Y_num'].mean() < 100:
                        poi_gdf = gpd.GeoDataFrame(valid_poi, geometry=gpd.points_from_xy(valid_poi['X_num'], valid_poi['Y_num']), crs="EPSG:4326")
                    else:
                        poi_gdf = gpd.GeoDataFrame(valid_poi, geometry=gpd.points_from_xy(valid_poi['X_num'], valid_poi['Y_num']), crs="EPSG:3006").to_crs(epsg=4326)
                        
                    for idx, row in poi_gdf.iterrows():
                        namn = safe_str(row.get('Namn', row.get('Plats', 'Intressant Plats')))
                        funktion = safe_str(row.get('Funktion', row.get('Typ', '')))
                        rots = safe_str(row.get('Antal_förtidsröster_2026', row.get('Antal_fortidsroster_2026', safe_str(row.get('Antal_förtidsröster', '0')))))
                        poi_list.append([row.geometry.y, row.geometry.x, namn, funktion, rots])

    # Foga in prelsiffrorna från adresspunkter i Huvudkartan
    if not agg_rost_26.empty:
        gdf_merged = gdf_merged.merge(agg_rost_26, on='MATCH_ID', how='left')

    lokaler_json_str = json.dumps(lokaler_list, cls=NumpyPandasEncoder)
    poi_json_str = json.dumps(poi_list, cls=NumpyPandasEncoder)

    val_data_dict = {}
    if not gdf_merged.empty:
        # Fyll in datan baserat på vårt Lexicon och tillgängliga kolumner
        for idx, row in gdf_merged.iterrows():
            match_id = safe_str(row.get('MATCH_ID', 'Okänt'))
            namn = safe_str(row.get('OFFICIELLT_NAMN_26', 'Område saknar Excel-namn'))
            
            # Smart matchning av 2022 års Röstberättigade & Valdeltagande 
            rostberattigade_22 = None
            valdeltagande_22 = None
            
            if not df_vd_2022.empty:
                match_row_22 = df_vd_2022[df_vd_2022['MATCH_ID'] == match_id]
                
                # FALLBACK: Match by fuzzy name if ID match fails
                if match_row_22.empty and namn != 'Område saknar Excel-namn':
                    namn_col_22 = get_exact_namn_col(df_vd_2022)
                    if namn_col_22:
                        # Här litar vi på vår robusta fuzzy-motor
                        fuzzy_match = fuzzy_name_match(namn, dict_excel_names_upper_22)
                        if pd.notna(fuzzy_match):
                             match_row_22 = df_vd_2022[df_vd_2022[namn_col_22].apply(fix_text) == fuzzy_match]
                    
                if not match_row_22.empty:
                    rb_col = find_column(df_vd_2022, ['RÖSTBERÄTTIGADE', 'ROSTBERATTIGADE', 'RÖSTBERÄTTIGADE 2022', 'ANTAL RÖSTBERÄTTIGADE'])
                    vd_col = find_column(df_vd_2022, ['VALDELTAGANDE', 'VALDELTAGANDE 2022', 'VALDELTAGANDE %'])
                    if rb_col: rostberattigade_22 = safe_num(match_row_22[rb_col].values[0])
                    if vd_col: valdeltagande_22 = safe_num(match_row_22[vd_col].values[0])

            rostberattigade_2025 = safe_num(row.get('Beraknad_Rostberattigade', 0))
            
            val_data_dict[match_id] = {
                'NAMN': namn,
                'Valkrets': safe_str(row.get('Valkrets', 'Saknas')),
                'Vallokal': safe_str(row.get('LOKAL', 'Saknas')),
                'Valdeltagande': round(valdeltagande_22, 1) if valdeltagande_22 and valdeltagande_22 > 0 else None,
                'Rostberattigade': int(rostberattigade_22) if rostberattigade_22 and rostberattigade_22 > 0 else None,
                'Rostberattigade_2025': int(rostberattigade_2025)
            }
        val_data_json_str = json.dumps(val_data_dict, cls=NumpyPandasEncoder)
    else:
        val_data_json_str = "{}"

    # =====================================================================
    # 4. KARTBYGGE
    # =====================================================================
    print("\nGenererar HTML-karta...")

    # TVÄTTA DATUM/TIMESTAMPS INFÖR FOLIUMS INTERNA JSON-EXPORTERING
    for g_df in [gdf_merged, gdf_22]:
        if not g_df.empty:
            for col in g_df.columns:
                if col != 'geometry':
                    if pd.api.types.is_datetime64_any_dtype(g_df[col]):
                        g_df[col] = g_df[col].astype(str)
                    else:
                        g_df[col] = g_df[col].apply(lambda x: str(x) if isinstance(x, (pd.Timestamp, datetime.datetime, datetime.date)) else x)

    m = folium.Map(location=[58.4102, 15.6216], zoom_start=11, tiles=None)

    # Bottenlager: 2026 (Klickbart)
    if not gdf_merged.empty:
        folium.GeoJson(
            gdf_merged, 
            name='Valdistrikt 2026', 
            style_function=lambda feature: {'fillColor': '#bdc3c7', 'color': '#2c3e50', 'weight': 2, 'fillOpacity': 0.6, 'className': 'polygon-layer valdistrikt-polygon'}
        ).add_to(m)

    # Topplager (osynligt tills togglat): 2022 års gränser för diff-analys
    if not gdf_22.empty:
        gdf_22_border = gdf_22.copy()
        folium.GeoJson(
            gdf_22_border,
            name='Gränser 2022',
            style_function=lambda feature: {'fillOpacity': 0, 'color': '#e74c3c', 'weight': 3, 'dashArray': '5, 5', 'className': 'border-2022-layer'}
        ).add_to(m)

    minimap = MiniMap(toggleDisplay=True, position="topleft", zoomLevelOffset=-4, tile_layer="cartodbpositron")
    m.add_child(minimap)

    # =====================================================================
    # 5. INJICERA GYLLENE STANDARDMALL FÖR INTERN ANALYS
    # =====================================================================
    ui_html = f"""
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet-search/3.0.2/leaflet-search.min.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster/dist/MarkerCluster.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster/dist/MarkerCluster.Default.css" />
    <script src="https://unpkg.com/leaflet.markercluster/dist/leaflet.markercluster.js"></script>
    <script src="https://unpkg.com/@turf/turf/turf.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

    <style>
        .header-panel {{ position: fixed; top: 20px; left: 50%; transform: translateX(-50%); z-index: 9999; background: rgba(255,255,255,0.95); padding: 10px 25px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); display: flex; align-items: center; font-family: sans-serif; white-space: nowrap; border-left: 5px solid #e74c3c; }}
        .header-panel img {{ height: 35px; margin-right: 15px; }}
        .header-panel h4 {{ margin: 0; font-weight: bold; color: #2c3e50; font-size: 20px; letter-spacing: 0.5px; }}
        
        .tools-panel {{ position: fixed; bottom: 30px; left: 60px; z-index: 9999; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 330px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; }}
        .layers-panel {{ position: fixed; top: 20px; right: 20px; z-index: 9999; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 340px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; }}
        
        .btn-custom {{ width: 100%; margin-bottom: 8px; text-align: left; font-size: 13px; padding: 6px 12px; font-weight: bold; }}
        .form-check-input {{ transform: scale(1.4); margin-top: 4px; margin-right: 10px; cursor: pointer; }}
        .form-check-label {{ cursor: pointer; font-size: 14px; }}
        
        .legend-container {{ position: fixed; bottom: 30px; left: 400px; z-index: 9998; display: flex; flex-direction: row; flex-wrap: wrap; align-items: flex-end; gap: 10px; pointer-events: none; max-width: calc(100vw - 400px); }}
        .variable-legend {{ pointer-events: auto; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.2); margin: 0; font-family: sans-serif; font-size: 12px; display: none; }}
        .legend-color-box {{ display: inline-block; width: 15px; height: 15px; margin-right: 5px; vertical-align: middle; border: 1px solid #ccc; }}
        
        .val-tooltip {{ background: rgba(255,255,255,0.98); border: 1px solid #ccc; box-shadow: 0 2px 10px rgba(0,0,0,0.2); border-radius: 4px; padding: 10px; color: #333; }}
        .custom-tooltip-wrapper {{ background: transparent; border: none; box-shadow: none; padding: 0; margin: 0; pointer-events: none; }}
        .border-polygon {{ pointer-events: none !important; }}
        
        /* Den gamla 2022 kanten ska inte sno klick */
        .border-2022-layer {{ pointer-events: none !important; display: none; }}
        .show-2022 .border-2022-layer {{ display: block !important; }}
    </style>
    
    <div class="header-panel">
        <img src="Img/Linkopingsloggo.png" alt="Linköping Logotyp" onerror="this.style.display='none'">
        <div>
            <h4>Gränsanalys Val 2026</h4>
            <span style="font-size:11px; color:#e74c3c; font-weight:bold;">INTERNT ARBETSVERKTYG</span>
        </div>
    </div>

    <!-- LEGEND -->
    <div class="legend-container" id="legend-container">
        <div id="legend-Valdeltagande" class="variable-legend"><h6 style="margin-bottom:5px;font-weight:bold;">Valdeltagande 2022 (%)</h6>
            <div><i class="legend-color-box" style="background:#023858"></i> &gt; 90%</div>
            <div><i class="legend-color-box" style="background:#0570b0"></i> 85 - 90%</div>
            <div><i class="legend-color-box" style="background:#74a9cf"></i> 80 - 85%</div>
            <div><i class="legend-color-box" style="background:#bdc9e1"></i> 75 - 80%</div>
            <div><i class="legend-color-box" style="background:#d0d1e6"></i> &lt; 75%</div>
        </div>
        <div id="legend-Rostberattigade" class="variable-legend"><h6 style="margin-bottom:5px;font-weight:bold;">Röstberättigade 2022</h6>
            <div><i class="legend-color-box" style="background:#006d2c"></i> &gt; 2000</div>
            <div><i class="legend-color-box" style="background:#31a354"></i> 1500 - 2000</div>
            <div><i class="legend-color-box" style="background:#74c476"></i> 1000 - 1500</div>
            <div><i class="legend-color-box" style="background:#bae4b3"></i> 500 - 1000</div>
            <div><i class="legend-color-box" style="background:#edf8e9"></i> &lt; 500</div>
        </div>
        <div id="legend-Rostberattigade_2025" class="variable-legend"><h6 style="margin-bottom:5px;font-weight:bold;">Röstberättigade 2026 (Prel)</h6>
            <div><i class="legend-color-box" style="background:#006d2c"></i> &gt; 2000</div>
            <div><i class="legend-color-box" style="background:#31a354"></i> 1500 - 2000</div>
            <div><i class="legend-color-box" style="background:#74c476"></i> 1000 - 1500</div>
            <div><i class="legend-color-box" style="background:#bae4b3"></i> 500 - 1000</div>
            <div><i class="legend-color-box" style="background:#edf8e9"></i> &lt; 500</div>
        </div>
    </div>

    <!-- VERKTYGSPANEL VÄNSTER -->
    <div class="tools-panel">
        <h5 class="fw-bold mb-3 border-bottom pb-2">⚙️ Gränsanalys (22 -> 26)</h5>
        
        <div class="alert alert-warning py-2 px-2 mb-3" style="font-size:12px; line-height:1.4;">
            <i class="fa-solid fa-code-compare"></i> Visar fastigheter/adresser som bytt tillhörighet mellan Valkarta 2022 och Valkarta 2026.
        </div>
        
        <div class="form-check mb-3 p-2 bg-light border rounded">
            <input class="form-check-input" type="checkbox" id="toggleChangedAddr">
            <label class="form-check-label fw-bold text-danger" for="toggleChangedAddr">
                📍 Visa bara flyttade adresser
                <div style="font-size:10px; font-weight:normal; color:#555;">(Röda markörer, döljer blå)</div>
            </label>
        </div>

        <button id="btn-export" class="btn btn-success btn-sm btn-custom mb-3">
            <i class="fa-solid fa-file-csv"></i> Exportera Lista (CSV)
        </button>

        <hr style="margin: 10px 0;">
        
        <h6 class="fw-bold mb-1" style="font-size: 13px;">🔍 Sök Valdistrikt (2026):</h6>
        <input type="text" id="searchDistrikt" list="distriktList" class="form-control mb-2" style="padding: 6px 10px; font-size: 13px;" placeholder="Skriv in namn...">
        <datalist id="distriktList"></datalist>

        <hr style="margin: 10px 0;">
        <button id="btn-reset" class="btn btn-outline-danger btn-sm btn-custom">🔄 Återställ vy</button>
    </div>

    <!-- KONTROLLPANEL HÖGER -->
    <div class="layers-panel">
        <h5 class="fw-bold mb-3 border-bottom pb-2">🗂️ Kartlager</h5>
        
        <h6 class="fw-bold mb-2" style="font-size: 13px;">🗺️ Bakgrundskarta</h6>
        <select id="basemapSelect" class="form-select form-select-sm mb-3" style="font-size: 12px;">
            <option value="blek" selected>Karta: Blek (Standard)</option>
            <option value="farg">Karta: Färgstark</option>
            <option value="flyg">Karta: Flygfoto</option>
        </select>
        
        <hr style="margin: 10px 0;">
        <h6 class="fw-bold mb-2">🔲 Distriktsgränser</h6>
        <div class="form-check mb-1">
            <input class="form-check-input" type="checkbox" id="t_granser_26" checked>
            <label class="form-check-label fw-bold" for="t_granser_26" style="color:#2c3e50;">Gränser 2026 (Svart linje)</label>
        </div>
        <div class="form-check mb-2">
            <input class="form-check-input" type="checkbox" id="t_granser_22">
            <label class="form-check-label fw-bold" for="t_granser_22" style="color:#e74c3c;">Gränser 2022 (Röd streckad linje)</label>
        </div>
        
        <hr style="margin: 10px 0;">
        <h6 class="fw-bold mb-2">📊 Ytor & Analys</h6>
        <div class="form-check mb-1">
            <input class="form-check-input var-toggle" type="radio" name="layerToggle" value="Granser" id="t_granser" checked>
            <label class="form-check-label" for="t_granser">🔲 Endast gränser (Grå yta)</label>
        </div>
        <div class="form-check mb-1">
            <input class="form-check-input var-toggle" type="radio" name="layerToggle" value="Rostberattigade_2025" id="t_rostberattigade_2025">
            <label class="form-check-label" for="t_rostberattigade_2025">📋 Röstberättigade 2026 (Prel)</label>
        </div>
        <div class="form-check mb-1">
            <input class="form-check-input var-toggle" type="radio" name="layerToggle" value="Rostberattigade" id="t_rostberattigade">
            <label class="form-check-label" for="t_rostberattigade">📋 Röstberättigade 2022 (Officiell)</label>
        </div>
        <div class="form-check mb-2">
            <input class="form-check-input var-toggle" type="radio" name="layerToggle" value="Valdeltagande" id="t_valdeltagande">
            <label class="form-check-label" for="t_valdeltagande">🗳️ Valdeltagande 2022 (%)</label>
        </div>

        <div class="p-2 mb-2 bg-light border border-secondary rounded shadow-sm">
            <div class="d-flex justify-content-between align-items-center mb-1">
                <label for="opacitySlider" class="form-label mb-0 fw-bold" style="font-size: 12px; color: #2c3e50;">Fyllnadsfärg (Ytor):</label>
                <span id="opacityVal" class="badge bg-primary" style="font-size: 11px;">60%</span>
            </div>
            <input type="range" class="form-range" id="opacitySlider" min="0" max="1" step="0.05" value="0.60">
        </div>

        <hr style="margin: 10px 0;">
        <h6 class="fw-bold mb-2">📍 Platser & Infrastruktur</h6>
        <div class="form-check mb-1">
            <input class="form-check-input" type="checkbox" id="toggleKluster">
            <label class="form-check-label" for="toggleKluster">🏘️ Adresspunkter 2025 (Alla)</label>
        </div>
        <div class="form-check mb-1">
            <input class="form-check-input" type="checkbox" id="toggleTrakter">
            <label class="form-check-label fw-bold text-primary" for="toggleTrakter">🏘️ Trakter/Kvarter (Summerat)</label>
        </div>
        <div class="form-check mb-1">
            <input class="form-check-input" type="checkbox" id="toggleLokaler" checked>
            <label class="form-check-label" for="toggleLokaler">📍 Vallokaler 2026</label>
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
    </div>

    <script>
        var valData = {val_data_json_str};
        var changedAddresses = {changed_json_str};
        var clusterPoints = {cluster_points_json_str};
        var traktData = {trakt_json_str};
        var lokalerData = {lokaler_json_str};
        var poiData = {poi_json_str};
        var transportData = {transport_str};
        var vattenData = {vatten_str};
        var currentActiveVariable = 'Granser';
        var currentBorderColor = '#2c3e50';

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
            document.body.appendChild(toast);
            setTimeout(() => {{
                if(document.body.contains(toast)) {{
                    toast.style.transition = 'opacity 0.5s ease';
                    toast.style.opacity = '0';
                    setTimeout(() => {{ if(document.body.contains(toast)) toast.remove(); }}, 500);
                }}
            }}, duration);
        }}

        document.addEventListener('DOMContentLoaded', function() {{
            var map_id = Object.keys(window).find(key => key.startsWith('map_'));
            var map = window[map_id];
            
            map.createPane('topMarkersPane'); map.getPane('topMarkersPane').style.zIndex = 660; 
            
            // Hantera 2022-lagret via CSS class-toggle på map-containern
            document.getElementById('t_granser_22').addEventListener('change', function(e) {{
                if (e.target.checked) {{
                    map._container.classList.add('show-2022');
                }} else {{
                    map._container.classList.remove('show-2022');
                }}
            }});
            
            // Klickbar gränslinje för 2026
            document.getElementById('t_granser_26').addEventListener('change', function(e) {{
                applyFilters();
            }});

            // Ladda Sökfältet
            var distriktNames = [];
            Object.values(valData).forEach(function(d) {{
                if(d.NAMN && !distriktNames.includes(d.NAMN)) distriktNames.push(d.NAMN);
            }});
            distriktNames.sort(function(a, b) {{ return a.localeCompare(b, 'sv'); }});
            var dList = document.getElementById('distriktList');
            distriktNames.forEach(function(namn) {{
                var opt = document.createElement('option');
                opt.value = namn;
                dList.appendChild(opt);
            }});

            // Bakgrundskartor
            var tileBlek = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{ attribution: '&copy; CARTO' }}).addTo(map);
            var tileFarg = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ attribution: '&copy; OSM' }});
            var tileFlyg = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ attribution: '&copy; Esri' }});
            
            document.getElementById('basemapSelect').addEventListener('change', function(e) {{
                map.removeLayer(tileBlek); map.removeLayer(tileFarg); map.removeLayer(tileFlyg);
                var isFlyg = false;
                if(e.target.value === 'blek') tileBlek.addTo(map); 
                else if(e.target.value === 'farg') tileFarg.addTo(map);
                else if(e.target.value === 'flyg') {{ tileFlyg.addTo(map); isFlyg = true; }}
                
                currentBorderColor = isFlyg ? '#ffffff' : '#2c3e50';
                applyFilters();
            }});

            function getColor(val, variable) {{
                if (val === null || val === undefined || isNaN(val)) return 'transparent';
                if (variable === 'Valdeltagande') {{ return val > 90 ? '#023858' : val > 85 ? '#0570b0' : val > 80 ? '#74a9cf' : val > 75 ? '#bdc9e1' : '#d0d1e6';
                }} else if (variable === 'Rostberattigade' || variable === 'Rostberattigade_2025') {{ return val > 2000 ? '#006d2c' : val > 1500 ? '#31a354' : val > 1000 ? '#74c476' : val > 500 ? '#bae4b3' : '#edf8e9';
                }}
                return 'transparent';
            }}

            // Läs in lagerevent bara EN gång så Tooltipen inte försvinner
            map.eachLayer(function(layer) {{
                if (layer.options && layer.options.className && layer.options.className.includes('valdistrikt-polygon')) {{
                    if (layer.feature && layer.feature.properties && layer.feature.properties.MATCH_ID) {{
                        let matchId = layer.feature.properties.MATCH_ID;
                        let data = valData[matchId];
                        if (data && !layer._eventsBound) {{
                            layer.bindTooltip("", {{sticky: true, direction: 'auto', className: 'custom-tooltip-wrapper'}});
                            
                            layer.on('mouseover', function(e) {{
                                var op = document.getElementById('opacitySlider').value;
                                this.setStyle({{ weight: 5, color: '#3498db', fillOpacity: Math.min(1.0, parseFloat(op) + 0.2) }});
                                if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) this.bringToFront();
                            }});
                            
                            layer.on('mouseout', function(e) {{
                                var bWeight = document.getElementById('t_granser_26').checked ? 2 : 0;
                                var op = document.getElementById('opacitySlider').value;
                                this.setStyle({{color: currentBorderColor, fillColor: layer.defaultStyle ? layer.defaultStyle.fillColor : '#bdc3c7', fillOpacity: op, weight: bWeight}});
                            }});
                            layer._eventsBound = true;
                        }}
                    }}
                }}
            }});

            function applyFilters() {{
                var op = document.getElementById('opacitySlider').value;
                var show26Borders = document.getElementById('t_granser_26').checked;
                var bWeight = show26Borders ? 2 : 0;
                
                map.eachLayer(function(layer) {{
                    if (layer.options && layer.options.className && layer.options.className.includes('valdistrikt-polygon')) {{
                        if (layer.feature && layer.feature.properties && layer.feature.properties.MATCH_ID) {{
                            let matchId = layer.feature.properties.MATCH_ID;
                            let data = valData[matchId];
                            
                            if (currentActiveVariable === 'Granser') {{
                                layer.setStyle({{color: currentBorderColor, fillColor: '#bdc3c7', fillOpacity: op, weight: bWeight}});
                                layer.defaultStyle = {{ weight: bWeight, color: currentBorderColor, fillOpacity: op, fillColor: '#bdc3c7' }};
                            }} else {{
                                var newColor = getColor(data ? data[currentActiveVariable] : null, currentActiveVariable);
                                layer.setStyle({{color: currentBorderColor, fillColor: newColor, fillOpacity: op, weight: bWeight}});
                                layer.defaultStyle = {{ weight: bWeight, color: currentBorderColor, fillOpacity: op, fillColor: newColor }};
                            }}
                            
                            // Uppdatera tooltippen säkert via setTooltipContent
                            if(data) {{
                                var valHtml = data.Valdeltagande !== null ? `<strong>Valdeltagande (2022):</strong> ${{data.Valdeltagande}} %<br>` : `<strong>Valdeltagande (2022):</strong> Data saknas<br>`;
                                var rostHtml = data.Rostberattigade !== null ? `<strong>Röstberättigade (2022):</strong> ${{data.Rostberattigade.toLocaleString('sv-SE')}} st<br>` : `<strong>Röstberättigade (2022):</strong> Data saknas<br>`;
                                
                                var html = `
                                    <div class="val-tooltip" style="font-size: 13px; line-height: 1.4; width: 220px;">
                                        <div style="font-size: 14px; border-bottom: 1px solid #ccc; padding-bottom: 4px; margin-bottom: 4px; font-weight: bold; color: #2c3e50;">
                                            ${{data.NAMN}}
                                        </div>
                                        <b>Röstberättigade (Prel. 2026):</b> ${{data.Rostberattigade_2025.toLocaleString('sv-SE')}} st<br>
                                        <hr style="margin:4px 0;">
                                        <b>Officiellt 2022:</b><br>
                                        ${{rostHtml}}
                                        ${{valHtml}}
                                    </div>
                                `;
                                layer.setTooltipContent(html);
                            }}
                        }}
                    }}
                }});
                
                document.querySelectorAll('.variable-legend').forEach(el => el.style.display = 'none');
                if (currentActiveVariable !== 'Granser') {{
                    var legendElement = document.getElementById('legend-' + currentActiveVariable);
                    if (legendElement) legendElement.style.display = 'block';
                }}
            }}

            document.getElementById('opacitySlider').addEventListener('input', function(e) {{
                document.getElementById('opacityVal').innerText = Math.round(e.target.value * 100) + '%';
                applyFilters();
            }});
            
            document.querySelectorAll('.var-toggle').forEach(function(radio) {{
                radio.addEventListener('change', function() {{
                    if(this.checked) {{
                        currentActiveVariable = this.value;
                        applyFilters();
                    }}
                }});
            }});

            // ================= NY FUNKTION: TRAKTER / KVARTER =================
            var traktLayerObj = L.markerClusterGroup({{maxClusterRadius: 40, disableClusteringAtZoom: 13}});
            traktData.forEach(function(t) {{
                var lat = t[0], lng = t[1], namn = t[2], rost = t[3];
                
                var html = `
                    <div class='val-tooltip' style='font-family:sans-serif; padding:5px; line-height: 1.4; text-align:center;'>
                        <b style='color:#2980b9; font-size:14px;'>📍 ${{namn}}</b><br>
                        <b>Röstberättigade (Prel 2025):</b> ${{rost.toLocaleString('sv-SE')}} st
                    </div>
                `;
                
                var displayNum = rost >= 1000 ? (rost/1000).toFixed(1).replace('.0','') + 'k' : rost;
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
            
            document.getElementById('toggleTrakter').addEventListener('change', function(e) {{
                if(this.checked) map.addLayer(traktLayerObj); 
                else map.removeLayer(traktLayerObj); 
            }});

            // ================= ÄNDRADE ADRESSER (DIFF) OCH VANLIGA PUNKTER =================
            var clusterLayerObj = L.markerClusterGroup({{disableClusteringAtZoom: 13, maxClusterRadius: 30}});
            var changedMarkers = L.layerGroup();
            var showOnlyChanged = false;
            
            clusterPoints.forEach(function(p) {{
                var fran = p[6];
                var till = p[7];
                var isChanged = (fran.toUpperCase() !== till.toUpperCase());
                
                var markerColor = isChanged ? '#e74c3c' : '#3498db';
                var titleText = isChanged ? "<b style='color:#e74c3c;'>📍 Flyttad Adresspunkt</b>" : "<b style='color:#3498db;'>📍 Adresspunkt</b>";
                
                var html = `
                    <div class="val-tooltip" style="font-family:sans-serif; font-size:12px; padding:5px; line-height: 1.4;">
                        ${{titleText}}<br>
                        <b>Adress:</b> ${{p[3]}}<br>
                        <b>Fastighet:</b> ${{p[4]}}<br>
                        <b>Röstberättigade:</b> ${{p[5]}} st<br>
                        <hr style="margin:4px 0;">
                        <b>2022:</b> ${{fran}}<br>
                        <b>2026:</b> ${{till}}
                    </div>
                `;
                var marker = L.circleMarker([p[0], p[1]], {{radius: isChanged ? 6 : 4, color: '#fff', weight: 1, fillColor: markerColor, fillOpacity: 0.9, pane: 'topMarkersPane'}});
                marker.bindTooltip(html, {{direction: 'top', className: 'custom-tooltip-wrapper'}});
                
                // Vi lägger in alla i huvudklustret
                clusterLayerObj.addLayer(marker);
                
                // De flyttade sparas även i en egen separat grupp
                if (isChanged) {{
                    var m2 = L.circleMarker([p[0], p[1]], {{radius: 6, color: '#fff', weight: 2, fillColor: '#e74c3c', fillOpacity: 1, pane: 'topMarkersPane'}});
                    m2.bindTooltip(html, {{direction: 'top', className: 'custom-tooltip-wrapper'}});
                    changedMarkers.addLayer(m2);
                }}
            }});

            document.getElementById('toggleChangedAddr').addEventListener('change', function(e) {{
                showOnlyChanged = e.target.checked;
                updateDiffLayer();
            }});

            map.on('zoomend', function() {{ updateDiffLayer(); }});

            function updateDiffLayer() {{
                // Om "Visa bara flyttade" är i-kryssad stänger vi av normala klusterpunkter
                if (showOnlyChanged) {{
                    if (map.hasLayer(clusterLayerObj)) map.removeLayer(clusterLayerObj);
                    if (map.getZoom() >= 13) {{ 
                        if (!map.hasLayer(changedMarkers)) map.addLayer(changedMarkers);
                    }} else {{
                        if (map.hasLayer(changedMarkers)) map.removeLayer(changedMarkers);
                    }}
                }} else {{
                    // Om "Visa bara flyttade" är AV, styrs vanliga klustret av "Adresspunkter 2025" knappen
                    if (map.hasLayer(changedMarkers)) map.removeLayer(changedMarkers);
                    if (document.getElementById('toggleKluster').checked) {{
                        if (!map.hasLayer(clusterLayerObj)) map.addLayer(clusterLayerObj);
                    }}
                }}
            }}
            
            document.getElementById('toggleKluster').addEventListener('change', function(e) {{
                if (!showOnlyChanged) {{
                    if(this.checked) map.addLayer(clusterLayerObj); else map.removeLayer(clusterLayerObj);
                }}
            }});

            // ================= CSV EXPORT =================
            document.getElementById('btn-export').addEventListener('click', function() {{
                if(changedAddresses.length === 0) {{
                    showToast("Inga adresser har bytt valdistrikt enligt underlagen.", 3000);
                    return;
                }}
                
                // BOM (\uFEFF) läggs till för att tvinga Excel att läsa i UTF-8 format
                var csvContent = "\uFEFFBelagenhetsadress;Fastighet;Rostberattigade(Prel 2025);Fran_Distrikt_2022;Till_Distrikt_2026\\n";
                
                changedAddresses.forEach(function(row) {{
                    var r = [
                        row.adress.replace(/;/g, ','), 
                        row.fastighet.replace(/;/g, ','), 
                        row.rostberattigade, 
                        row.fran_distrikt.replace(/;/g, ','), 
                        row.till_distrikt.replace(/;/g, ',')
                    ].join(";");
                    csvContent += r + "\\n";
                }});
                
                var blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
                var url = URL.createObjectURL(blob);
                var link = document.createElement("a");
                link.setAttribute("href", url);
                link.setAttribute("download", "Andrade_Adresser_Valdistrikt_22-26.csv");
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                showToast("✅ Nedladdning av CSV-fil startad!", 3000);
            }});

            // ================= SÖKFUNKTION =================
            document.getElementById('searchDistrikt').addEventListener('input', function(e) {{
                var val = this.value.toLowerCase().trim();
                if (!val) return;
                for (const [key, d] of Object.entries(valData)) {{
                    if (d.NAMN.toLowerCase() === val) {{
                        map.eachLayer(function(l) {{
                            if (l.feature && l.feature.properties && l.feature.properties.MATCH_ID === key) {{
                                if (l.options && l.options.className && l.options.className.includes('valdistrikt-polygon')) {{
                                    map.fitBounds(l.getBounds(), {{padding: [50, 50], maxZoom: 14}});
                                    var origStyle = l.defaultStyle;
                                    var blinks = 0;
                                    var blinkInterval = setInterval(function() {{
                                        l.setStyle({{ weight: 8, color: blinks % 2 === 0 ? '#ffff00' : '#ff0000', fillOpacity: 0.9 }});
                                        blinks++;
                                        if (blinks >= 6) {{
                                            clearInterval(blinkInterval);
                                            applyFilters(); 
                                        }}
                                    }}, 500);
                                }}
                            }}
                        }});
                    }}
                }}
            }});

            // Initiera POI och transport LAGER
            var transportLayerObj = L.geoJSON(transportData, {{
                style: function(f) {{ 
                    var h = (f.properties.highway || "").toString().toLowerCase();
                    if (h === 'motorway') return {{color: '#e31a1c', weight: 5, opacity: 0.9}}; 
                    if (h === 'primary' || h === 'secondary') return {{color: '#ffc107', weight: 3, opacity: 0.9}}; 
                    return {{color: '#888888', weight: 2, opacity: 0.7}};
                }}, interactive: false
            }});
            
            var vattenLayerObj = L.geoJSON(vattenData, {{ style: function(f) {{ return {{fillColor: '#85c1e9', color: '#2980b9', weight: 1, fillOpacity: 0.6}}; }}, interactive: false }});

            var lokalerLayerObj = L.markerClusterGroup({{maxClusterRadius: 20}});
            lokalerData.forEach(function(loc) {{
                var marker = L.circleMarker([loc[0], loc[1]], {{radius: 9, fillColor: '#8e44ad', color: '#fff', weight: 3, fillOpacity: 0.9, pane: 'topMarkersPane'}});
                marker.bindTooltip(`<b>${{loc[2]}}</b><br>📍 ${{loc[3]}}<br>Distrikt: ${{loc[5]}}`);
                lokalerLayerObj.addLayer(marker);
            }});
            
            var poiLayerObj = L.markerClusterGroup({{maxClusterRadius: 20}});
            poiData.forEach(function(poi) {{
                var isStadshus = poi[2].toLowerCase().includes('stadshus');
                var marker = L.circleMarker([poi[0], poi[1]], {{
                    radius: isStadshus ? 11 : 8, fillColor: isStadshus ? '#c0392b' : '#e67e22', color: isStadshus ? '#f1c40f' : '#fff', weight: isStadshus ? 3 : 2, fillOpacity: 0.9, pane: 'topMarkersPane'
                }}).bindTooltip(`<b>${{poi[2]}}</b><br><span style="font-size:11px;">${{poi[3]}}</span><hr style="margin:4px 0;">Förtidsröster: ${{poi[4]}} st`);
                poiLayerObj.addLayer(marker);
            }});

            map.addLayer(lokalerLayerObj); // På som default

            document.getElementById('toggleLokaler').addEventListener('change', function(e) {{ if(this.checked) map.addLayer(lokalerLayerObj); else map.removeLayer(lokalerLayerObj); }});
            document.getElementById('togglePOI').addEventListener('change', function(e) {{ if(this.checked) map.addLayer(poiLayerObj); else map.removeLayer(poiLayerObj); }});
            document.getElementById('toggleTransport').addEventListener('change', function(e) {{ if(this.checked) map.addLayer(transportLayerObj); else map.removeLayer(transportLayerObj); }});
            document.getElementById('toggleVatten').addEventListener('change', function(e) {{ if(this.checked) map.addLayer(vattenLayerObj); else map.removeLayer(vattenLayerObj); }});

            document.getElementById('btn-reset').addEventListener('click', function() {{ 
                map.setView([58.4102, 15.6216], 11); 
                document.getElementById('searchDistrikt').value = '';
                document.getElementById('opacitySlider').value = 0.60;
                document.getElementById('opacityVal').innerText = '60%';
                
                document.getElementById('t_granser_22').checked = false;
                map._container.classList.remove('show-2022');
                
                document.getElementById('t_granser_26').checked = true;
                
                document.getElementById('toggleChangedAddr').checked = false;
                showChanged = false;
                updateDiffLayer();
                
                currentActiveVariable = 'Granser';
                document.getElementById('t_granser').checked = true;
                
                // Nollställ Trakter
                document.getElementById('toggleTrakter').checked = false;
                if(map.hasLayer(traktLayerObj)) map.removeLayer(traktLayerObj);
                
                applyFilters();
            }});
            
            setTimeout(applyFilters, 1000);
        }});
    </script>
    """

    m.get_root().html.add_child(folium.Element(ui_html))
    html_out_path = os.path.join(moder_mapp, OUT_HTML_NAME)
    m.save(html_out_path)
    print(f"\n🎉 KLAR! Gränsanalyskartan sparades framgångsrikt som:\n➡️  {html_out_path}")

except Exception as e:
    print("\n❌ Ett fel inträffade under genereringen:")
    traceback.print_exc()