import os
import sys
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MiniMap
import branca.colormap as cm
import json
import math

# =====================================================================
# 1. GENERELL SETUP, GYLLENE REGLER & MAPPSTRUKTUR (Master Config v2.0)
# =====================================================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
    moder_mapp = os.path.dirname(current_folder)
except NameError:
    current_folder = os.getcwd()
    moder_mapp = os.path.dirname(current_folder)

kart_filer_dir = os.path.join(moder_mapp, 'kart_filer')
excel_filer_dir = os.path.join(moder_mapp, 'excel_filer')

# --- FILNAMN FÖR NYKO 4 ---
GEOJSON_NYKO4_FILENAME = 'NYKO4v23.geojson' 
EXCEL_POP_SHEET = 'Basområden'
EXCEL_HUSHALL_SHEET = 'Hushållstorl_basomr'
EXCEL_UPPLATELSE_SHEET = 'Upplåtelseform_basomr'
OUT_JSON_NAME = 'nyko4_data.json'
OUT_HTML_NAME = 'Linkoping_Basomraden_Nyko4.html'

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
# 2. DATAHANTERING & ÅLDERSAGGREGERING / BYT ÅR FÖR PUNKTDATA HÄR!
# =====================================================================
PUNKT_DATA_AR = "2025"

print("Läser in och processar data för Nyko 4 (2D Karta)...")

excel_path = os.path.join(excel_filer_dir, 'befolkning_och_platser.xlsx')
if not os.path.exists(excel_path):
    print(f"\nFEL: Hittar inte {excel_path}.")
    sys.exit(1)

geojson_path = os.path.join(kart_filer_dir, GEOJSON_NYKO4_FILENAME)
try:
    nyko4 = gpd.read_file(geojson_path)
except FileNotFoundError:
    print(f"\nFEL: Hittar inte GeoJSON-filen: {geojson_path}.")
    sys.exit(1)

nyko4['NAMN'] = nyko4['NAMN'].apply(fix_text)

# Projicera om för att beräkna area
nyko4_3006 = nyko4.to_crs(epsg=3006)
nyko4['Area_km2'] = nyko4_3006.geometry.area / 1_000_000
nyko4_3006_centroids = nyko4_3006.geometry.centroid

# --- Läs in Historisk Folkmängd och Karaktärskolumner ---
print(f"Hämtar historisk folkmängd och områdeskaraktär från fliken '{EXCEL_POP_SHEET}'...")
try:
    hist_df = pd.read_excel(excel_path, sheet_name=EXCEL_POP_SHEET)
    hist_df.columns = hist_df.columns.astype(str).str.strip() 
    hist_df['Namn'] = hist_df['Namn'].apply(fix_text)
    
    if 'Karaktär1' not in hist_df.columns: hist_df['Karaktär1'] = ''
    if 'Karaktär2' not in hist_df.columns: hist_df['Karaktär2'] = ''
        
except Exception as e:
    print(f"FEL vid inläsning av fliken '{EXCEL_POP_SHEET}': {e}")
    sys.exit(1)

years = [str(y) for y in range(1970, 2030)]
existing_years = [y for y in years if y in hist_df.columns]
latest_year = existing_years[-1] if existing_years else '2025'
prev_year = existing_years[-2] if len(existing_years) > 1 else latest_year

for y in existing_years:
    hist_df[y] = pd.to_numeric(hist_df[y].astype(str).str.replace('..', '', regex=False), errors='coerce')

nyko4 = nyko4.merge(hist_df[['Namn', 'Karaktär1', 'Karaktär2'] + existing_years], left_on='NAMN', right_on='Namn', how='left')
nyko4['Folkmängd'] = nyko4[latest_year].fillna(0).astype(int)
nyko4['Folkmängd_prev'] = nyko4[prev_year].fillna(0).astype(int)
nyko4['Pop_Change'] = nyko4['Folkmängd'] - nyko4['Folkmängd_prev']
nyko4['Karaktär1'] = nyko4['Karaktär1'].fillna('')
nyko4['Karaktär2'] = nyko4['Karaktär2'].fillna('')

nyko4['Area_km2'] = nyko4['Area_km2'].replace(0, 0.001).round(2)
nyko4['Inv_per_km2'] = (nyko4['Folkmängd'] / nyko4['Area_km2']).round(1)
nyko4['Inv_per_km2'] = nyko4['Inv_per_km2'].fillna(0)

# --- Läs in Hushållsstorlek ---
print(f"Hämtar data från fliken '{EXCEL_HUSHALL_SHEET}'...")
try:
    hushall_df = pd.read_excel(excel_path, sheet_name=EXCEL_HUSHALL_SHEET)
    hushall_df.columns = hushall_df.columns.astype(str).str.strip()
    hushall_df['Namn'] = hushall_df['Namn'].apply(fix_text)
    
    hushall_col = PUNKT_DATA_AR if PUNKT_DATA_AR in hushall_df.columns else [c for c in hushall_df.columns if c != 'Namn'][-1]
    hushall_df[hushall_col] = hushall_df[hushall_col].astype(str).str.replace(',', '.').str.replace('..', '', regex=False)
    hushall_df['Hushallsstorlek_tmp'] = pd.to_numeric(hushall_df[hushall_col], errors='coerce')
    
    nyko4 = nyko4.merge(hushall_df[['Namn', 'Hushallsstorlek_tmp']], left_on='NAMN', right_on='Namn', how='left')
    nyko4['Hushallsstorlek'] = nyko4['Hushallsstorlek_tmp'].fillna(0).astype(float).round(2)
except Exception as e:
    print(f"INFO: Kunde inte ladda fliken '{EXCEL_HUSHALL_SHEET}' ({e}). Sätter värden till 0.")
    nyko4['Hushallsstorlek'] = 0.0

# --- Läs in Upplåtelseform ---
print(f"Hämtar data från fliken '{EXCEL_UPPLATELSE_SHEET}'...")
try:
    uppl_df = pd.read_excel(excel_path, sheet_name=EXCEL_UPPLATELSE_SHEET)
    uppl_df.columns = uppl_df.columns.astype(str).str.strip()
    uppl_df['Namn'] = uppl_df['Namn'].apply(fix_text)
    
    for col in ['Äganderätt', 'Bostadsrätt', 'Hyresrätt', 'Totalt']:
        if col in uppl_df.columns:
            uppl_df[col] = pd.to_numeric(uppl_df[col], errors='coerce').fillna(0)
            
    uppl_df.rename(columns={'Totalt': 'Totalt_uppl'}, inplace=True)
    
    nyko4 = nyko4.merge(uppl_df[['Namn', 'Äganderätt', 'Bostadsrätt', 'Hyresrätt', 'Totalt_uppl']], left_on='NAMN', right_on='Namn', how='left')
    for col in ['Äganderätt', 'Bostadsrätt', 'Hyresrätt', 'Totalt_uppl']:
        nyko4[col] = nyko4[col].fillna(0)
        
    # Beräkna "Uppgift saknas" för diagrammet
    nyko4['Uppgift_saknas'] = nyko4['Totalt_uppl'] - (nyko4['Äganderätt'] + nyko4['Bostadsrätt'] + nyko4['Hyresrätt'])
    nyko4['Uppgift_saknas'] = nyko4['Uppgift_saknas'].apply(lambda x: max(0, x)) # Undviker ev. minusvärden
        
    # Beräkna andelar i procent (skydda mot division med noll) för kartlagren
    nyko4['Andel_Aganderatt'] = nyko4.apply(lambda r: round((r['Äganderätt'] / r['Totalt_uppl'] * 100), 1) if r['Totalt_uppl'] > 0 else 0.0, axis=1)
    nyko4['Andel_Bostadsratt'] = nyko4.apply(lambda r: round((r['Bostadsrätt'] / r['Totalt_uppl'] * 100), 1) if r['Totalt_uppl'] > 0 else 0.0, axis=1)
    nyko4['Andel_Hyresratt'] = nyko4.apply(lambda r: round((r['Hyresrätt'] / r['Totalt_uppl'] * 100), 1) if r['Totalt_uppl'] > 0 else 0.0, axis=1)

except Exception as e:
    print(f"INFO: Kunde inte ladda fliken '{EXCEL_UPPLATELSE_SHEET}' ({e}). Sätter andelar till 0.")
    for col in ['Totalt_uppl', 'Äganderätt', 'Bostadsrätt', 'Hyresrätt', 'Uppgift_saknas', 'Andel_Aganderatt', 'Andel_Bostadsratt', 'Andel_Hyresratt']:
        nyko4[col] = 0.0

# --- Skapa visningskolumner för att dölja data under < 5 (Sekretess) ---
def mask_pop(x):
    try:
        val = float(x)
        if 0 < val < 5: return '< 5 (sekretess)'
        return str(int(val))
    except:
        return '0'
        
def mask_other(x, pop):
    try:
        val_pop = float(pop)
        if 0 < val_pop < 5: return '-'
        return str(x)
    except:
        return str(x)

nyko4['Folkmängd_visa'] = nyko4['Folkmängd'].apply(mask_pop)
nyko4['Inv_per_km2_visa'] = nyko4.apply(lambda r: mask_other(r['Inv_per_km2'], r['Folkmängd']), axis=1)
nyko4['Hushallsstorlek_visa'] = nyko4.apply(lambda r: mask_other(r['Hushallsstorlek'], r['Folkmängd']), axis=1)

# Skapa masker för andelar (baserat på antalet hushåll)
nyko4['Andel_Aganderatt_visa'] = nyko4.apply(lambda r: mask_other(r['Andel_Aganderatt'], r['Totalt_uppl']), axis=1)
nyko4['Andel_Bostadsratt_visa'] = nyko4.apply(lambda r: mask_other(r['Andel_Bostadsratt'], r['Totalt_uppl']), axis=1)
nyko4['Andel_Hyresratt_visa'] = nyko4.apply(lambda r: mask_other(r['Andel_Hyresratt'], r['Totalt_uppl']), axis=1)


# Förbered historisk data för Grafen
hist_json_data = {}
for idx, row in nyko4.iterrows():
    namn = row['NAMN']
    data = []
    labels = []
    for y in existing_years:
        val = row[y]
        if pd.notna(val):
            labels.append(y)
            # Maskera värden under 5 i historik-grafen genom att lägga till None
            if 0 < int(val) < 5:
                data.append(None)
            else:
                data.append(int(val))
    hist_json_data[namn] = {'labels': labels, 'data': data}
hist_json_str = json.dumps(hist_json_data)

# --- Läs in BefKoord ---
pop_path = os.path.join(excel_filer_dir, f'BefKoord{PUNKT_DATA_AR}.csv')
try:
    pop_df = pd.read_csv(pop_path, sep=';', encoding='utf-8')
except UnicodeDecodeError:
    pop_df = pd.read_csv(pop_path, sep=';', encoding='latin-1')
except FileNotFoundError:
    print(f"\nFEL: Hittar inte {pop_path}.")
    sys.exit(1)

age_cols = ['0-1_år', '2-3_år', '4-5_år', '6_år', '7-9_år', '10-12_år', '13-15_år', '16-18_år', '19-24_år', '25-34_år', '35-44_år', '45-54_år', '55-64_år', '65-69_år', '70-79_år', '80+_år']
for col in age_cols:
    if col in pop_df.columns:
        pop_df[col] = pd.to_numeric(pop_df[col], errors='coerce').fillna(0)

pop_df['Grp_0_5'] = pop_df.get('0-1_år', 0) + pop_df.get('2-3_år', 0) + pop_df.get('4-5_år', 0)
pop_df['Grp_6_15'] = pop_df.get('6_år', 0) + pop_df.get('7-9_år', 0) + pop_df.get('10-12_år', 0) + pop_df.get('13-15_år', 0)
pop_df['Grp_6_9'] = pop_df.get('6_år', 0) + pop_df.get('7-9_år', 0)
pop_df['Grp_10_12'] = pop_df.get('10-12_år', 0)
pop_df['Grp_13_15'] = pop_df.get('13-15_år', 0)
pop_df['Grp_16_18'] = pop_df.get('16-18_år', 0)
pop_df['Grp_19_64'] = pop_df.get('19-24_år', 0) + pop_df.get('25-34_år', 0) + pop_df.get('35-44_år', 0) + pop_df.get('45-54_år', 0) + pop_df.get('55-64_år', 0)
pop_df['Grp_65_79'] = pop_df.get('65-69_år', 0) + pop_df.get('70-79_år', 0)
pop_df['Grp_80plus'] = pop_df.get('80+_år', 0)

# För polygon-matching (Nyko4)
pop_df['NYKO4_kod'] = pop_df['NYKO6'].astype(str).str.zfill(6).str[:4].astype(float)
pop_nyko4 = pop_df.groupby('NYKO4_kod')[['Totalt', 'Grp_0_5', 'Grp_6_15', 'Grp_6_9', 'Grp_10_12', 'Grp_13_15', 'Grp_16_18', 'Grp_19_64', 'Grp_65_79', 'Grp_80plus']].sum().reset_index()

# Merge med nyko4 Geodataframe
nyko4 = nyko4.merge(pop_nyko4, left_on='NYKO', right_on='NYKO4_kod', how='left')
fill_cols = ['Totalt', 'Grp_0_5', 'Grp_6_15', 'Grp_6_9', 'Grp_10_12', 'Grp_13_15', 'Grp_16_18', 'Grp_19_64', 'Grp_65_79', 'Grp_80plus']
for col in fill_cols:
    if col in nyko4.columns:
        nyko4[col] = nyko4[col].fillna(0)

# --- DYNAMISKA LAGREN (Nyko 1, Nyko 3, Nyko 4, Nyko 6) ---
print("Beräknar koordinater för detaljerad och dynamisk data...")
pts = gpd.GeoDataFrame(pop_df, geometry=gpd.points_from_xy(pop_df['Y_koordinat'], pop_df['X_koordinat']), crs=3006)
pts_wgs84 = pts.to_crs(4326)

# Sätt lat/lon på individnivå-dataframe för att kunna gruppera koordinater
pop_df['lat'] = pts_wgs84.geometry.y
pop_df['lon'] = pts_wgs84.geometry.x

# Använd string-koder så vi inte tappar inledande nollor
pop_df['NYKO1_str'] = pop_df['NYKO6'].astype(str).str.zfill(6).str[:1]
pop_df['NYKO3_str'] = pop_df['NYKO6'].astype(str).str.zfill(6).str[:3]
pop_df['NYKO4_str'] = pop_df['NYKO6'].astype(str).str.zfill(6).str[:4]
pop_df['NYKO6_str'] = pop_df['NYKO6'].astype(str).str.zfill(6)

def create_agg_pop(df, group_col):
    df_pop = df[df['Totalt'] > 0].copy()
    result = []
    for name, group in df_pop.groupby(group_col):
        tot_pop = group['Totalt'].sum()
        if tot_pop == 0: continue
        
        # 1. Teoretisk tyngdpunkt (Befolkningsviktad)
        weighted_lat = (group['lat'] * group['Totalt']).sum() / tot_pop
        weighted_lon = (group['lon'] * group['Totalt']).sum() / tot_pop
        
        # 2. Snappa till närmaste FAKTISKA befolkade punkt inom området
        dist_sq = (group['lat'] - weighted_lat)**2 + (group['lon'] - weighted_lon)**2
        best_idx = dist_sq.idxmin()
        
        stats = {'kod': name, 'lat': group.loc[best_idx, 'lat'], 'lon': group.loc[best_idx, 'lon']}
        for col in fill_cols:
            stats[col] = int(group[col].sum())
        result.append(stats)
    return result

agg_nyko1 = create_agg_pop(pop_df, 'NYKO1_str')
agg_nyko3 = create_agg_pop(pop_df, 'NYKO3_str')
agg_nyko4 = create_agg_pop(pop_df, 'NYKO4_str')
agg_nyko6 = create_agg_pop(pop_df, 'NYKO6_str')

dyn_pop1_str = json.dumps(agg_nyko1)
dyn_pop3_str = json.dumps(agg_nyko3)
dyn_pop4_str = json.dumps(agg_nyko4)
dyn_pop6_str = json.dumps(agg_nyko6)

heat_data = []
for idx, row in pts_wgs84.iterrows():
    if row['Totalt'] > 0:
        heat_data.append({
            'lat': round(row.geometry.y, 5), 'lon': round(row.geometry.x, 5),
            'tot': int(row['Totalt']), 'a0_5': int(row['Grp_0_5']), 'a6_15': int(row['Grp_6_15']),
            'a6_9': int(row['Grp_6_9']), 'a10_12': int(row['Grp_10_12']), 'a13_15': int(row['Grp_13_15']),
            'a16_18': int(row['Grp_16_18']), 'a19_64': int(row['Grp_19_64']), 
            'a65_79': int(row['Grp_65_79']), 'a80': int(row['Grp_80plus'])
        })

# --- LÄS IN ALLA POI-FLIKAR MED ORGANISATION ---
print("Hämtar intressepunkter (POI) från Excel-flikar...")
def load_poi_sheet(filepath, sheet_name, name_col, cat_col, layer_type, org_col=None):
    data = []
    try:
        df = pd.read_excel(filepath, sheet_name=sheet_name)
        for _, row in df.iterrows():
            if pd.notna(row.get('Latitud')) and pd.notna(row.get('Longitud')):
                org_val = fix_text(str(row.get(org_col, ''))) if org_col and pd.notna(row.get(org_col)) else ''
                data.append({
                    'namn': fix_text(str(row.get(name_col, 'Okänd'))),
                    'kategori': fix_text(str(row.get(cat_col, layer_type))),
                    'lat': float(row['Latitud']),
                    'lon': float(row['Longitud']),
                    'type': layer_type,
                    'org': org_val
                })
    except Exception as e:
        print(f"INFO: Kunde inte ladda data från fliken '{sheet_name}'.")
    return data

poi_platser = load_poi_sheet(excel_path, 'Platser', 'Plats', 'Kategori', 'plats')
poi_skolor  = load_poi_sheet(excel_path, 'Skolor', 'Skola', 'Nivå', 'skola', 'Organisation')
poi_vard    = load_poi_sheet(excel_path, 'Vårdboende', 'Namn', 'Typ', 'vard')
poi_data = poi_platser + poi_skolor + poi_vard


# --- LÄS IN EXTRA GEOGRAFI ---
transport_path = os.path.join(kart_filer_dir, 'transportleder.geojson')
if os.path.exists(transport_path):
    try:
        transport_geojson = gpd.read_file(transport_path).to_crs(4326).__geo_interface__
    except: transport_geojson = {"type": "FeatureCollection", "features": []}
else: transport_geojson = {"type": "FeatureCollection", "features": []}
transport_str = json.dumps(transport_geojson)

vatten_path = os.path.join(kart_filer_dir, 'vattendrag.geojson')
if os.path.exists(vatten_path):
    try:
        vatten_geojson = gpd.read_file(vatten_path).to_crs(4326).__geo_interface__
    except: vatten_geojson = {"type": "FeatureCollection", "features": []}
else: vatten_geojson = {"type": "FeatureCollection", "features": []}
vatten_str = json.dumps(vatten_geojson)


# =====================================================================
# 3. EXPORTERA TILL LOKAL DATABAS (.JSON filer)
# =====================================================================
centroids_wgs84 = nyko4_3006_centroids.to_crs(epsg=4326)
nyko4_data = []
for idx, row in nyko4.iterrows():
    point = centroids_wgs84.iloc[idx]
    if not point.is_empty:
        nyko4_data.append({
            'namn': row['NAMN'], 'lat': point.y, 'lon': point.x, 'area': row['Area_km2'],
            'k1': str(row.get('Karaktär1', '')), 'k2': str(row.get('Karaktär2', '')),
            'tot': int(row['Folkmängd']), 'pop_change': int(row['Pop_Change']),
            'hushall': float(row.get('Hushallsstorlek', 0)),
            'a0_5': int(row['Grp_0_5']), 'a6_15': int(row['Grp_6_15']), 'a6_9': int(row['Grp_6_9']),
            'a10_12': int(row['Grp_10_12']), 'a13_15': int(row['Grp_13_15']), 'a16_18': int(row['Grp_16_18']),
            'a19_64': int(row['Grp_19_64']), 'a65_79': int(row['Grp_65_79']), 'a80': int(row['Grp_80plus']),
            'agan': int(row.get('Äganderätt', 0)),
            'bost': int(row.get('Bostadsrätt', 0)),
            'hyre': int(row.get('Hyresrätt', 0)),
            'saknas': int(row.get('Uppgift_saknas', 0)),
            'tot_uppl': int(row.get('Totalt_uppl', 0))
        })

# Spara med nya namnet för Nyko4
with open(os.path.join(moder_mapp, OUT_JSON_NAME), 'w', encoding='utf-8') as f: json.dump(nyko4_data, f, ensure_ascii=False)
with open(os.path.join(moder_mapp, 'poi_data.json'), 'w', encoding='utf-8') as f: json.dump(poi_data, f, ensure_ascii=False)
with open(os.path.join(moder_mapp, 'heat_data.json'), 'w', encoding='utf-8') as f: json.dump(heat_data, f, ensure_ascii=False)

nyko4_json_str = json.dumps(nyko4_data)
poi_json_str = json.dumps(poi_data)
heat_data_str = json.dumps(heat_data) # Direkt inkludering för att slippa lokala Fetch-problem!

# =====================================================================
# 4. KARTBYGGE (HTML/JS Visualisering med Folium)
# =====================================================================
print("Genererar karta...")
m = folium.Map(location=[58.4102, 15.6216], zoom_start=11, tiles=None)

viridis_rev = ['#fde725', '#b5de2b', '#6ece58', '#35b779', '#1f9e89', '#26828e', '#31688e', '#3e4989', '#482878', '#440154']

# --- LAGER 1: Befolkning (Koroplet) ---
valid_pop = nyko4[nyko4['Folkmängd'] > 0]['Folkmängd']
min_pop = valid_pop.min() if not valid_pop.empty else 0
max_pop = valid_pop.max() if not valid_pop.empty else 1
colormap_pop = cm.LinearColormap(colors=viridis_rev, vmin=min_pop, vmax=max_pop)

folium.GeoJson(
    nyko4,
    name=f'Befolkning {latest_year}',
    style_function=lambda feature: {
        'fillColor': colormap_pop(feature['properties']['Folkmängd']) if feature['properties']['Folkmängd'] > 0 else 'transparent',
        'color': '#333333', 'weight': 1, 'fillOpacity': 0.60, 'className': 'polygon-layer pop-polygon'
    },
    tooltip=folium.GeoJsonTooltip(fields=['NAMN', 'Karaktär1', 'Karaktär2', 'Folkmängd_visa', 'Area_km2', 'Inv_per_km2_visa'], aliases=['Basområde:', 'Karaktär 1:', 'Karaktär 2:', f'Folkmängd ({latest_year}):', 'Yta (km²):', 'Invånare/km²:'], localize=True)
).add_to(m)

# --- LAGER 2: Befolkningstäthet (Koroplet) ---
valid_dens = nyko4[nyko4['Inv_per_km2'] > 0]['Inv_per_km2']
min_dens = valid_dens.min() if not valid_dens.empty else 0
max_dens = valid_dens.max() if not valid_dens.empty else 1
colormap_dens = cm.LinearColormap(colors=viridis_rev, vmin=min_dens, vmax=max_dens)

folium.GeoJson(
    nyko4,
    name='Befolkningstäthet',
    style_function=lambda feature: {
        'fillColor': colormap_dens(feature['properties']['Inv_per_km2']) if feature['properties']['Inv_per_km2'] > 0 else 'transparent',
        'color': '#333333', 'weight': 1, 'fillOpacity': 0.60, 'className': 'polygon-layer density-polygon'
    },
    tooltip=folium.GeoJsonTooltip(fields=['NAMN', 'Folkmängd_visa', 'Area_km2', 'Inv_per_km2_visa'], aliases=['Basområde:', f'Folkmängd ({latest_year}):', 'Yta (km²):', 'Invånare/km²:'], localize=True)
).add_to(m)

# --- LAGER 3: Hushållsstorlek (Koroplet) ---
valid_hushall = nyko4[nyko4['Hushallsstorlek'] > 0]['Hushallsstorlek']
min_hushall = valid_hushall.min() if not valid_hushall.empty else 0
max_hushall = valid_hushall.max() if not valid_hushall.empty else 1
min_hushall = max(0, min_hushall - 0.2)
max_hushall = max_hushall + 0.2

colormap_hushall = cm.LinearColormap(colors=viridis_rev, vmin=min_hushall, vmax=max_hushall)

folium.GeoJson(
    nyko4,
    name='Hushållsstorlek',
    style_function=lambda feature: {
        'fillColor': colormap_hushall(feature['properties']['Hushallsstorlek']) if feature['properties']['Hushallsstorlek'] > 0 else 'transparent',
        'color': '#333333', 'weight': 1, 'fillOpacity': 0.60, 'className': 'polygon-layer hushall-polygon'
    },
    tooltip=folium.GeoJsonTooltip(fields=['NAMN', 'Folkmängd_visa', 'Hushallsstorlek_visa'], aliases=['Basområde:', f'Folkmängd ({latest_year}):', 'Snitt hushållsstorlek:'], localize=True)
).add_to(m)

# --- LAGER 4-6: Upplåtelseformer (Choropleths) ---
colormap_agan = cm.LinearColormap(colors=viridis_rev, vmin=0, vmax=100)
colormap_bost = cm.LinearColormap(colors=viridis_rev, vmin=0, vmax=100)
colormap_hyre = cm.LinearColormap(colors=viridis_rev, vmin=0, vmax=100)

folium.GeoJson(
    nyko4,
    name='Äganderätt (%)',
    style_function=lambda feature: {
        'fillColor': colormap_agan(feature['properties']['Andel_Aganderatt']) if feature['properties'].get('Totalt_uppl', 0) > 0 else 'transparent',
        'color': '#333333', 'weight': 1, 'fillOpacity': 0.60, 'className': 'polygon-layer agan-polygon'
    },
    tooltip=folium.GeoJsonTooltip(fields=['NAMN', 'Andel_Aganderatt_visa'], aliases=['Basområde:', 'Andel Äganderätt (%):'], localize=True)
).add_to(m)

folium.GeoJson(
    nyko4,
    name='Bostadsrätt (%)',
    style_function=lambda feature: {
        'fillColor': colormap_bost(feature['properties']['Andel_Bostadsratt']) if feature['properties'].get('Totalt_uppl', 0) > 0 else 'transparent',
        'color': '#333333', 'weight': 1, 'fillOpacity': 0.60, 'className': 'polygon-layer bost-polygon'
    },
    tooltip=folium.GeoJsonTooltip(fields=['NAMN', 'Andel_Bostadsratt_visa'], aliases=['Basområde:', 'Andel Bostadsrätt (%):'], localize=True)
).add_to(m)

folium.GeoJson(
    nyko4,
    name='Hyresrätt (%)',
    style_function=lambda feature: {
        'fillColor': colormap_hyre(feature['properties']['Andel_Hyresratt']) if feature['properties'].get('Totalt_uppl', 0) > 0 else 'transparent',
        'color': '#333333', 'weight': 1, 'fillOpacity': 0.60, 'className': 'polygon-layer hyre-polygon'
    },
    tooltip=folium.GeoJsonTooltip(fields=['NAMN', 'Andel_Hyresratt_visa'], aliases=['Basområde:', 'Andel Hyresrätt (%):'], localize=True)
).add_to(m)


# --- LAGER 7: Områdesgränser (Endast linjer) ---
folium.GeoJson(nyko4, name='Områdesgränser', style_function=lambda feature: {'fill': False, 'color': '#2c3e50', 'weight': 2, 'className': 'polygon-layer border-polygon'}).add_to(m)

# --- LAGER 8: MiniMap (Karta i kartan) ---
minimap = MiniMap(
    toggleDisplay=True, 
    position="topleft", 
    zoomLevelOffset=-4, 
    tile_layer="cartodbpositron"
)
m.add_child(minimap)

# =====================================================================
# 6. INJICERA GYLLENE STANDARDMALL (Responsiv UI)
# =====================================================================

ui_html = f"""
<!-- Externa Bibliotek -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" /> <!-- Ikoner -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet-search/3.0.2/leaflet-search.min.css" />
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster/dist/MarkerCluster.css" />
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster/dist/MarkerCluster.Default.css" />
<script src="https://unpkg.com/leaflet.markercluster/dist/leaflet.markercluster.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>
<script src="https://unpkg.com/@turf/turf/turf.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet-search/3.0.2/leaflet-search.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<script src="https://unpkg.com/leaflet.heat/dist/leaflet-heat.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>
    :root {{ --poi-scale: 1; }}

    .tools-panel {{ position: fixed; bottom: 30px; left: 60px; z-index: 9999; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 300px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; transition: all 0.3s ease; }}
    .layers-panel {{ position: fixed; top: 20px; right: 20px; z-index: 9999; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 290px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; }}
    
    .info-panel {{ position: fixed; top: 20px; right: 330px; z-index: 9999; background: rgba(255,255,255,0.98); padding: 20px; border-radius: 8px; box-shadow: 0 0 20px rgba(0,0,0,0.3); width: 320px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; display: none; transition: all 0.3s ease; font-size: 14px; line-height: 1.5; }}
    .info-panel p {{ margin-bottom: 6px; }}
    
    .btn-custom {{ width: 100%; margin-bottom: 8px; text-align: left; font-size: 14px; padding: 6px 12px; }}
    .form-check-input {{ transform: scale(1.55); margin-top: 4px; margin-right: 12px; cursor: pointer; }}
    .form-check-label {{ cursor: pointer; font-size: 13px; }}
    
    .custom-marker {{ display: flex; justify-content: center; align-items: center; border-radius: 50%; color: white; font-size: 13px; box-shadow: 0 2px 5px rgba(0,0,0,0.5); border: 2px solid white; transform: scale(var(--poi-scale)); transition: transform 0.2s ease; transform-origin: center; }}
    .marker-pulse {{ animation: pulse 2s infinite; border: 3px solid gold !important; z-index: 1000 !important; }}
    @keyframes pulse {{
        0% {{ box-shadow: 0 0 0 0 rgba(243, 156, 18, 0.7); transform: scale(calc(var(--poi-scale) * 1.15)); }}
        70% {{ box-shadow: 0 0 0 15px rgba(243, 156, 18, 0); transform: scale(calc(var(--poi-scale) * 1.15)); }}
        100% {{ box-shadow: 0 0 0 0 rgba(243, 156, 18, 0); transform: scale(calc(var(--poi-scale) * 1.15)); }}
    }}

    /* RESPONSIV LEGEND-CONTAINER (EGENBYGGD) */
    .legend-container {{ position: fixed; bottom: 30px; right: 20px; z-index: 9998; display: flex; flex-direction: column; gap: 10px; pointer-events: none; max-height: 80vh; overflow-y: auto; }}
    .variable-legend {{ pointer-events: auto; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 220px; }}
    
    .leaflet-control-search .search-input {{ padding: 6px 10px; border-radius: 4px; border: 1px solid #ccc; outline: none; width: 190px; font-size: 14px; }}
    
    /* FIXAD CSS FÖR KLUSTER */
    .cluster-custom {{ background-color: transparent; }}
    .cluster-custom div {{ background-color: rgba(41, 128, 185, 0.95); color: white; border-radius: 50%; width: 34px; height: 34px; margin: 3px; text-align: center; line-height: 34px; font-weight: bold; font-size: 12px; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.4); }}

    .popup-table {{ width: 100%; font-size: 14px; }}
    .popup-table th {{ border-bottom: 2px solid #333; padding-bottom: 5px; margin-bottom: 5px; text-align:left; }}
    .popup-table td {{ padding-top: 3px; padding-bottom: 3px; }}
    .bar-bg {{ background: #e0e0e0; width: 100%; height: 12px; border-radius: 3px; overflow: hidden; margin-top:2px; }}
    .bar-fill {{ background: #3498db; height: 100%; }}
    
    /* RESPONSIVITET FÖR MOBILER */
    @media (max-width: 768px) {{
        .tools-panel {{ bottom: 10px; left: 10px; width: 220px; padding: 10px; }}
        .tools-panel button {{ font-size: 11px !important; padding: 6px !important; margin-bottom: 5px !important; }}
        .layers-panel {{ top: 10px; right: 10px; width: 220px; padding: 10px; }}
        .info-panel {{ top: 10px; right: 10px; width: calc(100% - 20px); max-height: 60vh; }}
        .legend-container {{ bottom: 10px; right: 10px; transform: scale(0.85); transform-origin: bottom right; }}
        .leaflet-control-minimap {{ display: none !important; }} /* DÖLJER MINIMAPEN HELT PÅ MOBILER! */
    }}
</style>

<!-- EGENBYGGDA, STABILA HTML-LEGENDER -->
<div class="legend-container" id="legend-container">
    <div id="legend-pop" class="variable-legend" style="display: block;">
        <h6 style="font-size: 13px; font-weight: bold; margin-bottom: 5px; color:#333;">Befolkning {latest_year} (inv)</h6>
        <div style="background: linear-gradient(to right, #fde725, #b5de2b, #6ece58, #35b779, #1f9e89, #26828e, #31688e, #3e4989, #482878, #440154); height: 12px; border-radius: 3px; width: 100%;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-top: 3px; color:#666;">
            <span>{int(min_pop)}</span>
            <span>{int(max_pop)}</span>
        </div>
    </div>

    <div id="legend-dens" class="variable-legend" style="display: none;">
        <h6 style="font-size: 13px; font-weight: bold; margin-bottom: 5px; color:#333;">Täthet {latest_year} (inv/km²)</h6>
        <div style="background: linear-gradient(to right, #fde725, #b5de2b, #6ece58, #35b779, #1f9e89, #26828e, #31688e, #3e4989, #482878, #440154); height: 12px; border-radius: 3px; width: 100%;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-top: 3px; color:#666;">
            <span>{int(min_dens)}</span>
            <span>{int(max_dens)}</span>
        </div>
    </div>

    <div id="legend-hushall" class="variable-legend" style="display: none;">
        <h6 style="font-size: 13px; font-weight: bold; margin-bottom: 5px; color:#333;">Hushållsstorlek (snitt)</h6>
        <div style="background: linear-gradient(to right, #fde725, #b5de2b, #6ece58, #35b779, #1f9e89, #26828e, #31688e, #3e4989, #482878, #440154); height: 12px; border-radius: 3px; width: 100%;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-top: 3px; color:#666;">
            <span>{round(min_hushall, 1)}</span>
            <span>{round(max_hushall, 1)}</span>
        </div>
    </div>

    <div id="legend-agan" class="variable-legend" style="display: none;">
        <h6 style="font-size: 13px; font-weight: bold; margin-bottom: 5px; color:#333;">Andel Äganderätt (%)</h6>
        <div style="background: linear-gradient(to right, #fde725, #b5de2b, #6ece58, #35b779, #1f9e89, #26828e, #31688e, #3e4989, #482878, #440154); height: 12px; border-radius: 3px; width: 100%;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-top: 3px; color:#666;">
            <span>0</span>
            <span>100</span>
        </div>
    </div>

    <div id="legend-bost" class="variable-legend" style="display: none;">
        <h6 style="font-size: 13px; font-weight: bold; margin-bottom: 5px; color:#333;">Andel Bostadsrätt (%)</h6>
        <div style="background: linear-gradient(to right, #fde725, #b5de2b, #6ece58, #35b779, #1f9e89, #26828e, #31688e, #3e4989, #482878, #440154); height: 12px; border-radius: 3px; width: 100%;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-top: 3px; color:#666;">
            <span>0</span>
            <span>100</span>
        </div>
    </div>

    <div id="legend-hyre" class="variable-legend" style="display: none;">
        <h6 style="font-size: 13px; font-weight: bold; margin-bottom: 5px; color:#333;">Andel Hyresrätt (%)</h6>
        <div style="background: linear-gradient(to right, #fde725, #b5de2b, #6ece58, #35b779, #1f9e89, #26828e, #31688e, #3e4989, #482878, #440154); height: 12px; border-radius: 3px; width: 100%;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-top: 3px; color:#666;">
            <span>0</span>
            <span>100</span>
        </div>
    </div>
</div>

<div id="infoPanel" class="info-panel">
    <div class="d-flex justify-content-between align-items-center mb-3" style="border-bottom: 2px solid #ccc; padding-bottom: 8px;">
        <h5 class="fw-bold mb-0">📊 Information</h5>
        <button type="button" class="btn-close" onclick="closeInfoPanel()"></button>
    </div>
    <div id="infoPanelContent"></div>
</div>

<div class="modal fade" id="chartModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-lg modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title fw-bold" id="chartModalLabel">Befolkningsutveckling</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body">
        <canvas id="popChart" height="120"></canvas>
      </div>
    </div>
  </div>
</div>

<!-- PANEL 1: VERKTYG (Vänster) -->
<div class="tools-panel">
    <h6 class="fw-bold mb-3">🛠️ Analysverktyg</h6>
    
    <div class="p-2 mb-3 bg-white border border-secondary rounded shadow-sm">
        <div class="d-flex justify-content-between align-items-center mb-1">
            <label for="opacitySlider" class="form-label mb-0 fw-bold" style="font-size: 13px; color: #2c3e50;">Opacitet färgade ytor:</label>
            <span id="opacityVal" class="badge bg-primary" style="font-size: 12px;">60%</span>
        </div>
        <input type="range" class="form-range" id="opacitySlider" min="0" max="1" step="0.05" value="0.60">
    </div>

    <div class="p-2 mb-3 bg-light border rounded">
        <h6 class="fw-bold mb-2" style="font-size: 13px;">Värmekartor (Var bor invånarna?)</h6>
        <select id="heatSelect" class="form-select form-select-sm" style="font-size: 13px;">
            <option value="none" selected>Ingen värmekarta aktiv</option>
            <option value="tot">Totalt alla invånare</option>
            <option value="a0_5">Barn i förskoleålder (0-5 år)</option>
            <option value="a6_15">Barn i grundskoleålder (6-15 år)</option>
            <option value="a16_18">Ungdomar i gymnasieålder (16-18 år)</option>
            <option value="a19_64">Vuxna / Arbetsföra (19-64 år)</option>
            <option value="a65_79">Äldre (65-79 år)</option>
            <option value="a80">Äldst (80+ år)</option>
        </select>
    </div>

    <h6 class="fw-bold mb-2" style="font-size: 13px;">Kartvy & Zooma</h6>
    <select id="zoomSelect" class="form-select form-select-sm mb-2" style="font-size: 13px;">
        <option value="">-- Zooma till enskilt basområde --</option>
    </select>
    <select id="zoomKaraktar1" class="form-select form-select-sm mb-2" style="font-size: 13px;">
        <option value="">-- Zooma till Huvudkaraktär (Karaktär 1) --</option>
    </select>
    <select id="zoomKaraktar2" class="form-select form-select-sm mb-2" style="font-size: 13px;">
        <option value="">-- Zooma till Detaljkaraktär (Karaktär 2) --</option>
    </select>
    
    <div class="form-check mb-3 mt-2">
        <input class="form-check-input" type="checkbox" id="toggleGraph" checked>
        <label class="form-check-label fw-bold" for="toggleGraph" style="font-size: 12px; color:#2c3e50;">📈 Visa graf vid klick (Områden)</label>
    </div>

    <button id="btn-reset" class="btn btn-outline-secondary btn-sm btn-custom mb-3">🔄 Återställ & Rensa allt</button>

    <h6 class="fw-bold mb-2" style="font-size: 13px;">Geografiska mätverktyg</h6>
    <button id="btn-measure" class="btn btn-outline-primary btn-sm btn-custom">📏 Avståndsmätare (Centrum)</button>
    <button id="btn-isochrone" class="btn btn-outline-info btn-sm btn-custom">⏱️ 10-min Nåbarhetsanalys</button>
    
    <hr style="margin: 8px 0;">
    <button id="btn-export" class="btn btn-outline-success btn-sm btn-custom">📷 Spara karta som bild</button>
</div>

<!-- PANEL 2: LAGERKONTROLL (Höger) -->
<div class="layers-panel">
    <h6 class="fw-bold mb-3">🗂️ Kartlager</h6>
    
    <h6 class="fw-bold mb-2" style="font-size: 13px;">Bakgrundskarta</h6>
    <select id="basemapSelect" class="form-select form-select-sm mb-3" style="font-size: 13px;">
        <option value="blek" selected>Karta: Blek (För tydlig analys)</option>
        <option value="farg">Karta: Färgstark (Detaljerad)</option>
        <option value="flyg">Karta: Flygfoto (Satellit)</option>
    </select>
    
    <hr style="margin: 10px 0;">
    <h6 class="fw-bold mb-2" style="font-size: 13px;">Ytor & Områden</h6>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="togglePop" checked><label class="form-check-label" for="togglePop">Befolkning {latest_year}</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleDens"><label class="form-check-label" for="toggleDens">Befolkningstäthet</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleHushall"><label class="form-check-label" for="toggleHushall">Hushållsstorlek</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleAgan"><label class="form-check-label" for="toggleAgan">Äganderätt (%)</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleBost"><label class="form-check-label" for="toggleBost">Bostadsrätt (%)</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleHyre"><label class="form-check-label" for="toggleHyre">Hyresrätt (%)</label></div>
    <div class="form-check mb-1 mt-2"><input class="form-check-input" type="checkbox" id="toggleBorders"><label class="form-check-label" for="toggleBorders">Områdesgränser</label></div>
    
    <hr style="margin: 10px 0;">
    <h6 class="fw-bold mb-2" style="font-size: 13px;">Infrastruktur & Natur</h6>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleTransport"><label class="form-check-label" for="toggleTransport">🛤️ Transportleder (Väg/Järnväg)</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleVatten"><label class="form-check-label" for="toggleVatten">💧 Sjöar & Vattendrag</label></div>

    <hr style="margin: 10px 0;">
    <h6 class="fw-bold mb-2" style="font-size: 13px;">Analyspunkter</h6>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleCentroids"><label class="form-check-label" for="toggleCentroids">🟡 Centrumpunkter</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleCircles"><label class="form-check-label" for="toggleCircles">🟢 Befolkningsringar (Åldrar)</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleClusters"><label class="form-check-label" for="toggleClusters">🔵 Detaljerad Befolkning (Kluster)</label></div>
    <div class="form-check mb-1">
        <input class="form-check-input" type="checkbox" id="toggleDynPop">
        <label class="form-check-label" for="toggleDynPop">🟠 Dynamisk Befolkning <span id="dynPopLabel" class="badge ms-1" style="display:none; font-size:10px; font-weight:normal;"></span></label>
    </div>
    
    <hr style="margin: 10px 0;">
    <h6 class="fw-bold mb-2" style="font-size: 13px;">Intresseplatser (POI)</h6>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleGrundskolor"><label class="form-check-label" for="toggleGrundskolor"><i class="fas fa-child text-primary"></i> Grundskolor</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleGymnasieskolor"><label class="form-check-label" for="toggleGymnasieskolor"><i class="fas fa-graduation-cap" style="color:#9b59b6;"></i> Gymnasieskolor</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleHandel"><label class="form-check-label" for="toggleHandel"><i class="fas fa-shopping-cart" style="color:#e67e22;"></i> Handel & Centrum</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleIdrott"><label class="form-check-label" for="toggleIdrott"><i class="fas fa-futbol text-success"></i> Idrott & Fritid</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleSamhalle"><label class="form-check-label" for="toggleSamhalle"><i class="fas fa-building" style="color:#34495e;"></i> Samhälle & Infrastruktur</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleKultur"><label class="form-check-label" for="toggleKultur"><i class="fas fa-theater-masks text-danger"></i> Kultur & Sevärdheter</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleOvriga"><label class="form-check-label" for="toggleOvriga"><i class="fas fa-map-marker-alt text-secondary"></i> Övriga platser</label></div>
    
    <button id="btnZoomPOI" class="btn btn-sm btn-outline-primary mt-3 w-100 fw-bold" style="font-size: 13px;">🔍 Zooma till valda platser</button>
</div>

<script>
    var lastZoomBounds = null;

    document.addEventListener('DOMContentLoaded', function() {{
        var map_id = Object.keys(window).find(key => key.startsWith('map_'));
        var map = window[map_id];
        var upplatelseChartInstans = null; // --- GLOBAL VARIABEL FÖR DIAGRAMMET ---
        
        document.documentElement.style.setProperty('--poi-scale', 1 + (map.getZoom() - 11) * 0.15);
        map.on('zoomend', function() {{
            var z = map.getZoom();
            var s = 1 + (z - 11) * 0.15; 
            if (s < 0.8) s = 0.8;
            if (s > 2.5) s = 2.5;
            document.documentElement.style.setProperty('--poi-scale', s);
        }});
        
        function getDistance(lat1, lon1, lat2, lon2) {{
            var R = 6371; var dLat = (lat2 - lat1) * Math.PI / 180; var dLon = (lon2 - lon1) * Math.PI / 180;
            var a = Math.sin(dLat/2) * Math.sin(dLat/2) + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon/2) * Math.sin(dLon/2);
            return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        }}

        function estimateTravelTimes(lat, lon) {{
            var distRC = getDistance(lat, lon, 58.4162, 15.6265);
            var walkTimeRC = Math.round((distRC * 1.3 / 5) * 60); 
            var bikeTimeRC = Math.round((distRC * 1.2 / 15) * 60); 
            var carTimeRC = Math.round((distRC * 1.3 / 40) * 60) + 1; 
            var ptTimeRC = Math.round((distRC * 1.4 / 20) * 60) + 5; 
            
            var distST = getDistance(lat, lon, 58.410689, 15.621606);
            var carDistST = (distST * 1.3).toFixed(2);
            var bikeDistST = (distST * 1.2).toFixed(2);
            
            return {{ rc: {{ walk: walkTimeRC, bike: bikeTimeRC, car: carTimeRC, pt: ptTimeRC }}, st: {{ dist: distST.toFixed(2), car: carDistST, bike: bikeDistST }} }};
        }}

        window.closeInfoPanel = function() {{
            document.getElementById('infoPanel').style.display = 'none';
            if (lastZoomBounds) {{ map.flyToBounds(lastZoomBounds, {{padding: [50, 50], maxZoom: 15}}); }}
        }}

        function showInfoPanel(htmlContent) {{
            document.getElementById('infoPanelContent').innerHTML = htmlContent;
            document.getElementById('infoPanel').style.display = 'block';
        }}

        var tileBlek = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{ attribution: '&copy; OpenStreetMap contributors &copy; CARTO', crossOrigin: true }}).addTo(map);
        var tileFarg = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ attribution: '&copy; OpenStreetMap contributors', crossOrigin: true }});
        var tileFlyg = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EAP, and the GIS User Community', crossOrigin: true }});

        document.getElementById('basemapSelect').addEventListener('change', function(e) {{
            map.removeLayer(tileBlek);
            map.removeLayer(tileFarg);
            map.removeLayer(tileFlyg);
            
            var isFlyg = false;
            if(e.target.value === 'blek') {{ tileBlek.addTo(map); }} 
            else if(e.target.value === 'farg') {{ tileFarg.addTo(map); }}
            else if(e.target.value === 'flyg') {{ tileFlyg.addTo(map); isFlyg = true; }}
            
            var borderColor = isFlyg ? '#ffffff' : '#2c3e50';
            map.eachLayer(function(layer) {{
                if (layer.options && layer.options.className && layer.options.className.includes('border-polygon')) {{
                    if (layer.setStyle) {{
                        layer.setStyle({{color: borderColor}});
                        layer.options.color = borderColor;
                        if (layer.defaultStyle) {{
                            layer.defaultStyle.color = borderColor;
                        }}
                    }}
                }}
            }});
        }});

        // --- UPPDATERAD VISIBILITETSFUNKTION FÖR ATT HANTERA EGNA HTML-LEGENDER ---
        function updatePolygonVisibility() {{
            var showPop = document.getElementById('togglePop').checked;
            var showDens = document.getElementById('toggleDens').checked;
            var showHushall = document.getElementById('toggleHushall').checked;
            var showAgan = document.getElementById('toggleAgan').checked;
            var showBost = document.getElementById('toggleBost').checked;
            var showHyre = document.getElementById('toggleHyre').checked;
            var showBorders = document.getElementById('toggleBorders').checked;

            var activeK1 = document.getElementById('zoomKaraktar1').value;
            var activeK2 = document.getElementById('zoomKaraktar2').value;

            map.eachLayer(function(layer) {{
                if (layer.feature && layer.feature.properties && layer.feature.properties.NAMN) {{
                    var props = layer.feature.properties;
                    
                    var match1 = activeK1 === "" || props.Karaktär1 === activeK1;
                    var match2 = activeK2 === "" || props.Karaktär2 === activeK2;
                    var matchesFilter = match1 && match2;

                    if (layer.options && layer.options.className) {{
                        var cls = layer.options.className;
                        var layerVisible = false;
                        if (cls.includes('pop-polygon') && showPop) layerVisible = true;
                        if (cls.includes('density-polygon') && showDens) layerVisible = true;
                        if (cls.includes('hushall-polygon') && showHushall) layerVisible = true;
                        if (cls.includes('agan-polygon') && showAgan) layerVisible = true;
                        if (cls.includes('bost-polygon') && showBost) layerVisible = true;
                        if (cls.includes('hyre-polygon') && showHyre) layerVisible = true;
                        if (cls.includes('border-polygon') && showBorders) layerVisible = true;

                        var path = layer.getElement ? layer.getElement() : layer._path;
                        if (path) {{
                            path.style.display = (layerVisible && matchesFilter) ? '' : 'none';
                        }}
                    }}
                }}
            }});
            
            // --- Hantera synlighet för våra inbyggda HTML-Legender ---
            document.querySelectorAll('.variable-legend').forEach(el => el.style.display = 'none');
            
            if (showPop) {{
                document.getElementById('legend-pop').style.display = 'block';
            }} else if (showDens) {{
                document.getElementById('legend-dens').style.display = 'block';
            }} else if (showHushall) {{
                document.getElementById('legend-hushall').style.display = 'block';
            }} else if (showAgan) {{
                document.getElementById('legend-agan').style.display = 'block';
            }} else if (showBost) {{
                document.getElementById('legend-bost').style.display = 'block';
            }} else if (showHyre) {{
                document.getElementById('legend-hyre').style.display = 'block';
            }}
        }}

        document.getElementById('opacitySlider').addEventListener('input', function(e) {{
            var val = e.target.value;
            document.getElementById('opacityVal').innerText = Math.round(val * 100) + '%';
            document.querySelectorAll('.pop-polygon, .density-polygon, .hushall-polygon, .agan-polygon, .bost-polygon, .hyre-polygon, .default-polygon').forEach(el => {{ el.style.fillOpacity = val; }});
        }});

        // --- ÖMSESIDIGT UTESLUTANDE RADIOLIKNANDE LOGIK FÖR YTOR ---
        var baseLayers = ['togglePop', 'toggleDens', 'toggleHushall', 'toggleAgan', 'toggleBost', 'toggleHyre'];
        
        baseLayers.forEach(function(id) {{
            var el = document.getElementById(id);
            if (el) {{
                el.addEventListener('change', function(e) {{
                    if (e.target.checked) {{
                        baseLayers.forEach(function(otherId) {{
                            if (otherId !== id) {{
                                document.getElementById(otherId).checked = false;
                            }}
                        }});
                    }}
                    updatePolygonVisibility();
                }});
            }}
        }});

        document.getElementById('toggleBorders').addEventListener('change', function(e) {{
            updatePolygonVisibility();
        }});

        updatePolygonVisibility();

        // Data injicerad från Python
        var nykoData = {nyko4_json_str}; 
        var poiData = {poi_json_str}; 
        var heatDataRaw = {heat_data_str}; 
        var transportData = {transport_str}; 
        var vattenData = {vatten_str};

        var dynPop1 = {dyn_pop1_str};
        var dynPop3 = {dyn_pop3_str};
        var dynPop4 = {dyn_pop4_str};
        var dynPop6 = {dyn_pop6_str};

        // --- DYNAMISK POPULERING AV ZOOM-MENYER ---
        var zoomSel = document.getElementById('zoomSelect');
        var zoomSelK1 = document.getElementById('zoomKaraktar1');
        var zoomSelK2 = document.getElementById('zoomKaraktar2');
        
        var k1Set = new Set();
        var k2Set = new Set();
        
        nykoData.sort((a,b) => a.namn.localeCompare(b.namn)).forEach(function(d) {{
            var opt = document.createElement('option'); opt.value = d.lat + ',' + d.lon; opt.innerHTML = d.namn; zoomSel.appendChild(opt);
            if(d.k1) k1Set.add(d.k1);
            if(d.k2) k2Set.add(d.k2);
        }});
        
        Array.from(k1Set).sort().forEach(function(k) {{
            var opt = document.createElement('option'); opt.value = k; opt.innerHTML = k; zoomSelK1.appendChild(opt);
        }});
        
        Array.from(k2Set).sort().forEach(function(k) {{
            var opt = document.createElement('option'); opt.value = k; opt.innerHTML = k; zoomSelK2.appendChild(opt);
        }});

        function zoomToCategory(prop, value) {{
            if(!value) return;
            var bounds = L.latLngBounds();
            var count = 0;
            nykoData.forEach(function(d) {{
                if(d[prop] === value) {{ bounds.extend([d.lat, d.lon]); count++; }}
            }});
            if(count > 0) {{
                map.flyToBounds(bounds, {{padding: [50, 50], maxZoom: 13}});
                lastZoomBounds = bounds;
            }}
        }}

        zoomSel.addEventListener('change', function() {{
            if(this.value) {{ var coords = this.value.split(','); map.flyTo([parseFloat(coords[0]), parseFloat(coords[1])], 14); }}
            zoomSelK1.value = ""; zoomSelK2.value = "";
            updatePolygonVisibility();
        }});
        
        zoomSelK1.addEventListener('change', function() {{ zoomToCategory('k1', this.value); zoomSel.value = ""; zoomSelK2.value = ""; updatePolygonVisibility(); }});
        zoomSelK2.addEventListener('change', function() {{ zoomToCategory('k2', this.value); zoomSel.value = ""; zoomSelK1.value = ""; updatePolygonVisibility(); }});
        
        // --- LÖSNING PÅ PANES (Tvingar cirklar att ligga ovanpå polygoner) ---
        map.createPane('centroidPane'); map.getPane('centroidPane').style.zIndex = 650;
        map.createPane('circlePane'); map.getPane('circlePane').style.zIndex = 600;

        var centroidLayer = L.featureGroup(); // Startar EJ på kartan
        var searchLayer = L.layerGroup().addTo(map); var customRadiusLayer = L.featureGroup().addTo(map); 
        var circleLayer = L.featureGroup(); var layerGrundskolor = L.featureGroup(); var layerGymnasieskolor = L.featureGroup(); var layerHandel = L.featureGroup(); var layerIdrott = L.featureGroup(); var layerSamhalle = L.featureGroup(); var layerKultur = L.featureGroup(); var layerOvriga = L.featureGroup(); var layerVard = L.featureGroup();

        var layerTransport = L.geoJSON(transportData, {{ style: function(feature) {{ var props = feature.properties || {{}}; if (props.railway || (props.fklass && props.fklass.toLowerCase().includes('järnväg'))) return {{ color: '#000000', weight: 3, dashArray: '5, 5' }}; else if (props.highway === 'motorway' || (props.namn && props.namn.includes('E4'))) return {{ color: '#e74c3c', weight: 4 }}; else return {{ color: '#f39c12', weight: 2 }}; }} }});
        var layerVatten = L.geoJSON(vattenData, {{ style: function(feature) {{ return {{ color: '#3498db', fillColor: '#3498db', weight: 1, fillOpacity: 0.5 }}; }} }});

        function safeStat(val) {{ return (val > 0 && val < 5) ? '< 5' : val; }} // Uppdaterad för sekretess
        
        function makeBarRow(label, value, total) {{
            var pct = total > 0 && value >= 5 ? ((value / total) * 100).toFixed(1) : 0;
            return `<tr><td style="width: 45%;">${{label}}</td><td style="width: 15%; text-align: right;"><strong>${{safeStat(value)}}</strong></td><td style="width: 40%; padding-left: 10px;"><div class="bar-bg"><div class="bar-fill" style="width: ${{pct}}%; background: ${{pct > 25 ? '#e74c3c' : '#3498db'}};"></div></div></td></tr>`;
        }}
        function makeSubRow(label, value) {{ return `<tr style="color: #666; font-size: 12px;"><td style="padding-left: 15px;">↳ varav ${{label}}</td><td style="text-align: right;">${{safeStat(value)}}</td><td></td></tr>`; }}

        function generateDemographicHtml(title, stats) {{
            // Maskera hela popupen med < 5 (Sekretess) för små basområden eller dynamiska nivåer
            if (stats.tot > 0 && stats.tot < 5) {{
                return `<h5 style="border-bottom:2px solid #333; padding-bottom:5px; margin-bottom:12px;"><b>${{title}}</b></h5>
                        <p style="color: #c0392b; font-weight: bold; font-size: 15px;">Sekretesskyddad data (< 5 invånare)</p>
                        <p style="font-size: 13px; color: #555;">Detaljerad demografisk information visas ej då för få personer är skrivna inom området.</p>`;
            }}
            
            return `<h5 style="border-bottom:2px solid #333; padding-bottom:5px; margin-bottom:12px;"><b>${{title}}</b></h5><table class="popup-table"><tr style="font-size:15px;"><td style="width: 60%;"><b>Totalt invånare:</b></td><td style="text-align: right;"><b>${{safeStat(stats.tot)}}</b></td><td style="width: 40%;"></td></tr><tr><td colspan="3"><hr style="margin: 5px 0;"></td></tr>${{makeBarRow('0-5 år', stats.a0_5, stats.tot)}}${{makeBarRow('6-15 år', stats.a6_15, stats.tot)}}${{makeSubRow('6-9 år', stats.a6_9)}}${{makeSubRow('10-12 år', stats.a10_12)}}${{makeSubRow('13-15 år', stats.a13_15)}}${{makeBarRow('16-18 år', stats.a16_18, stats.tot)}}${{makeBarRow('19-64 år', stats.a19_64, stats.tot)}}${{makeBarRow('65-79 år', stats.a65_79, stats.tot)}}${{makeBarRow('80+ år', stats.a80, stats.tot)}}</table>`;
        }}

        function getDemographicsInRadius(lat, lon, radiusKm) {{
            var circlePoly = turf.circle([lon, lat], radiusKm, {{steps: 64, units: 'kilometers'}});
            var stats = {{ tot: 0, a0_5: 0, a6_15: 0, a6_9: 0, a10_12: 0, a13_15: 0, a16_18: 0, a19_64: 0, a65_79: 0, a80: 0 }};
            if (heatDataRaw && heatDataRaw.length > 0) {{
                heatDataRaw.forEach(function(p) {{
                    if (turf.booleanPointInPolygon(turf.point([p.lon, p.lat]), circlePoly)) {{
                        stats.tot += p.tot; stats.a0_5 += p.a0_5; stats.a6_15 += p.a6_15; stats.a6_9 += p.a6_9; stats.a10_12 += p.a10_12; stats.a13_15 += p.a13_15;
                        stats.a16_18 += p.a16_18; stats.a19_64 += p.a19_64; stats.a65_79 += p.a65_79; stats.a80 += p.a80;
                    }}
                }});
            }}
            return stats;
        }}

        nykoData.forEach(function(d) {{
            if(d.tot > 0) {{
                var radius = Math.max(4, Math.sqrt(d.tot) * 0.4); 
                var prevTot = d.tot - d.pop_change; var pctChange = prevTot > 0 ? (d.pop_change / prevTot) * 100 : 0;
                var circleColor = '#f1c40f'; if (pctChange > 0.4) circleColor = '#27ae60'; else if (pctChange < -0.4) circleColor = '#e74c3c';
                var changeSign = d.pop_change > 0 ? '+' : '';
                
                var panelHtml = `${{generateDemographicHtml(d.namn, d)}}<div style="background: #f8f9fa; padding: 10px; border-radius: 5px; margin-top: 15px;"><p style="margin: 0; font-size: 14px;"><b>Utveckling (1 år):</b> <strong style="color:${{circleColor}}">${{changeSign}}${{d.pop_change}} inv (${{pctChange.toFixed(1)}}%)</strong></p></div>`;
                
                // --- TILLDELAR PANE 'circlePane' HÄR ---
                var circle = L.circleMarker([d.lat, d.lon], {{ radius: radius, fillColor: circleColor, color: '#fff', weight: 1, fillOpacity: 0.8, className: 'pop-ring', pane: 'circlePane' }}).bindTooltip("Klicka för åldersfördelning", {{direction: 'top'}});
                circle.on('click', function() {{ showInfoPanel(panelHtml); map.flyTo([d.lat, d.lon], 15); }});
                circle.addTo(circleLayer);

                var t = estimateTravelTimes(d.lat, d.lon); 
                var distances = nykoData.map(node => ({{ node: node, dist: getDistance(d.lat, d.lon, node.lat, node.lon) }})).filter(n => n.dist > 0 && n.node.namn !== d.namn); distances.sort((a,b) => a.dist - b.dist); var nearest = distances.slice(0, 3);
                var nnHtml = nearest.map(n => `<li style="margin-bottom:4px;">${{n.node.namn}}: <b>${{n.dist.toFixed(2)}} km</b></li>`).join('');

                // --- BYGGER TABBADE STRUKTUREN MED DIAGRAM ---
                var chartContent = d.tot_uppl > 0 
                    ? `<div style="height: 200px; width: 100%; position: relative;"><canvas id="upplatelsePieChart"></canvas></div><p style="font-size:12px; color:#666; margin-top:10px; text-align:center; margin-bottom:0;">Totalt antal hushåll: ${{d.tot_uppl}}</p>` 
                    : `<p style="text-align:center; font-style:italic; color:#999; margin-top:30px;">Upplåtelseform saknas för detta område.</p>`;

                var tabsHtml = `
                    <h4 style="border-bottom:2px solid #333; padding-bottom:5px; margin-bottom:12px;"><b>${{d.namn}}</b></h4>
                    <ul class="nav nav-tabs" role="tablist">
                        <li class="nav-item" role="presentation">
                            <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#tab-oversikt" type="button" style="padding: 6px 10px; font-size: 13px; color:#2c3e50;">Översikt</button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-uppl" type="button" style="padding: 6px 10px; font-size: 13px; color:#2c3e50;">Upplåtelseform</button>
                        </li>
                    </ul>
                    <div class="tab-content" style="padding-top: 12px;">
                        <div class="tab-pane fade show active" id="tab-oversikt" role="tabpanel">
                            <p style="font-size:14px; margin-bottom: 6px;"><b>Folkmängd:</b> ${{safeStat(d.tot)}} invånare</p>
                            <p style="font-size:14px; margin-bottom: 10px;"><b>Kategori:</b> ${{d.k1}} / ${{d.k2}}</p>
                            <p style="font-size:14px; margin-bottom: 6px;"><b>Fågelväg t. Stora torget:</b> 🚲 ${{t.st.bike}} km | 🚗 ${{t.st.car}} km</p>
                            <p style="font-size:14px; margin-bottom: 12px;"><b>Restid t. Resecentrum:</b><br>🚶 ${{t.rc.walk}} min | 🚲 ${{t.rc.bike}} min | 🚌 ${{t.rc.pt}} min | 🚗 ${{t.rc.car}} min</p>
                            <div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">
                                <b style="display:block; margin-bottom:5px; font-size:13px;">De 3 närmaste grannarna:</b>
                                <ul style="padding-left:20px; margin-bottom:0; font-size:13px;">${{nnHtml}}</ul>
                            </div>
                        </div>
                        <div class="tab-pane fade" id="tab-uppl" role="tabpanel">
                            ${{chartContent}}
                        </div>
                    </div>
                `;
                
                var centroidMarker = L.circleMarker([d.lat, d.lon], {{ radius: 7, fillColor: '#f1c40f', color: '#e74c3c', weight: 2, fillOpacity: 1, pane: 'centroidPane' }}).bindTooltip("Klicka för områdesanalys", {{direction: 'top'}});
                
                centroidMarker.on('click', function() {{ 
                    showInfoPanel(tabsHtml); 
                    map.flyTo([d.lat, d.lon], 15); 

                    // --- DIAGRAMRITNING ---
                    if (d.tot_uppl > 0) {{
                        setTimeout(() => {{
                            var ctx = document.getElementById('upplatelsePieChart');
                            if (ctx) {{
                                if (upplatelseChartInstans) {{ upplatelseChartInstans.destroy(); }}
                                upplatelseChartInstans = new Chart(ctx.getContext('2d'), {{
                                    type: 'pie',
                                    data: {{
                                        labels: ['Äganderätt', 'Bostadsrätt', 'Hyresrätt', 'Uppgift saknas'],
                                        datasets: [{{
                                            data: [d.agan, d.bost, d.hyre, d.saknas],
                                            backgroundColor: ['#2ecc71', '#3498db', '#e74c3c', '#95a5a6'],
                                            borderWidth: 1
                                        }}]
                                    }},
                                    options: {{
                                        responsive: true, 
                                        maintainAspectRatio: false,
                                        plugins: {{ legend: {{ position: 'right', labels: {{ boxWidth: 10, font: {{ size: 11 }} }} }} }}
                                    }}
                                }});
                            }}
                        }}, 50); // Timeout låter DOM rita HTML innan vi bygger diagrammet
                    }}
                }});
                
                centroidMarker.feature = {{ properties: {{ name: d.namn }} }}; 
                centroidMarker.addTo(centroidLayer);
                
                var ghost = L.marker([d.lat, d.lon], {{opacity: 0, interactive: false}}); ghost.feature = {{ properties: {{ name: d.namn }} }}; ghost.addTo(searchLayer);
            }}
        }});

        poiData.forEach(function(p) {{
            var cat = p.kategori.toLowerCase(); var typ = p.type; 
            var targetLayer = layerOvriga; var markerColor = '#bdc3c7'; var iconClass = 'fa-map-marker-alt';

            if (typ === 'skola' && cat.includes('grundskola')) {{ targetLayer = layerGrundskolor; markerColor = '#3498db'; iconClass = 'fa-child'; }} 
            else if (typ === 'skola' && cat.includes('gymnasi')) {{ targetLayer = layerGymnasieskolor; markerColor = '#9b59b6'; iconClass = 'fa-graduation-cap'; }} 
            else if (cat.includes('handel') || cat.includes('centrum') || cat.includes('torg')) {{ targetLayer = layerHandel; markerColor = '#e67e22'; iconClass = 'fa-shopping-cart'; }} 
            else if (cat.includes('idrott') || cat.includes('fritid') || cat.includes('sport') || cat.includes('bad') || cat.includes('park') || cat.includes('anläggning')) {{ targetLayer = layerIdrott; markerColor = '#2ecc71'; iconClass = 'fa-futbol'; }} 
            else if (typ === 'vard' || cat.includes('samhälle') || cat.includes('infrastruktur') || cat.includes('sjukhus') || cat.includes('station') || cat.includes('förvaltning') || cat.includes('näringsliv')) {{ targetLayer = layerSamhalle; markerColor = '#34495e'; iconClass = 'fa-building'; }} 
            else if (cat.includes('kultur') || cat.includes('sevärdhet') || cat.includes('kyrka') || cat.includes('museum') || cat.includes('evenemang')) {{ targetLayer = layerKultur; markerColor = '#e74c3c'; iconClass = 'fa-theater-masks'; }} 
            
            var isSpecial = p.namn.toLowerCase().includes('stora torget') || p.namn.toLowerCase().includes('resecentrum');
            var extraClass = isSpecial ? ' marker-pulse' : ''; var activeIcon = isSpecial ? 'fa-star' : iconClass;
            
            var iconHtml = `<div class="custom-marker${{extraClass}}" style="background-color: ${{markerColor}}; width: 100%; height: 100%;"><i class="fas ${{activeIcon}}"></i></div>`;
            var marker = L.marker([p.lat, p.lon], {{ icon: L.divIcon({{ html: iconHtml, className: '', iconSize: isSpecial ? [36, 36] : [26, 26] }}) }}).bindTooltip(`<b>${{p.namn}}</b> (Klicka för analys)`, {{direction: 'top'}});
            
            marker.on('click', function() {{
                var t = estimateTravelTimes(p.lat, p.lon); var demoStats = getDemographicsInRadius(p.lat, p.lon, 1);
                var orgText = p.org && p.org !== 'nan' && p.org !== 'None' && p.org !== '' ? `<p style="margin-bottom: 5px; font-size:15px; color:#2c3e50;"><b>Huvudman:</b> ${{p.org}}</p>` : '';
                var poiHtml = `<h5 style="border-bottom:2px solid #333; padding-bottom:5px; margin-bottom:12px;"><b>${{p.namn}}</b></h5><p style="margin-bottom: 3px; font-size:15px;"><b>Typ:</b> ${{p.kategori}}</p>${{orgText}}<p style="margin-bottom: 3px; font-size:15px; margin-top:10px;"><b>Avstånd t. Stora torget:</b> 🚲 ${{t.st.bike}} km | 🚗 ${{t.st.car}} km <i>(${{t.st.dist}} km)</i></p><p style="margin-bottom: 15px; font-size:15px;"><b>Restid t. Resecentrum:</b><br>🚶 ${{t.rc.walk}} min | 🚲 ${{t.rc.bike}} min | 🚌 ${{t.rc.pt}} min | 🚗 ${{t.rc.car}} min</p><div style="background: #f8f9fa; padding: 12px; border-radius: 5px;">${{generateDemographicHtml("Demografi inom 1 km radie", demoStats)}}</div>`;
                showInfoPanel(poiHtml); map.flyTo([p.lat, p.lon], 15);
            }});
            marker.addTo(targetLayer);
        }});

        var highlightedPolygon = null;
        function clearHighlight() {{ if (highlightedPolygon) {{ highlightedPolygon.setStyle({{weight: 1, color: '#333333'}}); highlightedPolygon = null; }} }}

        var searchControl = new L.Control.Search({{ 
            layer: searchLayer, propertyName: 'name', marker: false, collapsed: false, textPlaceholder: 'Sök basområde...',
            moveToLocation: function(latlng, title, map) {{ 
                map.flyTo(latlng, 15); clearHighlight();
                map.eachLayer(function(layer) {{ if (layer.feature && layer.feature.properties && layer.feature.properties.NAMN === title) {{ if (layer.setStyle) {{ layer.setStyle({{weight: 5, color: '#f39c12'}}); highlightedPolygon = layer; }} }} }});
                centroidLayer.eachLayer(function(layer) {{ 
                    if (layer.feature && layer.feature.properties.name === title) {{ 
                        // Startar fönstret och bygger grafen via klick-eventet
                        layer.fire('click'); 
                    }} 
                }});
            }} 
        }});
        map.addControl(searchControl);

        document.getElementById('btn-reset').addEventListener('click', function() {{
            map.setView([58.4102, 15.6216], 11); clearHighlight(); searchControl.collapse(); document.getElementById('zoomSelect').value = ""; document.getElementById('zoomKaraktar1').value = ""; document.getElementById('zoomKaraktar2').value = "";
            updatePolygonVisibility(); 
            if(drawnItems) drawnItems.clearLayers(); customRadiusLayer.clearLayers(); document.getElementById('infoPanel').style.display = 'none'; lastZoomBounds = null; 
            document.getElementById('opacitySlider').value = 0.60; document.getElementById('opacityVal').innerText = '60%';
            document.querySelectorAll('.pop-polygon, .density-polygon, .hushall-polygon, .agan-polygon, .bost-polygon, .hyre-polygon, .default-polygon').forEach(el => {{ el.style.fillOpacity = 0.60; }});
            document.getElementById('togglePop').checked = true; document.getElementById('togglePop').dispatchEvent(new Event('change'));
            
            document.getElementById('toggleCentroids').checked = false; document.getElementById('toggleCentroids').dispatchEvent(new Event('change'));
            document.getElementById('toggleDynPop').checked = false; document.getElementById('toggleDynPop').dispatchEvent(new Event('change'));
            
            if(measureMode) document.getElementById('btn-measure').click(); if(isochroneMode) document.getElementById('btn-isochrone').click();
            ['toggleTransport', 'toggleVatten', 'toggleGrundskolor', 'toggleGymnasieskolor', 'toggleHandel', 'toggleIdrott', 'toggleSamhalle', 'toggleKultur', 'toggleOvriga'].forEach(function(id) {{ var cb = document.getElementById(id); if(cb && cb.checked) {{ cb.checked = false; cb.dispatchEvent(new Event('change')); }} }});
        }});
        
        document.getElementById('btnZoomPOI').addEventListener('click', function() {{
            var bounds = L.latLngBounds(); var hasPoints = false;
            var layersToCheck = [ {{id: 'toggleGrundskolor', layer: layerGrundskolor}}, {{id: 'toggleGymnasieskolor', layer: layerGymnasieskolor}}, {{id: 'toggleHandel', layer: layerHandel}}, {{id: 'toggleIdrott', layer: layerIdrott}}, {{id: 'toggleSamhalle', layer: layerSamhalle}}, {{id: 'toggleKultur', layer: layerKultur}}, {{id: 'toggleOvriga', layer: layerOvriga}}, {{id: 'toggleVard', layer: layerVard}} ];
            layersToCheck.forEach(function(item) {{ var cb = document.getElementById(item.id); if (cb && cb.checked && !cb.disabled) {{ item.layer.eachLayer(function(marker) {{ bounds.extend(marker.getLatLng()); hasPoints = true; }}); }} }});
            if(hasPoints) {{ map.flyToBounds(bounds, {{padding: [50, 50], maxZoom: 15}}); lastZoomBounds = bounds; }} 
            else {{ showInfoPanel("<div style='padding:10px; font-size:15px;'><b>Inga platser valda.</b><br>Kryssa i minst en POI-kategori i lagerlistan för att zooma in.</div>"); }}
        }});

        // --- KONTROLLERA LAGER TÄND/SLÄCK ---
        document.getElementById('toggleCentroids').addEventListener('change', function(e) {{ if(e.target.checked) map.addLayer(centroidLayer); else map.removeLayer(centroidLayer); }});
        document.getElementById('toggleCircles').addEventListener('change', function(e) {{ if(e.target.checked) map.addLayer(circleLayer); else map.removeLayer(circleLayer); }});
        document.getElementById('toggleTransport').addEventListener('change', function(e) {{ if(e.target.checked) map.addLayer(layerTransport); else map.removeLayer(layerTransport); }});
        document.getElementById('toggleVatten').addEventListener('change', function(e) {{ if(e.target.checked) map.addLayer(layerVatten); else map.removeLayer(layerVatten); }});
        document.getElementById('toggleGrundskolor').addEventListener('change', function(e) {{ if(e.target.checked) map.addLayer(layerGrundskolor); else map.removeLayer(layerGrundskolor); }});
        document.getElementById('toggleGymnasieskolor').addEventListener('change', function(e) {{ if(e.target.checked) map.addLayer(layerGymnasieskolor); else map.removeLayer(layerGymnasieskolor); }});
        document.getElementById('toggleHandel').addEventListener('change', function(e) {{ if(e.target.checked) map.addLayer(layerHandel); else map.removeLayer(layerHandel); }});
        document.getElementById('toggleIdrott').addEventListener('change', function(e) {{ if(e.target.checked) map.addLayer(layerIdrott); else map.removeLayer(layerIdrott); }});
        document.getElementById('toggleSamhalle').addEventListener('change', function(e) {{ if(e.target.checked) map.addLayer(layerSamhalle); else map.removeLayer(layerSamhalle); }});
        document.getElementById('toggleKultur').addEventListener('change', function(e) {{ if(e.target.checked) map.addLayer(layerKultur); else map.removeLayer(layerKultur); }});
        document.getElementById('toggleOvriga').addEventListener('change', function(e) {{ if(e.target.checked) map.addLayer(layerOvriga); else map.removeLayer(layerOvriga); }});

        // --- 4. VÄRMEKARTOR & DETALJERADE KLUSTER ---
        var currentHeatLayer = null;
        var clusterLayer = L.markerClusterGroup({{
            chunkedLoading: true, 
            iconCreateFunction: function(cluster) {{
                var markers = cluster.getAllChildMarkers(); var sum = 0;
                for (var i = 0; i < markers.length; i++) {{ sum += markers[i].options.population || 0; }}
                var c = ' marker-cluster-'; if (sum < 100) {{ c += 'small'; }} else if (sum < 1000) {{ c += 'medium'; }} else {{ c += 'large'; }}
                var displaySum = (sum > 0 && sum < 5) ? "< 5" : sum;
                return new L.DivIcon({{ html: '<div class="' + c + '"><span>' + displaySum + '</span></div>', className: 'marker-cluster cluster-custom', iconSize: new L.Point(40, 40) }});
            }}
        }});

        // Klustren renderas nu direkt utan fetch-beroenden!
        var markersToAdd = [];
        heatDataRaw.forEach(function(p) {{
            var pop = p.tot;
            if (pop > 0) {{
                var displayPop = (pop < 5) ? "< 5" : pop;
                var markerIcon = L.divIcon({{ html: `<div style="background-color: #3498db; color: white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 11px; border: 1px solid #fff; opacity: 0.9;">${{displayPop}}</div>`, className: '', iconSize: [24, 24] }});
                var marker = L.marker([p.lat, p.lon], {{ icon: markerIcon, population: pop }});
                marker.on('click', function() {{
                    showInfoPanel(generateDemographicHtml("Befolkning på platsen", p)); 
                    map.flyTo([p.lat, p.lon], 16);
                }});
                markersToAdd.push(marker);
            }}
        }});
        clusterLayer.addLayers(markersToAdd);

        document.getElementById('heatSelect').addEventListener('change', function(e) {{
            if (currentHeatLayer) map.removeLayer(currentHeatLayer);
            var val = e.target.value;
            if (val === 'none' || heatDataRaw.length === 0) return;
            var heatPoints = heatDataRaw.map(p => [p.lat, p.lon, p[val]]).filter(p => p[2] > 0);
            var maxVal = 10;
            if (heatPoints.length > 0) {{ var values = heatPoints.map(p => p[2]).sort((a,b) => a - b); maxVal = values[Math.floor(values.length * 0.98)] || 10; }}
            maxVal = Math.max(3, maxVal); 
            currentHeatLayer = L.heatLayer(heatPoints, {{ radius: 15, blur: 20, maxZoom: 14, max: maxVal }}).addTo(map);
        }});

        document.getElementById('toggleClusters').addEventListener('change', function(e) {{ if(e.target.checked) map.addLayer(clusterLayer); else map.removeLayer(clusterLayer); }});

        // --- 5. NY DYNAMISK BEFOLKNING (BYTER ÖVER ZOOM-NIVÅER MED SNAPPAD TYNGDPUNKT) ---
        function buildDynLayer(data, color, levelName) {{
            var layer = L.featureGroup();
            data.forEach(function(d) {{
                var isSecret = d.Totalt > 0 && d.Totalt < 5;
                var displayPop = isSecret ? "< 5" : d.Totalt;
                var size = Math.max(30, Math.min(70, 15 + Math.sqrt(d.Totalt)*0.8));
                var html = `<div style="background-color: ${{color}}; color: white; border-radius: 50%; width: ${{size}}px; height: ${{size}}px; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight:bold; border: 2px solid #fff; opacity: 0.9; box-shadow: 0 2px 5px rgba(0,0,0,0.5);">${{displayPop}}</div>`;
                var markerIcon = L.divIcon({{ html: html, className: '', iconSize: [size, size], iconAnchor: [size/2, size/2] }});
                var marker = L.marker([d.lat, d.lon], {{ icon: markerIcon, pane: 'circlePane' }});
                
                var stats = {{
                    tot: d.Totalt, a0_5: d.Grp_0_5, a6_15: d.Grp_6_15, a6_9: d.Grp_6_9, 
                    a10_12: d.Grp_10_12, a13_15: d.Grp_13_15, a16_18: d.Grp_16_18, 
                    a19_64: d.Grp_19_64, a65_79: d.Grp_65_79, a80: d.Grp_80plus
                }};
                
                marker.bindTooltip("<b>" + levelName + " (" + d.kod + ")</b><br>" + (isSecret ? "Sekretesskyddad" : "Klicka för demografi"), {{direction: 'top'}});

                marker.on('click', function() {{
                    showInfoPanel(generateDemographicHtml("Demografi " + levelName + " (" + d.kod + ")", stats)); 
                    map.flyTo([d.lat, d.lon], map.getZoom() + 1);
                }});
                marker.addTo(layer);
            }});
            return layer;
        }}

        var layerDyn1 = buildDynLayer(dynPop1, '#2980b9', 'Nyko 1 (Kommundel)'); // Blå
        var layerDyn3 = buildDynLayer(dynPop3, '#8e44ad', 'Nyko 3 (Stadsdel)'); // Lila
        var layerDyn4 = buildDynLayer(dynPop4, '#e67e22', 'Nyko 4 (Basområde)'); // Orange
        var layerDyn6 = buildDynLayer(dynPop6, '#c0392b', 'Nyko 6 (Kvarter)'); // Röd

        function updateDynPopLayer() {{
            var lbl = document.getElementById('dynPopLabel');
            if (!document.getElementById('toggleDynPop').checked) {{
                map.removeLayer(layerDyn1); map.removeLayer(layerDyn3); map.removeLayer(layerDyn4); map.removeLayer(layerDyn6);
                lbl.style.display = 'none';
                return;
            }}
            
            lbl.style.display = 'inline-block';
            var z = map.getZoom();
            map.removeLayer(layerDyn1); map.removeLayer(layerDyn3); map.removeLayer(layerDyn4); map.removeLayer(layerDyn6);
            
            if (z <= 11) {{
                map.addLayer(layerDyn1);
                lbl.innerText = "Kommundel (Nyko 1)"; lbl.style.backgroundColor = "#2980b9";
            }} else if (z === 12) {{
                map.addLayer(layerDyn3);
                lbl.innerText = "Stadsdel (Nyko 3)"; lbl.style.backgroundColor = "#8e44ad";
            }} else if (z === 13 || z === 14) {{
                map.addLayer(layerDyn4);
                lbl.innerText = "Basområde (Nyko 4)"; lbl.style.backgroundColor = "#e67e22";
            }} else if (z >= 15) {{
                map.addLayer(layerDyn6);
                lbl.innerText = "Kvarter (Nyko 6)"; lbl.style.backgroundColor = "#c0392b";
            }}
        }}
        
        map.on('zoomend', updateDynPopLayer);
        document.getElementById('toggleDynPop').addEventListener('change', updateDynPopLayer);

        // --- 6. RITVERKTYG (AVANCERADE) ---
        var isDrawingMode = false; var measureMode = false; var isochroneMode = false;
        
        var drawnItems = new L.FeatureGroup(); map.addLayer(drawnItems);
        L.drawLocal.draw.toolbar.actions.title = 'Avbryt ritning'; L.drawLocal.draw.toolbar.actions.text = 'Avbryt'; L.drawLocal.draw.toolbar.finish.title = 'Slutför ritning'; L.drawLocal.draw.toolbar.finish.text = 'Slutför'; L.drawLocal.draw.toolbar.undo.title = 'Ångra sista punkten'; L.drawLocal.draw.toolbar.undo.text = 'Ångra'; L.drawLocal.draw.handlers.polygon.tooltip.start = 'Klicka för att börja rita en yta.'; L.drawLocal.draw.handlers.polygon.tooltip.cont = 'Klicka för att fortsätta rita ytan.'; L.drawLocal.draw.handlers.polygon.tooltip.end = 'Klicka på första punkten för att slutföra.'; L.drawLocal.draw.handlers.rectangle.tooltip.start = 'Klicka och dra för att rita en rektangel.';
        var drawControl = new L.Control.Draw({{ draw: {{ polyline: false, marker: false, circlemarker: false, circle: false, polygon: {{ shapeOptions: {{ color: '#9b59b6', weight: 2, fillOpacity: 0.3 }} }}, rectangle: {{ shapeOptions: {{ color: '#9b59b6', weight: 2, fillOpacity: 0.3 }} }} }}, edit: {{ featureGroup: drawnItems }} }});
        map.addControl(drawControl);

        map.on('draw:drawstart', function (e) {{ isDrawingMode = true; }});
        map.on('draw:drawstop', function (e) {{ isDrawingMode = false; }});

        map.on(L.Draw.Event.CREATED, function (e) {{
            var layer = e.layer; drawnItems.addLayer(layer); var polyGeoJson = layer.toGeoJSON();
            var stats = {{ tot: 0, a0_5: 0, a6_15: 0, a6_9: 0, a10_12: 0, a13_15: 0, a16_18: 0, a19_64: 0, a65_79: 0, a80: 0 }};
            if (heatDataRaw && heatDataRaw.length > 0) {{
                heatDataRaw.forEach(function(p) {{
                    var pt = turf.point([p.lon, p.lat]); 
                    if (turf.booleanPointInPolygon(pt, polyGeoJson)) {{
                        stats.tot += p.tot; stats.a0_5 += p.a0_5; stats.a6_15 += p.a6_15; stats.a6_9 += p.a6_9; stats.a10_12 += p.a10_12; stats.a13_15 += p.a13_15;
                        stats.a16_18 += p.a16_18; stats.a19_64 += p.a19_64; stats.a65_79 += p.a65_79; stats.a80 += p.a80;
                    }}
                }});
            }}
            layer.on('click', function() {{ showInfoPanel(generateDemographicHtml("Egenritad Yta", stats)); }});
            layer.fire('click'); 
        }});

        // --- 7. NÅBARHETSANALYS (ISOKRONER) & AVSTÅNDSMÄTARE ---
        document.getElementById('btn-measure').addEventListener('click', function() {{
            measureMode = !measureMode; isochroneMode = false; document.getElementById('btn-isochrone').classList.replace('btn-info', 'btn-outline-info');
            if(measureMode) {{ this.classList.replace('btn-outline-primary', 'btn-primary'); document.getElementById(map._container.id).style.cursor = 'crosshair'; }} else {{ this.classList.replace('btn-primary', 'btn-outline-primary'); document.getElementById(map._container.id).style.cursor = ''; }}
        }});

        document.getElementById('btn-isochrone').addEventListener('click', function() {{
            isochroneMode = !isochroneMode; measureMode = false; document.getElementById('btn-measure').classList.replace('btn-primary', 'btn-outline-primary');
            if(isochroneMode) {{ this.classList.replace('btn-outline-info', 'btn-info'); document.getElementById(map._container.id).style.cursor = 'crosshair'; }} else {{ this.classList.replace('btn-info', 'btn-outline-info'); document.getElementById(map._container.id).style.cursor = ''; }}
        }});
        
        map.on('click', function(e) {{
            if(measureMode) {{
                var dist = getDistance(58.4102, 15.6216, e.latlng.lat, e.latlng.lng).toFixed(2);
                L.popup().setLatLng(e.latlng).setContent(`<div style="font-size:14px; padding:5px;">Fågelvägen till Stora Torget: <b>${{dist}} km</b></div>`).openOn(map);
                return; 
            }}
            if(isochroneMode) {{
                customRadiusLayer.clearLayers(); 
                var lat = e.latlng.lat; var lon = e.latlng.lng;
                
                // --- JUSTERAD FÖR 10 MINUTER ---
                var rWalk = 0.83; // 5 km/h * 10 min
                var rBike = 2.5;  // 15 km/h * 10 min
                var rCar = 6.5;   // Blandad stadstrafik ~39 km/h * 10 min
                
                var carLayer = L.circle([lat, lon], {{radius: rCar*1000, color: '#e74c3c', weight: 1, fillOpacity: 0.1}}).addTo(customRadiusLayer);
                var bikeLayer = L.circle([lat, lon], {{radius: rBike*1000, color: '#f39c12', weight: 1, fillOpacity: 0.15}}).addTo(customRadiusLayer);
                var walkLayer = L.circle([lat, lon], {{radius: rWalk*1000, color: '#2ecc71', weight: 2, fillOpacity: 0.3}}).addTo(customRadiusLayer);
                
                var statsWalk = getDemographicsInRadius(lat, lon, rWalk);
                var statsBike = getDemographicsInRadius(lat, lon, rBike);
                var statsCar = getDemographicsInRadius(lat, lon, rCar);
                
                function sStat(v) {{ return (v > 0 && v < 5) ? '< 5' : v; }}
                
                var isoHtml = `
                    <h5 style="border-bottom:2px solid #333; padding-bottom:5px; margin-bottom:12px;"><b>Nåbarhet (10 minuter)</b></h5>
                    <p style="font-size:14px; margin-bottom:10px;">Antal invånare som når denna punkt på tio minuter:</p>
                    <table class="popup-table" style="margin-bottom:15px; font-size:15px;">
                        <tr><td style="padding-bottom:5px;">🚶 <b>Gång</b> (~0.8 km):</td><td style="text-align:right"><b>${{sStat(statsWalk.tot)}}</b></td></tr>
                        <tr><td style="padding-bottom:5px;">🚲 <b>Cykel</b> (~2.5 km):</td><td style="text-align:right"><b>${{sStat(statsBike.tot)}}</b></td></tr>
                        <tr><td style="padding-bottom:5px;">🚗 <b>Bil/Buss</b> (~6.5 km):</td><td style="text-align:right"><b>${{sStat(statsCar.tot)}}</b></td></tr>
                    </table>
                    <hr style="margin: 10px 0;">
                    <p style="font-size:13px; color:#666; margin-bottom:10px;">Nedan visas detaljerad demografi för cykelavståndet.</p>
                    <div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">
                        ${{generateDemographicHtml("Demografi (10 min Cykel)", statsBike)}}
                    </div>
                `;
                
                walkLayer.on('click', function() {{ showInfoPanel(isoHtml); }});
                bikeLayer.on('click', function() {{ showInfoPanel(isoHtml); }});
                carLayer.on('click', function() {{ showInfoPanel(isoHtml); }});
                
                showInfoPanel(isoHtml); map.flyTo([lat, lon], 13); return; 
            }}
        }});

        // --- 8. INTERAKTIV GRAF (Chart.js) VID KLICK ---
        var histData = {hist_json_str}; var myChart = null; var chartModal = new bootstrap.Modal(document.getElementById('chartModal'));

        function openChart(namn) {{
            if(!histData[namn] || histData[namn].labels.length === 0) return;
            document.getElementById('chartModalLabel').innerText = 'Befolkningsutveckling: ' + namn;
            if(myChart) myChart.destroy(); var ctx = document.getElementById('popChart').getContext('2d');
            myChart = new Chart(ctx, {{ type: 'line', data: {{ labels: histData[namn].labels, datasets: [{{ label: 'Folkmängd', data: histData[namn].data, borderColor: '#2ecc71', backgroundColor: 'rgba(46, 204, 113, 0.2)', borderWidth: 2, fill: true, tension: 0.3, pointRadius: 3 }}] }}, options: {{ responsive: true, scales: {{ y: {{ beginAtZero: false }} }} }} }});
            chartModal.show();
        }}

        function bindGraphClicks() {{
            var found = false;
            map.eachLayer(function(layer) {{
                if (layer.feature && layer.feature.properties && layer.feature.properties.NAMN) {{
                    layer.off('click'); 
                    layer.on('click', function(e) {{
                        if (measureMode || isochroneMode) return; 
                        if (!document.getElementById('toggleGraph').checked) return; 
                        openChart(layer.feature.properties.NAMN); L.DomEvent.stopPropagation(e);
                    }});
                    found = true;
                }}
            }});
            if (!found) setTimeout(bindGraphClicks, 500); 
        }}
        bindGraphClicks();

        // --- 9. HOVER-EFFEKT FÖR POLYGONER (RÖD RAM) ---
        function bindPolygonHover() {{
            map.eachLayer(function(layer) {{
                if (layer.feature && layer.feature.properties && layer.feature.properties.NAMN) {{
                    if (layer.options && layer.options.className && layer.options.className.includes('-polygon')) {{
                        if (!layer.defaultStyle) {{
                            layer.defaultStyle = {{
                                weight: layer.options.weight,
                                color: layer.options.color,
                                fillOpacity: layer.options.fillOpacity
                            }};
                        }}
                        layer.off('mouseover').on('mouseover', function(e) {{
                            if (isDrawingMode || measureMode || isochroneMode) return; 
                            var currentOpacity = document.getElementById('opacitySlider').value;
                            this.setStyle({{ weight: 4, color: '#ff0000', fillOpacity: Math.min(1.0, parseFloat(currentOpacity) + 0.2) }});
                            if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {{ this.bringToFront(); }}
                        }});
                        layer.off('mouseout').on('mouseout', function(e) {{
                            var currentOpacity = document.getElementById('opacitySlider').value;
                            var isBorder = this.options.className.includes('border-polygon');
                            this.setStyle({{ 
                                weight: layer.defaultStyle.weight, 
                                color: layer.defaultStyle.color,
                                fillOpacity: isBorder ? 0 : currentOpacity
                            }});
                        }});
                    }}
                }}
            }});
        }}
        // Initiera hover-effekter en kort stund efter att kartan renderats
        setTimeout(bindPolygonHover, 1000);
    }});
</script>
"""

m.get_root().html.add_child(folium.Element(ui_html))
html_out_path = os.path.join(moder_mapp, OUT_HTML_NAME)
m.save(html_out_path)
print(f"\nKlar! Din 2D-karta över basområden (Nyko 4) är sparad och redo:\n{html_out_path}")