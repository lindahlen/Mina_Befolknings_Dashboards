import os
import sys
import pandas as pd
import json

# ==========================================
# DATA OCH KÄLLMATERIAL
# Författare till matchinformation och grunddata: Jimmy Lindahl
# ==========================================

# ==========================================
# 1. GENERELL SETUP OCH SÖKVÄGAR
# ==========================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
    main_folder = os.path.abspath(os.path.join(current_folder, '..'))
    excel_folder = os.path.join(main_folder, 'excel_filer')
except NameError:
    pass 

# ==========================================
# 2. DATAHANTERING OCH TEXTFIX
# ==========================================
encoding_fix = {
    'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
    'Ã©': 'é', 'Ã¨': 'è', 'Ã‰': 'É', "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö"
}

# Här kan du mappa ihop lag som bytt namn så att de blir samma lag i databasen
team_name_mapping = {
    'Panos Ljungskile SK': 'Ljungskile SK',
    'FC Café Opera Djursholm': 'AFC Eskilstuna',
    'FC Café Opera United': 'AFC Eskilstuna',
    'Väsby United': 'AFC Eskilstuna',
    'FC Väsby United': 'AFC Eskilstuna',
    'Athletic FC United': 'AFC Eskilstuna',
    'Väsby IK': 'AFC Eskilstuna', # Om de hette så innan fusionen och du vill ha ihop dem
    'Bunkeflo IF': 'IF Limhamn Bunkeflo',
    'LB07': 'IF Limhamn Bunkeflo',
}

def fix_text(text):
    if not isinstance(text, str): return text
    for bad, good in encoding_fix.items():
        text = text.replace(bad, good)
    return text

def normalize_team(team_name):
    team = str(team_name).strip()
    return team_name_mapping.get(team, team)

excel_file = os.path.join(excel_folder, "Superettan_matcher_samlade.xlsx")

try:
    # Läs in den första fliken som vi förväntar oss heter Superettan
    df = pd.read_excel(excel_file)
    print(f"Laddade {len(df)} rader från Superettan_matcher_samlade.xlsx.")
    df['Säs'] = df['Säs'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    
    text_columns = ['Hemmalag', 'Bortalag', 'Arena', 'NOT', 'Domare', 'År', 'Omgång']
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].apply(fix_text)
            
    # Spara originalnamnen innan normalisering
    if 'Hemmalag' in df.columns: 
        df['Hemmalag_Org'] = df['Hemmalag']
        df['Hemmalag'] = df['Hemmalag'].apply(normalize_team)
    if 'Bortalag' in df.columns: 
        df['Bortalag_Org'] = df['Bortalag']
        df['Bortalag'] = df['Bortalag'].apply(normalize_team)
            
except FileNotFoundError:
    print(f"KRITISKT FEL: Filen '{excel_file}' hittades inte.")
    sys.exit(1)

df = df.fillna("")

season_info = {}
series_file = os.path.join(excel_folder, "Serietabellerna_samlade.xlsx")
try:
    df_series = pd.read_excel(series_file, sheet_name="Serienivå")
    for _, row in df_series.iterrows():
        sas_nr = str(row.get('Säsnr', '')).replace('.0', '').strip()
        
        # Mappa Allsvenskans säsongsnr (76) till Superettans Säs (1)
        try:
            mapped_sas = str(int(sas_nr) - 75)
        except ValueError:
            mapped_sas = sas_nr
            
        sas_name = str(row.get('Säsong', sas_nr)).strip()
        pts = row.get('Poäng_seger', 3)
        if pd.isna(pts) or pts == "": pts = 3
        season_info[mapped_sas] = {'name': sas_name, 'pts': int(pts)}
except Exception: pass

all_teams = sorted(list(set([t for t in df['Hemmalag'].tolist() + df['Bortalag'].tolist() if str(t).strip() != ""])))

def safe_season_sort(val):
    if str(val).strip() == "": return (999999, "") 
    try: return (0, float(val)) 
    except (ValueError, TypeError): return (1, str(val)) 

all_seasons_raw = sorted(list(set(df['Säs'].tolist())), key=safe_season_sort)
all_seasons = [str(s) for s in all_seasons_raw if str(s).strip() != ""]

# ==========================================
# BYGG EPOKER OCH DECENNIER
# ==========================================
decades = {}
custom_epochs = {}

for s in all_seasons:
    try:
        name = season_info.get(s, {}).get('name', s)
        year_str = "".join(filter(str.isdigit, name))[:4]
        if len(year_str) == 4:
            decade = year_str[:3] + "0-talet"
            if decade not in decades: decades[decade] = []
            decades[decade].append(s)
    except Exception: pass

try:
    df_epochs = pd.read_excel(excel_file, sheet_name="Epoker")
    df_epochs.columns = df_epochs.columns.str.strip() 
    c_period = next((c for c in df_epochs.columns if 'period' in c.lower()), df_epochs.columns[0])
    c_start = next((c for c in df_epochs.columns if 'första' in c.lower()), df_epochs.columns[1])
    c_end = next((c for c in df_epochs.columns if 'sista' in c.lower()), df_epochs.columns[2])
    
    for _, row in df_epochs.iterrows():
        period_name = str(row.get(c_period, '')).strip()
        if not period_name or period_name == "nan": continue
        try:
            start_id = float(str(row[c_start]).replace(',', '.'))
            end_id = float(str(row[c_end]).replace(',', '.'))
        except (ValueError, TypeError, KeyError): continue
            
        epoch_seasons = []
        for s in all_seasons:
            try:
                if start_id <= float(s) <= end_id: epoch_seasons.append(s)
            except ValueError: pass
        if epoch_seasons: custom_epochs[period_name] = epoch_seasons
except Exception: pass

# ==========================================
# LÄS IN MERITER OCH STARTPOÄNG FÖR SUPERETTAN
# ==========================================
team_merits = {} 
try:
    df_tabeller = pd.read_excel(series_file, sheet_name="Tabeller")
    df_tabeller.columns = df_tabeller.columns.str.strip()
    col_sasnr = next((c for c in df_tabeller.columns if 'säsnr' in c.lower()), 'Säsnr')
    col_lag = next((c for c in df_tabeller.columns if 'lag' in c.lower() and len(c) <= 4), 'Lag')
    col_merit = next((c for c in df_tabeller.columns if 'merit' in c.lower()), 'Merit')
    col_nya = next((c for c in df_tabeller.columns if 'nya' in c.lower()), 'Nya')
    col_startpts = next((c for c in df_tabeller.columns if 'startpoäng' in c.lower() or 'poängjustering' in c.lower()), None)
    col_serie = next((c for c in df_tabeller.columns if 'serie' in c.lower()), None)
    
    def sort_key(x):
        try: return float(str(x).replace(',', '.'))
        except: return 9999
        
    sas_unique = sorted(df_tabeller[col_sasnr].unique(), key=sort_key)
    
    for sas in sas_unique:
        sas_str = str(sas).replace('.0', '').strip()
        
        # Mappa Allsvenskans säsongsnr (76) till Superettans Säs (1)
        try:
            mapped_sas = str(int(sas_str) - 75)
        except ValueError:
            mapped_sas = sas_str
            
        if mapped_sas not in team_merits: team_merits[mapped_sas] = {}
        
        group = df_tabeller[df_tabeller[col_sasnr] == sas]
        for _, row in group.iterrows():
            team = str(row.get(col_lag, '')).strip()
            team = normalize_team(team) # Mappa ihop namn även här!
            
            merit = str(row.get(col_merit, '')).strip()
            nya = str(row.get(col_nya, '')).strip()
            if merit == 'nan': merit = ''
            if nya == 'nan': nya = ''
            
            # BEGRÄNSA TILL ENBART SUPERETTAN
            if col_serie:
                serie_val = str(row.get(col_serie, '')).strip()
                if serie_val and 'superettan' not in serie_val.lower():
                    continue # Hoppa över lag i Allsvenskan etc.
            
            start_pts = 0.0
            if col_startpts:
                try: start_pts = float(str(row.get(col_startpts, '0')).replace(',', '.'))
                except: pass
            if pd.isna(start_pts): start_pts = 0.0

            if team not in team_merits[mapped_sas]:
                team_merits[mapped_sas][team] = {'merit': merit, 'nya': nya, 'start_pts': start_pts}
            else:
                if start_pts != 0: team_merits[mapped_sas][team]['start_pts'] = start_pts
                if merit: team_merits[mapped_sas][team]['merit'] = merit
                if nya: team_merits[mapped_sas][team]['nya'] = nya
            
except Exception as e: 
    print(f"Info: {e}")

# Förbered JSON data
json_match_data = df.to_json(orient="records", force_ascii=False)
json_teams_data = json.dumps(all_teams, ensure_ascii=False)
json_seasons_data = json.dumps(all_seasons, ensure_ascii=False)
json_season_info = json.dumps(season_info, ensure_ascii=False)
json_decades_data = json.dumps(decades, ensure_ascii=False)
json_custom_epochs_data = json.dumps(custom_epochs, ensure_ascii=False)
json_team_merits_data = json.dumps(team_merits, ensure_ascii=False)

# ==========================================
# 3. HTML / FRONTEND
# ==========================================
html_template = """
<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Superettan Matchhistorik</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .custom-scroll::-webkit-scrollbar { width: 8px; height: 8px; }
        .custom-scroll::-webkit-scrollbar-track { background: #f1f1f1; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
        .custom-scroll::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
        .tab-btn.active { border-bottom: 2px solid #ea580c; color: #9a3412; font-weight: 600; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        optgroup { font-weight: 700; color: #475569; background-color: #f8fafc; }
        optgroup[disabled] { color: #94a3b8; background-color: #f1f5f9; }
        option { font-weight: normal; color: #0f172a; background-color: #fff; }
        .sortable-th { cursor: pointer; user-select: none; }
        .sortable-th:hover { background-color: #e2e8f0; }
        .tooltip-container:hover .tooltip-content { display: block; }
    </style>
</head>
<body class="bg-slate-50 text-slate-800 font-sans min-h-screen">

    <header class="bg-orange-600 text-white shadow-md">
        <div class="max-w-7xl mx-auto px-4 py-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
                <h1 class="text-3xl font-bold tracking-tight">Superettan Matchhistorik</h1>
                <p class="text-orange-100 mt-1">Näst högsta serien sedan år 2000</p>
            </div>
            <a href="nationella_index.html" class="inline-flex items-center text-orange-100 hover:text-white transition-colors text-sm font-medium bg-orange-700 hover:bg-orange-800 px-4 py-2 rounded-md shadow-sm border border-orange-800">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
                Tillbaka till översikten
            </a>
        </div>
    </header>

    <nav class="bg-white shadow-sm sticky top-0 z-20 border-b border-slate-200">
        <div class="max-w-7xl mx-auto px-4 flex overflow-x-auto custom-scroll">
            <button onclick="switchTab('h2h')" id="btn-h2h" class="tab-btn active whitespace-nowrap py-4 px-6 text-slate-500 hover:text-orange-600">Head-to-Head</button>
            <button onclick="switchTab('search')" id="btn-search" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-orange-600">Matchsök / Historik</button>
            <button onclick="switchTab('records')" id="btn-records" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-orange-600">Topplistor</button>
            <button onclick="switchTab('streaks')" id="btn-streaks" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-orange-600">Långa sviter</button>
            <button onclick="switchTab('tables')" id="btn-tables" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-orange-600">Tabeller</button>
            <button onclick="switchTab('profiles')" id="btn-profiles" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-orange-600">Säsongens Profiler</button>
            <button onclick="switchTab('strength')" id="btn-strength" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-orange-600">Säsongsstyrka</button>
            <button onclick="switchTab('goldrace')" id="btn-goldrace" class="tab-btn whitespace-nowrap py-4 px-6 text-amber-600 font-bold hover:text-amber-700 bg-amber-50">Toppstriden</button>
            <button onclick="switchTab('analysis')" id="btn-analysis" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-orange-600">Förutsägbarhet</button>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-4 py-8">
        
        <!-- FLIK 1: H2H -->
        <section id="tab-h2h" class="tab-content active">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <h2 class="text-xl font-bold mb-4">Analysera inbördes möten</h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Lag A (Fokuslag) <span id="rank-team-a" class="text-xs text-orange-600 font-normal ml-2"></span></label>
                        <select id="h2h-team-a" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500"></select>
                    </div>
                    <div class="flex justify-center pb-2"><span class="text-slate-400 font-bold">VS</span></div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Lag B (Motståndare) <span id="rank-team-b" class="text-xs text-orange-600 font-normal ml-2"></span></label>
                        <select id="h2h-team-b" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500"></select>
                    </div>
                </div>
                <div class="mt-4 flex flex-col md:flex-row justify-between items-center gap-4 border-t border-slate-100 pt-4">
                    <div class="flex flex-wrap gap-4 text-sm">
                        <label class="flex items-center gap-1 cursor-pointer"><input type="radio" name="h2h-context" value="all" checked onchange="calculateH2H()"> Alla möten</label>
                        <label class="flex items-center gap-1 cursor-pointer"><input type="radio" name="h2h-context" value="home" onchange="calculateH2H()"> Endast Lag A Hemma</label>
                        <label class="flex items-center gap-1 cursor-pointer"><input type="radio" name="h2h-context" value="away" onchange="calculateH2H()"> Endast Lag A Borta</label>
                    </div>
                    <div class="flex gap-2">
                        <button onclick="renderH2HOverview()" class="bg-slate-200 hover:bg-slate-300 text-slate-800 font-medium py-2 px-4 rounded-md transition-colors text-sm">Statistik mot alla lag</button>
                        <button onclick="calculateH2H()" class="bg-orange-600 hover:bg-orange-700 text-white font-medium py-2 px-6 rounded-md transition-colors shadow-sm text-sm">Analysera VS</button>
                    </div>
                </div>
            </div>
            
            <div id="h2h-results" class="hidden">
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6" id="h2h-summary-cards"></div>
                <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                    <div class="overflow-x-auto custom-scroll" style="max-height: 750px;">
                        <table class="w-full text-left text-sm whitespace-nowrap relative">
                            <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200 sticky top-0 z-10 shadow-sm">
                                <tr>
                                    <th class="px-4 py-3">Säsong</th><th class="px-4 py-3">Datum</th>
                                    <th class="px-4 py-3 text-right">Hemmalag</th><th class="px-4 py-3 text-center">Resultat</th>
                                    <th class="px-4 py-3">Bortalag</th><th class="px-4 py-3 text-right">Publik</th>
                                </tr>
                            </thead>
                            <tbody id="h2h-table-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                        </table>
                    </div>
                    <div id="h2h-notes" class="bg-slate-50 p-3 border-t border-slate-200 text-xs text-rose-600 font-semibold flex flex-col gap-1 hidden"></div>
                </div>
            </div>

            <div id="h2h-overview" class="hidden">
                <h3 class="text-lg font-bold mb-3 text-slate-700" id="overview-title">Sammanställning</h3>
                <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                    <div class="overflow-x-auto custom-scroll" style="max-height: 750px;">
                        <table class="w-full text-left text-sm whitespace-nowrap relative">
                            <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200 sticky top-0 z-10 shadow-sm">
                                <tr>
                                    <th class="px-4 py-3 sortable-th" onclick="sortOverview('team')">Motståndare ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center" onclick="sortOverview('played')">Spelade ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center text-emerald-600" onclick="sortOverview('w')">V ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center text-slate-500" onclick="sortOverview('d')">O ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center text-rose-600" onclick="sortOverview('l')">F ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center" onclick="sortOverview('gf')">GM ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center" onclick="sortOverview('ga')">IM ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center font-bold" onclick="sortOverview('gd')">+/- ↕</th>
                                </tr>
                            </thead>
                            <tbody id="h2h-overview-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </section>

        <!-- FLIK 2: Matchsök -->
        <section id="tab-search" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <h2 class="text-xl font-bold mb-4">Avancerad Matchsökning</h2>
                <div class="grid grid-cols-1 lg:grid-cols-5 gap-4 items-end">
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Säsong</label>
                        <select id="search-season" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500"></select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Omgång</label>
                        <input type="text" id="search-round" placeholder="T.ex. 15" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Lag</label>
                        <select id="search-team" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500"></select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1" title="Lagets mål - Motståndarens mål">Resultat (Mål)</label>
                        <div class="flex items-center gap-2">
                            <input type="number" id="search-hm" placeholder="Gjorda" min="0" class="w-full border border-slate-300 rounded-md p-2 text-center bg-slate-50">
                            <span class="font-bold text-slate-400">-</span>
                            <input type="number" id="search-bm" placeholder="Insläppta" min="0" class="w-full border border-slate-300 rounded-md p-2 text-center bg-slate-50">
                        </div>
                    </div>
                    <div class="flex gap-2">
                        <button onclick="clearSearch()" class="w-1/3 bg-slate-200 hover:bg-slate-300 text-slate-800 font-medium py-2 px-2 rounded-md transition-colors shadow-sm text-sm" title="Rensa filter">Rensa</button>
                        <button onclick="performSearch()" class="w-2/3 bg-orange-600 hover:bg-orange-700 text-white font-medium py-2 px-2 rounded-md transition-colors shadow-sm text-sm">Sök</button>
                    </div>
                </div>
            </div>
            <div id="search-results" class="hidden">
                <div class="mb-2 text-sm text-slate-600 font-medium" id="search-summary-text"></div>
                <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                    <div class="overflow-x-auto custom-scroll" style="max-height: 750px;">
                        <table class="w-full text-left text-sm whitespace-nowrap relative">
                            <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200 sticky top-0 z-10 shadow-sm">
                                <tr>
                                    <th class="px-4 py-3">Säsong</th><th class="px-4 py-3">Omgång</th><th class="px-4 py-3">Datum</th>
                                    <th class="px-4 py-3 text-right">Hemmalag</th><th class="px-4 py-3 text-center">Resultat</th>
                                    <th class="px-4 py-3">Bortalag</th><th class="px-4 py-3 text-right">Publik</th>
                                </tr>
                            </thead>
                            <tbody id="search-table-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                        </table>
                    </div>
                    <div id="search-notes" class="bg-slate-50 p-3 border-t border-slate-200 text-xs text-rose-600 font-semibold flex flex-col gap-1 hidden"></div>
                </div>
            </div>
        </section>

        <!-- FLIK 3: Rekord -->
        <section id="tab-records" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                    <div>
                        <h2 class="text-xl font-bold">Historiska Topplistor</h2>
                        <p class="text-sm text-slate-500">Listorna redovisar exakt <span class="font-bold">År</span> som matchen spelades.</p>
                    </div>
                    <div class="w-full md:w-64">
                        <select id="records-team" onchange="renderRecords()" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500"></select>
                    </div>
                </div>

                <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
                    <div class="border border-slate-200 rounded-lg overflow-hidden">
                        <div class="bg-slate-50 px-4 py-3 border-b border-slate-200"><h3 class="font-bold text-slate-700" id="rec-title-wins">Största segrarna</h3></div>
                        <div class="p-0 overflow-x-auto"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-list-wins"></tbody></table></div>
                    </div>
                    <div class="border border-slate-200 rounded-lg overflow-hidden">
                        <div class="bg-slate-50 px-4 py-3 border-b border-slate-200"><h3 class="font-bold text-slate-700" id="rec-title-losses">Största förlusterna</h3></div>
                        <div class="p-0 overflow-x-auto"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-list-losses"></tbody></table></div>
                    </div>
                    <div class="border border-slate-200 rounded-lg overflow-hidden">
                        <div class="bg-slate-50 px-4 py-3 border-b border-slate-200"><h3 class="font-bold text-slate-700" id="rec-title-goals">Målrikaste matcherna</h3></div>
                        <div class="p-0 overflow-x-auto"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-list-goals"></tbody></table></div>
                    </div>
                </div>
                
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div class="border border-slate-200 rounded-lg overflow-hidden">
                        <div class="bg-slate-50 px-4 py-3 border-b border-slate-200"><h3 class="font-bold text-slate-700" id="rec-title-att-high">Högsta publiksiffrorna</h3></div>
                        <div class="p-0 overflow-x-auto"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-list-att-high"></tbody></table></div>
                    </div>
                    <div class="border border-slate-200 rounded-lg overflow-hidden">
                        <div class="bg-slate-50 px-4 py-3 border-b border-slate-200"><h3 class="font-bold text-slate-700" id="rec-title-att-low">Lägsta publiksiffrorna (>10)</h3></div>
                        <div class="p-0 overflow-x-auto"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-list-att-low"></tbody></table></div>
                        <div class="px-4 py-2 bg-slate-50 text-xs text-slate-500 border-t border-slate-200">* Matcher med 10 åskådare eller färre är exkluderade.</div>
                    </div>
                </div>
            </div>
        </section>

        <!-- FLIK 4: Sviter -->
        <section id="tab-streaks" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 items-end mb-6">
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Välj lag för att beräkna sviter</label>
                        <select id="streaks-team" onchange="calculateStreaks()" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500">
                        </select>
                    </div>
                    <div class="flex gap-4 bg-slate-100 p-2 rounded-md justify-center">
                        <label class="flex items-center gap-1 cursor-pointer text-sm font-medium"><input type="radio" name="streak-context" value="all" checked onchange="calculateStreaks()"> Totalt</label>
                        <label class="flex items-center gap-1 cursor-pointer text-sm font-medium"><input type="radio" name="streak-context" value="home" onchange="calculateStreaks()"> Endast Hemma</label>
                        <label class="flex items-center gap-1 cursor-pointer text-sm font-medium"><input type="radio" name="streak-context" value="away" onchange="calculateStreaks()"> Endast Borta</label>
                    </div>
                    <div class="flex flex-col gap-2">
                        <div class="bg-orange-50 border border-orange-100 p-2 rounded-md">
                            <label class="flex items-center gap-2 cursor-pointer text-sm font-semibold text-orange-800">
                                <input type="checkbox" id="streak-from-start" onchange="calculateStreaks()" class="w-4 h-4 text-orange-600"> Enbart från säsongsstart
                            </label>
                        </div>
                        <div class="bg-orange-50 border border-orange-100 p-2 rounded-md">
                            <label class="flex items-center gap-2 cursor-pointer text-sm font-semibold text-orange-800">
                                <input type="checkbox" id="streak-same-season" onchange="calculateStreaks()" class="w-4 h-4 text-orange-600"> Bryt svit vid säsongsslut
                            </label>
                        </div>
                    </div>
                </div>
                
                <h3 class="text-lg font-bold mb-4 text-slate-700" id="streaks-main-title">Längsta Sviterna (Klicka på korten för lista)</h3>
                <div id="streaks-results" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4 hidden mb-8"></div>
                
                <div id="season-records-section" class="hidden">
                    <h3 class="text-lg font-bold mb-4 text-slate-700" id="season-records-title">Max totalt under en säsong</h3>
                    <div id="season-records-results" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8"></div>
                </div>

                <div class="mt-8 pt-8 border-t border-slate-200">
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-4">
                        <h3 class="font-bold text-lg text-slate-700">Topp 10: Historiska Sviter</h3>
                        <select id="streak-toplist-type" onchange="renderStreakToplist()" class="w-full md:w-64 border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500">
                            <option value="win" selected>Längsta Segersvit</option>
                            <option value="unb">Längst Obesegrade</option>
                            <option value="loss">Längsta Förlustsvit</option>
                            <option value="winless">Längst Utan Seger</option>
                            <option value="draw">Flest Oavgjorda i rad</option>
                            <option value="cs">Flest Hållna Nollor i rad</option>
                            <option value="ns">Längsta Måltorka i rad</option>
                        </select>
                    </div>
                    
                    <div id="streak-toplist-container" class="hidden bg-white rounded-lg border border-slate-200 overflow-hidden">
                        <div class="overflow-x-auto">
                            <table class="w-full text-left text-sm whitespace-nowrap">
                                <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200">
                                    <tr><th class="p-3 w-10">#</th><th class="p-3">Lag</th><th class="p-3 text-center">Antal Matcher</th><th class="p-3 text-slate-500">Start</th><th class="p-3 text-slate-500">Slut</th><th class="p-3 text-center">Målskillnad</th></tr>
                                </thead>
                                <tbody id="streak-toplist-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div id="streaks-placeholder" class="text-center py-10 text-slate-500">Kalkylatorn letar fram de längsta sviterna.</div>
            </div>
        </section>

        <!-- FLIK 5: Tabeller -->
        <section id="tab-tables" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <h2 class="text-xl font-bold mb-4">Dynamisk Serietabell</h2>
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end mb-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Säsong</label>
                        <select id="table-season" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500"></select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Efter omgång</label>
                        <input type="text" id="table-round" placeholder="T.ex. 15" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500">
                    </div>
                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="block text-sm font-medium text-slate-700 mb-1">Perspektiv</label>
                            <select id="table-perspective" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500">
                                <option value="ALL">Totalt (Fulltid)</option>
                                <option value="HOME">Hemmatabell</option>
                                <option value="AWAY">Bortatabell</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-slate-700 mb-1">Poäng/Seger</label>
                            <select id="table-points" onchange="if(!document.getElementById('table-results').classList.contains('hidden')){ if(document.getElementById('table-title').innerText.includes('Maratontabell')) renderDynamicAllTimeTable(); else calculateLeagueTable(); }" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500">
                                <option value="3">3 p</option><option value="2">2 p</option>
                            </select>
                        </div>
                    </div>
                    <div>
                        <button onclick="calculateLeagueTable()" class="w-full bg-orange-600 hover:bg-orange-700 text-white font-medium p-2 rounded-md shadow-sm">Bygg Tabell</button>
                    </div>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end border-t border-slate-100 pt-4">
                    <div class="md:col-span-2">
                        <label class="block text-sm font-medium text-slate-700 mb-1">Maratontabell (Välj epok eller totalt)</label>
                        <div class="flex gap-2">
                            <select id="table-epoch" class="w-2/3 border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500"></select>
                            <button onclick="renderDynamicAllTimeTable()" class="w-1/3 bg-slate-800 hover:bg-slate-900 text-white font-medium py-2 px-4 rounded-md shadow-sm text-sm">Visa Maraton</button>
                        </div>
                    </div>
                </div>
            </div>
            
            <div id="table-results" class="hidden bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden mb-6">
                <div class="bg-slate-50 p-3 border-b border-slate-200 flex flex-col md:flex-row justify-between items-start md:items-center">
                    <div class="flex items-center gap-4">
                        <h3 class="font-bold text-slate-700" id="table-title">Tabell</h3>
                        <span id="table-goal-stats" class="text-xs font-semibold text-orange-800 bg-orange-100 px-3 py-1 rounded hidden border border-orange-200 shadow-sm"></span>
                    </div>
                    <div id="table-legend" class="text-[10px] text-slate-500 flex flex-wrap gap-3 mt-2 md:mt-0 hidden">
                        <span class="flex items-center"><span class="text-emerald-600 mr-1 text-sm">⬆️</span> Till Allsvenskan</span>
                        <span class="flex items-center"><span class="text-emerald-500 mr-1 text-sm">↗️</span> Kval uppåt</span>
                        <span class="flex items-center"><span class="bg-purple-100 text-purple-600 px-1 rounded font-bold mr-1">⬇️A</span> Nedflyttad från Allsvenskan</span>
                        <span class="flex items-center"><span class="bg-blue-100 text-blue-600 px-1 rounded font-bold mr-1">NY</span> Nykomling (från Div 1)</span>
                        <span class="flex items-center"><span class="text-rose-600 font-bold mr-1">↓</span> Degraderad</span>
                    </div>
                </div>
                <div class="overflow-x-auto custom-scroll" style="max-height: 750px;">
                    <table class="w-full text-left text-sm whitespace-nowrap relative">
                        <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200 sticky top-0 z-10 shadow-sm" id="league-table-head"></thead>
                        <tbody id="league-table-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                    </table>
                </div>
                <!-- Fotnoter -->
                <div id="table-notes" class="bg-slate-50 p-3 border-t border-slate-200 text-xs text-rose-600 font-semibold flex flex-col gap-1 hidden"></div>
            </div>

            <div id="team-trend-section" class="hidden bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 border-b border-slate-100 pb-4">
                    <h3 class="font-bold text-lg text-slate-700" id="trend-title">Placeringsutveckling under säsongen</h3>
                    <div class="w-full md:w-64 mt-2 md:mt-0">
                        <select id="trend-team-select" onchange="renderTeamTrend()" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500"></select>
                    </div>
                </div>
                <div class="relative h-72 w-full"><canvas id="teamTrendChart"></canvas></div>
            </div>
        </section>

        <!-- FLIK 6: SÄSONGENS PROFILER -->
        <section id="tab-profiles" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <h2 class="text-xl font-bold mb-2">Säsongens Profiler i Superettan</h2>
                <p class="text-slate-500 text-sm mb-4">Fokusera på lagen som var nya för serien i år, samt de som tog klivet upp till Allsvenskan.</p>
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Välj Säsong</label>
                        <select id="profiles-season" onchange="renderProfiles()" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500"></select>
                    </div>
                </div>
            </div>
            <div id="profiles-results" class="hidden flex flex-col gap-6">
                <div id="profile-champions"></div>
                <div id="profile-defending"></div>
                <div id="profile-promoted"></div>
            </div>
            <div id="profiles-placeholder" class="text-center py-10 text-slate-500">Välj en säsong ovan för att se detaljerad historik.</div>
        </section>

        <!-- FLIK 7: SÄSONGSSTYRKA -->
        <section id="tab-strength" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <div class="flex items-center gap-3 mb-2">
                            <span class="text-2xl">💪</span>
                            <h2 class="text-xl font-bold text-slate-800">Säsongsstyrka (Historisk Ranking Superettan)</h2>
                        </div>
                        <p class="text-slate-500 text-sm max-w-3xl">Vilken säsong var egentligen tuffast? Genom att värdera varje deltagande lag utifrån deras <b class="text-slate-700">historiska totalpoäng i Superettan</b> och <b class="text-slate-700">Maratonplacering</b> får vi fram ett styrkeindex för hela ligan respektive toppstriden.</p>
                    </div>
                    <div class="tooltip-container relative cursor-pointer z-50">
                        <div class="bg-orange-100 text-orange-800 rounded-full w-8 h-8 flex items-center justify-center font-bold font-serif">i</div>
                        <div class="tooltip-content hidden absolute right-0 top-10 w-96 bg-slate-800 text-white text-xs p-4 rounded shadow-xl">
                            <p class="font-bold mb-2 text-sm text-orange-300">Så här fungerar kolumnerna:</p>
                            <p class="mb-2"><span class="font-bold text-emerald-400">Snitt Maratontabell (Topp 3):</span> Ett värde på 2.0 innebär att platserna 1, 2 och 3 togs av de tre lag som leder Superettans maratontabell. Ett lägre värde = fler Superettan-veteraner i toppen.</p>
                            <p class="mb-2"><span class="font-bold text-emerald-400">Snitt Maratontabell (Hela Serien):</span> Samma princip men för alla lag i serien.</p>
                            <p><span class="font-bold text-orange-300">Styrkeindex (0-100):</span> Beräknas genom att ta de deltagande lagens <i>historiska poängsnitt per match (PPG) i Superettan</i>, slå ihop det till ett snitt för säsongen, och multiplicera med 50. <b>Ju högre index, desto fler framgångsrika lag deltog det året.</b></p>
                        </div>
                    </div>
                </div>
                <button onclick="runStrengthAnalysis()" id="btn-run-strength" class="bg-orange-600 hover:bg-orange-700 text-white font-bold py-3 px-6 rounded-md shadow-sm transition-colors flex items-center gap-2">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2m0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                    Beräkna Historisk Säsongsstyrka
                </button>
            </div>
            
            <div id="strength-loading" class="hidden text-center py-10">
                <div class="inline-block animate-spin w-8 h-8 border-4 border-orange-600 border-t-transparent rounded-full mb-4"></div>
                <p class="text-slate-500 font-medium">Sammanställer All-Time-data och utvärderar alla säsonger...</p>
            </div>

            <div id="strength-results" class="hidden bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                <div class="bg-slate-50 p-4 border-b border-slate-200">
                    <h3 class="font-bold text-slate-800">Ranking av Superettan-säsonger</h3>
                </div>
                <div class="overflow-x-auto custom-scroll" style="max-height: 750px;">
                    <table class="w-full text-left text-sm whitespace-nowrap relative">
                        <thead class="bg-slate-100 text-slate-600 font-medium sticky top-0 z-10 shadow-sm">
                            <tr>
                                <th class="px-4 py-3 sortable-th" onclick="sortStrength('season')">Säsong ↕</th>
                                <th class="px-4 py-3 sortable-th text-center" onclick="sortStrength('nTeams')">Antal Lag ↕</th>
                                <th class="px-4 py-3 sortable-th text-center text-slate-500" onclick="sortStrength('avgRank')" title="Lägst är bäst">Snitt Maratontabell (Hela Serien) ↕</th>
                                <th class="px-4 py-3 sortable-th text-center text-slate-500" onclick="sortStrength('avgTop3Rank')" title="Lägst är bäst">Snitt Maratontabell (Topp 3) ↕</th>
                                <th class="px-4 py-3 sortable-th text-center font-bold text-orange-600" onclick="sortStrength('index')" title="Baserat på lagens historiska PPG (Points per game). Högst är starkast!">Styrkeindex ↕</th>
                            </tr>
                        </thead>
                        <tbody id="strength-table-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- FLIK 8: TOPPSTRIDEN -->
        <section id="tab-goldrace" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <div class="flex items-center gap-3 mb-2">
                    <span class="text-2xl">📈</span>
                    <h2 class="text-xl font-bold text-slate-800">Toppstriden & Direktuppflyttning</h2>
                </div>
                <p class="text-slate-500 text-sm mb-6 max-w-3xl">Här analyseras kampen om de två översta platserna (Direktuppflyttning). Vem har legat på Topp 2 flest gånger? Vilka tappade en direktplats i allra sista omgången?</p>
                <button onclick="runPromotionRaceAnalysis()" id="btn-run-gold" class="bg-amber-500 hover:bg-amber-600 text-white font-bold py-3 px-6 rounded-md shadow-sm transition-colors flex items-center gap-2">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                    Kör Analys av Toppstriden
                </button>
            </div>
            <div id="goldrace-loading" class="hidden text-center py-10">
                <div class="inline-block animate-spin w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full mb-4"></div>
                <p class="text-slate-500 font-medium">Processar och bygger omgångstabeller för alla säsonger...</p>
            </div>
            <div id="goldrace-results" class="hidden flex flex-col gap-6">
                <div class="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                    <div class="bg-slate-50 border-b border-slate-200 p-4">
                        <h3 class="font-bold text-slate-800">Dramatik i sista omgången (Tappade Top 2-platser)</h3>
                        <p class="text-xs text-slate-500 mt-1">Säsonger där ett lag låg på Topp 2 (uppflyttning) inför sista omgången, men <b>tappade platsen</b> på målsnöret.</p>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-sm whitespace-nowrap">
                            <thead class="bg-slate-100 text-slate-600"><tr><th class="p-3">Säsong</th><th class="p-3 text-rose-600">Laget som snubblade (Top 2 -> Miss)</th><th class="p-3 text-emerald-600">Laget som tog platsen</th></tr></thead>
                            <tbody id="gr-late-winners" class="divide-y divide-slate-100"></tbody>
                        </table>
                    </div>
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div class="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                        <div class="bg-slate-50 border-b border-slate-200 p-4"><h3 class="font-bold text-slate-800">Dominanterna</h3><p class="text-xs text-slate-500 mt-1">Flest omgångar på <b>Topp 2</b> under en och samma säsong.</p></div>
                        <div class="overflow-x-auto">
                            <table class="w-full text-left text-sm whitespace-nowrap"><thead class="bg-slate-100 text-slate-600"><tr><th class="p-3">#</th><th class="p-3">Lag</th><th class="p-3">Säsong</th><th class="p-3 text-center">Omg. på Topp 2</th></tr></thead><tbody id="gr-most-lead" class="divide-y divide-slate-100"></tbody></table>
                        </div>
                    </div>
                    <div class="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                        <div class="bg-slate-50 border-b border-slate-200 p-4"><h3 class="font-bold text-slate-800">Snubblarna</h3><p class="text-xs text-slate-500 mt-1">Flest omgångar på Topp 2 <b>utan</b> att sluta Topp 2.</p></div>
                        <div class="overflow-x-auto">
                            <table class="w-full text-left text-sm whitespace-nowrap"><thead class="bg-slate-100 text-slate-600"><tr><th class="p-3">#</th><th class="p-3 text-rose-600">Tappade platsen</th><th class="p-3">Säsong</th><th class="p-3 text-center">Omg. på Topp 2</th></tr></thead><tbody id="gr-most-lead-nowin" class="divide-y divide-slate-100"></tbody></table>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- FLIK 9: Analys (Förutsägbarhet) -->
        <section id="tab-analysis" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <h2 class="text-xl font-bold mb-1">Har serien "satt sig"?</h2>
                        <p class="text-slate-500 text-sm max-w-3xl">Mät tabellens förutsägbarhet över tid. Välj mellan att se utvecklingen över en säsong/epok i en graf, eller jämför alla säsonger i en specifik omgång.</p>
                    </div>
                    <div class="tooltip-container relative cursor-pointer z-50">
                        <div class="bg-orange-100 text-orange-800 rounded-full w-8 h-8 flex items-center justify-center font-bold font-serif">i</div>
                        <div class="tooltip-content hidden absolute right-0 top-10 w-80 bg-slate-800 text-white text-xs p-4 rounded shadow-xl">
                            <p class="font-bold mb-2 text-sm text-orange-300">Analysmetoder:</p>
                            <p class="mb-2"><span class="font-bold text-emerald-400">Positionsfel (MAE):</span> Visar hur många placeringar lagen i snitt ligger ifrån sin slutgiltiga placering. Ett värde på 1.5 betyder att lagen i snitt skiljer sig 1.5 placeringar från facit.</p>
                            <p class="mb-2"><span class="font-bold text-emerald-400">Spearmans Rangkorrelation:</span> Ett matematiskt mått mellan -1 och 1. Värdet 1.0 betyder att tabellen är 100% identisk med sluttabellen. Allt över 0.8 anses vara ett mycket starkt samband.</p>
                            <p><span class="font-bold text-orange-300">Delstrider (Topp/Botten 3):</span> Rankingen skalas om från 1 till 3 internt för dessa lag innan Spearmans beräknas, för att säkerställa att värdet håller sig strikt inom -1 till 1.</p>
                        </div>
                    </div>
                </div>

                <div class="flex gap-4 mb-6 border-b border-slate-200 pb-2">
                    <button onclick="toggleAnalysisMode('chart')" id="btn-mode-chart" class="font-bold text-orange-600 border-b-2 border-orange-600 px-2 pb-1 transition-colors">Utveckling över omgångar</button>
                    <button onclick="toggleAnalysisMode('table')" id="btn-mode-table" class="font-medium text-slate-500 hover:text-orange-600 px-2 pb-1 transition-colors">Jämför vid specifik omgång</button>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1" id="lbl-analysis-season">Välj Epok / Säsong</label>
                        <select id="analysis-season" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500"></select>
                    </div>
                    <div id="div-analysis-round" class="hidden">
                        <label class="block text-sm font-medium text-slate-700 mb-1">Utvärdera efter omgång</label>
                        <input type="number" id="analysis-round" value="10" min="1" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Fokusområde</label>
                        <select id="analysis-focus" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-orange-500">
                            <option value="all">Hela tabellen</option><option value="top">Toppstriden (3 lag)</option><option value="bottom">Bottenstriden (3 lag)</option>
                        </select>
                    </div>
                    <div>
                        <button onclick="runPredictabilityAnalysis()" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2 px-4 rounded-md shadow-sm">Kör Analys</button>
                    </div>
                </div>
            </div>
            
            <div id="analysis-results" class="hidden">
                <div id="analysis-warning" class="hidden mb-4 p-4 rounded-md text-sm border"></div>
                <div id="analysis-chart-container" class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                    <div class="relative h-96 w-full"><canvas id="analysisChart"></canvas></div>
                </div>
                <div id="analysis-comparison-table" class="hidden bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden mb-6">
                    <div class="bg-slate-50 p-3 border-b border-slate-200 flex justify-between items-center"><h3 class="font-bold text-slate-700" id="comparison-title">Jämförelse vid omgång X</h3></div>
                    <div class="overflow-x-auto custom-scroll" style="max-height: 500px;">
                        <table class="w-full text-left text-sm whitespace-nowrap">
                            <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200 sticky top-0 z-10 shadow-sm">
                                <tr><th class="p-3">Säsong</th><th class="p-3 text-center">Positionsfel (MAE)</th><th class="p-3 text-center">Spearmans Korrelation</th></tr>
                            </thead>
                            <tbody id="comparison-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                        </table>
                    </div>
                </div>
                <div id="analysis-details" class="hidden bg-slate-800 rounded-lg shadow-lg border border-slate-700 p-6 text-white mb-6">
                    <div class="flex justify-between items-end mb-6">
                        <div>
                            <h3 class="text-xl font-bold text-blue-300" id="details-title">Omgång X</h3>
                            <p class="text-sm text-slate-400">Jämförelse mellan denna omgång och sluttabellen.</p>
                        </div>
                        <div class="text-right">
                            <div class="text-sm text-slate-400">Genomsnittligt fel: <span id="details-mae" class="text-white font-bold"></span> placeringar</div>
                            <div class="text-sm text-slate-400">Spearmans Korrelation: <span id="details-spearman" class="text-emerald-400 font-bold"></span></div>
                        </div>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-sm whitespace-nowrap bg-slate-900 rounded-lg overflow-hidden">
                            <thead class="bg-slate-700 text-slate-300 border-b border-slate-600">
                                <tr><th class="p-3">Lag</th><th class="p-3 text-center">Placering Nu</th><th class="p-3 text-center text-emerald-300">Slutplacering (Facit)</th><th class="p-3 text-center font-bold">Diff</th></tr>
                            </thead>
                            <tbody id="details-body" class="divide-y divide-slate-800"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </section>

        <!-- MODAL FÖR SVIT-MATCHER -->
        <div id="streak-modal" class="hidden fixed inset-0 bg-slate-900/50 z-50 flex items-center justify-center p-4">
            <div class="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col">
                <div class="p-4 border-b flex justify-between items-center bg-slate-50 rounded-t-lg">
                    <h3 id="modal-title" class="text-lg font-bold text-slate-800"></h3>
                    <button onclick="closeStreakModal()" class="text-slate-500 hover:text-slate-800 p-1"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button>
                </div>
                <div class="p-0 overflow-y-auto custom-scroll flex-1">
                    <table class="w-full text-left text-sm whitespace-nowrap">
                        <thead class="bg-slate-100 sticky top-0 shadow-sm border-b border-slate-200">
                            <tr><th class="p-3">Säsong</th><th class="p-3">Omg.</th><th class="p-3">Datum</th><th class="p-3 text-right">Hemmalag</th><th class="p-3 text-center">Resultat</th><th class="p-3">Bortalag</th></tr>
                        </thead>
                        <tbody id="modal-tbody" class="divide-y divide-slate-100 text-slate-700"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </main>

    <script>
        const MATCH_DATA = %%MATCH_DATA_JSON%%;
        const TEAMS = %%TEAMS_JSON%%;
        const SEASONS = %%SEASONS_JSON%%;
        const SEASON_INFO = %%SEASON_INFO_JSON%%; 
        const DECADES = %%DECADES_JSON%%;
        const CUSTOM_EPOCHS = %%CUSTOM_EPOCHS_JSON%%;
        const TEAM_MERITS = %%TEAM_MERITS_JSON%%; 
        
        let currentOverviewData = []; let currentOverviewSort = { col: 'played', asc: false }; let currentStreakMatches = {}; 
        let globalAllStreaks = []; 
        let ALL_TIME_TABLE = []; let TEAM_RANKS = {}; let TEAM_ALLTIME_PPG = {}; let analysisChartInstance = null; let globalAnalysisData = {}; 
        let analysisMode = 'chart'; let globalSeasonRanks = {}; let globalSeasonTeams = []; let trendChartInstance = null;
        let currentStrengthData = []; let currentStrengthSort = { col: 'index', asc: false };

        function formatDate(val, fallbackYear) {
            if (val === null || val === "" || val === undefined) return fallbackYear || '-';
            if (typeof val === 'number') {
                if (Math.abs(val) > 0 && Math.abs(val) < 10000) return String(val); 
                return new Date(val).toISOString().split('T')[0]; 
            }
            let s = String(val); return s.length > 10 ? s.substring(0, 10) : s;
        }

        function extractYear(dateVal, fallback) {
            if (dateVal === null || dateVal === "" || dateVal === undefined) return fallback || '-';
            if (typeof dateVal === 'number') {
                if (Math.abs(dateVal) > 10000) return new Date(dateVal).getFullYear().toString();
                return String(dateVal);
            }
            const s = String(dateVal); return s.length >= 4 ? s.substring(0, 4) : fallback || '-';
        }

        function getSeasonName(sasId) { return (SEASON_INFO[sasId] && SEASON_INFO[sasId].name) ? SEASON_INFO[sasId].name : String(sasId); }

        function getNoteString(team1, team2, notText, dateStr) {
            if (!notText) return null;
            let nTxt = String(notText).toUpperCase();
            let noteFound = null;

            if (nTxt.includes("EJ KVALIFICERAD SPELARE; V")) noteFound = "Ej kvalificerad spelare, dömt till hemmaseger.";
            else if (nTxt.includes("EJ KVALIFICERAD SPELARE; F")) noteFound = "Ej kvalificerad spelare, dömt till bortaseger.";
            else if (nTxt.includes("W.O; H")) noteFound = "W.O. till hemmalaget.";
            else if (nTxt.includes("W.O; B")) noteFound = "W.O. till bortalaget.";
            else if (nTxt.includes("AVBRUTEN; V")) noteFound = "Avbruten, dömt till hemmaseger.";
            else if (nTxt.includes("AVBRUTEN; F")) noteFound = "Avbruten, dömt till bortaseger.";
            else if (nTxt.includes("AVBRUTEN; O")) noteFound = "Avbruten, dömt till en poäng vardera.";
            else if (nTxt.includes("AVBRUTEN")) noteFound = "Avbruten match.";
            
            if (noteFound) {
                return dateStr ? `${dateStr} (${team1}-${team2}): ${noteFound}` : `(${team1}-${team2}): ${noteFound}`;
            }
            return null;
        }

        function updatePhaseDropdown() {
            const season = document.getElementById('table-season').value;
            const phaseSelect = document.getElementById('table-phase');
            if (!phaseSelect) return;
            let isM = ["67", "68", "1991", "1992"].includes(String(season));
            Array.from(phaseSelect.options).forEach(opt => {
                if(opt.value !== "ALL") {
                    opt.disabled = !isM;
                    if(!isM) opt.classList.add('text-slate-300'); else opt.classList.remove('text-slate-300');
                }
            });
            if(!isM && phaseSelect.value !== "ALL") phaseSelect.value = "ALL";
        }

        document.addEventListener('DOMContentLoaded', () => {
            initAllTimeTable(); populateAllDropdowns();
            if(ALL_TIME_TABLE.length >= 2) {
                document.getElementById('h2h-team-a').value = ALL_TIME_TABLE[0].team;
                updateOpponentDropdown('h2h-team-a', 'h2h-team-b');
                
                // Leta upp en giltig motståndare till lag A (om 2an inte har mött 1an väljer den första bästa)
                let bOpts = Array.from(document.getElementById('h2h-team-b').options);
                let validB = bOpts.filter(o => !o.disabled && o.value !== "").map(o => o.value);
                if (validB.includes(ALL_TIME_TABLE[1].team)) {
                    document.getElementById('h2h-team-b').value = ALL_TIME_TABLE[1].team;
                } else if (validB.length > 0) {
                    document.getElementById('h2h-team-b').value = validB[0];
                }
            }
            updateRankDisplays();
            
            // H2H räknas ut och renderas direkt på startskärmen
            calculateH2H();
            
            document.getElementById('h2h-team-a').addEventListener('change', () => { updateOpponentDropdown('h2h-team-a', 'h2h-team-b'); updateRankDisplays(); document.getElementById('h2h-overview').classList.add('hidden'); document.getElementById('h2h-results').classList.add('hidden'); });
            document.getElementById('h2h-team-b').addEventListener('change', () => { updateOpponentDropdown('h2h-team-b', 'h2h-team-a'); updateRankDisplays(); document.getElementById('h2h-overview').classList.add('hidden'); document.getElementById('h2h-results').classList.add('hidden'); });
            document.getElementById('search-season').addEventListener('change', () => { updateSearchTeamDropdown(); });
            document.getElementById('table-season').addEventListener('change', (e) => { 
                const sas = e.target.value; 
                if (SEASON_INFO[sas] && SEASON_INFO[sas].pts) document.getElementById('table-points').value = SEASON_INFO[sas].pts; 
                updatePhaseDropdown();
            });
            if (SEASONS.length > 0) document.getElementById('search-season').value = [...SEASONS].reverse()[0];
            
            updatePhaseDropdown();
            
            // Topplistor och sviter räknas ut direkt i bakgrunden så att de syns när man byter flik
            renderRecords(); 
            calculateStreaks(); 
        });

        function initAllTimeTable() {
            let table = {};
            MATCH_DATA.forEach(m => {
                [m.Hemmalag, m.Bortalag].forEach(t => { if(!table[t]) table[t] = { team: t, pld:0, w:0, d:0, l:0, gf:0, ga:0, gd:0, pts:0, seasons: new Set() }; });
                let hm = parseInt(m.HM); let bm = parseInt(m.BM);
                let notText = String(m.NOT).toUpperCase();
                let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                
                if (isNaN(hm) || isNaN(bm)) {
                    if (!(isWOH || isWOB)) return;
                    hm = 0; bm = 0; 
                } 
                table[m.Hemmalag].pld++; table[m.Bortalag].pld++;
                table[m.Hemmalag].gf += hm; table[m.Bortalag].gf += bm;
                table[m.Hemmalag].ga += bm; table[m.Bortalag].ga += hm;
                
                if (isWOH) { table[m.Hemmalag].w++; table[m.Bortalag].l++; table[m.Hemmalag].pts += 3; }
                else if (isWOB) { table[m.Bortalag].w++; table[m.Hemmalag].l++; table[m.Bortalag].pts += 3; }
                else if (hm > bm) { table[m.Hemmalag].w++; table[m.Bortalag].l++; table[m.Hemmalag].pts += 3; }
                else if (hm < bm) { table[m.Bortalag].w++; table[m.Hemmalag].l++; table[m.Bortalag].pts += 3; }
                else { table[m.Hemmalag].d++; table[m.Bortalag].d++; table[m.Hemmalag].pts += 1; table[m.Bortalag].pts += 1; }
                table[m.Hemmalag].seasons.add(String(m.Säs)); table[m.Bortalag].seasons.add(String(m.Säs));
            });
            
            Object.values(table).forEach(t => {
                let totalDeduction = 0;
                t.seasons.forEach(sas => {
                    let mInfo = TEAM_MERITS[sas] && TEAM_MERITS[sas][t.team];
                    if (mInfo && mInfo.start_pts < 0) {
                        totalDeduction += mInfo.start_pts;
                    }
                });
                t.pts += totalDeduction;
            });

            let arr = Object.values(table);
            arr.forEach(r => { r.gd = r.gf - r.ga; TEAM_ALLTIME_PPG[r.team] = r.pts / r.pld; });
            arr.sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf);
            ALL_TIME_TABLE = arr;
            arr.forEach((r, i) => { TEAM_RANKS[r.team] = i + 1; });
        }

        function updateRankDisplays() {
            const teamA = document.getElementById('h2h-team-a').value; const teamB = document.getElementById('h2h-team-b').value;
            const elA = document.getElementById('rank-team-a'); const elB = document.getElementById('rank-team-b');
            if(teamA && TEAM_RANKS[teamA]) elA.innerText = `(Maratonplacering: ${TEAM_RANKS[teamA]})`; else elA.innerText = '';
            if(teamB && TEAM_RANKS[teamB]) elB.innerText = `(Maratonplacering: ${TEAM_RANKS[teamB]})`; else elB.innerText = '';
        }

        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            document.getElementById('btn-' + tabId).classList.add('active');
        }

        function populateAllDropdowns() {
            let teamOpts = ''; TEAMS.forEach(team => { teamOpts += `<option value="${team}">${team}</option>`; });
            document.getElementById('h2h-team-a').innerHTML = '<option value="">-- Välj ett lag --</option>' + teamOpts;
            document.getElementById('h2h-team-b').innerHTML = '<option value="">-- Välj ett lag --</option>' + teamOpts;
            document.getElementById('search-team').innerHTML = '<option value="">-- Alla lag --</option>' + teamOpts;
            document.getElementById('records-team').innerHTML = '<option value="">-- Totalt i Superettan --</option>' + teamOpts;
            document.getElementById('streaks-team').innerHTML = '<option value="ALL">-- Alla Lag (Historiska Rekord) --</option>' + teamOpts;

            let seasonOpts = '<option value="">-- Alla säsonger --</option>';
            [...SEASONS].reverse().forEach(s => { if(s) seasonOpts += `<option value="${s}">${getSeasonName(s)}</option>`; });
            document.getElementById('search-season').innerHTML = seasonOpts;
            document.getElementById('table-season').innerHTML = seasonOpts.replace('<option value="">-- Alla säsonger --</option>', '<option value="">-- Välj säsong --</option>');
            document.getElementById('profiles-season').innerHTML = seasonOpts.replace('<option value="">-- Alla säsonger --</option>', '<option value="">-- Välj säsong --</option>');
            
            if (SEASONS.length > 0) document.getElementById('search-season').value = [...SEASONS].reverse()[0];
            updateSearchTeamDropdown();
            
            let epokOpts = '<option value="ALL">Totalt (Alla säsonger)</option>';
            let analysisOpts = '<option value="">-- Välj säsong/epok --</option><option value="ALL_SEASONS">-- Alla säsonger --</option>';
            
            if (Object.keys(CUSTOM_EPOCHS).length > 0) {
                let block = '<optgroup label="Egna Epoker (Från Excel)">';
                Object.keys(CUSTOM_EPOCHS).forEach(d => { block += `<option value="EPOCH_CUSTOM_${d}">${d}</option>`; });
                block += '</optgroup>'; epokOpts += block; analysisOpts += block;
            }
            if (Object.keys(DECADES).length > 0) {
                let block = '<optgroup label="Årtionden">';
                Object.keys(DECADES).reverse().forEach(d => { block += `<option value="EPOCH_DECADE_${d}">${d}</option>`; });
                block += '</optgroup>'; epokOpts += block; analysisOpts += block;
            }
            analysisOpts += '<optgroup label="Enskilda Säsonger">';
            [...SEASONS].reverse().forEach(s => { if(s) analysisOpts += `<option value="${s}">${getSeasonName(s)}</option>`; });
            analysisOpts += '</optgroup>';
            document.getElementById('table-epoch').innerHTML = epokOpts;
            document.getElementById('analysis-season').innerHTML = analysisOpts;
        }

        function updateSearchTeamDropdown() {
            const season = document.getElementById('search-season').value; const targetSelect = document.getElementById('search-team');
            const currentTargetValue = targetSelect.value;
            if (!season) {
                let teamOpts = '<option value="">-- Alla lag --</option>'; TEAMS.forEach(team => { teamOpts += `<option value="${team}">${team}</option>`; });
                targetSelect.innerHTML = teamOpts; targetSelect.value = currentTargetValue; return;
            }
            const validTeams = new Set();
            MATCH_DATA.forEach(m => { if (String(m.Säs) === String(season)) { validTeams.add(m.Hemmalag); validTeams.add(m.Bortalag); } });
            const activeTeams = TEAMS.filter(t => validTeams.has(t)); const inactiveTeams = TEAMS.filter(t => !validTeams.has(t));
            let html = '<option value="">-- Alla lag --</option>';
            if (activeTeams.length > 0) { html += '<optgroup label="Spelade i Superettan denna säsong">'; activeTeams.forEach(t => { html += `<option value="${t}">${t}</option>`; }); html += '</optgroup>'; }
            if (inactiveTeams.length > 0) { html += '<optgroup label="Spelade ej i Superettan" disabled>'; inactiveTeams.forEach(t => { html += `<option value="${t}">${t}</option>`; }); html += '</optgroup>'; }
            targetSelect.innerHTML = html; targetSelect.value = validTeams.has(currentTargetValue) ? currentTargetValue : "";
        }

        function updateOpponentDropdown(sourceId, targetId) {
            const sourceTeam = document.getElementById(sourceId).value; const targetSelect = document.getElementById(targetId);
            const currentTargetValue = targetSelect.value;
            if (!sourceTeam) {
                let options = '<option value="">-- Välj ett lag --</option>'; TEAMS.forEach(team => { options += `<option value="${team}">${team}</option>`; });
                targetSelect.innerHTML = options; targetSelect.value = currentTargetValue; return;
            }
            const opponents = new Set();
            MATCH_DATA.forEach(m => { if (m.Hemmalag === sourceTeam) opponents.add(m.Bortalag); if (m.Bortalag === sourceTeam) opponents.add(m.Hemmalag); });
            const validOpponents = TEAMS.filter(t => opponents.has(t)); const invalidOpponents = TEAMS.filter(t => !opponents.has(t) && t !== sourceTeam);
            let html = '<option value="">-- Välj motståndare --</option>';
            if (validOpponents.length > 0) { html += '<optgroup label="Tidigare motståndare">'; validOpponents.forEach(t => { html += `<option value="${t}">${t}</option>`; }); html += '</optgroup>'; }
            if (invalidOpponents.length > 0) { html += '<optgroup label="Har ej mött" disabled>'; invalidOpponents.forEach(t => { html += `<option value="${t}">${t}</option>`; }); html += '</optgroup>'; }
            targetSelect.innerHTML = html; targetSelect.value = validOpponents.includes(currentTargetValue) ? currentTargetValue : "";
        }

        // --- H2H ---
        function calculateH2H() {
            const teamA = document.getElementById('h2h-team-a').value; const teamB = document.getElementById('h2h-team-b').value;
            const context = document.querySelector('input[name="h2h-context"]:checked').value;
            if (!teamA || !teamB || teamA === teamB) return;
            document.getElementById('h2h-overview').classList.add('hidden');
            let h2hMatches = MATCH_DATA.filter(m => (m.Hemmalag === teamA && m.Bortalag === teamB) || (m.Hemmalag === teamB && m.Bortalag === teamA));
            if (context === 'home') h2hMatches = h2hMatches.filter(m => m.Hemmalag === teamA);
            if (context === 'away') h2hMatches = h2hMatches.filter(m => m.Bortalag === teamA);
            h2hMatches.sort((a, b) => {
                let d1 = new Date(formatDate(a.Matchdatum, a.År)).getTime();
                let d2 = new Date(formatDate(b.Matchdatum, b.År)).getTime();
                if(isNaN(d1)) d1=0; if(isNaN(d2)) d2=0;
                if(d1!==d2) return d1-d2;
                return a.Match_ID - b.Match_ID;
            });
            
            let winsA = 0, draws = 0, winsB = 0, tableHTML = '';
            let matchNotes = new Set();
            
            h2hMatches.forEach(match => {
                const isHomeA = match.Hemmalag === teamA;
                let hm = parseInt(match.HM); let bm = parseInt(match.BM);
                let notText = String(match.NOT).toUpperCase();
                
                let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                
                let origH = match.Hemmalag_Org || match.Hemmalag;
                let origB = match.Bortalag_Org || match.Bortalag;
                let displayDate = formatDate(match.Matchdatum, match.År);
                let noteStr = getNoteString(origH, origB, match.NOT, displayDate);
                if (noteStr) matchNotes.add(noteStr);

                if (isNaN(hm) || isNaN(bm)) {
                    if (!(isWOH || isWOB)) return; hm = 0; bm = 0;
                }
                const matchGoalsA = isHomeA ? hm : bm; const matchGoalsB = isHomeA ? bm : hm;
                
                if (isWOH) { if (isHomeA) winsA++; else winsB++; }
                else if (isWOB) { if (!isHomeA) winsA++; else winsB++; }
                else if (matchGoalsA > matchGoalsB) winsA++; else if (matchGoalsA < matchGoalsB) winsB++; else draws++;

                const homeBold = hm > bm ? 'font-bold text-blue-600' : (bm > hm ? 'text-rose-600' : 'text-slate-900');
                const awayBold = bm > hm ? 'font-bold text-blue-600' : (hm > bm ? 'text-rose-600' : 'text-slate-900');
                tableHTML += `<tr class="hover:bg-slate-50"><td class="px-4 py-2">${getSeasonName(match.Säs)}</td><td class="px-4 py-2 text-slate-500 text-xs">${displayDate}</td><td class="px-4 py-2 text-right ${homeBold}">${origH}</td><td class="px-4 py-2 text-center font-mono bg-slate-50 border-x border-slate-100 font-semibold">${hm} - ${bm}</td><td class="px-4 py-2 ${awayBold}">${origB}</td><td class="px-4 py-2 text-right text-slate-500">${match.Publik ? match.Publik.toLocaleString('sv-SE') : '-'}</td></tr>`;
            });
            document.getElementById('h2h-table-body').innerHTML = tableHTML || '<tr><td colspan="6" class="text-center py-6 text-slate-500">Inga möten hittades.</td></tr>';
            
            let nHtml = "";
            matchNotes.forEach(n => { nHtml += `<div>* ${n}</div>`; });
            const notesEl = document.getElementById('h2h-notes');
            if (nHtml !== "") { notesEl.innerHTML = nHtml; notesEl.classList.remove('hidden'); } else { notesEl.classList.add('hidden'); }

            document.getElementById('h2h-summary-cards').innerHTML = `<div class="bg-blue-50 p-3 rounded-lg border border-blue-100 text-center"><div class="text-xs text-blue-600 font-medium uppercase tracking-wider mb-1">Möten</div><div class="text-2xl font-bold text-blue-900">${h2hMatches.length}</div></div><div class="bg-emerald-50 p-3 rounded-lg border border-emerald-100 text-center"><div class="text-xs text-emerald-600 font-medium uppercase tracking-wider mb-1">Vinster ${teamA}</div><div class="text-2xl font-bold text-emerald-900">${winsA}</div></div><div class="bg-slate-100 p-3 rounded-lg border border-slate-200 text-center"><div class="text-xs text-slate-600 font-medium uppercase tracking-wider mb-1">Oavgjorda</div><div class="text-2xl font-bold text-slate-800">${draws}</div></div><div class="bg-rose-50 p-3 rounded-lg border border-rose-100 text-center"><div class="text-xs text-rose-600 font-medium uppercase tracking-wider mb-1">Vinster ${teamB}</div><div class="text-2xl font-bold text-rose-900">${winsB}</div></div>`;
            document.getElementById('h2h-results').classList.remove('hidden');
        }

        function renderH2HOverview() {
            const teamA = document.getElementById('h2h-team-a').value; const context = document.querySelector('input[name="h2h-context"]:checked').value;
            if (!teamA) { alert("Välj Lag A först."); return; }
            document.getElementById('h2h-results').classList.add('hidden');
            let oppStats = {}; let matches = MATCH_DATA.filter(m => m.Hemmalag === teamA || m.Bortalag === teamA);
            if (context === 'home') matches = matches.filter(m => m.Hemmalag === teamA);
            if (context === 'away') matches = matches.filter(m => m.Bortalag === teamA);
            matches.forEach(m => {
                const isHome = m.Hemmalag === teamA; const opp = isHome ? m.Bortalag : m.Hemmalag;
                let hm = parseInt(m.HM); let bm = parseInt(m.BM);
                let notText = String(m.NOT).toUpperCase();
                let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                
                if(isNaN(hm) || isNaN(bm)) { if (!(isWOH||isWOB)) return; hm=0; bm=0; }
                const gf = isHome ? hm : bm; const ga = isHome ? bm : hm;
                if (!oppStats[opp]) oppStats[opp] = { team: opp, played: 0, w: 0, d: 0, l: 0, gf: 0, ga: 0, gd: 0 };
                oppStats[opp].played++; oppStats[opp].gf += gf; oppStats[opp].ga += ga;
                
                if (isWOH) { if (isHome) oppStats[opp].w++; else oppStats[opp].l++; }
                else if (isWOB) { if (!isHome) oppStats[opp].w++; else oppStats[opp].l++; }
                else if (gf > ga) oppStats[opp].w++; else if (gf < ga) oppStats[opp].l++; else oppStats[opp].d++;
                
                oppStats[opp].gd = oppStats[opp].gf - oppStats[opp].ga;
            });
            currentOverviewData = Object.values(oppStats);
            document.getElementById('overview-title').innerText = `Sammanställning: ${teamA} ${context === 'home' ? '(Endast Hemma)' : context === 'away' ? '(Endast Borta)' : '(Alla Möten)'}`;
            sortOverview('played', true); document.getElementById('h2h-overview').classList.remove('hidden');
        }

        function sortOverview(col, forceDesc = false) {
            if (forceDesc) { currentOverviewSort.col = col; currentOverviewSort.asc = false; }
            else if (currentOverviewSort.col === col) { currentOverviewSort.asc = !currentOverviewSort.asc; }
            else { currentOverviewSort.col = col; currentOverviewSort.asc = false; }
            currentOverviewData.sort((a, b) => {
                let valA = a[col], valB = b[col];
                if (typeof valA === 'string') return currentOverviewSort.asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
                return currentOverviewSort.asc ? valA - valB : valB - valA;
            });
            let html = currentOverviewData.map(r => `<tr class="hover:bg-slate-50"><td class="px-4 py-2 font-medium">${r.team}</td><td class="px-4 py-2 text-center bg-slate-50 border-x border-slate-100">${r.played}</td><td class="px-4 py-2 text-center text-emerald-600 font-semibold">${r.w}</td><td class="px-4 py-2 text-center text-slate-500">${r.d}</td><td class="px-4 py-2 text-center text-rose-600">${r.l}</td><td class="px-4 py-2 text-center">${r.gf}</td><td class="px-4 py-2 text-center">${r.ga}</td><td class="px-4 py-2 text-center font-bold ${r.gd > 0 ? 'text-emerald-600' : r.gd < 0 ? 'text-rose-600' : ''}">${r.gd > 0 ? '+'+r.gd : r.gd}</td></tr>`).join('');
            document.getElementById('h2h-overview-body').innerHTML = html;
        }

        function clearSearch() {
            document.getElementById('search-round').value = ""; document.getElementById('search-hm').value = ""; document.getElementById('search-bm').value = "";
            if (SEASONS.length > 0) document.getElementById('search-season').value = [...SEASONS].reverse()[0];
            updateSearchTeamDropdown(); document.getElementById('search-team').value = ""; performSearch();
        }

        function performSearch() {
            const season = document.getElementById('search-season').value; const roundRaw = document.getElementById('search-round').value.trim().toUpperCase();
            const team = document.getElementById('search-team').value; const searchGoalsTeam = document.getElementById('search-hm').value; const searchGoalsOpp = document.getElementById('search-bm').value;
            let filtered = MATCH_DATA;
            if (season) filtered = filtered.filter(m => String(m.Säs) === String(season));
            if (roundRaw !== "") filtered = filtered.filter(m => String(m.Omgång).trim().toUpperCase() === roundRaw);
            filtered = filtered.filter(m => {
                if (team && m.Hemmalag !== team && m.Bortalag !== team) return false;
                let mHm = parseInt(m.HM); let mBm = parseInt(m.BM);
                if (isNaN(mHm) || isNaN(mBm)) return true; 
                if (team) {
                    let teamGoals = (m.Hemmalag === team) ? mHm : mBm; let oppGoals = (m.Hemmalag === team) ? mBm : mHm;
                    if (searchGoalsTeam !== "" && teamGoals !== parseInt(searchGoalsTeam)) return false;
                    if (searchGoalsOpp !== "" && oppGoals !== parseInt(searchGoalsOpp)) return false;
                } else {
                    if (searchGoalsTeam !== "" && mHm !== parseInt(searchGoalsTeam)) return false;
                    if (searchGoalsOpp !== "" && mBm !== parseInt(searchGoalsOpp)) return false;
                }
                return true;
            });
            filtered.sort((a, b) => b.Match_ID - a.Match_ID);
            let tableHTML = ''; let totalPublik = 0, matcherMedPublik = 0;
            let matchNotes = new Set();

            filtered.forEach(match => {
                let displayDate = formatDate(match.Matchdatum, match.År); 
                if (match.Publik !== "") { totalPublik += match.Publik; matcherMedPublik++; }

                let hm = parseInt(match.HM); let bm = parseInt(match.BM);
                let notText = String(match.NOT).toUpperCase();
                
                let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                
                let origH = match.Hemmalag_Org || match.Hemmalag;
                let origB = match.Bortalag_Org || match.Bortalag;
                let noteStr = getNoteString(origH, origB, match.NOT, displayDate);
                if (noteStr) matchNotes.add(noteStr);

                let homeWon = hm > bm; let awayWon = bm > hm;
                if (isWOH) { homeWon = true; awayWon = false; } else if (isWOB) { awayWon = true; homeWon = false; }

                let homeColor = homeWon ? 'text-blue-600' : (awayWon ? 'text-rose-600' : 'text-slate-700');
                let awayColor = awayWon ? 'text-blue-600' : (homeWon ? 'text-rose-600' : 'text-slate-700');
                let homeBold = ''; let awayBold = '';
                
                if (team) {
                    if (match.Hemmalag === team) homeBold = 'font-bold';
                    if (match.Bortalag === team) awayBold = 'font-bold';
                } else {
                    if (homeWon) homeBold = 'font-bold';
                    if (awayWon) awayBold = 'font-bold';
                }

                let homeClass = `${homeColor} ${homeBold}`;
                let awayClass = `${awayColor} ${awayBold}`;

                tableHTML += `<tr class="hover:bg-slate-50"><td class="px-4 py-2">${getSeasonName(match.Säs)}</td><td class="px-4 py-2 text-slate-500">${match.Omgång || '-'}</td><td class="px-4 py-2 text-slate-500 text-xs">${displayDate}</td><td class="px-4 py-2 text-right ${homeClass}">${origH}</td><td class="px-4 py-2 text-center bg-slate-50 border-x border-slate-100"><span class="font-mono font-bold">${match.HM} - ${match.BM}</span></td><td class="px-4 py-2 ${awayClass}">${origB}</td><td class="px-4 py-2 text-right text-slate-500">${match.Publik !== "" ? match.Publik.toLocaleString('sv-SE') : '-'}</td></tr>`;
            });
            
            document.getElementById('search-table-body').innerHTML = tableHTML || '<tr><td colspan="7" class="text-center py-6 text-slate-500">Inga matcher matchade sökningen.</td></tr>';
            
            let nHtml = "";
            matchNotes.forEach(n => { nHtml += `<div>* ${n}</div>`; });
            const notesEl = document.getElementById('search-notes');
            if (nHtml !== "") { notesEl.innerHTML = nHtml; notesEl.classList.remove('hidden'); } else { notesEl.classList.add('hidden'); }

            let snitt = matcherMedPublik > 0 ? Math.round(totalPublik / matcherMedPublik).toLocaleString('sv-SE') : 0;
            document.getElementById('search-summary-text').innerHTML = `Hittade <span class="font-bold text-blue-600">${filtered.length}</span> matcher. ${matcherMedPublik > 0 ? `Snitt: <span class="font-bold">${snitt}</span>` : ''}`;
            document.getElementById('search-results').classList.remove('hidden');
        }

        function renderRecords() {
            const team = document.getElementById('records-team').value; const suffix = team ? ` (${team})` : '';
            document.getElementById('rec-title-wins').innerText = team ? `Största segrar för ${team}` : 'Största segrarna totalt';
            document.getElementById('rec-title-losses').innerText = team ? `Största förluster för ${team}` : 'Största förlusterna totalt';
            let teamData = team ? MATCH_DATA.filter(m => m.Hemmalag === team || m.Bortalag === team) : MATCH_DATA;
            const buildRows = (matches, valueKeyFn, valueLabel = "") => {
                if (matches.length === 0) return `<tr><td colspan="5" class="py-4 text-center text-slate-500 italic">Inga rekord hittades.</td></tr>`;
                return matches.map(m => {
                    let origH = m.Hemmalag_Org || m.Hemmalag;
                    let origB = m.Bortalag_Org || m.Bortalag;
                    let hClass = (team && m.Hemmalag === team) ? 'font-bold text-slate-900' : 'text-slate-700';
                    let aClass = (team && m.Bortalag === team) ? 'font-bold text-slate-900' : 'text-slate-700';
                    return `<tr class="border-b border-slate-100 hover:bg-slate-50"><td class="py-2 px-2 text-xs text-slate-500 w-12 font-medium">${extractYear(m.Matchdatum, m.År)}</td><td class="py-2 px-2 text-right ${hClass} truncate max-w-[100px]" title="${origH}">${origH}</td><td class="py-2 px-2 text-center bg-slate-50/50 w-16"><span class="font-mono font-bold text-sm block">${m.HM} - ${m.BM}</span></td><td class="py-2 px-2 ${aClass} truncate max-w-[100px]" title="${origB}">${origB}</td><td class="py-2 px-2 text-right font-semibold text-blue-600">${valueKeyFn(m)} ${valueLabel}</td></tr>`;
                }).join('');
            };
            let winsData = team ? teamData.filter(m => (m.Hemmalag === team && parseInt(m.HM) > parseInt(m.BM)) || (m.Bortalag === team && parseInt(m.BM) > parseInt(m.HM))) : MATCH_DATA;
            let biggestWins = [...winsData].sort((a, b) => Math.abs(parseInt(b.HM) - parseInt(b.BM)) - Math.abs(parseInt(a.HM) - parseInt(a.BM)) || Math.max(parseInt(b.HM), parseInt(b.BM)) - Math.max(parseInt(a.HM), parseInt(a.BM))).slice(0, 10);
            document.getElementById('rec-list-wins').innerHTML = buildRows(biggestWins, m => `+${Math.abs(parseInt(m.HM) - parseInt(m.BM))}`, 'mål');
            let lossesData = team ? teamData.filter(m => (m.Hemmalag === team && parseInt(m.HM) < parseInt(m.BM)) || (m.Bortalag === team && parseInt(m.BM) < parseInt(m.HM))) : MATCH_DATA;
            let biggestLosses = [...lossesData].sort((a, b) => Math.abs(parseInt(b.HM) - parseInt(b.BM)) - Math.abs(parseInt(a.HM) - parseInt(a.BM)) || Math.max(parseInt(b.HM), parseInt(b.BM)) - Math.max(parseInt(a.HM), parseInt(a.BM))).slice(0, 10);
            document.getElementById('rec-list-losses').innerHTML = buildRows(biggestLosses, m => `-${Math.abs(parseInt(m.HM) - parseInt(m.BM))}`, 'mål');
            let mostGoals = [...teamData].sort((a, b) => (parseInt(b.HM) + parseInt(b.BM)) - (parseInt(a.HM) + parseInt(a.BM)) || Math.abs(parseInt(b.HM) - parseInt(b.BM)) - Math.abs(parseInt(a.HM) - parseInt(a.BM))).slice(0, 10);
            document.getElementById('rec-list-goals').innerHTML = buildRows(mostGoals, m => (parseInt(m.HM) + parseInt(m.BM)), 'mål');
            
            let validPublik = teamData.filter(m => typeof m.Publik === 'number');
            let highestAtt = [...validPublik].sort((a, b) => b.Publik - a.Publik).slice(0, 10);
            document.getElementById('rec-list-att-high').innerHTML = buildRows(highestAtt, m => m.Publik.toLocaleString('sv-SE'), '');
            let lowestAtt = [...validPublik].filter(m => m.Publik > 10).sort((a, b) => a.Publik - b.Publik).slice(0, 10);
            document.getElementById('rec-list-att-low').innerHTML = buildRows(lowestAtt, m => m.Publik.toLocaleString('sv-SE'), '');
        }

        // --- Sviter Logik ---
        function calculateStreaks() {
            const teamFilter = document.getElementById('streaks-team').value; const context = document.querySelector('input[name="streak-context"]:checked').value;
            const fromStart = document.getElementById('streak-from-start').checked; const sameSeason = document.getElementById('streak-same-season').checked;
            document.getElementById('streaks-placeholder').classList.add('hidden');
            let teamsToProcess = teamFilter === "ALL" ? TEAMS : [teamFilter];
            let absoluteMax = { win: { len: 0, arr: [], team: "" }, unb: { len: 0, arr: [], team: "" }, loss: { len: 0, arr: [], team: "" }, winless: { len: 0, arr: [], team: "" }, draw: { len: 0, arr: [], team: "" }, cs: { len: 0, arr: [], team: "" }, ns: { len: 0, arr: [], team: "" } };
            
            let seasonMax = { w:0, wS:"", wT:"", l:0, lS:"", lT:"", gf:0, gfS:"", gfT:"", ga:0, gaS:"", gaT:"" };
            globalAllStreaks = { win:[], unb:[], loss:[], winless:[], draw:[], cs:[], ns:[] };

            teamsToProcess.forEach(team => {
                let matches = MATCH_DATA.filter(m => m.Hemmalag === team || m.Bortalag === team);
                if (context === 'home') matches = matches.filter(m => m.Hemmalag === team);
                if (context === 'away') matches = matches.filter(m => m.Bortalag === team);
                matches.sort((a, b) => {
                    let d1 = new Date(formatDate(a.Matchdatum, a.År)).getTime();
                    let d2 = new Date(formatDate(b.Matchdatum, b.År)).getTime();
                    if(isNaN(d1)) d1=0; if(isNaN(d2)) d2=0;
                    if(d1!==d2) return d1-d2;
                    return a.Match_ID - b.Match_ID;
                });

                let max = { win:[], unb:[], loss:[], winless:[], draw:[], cs:[], ns:[] };
                let cur = { win:[], unb:[], loss:[], winless:[], draw:[], cs:[], ns:[] };
                let valid = { win:true, unb:true, loss:true, winless:true, draw:true, cs:true, ns:true }; 

                const processMatch = (m) => {
                    const isHome = m.Hemmalag === team;
                    const gf = isHome ? parseInt(m.HM) : parseInt(m.BM); const ga = isHome ? parseInt(m.BM) : parseInt(m.HM);
                    let notText = String(m.NOT).toUpperCase();
                    let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                    let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                    if (isNaN(gf) || isNaN(ga)) { if (!(isWOH || isWOB)) return; }
                    
                    let matchWon = false, matchLost = false, matchDrawn = false;
                    if (isWOH) { if (isHome) matchWon = true; else matchLost = true; }
                    else if (isWOB) { if (!isHome) matchWon = true; else matchLost = true; }
                    else if (gf > ga) matchWon = true;
                    else if (gf < ga) matchLost = true;
                    else matchDrawn = true;

                    const c = { win: matchWon, unb: matchWon || matchDrawn, loss: matchLost, winless: matchLost || matchDrawn, draw: matchDrawn, cs: ga === 0, ns: gf === 0 };
                    Object.keys(c).forEach(k => {
                        if (c[k]) { if (valid[k]) cur[k].push(m); } else {
                            if (cur[k].length > 0) globalAllStreaks[k].push({ team: team, len: cur[k].length, arr: [...cur[k]] });
                            if (cur[k].length > max[k].length) max[k] = [...cur[k]];
                            cur[k] = []; if (fromStart) valid[k] = false; 
                        }
                    });
                };

                let seasonMap = {}; matches.forEach(m => { if (!seasonMap[m.Säs]) seasonMap[m.Säs] = []; seasonMap[m.Säs].push(m); });
                if (sameSeason || fromStart) {
                    Object.values(seasonMap).forEach(sMatches => {
                        cur = { win:[], unb:[], loss:[], winless:[], draw:[], cs:[], ns:[] };
                        if (fromStart) valid = { win:true, unb:true, loss:true, winless:true, draw:true, cs:true, ns:true };
                        
                        let sW=0, sL=0, sGf=0, sGa=0;

                        sMatches.forEach(m => {
                            processMatch(m);
                            const isHome = m.Hemmalag === team;
                            const gf = isHome ? parseInt(m.HM) : parseInt(m.BM); const ga = isHome ? parseInt(m.BM) : parseInt(m.HM);
                            let notText = String(m.NOT).toUpperCase();
                            let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                            let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                            
                            if (isWOH) { if(isHome) sW++; else sL++; }
                            else if (isWOB) { if(!isHome) sW++; else sL++; }
                            else if (!isNaN(gf) && !isNaN(ga)) {
                                sGf += gf; sGa += ga;
                                if (gf > ga) sW++; else if (gf < ga) sL++;
                            }
                        });
                        Object.keys(cur).forEach(k => { 
                            if (cur[k].length > 0) globalAllStreaks[k].push({ team: team, len: cur[k].length, arr: [...cur[k]] });
                            if (cur[k].length > max[k].length) max[k] = [...cur[k]]; 
                        });

                        let sasName = getSeasonName(sMatches[0].Säs);
                        if (sW > seasonMax.w) { seasonMax.w = sW; seasonMax.wS = sasName; seasonMax.wT = team; }
                        if (sL > seasonMax.l) { seasonMax.l = sL; seasonMax.lS = sasName; seasonMax.lT = team; }
                        if (sGf > seasonMax.gf) { seasonMax.gf = sGf; seasonMax.gfS = sasName; seasonMax.gfT = team; }
                        if (sGa > seasonMax.ga) { seasonMax.ga = sGa; seasonMax.gaS = sasName; seasonMax.gaT = team; }
                    });
                } else {
                    matches.forEach(processMatch);
                    Object.keys(cur).forEach(k => { 
                        if (cur[k].length > 0) globalAllStreaks[k].push({ team: team, len: cur[k].length, arr: [...cur[k]] });
                        if (cur[k].length > max[k].length) max[k] = [...cur[k]]; 
                    });
                }

                Object.keys(max).forEach(k => {
                    if (max[k].length > absoluteMax[k].len) absoluteMax[k] = { len: max[k].length, arr: [...max[k]], team: team };
                });
            });

            currentStreakMatches = {}; Object.keys(absoluteMax).forEach(k => { currentStreakMatches[k] = absoluteMax[k].arr; });

            const renderCard = (title, dataObj, key, color) => {
                const teamLabel = teamFilter === "ALL" ? `<div class="text-[11px] font-bold text-slate-800 mt-1 truncate px-2" title="${dataObj.team}">${dataObj.team}</div>` : "";
                return `<div onclick="openStreakModal('${key}', '${title}', '${dataObj.team}')" class="bg-white p-4 rounded-lg border border-slate-200 shadow-sm text-center cursor-pointer hover:shadow-md hover:border-slate-300 transition-all group relative overflow-hidden flex flex-col justify-center"><div class="absolute inset-0 bg-${color.split('-')[1]}-50 opacity-0 group-hover:opacity-100 transition-opacity z-0"></div><div class="relative z-10"><div class="text-xs font-semibold uppercase tracking-wider mb-1 text-slate-500 group-hover:text-slate-800 transition-colors">${title}</div><div class="text-4xl font-black ${color}">${dataObj.len}</div>${teamLabel}<div class="text-[10px] text-slate-400 mt-1 uppercase flex items-center justify-center gap-1 group-hover:text-slate-600 transition-colors">Klicka för lista</div></div></div>`;
            };

            document.getElementById('streaks-results').innerHTML = `
                ${renderCard('Segrar', absoluteMax.win, 'win', 'text-emerald-600')}
                ${renderCard('Obesegrade', absoluteMax.unb, 'unb', 'text-emerald-500')}
                ${renderCard('Förluster', absoluteMax.loss, 'loss', 'text-rose-600')}
                ${renderCard('Utan Seger', absoluteMax.winless, 'winless', 'text-orange-500')}
                ${renderCard('Oavgjorda', absoluteMax.draw, 'draw', 'text-slate-600')}
                ${renderCard('Hållna Nollor', absoluteMax.cs, 'cs', 'text-blue-500')}
                ${renderCard('Måltorka', absoluteMax.ns, 'ns', 'text-slate-400')}
            `;
            document.getElementById('streaks-results').classList.remove('hidden');

            if (sameSeason) {
                const renderSeasonCard = (title, val, sTeam, sSeason, color) => {
                    const tLabel = teamFilter === "ALL" ? `<div class="text-[11px] font-bold text-slate-800 mt-1 truncate px-2">${sTeam}</div>` : "";
                    return `<div class="bg-slate-50 p-4 rounded-lg border border-slate-200 shadow-sm text-center flex flex-col justify-center"><div class="text-xs font-semibold uppercase tracking-wider mb-1 text-slate-500">${title}</div><div class="text-3xl font-black ${color}">${val}</div>${tLabel}<div class="text-[11px] text-slate-500 mt-1">${sSeason}</div></div>`;
                };
                document.getElementById('season-records-results').innerHTML = `
                    ${renderSeasonCard('Flest Segrar', seasonMax.w, seasonMax.wT, seasonMax.wS, 'text-emerald-600')}
                    ${renderSeasonCard('Flest Förluster', seasonMax.l, seasonMax.lT, seasonMax.lS, 'text-rose-600')}
                    ${renderSeasonCard('Flest Gjorda Mål', seasonMax.gf, seasonMax.gfT, seasonMax.gfS, 'text-blue-600')}
                    ${renderSeasonCard('Flest Insläppta Mål', seasonMax.ga, seasonMax.gaT, seasonMax.gaS, 'text-orange-600')}
                `;
                document.getElementById('season-records-section').classList.remove('hidden');
            } else {
                document.getElementById('season-records-section').classList.add('hidden');
            }
            renderStreakToplist();
        }

        function renderStreakToplist() {
            const type = document.getElementById('streak-toplist-type').value;
            if (!type) { document.getElementById('streak-toplist-container').classList.add('hidden'); return; }
            
            let allOfType = globalAllStreaks[type];
            allOfType.sort((a, b) => b.len - a.len); 
            
            let uniqueStreaks = []; let seen = new Set();
            for (let s of allOfType) {
                if (s.len === 0) continue;
                let startM = s.arr[0]; let endM = s.arr[s.arr.length-1];
                let key = `${s.team}_${startM.Match_ID}_${endM.Match_ID}`;
                
                let isSubset = false;
                for (let u of uniqueStreaks) {
                    if (u.team === s.team && u.arr[0].Match_ID <= startM.Match_ID && u.arr[u.arr.length-1].Match_ID >= endM.Match_ID) {
                        isSubset = true; break;
                    }
                }
                
                if (!seen.has(key) && !isSubset) {
                    seen.add(key);
                    let gf = 0, ga = 0;
                    s.arr.forEach(m => {
                        let mHm = parseInt(m.HM)||0; let mBm = parseInt(m.BM)||0;
                        if (m.Hemmalag === s.team) { gf += mHm; ga += mBm; } else { gf += mBm; ga += mHm; }
                    });
                    s.gd = gf - ga; uniqueStreaks.push(s);
                }
                if (uniqueStreaks.length >= 10) break;
            }
            
            let html = uniqueStreaks.map((s, i) => {
                let startD = formatDate(s.arr[0].Matchdatum, s.arr[0].År);
                let endD = formatDate(s.arr[s.arr.length-1].Matchdatum, s.arr[s.arr.length-1].År);
                let gdColor = s.gd > 0 ? 'text-emerald-600' : (s.gd < 0 ? 'text-rose-600' : '');
                let gdSign = s.gd > 0 ? '+' : '';
                return `<tr class="hover:bg-slate-50 cursor-pointer" onclick="openStreakModalFromToplist('${type}', ${i})"><td class="p-3 font-bold text-slate-500">${i+1}</td><td class="p-3 font-medium text-slate-800">${s.team}</td><td class="p-3 text-center font-bold text-blue-600 text-lg">${s.len}</td><td class="p-3 text-xs text-slate-500">${startD} <span class="text-[10px] bg-slate-200 px-1 rounded ml-1">${getSeasonName(s.arr[0].Säs)}</span></td><td class="p-3 text-xs text-slate-500">${endD} <span class="text-[10px] bg-slate-200 px-1 rounded ml-1">${getSeasonName(s.arr[s.arr.length-1].Säs)}</span></td><td class="p-3 text-center font-bold font-mono ${gdColor}">${gdSign}${s.gd}</td></tr>`;
            }).join('');
            
            window._currentToplistMatches = uniqueStreaks;
            document.getElementById('streak-toplist-body').innerHTML = html || '<tr><td colspan="6" class="p-6 text-center text-slate-500">Inga sviter hittades.</td></tr>';
            document.getElementById('streak-toplist-container').classList.remove('hidden');
        }

        function openStreakModalFromToplist(type, index) {
            const streakObj = window._currentToplistMatches[index];
            const selectEl = document.getElementById('streak-toplist-type');
            const title = selectEl.options[selectEl.selectedIndex].text;
            
            document.getElementById('modal-title').innerText = `${title}: ${streakObj.team} (${streakObj.len} matcher)`;
            let html = '';
            streakObj.arr.forEach(m => {
                let origH = m.Hemmalag_Org || m.Hemmalag;
                let origB = m.Bortalag_Org || m.Bortalag;
                let hClass = m.Hemmalag === streakObj.team ? 'font-bold text-slate-900' : ''; 
                let aClass = m.Bortalag === streakObj.team ? 'font-bold text-slate-900' : '';
                let displayDate = formatDate(m.Matchdatum, m.År);
                html += `<tr class="border-b hover:bg-slate-50 transition-colors"><td class="p-3 text-slate-600">${getSeasonName(m.Säs)}</td><td class="p-3 text-slate-500 text-xs">${m.Omgång || '-'}</td><td class="p-3 text-slate-500 text-xs">${displayDate}</td><td class="p-3 text-right ${hClass}">${origH}</td><td class="p-3 text-center font-mono font-bold bg-slate-50 border-x border-slate-100">${m.HM} - ${m.BM}</td><td class="p-3 ${aClass}">${origB}</td></tr>`;
            });
            document.getElementById('modal-tbody').innerHTML = html;
            document.getElementById('streak-modal').classList.remove('hidden');
        }

        function openStreakModal(type, title, holderTeam) {
            const matches = currentStreakMatches[type];
            document.getElementById('modal-title').innerText = `${title}: ${holderTeam} (${matches.length} matcher i rad)`;
            let html = '';
            matches.forEach(m => {
                let origH = m.Hemmalag_Org || m.Hemmalag;
                let origB = m.Bortalag_Org || m.Bortalag;
                let hClass = m.Hemmalag === holderTeam ? 'font-bold text-slate-900' : ''; let aClass = m.Bortalag === holderTeam ? 'font-bold text-slate-900' : '';
                let displayDate = formatDate(m.Matchdatum, m.År);
                html += `<tr class="border-b hover:bg-slate-50 transition-colors"><td class="p-3 text-slate-600">${getSeasonName(m.Säs)}</td><td class="p-3 text-slate-500 text-xs">${m.Omgång || '-'}</td><td class="p-3 text-slate-500 text-xs">${displayDate}</td><td class="p-3 text-right ${hClass}">${origH}</td><td class="p-3 text-center font-mono font-bold bg-slate-50 border-x border-slate-100">${m.HM} - ${m.BM}</td><td class="p-3 ${aClass}">${origB}</td></tr>`;
            });
            document.getElementById('modal-tbody').innerHTML = html || '<tr><td colspan="6" class="p-6 text-center text-slate-500">Inga matcher att visa.</td></tr>';
            document.getElementById('streak-modal').classList.remove('hidden');
        }
        function closeStreakModal() { document.getElementById('streak-modal').classList.add('hidden'); }

        // --- Tabeller Logik ---
        function getMeritBadges(team, sas) {
            if (!TEAM_MERITS[sas] || !TEAM_MERITS[sas][team]) return '';
            const info = TEAM_MERITS[sas][team]; let badges = '';
            if (info.merit === 'Till Allsvenskan') badges += '<span title="Uppflyttad till Allsvenskan" class="cursor-help ml-1 text-emerald-600" style="font-size: 0.9em;">⬆️</span>';
            if (info.merit === 'Till Allsvenskan kval') badges += '<span title="Kval till Allsvenskan" class="cursor-help ml-1 text-emerald-500" style="font-size: 0.9em;">↗️</span>';
            if (info.nya === 'Från Allsvenskan') badges += '<span title="Nedflyttad från Allsvenskan" class="cursor-help ml-1 text-purple-600 font-bold text-[10px] bg-purple-100 rounded px-1">⬇️A</span>';
            if (info.nya === 'Nykomling') badges += '<span title="Nykomling från Div 1" class="cursor-help ml-1 text-blue-600 font-bold text-[10px] bg-blue-100 rounded px-1">NY</span>';
            if (info.merit === 'Degraderade' || info.merit === 'Degraderade kval') badges += '<span title="Degraderad" class="cursor-help ml-1 text-rose-600 font-bold text-[10px] bg-rose-100 rounded px-1">↓</span>';
            return badges;
        }

        function calculateLeagueTable() {
            const season = document.getElementById('table-season').value; 
            const maxRoundRaw = document.getElementById('table-round').value.trim().toUpperCase();
            const phase = document.getElementById('table-phase').value;
            const pointsForWin = parseInt(document.getElementById('table-points').value);
            const perspective = document.getElementById('table-perspective').value;
            const pCtx = perspective; 
            
            if(!season) { alert("Välj en säsong."); return; }
            document.getElementById('table-title').innerText = `Tabell: ${getSeasonName(season)} ${maxRoundRaw ? '(Efter omgång ' + maxRoundRaw + ')' : ''}`;
            document.getElementById('table-legend').classList.remove('hidden'); 
            
            let matches = MATCH_DATA.filter(m => String(m.Säs) === String(season));

            matches = matches.filter(m => {
                if (maxRoundRaw === "ALL" || maxRoundRaw === "") return true;
                let rRaw = String(m.Omgång).trim().toUpperCase();
                if (rRaw === "") {
                    let maxR = parseInt(maxRoundRaw);
                    if (!isNaN(maxR) && maxR >= 30) return true;
                    return false;
                }
                return parseInt(rRaw) <= parseInt(maxRoundRaw);
            });
            
            let table = {};
            let seasonTeamNames = {};
            let notesSet = new Set();
            let totalGoals = 0; let totalMatchesPlayed = 0;
            let totalAttendance = 0; let matchesWithAttendance = 0;

            matches.forEach(m => {
                seasonTeamNames[m.Hemmalag] = m.Hemmalag_Org || m.Hemmalag;
                seasonTeamNames[m.Bortalag] = m.Bortalag_Org || m.Bortalag;
                [m.Hemmalag, m.Bortalag].forEach(t => { if(!table[t]) table[t] = { team: t, pld:0, w:0, d:0, l:0, gf:0, ga:0, gd:0, pts:0 }; });
                
                let hm = parseInt(m.HM); let bm = parseInt(m.BM);

                let notText = String(m.NOT).toUpperCase();
                let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                let isAvbrutenO = notText.includes("AVBRUTEN; O");

                let noteStr = getNoteString(m.Hemmalag_Org || m.Hemmalag, m.Bortalag_Org || m.Bortalag, m.NOT, null);
                if (noteStr) notesSet.add(noteStr);

                if (isNaN(hm) || isNaN(bm)) {
                    if (!(isWOH || isWOB)) return;
                    hm = 0; bm = 0; 
                }

                let hPts = 0, bPts = 0, hW = 0, hD = 0, hL = 0, bW = 0, bD = 0, bL = 0;

                if (isWOH || isWOB || isAvbrutenO) {
                    if (isWOH) { hPts = pointsForWin; hW = 1; bL = 1; }
                    else if (isWOB) { bPts = pointsForWin; bW = 1; hL = 1; }
                    else if (isAvbrutenO) { hPts = 1; bPts = 1; hD = 1; bD = 1; }
                } else {
                    if (hm > bm) { hPts = pointsForWin; hW = 1; bL = 1; }
                    else if (hm < bm) { bPts = pointsForWin; bW = 1; hL = 1; }
                    else { hPts = 1; bPts = 1; hD = 1; bD = 1; }
                }

                if (perspective === 'ALL' || perspective === 'HOME') {
                    table[m.Hemmalag].pld++; table[m.Hemmalag].gf += hm; table[m.Hemmalag].ga += bm;
                    table[m.Hemmalag].w += hW; table[m.Hemmalag].d += hD; table[m.Hemmalag].l += hL; table[m.Hemmalag].pts += hPts;
                }
                if (perspective === 'ALL' || perspective === 'AWAY') {
                    table[m.Bortalag].pld++; table[m.Bortalag].gf += bm; table[m.Bortalag].ga += hm;
                    table[m.Bortalag].w += bW; table[m.Bortalag].d += bD; table[m.Bortalag].l += bL; table[m.Bortalag].pts += bPts;
                }

                totalGoals += (hm + bm);
                totalMatchesPlayed++;
                let pub = parseInt(m.Publik);
                if (!isNaN(pub) && pub > 0) { totalAttendance += pub; matchesWithAttendance++; }
            });

            if (pCtx === 'ALL') {
                Object.values(table).forEach(t => {
                    let mInfo = TEAM_MERITS[season] && TEAM_MERITS[season][t.team];
                    if (mInfo && mInfo.start_pts !== 0) {
                        let adj = mInfo.start_pts;
                        t.pts += adj;
                    }
                });
            }

            document.getElementById('league-table-head').innerHTML = `
                <tr><th class="px-4 py-3 w-10">Plac</th><th class="px-4 py-3">Lag</th><th class="px-4 py-3 text-center">Sp</th><th class="px-4 py-3 text-center">V</th><th class="px-4 py-3 text-center">O</th><th class="px-4 py-3 text-center">F</th><th class="px-4 py-3 text-center">GM-IM</th><th class="px-4 py-3 text-center">+/-</th><th class="px-4 py-3 text-center font-bold">P</th></tr>
            `;

            let tableArr = Object.values(table).filter(r => r.pld > 0);
            tableArr.forEach(r => r.gd = r.gf - r.ga);
            tableArr.sort((a, b) => {
                if (b.pts !== a.pts) return b.pts - a.pts;
                if (b.gd !== a.gd) return b.gd - a.gd;
                return b.gf - a.gf;
            });

            let html = tableArr.map((r, i) => {
                let origTeamName = seasonTeamNames[r.team] || r.team;
                let badges = getMeritBadges(r.team, season);
                let gdCell = r.gd > 0 ? '+'+r.gd : r.gd;
                let gdColor = r.gd > 0 ? 'text-emerald-600' : r.gd < 0 ? 'text-rose-600' : '';
                
                return `<tr class="hover:bg-slate-50"><td class="px-4 py-2 font-bold text-slate-500">${i+1}</td><td class="px-4 py-2 font-medium"><div class="flex items-center">${origTeamName}${badges}</div></td><td class="px-4 py-2 text-center bg-slate-50">${r.pld}</td><td class="px-4 py-2 text-center text-emerald-600">${r.w}</td><td class="px-4 py-2 text-center text-slate-500">${r.d}</td><td class="px-4 py-2 text-center text-rose-600">${r.l}</td><td class="px-4 py-2 text-center">${r.gf} - ${r.ga}</td><td class="px-4 py-2 text-center font-bold ${gdColor}">${gdCell}</td><td class="px-4 py-2 text-center font-black bg-blue-50/50">${r.pts}</td></tr>`;
            }).join('');

            document.getElementById('league-table-body').innerHTML = html || '<tr><td colspan="9" class="text-center py-6 text-slate-500">Inga matcher hittades.</td></tr>';
            
            let notesHTML = "";
            notesSet.forEach(n => { notesHTML += `<div class='flex gap-1 items-center'><span>*</span><span>${n}</span></div>`; });

            document.getElementById('table-notes').innerHTML = notesHTML;
            if(notesHTML === "") document.getElementById('table-notes').classList.add('hidden');
            else document.getElementById('table-notes').classList.remove('hidden');
            
            // Uppdatera målstatistik och Publiksnitt
            let goalAvg = totalMatchesPlayed > 0 ? (totalGoals / totalMatchesPlayed).toFixed(2) : "0.00";
            let pubAvg = matchesWithAttendance > 0 ? Math.round(totalAttendance / matchesWithAttendance).toLocaleString('sv-SE') : "0";
            document.getElementById('table-goal-stats').innerText = `${totalGoals} Mål (${goalAvg} per match) | Publiksnitt: ${pubAvg}`;
            document.getElementById('table-goal-stats').classList.remove('hidden');

            document.getElementById('table-results').classList.remove('hidden');

            // --- TREND DATA ---
            if (pCtx === 'ALL') {
                globalSeasonRanks = {}; globalSeasonTeams = Object.keys(table); 
                let sMaxRound = 0; let mRoundsActive = false;
                matches.forEach(m => { 
                    sMaxRound = Math.max(sMaxRound, parseInt(m.Omgång)||0); 
                });
                
                for(let r = 1; r <= sMaxRound; r++) {
                    let rTable = {}; globalSeasonTeams.forEach(t => { rTable[t] = { team: t, pts:0, gd:0, gf:0 }; });
                    matches.filter(m => parseInt(m.Omgång) <= r).forEach(m => {
                        let hm = parseInt(m.HM)||0; let bm = parseInt(m.BM)||0;
                        let nTxt = String(m.NOT).toUpperCase();
                        let isWOH = nTxt.includes("W.O; H") || nTxt.includes("AVBRUTEN; V") || nTxt.includes("EJ KVALIFICERAD SPELARE; V");
                        let isWOB = nTxt.includes("W.O; B") || nTxt.includes("AVBRUTEN; F") || nTxt.includes("EJ KVALIFICERAD SPELARE; F");
                        let isAvbrutenO = nTxt.includes("AVBRUTEN; O");
                        if (isNaN(hm) || isNaN(bm)) { hm = 0; bm = 0; }
                        rTable[m.Hemmalag].gf += hm; rTable[m.Bortalag].gf += bm; rTable[m.Hemmalag].gd += (hm - bm); rTable[m.Bortalag].gd += (bm - hm);
                        if (isWOH) { rTable[m.Hemmalag].pts += pointsForWin; }
                        else if (isWOB) { rTable[m.Bortalag].pts += pointsForWin; }
                        else if (isAvbrutenO) { rTable[m.Hemmalag].pts += 1; rTable[m.Bortalag].pts += 1; }
                        else if (hm > bm) rTable[m.Hemmalag].pts += pointsForWin; 
                        else if (hm < bm) rTable[m.Bortalag].pts += pointsForWin;
                        else { rTable[m.Hemmalag].pts += 1; rTable[m.Bortalag].pts += 1; }
                    });
                    
                    Object.values(rTable).forEach(t => {
                        let mInfo = TEAM_MERITS[season] && TEAM_MERITS[season][t.team];
                        if (mInfo && mInfo.start_pts < 0) {
                            let adj = mInfo.start_pts;
                            t.pts += adj;
                        }
                    });
                    
                    let tArr = Object.values(rTable); 
                    tArr.sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf);
                    globalSeasonRanks[r] = {}; tArr.forEach((row, i) => { globalSeasonRanks[r][row.team] = i + 1; });
                }
                let trendSelect = document.getElementById('trend-team-select');
                let options = '<option value="">-- Välj lag --</option>'; globalSeasonTeams.sort().forEach(t => { options += `<option value="${t}">${t}</option>`; });
                trendSelect.innerHTML = options; document.getElementById('team-trend-section').classList.remove('hidden');
                if (trendChartInstance) trendChartInstance.destroy();
            } else { document.getElementById('team-trend-section').classList.add('hidden'); }
        }

        function renderTeamTrend() {
            const team = document.getElementById('trend-team-select').value; if(!team) return;
            const season = document.getElementById('table-season').value;
            document.getElementById('trend-title').innerText = `Placeringsutveckling: ${team} (${getSeasonName(season)})`;
            let labels = []; let data = []; let r_keys = Object.keys(globalSeasonRanks).map(Number).sort((a,b)=>a-b);
            let maxR = r_keys.length > 0 ? r_keys[r_keys.length-1] : 0;
            for(let r=1; r<=maxR; r++) { labels.push(`Omg ${r}`); data.push(globalSeasonRanks[r] ? globalSeasonRanks[r][team] || null : null); }
            const ctx = document.getElementById('teamTrendChart').getContext('2d');
            if(trendChartInstance) trendChartInstance.destroy();
            trendChartInstance = new Chart(ctx, { type: 'line', data: { labels: labels, datasets: [{ label: 'Placering', data: data, borderColor: '#ea580c', backgroundColor: '#ea580c', borderWidth: 3, tension: 0.1, pointBackgroundColor: '#9a3412', pointRadius: 4 }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { reverse: true, min: 1, max: globalSeasonTeams.length, ticks: { stepSize: 1 }, title: { display: true, text: 'Tabellplacering' } } } } });
        }

        function renderDynamicAllTimeTable() {
            const epochSelection = document.getElementById('table-epoch').value;
            const pointsForWin = parseInt(document.getElementById('table-points').value) || 3;
            const perspective = document.getElementById('table-perspective').value;
            
            const pCtx = perspective;
            
            document.getElementById('team-trend-section').classList.add('hidden');
            document.getElementById('table-legend').classList.add('hidden');
            document.getElementById('table-notes').classList.add('hidden'); 
            
            let seasonsToInclude = []; let titleSuffix = "Totalt (Alla säsonger)";
            if (epochSelection === "ALL") { seasonsToInclude = SEASONS; } 
            else if (epochSelection.startsWith("EPOCH_CUSTOM_")) { let epochName = epochSelection.replace("EPOCH_CUSTOM_", ""); seasonsToInclude = CUSTOM_EPOCHS[epochName]; titleSuffix = `Egen Epok: ${epochName}`; } 
            else if (epochSelection.startsWith("EPOCH_DECADE_")) { let epochName = epochSelection.replace("EPOCH_DECADE_", ""); seasonsToInclude = DECADES[epochName]; titleSuffix = `Årtionde: ${epochName}`; }

            const seasonSet = new Set(seasonsToInclude.map(String));
            let matches = MATCH_DATA.filter(m => seasonSet.has(String(m.Säs)));

            if (matches.length === 0) { alert("Inga matcher hittades för denna period/epok."); return; }

            let persText = "";
            if (pCtx === 'HOME') persText = " (Endast Hemmamatcher)"; if (pCtx === 'AWAY') persText = " (Endast Bortamatcher)";

            document.getElementById('table-title').innerText = `Maratontabell - ${titleSuffix}${persText} (${pointsForWin} poäng för seger)`;

            let table = {};
            let totalGoals = 0; let totalMatchesPlayed = 0;
            let totalAttendance = 0; let matchesWithAttendance = 0;

            matches.forEach(m => {
                [m.Hemmalag, m.Bortalag].forEach(t => {
                    if(!table[t]) table[t] = { team: t, pld:0, w:0, d:0, l:0, gf:0, ga:0, gd:0, pts:0, firstS: null, lastS: null, seasons: new Set() };
                });
                
                let hm = parseInt(m.HM); let bm = parseInt(m.BM);

                let notText = String(m.NOT).toUpperCase();
                let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                let isAvbrutenO = notText.includes("AVBRUTEN; O");

                if (isNaN(hm) || isNaN(bm)) {
                    if (!(isWOH || isWOB)) return;
                    hm = 0; bm = 0; 
                }

                let hPts = 0, bPts = 0, hW = 0, hD = 0, hL = 0, bW = 0, bD = 0, bL = 0;
                if (isWOH || isWOB || isAvbrutenO) {
                    if (isWOH) { hPts = pointsForWin; hW = 1; bL = 1; }
                    else if (isWOB) { bPts = pointsForWin; bW = 1; hL = 1; }
                    else if (isAvbrutenO) { hPts = 1; bPts = 1; hD = 1; bD = 1; }
                } else {
                    if (hm > bm) { hPts = pointsForWin; hW = 1; bL = 1; } 
                    else if (hm < bm) { bPts = pointsForWin; bW = 1; hL = 1; } 
                    else { hPts = 1; bPts = 1; hD = 1; bD = 1; }
                }

                if (pCtx === 'ALL' || pCtx === 'HOME') {
                    table[m.Hemmalag].pld++; table[m.Hemmalag].gf += hm; table[m.Hemmalag].ga += bm;
                    table[m.Hemmalag].w += hW; table[m.Hemmalag].d += hD; table[m.Hemmalag].l += hL; table[m.Hemmalag].pts += hPts; table[m.Hemmalag].seasons.add(String(m.Säs));
                }
                if (pCtx === 'ALL' || pCtx === 'AWAY') {
                    table[m.Bortalag].pld++; table[m.Bortalag].gf += bm; table[m.Bortalag].ga += hm;
                    table[m.Bortalag].w += bW; table[m.Bortalag].d += bD; table[m.Bortalag].l += bL; table[m.Bortalag].pts += bPts; table[m.Bortalag].seasons.add(String(m.Säs));
                }

                totalGoals += (hm + bm);
                totalMatchesPlayed++;
                let pub = parseInt(m.Publik);
                if (!isNaN(pub) && pub > 0) { totalAttendance += pub; matchesWithAttendance++; }
            });

            if (pCtx === 'ALL') {
                Object.values(table).forEach(t => {
                    let totalDeduction = 0;
                    t.seasons.forEach(sas => {
                        let mInfo = TEAM_MERITS[sas] && TEAM_MERITS[sas][t.team];
                        if (mInfo && mInfo.start_pts < 0) {
                            let adj = mInfo.start_pts;
                            if (adj === -3 && pointsForWin === 2) adj = -2;
                            totalDeduction += adj;
                        }
                    });
                    t.pts += totalDeduction;
                });
            }

            let arr = Object.values(table).filter(r => r.pld > 0);
            arr.forEach(r => {
                r.gd = r.gf - r.ga;
                let s_arr = Array.from(r.seasons).sort((a,b) => parseFloat(a) - parseFloat(b));
                if (s_arr.length > 0) { r.firstS = getSeasonName(s_arr[0]); r.lastS = getSeasonName(s_arr[s_arr.length-1]); }
            });
            arr.sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf);
            
            document.getElementById('league-table-head').innerHTML = `
                <tr><th class="px-4 py-3 w-10">Plac</th><th class="px-4 py-3">Lag</th><th class="px-4 py-3 text-center bg-slate-50">Första-Sista</th><th class="px-4 py-3 text-center bg-slate-50">Säsonger</th><th class="px-4 py-3 text-center">Sp</th><th class="px-4 py-3 text-center">V</th><th class="px-4 py-3 text-center">O</th><th class="px-4 py-3 text-center">F</th><th class="px-4 py-3 text-center">GM-IM</th><th class="px-4 py-3 text-center">+/-</th><th class="px-4 py-3 text-center font-bold">P</th></tr>
            `;

            let html = arr.map((r, i) => `
                <tr class="hover:bg-slate-50"><td class="px-4 py-2 font-bold text-slate-500">${i+1}</td><td class="px-4 py-2 font-medium">${r.team}</td><td class="px-4 py-2 text-center bg-slate-50 text-xs text-slate-500">${r.firstS} - ${r.lastS}</td><td class="px-4 py-2 text-center bg-slate-50 font-bold">${r.seasons.size}</td><td class="px-4 py-2 text-center">${r.pld}</td><td class="px-4 py-2 text-center text-emerald-600">${r.w}</td><td class="px-4 py-2 text-center text-slate-500">${r.d}</td><td class="px-4 py-2 text-center text-rose-600">${r.l}</td><td class="px-4 py-2 text-center">${r.gf} - ${r.ga}</td><td class="px-4 py-2 text-center font-bold ${r.gd > 0 ? 'text-emerald-600' : r.gd < 0 ? 'text-rose-600' : ''}">${r.gd > 0 ? '+'+r.gd : r.gd}</td><td class="px-4 py-2 text-center font-black bg-blue-50/50">${r.pts}</td></tr>
            `).join('');

            let goalAvg = totalMatchesPlayed > 0 ? (totalGoals / totalMatchesPlayed).toFixed(2) : "0.00";
            let pubAvg = matchesWithAttendance > 0 ? Math.round(totalAttendance / matchesWithAttendance).toLocaleString('sv-SE') : "0";
            document.getElementById('table-goal-stats').innerText = `${totalGoals} Mål (${goalAvg} per match) | Publiksnitt: ${pubAvg}`;
            document.getElementById('table-goal-stats').classList.remove('hidden');

            document.getElementById('league-table-body').innerHTML = html || '<tr><td colspan="11" class="text-center py-6 text-slate-500">Inga matcher hittades.</td></tr>';
            document.getElementById('table-results').classList.remove('hidden');
        }

        // --- SÄSONGENS PROFILER ---
        function renderProfiles() {
            const season = document.getElementById('profiles-season').value;
            if(!season) {
                document.getElementById('profiles-results').classList.add('hidden');
                document.getElementById('profiles-placeholder').classList.remove('hidden');
                return;
            }
            
            document.getElementById('profiles-placeholder').classList.add('hidden');
            document.getElementById('profiles-results').classList.remove('hidden');
            
            let champs = []; let defending = []; let promoted = [];
            if(TEAM_MERITS[season]) {
                Object.keys(TEAM_MERITS[season]).forEach(team => {
                    const info = TEAM_MERITS[season][team];
                    if(info.merit === 'Till Allsvenskan') champs.push(team);
                    if(info.nya === 'Från Allsvenskan') defending.push(team);
                    if(info.nya === 'Nykomling') promoted.push(team);
                });
            }
            
            const seasonMatches = MATCH_DATA.filter(m => String(m.Säs) === String(season));
            
            document.getElementById('profile-champions').innerHTML = buildProfileSection("Uppflyttade till Allsvenskan", champs, seasonMatches, "text-emerald-600", "bg-emerald-50", "border-emerald-200", "⬆️");
            document.getElementById('profile-defending').innerHTML = buildProfileSection("Nedflyttade från Allsvenskan", defending, seasonMatches, "text-purple-600", "bg-purple-50", "border-purple-200", "⬇️A");
            document.getElementById('profile-promoted').innerHTML = buildProfileSection("Nykomlingar (från Div 1)", promoted, seasonMatches, "text-blue-600", "bg-blue-50", "border-blue-200", "NY");
        }

        function buildProfileSection(title, teams, matches, textColor, bgColor, borderColor, icon) {
            if(teams.length === 0) return '';
            let html = `<div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden"><div class="${bgColor} px-4 py-3 border-b ${borderColor} flex items-center gap-2"><span class="text-xl font-bold bg-white px-2 py-0.5 rounded shadow-sm border ${borderColor}">${icon}</span><h3 class="font-bold text-lg ${textColor}">${title}</h3></div><div class="p-4 flex flex-col gap-6">`;
                
            teams.forEach(team => {
                let tMatches = matches.filter(m => m.Hemmalag === team || m.Bortalag === team);
                tMatches.sort((a,b) => {
                    let d1 = new Date(formatDate(a.Matchdatum, a.År)).getTime(); let d2 = new Date(formatDate(b.Matchdatum, b.År)).getTime();
                    if(isNaN(d1)) d1=0; if(isNaN(d2)) d2=0;
                    if(d1!==d2) return d1-d2; return a.Match_ID - b.Match_ID;
                });
                
                let displayTeamName = tMatches.length > 0 ? (tMatches[0].Hemmalag === team ? (tMatches[0].Hemmalag_Org || tMatches[0].Hemmalag) : (tMatches[0].Bortalag_Org || tMatches[0].Bortalag)) : team;
                
                let w=0, d=0, l=0, gf=0, ga=0; let mHtml = '';
                tMatches.forEach(m => {
                    const isHome = m.Hemmalag === team;
                    let hm = parseInt(m.HM); let bm = parseInt(m.BM);
                    if(!isNaN(hm) && !isNaN(bm)) {
                        let tg = isHome ? hm : bm; let og = isHome ? bm : hm;
                        gf+=tg; ga+=og;
                        if(tg>og) w++; else if(tg<og) l++; else d++;
                    }
                    let resClass = "";
                    if (hm === bm) resClass = "bg-slate-100 text-slate-800";
                    else if (isHome && hm>bm || !isHome && bm>hm) resClass = "bg-emerald-100 text-emerald-800";
                    else resClass = "bg-rose-100 text-rose-800";
                    
                    let origH = m.Hemmalag_Org || m.Hemmalag;
                    let origB = m.Bortalag_Org || m.Bortalag;

                    mHtml += `<div class="flex justify-between items-center text-xs p-2 border-b border-slate-50 hover:bg-slate-50"><span class="w-1/4 text-slate-500">${m.Omgång||'-'} | ${formatDate(m.Matchdatum, m.År)}</span><span class="w-1/4 text-right ${isHome?'font-bold':''}">${origH}</span><span class="w-1/6 text-center font-mono font-bold ${resClass} rounded px-1">${m.HM}-${m.BM}</span><span class="w-1/4 ${!isHome?'font-bold':''}">${origB}</span></div>`;
                });
                
                html += `<div><h4 class="font-bold text-slate-800 mb-2">${displayTeamName}</h4><div class="flex gap-4 text-sm mb-3"><div class="bg-slate-50 px-3 py-1 rounded border border-slate-100">Matcher: <b>${tMatches.length}</b></div><div class="bg-slate-50 px-3 py-1 rounded border border-slate-100 text-emerald-600">V: <b>${w}</b></div><div class="bg-slate-50 px-3 py-1 rounded border border-slate-100 text-slate-600">O: <b>${d}</b></div><div class="bg-slate-50 px-3 py-1 rounded border border-slate-100 text-rose-600">F: <b>${l}</b></div><div class="bg-slate-50 px-3 py-1 rounded border border-slate-100">Mål: <b>${gf}-${ga}</b></div></div><div class="border border-slate-200 rounded max-h-64 overflow-y-auto custom-scroll">${mHtml}</div></div>`;
            });
            html += `</div></div>`; return html;
        }

        // --- SÄSONGSSTYRKA ---
        function runStrengthAnalysis() {
            document.getElementById('strength-loading').classList.remove('hidden');
            document.getElementById('strength-results').classList.add('hidden');
            
            setTimeout(() => {
                let strengthData = [];
                
                SEASONS.forEach(season => {
                    let sMatches = MATCH_DATA.filter(m => String(m.Säs) === String(season));
                    if(sMatches.length === 0) return;
                    
                    let table = {};
                    const ptsForWin = (SEASON_INFO[season] && SEASON_INFO[season].pts) ? SEASON_INFO[season].pts : 3;
                    
                    sMatches.forEach(m => {
                        [m.Hemmalag, m.Bortalag].forEach(t => { if(!table[t]) table[t] = { team: t, pts:0, gd:0, gf:0, pld:0 }; });
                        let hm = parseInt(m.HM); let bm = parseInt(m.BM);
                        let nTxt = String(m.NOT).toUpperCase();
                        let isWOH = nTxt.includes("W.O; H") || nTxt.includes("AVBRUTEN; V") || nTxt.includes("EJ KVALIFICERAD SPELARE; V");
                        let isWOB = nTxt.includes("W.O; B") || nTxt.includes("AVBRUTEN; F") || nTxt.includes("EJ KVALIFICERAD SPELARE; F");
                        let isO = nTxt.includes("AVBRUTEN; O");
                        
                        let noteStr = getNoteString(m.Hemmalag_Org || m.Hemmalag, m.Bortalag_Org || m.Bortalag, m.NOT, null);
                        
                        if(isNaN(hm) || isNaN(bm)) {
                            if(!(isWOH||isWOB)) return; hm=0; bm=0;
                        }
                        
                        table[m.Hemmalag].pld++; table[m.Bortalag].pld++;
                        table[m.Hemmalag].gf += hm; table[m.Bortalag].gf += bm;
                        table[m.Hemmalag].gd += (hm - bm); table[m.Bortalag].gd += (bm - hm);
                        
                        if (isWOH) { table[m.Hemmalag].pts += ptsForWin; }
                        else if (isWOB) { table[m.Bortalag].pts += ptsForWin; }
                        else if (isO) { table[m.Hemmalag].pts += 1; table[m.Bortalag].pts += 1; }
                        else if (hm > bm) { table[m.Hemmalag].pts += ptsForWin; }
                        else if (hm < bm) { table[m.Bortalag].pts += ptsForWin; }
                        else { table[m.Hemmalag].pts += 1; table[m.Bortalag].pts += 1; }
                    });
                    
                    Object.values(table).forEach(t => {
                        let mInfo = TEAM_MERITS[season] && TEAM_MERITS[season][t.team];
                        if (mInfo && mInfo.start_pts < 0) {
                            let adj = mInfo.start_pts;
                            t.pts += adj;
                        }
                    });

                    let tArr = Object.values(table).filter(r => r.pld > 0);
                    if(tArr.length === 0) return;
                    tArr.sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf);
                    
                    let nTeams = tArr.length;
                    let sumRank = 0; let sumPPG = 0;
                    
                    tArr.forEach(t => {
                        sumRank += (TEAM_RANKS[t.team] || 999);
                        sumPPG += (TEAM_ALLTIME_PPG[t.team] || 0);
                    });
                    
                    let avgRank = sumRank / nTeams;
                    let avgPPG = sumPPG / nTeams;
                    
                    let top3SumRank = 0;
                    let top3Count = Math.min(3, nTeams);
                    for(let i=0; i<top3Count; i++) {
                        top3SumRank += (TEAM_RANKS[tArr[i].team] || 999);
                    }
                    let avgTop3Rank = top3SumRank / top3Count;
                    
                    strengthData.push({
                        season: season,
                        name: getSeasonName(season),
                        nTeams: nTeams,
                        avgRank: avgRank,
                        avgTop3Rank: avgTop3Rank,
                        avgPPG: avgPPG,
                        index: avgPPG * 50 
                    });
                });
                
                currentStrengthData = strengthData;
                sortStrength('index', true);
                
                document.getElementById('strength-loading').classList.add('hidden');
                document.getElementById('strength-results').classList.remove('hidden');
            }, 100);
        }

        function sortStrength(col, forceDesc = false) {
            if (forceDesc) { currentStrengthSort.col = col; currentStrengthSort.asc = false; }
            else if (currentStrengthSort.col === col) { currentStrengthSort.asc = !currentStrengthSort.asc; }
            else { currentStrengthSort.col = col; currentStrengthSort.asc = false; }
            
            currentStrengthData.sort((a, b) => {
                let valA = a[col], valB = b[col];
                if (typeof valA === 'string') return currentStrengthSort.asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
                return currentStrengthSort.asc ? valA - valB : valB - valA;
            });
            
            let html = currentStrengthData.map(r => `
                <tr class="hover:bg-slate-50">
                    <td class="px-4 py-3 font-medium">${r.name}</td>
                    <td class="px-4 py-3 text-center">${r.nTeams}</td>
                    <td class="px-4 py-3 text-center font-mono ${r.avgRank < 10 ? 'text-emerald-600 font-bold' : 'text-slate-500'}">${r.avgRank.toFixed(1)}</td>
                    <td class="px-4 py-3 text-center font-mono ${r.avgTop3Rank < 5 ? 'text-emerald-600 font-bold' : 'text-slate-500'}">${r.avgTop3Rank.toFixed(1)}</td>
                    <td class="px-4 py-3 text-center font-mono font-bold text-orange-600 text-lg bg-orange-50/50">${r.index.toFixed(1)}</td>
                </tr>
            `).join('');
            
            document.getElementById('strength-table-body').innerHTML = html;
        }

        // --- Analys: TOPPSTRIDEN ---
        function runPromotionRaceAnalysis() {
            document.getElementById('goldrace-loading').classList.remove('hidden');
            document.getElementById('goldrace-results').classList.add('hidden');
            
            setTimeout(() => {
                let allSeasonsData = []; let leaderCounts = [];

                SEASONS.forEach(season => {
                    let sMatches = MATCH_DATA.filter(m => String(m.Säs) === String(season) && m.Omgång !== "");
                    if (sMatches.length === 0) return;

                    let roundSet = new Set();
                    sMatches.forEach(m => roundSet.add(String(m.Omgång).trim().toUpperCase()));
                    let rounds = Array.from(roundSet).sort((a, b) => {
                        let aNum = parseInt(a) || 0; let bNum = parseInt(b) || 0;
                        return aNum - bNum;
                    });

                    if (rounds.length < 2) return;

                    const ptsForWin = (SEASON_INFO[season] && SEASON_INFO[season].pts) ? SEASON_INFO[season].pts : 3;

                    let sTeams = new Set();
                    sMatches.forEach(m => { sTeams.add(m.Hemmalag); sTeams.add(m.Bortalag); });

                    let leadersPerRound = [];
                    
                    for (let i = 0; i < rounds.length; i++) {
                        let currentRound = rounds[i];
                        
                        let rTable = {};
                        sTeams.forEach(t => { rTable[t] = { team: t, pts: 0, gd: 0, gf: 0, ga: 0, pld: 0 }; });
                        
                        let matchesUpTo = sMatches.filter(m => {
                            let mRound = String(m.Omgång).trim().toUpperCase();
                            return rounds.indexOf(mRound) <= i;
                        });

                        matchesUpTo.forEach(m => {
                            let hm = parseInt(m.HM); let bm = parseInt(m.BM);
                            if (isNaN(hm) || isNaN(bm)) { hm = 0; bm = 0; }
                            
                            let nTxt = String(m.NOT).toUpperCase();
                            let isWOH = nTxt.includes("W.O; H") || nTxt.includes("AVBRUTEN; V") || nTxt.includes("EJ KVALIFICERAD SPELARE; V");
                            let isWOB = nTxt.includes("W.O; B") || nTxt.includes("AVBRUTEN; F") || nTxt.includes("EJ KVALIFICERAD SPELARE; F");
                            
                            rTable[m.Hemmalag].gf += hm; rTable[m.Bortalag].gf += bm;
                            rTable[m.Hemmalag].ga += bm; rTable[m.Bortalag].ga += hm;
                            rTable[m.Hemmalag].gd += (hm - bm); rTable[m.Bortalag].gd += (bm - hm);
                            rTable[m.Hemmalag].pld++; rTable[m.Bortalag].pld++;

                            if (isWOH) { rTable[m.Hemmalag].pts += ptsForWin; }
                            else if (isWOB) { rTable[m.Bortalag].pts += ptsForWin; }
                            else if (hm > bm) { rTable[m.Hemmalag].pts += ptsForWin; }
                            else if (hm < bm) { rTable[m.Bortalag].pts += ptsForWin; }
                            else { rTable[m.Hemmalag].pts += 1; rTable[m.Bortalag].pts += 1; }
                        });

                        Object.values(rTable).forEach(t => { 
                            let mInfo = TEAM_MERITS[season] && TEAM_MERITS[season][t.team]; 
                            if (mInfo && mInfo.start_pts < 0) {
                                let adj = mInfo.start_pts;
                                t.pts += adj;
                            }
                        });

                        let tArr = Object.values(rTable).filter(r => r.pld > 0);
                        tArr.sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf);

                        // För Superettan kollar vi TOP 2
                        if (tArr.length >= 2) {
                            leadersPerRound.push({ round: currentRound, top1: tArr[0].team, top2: tArr[1].team });
                        }
                    }

                    if(leadersPerRound.length < 2) return;

                    let finalTop2 = [leadersPerRound[leadersPerRound.length - 1].top1, leadersPerRound[leadersPerRound.length - 1].top2];
                    let preFinalTop2 = [leadersPerRound[leadersPerRound.length - 2].top1, leadersPerRound[leadersPerRound.length - 2].top2];

                    // Vilka var i Top 2 innan sista, men missade till slut?
                    preFinalTop2.forEach(team => {
                        if (!finalTop2.includes(team)) {
                            // De missade! Vilka tog deras plats? De i finalTop2 som inte var i preFinalTop2
                            let newlyPromoted = finalTop2.filter(t => !preFinalTop2.includes(t));
                            allSeasonsData.push({ type: 'LATE_DROP', seasonName: getSeasonName(season), dropped: team, passedBy: newlyPromoted.join(', ') });
                        }
                    });

                    let tCounts = {}; 
                    leadersPerRound.forEach(r => { 
                        tCounts[r.top1] = (tCounts[r.top1] || 0) + 1; 
                        tCounts[r.top2] = (tCounts[r.top2] || 0) + 1; 
                    });

                    Object.keys(tCounts).forEach(t => { 
                        leaderCounts.push({ team: t, seasonName: getSeasonName(season), ledRounds: tCounts[t], promoted: finalTop2.includes(t) }); 
                    });
                });

                let lateWinnersHTML = allSeasonsData.filter(d => d.type === 'LATE_DROP').map(d => `<tr class="hover:bg-slate-50"><td class="p-3 font-medium">${d.seasonName}</td><td class="p-3 font-bold text-rose-600">${d.dropped}</td><td class="p-3 text-emerald-600 font-bold">${d.passedBy}</td></tr>`).join('');
                document.getElementById('gr-late-winners').innerHTML = lateWinnersHTML || '<tr><td colspan="3" class="p-3 text-center text-slate-500">Inget lag tappade sin uppflyttningsplats i sista omgången.</td></tr>';

                let mostLeadHTML = [...leaderCounts].sort((a,b) => b.ledRounds - a.ledRounds).slice(0,10).map((d,i) => `<tr class="hover:bg-slate-50"><td class="p-3 text-slate-400 font-bold">${i+1}</td><td class="p-3 font-medium ${d.promoted?'text-emerald-600':'text-slate-800'}">${d.team} ${d.promoted?'⬆️':''}</td><td class="p-3 text-slate-500 text-xs">${d.seasonName}</td><td class="p-3 text-center font-bold text-lg text-blue-600">${d.ledRounds}</td></tr>`).join('');
                document.getElementById('gr-most-lead').innerHTML = mostLeadHTML;

                let mostLeadNoWinHTML = [...leaderCounts].filter(d => !d.promoted).sort((a,b) => b.ledRounds - a.ledRounds).slice(0,10).map((d,i) => `<tr class="hover:bg-slate-50"><td class="p-3 text-slate-400 font-bold">${i+1}</td><td class="p-3 font-medium text-rose-600">${d.team}</td><td class="p-3 text-slate-500 text-xs">${d.seasonName}</td><td class="p-3 text-center font-bold text-lg text-rose-600">${d.ledRounds}</td></tr>`).join('');
                document.getElementById('gr-most-lead-nowin').innerHTML = mostLeadNoWinHTML;

                document.getElementById('goldrace-loading').classList.add('hidden'); document.getElementById('goldrace-results').classList.remove('hidden');
            }, 100);
        }

        // --- Analys: Förutsägbarhet ---
        function toggleAnalysisMode(mode) {
            analysisMode = mode;
            document.getElementById('btn-mode-chart').className = mode === 'chart' ? "font-bold text-orange-600 border-b-2 border-orange-600 px-2 pb-1 transition-colors" : "font-medium text-slate-500 hover:text-orange-600 px-2 pb-1 transition-colors";
            document.getElementById('btn-mode-table').className = mode === 'table' ? "font-bold text-orange-600 border-b-2 border-orange-600 px-2 pb-1 transition-colors" : "font-medium text-slate-500 hover:text-orange-600 px-2 pb-1 transition-colors";
            if (mode === 'table') { document.getElementById('div-analysis-round').classList.remove('hidden'); document.getElementById('analysis-chart-container').classList.add('hidden'); document.getElementById('analysis-details').classList.add('hidden'); document.getElementById('analysis-comparison-table').classList.remove('hidden'); } 
            else { document.getElementById('div-analysis-round').classList.add('hidden'); document.getElementById('analysis-chart-container').classList.remove('hidden'); document.getElementById('analysis-comparison-table').classList.add('hidden'); }
        }

        function calculateSpearman(ranks1, ranks2, teams) {
            let n = teams.length; if (n <= 1) return 0;
            let sumDSq = 0; teams.forEach(t => { let d = (ranks1[t] || 0) - (ranks2[t] || 0); sumDSq += (d * d); });
            return 1 - ((6 * sumDSq) / (n * (n * n - 1)));
        }

        function calculateSubsetSpearman(currentRanks, finalRanks, teamsSubset) {
            let n = teamsSubset.length; if (n <= 1) return 0;
            let cRanks = {}; let sortedC = [...teamsSubset].sort((a, b) => currentRanks[a] - currentRanks[b]);
            sortedC.forEach((t, i) => { cRanks[t] = i + 1; });
            let fRanks = {}; let sortedF = [...teamsSubset].sort((a, b) => finalRanks[a] - finalRanks[b]);
            sortedF.forEach((t, i) => { fRanks[t] = i + 1; });
            
            let sumDSq = 0;
            teamsSubset.forEach(t => { let d = cRanks[t] - fRanks[t]; sumDSq += (d * d); });
            return 1 - ((6 * sumDSq) / (n * (n * n - 1)));
        }

        function runPredictabilityAnalysis() {
            const selection = document.getElementById('analysis-season').value; const focus = document.getElementById('analysis-focus').value;
            if(!selection) { alert("Välj en säsong eller epok att analysera."); return; }
            document.getElementById('analysis-details').classList.add('hidden'); 
            let seasonsToAnalyze = [];

            if (selection === "ALL_SEASONS") { seasonsToAnalyze = [...SEASONS].reverse(); document.getElementById('analysis-warning').classList.add('hidden'); } 
            else if (selection.startsWith("EPOCH_CUSTOM_")) { let epoch = selection.replace("EPOCH_CUSTOM_", ""); seasonsToAnalyze = CUSTOM_EPOCHS[epoch]; if (analysisMode === 'chart') { document.getElementById('analysis-warning').innerText = `Analyserar egen epok: ${epoch}. Detta är ett genomsnitt av ${seasonsToAnalyze.length} säsonger.`; document.getElementById('analysis-warning').classList.remove('hidden', 'text-orange-800', 'bg-orange-50'); document.getElementById('analysis-warning').classList.add('text-blue-800', 'bg-blue-50'); } else { document.getElementById('analysis-warning').classList.add('hidden'); } } 
            else if (selection.startsWith("EPOCH_DECADE_")) { let epoch = selection.replace("EPOCH_DECADE_", ""); seasonsToAnalyze = DECADES[epoch]; if (analysisMode === 'chart') { document.getElementById('analysis-warning').innerText = `Analyserar årtionde: ${epoch}. Detta är ett genomsnitt av ${seasonsToAnalyze.length} säsonger.`; document.getElementById('analysis-warning').classList.remove('hidden', 'text-orange-800', 'bg-orange-50'); document.getElementById('analysis-warning').classList.add('text-blue-800', 'bg-blue-50'); } else { document.getElementById('analysis-warning').classList.add('hidden'); } } 
            else { seasonsToAnalyze = [selection]; document.getElementById('analysis-warning').classList.add('hidden'); }

            if (analysisMode === 'table') {
                document.getElementById('analysis-chart-container').classList.add('hidden'); document.getElementById('analysis-details').classList.add('hidden'); document.getElementById('analysis-comparison-table').classList.remove('hidden');
                const targetRound = parseInt(document.getElementById('analysis-round').value) || 10; let tableData = [];

                seasonsToAnalyze.forEach(season => {
                    let sMatches = MATCH_DATA.filter(m => String(m.Säs) === String(season) && m.Omgång !== "" && !isNaN(parseInt(m.Omgång)));
                    if (sMatches.length === 0) return;
                    let maxRound = 0; sMatches.forEach(m => { maxRound = Math.max(maxRound, parseInt(m.Omgång)); });
                    if (maxRound < targetRound) return; 
                    const ptsForWin = (SEASON_INFO[season] && SEASON_INFO[season].pts) ? SEASON_INFO[season].pts : 3;

                    const getTableAtRound = (rnd) => {
                        let table = {}; sMatches.forEach(m => { [m.Hemmalag, m.Bortalag].forEach(t => { if(!table[t]) table[t] = { team: t, pts:0, gd:0, gf:0 }; }); });
                        sMatches.filter(m => parseInt(m.Omgång) <= rnd).forEach(m => {
                            let hm = parseInt(m.HM)||0; let bm = parseInt(m.BM)||0;
                            let nTxt = String(m.NOT).toUpperCase();
                            let isWOH = nTxt.includes("W.O; H") || nTxt.includes("AVBRUTEN; V") || nTxt.includes("EJ KVALIFICERAD SPELARE; V");
                            let isWOB = nTxt.includes("W.O; B") || nTxt.includes("AVBRUTEN; F") || nTxt.includes("EJ KVALIFICERAD SPELARE; F");
                            
                            if (isNaN(hm) || isNaN(bm)) { hm=0; bm=0; }
                            table[m.Hemmalag].gf += hm; table[m.Bortalag].gf += bm; table[m.Hemmalag].gd += (hm - bm); table[m.Bortalag].gd += (bm - hm);
                            if (isWOH) { table[m.Hemmalag].pts += ptsForWin; } else if (isWOB) { table[m.Bortalag].pts += ptsForWin; }
                            else if (hm > bm) { table[m.Hemmalag].pts += ptsForWin; } else if (hm < bm) { table[m.Bortalag].pts += ptsForWin; }
                            else { table[m.Hemmalag].pts += 1; table[m.Bortalag].pts += 1; }
                        });
                        
                        Object.values(table).forEach(t => {
                            let mInfo = TEAM_MERITS[season] && TEAM_MERITS[season][t.team];
                            if (mInfo && mInfo.start_pts < 0) {
                                let adj = mInfo.start_pts;
                                t.pts += adj;
                            }
                        });
                        
                        let arr = Object.values(table); arr.sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf);
                        let rankMap = {}; arr.forEach((r, i) => { rankMap[r.team] = i + 1; }); return { ranks: rankMap, sortedArray: arr };
                    };

                    const finalTable = getTableAtRound(maxRound); const targetTable = getTableAtRound(targetRound);
                    let teamsToAnalyze = Object.keys(finalTable.ranks);
                    if (focus === 'top') teamsToAnalyze = finalTable.sortedArray.slice(0, 3).map(r => r.team);
                    else if (focus === 'bottom') teamsToAnalyze = finalTable.sortedArray.slice(-3).map(r => r.team);

                    let totalError = 0; teamsToAnalyze.forEach(t => { totalError += Math.abs(targetTable.ranks[t] - finalTable.ranks[t]); });
                    let mae = totalError / teamsToAnalyze.length; 
                    
                    let spearman = focus === 'all' ? calculateSpearman(targetTable.ranks, finalTable.ranks, teamsToAnalyze) : calculateSubsetSpearman(targetTable.ranks, finalTable.ranks, teamsToAnalyze);
                    
                    tableData.push({ season: season, name: getSeasonName(season), mae: mae, spearman: spearman });
                });

                if (tableData.length === 0) {
                    document.getElementById('analysis-warning').innerText = `Kunde inte hitta data för omgång ${targetRound} i de valda säsongerna.`; document.getElementById('analysis-warning').classList.remove('hidden', 'text-orange-800', 'bg-orange-50'); document.getElementById('analysis-warning').classList.add('text-amber-800', 'bg-amber-50'); document.getElementById('analysis-comparison-table').classList.add('hidden');
                } else {
                    document.getElementById('comparison-title').innerText = `Jämförelse vid omgång ${targetRound}`;
                    
                    let avgMae = (tableData.reduce((sum, d) => sum + d.mae, 0) / tableData.length).toFixed(2);
                    let avgSpearman = (tableData.reduce((sum, d) => sum + d.spearman, 0) / tableData.length).toFixed(3);
                    let summaryRow = `<tr class="bg-orange-50 border-b-2 border-orange-200"><td class="p-3 font-bold text-orange-800">Snitt (Vald period)</td><td class="p-3 text-center font-bold text-orange-800 font-mono">${avgMae}</td><td class="p-3 text-center font-bold text-orange-800 font-mono">${avgSpearman}</td></tr>`;
                    
                    let html = summaryRow + tableData.map(d => `<tr class="hover:bg-slate-50 border-b border-slate-100"><td class="p-3 font-medium">${d.name}</td><td class="p-3 text-center font-mono ${d.mae < 1.0 ? 'text-emerald-600 font-bold' : ''}">${d.mae.toFixed(2)}</td><td class="p-3 text-center font-mono ${d.spearman > 0.8 ? 'text-emerald-600 font-bold' : ''}">${d.spearman.toFixed(3)}</td></tr>`).join('');
                    document.getElementById('comparison-body').innerHTML = html;
                }
                document.getElementById('analysis-results').classList.remove('hidden'); return; 
            }

            // --- CHART MODE ---
            document.getElementById('analysis-comparison-table').classList.add('hidden'); document.getElementById('analysis-chart-container').classList.remove('hidden');
            let allErrors = []; globalAnalysisData = {}; 

            seasonsToAnalyze.forEach(season => {
                let sMatches = MATCH_DATA.filter(m => String(m.Säs) === String(season) && m.Omgång !== "" && !isNaN(parseInt(m.Omgång)));
                if (sMatches.length === 0) return; 
                const ptsForWin = (SEASON_INFO[season] && SEASON_INFO[season].pts) ? SEASON_INFO[season].pts : 3;
                let maxRound = 0; sMatches.forEach(m => { maxRound = Math.max(maxRound, parseInt(m.Omgång)); });

                const getTableAtRound = (rnd) => {
                    let table = {}; sMatches.forEach(m => { [m.Hemmalag, m.Bortalag].forEach(t => { if(!table[t]) table[t] = { team: t, pts:0, gd:0, gf:0 }; }); });
                    sMatches.filter(m => parseInt(m.Omgång) <= rnd).forEach(m => {
                        let hm = parseInt(m.HM)||0; let bm = parseInt(m.BM)||0;
                        let nTxt = String(m.NOT).toUpperCase();
                        let isWOH = nTxt.includes("W.O; H") || nTxt.includes("AVBRUTEN; V") || nTxt.includes("EJ KVALIFICERAD SPELARE; V");
                        let isWOB = nTxt.includes("W.O; B") || nTxt.includes("AVBRUTEN; F") || nTxt.includes("EJ KVALIFICERAD SPELARE; F");
                        
                        if (isNaN(hm) || isNaN(bm)) { hm=0; bm=0; }
                        table[m.Hemmalag].gf += hm; table[m.Bortalag].gf += bm; table[m.Hemmalag].gd += (hm - bm); table[m.Bortalag].gd += (bm - hm);
                        if (isWOH) { table[m.Hemmalag].pts += ptsForWin; }
                        else if (isWOB) { table[m.Bortalag].pts += ptsForWin; }
                        else if (hm > bm) { table[m.Hemmalag].pts += ptsForWin; }
                        else if (hm < bm) { table[m.Bortalag].pts += ptsForWin; }
                        else { table[m.Hemmalag].pts += 1; table[m.Bortalag].pts += 1; }
                    });
                    
                    Object.values(table).forEach(t => {
                        let mInfo = TEAM_MERITS[season] && TEAM_MERITS[season][t.team];
                        if (mInfo && mInfo.start_pts < 0) {
                            let adj = mInfo.start_pts;
                            t.pts += adj;
                        }
                    });
                    
                    let arr = Object.values(table); arr.sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf);
                    let rankMap = {}; arr.forEach((r, i) => { rankMap[r.team] = i + 1; }); return { ranks: rankMap, sortedArray: arr };
                };

                const finalTable = getTableAtRound(maxRound); const finalRanks = finalTable.ranks;
                let teamsToAnalyze = Object.keys(finalRanks);
                if (focus === 'top') teamsToAnalyze = finalTable.sortedArray.slice(0, 3).map(r => r.team);
                else if (focus === 'bottom') teamsToAnalyze = finalTable.sortedArray.slice(-3).map(r => r.team);

                let seasonErrors = []; let seasonDataObj = {};
                for (let r = 1; r <= maxRound; r++) {
                    let currentTable = getTableAtRound(r); let currentRanks = currentTable.ranks;
                    let totalError = 0; teamsToAnalyze.forEach(t => { totalError += Math.abs(currentRanks[t] - finalRanks[t]); });
                    let meanError = totalError / teamsToAnalyze.length; 
                    
                    let spearman = focus === 'all' ? calculateSpearman(currentRanks, finalRanks, teamsToAnalyze) : calculateSubsetSpearman(currentRanks, finalRanks, teamsToAnalyze);
                    
                    seasonErrors.push(meanError);
                    if (seasonsToAnalyze.length === 1) {
                        seasonDataObj[r] = { mae: meanError, spearman: spearman, teams: teamsToAnalyze.map(t => ({ name: t, currentRank: currentRanks[t], finalRank: finalRanks[t], diff: currentRanks[t] - finalRanks[t] })).sort((a,b) => a.currentRank - b.currentRank) };
                    }
                }
                allErrors.push(seasonErrors);
                if (seasonsToAnalyze.length === 1) globalAnalysisData = seasonDataObj;
            });

            if (allErrors.length === 0) {
                document.getElementById('analysis-warning').innerText = "Data saknas! Omgångar är inte ifyllda för valt år, analysen kan inte genomföras."; document.getElementById('analysis-warning').classList.remove('hidden', 'text-orange-800', 'bg-orange-50'); document.getElementById('analysis-warning').classList.add('text-amber-800', 'bg-amber-50'); document.getElementById('analysis-results').classList.remove('hidden'); document.getElementById('analysis-chart-container').classList.add('hidden'); if (analysisChartInstance) analysisChartInstance.destroy(); return;
            }

            let maxLen = Math.max(...allErrors.map(e => e.length)); let averagedErrors = [];
            for(let i=0; i<maxLen; i++) { let sum = 0, count = 0; allErrors.forEach(errArr => { if (errArr[i] !== undefined) { sum += errArr[i]; count++; } }); averagedErrors.push(sum / count); }

            let labels = Array.from({length: maxLen}, (_, i) => `Omg ${i+1}`);
            document.getElementById('analysis-results').classList.remove('hidden'); const ctx = document.getElementById('analysisChart').getContext('2d');
            if (analysisChartInstance) { analysisChartInstance.destroy(); }
            analysisChartInstance = new Chart(ctx, {
                type: 'line', data: { labels: labels, datasets: [{ label: 'Genomsnittligt Positionsfel (MAE)', data: averagedErrors, borderColor: '#ea580c', backgroundColor: 'rgba(234, 88, 12, 0.1)', borderWidth: 3, pointBackgroundColor: '#9a3412', pointHoverRadius: 8, pointHoverBackgroundColor: '#f59e0b', fill: true, tension: 0.3 }] },
                options: { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, plugins: { legend: { display: false }, tooltip: { callbacks: { label: function(c) { return ` MAE: ${c.parsed.y.toFixed(2)}`; } } } }, scales: { y: { beginAtZero: true, title: { display: true, text: 'Positionsfel' } }, x: { grid: { display: false } } },
                    onClick: (e, activeEls) => { if (seasonsToAnalyze.length > 1) { alert("Detaljerad tabell är endast tillgänglig när du granskar en enskild säsong, inte hela epoker/perioder."); return; } if (activeEls.length > 0) { const round = activeEls[0].index + 1; showAnalysisDetails(round); } }
                }
            });
        }

        function showAnalysisDetails(round) {
            const data = globalAnalysisData[round]; if (!data) return;
            document.getElementById('details-title').innerText = `Tabellstatus i omgång ${round}`; document.getElementById('details-mae').innerText = data.mae.toFixed(2); document.getElementById('details-spearman').innerText = data.spearman.toFixed(3);
            let html = data.teams.map(t => {
                let diffStr = '<span class="text-slate-500">-</span>';
                if (t.diff > 0) diffStr = `<span class="text-emerald-400 font-bold">+${t.diff}</span> <span class="text-[10px] text-emerald-200/70 uppercase tracking-widest">(Upp)</span>`;
                else if (t.diff < 0) diffStr = `<span class="text-rose-400 font-bold">${t.diff}</span> <span class="text-[10px] text-rose-200/70 uppercase tracking-widest">(Ner)</span>`;
                return `<tr class="hover:bg-slate-800 transition-colors"><td class="p-3 font-medium text-orange-200">${t.name}</td><td class="p-3 text-center">${t.currentRank}</td><td class="p-3 text-center text-emerald-300 font-semibold">${t.finalRank}</td><td class="p-3 text-center">${diffStr}</td></tr>`;
            }).join('');
            document.getElementById('details-body').innerHTML = html; document.getElementById('analysis-details').classList.remove('hidden'); document.getElementById('analysis-details').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    </script>
</body>
</html>
"""

final_html = html_template.replace("%%MATCH_DATA_JSON%%", json_match_data) \
    .replace("%%TEAMS_JSON%%", json_teams_data) \
    .replace("%%SEASONS_JSON%%", json_seasons_data) \
    .replace("%%SEASON_INFO_JSON%%", json_season_info) \
    .replace("%%DECADES_JSON%%", json_decades_data) \
    .replace("%%CUSTOM_EPOCHS_JSON%%", json_custom_epochs_data) \
    .replace("%%TEAM_MERITS_JSON%%", json_team_merits_data)

output_file = os.path.join(main_folder, "Matchanalys_Superettan_Dashboard.html")
with open(output_file, "w", encoding="utf-8") as f:
    f.write(final_html)

print(f"SUCCÉ! Filen '{output_file}' har skapats.")