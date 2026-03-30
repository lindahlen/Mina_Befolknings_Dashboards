import os
import sys
import geopandas as gpd

# Kontrollera att osmnx finns installerat
try:
    import osmnx as ox
except ImportError:
    print("\nFEL: Biblioteket 'osmnx' saknas i din gis-env.")
    print("För att hämta vägar och sjöar behöver du installera det.")
    print("Kör följande kommando i din terminal:")
    print("conda install -c conda-forge osmnx")
    sys.exit(1)

# =====================================================================
# 1. SETUP SÖKVÄGAR & MILJÖ
# =====================================================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
    moder_mapp = os.path.dirname(current_folder)
except NameError:
    current_folder = os.getcwd()
    moder_mapp = os.path.dirname(current_folder)

kart_filer_dir = os.path.join(moder_mapp, 'kart_filer')
os.makedirs(kart_filer_dir, exist_ok=True)

plats = "Linköpings kommun, Sweden"

# Visa lite utskrifter i terminalen från OSMnx så du ser att det laddar
ox.settings.log_console = True

def clean_data_for_geojson(gdf):
    """
    Rensar upp datan innan export till GeoJSON.
    Tar bort komplexa listor som OpenStreetMap ibland skickar med, 
    vilka annars kan få GeoJSON-exporten att krascha.
    """
    # Vi behåller bara de kolumner som är relevanta för kartan
    cols_to_keep = ['name', 'highway', 'railway', 'natural', 'waterway', 'geometry']
    gdf = gdf[[c for c in cols_to_keep if c in gdf.columns]].copy()
    
    # Konvertera listor till kommaseparerade strängar
    for col in gdf.columns:
        if col != 'geometry':
            gdf[col] = gdf[col].apply(lambda x: ', '.join(map(str, x)) if isinstance(x, list) else x)
    
    return gdf

print(f"\n🌍 Kopplar upp mot OpenStreetMap för att hämta infrastruktur i {plats}...")
print("Detta kan ta en minut eller två beroende på din uppkoppling. Ha tålamod!")

# =====================================================================
# 2. HÄMTA TRANSPORTLEDER (VÄGAR & JÄRNVÄG)
# =====================================================================
print("\nLaddar ner transportleder (Stambanan, Stångådalsbanan, E4, riks- & matarvägar)...")
tags_transport = {
    'highway': ['motorway', 'trunk', 'primary', 'secondary'], # E4 och viktiga vägar
    'railway': ['rail']                                       # Järnvägar
}

gdf_transport = ox.features_from_place(plats, tags=tags_transport)

# Vi vill bara ha linjer (inte ytor för stationer eller liknande)
gdf_transport = gdf_transport[gdf_transport.geometry.type.isin(['LineString', 'MultiLineString'])]
gdf_transport = clean_data_for_geojson(gdf_transport)

transport_path = os.path.join(kart_filer_dir, 'transportleder.geojson')

# LÖSNING PÅ GDAL/PYOGRIO-BUGGEN: 
# Vi sparar filen som ren text-JSON istället för att använda det buggiga .to_file()-kommandot
with open(transport_path, 'w', encoding='utf-8') as f:
    f.write(gdf_transport.to_json())
    
print(f"✅ Transportleder sparade till: {transport_path}")


# =====================================================================
# 3. HÄMTA SJÖAR OCH VATTENDRAG
# =====================================================================
print("\nLaddar ner sjöar och vattendrag (Roxen, Stångån, Tinnerbäcken, Svartån etc.)...")
tags_vatten = {
    'natural': ['water'],                          # Större sjöar och vattenytor
    'waterway': ['river', 'stream', 'canal']       # Åar, bäckar och kanaler
}

gdf_vatten = ox.features_from_place(plats, tags=tags_vatten)

# Vatten kan vara både polygoner (sjöar) och linjer (mindre åar/bäckar)
gdf_vatten = gdf_vatten[gdf_vatten.geometry.type.isin(['Polygon', 'MultiPolygon', 'LineString', 'MultiLineString'])]
gdf_vatten = clean_data_for_geojson(gdf_vatten)

vatten_path = os.path.join(kart_filer_dir, 'vattendrag.geojson')

# Samma skottsäkra spar-metod här
with open(vatten_path, 'w', encoding='utf-8') as f:
    f.write(gdf_vatten.to_json())
    
print(f"✅ Vattendrag sparade till: {vatten_path}")

print("\n🎉 Nedladdning färdig! All data ligger nu redo i din 'kart_filer'-mapp.")
print("Kör ditt huvudskript (linkoping_karta.py) igen, så kommer de nya lagren synas i kontrollpanelen!")