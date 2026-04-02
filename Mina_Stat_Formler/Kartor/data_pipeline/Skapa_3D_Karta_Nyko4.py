import os
import sys
import json
import pandas as pd
import geopandas as gpd
import pydeck as pdk
import matplotlib.cm as cm
import matplotlib.colors as colors

# =====================================================================
# 1. GENERELL SETUP (Master Config v2.0)
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

GEOJSON_NYKO4_FILENAME = 'NYKO4v23.geojson' 
EXCEL_POP_SHEET = 'Basområden'
OUT_HTML_NAME = 'Linkoping_3D_Extrudering_Nyko4.html'

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
# 2. DATAHANTERING
# =====================================================================
print("Läser in och processar data för 3D-karta...")

excel_path = os.path.join(excel_filer_dir, 'befolkning_och_platser.xlsx')
geojson_path = os.path.join(kart_filer_dir, GEOJSON_NYKO4_FILENAME)

if not os.path.exists(excel_path) or not os.path.exists(geojson_path):
    print("FEL: Hittar inte Excel- eller GeoJSON-filen.")
    sys.exit(1)

# Läs in och städa GeoJSON
nyko4 = gpd.read_file(geojson_path)
nyko4['NAMN'] = nyko4['NAMN'].apply(fix_text)

# Beräkna Area (EPSG:3006)
nyko4_3006 = nyko4.to_crs(epsg=3006)
nyko4['Area_km2'] = nyko4_3006.geometry.area / 1_000_000

# Läs in Befolkning
hist_df = pd.read_excel(excel_path, sheet_name=EXCEL_POP_SHEET)
hist_df.columns = hist_df.columns.astype(str).str.strip() 
hist_df['Namn'] = hist_df['Namn'].apply(fix_text)

# Hitta senaste året (ex. "2025")
years = [str(y) for y in range(1970, 2030)]
existing_years = [y for y in years if y in hist_df.columns]
latest_year = existing_years[-1] if existing_years else '2025'

# Städa data och konvertera till numeriskt
hist_df[latest_year] = pd.to_numeric(hist_df[latest_year].astype(str).str.replace('..', '', regex=False), errors='coerce')

# Merge
nyko4 = nyko4.merge(hist_df[['Namn', latest_year]], left_on='NAMN', right_on='Namn', how='left')
nyko4['Folkmängd'] = nyko4[latest_year].fillna(0).astype(int)

# Undvik division med 0 och beräkna täthet
nyko4['Area_km2'] = nyko4['Area_km2'].replace(0, 0.001)
nyko4['Inv_per_km2'] = (nyko4['Folkmängd'] / nyko4['Area_km2']).round(1)

# =====================================================================
# 3. FÄRGSÄTTNING FÖR PYDECK (RGB)
# =====================================================================
# Pydeck vill ha färger som en lista: [R, G, B, Alpha]. 

print("Skapar färgskalor...")
# Filtrera bort de utan befolkning för att få en bra max för färgskalan
valid_dens = nyko4[nyko4['Inv_per_km2'] > 0]['Inv_per_km2']
vmax = valid_dens.max() if not valid_dens.empty else 1

# Vi sätter tröskelvärdet för glesbygd till 50 inv/km2
THRESHOLD_RURAL = 50

# Magma-skalan (omvänd) för de tätare områdena (50 -> max)
cmap_dense = cm.get_cmap('magma_r')
norm_dense = colors.Normalize(vmin=THRESHOLD_RURAL, vmax=vmax)

def get_color(density, pop):
    if pop < 5: 
        return [200, 200, 200, 150] # Grå och lite transparent för sekretess/obefolkat
    
    if density < THRESHOLD_RURAL:
        # Ljusgrön för områden med låg täthet (landsbygd)
        return [169, 223, 191, 240] 
    else:
        # För områden över tröskelvärdet använder vi omvänd magma (magma_r).
        # Eftersom 1.0 (max) är kolsvart i magma_r, multiplicerar vi det med 0.85 
        # för att stanna vid en snygg djuplila färg och undvika det helt svarta.
        val_norm = norm_dense(density)
        val_adj = val_norm * 0.85 
        
        rgba = cmap_dense(val_adj)
        return [int(rgba[0]*255), int(rgba[1]*255), int(rgba[2]*255), 240]

nyko4['color_rgb'] = nyko4.apply(lambda row: get_color(row['Inv_per_km2'], row['Folkmängd']), axis=1)

# =====================================================================
# 4. BYGG 3D-KARTAN MED PYDECK
# =====================================================================
print("Genererar 3D-karta...")

# Måste ibland konvertera GDF till JSON-sträng för Pydeck för säker inläsning
geojson_data = json.loads(nyko4.to_json())

# Skapa lagret
extruded_layer = pdk.Layer(
    "GeoJsonLayer",
    geojson_data,
    opacity=0.9,
    stroked=True,
    filled=True,
    extruded=True,
    wireframe=True,
    # HÖJD: Hämtas från Folkmängd
    get_elevation="properties.Folkmängd",
    # Justera denna siffra för att göra staplarna högre/lägre i proportion. 
    elevation_scale=2, 
    # FÄRG: Hämtas från vår beräknade färgkolumn
    get_fill_color="properties.color_rgb",
    get_line_color=[100, 100, 100, 120], # Mörkare grå kantlinje för att avgränsa kommunen tydligt
    pickable=True
)

# Sätt kamerans startposition (Tiltad 45 grader)
view_state = pdk.ViewState(
    latitude=58.4102,
    longitude=15.6216,
    zoom=10.5,
    pitch=45, # Det är detta som ger 3D-effekten!
    bearing=0
)

# Tooltip som visas när man hovrar över en 3D-stapel
tooltip = {
    "html": "<b>Område:</b> {NAMN} <br/>"
            "<b>Folkmängd:</b> {Folkmängd} inv<br/>"
            "<b>Täthet:</b> {Inv_per_km2} inv/km²",
    "style": {
        "backgroundColor": "#2c3e50",
        "color": "white",
        "fontFamily": "sans-serif",
        "borderRadius": "8px",
        "padding": "10px"
    }
}

# ---------------------------------------------------------------------
# TIPS FÖR KARTSTIL (map_style):
# Pydeck stödjer flera inbyggda stilar. Här är alternativen du kan byta mellan:
# 'light'           - Ljus gråtonad bas (bra för data med mycket färg)
# 'dark'            - Mörk bas (får ljusa färger att poppa)
# 'road'            - Traditionell vägkarta (mer färgstark och ljus)
# 'satellite'       - Satellitvy (fotografi)
# 'dark_no_labels'  - Mörk utan text/etiketter
# 'light_no_labels' - Ljus utan text/etiketter
# ---------------------------------------------------------------------

# Rendera kartan
deck = pdk.Deck(
    layers=[extruded_layer],
    initial_view_state=view_state,
    tooltip=tooltip,
    map_style='road' # Ändrat till 'road' för en ljusare upplevelse
)

html_out_path = os.path.join(moder_mapp, OUT_HTML_NAME)
deck.to_html(html_out_path)

# =====================================================================
# 5. INJICERA FÖRKLARANDE UI I HTML-FILEN
# =====================================================================
print("Lägger till instruktioner och teckenförklaring...")
with open(html_out_path, 'r', encoding='utf-8') as f:
    html_content = f.read()

# UI-boxen som läggs överst i kartan
ui_overlay = """
<!-- 
TIPS FÖR UTVECKLAREN:
Om du vill byta bakgrundskarta i Pydeck görs detta i Python-skriptet.
Leta upp `map_style='...'` i `pdk.Deck()` anropet.
Tillgängliga alternativ: 'light', 'dark', 'road', 'satellite', 'dark_no_labels', 'light_no_labels'.
-->

<div style="position: absolute; top: 20px; left: 20px; z-index: 1000; background: rgba(255, 255, 255, 0.95); padding: 15px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); font-family: sans-serif; max-width: 320px;">
    <h3 style="margin-top: 0; margin-bottom: 10px; font-size: 16px; color: #2c3e50;">📊 3D-Karta: Befolkning & Täthet</h3>
    <p style="font-size: 13px; color: #333; margin-bottom: 10px; line-height: 1.4;">
        <b>Höjd på stapel:</b> Representerar total folkmängd i basområdet.<br>
        <b>Färg på stapel:</b> <span style="color: #2ecc71; font-weight: bold;">Ljusgrönt</span> markerar glesbygd (< 50 inv/km²). För tätare områden övergår färgen från lysande gult till mörklila (omvänd Magma-skala).
    </p>
    <hr style="border: 0; height: 1px; background: #ccc; margin: 10px 0;">
    <h4 style="margin-top: 0; margin-bottom: 8px; font-size: 14px; color: #2c3e50;">🕹️ Navigering i 3D:</h4>
    <ul style="font-size: 12px; color: #444; padding-left: 20px; margin-bottom: 0; line-height: 1.5;">
        <li><b>Snurra & Tilta:</b> Håll in <i>Höger musknapp</i> (eller Ctrl + Vänster) och dra.</li>
        <li><b>Panorera:</b> Håll in <i>Vänster musknapp</i> och dra.</li>
        <li><b>Zooma:</b> Skrolla med mushjulet.</li>
        <li><b>Information:</b> Hovra över staplarna.</li>
    </ul>
</div>
"""

# Hitta avslutande body-tagg och lägg in vår UI-div precis innan
html_content = html_content.replace('</body>', ui_overlay + '\n</body>')

with open(html_out_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"\nKlar! Din 3D-karta har sparats som:\n{html_out_path}")