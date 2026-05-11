import os
import sys
import pandas as pd
import json
import math

# ==========================================
# DATA OCH KÄLLMATERIAL
# Författare till matchinformation och grunddata: Jimmy Lindahl
# ==========================================

py_logs = []
def dlog(msg):
    py_logs.append(msg)
    print(msg)

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

def fix_text(text):
    if not isinstance(text, str): return text
    for bad, good in encoding_fix.items():
        text = text.replace(bad, good)
    return text

excel_file = os.path.join(excel_folder, "Cupen_Svenska_matcher_samlade.xlsx")

# 1. LÄS IN CUPLAGEN (Namn-mappning)
team_mapping = {}
try:
    df_lagen = pd.read_excel(excel_file, sheet_name="Cuplagen")
    df_lagen.columns = df_lagen.columns.str.strip()
    for _, row in df_lagen.iterrows():
        lagnamn = str(row.get('Lagnamn', '')).strip()
        lagbeteckning = str(row.get('Lagbeteckning', '')).strip()
        if lagnamn and lagbeteckning and lagnamn != 'nan':
            team_mapping[lagnamn] = lagbeteckning
    dlog(f"Laddade {len(team_mapping)} lagnamn-alias från Cuplagen.")
except Exception as e:
    dlog(f"Kunde inte läsa Cuplagen: {e}")

def normalize_team(team_name):
    team = str(team_name).strip()
    return team_mapping.get(team, team)

# 2. LÄS IN SERIEBETECKNING (Nivå-mappning)
serie_rules = []
try:
    df_serie = pd.read_excel(excel_file, sheet_name="Seriebeteckning")
    df_serie.columns = df_serie.columns.str.strip()
    for _, row in df_serie.iterrows():
        kod = str(row.get('Serie_Kod', '')).strip()
        try: start = int(row.get('Första_Säs', 1))
        except: start = 1
        
        end_val = row.get('Sista_Säs', 'Senaste')
        if str(end_val).strip().lower() == 'senaste': end = 9999
        else:
            try: end = int(end_val)
            except: end = 9999
            
        try: niva = int(row.get('Serienivå', 99))
        except: niva = 99
        
        if kod and kod != 'nan':
            serie_rules.append({'kod': kod, 'start': start, 'end': end, 'niva': niva})
    dlog(f"Laddade {len(serie_rules)} seriebeteckningar.")
except Exception as e:
    dlog(f"Kunde inte läsa Seriebeteckning: {e}")

def get_tier(kod, sas_nr):
    k = str(kod).strip()
    if not k or pd.isna(k) or k == 'nan': return 99
    try: s_nr = int(sas_nr)
    except: return 99
    
    for rule in serie_rules:
        if rule['kod'] == k and rule['start'] <= s_nr <= rule['end']:
            return rule['niva']
    return 99

# 3. LÄS IN MATCHERNA
try:
    df = pd.read_excel(excel_file, sheet_name="Cupen")
    df.columns = df.columns.str.strip() 
    dlog(f"Följande kolumner hittades i Cupen-fliken: {list(df.columns)}")
    
    # Robust Omdöpning av kolumner om namn skiljer sig
    def ensure_col(target, keywords):
        if target in df.columns: return
        for kw in keywords:
            match = next((c for c in df.columns if kw.lower() == c.lower()), None)
            if not match:
                match = next((c for c in df.columns if kw.lower() in c.lower()), None)
            if match:
                df.rename(columns={match: target}, inplace=True)
                dlog(f"Omdöpte kolumn '{match}' till '{target}'")
                return
        dlog(f"VARNING: Hittade ingen kolumn som liknar '{target}'.")

    ensure_col('Säsong', ['säsong', 'sasong', 'säs'])
    ensure_col('År', ['år', 'year'])
    ensure_col('Hemmalag', ['hemmalag', 'hemma'])
    ensure_col('Bortalag', ['bortalag', 'borta'])
    ensure_col('Matchdatum', ['matchdatum', 'datum'])
    ensure_col('Fas', ['fas', 'omgång', 'omgang', 'round'])
    ensure_col('Avancerade', ['avancerade', 'vidare'])
    ensure_col('Publik', ['publik', 'åskådare'])
    ensure_col('NOT', ['not', 'notering', 'anteckning'])
    ensure_col('HM', ['hm', 'mål h'])
    ensure_col('BM', ['bm', 'mål b'])

    # Säkra datatyper
    if 'Säsong' in df.columns:
        df['Säsong'] = df['Säsong'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    if 'År' in df.columns:
        df['År'] = df['År'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        
    text_columns = ['Hemmalag', 'Bortalag', 'Arena', 'Ort', 'NOT', 'Domare', 'Fas', 'Serie_H', 'Serie_B']
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].apply(fix_text)
            df[col] = df[col].fillna("")
            
    # Spara originalnamn och applicera mappning
    if 'Hemmalag' in df.columns: 
        df['Hemmalag_Org'] = df['Hemmalag']
        df['Hemmalag'] = df['Hemmalag'].apply(normalize_team)
    if 'Bortalag' in df.columns: 
        df['Bortalag_Org'] = df['Bortalag']
        df['Bortalag'] = df['Bortalag'].apply(normalize_team)
        
    # Beräkna serienivåer dynamiskt
    if 'Serie_H' in df.columns and 'Säs_nr' in df.columns:
        df['Nivå_H'] = df.apply(lambda r: get_tier(r['Serie_H'], r['Säs_nr']), axis=1)
    else:
        df['Nivå_H'] = 99
        
    if 'Serie_B' in df.columns and 'Säs_nr' in df.columns:
        df['Nivå_B'] = df.apply(lambda r: get_tier(r['Serie_B'], r['Säs_nr']), axis=1)
    else:
        df['Nivå_B'] = 99

    # Städa numeriska värden
    def safe_int_str(val):
        try:
            if pd.isna(val) or str(val).strip() == "" or str(val).lower() == 'nan': return ""
            return str(int(float(str(val).replace(',', '.'))))
        except: return ""

    num_cols = ['HM', 'BM', 'Förl_H', 'Förl_B', 'Straff_H', 'Straff_B', 'Publik', 'Avancerade', 'Säs_nr', 'Match_ID']
    for col in num_cols:
        if col in df.columns:
            df[col] = df[col].apply(safe_int_str)

    dlog("Matchdata har formaterats klart.")

except FileNotFoundError:
    print(f"KRITISKT FEL: Filen '{excel_file}' hittades inte. Kontrollera namnet.")
    sys.exit(1)
except Exception as e:
    dlog(f"KRITISKT FEL vid bearbetning av Cup-fliken: {e}")

all_teams = sorted(list(set([t for t in df['Hemmalag'].tolist() + df['Bortalag'].tolist() if str(t).strip() != "" and str(t).lower() != 'nan'])))

def safe_season_sort(val):
    if str(val).strip() == "" or str(val).lower() == 'nan': return (999999, "") 
    try:
        # Säker sortering genom att enbart extrahera de första fyra siffrorna i strängen
        digits = "".join(filter(str.isdigit, str(val)))
        return (0, float(digits[:4]) if digits else 0)
    except: return (1, str(val)) 

all_seasons_raw = sorted(list(set(df['Säsong'].tolist())), key=safe_season_sort)
all_seasons = [str(s) for s in all_seasons_raw if str(s).strip() != "" and str(s).lower() != 'nan']

# Extrahera unika Faser
all_phases = sorted(list(set([str(f).strip() for f in df['Fas'].tolist() if str(f).strip() != "" and str(f).lower() != 'nan'])))

# ==========================================
# BYGG EPOKER / ÅRTIONDEN
# ==========================================
decades = {}
custom_epochs = {}

for s in all_seasons:
    try:
        year_str = "".join(filter(str.isdigit, s))[:4]
        if len(year_str) == 4:
            decade = year_str[:3] + "0-talet"
            if decade not in decades: decades[decade] = []
            decades[decade].append(s)
    except Exception: pass

try:
    df_epochs = pd.read_excel(excel_file, sheet_name="Epoker")
    df_epochs.columns = df_epochs.columns.str.strip() 
    
    # Försök hitta kolumnerna dynamiskt
    c_period = next((c for c in df_epochs.columns if 'period' in c.lower() or 'epok' in c.lower()), df_epochs.columns[0])
    c_start = next((c for c in df_epochs.columns if 'första' in c.lower() or 'start' in c.lower()), df_epochs.columns[1])
    c_end = next((c for c in df_epochs.columns if 'sista' in c.lower() or 'slut' in c.lower()), df_epochs.columns[2])
    
    dlog(f"Hittade epok-kolumner: Namn='{c_period}', Start='{c_start}', Slut='{c_end}'")
    
    for _, row in df_epochs.iterrows():
        period_name = str(row.get(c_period, '')).strip()
        if not period_name or period_name == "nan": continue
        
        epoch_seasons = []
        try:
            s_str = str(row.get(c_start, ''))
            e_str = str(row.get(c_end, ''))
            
            if s_str == 'nan' or e_str == 'nan' or not s_str or not e_str: continue
            
            s_digits = "".join(filter(str.isdigit, s_str))
            e_digits = "".join(filter(str.isdigit, e_str))
            
            if not s_digits or not e_digits: continue
            
            start_yr = float(s_digits[:4])
            end_yr = float(e_digits[:4])
            
            for s in all_seasons:
                s_dig = "".join(filter(str.isdigit, str(s)))
                if s_dig:
                    s_yr = float(s_dig[:4])
                    if start_yr <= s_yr <= end_yr:
                        epoch_seasons.append(s)
        except Exception as e: 
            pass
            
        if epoch_seasons: 
            custom_epochs[period_name] = epoch_seasons
except Exception as e:
    dlog(f"Kunde inte läsa fliken Epoker: {e}")

# Förbered JSON data
json_match_data = df.to_json(orient="records", force_ascii=False)
json_teams_data = json.dumps(all_teams, ensure_ascii=False)
json_seasons_data = json.dumps(all_seasons, ensure_ascii=False)
json_decades_data = json.dumps(decades, ensure_ascii=False)
json_custom_epochs_data = json.dumps(custom_epochs, ensure_ascii=False)
json_team_mapping = json.dumps(team_mapping, ensure_ascii=False)
json_phases = json.dumps(all_phases, ensure_ascii=False)
json_py_logs = json.dumps(py_logs, ensure_ascii=False)

# ==========================================
# 3. HTML / FRONTEND
# ==========================================
html_template = """
<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Svenska Cupen Matchhistorik</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .custom-scroll::-webkit-scrollbar { width: 8px; height: 8px; }
        .custom-scroll::-webkit-scrollbar-track { background: #f1f1f1; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
        .custom-scroll::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
        .tab-btn.active { border-bottom: 2px solid #4f46e5; color: #312e81; font-weight: 600; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        optgroup { font-weight: 700; color: #475569; background-color: #f8fafc; }
        optgroup[disabled] { color: #94a3b8; background-color: #f1f5f9; }
        option { font-weight: normal; color: #0f172a; background-color: #fff; }
        .sortable-th { cursor: pointer; user-select: none; }
        .sortable-th:hover { background-color: #e2e8f0; }
    </style>
</head>
<body class="bg-slate-50 text-slate-800 font-sans min-h-screen">

    <!-- FELSÖKNINGSRUTA FÖR JAVASCRIPT-KRASCHER -->
    <div id="debug-box" class="hidden fixed bottom-4 right-4 w-96 bg-red-50 border-2 border-red-500 rounded-lg shadow-2xl z-[9999] flex flex-col max-h-96">
        <div class="bg-red-600 text-white px-4 py-2 font-bold flex justify-between items-center rounded-t-sm">
            <span>Systemfel upptäckt!</span>
            <button onclick="document.getElementById('debug-box').classList.add('hidden')" class="text-white hover:text-red-200 font-bold">✕</button>
        </div>
        <div class="p-3 overflow-y-auto text-xs font-mono text-red-900 space-y-2" id="debug-content"></div>
    </div>

    <header class="bg-indigo-900 text-white shadow-md">
        <div class="max-w-7xl mx-auto px-4 py-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
                <h1 class="text-3xl font-bold tracking-tight">Svenska Cupen Matchhistorik</h1>
                <p class="text-indigo-200 mt-1">David mot Goliat, straffar och cuptitlar</p>
                <p class="text-xs text-indigo-400 mt-1">Sammanställning av Jimmy Lindahl</p>
            </div>
            <a href="nationella_index.html" class="inline-flex items-center text-indigo-100 hover:text-white transition-colors text-sm font-medium bg-indigo-800 hover:bg-indigo-700 px-4 py-2 rounded-md shadow-sm border border-indigo-700">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>
                Tillbaka till översikten
            </a>
        </div>
    </header>

    <nav class="bg-white shadow-sm sticky top-0 z-20 border-b border-slate-200">
        <div class="max-w-7xl mx-auto px-4 flex overflow-x-auto custom-scroll">
            <button onclick="switchTab('overview')" id="btn-overview" class="tab-btn active whitespace-nowrap py-4 px-6 text-slate-500 hover:text-indigo-600">Säsongsöversikt & Mästare</button>
            <button onclick="switchTab('h2h')" id="btn-h2h" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-indigo-600">Head-to-Head</button>
            <button onclick="switchTab('search')" id="btn-search" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-indigo-600">Matchsök / Historik</button>
            <button onclick="switchTab('records')" id="btn-records" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-indigo-600">Topplistor</button>
            <button onclick="switchTab('streaks')" id="btn-streaks" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-indigo-600">Långa sviter</button>
            <button onclick="switchTab('tables')" id="btn-tables" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-indigo-600">Maratontabeller</button>
            <button onclick="switchTab('bracket')" id="btn-bracket" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-indigo-600">Slutspel & Träd</button>
            <button onclick="switchTab('upsets')" id="btn-upsets" class="tab-btn whitespace-nowrap py-4 px-6 text-pink-600 font-bold hover:text-pink-700 bg-pink-50">Största Skrällarna</button>
            <button onclick="switchTab('admin')" id="btn-admin" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-400 hover:text-slate-600">Datakontroll</button>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-4 py-8">
        
        <!-- FLIK 0: ÖVERSIKT -->
        <section id="tab-overview" class="tab-content active">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <div class="flex items-center gap-3 mb-2">
                    <span class="text-2xl">📖</span>
                    <h2 class="text-xl font-bold text-slate-800">Historiska Säsonger & Vinnare</h2>
                </div>
                <p class="text-slate-500 text-sm">Klicka på en säsong för att se detaljerad fakta, målskörd, debutanter och vem som lyfte bucklan.</p>
            </div>
            <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                <div class="overflow-x-auto custom-scroll" style="max-height: 800px;">
                    <table class="w-full text-left text-sm relative">
                        <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200 sticky top-0 z-10 shadow-sm">
                            <tr>
                                <th class="px-4 py-3">Säsong</th>
                                <th class="px-4 py-3">Cupsegrare / Mästare</th>
                                <th class="px-4 py-3 text-center">Deltagande Lag</th>
                                <th class="px-4 py-3 text-center">Matcher</th>
                                <th class="px-4 py-3 text-center">Målsnitt</th>
                                <th class="px-4 py-3 text-right">Mer info</th>
                            </tr>
                        </thead>
                        <tbody id="overview-table-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- FLIK 1: H2H -->
        <section id="tab-h2h" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <h2 class="text-xl font-bold mb-4">Analysera inbördes möten</h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Lag A (Fokuslag) <span id="rank-team-a" class="text-xs text-indigo-600 font-normal ml-2"></span></label>
                        <select id="h2h-team-a" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-indigo-500"></select>
                    </div>
                    <div class="flex justify-center pb-2"><span class="text-slate-400 font-bold">VS</span></div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Lag B (Motståndare) <span id="rank-team-b" class="text-xs text-indigo-600 font-normal ml-2"></span></label>
                        <select id="h2h-team-b" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-indigo-500"></select>
                    </div>
                </div>
                <div class="mt-4 flex flex-col md:flex-row justify-between items-center gap-4 border-t border-slate-100 pt-4">
                    <div class="flex flex-wrap gap-4 text-sm">
                        <label class="flex items-center gap-1 cursor-pointer"><input type="radio" name="h2h-context" value="all" checked onchange="calculateH2H()"> Alla möten</label>
                        <label class="flex items-center gap-1 cursor-pointer"><input type="radio" name="h2h-context" value="home" onchange="calculateH2H()"> Endast Lag A Hemma</label>
                        <label class="flex items-center gap-1 cursor-pointer"><input type="radio" name="h2h-context" value="away" onchange="calculateH2H()"> Endast Lag A Borta</label>
                    </div>
                    <div class="flex gap-2">
                        <button onclick="clearH2H()" class="bg-rose-100 hover:bg-rose-200 text-rose-800 font-medium py-2 px-4 rounded-md transition-colors text-sm">Rensa</button>
                        <button onclick="renderH2HOverview()" class="bg-slate-200 hover:bg-slate-300 text-slate-800 font-medium py-2 px-4 rounded-md transition-colors text-sm">Statistik mot alla</button>
                        <button onclick="calculateH2H()" class="bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-6 rounded-md transition-colors shadow-sm text-sm">Analysera VS</button>
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
                                    <th class="px-4 py-3">Säsong (Fas)</th><th class="px-4 py-3">Datum</th>
                                    <th class="px-4 py-3 text-right">Hemmalag (Serie)</th><th class="px-4 py-3 text-center">Resultat</th>
                                    <th class="px-4 py-3">Bortalag (Serie)</th><th class="px-4 py-3 text-right">Publik</th>
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
                <p class="text-xs text-slate-500 mb-3">* Målskillnad baseras enbart på spelet (ordinarie tid + förlängning). "V", "O" och "F" redovisar spelets resultat. "Gått Vidare" visar totala avancemang oavsett straffar.</p>
                <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                    <div class="overflow-x-auto custom-scroll" style="max-height: 750px;">
                        <table class="w-full text-left text-sm whitespace-nowrap relative">
                            <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200 sticky top-0 z-10 shadow-sm">
                                <tr>
                                    <th class="px-4 py-3 sortable-th" onclick="sortOverview('team')">Motståndare ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center" onclick="sortOverview('played')">Spelade ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center text-emerald-600" onclick="sortOverview('w')" title="Segrar under spel">V (Spel) ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center text-slate-500" onclick="sortOverview('d')" title="Oavgjort under spel">O (Spel) ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center text-rose-600" onclick="sortOverview('l')" title="Förluster under spel">F (Spel) ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center text-indigo-600" onclick="sortOverview('adv')" title="Antal gånger laget slagit ut/besegrat motståndaren totalt">Gått Vidare / Seger ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center" onclick="sortOverview('gf')">GM ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center" onclick="sortOverview('ga')">IM ↕</th>
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
                <div class="grid grid-cols-1 lg:grid-cols-4 gap-4 items-end">
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Säsong</label>
                        <select id="search-season" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-indigo-500"></select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Fas (Fritext eller välj)</label>
                        <input type="text" id="search-round" list="phase-list" placeholder="T.ex. Final..." class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-indigo-500">
                        <datalist id="phase-list"></datalist>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Lag</label>
                        <select id="search-team" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-indigo-500"></select>
                    </div>
                    <div class="flex gap-2">
                        <button onclick="clearSearch()" class="w-1/3 bg-slate-200 hover:bg-slate-300 text-slate-800 font-medium py-2 px-2 rounded-md transition-colors shadow-sm text-sm" title="Rensa filter">Rensa</button>
                        <button onclick="performSearch()" class="w-2/3 bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-2 rounded-md transition-colors shadow-sm text-sm">Sök</button>
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
                                    <th class="px-4 py-3">Säsong (Fas)</th><th class="px-4 py-3">Datum</th>
                                    <th class="px-4 py-3 text-right">Hemmalag (Serie)</th><th class="px-4 py-3 text-center">Resultat</th>
                                    <th class="px-4 py-3">Bortalag (Serie)</th><th class="px-4 py-3 text-right">Publik</th>
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
                        <h2 class="text-xl font-bold">Historiska Topplistor i Cupen</h2>
                        <p class="text-sm text-slate-500">Filtrera på lag för att se deras specifika rekord.</p>
                    </div>
                    <div class="w-full md:w-64">
                        <select id="records-team" onchange="renderRecords()" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-indigo-500"></select>
                    </div>
                </div>

                <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
                    <div class="border border-slate-200 rounded-lg overflow-hidden">
                        <div class="bg-slate-50 px-4 py-3 border-b border-slate-200"><h3 class="font-bold text-slate-700" id="rec-title-wins">Största segrarna (i spelet)</h3></div>
                        <div class="p-0 overflow-x-auto"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-list-wins"></tbody></table></div>
                    </div>
                    <div id="col-losses" class="border border-slate-200 rounded-lg overflow-hidden hidden">
                        <div class="bg-slate-50 px-4 py-3 border-b border-slate-200"><h3 class="font-bold text-slate-700" id="rec-title-losses">Största förlusterna (i spelet)</h3></div>
                        <div class="p-0 overflow-x-auto"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-list-losses"></tbody></table></div>
                    </div>
                    <div class="border border-slate-200 rounded-lg overflow-hidden">
                        <div class="bg-slate-50 px-4 py-3 border-b border-slate-200"><h3 class="font-bold text-slate-700" id="rec-title-goals">Målrikaste matcherna (i spelet)</h3></div>
                        <div class="p-0 overflow-x-auto"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-list-goals"></tbody></table></div>
                    </div>
                </div>
                
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div class="border border-slate-200 rounded-lg overflow-hidden">
                        <div class="bg-slate-50 px-4 py-3 border-b border-slate-200"><h3 class="font-bold text-slate-700" id="rec-title-penalties">Längsta Straffläggningarna</h3></div>
                        <div class="p-0 overflow-x-auto"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-list-penalties"></tbody></table></div>
                    </div>
                    <div class="border border-slate-200 rounded-lg overflow-hidden">
                        <div class="bg-slate-50 px-4 py-3 border-b border-slate-200"><h3 class="font-bold text-slate-700" id="rec-title-att-high">Högsta publiksiffrorna</h3></div>
                        <div class="p-0 overflow-x-auto"><table class="w-full text-left text-sm whitespace-nowrap"><tbody id="rec-list-att-high"></tbody></table></div>
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
                        <select id="streaks-team" onchange="calculateStreaks()" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-indigo-500">
                        </select>
                    </div>
                    <div class="flex gap-4 bg-slate-100 p-2 rounded-md justify-center">
                        <label class="flex items-center gap-1 cursor-pointer text-sm font-medium"><input type="radio" name="streak-context" value="all" checked onchange="calculateStreaks()"> Totalt</label>
                        <label class="flex items-center gap-1 cursor-pointer text-sm font-medium"><input type="radio" name="streak-context" value="home" onchange="calculateStreaks()"> Endast Hemma</label>
                        <label class="flex items-center gap-1 cursor-pointer text-sm font-medium"><input type="radio" name="streak-context" value="away" onchange="calculateStreaks()"> Endast Borta</label>
                    </div>
                    <div class="flex flex-col gap-2">
                        <div class="bg-indigo-50 border border-indigo-100 p-2 rounded-md">
                            <label class="flex items-center gap-2 cursor-pointer text-sm font-semibold text-indigo-800">
                                <input type="checkbox" id="streak-from-start" onchange="calculateStreaks()" class="w-4 h-4 text-indigo-600"> Enbart från säsongsstart
                            </label>
                        </div>
                        <div class="bg-indigo-50 border border-indigo-100 p-2 rounded-md">
                            <label class="flex items-center gap-2 cursor-pointer text-sm font-semibold text-indigo-800">
                                <input type="checkbox" id="streak-same-season" onchange="calculateStreaks()" class="w-4 h-4 text-indigo-600"> Bryt svit vid säsongsslut
                            </label>
                        </div>
                    </div>
                </div>
                
                <h3 class="text-lg font-bold mb-4 text-slate-700" id="streaks-main-title">Längsta Sviterna (I spelet, straffar = oavgjort)</h3>
                <div id="streaks-results" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4 hidden mb-8"></div>
                
                <div class="mt-8 pt-8 border-t border-slate-200">
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-4">
                        <h3 class="font-bold text-lg text-slate-700">Topp 10: Historiska Sviter</h3>
                        <select id="streak-toplist-type" onchange="renderStreakToplist()" class="w-full md:w-64 border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-indigo-500">
                            <option value="win" selected>Längsta Segersvit (Spel)</option>
                            <option value="unb">Längst Obesegrade (Spel)</option>
                            <option value="loss">Längsta Förlustsvit (Spel)</option>
                            <option value="winless">Längst Utan Seger (Spel)</option>
                            <option value="cs">Flest Hållna Nollor i rad</option>
                            <option value="ns">Längsta Måltorka i rad</option>
                            <option value="adv">Flest avancemang i rad (Inkl. straffar)</option>
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
            </div>
        </section>

        <!-- FLIK 5: Tabeller (Maraton) -->
        <section id="tab-tables" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <h2 class="text-xl font-bold mb-1">Dynamisk Maratontabell (Cupen)</h2>
                        <p class="text-sm text-slate-500">Bygg den ultimata maratontabellen. Välj om du vill räkna enbart spelet (som är standard), eller skapa specialtabeller enbart för förlängningar och straffar.</p>
                    </div>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-5 gap-4 items-end mb-4">
                    <div class="md:col-span-2">
                        <label class="block text-sm font-medium text-slate-700 mb-1">Tidsperiod / Epok</label>
                        <select id="table-epoch" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-indigo-500"></select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Inkludera faser</label>
                        <select id="table-phase" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-indigo-500">
                            <option value="ALL">Alla matchfaser</option>
                            <option value="GRUPP">Enbart Gruppspel</option>
                            <option value="SLUTSPEL">Enbart Utslagning / Slutspel</option>
                            <option value="FINAL">Enbart Finaler</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Speltid / Avgörande</label>
                        <select id="table-mode" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-indigo-500">
                            <option value="120">Ordinarie Tid + Förlängning (Std)</option>
                            <option value="90">Enbart Ordinarie Tid (90 min)</option>
                            <option value="FORL">Enbart Förlängningar</option>
                            <option value="STR">Enbart Straffläggningar</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Poäng/Seger</label>
                        <div class="flex gap-1">
                            <select id="table-points" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-indigo-500">
                                <option value="3">3 p</option><option value="2">2 p</option>
                            </select>
                            <button onclick="renderDynamicAllTimeTable()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium p-2 rounded-md shadow-sm">Visa</button>
                        </div>
                    </div>
                </div>
            </div>
            
            <div id="table-results" class="hidden bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden mb-6">
                <div class="bg-slate-50 p-3 border-b border-slate-200 flex flex-col md:flex-row justify-between items-start md:items-center">
                    <div class="flex items-center gap-4">
                        <h3 class="font-bold text-slate-700" id="table-title">Tabell</h3>
                        <span id="table-goal-stats" class="text-xs font-semibold text-indigo-800 bg-indigo-100 px-3 py-1 rounded hidden border border-indigo-200 shadow-sm"></span>
                    </div>
                </div>
                <div class="overflow-x-auto custom-scroll" style="max-height: 750px;">
                    <table class="w-full text-left text-sm whitespace-nowrap relative">
                        <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200 sticky top-0 z-10 shadow-sm" id="league-table-head"></thead>
                        <tbody id="league-table-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                    </table>
                </div>
                <div id="table-notes" class="bg-slate-50 p-3 border-t border-slate-200 text-xs text-rose-600 font-semibold flex flex-col gap-1 hidden"></div>
            </div>
        </section>

        <!-- FLIK 6: CUPTRÄD / AVANCEMANG -->
        <section id="tab-bracket" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <div class="flex items-center gap-3 mb-2">
                            <span class="text-2xl">🏆</span>
                            <h2 class="text-xl font-bold text-slate-800">Cupäventyret (Slutspel)</h2>
                        </div>
                        <p class="text-slate-500 text-sm max-w-3xl">Välj en säsong för att se vilka lag som nådde hela vägen och hur slutspelsfaserna utspelade sig.</p>
                    </div>
                </div>
                <div class="flex items-end gap-4 max-w-md">
                    <div class="flex-1">
                        <label class="block text-sm font-medium text-slate-700 mb-1">Säsong</label>
                        <select id="bracket-season" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-indigo-500"></select>
                    </div>
                    <button onclick="renderBracket()" class="bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-6 rounded-md shadow-sm transition-colors">Visa Slutspel</button>
                </div>
            </div>
            
            <div id="bracket-results" class="hidden">
                <div class="bg-gradient-to-r from-indigo-900 to-indigo-700 rounded-t-lg p-6 text-center text-white shadow-sm border-b-4 border-yellow-500">
                    <h3 class="text-sm font-medium text-indigo-200 uppercase tracking-widest mb-1">Cupsegrare <span id="bracket-season-label"></span></h3>
                    <div id="bracket-winner" class="text-4xl font-black text-yellow-400 drop-shadow-md"></div>
                </div>
                
                <div class="bg-white rounded-b-lg shadow-sm border border-slate-200 p-6">
                    <div id="bracket-stages" class="flex flex-col gap-8">
                        <!-- Här fylls omgångarna på via JS -->
                    </div>
                </div>
            </div>
        </section>

        <!-- FLIK 7: SKRÄLLARNA -->
        <section id="tab-upsets" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6 border-l-4 border-l-pink-500">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <div class="flex items-center gap-3 mb-2">
                            <span class="text-2xl">⚡</span>
                            <h2 class="text-xl font-bold text-slate-800">Tidernas Största Skrällar</h2>
                        </div>
                        <p class="text-slate-500 text-sm max-w-3xl">Listan visar matcher där ett lag från en lägre division slog ut ett lag från en högre division. Differensen baseras på serietillhörighet vid tillfället.</p>
                    </div>
                </div>
                
                <div class="flex flex-wrap gap-2 text-sm bg-slate-50 p-3 rounded border border-slate-200">
                    <button onclick="renderUpsets('all')" class="bg-white hover:bg-pink-50 border border-slate-300 text-slate-700 font-medium py-1 px-4 rounded transition-colors focus:ring-2 ring-pink-500 focus:border-pink-500">Alla Skrällar</button>
                    <button onclick="renderUpsets(3)" class="bg-white hover:bg-pink-50 border border-slate-300 text-slate-700 font-medium py-1 px-4 rounded transition-colors focus:ring-2 ring-pink-500 focus:border-pink-500">Minst 3 nivåers diff</button>
                    <button onclick="renderUpsets('final')" class="bg-white hover:bg-pink-50 border border-slate-300 text-slate-700 font-medium py-1 px-4 rounded transition-colors focus:ring-2 ring-pink-500 focus:border-pink-500">Skrällar i Final/Semi</button>
                </div>
            </div>
            
            <div id="upsets-results" class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                <div class="overflow-x-auto custom-scroll" style="max-height: 800px;">
                    <table class="w-full text-left text-sm whitespace-nowrap relative">
                        <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200 sticky top-0 z-10 shadow-sm">
                            <tr>
                                <th class="px-4 py-3">Säsong (Fas)</th>
                                <th class="px-4 py-3">Skrällaget</th>
                                <th class="px-4 py-3 text-center">Resultat</th>
                                <th class="px-4 py-3">Utslaget lag</th>
                                <th class="px-4 py-3 text-center font-bold text-pink-600">Nivådiff</th>
                            </tr>
                        </thead>
                        <tbody id="upsets-table-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- FLIK 8: DATAKONTROLL (ADMIN) -->
        <section id="tab-admin" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <div class="flex justify-between items-start mb-4">
                    <div>
                        <div class="flex items-center gap-3 mb-2">
                            <span class="text-2xl">⚙️</span>
                            <h2 class="text-xl font-bold text-slate-800">Datakontroll & Administration</h2>
                        </div>
                        <p class="text-slate-500 text-sm max-w-3xl">Här kan du kvalitetssäkra din Excel-fil. Koden letar automatiskt efter lag som saknar matchning i din alias-tabell, varnar om ett lag har registrerats i flera olika serier (Serie_H/B) under samma cupsäsong, samt listar alla lag som har spelat i cupen under mer än ett lagnamn.</p>
                    </div>
                    <div class="flex flex-col gap-2">
                        <button onclick="runDataCheck()" class="bg-slate-800 hover:bg-slate-900 text-white font-medium py-2 px-6 rounded-md shadow-sm transition-colors">Kör Granskning</button>
                        <button onclick="showPythonLogs()" class="bg-indigo-100 hover:bg-indigo-200 text-indigo-800 font-medium py-2 px-6 rounded-md shadow-sm transition-colors border border-indigo-300">Visa Python-logg</button>
                    </div>
                </div>
            </div>
            
            <div id="admin-results" class="hidden flex flex-col gap-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                        <div class="bg-rose-50 px-4 py-3 border-b border-rose-100">
                            <h3 class="font-bold text-rose-800">Saknas i "Cuplagen"</h3>
                            <p class="text-xs text-rose-600 mt-1">Lag som spelat matcher, men som koden inte hittar någon alias-matchning för. (Kan vara korrekt om de inte bytt namn, men bra för att identifiera nya lag!).</p>
                        </div>
                        <div class="p-4 overflow-y-auto custom-scroll" style="max-height: 350px;">
                            <ul id="admin-unmapped" class="list-disc pl-5 text-sm text-slate-600 marker:text-rose-400 space-y-1"></ul>
                        </div>
                    </div>

                    <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                        <div class="bg-amber-50 px-4 py-3 border-b border-amber-100">
                            <h3 class="font-bold text-amber-800">Serie-inkonsekvens</h3>
                            <p class="text-xs text-amber-600 mt-1">Lag som har olika Seriebeteckningar inom SAMMA säsong. (Detta är oftast ett skrivfel i Excel).</p>
                        </div>
                        <div class="p-4 overflow-y-auto custom-scroll" style="max-height: 350px;">
                            <ul id="admin-series" class="list-disc pl-5 text-sm text-slate-600 marker:text-amber-500 space-y-2"></ul>
                        </div>
                    </div>
                </div>
                
                <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden mt-2">
                    <div class="bg-indigo-50 px-4 py-3 border-b border-indigo-100">
                        <h3 class="font-bold text-indigo-800">Lag med flera namn (Alias)</h3>
                        <p class="text-xs text-indigo-600 mt-1">Lag som historiskt sett spelat under olika lagnamn men knutits samman till en och samma Lagbeteckning i maratontabellen.</p>
                    </div>
                    <div class="p-4 overflow-y-auto custom-scroll" style="max-height: 400px;">
                        <ul id="admin-aliases" class="list-disc pl-5 text-sm text-slate-600 marker:text-indigo-500 space-y-2"></ul>
                    </div>
                </div>
            </div>
        </section>

        <!-- Detalj-Modal för säsong (Placerad här i botten av main) -->
        <div id="season-modal" class="hidden fixed inset-0 bg-slate-900/60 z-50 flex items-center justify-center p-4">
            <div class="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
                <div class="p-6 border-b bg-indigo-900 text-white flex justify-between items-center">
                    <div>
                        <h3 id="season-modal-title" class="text-2xl font-bold"></h3>
                        <p id="season-modal-dates" class="text-indigo-200 text-sm mt-1"></p>
                    </div>
                    <button onclick="closeSeasonModal()" class="text-indigo-200 hover:text-white"><svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button>
                </div>
                <div class="p-6 overflow-y-auto custom-scroll flex-1 bg-slate-50">
                    <div class="bg-gradient-to-br from-yellow-50 to-amber-100 p-4 rounded-lg border border-yellow-200 text-center mb-6 shadow-sm">
                        <div class="text-xs font-bold text-yellow-600 uppercase tracking-widest mb-1">Cupsegrare</div>
                        <div id="season-modal-winner" class="text-3xl font-black text-yellow-700"></div>
                        <div id="season-modal-finalres" class="text-sm text-yellow-800 mt-2 font-medium"></div>
                    </div>
                    
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                        <div class="bg-white p-3 rounded shadow-sm border border-slate-200 text-center"><div class="text-xs text-slate-400">Lag</div><div id="sm-teams" class="text-xl font-bold text-indigo-700"></div></div>
                        <div class="bg-white p-3 rounded shadow-sm border border-slate-200 text-center"><div class="text-xs text-slate-400">Debutanter</div><div id="sm-debutants" class="text-xl font-bold text-emerald-600"></div></div>
                        <div class="bg-white p-3 rounded shadow-sm border border-slate-200 text-center"><div class="text-xs text-slate-400">Matcher</div><div id="sm-matches" class="text-xl font-bold text-slate-700"></div></div>
                        <div class="bg-white p-3 rounded shadow-sm border border-slate-200 text-center"><div class="text-xs text-slate-400">Publiksnitt</div><div id="sm-att" class="text-xl font-bold text-slate-700"></div></div>
                    </div>

                    <h4 class="font-bold text-slate-700 mb-2 border-b pb-1">Målstatistik</h4>
                    <div class="bg-white p-4 rounded shadow-sm border border-slate-200 mb-6">
                        <div class="flex justify-between items-center mb-2"><span class="text-sm text-slate-600">Totalt antal mål i spelet (90+120 min):</span> <span id="sm-goals" class="font-bold text-lg"></span></div>
                        <div class="w-full bg-slate-100 rounded-full h-2.5 mb-4 overflow-hidden flex"><div id="sm-bar-90" class="bg-blue-500 h-2.5"></div><div id="sm-bar-120" class="bg-indigo-500 h-2.5"></div></div>
                        <div class="grid grid-cols-3 text-xs text-center text-slate-500">
                            <div><span class="inline-block w-2 h-2 bg-blue-500 rounded-full mr-1"></span>Ordinarie tid: <b id="sm-goals-90" class="text-slate-700"></b></div>
                            <div><span class="inline-block w-2 h-2 bg-indigo-500 rounded-full mr-1"></span>Förlängning: <b id="sm-goals-120" class="text-slate-700"></b></div>
                            <div class="border-l border-slate-200">Straffmål (avgörande): <b id="sm-goals-str" class="text-slate-700"></b></div>
                        </div>
                    </div>
                    
                    <div id="sm-debutant-list-container" class="hidden">
                        <h4 class="font-bold text-slate-700 mb-2 border-b pb-1">Årets Debutanter</h4>
                        <div id="sm-debutant-list" class="text-sm text-slate-600 bg-white p-3 rounded border border-slate-200 shadow-sm leading-relaxed"></div>
                    </div>
                </div>
                <div class="p-4 border-t bg-white text-center">
                    <button id="btn-go-bracket" class="bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-8 rounded shadow transition-colors">Visa Slutspelsträd för säsongen</button>
                </div>
            </div>
        </div>

        <!-- MODAL FÖR SVIT-MATCHER (Placerad här i botten av main) -->
        <div id="streak-modal" class="hidden fixed inset-0 bg-slate-900/50 z-50 flex items-center justify-center p-4">
            <div class="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
                <div class="p-4 border-b flex justify-between items-center bg-slate-50 rounded-t-lg">
                    <h3 id="modal-title" class="text-lg font-bold text-slate-800"></h3>
                    <button onclick="closeStreakModal()" class="text-slate-500 hover:text-slate-800 p-1"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button>
                </div>
                <div class="p-0 overflow-y-auto custom-scroll flex-1">
                    <table class="w-full text-left text-sm whitespace-nowrap">
                        <thead class="bg-slate-100 sticky top-0 shadow-sm border-b border-slate-200">
                            <tr><th class="p-3">Säsong</th><th class="p-3">Fas</th><th class="p-3">Datum</th><th class="p-3 text-right">Hemmalag</th><th class="p-3 text-center">Resultat</th><th class="p-3">Bortalag</th></tr>
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
        const DECADES = %%DECADES_JSON%%;
        const CUSTOM_EPOCHS = %%CUSTOM_EPOCHS_JSON%%;
        const TEAM_MAPPING = %%TEAM_MAPPING_JSON%%;
        const PHASES = %%PHASES_JSON%%;
        const PY_LOGS = %%PY_LOGS_JSON%%;
        
        let currentOverviewData = []; let currentOverviewSort = { col: 'played', asc: false }; 
        let currentStreakMatches = {}; let globalAllStreaks = {}; 
        let ALL_TIME_TABLE = []; let TEAM_RANKS = {}; let TEAM_ALLTIME_PPG = {};

        // Felhanterings-system
        function logError(context, error) {
            console.error(context, error);
            const box = document.getElementById('debug-box');
            const content = document.getElementById('debug-content');
            if (box && content) {
                const errText = error ? (error.message + "\\n" + error.stack) : "Okänt fel";
                content.innerHTML += `<div class="border-b border-red-200 pb-2"><b>${context}:</b><br><pre class="whitespace-pre-wrap mt-1 text-[10px]">${errText}</pre></div>`;
                box.classList.remove('hidden');
            } else {
                alert("FEL i " + context + ": " + (error ? error.message : ""));
            }
        }

        window.onerror = function(msg, src, lineno, colno, err) {
            logError("Global Felhanterare (Rad " + lineno + ")", err || new Error(msg));
        };

        function showPythonLogs() {
            if (PY_LOGS && PY_LOGS.length > 0) {
                alert("PYTHON SYSTEM-LOGG:\\n\\n" + PY_LOGS.join("\\n"));
            } else {
                alert("Inga Python-loggar hittades.");
            }
        }

        function safeSetHTML(id, html) {
            let el = document.getElementById(id);
            if (el) el.innerHTML = html;
        }

        // Säkra int-parser
        function getInt(val) { return parseInt(val) || 0; }
        function hasVal(val) { return val !== "" && val !== null && val !== undefined; }

        // Hjälpfunktioner för resultat och avancemang
        function getMatchResultText(m) {
            try {
                if (!hasVal(m.HM) || !hasVal(m.BM)) {
                    let nTxt = String(m.NOT || "").toUpperCase();
                    if (nTxt.includes("W.O; H") || nTxt.includes("EJ KVALIFICERAD SPELARE; V")) return "W.O. (H)";
                    if (nTxt.includes("W.O; B") || nTxt.includes("EJ KVALIFICERAD SPELARE; F")) return "W.O. (B)";
                    return "-";
                }
                let hm = getInt(m.HM); let bm = getInt(m.BM);
                let res = `${hm} - ${bm}`;
                if (hasVal(m.Förl_H) && hasVal(m.Förl_B)) res = `${hm+getInt(m.Förl_H)} - ${bm+getInt(m.Förl_B)} e.f.`;
                if (hasVal(m.Straff_H) && hasVal(m.Straff_B)) res += ` (${getInt(m.Straff_H)}-${getInt(m.Straff_B)} str)`;
                return res;
            } catch(e) {
                logError("getMatchResultText", e);
                return "Fel";
            }
        }

        function getAdvancingTeam(m) {
            let c = getInt(m.Avancerade);
            if (c === 1 || c === 5) return 1;
            if (c === 2 || c === 4 || c === 6) return 2;
            return 0; 
        }

        function isBye(m) { return getInt(m.Avancerade) === 7; }
        
        function formatDate(val, fallbackYear) {
            if (!hasVal(val)) return fallbackYear || '-';
            let s = String(val).trim();
            if (s.length === 4) return s; 
            if (typeof val === 'number') {
                if (Math.abs(val) > 0 && Math.abs(val) < 10000) return String(val); 
                return new Date(val).toISOString().split('T')[0]; 
            }
            return s.length > 10 ? s.substring(0, 10) : s;
        }

        function extractYear(dateVal, fallback) {
            if (!hasVal(dateVal)) return fallback || '-';
            if (typeof dateVal === 'number') {
                if (Math.abs(dateVal) > 10000) return new Date(dateVal).getFullYear().toString();
                return String(dateVal);
            }
            const s = String(dateVal); return s.length >= 4 ? s.substring(0, 4) : fallback || '-';
        }

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
            else if (nTxt.includes("OMSPEL")) noteFound = "Omspel.";
            
            if (noteFound) { return dateStr ? `${dateStr} (${team1}-${team2}): ${noteFound}` : `(${team1}-${team2}): ${noteFound}`; }
            return null;
        }

        document.addEventListener('DOMContentLoaded', () => {
            try {
                initAllTimeTable(); 
                populateAllDropdowns();
                renderSeasonOverview();
                
                if(TEAMS.length >= 2 && ALL_TIME_TABLE.length >= 2) {
                    let elA = document.getElementById('h2h-team-a');
                    if (elA) {
                        elA.value = ALL_TIME_TABLE[0].team;
                        updateOpponentDropdown('h2h-team-a', 'h2h-team-b');
                        
                        let elB = document.getElementById('h2h-team-b');
                        if (elB) {
                            let bOpts = Array.from(elB.options).map(o => o.value);
                            if (bOpts.includes(ALL_TIME_TABLE[1].team)) { elB.value = ALL_TIME_TABLE[1].team; } 
                            else {
                                let validB = bOpts.filter(v => v !== "");
                                if (validB.length > 0) elB.value = validB[0];
                            }
                        }
                    }
                }
                
                calculateH2H();
                
                let h2hA = document.getElementById('h2h-team-a');
                if (h2hA) h2hA.addEventListener('change', () => { updateOpponentDropdown('h2h-team-a', 'h2h-team-b'); document.getElementById('h2h-overview').classList.add('hidden'); document.getElementById('h2h-results').classList.add('hidden'); });
                
                let h2hB = document.getElementById('h2h-team-b');
                if (h2hB) h2hB.addEventListener('change', () => { updateOpponentDropdown('h2h-team-b', 'h2h-team-a'); document.getElementById('h2h-overview').classList.add('hidden'); document.getElementById('h2h-results').classList.add('hidden'); });
                
                let sSeason = document.getElementById('search-season');
                if (sSeason) sSeason.addEventListener('change', () => { updateSearchTeamDropdown(); });
                
                if (SEASONS.length > 0) {
                    if(document.getElementById('search-season')) document.getElementById('search-season').value = [...SEASONS].reverse()[0];
                    if(document.getElementById('bracket-season')) document.getElementById('bracket-season').value = [...SEASONS].reverse()[0];
                }
                
                renderRecords(); 
                calculateStreaks(); 
                renderUpsets('all');
            } catch(e) {
                logError("Uppstart (DOMContentLoaded)", e);
            }
        });

        function clearH2H() {
            try {
                if(TEAMS.length >= 2 && ALL_TIME_TABLE.length >= 2) {
                    let elA = document.getElementById('h2h-team-a');
                    let elB = document.getElementById('h2h-team-b');
                    if(elA && elB) {
                        elA.value = ALL_TIME_TABLE[0].team;
                        updateOpponentDropdown('h2h-team-a', 'h2h-team-b');
                        
                        let bOpts = Array.from(elB.options).map(o => o.value);
                        if (bOpts.includes(ALL_TIME_TABLE[1].team)) { elB.value = ALL_TIME_TABLE[1].team; } 
                        else {
                            let validB = bOpts.filter(v => v !== "");
                            if (validB.length > 0) elB.value = validB[0];
                        }
                    }
                }
                if(document.getElementById('h2h-results')) document.getElementById('h2h-results').classList.add('hidden');
                if(document.getElementById('h2h-overview')) document.getElementById('h2h-overview').classList.add('hidden');
            } catch(e) { logError("clearH2H", e); }
        }

        function initAllTimeTable() {
            let table = {};
            MATCH_DATA.forEach(m => {
                if(isBye(m)) return;
                if(!m.Hemmalag || !m.Bortalag) return;
                [m.Hemmalag, m.Bortalag].forEach(t => { if(!table[t]) table[t] = { team: t, pld:0, w:0, d:0, l:0, gf:0, ga:0, gd:0, pts:0, seasons: new Set() }; });
                
                let notText = String(m.NOT || "").toUpperCase();
                let isWOH = notText.includes("W.O; H") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                let isWOB = notText.includes("W.O; B") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                
                let hm = hasVal(m.HM) ? getInt(m.HM) + (hasVal(m.Förl_H) ? getInt(m.Förl_H) : 0) : null;
                let bm = hasVal(m.BM) ? getInt(m.BM) + (hasVal(m.Förl_B) ? getInt(m.Förl_B) : 0) : null;
                
                if (hm === null || bm === null) {
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
                table[m.Hemmalag].seasons.add(String(m.Säsong)); table[m.Bortalag].seasons.add(String(m.Säsong));
            });
            
            let arr = Object.values(table);
            arr.forEach(r => { r.gd = r.gf - r.ga; TEAM_ALLTIME_PPG[r.team] = r.pld > 0 ? (r.pts / r.pld) : 0; });
            arr.sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf);
            ALL_TIME_TABLE = arr;
            arr.forEach((r, i) => { TEAM_RANKS[r.team] = i + 1; });
        }

        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            if(document.getElementById('tab-' + tabId)) document.getElementById('tab-' + tabId).classList.add('active');
            if(document.getElementById('btn-' + tabId)) document.getElementById('btn-' + tabId).classList.add('active');
        }

        function populateAllDropdowns() {
            try {
                let teamOpts = ''; TEAMS.forEach(team => { teamOpts += `<option value="${team}">${team}</option>`; });
                safeSetHTML('h2h-team-a', '<option value="">-- Välj ett lag --</option>' + teamOpts);
                safeSetHTML('h2h-team-b', '<option value="">-- Välj ett lag --</option>' + teamOpts);
                safeSetHTML('search-team', '<option value="">-- Alla lag --</option>' + teamOpts);
                safeSetHTML('records-team', '<option value="">-- Totalt i Cupen --</option>' + teamOpts);
                safeSetHTML('streaks-team', '<option value="ALL">-- Alla Lag (Historiska Rekord) --</option>' + teamOpts);

                let seasonOpts = '<option value="">-- Alla säsonger --</option>';
                [...SEASONS].reverse().forEach(s => { seasonOpts += `<option value="${s}">${s}</option>`; });
                safeSetHTML('search-season', seasonOpts);
                safeSetHTML('bracket-season', seasonOpts.replace('<option value="">-- Alla säsonger --</option>', ''));
                
                let phaseOpts = '';
                PHASES.forEach(p => { phaseOpts += `<option value="${p}">`; });
                safeSetHTML('phase-list', phaseOpts);

                updateSearchTeamDropdown();
                
                let epokOpts = '<option value="ALL">Totalt (Alla säsonger)</option>';
                if (Object.keys(CUSTOM_EPOCHS).length > 0) {
                    let block = '<optgroup label="Egna Epoker (Från Excel)">';
                    Object.keys(CUSTOM_EPOCHS).forEach(d => { block += `<option value="EPOCH_CUSTOM_${d}">${d}</option>`; });
                    block += '</optgroup>'; epokOpts += block;
                }
                if (Object.keys(DECADES).length > 0) {
                    let block = '<optgroup label="Årtionden">';
                    Object.keys(DECADES).reverse().forEach(d => { block += `<option value="EPOCH_DECADE_${d}">${d}</option>`; });
                    block += '</optgroup>'; epokOpts += block;
                }
                safeSetHTML('table-epoch', epokOpts);
            } catch(e) { logError("populateAllDropdowns", e); }
        }

        function updateSearchTeamDropdown() {
            let elSeason = document.getElementById('search-season');
            let elTarget = document.getElementById('search-team');
            if(!elSeason || !elTarget) return;

            const season = elSeason.value; 
            const currentTargetValue = elTarget.value;
            if (!season) {
                let teamOpts = '<option value="">-- Alla lag --</option>'; TEAMS.forEach(team => { teamOpts += `<option value="${team}">${team}</option>`; });
                elTarget.innerHTML = teamOpts; elTarget.value = currentTargetValue; return;
            }
            const validTeams = new Set();
            MATCH_DATA.forEach(m => { if (String(m.Säsong) === season && !isBye(m)) { if(m.Hemmalag) validTeams.add(m.Hemmalag); if(m.Bortalag) validTeams.add(m.Bortalag); } });
            const activeTeams = TEAMS.filter(t => validTeams.has(t)); const inactiveTeams = TEAMS.filter(t => !validTeams.has(t));
            let html = '<option value="">-- Alla lag --</option>';
            if (activeTeams.length > 0) { html += '<optgroup label="Spelade i Cupen denna säsong">'; activeTeams.forEach(t => { html += `<option value="${t}">${t}</option>`; }); html += '</optgroup>'; }
            if (inactiveTeams.length > 0) { html += '<optgroup label="Deltog ej" disabled>'; inactiveTeams.forEach(t => { html += `<option value="${t}">${t}</option>`; }); html += '</optgroup>'; }
            elTarget.innerHTML = html; elTarget.value = validTeams.has(currentTargetValue) ? currentTargetValue : "";
        }

        function updateOpponentDropdown(sourceId, targetId) {
            let elSource = document.getElementById(sourceId);
            let elTarget = document.getElementById(targetId);
            if(!elSource || !elTarget) return;

            const sourceTeam = elSource.value; 
            const currentTargetValue = elTarget.value;
            if (!sourceTeam) {
                let options = '<option value="">-- Välj ett lag --</option>'; TEAMS.forEach(team => { options += `<option value="${team}">${team}</option>`; });
                elTarget.innerHTML = options; elTarget.value = currentTargetValue; return;
            }
            const opponents = new Set();
            MATCH_DATA.forEach(m => { if(!isBye(m)) { if (m.Hemmalag === sourceTeam) opponents.add(m.Bortalag); if (m.Bortalag === sourceTeam) opponents.add(m.Hemmalag); } });
            const validOpponents = TEAMS.filter(t => opponents.has(t));
            
            let html = '<option value="">-- Välj motståndare --</option>';
            if (validOpponents.length > 0) { 
                validOpponents.forEach(t => { html += `<option value="${t}">${t}</option>`; }); 
            } else {
                html += `<option value="" disabled>Inga motståndare hittades</option>`;
            }
            elTarget.innerHTML = html; 
            elTarget.value = validOpponents.includes(currentTargetValue) ? currentTargetValue : "";
        }

        // --- ÖVERSIKT / MÄSTARE ---
        function renderSeasonOverview() {
            try {
                let overviewData = [];
                [...SEASONS].reverse().forEach(season => {
                    let sMatches = MATCH_DATA.filter(m => String(m.Säsong) === season && !isBye(m));
                    if(sMatches.length === 0) return;
                    
                    let winner = "-", finalMatch = null;
                    let fMatch = sMatches.find(m => getInt(m.Avancerade) === 5 || getInt(m.Avancerade) === 6);
                    if (fMatch) {
                        winner = (getInt(fMatch.Avancerade) === 5) ? (fMatch.Hemmalag_Org || fMatch.Hemmalag) : (fMatch.Bortalag_Org || fMatch.Bortalag);
                        finalMatch = fMatch;
                    } else {
                        let fbMatch = sMatches.find(m => String(m.Fas).toLowerCase().includes('final') && !String(m.Fas).toLowerCase().includes('kvart') && !String(m.Fas).toLowerCase().includes('semi'));
                        if(fbMatch) {
                            let adv = getAdvancingTeam(fbMatch);
                            if(adv===1) winner = fbMatch.Hemmalag_Org || fbMatch.Hemmalag;
                            else if(adv===2) winner = fbMatch.Bortalag_Org || fbMatch.Bortalag;
                            finalMatch = fbMatch;
                        }
                    }
                    
                    let teamsInSeason = new Set(); let g90=0, g120=0, gStr=0;
                    sMatches.forEach(m => {
                        if(m.Hemmalag) teamsInSeason.add(m.Hemmalag); 
                        if(m.Bortalag) teamsInSeason.add(m.Bortalag);
                        g90 += (getInt(m.HM) + getInt(m.BM));
                        g120 += (getInt(m.Förl_H) + getInt(m.Förl_B));
                        gStr += (getInt(m.Straff_H) + getInt(m.Straff_B));
                    });
                    
                    let gTot = g90 + g120;
                    let avg = sMatches.length > 0 ? (gTot / sMatches.length).toFixed(2) : "0.00";
                    
                    overviewData.push({
                        season: season, winner: winner,
                        matches: sMatches.length, teams: teamsInSeason.size,
                        avg: avg, g90: g90, g120: g120, gStr: gStr,
                        finalRes: finalMatch ? getMatchResultText(finalMatch) : "",
                        teamsSet: teamsInSeason
                    });
                });
                
                let html = overviewData.map((d, i) => `
                    <tr class="hover:bg-slate-50 cursor-pointer transition-colors" onclick='openSeasonModal(${i})'>
                        <td class="px-4 py-3 font-medium text-slate-800">${d.season}</td>
                        <td class="px-4 py-3 font-bold text-yellow-600">${d.winner} ${d.winner !== '-' ? '🏆' : ''}</td>
                        <td class="px-4 py-3 text-center text-slate-500">${d.teams}</td>
                        <td class="px-4 py-3 text-center text-slate-500">${d.matches}</td>
                        <td class="px-4 py-3 text-center font-mono font-bold">${d.avg}</td>
                        <td class="px-4 py-3 text-right text-indigo-600 font-bold">»</td>
                    </tr>
                `).join('');
                
                safeSetHTML('overview-table-body', html);
                window._seasonOverviewData = overviewData;
            } catch(e) { logError("renderSeasonOverview", e); }
        }

        function openSeasonModal(index) {
            try {
                const d = window._seasonOverviewData[index];
                document.getElementById('season-modal-title').innerText = `Säsongen ${d.season}`;
                
                let sMatches = MATCH_DATA.filter(m => String(m.Säsong) === d.season && !isBye(m));
                sMatches.sort((a,b) => {
                    let d1 = new Date(formatDate(a.Matchdatum, a.År)).getTime(); let d2 = new Date(formatDate(b.Matchdatum, b.År)).getTime();
                    if(isNaN(d1)) d1=0; if(isNaN(d2)) d2=0; return d1-d2;
                });
                let dStart = sMatches.length > 0 ? formatDate(sMatches[0].Matchdatum, sMatches[0].År) : "?";
                let dEnd = sMatches.length > 0 ? formatDate(sMatches[sMatches.length-1].Matchdatum, sMatches[sMatches.length-1].År) : "?";
                document.getElementById('season-modal-dates').innerText = `${dStart} — ${dEnd}`;
                
                document.getElementById('season-modal-winner').innerText = d.winner;
                document.getElementById('season-modal-finalres').innerText = d.finalRes ? `Final: ${d.finalRes}` : "";
                
                document.getElementById('sm-teams').innerText = d.teams;
                document.getElementById('sm-matches').innerText = d.matches;
                
                let totAtt=0, attMatches=0;
                sMatches.forEach(m => { if(hasVal(m.Publik)) {totAtt+=getInt(m.Publik); attMatches++;} });
                document.getElementById('sm-att').innerText = attMatches > 0 ? Math.round(totAtt/attMatches).toLocaleString('sv-SE') : "-";
                
                document.getElementById('sm-goals').innerText = d.g90 + d.g120;
                document.getElementById('sm-goals-90').innerText = d.g90;
                document.getElementById('sm-goals-120').innerText = d.g120;
                document.getElementById('sm-goals-str').innerText = d.gStr;
                
                let w90 = ((d.g90 / (d.g90+d.g120)) * 100) || 0;
                document.getElementById('sm-bar-90').style.width = `${w90}%`;
                document.getElementById('sm-bar-120').style.width = `${100-w90}%`;

                // Debutanter
                let debutants = [];
                d.teamsSet.forEach(t => {
                    let firstAppearance = null;
                    for (let s of [...SEASONS].sort((a,b)=> {
                        let na = parseFloat(a.replace(/[^0-9]/g,'')) || 0;
                        let nb = parseFloat(b.replace(/[^0-9]/g,'')) || 0;
                        return na - nb;
                    })) {
                        let played = MATCH_DATA.some(m => String(m.Säsong) === s && !isBye(m) && (m.Hemmalag === t || m.Bortalag === t));
                        if (played) { firstAppearance = s; break; }
                    }
                    if (firstAppearance === d.season) debutants.push(t);
                });
                
                document.getElementById('sm-debutants').innerText = debutants.length;
                if(debutants.length > 0) {
                    document.getElementById('sm-debutant-list').innerText = debutants.join(", ");
                    document.getElementById('sm-debutant-list-container').classList.remove('hidden');
                } else {
                    document.getElementById('sm-debutant-list-container').classList.add('hidden');
                }
                
                document.getElementById('btn-go-bracket').onclick = function() {
                    closeSeasonModal();
                    if(document.getElementById('bracket-season')) document.getElementById('bracket-season').value = d.season;
                    switchTab('bracket');
                    renderBracket();
                };
                
                document.getElementById('season-modal').classList.remove('hidden');
            } catch(e) { logError("openSeasonModal", e); }
        }
        function closeSeasonModal() { document.getElementById('season-modal').classList.add('hidden'); }


        // --- H2H ---
        function calculateH2H() {
            try {
                let elA = document.getElementById('h2h-team-a'); let elB = document.getElementById('h2h-team-b');
                if(!elA || !elB) return;
                const teamA = elA.value; const teamB = elB.value;
                
                let elCtx = document.querySelector('input[name="h2h-context"]:checked');
                const context = elCtx ? elCtx.value : 'all';
                if (!teamA || !teamB || teamA === teamB) return;
                
                if(document.getElementById('h2h-overview')) document.getElementById('h2h-overview').classList.add('hidden');
                let h2hMatches = MATCH_DATA.filter(m => !isBye(m) && ((m.Hemmalag === teamA && m.Bortalag === teamB) || (m.Hemmalag === teamB && m.Bortalag === teamA)));
                if (context === 'home') h2hMatches = h2hMatches.filter(m => m.Hemmalag === teamA);
                if (context === 'away') h2hMatches = h2hMatches.filter(m => m.Bortalag === teamA);
                h2hMatches.sort((a, b) => {
                    let d1 = new Date(formatDate(a.Matchdatum, a.År)).getTime(); let d2 = new Date(formatDate(b.Matchdatum, b.År)).getTime();
                    if(isNaN(d1)) d1=0; if(isNaN(d2)) d2=0; if(d1!==d2) return d1-d2; return getInt(a.Match_ID) - getInt(b.Match_ID);
                });
                
                let winsA = 0, draws = 0, winsB = 0, tableHTML = '';
                let matchNotes = new Set();
                
                h2hMatches.forEach(match => {
                    const isHomeA = match.Hemmalag === teamA;
                    let origH = match.Hemmalag_Org || match.Hemmalag;
                    let origB = match.Bortalag_Org || match.Bortalag;
                    let displayDate = formatDate(match.Matchdatum, match.År);
                    
                    let noteStr = getNoteString(origH, origB, match.NOT, displayDate);
                    if (noteStr) matchNotes.add(noteStr);

                    let resText = getMatchResultText(match);
                    let isWOH = resText === "W.O. (H)"; let isWOB = resText === "W.O. (B)";
                    
                    let hm = hasVal(match.HM) ? getInt(match.HM) + (hasVal(match.Förl_H) ? getInt(match.Förl_H) : 0) : null;
                    let bm = hasVal(match.BM) ? getInt(match.BM) + (hasVal(match.Förl_B) ? getInt(match.Förl_B) : 0) : null;
                    
                    if (isWOH) { if (isHomeA) winsA++; else winsB++; }
                    else if (isWOB) { if (!isHomeA) winsA++; else winsB++; }
                    else if (hm !== null && bm !== null) {
                        const matchGoalsA = isHomeA ? hm : bm; const matchGoalsB = isHomeA ? bm : hm;
                        if (matchGoalsA > matchGoalsB) winsA++; else if (matchGoalsA < matchGoalsB) winsB++; else draws++;
                    }

                    let adv = getAdvancingTeam(match);
                    let aWon = (isHomeA && adv === 1) || (!isHomeA && adv === 2) || (hm > bm && isHomeA) || (bm > hm && !isHomeA);
                    let bWon = (!isHomeA && adv === 1) || (isHomeA && adv === 2) || (hm < bm && isHomeA) || (bm < hm && !isHomeA);
                    
                    let homeBold = (adv === 1 || (hm>bm && adv===0)) ? 'font-bold text-indigo-600' : '';
                    let awayBold = (adv === 2 || (bm>hm && adv===0)) ? 'font-bold text-indigo-600' : '';
                    
                    let fasStr = match.Fas ? `<span class="text-[10px] bg-slate-200 px-1 rounded ml-1">${match.Fas}</span>` : '';
                    let sH = match.Serie_H ? ` <span class="text-slate-400 font-normal">(${match.Serie_H})</span>` : '';
                    let sB = match.Serie_B ? ` <span class="text-slate-400 font-normal">(${match.Serie_B})</span>` : '';

                    tableHTML += `<tr class="hover:bg-slate-50"><td class="px-4 py-2">${match.Säsong} ${fasStr}</td><td class="px-4 py-2 text-slate-500 text-xs">${displayDate}</td><td class="px-4 py-2 text-right ${homeBold}">${origH}${sH}</td><td class="px-4 py-2 text-center font-mono bg-slate-50 border-x border-slate-100 font-semibold">${resText}</td><td class="px-4 py-2 ${awayBold}">${origB}${sB}</td><td class="px-4 py-2 text-right text-slate-500">${hasVal(match.Publik) ? getInt(match.Publik).toLocaleString('sv-SE') : '-'}</td></tr>`;
                });
                safeSetHTML('h2h-table-body', tableHTML || '<tr><td colspan="6" class="text-center py-6 text-slate-500">Inga möten hittades.</td></tr>');
                
                let nHtml = ""; matchNotes.forEach(n => { nHtml += `<div>* ${n}</div>`; });
                const notesEl = document.getElementById('h2h-notes');
                if(notesEl) {
                    if (nHtml !== "") { notesEl.innerHTML = nHtml; notesEl.classList.remove('hidden'); } else { notesEl.classList.add('hidden'); }
                }

                safeSetHTML('h2h-summary-cards', `<div class="bg-indigo-50 p-3 rounded-lg border border-indigo-100 text-center"><div class="text-xs text-indigo-600 font-medium uppercase tracking-wider mb-1">Möten</div><div class="text-2xl font-bold text-indigo-900">${h2hMatches.length}</div></div><div class="bg-emerald-50 p-3 rounded-lg border border-emerald-100 text-center"><div class="text-xs text-emerald-600 font-medium uppercase tracking-wider mb-1">Vinster (Spel) ${teamA}</div><div class="text-2xl font-bold text-emerald-900">${winsA}</div></div><div class="bg-slate-100 p-3 rounded-lg border border-slate-200 text-center"><div class="text-xs text-slate-600 font-medium uppercase tracking-wider mb-1">Oavgjort / Straffar</div><div class="text-2xl font-bold text-slate-800">${draws}</div></div><div class="bg-rose-50 p-3 rounded-lg border border-rose-100 text-center"><div class="text-xs text-rose-600 font-medium uppercase tracking-wider mb-1">Vinster (Spel) ${teamB}</div><div class="text-2xl font-bold text-rose-900">${winsB}</div></div>`);
                if(document.getElementById('h2h-results')) document.getElementById('h2h-results').classList.remove('hidden');
            } catch(e) { logError("calculateH2H", e); }
        }

        function renderH2HOverview() {
            try {
                let elA = document.getElementById('h2h-team-a'); if(!elA) return;
                const teamA = elA.value; 
                let elCtx = document.querySelector('input[name="h2h-context"]:checked');
                const context = elCtx ? elCtx.value : 'all';
                if (!teamA) { alert("Välj Lag A först."); return; }
                if(document.getElementById('h2h-results')) document.getElementById('h2h-results').classList.add('hidden');
                
                let oppStats = {}; let matches = MATCH_DATA.filter(m => !isBye(m) && (m.Hemmalag === teamA || m.Bortalag === teamA));
                if (context === 'home') matches = matches.filter(m => m.Hemmalag === teamA);
                if (context === 'away') matches = matches.filter(m => m.Bortalag === teamA);
                matches.forEach(m => {
                    const isHome = m.Hemmalag === teamA; const opp = isHome ? m.Bortalag : m.Hemmalag;
                    
                    let resText = getMatchResultText(m);
                    let isWOH = resText === "W.O. (H)"; let isWOB = resText === "W.O. (B)";
                    
                    let hm = hasVal(m.HM) ? getInt(m.HM) + (hasVal(m.Förl_H) ? getInt(m.Förl_H) : 0) : null;
                    let bm = hasVal(m.BM) ? getInt(m.BM) + (hasVal(m.Förl_B) ? getInt(m.Förl_B) : 0) : null;
                    
                    if (!oppStats[opp]) oppStats[opp] = { team: opp, played: 0, w: 0, d: 0, l: 0, adv: 0, gf: 0, ga: 0, gd: 0 };
                    oppStats[opp].played++; 
                    
                    if (hm !== null && bm !== null && !isWOH && !isWOB) {
                        const gf = isHome ? hm : bm; const ga = isHome ? bm : hm;
                        oppStats[opp].gf += gf; oppStats[opp].ga += ga;
                        if (gf > ga) oppStats[opp].w++; else if (gf < ga) oppStats[opp].l++; else oppStats[opp].d++;
                    } else if (isWOH) {
                        if (isHome) oppStats[opp].w++; else oppStats[opp].l++;
                    } else if (isWOB) {
                        if (!isHome) oppStats[opp].w++; else oppStats[opp].l++;
                    }
                    
                    let adv = getAdvancingTeam(m);
                    if ((isHome && adv === 1) || (!isHome && adv === 2)) oppStats[opp].adv++;
                    
                    oppStats[opp].gd = oppStats[opp].gf - oppStats[opp].ga;
                });
                currentOverviewData = Object.values(oppStats);
                let ot = document.getElementById('overview-title');
                if(ot) ot.innerText = `Sammanställning: ${teamA} ${context === 'home' ? '(Endast Hemma)' : context === 'away' ? '(Endast Borta)' : '(Alla Möten)'}`;
                sortOverview('played', true); 
                if(document.getElementById('h2h-overview')) document.getElementById('h2h-overview').classList.remove('hidden');
            } catch(e) { logError("renderH2HOverview", e); }
        }

        function sortOverview(col, forceDesc = false) {
            try {
                if (forceDesc) { currentOverviewSort.col = col; currentOverviewSort.asc = false; }
                else if (currentOverviewSort.col === col) { currentOverviewSort.asc = !currentOverviewSort.asc; }
                else { currentOverviewSort.col = col; currentOverviewSort.asc = false; }
                currentOverviewData.sort((a, b) => {
                    let valA = a[col], valB = b[col];
                    if (typeof valA === 'string') return currentOverviewSort.asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
                    return currentOverviewSort.asc ? valA - valB : valB - valA;
                });
                let html = currentOverviewData.map(r => `<tr class="hover:bg-slate-50"><td class="px-4 py-2 font-medium">${r.team}</td><td class="px-4 py-2 text-center bg-slate-50 border-x border-slate-100">${r.played}</td><td class="px-4 py-2 text-center text-emerald-600 font-semibold">${r.w}</td><td class="px-4 py-2 text-center text-slate-500">${r.d}</td><td class="px-4 py-2 text-center text-rose-600">${r.l}</td><td class="px-4 py-2 text-center font-bold text-indigo-600 bg-indigo-50">${r.adv}</td><td class="px-4 py-2 text-center">${r.gf}</td><td class="px-4 py-2 text-center">${r.ga}</td></tr>`).join('');
                safeSetHTML('h2h-overview-body', html);
            } catch(e) { logError("sortOverview", e); }
        }

        // --- MATCHSÖK ---
        function clearSearch() {
            let elR = document.getElementById('search-round'); if(elR) elR.value = ""; 
            let elS = document.getElementById('search-season'); if(elS) elS.value = [...SEASONS].reverse()[0];
            updateSearchTeamDropdown(); 
            let elT = document.getElementById('search-team'); if(elT) elT.value = ""; 
            performSearch();
        }

        function performSearch() {
            try {
                let elS = document.getElementById('search-season'); const season = elS ? elS.value : ""; 
                let elR = document.getElementById('search-round'); const fasRaw = elR ? elR.value.trim().toLowerCase() : "";
                let elT = document.getElementById('search-team'); const team = elT ? elT.value : "";
                
                let filtered = MATCH_DATA.filter(m => !isBye(m));
                if (season) filtered = filtered.filter(m => String(m.Säsong) === season);
                if (fasRaw !== "") filtered = filtered.filter(m => String(m.Fas).toLowerCase().includes(fasRaw));
                if (team) filtered = filtered.filter(m => m.Hemmalag === team || m.Bortalag === team);
                
                filtered.sort((a, b) => getInt(b.Match_ID) - getInt(a.Match_ID));
                let tableHTML = ''; let totalPublik = 0, matcherMedPublik = 0;
                let matchNotes = new Set();

                filtered.forEach(match => {
                    let displayDate = formatDate(match.Matchdatum, match.År); 
                    if (hasVal(match.Publik)) { totalPublik += getInt(match.Publik); matcherMedPublik++; }

                    let origH = match.Hemmalag_Org || match.Hemmalag;
                    let origB = match.Bortalag_Org || match.Bortalag;
                    let noteStr = getNoteString(origH, origB, match.NOT, displayDate);
                    if (noteStr) matchNotes.add(noteStr);

                    let resText = getMatchResultText(match);
                    let adv = getAdvancingTeam(match);
                    
                    let homeBold = (adv === 1) ? 'font-bold' : '';
                    let awayBold = (adv === 2) ? 'font-bold' : '';
                    if (team) {
                        if (match.Hemmalag === team) homeBold += ' text-indigo-700 underline';
                        if (match.Bortalag === team) awayBold += ' text-indigo-700 underline';
                    }

                    let fasStr = match.Fas ? `<span class="text-[10px] bg-slate-200 px-1 rounded block mt-1 w-fit">${match.Fas}</span>` : '';
                    let nHStr = match.Serie_H ? `<span class="text-[10px] text-slate-400"> (${match.Serie_H})</span>` : '';
                    let nBStr = match.Serie_B ? `<span class="text-[10px] text-slate-400"> (${match.Serie_B})</span>` : '';

                    tableHTML += `<tr class="hover:bg-slate-50"><td class="px-4 py-2">${match.Säsong}${fasStr}</td><td class="px-4 py-2 text-slate-500 text-xs">${displayDate}</td><td class="px-4 py-2 text-right ${homeBold}">${origH}${nHStr}</td><td class="px-4 py-2 text-center bg-slate-50 border-x border-slate-100"><span class="font-mono font-bold">${resText}</span></td><td class="px-4 py-2 ${awayBold}">${origB}${nBStr}</td><td class="px-4 py-2 text-right text-slate-500">${hasVal(match.Publik) ? getInt(match.Publik).toLocaleString('sv-SE') : '-'}</td></tr>`;
                });
                
                safeSetHTML('search-table-body', tableHTML || '<tr><td colspan="7" class="text-center py-6 text-slate-500">Inga matcher matchade sökningen.</td></tr>');
                
                let nHtml = ""; matchNotes.forEach(n => { nHtml += `<div>* ${n}</div>`; });
                const notesEl = document.getElementById('search-notes');
                if (notesEl) {
                    if (nHtml !== "") { notesEl.innerHTML = nHtml; notesEl.classList.remove('hidden'); } else { notesEl.classList.add('hidden'); }
                }

                let snitt = matcherMedPublik > 0 ? Math.round(totalPublik / matcherMedPublik).toLocaleString('sv-SE') : 0;
                safeSetHTML('search-summary-text', `Hittade <span class="font-bold text-indigo-600">${filtered.length}</span> matcher. ${matcherMedPublik > 0 ? `Snitt: <span class="font-bold">${snitt}</span>` : ''}`);
                if(document.getElementById('search-results')) document.getElementById('search-results').classList.remove('hidden');
            } catch(e) { logError("performSearch", e); }
        }

        // --- REKORD ---
        function renderRecords() {
            try {
                let elTeam = document.getElementById('records-team');
                const team = elTeam ? elTeam.value : ""; 
                
                if (!team) {
                    if(document.getElementById('col-losses')) document.getElementById('col-losses').classList.add('hidden');
                    if(document.getElementById('rec-title-wins')) document.getElementById('rec-title-wins').innerText = 'Största Segrarna (i spelet)';
                } else {
                    if(document.getElementById('col-losses')) document.getElementById('col-losses').classList.remove('hidden');
                    if(document.getElementById('rec-title-wins')) document.getElementById('rec-title-wins').innerText = `Största segrar för ${team}`;
                    if(document.getElementById('rec-title-losses')) document.getElementById('rec-title-losses').innerText = `Största förluster för ${team}`;
                }
                
                if(document.getElementById('rec-title-goals')) document.getElementById('rec-title-goals').innerText = team ? `Målrikaste matcherna för ${team}` : 'Målrikaste matcherna (i spelet)';
                
                let teamData = MATCH_DATA.filter(m => !isBye(m));
                if (team) teamData = teamData.filter(m => m.Hemmalag === team || m.Bortalag === team);
                
                const buildRows = (matches, valueKeyFn, valueLabel = "") => {
                    if (matches.length === 0) return `<tr><td colspan="5" class="py-4 text-center text-slate-500 italic">Inga rekord hittades.</td></tr>`;
                    return matches.map(m => {
                        let origH = m.Hemmalag_Org || m.Hemmalag;
                        let origB = m.Bortalag_Org || m.Bortalag;
                        let hClass = (team && m.Hemmalag === team) ? 'font-bold text-slate-900' : 'text-slate-700';
                        let aClass = (team && m.Bortalag === team) ? 'font-bold text-slate-900' : 'text-slate-700';
                        return `<tr class="border-b border-slate-100 hover:bg-slate-50"><td class="py-2 px-2 text-xs text-slate-500 w-12 font-medium">${extractYear(m.Matchdatum, m.År)}</td><td class="py-2 px-2 text-right ${hClass} truncate max-w-[100px]" title="${origH}">${origH}</td><td class="py-2 px-2 text-center bg-slate-50/50 w-24"><span class="font-mono font-bold text-[11px] block whitespace-nowrap">${getMatchResultText(m)}</span></td><td class="py-2 px-2 ${aClass} truncate max-w-[100px]" title="${origB}">${origB}</td><td class="py-2 px-2 text-right font-semibold text-indigo-600">${valueKeyFn(m)} ${valueLabel}</td></tr>`;
                    }).join('');
                };

                let validGoals = teamData.filter(m => hasVal(m.HM) && hasVal(m.BM));
                
                let winsData = team ? validGoals.filter(m => {
                    let hm = getInt(m.HM) + (hasVal(m.Förl_H) ? getInt(m.Förl_H) : 0);
                    let bm = getInt(m.BM) + (hasVal(m.Förl_B) ? getInt(m.Förl_B) : 0);
                    return (m.Hemmalag === team && hm > bm) || (m.Bortalag === team && bm > hm);
                }) : validGoals;
                
                let biggestWins = [...winsData].sort((a, b) => {
                    let ha = getInt(a.HM) + (hasVal(a.Förl_H) ? getInt(a.Förl_H) : 0); let ba = getInt(a.BM) + (hasVal(a.Förl_B) ? getInt(a.Förl_B) : 0);
                    let hb = getInt(b.HM) + (hasVal(b.Förl_H) ? getInt(b.Förl_H) : 0); let bb = getInt(b.BM) + (hasVal(b.Förl_B) ? getInt(b.Förl_B) : 0);
                    return Math.abs(hb - bb) - Math.abs(ha - ba) || Math.max(hb, bb) - Math.max(ha, ba);
                }).slice(0, 10);
                safeSetHTML('rec-list-wins', buildRows(biggestWins, m => {
                    let h = getInt(m.HM) + (hasVal(m.Förl_H) ? getInt(m.Förl_H) : 0); let b = getInt(m.BM) + (hasVal(m.Förl_B) ? getInt(m.Förl_B) : 0); return `+${Math.abs(h-b)}`;
                }, 'mål'));

                if (team) {
                    let lossesData = validGoals.filter(m => {
                        let hm = getInt(m.HM) + (hasVal(m.Förl_H) ? getInt(m.Förl_H) : 0);
                        let bm = getInt(m.BM) + (hasVal(m.Förl_B) ? getInt(m.Förl_B) : 0);
                        return (m.Hemmalag === team && hm < bm) || (m.Bortalag === team && bm < hm);
                    });

                    let biggestLosses = [...lossesData].sort((a, b) => {
                        let ha = getInt(a.HM) + getInt(a.Förl_H); let ba = getInt(a.BM) + getInt(a.Förl_B);
                        let hb = getInt(b.HM) + getInt(b.Förl_H); let bb = getInt(b.BM) + getInt(b.Förl_B);
                        
                        let marginA = (a.Hemmalag === team ? ba - ha : ha - ba);
                        let marginB = (b.Hemmalag === team ? bb - hb : hb - bb);
                        
                        if (marginB !== marginA) return marginB - marginA;
                        return Math.max(hb, bb) - Math.max(ha, ba);
                    }).slice(0, 10);
                    
                    safeSetHTML('rec-list-losses', buildRows(biggestLosses, m => {
                        let h = getInt(m.HM) + getInt(m.Förl_H); let b = getInt(m.BM) + getInt(m.Förl_B);
                        let margin = (m.Hemmalag === team ? b - h : h - b);
                        return `-${margin}`;
                    }, 'mål'));
                }

                let mostGoals = [...validGoals].sort((a, b) => {
                    let ha = getInt(a.HM) + (hasVal(a.Förl_H) ? getInt(a.Förl_H) : 0); let ba = getInt(a.BM) + (hasVal(a.Förl_B) ? getInt(a.Förl_B) : 0);
                    let hb = getInt(b.HM) + (hasVal(b.Förl_H) ? getInt(b.Förl_H) : 0); let bb = getInt(b.BM) + (hasVal(b.Förl_B) ? getInt(b.Förl_B) : 0);
                    return (hb+bb) - (ha+ba);
                }).slice(0, 10);
                safeSetHTML('rec-list-goals', buildRows(mostGoals, m => {
                    let h = getInt(m.HM) + (hasVal(m.Förl_H) ? getInt(m.Förl_H) : 0); let b = getInt(m.BM) + (hasVal(m.Förl_B) ? getInt(m.Förl_B) : 0); return (h+b);
                }, 'mål'));

                let penData = teamData.filter(m => hasVal(m.Straff_H) && hasVal(m.Straff_B));
                let longestPens = [...penData].sort((a,b) => (getInt(b.Straff_H)+getInt(b.Straff_B)) - (getInt(a.Straff_H)+getInt(a.Straff_B))).slice(0,10);
                safeSetHTML('rec-list-penalties', buildRows(longestPens, m => (getInt(m.Straff_H)+getInt(m.Straff_B)), 'str.mål'));

                let validPublik = teamData.filter(m => hasVal(m.Publik));
                let highestAtt = [...validPublik].sort((a, b) => getInt(b.Publik) - getInt(a.Publik)).slice(0, 10);
                safeSetHTML('rec-list-att-high', buildRows(highestAtt, m => getInt(m.Publik).toLocaleString('sv-SE'), ''));
                let lowestAtt = [...validPublik].filter(m => getInt(m.Publik) > 10).sort((a, b) => getInt(a.Publik) - getInt(b.Publik)).slice(0, 10);
                safeSetHTML('rec-list-att-low', buildRows(lowestAtt, m => getInt(m.Publik).toLocaleString('sv-SE'), ''));
            } catch(e) { logError("renderRecords", e); }
        }

        // --- SVITER ---
        function calculateStreaks() {
            try {
                let elTeam = document.getElementById('streaks-team'); if(!elTeam) return;
                const teamFilter = elTeam.value; 
                let elCtx = document.querySelector('input[name="streak-context"]:checked');
                const context = elCtx ? elCtx.value : 'all';
                const fromStart = document.getElementById('streak-from-start') ? document.getElementById('streak-from-start').checked : false; 
                const sameSeason = document.getElementById('streak-same-season') ? document.getElementById('streak-same-season').checked : false;
                
                let teamsToProcess = teamFilter === "ALL" ? TEAMS : [teamFilter];
                let absoluteMax = { win: { len: 0, arr: [], team: "" }, unb: { len: 0, arr: [], team: "" }, loss: { len: 0, arr: [], team: "" }, winless: { len: 0, arr: [], team: "" }, cs: { len: 0, arr: [], team: "" }, ns: { len: 0, arr: [], team: "" }, adv: { len: 0, arr: [], team: "" } };
                
                globalAllStreaks = { win:[], unb:[], loss:[], winless:[], cs:[], ns:[], adv:[] };

                teamsToProcess.forEach(team => {
                    if (!team) return;
                    let matches = MATCH_DATA.filter(m => !isBye(m) && (m.Hemmalag === team || m.Bortalag === team));
                    if (context === 'home') matches = matches.filter(m => m.Hemmalag === team);
                    if (context === 'away') matches = matches.filter(m => m.Bortalag === team);
                    matches.sort((a, b) => {
                        let d1 = new Date(formatDate(a.Matchdatum, a.År)).getTime(); let d2 = new Date(formatDate(b.Matchdatum, b.År)).getTime();
                        if(isNaN(d1)) d1=0; if(isNaN(d2)) d2=0; if(d1!==d2) return d1-d2; return getInt(a.Match_ID) - getInt(b.Match_ID);
                    });

                    let max = { win:[], unb:[], loss:[], winless:[], cs:[], ns:[], adv:[] };
                    let cur = { win:[], unb:[], loss:[], winless:[], cs:[], ns:[], adv:[] };
                    let valid = { win:true, unb:true, loss:true, winless:true, cs:true, ns:true, adv:true }; 

                    const processMatch = (m) => {
                        const isHome = m.Hemmalag === team;
                        let notText = String(m.NOT).toUpperCase();
                        let isWOH = notText.includes("W.O; H") || notText.includes("AVBRUTEN; V") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                        let isWOB = notText.includes("W.O; B") || notText.includes("AVBRUTEN; F") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                        
                        let matchWon = false, matchLost = false, matchDrawn = false, advanced = false;
                        let gf = 0, ga = 0;
                        
                        let advCode = getAdvancingTeam(m);
                        if ((isHome && advCode === 1) || (!isHome && advCode === 2)) advanced = true;

                        if (isWOH) { if (isHome) {matchWon=true; advanced=true;} else {matchLost=true; advanced=false;} }
                        else if (isWOB) { if (!isHome) {matchWon=true; advanced=true;} else {matchLost=true; advanced=false;} }
                        else if (hasVal(m.HM) && hasVal(m.BM)) {
                            gf = isHome ? getInt(m.HM) : getInt(m.BM); ga = isHome ? getInt(m.BM) : getInt(m.HM);
                            if (hasVal(m.Förl_H)) { gf += (isHome ? getInt(m.Förl_H) : getInt(m.Förl_B)); ga += (isHome ? getInt(m.Förl_B) : getInt(m.Förl_H)); }
                            if (gf > ga) matchWon = true; else if (gf < ga) matchLost = true; else matchDrawn = true;
                        } else { return; }

                        const c = { win: matchWon, unb: matchWon || matchDrawn, loss: matchLost, winless: matchLost || matchDrawn, cs: ga === 0, ns: gf === 0, adv: advanced };
                        Object.keys(c).forEach(k => {
                            if (c[k]) { if (valid[k]) cur[k].push(m); } else {
                                if (cur[k].length > 0) globalAllStreaks[k].push({ team: team, len: cur[k].length, arr: [...cur[k]] });
                                if (cur[k].length > max[k].length) max[k] = [...cur[k]];
                                cur[k] = []; if (fromStart) valid[k] = false; 
                            }
                        });
                    };

                    let seasonMap = {}; matches.forEach(m => { if (!seasonMap[m.Säsong]) seasonMap[m.Säsong] = []; seasonMap[m.Säsong].push(m); });
                    if (sameSeason || fromStart) {
                        Object.values(seasonMap).forEach(sMatches => {
                            cur = { win:[], unb:[], loss:[], winless:[], cs:[], ns:[], adv:[] };
                            if (fromStart) valid = { win:true, unb:true, loss:true, winless:true, cs:true, ns:true, adv:true };
                            sMatches.forEach(processMatch);
                            Object.keys(cur).forEach(k => { 
                                if (cur[k].length > 0) globalAllStreaks[k].push({ team: team, len: cur[k].length, arr: [...cur[k]] });
                                if (cur[k].length > max[k].length) max[k] = [...cur[k]]; 
                            });
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
                    return `<div onclick="openStreakModal('${key}', '${title}', '${dataObj.team}')" class="bg-white p-4 rounded-lg border border-slate-200 shadow-sm text-center cursor-pointer hover:shadow-md hover:border-slate-300 transition-all group relative overflow-hidden flex flex-col justify-center"><div class="absolute inset-0 bg-${color.split('-')[1]}-50 opacity-0 group-hover:opacity-100 transition-opacity z-0"></div><div class="relative z-10"><div class="text-[10px] font-semibold uppercase tracking-wider mb-1 text-slate-500 group-hover:text-slate-800 transition-colors">${title}</div><div class="text-3xl font-black ${color}">${dataObj.len}</div>${teamLabel}</div></div>`;
                };

                let cardHTML = `
                    ${renderCard('Segrar (Spel)', absoluteMax.win, 'win', 'text-emerald-600')}
                    ${renderCard('Obesegrade', absoluteMax.unb, 'unb', 'text-emerald-500')}
                    ${renderCard('Avancemang', absoluteMax.adv, 'adv', 'text-indigo-600')}
                    ${renderCard('Förluster (Spel)', absoluteMax.loss, 'loss', 'text-rose-600')}
                    ${renderCard('Utan Seger', absoluteMax.winless, 'winless', 'text-orange-500')}
                    ${renderCard('Hållna Nollor', absoluteMax.cs, 'cs', 'text-blue-500')}
                    ${renderCard('Måltorka', absoluteMax.ns, 'ns', 'text-slate-400')}
                `;
                safeSetHTML('streaks-results', cardHTML);
                if(document.getElementById('streaks-placeholder')) document.getElementById('streaks-placeholder').classList.add('hidden');
                if(document.getElementById('streaks-results')) document.getElementById('streaks-results').classList.remove('hidden');
                renderStreakToplist();
            } catch(e) { logError("calculateStreaks", e); }
        }

        function renderStreakToplist() {
            try {
                let elType = document.getElementById('streak-toplist-type');
                const type = elType ? elType.value : "";
                if (!type || !globalAllStreaks[type]) { 
                    if(document.getElementById('streak-toplist-container')) document.getElementById('streak-toplist-container').classList.add('hidden'); 
                    return; 
                }
                
                let allOfType = globalAllStreaks[type];
                allOfType.sort((a, b) => b.len - a.len); 
                
                let uniqueStreaks = []; let seen = new Set();
                for (let s of allOfType) {
                    if (s.len === 0) continue;
                    let startM = s.arr[0]; let endM = s.arr[s.arr.length-1];
                    let key = `${s.team}_${startM.Match_ID}_${endM.Match_ID}`;
                    
                    let isSubset = false;
                    for (let u of uniqueStreaks) {
                        if (u.team === s.team && getInt(u.arr[0].Match_ID) <= getInt(startM.Match_ID) && getInt(u.arr[u.arr.length-1].Match_ID) >= getInt(endM.Match_ID)) {
                            isSubset = true; break;
                        }
                    }
                    
                    if (!seen.has(key) && !isSubset) {
                        seen.add(key);
                        let gf = 0, ga = 0;
                        s.arr.forEach(m => {
                            let mHm = getInt(m.HM); let mBm = getInt(m.BM);
                            let fH = hasVal(m.Förl_H) ? getInt(m.Förl_H) : 0; let fB = hasVal(m.Förl_B) ? getInt(m.Förl_B) : 0;
                            if (m.Hemmalag === s.team) { gf += (mHm+fH); ga += (mBm+fB); } else { gf += (mBm+fB); ga += (mHm+fH); }
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
                    return `<tr class="hover:bg-slate-50 cursor-pointer" onclick="openStreakModalFromToplist('${type}', ${i})"><td class="p-3 font-bold text-slate-500">${i+1}</td><td class="p-3 font-medium text-slate-800">${s.team}</td><td class="p-3 text-center font-bold text-indigo-600 text-lg">${s.len}</td><td class="p-3 text-xs text-slate-500">${startD} <span class="text-[10px] bg-slate-200 px-1 rounded ml-1">${s.arr[0].Säsong}</span></td><td class="p-3 text-xs text-slate-500">${endD} <span class="text-[10px] bg-slate-200 px-1 rounded ml-1">${s.arr[s.arr.length-1].Säsong}</span></td><td class="p-3 text-center font-bold font-mono ${gdColor}">${gdSign}${s.gd}</td></tr>`;
                }).join('');
                
                window._currentToplistMatches = uniqueStreaks;
                safeSetHTML('streak-toplist-body', html || '<tr><td colspan="6" class="p-6 text-center text-slate-500">Inga sviter hittades.</td></tr>');
                if(document.getElementById('streak-toplist-container')) document.getElementById('streak-toplist-container').classList.remove('hidden');
            } catch(e) { logError("renderStreakToplist", e); }
        }

        function openStreakModalFromToplist(type, index) {
            try {
                const streakObj = window._currentToplistMatches[index];
                const selectEl = document.getElementById('streak-toplist-type');
                const title = selectEl ? selectEl.options[selectEl.selectedIndex].text : "Svit";
                
                safeSetHTML('modal-title', `${title}: ${streakObj.team} (${streakObj.len} matcher)`);
                let html = '';
                streakObj.arr.forEach(m => {
                    let origH = m.Hemmalag_Org || m.Hemmalag;
                    let origB = m.Bortalag_Org || m.Bortalag;
                    let hClass = m.Hemmalag === streakObj.team ? 'font-bold text-slate-900' : ''; 
                    let aClass = m.Bortalag === streakObj.team ? 'font-bold text-slate-900' : '';
                    let displayDate = formatDate(m.Matchdatum, m.År);
                    html += `<tr class="border-b hover:bg-slate-50 transition-colors"><td class="p-3 text-slate-600">${m.Säsong}</td><td class="p-3 text-slate-500 text-xs">${m.Fas || '-'}</td><td class="p-3 text-slate-500 text-xs">${displayDate}</td><td class="p-3 text-right ${hClass}">${origH}</td><td class="p-3 text-center font-mono font-bold bg-slate-50 border-x border-slate-100">${getMatchResultText(m)}</td><td class="p-3 ${aClass}">${origB}</td></tr>`;
                });
                safeSetHTML('modal-tbody', html);
                if(document.getElementById('streak-modal')) document.getElementById('streak-modal').classList.remove('hidden');
            } catch(e) { logError("openStreakModalFromToplist", e); }
        }

        function openStreakModal(type, title, holderTeam) {
            try {
                const matches = currentStreakMatches[type] || [];
                safeSetHTML('modal-title', `${title}: ${holderTeam} (${matches.length} matcher i rad)`);
                let html = '';
                matches.forEach(m => {
                    let origH = m.Hemmalag_Org || m.Hemmalag;
                    let origB = m.Bortalag_Org || m.Bortalag;
                    let hClass = m.Hemmalag === holderTeam ? 'font-bold text-slate-900' : ''; let aClass = m.Bortalag === holderTeam ? 'font-bold text-slate-900' : '';
                    let displayDate = formatDate(m.Matchdatum, m.År);
                    html += `<tr class="border-b hover:bg-slate-50 transition-colors"><td class="p-3 text-slate-600">${m.Säsong}</td><td class="p-3 text-slate-500 text-xs">${m.Fas || '-'}</td><td class="p-3 text-slate-500 text-xs">${displayDate}</td><td class="p-3 text-right ${hClass}">${origH}</td><td class="p-3 text-center font-mono font-bold bg-slate-50 border-x border-slate-100">${getMatchResultText(m)}</td><td class="p-3 ${aClass}">${origB}</td></tr>`;
                });
                safeSetHTML('modal-tbody', html || '<tr><td colspan="6" class="p-6 text-center text-slate-500">Inga matcher att visa.</td></tr>');
                if(document.getElementById('streak-modal')) document.getElementById('streak-modal').classList.remove('hidden');
            } catch(e) { logError("openStreakModal", e); }
        }
        function closeStreakModal() { if(document.getElementById('streak-modal')) document.getElementById('streak-modal').classList.add('hidden'); }

        // --- DYNAMISK MARATONTABELL (Cupen) ---
        function renderDynamicAllTimeTable() {
            try {
                let elEpoch = document.getElementById('table-epoch'); const epochSelection = elEpoch ? elEpoch.value : "ALL";
                let elPhase = document.getElementById('table-phase'); const phaseSel = elPhase ? elPhase.value : "ALL";
                let elPts = document.getElementById('table-points'); const pointsForWin = elPts ? parseInt(elPts.value) || 3 : 3;
                let elMode = document.getElementById('table-mode'); const tableMode = elMode ? elMode.value : "120";
                
                let seasonsToInclude = []; let titleSuffix = "Totalt (Alla säsonger)";
                if (epochSelection === "ALL") { seasonsToInclude = SEASONS; } 
                else if (epochSelection.startsWith("EPOCH_CUSTOM_")) { let epochName = epochSelection.replace("EPOCH_CUSTOM_", ""); seasonsToInclude = CUSTOM_EPOCHS[epochName] || []; titleSuffix = `Egen Epok: ${epochName}`; } 
                else if (epochSelection.startsWith("EPOCH_DECADE_")) { let epochName = epochSelection.replace("EPOCH_DECADE_", ""); seasonsToInclude = DECADES[epochName] || []; titleSuffix = `Årtionde: ${epochName}`; }

                const seasonSet = new Set(seasonsToInclude.map(String));
                let matches = MATCH_DATA.filter(m => seasonSet.has(String(m.Säsong)) && !isBye(m));
                
                if (phaseSel === 'GRUPP') {
                    matches = matches.filter(m => { let c=getInt(m.Avancerade); return c===9 || c===10 || String(m.Fas).toLowerCase().includes("grupp"); });
                    titleSuffix += " - Enbart Gruppspel";
                } else if (phaseSel === 'SLUTSPEL') {
                    matches = matches.filter(m => { let c=getInt(m.Avancerade); return (c>=1 && c<=8 && !String(m.Fas).toLowerCase().includes("grupp")); });
                    titleSuffix += " - Enbart Slutspel/Utslagning";
                } else if (phaseSel === 'FINAL') {
                    matches = matches.filter(m => String(m.Fas).toLowerCase().includes("final") && !String(m.Fas).toLowerCase().includes("kvarts") && !String(m.Fas).toLowerCase().includes("semi"));
                    titleSuffix += " - Enbart Finaler";
                }

                if (matches.length === 0) { alert("Inga matcher hittades för vald filtrering."); return; }

                // Mode titles
                if (tableMode === '90') titleSuffix += " (Mål under 90 min)";
                else if (tableMode === 'FORL') titleSuffix += " (Enbart Förlängningar)";
                else if (tableMode === 'STR') titleSuffix += " (Enbart Straffläggningar)";

                safeSetHTML('table-title', `Maratontabell - ${titleSuffix} (${pointsForWin} poäng för seger)`);

                let table = {};
                let totalGoals = 0; let totalMatchesPlayed = 0;

                matches.forEach(m => {
                    if(!m.Hemmalag || !m.Bortalag) return;
                    let notText = String(m.NOT).toUpperCase();
                    let isWOH = notText.includes("W.O; H") || notText.includes("EJ KVALIFICERAD SPELARE; V");
                    let isWOB = notText.includes("W.O; B") || notText.includes("EJ KVALIFICERAD SPELARE; F");
                    
                    let hPts = 0, bPts = 0, hW = 0, hD = 0, hL = 0, bW = 0, bD = 0, bL = 0;
                    let hm = null, bm = null;
                    
                    if (tableMode === '120') {
                        if (isWOH || isWOB) { hm = isWOH ? 3:0; bm = isWOB ? 3:0; }
                        else if (hasVal(m.HM) && hasVal(m.BM)) {
                            hm = getInt(m.HM) + (hasVal(m.Förl_H) ? getInt(m.Förl_H) : 0);
                            bm = getInt(m.BM) + (hasVal(m.Förl_B) ? getInt(m.Förl_B) : 0);
                        }
                    } else if (tableMode === '90') {
                        if (isWOH || isWOB) { hm = isWOH ? 3:0; bm = isWOB ? 3:0; }
                        else if (hasVal(m.HM) && hasVal(m.BM)) { hm = getInt(m.HM); bm = getInt(m.BM); }
                    } else if (tableMode === 'FORL') {
                        if (hasVal(m.Förl_H) && hasVal(m.Förl_B)) { hm = getInt(m.Förl_H); bm = getInt(m.Förl_B); }
                    } else if (tableMode === 'STR') {
                        if (hasVal(m.Straff_H) && hasVal(m.Straff_B)) { hm = getInt(m.Straff_H); bm = getInt(m.Straff_B); }
                    }
                    
                    if (hm === null || bm === null) return; 

                    [m.Hemmalag, m.Bortalag].forEach(t => {
                        if(!table[t]) table[t] = { team: t, pld:0, w:0, d:0, l:0, gf:0, ga:0, gd:0, pts:0, seasons: new Set() };
                    });

                    if (isWOH && tableMode !== 'FORL' && tableMode !== 'STR') { hPts = pointsForWin; hW = 1; bL = 1; }
                    else if (isWOB && tableMode !== 'FORL' && tableMode !== 'STR') { bPts = pointsForWin; bW = 1; hL = 1; }
                    else {
                        if (hm > bm) { hPts = pointsForWin; hW = 1; bL = 1; } 
                        else if (hm < bm) { bPts = pointsForWin; bW = 1; hL = 1; } 
                        else { hPts = 1; bPts = 1; hD = 1; bD = 1; } 
                    }

                    table[m.Hemmalag].pld++; table[m.Hemmalag].gf += hm; table[m.Hemmalag].ga += bm;
                    table[m.Hemmalag].w += hW; table[m.Hemmalag].d += hD; table[m.Hemmalag].l += hL; table[m.Hemmalag].pts += hPts; table[m.Hemmalag].seasons.add(m.Säsong);
                    
                    table[m.Bortalag].pld++; table[m.Bortalag].gf += bm; table[m.Bortalag].ga += hm;
                    table[m.Bortalag].w += bW; table[m.Bortalag].d += bD; table[m.Bortalag].l += bL; table[m.Bortalag].pts += bPts; table[m.Bortalag].seasons.add(m.Säsong);

                    totalGoals += (hm + bm);
                    totalMatchesPlayed++;
                });

                let arr = Object.values(table).filter(r => r.pld > 0);
                arr.forEach(r => { r.gd = r.gf - r.ga; });
                arr.sort((a, b) => b.pts - a.pts || b.gd - a.gd || b.gf - a.gf);
                
                safeSetHTML('league-table-head', `
                    <tr><th class="px-4 py-3 w-10">Plac</th><th class="px-4 py-3">Lag</th><th class="px-4 py-3 text-center bg-slate-50">Säsonger</th><th class="px-4 py-3 text-center">Sp</th><th class="px-4 py-3 text-center">V</th><th class="px-4 py-3 text-center">O</th><th class="px-4 py-3 text-center">F</th><th class="px-4 py-3 text-center">GM-IM</th><th class="px-4 py-3 text-center">+/-</th><th class="px-4 py-3 text-center font-bold text-indigo-700">P</th></tr>
                `);

                let html = arr.map((r, i) => `
                    <tr class="hover:bg-slate-50"><td class="px-4 py-2 font-bold text-slate-500">${i+1}</td><td class="px-4 py-2 font-medium text-slate-800">${r.team}</td><td class="px-4 py-2 text-center bg-slate-50 font-bold text-slate-600">${r.seasons.size}</td><td class="px-4 py-2 text-center">${r.pld}</td><td class="px-4 py-2 text-center text-emerald-600">${r.w}</td><td class="px-4 py-2 text-center text-slate-500">${r.d}</td><td class="px-4 py-2 text-center text-rose-600">${r.l}</td><td class="px-4 py-2 text-center">${r.gf} - ${r.ga}</td><td class="px-4 py-2 text-center font-bold ${r.gd > 0 ? 'text-emerald-600' : r.gd < 0 ? 'text-rose-600' : ''}">${r.gd > 0 ? '+'+r.gd : r.gd}</td><td class="px-4 py-2 text-center font-black bg-indigo-50/80 text-indigo-800">${r.pts}</td></tr>
                `).join('');

                let goalAvg = totalMatchesPlayed > 0 ? (totalGoals / totalMatchesPlayed).toFixed(2) : "0.00";
                safeSetHTML('table-goal-stats', `${totalMatchesPlayed} matcher | ${totalGoals} Mål (${goalAvg} per match i snitt)`);
                if(document.getElementById('table-goal-stats')) document.getElementById('table-goal-stats').classList.remove('hidden');

                safeSetHTML('league-table-body', html || '<tr><td colspan="10" class="text-center py-6 text-slate-500">Inga matcher hittades.</td></tr>');
                if(document.getElementById('table-results')) document.getElementById('table-results').classList.remove('hidden');
            } catch(e) { logError("renderDynamicAllTimeTable", e); }
        }

        // --- CUP-TRÄD (BRACKET) ---
        function renderBracket() {
            try {
                let elSeason = document.getElementById('bracket-season');
                const season = elSeason ? elSeason.value : "";
                if(!season) return;
                
                let sMatches = MATCH_DATA.filter(m => String(m.Säsong) === String(season) && !isBye(m));
                if(sMatches.length === 0) { alert("Inga data för säsongen."); return; }
                
                safeSetHTML('bracket-season-label', season);
                
                let winner = "Okänd Mästare";
                let finalMatch = sMatches.find(m => getInt(m.Avancerade) === 5 || getInt(m.Avancerade) === 6);
                if (finalMatch) {
                    winner = (getInt(finalMatch.Avancerade) === 5) ? (finalMatch.Hemmalag_Org || finalMatch.Hemmalag) : (finalMatch.Bortalag_Org || finalMatch.Bortalag);
                } else {
                    let fbMatch = sMatches.find(m => String(m.Fas).toLowerCase().includes('final') && !String(m.Fas).toLowerCase().includes('kvart') && !String(m.Fas).toLowerCase().includes('semi'));
                    if(fbMatch) {
                        let adv = getAdvancingTeam(fbMatch);
                        if(adv===1) winner = fbMatch.Hemmalag_Org || fbMatch.Hemmalag;
                        else if(adv===2) winner = fbMatch.Bortalag_Org || fbMatch.Bortalag;
                    }
                }
                safeSetHTML('bracket-winner', winner);

                let stages = {};
                sMatches.forEach(m => {
                    let fLow = String(m.Fas).toLowerCase();
                    if (fLow.includes("kvart") || fLow.includes("semi") || fLow.includes("åtton") || fLow.includes("1/8") || (fLow.includes("final") && !fLow.includes("kvart") && !fLow.includes("semi") && !fLow.includes("åtton"))) {
                        let groupName = "Övrigt";
                        if(fLow.includes("åtton") || fLow.includes("1/8")) groupName = "Åttondelsfinaler";
                        else if(fLow.includes("kvart")) groupName = "Kvartsfinaler";
                        else if(fLow.includes("semi")) groupName = "Semifinaler";
                        else if(fLow.includes("final")) groupName = "Final";
                        
                        if(!stages[groupName]) stages[groupName] = [];
                        stages[groupName].push(m);
                    }
                });

                let html = "";
                ['Åttondelsfinaler', 'Kvartsfinaler', 'Semifinaler', 'Final'].forEach(stageName => {
                    if (stages[stageName] && stages[stageName].length > 0) {
                        html += `<div class="mb-6"><h4 class="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 pb-1 border-b border-slate-100">${stageName}</h4><div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">`;
                        
                        stages[stageName].forEach(m => {
                            let origH = m.Hemmalag_Org || m.Hemmalag; let origB = m.Bortalag_Org || m.Bortalag;
                            let adv = getAdvancingTeam(m);
                            if (getInt(m.Avancerade) === 8) adv = 0; 
                            
                            let hBold = adv === 1 ? 'font-bold text-indigo-700' : 'text-slate-600';
                            let bBold = adv === 2 ? 'font-bold text-indigo-700' : 'text-slate-600';
                            
                            let date = formatDate(m.Matchdatum, m.År);
                            let res = getMatchResultText(m);
                            
                            html += `<div class="bg-slate-50 border border-slate-200 rounded p-2 text-sm shadow-sm flex flex-col justify-between"><div class="flex justify-between items-center mb-1"><span class="${hBold} truncate" title="${origH}">${origH}</span><span class="text-[10px] text-slate-400 bg-white px-1 border border-slate-100 rounded">${m.Serie_H||'?'}</span></div><div class="flex justify-between items-center"><span class="${bBold} truncate" title="${origB}">${origB}</span><span class="text-[10px] text-slate-400 bg-white px-1 border border-slate-100 rounded">${m.Serie_B||'?'}</span></div><div class="mt-2 pt-1 border-t border-slate-200 flex justify-between items-center text-xs"><span class="text-slate-400">${date}</span><span class="font-mono font-bold bg-indigo-50 text-indigo-800 px-1 rounded">${res}</span></div></div>`;
                        });
                        
                        html += `</div></div>`;
                    }
                });

                safeSetHTML('bracket-stages', html || "<div class='text-center text-slate-500 py-4'>Kunde inte hitta några slutspelsmatcher för denna säsong.</div>");
                if(document.getElementById('bracket-results')) document.getElementById('bracket-results').classList.remove('hidden');
            } catch(e) { logError("renderBracket", e); }
        }

        // --- SKRÄLLARNA ---
        function renderUpsets(filterType) {
            try {
                let upsets = [];
                MATCH_DATA.forEach(m => {
                    if(isBye(m)) return;
                    let adv = getAdvancingTeam(m);
                    if (adv === 0) return; 
                    
                    let nH = getInt(m.Nivå_H); let nB = getInt(m.Nivå_B);
                    if (nH === 99 || nB === 99 || nH === 0 || nB === 0) return; 
                    
                    let diff = 0; let skrallTeam = "", forlorare = "";
                    let sNiva = 0, fNiva = 0; let sSerie = "", fSerie = "";
                    
                    if (adv === 1) { 
                        if (nH > nB) { 
                            diff = nH - nB; skrallTeam = m.Hemmalag_Org || m.Hemmalag; forlorare = m.Bortalag_Org || m.Bortalag;
                            sNiva = nH; fNiva = nB; sSerie = m.Serie_H; fSerie = m.Serie_B;
                        }
                    } else if (adv === 2) { 
                        if (nB > nH) { 
                            diff = nB - nH; skrallTeam = m.Bortalag_Org || m.Bortalag; forlorare = m.Hemmalag_Org || m.Hemmalag;
                            sNiva = nB; fNiva = nH; sSerie = m.Serie_B; fSerie = m.Serie_H;
                        }
                    }
                    
                    if (diff > 0) {
                        upsets.push({...m, diff: diff, skrallTeam: skrallTeam, forlorare: forlorare, sNiva: sNiva, fNiva: fNiva, sSerie: sSerie, fSerie: fSerie});
                    }
                });
                
                if (filterType === 3) upsets = upsets.filter(u => u.diff >= 3);
                else if (filterType === 'final') upsets = upsets.filter(u => String(u.Fas).toLowerCase().includes("final") || String(u.Fas).toLowerCase().includes("semi"));
                
                upsets.sort((a,b) => b.diff - a.diff || getInt(a.Match_ID) - getInt(b.Match_ID));
                
                let html = upsets.map(u => {
                    let res = getMatchResultText(u);
                    let fas = u.Fas ? `<div class="text-[10px] text-slate-400">${u.Fas}</div>` : '';
                    return `<tr class="hover:bg-slate-50"><td class="px-4 py-3"><div class="font-medium text-slate-700">${u.Säsong}</div>${fas}</td><td class="px-4 py-3"><div class="font-bold text-slate-900">${u.skrallTeam} <span class="text-slate-500 font-normal">(${u.sSerie})</span></div><div class="text-xs text-pink-600 bg-pink-50 inline-block px-1 rounded">Nivå ${u.sNiva}</div></td><td class="px-4 py-3 text-center"><span class="font-mono font-bold bg-slate-100 px-2 py-1 rounded border border-slate-200">${res}</span></td><td class="px-4 py-3"><div class="font-medium text-slate-600">${u.forlorare} <span class="text-slate-400 font-normal">(${u.fSerie})</span></div><div class="text-xs text-slate-400 bg-slate-50 inline-block px-1 rounded border border-slate-100">Nivå ${u.fNiva}</div></td><td class="px-4 py-3 text-center font-black text-pink-600 text-xl">+${u.diff}</td></tr>`;
                }).join('');
                
                safeSetHTML('upsets-table-body', html || '<tr><td colspan="5" class="text-center py-8 text-slate-500">Inga skrällar hittades för det valda filtret.</td></tr>');
            } catch(e) { logError("renderUpsets", e); }
        }

        // --- DATAKONTROLL (ADMIN) ---
        function runDataCheck() {
            try {
                let unmapped = new Set();
                let teamSeries = {};
                let teamNamesMap = {};
                
                MATCH_DATA.forEach(m => {
                    if(isBye(m)) return;
                    
                    let origH = m.Hemmalag_Org; let origB = m.Bortalag_Org;
                    
                    if(origH && !TEAM_MAPPING[origH] && !Object.values(TEAM_MAPPING).includes(origH)) unmapped.add(origH);
                    if(origB && !TEAM_MAPPING[origB] && !Object.values(TEAM_MAPPING).includes(origB)) unmapped.add(origB);
                    
                    let kH = `${m.Säsong}_${m.Hemmalag}`;
                    if(!teamSeries[kH]) teamSeries[kH] = new Set();
                    if(m.Serie_H) teamSeries[kH].add(m.Serie_H);
                    
                    let kB = `${m.Säsong}_${m.Bortalag}`;
                    if(!teamSeries[kB]) teamSeries[kB] = new Set();
                    if(m.Serie_B) teamSeries[kB].add(m.Serie_B);

                    if (m.Hemmalag && origH) {
                        if (!teamNamesMap[m.Hemmalag]) teamNamesMap[m.Hemmalag] = new Set();
                        teamNamesMap[m.Hemmalag].add(origH);
                    }
                    if (m.Bortalag && origB) {
                        if (!teamNamesMap[m.Bortalag]) teamNamesMap[m.Bortalag] = new Set();
                        teamNamesMap[m.Bortalag].add(origB);
                    }
                });
                
                let unmappedHTML = "";
                Array.from(unmapped).sort().forEach(t => unmappedHTML += `<li>${t}</li>`);
                safeSetHTML('admin-unmapped', unmappedHTML || "<li class='text-emerald-600 font-medium'>Inga o-mappade lag hittades!</li>");
                
                let seriesHTML = "";
                Object.keys(teamSeries).forEach(k => {
                    if(teamSeries[k].size > 1) {
                        let parts = k.split('_');
                        seriesHTML += `<li><b>${parts[1]}</b> (${parts[0]}): Registrerad med serierna [ ${Array.from(teamSeries[k]).join(', ')} ]</li>`;
                    }
                });
                safeSetHTML('admin-series', seriesHTML || "<li class='text-emerald-600 font-medium'>Inga serie-inkonsekvenser hittades!</li>");
                
                let aliasHTML = "";
                Object.keys(teamNamesMap).sort().forEach(t => {
                    if(teamNamesMap[t].size > 1) {
                        aliasHTML += `<li><b>${t}</b> har spelat under namnen: [ ${Array.from(teamNamesMap[t]).join(', ')} ]</li>`;
                    }
                });
                safeSetHTML('admin-aliases', aliasHTML || "<li class='text-emerald-600 font-medium'>Inga lag med flera namn hittades.</li>");

                if(document.getElementById('admin-results')) document.getElementById('admin-results').classList.remove('hidden');
            } catch(e) { logError("runDataCheck", e); }
        }

    </script>
</body>
</html>
"""

final_html = html_template.replace("%%MATCH_DATA_JSON%%", json_match_data) \
    .replace("%%TEAMS_JSON%%", json_teams_data) \
    .replace("%%SEASONS_JSON%%", json_seasons_data) \
    .replace("%%DECADES_JSON%%", json_decades_data) \
    .replace("%%CUSTOM_EPOCHS_JSON%%", json_custom_epochs_data) \
    .replace("%%TEAM_MAPPING_JSON%%", json_team_mapping) \
    .replace("%%PHASES_JSON%%", json_phases) \
    .replace("%%PY_LOGS_JSON%%", json_py_logs)

output_file = os.path.join(main_folder, "Matchanalys_SvenskaCupen_Dashboard.html")
with open(output_file, "w", encoding="utf-8") as f:
    f.write(final_html)

dlog(f"SUCCÉ! Filen '{output_file}' har skapats.")