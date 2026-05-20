# -*- coding: utf-8 -*-
import os
import sys
import re
import json
import math
import pandas as pd

# Inga fler import av Matplotlib, Seaborn eller Scipy!
# Vi använder inte ens numpy för matematiken längre för att undvika
# C-kraschar i korrupta Anaconda-miljöer.

# ==========================================
# 1. GENERELL SETUP OCH GYLLENE REGLER
# ==========================================
# Garantera att filer hittas i samma mapp
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
except NameError:
    current_folder = os.getcwd()

# Standardkod för textfix
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
# 2. DATAHANTERING OCH PX-PARSER
# ==========================================
def parse_px(filepath):
    print("Laddar och tolkar PX-fil...")
    with open(filepath, 'r', encoding='latin1') as f:
        content = f.read()

    def get_values(var_name):
        match = re.search(rf'VALUES\("{var_name}"\)=\s*([^;]+);', content, re.DOTALL)
        if match:
            return re.findall(r'"([^"]*)"', match.group(1))
        return []

    tid = get_values('tid')
    alder = get_values('ålder')
    riktning = get_values('riktning')
    relation = get_values('flyttningsrelation')

    alder = [fix_text(a).strip() for a in alder]
    riktning = [fix_text(r).strip() for r in riktning]
    relation = [fix_text(r).strip() for r in relation]

    data_match = re.search(r'DATA=\s*([^;]+);', content, re.DOTALL)
    data_str = data_match.group(1).split()
    
    data_series = pd.Series(data_str).str.replace('"', '')
    data_values = pd.to_numeric(data_series, errors='coerce').values

    index = pd.MultiIndex.from_product(
        [tid, alder, riktning, relation], 
        names=['Tid', 'Ålder', 'Riktning', 'Relation']
    )

    df = pd.DataFrame({'Antal': data_values}, index=index).reset_index()
    return df

# ==========================================
# 3. KATEGORISERING OCH AGGREGERING
# ==========================================
def extract_age(age_str):
    if 'Totalt' in str(age_str): 
        return -1
    match = re.search(r'(\d+)', str(age_str))
    return int(match.group(1)) if match else -1

def prepare_data(df):
    print("Filtrerar och aggregerar åldersgrupper och geografiska relationer...")
    
    df['Ålder_Int'] = df['Ålder'].apply(extract_age)
    
    relationer_att_behalla = ['Totalt', 'Inrikes totalt', 'Annat land', 'Eget län', 'Annat län']
    
    df_base = df[
        (df['Riktning'].isin(['Inflyttning', 'Utflyttning'])) & 
        (df['Relation'].isin(relationer_att_behalla)) &
        (df['Ålder_Int'] >= 0)
    ].copy()

    bins = {
        '0-5 år': lambda x: 0 <= x <= 5,
        '6-9 år': lambda x: 6 <= x <= 9,
        '10-12 år': lambda x: 10 <= x <= 12,
        '13-15 år': lambda x: 13 <= x <= 15,
        '16-18 år': lambda x: 16 <= x <= 18,
        '30-59 år': lambda x: 30 <= x <= 59,
        '40-55 år': lambda x: 40 <= x <= 55
    }

    rows = []
    for (tid, rikt, rel), group in df_base.groupby(['Tid', 'Riktning', 'Relation']):
        row = {'Tid': int(tid), 'Riktning': rikt, 'Relation': rel}
        
        for bin_name, bin_func in bins.items():
            mask = group['Ålder_Int'].apply(bin_func)
            subgroup = group[mask]['Antal']
            
            if subgroup.isna().all():
                row[bin_name] = None
            else:
                row[bin_name] = subgroup.sum()
                
        rows.append(row)
    
    df_pivot = pd.DataFrame(rows).sort_values(['Riktning', 'Relation', 'Tid'])
    return df_pivot

# ==========================================
# 4. SÄKER STATISTISK ANALYS (Ren Python)
# ==========================================
def safe_math_regression(x, y):
    n = len(x)
    if n < 2:
        return 0.0, 0.0, 0.0, 0.0
    
    x_mean = sum(x) / n
    y_mean = sum(y) / n
    
    numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
    sum_sq_x = sum((xi - x_mean)**2 for xi in x)
    sum_sq_y = sum((yi - y_mean)**2 for yi in y)
    
    if sum_sq_x == 0 or sum_sq_y == 0:
        return 0.0, 0.0, 0.0, 0.0
        
    r = numerator / math.sqrt(sum_sq_x * sum_sq_y)
    r_squared = r**2
    
    m = numerator / sum_sq_x
    b = y_mean - m * x_mean
    
    return float(r), float(r_squared), float(m), float(b)

def perform_math_analysis(df_pivot):
    print("Beräknar multi-dimensionella korrelationer (Säker algoritm)...")
    child_groups = ['0-5 år', '6-9 år', '10-12 år', '13-15 år', '16-18 år']
    adult_groups = ['30-59 år', '40-55 år']
    riktningar = ['Inflyttning', 'Utflyttning']
    relationer = ['Totalt', 'Inrikes totalt', 'Annat land', 'Eget län', 'Annat län']
    
    # Nyhet: Dynamiska tidsfönster för filtrering
    time_windows = {
        'Alla år': 0,
        'Senaste 25 åren': 25,
        'Senaste 10 åren': 10,
        'Senaste 5 åren': 5
    }
    
    charts_data = []

    for riktning in riktningar:
        for relation in relationer:
            df_sub = df_pivot[(df_pivot['Riktning'] == riktning) & (df_pivot['Relation'] == relation)]
            
            for adult_col in adult_groups:
                for child_col in child_groups:
                    for period_name, years in time_windows.items():
                        try:
                            if adult_col not in df_sub.columns or child_col not in df_sub.columns:
                                continue
                            
                            # Tvätta datan
                            valid_data = df_sub[['Tid', adult_col, child_col]].dropna()
                            if valid_data.empty:
                                continue
                            
                            # Applicera tidsfönster baserat på max-året för att garantera framtidssäkerhet
                            max_year = valid_data['Tid'].max()
                            if years > 0:
                                valid_data = valid_data[valid_data['Tid'] > (max_year - years)]
                            
                            tid_list = valid_data['Tid'].tolist()
                            x_list = valid_data[adult_col].tolist()
                            y_list = valid_data[child_col].tolist()
                            
                            if len(x_list) < 2:
                                continue
                            
                            # Matematik
                            r, r_squared, m, b = safe_math_regression(x_list, y_list)
                            
                            scatter_pts = [{'x': float(xv), 'y': float(yv), 'year': int(tv)} for xv, yv, tv in zip(x_list, y_list, tid_list)]
                            min_x, max_x = float(min(x_list)), float(max(x_list))
                            
                            line_pts = [
                                {'x': min_x, 'y': float(m * min_x + b)},
                                {'x': max_x, 'y': float(m * max_x + b)}
                            ]
                            
                            chart_id = f"chart_{riktning}_{child_col}".replace(' ', '_').replace('-', '_').replace('å', 'a')
                            
                            charts_data.append({
                                'id': chart_id,
                                'riktning': riktning,
                                'relation': relation,
                                'adult_col': adult_col,
                                'child_col': child_col,
                                'period': period_name,
                                'scatter': scatter_pts,
                                'line': line_pts,
                                'r2': f"{r_squared:.3f}",  # Format med exakt 3 decimaler
                                'r': f"{r:.3f}",          # Format med exakt 3 decimaler
                                'slope': f"{m:.3f}"       # Format med exakt 3 decimaler
                            })

                        except Exception as e:
                            print(f" -> FEL vid beräkning av {child_col} ({riktning} / {relation} / {adult_col} / {period_name}): {e}")

    return charts_data

# ==========================================
# 5. SKAPA HTML-DASHBOARD (Dynamisk JS)
# ==========================================
def generate_html_report(charts_data):
    print("Genererar dynamisk HTML Dashboard med Chart.js och Selectors...")
    
    js_data = json.dumps(charts_data)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="sv">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Interaktiv Flyttanalys: Barn och Vuxna</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {{ background-color: #f8f9fa; padding: 20px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
            .card {{ box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: none; }}
            .header-main {{ background-color: #004b87; color: white; padding: 10px; border-radius: 5px 5px 0 0; }}
            .analysis-text {{ font-size: 1.05em; line-height: 1.6; }}
            .control-panel {{ background-color: #e9ecef; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 5px solid #004b87; }}
            h2.section-title {{ color: #004b87; margin-top: 20px; margin-bottom: 20px; border-bottom: 2px solid #004b87; padding-bottom: 5px; }}
            .table-responsive {{ max-height: 400px; overflow-y: auto; }}
            thead th {{ position: sticky; top: 0; background-color: #004b87; color: white; }}
            .table th, .table td {{ text-align: left !important; vertical-align: middle; }}
            .trend-text {{ color: #e74c3c; font-weight: bold; margin-top: 5px; font-size: 0.9em; }}
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <!-- TILLBAKA-KNAPP -->
            <a href="../prognoskalkylator.html" class="btn btn-outline-primary mb-3">&larr; Tillbaka till Prognoskalkylatorn</a>
            
            <h1 class="mb-3" style="color: #004b87;">Interaktiv Analys: Flyttningssamband Barn och Vuxna</h1>
            <p class="lead">Linköpings kommun: Jämförelse mellan breda vuxengrupper, kärnfamiljer och geografiska områden.</p>
            
            <div class="row">
                <div class="col-12 mb-4">
                    <div class="card">
                        <div class="header-main">
                            <h5 class="m-0">Analys från Prognosmakaren (Baserat på faktisk statistik)</h5>
                        </div>
                        <div class="card-body analysis-text">
                            <p>Genom OLS-regression och Pearson-korrelation på historisk flyttdata fastställer vi sambanden. <strong>R²-värdet</strong> visar hur starkt sambandet är, och <strong>Barn per vuxen (Trend)</strong> utgör linjens matematiska lutning (multiplikatorn).</p>
                            <ul>
                                <li><strong>Hur man läser "Barn per vuxen":</strong> Detta värde anger den förväntade ökningen/minskningen av antalet barn för varje extra vuxen som flyttar. Är trenden 0.150 innebär det statistiskt att för 100 flyttande vuxna följer 15 barn med.</li>
                                <li><strong>Bredd vs Kärnfamilj:</strong> Att välja gruppen (30-59) drar ner R²-värdena på grund av bruset från ensamflyttande unga vuxna. Byter du till <strong>40-55 år</strong> (Etablerade familjer) blir sambanden och R² ofta nästan perfekta.</li>
                                <li><strong>Geografi och Tid:</strong> Du kan nu separera på geografisk relation samt inskränka analysen till de senaste åren för att fånga upp moderna mönster. Om du väljer "Senaste X åren" utgår kalkylatorn alltid från det modernaste årtalet som finns i SCB-datan.</li>
                            </ul>
                            <p><em>Hovra över punkterna i diagrammen nedan för att se både det specifika årtalet och de exakta värdena!</em></p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- KONTROLLPANEL FÖR GRAFER -->
            <div class="control-panel">
                <h5 class="mb-3">Välj Parametrar för Analysen:</h5>
                <div class="row">
                    <div class="col-md-3 mb-2">
                        <label class="form-label fw-bold">In- eller Utflyttning:</label>
                        <select id="select-riktning" class="form-select border-primary">
                            <option value="Inflyttning">Inflyttning</option>
                            <option value="Utflyttning">Utflyttning</option>
                        </select>
                    </div>
                    <div class="col-md-3 mb-2">
                        <label class="form-label fw-bold">Geografisk Relation:</label>
                        <select id="select-relation" class="form-select border-primary">
                            <option value="Totalt">Totalt (Alla flyttningar)</option>
                            <option value="Inrikes totalt">Inrikes totalt</option>
                            <option value="Annat land">Annat land (Utrikes)</option>
                            <option value="Eget län">Eget län (Data fr.o.m 2002)</option>
                            <option value="Annat län">Annat län (Data fr.o.m 2002)</option>
                        </select>
                    </div>
                    <div class="col-md-3 mb-2">
                        <label class="form-label fw-bold">Vuxengrupp att relatera till:</label>
                        <select id="select-adult" class="form-select border-primary">
                            <option value="30-59 år">30-59 år (Bred grupp inkl. brus)</option>
                            <option value="40-55 år" selected>40-55 år (Kärnfamilj / Etablerade)</option>
                        </select>
                    </div>
                    <div class="col-md-3 mb-2">
                        <label class="form-label fw-bold">Tidsperiod:</label>
                        <select id="select-period" class="form-select border-primary">
                            <option value="Alla år">Alla tillgängliga år</option>
                            <option value="Senaste 25 åren">Senaste 25 åren</option>
                            <option value="Senaste 10 åren" selected>Senaste 10 åren</option>
                            <option value="Senaste 5 åren">Senaste 5 åren</option>
                        </select>
                    </div>
                </div>
            </div>

            <!-- DYNAMISKT GRAF-CONTAINER -->
            <h2 class="section-title" id="chart-section-title">Grafer laddas...</h2>
            <div class="row" id="charts-container"></div>

            <!-- DYNAMISK TABELL -->
            <div class="row mt-5 mb-4">
                <div class="col-12">
                    <div class="card">
                        <div class="header-main">
                            <h5 class="m-0">Källdata: Statistik för aktuell filtrering</h5>
                        </div>
                        <div class="card-body table-responsive">
                            <table class="table table-striped table-hover table-sm">
                                <thead>
                                    <tr>
                                        <th>Riktning</th>
                                        <th>Relation</th>
                                        <th>Målgrupp (Vuxna)</th>
                                        <th>Målgrupp (Barn)</th>
                                        <th>Tidsperiod</th>
                                        <th>Korrelation (r)</th>
                                        <th>Förklaringsgrad (R²)</th>
                                        <th>Barn per vuxen (Trend)</th>
                                    </tr>
                                </thead>
                                <tbody id="dynamic-table-body">
                                    <!-- Fylls av JavaScript -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

        </div>

        <script>
            const chartData = {js_data};
            const childGroups = ['0-5 år', '6-9 år', '10-12 år', '13-15 år', '16-18 år'];
            let chartInstances = {{}};

            function renderCharts() {{
                const riktning = document.getElementById('select-riktning').value;
                const relation = document.getElementById('select-relation').value;
                const adultVal = document.getElementById('select-adult').value;
                const periodVal = document.getElementById('select-period').value;
                
                document.getElementById('chart-section-title').innerText = `Korrelation: Barn vs ${{adultVal}} | ${{riktning}} (${{relation}}) | ${{periodVal}}`;

                const container = document.getElementById('charts-container');
                const tableBody = document.getElementById('dynamic-table-body');
                
                if(!document.getElementById('chart_0')) {{
                    container.innerHTML = ''; 
                    childGroups.forEach((child, i) => {{
                        container.innerHTML += `
                        <div class="col-lg-4 col-md-6 mb-4">
                            <div class="card h-100 border-primary">
                                <div class="card-header text-center bg-light">
                                    <strong class="fs-5">${{child}}</strong><br>
                                    <div id="stats_${{i}}" class="mt-2">Laddar...</div>
                                </div>
                                <div class="card-body p-2">
                                    <canvas id="chart_${{i}}"></canvas>
                                </div>
                            </div>
                        </div>
                        `;
                    }});
                }}

                let tableHTML = '';

                childGroups.forEach((child, i) => {{
                    const dataObj = chartData.find(d => 
                        d.riktning === riktning && 
                        d.relation === relation && 
                        d.adult_col === adultVal && 
                        d.child_col === child &&
                        d.period === periodVal
                    );
                    
                    if(dataObj) {{
                        // Uppdatera statiska rutor
                        document.getElementById(`stats_${{i}}`).innerHTML = `
                            <span class="badge bg-primary">R² = ${{dataObj.r2}} | r = ${{dataObj.r}}</span>
                            <div class="trend-text">→ Estimerat antal barn per vuxen: ${{dataObj.slope}}</div>
                        `;
                        
                        // Bygg tabellrad för detta barn
                        tableHTML += `<tr>
                            <td>${{dataObj.riktning}}</td>
                            <td>${{dataObj.relation}}</td>
                            <td>${{dataObj.adult_col}}</td>
                            <td><strong>${{dataObj.child_col}}</strong></td>
                            <td>${{dataObj.period}}</td>
                            <td>${{dataObj.r}}</td>
                            <td>${{dataObj.r2}}</td>
                            <td><strong>${{dataObj.slope}}</strong></td>
                        </tr>`;

                        if(chartInstances[i]) {{
                            chartInstances[i].destroy();
                        }}

                        const ctx = document.getElementById(`chart_${{i}}`).getContext('2d');
                        chartInstances[i] = new Chart(ctx, {{
                            type: 'scatter',
                            data: {{
                                datasets: [
                                    {{
                                        label: 'Observationer',
                                        data: dataObj.scatter,
                                        backgroundColor: 'rgba(52, 152, 219, 0.7)',
                                        borderColor: 'rgba(41, 128, 185, 0.9)',
                                        pointRadius: 4,
                                        pointHoverRadius: 8
                                    }},
                                    {{
                                        type: 'line',
                                        label: 'Regressionslinje',
                                        data: dataObj.line,
                                        borderColor: 'rgba(231, 76, 60, 1)',
                                        borderWidth: 2,
                                        fill: false,
                                        pointRadius: 0,
                                        pointHitRadius: 0
                                    }}
                                ]
                            }},
                            options: {{
                                responsive: true,
                                plugins: {{
                                    legend: {{ display: false }},
                                    tooltip: {{
                                        callbacks: {{
                                            label: function(context) {{
                                                if (context.dataset.type === 'line') {{
                                                    return 'Trendlinje';
                                                }}
                                                const year = context.raw.year;
                                                return `År ${{year}} | Vuxna: ${{context.parsed.x}} | Barn: ${{context.parsed.y}}`;
                                            }}
                                        }}
                                    }}
                                }},
                                scales: {{
                                    x: {{ 
                                        title: {{ display: true, text: 'Antal flyttande vuxna (' + adultVal + ')', font: {{weight: 'bold'}} }},
                                        beginAtZero: false
                                    }},
                                    y: {{ 
                                        title: {{ display: true, text: 'Antal flyttande barn (' + child + ')', font: {{weight: 'bold'}} }},
                                        beginAtZero: false
                                    }}
                                }}
                            }}
                        }});
                    }} else {{
                         document.getElementById(`stats_${{i}}`).innerHTML = "<span class='badge bg-secondary'>Ingen data för denna period</span>";
                         if(chartInstances[i]) chartInstances[i].destroy();
                    }}
                }});

                // Uppdatera html i tabellen så den matchar filtren exakt
                if(tableHTML === '') {{
                    tableBody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">Ingen data tillgänglig för det valda filtret.</td></tr>';
                }} else {{
                    tableBody.innerHTML = tableHTML;
                }}
            }}

            document.getElementById('select-riktning').addEventListener('change', renderCharts);
            document.getElementById('select-relation').addEventListener('change', renderCharts);
            document.getElementById('select-adult').addEventListener('change', renderCharts);
            document.getElementById('select-period').addEventListener('change', renderCharts);
            
            renderCharts();
        </script>
    </body>
    </html>
    """
    
    html_path = os.path.join(current_folder, "flyttanalys_dashboard.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Dashboard sparad som '{html_path}'")

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    px_file = os.path.join(current_folder, 'px_filer', 'fl01vf.px')
    
    if not os.path.exists(px_file):
        print(f"FEL: Hittade inte {px_file}. Lägg filen i undermappen 'px_filer'.")
    else:
        df_raw = parse_px(px_file)
        df_pivot = prepare_data(df_raw)
        
        excel_path = os.path.join(current_folder, "Aggregerad_Flyttdata_Linkoping.xlsx")
        df_pivot.to_excel(excel_path, index=False)
        print(f"Rådata sparad till '{excel_path}'")
        
        charts_data = perform_math_analysis(df_pivot)
        
        generate_html_report(charts_data)
        print("\n=== KLAR ===")
        print("Analysen är klar. Öppna 'flyttanalys_dashboard.html' i din webbläsare för att se resultatet och de interaktiva graferna.")