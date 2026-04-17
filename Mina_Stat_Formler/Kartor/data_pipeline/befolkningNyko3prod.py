import os
import sys
import pandas as pd
import geopandas as gpd
import folium
import branca.colormap as cm
import json
import math

# =====================================================================
# 1. GENERELL SETUP, GYLLENE REGLER & MAPPSTRUKTUR
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
# Välj vilket år filen med koordinatsatt befolkning avser.
PUNKT_DATA_AR = "2025"

print("Läser in och processar data...")

excel_path = os.path.join(excel_filer_dir, 'befolkning_och_platser.xlsx')
if not os.path.exists(excel_path):
    print(f"\nFEL: Hittar inte {excel_path}.")
    sys.exit(1)

geojson_path = os.path.join(kart_filer_dir, 'NYKO3v23.geojson')
nyko3 = gpd.read_file(geojson_path)
nyko3['NAMN'] = nyko3['NAMN'].apply(fix_text)

nyko3_3006 = nyko3.to_crs(epsg=3006)
nyko3['Area_km2'] = nyko3_3006.geometry.area / 1_000_000
nyko3_3006_centroids = nyko3_3006.geometry.centroid

# --- Läs in Historisk Folkmängd ---
print("Hämtar historisk folkmängd från fliken 'Folkmängd'...")
try:
    hist_df = pd.read_excel(excel_path, sheet_name='Folkmängd')
    hist_df.columns = hist_df.columns.astype(str).str.strip() 
    hist_df['Namn'] = hist_df['Namn'].apply(fix_text)
except Exception as e:
    print(f"FEL vid inläsning av fliken 'Folkmängd': {e}")
    sys.exit(1)

years = [str(y) for y in range(1970, 2030)]
existing_years = [y for y in years if y in hist_df.columns]
latest_year = existing_years[-1] if existing_years else '2025'
prev_year = existing_years[-2] if len(existing_years) > 1 else latest_year

for y in existing_years:
    hist_df[y] = pd.to_numeric(hist_df[y].astype(str).str.replace('..', '', regex=False), errors='coerce')

nyko3 = nyko3.merge(hist_df[['Namn'] + existing_years], left_on='NAMN', right_on='Namn', how='left')
nyko3['Folkmängd'] = nyko3[latest_year].fillna(0).astype(int)
nyko3['Folkmängd_prev'] = nyko3[prev_year].fillna(0).astype(int)
nyko3['Pop_Change'] = nyko3['Folkmängd'] - nyko3['Folkmängd_prev']

nyko3['Area_km2'] = nyko3['Area_km2'].replace(0, 0.001).round(2)
nyko3['Inv_per_km2'] = (nyko3['Folkmängd'] / nyko3['Area_km2']).round(1)
nyko3['Inv_per_km2'] = nyko3['Inv_per_km2'].fillna(0)

# Förbered historisk data för Grafen (INKLUSIVE SEKRETESS-MASKERING < 5)
hist_json_data = {}
for idx, row in nyko3.iterrows():
    namn = row['NAMN']
    data = []
    labels = []
    for y in existing_years:
        val = row[y]
        if pd.notna(val):
            labels.append(y)
            # Sekretessmaskering för linjegrafen
            if 0 < int(val) < 5:
                data.append(None) # Skapar en lucka i grafen
            else:
                data.append(int(val))
    hist_json_data[namn] = {'labels': labels, 'data': data}
hist_json_str = json.dumps(hist_json_data)


# --- Läs in Hushållsstorlek ---
print("Hämtar data för Hushållsstorlek...")
try:
    hushall_df = pd.read_excel(excel_path, sheet_name='Hushållsstorlek')
    hushall_df.columns = hushall_df.columns.astype(str).str.strip()
    hushall_df['Namn'] = hushall_df['Namn'].apply(fix_text)
    
    hushall_col = PUNKT_DATA_AR if PUNKT_DATA_AR in hushall_df.columns else [c for c in hushall_df.columns if c != 'Namn'][-1]
    hushall_df[hushall_col] = hushall_df[hushall_col].astype(str).str.replace(',', '.').str.replace('..', '', regex=False)
    hushall_df['Hushallsstorlek_tmp'] = pd.to_numeric(hushall_df[hushall_col], errors='coerce')
    
    nyko3 = nyko3.merge(hushall_df[['Namn', 'Hushallsstorlek_tmp']], left_on='NAMN', right_on='Namn', how='left')
    nyko3['Hushallsstorlek'] = nyko3['Hushallsstorlek_tmp'].fillna(0).astype(float).round(2)
except Exception as e:
    print(f"INFO: Kunde inte ladda fliken 'Hushållsstorlek' ({e}).")
    nyko3['Hushallsstorlek'] = 0.0

# --- Läs in Upplåtelseformer ---
print("Hämtar data för Upplåtelseformer...")
try:
    uppl_df = pd.read_excel(excel_path, sheet_name='Upplåtelseformer')
    uppl_df.columns = uppl_df.columns.astype(str).str.strip()
    uppl_df['Namn'] = uppl_df['Namn'].apply(fix_text)
    
    if 'Totalt' in uppl_df.columns:
        uppl_df.rename(columns={'Totalt': 'Totalt_uppl'}, inplace=True)
    else:
        uppl_df['Totalt_uppl'] = uppl_df[['Äganderätt', 'Bostadsrätt', 'Hyresrätt']].sum(axis=1)

    for col in ['Totalt_uppl', 'Äganderätt', 'Bostadsrätt', 'Hyresrätt']:
        if col in uppl_df.columns:
            uppl_df[col] = pd.to_numeric(uppl_df[col], errors='coerce').fillna(0)

    # Beräkna Uppgift_saknas och maxa på 0 så det inte blir minus
    uppl_df['Uppgift_saknas'] = uppl_df['Totalt_uppl'] - (uppl_df['Äganderätt'] + uppl_df['Bostadsrätt'] + uppl_df['Hyresrätt'])
    uppl_df['Uppgift_saknas'] = uppl_df['Uppgift_saknas'].apply(lambda x: max(0, x))

    # Beräkna procentandelar
    uppl_df['Andel_Aganderatt'] = uppl_df.apply(lambda r: round((r['Äganderätt'] / r['Totalt_uppl'] * 100), 1) if r['Totalt_uppl'] > 0 else 0.0, axis=1)
    uppl_df['Andel_Bostadsratt'] = uppl_df.apply(lambda r: round((r['Bostadsrätt'] / r['Totalt_uppl'] * 100), 1) if r['Totalt_uppl'] > 0 else 0.0, axis=1)
    uppl_df['Andel_Hyresratt'] = uppl_df.apply(lambda r: round((r['Hyresrätt'] / r['Totalt_uppl'] * 100), 1) if r['Totalt_uppl'] > 0 else 0.0, axis=1)

    nyko3 = nyko3.merge(uppl_df[['Namn', 'Totalt_uppl', 'Äganderätt', 'Bostadsrätt', 'Hyresrätt', 'Uppgift_saknas', 'Andel_Aganderatt', 'Andel_Bostadsratt', 'Andel_Hyresratt']], left_on='NAMN', right_on='Namn', how='left')
    
    # Fillna för säkerhets skull
    for col in ['Totalt_uppl', 'Äganderätt', 'Bostadsrätt', 'Hyresrätt', 'Uppgift_saknas', 'Andel_Aganderatt', 'Andel_Bostadsratt', 'Andel_Hyresratt']:
        nyko3[col] = nyko3[col].fillna(0)

except Exception as e:
    print(f"INFO: Kunde inte ladda fliken 'Upplåtelseformer' ({e}).")
    for col in ['Totalt_uppl', 'Äganderätt', 'Bostadsrätt', 'Hyresrätt', 'Uppgift_saknas', 'Andel_Aganderatt', 'Andel_Bostadsratt', 'Andel_Hyresratt']:
        nyko3[col] = 0.0


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

# Hantera NYKO-koder för dynamisk aggregering (Nivå 1, 3, 4 och 6)
pop_df['NYKO_str'] = pop_df['NYKO6'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(6)
pop_df['NYKO1'] = pop_df['NYKO_str'].str[:1]
pop_df['NYKO3'] = pop_df['NYKO_str'].str[:3]
pop_df['NYKO4'] = pop_df['NYKO_str'].str[:4]
pop_df['NYKO6_kod'] = pop_df['NYKO_str']

# För över till Nyko3 (Koroplet)
pop_df['NYKO3_kod'] = pop_df['NYKO3'].astype(float)
pop_df['Grp_0_5'] = pop_df.get('0-1_år', 0) + pop_df.get('2-3_år', 0) + pop_df.get('4-5_år', 0)
pop_df['Grp_6_15'] = pop_df.get('6_år', 0) + pop_df.get('7-9_år', 0) + pop_df.get('10-12_år', 0) + pop_df.get('13-15_år', 0)
pop_df['Grp_6_9'] = pop_df.get('6_år', 0) + pop_df.get('7-9_år', 0)
pop_df['Grp_10_12'] = pop_df.get('10-12_år', 0)
pop_df['Grp_13_15'] = pop_df.get('13-15_år', 0)
pop_df['Grp_16_18'] = pop_df.get('16-18_år', 0)
pop_df['Grp_19_64'] = pop_df.get('19-24_år', 0) + pop_df.get('25-34_år', 0) + pop_df.get('35-44_år', 0) + pop_df.get('45-54_år', 0) + pop_df.get('55-64_år', 0)
pop_df['Grp_65_79'] = pop_df.get('65-69_år', 0) + pop_df.get('70-79_år', 0)
pop_df['Grp_80plus'] = pop_df.get('80+_år', 0)

pop_nyko3 = pop_df.groupby('NYKO3_kod')[['Totalt', 'Grp_0_5', 'Grp_6_15', 'Grp_6_9', 'Grp_10_12', 'Grp_13_15', 'Grp_16_18', 'Grp_19_64', 'Grp_65_79', 'Grp_80plus']].sum().reset_index()

nyko3 = nyko3.merge(pop_nyko3, left_on='NYKO', right_on='NYKO3_kod', how='left')
fill_cols = ['Totalt', 'Grp_0_5', 'Grp_6_15', 'Grp_6_9', 'Grp_10_12', 'Grp_13_15', 'Grp_16_18', 'Grp_19_64', 'Grp_65_79', 'Grp_80plus']
for col in fill_cols:
    if col in nyko3.columns:
        nyko3[col] = nyko3[col].fillna(0)

print("Beräknar koordinater för detaljerad data...")
pts = gpd.GeoDataFrame(pop_df, geometry=gpd.points_from_xy(pop_df['Y_koordinat'], pop_df['X_koordinat']), crs=3006)
pts_wgs84 = pts.to_crs(4326)

# Lagra lat/lon i dataframe för snabb åtkomst
pop_df['lat'] = pts_wgs84.geometry.y
pop_df['lon'] = pts_wgs84.geometry.x

# Skapa rådata för Heatmap och Kluster
heat_data = []
for idx, row in pop_df.iterrows():
    if row['Totalt'] > 0:
        heat_data.append({
            'lat': round(row['lat'], 5), 'lon': round(row['lon'], 5),
            'tot': int(row['Totalt']), 'a0_5': int(row['Grp_0_5']), 'a6_15': int(row['Grp_6_15']),
            'a6_9': int(row['Grp_6_9']), 'a10_12': int(row['Grp_10_12']), 'a13_15': int(row['Grp_13_15']),
            'a16_18': int(row['Grp_16_18']), 'a19_64': int(row['Grp_19_64']), 
            'a65_79': int(row['Grp_65_79']), 'a80': int(row['Grp_80plus'])
        })

# --- SKAPA DYNAMISKA BEFOLKNINGS-NIVÅER ---
print("Aggregerar dynamiska zoom-nivåer (Nyko 1, 3, 4, 6)...")
def aggregate_dyn_pop(level_col):
    agg_data = []
    for kod, group in pop_df.groupby(level_col):
        tot = int(group['Totalt'].sum())
        if tot == 0: continue
        
        w_lat = (group['lat'] * group['Totalt']).sum() / tot if tot > 0 else group['lat'].mean()
        w_lon = (group['lon'] * group['Totalt']).sum() / tot if tot > 0 else group['lon'].mean()
        
        distances = ((group['lat'] - w_lat)**2 + (group['lon'] - w_lon)**2)
        closest_idx = distances.idxmin()
        lat_val = group.loc[closest_idx, 'lat']
        lon_val = group.loc[closest_idx, 'lon']
        
        agg_data.append({
            'kod': str(kod),
            'lat': round(lat_val, 5),
            'lon': round(lon_val, 5),
            'Totalt': tot,
            'Grp_0_5': int(group['Grp_0_5'].sum()),
            'Grp_6_15': int(group['Grp_6_15'].sum()),
            'Grp_6_9': int(group['Grp_6_9'].sum()),
            'Grp_10_12': int(group['Grp_10_12'].sum()),
            'Grp_13_15': int(group['Grp_13_15'].sum()),
            'Grp_16_18': int(group['Grp_16_18'].sum()),
            'Grp_19_64': int(group['Grp_19_64'].sum()),
            'Grp_65_79': int(group['Grp_65_79'].sum()),
            'Grp_80plus': int(group['Grp_80plus'].sum())
        })
    return agg_data

dyn_pop1_str = json.dumps(aggregate_dyn_pop('NYKO1'))
dyn_pop3_str = json.dumps(aggregate_dyn_pop('NYKO3'))
dyn_pop4_str = json.dumps(aggregate_dyn_pop('NYKO4'))
dyn_pop6_str = json.dumps(aggregate_dyn_pop('NYKO6_kod'))


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
centroids_wgs84 = nyko3_3006_centroids.to_crs(epsg=4326)
nyko_data = []
for idx, row in nyko3.iterrows():
    point = centroids_wgs84.iloc[idx]
    if not point.is_empty:
        nyko_data.append({
            'namn': row['NAMN'], 'lat': point.y, 'lon': point.x, 'area': row['Area_km2'],
            'tot': int(row['Folkmängd']), 'pop_change': int(row['Pop_Change']),
            'hushall': float(row.get('Hushallsstorlek', 0)),
            
            # Upplåtelseform exporteras
            'tot_uppl': int(row.get('Totalt_uppl', 0)),
            'agan': int(row.get('Äganderätt', 0)),
            'bost': int(row.get('Bostadsrätt', 0)),
            'hyre': int(row.get('Hyresrätt', 0)),
            'saknas': int(row.get('Uppgift_saknas', 0)),

            'a0_5': int(row['Grp_0_5']), 'a6_15': int(row['Grp_6_15']), 'a6_9': int(row['Grp_6_9']),
            'a10_12': int(row['Grp_10_12']), 'a13_15': int(row['Grp_13_15']), 'a16_18': int(row['Grp_16_18']),
            'a19_64': int(row['Grp_19_64']), 'a65_79': int(row['Grp_65_79']), 'a80': int(row['Grp_80plus'])
        })

with open(os.path.join(moder_mapp, 'nyko_data.json'), 'w', encoding='utf-8') as f: json.dump(nyko_data, f, ensure_ascii=False)
with open(os.path.join(moder_mapp, 'poi_data.json'), 'w', encoding='utf-8') as f: json.dump(poi_data, f, ensure_ascii=False)
with open(os.path.join(moder_mapp, 'heat_data.json'), 'w', encoding='utf-8') as f: json.dump(heat_data, f, ensure_ascii=False)

nyko_json_str = json.dumps(nyko_data)
poi_json_str = json.dumps(poi_data)

# =====================================================================
# 4. KARTBYGGE (HTML/JS Visualisering med Folium)
# =====================================================================
print("Genererar karta...")
m = folium.Map(location=[58.4102, 15.6216], zoom_start=11, tiles=None)

viridis_rev = ['#fde725', '#b5de2b', '#6ece58', '#35b779', '#1f9e89', '#26828e', '#31688e', '#3e4989', '#482878', '#440154']

# --- LAGER 1: Befolkning (Koroplet) ---
max_pop = nyko3['Folkmängd'].max()
colormap_pop = cm.LinearColormap(colors=viridis_rev, vmin=0, vmax=max_pop)
folium.GeoJson(
    nyko3,
    name=f'Befolkning {latest_year}',
    style_function=lambda feature: {
        'fillColor': colormap_pop(feature['properties']['Folkmängd']),
        'color': '#333333', 'weight': 1, 'fillOpacity': 0.60, 'className': 'polygon-layer pop-polygon'
    },
    tooltip=folium.GeoJsonTooltip(fields=['NAMN', 'Folkmängd', 'Area_km2', 'Inv_per_km2'], aliases=['Område:', f'Folkmängd ({latest_year}):', 'Yta (km²):', 'Invånare/km²:'], localize=True)
).add_to(m)

# --- LAGER 2: Befolkningstäthet (Koroplet) ---
max_dens = nyko3['Inv_per_km2'].max()
colormap_dens = cm.LinearColormap(colors=viridis_rev, vmin=0, vmax=max_dens)
folium.GeoJson(
    nyko3,
    name='Befolkningstäthet',
    style_function=lambda feature: {
        'fillColor': colormap_dens(feature['properties']['Inv_per_km2']),
        'color': '#333333', 'weight': 1, 'fillOpacity': 0.60, 'className': 'polygon-layer density-polygon'
    },
    tooltip=folium.GeoJsonTooltip(fields=['NAMN', 'Folkmängd', 'Area_km2', 'Inv_per_km2'], aliases=['Område:', f'Folkmängd ({latest_year}):', 'Yta (km²):', 'Invånare/km²:'], localize=True)
).add_to(m)

# --- LAGER 3: Hushållsstorlek (Koroplet) ---
valid_hushall = nyko3[nyko3['Hushallsstorlek'] > 0]['Hushallsstorlek']
min_hushall = max(0, (valid_hushall.min() if not valid_hushall.empty else 0) - 0.2)
max_hushall = (valid_hushall.max() if not valid_hushall.empty else 1) + 0.2

colormap_hushall = cm.LinearColormap(colors=viridis_rev, vmin=min_hushall, vmax=max_hushall)
folium.GeoJson(
    nyko3,
    name='Hushållsstorlek',
    style_function=lambda feature: {
        'fillColor': colormap_hushall(feature['properties']['Hushallsstorlek']) if feature['properties']['Hushallsstorlek'] > 0 else 'transparent',
        'color': '#333333', 'weight': 1, 'fillOpacity': 0.60, 'className': 'polygon-layer hushall-polygon'
    },
    tooltip=folium.GeoJsonTooltip(fields=['NAMN', 'Folkmängd', 'Hushallsstorlek'], aliases=['Område:', f'Folkmängd ({latest_year}):', 'Snitt hushållsstorlek:'], localize=True)
).add_to(m)

# --- LAGER 4-6: UPPÅTELSEFORMER (Koroplet) ---
colormap_pct = cm.LinearColormap(colors=viridis_rev, vmin=0, vmax=100)

# 4. Äganderätt
folium.GeoJson(
    nyko3, name='Äganderätt',
    style_function=lambda feature: {
        'fillColor': colormap_pct(feature['properties']['Andel_Aganderatt']) if feature['properties']['Totalt_uppl'] > 0 else 'transparent',
        'color': '#333333', 'weight': 1, 'fillOpacity': 0.60, 'className': 'polygon-layer agan-polygon'
    },
    tooltip=folium.GeoJsonTooltip(fields=['NAMN', 'Andel_Aganderatt', 'Totalt_uppl'], aliases=['Område:', 'Äganderätt (%):', 'Totalt antal bostäder:'], localize=True)
).add_to(m)

# 5. Bostadsrätt
folium.GeoJson(
    nyko3, name='Bostadsrätt',
    style_function=lambda feature: {
        'fillColor': colormap_pct(feature['properties']['Andel_Bostadsratt']) if feature['properties']['Totalt_uppl'] > 0 else 'transparent',
        'color': '#333333', 'weight': 1, 'fillOpacity': 0.60, 'className': 'polygon-layer bost-polygon'
    },
    tooltip=folium.GeoJsonTooltip(fields=['NAMN', 'Andel_Bostadsratt', 'Totalt_uppl'], aliases=['Område:', 'Bostadsrätt (%):', 'Totalt antal bostäder:'], localize=True)
).add_to(m)

# 6. Hyresrätt
folium.GeoJson(
    nyko3, name='Hyresrätt',
    style_function=lambda feature: {
        'fillColor': colormap_pct(feature['properties']['Andel_Hyresratt']) if feature['properties']['Totalt_uppl'] > 0 else 'transparent',
        'color': '#333333', 'weight': 1, 'fillOpacity': 0.60, 'className': 'polygon-layer hyre-polygon'
    },
    tooltip=folium.GeoJsonTooltip(fields=['NAMN', 'Andel_Hyresratt', 'Totalt_uppl'], aliases=['Område:', 'Hyresrätt (%):', 'Totalt antal bostäder:'], localize=True)
).add_to(m)


# --- LAGER 7: Områdesgränser (Endast linjer) ---
folium.GeoJson(nyko3, name='Områdesgränser', style_function=lambda feature: {'fill': False, 'color': '#2c3e50', 'weight': 2, 'className': 'polygon-layer border-polygon'}).add_to(m)

# =====================================================================
# 5. INJICERA GYLLENE STANDARDMALL
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

    /* Dölj Foliums inbyggda legender permanent */
    .legend {{ display: none !important; }}

    .tools-panel {{ position: fixed; bottom: 30px; left: 60px; z-index: 9999; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 300px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; transition: all 0.3s ease; }}
    .layers-panel {{ position: fixed; top: 20px; right: 20px; z-index: 9999; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 310px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; }}
    
    .info-panel {{ position: fixed; top: 20px; right: 340px; z-index: 9999; background: rgba(255,255,255,0.98); padding: 20px; border-radius: 8px; box-shadow: 0 0 20px rgba(0,0,0,0.3); width: 320px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; display: none; transition: all 0.3s ease; font-size: 14px; line-height: 1.5; }}
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

    /* EGENBYGGDA, STABILA HTML-LEGENDER */
    .legend-container {{ position: fixed; bottom: 30px; right: 20px; z-index: 9998; display: flex; flex-direction: column; gap: 10px; pointer-events: none; max-height: 80vh; overflow-y: auto; }}
    .variable-legend {{ pointer-events: auto; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 220px; }}
    
    .leaflet-control-search .search-input {{ padding: 6px 10px; border-radius: 4px; border: 1px solid #ccc; outline: none; width: 190px; font-size: 14px; }}
    
    /* Dynamiska Gränser för Satellit-läge */
    body.sat-mode path.border-polygon {{ stroke: #ffffff !important; }}

    .popup-table {{ width: 100%; font-size: 14px; }}
    .popup-table th {{ border-bottom: 2px solid #333; padding-bottom: 5px; margin-bottom: 5px; text-align:left; }}
    .popup-table td {{ padding-top: 3px; padding-bottom: 3px; }}
    .bar-bg {{ background: #e0e0e0; width: 100%; height: 12px; border-radius: 3px; overflow: hidden; margin-top:2px; }}
    .bar-fill {{ background: #3498db; height: 100%; }}

    /* Responsivitet för surfplattor och mobiler */
    @media (max-width: 992px) {{
        .tools-panel {{ left: 10px; bottom: 10px; width: 260px; padding: 12px; }}
        .layers-panel {{ right: 10px; top: 10px; width: 260px; padding: 12px; }}
        .info-panel {{ right: 280px; top: 10px; width: 300px; padding: 15px; }}
        .legend-container {{ right: 10px; bottom: 10px; transform: scale(0.85); transform-origin: bottom right; }}
    }}
    @media (max-width: 650px) {{
        .layers-panel {{ width: calc(100% - 60px); top: 10px; right: 10px; max-height: 35vh; }}
        .tools-panel {{ width: calc(100% - 20px); left: 10px; bottom: 10px; max-height: 35vh; }}
        /* På mycket små skärmar låter vi Info-panelen flyta fritt överst och ta mer plats */
        .info-panel {{ width: calc(100% - 20px); left: 10px; top: 10px; right: auto; max-height: 70vh; z-index: 10005; box-shadow: 0 0 30px rgba(0,0,0,0.6); }}
        .legend-container {{ bottom: 38vh; right: 10px; transform: scale(0.7); }}
    }}
</style>

<!-- EGENBYGGDA HTML-LEGENDER -->
<div class="legend-container" id="legend-container">
    <div id="legend-pop" class="variable-legend" style="display: block;">
        <h6 style="font-size: 13px; font-weight: bold; margin-bottom: 5px; color:#333;">Befolkning (inv)</h6>
        <div style="background: linear-gradient(to right, #fde725, #b5de2b, #6ece58, #35b779, #1f9e89, #26828e, #31688e, #3e4989, #482878, #440154); height: 12px; border-radius: 3px; width: 100%;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-top: 3px; color:#666;"><span>Lägst</span><span>Högst</span></div>
    </div>
    <div id="legend-dens" class="variable-legend" style="display: none;">
        <h6 style="font-size: 13px; font-weight: bold; margin-bottom: 5px; color:#333;">Befolkningstäthet (inv/km²)</h6>
        <div style="background: linear-gradient(to right, #fde725, #b5de2b, #6ece58, #35b779, #1f9e89, #26828e, #31688e, #3e4989, #482878, #440154); height: 12px; border-radius: 3px; width: 100%;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-top: 3px; color:#666;"><span>Lägst</span><span>Högst</span></div>
    </div>
    <div id="legend-hushall" class="variable-legend" style="display: none;">
        <h6 style="font-size: 13px; font-weight: bold; margin-bottom: 5px; color:#333;">Hushållsstorlek (pers/hushåll)</h6>
        <div style="background: linear-gradient(to right, #fde725, #b5de2b, #6ece58, #35b779, #1f9e89, #26828e, #31688e, #3e4989, #482878, #440154); height: 12px; border-radius: 3px; width: 100%;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-top: 3px; color:#666;"><span>Minst</span><span>Störst</span></div>
    </div>
    <div id="legend-agan" class="variable-legend" style="display: none;">
        <h6 style="font-size: 13px; font-weight: bold; margin-bottom: 5px; color:#333;">Äganderätt (%)</h6>
        <div style="background: linear-gradient(to right, #fde725, #b5de2b, #6ece58, #35b779, #1f9e89, #26828e, #31688e, #3e4989, #482878, #440154); height: 12px; border-radius: 3px; width: 100%;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-top: 3px; color:#666;"><span>0%</span><span>100%</span></div>
    </div>
    <div id="legend-bost" class="variable-legend" style="display: none;">
        <h6 style="font-size: 13px; font-weight: bold; margin-bottom: 5px; color:#333;">Bostadsrätt (%)</h6>
        <div style="background: linear-gradient(to right, #fde725, #b5de2b, #6ece58, #35b779, #1f9e89, #26828e, #31688e, #3e4989, #482878, #440154); height: 12px; border-radius: 3px; width: 100%;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-top: 3px; color:#666;"><span>0%</span><span>100%</span></div>
    </div>
    <div id="legend-hyre" class="variable-legend" style="display: none;">
        <h6 style="font-size: 13px; font-weight: bold; margin-bottom: 5px; color:#333;">Hyresrätt (%)</h6>
        <div style="background: linear-gradient(to right, #fde725, #b5de2b, #6ece58, #35b779, #1f9e89, #26828e, #31688e, #3e4989, #482878, #440154); height: 12px; border-radius: 3px; width: 100%;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-top: 3px; color:#666;"><span>0%</span><span>100%</span></div>
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
        <option value="">-- Zooma till stadsdel --</option>
    </select>
    
    <div class="form-check mb-3 mt-2">
        <input class="form-check-input" type="checkbox" id="toggleGraph" checked>
        <label class="form-check-label fw-bold" for="toggleGraph" style="font-size: 12px; color:#2c3e50;">📈 Visa graf vid klick (Områden)</label>
    </div>

    <button id="btn-reset" class="btn btn-outline-secondary btn-sm btn-custom mb-3">🔄 Återställ & Rensa allt</button>

    <h6 class="fw-bold mb-2" style="font-size: 13px;">Geografiska mätverktyg</h6>
    <button id="btn-measure" class="btn btn-outline-primary btn-sm btn-custom">📏 Avståndsmätare (Centrum)</button>
    <button id="btn-isochrone" class="btn btn-outline-info btn-sm btn-custom">⏱️ 15-min Nåbarhetsanalys</button>
    
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
        <option value="satellit">Karta: Satellit (Flygfoto)</option>
    </select>
    
    <hr style="margin: 10px 0;">
    <h6 class="fw-bold mb-2" style="font-size: 13px;">Ytor & Områden</h6>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="togglePop" checked><label class="form-check-label" for="togglePop">Befolkning {latest_year}</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleDens"><label class="form-check-label" for="toggleDens">Befolkningstäthet</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleHushall"><label class="form-check-label" for="toggleHushall">Hushållsstorlek</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleAgan"><label class="form-check-label" for="toggleAgan">Äganderätt (%)</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleBost"><label class="form-check-label" for="toggleBost">Bostadsrätt (%)</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleHyre"><label class="form-check-label" for="toggleHyre">Hyresrätt (%)</label></div>
    <div class="form-check mb-1 mt-2 border-top pt-2"><input class="form-check-input" type="checkbox" id="toggleBorders"><label class="form-check-label" for="toggleBorders">Endast Områdesgränser</label></div>
    
    <hr style="margin: 10px 0;">
    <h6 class="fw-bold mb-2" style="font-size: 13px;">Infrastruktur & Natur</h6>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleTransport"><label class="form-check-label" for="toggleTransport">🛤️ Transportleder (Väg/Järnväg)</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleVatten"><label class="form-check-label" for="toggleVatten">💧 Sjöar & Vattendrag</label></div>

    <hr style="margin: 10px 0;">
    <h6 class="fw-bold mb-2" style="font-size: 13px;">Analyspunkter</h6>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleCentroids" checked><label class="form-check-label" for="toggleCentroids">🟡 Centrumpunkter</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleCircles"><label class="form-check-label" for="toggleCircles">🟢 Befolkningsringar (Åldrar)</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleDynPop"><label class="form-check-label" for="toggleDynPop">🟠 Dynamisk Befolkning <span id="dynPopLabel" class="badge" style="display:none; font-size:10px; margin-left:3px; background-color:#2980b9;">Nyko 1</span></label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleClusters"><label class="form-check-label" for="toggleClusters">🔵 Detaljerad Befolkning (Kluster)</label></div>
    
    <hr style="margin: 10px 0;">
    <h6 class="fw-bold mb-2" style="font-size: 13px;">Intresseplatser (POI)</h6>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleGrundskolor"><label class="form-check-label" for="toggleGrundskolor"><i class="fas fa-child text-primary"></i> Grundskolor</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleGymnasieskolor"><label class="form-check-label" for="toggleGymnasieskolor"><i class="fas fa-graduation-cap" style="color:#9b59b6;"></i> Gymnasieskolor</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleHandel"><label class="form-check-label" for="toggleHandel"><i class="fas fa-shopping-cart" style="color:#e67e22;"></i> Handel & Centrum</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleIdrott"><label class="form-check-label" for="toggleIdrott"><i class="fas fa-futbol text-success"></i> Idrott & Fritid</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleSamhalle"><label class="form-check-label" for="toggleSamhalle"><i class="fas fa-building" style="color:#34495e;"></i> Samhälle & Infrastruktur</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleKultur"><label class="form-check-label" for="toggleKultur"><i class="fas fa-theater-masks text-danger"></i> Kultur & Sevärdheter</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleOvriga"><label class="form-check-label" for="toggleOvriga"><i class="fas fa-map-marker-alt text-secondary"></i> Övriga platser</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleVard" disabled><label class="form-check-label text-muted" for="toggleVard"><i class="fas fa-heartbeat"></i> Vårdboenden (Kommande)</label></div>
    
    <button id="btnZoomPOI" class="btn btn-sm btn-outline-primary mt-3 w-100 fw-bold" style="font-size: 13px;">🔍 Zooma till valda platser</button>
</div>

<script>
    var lastZoomBounds = null;
    var upplatelseChartInstans = null; // Global instans för cirkeldiagrammet

    document.addEventListener('DOMContentLoaded', function() {{
        var map_id = Object.keys(window).find(key => key.startsWith('map_'));
        var map = window[map_id];
        
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
        var tileSatellit = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ attribution: 'Tiles &copy; Esri', crossOrigin: true }});

        document.getElementById('basemapSelect').addEventListener('change', function(e) {{
            map.removeLayer(tileBlek); 
            map.removeLayer(tileFarg); 
            map.removeLayer(tileSatellit);
            
            if(e.target.value === 'blek') {{ 
                tileBlek.addTo(map); 
                document.body.classList.remove('sat-mode');
            }} else if(e.target.value === 'farg') {{ 
                tileFarg.addTo(map); 
                document.body.classList.remove('sat-mode');
            }} else if(e.target.value === 'satellit') {{
                tileSatellit.addTo(map);
                document.body.classList.add('sat-mode');
            }}
        }});
        
        // --- HANTERA EXKLUDERANDE RADIOKNAPPAR FÖR YTLAGER & EGNA LEGENDER ---
        function updatePolygonVisibility() {{
            var showPop = document.getElementById('togglePop').checked;
            var showDens = document.getElementById('toggleDens').checked;
            var showHushall = document.getElementById('toggleHushall').checked;
            var showAgan = document.getElementById('toggleAgan').checked;
            var showBost = document.getElementById('toggleBost').checked;
            var showHyre = document.getElementById('toggleHyre').checked;

            document.querySelectorAll('.pop-polygon').forEach(el => el.style.display = showPop ? '' : 'none');
            document.querySelectorAll('.density-polygon').forEach(el => el.style.display = showDens ? '' : 'none');
            document.querySelectorAll('.hushall-polygon').forEach(el => el.style.display = showHushall ? '' : 'none');
            document.querySelectorAll('.agan-polygon').forEach(el => el.style.display = showAgan ? '' : 'none');
            document.querySelectorAll('.bost-polygon').forEach(el => el.style.display = showBost ? '' : 'none');
            document.querySelectorAll('.hyre-polygon').forEach(el => el.style.display = showHyre ? '' : 'none');
            
            // Hantera Legender (Släck alla, tänd aktiv)
            document.querySelectorAll('.variable-legend').forEach(el => el.style.display = 'none');
            if (showPop) document.getElementById('legend-pop').style.display = 'block';
            else if (showDens) document.getElementById('legend-dens').style.display = 'block';
            else if (showHushall) document.getElementById('legend-hushall').style.display = 'block';
            else if (showAgan) document.getElementById('legend-agan').style.display = 'block';
            else if (showBost) document.getElementById('legend-bost').style.display = 'block';
            else if (showHyre) document.getElementById('legend-hyre').style.display = 'block';
        }}
        
        var baseLayers = ['togglePop', 'toggleDens', 'toggleHushall', 'toggleAgan', 'toggleBost', 'toggleHyre'];
        baseLayers.forEach(function(id) {{
            var el = document.getElementById(id);
            if (el) {{
                el.addEventListener('change', function(e) {{
                    if (e.target.checked) {{
                        baseLayers.forEach(function(otherId) {{
                            if (otherId !== id) document.getElementById(otherId).checked = false;
                        }});
                    }}
                    updatePolygonVisibility();
                }});
            }}
        }});
        
        // Initial Döljning
        document.querySelectorAll('.density-polygon, .hushall-polygon, .agan-polygon, .bost-polygon, .hyre-polygon, .border-polygon').forEach(el => el.style.display = 'none');

        document.getElementById('opacitySlider').addEventListener('input', function(e) {{
            var val = e.target.value;
            document.getElementById('opacityVal').innerText = Math.round(val * 100) + '%';
            document.querySelectorAll('.pop-polygon, .density-polygon, .hushall-polygon, .agan-polygon, .bost-polygon, .hyre-polygon, .default-polygon').forEach(el => {{ el.style.fillOpacity = val; }});
        }});

        document.getElementById('toggleBorders').addEventListener('change', function(e) {{
            document.querySelectorAll('.border-polygon').forEach(el => el.style.display = e.target.checked ? '' : 'none');
        }});

        updatePolygonVisibility();

        var nykoData = {nyko_json_str}; 
        var poiData = {poi_json_str}; 
        var heatDataRaw = []; 
        var transportData = {transport_str}; 
        var vattenData = {vatten_str};
        
        // Dynamisk Zoom-data inläsning
        var dynPop1 = {dyn_pop1_str};
        var dynPop3 = {dyn_pop3_str};
        var dynPop4 = {dyn_pop4_str};
        var dynPop6 = {dyn_pop6_str};

        var zoomSel = document.getElementById('zoomSelect');
        nykoData.sort((a,b) => a.namn.localeCompare(b.namn)).forEach(function(d) {{
            var opt = document.createElement('option'); opt.value = d.lat + ',' + d.lon; opt.innerHTML = d.namn; zoomSel.appendChild(opt);
        }});
        zoomSel.addEventListener('change', function() {{
            if(this.value) {{ var coords = this.value.split(','); map.flyTo([parseFloat(coords[0]), parseFloat(coords[1])], 14); }}
        }});
        
        var centroidLayer = L.featureGroup().addTo(map); var searchLayer = L.layerGroup().addTo(map); var customRadiusLayer = L.featureGroup().addTo(map); 
        var circleLayer = L.featureGroup(); var layerGrundskolor = L.featureGroup(); var layerGymnasieskolor = L.featureGroup(); var layerHandel = L.featureGroup(); var layerIdrott = L.featureGroup(); var layerSamhalle = L.featureGroup(); var layerKultur = L.featureGroup(); var layerOvriga = L.featureGroup(); var layerVard = L.featureGroup();

        var layerTransport = L.geoJSON(transportData, {{ style: function(feature) {{ var props = feature.properties || {{}}; if (props.railway || (props.fklass && props.fklass.toLowerCase().includes('järnväg'))) return {{ color: '#000000', weight: 3, dashArray: '5, 5' }}; else if (props.highway === 'motorway' || (props.namn && props.namn.includes('E4'))) return {{ color: '#e74c3c', weight: 4 }}; else return {{ color: '#f39c12', weight: 2 }}; }} }});
        var layerVatten = L.geoJSON(vattenData, {{ style: function(feature) {{ return {{ color: '#3498db', fillColor: '#3498db', weight: 1, fillOpacity: 0.5 }}; }} }});

        map.createPane('centroidPane'); map.getPane('centroidPane').style.zIndex = 650;

        function safeStat(val) {{ return val < 5 ? '< 5' : val; }}
        function makeBarRow(label, value, total) {{
            var pct = total > 0 && value >= 5 ? ((value / total) * 100).toFixed(1) : 0;
            return `<tr><td style="width: 45%;">${{label}}</td><td style="width: 15%; text-align: right;"><strong>${{safeStat(value)}}</strong></td><td style="width: 40%; padding-left: 10px;"><div class="bar-bg"><div class="bar-fill" style="width: ${{pct}}%; background: ${{pct > 25 ? '#e74c3c' : '#3498db'}};"></div></div></td></tr>`;
        }}
        function makeSubRow(label, value) {{ return `<tr style="color: #666; font-size: 12px;"><td style="padding-left: 15px;">↳ varav ${{label}}</td><td style="text-align: right;">${{safeStat(value)}}</td><td></td></tr>`; }}

        function generateDemographicHtml(title, stats) {{
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

        // --- 5. NY DYNAMISK BEFOLKNING (BYTER ÖVER ZOOM-NIVÅER) ---
        function buildDynLayer(data, color, levelName) {{
            var layer = L.featureGroup();
            data.forEach(function(d) {{
                var isSecret = d.Totalt > 0 && d.Totalt < 5;
                var displayPop = isSecret ? "< 5" : d.Totalt;
                var size = Math.max(30, Math.min(70, 15 + Math.sqrt(d.Totalt)*0.8));
                var html = `<div style="background-color: ${{color}}; color: white; border-radius: 50%; width: ${{size}}px; height: ${{size}}px; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight:bold; border: 2px solid #fff; opacity: 0.9; box-shadow: 0 2px 5px rgba(0,0,0,0.5);">${{displayPop}}</div>`;
                var markerIcon = L.divIcon({{ html: html, className: '', iconSize: [size, size], iconAnchor: [size/2, size/2] }});
                var marker = L.marker([d.lat, d.lon], {{ icon: markerIcon }});
                
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
                lbl.innerText = "Nyko 1"; lbl.style.backgroundColor = "#2980b9";
            }} else if (z === 12) {{
                map.addLayer(layerDyn3);
                lbl.innerText = "Nyko 3"; lbl.style.backgroundColor = "#8e44ad";
            }} else if (z === 13 || z === 14) {{
                map.addLayer(layerDyn4);
                lbl.innerText = "Nyko 4"; lbl.style.backgroundColor = "#e67e22";
            }} else if (z >= 15) {{
                map.addLayer(layerDyn6);
                lbl.innerText = "Nyko 6"; lbl.style.backgroundColor = "#c0392b";
            }}
        }}
        
        map.on('zoomend', updateDynPopLayer);
        document.getElementById('toggleDynPop').addEventListener('change', updateDynPopLayer);


        nykoData.forEach(function(d) {{
            if(d.tot > 0) {{
                var radius = Math.max(4, Math.sqrt(d.tot) * 0.4); 
                var prevTot = d.tot - d.pop_change; var pctChange = prevTot > 0 ? (d.pop_change / prevTot) * 100 : 0;
                var circleColor = '#f1c40f'; if (pctChange > 0.4) circleColor = '#27ae60'; else if (pctChange < -0.4) circleColor = '#e74c3c';
                var changeSign = d.pop_change > 0 ? '+' : '';
                
                var panelHtml = `${{generateDemographicHtml(d.namn, d)}}<div style="background: #f8f9fa; padding: 10px; border-radius: 5px; margin-top: 15px;"><p style="margin: 0; font-size: 14px;"><b>Utveckling (1 år):</b> <strong style="color:${{circleColor}}">${{changeSign}}${{d.pop_change}} inv (${{pctChange.toFixed(1)}}%)</strong></p></div>`;
                
                var circle = L.circleMarker([d.lat, d.lon], {{ radius: radius, fillColor: circleColor, color: '#fff', weight: 1, fillOpacity: 0.8, className: 'pop-ring' }}).bindTooltip("Klicka för åldersfördelning", {{direction: 'top'}});
                circle.on('click', function() {{ showInfoPanel(panelHtml); map.flyTo([d.lat, d.lon], 14); }});
                circle.addTo(circleLayer);

                var t = estimateTravelTimes(d.lat, d.lon); 
                var distances = nykoData.map(node => ({{ node: node, dist: getDistance(d.lat, d.lon, node.lat, node.lon) }})).filter(n => n.dist > 0 && n.node.namn !== d.namn); distances.sort((a,b) => a.dist - b.dist); var nearest = distances.slice(0, 3);
                var nnHtml = nearest.map(n => `<li style="margin-bottom:4px;">${{n.node.namn}}: <b>${{n.dist.toFixed(2)}} km</b></li>`).join('');

                var chartContent = d.tot_uppl > 0 
                    ? `<div style="height: 200px; width: 100%; position: relative;"><canvas id="upplatelsePieChart"></canvas></div><p style="font-size:12px; text-align:center; color:#666; margin-top:5px;">Totalt antal bostäder: ${{d.tot_uppl}}</p>` 
                    : `<p style="text-align:center; color:#999; margin-top:30px;">Data saknas.</p>`;

                var centroidHtml = `
                    <h4 style="border-bottom:2px solid #333; padding-bottom:5px; margin-bottom:12px;"><b>${{d.namn}}</b></h4>
                    <ul class="nav nav-tabs" role="tablist">
                        <li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#tab-oversikt" type="button" style="font-size: 13px; padding: 5px 10px;">Översikt</button></li>
                        <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-uppl" type="button" style="font-size: 13px; padding: 5px 10px;">Upplåtelseform</button></li>
                    </ul>
                    <div class="tab-content" style="padding-top: 12px;">
                        <div class="tab-pane fade show active" id="tab-oversikt" role="tabpanel">
                            <p style="font-size:15px;"><b>Folkmängd:</b> ${{d.tot}} invånare</p>
                            <p style="font-size:15px;"><b>Fågelväg t. Stora torget:</b> 🚲 ${{t.st.bike}} km | 🚗 ${{t.st.car}} km <i>(${{t.st.dist}} km)</i></p>
                            <p style="font-size:15px; margin-bottom: 15px;"><b>Restid t. Resecentrum:</b><br>🚶 ${{t.rc.walk}} min | 🚲 ${{t.rc.bike}} min | 🚌 ${{t.rc.pt}} min | 🚗 ${{t.rc.car}} min</p>
                            <div style="background: #f8f9fa; padding: 12px; border-radius: 5px;">
                                <b style="display:block; margin-bottom:8px; font-size:14px;">De 3 närmaste grannarna:</b>
                                <ul style="padding-left:20px; margin-bottom:0; font-size:14px;">${{nnHtml}}</ul>
                            </div>
                        </div>
                        <div class="tab-pane fade" id="tab-uppl" role="tabpanel">
                            ${{chartContent}}
                        </div>
                    </div>
                `;
                
                var centroidMarker = L.circleMarker([d.lat, d.lon], {{ radius: 7, fillColor: '#f1c40f', color: '#e74c3c', weight: 2, fillOpacity: 1, pane: 'centroidPane' }}).bindTooltip("Klicka för områdesanalys", {{direction: 'top'}});
                
                centroidMarker.on('click', function() {{ 
                    showInfoPanel(centroidHtml); 
                    map.flyTo([d.lat, d.lon], 14); 
                    
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
                                        plugins: {{
                                            legend: {{ position: 'bottom', labels: {{ boxWidth: 12, font: {{ size: 11 }} }} }}
                                        }} 
                                    }}
                                }});
                            }}
                        }}, 100);
                    }}
                }});
                
                centroidMarker.feature = {{ properties: {{ name: d.namn, html: centroidHtml }} }}; 
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
            layer: searchLayer, propertyName: 'name', marker: false, collapsed: false, textPlaceholder: 'Sök område...',
            moveToLocation: function(latlng, title, map) {{ 
                map.flyTo(latlng, 14); clearHighlight();
                map.eachLayer(function(layer) {{ if (layer.feature && layer.feature.properties && layer.feature.properties.NAMN === title) {{ if (layer.setStyle) {{ layer.setStyle({{weight: 5, color: '#f39c12'}}); highlightedPolygon = layer; }} }} }});
                centroidLayer.eachLayer(function(layer) {{ if (layer.feature && layer.feature.properties.name === title) {{ showInfoPanel(layer.feature.properties.html); }} }});
            }} 
        }});
        map.addControl(searchControl);

        document.getElementById('btn-reset').addEventListener('click', function() {{
            map.setView([58.4102, 15.6216], 11); clearHighlight(); searchControl.collapse(); document.getElementById('zoomSelect').value = ""; 
            if(drawnItems) drawnItems.clearLayers(); customRadiusLayer.clearLayers(); document.getElementById('infoPanel').style.display = 'none'; lastZoomBounds = null; 
            
            document.getElementById('basemapSelect').value = 'blek';
            document.getElementById('basemapSelect').dispatchEvent(new Event('change'));

            document.getElementById('opacitySlider').value = 0.60; document.getElementById('opacityVal').innerText = '60%';
            document.querySelectorAll('.pop-polygon, .density-polygon, .hushall-polygon, .agan-polygon, .bost-polygon, .hyre-polygon, .default-polygon').forEach(el => {{ el.style.fillOpacity = 0.60; }});
            document.getElementById('togglePop').checked = true; document.getElementById('togglePop').dispatchEvent(new Event('change'));
            document.getElementById('toggleCentroids').checked = true; document.getElementById('toggleCentroids').dispatchEvent(new Event('change'));
            if(measureMode) document.getElementById('btn-measure').click(); if(isochroneMode) document.getElementById('btn-isochrone').click();
            ['toggleDens', 'toggleHushall', 'toggleAgan', 'toggleBost', 'toggleHyre', 'toggleBorders', 'toggleCircles', 'toggleDynPop', 'toggleClusters', 'toggleTransport', 'toggleVatten', 'toggleGrundskolor', 'toggleGymnasieskolor', 'toggleHandel', 'toggleIdrott', 'toggleSamhalle', 'toggleKultur', 'toggleOvriga'].forEach(function(id) {{ var cb = document.getElementById(id); if(cb && cb.checked) {{ cb.checked = false; cb.dispatchEvent(new Event('change')); }} }});
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
        
        function createCleanIcon(pop) {{
            var size = 24;
            if (pop >= 10) size = 28;
            if (pop >= 50) size = 32;
            if (pop >= 200) size = 38;
            if (pop >= 1000) size = 46;

            var displayPop = pop < 5 ? "" : pop;
            var fSize = pop >= 1000 ? 11 : 12;

            return L.divIcon({{
                html: `<div style="background-color: rgba(52, 152, 219, 0.95); color: white; border-radius: 50%; width: ${{size}}px; height: ${{size}}px; display: flex; align-items: center; justify-content: center; font-size: ${{fSize}}px; font-weight: bold; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.4);">${{displayPop}}</div>`,
                className: '',
                iconSize: [size, size]
            }});
        }}
        
        var clusterLayer = L.markerClusterGroup({{
            chunkedLoading: true, 
            iconCreateFunction: function(cluster) {{
                var markers = cluster.getAllChildMarkers(); 
                var sum = 0;
                for (var i = 0; i < markers.length; i++) {{ sum += markers[i].options.population || 0; }}
                return createCleanIcon(sum); 
            }}
        }});

        fetch('heat_data.json').then(response => response.json()).then(data => {{ 
            heatDataRaw = data; var markersToAdd = [];
            heatDataRaw.forEach(function(p) {{
                var pop = p.tot;
                if (pop > 0) {{
                    var markerIcon = createCleanIcon(pop);
                    var marker = L.marker([p.lat, p.lon], {{ icon: markerIcon, population: pop }});
                    marker.on('click', function() {{
                        var html = "";
                        if (pop < 5) {{ html = `<div style="font-size: 14px; padding: 10px;"><b>Sekretesskyddad data</b><br>Detaljerad demografisk information visas ej då färre än 5 personer är skrivna på denna koordinat.</div>`; }} 
                        else {{ html = generateDemographicHtml("Befolkning på platsen", p); }}
                        showInfoPanel(html); map.flyTo([p.lat, p.lon], 16);
                    }});
                    markersToAdd.push(marker);
                }}
            }});
            clusterLayer.addLayers(markersToAdd);
        }}).catch(err => console.error("Kunde inte ladda punktdata:", err));

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

        // --- 5. RITA EGNA POLYGONER FÖR DEMOGRAFIANALYS ---
        var drawnItems = new L.FeatureGroup(); map.addLayer(drawnItems);
        L.drawLocal.draw.toolbar.actions.title = 'Avbryt ritning'; L.drawLocal.draw.toolbar.actions.text = 'Avbryt'; L.drawLocal.draw.toolbar.finish.title = 'Slutför ritning'; L.drawLocal.draw.toolbar.finish.text = 'Slutför'; L.drawLocal.draw.toolbar.undo.title = 'Ångra sista punkten'; L.drawLocal.draw.toolbar.undo.text = 'Ångra'; L.drawLocal.draw.handlers.polygon.tooltip.start = 'Klicka för att börja rita en yta.'; L.drawLocal.draw.handlers.polygon.tooltip.cont = 'Klicka för att fortsätta rita ytan.'; L.drawLocal.draw.handlers.polygon.tooltip.end = 'Klicka på första punkten för att slutföra.'; L.drawLocal.draw.handlers.rectangle.tooltip.start = 'Klicka och dra för att rita en rektangel.';
        var drawControl = new L.Control.Draw({{ draw: {{ polyline: false, marker: false, circlemarker: false, circle: false, polygon: {{ shapeOptions: {{ color: '#9b59b6', weight: 2, fillOpacity: 0.3 }} }}, rectangle: {{ shapeOptions: {{ color: '#9b59b6', weight: 2, fillOpacity: 0.3 }} }} }}, edit: {{ featureGroup: drawnItems }} }});
        map.addControl(drawControl);

        var isDrawingMode = false;
        map.on('draw:drawstart', function(e) {{ isDrawingMode = true; }});
        map.on('draw:drawstop', function(e) {{ isDrawingMode = false; }});

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

        // --- 6. NÅBARHETSANALYS (ISOKRONER) & AVSTÅNDSMÄTARE ---
        var measureMode = false; var isochroneMode = false;

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
                var rWalk = 0.96; var rBike = 3.12; var rCar = 7.69;
                
                var carLayer = L.circle([lat, lon], {{radius: rCar*1000, color: '#e74c3c', weight: 1, fillOpacity: 0.1}}).addTo(customRadiusLayer);
                var bikeLayer = L.circle([lat, lon], {{radius: rBike*1000, color: '#f39c12', weight: 1, fillOpacity: 0.15}}).addTo(customRadiusLayer);
                var walkLayer = L.circle([lat, lon], {{radius: rWalk*1000, color: '#2ecc71', weight: 2, fillOpacity: 0.3}}).addTo(customRadiusLayer);
                
                var statsWalk = getDemographicsInRadius(lat, lon, rWalk);
                var statsBike = getDemographicsInRadius(lat, lon, rBike);
                var statsCar = getDemographicsInRadius(lat, lon, rCar);
                
                function sStat(v) {{ return v < 5 ? '< 5' : v; }}
                
                var isoHtml = `
                    <h5 style="border-bottom:2px solid #333; padding-bottom:5px; margin-bottom:12px;"><b>Nåbarhet (15 minuter)</b></h5>
                    <p style="font-size:14px; margin-bottom:10px;">Antal invånare som når denna punkt på en kvart:</p>
                    <table class="popup-table" style="margin-bottom:15px; font-size:15px;">
                        <tr><td style="padding-bottom:5px;">🚶 <b>Gång</b> (~1 km):</td><td style="text-align:right"><b>${{sStat(statsWalk.tot)}}</b></td></tr>
                        <tr><td style="padding-bottom:5px;">🚲 <b>Cykel</b> (~3 km):</td><td style="text-align:right"><b>${{sStat(statsBike.tot)}}</b></td></tr>
                        <tr><td style="padding-bottom:5px;">🚗 <b>Bil/Buss</b> (~7.5 km):</td><td style="text-align:right"><b>${{sStat(statsCar.tot)}}</b></td></tr>
                    </table>
                    <hr style="margin: 10px 0;">
                    <p style="font-size:13px; color:#666; margin-bottom:10px;">Nedan visas detaljerad demografi för cykelavståndet.</p>
                    <div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">
                        ${{generateDemographicHtml("Demografi (15 min Cykel)", statsBike)}}
                    </div>
                `;
                
                walkLayer.on('click', function() {{ showInfoPanel(isoHtml); }});
                bikeLayer.on('click', function() {{ showInfoPanel(isoHtml); }});
                carLayer.on('click', function() {{ showInfoPanel(isoHtml); }});
                
                showInfoPanel(isoHtml); map.flyTo([lat, lon], 12); return; 
            }}
        }});

        // --- 7. HOVER-EFFEKT & GRAF VID KLICK ---
        var histData = {hist_json_str}; var myChart = null; var chartModal = new bootstrap.Modal(document.getElementById('chartModal'));

        function openChart(namn) {{
            if(!histData[namn] || histData[namn].labels.length === 0) return;
            document.getElementById('chartModalLabel').innerText = 'Befolkningsutveckling: ' + namn;
            if(myChart) myChart.destroy(); var ctx = document.getElementById('popChart').getContext('2d');
            myChart = new Chart(ctx, {{ 
                type: 'line', 
                data: {{ 
                    labels: histData[namn].labels, 
                    datasets: [{{ 
                        label: 'Folkmängd', data: histData[namn].data, borderColor: '#2ecc71', backgroundColor: 'rgba(46, 204, 113, 0.2)', borderWidth: 2, fill: true, tension: 0.3, pointRadius: 3 
                    }}] 
                }}, 
                options: {{ 
                    responsive: true, 
                    scales: {{ y: {{ beginAtZero: false }} }},
                    spanGaps: false // För sekretessmaskerade data
                }} 
            }});
            chartModal.show();
        }}

        function bindPolygonInteractions() {{
            var found = false;
            map.eachLayer(function(layer) {{
                if (layer.feature && layer.feature.properties && layer.feature.properties.NAMN) {{
                    layer.off('mouseover mouseout click'); 
                    
                    layer.on('mouseover', function(e) {{
                        if (measureMode || isochroneMode || isDrawingMode) return; 
                        var target = e.target;
                        target.setStyle({{ weight: 4, color: '#e74c3c' }});
                        if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {{
                            target.bringToFront();
                        }}
                    }});

                    layer.on('mouseout', function(e) {{
                        var target = e.target;
                        if (target === highlightedPolygon) {{
                            target.setStyle({{weight: 5, color: '#f39c12'}});
                            return;
                        }}
                        var isBorder = target.options.className && target.options.className.includes('border-polygon');
                        var currentOpacity = document.getElementById('opacitySlider').value;
                        var defaultBorderColor = document.body.classList.contains('sat-mode') ? '#ffffff' : '#2c3e50';
                        if (isBorder) {{
                            target.setStyle({{weight: 2, color: defaultBorderColor, fill: false}});
                        }} else {{
                            target.setStyle({{weight: 1, color: '#333333', fillOpacity: currentOpacity}});
                        }}
                    }});

                    layer.on('click', function(e) {{
                        if (measureMode || isochroneMode || isDrawingMode) return; 
                        if (!document.getElementById('toggleGraph').checked) return; 
                        openChart(layer.feature.properties.NAMN); 
                        L.DomEvent.stopPropagation(e);
                    }});
                    found = true;
                }}
            }});
            if (!found) setTimeout(bindPolygonInteractions, 500); 
        }}
        bindPolygonInteractions();
    }});
</script>
"""

m.get_root().html.add_child(folium.Element(ui_html))
html_out_path = os.path.join(moder_mapp, 'Linkoping_Analyskarta_v1.html')
m.save(html_out_path)
print(f"\nKlar! Kartan har sparats som:\n{html_out_path}")