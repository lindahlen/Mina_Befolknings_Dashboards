import os
import sys
import pandas as pd
import geopandas as gpd
import folium
import branca.colormap as cm
import json
import numpy as np # Endast för att generera testdata tills riktiga filer finns

# =====================================================================
# 1. GENERELL SETUP & MAPPSTRUKTUR (Master Config v2.0)
# =====================================================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
    moder_mapp = os.path.dirname(current_folder)
except NameError:
    current_folder = os.getcwd()
    moder_mapp = os.path.dirname(current_folder)

# Sökvägar baserat på Linköpings kommuns struktur
kart_filer_dir = os.path.join(moder_mapp, 'kart_filer')
excel_filer_dir = os.path.join(moder_mapp, 'excel_filer')

GEOJSON_NYKO4_FILENAME = 'NYKO4v23.geojson' 
OUT_HTML_NAME = 'Linkoping_SEI_Nyko4.html'

# Teckenkodningsfix
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
# 2. LÄS IN GEOGRAFI OCH BEFINTLIGA RESURSER
# =====================================================================
print("Laddar geografi och befintliga resurser (NYKO 4)...")

# Läs in Nyko 4
geojson_path = os.path.join(kart_filer_dir, GEOJSON_NYKO4_FILENAME)
# Fallback om filen inte finns lokalt under utveckling: Skapa tom GDF
if os.path.exists(geojson_path):
    nyko4 = gpd.read_file(geojson_path)
else:
    print(f"VARNING: Hittade inte {geojson_path}. Kontrollera sökvägen.")
    sys.exit()

nyko4['NAMN'] = nyko4['NAMN'].apply(fix_text)

# Projicera för area-beräkning (EPSG:3006 SWEREF 99 TM)
nyko4_3006 = nyko4.to_crs(epsg=3006)
nyko4['Area_km2'] = nyko4_3006.geometry.area / 1_000_000
nyko4_3006_centroids = nyko4_3006.geometry.centroid

# Läs in existerande POI och Heatmap-data (skapar tomma om de saknas just nu)
def load_json_safe(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f: return f.read()
    return "[]"

poi_json_str = load_json_safe(os.path.join(moder_mapp, 'poi_data.json'))
heat_data_str = load_json_safe(os.path.join(moder_mapp, 'heat_data.json'))

# Infrastruktur
def load_infa(filename):
    path = os.path.join(kart_filer_dir, filename)
    if os.path.exists(path):
        try: return json.dumps(gpd.read_file(path).to_crs(4326).__geo_interface__)
        except: pass
    return json.dumps({"type": "FeatureCollection", "features": []})

transport_str = load_infa('transportleder.geojson')
vatten_str = load_infa('vattendrag.geojson')

# =====================================================================
# 3. LÄS IN OCH BEARBETA SEI-DATA (EXCEL & PX)
# =====================================================================
print("Bearbetar SEI-data...")

sei_excel_path = os.path.join(excel_filer_dir, 'sei_data.xlsx')
px_data_path = os.path.join(excel_filer_dir, 'inkomst_data.csv') # Antar konverterad PX till CSV

# --- MOCK DATA GENERATOR (Tills du laddar upp riktiga filer) ---
# Denna logik skapar realistisk data baserad på dina NYKO4-namn
sei_data = pd.DataFrame({'NAMN': nyko4['NAMN']})
np.random.seed(42) # För reproducerbarhet
sei_data['SEI_Index'] = np.random.uniform(40, 100, size=len(nyko4)).round(1)
sei_data['Medianinkomst'] = np.random.uniform(200000, 550000, size=len(nyko4)).round(-3)
sei_data['Sysselsattningsgrad'] = np.random.uniform(60, 95, size=len(nyko4)).round(1)

# TODO: När du har laddat upp filerna, avkommentera detta block!
"""
try:
    # 1. Läs Excel
    df_excel = pd.read_excel(sei_excel_path)
    df_excel['NAMN'] = df_excel['NAMN'].apply(fix_text)
    
    # 2. Läs PX (antingen via pyaxis eller som konverterad CSV)
    df_px = pd.read_csv(px_data_path, encoding='utf-8')
    df_px['NAMN'] = df_px['NAMN'].apply(fix_text)
    
    # 3. Merga data
    sei_data = pd.merge(df_excel, df_px, on='NAMN', how='left')
    
    # Beräkna ev. ett komposit-index här mha Code Interpreter logik
    # sei_data['SEI_Index'] = (sei_data['Var1'] * 0.5) + (sei_data['Var2'] * 0.5)
    
    print("Riktig SEI-data inladdad och mergad!")
except Exception as e:
    print(f"Kunde inte ladda riktiga filer (Använder testdata). Fel: {e}")
"""

# Koppla data till GeoDataFrame
nyko4 = nyko4.merge(sei_data, on='NAMN', how='left')

# =====================================================================
# 4. EXPORTERA OMRÅDESDATA TILL LOKAL JSON (FÖR JAVASCRIPT UI)
# =====================================================================
centroids_wgs84 = nyko4_3006_centroids.to_crs(epsg=4326)
nyko4_data = []

# Fyll i saknade värden för JS
nyko4['SEI_Index'] = nyko4['SEI_Index'].fillna(0)
nyko4['Medianinkomst'] = nyko4['Medianinkomst'].fillna(0)
nyko4['Sysselsattningsgrad'] = nyko4['Sysselsattningsgrad'].fillna(0)

for idx, row in nyko4.iterrows():
    point = centroids_wgs84.iloc[idx]
    if not point.is_empty:
        nyko4_data.append({
            'namn': row['NAMN'], 
            'lat': point.y, 
            'lon': point.x, 
            'area': round(row['Area_km2'], 2),
            'sei_index': row['SEI_Index'],
            'inkomst': row['Medianinkomst'],
            'sysselsattning': row['Sysselsattningsgrad']
        })
nyko4_json_str = json.dumps(nyko4_data)

# =====================================================================
# 5. KARTBYGGE (HTML/JS Visualisering med Folium)
# =====================================================================
print("Genererar karta och färgskalor...")
m = folium.Map(location=[58.4102, 15.6216], zoom_start=11, tiles=None, control_scale=True)

# Skapa en färgskala (Colormap) för SEI-index (Röd -> Gul -> Grön)
min_sei, max_sei = nyko4['SEI_Index'].min(), nyko4['SEI_Index'].max()
colormap_sei = cm.LinearColormap(
    colors=['#d73027', '#fee08b', '#1a9850'], 
    index=[min_sei, (min_sei+max_sei)/2, max_sei],
    vmin=min_sei, vmax=max_sei,
    caption='Socioekonomiskt Index (SEI)'
)
m.add_child(colormap_sei) # Lägg till på kartan så UI-skriptet kan plocka upp den

# CHOROPLETH LAGER: SEI Index
folium.GeoJson(
    nyko4,
    name='SEI Index (Polygon)',
    style_function=lambda feature: {
        'fillColor': colormap_sei(feature['properties']['SEI_Index']) if feature['properties']['SEI_Index'] else 'transparent',
        'color': 'transparent', # Dölj default border, vi ritar egen
        'weight': 0,
        'fillOpacity': 0.60, # Start-opacitet, styrs av slider
        'className': 'sei-polygon'
    }
).add_to(m)

# Standardgränser (Border layer - påverkas ej av opacitetsslidern)
folium.GeoJson(
    nyko4, 
    name='Områdesgränser', 
    style_function=lambda feature: {
        'fill': False, 
        'color': '#2c3e50', 
        'weight': 2, 
        'className': 'polygon-layer border-polygon'
    }
).add_to(m)


# =====================================================================
# 6. INJICERA GYLLENE STANDARDMALL (Responsiv UI)
# =====================================================================
# Anpassad för SEI, med isokroner, mätverktyg och POI bevarat

ui_html = f"""
<!-- Externa Bibliotek -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet-search/3.0.2/leaflet-search.min.css" />
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster/dist/MarkerCluster.css" />
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster/dist/MarkerCluster.Default.css" />
<script src="https://unpkg.com/leaflet.markercluster/dist/leaflet.markercluster.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>
<script src="https://unpkg.com/@turf/turf/turf.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet-search/3.0.2/leaflet-search.min.js"></script>
<script src="https://unpkg.com/leaflet.heat/dist/leaflet-heat.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>
    :root {{ --poi-scale: 1; }}
    /* Dölj Foliums inbyggda LayerControl för att använda vår egna */
    .leaflet-control-layers {{ display: none !important; }}
    
    .tools-panel {{ position: fixed; bottom: 30px; left: 60px; z-index: 9999; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 300px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; }}
    .layers-panel {{ position: fixed; top: 20px; right: 20px; z-index: 9999; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.2); width: 290px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; }}
    .info-panel {{ position: fixed; top: 20px; right: 330px; z-index: 9999; background: rgba(255,255,255,0.98); padding: 20px; border-radius: 8px; box-shadow: 0 0 20px rgba(0,0,0,0.3); width: 320px; max-height: 85vh; overflow-y: auto; font-family: sans-serif; display: none; }}
    .btn-custom {{ width: 100%; margin-bottom: 8px; text-align: left; font-size: 14px; padding: 6px 12px; }}
    .form-check-input {{ transform: scale(1.3); margin-top: 5px; margin-right: 10px; cursor: pointer; }}
    .form-check-label {{ cursor: pointer; font-size: 13px; font-weight: 500; }}
    
    .legend-container {{ position: fixed; bottom: 30px; right: 20px; z-index: 9998; display: flex; flex-direction: column; gap: 10px; pointer-events: none; max-height: 80vh; overflow-y: auto; }}
    .legend {{ pointer-events: auto; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.2); position: relative !important; top: auto !important; right: auto !important; bottom: auto !important; margin: 0; border: none; }}
    
    @media (max-width: 768px) {{
        .tools-panel {{ bottom: 10px; left: 10px; width: 240px; padding: 10px; }}
        .layers-panel {{ top: 10px; right: 10px; width: 220px; padding: 10px; }}
        .info-panel {{ top: 10px; right: 10px; width: calc(100% - 20px); z-index: 10000; }}
        .legend-container {{ bottom: 10px; right: 10px; transform: scale(0.85); transform-origin: bottom right; }}
    }}
</style>

<div class="legend-container" id="legend-container"></div>

<!-- INFORMATIONSPANEL (Öppnas vid klick på område) -->
<div id="infoPanel" class="info-panel">
    <div class="d-flex justify-content-between align-items-center mb-3" style="border-bottom: 2px solid #ccc; padding-bottom: 8px;">
        <h5 class="fw-bold mb-0 text-primary" id="infoTitle">📊 Information</h5>
        <button type="button" class="btn-close" onclick="closeInfoPanel()"></button>
    </div>
    <div id="infoPanelContent"></div>
</div>

<!-- PANEL 1: VERKTYG (Vänster) -->
<div class="tools-panel">
    <h6 class="fw-bold mb-3"><i class="fas fa-chart-pie text-primary"></i> SEI Analysverktyg</h6>
    
    <div class="p-2 mb-3 bg-light border border-secondary rounded shadow-sm">
        <label for="opacitySlider" class="form-label mb-0 fw-bold" style="font-size: 13px;">Opacitet index-lager:</label>
        <input type="range" class="form-range" id="opacitySlider" min="0" max="1" step="0.05" value="0.60">
    </div>
    
    <select id="zoomSelect" class="form-select form-select-sm mb-3" style="font-size: 13px;">
        <option value="">-- Zooma till basområde --</option>
    </select>

    <button id="btn-reset" class="btn btn-outline-danger btn-sm btn-custom mb-3"><i class="fas fa-trash-alt"></i> Återställ karta</button>

    <h6 class="fw-bold mb-2" style="font-size: 13px;">Geografiska mätverktyg</h6>
    <button id="btn-measure" class="btn btn-outline-primary btn-sm btn-custom"><i class="fas fa-ruler"></i> Avståndsmätare</button>
    <button id="btn-isochrone" class="btn btn-outline-info btn-sm btn-custom"><i class="fas fa-stopwatch"></i> Nåbarhet (Ritverktyg)</button>
</div>

<!-- PANEL 2: LAGERKONTROLL (Höger) -->
<div class="layers-panel">
    <h6 class="fw-bold mb-3"><i class="fas fa-layer-group text-primary"></i> Kartlager</h6>
    <select id="basemapSelect" class="form-select form-select-sm mb-3" style="font-size: 13px;">
        <option value="blek" selected>Karta: Blek (För analys)</option>
        <option value="farg">Karta: Färgstark (OSM)</option>
        <option value="flyg">Karta: Flygfoto (Esri)</option>
    </select>
    
    <hr style="margin: 10px 0;">
    <h6 class="fw-bold mb-2" style="font-size: 13px;">Socioekonomi (SEI)</h6>
    <div class="form-check mb-1">
        <input class="form-check-input" type="checkbox" id="toggleSei" checked>
        <label class="form-check-label" for="toggleSei">Visa SEI Index (Färgytor)</label>
    </div>
    
    <hr style="margin: 10px 0;">
    <h6 class="fw-bold mb-2" style="font-size: 13px;">Infrastruktur & Natur</h6>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleTransport"><label class="form-check-label" for="toggleTransport">🛤️ Transportleder</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleVatten"><label class="form-check-label" for="toggleVatten">💧 Sjöar & Vattendrag</label></div>
    
    <hr style="margin: 10px 0;">
    <h6 class="fw-bold mb-2" style="font-size: 13px;">Intresseplatser (POI)</h6>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleGrundskolor"><label class="form-check-label" for="toggleGrundskolor"><i class="fas fa-child text-primary"></i> Grundskolor</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleHandel"><label class="form-check-label" for="toggleHandel"><i class="fas fa-shopping-cart" style="color:#e67e22;"></i> Handel & Centrum</label></div>
    <div class="form-check mb-1"><input class="form-check-input" type="checkbox" id="toggleHeatmap"><label class="form-check-label" for="toggleHeatmap"><i class="fas fa-fire text-danger"></i> Värmekarta (Täthet)</label></div>
</div>

<script>
    document.addEventListener('DOMContentLoaded', function() {{
        // 1. INITIERA KARTA OCH PANES
        var map_id = Object.keys(window).find(key => key.startsWith('map_'));
        var map = window[map_id];
        
        map.createPane('centroidPane'); map.getPane('centroidPane').style.zIndex = 650;
        map.createPane('circlePane'); map.getPane('circlePane').style.zIndex = 600;
        
        // Flytta legenden
        var container = document.getElementById('legend-container');
        var legends = document.querySelectorAll('.legend');
        legends.forEach(function(leg) {{ container.appendChild(leg); leg.style.display = 'block'; }});

        // 2. DATA FRÅN PYTHON
        var nykoData = {nyko4_json_str}; 
        var poiData = {poi_json_str}; 
        var heatDataRaw = {heat_data_str}; 
        var transportData = {transport_str}; 
        var vattenData = {vatten_str};

        // 3. UI-FUNKTIONER (Info Panel)
        window.closeInfoPanel = function() {{
            document.getElementById('infoPanel').style.display = 'none';
        }}
        
        function formatNumber(num) {{
            return num.toString().replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, " ");
        }}

        function showAreaInfo(namn) {{
            var data = nykoData.find(d => d.namn === namn);
            if(!data) return;
            
            document.getElementById('infoTitle').innerText = namn;
            
            // SEI Dashboard HTML
            var html = `
                <div class="mb-3">
                    <span class="badge bg-secondary mb-2">Area: ${{data.area}} km²</span>
                </div>
                
                <h6 class="fw-bold text-dark border-bottom pb-1">Socioekonomi (SEI)</h6>
                <div class="d-flex justify-content-between mb-1">
                    <span>SEI Index:</span>
                    <span class="fw-bold text-primary">${{data.sei_index.toFixed(1)}}</span>
                </div>
                <div class="progress mb-3" style="height: 8px;">
                    <div class="progress-bar" role="progressbar" style="width: ${{data.sei_index}}%; background-color: #1a9850;" aria-valuenow="${{data.sei_index}}" aria-valuemin="0" aria-valuemax="100"></div>
                </div>

                <div class="d-flex justify-content-between mb-1">
                    <span>Medianinkomst:</span>
                    <span class="fw-bold">${{formatNumber(data.inkomst)}} kr</span>
                </div>
                <div class="d-flex justify-content-between mb-3">
                    <span>Sysselsättning:</span>
                    <span class="fw-bold">${{data.sysselsattning.toFixed(1)}} %</span>
                </div>
                
                <canvas id="seiChart" width="100" height="60" class="mt-3"></canvas>
            `;
            
            document.getElementById('infoPanelContent').innerHTML = html;
            document.getElementById('infoPanel').style.display = 'block';
            
            // Render Chart.js
            setTimeout(() => {{
                var ctx = document.getElementById('seiChart').getContext('2d');
                new Chart(ctx, {{
                    type: 'bar',
                    data: {{
                        labels: ['Sysselsättning (%)', 'SEI Index'],
                        datasets: [{{
                            label: 'Nyckeltal',
                            data: [data.sysselsattning, data.sei_index],
                            backgroundColor: ['#3498db', '#2ecc71']
                        }}]
                    }},
                    options: {{
                        scales: {{ y: {{ beginAtZero: true, max: 100 }} }},
                        plugins: {{ legend: {{ display: false }} }}
                    }}
                }});
            }}, 100);
        }}

        // 4. KOPPLA KARTANS LAGER TILL INTERAKTION
        var seiLayerGroup = L.layerGroup();
        
        function bindPolygonEvents() {{
            var select = document.getElementById('zoomSelect');
            
            map.eachLayer(function(layer) {{
                if (layer.feature && layer.feature.properties && layer.feature.properties.NAMN) {{
                    var isBorder = layer.options.className && layer.options.className.includes('border-polygon');
                    var isSei = layer.options.className && layer.options.className.includes('sei-polygon');
                    
                    if (isSei) {{
                        seiLayerGroup.addLayer(layer); // Spara för checkbox-toggling
                    }}

                    // Lägg till i Zoom-dropdown (bara en gång)
                    if (isBorder) {{
                        var opt = document.createElement('option');
                        opt.value = layer.feature.properties.NAMN;
                        opt.innerHTML = layer.feature.properties.NAMN;
                        select.appendChild(opt);
                    }}

                    if (!layer.defaultStyle) {{
                        layer.defaultStyle = {{ weight: layer.options.weight, color: layer.options.color, fillOpacity: layer.options.fillOpacity }};
                    }}
                    
                    // Hover-effekt
                    layer.off('mouseover').on('mouseover', function(e) {{
                        var currentOpacity = document.getElementById('opacitySlider').value;
                        this.setStyle({{ weight: 3, color: '#ffeb3b', fillOpacity: Math.min(1.0, parseFloat(currentOpacity) + 0.3) }});
                        if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) this.bringToFront();
                    }});
                    
                    layer.off('mouseout').on('mouseout', function(e) {{
                        var currentOpacity = document.getElementById('opacitySlider').value;
                        // Återställ till rätt opacitet beroende på om det är kant eller fylld polygon
                        this.setStyle({{ weight: layer.defaultStyle.weight, color: layer.defaultStyle.color, fillOpacity: isBorder ? 0 : currentOpacity }});
                    }});
                    
                    // Klick för Info-panel
                    layer.off('click').on('click', function(e) {{
                        showAreaInfo(layer.feature.properties.NAMN);
                        L.DomEvent.stopPropagation(e);
                    }});
                }}
            }});
            
            // Sortera dropdown
            var options = Array.from(select.options);
            var first = options.shift();
            options.sort((a,b) => a.text.localeCompare(b.text, 'sv'));
            select.innerHTML = ''; select.appendChild(first);
            options.forEach(opt => select.appendChild(opt));
        }}
        setTimeout(bindPolygonEvents, 1000);

        // 5. KONTROLLER (Checkboxar, Sliders, Bakgrund)
        // Bakgrund
        var tileBlek = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{ attribution: '&copy; CARTO' }}).addTo(map);
        var tileFarg = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ attribution: '&copy; OSM' }});
        var tileFlyg = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{ attribution: '&copy; Esri' }});

        document.getElementById('basemapSelect').addEventListener('change', function(e) {{
            map.removeLayer(tileBlek); map.removeLayer(tileFarg); map.removeLayer(tileFlyg);
            if(e.target.value === 'blek') tileBlek.addTo(map);
            else if(e.target.value === 'farg') tileFarg.addTo(map);
            else if(e.target.value === 'flyg') tileFlyg.addTo(map);
            
            var borderColor = (e.target.value === 'flyg') ? '#ffffff' : '#2c3e50';
            map.eachLayer(function(layer) {{
                if (layer.options && layer.options.className && layer.options.className.includes('border-polygon')) {{
                    layer.setStyle({{color: borderColor}});
                    if (layer.defaultStyle) layer.defaultStyle.color = borderColor;
                }}
            }});
        }});

        // Opacitet SEI
        document.getElementById('opacitySlider').addEventListener('input', function(e) {{
            var val = parseFloat(e.target.value);
            seiLayerGroup.eachLayer(function(layer) {{
                layer.setStyle({{fillOpacity: val}});
                if(layer.defaultStyle) layer.defaultStyle.fillOpacity = val;
            }});
        }});

        // Toggla SEI Lager
        document.getElementById('toggleSei').addEventListener('change', function(e) {{
            if(e.target.checked) {{
                seiLayerGroup.eachLayer(l => l.setStyle({{fillOpacity: document.getElementById('opacitySlider').value}}));
                document.getElementById('legend-container').style.display = 'flex';
            }} else {{
                seiLayerGroup.eachLayer(l => l.setStyle({{fillOpacity: 0}}));
                document.getElementById('legend-container').style.display = 'none';
            }}
        }});

        // Zoom dropdown
        document.getElementById('zoomSelect').addEventListener('change', function(e) {{
            var namn = e.target.value;
            if(!namn) return;
            map.eachLayer(function(layer) {{
                if (layer.feature && layer.feature.properties && layer.feature.properties.NAMN === namn) {{
                    map.fitBounds(layer.getBounds(), {{padding: [50,50]}});
                    showAreaInfo(namn);
                }}
            }});
        }});

        // 6. INFRASTRUKTUR & POI LOGIK (Mockups/Stubs från tidigare)
        var transportLayer = L.geoJSON(transportData.features.length ? transportData : null, {{style: {{color: '#555', weight: 2}}}});
        var vattenLayer = L.geoJSON(vattenData.features.length ? vattenData : null, {{style: {{color: '#3498db', weight: 2}}}});
        
        document.getElementById('toggleTransport').addEventListener('change', e => e.target.checked ? transportLayer.addTo(map) : map.removeLayer(transportLayer));
        document.getElementById('toggleVatten').addEventListener('change', e => e.target.checked ? vattenLayer.addTo(map) : map.removeLayer(vattenLayer));
        
        // Återställ-knapp
        document.getElementById('btn-reset').addEventListener('click', function() {{
            map.setView([58.4102, 15.6216], 11);
            closeInfoPanel();
            document.getElementById('zoomSelect').value = "";
        }});

    }});
</script>
"""

m.get_root().html.add_child(folium.Element(ui_html))
html_out_path = os.path.join(moder_mapp, OUT_HTML_NAME)
m.save(html_out_path)
print(f"\n✅ Klar! SEI-Kartan har sparats som:\n{html_out_path}")