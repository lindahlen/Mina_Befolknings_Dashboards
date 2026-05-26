# -*- coding: utf-8 -*-
import os
import sys
import re
import json
import math
import pandas as pd

# ==========================================
# 1. GENERELL SETUP
# ==========================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
except NameError:
    current_folder = os.getcwd()

encoding_fix = {
    'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
    'Ã©': 'é', 'Ãè': 'è', 'Ã‰': 'É', "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö"
}

def fix_text(text):
    if not isinstance(text, str): return text
    for bad, good in encoding_fix.items():
        text = text.replace(bad, good)
    return text

# ==========================================
# 2. GENERISK PX-PARSER
# ==========================================
def parse_generic_px(filepath):
    print(f" -> Tolkar {os.path.basename(filepath)}...")
    with open(filepath, 'r', encoding='latin1') as f:
        content = f.read()

    stub_match = re.search(r'STUB=([^;]+);', content)
    heading_match = re.search(r'HEADING=([^;]+);', content)

    stubs = [x.strip('"') for x in stub_match.group(1).split(',')] if stub_match else []
    headings = [x.strip('"') for x in heading_match.group(1).split(',')] if heading_match else []
    dimensions = stubs + headings

    dim_values = {}
    for dim in dimensions:
        val_match = re.search(rf'VALUES\("{dim}"\)=\s*([^;]+);', content, re.IGNORECASE | re.DOTALL)
        if val_match:
            vals = re.findall(r'"([^"]*)"', val_match.group(1))
            dim_values[dim] = [fix_text(v).strip() for v in vals]

    data_match = re.search(r'DATA=\s*([^;]+);', content, re.DOTALL)
    data_str = data_match.group(1).split()
    
    data_series = pd.Series(data_str).str.replace('"', '')
    data_values = pd.to_numeric(data_series, errors='coerce').values

    levels = [dim_values[dim] for dim in dimensions]
    index = pd.MultiIndex.from_product(levels, names=[d for d in dimensions])

    df = pd.DataFrame({'Antal': data_values}, index=index).reset_index()
    
    # Standardisera kolumnnamn
    rename_dict = {}
    for col in df.columns:
        clower = col.lower()
        if clower in ['tid', 'år', 'year']: rename_dict[col] = 'Tid'
        elif 'ålder' in clower or 'age' in clower: rename_dict[col] = 'Ålder'
        elif 'kön' in clower or 'sex' in clower: rename_dict[col] = 'Kön'
        elif 'riktning' in clower: rename_dict[col] = 'Riktning'
        elif 'relation' in clower: rename_dict[col] = 'Relation'
        elif 'flyttningsrelation' in clower: rename_dict[col] = 'Relation'
        elif 'tabelluppgift' in clower: rename_dict[col] = 'Tabelluppgift'
        
    df.rename(columns=rename_dict, inplace=True)
    return df

# ==========================================
# 3. KATEGORISERING & DATA MERGE
# ==========================================
def extract_age(age_str):
    s = str(age_str).lower()
    if 'totalt' in s: return -1
    match = re.search(r'(\d+)', s)
    return int(match.group(1)) if match else -1

def build_mig_groups(df):
    groups = []
    # 20-24 år
    g1 = df[(df['Ålder_Int'] >= 20) & (df['Ålder_Int'] <= 24)].copy()
    g1['Mig_Åldersgrupp'] = 'Kvinnor 20-24 år'
    groups.append(g1)
    # 25-29 år
    g2 = df[(df['Ålder_Int'] >= 25) & (df['Ålder_Int'] <= 29)].copy()
    g2['Mig_Åldersgrupp'] = 'Kvinnor 25-29 år'
    groups.append(g2)
    # 30-34 år
    g3 = df[(df['Ålder_Int'] >= 30) & (df['Ålder_Int'] <= 34)].copy()
    g3['Mig_Åldersgrupp'] = 'Kvinnor 30-34 år'
    groups.append(g3)
    # 20-29 år
    g4 = df[(df['Ålder_Int'] >= 20) & (df['Ålder_Int'] <= 29)].copy()
    g4['Mig_Åldersgrupp'] = 'Kvinnor 20-29 år'
    groups.append(g4)
    # 20-34 år
    g5 = df[(df['Ålder_Int'] >= 20) & (df['Ålder_Int'] <= 34)].copy()
    g5['Mig_Åldersgrupp'] = 'Kvinnor 20-34 år'
    groups.append(g5)
    
    df_grouped = pd.concat(groups)
    return df_grouped.groupby(['Tid', 'Relation', 'Mig_Åldersgrupp'])['Antal'].sum().reset_index()

def map_birth_age(age_int):
    if age_int < 0: return 'Totalt antal födda'
    if age_int < 25: return 'Mödrar under 25 år'
    if 25 <= age_int <= 29: return 'Mödrar 25-29 år'
    if 30 <= age_int <= 34: return 'Mödrar 30-34 år'
    if age_int >= 35: return 'Mödrar 35+ år'
    return 'Övriga'

def get_time_series(df_tfr):
    """ Extraherar data för TFR och Totalt antal födda över tid per åldersgrupp """
    df_ts = df_tfr.copy()
    df_ts['Ålder_Int'] = df_ts['Ålder'].apply(extract_age)
    df_ts['Tid'] = df_ts['Tid'].astype(str).str.extract(r'(\d{4})')[0].astype(int)
    df_ts['Födda_Grupp'] = df_ts['Ålder_Int'].apply(map_birth_age)
    
    tfr_js = {}
    births_js = {}
    
    # Summerad fruktsamhet (TFR) per målgrupp
    df_frukt = df_ts[df_ts['Tabelluppgift'].str.lower() == 'fruktsamhet']
    for grp in df_frukt['Födda_Grupp'].unique():
        df_g = df_frukt[df_frukt['Födda_Grupp'] == grp]
        agg = df_g.groupby('Tid')['Antal'].sum().reset_index()
        # Justera om TFR är angett per 1000 kvinnor (värde > 100)
        tfr_js[grp] = [{'x': int(r.Tid), 'y': float(r.Antal)/1000.0 if float(r.Antal)>100 else float(r.Antal)} for r in agg.itertuples()]
    
    # Totalt antal födda per målgrupp
    df_born = df_ts[df_ts['Tabelluppgift'].str.lower() == 'födda barn']
    for grp in df_born['Födda_Grupp'].unique():
        df_g = df_born[df_born['Födda_Grupp'] == grp]
        agg = df_g.groupby('Tid')['Antal'].sum().reset_index()
        births_js[grp] = [{'x': int(r.Tid), 'y': int(r.Antal)} for r in agg.itertuples()]
    
    return tfr_js, births_js

def prepare_merged_data(df_mig, df_tfr):
    print("Samkör flyttdata med födelsedata och bygger tidsfördröjningar (lags)...")
    
    # 1. PREPPA FLYTTDATA
    if 'Kön' in df_mig.columns:
        df_mig = df_mig[df_mig['Kön'].str.lower() == 'kvinnor'].copy()
        
    df_mig = df_mig[df_mig['Riktning'].str.title() == 'Inflyttning'].copy()
    df_mig['Ålder_Int'] = df_mig['Ålder'].apply(extract_age)
    df_mig['Tid'] = df_mig['Tid'].astype(str).str.extract(r'(\d{4})')[0].astype(int)
    
    # FIX: Ta bort data före 2002 för länsuppdelning, då detta saknas hos SCB och ger missvisande 0-värden
    mask_to_drop = (df_mig['Relation'].isin(['Eget län', 'Annat län'])) & (df_mig['Tid'] < 2002)
    df_mig = df_mig[~mask_to_drop].copy()
    
    df_mig_agg = build_mig_groups(df_mig)
    df_mig_agg.rename(columns={'Antal': 'Antal_Inflyttade'}, inplace=True)

    # 2. PREPPA FÖDELSEDATA
    df_tfr = df_tfr[df_tfr['Tabelluppgift'].str.lower() == 'födda barn'].copy()
    df_tfr['Ålder_Int'] = df_tfr['Ålder'].apply(extract_age)
    df_tfr['Tid'] = df_tfr['Tid'].astype(str).str.extract(r'(\d{4})')[0].astype(int)
    
    df_tfr['Födda_Grupp'] = df_tfr['Ålder_Int'].apply(map_birth_age)
    df_tfr_agg = df_tfr.groupby(['Tid', 'Födda_Grupp'])['Antal'].sum().reset_index()
    df_tfr_agg.rename(columns={'Antal': 'Antal_Födda'}, inplace=True)

    # 3. MERGE MED TIDSFÖRDRÖJNING
    all_lags = []
    for lag in range(0, 6):
        df_tfr_lagged = df_tfr_agg.copy()
        df_tfr_lagged['Tid_Match'] = df_tfr_lagged['Tid'] - lag 
        df_tfr_lagged['Tid_Födda'] = df_tfr_lagged['Tid']
        df_tfr_lagged.drop(columns=['Tid'], inplace=True)
        
        df_m = pd.merge(df_mig_agg, df_tfr_lagged, left_on='Tid', right_on='Tid_Match', how='inner')
        df_m['Lag_Years'] = lag
        all_lags.append(df_m)
        
    df_final = pd.concat(all_lags, ignore_index=True)
    return df_final

# ==========================================
# 4. SÄKER STATISTISK ANALYS
# ==========================================
def safe_math_regression(x, y):
    n = len(x)
    if n < 2: return 0.0, 0.0, 0.0, 0.0
    x_mean = sum(x) / n
    y_mean = sum(y) / n
    numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
    sum_sq_x = sum((xi - x_mean)**2 for xi in x)
    sum_sq_y = sum((yi - y_mean)**2 for yi in y)
    if sum_sq_x == 0 or sum_sq_y == 0: return 0.0, 0.0, 0.0, 0.0
    r = numerator / math.sqrt(sum_sq_x * sum_sq_y)
    r_squared = r**2
    m = numerator / sum_sq_x
    b = y_mean - m * x_mean
    return float(r), float(r_squared), float(m), float(b)

def perform_analysis(df_merged):
    print("Kör regressionsmodeller för samtliga ålderskombinationer, perioder och fördröjningar...")
    
    mig_groups = df_merged['Mig_Åldersgrupp'].unique().tolist()
    birth_groups = df_merged['Födda_Grupp'].unique().tolist()
    relationer = df_merged['Relation'].unique().tolist()
    lags = sorted(df_merged['Lag_Years'].unique().tolist())
    
    # Nya smarta tidsperioder baserade på folkbokföring och studenttrender
    time_windows = {
        'Alla år': 0,
        '1968-1994': (1968, 1994),
        '1995-Nu': (1995, 2030),
        '1968-1999': (1968, 1999),
        '2000-Nu': (2000, 2030),
        'Senaste 25 åren': 25,
        'Senaste 10 åren': 10
    }
    
    charts_data = []

    for relation in relationer:
        for m_grp in mig_groups:
            for b_grp in birth_groups:
                for period_name, config in time_windows.items():
                    
                    df_sub = df_merged[(df_merged['Relation'] == relation) & 
                                       (df_merged['Mig_Åldersgrupp'] == m_grp) & 
                                       (df_merged['Födda_Grupp'] == b_grp)]
                    if df_sub.empty: continue
                    
                    # Applicera tidsfilter
                    if isinstance(config, tuple):
                        df_period = df_sub[(df_sub['Tid'] >= config[0]) & (df_sub['Tid'] <= config[1])]
                    elif config > 0:
                        max_year = df_sub['Tid'].max()
                        df_period = df_sub[df_sub['Tid'] > (max_year - config)]
                    else:
                        df_period = df_sub
                        
                    if df_period.empty: continue
                    
                    lag_profile = []
                    best_lag = 0
                    best_r2 = -1.0
                    
                    # Bygg profilen för inkubationsgrafen
                    for lag in lags:
                        df_lag = df_period[df_period['Lag_Years'] == lag].dropna(subset=['Antal_Inflyttade', 'Antal_Födda'])
                        if len(df_lag) < 2: 
                            lag_profile.append(0.0)
                            continue
                            
                        x_list = df_lag['Antal_Inflyttade'].tolist()
                        y_list = df_lag['Antal_Födda'].tolist()
                        r, r_squared, _, _ = safe_math_regression(x_list, y_list)
                        lag_profile.append(round(r_squared, 3))
                        
                        if r_squared > best_r2:
                            best_r2 = r_squared
                            best_lag = lag

                    # Spara datapunkter för varje lag
                    for lag in lags:
                        df_lag = df_period[df_period['Lag_Years'] == lag].dropna(subset=['Antal_Inflyttade', 'Antal_Födda'])
                        if len(df_lag) < 2: continue
                        
                        x_list = df_lag['Antal_Inflyttade'].tolist()
                        y_list = df_lag['Antal_Födda'].tolist()
                        mig_years = df_lag['Tid'].tolist()
                        birth_years = df_lag['Tid_Födda'].tolist()
                        
                        r, r_squared, m, b = safe_math_regression(x_list, y_list)
                        
                        scatter_pts = [{'x': float(xv), 'y': float(yv), 'mig_year': int(my), 'birth_year': int(by)} 
                                       for xv, yv, my, by in zip(x_list, y_list, mig_years, birth_years)]
                        
                        min_x, max_x = float(min(x_list)), float(max(x_list))
                        line_pts = [
                            {'x': min_x * 0.98, 'y': float(m * (min_x * 0.98) + b)},
                            {'x': max_x * 1.05, 'y': float(m * (max_x * 1.05) + b)}
                        ]
                        
                        chart_id = f"chart_{relation}_{m_grp}_{b_grp}_{period_name}_{lag}".replace(' ', '_').replace('/', '_').replace('å', 'a').replace('+', '_').replace('-', '_')
                        
                        charts_data.append({
                            'id': chart_id,
                            'relation': relation,
                            'mig_group': m_grp,
                            'birth_group': b_grp,
                            'period': period_name,
                            'lag': lag,
                            'lag_profile': lag_profile,
                            'best_lag': best_lag,
                            'scatter': scatter_pts,
                            'line': line_pts,
                            'r2': f"{r_squared:.3f}",
                            'r': f"{r:.3f}",
                            'slope': f"{m:.4f}",
                            'intercept': f"{b:.2f}"
                        })

    return charts_data, relationer, mig_groups, birth_groups, list(time_windows.keys()), lags

# ==========================================
# 5. SKAPA HTML-DASHBOARD OCH EXTERN DATA (.JS)
# ==========================================
def generate_html_report(charts_data, relationer, mig_groups, birth_groups, periods, lags, tfr_js, births_js):
    print("Genererar extern datafil (.js) och dynamisk HTML Dashboard...")
    
    # 1. SKAPA EXTERN DATAFIL (.js för att kringgå lokala CORS-blockeringar)
    js_data_content = f"""// Automatiskt genererad datafil för fruktsamhetsanalys
const chartData = {json.dumps(charts_data)};
const tfrTimeSeries = {json.dumps(tfr_js)};
const birthsTimeSeries = {json.dumps(births_js)};
const birthGroups = {json.dumps(birth_groups)};
"""
    data_path = os.path.join(current_folder, "fruktsamhet_data.js")
    with open(data_path, "w", encoding="utf-8") as f:
        f.write(js_data_content)
    print(f" -> Data sparad i '{data_path}'")

    # 2. SKAPA EXTREMT LÄTTVIKTIG HTML
    def make_opts(items, default=None):
        return "\n".join([f'<option value="{i}" {"selected" if i == default else ""}>{i}</option>' for i in items])

    html_content = f"""
    <!DOCTYPE html>
    <html lang="sv">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Demografisk Analys: Fruktsamhet</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        
        <!-- HÄR LADDAS DATAN IN SEPARAT -->
        <script src="fruktsamhet_data.js"></script>
        
        <style>
            body {{ background-color: #f8f9fa; padding: 20px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
            .card {{ box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: none; }}
            .header-main {{ background-color: #27ae60; color: white; padding: 10px; border-radius: 5px 5px 0 0; }}
            .control-panel {{ background-color: #e9ecef; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 5px solid #27ae60; }}
            h2.section-title {{ color: #27ae60; margin-top: 20px; margin-bottom: 20px; border-bottom: 2px solid #27ae60; padding-bottom: 5px; }}
            .trend-text {{ color: #e74c3c; font-weight: bold; margin-top: 5px; font-size: 0.9em; }}
            
            /* Smarta responsiva filterfält */
            .filter-wrapper {{ display: flex; flex-wrap: wrap; gap: 1rem; }}
            .filter-item {{ flex: 1 1 180px; max-width: 280px; }}
            
            /* Dubbla grafer i korten */
            .dual-chart-container {{ display: flex; flex-direction: column; gap: 15px; }}
            .main-canvas {{ height: 280px; width: 100%; }}
            .mini-canvas {{ height: 120px; width: 100%; border-top: 1px dashed #ccc; padding-top: 10px; }}
            
            /* Styling för dragspel (i-knapp) */
            .accordion-button:not(.collapsed) {{ background-color: #e8f8f5; color: #27ae60; }}
            .accordion-button:focus {{ box-shadow: none; border-color: rgba(39, 174, 96, 0.5); }}
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <!-- TILLBAKA-KNAPPAR -->
            <div class="mb-3 d-flex flex-wrap gap-2">
                <a href="../prognoskalkylator.html" class="btn btn-outline-secondary">&larr; Tillbaka till Prognoskalkylatorn</a>
                <a href="flyttbenagenhet_dashboard.html" class="btn btn-outline-info" style="color: #8e44ad; border-color: #8e44ad;">Gå till Flyttningsbenägenhet (Inrikes)</a>
            </div>
            
            <h1 class="mb-3" style="color: #27ae60;">Analys av Fruktsamhet och Flyttningsmönster</h1>
            <p class="lead">Undersök kommunens barnafödande samt hur inflyttningen av unga vuxna påverkar BB-statistiken.</p>
            
            <!-- UTVIDGAD INFO-PANEL (ACCORDION) -->
            <div class="accordion mb-4" id="infoAccordion">
              <div class="accordion-item" style="border: 1px solid #27ae60;">
                <h2 class="accordion-header" id="headingInfo">
                  <button class="accordion-button collapsed fw-bold" type="button" data-bs-toggle="collapse" data-bs-target="#collapseInfo" aria-expanded="false" aria-controls="collapseInfo" style="color: #27ae60;">
                    ℹ️ Läsguide: Så tolkar du analyserna och diagrammen (Klicka för att fälla ut)
                  </button>
                </h2>
                <div id="collapseInfo" class="accordion-collapse collapse" aria-labelledby="headingInfo" data-bs-parent="#infoAccordion">
                  <div class="accordion-body" style="font-size: 1.05em; line-height: 1.6;">
                    <div class="row">
                        <div class="col-md-6">
                            <h5 style="color: #27ae60;">Fördröjd Fruktsamhet (Inkubationstid)</h5>
                            <p>Ofta dröjer det en tid från det att unga vuxna flyttar till kommunen tills de bildar familj. Denna vy kopplar ihop <strong>inflyttade kvinnor</strong> ett visst år, med antalet <strong>födda barn</strong> upp till 5 år senare.</p>
                            <ul>
                                <li><strong>Huvudgraf (Spridning):</strong> Varje punkt är ett kalenderår. Grafen visar korrelationen mellan volymen inflyttare och volymen barn X år senare.</li>
                                <li><strong>Inkubationsgraf (Staplar):</strong> Visar hur starkt sambandet (R²) är vid de olika fördröjningarna. Den <span style="color: #2980b9; font-weight:bold;">blå stapeln</span> är det starkaste sambandet, och den <span style="color: #e74c3c; font-weight:bold;">röda stapeln</span> är det år du har valt att visa ovan.</li>
                                <li><strong>Trend (Lutning):</strong> Ett trendvärde på <code>0.12</code> innebär att 100 extra inflyttade kvinnor ger ca 12 extra barn under den valda tidsfördröjningen.</li>
                            </ul>
                        </div>
                        <div class="col-md-6 border-start">
                            <h5 style="color: #2980b9;">Summerad Fruktsamhet (TFR)</h5>
                            <p>TFR (Total Fertility Rate) är det klassiska demografiska måttet. Det visar hur många barn en kvinna i genomsnitt förväntas föda under sin livstid, baserat på det aktuella årets fruktsamhetsmönster.</p>
                            <ul>
                                <li>Du kan nu filtrera TFR på specifika åldersgrupper för att se de underliggande trenderna (t.ex. att äldre kvinnors barnafödande ökat medan yngres minskat).</li>
                                <li>För att befolkningen ska hållas konstant på sikt krävs ett totalt TFR på ca <strong>2.1 barn per kvinna</strong>.</li>
                                <li><strong>Tips:</strong> Använd <em>Y-axel Inställningar</em> för att låsa skalan eller lägga till marginal så att jämförelser blir enklare.</li>
                            </ul>
                            <h5 class="mt-4" style="color: #8e44ad;">Totalt Antal Födda Barn</h5>
                            <p>Till skillnad från TFR är detta den <em>faktiska volymen</em> barn som fötts. Genom att byta målgrupp kan du se exakt hur många barn som fötts av mödrar i olika åldersintervall över tid.</p>
                        </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- KONTROLLPANEL FÖR GRAFER (ALLT PÅ EN FLYTANDE RAD) -->
            <div class="control-panel">
                <h5 class="mb-3">Filter och Inställningar:</h5>
                <div class="filter-wrapper align-items-end">
                    
                    <div class="filter-item">
                        <label class="form-label fw-bold text-primary">Diagramtyp / Vy:</label>
                        <select id="select-charttype" class="form-select border-primary" style="background-color: #f0f8ff;">
                            <option value="lag">Fördröjd fruktsamhet (Inkubationstid)</option>
                            <option value="tfr">Summerad fruktsamhet (TFR) över tid</option>
                            <option value="births">Totalt antal födda barn över tid</option>
                        </select>
                    </div>

                    <!-- Tidsperiod (Gäller ALLA grafer) -->
                    <div class="filter-item">
                        <label class="form-label fw-bold" style="color: #d35400;">Tidsperiod (Epok):</label>
                        <select id="select-period" class="form-select border-warning" style="background-color: #fff9e6;">
                            {make_opts(periods, 'Alla år')}
                        </select>
                    </div>
                    
                    <!-- Fält enbart för Tidsserier (TFR/Födda) -->
                    <div class="filter-item ts-control" style="display: none;">
                        <label class="form-label fw-bold text-primary">Målgrupp (Mödrar):</label>
                        <select id="select-ts-age" class="form-select border-primary">
                            {make_opts(birth_groups, 'Totalt antal födda')}
                        </select>
                    </div>

                    <!-- Kryssrutor för Skala & Marginal -->
                    <div class="filter-item ts-control" style="display: none; max-width: 150px;">
                        <label class="form-label fw-bold text-primary">Y-axel Inställningar:</label>
                        <div class="form-check mt-1">
                            <input class="form-check-input border-primary" type="checkbox" id="check-ts-zero">
                            <label class="form-check-label text-primary" for="check-ts-zero" style="font-size: 0.9em;">Utgå från 0</label>
                        </div>
                        <div class="form-check">
                            <input class="form-check-input border-primary" type="checkbox" id="check-ts-fixed">
                            <label class="form-check-label text-primary" for="check-ts-fixed" style="font-size: 0.9em;" title="Låser skalan utifrån din nuvarande vy">Fast skala</label>
                        </div>
                    </div>
                    
                    <div class="filter-item ts-control" style="display: none; max-width: 120px;">
                        <label class="form-label fw-bold text-primary">Marginal:</label>
                        <select id="select-ts-grace" class="form-select border-primary">
                            <option value="0%">0%</option>
                            <option value="5%" selected>5%</option>
                            <option value="10%">10%</option>
                            <option value="20%">20%</option>
                        </select>
                    </div>

                    <!-- Följande tre är enbart för Fördröjd Fruktsamhet -->
                    <div class="filter-item lag-control">
                        <label class="form-label fw-bold">Geografisk Relation:</label>
                        <select id="select-relation" class="form-select border-success">
                            {make_opts(relationer, 'Inrikes totalt')}
                        </select>
                    </div>
                    
                    <div class="filter-item lag-control">
                        <label class="form-label fw-bold">Inflyttade (X-axel):</label>
                        <select id="select-miggroup" class="form-select border-success">
                            {make_opts(mig_groups, 'Kvinnor 20-29 år')}
                        </select>
                    </div>
                    
                    <div class="filter-item lag-control">
                        <label class="form-label fw-bold" style="color: #c0392b;">Tidsfördröjning (Lags):</label>
                        <select id="select-lag" class="form-select" style="border-color: #e74c3c; background-color: #fdedec;">
                            <option value="0">Ingen fördröjning (Samma år)</option>
                            <option value="1">1 år senare</option>
                            <option value="2" selected>2 år senare</option>
                            <option value="3">3 år senare</option>
                            <option value="4">4 år senare</option>
                            <option value="5">5 år senare</option>
                        </select>
                    </div>

                </div>
            </div>

            <h2 class="section-title" id="chart-section-title">Grafer laddas...</h2>
            
            <div class="row" id="charts-container">
                <!-- Javascript skapar rutorna dynamiskt -->
            </div>

        </div>

        <script>
            // Datan (chartData, tfrTimeSeries, birthsTimeSeries, birthGroups) läses nu in via fruktsamhet_data.js
            
            let mainChartInstances = {{}};
            let miniChartInstances = {{}};
            
            let lockedYMin = null;
            let lockedYMax = null;

            document.getElementById('select-charttype').addEventListener('change', function(e) {{
                if (e.target.value === 'births') {{
                    document.getElementById('check-ts-zero').checked = true;
                }} else if (e.target.value === 'tfr') {{
                    document.getElementById('check-ts-zero').checked = false;
                }}
                document.getElementById('check-ts-fixed').checked = false;
            }});

            function renderCharts() {{
                // Fallback om datafilen laddar långsammare (mycket ovanligt lokalt, men säkert)
                if (typeof chartData === 'undefined') {{
                    setTimeout(renderCharts, 100);
                    return;
                }}

                const chartType = document.getElementById('select-charttype').value;
                const periodVal = document.getElementById('select-period').value;
                const container = document.getElementById('charts-container');
                
                const lagControls = document.querySelectorAll('.lag-control');
                const tsControls = document.querySelectorAll('.ts-control');
                
                if(chartType === 'lag') {{
                    lagControls.forEach(el => el.style.display = 'block');
                    tsControls.forEach(el => el.style.display = 'none');
                }} else {{
                    lagControls.forEach(el => el.style.display = 'none');
                    tsControls.forEach(el => el.style.display = 'block');
                }}

                Object.values(mainChartInstances).forEach(c => c.destroy());
                Object.values(miniChartInstances).forEach(c => c.destroy());
                mainChartInstances = {{}};
                miniChartInstances = {{}};
                container.innerHTML = '';

                // RITA STORA TIDSSERIE-DIAGRAM (TFR eller Födda)
                if (chartType === 'tfr' || chartType === 'births') {{
                    const isTfr = chartType === 'tfr';
                    const tsAge = document.getElementById('select-ts-age').value;
                    
                    const isZero = document.getElementById('check-ts-zero').checked;
                    const isFixed = document.getElementById('check-ts-fixed').checked;
                    const graceStr = document.getElementById('select-ts-grace').value;
                    
                    if (!isFixed) {{
                        lockedYMin = null;
                        lockedYMax = null;
                    }}
                    
                    const titleText = isTfr ? 'Summerad Fruktsamhet (TFR)' : 'Totalt Antal Födda Barn';
                    document.getElementById('chart-section-title').innerText = `${{titleText}} | ${{tsAge}} (${{periodVal}})`;
                    
                    container.innerHTML = `
                    <div class="col-12 mb-4">
                        <div class="card" style="border: 2px solid ${{isTfr ? '#2980b9' : '#8e44ad'}};">
                            <div class="card-header bg-light text-center">
                                <strong class="fs-4" style="color: ${{isTfr ? '#2980b9' : '#8e44ad'}};">${{titleText}}: ${{tsAge}}</strong>
                            </div>
                            <div class="card-body p-4">
                                <div style="height: 500px; width: 100%;"><canvas id="chart_main_ts"></canvas></div>
                            </div>
                        </div>
                    </div>
                    `;
                    
                    const ctx = document.getElementById('chart_main_ts').getContext('2d');
                    const tsDataMap = isTfr ? tfrTimeSeries : birthsTimeSeries;
                    let tsData = tsDataMap[tsAge] || [];
                    
                    if (periodVal !== 'Alla år') {{
                        if (periodVal.includes('-')) {{
                            const parts = periodVal.split('-');
                            const start = parseInt(parts[0]);
                            const end = parts[1] === 'Nu' ? 2100 : parseInt(parts[1]);
                            tsData = tsData.filter(d => d.x >= start && d.x <= end);
                        }} else if (periodVal.includes('Senaste')) {{
                            const years = parseInt(periodVal.match(/\d+/)[0]);
                            const maxYear = Math.max(...tsData.map(d => d.x));
                            tsData = tsData.filter(d => d.x > (maxYear - years));
                        }}
                    }}
                    
                    if (isFixed && lockedYMin === null && tsData.length > 0) {{
                        const yVals = tsData.map(d => d.y);
                        const minVal = Math.min(...yVals);
                        const maxVal = Math.max(...yVals);
                        const range = (maxVal - minVal) || 1;
                        const gPct = parseInt(graceStr.replace('%','')) / 100;
                        
                        lockedYMax = maxVal + (range * gPct);
                        
                        if (isZero) {{
                            lockedYMin = 0;
                        }} else {{
                            lockedYMin = minVal - (range * gPct);
                            if (minVal >= 0 && lockedYMin < 0) lockedYMin = 0;
                        }}
                    }}

                    let yConfig = {{
                        title: {{ display: true, text: isTfr ? 'Bidrag till TFR / Barn per kvinna' : 'Antal barn', font: {{weight: 'bold', size: 12}} }},
                        beginAtZero: isZero,
                        grace: isFixed ? undefined : graceStr
                    }};

                    if (isFixed && lockedYMin !== null) {{
                        yConfig.min = lockedYMin;
                        yConfig.max = lockedYMax;
                    }}
                    
                    const lineColor = isTfr ? 'rgba(41, 128, 185, 1)' : 'rgba(142, 68, 173, 1)';
                    const fillColor = isTfr ? 'rgba(41, 128, 185, 0.15)' : 'rgba(142, 68, 173, 0.15)';
                    
                    if(tsData.length > 0) {{
                        mainChartInstances[0] = new Chart(ctx, {{
                            type: 'line',
                            data: {{
                                datasets: [{{
                                    label: isTfr ? 'TFR' : 'Födda barn',
                                    data: tsData,
                                    borderColor: lineColor,
                                    backgroundColor: fillColor,
                                    borderWidth: 3,
                                    fill: true,
                                    pointRadius: 4,
                                    pointHoverRadius: 8,
                                    tension: 0.15
                                }}]
                            }},
                            options: {{
                                responsive: true, maintainAspectRatio: false,
                                plugins: {{ 
                                    legend: {{ display: false }},
                                    tooltip: {{
                                        callbacks: {{
                                            label: function(c) {{
                                                const val = isTfr ? c.raw.y.toFixed(3) : c.raw.y.toLocaleString('sv-SE');
                                                return `År ${{c.raw.x}}: ${{val}}`;
                                            }}
                                        }}
                                    }}
                                }},
                                scales: {{
                                    x: {{ 
                                        type: 'linear', 
                                        title: {{ display: true, text: 'Årtal', font: {{weight: 'bold', size: 12}} }},
                                        ticks: {{ stepSize: 2, callback: v => v.toString().replace(/,/g, '') }} 
                                    }},
                                    y: yConfig
                                }}
                            }}
                        }});
                    }} else {{
                        ctx.fillStyle = '#bdc3c7';
                        ctx.font = 'bold 24px "Segoe UI", sans-serif';
                        ctx.textAlign = 'center';
                        ctx.fillText('Data saknas för vald epok och målgrupp', ctx.canvas.width / 2, ctx.canvas.height / 2);
                    }}
                }} 
                
                // RITA "FÖRDRÖJD FRUKTSAMHET" GRID (Scatter + Bar)
                else if (chartType === 'lag') {{
                    const relation = document.getElementById('select-relation').value;
                    const migGroup = document.getElementById('select-miggroup').value;
                    const lagVal = parseInt(document.getElementById('select-lag').value);
                    
                    document.getElementById('chart-section-title').innerText = `Samband: Inflyttade ${{migGroup}} mot Födda barn | Fördröjning: ${{lagVal}} år | Epok: ${{periodVal}}`;

                    birthGroups.forEach((bGrp, i) => {{
                        container.innerHTML += `
                        <div class="col-lg-4 col-md-6 mb-4">
                            <div class="card h-100 border-success">
                                <div class="card-header text-center bg-light">
                                    <strong class="fs-5">${{bGrp}} (Y-axel)</strong><br>
                                    <div id="stats_${{i}}" class="mt-2">Laddar...</div>
                                </div>
                                <div class="card-body p-2 dual-chart-container">
                                    <div class="main-canvas"><canvas id="chart_main_${{i}}"></canvas></div>
                                    <div class="mini-canvas"><canvas id="chart_mini_${{i}}"></canvas></div>
                                </div>
                            </div>
                        </div>
                        `;
                    }});

                    birthGroups.forEach((bGrp, i) => {{
                        const dataObj = chartData.find(d => 
                            d.relation === relation && 
                            d.mig_group === migGroup && 
                            d.birth_group === bGrp && 
                            d.period === periodVal &&
                            d.lag === lagVal
                        );
                        
                        const mainCtx = document.getElementById(`chart_main_${{i}}`).getContext('2d');
                        const miniCtx = document.getElementById(`chart_mini_${{i}}`).getContext('2d');
                        
                        if(dataObj) {{
                            document.getElementById(`stats_${{i}}`).innerHTML = `
                                <span class="badge" style="background-color: #27ae60;">R² = ${{dataObj.r2}} | r = ${{dataObj.r}}</span>
                                <div class="trend-text">→ Trend (Nya barn per inflyttad): ${{dataObj.slope}}</div>
                            `;
                            
                            // HUVUDGRAF
                            mainChartInstances[i] = new Chart(mainCtx, {{
                                type: 'scatter',
                                data: {{
                                    datasets: [
                                        {{
                                            label: 'Observationer',
                                            data: dataObj.scatter,
                                            backgroundColor: 'rgba(39, 174, 96, 0.6)',
                                            borderColor: 'rgba(34, 153, 84, 0.9)',
                                            pointRadius: 5,
                                            pointHoverRadius: 8
                                        }},
                                        {{
                                            type: 'line',
                                            label: 'Trendlinje',
                                            data: dataObj.line,
                                            borderColor: 'rgba(192, 57, 43, 1)',
                                            borderWidth: 2,
                                            fill: false,
                                            pointRadius: 0,
                                            pointHitRadius: 0
                                        }}
                                    ]
                                }},
                                options: {{
                                    responsive: true, maintainAspectRatio: false,
                                    plugins: {{
                                        legend: {{ display: false }},
                                        tooltip: {{
                                            callbacks: {{
                                                label: function(c) {{
                                                    if (c.dataset.type === 'line') return 'Trendlinje';
                                                    return `Inflytt: ${{c.raw.mig_year}} | Födda: ${{c.raw.birth_year}} | X: ${{c.parsed.x}} | Y: ${{c.parsed.y}}`;
                                                }}
                                            }}
                                        }}
                                    }},
                                    scales: {{
                                        x: {{ title: {{ display: true, text: 'Inflyttade (' + migGroup + ')', font: {{weight: 'bold', size: 10}} }} }},
                                        y: {{ title: {{ display: true, text: 'Födda barn (' + bGrp + ')', font: {{weight: 'bold', size: 10}} }} }}
                                    }}
                                }}
                            }});

                            // INKUBATIONSGRAF MED SMARTA FÄRGER
                            const maxR2 = Math.max(...dataObj.lag_profile);
                            const maxIdx = dataObj.lag_profile.indexOf(maxR2);

                            const barColors = dataObj.lag_profile.map((val, idx) => {{
                                if (idx === lagVal && idx === maxIdx) return 'rgba(231, 76, 60, 0.9)'; // Röd (Både vald och högst)
                                if (idx === lagVal) return 'rgba(231, 76, 60, 0.6)'; // Ljusröd (Endast vald)
                                if (idx === maxIdx) return 'rgba(41, 128, 185, 0.8)'; // Blå (Högst men ej vald)
                                return 'rgba(149, 165, 166, 0.4)'; // Grå (Övriga)
                            }});
                            
                            const barBorders = dataObj.lag_profile.map((val, idx) => {{
                                if (idx === maxIdx) return '#2c3e50'; // Mörk kant på den högsta stapeln
                                return 'transparent';
                            }});
                            
                            const barBorderWidths = dataObj.lag_profile.map((val, idx) => idx === maxIdx ? 2 : 0);
                            
                            miniChartInstances[i] = new Chart(miniCtx, {{
                                type: 'bar',
                                data: {{
                                    labels: ['+0 år', '+1 år', '+2 år', '+3 år', '+4 år', '+5 år'],
                                    datasets: [{{
                                        label: 'R² (Förklaringsgrad)',
                                        data: dataObj.lag_profile,
                                        backgroundColor: barColors,
                                        borderColor: barBorders,
                                        borderWidth: barBorderWidths,
                                        borderRadius: 3
                                    }}]
                                }},
                                options: {{
                                    responsive: true, maintainAspectRatio: false,
                                    plugins: {{
                                        legend: {{ display: false }},
                                        title: {{ display: true, text: 'R² Profil (Högst markerad blå, Röd = valt år)', font: {{size: 11}}, padding: {{top: 0, bottom: 5}} }},
                                        tooltip: {{
                                            callbacks: {{
                                                label: function(c) {{ return `R²: ${{c.raw}}`; }}
                                            }}
                                        }}
                                    }},
                                    scales: {{
                                        x: {{ grid: {{ display: false }}, ticks: {{font: {{size: 10}}}} }},
                                        y: {{ beginAtZero: true, max: 1.0, ticks: {{font: {{size: 9}}, stepSize: 0.5}} }}
                                    }}
                                }}
                            }});
                            
                        }} else {{
                             document.getElementById(`stats_${{i}}`).innerHTML = "<span class='badge bg-secondary'>Datan saknas för tidsperioden</span>";
                             
                             mainCtx.clearRect(0, 0, mainCtx.canvas.width, mainCtx.canvas.height);
                             mainCtx.fillStyle = '#bdc3c7';
                             mainCtx.font = 'bold 20px "Segoe UI", sans-serif';
                             mainCtx.textAlign = 'center';
                             mainCtx.fillText('Data saknas', mainCtx.canvas.width / 2, mainCtx.canvas.height / 2);
                             
                             miniCtx.clearRect(0, 0, miniCtx.canvas.width, miniCtx.canvas.height);
                        }}
                    }});
                }}
            }}

            const selectors = [
                'select-charttype', 'select-period', 'select-ts-age', 'select-relation', 'select-miggroup', 'select-lag',
                'select-ts-grace', 'check-ts-zero', 'check-ts-fixed'
            ];
            selectors.forEach(id => {{
                const el = document.getElementById(id);
                if (el) el.addEventListener('change', renderCharts);
            }});
            
            renderCharts();
        </script>
    </body>
    </html>
    """
    
    html_path = os.path.join(current_folder, "fruktsamhet_dashboard.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Dashboard sparad som '{html_path}'")

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    px_mig = os.path.join(current_folder, 'px_filer', 'fl01vk.px')
    px_tfr = os.path.join(current_folder, 'px_filer', 'TFR82.px')
    
    missing = [f for f in [px_mig, px_tfr] if not os.path.exists(f)]
    
    if missing:
        print(f"FEL: Saknar filer i 'px_filer' mappen: {[os.path.basename(m) for m in missing]}")
    else:
        df_mig = parse_generic_px(px_mig)
        df_tfr = parse_generic_px(px_tfr)
        
        tfr_js, births_js = get_time_series(df_tfr)
        df_merged = prepare_merged_data(df_mig, df_tfr)
        
        excel_path = os.path.join(current_folder, "Samkord_Fruktsamhet.xlsx")
        df_merged.to_excel(excel_path, index=False)
        print(f"Rådata sparad till '{excel_path}'")
        
        charts_data, relationer, mig_groups, birth_groups, periods, lags = perform_analysis(df_merged)
        
        generate_html_report(charts_data, relationer, mig_groups, birth_groups, periods, lags, tfr_js, births_js)
        
        print("\n=== KLAR ===")
        print("Analysen är klar. Öppna 'fruktsamhet_dashboard.html' i din webbläsare!")