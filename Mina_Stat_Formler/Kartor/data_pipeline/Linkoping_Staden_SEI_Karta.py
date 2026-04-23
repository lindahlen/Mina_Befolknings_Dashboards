import os
import sys
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MiniMap
import branca.colormap as cm
import json
import math
import numpy as np
import shapely.affinity
from shapely.geometry import Point

# =====================================================================
# 1. GENERELL SETUP & MAPPSTRUKTUR (STADEN VERSION)
# Author: Jimmy Lindahl, Analys & Utredning, Linköpings kommun
# =====================================================================
# 
# 🛑 ÄNDRA ÅRTAL OCH FILNAMN HÄR NÄSTA ÅR! 🛑
# --------------------------------------------------
GEOJSON_NYKO4_FILENAME = 'NYKO4v23.geojson' 
PUNKT_DATA_FILNAMN = 'BefKoord2025.csv'      # <--- Byt till t.ex. 'BefKoord2026.csv' nästa år!
PUNKT_DATA_AR = "2025"                       # <--- Byt till "2026"
EXCLUDE_146300 = True # Ändra till False om 146300 ska inkluderas i framtiden
# --------------------------------------------------

EXCEL_POP_SHEET = 'Basområden'
EXCEL_HUSHALL_SHEET = 'Hushållstorl_basomr'
EXCEL_UPPLATELSE_SHEET = 'Upplåtelseform_basomr'

OUT_HTML_NAME = 'Linkoping_SEI_Staden.html'

try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
    moder_mapp = os.path.dirname(current_folder)
except NameError:
    current_folder = os.getcwd()
    moder_mapp = os.path.dirname(current_folder)

kart_filer_dir = os.path.join(moder_mapp, 'kart_filer')
excel_filer_dir = os.path.join(moder_mapp, 'excel_filer')
kart_data_dir = os.path.join(moder_mapp, 'kart_data_staden') # <-- MAPP FÖR EXTERN DATA

os.makedirs(kart_data_dir, exist_ok=True)

encoding_fix = {
    'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
    'Ã©': 'é', 'Ã¨': 'è', 'Ã‰': 'É', "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö"
}

def fix_text(text):
    if not isinstance(text, str): return text
    for bad, good in encoding_fix.items():
        text = text.replace(bad, good)
    return text

# =====================================================================
# 2. DATAHANTERING & GEOGRAFI (FILTRERAT PÅ STADEN)
# =====================================================================
print("Läser in och processar data för Nyko 4 (Staden)...")

geojson_path = os.path.join(kart_filer_dir, GEOJSON_NYKO4_FILENAME)
try:
    nyko4 = gpd.read_file(geojson_path)
except FileNotFoundError:
    print(f"\nFEL: Hittar inte GeoJSON-filen: {geojson_path}.")
    sys.exit(1)

nyko4['NAMN'] = nyko4['NAMN'].apply(fix_text)
nyko4['Namn_clean'] = nyko4['NAMN'].astype(str).str.strip().str.lower()
nyko_col = next((c for c in nyko4.columns if str(c).upper() in ['NYKO', 'KODNYKO4', 'KOD']), 'NYKO')
if nyko_col in nyko4.columns:
    nyko4['NYKO_str'] = nyko4[nyko_col].astype(str).str.replace('.0', '', regex=False).str.zfill(4)
else:
    nyko4['NYKO_str'] = [str(i).zfill(4) for i in range(1, len(nyko4)+1)]

# === FILTER: BEHÅLL BARA LINKÖPINGS STAD OCH MALMSLÄTT ===
def filter_staden_row(row):
    k_str = str(row['NYKO_str'])
    
    if 'SUBTYP' in row and pd.notnull(row['SUBTYP']):
        if str(row['SUBTYP']).strip().lower() == 'stadsdelar':
            return True
    try:
        k = int(k_str)
        if 1111 <= k <= 1383: return True
        if 1411 <= k <= 1492: return True
        if 1511 <= k <= 1531: return True
        if 1551 <= k <= 1563: return True
        if 1611 <= k <= 1614: return True # Malmslätt inlagt
    except: pass
    return False

nyko4 = nyko4[nyko4.apply(filter_staden_row, axis=1)].copy()
print(f"✅ Filtrerat till {len(nyko4)} stads-polygon(er).")

nyko4_3006 = nyko4.to_crs(epsg=3006)
nyko4['Area_km2'] = nyko4_3006.geometry.area / 1_000_000

nyko4_4326 = nyko4.to_crs(epsg=4326)
nyko4_3006_centroids = nyko4_3006.geometry.centroid

# Skapa en enhetlig gräns för HELA den valda staden för att klippa POI och Mikroklimat
staden_geom_4326 = nyko4_4326.geometry.unary_union
bounds = staden_geom_4326.bounds
initial_bounds_js = f"[[{bounds[1]}, {bounds[0]}], [{bounds[3]}, {bounds[2]}]]"

def load_infa(filename):
    path = os.path.join(kart_filer_dir, filename)
    if os.path.exists(path):
        try: return json.dumps(gpd.read_file(path).to_crs(4326).__geo_interface__)
        except: pass
    return json.dumps({"type": "FeatureCollection", "features": []})

transport_str = load_infa('transportleder.geojson')
vatten_str = load_infa('vattendrag.geojson')

# Läs in och filtrera Stångåstaden på Staden-geometrin
stanga_path = os.path.join(kart_filer_dir, 'stangastadensomr.geojson')
if os.path.exists(stanga_path):
    try:
        stanga_gdf = gpd.read_file(stanga_path).to_crs(4326)
        stanga_gdf = stanga_gdf[stanga_gdf.geometry.intersects(staden_geom_4326)]
        stanga_str = json.dumps(stanga_gdf.__geo_interface__)
    except:
        stanga_str = '{"type": "FeatureCollection", "features": []}'
else:
    stanga_str = '{"type": "FeatureCollection", "features": []}'

# Läs in Mikroklimat
mikro_path = os.path.join(kart_filer_dir, 'linkoping_mikroklimat_kombinerad.geojson')
if os.path.exists(mikro_path):
    try:
        mikro_gdf = gpd.read_file(mikro_path).to_crs(4326)
        mikro_gdf = mikro_gdf[mikro_gdf.geometry.intersects(staden_geom_4326)]
        mikro_str = json.dumps(mikro_gdf.__geo_interface__)
    except:
        mikro_str = '{"type": "FeatureCollection", "features": []}'
else:
    mikro_str = '{"type": "FeatureCollection", "features": []}'


# =====================================================================
# 3. LÄS IN SEI-DATA, INDIKATORER & KODER (SEI_utdrag.xlsx)
# =====================================================================
print("Bearbetar Excel-data för SEI (SEI_utdrag.xlsx)...")
sei_path = os.path.join(excel_filer_dir, 'SEI_utdrag.xlsx')

ind_keys = [
    'ind_netink', 'ind_forvink', 'ind_syssel', 'ind_arblosa', 'ind_ejsjalv', 'ind_bistand', 
    'ind_barnfattig', 'ind_lagekon', 'ind_lagink', 'ind_trang', 'ind_kvm', 'ind_kvarboende', 'ind_ensam', 'ind_ohalsa', 'ind_forgym', 
    'ind_forskola', 'ind_behoriga', 'ind_uvas', 'ind_utrfod', 'ind_utlbak', 'ind_val'
]

for col in ['SEI_Index', 'Snitt_15_19', 'Snitt_20_24', 'SEI_Change'] + ind_keys:
    nyko4[col] = 0.0

if os.path.exists(sei_path):
    try:
        df_sei = pd.read_excel(sei_path, sheet_name='SEIsnitt')
        df_sei.columns = df_sei.columns.astype(str).str.strip()
        namn_col = next((c for c in df_sei.columns if c.lower() in ['namn', 'basområde', 'område']), None)
        
        if namn_col and 'Medel' in df_sei.columns:
            if 'Ingår' in df_sei.columns:
                df_sei = df_sei[df_sei['Ingår'].astype(str).str.strip().isin(['1', '1.0', 'Ja', 'ja', 'True', 'true'])]
            
            df_sei['SEI_Index'] = pd.to_numeric(df_sei['Medel'].astype(str).str.replace('..', '', regex=False), errors='coerce').fillna(0)
            snitt_15_col = next((c for c in df_sei.columns if '15-19' in c or '15_19' in c), None)
            snitt_20_col = next((c for c in df_sei.columns if '20-24' in c or '20_24' in c), None)
            if snitt_15_col: df_sei['Snitt_15_19'] = pd.to_numeric(df_sei[snitt_15_col].astype(str).str.replace('..', '', regex=False), errors='coerce').fillna(0)
            if snitt_20_col: df_sei['Snitt_20_24'] = pd.to_numeric(df_sei[snitt_20_col].astype(str).str.replace('..', '', regex=False), errors='coerce').fillna(0)
            
            df_sei['SEI_Change'] = df_sei['Snitt_20_24'] - df_sei['Snitt_15_19']
            df_sei['Namn_clean'] = df_sei[namn_col].apply(fix_text).astype(str).str.strip().str.lower()
            
            cols_sei = ['Namn_clean', 'SEI_Index', 'Snitt_15_19', 'Snitt_20_24', 'SEI_Change']
            nyko4 = nyko4.drop(columns=[c for c in cols_sei if c != 'Namn_clean']).merge(df_sei[cols_sei], on='Namn_clean', how='left')
    except Exception as e: print(f"INFO: SEIsnitt misslyckades - {e}")

    try:
        df_ind = pd.read_excel(sei_path, sheet_name='Indikatorer_data')
        df_ind.columns = df_ind.columns.astype(str).str.strip()
        namn_col = next((c for c in df_ind.columns if c.lower() in ['namn', 'basområde']), None)
        
        if namn_col:
            df_ind['Namn_clean'] = df_ind[namn_col].apply(fix_text).astype(str).str.strip().str.lower()
            def get_col(kws): return next((c for c in df_ind.columns if any(k in c.lower() for k in kws)), None)
            
            mappings = {
                'ind_netink': ['nettoinkomst'], 'ind_forvink': ['förvärvsinkomst'], 'ind_syssel': ['sysselsättningsgrad', 'sysselsättning'],
                'ind_arblosa': ['arbetslösa'], 'ind_ejsjalv': ['ej självförsörjande', 'självförsörjande'], 'ind_bistand': ['bistånd'],
                'ind_barnfattig': ['barnfattigdom', 'barnfattig'], 'ind_lagekon': ['låg_ekonomisk', 'låg ekonomisk'],
                'ind_lagink': ['inkomststandard', 'låg_inkomst', 'låg inkomst'], 'ind_trang': ['trångbodda'], 'ind_kvm': ['kvm'],
                'ind_kvarboende': ['kvarboende', 'kvarboende_minst_tre_år'], 'ind_ensam': ['ensamstående'], 'ind_ohalsa': ['ohälsotal', 'ohälsa'], 
                'ind_forgym': ['förgymnasial'], 'ind_forskola': ['inskrivna förskolebarn', 'förskolebarn', 'inskrivna_förskolebarn'], 
                'ind_behoriga': ['behöriga_gymnasiets_yrkesprogram', 'behöriga gymn', 'yrkesprogram'], 'ind_uvas': ['uvas'],
                'ind_utrfod': ['utrikes födda', 'utrikes_födda', 'utrikes'], 'ind_utlbak': ['utländsk', 'utländsk_bakgrund'], 'ind_val': ['valdeltagande']
            }
            loaded_cols = ['Namn_clean']
            for ind_key, kws in mappings.items():
                c_name = get_col(kws)
                if c_name:
                    df_ind[ind_key] = pd.to_numeric(df_ind[c_name].astype(str).str.replace('..', '', regex=False).str.replace(',', '.'), errors='coerce')
                    loaded_cols.append(ind_key)
            
            nyko4 = nyko4.drop(columns=[c for c in loaded_cols if c != 'Namn_clean']).merge(df_ind[loaded_cols], on='Namn_clean', how='left')
    except Exception as e: print(f"INFO: Indikatorer_data misslyckades/saknas - {e}")

for col in ['SEI_Index', 'Snitt_15_19', 'Snitt_20_24', 'SEI_Change'] + ind_keys:
    if col in nyko4.columns: nyko4[col] = nyko4[col].fillna(0.0)
    else: nyko4[col] = 0.0

if nyko4['SEI_Index'].max() == 0: nyko4['SEI_Index'] = np.random.randint(1, 7, size=len(nyko4))

# =====================================================================
# 4. DEMOGRAFI & EXCEL
# =====================================================================
excel_path = os.path.join(excel_filer_dir, 'befolkning_och_platser.xlsx')

print(f"Hämtar historisk folkmängd och områdeskaraktär...")
try:
    hist_df = pd.read_excel(excel_path, sheet_name=EXCEL_POP_SHEET)
    hist_df.columns = hist_df.columns.astype(str).str.strip() 
    hist_df['Namn_clean'] = hist_df['Namn'].apply(fix_text).astype(str).str.strip().str.lower()
    
    if 'Karaktär1' not in hist_df.columns: hist_df['Karaktär1'] = ''
    if 'Karaktär2' not in hist_df.columns: hist_df['Karaktär2'] = ''
    
    years = [str(y) for y in range(1970, 2030)]
    existing_years = [y for y in years if y in hist_df.columns]
    latest_year = existing_years[-1] if existing_years else '2025'
    prev_year = existing_years[-2] if len(existing_years) > 1 else latest_year

    for y in existing_years: hist_df[y] = pd.to_numeric(hist_df[y].astype(str).str.replace('..', '', regex=False), errors='coerce')

    nyko4 = nyko4.merge(hist_df[['Namn_clean', 'Karaktär1', 'Karaktär2'] + existing_years], on='Namn_clean', how='left')
    nyko4['Folkmängd'] = nyko4[latest_year].fillna(0).astype(int)
    nyko4['Folkmängd_prev'] = nyko4[prev_year].fillna(0).astype(int)
    nyko4['Karaktär1'] = nyko4['Karaktär1'].fillna('')
    nyko4['Karaktär2'] = nyko4['Karaktär2'].fillna('')

    def calc_trend_color(row):
        prev, curr = row['Folkmängd_prev'], row['Folkmängd']
        if prev > 0:
            diff = ((curr - prev) / prev) * 100
            if diff > 1.0: return '#2ecc71'
            if diff < -1.0: return '#e74c3c'
        return '#f1c40f'
    nyko4['Trend_Color'] = nyko4.apply(calc_trend_color, axis=1)
except Exception:
    nyko4['Folkmängd'], nyko4['Trend_Color'], nyko4['Karaktär1'], nyko4['Karaktär2'] = 0, '#f1c40f', '', ''
    existing_years = []

nyko4['Area_km2'] = nyko4['Area_km2'].replace(0, 0.001).round(2)
nyko4['Inv_per_km2'] = (nyko4['Folkmängd'] / nyko4['Area_km2']).round(1).fillna(0)

try:
    hushall_df = pd.read_excel(excel_path, sheet_name=EXCEL_HUSHALL_SHEET)
    hushall_df.columns = hushall_df.columns.astype(str).str.strip()
    hushall_df['Namn_clean'] = hushall_df['Namn'].apply(fix_text).astype(str).str.strip().str.lower()
    
    hushall_col = [c for c in hushall_df.columns if c != 'Namn' and c != 'Namn_clean'][-1]
    hushall_df[hushall_col] = hushall_df[hushall_col].astype(str).str.replace(',', '.').str.replace('..', '', regex=False).str.strip()
    hushall_df['Hushallsstorlek_tmp'] = pd.to_numeric(hushall_df[hushall_col], errors='coerce')
    nyko4 = nyko4.merge(hushall_df[['Namn_clean', 'Hushallsstorlek_tmp']], on='Namn_clean', how='left')
    nyko4['Hushallsstorlek'] = nyko4['Hushallsstorlek_tmp'].fillna(0).astype(float)
except Exception as e: 
    nyko4['Hushallsstorlek'] = 0.0

try:
    uppl_df = pd.read_excel(excel_path, sheet_name=EXCEL_UPPLATELSE_SHEET)
    uppl_df.columns = uppl_df.columns.astype(str).str.strip()
    uppl_df['Namn_clean'] = uppl_df['Namn'].apply(fix_text).astype(str).str.strip().str.lower()
    for col in ['Äganderätt', 'Bostadsrätt', 'Hyresrätt', 'Totalt']:
        if col in uppl_df.columns: uppl_df[col] = pd.to_numeric(uppl_df[col], errors='coerce').fillna(0)
    uppl_df.rename(columns={'Totalt': 'Totalt_uppl'}, inplace=True)
    nyko4 = nyko4.merge(uppl_df[['Namn_clean', 'Äganderätt', 'Bostadsrätt', 'Hyresrätt', 'Totalt_uppl']], on='Namn_clean', how='left')
    for col in ['Äganderätt', 'Bostadsrätt', 'Hyresrätt', 'Totalt_uppl']: nyko4[col] = nyko4[col].fillna(0)
    nyko4['Uppgift_saknas'] = (nyko4['Totalt_uppl'] - (nyko4['Äganderätt'] + nyko4['Bostadsrätt'] + nyko4['Hyresrätt'])).apply(lambda x: max(0, x))
    nyko4['Andel_Aganderatt'] = nyko4.apply(lambda r: round((r['Äganderätt'] / r['Totalt_uppl'] * 100), 1) if r['Totalt_uppl'] > 0 else 0.0, axis=1)
    nyko4['Andel_Bostadsratt'] = nyko4.apply(lambda r: round((r['Bostadsrätt'] / r['Totalt_uppl'] * 100), 1) if r['Totalt_uppl'] > 0 else 0.0, axis=1)
    nyko4['Andel_Hyresratt'] = nyko4.apply(lambda r: round((r['Hyresrätt'] / r['Totalt_uppl'] * 100), 1) if r['Totalt_uppl'] > 0 else 0.0, axis=1)
except Exception:
    for col in ['Totalt_uppl', 'Andel_Aganderatt', 'Andel_Bostadsratt', 'Andel_Hyresratt', 'Uppgift_saknas']: nyko4[col] = 0.0

def mask_pop(x): return '< 5' if 0 < float(x) < 5 else str(int(float(x)))
def mask_other(x, pop): return '-' if 0 < float(pop) < 5 else str(x)

def mask_hushall(h, pop):
    try:
        if 0 < float(pop) < 5: return '-'
        val = float(h)
        if val == 0: return '-'
        return f"{val:.2f}"
    except: return '-'

nyko4['Folkmängd_visa'] = nyko4['Folkmängd'].apply(mask_pop)
nyko4['Inv_per_km2_visa'] = nyko4.apply(lambda r: mask_other(r['Inv_per_km2'], r['Folkmängd']), axis=1)
nyko4['Hushallsstorlek_visa'] = nyko4.apply(lambda r: mask_hushall(r['Hushallsstorlek'], r['Folkmängd']), axis=1)

hist_json_data = {}
for idx, row in nyko4.iterrows():
    namn = row['NAMN']
    data, labels = [], []
    for y in existing_years:
        val = row.get(y)
        if pd.notna(val):
            labels.append(y)
            if 0 < int(val) < 5: data.append(None)
            else: data.append(int(val))
    hist_json_data[namn] = {'labels': labels, 'data': data}
hist_json_str = json.dumps(hist_json_data)

# =====================================================================
# 5. LÄS IN BEFKOORD OCH BYGG DEMOGRAFISK TYNGDPUNKT OCH VÄRMEKARTA
# =====================================================================
print(f"Bearbetar punktdata för värmekarta och kluster ({PUNKT_DATA_FILNAMN})...")
pop_path = os.path.join(excel_filer_dir, PUNKT_DATA_FILNAMN)
pop_df = pd.DataFrame()

try: 
    pop_df = pd.read_csv(pop_path, sep=';', encoding='utf-8')
except UnicodeDecodeError: 
    try: pop_df = pd.read_csv(pop_path, sep=';', encoding='latin-1')
    except: pass
except FileNotFoundError: 
    print(f"\nFEL: Hittar inte {pop_path}.")

dyn_pop1_str, dyn_pop3_str, dyn_pop4_str, dyn_pop6_str, heat_data_str = "[]", "[]", "[]", "[]", "[]"

demo_centers = {} 

if not pop_df.empty:
    pop_df.columns = pop_df.columns.astype(str).str.strip()
    
    if 'Y_koordinat' in pop_df.columns and 'X_koordinat' in pop_df.columns:
        pop_df['X_koordinat'] = pd.to_numeric(pop_df['X_koordinat'], errors='coerce')
        pop_df['Y_koordinat'] = pd.to_numeric(pop_df['Y_koordinat'], errors='coerce')
        valid_coords = pop_df.dropna(subset=['X_koordinat', 'Y_koordinat']).copy()
        
        if not valid_coords.empty:
            pts = gpd.GeoDataFrame(valid_coords, geometry=gpd.points_from_xy(valid_coords['Y_koordinat'], valid_coords['X_koordinat']), crs=3006)
            pts_wgs84 = pts.to_crs(4326)
            valid_coords['lat'] = pts_wgs84.geometry.y
            valid_coords['lon'] = pts_wgs84.geometry.x
            pop_df = valid_coords
        else:
            pop_df['lat'], pop_df['lon'] = 0.0, 0.0
    else:
        pop_df['lat'], pop_df['lon'] = 0.0, 0.0

    pop_df_valid = pop_df[pop_df['lat'] > 0.0].copy()

    if not pop_df_valid.empty:
        age_cols = ['0-1_år', '2-3_år', '4-5_år', '6_år', '7-9_år', '10-12_år', '13-15_år', '16-18_år', '19-24_år', '25-34_år', '35-44_år', '45-54_år', '55-64_år', '65-69_år', '70-79_år', '80+_år']
        for col in age_cols:
            if col in pop_df_valid.columns:
                pop_df_valid[col] = pd.to_numeric(pop_df_valid[col], errors='coerce').fillna(0)

        if 'Totalt' not in pop_df_valid.columns: pop_df_valid['Totalt'] = pop_df_valid[age_cols].sum(axis=1)
        else: pop_df_valid['Totalt'] = pd.to_numeric(pop_df_valid['Totalt'], errors='coerce').fillna(0)
        
        pop_df_valid['Grp_0_5'] = pop_df_valid.get('0-1_år', 0) + pop_df_valid.get('2-3_år', 0) + pop_df_valid.get('4-5_år', 0)
        pop_df_valid['Grp_6_15'] = pop_df_valid.get('6_år', 0) + pop_df_valid.get('7-9_år', 0) + pop_df_valid.get('10-12_år', 0) + pop_df_valid.get('13-15_år', 0)
        pop_df_valid['Grp_6_9'] = pop_df_valid.get('6_år', 0) + pop_df_valid.get('7-9_år', 0)
        pop_df_valid['Grp_10_12'] = pop_df_valid.get('10-12_år', 0)
        pop_df_valid['Grp_13_15'] = pop_df_valid.get('13-15_år', 0)
        pop_df_valid['Grp_16_18'] = pop_df_valid.get('16-18_år', 0)
        pop_df_valid['Grp_19_64'] = pop_df_valid.get('19-24_år', 0) + pop_df_valid.get('25-34_år', 0) + pop_df_valid.get('35-44_år', 0) + pop_df_valid.get('45-54_år', 0) + pop_df_valid.get('55-64_år', 0)
        
        pop_df_valid['Grp_19_34'] = pop_df_valid.get('19-24_år', 0) + pop_df_valid.get('25-34_år', 0)
        pop_df_valid['Grp_35_64'] = pop_df_valid.get('35-44_år', 0) + pop_df_valid.get('45-54_år', 0) + pop_df_valid.get('55-64_år', 0)
        
        pop_df_valid['Grp_65_79'] = pop_df_valid.get('65-69_år', 0) + pop_df_valid.get('70-79_år', 0)
        pop_df_valid['Grp_80plus'] = pop_df_valid.get('80+_år', 0)

        if 'NYKO6' in pop_df_valid.columns:
            pop_df_valid['NYKO6_str'] = pd.to_numeric(pop_df_valid['NYKO6'], errors='coerce').fillna(0).astype(int).astype(str).str.zfill(6)
            pop_df_valid['NYKO1_str'] = pop_df_valid['NYKO6_str'].str[:1]
            pop_df_valid['NYKO3_str'] = pop_df_valid['NYKO6_str'].str[:3]
            pop_df_valid['NYKO4_str'] = pop_df_valid['NYKO6_str'].str[:4]
            pop_df_valid['NYKO4_kod'] = pop_df_valid['NYKO4_str'].astype(float)
            
            def is_pt_staden(nyko_str):
                try:
                    k = int(nyko_str)
                    if 1111 <= k <= 1383: return True
                    if 1411 <= k <= 1492: return True
                    if 1511 <= k <= 1531: return True
                    if 1551 <= k <= 1563: return True
                    if 1611 <= k <= 1614: return True # Malmslätt inlagt
                    return False
                except:
                    return False
            
            pop_df_valid = pop_df_valid[pop_df_valid['NYKO4_str'].apply(is_pt_staden)].copy()
            
            if EXCLUDE_146300:
                pop_df_valid = pop_df_valid[pop_df_valid['NYKO6_str'] != '146300'].copy()
            
            grp_cols = ['Grp_0_5', 'Grp_6_15', 'Grp_6_9', 'Grp_10_12', 'Grp_13_15', 'Grp_16_18', 'Grp_19_64', 'Grp_19_34', 'Grp_35_64', 'Grp_65_79', 'Grp_80plus']
            pop_nyko4 = pop_df_valid.groupby('NYKO4_str')[grp_cols].sum().reset_index()
            nyko4 = nyko4.merge(pop_nyko4, left_on='NYKO_str', right_on='NYKO4_str', how='left')
            for c in grp_cols:
                nyko4[c] = nyko4[c].fillna(0).astype(int)

        fill_cols = ['Totalt', 'Grp_0_5', 'Grp_6_15', 'Grp_6_9', 'Grp_10_12', 'Grp_13_15', 'Grp_16_18', 'Grp_19_64', 'Grp_19_34', 'Grp_35_64', 'Grp_65_79', 'Grp_80plus']
        def create_agg_pop(df, group_col):
            df_pop = df[df['Totalt'] > 0].copy()
            result = []
            if group_col in df_pop.columns:
                for name, group in df_pop.groupby(group_col):
                    tot_pop = group['Totalt'].sum()
                    if tot_pop == 0: continue
                    weighted_lat = (group['lat'] * group['Totalt']).sum() / tot_pop
                    weighted_lon = (group['lon'] * group['Totalt']).sum() / tot_pop
                    dist_sq = (group['lat'] - weighted_lat)**2 + (group['lon'] - weighted_lon)**2
                    best_idx = dist_sq.idxmin()
                    stats = {'kod': name, 'lat': group.loc[best_idx, 'lat'], 'lon': group.loc[best_idx, 'lon']}
                    for col in fill_cols: stats[col] = int(group[col].sum())
                    result.append(stats)
            return result

        dyn_pop1_str = json.dumps(create_agg_pop(pop_df_valid, 'NYKO1_str'))
        dyn_pop3_str = json.dumps(create_agg_pop(pop_df_valid, 'NYKO3_str'))
        dyn_pop4_str = json.dumps(create_agg_pop(pop_df_valid, 'NYKO4_str'))
        dyn_pop6_str = json.dumps(create_agg_pop(pop_df_valid, 'NYKO6_str'))

        # Bygg dictionary med demografiska tyngdpunkter för NYKO4
        if 'NYKO4_str' in pop_df_valid.columns:
            for name, group in pop_df_valid[pop_df_valid['Totalt'] > 0].groupby('NYKO4_str'):
                tot_pop = group['Totalt'].sum()
                if tot_pop == 0: continue
                weighted_lat = (group['lat'] * group['Totalt']).sum() / tot_pop
                weighted_lon = (group['lon'] * group['Totalt']).sum() / tot_pop
                demo_centers[name] = (weighted_lat, weighted_lon)

        heat_data = []
        for idx, row in pop_df_valid.iterrows():
            if row['Totalt'] > 0:
                heat_data.append({
                    'lat': round(row['lat'], 5), 'lon': round(row['lon'], 5),
                    'tot': int(row['Totalt']), 'a0_5': int(row['Grp_0_5']), 'a6_15': int(row['Grp_6_15']),
                    'a6_9': int(row['Grp_6_9']), 'a10_12': int(row['Grp_10_12']), 'a13_15': int(row['Grp_13_15']),
                    'a16_18': int(row['Grp_16_18']), 'a19_64': int(row['Grp_19_64']), 
                    'a19_34': int(row['Grp_19_34']), 'a35_64': int(row['Grp_35_64']),
                    'a65_79': int(row['Grp_65_79']), 'a80': int(row['Grp_80plus'])
                })
        heat_data_str = json.dumps(heat_data)
        print("✅ Adresspunkter / Värmekartedata framgångsrikt processad.")

# =====================================================================
# 6. EXPORTERA OMRÅDESDATA OCH POI (TILL EXTERNA FILER)
# =====================================================================
nyko4_data = []

for idx, row in nyko4.iterrows():
    kod = str(row['NYKO_str'])
    geom_4326 = nyko4_4326.geometry.iloc[idx]
    
    rep_pt = geom_4326.representative_point()
    pt_lat, pt_lon = rep_pt.y, rep_pt.x
    
    if kod in demo_centers:
        d_lat, d_lon = demo_centers[kod]
        d_pt = Point(d_lon, d_lat)
        if geom_4326.contains(d_pt):
            pt_lat, pt_lon = d_lat, d_lon
    
    nyko4_data.append({
        'namn': row['NAMN'], 'kod': kod,
        'trend_color': row.get('Trend_Color', '#3498db'),
        'lat': pt_lat, 'lon': pt_lon, 'area': row.get('Area_km2', 0),
        'sei_index': float(row['SEI_Index']),
        'folkmangd': float(row.get('Folkmängd', 0)),
        'folkmangd_visa': str(row.get('Folkmängd_visa', '0')),
        'inv_per_km2': float(row.get('Inv_per_km2', 0)),
        'hushall': float(row.get('Hushallsstorlek', 0)),
        'char1': str(row.get('Karaktär1', '')), 'char2': str(row.get('Karaktär2', '')),
        'hushall_visa': str(row.get('Hushallsstorlek_visa', '-')),
        'agan_pct': float(row.get('Andel_Aganderatt', 0)),
        'bost_pct': float(row.get('Andel_Bostadsratt', 0)),
        'hyre_pct': float(row.get('Andel_Hyresratt', 0)),
        'tot_uppl': float(row.get('Totalt_uppl', 0)),
        'agan': float(row.get('Äganderätt', 0)),
        'bost': float(row.get('Bostadsrätt', 0)),
        'hyre': float(row.get('Hyresrätt', 0)),
        'saknas': float(row.get('Uppgift_saknas', 0)),
        # Alla 21 Indikatorer
        'ind_netink': float(row['ind_netink']) if pd.notnull(row.get('ind_netink')) else None,
        'ind_forvink': float(row['ind_forvink']) if pd.notnull(row.get('ind_forvink')) else None,
        'ind_syssel': float(row['ind_syssel']) if pd.notnull(row.get('ind_syssel')) else None,
        'ind_arblosa': float(row['ind_arblosa']) if pd.notnull(row.get('ind_arblosa')) else None,
        'ind_ejsjalv': float(row['ind_ejsjalv']) if pd.notnull(row.get('ind_ejsjalv')) else None,
        'ind_bistand': float(row['ind_bistand']) if pd.notnull(row.get('ind_bistand')) else None,
        'ind_barnfattig': float(row['ind_barnfattig']) if pd.notnull(row.get('ind_barnfattig')) else None,
        'ind_lagekon': float(row['ind_lagekon']) if pd.notnull(row.get('ind_lagekon')) else None,
        'ind_lagink': float(row['ind_lagink']) if pd.notnull(row.get('ind_lagink')) else None,
        'ind_trang': float(row['ind_trang']) if pd.notnull(row.get('ind_trang')) else None,
        'ind_kvm': float(row['ind_kvm']) if pd.notnull(row.get('ind_kvm')) else None,
        'ind_kvarboende': float(row['ind_kvarboende']) if pd.notnull(row.get('ind_kvarboende')) else None,
        'ind_ensam': float(row['ind_ensam']) if pd.notnull(row.get('ind_ensam')) else None,
        'ind_ohalsa': float(row['ind_ohalsa']) if pd.notnull(row.get('ind_ohalsa')) else None,
        'ind_forgym': float(row['ind_forgym']) if pd.notnull(row.get('ind_forgym')) else None,
        'ind_forskola': float(row['ind_forskola']) if pd.notnull(row.get('ind_forskola')) else None,
        'ind_behoriga': float(row['ind_behoriga']) if pd.notnull(row.get('ind_behoriga')) else None,
        'ind_uvas': float(row['ind_uvas']) if pd.notnull(row.get('ind_uvas')) else None,
        'ind_utrfod': float(row['ind_utrfod']) if pd.notnull(row.get('ind_utrfod')) else None,
        'ind_utlbak': float(row['ind_utlbak']) if pd.notnull(row.get('ind_utlbak')) else None,
        'ind_val': float(row['ind_val']) if pd.notnull(row.get('ind_val')) else None,
        # Trender
        'snitt_15_19': float(row.get('Snitt_15_19', 0)),
        'snitt_20_24': float(row.get('Snitt_20_24', 0)),
        'sei_change': float(row.get('SEI_Change', 0)),
        # Detaljerad Demografi
        'grp_0_5': int(row.get('Grp_0_5', 0)),
        'grp_6_15': int(row.get('Grp_6_15', 0)),
        'grp_6_9': int(row.get('Grp_6_9', 0)),
        'grp_10_12': int(row.get('Grp_10_12', 0)),
        'grp_13_15': int(row.get('Grp_13_15', 0)),
        'grp_16_18': int(row.get('Grp_16_18', 0)),
        'grp_19_64': int(row.get('Grp_19_64', 0)),
        'grp_19_34': int(row.get('Grp_19_34', 0)),
        'grp_35_64': int(row.get('Grp_35_64', 0)),
        'grp_65_79': int(row.get('Grp_65_79', 0)),
        'grp_80plus': int(row.get('Grp_80plus', 0))
    })
nyko4_json_str = json.dumps(nyko4_data)

excel_pois = []
vardboende_colors = {}
vardboende_palette = ['#e74c3c', '#8e44ad', '#2980b9', '#d35400', '#16a085']

def extract_excel_pois(sheet_name, name_col, type_col, org_col=None):
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
        for _, row in df.dropna(subset=['Latitud', 'Longitud']).iterrows():
            type_val = str(row[type_col])
            cat = type_val.lower()
            org_val = str(row[org_col]) if org_col and org_col in df.columns else ""
            
            # Klipp POI till Staden geom (exkludera de utanför staden)
            pt = Point(float(row['Longitud']), float(row['Latitud']))
            if not staden_geom_4326.contains(pt):
                continue
            
            if sheet_name == 'Skolor':
                if 'grund' in cat: group, icon, color = 'Grundskolor', 'fa-child', '#3498db'
                else: group, icon, color = 'Gymnasieskolor', 'fa-graduation-cap', '#9b59b6'
            elif sheet_name == 'Vårdboende': 
                if type_val not in vardboende_colors:
                    vardboende_colors[type_val] = vardboende_palette[len(vardboende_colors) % len(vardboende_palette)]
                group, icon, color = 'Vårdboende', 'fa-heartbeat', vardboende_colors[type_val]
            elif sheet_name == 'Platser':
                if 'centrum' in cat or 'handel' in cat: group, icon, color = 'Handel & Centrum', 'fa-shopping-cart', '#f39c12'
                elif 'idrottsanläggning' in cat or 'fritid' in cat: group, icon, color = 'Idrott & Fritid', 'fa-running', '#2ecc71'
                elif 'kultur' in cat or 'evenemang' in cat: group, icon, color = 'Kultur & Sevärdheter', 'fa-theater-masks', '#e67e22'
                elif 'förvaltning' in cat or 'institution' in cat or 'infrastruktur' in cat: group, icon, color = 'Samhälle & Infrastruktur', 'fa-building', '#e74c3c'
                elif 'landmärke' in cat or 'näringsliv' in cat: group, icon, color = 'Övriga platser', 'fa-map-marker-alt', '#95a5a6'
                else: continue
            
            excel_pois.append({'name': str(row[name_col]), 'type': type_val, 'org': org_val, 'lat': float(row['Latitud']), 'lon': float(row['Longitud']), 'group': group, 'icon': icon, 'color': color})
    except Exception: pass

extract_excel_pois('Skolor', 'Skola', 'Nivå', 'Organisation')
extract_excel_pois('Platser', 'Plats', 'Kategori', None)
extract_excel_pois('Vårdboende', 'Namn', 'Typ', 'Organisation')
excel_poi_json_str = json.dumps(excel_pois)
vardboende_count = sum(1 for p in excel_pois if p['group'] == 'Vårdboende')
vard_text = "Vårdboenden" if vardboende_count > 0 else "Vårdboenden (Kommer snart)"
vard_disabled = "" if vardboende_count > 0 else "disabled"

# --- SKRIV DATA TILL EXTERNA JS-FILER FÖR ATT BOTA HTML-FILEN ---
print("Sparar data till externa JS-filer för att radikalt snabba upp webbläsaren...")
with open(os.path.join(kart_data_dir, 'nyko4_data_staden.js'), 'w', encoding='utf-8') as f:
    f.write(f"window.nykoData = {nyko4_json_str};")
with open(os.path.join(kart_data_dir, 'hist_data_staden.js'), 'w', encoding='utf-8') as f:
    f.write(f"window.popHistData = {hist_json_str};")
with open(os.path.join(kart_data_dir, 'poi_data_staden.js'), 'w', encoding='utf-8') as f:
    f.write(f"window.excelPois = {excel_poi_json_str};")
with open(os.path.join(kart_data_dir, 'heat_data_staden.js'), 'w', encoding='utf-8') as f:
    f.write(f"window.heatDataRaw = {heat_data_str};")
with open(os.path.join(kart_data_dir, 'dyn_pop_data_staden.js'), 'w', encoding='utf-8') as f:
    f.write(f"window.dynPop1 = {dyn_pop1_str};\nwindow.dynPop3 = {dyn_pop3_str};\nwindow.dynPop4 = {dyn_pop4_str};\nwindow.dynPop6 = {dyn_pop6_str};\n")
with open(os.path.join(kart_data_dir, 'infra_data_staden.js'), 'w', encoding='utf-8') as f:
    f.write(f"window.transportData = {transport_str};\nwindow.vattenData = {vatten_str};\nwindow.stangaData = {stanga_str};\nwindow.mikroData = {mikro_str};\n")

# =====================================================================
# 7. KARTBYGGE OCH FÄRGSKALOR
# =====================================================================
print("Genererar karta och färgskalor...")

# Hög precision för att undvika glapp (ÅTERSTÄLLD)
nyko4['geometry'] = nyko4.geometry.simplify(tolerance=0.00002, preserve_topology=True)

m = folium.Map(location=[58.4102, 15.6216], zoom_start=12, tiles=None, control_scale=True)

def add_poly_layer(gdf, col, name, cmap, class_name):
    if col not in gdf.columns:
        gdf[col] = 0.0
        
    cols_to_keep = ['NAMN', col, 'geometry']
    if col == 'SEI_Change' and 'Snitt_15_19' in gdf.columns: cols_to_keep.append('Snitt_15_19')
    mini_gdf = gdf[cols_to_keep].copy()
    
    def style_fn(feature):
        val = feature['properties'].get(col)
        if pd.isnull(val): return {'fillColor': 'transparent', 'color': 'transparent', 'weight': 0, 'fillOpacity': 0.60, 'className': f'polygon-layer {class_name}'}
        if col == 'SEI_Change':
            s15 = feature['properties'].get('Snitt_15_19', 0)
            if pd.isnull(s15) or s15 == 0: return {'fillColor': 'transparent', 'color': 'transparent', 'weight': 0, 'fillOpacity': 0.60, 'className': f'polygon-layer {class_name}'}
            return {'fillColor': cmap(val), 'color': 'transparent', 'weight': 0, 'fillOpacity': 0.60, 'className': f'polygon-layer {class_name}'}
        else:
            if val <= 0: return {'fillColor': 'transparent', 'color': 'transparent', 'weight': 0, 'fillOpacity': 0.60, 'className': f'polygon-layer {class_name}'}
            return {'fillColor': cmap(val), 'color': 'transparent', 'weight': 0, 'fillOpacity': 0.60, 'className': f'polygon-layer {class_name}'}

    folium.GeoJson(mini_gdf, name=name, style_function=style_fn).add_to(m)

def get_min_max(serie, is_change=False):
    s = pd.to_numeric(serie, errors='coerce').dropna()
    if not is_change: s = s[s > 0] 
    if s.empty: return (-1.5, 1.5) if is_change else (0.0, 100.0)
    return float(s.min()), float(s.max())

# --- A. SEI-Nivåer ---
sei_mapping = {
    1: {"label": "Stora utmaningar", "color": "#440154"}, 
    2: {"label": "Betydande utmaningar", "color": "#3b528b"}, 
    3: {"label": "Stabila förutsättningar", "color": "#21918c"}, 
    4: {"label": "Goda förutsättningar", "color": "#5ec962"}, 
    5: {"label": "Välmående", "color": "#a5db36"}, 
    6: {"label": "Mycket välmående", "color": "#fde725"}  
}
unique_sei_levels = sorted([x for x in nyko4['SEI_Index'].unique() if pd.notnull(x) and x > 0])
sei_checkboxes_html = ""
for level in unique_sei_levels:
    lvl_int = int(level)
    lbl = sei_mapping[lvl_int]['label'] if lvl_int in sei_mapping else f"Okänd nivå ({lvl_int})"
    color = sei_mapping[lvl_int]['color'] if lvl_int in sei_mapping else "#888888"
    sei_checkboxes_html += f'<div class="form-check mb-1"><input class="form-check-input sei-toggle" type="checkbox" value="{lvl_int}" id="toggleSei_{lvl_int}" checked><label class="form-check-label" for="toggleSei_{lvl_int}"><span style="display:inline-block; width:13px; height:13px; background:{color}; border-radius:50%; margin-right:6px; border:1px solid #ccc; vertical-align: middle;"></span>{lvl_int}. {lbl}</label></div>'
    
    level_data = nyko4[nyko4['SEI_Index'] == level][['NAMN', 'SEI_Index', 'geometry']].copy()
    folium.GeoJson(
        level_data, name=f'SEI Nivå {lvl_int}',
        style_function=lambda feature, c=color: {'fillColor': c, 'color': 'transparent', 'weight': 0, 'fillOpacity': 0.60, 'className': f'polygon-layer sei-polygon sei-level-{lvl_int}'}
    ).add_to(m)

m_pop, mx_pop = get_min_max(nyko4['Folkmängd'])
m_dens, mx_dens = get_min_max(nyko4['Inv_per_km2'])
m_hush, mx_hush = get_min_max(nyko4['Hushallsstorlek'])
m_netink, mx_netink = get_min_max(nyko4['ind_netink'])
m_forvink, mx_forvink = get_min_max(nyko4['ind_forvink'])
m_syssel, mx_syssel = get_min_max(nyko4['ind_syssel'])
m_arblosa, mx_arblosa = get_min_max(nyko4['ind_arblosa'])
m_ejsjalv, mx_ejsjalv = get_min_max(nyko4['ind_ejsjalv'])
m_bistand, mx_bistand = get_min_max(nyko4['ind_bistand'])
m_barnfattig, mx_barnfattig = get_min_max(nyko4['ind_barnfattig'])
m_lagekon, mx_lagekon = get_min_max(nyko4['ind_lagekon'])
m_lagink, mx_lagink = get_min_max(nyko4['ind_lagink'])
m_trang, mx_trang = get_min_max(nyko4['ind_trang'])
m_kvm, mx_kvm = get_min_max(nyko4['ind_kvm'])
m_kvarboende, mx_kvarboende = get_min_max(nyko4['ind_kvarboende'])
m_ensam, mx_ensam = get_min_max(nyko4['ind_ensam'])
m_ohalsa, mx_ohalsa = get_min_max(nyko4['ind_ohalsa'])
m_forgym, mx_forgym = get_min_max(nyko4['ind_forgym'])
m_forskola, mx_forskola = get_min_max(nyko4['ind_forskola'])
m_behoriga, mx_behoriga = get_min_max(nyko4['ind_behoriga'])
m_uvas, mx_uvas = get_min_max(nyko4['ind_uvas'])
m_utrfod, mx_utrfod = get_min_max(nyko4['ind_utrfod'])
m_utlbak, mx_utlbak = get_min_max(nyko4['ind_utlbak'])
m_val, mx_val = get_min_max(nyko4['ind_val'])
m_snitt15, mx_snitt15 = get_min_max(nyko4['Snitt_15_19'])
m_snitt20, mx_snitt20 = get_min_max(nyko4['Snitt_20_24'])

pal_green = ['#c7e9c0', '#a1d99b', '#74c476', '#31a354', '#006d2c']
pal_blue = ['#c6dbef', '#9ecae1', '#6baed6', '#3182bd', '#08519c']
pal_red = ['#fcbba1', '#fc9272', '#fb6a4a', '#de2d26', '#a50f15']
pal_purp = ['#dadaeb', '#bcbddc', '#9e9ac8', '#756bb1', '#54278f']
pal_orng = ['#fdd0a2', '#fdae6b', '#fd8d3c', '#e6550d', '#a63603']
viridis_rev = ['#fde725', '#b5de2b', '#6ece58', '#35b779', '#1f9e89', '#26828e', '#31688e', '#3e4989', '#482878', '#440154']

ind_settings = [
    ('ind_netink', 'Nettoinkomst', pal_green, 'ind-netink-polygon', m_netink, mx_netink),
    ('ind_forvink', 'Förvärvsinkomst', pal_green, 'ind-forvink-polygon', m_forvink, mx_forvink),
    ('ind_syssel', 'Sysselsättningsgrad', pal_blue, 'ind-syssel-polygon', m_syssel, mx_syssel),
    ('ind_arblosa', 'Arbetslösa', pal_red, 'ind-arblosa-polygon', m_arblosa, mx_arblosa),
    ('ind_ejsjalv', 'Ej självförsörjande (%)', pal_red, 'ind-ejsjalv-polygon', m_ejsjalv, mx_ejsjalv),
    ('ind_bistand', 'Bistånd', pal_red, 'ind-bistand-polygon', m_bistand, mx_bistand),
    ('ind_barnfattig', 'Barnfattigdom (%)', pal_red, 'ind-barnfattig-polygon', m_barnfattig, mx_barnfattig),
    ('ind_lagekon', 'Låg ekon std', pal_red, 'ind-lagekon-polygon', m_lagekon, mx_lagekon),
    ('ind_lagink', 'Låg ink std', pal_red, 'ind-lagink-polygon', m_lagink, mx_lagink),
    ('ind_trang', 'Trångbodda', pal_red, 'ind-trang-polygon', m_trang, mx_trang),
    ('ind_kvm', 'Kvm per person', pal_purp, 'ind-kvm-polygon', m_kvm, mx_kvm),
    ('ind_kvarboende', 'Kvarboende minst tre år (%)', pal_blue, 'ind-kvarboende-polygon', m_kvarboende, mx_kvarboende),
    ('ind_ensam', 'Ensamstående hushåll', pal_purp, 'ind-ensam-polygon', m_ensam, mx_ensam),
    ('ind_ohalsa', 'Ohälsotal 50-64 år (dagar)', pal_red, 'ind-ohalsa-polygon', m_ohalsa, mx_ohalsa),
    ('ind_forgym', 'Förgymnasial', pal_orng, 'ind-forgym-polygon', m_forgym, mx_forgym),
    ('ind_forskola', 'Inskrivna förskolebarn (%)', pal_blue, 'ind-forskola-polygon', m_forskola, mx_forskola),
    ('ind_behoriga', 'Behöriga gymn. yrkesprogr. (%)', pal_blue, 'ind-behoriga-polygon', m_behoriga, mx_behoriga),
    ('ind_uvas', 'UVAS', pal_red, 'ind-uvas-polygon', m_uvas, mx_uvas),
    ('ind_utrfod', 'Utrikes födda', pal_purp, 'ind-utrfod-polygon', m_utrfod, mx_utrfod),
    ('ind_utlbak', 'Utländsk bakgrund', pal_purp, 'ind-utlbak-polygon', m_utlbak, mx_utlbak),
    ('ind_val', 'Valdeltagande', pal_blue, 'ind-val-polygon', m_val, mx_val)
]

for ind_col, name, pal, cls_name, vmin, vmax in ind_settings:
    add_poly_layer(nyko4, ind_col, name, cm.LinearColormap(colors=pal, vmin=vmin, vmax=vmax), cls_name)

# --- C. Trender ---
cmap_trend15 = cm.LinearColormap(colors=viridis_rev, vmin=m_snitt15, vmax=mx_snitt15)
add_poly_layer(nyko4, 'Snitt_15_19', 'Snitt 15-19', cmap_trend15, 'snitt15-polygon')

cmap_trend20 = cm.LinearColormap(colors=viridis_rev, vmin=m_snitt20, vmax=mx_snitt20)
add_poly_layer(nyko4, 'Snitt_20_24', 'Snitt 20-24', cmap_trend20, 'snitt20-polygon')

m_change, mx_change = get_min_max(nyko4['SEI_Change'], is_change=True)
min_c = min(m_change, -0.5)
max_c = max(mx_change, 0.5)

cmap_change = cm.StepColormap(
    colors=['#e74c3c', '#f1c40f', '#2ecc71'], 
    index=[min_c, -0.01, 0.01, max_c],
    vmin=min_c, 
    vmax=max_c
)
add_poly_layer(nyko4, 'SEI_Change', 'Förändring SEI', cmap_change, 'seichange-polygon')

# --- D. Ytor & Områden ---
add_poly_layer(nyko4, 'Folkmängd', 'Befolkning', cm.LinearColormap(colors=viridis_rev, vmin=m_pop, vmax=mx_pop), 'pop-polygon')
add_poly_layer(nyko4, 'Inv_per_km2', 'Täthet', cm.LinearColormap(colors=viridis_rev, vmin=m_dens, vmax=mx_dens), 'density-polygon')
add_poly_layer(nyko4, 'Hushallsstorlek', 'Hushåll', cm.LinearColormap(colors=viridis_rev, vmin=max(0, m_hush-0.2), vmax=mx_hush+0.2), 'hushall-polygon')

cmap_pct = cm.LinearColormap(colors=viridis_rev, vmin=0, vmax=100)
add_poly_layer(nyko4, 'Andel_Aganderatt', 'Äganderätt', cmap_pct, 'agan-polygon')
add_poly_layer(nyko4, 'Andel_Bostadsratt', 'Bostadsrätt', cmap_pct, 'bost-polygon')
add_poly_layer(nyko4, 'Andel_Hyresratt', 'Hyresrätt', cmap_pct, 'hyre-polygon')

# --- E. Områdesgränser ---
folium.GeoJson(
    nyko4[['NAMN', 'geometry']].copy(), name='Områdesgränser', 
    style_function=lambda feature: {'fill': False, 'color': '#2c3e50', 'weight': 1, 'className': 'polygon-layer border-polygon'}
).add_to(m)

# =====================================================================
# 8. INJICERA GYLLENE STANDARDMALL 
# =====================================================================
ui_html = f"""
<!-- LÄS IN ALL KARTDATA EXTERNT FÖR MAXIMAL PRESTANDA -->
<script src="kart_data_staden/nyko4_data_staden.js"></script>
<script src="kart_data_staden/hist_data_staden.js"></script>
<script src="kart_data_staden/poi_data_staden.js"></script>
<script src="kart_data_staden/heat_data_staden.js"></script>
<script src="kart_data_staden/dyn_pop_data_staden.js"></script>
<script src="kart_data_staden/infra_data_staden.js"></script>

<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster/dist/MarkerCluster.css" />
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster/dist/MarkerCluster.Default.css" />
<script src="https://unpkg.com/leaflet.markercluster/dist/leaflet.markercluster.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://unpkg.com/@turf/turf/turf.min.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>

<style>
    /* Custom Scrollbars */
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: #bbb; border-radius: 4px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: #888; }}

    .leaflet-control-layers {{ display: none !important; }}
    
    .tools-panel {{ position: fixed; bottom: 30px; left: 60px; z-index: 9999; background: rgba(255,255,255,0.96); padding: 18px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 310px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; }}
    .layers-panel {{ position: fixed; top: 20px; right: 20px; z-index: 9999; background: rgba(255,255,255,0.96); padding: 20px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 380px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; }}
    
    .layers-panel h6, .tools-panel h6 {{ font-size: 15px !important; margin-top: 15px; margin-bottom: 10px !important; }}
    .layers-panel .form-check-label {{ font-size: 13px; margin-left: 6px; cursor: pointer; }}
    .layers-panel .form-check-input {{ transform: scale(1.3); margin-top: 5px; cursor: pointer; }}
    .layers-panel input[type="radio"] {{ transform: scale(1.2); margin-right: 5px; cursor: pointer; }}
    
    .info-panel {{ position: fixed; top: 20px; right: 420px; z-index: 9999; background: rgba(255,255,255,0.98); padding: 20px; border-radius: 8px; box-shadow: 0 0 20px rgba(0,0,0,0.3); width: 380px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; display: none; }}
    .custom-tooltip {{ font-weight: normal; font-size: 13px; background: rgba(255,255,255,0.95); border: 1px solid #ccc; border-radius: 6px; padding: 8px 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); pointer-events: none; }}
    .leaflet-interactive {{ outline: none; }}
    
    .cluster-custom div {{ color: white; font-weight: bold; font-size: 13px; font-family: sans-serif; border-radius: 50%; width: 30px; height: 30px; margin: 5px; display: flex; justify-content: center; align-items: center; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.4); }}
    
    .legend-container {{ position: fixed; bottom: 30px; right: 20px; z-index: 9998; display: flex; flex-direction: column; gap: 10px; pointer-events: none; max-height: 80vh; overflow-y: auto; }}
    .variable-legend {{ pointer-events: auto; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 220px; display: none; }}
    
    /* Responsivitet */
    @media (max-width: 1200px) {{
        .tools-panel {{ width: 280px; left: 20px; }}
        .layers-panel {{ width: 320px; right: 20px; }}
        .info-panel {{ right: 350px; width: 320px; }}
    }}
    @media (max-width: 768px) {{
        .tools-panel {{ left: 10px; bottom: 10px; width: calc(50vw - 15px); max-height: 45vh; padding: 12px; }}
        .layers-panel {{ right: 10px; top: 10px; width: calc(50vw - 15px); max-height: 45vh; padding: 12px; }}
        .info-panel {{ right: 10px; bottom: 10px; top: auto; width: calc(100vw - 20px); max-height: 40vh; z-index: 10005; }}
        .tools-panel h6, .layers-panel h6 {{ font-size: 12px !important; }}
        .form-check-label {{ font-size: 11px !important; }}
        .btn {{ font-size: 11px !important; padding: 6px !important; }}
        #btn-measure, #btn-isochrone, #btn-draw {{ font-size: 12px !important; padding: 8px !important; }}
        .leaflet-control-zoom {{ display: none !important; }}
    }}
</style>

<!-- HEADER MED LOGO OCH RUBRIK -->
<div style="position: absolute; top: 10px; left: 60px; z-index: 9999; background: rgba(255,255,255,0.95); padding: 10px 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); display: flex; align-items: center; gap: 15px;">
    <img src="Img/Linkopingsloggo.png" alt="Linköpings kommun" style="height: 40px;" onerror="this.style.display='none'">
    <h4 style="margin: 0; color: #2c3e50; font-weight: bold; font-family: sans-serif;">SEI-analys Linköping (Staden)</h4>
</div>

<!-- TOAST MEDDELANDE (ISTÄLLET FÖR ALERT) -->
<div id="toastMessage" style="display:none; position:fixed; top:80px; left:50%; transform:translateX(-50%); z-index:9999; background:rgba(44, 62, 80, 0.9); color:#fff; padding:10px 25px; border-radius:30px; font-weight:bold; font-size:14px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); transition: opacity 0.5s;">
</div>

<div id="dynPopLabel" style="display:none; position:fixed; top:20px; left:50%; transform:translateX(-50%); z-index:9999; background:rgba(0,0,0,0.8); color:#fff; padding:8px 20px; border-radius:20px; font-weight:bold; font-size:15px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
    <i class="fas fa-users"></i> <span id="dynPopText"></span>
</div>

<div class="legend-container" id="legend-container">
    <div id="dynamic-legend" class="variable-legend">
        <h6 id="dl-title" style="font-size: 13px; font-weight: bold; margin-bottom: 5px;">Titel</h6>
        <div id="dl-grad" style="height: 12px; border-radius: 3px; width: 100%;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-top: 3px;">
            <span id="dl-min">0</span><span id="dl-max">100</span>
        </div>
    </div>
</div>

<div id="infoPanel" class="info-panel">
    <div class="d-flex justify-content-between align-items-center mb-3" style="border-bottom: 2px solid #ccc; padding-bottom: 8px;">
        <h5 class="fw-bold mb-0 text-primary" id="infoTitle">📊 Information</h5>
        <button type="button" class="btn-close" onclick="closeInfoPanel()"></button>
    </div>
    <div id="infoPanelContent"></div>
</div>

<div class="tools-panel">
    <button id="btn-reset" class="btn btn-danger w-100 mb-3 fw-bold shadow-sm" style="font-size: 13px; padding: 6px;"><i class="fas fa-sync-alt"></i> Återställ & Rensa Allt</button>

    <h6 class="fw-bold mb-3"><i class="fas fa-chart-pie text-primary"></i> Analysverktyg & Filter</h6>
    <div class="p-2 mb-3 bg-light border border-secondary rounded shadow-sm">
        <label for="opacitySlider" class="form-label mb-0 fw-bold" style="font-size: 13px;">Opacitet färgade ytor: <span id="opacityVal" style="color:#e74c3c;">60%</span></label>
        <input type="range" class="form-range" id="opacitySlider" min="0" max="1" step="0.05" value="0.60">
    </div>
    
    <label class="form-label mb-1 fw-bold" style="font-size: 12px;">Visa urval (Topp/Lägsta 10)</label>
    <div class="btn-group w-100 mb-3" role="group">
        <button type="button" id="btn-top10" class="btn btn-outline-success btn-sm" style="font-size: 12px; font-weight: bold;">Topp 10</button>
        <button type="button" id="btn-all10" class="btn btn-primary btn-sm active" style="font-size: 12px; font-weight: bold;">Alla ytor</button>
        <button type="button" id="btn-bot10" class="btn btn-outline-danger btn-sm" style="font-size: 12px; font-weight: bold;">Lägsta 10</button>
    </div>

    <!-- Värmekarta -->
    <label class="form-label mb-0 fw-bold" style="font-size: 12px;"><i class="fas fa-fire text-warning"></i> Värmekarta (Ålder)</label>
    <select id="heatSelect" class="form-select form-select-sm mb-3" style="font-size: 13px;">
        <option value="none">Ingen värmekarta aktiv</option>
        <option value="tot">Totalt alla invånare</option>
        <option value="a0_5">Barn i förskoleålder (0-5 år)</option>
        <option value="a6_15">Barn i grundskoleålder (6-15 år)</option>
        <option value="a6_9">&nbsp;&nbsp;&nbsp;&nbsp;varav 6-9 år</option>
        <option value="a10_12">&nbsp;&nbsp;&nbsp;&nbsp;varav 10-12 år</option>
        <option value="a13_15">&nbsp;&nbsp;&nbsp;&nbsp;varav 13-15 år</option>
        <option value="a16_18">Ungdomar i gymnasieålder (16-18 år)</option>
        <option value="a19_64">Vuxna/Arbetsföra (19-64 år)</option>
        <option value="a19_34">&nbsp;&nbsp;&nbsp;&nbsp;varav 19-34 år</option>
        <option value="a35_64">&nbsp;&nbsp;&nbsp;&nbsp;varav 35-64 år</option>
        <option value="a65_79">Äldre (65-79 år)</option>
        <option value="a80">Äldst (80+ år)</option>
    </select>
    
    <label class="form-label mb-0 fw-bold" style="font-size: 12px;">Snabbzoom (Sök Område)</label>
    <select id="zoomSelect" class="form-select form-select-sm mb-3" style="font-size: 13px;"><option value="">-- Välj basområde --</option></select>
    
    <label class="form-label mb-0 fw-bold" style="font-size: 12px;">Zoom via Karaktär</label>
    <select id="charSelect" class="form-select form-select-sm mb-3" style="font-size: 13px;">
        <option value="">-- Välj karaktär/stadsdel --</option>
        <option value="Inre staden">Inre staden</option>
        <option value="Yttre staden">Yttre staden</option>
        <option value="Berga">Berga</option>
        <option value="Innerstaden">Innerstaden</option>
        <option value="Lambohov">Lambohov</option>
        <option value="Ryd">Ryd</option>
        <option value="Skäggetorp">Skäggetorp</option>
    </select>

    <hr style="margin: 15px 0;">
    <h6 class="fw-bold mb-2" style="font-size: 13px;">Geografiska mätverktyg</h6>
    <button id="btn-measure" class="btn btn-outline-primary w-100 mb-2" style="text-align: left; font-size: 16px; padding: 12px; font-weight: bold;"><i class="fas fa-ruler"></i> Avstånd till Centrum</button>
    <button id="btn-isochrone" class="btn btn-outline-info w-100 mb-2" style="text-align: left; font-size: 16px; padding: 12px; font-weight: bold;"><i class="fas fa-stopwatch"></i> 10-min Nåbarhetsanalys</button>
    <button id="btn-draw" class="btn btn-outline-success w-100" style="text-align: left; font-size: 16px; padding: 12px; font-weight: bold;"><i class="fas fa-draw-polygon"></i> Rita egen yta</button>
</div>

<div class="layers-panel">
    <h6 class="fw-bold mb-3" style="margin-top:0;"><i class="fas fa-layer-group text-primary"></i> Kartlager & Kontroller</h6>
    <select id="basemapSelect" class="form-select form-select-sm mb-3" style="font-size: 14px;">
        <option value="blek" selected>Blek (För tydlig analys)</option>
        <option value="farg">Färgstark (Detaljerad)</option>
        <option value="flyg">Flygfoton (Satellit)</option>
    </select>
    
    <hr style="margin: 15px 0;">
    <h6 class="fw-bold text-dark mb-2">SEI-nivåer (Styrkartan)</h6>
    <p style="font-size:11px; color:#666; margin-bottom:5px;">Kryssrutorna styr vilka områden som är aktiva för <b>alla</b> indikatorer nedan.</p>
    <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" id="radioSeiMode" value="none" checked><label class="form-check-label fw-bold text-primary" for="radioSeiMode">Visa SEI-färgning i kartan</label></div>
    
    <div class="form-check mb-2 pb-2 mt-2" style="border-bottom: 1px solid #ddd;">
        <input class="form-check-input" type="checkbox" id="toggleAllSei" checked>
        <label class="form-check-label fw-bold" for="toggleAllSei" style="font-size: 12px;">Markera / Avmarkera alla</label>
    </div>
    {sei_checkboxes_html}

    <hr style="margin: 15px 0;">
    <h6 class="fw-bold text-dark mb-2">Områdesnamn (SEI)</h6>
    <div class="form-check mb-1"><input class="form-check-input name-toggle" type="checkbox" value="1" id="toggleName_1"><label class="form-check-label" for="toggleName_1">Namn för SEI 1</label></div>
    <div id="namnCollapse" style="display: none; padding-left: 10px; border-left: 2px solid #ccc; margin-left: 5px;">
        <div class="form-check mb-1"><input class="form-check-input name-toggle" type="checkbox" value="2" id="toggleName_2"><label class="form-check-label" for="toggleName_2">Namn för SEI 2</label></div>
        <div class="form-check mb-1"><input class="form-check-input name-toggle" type="checkbox" value="6" id="toggleName_6"><label class="form-check-label" for="toggleName_6">Namn för SEI 6</label></div>
    </div>
    <a href="javascript:void(0);" id="toggleNamnBtn" class="d-block mt-1 mb-2" style="font-size: 12px; text-decoration: none; color: #3498db; font-weight: bold;"><i class="fas fa-chevron-down" id="namnIcon"></i> <span id="namnText">Visa fler nivåer...</span></a>

    <hr style="margin: 15px 0;">
    <h6 class="fw-bold text-dark mb-2">SEI-indikatorer</h6>
    <div id="seiIndCollapse" style="display: none; padding-left: 10px; border-left: 2px solid #ccc; margin-left: 5px;">
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_netink"> <label class="form-check-label">Nettoinkomst (tkr)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_forvink"> <label class="form-check-label">Förvärvsinkomst (tkr)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_syssel"> <label class="form-check-label">Sysselsättningsgrad (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_arblosa"> <label class="form-check-label">Inskrivna arbetslösa (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_ejsjalv"> <label class="form-check-label">Ej självförsörjande (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_bistand"> <label class="form-check-label">Långv. ekon. bistånd (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_barnfattig"> <label class="form-check-label">Barnfattigdom (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_lagekon"> <label class="form-check-label">Låg ekonomisk std (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_lagink"> <label class="form-check-label">Låg inkomststandard (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_trang"> <label class="form-check-label">Trångbodda hushåll (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_kvm"> <label class="form-check-label">Kvm per person</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_kvarboende"> <label class="form-check-label">Kvarboende minst tre år (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_ensam"> <label class="form-check-label">Ensamstående hushåll (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_ohalsa"> <label class="form-check-label">Ohälsotal 50-64 år (dagar)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_forgym"> <label class="form-check-label">Förgymnasial utbildning (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_forskola"> <label class="form-check-label">Inskrivna förskolebarn (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_behoriga"> <label class="form-check-label">Behöriga gymn. yrkesprogr. (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_uvas"> <label class="form-check-label">UVAS (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_utrfod"> <label class="form-check-label">Utrikes födda (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_utlbak"> <label class="form-check-label">Utländsk bakgrund (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="ind_val"> <label class="form-check-label">Valdeltagande (%)</label></div>
    </div>
    <a href="javascript:void(0);" id="toggleSeiIndBtn" class="d-block mt-1 mb-2" style="font-size: 12px; text-decoration: none; color: #3498db; font-weight: bold;"><i class="fas fa-chevron-down" id="seiIndIcon"></i> <span id="seiIndText">Visa indikatorer...</span></a>

    <hr style="margin: 15px 0;">
    <h6 class="fw-bold text-dark mb-2">SEI-koder (Trender)</h6>
    <div id="seiKoderCollapse" style="display: none; padding-left: 10px; border-left: 2px solid #ccc; margin-left: 5px;">
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="snitt15"> <label class="form-check-label">Snitt 15-19</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="snitt20"> <label class="form-check-label">Snitt 20-24</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="seichange"> <label class="form-check-label">Förändring SEI</label></div>
    </div>
    <a href="javascript:void(0);" id="toggleSeiKoderBtn" class="d-block mt-1 mb-2" style="font-size: 12px; text-decoration: none; color: #3498db; font-weight: bold;"><i class="fas fa-chevron-down" id="seiKoderIcon"></i> <span id="seiKoderText">Visa tidsperioder...</span></a>

    <hr style="margin: 15px 0;">
    <h6 class="fw-bold text-dark mb-2">Ytor & Områden</h6>
    <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" id="radioPop" value="pop"><label class="form-check-label" for="radioPop">Befolkning {latest_year}</label></div>
    <div id="ytorCollapse" style="display: none; padding-left: 10px; border-left: 2px solid #ccc; margin-left: 5px;">
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="dens" id="radioDens"> <label class="form-check-label" for="radioDens">Befolkningstäthet</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="hushall" id="radioHushall"> <label class="form-check-label" for="radioHushall">Hushållsstorlek</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="agan" id="radioAgan"> <label class="form-check-label" for="radioAgan">Äganderätt (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="bost" id="radioBost"> <label class="form-check-label" for="radioBost">Bostadsrätt (%)</label></div>
        <div class="form-check mb-1"><input class="form-check-input base-toggle" type="radio" name="baseArea" value="hyre" id="radioHyre"> <label class="form-check-label" for="radioHyre">Hyresrätt (%)</label></div>
    </div>
    <a href="javascript:void(0);" id="toggleYtorBtn" class="d-block mt-1 mb-2" style="font-size: 12px; text-decoration: none; color: #3498db; font-weight: bold;"><i class="fas fa-chevron-down" id="ytorIcon"></i> <span id="ytorText">Visa fler ytor...</span></a>
    
    <div class="form-check mt-3 pt-2" style="border-top: 1px solid #ccc;">
        <input class="form-check-input" type="checkbox" id="toggleBorders" checked>
        <label class="form-check-label fw-bold" for="toggleBorders">Visa Områdesgränser</label>
    </div>

    <hr style="margin: 15px 0;">
    <h6 class="fw-bold text-dark mb-2">Analyspunkter & Befolkning</h6>
    <div class="form-check mb-1"><input class="form-check-input pop-toggle" type="checkbox" value="Centrumpunkter" id="toggle_centroids"><label class="form-check-label" for="toggle_centroids"><i class="fas fa-dot-circle" style="color: #f1c40f; width:18px;"></i> Centrumpunkt (Demografisk)</label></div>
    <div id="analysCollapse" style="display: none; padding-left: 10px; border-left: 2px solid #ccc; margin-left: 5px;">
        <div class="form-check mb-1"><input class="form-check-input pop-toggle" type="checkbox" value="Befolkningsringar" id="toggle_pop_rings"><label class="form-check-label" for="toggle_pop_rings"><i class="fas fa-circle" style="color: #3498db; width:18px;"></i> Befolkningsringar (Trend)</label></div>
        <div class="form-check mb-1"><input class="form-check-input pop-toggle" type="checkbox" value="Detaljerad" id="toggleClusters"><label class="form-check-label" for="toggleClusters"><i class="fas fa-users" style="color: #3498db; width:18px;"></i> Detaljerad Befolkning (Kluster)</label></div>
        <div class="form-check mb-1"><input class="form-check-input pop-toggle" type="checkbox" value="Dynamisk" id="toggle_pop_dyn"><label class="form-check-label" for="toggle_pop_dyn"><i class="fas fa-users-cog" style="color: #3498db; width:18px;"></i> Dynamisk Befolkning</label></div>
    </div>
    <a href="javascript:void(0);" id="toggleAnalysBtn" class="d-block mt-1 mb-2" style="font-size: 12px; text-decoration: none; color: #3498db; font-weight: bold;"><i class="fas fa-chevron-down" id="analysIcon"></i> <span id="analysText">Visa fler analyspunkter...</span></a>
    
    <hr style="margin: 15px 0;">
    <h6 class="fw-bold text-dark mb-2">Intresseplatser (POI)</h6>
    <div class="form-check mb-1"><input class="form-check-input poi-toggle" type="checkbox" value="Grundskolor" id="toggle_grund"><label class="form-check-label" for="toggle_grund"><i class="fas fa-child" style="color: #3498db; width:18px;"></i> Grundskolor</label></div>
    <div id="poiCollapse" style="display: none; padding-left: 10px; border-left: 2px solid #ccc; margin-left: 5px;">
        <div class="form-check mb-1"><input class="form-check-input poi-toggle" type="checkbox" value="Gymnasieskolor" id="toggle_gymnas"><label class="form-check-label" for="toggle_gymnas"><i class="fas fa-graduation-cap" style="color: #9b59b6; width:18px;"></i> Gymnasieskolor</label></div>
        <div class="form-check mb-1"><input class="form-check-input poi-toggle" type="checkbox" value="Handel & Centrum" id="toggle_handel"><label class="form-check-label" for="toggle_handel"><i class="fas fa-shopping-cart" style="color: #f39c12; width:18px;"></i> Handel & Centrum</label></div>
        <div class="form-check mb-1"><input class="form-check-input poi-toggle" type="checkbox" value="Idrott & Fritid" id="toggle_idrott"><label class="form-check-label" for="toggle_idrott"><i class="fas fa-running" style="color: #2ecc71; width:18px;"></i> Idrott & Fritid</label></div>
        <div class="form-check mb-1"><input class="form-check-input poi-toggle" type="checkbox" value="Kultur & Sevärdheter" id="toggle_kultur"><label class="form-check-label" for="toggle_kultur"><i class="fas fa-theater-masks" style="color: #e67e22; width:18px;"></i> Kultur & Sevärdheter</label></div>
        <div class="form-check mb-1"><input class="form-check-input poi-toggle" type="checkbox" value="Samhälle & Infrastruktur" id="toggle_samhalle"><label class="form-check-label" for="toggle_samhalle"><i class="fas fa-building" style="color: #e74c3c; width:18px;"></i> Samhälle & Infrastruktur</label></div>
        <div class="form-check mb-1"><input class="form-check-input poi-toggle" type="checkbox" value="Övriga platser" id="toggle_ovriga"><label class="form-check-label" for="toggle_ovriga"><i class="fas fa-map-marker-alt" style="color: #95a5a6; width:18px;"></i> Övriga platser</label></div>
        <div class="form-check mb-1"><input class="form-check-input poi-toggle" type="checkbox" value="Vårdboende" id="toggle_vard" {vard_disabled}><label class="form-check-label" for="toggle_vard"><i class="fas fa-heartbeat" style="color: #e74c3c; width:18px;"></i> {vard_text}</label></div>
    </div>
    <a href="javascript:void(0);" id="togglePoiBtn" class="d-block mt-1 mb-2" style="font-size: 12px; text-decoration: none; color: #3498db; font-weight: bold;"><i class="fas fa-chevron-down" id="poiIcon"></i> <span id="poiText">Visa fler platser...</span></a>

    <hr style="margin: 15px 0;">
    <h6 class="fw-bold text-dark">Infrastruktur & Natur</h6>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleStanga"><label class="form-check-label" for="toggleStanga">🏘️ Stångåstadens områden</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleTransport"><label class="form-check-label" for="toggleTransport">🛤️ Transportleder (Väg/Järnväg)</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleVatten"><label class="form-check-label" for="toggleVatten">💧 Sjöar & Vattendrag</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleMikro"><label class="form-check-label" for="toggleMikro">🌡️ Mikroklimat</label></div>
    
    <button id="btn-zoom-selected" class="btn btn-outline-secondary w-100 shadow-sm mt-3" style="text-align: left; font-size: 14px; padding: 10px; font-weight: bold;"><i class="fas fa-search-location"></i> Zooma till valda platser</button>
</div>

<script src="https://unpkg.com/leaflet.heat/dist/leaflet-heat.js"></script>

<script>
    document.addEventListener('DOMContentLoaded', function() {{
        var map_id = Object.keys(window).find(key => key.startsWith('map_'));
        var map = window[map_id];
        
        var initialBounds = {initial_bounds_js};
        map.fitBounds(initialBounds);

        map.createPane('analysPane');
        map.getPane('analysPane').style.zIndex = 600;
        
        map.createPane('stangaPane'); 
        map.getPane('stangaPane').style.zIndex = 460; 

        map.createPane('mikroPane'); 
        map.getPane('mikroPane').style.zIndex = 455;

        window.measureModeActive = false; 
        window.isochroneModeActive = false;
        window.drawModeActive = false;

        var nykoData = window.nykoData || []; 
        var popHistData = window.popHistData || {{}};
        var excelPois = window.excelPois || [];
        var heatDataRaw = window.heatDataRaw || [];
        var dynPop1 = window.dynPop1 || [];
        var dynPop3 = window.dynPop3 || [];
        var dynPop4 = window.dynPop4 || [];
        var dynPop6 = window.dynPop6 || [];
        var transportData = window.transportData;
        var vattenData = window.vattenData;
        var stangaData = window.stangaData;
        var mikroData = window.mikroData;

        window.showToast = function(msg) {{
            var t = document.getElementById('toastMessage');
            t.innerHTML = msg;
            t.style.display = 'block';
            t.style.opacity = '1';
            setTimeout(function() {{ 
                t.style.opacity = '0'; 
                setTimeout(function(){{ t.style.display = 'none'; }}, 500); 
            }}, 3000);
        }}

        window.showInfoPanel = function(htmlContent, titleText = '📊 Information') {{
            document.getElementById('infoTitle').innerText = titleText;
            document.getElementById('infoPanelContent').innerHTML = htmlContent;
            document.getElementById('infoPanel').style.display = 'block';
        }}
        
        window.closeInfoPanel = function() {{ document.getElementById('infoPanel').style.display = 'none'; }}
        function formatNumber(num) {{ return num ? num.toString().replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, " ") : "0"; }}

        function bindCollapse(btnId, collId, iconId, textId, showText, hideText) {{
            document.getElementById(btnId).addEventListener('click', function(e) {{
                e.preventDefault();
                var coll = document.getElementById(collId);
                var icon = document.getElementById(iconId);
                var text = document.getElementById(textId);
                if (coll.style.display === 'none') {{
                    coll.style.display = 'block'; icon.className = 'fas fa-chevron-up'; text.innerText = hideText;
                }} else {{
                    coll.style.display = 'none'; icon.className = 'fas fa-chevron-down'; text.innerText = showText;
                }}
            }});
        }}
        bindCollapse('toggleSeiIndBtn', 'seiIndCollapse', 'seiIndIcon', 'seiIndText', 'Visa indikatorer...', 'Dölj indikatorer...');
        bindCollapse('toggleSeiKoderBtn', 'seiKoderCollapse', 'seiKoderIcon', 'seiKoderText', 'Visa tidsperioder...', 'Dölj tidsperioder...');
        bindCollapse('toggleYtorBtn', 'ytorCollapse', 'ytorIcon', 'ytorText', 'Visa fler ytor...', 'Dölj ytor...');
        bindCollapse('toggleAnalysBtn', 'analysCollapse', 'analysIcon', 'analysText', 'Visa fler analyspunkter...', 'Dölj analyspunkter...');
        bindCollapse('togglePoiBtn', 'poiCollapse', 'poiIcon', 'poiText', 'Visa fler platser...', 'Dölj platser...');
        bindCollapse('toggleNamnBtn', 'namnCollapse', 'namnIcon', 'namnText', 'Visa fler nivåer...', 'Dölj nivåer...');

        var cSel = document.getElementById('charSelect');
        var activeCharFilter = "";
        
        var districtCodes = {{
            "Berga": ["1411", "1412", "1413", "1414", "1415"],
            "Innerstaden": ["1331", "1332", "1333", "1334", "1335", "1336", "1337"],
            "Lambohov": ["1521", "1522", "1523", "1524"],
            "Ryd": ["1111", "1112", "1113", "1114", "1115", "1116", "1117"],
            "Skäggetorp": ["1121", "1122", "1123", "1124"]
        }};

        var topBotFilter = 'all';
        document.getElementById('btn-all10').addEventListener('click', function() {{
            topBotFilter = 'all';
            this.classList.replace('btn-outline-primary', 'btn-primary');
            document.getElementById('btn-top10').classList.replace('btn-success', 'btn-outline-success');
            document.getElementById('btn-bot10').classList.replace('btn-danger', 'btn-outline-danger');
            updatePolygonVisibility(false);
        }});
        document.getElementById('btn-top10').addEventListener('click', function() {{
            topBotFilter = 'top10';
            this.classList.replace('btn-outline-success', 'btn-success');
            document.getElementById('btn-all10').classList.replace('btn-primary', 'btn-outline-primary');
            document.getElementById('btn-bot10').classList.replace('btn-danger', 'btn-outline-danger');
            updatePolygonVisibility(false);
        }});
        document.getElementById('btn-bot10').addEventListener('click', function() {{
            topBotFilter = 'bot10';
            this.classList.replace('btn-outline-danger', 'btn-danger');
            document.getElementById('btn-all10').classList.replace('btn-primary', 'btn-outline-primary');
            document.getElementById('btn-top10').classList.replace('btn-success', 'btn-outline-success');
            updatePolygonVisibility(false);
        }});

        var legendData = {{
            'pop': {{ title: 'Befolkning {latest_year} (inv)', min: {m_pop}, max: {mx_pop}, grad: '{", ".join(viridis_rev)}' }},
            'dens': {{ title: 'Täthet (inv/km²)', min: {m_dens}, max: {mx_dens}, grad: '{", ".join(viridis_rev)}' }},
            'hushall': {{ title: 'Hushållsstorlek (snitt)', min: {max(0, m_hush-0.2)}, max: {mx_hush+0.2}, grad: '{", ".join(viridis_rev)}' }},
            'agan': {{ title: 'Äganderätt (%)', min: 0, max: 100, grad: '{", ".join(viridis_rev)}' }},
            'bost': {{ title: 'Bostadsrätt (%)', min: 0, max: 100, grad: '{", ".join(viridis_rev)}' }},
            'hyre': {{ title: 'Hyresrätt (%)', min: 0, max: 100, grad: '{", ".join(viridis_rev)}' }},
            
            'ind_netink': {{ title: 'Nettoinkomst (tkr)', min: {m_netink}, max: {mx_netink}, grad: '{", ".join(pal_green)}' }},
            'ind_forvink': {{ title: 'Förvärvsinkomst (tkr)', min: {m_forvink}, max: {mx_forvink}, grad: '{", ".join(pal_green)}' }},
            'ind_syssel': {{ title: 'Sysselsättningsgrad (%)', min: {m_syssel}, max: {mx_syssel}, grad: '{", ".join(pal_blue)}' }},
            'ind_arblosa': {{ title: 'Inskrivna arbetslösa (%)', min: {m_arblosa}, max: {mx_arblosa}, grad: '{", ".join(pal_red)}' }},
            'ind_ejsjalv': {{ title: 'Ej självförsörjande (%)', min: {m_ejsjalv}, max: {mx_ejsjalv}, grad: '{", ".join(pal_red)}' }},
            'ind_bistand': {{ title: 'Långv. ekon. bistånd (%)', min: {m_bistand}, max: {mx_bistand}, grad: '{", ".join(pal_red)}' }},
            'ind_barnfattig': {{ title: 'Barnfattigdom (%)', min: {m_barnfattig}, max: {mx_barnfattig}, grad: '{", ".join(pal_red)}' }},
            'ind_lagekon': {{ title: 'Låg ekonomisk std (%)', min: {m_lagekon}, max: {mx_lagekon}, grad: '{", ".join(pal_red)}' }},
            'ind_lagink': {{ title: 'Låg inkomststandard (%)', min: {m_lagink}, max: {mx_lagink}, grad: '{", ".join(pal_red)}' }},
            'ind_trang': {{ title: 'Trångbodda hushåll (%)', min: {m_trang}, max: {mx_trang}, grad: '{", ".join(pal_red)}' }},
            'ind_kvm': {{ title: 'Kvm per person', min: {m_kvm}, max: {mx_kvm}, grad: '{", ".join(pal_purp)}' }},
            'ind_kvarboende': {{ title: 'Kvarboende minst tre år (%)', min: {m_kvarboende}, max: {mx_kvarboende}, grad: '{", ".join(pal_blue)}' }},
            'ind_ensam': {{ title: 'Ensamstående hushåll (%)', min: {m_ensam}, max: {mx_ensam}, grad: '{", ".join(pal_purp)}' }},
            'ind_ohalsa': {{ title: 'Ohälsotal 50-64 år (dagar)', min: {m_ohalsa}, max: {mx_ohalsa}, grad: '{", ".join(pal_red)}' }},
            'ind_forgym': {{ title: 'Förgymnasial utbildning (%)', min: {m_forgym}, max: {mx_forgym}, grad: '{", ".join(pal_orng)}' }},
            'ind_forskola': {{ title: 'Inskrivna förskolebarn (%)', min: {m_forskola}, max: {mx_forskola}, grad: '{", ".join(pal_blue)}' }},
            'ind_behoriga': {{ title: 'Behöriga gymn. yrkesprogr. (%)', min: {m_behoriga}, max: {mx_behoriga}, grad: '{", ".join(pal_blue)}' }},
            'ind_uvas': {{ title: 'UVAS (%)', min: {m_uvas}, max: {mx_uvas}, grad: '{", ".join(pal_red)}' }},
            'ind_utrfod': {{ title: 'Utrikes födda (%)', min: {m_utrfod}, max: {mx_utrfod}, grad: '{", ".join(pal_purp)}' }},
            'ind_utlbak': {{ title: 'Utländsk bakgrund (%)', min: {m_utlbak}, max: {mx_utlbak}, grad: '{", ".join(pal_purp)}' }},
            'ind_val': {{ title: 'Valdeltagande (%)', min: {m_val}, max: {mx_val}, grad: '{", ".join(pal_blue)}' }},
            
            'snitt15': {{ title: 'SEI Snitt 15-19', min: {m_snitt15}, max: {mx_snitt15}, grad: '{", ".join(viridis_rev)}' }},
            'snitt20': {{ title: 'SEI Snitt 20-24', min: {m_snitt20}, max: {mx_snitt20}, grad: '{", ".join(viridis_rev)}' }},
            'seichange': {{ title: 'Förändring SEI', min: -1.5, max: 1.5, grad: '#e74c3c 0%, #e74c3c 45%, #f1c40f 45%, #f1c40f 55%, #2ecc71 55%, #2ecc71 100%' }}
        }};

        var labelLayers = {{ 1: L.layerGroup(), 2: L.layerGroup(), 6: L.layerGroup() }};
        nykoData.forEach(d => {{
            var lvl = Math.round(d.sei_index);
            if (lvl === 1 || lvl === 2 || lvl === 6) {{
                var icon = L.divIcon({{
                    className: 'sei-label',
                    html: `<div style="color: #333; font-weight: 900; font-size: 11px; text-shadow: 1px 1px 2px #fff, -1px -1px 2px #fff, 1px -1px 2px #fff, -1px 1px 2px #fff; white-space: nowrap; transform: translate(-50%, -50%);">${{d.namn}}</div>`,
                    iconSize: [0, 0]
                }});
                var marker = L.marker([d.lat, d.lon], {{icon: icon, interactive: false}});
                labelLayers[lvl].addLayer(marker);
            }}
        }});
        document.querySelectorAll('.name-toggle').forEach(cb => {{
            cb.addEventListener('change', function() {{
                var lvl = parseInt(this.value);
                if (this.checked) map.addLayer(labelLayers[lvl]);
                else map.removeLayer(labelLayers[lvl]);
            }});
        }});

        function updatePolygonVisibility(doZoom) {{
            var activeBase = document.querySelector('input[name="baseArea"]:checked').value;
            var showBorders = document.getElementById('toggleBorders').checked;
            var currentOpacity = document.getElementById('opacitySlider').value;
            document.getElementById('opacityVal').innerText = Math.round(currentOpacity * 100) + '%';
            
            var isFlyg = document.getElementById('basemapSelect').value === 'flyg';
            var defaultBorder = isFlyg ? '#ffffff' : '#2c3e50';
            
            var lBox = document.getElementById('dynamic-legend');
            if (activeBase === 'none') {{
                lBox.style.display = 'none';
            }} else {{
                var l = legendData[activeBase];
                if (l) {{
                    lBox.style.display = 'block';
                    document.getElementById('dl-title').innerText = l.title;
                    document.getElementById('dl-grad').style.background = 'linear-gradient(to right, ' + l.grad + ')';
                    document.getElementById('dl-min').innerText = parseFloat(l.min).toFixed(1);
                    document.getElementById('dl-max').innerText = parseFloat(l.max).toFixed(1);
                    if (activeBase === 'seichange') {{
                        document.getElementById('dl-min').innerText = 'Sämre';
                        document.getElementById('dl-max').innerText = 'Bättre';
                    }}
                }}
            }}

            var matchedAreas = [];
            nykoData.forEach(d => {{
                var matchesChar = true;
                if (activeCharFilter !== "") {{
                    matchesChar = false;
                    if (d) {{
                        if (activeCharFilter === "Inre staden" || activeCharFilter === "Yttre staden") {{
                            matchesChar = (d.char2 === activeCharFilter);
                        }} else if (districtCodes[activeCharFilter]) {{
                            matchesChar = districtCodes[activeCharFilter].includes(d.kod);
                        }} else {{
                            matchesChar = (d.namn.includes(activeCharFilter) || d.char2 === activeCharFilter);
                        }}
                    }}
                }}

                var cb = document.getElementById('toggleSei_' + Math.round(d.sei_index));
                var matchesSei = cb ? cb.checked : true;
                if (matchesChar && matchesSei) matchedAreas.push(d);
            }});

            if (topBotFilter !== 'all' && activeBase !== 'none') {{
                var propMapKeys = {{
                    'pop': 'folkmangd', 'dens': 'inv_per_km2', 'hushall': 'hushall',
                    'agan': 'agan_pct', 'bost': 'bost_pct', 'hyre': 'hyre_pct',
                    'ind_netink': 'ind_netink', 'ind_forvink': 'ind_forvink', 'ind_syssel': 'ind_syssel',
                    'ind_arblosa': 'ind_arblosa', 'ind_ejsjalv': 'ind_ejsjalv', 'ind_bistand': 'ind_bistand',
                    'ind_barnfattig': 'ind_barnfattig', 'ind_lagekon': 'ind_lagekon',
                    'ind_lagink': 'ind_lagink', 'ind_trang': 'ind_trang', 'ind_kvm': 'ind_kvm',
                    'ind_kvarboende': 'ind_kvarboende', 'ind_ensam': 'ind_ensam', 'ind_ohalsa': 'ind_ohalsa', 
                    'ind_forgym': 'ind_forgym', 'ind_forskola': 'ind_forskola', 'ind_behoriga': 'ind_behoriga', 'ind_uvas': 'ind_uvas',
                    'ind_utrfod': 'ind_utrfod', 'ind_utlbak': 'ind_utlbak', 'ind_val': 'ind_val',
                    'snitt15': 'snitt_15_19', 'snitt20': 'snitt_20_24', 'seichange': 'sei_change'
                }};
                var prop = propMapKeys[activeBase];
                if (prop) {{
                    var validAreas = matchedAreas.filter(a => a[prop] !== null && (prop === 'sei_change' ? true : a[prop] > 0));
                    validAreas.sort((a, b) => b[prop] - a[prop]); 
                    if (topBotFilter === 'top10') matchedAreas = validAreas.slice(0, 10);
                    else if (topBotFilter === 'bot10') matchedAreas = validAreas.slice(-10);
                }}
            }}

            var matchedNames = new Set(matchedAreas.map(d => d.namn));
            var baseToClass = {{
                'pop': 'pop-polygon', 'dens': 'density-polygon', 'hushall': 'hushall-polygon',
                'agan': 'agan-polygon', 'bost': 'bost-polygon', 'hyre': 'hyre-polygon',
                'ind_netink': 'ind-netink-polygon', 'ind_forvink': 'ind-forvink-polygon', 'ind_syssel': 'ind-syssel-polygon',
                'ind_arblosa': 'ind-arblosa-polygon', 'ind_ejsjalv': 'ind-ejsjalv-polygon', 'ind_bistand': 'ind-bistand-polygon',
                'ind_barnfattig': 'ind-barnfattig-polygon', 'ind_lagekon': 'ind-lagekon-polygon',
                'ind_lagink': 'ind-lagink-polygon', 'ind_trang': 'ind-trang-polygon', 'ind_kvm': 'ind-kvm-polygon',
                'ind_kvarboende': 'ind-kvarboende-polygon', 'ind_ensam': 'ind-ensam-polygon', 'ind_ohalsa': 'ind-ohalsa-polygon', 
                'ind_forgym': 'ind-forgym-polygon', 'ind_forskola': 'ind-forskola-polygon', 'ind_behoriga': 'ind-behoriga-polygon', 'ind_uvas': 'ind-uvas-polygon',
                'ind_utrfod': 'ind-utrfod-polygon', 'ind_utlbak': 'ind-utlbak-polygon', 'ind_val': 'ind-val-polygon',
                'snitt15': 'snitt15-polygon', 'snitt20': 'snitt20-polygon', 'seichange': 'seichange-polygon'
            }};

            map.eachLayer(function(layer) {{
                if (layer.options && layer.options.className && layer.options.className.includes('polygon-layer')) {{
                    var name = layer.feature.properties.NAMN;
                    var d = nykoData.find(x => x.namn === name);
                    
                    var matchesChar = true;
                    if (activeCharFilter !== "") {{
                        matchesChar = false;
                        if (d) {{
                            if (activeCharFilter === "Inre staden" || activeCharFilter === "Yttre staden") {{
                                matchesChar = (d.char2 === activeCharFilter);
                            }} else if (districtCodes[activeCharFilter]) {{
                                matchesChar = districtCodes[activeCharFilter].includes(d.kod);
                            }} else {{
                                matchesChar = (d.namn.includes(activeCharFilter) || d.char2 === activeCharFilter);
                            }}
                        }}
                    }}

                    var cb = d ? document.getElementById('toggleSei_' + Math.round(d.sei_index)) : null;
                    var matchesSei = cb ? cb.checked : true;
                    var isMatched = matchedNames.has(name);

                    var cls = layer.options.className;
                    var isVisible = false;
                    var polyWeight = 0;
                    var polyColor = 'transparent';
                    
                    if (cls.includes('border-polygon')) {{
                        isVisible = showBorders && matchesChar;
                        polyWeight = 1;
                        polyColor = isVisible ? defaultBorder : 'transparent';
                        layer.setStyle({{ opacity: isVisible ? 1 : 0, fillOpacity: 0, weight: polyWeight, color: polyColor }});
                        layer.mySavedStyle = {{ opacity: isVisible ? 1 : 0, fillOpacity: 0, weight: polyWeight, color: polyColor }};
                    }} 
                    else {{
                        if (activeBase === 'none' && cls.includes('sei-polygon')) {{
                            isVisible = matchesChar && matchesSei;
                        }}
                        else if (baseToClass[activeBase] && cls.includes(baseToClass[activeBase])) {{
                            isVisible = isMatched;
                        }}

                        if (isVisible && activeBase !== 'none') {{
                            polyWeight = 1;
                            polyColor = isFlyg ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.3)';
                        }}

                        layer.setStyle({{ fillOpacity: isVisible ? currentOpacity : 0, weight: polyWeight, color: polyColor }});
                        layer.mySavedStyle = {{ fillOpacity: isVisible ? currentOpacity : 0, opacity: layer.options.opacity, weight: polyWeight, color: polyColor }};
                    }}
                    
                    if (layer._path) layer._path.style.pointerEvents = isMatched && (isVisible || cls.includes('border-polygon')) ? 'auto' : 'none';
                }}
            }});
        }}

        // ZOOM TILL SPECIFIK KARAKTÄR DIREKT FRÅN RULLISTAN
        cSel.addEventListener('change', e => {{ 
            activeCharFilter = e.target.value; 
            updatePolygonVisibility(false); 
            
            if (activeCharFilter !== "") {{
                var bounds = L.latLngBounds();
                var found = false;
                map.eachLayer(function(layer) {{
                    if (layer.options && layer.options.className && layer.options.className.includes('border-polygon')) {{
                        var name = layer.feature.properties.NAMN;
                        var d = nykoData.find(x => x.namn === name);
                        if (d) {{
                            var isMatch = false;
                            if (activeCharFilter === "Inre staden" || activeCharFilter === "Yttre staden") {{
                                isMatch = (d.char2 === activeCharFilter);
                            }} else if (districtCodes[activeCharFilter]) {{
                                isMatch = districtCodes[activeCharFilter].includes(d.kod);
                            }} else {{
                                isMatch = (d.namn.includes(activeCharFilter) || d.char2 === activeCharFilter);
                            }}
                            if (isMatch) {{
                                bounds.extend(layer.getBounds());
                                found = true;
                            }}
                        }}
                    }}
                }});
                if (found) map.fitBounds(bounds, {{padding: [40,40]}});
            }} else {{
                map.fitBounds(initialBounds);
            }}
        }});

        // Smart Zoom till valda platser (Lösningen för att respektera alla valda polygoner)
        var btnZoom = document.getElementById('btn-zoom-selected');
        if (btnZoom) {{
            btnZoom.addEventListener('click', function() {{
                var bounds = L.latLngBounds();
                var found = false;
                
                // 1. Kolla POI-grupper
                var poiActive = false;
                Object.values(poiGroups).forEach(group => {{
                    if (map.hasLayer(group) && group.getLayers().length > 0) {{
                        bounds.extend(group.getBounds());
                        found = true;
                        poiActive = true;
                    }}
                }});

                // 2. Beräkna exakt vilka ytor som faktiskt är filtrerade
                var activeBase = document.querySelector('input[name="baseArea"]:checked').value;
                var tempMatched = [];
                nykoData.forEach(d => {{
                    var matchesChar = true;
                    if (activeCharFilter !== "") {{
                        matchesChar = false;
                        if (activeCharFilter === "Inre staden" || activeCharFilter === "Yttre staden") {{
                            matchesChar = (d.char2 === activeCharFilter);
                        }} else if (districtCodes[activeCharFilter]) {{
                            matchesChar = districtCodes[activeCharFilter].includes(d.kod);
                        }} else {{
                            matchesChar = (d.namn.includes(activeCharFilter) || d.char2 === activeCharFilter);
                        }}
                    }}
                    var cb = document.getElementById('toggleSei_' + Math.round(d.sei_index));
                    var matchesSei = cb ? cb.checked : true;
                    if (matchesChar && matchesSei) tempMatched.push(d);
                }});

                if (topBotFilter !== 'all' && activeBase !== 'none') {{
                    var propMapKeys = {{
                        'pop': 'folkmangd', 'dens': 'inv_per_km2', 'hushall': 'hushall',
                        'agan': 'agan_pct', 'bost': 'bost_pct', 'hyre': 'hyre_pct',
                        'ind_netink': 'ind_netink', 'ind_forvink': 'ind_forvink', 'ind_syssel': 'ind_syssel',
                        'ind_arblosa': 'ind_arblosa', 'ind_ejsjalv': 'ind_ejsjalv', 'ind_bistand': 'ind_bistand',
                        'ind_barnfattig': 'ind_barnfattig', 'ind_lagekon': 'ind_lagekon',
                        'ind_lagink': 'ind_lagink', 'ind_trang': 'ind_trang', 'ind_kvm': 'ind_kvm',
                        'ind_kvarboende': 'ind_kvarboende', 'ind_ensam': 'ind_ensam', 'ind_ohalsa': 'ind_ohalsa', 
                        'ind_forgym': 'ind_forgym', 'ind_forskola': 'ind_forskola', 'ind_behoriga': 'ind_behoriga', 'ind_uvas': 'ind_uvas',
                        'ind_utrfod': 'ind_utrfod', 'ind_utlbak': 'ind_utlbak', 'ind_val': 'ind_val',
                        'snitt15': 'snitt_15_19', 'snitt20': 'snitt_20_24', 'seichange': 'sei_change'
                    }};
                    var prop = propMapKeys[activeBase];
                    if (prop) {{
                        var validAreas = tempMatched.filter(a => a[prop] !== null && (prop === 'sei_change' ? true : a[prop] > 0));
                        validAreas.sort((a, b) => b[prop] - a[prop]); 
                        if (topBotFilter === 'top10') tempMatched = validAreas.slice(0, 10);
                        else if (topBotFilter === 'bot10') tempMatched = validAreas.slice(-10);
                    }}
                }}
                
                var matchedNames = new Set(tempMatched.map(d => d.namn));
                var allSeiChecked = document.getElementById('toggleAllSei').checked;
                var isFilteringPolygons = activeCharFilter !== "" || topBotFilter !== 'all' || !allSeiChecked;

                // Om vi filtrerar polygoner aktivt ELLER inte tittar på POI -> Zooma till polygonerna
                if (isFilteringPolygons || !poiActive) {{
                    map.eachLayer(function(layer) {{
                        if (layer.options && layer.options.className && layer.options.className.includes('polygon-layer') && !layer.options.className.includes('border-polygon')) {{
                            if (layer.feature && layer.feature.properties && matchedNames.has(layer.feature.properties.NAMN)) {{
                                if (layer.getBounds) {{
                                    bounds.extend(layer.getBounds());
                                    found = true;
                                }}
                            }}
                        }}
                    }});
                }}

                if (found) {{
                    map.fitBounds(bounds, {{padding: [40,40]}});
                }} else {{
                    map.fitBounds(initialBounds);
                }}
            }});
        }}

        document.querySelectorAll('.base-toggle').forEach(r => r.addEventListener('change', () => updatePolygonVisibility(false)));
        document.getElementById('toggleBorders').addEventListener('change', () => updatePolygonVisibility(false));
        document.getElementById('opacitySlider').addEventListener('input', () => updatePolygonVisibility(false));
        
        var seiCheckboxes = document.querySelectorAll('.sei-toggle');
        seiCheckboxes.forEach(cb => cb.addEventListener('change', function() {{
            var allChecked = Array.from(seiCheckboxes).every(c => c.checked);
            document.getElementById('toggleAllSei').checked = allChecked;
            updatePolygonVisibility(false);
        }}));

        document.getElementById('toggleAllSei').addEventListener('change', function(e) {{
            var isChecked = this.checked;
            seiCheckboxes.forEach(cb => cb.checked = isChecked);
            updatePolygonVisibility(false);
        }});
        
        document.getElementById('zoomSelect').addEventListener('change', function(e) {{
            var namn = e.target.value; if(!namn) return;
            map.eachLayer(function(layer) {{
                if (layer.feature && layer.feature.properties && layer.feature.properties.NAMN === namn && layer.options.className.includes('border-polygon')) {{
                    map.fitBounds(layer.getBounds(), {{padding: [50,50]}});
                    showAreaInfo(namn);
                }}
            }});
        }});

        // --- ÅTERSTÄLL & RENSA ALLT ---
        document.getElementById('btn-reset').addEventListener('click', function() {{
            cSel.value = ""; activeCharFilter = "";
            document.getElementById('zoomSelect').value = "";
            document.getElementById('btn-all10').click(); 
            document.getElementById('radioSeiMode').checked = true;
            document.querySelectorAll('.pop-toggle, .poi-toggle, .name-toggle').forEach(cb => {{ cb.checked = false; cb.dispatchEvent(new Event('change')); }});
            document.getElementById('toggleBorders').checked = true;
            document.getElementById('toggleAllSei').checked = true;
            seiCheckboxes.forEach(cb => cb.checked = true);
            document.getElementById('heatSelect').value = 'none';
            document.getElementById('heatSelect').dispatchEvent(new Event('change'));
            if (window.measureModeActive) document.getElementById('btn-measure').click();
            if (window.isochroneModeActive) document.getElementById('btn-isochrone').click();
            if (window.drawModeActive) document.getElementById('btn-draw').click();
            
            if (typeof drawLayer !== 'undefined') drawLayer.clearLayers(); 
            
            if (document.getElementById('toggleStanga') && document.getElementById('toggleStanga').checked) document.getElementById('toggleStanga').click();
            if (document.getElementById('toggleMikro') && document.getElementById('toggleMikro').checked) document.getElementById('toggleMikro').click();
            
            map.fitBounds(initialBounds);
            document.getElementById('opacitySlider').value = 0.60;
            updatePolygonVisibility(false);
            window.closeInfoPanel();
        }});

        // --- TABBAD POPUP & DIAGRAM ---
        var upplatelseChartInstans = null;
        var popChartInstans = null;
        var seiLabels = {{ 1: "Stora utmaningar", 2: "Betydande utmaningar", 3: "Stabila förutsättningar", 4: "Goda förutsättningar", 5: "Välmående", 6: "Mycket välmående" }};

        window.resizePieChart = function() {{
            setTimeout(function() {{ if (upplatelseChartInstans) upplatelseChartInstans.resize(); }}, 50);
        }}

        function showAreaInfo(namn) {{
            var d = nykoData.find(nd => nd.namn === namn);
            if(!d) return;
            
            var seiText = seiLabels[Math.round(d.sei_index)] || "Okänd nivå";
            var pWidth = d.sei_index ? (d.sei_index/6)*100 : 0;
            
            var hist = popHistData[namn];
            var dispHushall = (d.hushall_visa !== '-' && d.hushall_visa !== '0') ? d.hushall_visa : (d.hushall > 0 ? d.hushall : '-');
            var isSec = d.folkmangd > 0 && d.folkmangd < 5;

            var chartHtml = (hist && hist.labels && hist.labels.length > 0 && !isSec) ? `<div style="height: 180px; width: 100%; position: relative;"><canvas id="popChartCanvas"></canvas></div>` : `<p style="color:#999; font-style:italic;">Data saknas/Sekretess</p>`;
            var pieHtml = (d.tot_uppl > 0 && !isSec) ? `<div style="height: 180px; width: 100%; position: relative;"><canvas id="upplatelsePieChart"></canvas></div>` : `<p style="color:#999; font-style:italic;">Data saknas/Sekretess</p>`;

            // Säkra alla variabler från att orsaka f-strängskraschar
            var vNetink = isSec || d.ind_netink == null || d.ind_netink <= 0 ? '-' : d.ind_netink + ' tkr';
            var vForvink = isSec || d.ind_forvink == null || d.ind_forvink <= 0 ? '-' : d.ind_forvink + ' tkr';
            var vSyssel = isSec || d.ind_syssel == null || d.ind_syssel <= 0 ? '-' : d.ind_syssel + ' %';
            var vArblosa = isSec || d.ind_arblosa == null || d.ind_arblosa <= 0 ? '-' : d.ind_arblosa + ' %';
            var vEjsjalv = isSec || d.ind_ejsjalv == null || d.ind_ejsjalv <= 0 ? '-' : d.ind_ejsjalv + ' %';
            var vBistand = isSec || d.ind_bistand == null || d.ind_bistand <= 0 ? '-' : d.ind_bistand + ' %';
            var vBarnfattig = isSec || d.ind_barnfattig == null || d.ind_barnfattig <= 0 ? '-' : d.ind_barnfattig + ' %';
            var vLagekon = isSec || d.ind_lagekon == null || d.ind_lagekon <= 0 ? '-' : d.ind_lagekon + ' %';
            var vLagink = isSec || d.ind_lagink == null || d.ind_lagink <= 0 ? '-' : d.ind_lagink + ' %';
            var vTrang = isSec || d.ind_trang == null || d.ind_trang <= 0 ? '-' : d.ind_trang + ' %';
            var vKvm = isSec || d.ind_kvm == null || d.ind_kvm <= 0 ? '-' : d.ind_kvm;
            var vKvarboende = isSec || d.ind_kvarboende == null || d.ind_kvarboende <= 0 ? '-' : d.ind_kvarboende + ' %';
            var vEnsam = isSec || d.ind_ensam == null || d.ind_ensam <= 0 ? '-' : d.ind_ensam + ' %';
            var vOhalsa = isSec || d.ind_ohalsa == null || d.ind_ohalsa <= 0 ? '-' : d.ind_ohalsa;
            var vForgym = isSec || d.ind_forgym == null || d.ind_forgym <= 0 ? '-' : d.ind_forgym + ' %';
            var vForskola = isSec || d.ind_forskola == null || d.ind_forskola <= 0 ? '-' : d.ind_forskola + ' %';
            var vBehoriga = isSec || d.ind_behoriga == null || d.ind_behoriga <= 0 ? '-' : d.ind_behoriga + ' %';
            var vUvas = isSec || d.ind_uvas == null || d.ind_uvas <= 0 ? '-' : d.ind_uvas + ' %';
            var vUtrfod = isSec || d.ind_utrfod == null || d.ind_utrfod <= 0 ? '-' : d.ind_utrfod + ' %';
            var vUtlbak = isSec || d.ind_utlbak == null || d.ind_utlbak <= 0 ? '-' : d.ind_utlbak + ' %';
            var vVal = isSec || d.ind_val == null || d.ind_val <= 0 ? '-' : d.ind_val + ' %';
            var vHyre = isSec ? '-' : d.hyre_pct + ' %';
            var vHushall = isSec || dispHushall === '-' ? '-' : dispHushall + ' pers';
            var vTotUppl = isSec ? '-' : d.tot_uppl;

            var tabsHtml = `
                <div class="mb-2"><span class="badge bg-secondary" style="font-size: 15px; padding: 8px 12px;">Area: ${{d.area}} km²</span></div>
                <ul class="nav nav-tabs" role="tablist">
                    <li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#tab-ov" type="button" style="padding:5px 8px; font-size:12px;">Översikt</button></li>
                    <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-sei" type="button" style="padding:5px 8px; font-size:12px;">SEI-Data</button></li>
                    <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-up" type="button" onclick="resizePieChart()" style="padding:5px 8px; font-size:12px;">Boende</button></li>
                    <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-hi" type="button" style="padding:5px 8px; font-size:12px;">Historik</button></li>
                </ul>
                <div class="tab-content" style="padding-top: 12px;">
                    <div class="tab-pane fade show active" id="tab-ov">
                        <h6 class="fw-bold text-dark border-bottom pb-1" style="font-size:13px;">Socioekonomi (SEI 2025)</h6>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Nivå:</span><span class="fw-bold text-primary">${{d.sei_index}} - ${{seiText}}</span></div>
                        <div class="progress mb-2" style="height: 8px;"><div class="progress-bar" style="width: ${{pWidth}}%; background-color: #2a788e;"></div></div>
                        
                        <h6 class="fw-bold text-dark border-bottom pb-1 mt-3" style="font-size:13px;">Demografi & Hushåll</h6>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Folkmängd:</span><span class="fw-bold">${{d.folkmangd_visa}} pers</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Hushållsstorlek:</span><span class="fw-bold">${{vHushall}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Hyresrätt:</span><span class="fw-bold">${{vHyre}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Kategori:</span><span class="fw-bold">${{d.char1}} / ${{d.char2}}</span></div>
                    </div>
                    <div class="tab-pane fade" id="tab-sei">
                        <h6 class="fw-bold text-dark border-bottom pb-1" style="font-size:13px;">SEI-Indikatorer</h6>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Nettoinkomst:</span><span class="fw-bold">${{vNetink}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Förvärvsinkomst:</span><span class="fw-bold">${{vForvink}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Sysselsättningsgrad:</span><span class="fw-bold">${{vSyssel}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Inskrivna arbetslösa:</span><span class="fw-bold">${{vArblosa}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Ej självförsörjande:</span><span class="fw-bold">${{vEjsjalv}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Långv. ekon. bistånd:</span><span class="fw-bold">${{vBistand}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Barnfattigdom:</span><span class="fw-bold">${{vBarnfattig}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Låg ekonomisk std:</span><span class="fw-bold">${{vLagekon}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Låg inkomststandard:</span><span class="fw-bold">${{vLagink}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Trångbodda hushåll:</span><span class="fw-bold">${{vTrang}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Kvm per person:</span><span class="fw-bold">${{vKvm}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Kvarboende minst tre år:</span><span class="fw-bold">${{vKvarboende}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Ensamstående hushåll:</span><span class="fw-bold">${{vEnsam}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Ohälsotal 50-64 år (dagar):</span><span class="fw-bold">${{vOhalsa}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Förgymnasial utbildn:</span><span class="fw-bold">${{vForgym}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Inskrivna förskolebarn:</span><span class="fw-bold">${{vForskola}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Behöriga gymn. yrkesprogr.:</span><span class="fw-bold">${{vBehoriga}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>UVAS:</span><span class="fw-bold">${{vUvas}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Utrikes födda:</span><span class="fw-bold">${{vUtrfod}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Utländsk bakgrund:</span><span class="fw-bold">${{vUtlbak}}</span></div>
                        <div class="d-flex justify-content-between mb-1" style="font-size:12px;"><span>Valdeltagande:</span><span class="fw-bold">${{vVal}}</span></div>
                    </div>
                    <div class="tab-pane fade" id="tab-up">
                        <h6 class="fw-bold text-dark mb-1" style="font-size:13px;">Upplåtelseformer</h6>
                        <p style="font-size:11px; color:#666;">Totalt hushåll: ${{vTotUppl}}</p>
                        ${{pieHtml}}
                    </div>
                    <div class="tab-pane fade" id="tab-hi">
                        <h6 class="fw-bold text-dark mb-2" style="font-size:13px;">Befolkningsutveckling</h6>
                        ${{chartHtml}}
                    </div>
                </div>
            `;
            showInfoPanel(tabsHtml, "📍 Områdesinformation: " + d.namn);

            setTimeout(() => {{
                if (d.tot_uppl > 0 && !isSec) {{
                    if (upplatelseChartInstans) upplatelseChartInstans.destroy();
                    upplatelseChartInstans = new Chart(document.getElementById('upplatelsePieChart').getContext('2d'), {{
                        type: 'pie', data: {{ labels: ['Äganderätt', 'Bostadsrätt', 'Hyresrätt', 'Saknas'], datasets: [{{ data: [d.agan, d.bost, d.hyre, d.saknas], backgroundColor: ['#2ecc71', '#3498db', '#e74c3c', '#95a5a6'], borderWidth: 1 }}] }},
                        options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ position: 'right', labels: {{ boxWidth: 10, font: {{ size: 10 }} }} }} }} }}
                    }});
                }}
                if (hist && hist.labels && hist.labels.length > 0 && !isSec) {{
                    if (popChartInstans) popChartInstans.destroy();
                    popChartInstans = new Chart(document.getElementById('popChartCanvas').getContext('2d'), {{
                        type: 'line', data: {{ labels: hist.labels, datasets: [{{ label: 'Invånare', data: hist.data, borderColor: '#3498db', backgroundColor: 'rgba(52,152,219,0.2)', fill: true, tension: 0.3, pointRadius: 2 }}] }},
                        options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ ticks: {{ font: {{ size: 9 }} }} }}, y: {{ ticks: {{ font: {{ size: 10 }} }} }} }} }}
                    }});
                }}
                
                var tabUpEl = document.querySelector('button[data-bs-target="#tab-up"]');
                if (tabUpEl) {{
                    tabUpEl.addEventListener('shown.bs.tab', function () {{
                        if (upplatelseChartInstans) upplatelseChartInstans.resize();
                    }});
                }}
            }}, 150);
        }}

        // Hover & Click logic med DYNAMISK TOOLTIP och KORREKT RESET AV RÖDA KANTER
        setTimeout(function() {{
            var select = document.getElementById('zoomSelect');
            map.eachLayer(function(layer) {{
                if (layer.feature && layer.feature.properties && layer.feature.properties.NAMN) {{
                    var omradesNamn = layer.feature.properties.NAMN;
                    if (layer.options.className && layer.options.className.includes('border-polygon')) {{
                        var opt = document.createElement('option'); opt.value = omradesNamn; opt.innerHTML = omradesNamn; select.appendChild(opt);
                        layer.bindTooltip("", {{sticky: true, className: 'custom-tooltip'}});
                    }}
                    
                    layer.off('mouseover').on('mouseover', function(e) {{
                        if (layer.mySavedStyle && layer.mySavedStyle.fillOpacity === 0 && layer.mySavedStyle.opacity === 0) return; 
                        var currentOpacity = document.getElementById('opacitySlider').value;
                        
                        // Fix för spök-kanter: Rensa eventuellt tidigare hovrad yta benhårt!
                        if (window.currentlyHoveredLayer && window.currentlyHoveredLayer !== this && window.currentlyHoveredLayer.mySavedStyle) {{
                            window.currentlyHoveredLayer.setStyle(window.currentlyHoveredLayer.mySavedStyle);
                        }}
                        window.currentlyHoveredLayer = this;

                        var activeBase = document.querySelector('input[name="baseArea"]:checked').value;
                        var toolTipText = "<b style='font-size:15px;'>" + omradesNamn + "</b>";
                        var d = nykoData.find(x => x.namn === omradesNamn);
                        
                        if (d && activeBase !== 'none') {{
                            var propMap = {{
                                'pop': {{p:'folkmangd_visa', l:'Befolkning'}},
                                'dens': {{p:'inv_per_km2', l:'Inv/km²'}},
                                'hushall': {{p:'hushall_visa', l:'Hushållsstorlek'}},
                                'agan': {{p:'agan_pct', l:'Äganderätt'}},
                                'bost': {{p:'bost_pct', l:'Bostadsrätt'}},
                                'hyre': {{p:'hyre_pct', l:'Hyresrätt'}},
                                'ind_netink': {{p:'ind_netink', l:'Nettoinkomst (tkr)'}},
                                'ind_forvink': {{p:'ind_forvink', l:'Förvärvsinkomst (tkr)'}},
                                'ind_syssel': {{p:'ind_syssel', l:'Sysselsättningsgrad'}},
                                'ind_arblosa': {{p:'ind_arblosa', l:'Inskrivna arbetslösa'}},
                                'ind_ejsjalv': {{p:'ind_ejsjalv', l:'Ej självförsörjande'}},
                                'ind_bistand': {{p:'ind_bistand', l:'Långv. ekon. bistånd'}},
                                'ind_barnfattig': {{p:'ind_barnfattig', l:'Barnfattigdom'}},
                                'ind_lagekon': {{p:'ind_lagekon', l:'Låg ekon. standard'}},
                                'ind_lagink': {{p:'ind_lagink', l:'Låg inkomststandard'}},
                                'ind_trang': {{p:'ind_trang', l:'Trångbodda hushåll'}},
                                'ind_kvm': {{p:'ind_kvm', l:'Kvm per person'}},
                                'ind_kvarboende': {{p:'ind_kvarboende', l:'Kvarboende minst tre år'}},
                                'ind_ensam': {{p:'ind_ensam', l:'Ensamstående hushåll'}},
                                'ind_ohalsa': {{p:'ind_ohalsa', l:'Ohälsotal 50-64 år (dagar)'}},
                                'ind_forgym': {{p:'ind_forgym', l:'Förgymnasial utbildning'}},
                                'ind_forskola': {{p:'ind_forskola', l:'Inskrivna förskolebarn'}},
                                'ind_behoriga': {{p:'ind_behoriga', l:'Behöriga gymn. yrkesprogr.'}},
                                'ind_uvas': {{p:'ind_uvas', l:'UVAS'}},
                                'ind_utrfod': {{p:'ind_utrfod', l:'Utrikes födda'}},
                                'ind_utlbak': {{p:'ind_utlbak', l:'Utländsk bakgrund'}},
                                'ind_val': {{p:'ind_val', l:'Valdeltagande'}},
                                'snitt15': {{p:'snitt_15_19', l:'SEI Snitt 15-19'}},
                                'snitt20': {{p:'snitt_20_24', l:'SEI Snitt 20-24'}},
                                'seichange': {{p:'sei_change', l:'SEI Förändring'}}
                            }};
                            if(propMap[activeBase]) {{
                                var val = d[propMap[activeBase].p];
                                var displayVal = '-';
                                if (activeBase === 'pop') displayVal = d.folkmangd_visa;
                                else if (activeBase === 'dens') displayVal = d.inv_per_km2_visa;
                                else if (activeBase === 'hushall') displayVal = d.hushall_visa;
                                else if (activeBase === 'seichange') displayVal = (val !== null && val !== 0) ? val : '-';
                                else {{
                                    var suffix = ['agan', 'bost', 'hyre', 'ind_syssel', 'ind_arblosa', 'ind_ejsjalv', 'ind_bistand', 'ind_barnfattig', 'ind_lagekon', 'ind_lagink', 'ind_trang', 'ind_kvarboende', 'ind_ensam', 'ind_forgym', 'ind_forskola', 'ind_behoriga', 'ind_uvas', 'ind_utrfod', 'ind_utlbak', 'ind_val'].includes(activeBase) ? ' %' : '';
                                    displayVal = (val !== null && val !== undefined && (activeBase === 'seichange' || val > 0)) ? val + suffix : '-';
                                    if (d.folkmangd > 0 && d.folkmangd < 5) displayVal = '-'; // Göm vid sekretess
                                }}
                                toolTipText += "<br>" + propMap[activeBase].l + ": <span style='color:#e74c3c; font-weight:bold;'>" + displayVal + "</span>";
                            }}
                        }} else if (d && activeBase === 'none') {{
                            toolTipText += "<br>SEI-Nivå: <span style='color:#e74c3c; font-weight:bold;'>" + d.sei_index + "</span>";
                        }}
                        
                        var tooltip = this.getTooltip();
                        if (tooltip) {{
                            tooltip.setContent(toolTipText);
                        }} else {{
                            this.bindTooltip(toolTipText, {{sticky: true, className: 'custom-tooltip'}}).openTooltip();
                        }}

                        this.setStyle({{ weight: 3, color: '#ff0000', fillOpacity: Math.min(1.0, parseFloat(currentOpacity) + 0.3) }});
                        if (!L.Browser.ie) this.bringToFront();
                    }});
                    
                    layer.off('mouseout').on('mouseout', function(e) {{
                        if(layer.mySavedStyle) {{
                            this.setStyle(layer.mySavedStyle);
                        }}
                        if (window.currentlyHoveredLayer === this) window.currentlyHoveredLayer = null;
                    }});
                    
                    layer.off('click').on('click', function(e) {{ 
                        if (window.measureModeActive || window.isochroneModeActive || window.drawModeActive) {{
                            map.fire('click', {{latlng: e.latlng}});
                            return;
                        }}
                        showAreaInfo(omradesNamn); 
                        L.DomEvent.stopPropagation(e); 
                    }});
                }}
            }});
            updatePolygonVisibility(false);
        }}, 1000);

        // --- AVANCERAD POPUP-FUNKTION (För POI, Centrumpunkter, Nåbarhet) ---
        function formatSecret(val) {{ return (val > 0 && val < 5) ? "<5" : formatNumber(val); }}
        
        function getDemographicsWithinRadius(lat, lon, radiusKm) {{
            var pt1 = turf.point([lon, lat]);
            var stats = {{tot:0, a0_5:0, a6_15:0, a6_9:0, a10_12:0, a13_15:0, a16_18:0, a19_64:0, a19_34:0, a35_64:0, a65_79:0, a80:0}};
            if (typeof heatDataRaw !== 'undefined' && heatDataRaw.length > 0) {{
                heatDataRaw.forEach(p => {{
                    var pt2 = turf.point([p.lon, p.lat]);
                    if (turf.distance(pt1, pt2, {{units: 'kilometers'}}) <= radiusKm) {{
                        stats.tot += p.tot;
                        stats.a0_5 += p.a0_5;
                        stats.a6_15 += p.a6_15;
                        stats.a6_9 += p.a6_9 || 0;
                        stats.a10_12 += p.a10_12 || 0;
                        stats.a13_15 += p.a13_15 || 0;
                        stats.a16_18 += p.a16_18;
                        stats.a19_64 += p.a19_64;
                        stats.a19_34 += p.a19_34 || 0;
                        stats.a35_64 += p.a35_64 || 0;
                        stats.a65_79 += p.a65_79;
                        stats.a80 += p.a80;
                    }}
                }});
            }}
            return stats;
        }}

        function buildAdvancedPopup(title, lat, lon, extraHtml, demoData = null) {{
            var reseCentrum = [58.4160, 15.6250];
            var storaTorget = [58.4109, 15.6216];
            
            var pt1 = turf.point([lon, lat]);
            var distST = turf.distance(pt1, turf.point([storaTorget[1], storaTorget[0]]));
            var distRC = turf.distance(pt1, turf.point([reseCentrum[1], reseCentrum[0]]));
            
            var cykelST = (distST * 1.2).toFixed(1);
            var bilST = (distST * 1.3).toFixed(1);
            
            var tGangRC = Math.round((distRC * 1.2 / 5) * 60);
            var tCykelRC = Math.round((distRC * 1.2 / 15) * 60);
            var tBilRC = Math.round((distRC * 1.3 / 40) * 60);
            var tKollRC = Math.round((distRC * 1.3 / 20) * 60 + 5);

            var demo = demoData || getDemographicsWithinRadius(lat, lon, 1.0); 
            var demoTitle = demoData ? "Demografi (Hela basområdet)" : "Demografi (1 km radie)";
            
            var html = `<div style="min-width:280px; font-size:13px; font-family:sans-serif;">
                <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                    <div style="width:48%; background:#f8f9fa; padding:5px; border-radius:4px; border:1px solid #eee;">
                        <b style="color:#2980b9; font-size:11px;">Avstånd Stora Torget</b><br>
                        <span style="font-size:11px;">🚲 Cykel:<br>(${{cykelST}} km)</span><br>
                        <span style="font-size:11px;">🚗 Bil:<br>(${{bilST}} km)</span>
                    </div>
                    <div style="width:48%; background:#f8f9fa; padding:5px; border-radius:4px; border:1px solid #eee;">
                        <b style="color:#27ae60; font-size:11px;">Restid Resecentrum</b><br>
                        <span style="font-size:11px;">🚶 Gång: ~${{tGangRC}} min</span><br>
                        <span style="font-size:11px;">🚲 Cykel: ~${{tCykelRC}} min</span><br>
                        <span style="font-size:11px;">🚌 Koll.: ~${{tKollRC}} min</span><br>
                        <span style="font-size:11px;">🚗 Bil: ~${{tBilRC}} min</span>
                    </div>
                </div>
                <hr style="margin:5px 0;">
                ${{extraHtml ? extraHtml + '<hr style="margin:5px 0;">' : ''}}
                <b style="color:#e67e22; font-size:13px;">${{demoTitle}}</b>
                <div style="display:flex; justify-content:space-between; margin-top:2px;"><span>Totalt invånare:</span><b style="color:#2c3e50; font-size:14px;">${{formatSecret(demo.tot)}}</b></div>
                <div style="display:flex; justify-content:space-between;"><span>0-5 år:</span><b>${{formatSecret(demo.a0_5)}}</b></div>
                <div style="display:flex; justify-content:space-between;"><span>6-15 år:</span><b>${{formatSecret(demo.a6_15)}}</b></div>
                <div style="padding-left:10px; color:#666; font-size:11px; display:flex; justify-content:space-between;"><span>- Varav 6-9 år:</span><span>${{formatSecret(demo.a6_9)}}</span></div>
                <div style="padding-left:10px; color:#666; font-size:11px; display:flex; justify-content:space-between;"><span>- Varav 10-12 år:</span><span>${{formatSecret(demo.a10_12)}}</span></div>
                <div style="padding-left:10px; color:#666; font-size:11px; display:flex; justify-content:space-between;"><span>- Varav 13-15 år:</span><span>${{formatSecret(demo.a13_15)}}</span></div>
                <div style="display:flex; justify-content:space-between;"><span>16-18 år:</span><b>${{formatSecret(demo.a16_18)}}</b></div>
                <div style="display:flex; justify-content:space-between;"><span>19-64 år:</span><b>${{formatSecret(demo.a19_64)}}</b></div>
                <div style="padding-left:10px; color:#666; font-size:11px; display:flex; justify-content:space-between;"><span>- Varav 19-34 år:</span><span>${{formatSecret(demo.a19_34)}}</span></div>
                <div style="padding-left:10px; color:#666; font-size:11px; display:flex; justify-content:space-between;"><span>- Varav 35-64 år:</span><span>${{formatSecret(demo.a35_64)}}</span></div>
                <div style="display:flex; justify-content:space-between;"><span>65-79 år:</span><b>${{formatSecret(demo.a65_79)}}</b></div>
                <div style="display:flex; justify-content:space-between;"><span>80+ år:</span><b>${{formatSecret(demo.a80)}}</b></div>
            </div>`;
            return html;
        }}

        // --- CENTRUMPUNKTER (NÄRMASTE GRANNAR OCH DEMOGRAFI) ---
        var centroidLayer = L.featureGroup();
        nykoData.forEach(d => {{
            if(d.lat && d.lon) {{
                var cm = L.circleMarker([d.lat, d.lon], {{ radius: 7, fillColor: '#f1c40f', color: '#e74c3c', weight: 2, fillOpacity: 1, pane: 'analysPane' }});
                
                cm.bindTooltip("Klicka för analys av " + d.namn, {{direction: 'top'}});

                cm.on('click', function(e) {{
                    if (window.measureModeActive || window.isochroneModeActive || window.drawModeActive) return;

                    var neighbors = [];
                    nykoData.forEach(other => {{
                        if(other.kod !== d.kod && other.lat && other.lon) {{
                            var pt1 = turf.point([d.lon, d.lat]);
                            var pt2 = turf.point([other.lon, other.lat]);
                            var dist = turf.distance(pt1, pt2, {{units: 'kilometers'}});
                            neighbors.push({{name: other.namn, dist: dist}});
                        }}
                    }});
                    neighbors.sort((a, b) => a.dist - b.dist);
                    var top3 = neighbors.slice(0, 3);
                    var nHtml = top3.map(n => `<li style="margin-bottom:2px;">${{n.name}} <span style="color:#7f8c8d;">(${{n.dist.toFixed(2)}} km)</span></li>`).join('');
                    
                    var isSec = d.folkmangd > 0 && d.folkmangd < 5;
                    var dispHushall = isSec ? '-' : ((d.hushall_visa !== '-' && d.hushall_visa !== '0') ? d.hushall_visa : (d.hushall > 0 ? d.hushall : '-'));
                    
                    var extra = `
                        <div style="display:flex; justify-content:space-between; margin-bottom:2px;"><span>Kategori:</span><b>${{d.char1}}</b></div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:2px;"><span>Typ:</span><b>${{d.char2}}</b></div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:8px;"><span>Hushållsstorlek:</span><b style="color:#e74c3c;">${{dispHushall}}</b></div>
                        <b style="color:#2c3e50; font-size:12px;">De tre närmaste grannarna:</b>
                        <ul style="margin:5px 0 0 0; padding-left:18px; color:#333;">${{nHtml}}</ul>
                    `;
                    
                    var areaDemoStats = {{
                        tot: d.folkmangd, a0_5: d.grp_0_5, a6_15: d.grp_6_15, a6_9: d.grp_6_9, 
                        a10_12: d.grp_10_12, a13_15: d.grp_13_15, a16_18: d.grp_16_18, 
                        a19_64: d.grp_19_64, a19_34: d.grp_19_34, a35_64: d.grp_35_64, 
                        a65_79: d.grp_65_79, a80: d.grp_80plus
                    }};

                    var popupContent = buildAdvancedPopup("", d.lat, d.lon, extra, areaDemoStats);
                    showInfoPanel(popupContent, "📍 Centrumpunkt (Demografisk): " + d.namn);
                }});
                cm.addTo(centroidLayer);
            }}
        }});
        document.getElementById('toggle_centroids').addEventListener('change', e => e.target.checked ? centroidLayer.addTo(map) : map.removeLayer(centroidLayer));

        // --- VÄRMEKARTOR & DETALJERADE KLUSTER ---
        var currentHeatLayer = null;
        var clusterLayer = L.markerClusterGroup({{
            chunkedLoading: true, 
            iconCreateFunction: function(cluster) {{
                var markers = cluster.getAllChildMarkers(); var sum = 0;
                for (var i = 0; i < markers.length; i++) {{ sum += markers[i].options.population || 0; }}
                var displaySum = (sum > 0 && sum < 5) ? "<5" : sum;
                return new L.DivIcon({{ 
                    html: `<div style="background-color: rgba(52,152,219,0.85); border-radius: 50%; width: 40px; height: 40px; display: flex; justify-content: center; align-items: center; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.4);"><span style="color: white; font-weight: bold; font-size: 13px;">${{displaySum}}</span></div>`, 
                    className: 'cluster-custom', 
                    iconSize: new L.Point(40, 40) 
                }});
            }}
        }});

        var markersToAdd = [];
        
        if (typeof heatDataRaw !== 'undefined' && heatDataRaw.length > 0) {{
            heatDataRaw.forEach(function(p) {{
                var pop = p.tot;
                if (pop > 0) {{
                    var displayPop = (pop < 5) ? "<5" : pop;
                    var markerIcon = L.divIcon({{ html: `<div style="background-color: #3498db; color: white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 11px; border: 1px solid #fff; opacity: 0.9;">${{displayPop}}</div>`, className: '', iconSize: [24, 24] }});
                    var marker = L.marker([p.lat, p.lon], {{ icon: markerIcon, population: pop }});
                    marker.on('click', function(e) {{
                        if (window.measureModeActive || window.isochroneModeActive || window.drawModeActive) return;
                        var extra = `<div style="display:flex; justify-content:space-between; margin-bottom:2px;"><span>Specifik population:</span><b style="color:#e74c3c;">${{displayPop}} pers</b></div>`;
                        var popupContent = buildAdvancedPopup("", p.lat, p.lon, extra, null);
                        showInfoPanel(popupContent, "🏠 Adressinformation");
                    }});
                    markersToAdd.push(marker);
                }}
            }});
            clusterLayer.addLayers(markersToAdd);
        }}

        document.getElementById('heatSelect').addEventListener('change', function(e) {{
            if (currentHeatLayer) map.removeLayer(currentHeatLayer);
            var val = e.target.value;
            if (val === 'none' || typeof heatDataRaw === 'undefined' || heatDataRaw.length === 0) return;
            var heatPoints = heatDataRaw.map(p => [p.lat, p.lon, p[val]]).filter(p => p[2] > 0);
            var maxVal = 10;
            if (heatPoints.length > 0) {{ var values = heatPoints.map(p => p[2]).sort((a,b) => a - b); maxVal = values[Math.floor(values.length * 0.98)] || 10; }}
            maxVal = Math.max(3, maxVal); 
            currentHeatLayer = L.heatLayer(heatPoints, {{ radius: 15, blur: 20, maxZoom: 14, max: maxVal }}).addTo(map);
        }});

        document.getElementById('toggleClusters').addEventListener('change', function(e) {{ if(e.target.checked) map.addLayer(clusterLayer); else map.removeLayer(clusterLayer); }});

        // --- EXCEL POI KLUSTER ---
        var poiGroups = {{}};
        if (typeof excelPois !== 'undefined') {{
            excelPois.forEach(function(p) {{
                if (!poiGroups[p.group]) poiGroups[p.group] = L.markerClusterGroup({{maxClusterRadius: 40}});
                var iconHtml = `<div style="background-color: ${{p.color}}; width: 30px; height: 30px; border-radius: 50%; color: white; display: flex; align-items: center; justify-content: center; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"><i class="fas ${{p.icon}}" style="font-size: 14px;"></i></div>`;
                var marker = L.marker([p.lat, p.lon], {{icon: L.divIcon({{ html: iconHtml, className: '', iconSize: [30, 30], iconAnchor: [15, 15] }})}});
                
                marker.on('click', function(e) {{
                    if (window.measureModeActive || window.isochroneModeActive || window.drawModeActive) return;
                    var extra = `<div style="display:flex; justify-content:space-between; margin-bottom:2px;"><span>Grupp:</span><b>${{p.group}}</b></div>`;
                    
                    if (p.type && p.type.trim() !== '' && p.type !== 'nan' && p.type !== 'None') {{
                        extra += `<div style="display:flex; justify-content:space-between; margin-bottom:2px;"><span>Kategori/Typ:</span><b>${{p.type}}</b></div>`;
                    }}
                    
                    if (p.org && p.org.trim() !== '' && p.org !== 'nan' && p.org !== 'None') {{
                        extra += `<div style="display:flex; justify-content:space-between; margin-bottom:2px;"><span>Huvudman:</span><b>${{p.org}}</b></div>`;
                    }}
                    
                    var popupContent = buildAdvancedPopup("", p.lat, p.lon, extra, null);
                    showInfoPanel(popupContent, "📌 " + p.name);
                }});
                
                poiGroups[p.group].addLayer(marker);
            }});
        }}
        
        document.querySelectorAll('.poi-toggle').forEach(cb => {{
            cb.addEventListener('change', function() {{
                var g = this.value;
                if (poiGroups[g]) {{ if (this.checked) map.addLayer(poiGroups[g]); else map.removeLayer(poiGroups[g]); }}
            }});
        }});

        // --- STÅNGÅSTADENS OMRÅDEN (TURF.JS PIP) ---
        if (typeof stangaData !== 'undefined' && stangaData.features) {{
            var stangaLayerGroup = L.layerGroup();
            var stangaLayer = L.geoJSON(stangaData, {{
                pane: 'stangaPane',
                style: function(f) {{
                    var p = f.properties || {{}};
                    var isStudent = false;
                    for (var key in p) {{
                        if (String(p[key]).toLowerCase().includes('student')) isStudent = true;
                    }}
                    return {{ color: isStudent ? '#9b59b6' : '#e67e22', weight: 2, fillOpacity: 0.5 }};
                }},
                onEachFeature: function(feature, layer) {{
                    var p = feature.properties || {{}};
                    var name = p.NAMN || p.Namn || p.name || p.område || "Stångåstadens område";
                    layer.bindTooltip("<b>" + name + "</b>", {{sticky: true, className: 'custom-tooltip'}});
                    
                    layer.on('click', function(e) {{
                        if (window.measureModeActive || window.isochroneModeActive || window.drawModeActive) {{
                            map.fire('click', {{latlng: e.latlng}});
                            return;
                        }}
                        L.DomEvent.stopPropagation(e);
                        
                        var stats = {{tot:0, a0_5:0, a6_15:0, a6_9:0, a10_12:0, a13_15:0, a16_18:0, a19_64:0, a19_34:0, a35_64:0, a65_79:0, a80:0}};
                        if (typeof heatDataRaw !== 'undefined' && heatDataRaw.length > 0) {{
                            heatDataRaw.forEach(pt => {{
                                var turfPt = turf.point([pt.lon, pt.lat]);
                                if (turf.booleanPointInPolygon(turfPt, feature)) {{
                                    stats.tot += pt.tot; stats.a0_5 += pt.a0_5; stats.a6_15 += pt.a6_15;
                                    stats.a6_9 += pt.a6_9 || 0; stats.a10_12 += pt.a10_12 || 0; stats.a13_15 += pt.a13_15 || 0;
                                    stats.a16_18 += pt.a16_18; stats.a19_64 += pt.a19_64;
                                    stats.a19_34 += pt.a19_34 || 0; stats.a35_64 += pt.a35_64 || 0;
                                    stats.a65_79 += pt.a65_79; stats.a80 += pt.a80;
                                }}
                            }});
                        }}
                        
                        var isStudent = false;
                        for (var key in p) {{ if (String(p[key]).toLowerCase().includes('student')) isStudent = true; }}
                        var catText = isStudent ? "Studentområden" : "Stångåstadens områden";
                        
                        var extra = `<div style="display:flex; justify-content:space-between; margin-bottom:2px;"><span>Kategori:</span><b>${{catText}}</b></div>`;
                        
                        var popupContent = buildAdvancedPopup("", e.latlng.lat, e.latlng.lng, extra, stats, true);
                        showInfoPanel(popupContent, "🏢 " + name);
                    }});
                }}
            }});
            stangaLayerGroup.addLayer(stangaLayer);
            
            document.getElementById('toggleStanga').addEventListener('change', function(e) {{
                if(e.target.checked) stangaLayerGroup.addTo(map);
                else map.removeLayer(stangaLayerGroup);
            }});
        }}

        // --- MIKROKLIMAT (TURF.JS PIP) ---
        if (typeof mikroData !== 'undefined' && mikroData.features) {{
            var mikroLayerGroup = L.layerGroup();
            var mikroLayer = L.geoJSON(mikroData, {{
                pane: 'mikroPane',
                style: function(f) {{
                    var p = f.properties || {{}};
                    var catRaw = String(p.kategori_kod || "");
                    var color = '#95a5a6'; 
                    if (catRaw.startsWith('1')) color = '#1e8449'; // Mörkgrönt
                    else if (catRaw.startsWith('2')) color = '#2ecc71'; // Ljusgrönt
                    else if (catRaw.startsWith('3')) color = '#e67e22'; // Orange
                    else if (catRaw.startsWith('4')) color = '#c0392b'; // Mörkrött
                    
                    return {{ color: color, weight: 2, fillOpacity: 0.5 }};
                }},
                onEachFeature: function(feature, layer) {{
                    var p = feature.properties || {{}};
                    var name = p.omrade || "Okänt område";
                    var catRaw = p.kategori_kod || "Okänd klass";
                    var catClean = catRaw.replace(/^\d+[\s\.\-\_]*/, '').trim(); 
                    
                    layer.bindTooltip("<b>" + name + "</b><br><span style='font-size:11px; color:#555;'>" + catClean + "</span>", {{sticky: true, className: 'custom-tooltip'}});
                    
                    layer.on('click', function(e) {{
                        if (window.measureModeActive || window.isochroneModeActive || window.drawModeActive) {{
                            map.fire('click', {{latlng: e.latlng}});
                            return;
                        }}
                        L.DomEvent.stopPropagation(e);
                        
                        var stats = {{tot:0, a0_5:0, a6_15:0, a6_9:0, a10_12:0, a13_15:0, a16_18:0, a19_64:0, a19_34:0, a35_64:0, a65_79:0, a80:0}};
                        if (typeof heatDataRaw !== 'undefined' && heatDataRaw.length > 0) {{
                            heatDataRaw.forEach(pt => {{
                                var turfPt = turf.point([pt.lon, pt.lat]);
                                if (turf.booleanPointInPolygon(turfPt, feature)) {{
                                    stats.tot += pt.tot; stats.a0_5 += pt.a0_5; stats.a6_15 += pt.a6_15;
                                    stats.a6_9 += pt.a6_9 || 0; stats.a10_12 += pt.a10_12 || 0; stats.a13_15 += pt.a13_15 || 0;
                                    stats.a16_18 += pt.a16_18; stats.a19_64 += pt.a19_64;
                                    stats.a19_34 += pt.a19_34 || 0; stats.a35_64 += pt.a35_64 || 0;
                                    stats.a65_79 += pt.a65_79; stats.a80 += pt.a80;
                                }}
                            }});
                        }}
                        
                        var extra = `<div style="display:flex; justify-content:space-between; margin-bottom:2px;"><span>Kategori:</span><b>${{catClean}}</b></div>`;
                        
                        var popupContent = buildAdvancedPopup("", e.latlng.lat, e.latlng.lng, extra, stats, true);
                        showInfoPanel(popupContent, "🌡️ " + name);
                    }});
                }}
            }});
            mikroLayerGroup.addLayer(mikroLayer);
            
            document.getElementById('toggleMikro').addEventListener('change', function(e) {{
                if(e.target.checked) mikroLayerGroup.addTo(map);
                else map.removeLayer(mikroLayerGroup);
            }});
        }}

        // --- DYNAMISK BEFOLKNING ---
        function buildDynLayer(data, color, levelName) {{
            var layer = L.featureGroup();
            if(!data || data.length === 0) return layer;
            data.forEach(function(d) {{
                var isSecret = d.Totalt > 0 && d.Totalt < 5;
                var displayPop = isSecret ? "<5" : d.Totalt;
                var size = Math.max(30, Math.min(70, 15 + Math.sqrt(d.Totalt)*0.8));
                var html = `<div style="background-color: ${{color}}; color: white; border-radius: 50%; width: ${{size}}px; height: ${{size}}px; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight:bold; border: 2px solid #fff; opacity: 0.9; box-shadow: 0 2px 5px rgba(0,0,0,0.5);">${{displayPop}}</div>`;
                var markerIcon = L.divIcon({{ html: html, className: '', iconSize: [size, size], iconAnchor: [size/2, size/2] }});
                var marker = L.marker([d.lat, d.lon], {{ icon: markerIcon, pane: 'analysPane' }});
                
                marker.bindTooltip("<b>" + levelName + " (" + d.kod + ")</b><br>Klicka för att zooma in", {{direction: 'top'}});

                marker.on('click', function(e) {{
                    if (window.measureModeActive || window.isochroneModeActive || window.drawModeActive) return;
                    map.flyTo([d.lat, d.lon], map.getZoom() + 1);
                }});
                marker.addTo(layer);
            }});
            return layer;
        }}

        var layerDyn1 = typeof dynPop1 !== 'undefined' ? buildDynLayer(dynPop1, '#3498db', 'Nyko 1 (Kommundel)') : L.featureGroup();
        var layerDyn3 = typeof dynPop3 !== 'undefined' ? buildDynLayer(dynPop3, '#3498db', 'Nyko 3 (Stadsdel)') : L.featureGroup();
        var layerDyn4 = typeof dynPop4 !== 'undefined' ? buildDynLayer(dynPop4, '#3498db', 'Nyko 4 (Basområde)') : L.featureGroup();
        var layerDyn6 = typeof dynPop6 !== 'undefined' ? buildDynLayer(dynPop6, '#3498db', 'Nyko 6 (Kvarter)') : L.featureGroup();

        function updateDynPopLayer() {{
            var lbl = document.getElementById('dynPopLabel');
            if (!document.getElementById('toggle_pop_dyn').checked) {{
                map.removeLayer(layerDyn1); map.removeLayer(layerDyn3); map.removeLayer(layerDyn4); map.removeLayer(layerDyn6);
                lbl.style.display = 'none';
                return;
            }}
            
            lbl.style.display = 'inline-block';
            var z = map.getZoom();
            map.removeLayer(layerDyn1); map.removeLayer(layerDyn3); map.removeLayer(layerDyn4); map.removeLayer(layerDyn6);
            var col = '#3498db';
            
            if (z <= 11) {{
                map.addLayer(layerDyn1);
                lbl.innerText = "Kommundel (Nyko 1)"; lbl.style.backgroundColor = col;
            }} else if (z === 12) {{
                map.addLayer(layerDyn3);
                lbl.innerText = "Stadsdel (Nyko 3)"; lbl.style.backgroundColor = col;
            }} else if (z === 13 || z === 14) {{
                map.addLayer(layerDyn4);
                lbl.innerText = "Basområde (Nyko 4)"; lbl.style.backgroundColor = col;
            }} else if (z >= 15) {{
                map.addLayer(layerDyn6);
                lbl.innerText = "Kvarter (Nyko 6)"; lbl.style.backgroundColor = col;
            }}
        }}
        
        map.on('zoomend', updateDynPopLayer);
        document.getElementById('toggle_pop_dyn').addEventListener('change', updateDynPopLayer);

        // --- TRENDRINGAR ---
        var popRingsGroup = L.layerGroup();
        if (typeof dynPop4 !== 'undefined' && dynPop4.length > 0) {{
            dynPop4.forEach(d => {{
                var nData = nykoData.find(nd => nd.kod === d.kod || nd.namn === d.kod);
                var color = nData && nData.trend_color ? nData.trend_color : '#f1c40f'; 
                var areaName = nData && nData.namn ? nData.namn : d.kod;
                var radius = Math.max(10, Math.sqrt(d.Totalt) * 0.4); 
                var cm = L.circleMarker([d.lat, d.lon], {{ radius: radius, color: '#2c3e50', fillColor: color, fillOpacity: 0.85, weight: 1.5, pane: 'analysPane' }});
                
                cm.on('click', function(e) {{
                    if (window.measureModeActive || window.isochroneModeActive || window.drawModeActive) return;
                    var extra = `<div style="text-align:center; color:${{color}};"><b>Befolkningsutveckling sedan föregående period: ` + (color === '#2ecc71' ? 'ÖKAR' : (color === '#e74c3c' ? 'MINSKAR' : 'OFÖRÄNDRAD')) + `</b></div>`;
                    
                    var stats = {{
                        tot: d.Totalt, a0_5: d.Grp_0_5, a6_15: d.Grp_6_15, a6_9: d.Grp_6_9, 
                        a10_12: d.Grp_10_12, a13_15: d.Grp_13_15, a16_18: d.Grp_16_18, 
                        a19_64: d.Grp_19_64, a19_34: d.Grp_19_34, a35_64: d.Grp_35_64, 
                        a65_79: d.Grp_65_79, a80: d.Grp_80plus
                    }};
                    var popupContent = buildAdvancedPopup("", d.lat, d.lon, extra, stats);
                    showInfoPanel(popupContent, "📈 Befolkningstrend: " + areaName);
                }});
                cm.addTo(popRingsGroup);
            }});
        }}
        document.getElementById('toggle_pop_rings').addEventListener('change', e => e.target.checked ? popRingsGroup.addTo(map) : map.removeLayer(popRingsGroup));

        // --- 6. MÄTVERKTYG OCH NÅBARHET OCH RITVERKTYG ---
        var drawLayer = L.featureGroup().addTo(map);
        var storaTorget = [58.4109, 15.6216];
        var measureLine = null; var measureMarker = null;

        var drawPolygonControl = new L.Draw.Polygon(map, {{
            shapeOptions: {{ color: '#e67e22', weight: 3, fillOpacity: 0.3 }}
        }});

        document.getElementById('btn-draw').addEventListener('click', function() {{
            window.drawModeActive = !window.drawModeActive;
            if (window.drawModeActive) {{
                window.measureModeActive = false;
                window.isochroneModeActive = false;
                document.getElementById('btn-measure').classList.replace('btn-primary', 'btn-outline-primary');
                document.getElementById('btn-measure').innerHTML = '<i class="fas fa-ruler"></i> Avstånd till Centrum';
                document.getElementById('btn-isochrone').classList.replace('btn-info', 'btn-outline-info');
                document.getElementById('btn-isochrone').innerHTML = '<i class="fas fa-stopwatch"></i> 10-min Nåbarhetsanalys';
                
                drawLayer.clearLayers();
                drawPolygonControl.enable();
                this.classList.replace('btn-outline-success', 'btn-success');
                this.innerHTML = '<i class="fas fa-times"></i> Avbryt ritning';
                window.showToast("✏️ Klicka i kartan för att rita en yta. Klicka på första punkten för att avsluta.");
            }} else {{
                drawPolygonControl.disable();
                this.classList.replace('btn-success', 'btn-outline-success');
                this.innerHTML = '<i class="fas fa-draw-polygon"></i> Rita egen yta';
            }}
        }});

        map.on(L.Draw.Event.CREATED, function (e) {{
            if (e.layerType === 'polygon') {{
                drawLayer.clearLayers();
                var layer = e.layer;
                drawLayer.addLayer(layer);
                
                var geojsonPoly = layer.toGeoJSON();
                var stats = {{tot:0, a0_5:0, a6_15:0, a6_9:0, a10_12:0, a13_15:0, a16_18:0, a19_64:0, a19_34:0, a35_64:0, a65_79:0, a80:0}};
                
                if (typeof heatDataRaw !== 'undefined' && heatDataRaw.length > 0) {{
                    heatDataRaw.forEach(pt => {{
                        var turfPt = turf.point([pt.lon, pt.lat]);
                        if (turf.booleanPointInPolygon(turfPt, geojsonPoly)) {{
                            stats.tot += pt.tot; stats.a0_5 += pt.a0_5; stats.a6_15 += pt.a6_15;
                            stats.a6_9 += pt.a6_9 || 0; stats.a10_12 += pt.a10_12 || 0; stats.a13_15 += pt.a13_15 || 0;
                            stats.a16_18 += pt.a16_18; stats.a19_64 += pt.a19_64;
                            stats.a19_34 += pt.a19_34 || 0; stats.a35_64 += pt.a35_64 || 0;
                            stats.a65_79 += pt.a65_79; stats.a80 += pt.a80;
                        }}
                    }});
                }}
                
                var area = turf.area(geojsonPoly) / 1000000;
                var extra = `<div style="display:flex; justify-content:space-between; margin-bottom:2px;"><span>Areal:</span><b>${{area.toFixed(2)}} km²</b></div>`;
                
                var popupContent = buildAdvancedPopup("", layer.getBounds().getCenter().lat, layer.getBounds().getCenter().lng, extra, stats, true);
                showInfoPanel(popupContent, "✏️ Egenritad yta");
                
                document.getElementById('btn-draw').classList.replace('btn-success', 'btn-outline-success');
                document.getElementById('btn-draw').innerHTML = '<i class="fas fa-draw-polygon"></i> Rita egen yta';
                window.drawModeActive = false;
            }}
        }});

        document.getElementById('btn-measure').addEventListener('click', function() {{
            window.measureModeActive = !window.measureModeActive;
            if (window.measureModeActive) {{
                window.isochroneModeActive = false; 
                if (window.drawModeActive) {{ drawPolygonControl.disable(); window.drawModeActive = false; document.getElementById('btn-draw').classList.replace('btn-success', 'btn-outline-success'); document.getElementById('btn-draw').innerHTML = '<i class="fas fa-draw-polygon"></i> Rita egen yta'; }}
                document.getElementById('btn-isochrone').classList.replace('btn-info', 'btn-outline-info');
                document.getElementById('btn-isochrone').innerHTML = '<i class="fas fa-stopwatch"></i> 10-min Nåbarhetsanalys';
                
                this.classList.replace('btn-outline-primary', 'btn-primary');
                this.innerHTML = '<i class="fas fa-times"></i> Stäng Avståndsmätare';
                map.getContainer().style.cursor = 'crosshair';
                
                drawLayer.clearLayers();
                measureMarker = L.marker(storaTorget, {{ icon: L.divIcon({{html: '<div style="color:#e74c3c; font-size:24px; text-shadow: 1px 1px 2px #000;"><i class="fas fa-map-marker-alt"></i></div>', className: '', iconSize:[24,24], iconAnchor:[12,24]}}) }}).addTo(drawLayer).bindTooltip("Stora Torget", {{permanent: true, direction: 'top'}});
                window.showToast("📍 Klicka var som helst på kartan (även på färgade områden) för att mäta från Stora Torget.");
            }} else {{
                this.classList.replace('btn-primary', 'btn-outline-primary');
                this.innerHTML = '<i class="fas fa-ruler"></i> Avstånd till Centrum';
                map.getContainer().style.cursor = '';
                drawLayer.clearLayers();
            }}
        }});

        document.getElementById('btn-isochrone').addEventListener('click', function() {{
            window.isochroneModeActive = !window.isochroneModeActive;
            if (window.isochroneModeActive) {{
                window.measureModeActive = false;
                if (window.drawModeActive) {{ drawPolygonControl.disable(); window.drawModeActive = false; document.getElementById('btn-draw').classList.replace('btn-success', 'btn-outline-success'); document.getElementById('btn-draw').innerHTML = '<i class="fas fa-draw-polygon"></i> Rita egen yta'; }}
                document.getElementById('btn-measure').classList.replace('btn-primary', 'btn-outline-primary');
                document.getElementById('btn-measure').innerHTML = '<i class="fas fa-ruler"></i> Avstånd till Centrum';
                
                this.classList.replace('btn-outline-info', 'btn-info');
                this.innerHTML = '<i class="fas fa-times"></i> Stäng Nåbarhet';
                map.getContainer().style.cursor = 'crosshair';
                drawLayer.clearLayers();
                window.showToast("⏱️ Klicka på kartan (även på färgade områden) för att simulera en 10-minuters cykelradie (~2.5 km).");
            }} else {{
                this.classList.replace('btn-info', 'btn-outline-info');
                this.innerHTML = '<i class="fas fa-stopwatch"></i> 10-min Nåbarhetsanalys';
                map.getContainer().style.cursor = '';
                drawLayer.clearLayers();
            }}
        }});

        map.on('click', function(e) {{
            if (window.measureModeActive) {{
                drawLayer.clearLayers();
                measureMarker = L.marker(storaTorget, {{ icon: L.divIcon({{html: '<div style="color:#e74c3c; font-size:24px; text-shadow: 1px 1px 2px #000;"><i class="fas fa-map-marker-alt"></i></div>', className: '', iconSize:[24,24], iconAnchor:[12,24]}}) }}).addTo(drawLayer).bindTooltip("Stora Torget", {{permanent: true, direction: 'top'}});
                
                var clickedPt = [e.latlng.lat, e.latlng.lng];
                L.polyline([storaTorget, clickedPt], {{color: '#e74c3c', weight: 4, dashArray: '5, 10'}}).addTo(drawLayer);
                var line = turf.lineString([[storaTorget[1], storaTorget[0]], [clickedPt[1], clickedPt[0]]]);
                var length = turf.length(line, {{units: 'kilometers'}});
                
                var html = `<div style="text-align:center; padding: 10px;">
                                <i class="fas fa-ruler fa-2x" style="color:#e74c3c; margin-bottom:10px;"></i><br>
                                <b>Avstånd till Stora Torget:</b><br>
                                <span style="font-size:20px; color:#e74c3c; font-weight:bold;">${{length.toFixed(2)}} km</span>
                            </div>`;
                showInfoPanel(html, "📏 Avståndsmätare");
            }} 
            else if (window.isochroneModeActive) {{
                drawLayer.clearLayers();
                var circle = L.circle(e.latlng, {{ radius: 2500, color: '#3498db', fillColor: '#3498db', fillOpacity: 0.2, weight: 2 }}).addTo(drawLayer);
                
                var walkStats = getDemographicsWithinRadius(e.latlng.lat, e.latlng.lng, 0.83);
                var bikeStats = getDemographicsWithinRadius(e.latlng.lat, e.latlng.lng, 2.5);
                var carStats = getDemographicsWithinRadius(e.latlng.lat, e.latlng.lng, 6.6);
                
                var popupHtml = `
                    <div style="min-width:280px; font-size:13px; font-family:sans-serif;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <div style="width:32%; background:#f8f9fa; padding:5px; border-radius:4px; text-align:center; border:1px solid #eee;">
                                🚶 <b>Gång</b><br><span style="font-size:11px; color:#666; font-weight:normal;">(0.8 km)</span><br><span style="font-size:14px; color:#27ae60; font-weight:bold;">${{formatNumber(walkStats.tot)}}</span>
                            </div>
                            <div style="width:32%; background:#f8f9fa; padding:5px; border-radius:4px; text-align:center; border:1px solid #eee;">
                                🚲 <b>Cykel</b><br><span style="font-size:11px; color:#666; font-weight:normal;">(2.5 km)</span><br><span style="font-size:14px; color:#2980b9; font-weight:bold;">${{formatNumber(bikeStats.tot)}}</span>
                            </div>
                            <div style="width:32%; background:#f8f9fa; padding:5px; border-radius:4px; text-align:center; border:1px solid #eee;">
                                🚗 <b>Bil/Buss</b><br><span style="font-size:11px; color:#666; font-weight:normal;">(6.6 km)</span><br><span style="font-size:14px; color:#e74c3c; font-weight:bold;">${{formatNumber(carStats.tot)}}</span>
                            </div>
                        </div>
                        <hr style="margin:8px 0;">
                        <b style="color:#2980b9; font-size:13px;">Detaljerad demografi (Cykel 10 min)</b>
                        <div style="display:flex; justify-content:space-between; margin-top:4px;"><span>Totalt invånare:</span><b style="color:#2c3e50; font-size:14px;">${{formatSecret(bikeStats.tot)}}</b></div>
                        <div style="display:flex; justify-content:space-between;"><span>0-5 år:</span><b>${{formatSecret(bikeStats.a0_5)}}</b></div>
                        <div style="display:flex; justify-content:space-between;"><span>6-15 år:</span><b>${{formatSecret(bikeStats.a6_15)}}</b></div>
                        <div style="padding-left:10px; color:#666; font-size:11px; display:flex; justify-content:space-between;"><span>- Varav 6-9 år:</span><span>${{formatSecret(bikeStats.a6_9)}}</span></div>
                        <div style="padding-left:10px; color:#666; font-size:11px; display:flex; justify-content:space-between;"><span>- Varav 10-12 år:</span><span>${{formatSecret(bikeStats.a10_12)}}</span></div>
                        <div style="padding-left:10px; color:#666; font-size:11px; display:flex; justify-content:space-between;"><span>- Varav 13-15 år:</span><span>${{formatSecret(bikeStats.a13_15)}}</span></div>
                        <div style="display:flex; justify-content:space-between;"><span>16-18 år:</span><b>${{formatSecret(bikeStats.a16_18)}}</b></div>
                        <div style="display:flex; justify-content:space-between;"><span>19-64 år:</span><b>${{formatSecret(bikeStats.a19_64)}}</b></div>
                        <div style="padding-left:10px; color:#666; font-size:11px; display:flex; justify-content:space-between;"><span>- Varav 19-34 år:</span><span>${{formatSecret(bikeStats.a19_34)}}</span></div>
                        <div style="padding-left:10px; color:#666; font-size:11px; display:flex; justify-content:space-between;"><span>- Varav 35-64 år:</span><span>${{formatSecret(bikeStats.a35_64)}}</span></div>
                        <div style="display:flex; justify-content:space-between;"><span>65-79 år:</span><b>${{formatSecret(bikeStats.a65_79)}}</b></div>
                        <div style="display:flex; justify-content:space-between;"><span>80+ år:</span><b>${{formatSecret(bikeStats.a80)}}</b></div>
                    </div>
                `;
                showInfoPanel(popupHtml, "⏱️ 10-min Nåbarhetsanalys");
            }}
        }});

        // --- 7. INFRASTRUKTUR ---
        var transportLayer = null;
        var vattenLayer = null;
        if (typeof transportData !== 'undefined') {{
            map.createPane('transportPane'); map.getPane('transportPane').style.zIndex = 450; 
            transportLayer = L.geoJSON(transportData, {{
                pane: 'transportPane', interactive: false,
                style: function(f) {{
                    var p = f.properties || {{}};
                    if (p.highway === 'motorway') return {{ color: '#e74c3c', weight: 6, opacity: 0.9 }};
                    if (p.highway === 'primary') return {{ color: '#f1c40f', weight: 4.5, opacity: 0.9 }};
                    if (p.highway === 'secondary') return {{ color: '#f1c40f', weight: 2.5, opacity: 0.9 }};
                    if (p.railway === 'rail') return {{ color: '#000000', weight: p.name === 'Södra stambanan' ? 3.5 : 2.5, opacity: 0.9, dashArray: p.name === 'Södra stambanan' ? '6, 8' : '3, 4' }};
                    return {{ color: '#7f8c8d', weight: 1.5, opacity: 0.6, dashArray: '2, 4' }};
                }}
            }});
            document.getElementById('toggleTransport').addEventListener('change', e => e.target.checked ? transportLayer.addTo(map) : map.removeLayer(transportLayer));
        }}
        
        if (typeof vattenData !== 'undefined') {{
            vattenLayer = L.geoJSON(vattenData, {{ interactive: false, style: {{color: '#3498db', weight: 2, fillOpacity: 0.5}} }});
            document.getElementById('toggleVatten').addEventListener('change', e => e.target.checked ? vattenLayer.addTo(map) : map.removeLayer(vattenLayer));
        }}

        // --- 8. BAKGRUNDSKARTA ---
        var tileBlek = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{ attribution: '&copy; CARTO' }}).addTo(map);
        var tileFarg = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ attribution: '&copy; OSM' }});
        var tileFlyg = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ attribution: '&copy; Esri' }});

        document.getElementById('basemapSelect').addEventListener('change', function(e) {{
            map.removeLayer(tileBlek); map.removeLayer(tileFarg); map.removeLayer(tileFlyg);
            var isFlyg = e.target.value === 'flyg';
            if(e.target.value === 'blek') tileBlek.addTo(map);
            else if(e.target.value === 'farg') tileFarg.addTo(map);
            else if(isFlyg) tileFlyg.addTo(map);
            
            var newBorderColor = isFlyg ? '#ffffff' : '#2c3e50';
            map.eachLayer(function(layer) {{
                if (layer.options && layer.options.className && layer.options.className.includes('border-polygon')) {{
                    layer.setStyle({{color: newBorderColor}});
                    if (layer.defaultStyle) layer.defaultStyle.color = newBorderColor;
                }}
            }});
        }});
    }});
</script>
"""

m.get_root().html.add_child(folium.Element(ui_html))
html_out_path = os.path.join(moder_mapp, OUT_HTML_NAME)
m.save(html_out_path)
print(f"\n✅ Klar! Den ultimata analytikerkartan (STADEN) är genererad och sparad som:\n{html_out_path}")