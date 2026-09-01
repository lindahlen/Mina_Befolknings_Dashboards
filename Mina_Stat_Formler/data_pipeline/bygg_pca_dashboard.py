import os
import pandas as pd
import geopandas as gpd
import folium
import branca.colormap as cm

# --- 1. SÄKERSTÄLL SÖKVÄG ---
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
except NameError:
    pass

print("🚀 Startar bygge av Dashboard med ny Brun-Blå färgskala för Faktor 3...")

parent_folder = os.path.dirname(current_folder)
file_base = os.path.join(parent_folder, "segregation_base.csv")
file_pca = os.path.join(parent_folder, "pca_faktorer_linkoping.csv")

# --- KONTROLLPANEL FÖR OMRÅDEN ---
# 1. Nybyggda områden som ska döljas före ett visst år
exkludera_omraden = {
    'djurgården centrum': 2025,
    'folkungavallen': 2025,
    'skogsvallen': 2022,
    'ebbepark': 2021,
    'vallastaden': 2017,
    'stångebro östra': 2016
}

# 2. TILLFÄLLIG PAUS: Helt tom eftersom matematiken nu är åtgärdad
pausade_omraden = [
    'kanaljorden' # Byt ut detta mot det faktiska namnet (gemener)
]

# 1. LÄS IN OCH TVÄTTA DATA
df_base = pd.read_csv(file_base, encoding='utf-8')
if len(df_base.columns) < 5:
    df_base = pd.read_csv(file_base, encoding='utf-8', sep=';')
df_base.columns = df_base.columns.str.strip().str.lower()
df_pca = pd.read_csv(file_pca, encoding='utf-8')

df_final = pd.merge(df_base, df_pca, on=['basområde', 'tid'], how='left')
df_final['match_namn'] = df_final['basområde'].astype(str).str.strip().str.lower()

# --- AUTOMATISK TIDS-LOGIK ---
alla_ar = sorted(df_final[df_final['PCA_Faktor_1'].notna()]['tid'].unique().tolist())
senaste_aret = max(alla_ar) if alla_ar else 2024

if senaste_aret >= 2025:
    valda_ar_temp = [2015, 2020, 2025]
else:
    valda_ar_temp = [2015, 2019, 2024] 

valda_ar = [ar for ar in valda_ar_temp if ar in alla_ar]
visnings_ar = senaste_aret if senaste_aret in valda_ar else (valda_ar[-1] if valda_ar else 2024)

# Letar efter NYKO3/Stadsdel kolumn
stadsdel_col = None
for col in ['nyko 3', 'nyko3', 'stadsdel', 'område']:
    if col in df_final.columns:
        stadsdel_col = col
        break

# 2. LÄS IN KARTAN
geojson_path = os.path.join(parent_folder, "Kartor", "kart_filer", "NYKO4v23.geojson")
nyko_gdf = gpd.read_file(geojson_path)
nyko_gdf['match_namn'] = nyko_gdf['NAMN'].astype(str).str.strip().str.lower()

# ==========================================
# GEOMETRISK BANTNING (Snabbare webbkarta)
# ==========================================
# (Kontrollera att din variabel heter 'gdf'. Om den heter något annat, t.ex. 'geo_data', byt ut 'gdf' mot det!)

print("⏳ Bantar kartans geometri för blixtsnabb laddning...")

# 1. Byt till SWEREF 99 TM (EPSG:3006) enligt Master Config (så vi kan mäta i meter)
nyko_gdf = nyko_gdf.to_crs(epsg=3006)

# 2. Förenkla! 1.5 meters tolerans raderar tiotusentals onödiga punkter på raka sträckor
nyko_gdf.geometry = nyko_gdf.geometry.simplify(1.5)

# 3. Byt tillbaka till WGS84 (EPSG:4326) som webbläsaren och Folium kräver
nyko_gdf = nyko_gdf.to_crs(epsg=4326)

print("✅ Geometri bantad!")

# ==========================================
# Därefter följer ditt vanliga KARTBYGGE
# ==========================================
# m = folium.Map(...) 
# folium.TileLayer(...).add_to(m)
# folium.GeoJson(gdf, smooth_factor=2.0 ...).add_to(m)

# 3. KARTBYGGE (Sätt global max_zoom till 19 för att tillåta djupdykning)

m = folium.Map(location=[58.4108, 15.6214], zoom_start=11, max_zoom=19, tiles=None)

# CartoDB Positron (Direkt-URL som är supersnabb och blockerar API-krav)
folium.TileLayer(
    tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    attr='&copy; OpenStreetMap contributors &copy; CARTO',
    name='Blek (CartoDB Positron)',
    control=True,
    show=True,
    max_zoom=19
).add_to(m)

# Färgstark OpenStreetMap som valbart alternativ (stöder naturligt zoom 19)
folium.TileLayer(
    'OpenStreetMap', 
    name='Färgstark (Detaljerad)', 
    control=True, 
    show=False,
    max_zoom=19
).add_to(m)

# --- KONFIGURATION (Uppdaterad till Brun -> Vit -> Blå) ---
faktor_configs = [
    {
        'col': 'PCA_Faktor_1', 'ui_name': 'Faktor 1_ Socioekonomi', 'short': 'Faktor 1',
        'colors': ['#1a9850', '#ffffff', '#d73027'], 
        'vars': [('Barnfattigdom (%)', 'barnfattigdom'), ('Ej självförsörjande (%)', 'ej självförsörjande'), ('Nettoinkomst (tkr)', 'nettoinkomst (tkr)')]
    },
    {
        'col': 'PCA_Faktor_2', 'ui_name': 'Faktor 2_ Demografi', 'short': 'Faktor 2',
        'colors': ['#5e3c99', '#ffffff', '#e66101'], 
        'vars': [('Skolungdomar 6-15 (%)', 'skolungdomar 6-15 år'), ('Förgymnasial utb 20-64 år (%)', 'förgymnasial utbildning'), ('Små bostäder (%)', 'små bostäder')]
    },
    {
        'col': 'PCA_Faktor_3', 'ui_name': 'Faktor 3_ Livsfas & Bebyggelse', 'short': 'Faktor 3',
        'colors': ['#2166ac', '#ffffff', '#8c510a'], # Justera ordningen (Blå/Brun) om axeln är flippad i kartan
        'vars': [
            ('Äldre 80+ (%)', 'äldre 80+ år'), 
            ('Bostadsyta (kvm/pers)', 'kvm per person'), 
            ('Utrikes födda (%)', 'utrikes födda')
        ]
    }
]

# 4. SKAPA LAGER FÖR VARJE ÅR OCH FAKTOR
for config in faktor_configs:
    col = config['col']
    
    # FIX: Vi använder percentiler (2% till 98%) istället för absolut min/max. 
    # Detta skär bort extremerna och tvingar fram färgnyanserna!
    min_val = df_final[col].quantile(0.02)
    max_val = df_final[col].quantile(0.98)
    
    # Tvinga mitten att vara 0 för att färgerna ska balanseras korrekt
    max_abs = max(abs(min_val), abs(max_val))
    min_val = -max_abs
    max_val = max_abs
    mid_val = 0 
    
    colormap = cm.LinearColormap(
        colors=config['colors'], index=[min_val, mid_val, max_val],
        vmin=min_val, vmax=max_val, caption=config['ui_name'].replace('_', ':')
    )
    colormap.add_to(m)
    
    for year in valda_ar:
        df_year = df_final[df_final['tid'] == year].copy()
        merged_gdf = nyko_gdf.merge(df_year, on='match_namn', how='left')
        
        layer_name = f"{year}_{config['short']}"
        fg = folium.FeatureGroup(name=layer_name, control=True, show=False)
        
        for idx, row in merged_gdf.iterrows():
            if row['geometry'] is None: continue
            
            omrade_namn = row['match_namn']
            
            # --- TILLÄMPA PAUS OCH EXKLUDERING ---
            if omrade_namn in pausade_omraden:
                continue 
                
            if omrade_namn in exkludera_omraden:
                if year < exkludera_omraden[omrade_namn]:
                    continue 
            
            all_nan = True
            for _, var_db in config['vars']:
                if not pd.isna(row.get(var_db, float('nan'))):
                    all_nan = False
                    break
            
            if all_nan or pd.isna(row[col]): 
                continue 
            
            score = row[col]
            var_html = ""
            for var_label, var_db in config['vars']:
                val = row.get(var_db, float('nan'))
                val_str = f"{val:.1f}" if not pd.isna(val) else "NaN"
                var_html += f'<tr><td style="padding:3px; border-bottom: 1px solid #ddd;">{var_label}</td><td style="text-align:right; border-bottom: 1px solid #ddd;">{val_str}</td></tr>'
            
            nyko3_namn = row.get(stadsdel_col, '') if stadsdel_col else ''
            display_namn = f"{row['NAMN']} ({nyko3_namn})" if pd.notna(nyko3_namn) and nyko3_namn != '' else row['NAMN']

            html = f"""
            <div style="font-family: Arial; width: 250px;">
                <h4 style="margin: 0 0 5px 0; color: #333;">{display_namn}</h4>
                <div style="font-weight: bold; margin-bottom: 10px; color: #555;">{config['ui_name'].replace('_', ':')}: {score:.2f}</div>
                <table style="width: 100%; font-size: 11px; border-collapse: collapse;">{var_html}</table>
            </div>
            """
            
            fill_color = colormap(score)
            geo_json = folium.GeoJson(
                row['geometry'],
                style_function=lambda x, color=fill_color: {'fillColor': color, 'color': '#333', 'weight': 1, 'fillOpacity': 0.8, 'className': 'pca-polygon'}
            )
            
            tooltip = folium.Tooltip(display_namn)
            tooltip.add_to(geo_json)
            
            popup = folium.Popup(html, max_width=300)
            popup.add_to(geo_json)
            geo_json.add_to(fg)
        fg.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

# 5. UI & JAVASCRIPT
options_html = "".join([f'<option value="{y}" {"selected" if y == visnings_ar else ""}>{y}</option>' for y in reversed(valda_ar)])

ui_html = f"""
<style>
    .leaflet-control-layers {{ display: none !important; }}
    
    .left-info-panel {{ position: fixed; bottom: 40px; left: 40px; z-index: 9999; background: rgba(255,255,255,0.95); padding: 25px; border-radius: 8px; box-shadow: 0 0 20px rgba(0,0,0,0.3); width: 370px; font-family: Arial, sans-serif; }}
    .factor-text {{ display: none; font-size: 13px; color: #444; line-height: 1.5; }}
    .factor-text h4 {{ margin: 0 0 10px 0; color: #2c3e50; font-size: 16px; border-bottom: 1px solid #ddd; padding-bottom: 5px; font-weight: bold; }}
    .factor-text p {{ margin-bottom: 8px; }}
    
    .right-control-panel {{ position: fixed; top: 20px; right: 20px; z-index: 9999; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; box-shadow: 0 0 20px rgba(0,0,0,0.3); width: 280px; font-family: Arial, sans-serif; }}
    .control-section {{ margin-bottom: 15px; border-bottom: 1px solid #ddd; padding-bottom: 15px; }}
    .control-section:last-child {{ border: none; margin: 0; padding: 0; }}
    .control-title {{ font-size: 12px; font-weight: bold; color: #333; margin-bottom: 8px; text-transform: uppercase; }}
    
    .form-check {{ margin-bottom: 8px; display: flex; align-items: center; cursor: pointer; }}
    .form-check-label {{ display: flex; align-items: center; font-size: 13px; cursor: pointer; color: #333; }}
    .form-check-input {{ margin-right: 8px; cursor: pointer; width: 16px; height: 16px; }}
    .color-dot {{ display: inline-block; width: 14px; height: 14px; border-radius: 50%; margin-right: 8px; border: 1px solid #ccc; }}
    
    .year-select {{ width: 100%; padding: 6px; border-radius: 4px; border: 1px solid #ccc; font-size: 13px; font-weight: bold; margin-bottom: 5px; cursor: pointer; }}
    
    .legend-container {{ position: fixed; bottom: 30px; right: 20px; width: 280px; z-index: 9998; background: rgba(255,255,255,0.95); padding: 10px; border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.2); pointer-events: auto; display: flex; flex-direction: column; gap: 8px; max-height: 50vh; overflow-y: auto; }}
    .legend {{ box-shadow: none !important; margin: 0 !important; background: transparent !important; display: block !important; width: 100% !important; }}
</style>

<div class="left-info-panel">
    <h3 id="dashboard-title" style="margin-top: 0; color: #2c3e50; margin-bottom: 15px; font-weight: bold;">Segregationsanalys {visnings_ar}</h3>
    
    <div id="text-1" class="factor-text" style="display: block;">
        <h4>Faktor 1: Socioekonomi & Utsatthet</h4>
        <p>Denna faktor förklarar kommunens största strukturella klyfta. Höga värden (röda) präglas av barnfattigdom, låg ekonomisk standard och en hög andel som ej är självförsörjande.</p>
        <p><b><span style="color:#1a9850;">Grön (Minus):</span></b> Resursstarka områden med hög nettoinkomst, högt bilinnehav och hög andel kvarboende över tid.</p>
        <p><b><span style="color:#d73027;">Röd (Plus):</span></b> Områden med hög strukturell utsatthet, barnfattigdom och lägre genomsnittsinkomster.</p>
    </div>
    
    <div id="text-2" class="factor-text">
        <h4>Faktor 2: Demografi & Utbildning</h4>
        <p>Denna faktor ställer studenter och unga vuxna mot områden med fler skolungdomar och en generellt lägre formell utbildningsnivå.</p>
        <p><b><span style="color:#5e3c99;">Lila (Minus):</span></b> Drivs starkt av små bostäder, ensamstående hushåll och hög andel med lång eftergymnasial utbildning (ofta utpräglade studentområden).</p>
        <p><b><span style="color:#e66101;">Orange (Plus):</span></b> Områden med många skolungdomar (6-15 år), hög andel förgymnasial utbildning och UVAS.</p>
    </div>
    
    <div id="text-3" class="factor-text">
        <h4>Faktor 3: Livsfas & Bebyggelse</h4>
        <p>Denna faktor separerar äldre, etablerade bostadsområden från yngre och mer internationella områden.</p>
        <p><b><span style="color:#2166ac;">Blå (Minus):</span></b> Drivs primärt av många skolungdomar, en hög andel utrikes födda och lång eftergymnasial utbildning.</p>
        <p><b><span style="color:#8c510a;">Brun (Plus):</span></b> Kännetecknas av en hög andel äldre (80+), mycket bostadsyta per person och ett högre ohälsotal i åldern 50-64 år.</p>
    </div>
</div>

<div class="right-control-panel">
    <div class="control-section">
        <div class="control-title">1. Välj År</div>
        <select id="year-dropdown" class="year-select">
            {options_html}
        </select>
    </div>
    
    <div class="control-section">
        <div class="control-title">2. Välj Data (Faktor)</div>
        <div class="form-check">
            <input class="form-check-input custom-data" type="radio" name="faktor_val" value="1" id="f_1" checked>
            <label class="form-check-label" for="f_1"><span class="color-dot" style="background:#1a9850;"></span> Faktor 1: Socioekonomi</label>
        </div>
        <div class="form-check">
            <input class="form-check-input custom-data" type="radio" name="faktor_val" value="2" id="f_2">
            <label class="form-check-label" for="f_2"><span class="color-dot" style="background:#5e3c99;"></span> Faktor 2: Demografi</label>
        </div>
        <div class="form-check">
            <input class="form-check-input custom-data" type="radio" name="faktor_val" value="3" id="f_3">
            <label class="form-check-label" for="f_3"><span class="color-dot" style="background:#2166ac;"></span> Faktor 3: Livsfas & Bebyggelse</label>
        </div>
    </div>
    
    <div class="control-section">
        <div class="control-title">3. Bakgrundskarta</div>
        <div class="form-check">
            <input class="form-check-input bg-toggle" type="radio" name="bg_val" value="Blek" id="bg_b" checked>
            <label class="form-check-label" for="bg_b">Blek (Tydlig analys)</label>
        </div>
        <div class="form-check">
            <input class="form-check-input bg-toggle" type="radio" name="bg_val" value="Färgstark" id="bg_f">
            <label class="form-check-label" for="bg_f">Färgstark (Detaljerad)</label>
        </div>
    </div>
    
    <div class="control-section" style="margin-bottom:0; border-bottom:none; padding-bottom:0;">
        <div class="control-title">4. Opacitet</div>
        <input type="range" id="opacity-slider" min="0.1" max="1.0" step="0.1" value="0.8" style="width:100%;">
    </div>
</div>
<div class="legend-container" id="legend-container"></div>

<script>
    function clickHiddenFoliumMenu(nameToMatch, turnOn) {{
        var foliumLabels = document.querySelectorAll('.leaflet-control-layers label');
        foliumLabels.forEach(function(label) {{
            if (label.innerText.includes(nameToMatch)) {{
                var checkbox = label.querySelector('input');
                if (checkbox) {{
                    if (turnOn && !checkbox.checked) checkbox.click();
                    if (!turnOn && checkbox.checked) checkbox.click();
                }}
            }}
        }});
    }}

    window.addEventListener('load', function() {{
        setTimeout(function() {{
            
            var legends = document.querySelectorAll('.legend');
            var container = document.getElementById('legend-container');
            legends.forEach(function(l) {{ container.appendChild(l); }});
            
            var availableYears = {valda_ar};
            var latestYear = '{visnings_ar}';
            
            // Stäng av alla faktor-lager först
            availableYears.forEach(y => {{
                ['1', '2', '3'].forEach(f => {{
                    clickHiddenFoliumMenu(y + '_Faktor ' + f, false);
                }});
            }});
            
            // Slå endast på det valda året och faktor 1 vid start
            clickHiddenFoliumMenu(latestYear + '_Faktor 1', true);
            clickHiddenFoliumMenu('Färgstark', false);
            
            function updateMapData() {{
                var selectedYear = document.getElementById('year-dropdown').value;
                var selectedFactor = document.querySelector('.custom-data:checked').value;
                
                // Fetstil för rubriken uppdateras
                document.getElementById('dashboard-title').innerHTML = '<b>Segregationsanalys ' + selectedYear + '</b>';
                
                availableYears.forEach(y => {{
                    ['1', '2', '3'].forEach(f => {{
                        clickHiddenFoliumMenu(y + '_Faktor ' + f, false);
                    }});
                }});
                
                clickHiddenFoliumMenu(selectedYear + '_Faktor ' + selectedFactor, true);
                
                document.querySelectorAll('.factor-text').forEach(el => el.style.display = 'none');
                document.getElementById('text-' + selectedFactor).style.display = 'block';
                
                setTimeout(updateOpacity, 100);
            }}

            document.getElementById('year-dropdown').addEventListener('change', updateMapData);
            document.querySelectorAll('.custom-data').forEach(radio => radio.addEventListener('change', updateMapData));

            document.querySelectorAll('.bg-toggle').forEach(function(radio) {{
                radio.addEventListener('change', function(e) {{
                    var isBlek = e.target.value === 'Blek';
                    clickHiddenFoliumMenu('Blek', isBlek);
                    clickHiddenFoliumMenu('Färgstark', !isBlek);
                }});
            }});

            function updateOpacity() {{
                var op = document.getElementById('opacity-slider').value;
                document.querySelectorAll('path.pca-polygon').forEach(function(el) {{
                    el.style.fillOpacity = op;
                }});
            }}
            document.getElementById('opacity-slider').addEventListener('input', updateOpacity);
            updateOpacity();

        }}, 1000); 
    }});
</script>
"""
m.get_root().html.add_child(folium.Element(ui_html))
output_map = os.path.join(parent_folder, "Linkoping_PCA_Dashboard.html")
m.save(output_map)
print(f"💾 Proxy-Dashboard uppdaterad med korrekt matematik, texter och popups!")