import os
import pandas as pd
import numpy as np
import json

# ==========================================
# 1. ANVÄNDARINSTÄLLNINGAR FÖR VYER
# ==========================================
# Ange år för en pågående/kommande säsong (t.ex. 2026) som ska döljas från 
# Maratontabell, Serietabeller och Topplistor tills den är färdigspelad.
# Den påverkar dock färgmarkeringar (upp/ned) och Serievandringar.
# Sätt till None om ingen säsong ska döljas.
PAGAENDE_SASONG = 2026

# ==========================================
# 2. GENERELL SETUP OCH DATA-LADDNING
# ==========================================
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
except NameError:
    project_root = os.getcwd()
    pass 

def find_target_file(keyword, search_root):
    for root, dirs, files in os.walk(search_root):
        for filename in files:
            if keyword.lower() in filename.lower() and filename.lower().endswith(".xlsx") and not filename.startswith("~$"):
                return os.path.join(root, filename)
    return None

def fix_text(text):
    encoding_fix = {
        'Ã¥': 'å', 'Ã¤': 'ä', 'Ã¶': 'ö', 'Ã…': 'Å', 'Ã„': 'Ä', 'Ã–': 'Ö',
        'Ã©': 'é', 'Ã¨': 'è', 'Ã‰': 'É', "Ã\x85": "Å", "Ã\x90": "Ä", "Ã\x96": "Ö"
    }
    if not isinstance(text, str): return text
    for bad, good in encoding_fix.items():
        text = text.replace(bad, good)
    return text.strip()

def clean_dataframe(df):
    if df is None: return None
    str_cols = df.select_dtypes(include=['object']).columns
    for col in str_cols:
        df[col] = df[col].apply(fix_text)
    return df

def get_master_data():
    excel_path = find_target_file("Serietabellerna_samlade", project_root)
    if not excel_path:
        print("FEL: Hittade inte filen Serietabellerna_samlade.")
        return None, None, None
        
    print(f"Laddar databasen från: {os.path.basename(excel_path)}...")
    excel_dict = pd.read_excel(excel_path, sheet_name=None, engine='openpyxl')
    
    df_tabeller = clean_dataframe(excel_dict.get('Tabeller'))
    df_lag_nr = clean_dataframe(excel_dict.get('Lag_nr'))
    df_lag_id = clean_dataframe(excel_dict.get('Lag_id'))
    df_serieniva = clean_dataframe(excel_dict.get('Serienivå'))
    df_snabbval = clean_dataframe(excel_dict.get('Snabbval')) # Ny flik!
    
    if df_tabeller is not None:
        df_tabeller = df_tabeller.rename(columns={'Lag': 'Laget i tabell'}) 
    
    master = pd.merge(df_tabeller, df_lag_nr[['Laget', 'Lag_ID']], left_on='Laget i tabell', right_on='Laget', how='left')
    master = pd.merge(master, df_lag_id[['Lag_ID', 'Lag', 'Distrikt', 'Kommun']], on='Lag_ID', how='left').rename(columns={'Lag': 'Standard_Lagnamn'})
    master = pd.merge(master, df_serieniva[['Säsnr', 'Poäng_seger']], on='Säsnr', how='left')
    
    master['Analys_Lagnamn'] = master['Standard_Lagnamn'].fillna(master['Laget i tabell'])
    master['Startår_Numerisk'] = master['Säsong'].astype(str).str.extract(r'^(\d{4})').astype(float)
    
    if 'Poängjustering_Startpoäng' in master.columns:
        master['Poängjustering_Startpoäng'] = pd.to_numeric(master['Poängjustering_Startpoäng'], errors='coerce').fillna(0)
        master['Giltig_Poängavdrag'] = master['Poängjustering_Startpoäng'].apply(lambda x: x if x < 0 else 0)
    else:
        master['Giltig_Poängavdrag'] = 0
        master['Poängjustering_Startpoäng'] = 0

    for col in ['Sp', 'V', 'O', 'F', 'Gjorda', 'Insl', 'P']:
        master[col] = pd.to_numeric(master[col], errors='coerce').fillna(0)

    master['Målskillnad'] = master['Gjorda'] - master['Insl']
    
    return master, df_tabeller, df_snabbval

# ==========================================
# 3. HTML DASHBOARD GENERATOR (FLIKAR)
# ==========================================
def export_html_dashboard(df, df_snabbval):
    print("\nSkapar interaktiv flik-baserad HTML-dashboard...")
    
    export_cols = [
        'Startår_Numerisk', 'Säsong', 'Säsnr', 'Nivå', 'Division', 'Serie', 'Plac', 
        'Analys_Lagnamn', 'Sp', 'V', 'O', 'F', 'Gjorda', 'Insl', 'P',
        'Giltig_Poängavdrag', 'Poängjustering_Startpoäng', 'Lag_ID', 'Laget i tabell', 'Standard_Lagnamn'
    ]
    available_cols = [c for c in export_cols if c in df.columns]
    df_export = df[available_cols].copy()
    
    df_export = df_export.fillna('')
    df_export['Nivå'] = pd.to_numeric(df_export['Nivå'], errors='coerce').fillna(0).astype(int)
    
    df_export = df_export[(df_export['Nivå'] > 0) & (df_export['Nivå'] <= 5)]
    
    json_data = df_export.to_json(orient='records').replace('</script>', '<\/script>')
    
    # Hantera Snabbval-fliken
    if df_snabbval is not None and not df_snabbval.empty:
        json_snabbval = df_snabbval.to_json(orient='records').replace('</script>', '<\/script>')
    else:
        json_snabbval = "[]"
    
    orphans = df_export[df_export['Lag_ID'] == '']['Laget i tabell'].unique().tolist()
    
    name_changes = []
    valid_teams = df_export[df_export['Lag_ID'] != '']
    grouped_teams = valid_teams.groupby('Analys_Lagnamn')
    
    for std_name, group in grouped_teams:
        aliases = group['Laget i tabell'].unique()
        if len(aliases) > 1:
            alias_info = []
            for alias in aliases:
                alias_rows = group[group['Laget i tabell'] == alias]
                if not alias_rows.empty:
                    min_year = int(alias_rows['Startår_Numerisk'].min())
                    max_year = int(alias_rows['Startår_Numerisk'].max())
                    if min_year == max_year:
                        alias_info.append(f"{alias} ({min_year})")
                    else:
                        alias_info.append(f"{alias} ({min_year}-{max_year})")
                else:
                    alias_info.append(alias)
            name_changes.append({"standard": std_name, "aliases": alias_info})
            
    admin_stats = {
        "total_rows": len(df_export),
        "unique_teams": df_export['Analys_Lagnamn'].nunique(),
        "orphans_count": len(orphans),
        "orphans_list": orphans,
        "name_changes": sorted(name_changes, key=lambda x: x['standard'])
    }
    json_admin = json.dumps(admin_stats)

    html_template = """<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Svensk Fotbollshistoria - Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #f3f4f6; font-family: ui-sans-serif, system-ui, sans-serif; }
        th { position: sticky; top: 0; background-color: #e5e7eb; z-index: 10; }
        .table-container { max-height: 60vh; overflow-y: auto; }
        .tab-btn.active { border-bottom: 2px solid #2563eb; color: #2563eb; font-weight: 600; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .row-promoted { background-color: #f0fdf4 !important; }
        .row-promoted:hover { background-color: #dcfce7 !important; }
        .row-relegated { background-color: #fef2f2 !important; }
        .row-relegated:hover { background-color: #fee2e2 !important; }
        select:disabled { background-color: #f3f4f6; color: #9ca3af; }
    </style>
</head>
<body class="p-4 md:p-6">

    <div class="max-w-7xl mx-auto bg-white rounded-xl shadow-lg p-6">
        <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-4">
            <h1 class="text-3xl font-bold text-gray-800">Svensk Fotbollshistoria</h1>
            <button onclick="exportCSV()" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded shadow flex items-center">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                Ladda ner CSV
            </button>
        </div>

        <!-- Flik-navigering -->
        <div class="flex overflow-x-auto border-b border-gray-200 mb-6 pb-1 space-x-1">
            <button class="tab-btn active px-4 py-2 text-gray-600 hover:text-blue-600 focus:outline-none whitespace-nowrap" onclick="switchTab('tab-maraton', this)">Maratontabeller</button>
            <button class="tab-btn px-4 py-2 text-gray-600 hover:text-blue-600 focus:outline-none whitespace-nowrap" onclick="switchTab('tab-sasong', this)">Serietabeller</button>
            <button class="tab-btn px-4 py-2 text-gray-600 hover:text-blue-600 focus:outline-none whitespace-nowrap" onclick="switchTab('tab-vandring', this)">Serievandringar</button>
            <button class="tab-btn px-4 py-2 text-gray-600 hover:text-blue-600 focus:outline-none whitespace-nowrap" onclick="switchTab('tab-topp', this)">Topplistor</button>
            <button class="tab-btn px-4 py-2 text-gray-600 hover:text-blue-600 focus:outline-none whitespace-nowrap" onclick="switchTab('tab-admin', this)">Administration</button>
        </div>

        <!-- ============================================== -->
        <!-- FLIK 1: MARATONTABELL                          -->
        <!-- ============================================== -->
        <div id="tab-maraton" class="tab-content active">
            <div class="grid grid-cols-1 md:grid-cols-6 gap-4 mb-4 bg-gray-50 p-4 rounded-lg border border-gray-200 items-end">
                <div class="md:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Sök Lag</label>
                    <input type="text" id="maratonSearch" placeholder="Skriv för att söka..." class="w-full border-gray-300 rounded-md p-2 border" onkeyup="renderMaraton()">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Poängsystem</label>
                    <select id="maratonPointsMode" class="w-full border-gray-300 rounded-md p-2 border" onchange="renderMaraton()">
                        <option value="3">3 poäng för seger</option>
                        <option value="2">2 poäng för seger</option>
                        <option value="hist">Historiska poäng (P)</option>
                    </select>
                </div>
                <div class="md:col-span-2">
                    <label class="block text-sm font-medium text-blue-700 mb-1">Snabbval (Färdiga Maraton)</label>
                    <select id="maratonSnabbval" class="w-full border-blue-300 bg-blue-50 text-blue-900 font-medium rounded-md p-2 border" onchange="toggleSnabbval()">
                        <option value="Inget">-- Använd egna filter --</option>
                    </select>
                </div>
                <div>
                    <button class="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded border border-gray-300 transition-colors" onclick="resetFilters('maraton')">
                        Återställ
                    </button>
                </div>
                
                <!-- Egna filter (Spärras när Snabbval är valt) -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Startår</label>
                    <select id="maratonStartYear" class="w-full border-gray-300 rounded-md p-2 border custom-filter" onchange="renderMaraton()"></select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Slutår</label>
                    <select id="maratonEndYear" class="w-full border-gray-300 rounded-md p-2 border custom-filter" onchange="renderMaraton()"></select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Serienivå</label>
                    <select id="maratonLevel" class="w-full border-gray-300 rounded-md p-2 border custom-filter" onchange="syncDropdowns('maratonLevel', 'maratonDivision', 'levelToDiv'); renderMaraton()">
                        <option value="Alla">-- Alla Nivåer --</option>
                        <option value="1">Nivå 1</option>
                        <option value="2">Nivå 2</option>
                        <option value="3">Nivå 3</option>
                        <option value="4">Nivå 4</option>
                        <option value="5">Nivå 5</option>
                    </select>
                </div>
                <div class="md:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Seriebeteckning (Division)</label>
                    <select id="maratonDivision" class="w-full border-gray-300 rounded-md p-2 border custom-filter" onchange="syncDropdowns('maratonDivision', 'maratonLevel', 'divToLevel'); renderMaraton()">
                        <option value="Alla">-- Alla Beteckningar --</option>
                    </select>
                </div>
            </div>
            <div class="text-sm text-gray-500 mb-2 flex justify-between">
                <span id="maratonCounter"></span>
                <span class="italic text-xs">Tips: Klicka på ett lag för att se deras tabeller.</span>
            </div>
            <div class="table-container border border-gray-200 rounded-lg">
                <table class="min-w-full text-sm text-left whitespace-nowrap" id="maratonTable">
                    <thead class="text-xs text-gray-700 uppercase bg-gray-100" id="maratonHead"></thead>
                    <tbody class="divide-y divide-gray-200" id="maratonBody"></tbody>
                </table>
            </div>
        </div>

        <!-- ============================================== -->
        <!-- FLIK 2: SERIETABELLER (SÄSONG)                 -->
        <!-- ============================================== -->
        <div id="tab-sasong" class="tab-content">
            <div class="grid grid-cols-1 md:grid-cols-6 gap-4 mb-2 bg-gray-50 p-4 rounded-lg border border-gray-200 items-end">
                <div class="md:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Välj Säsong</label>
                    <select id="sasongYear" class="w-full border-gray-300 rounded-md p-2 border font-medium" onchange="renderSasong()">
                        <option value="Alla">-- Alla Säsonger --</option>
                    </select>
                </div>
                <div class="md:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Specifikt Lag (Följ historik)</label>
                    <select id="sasongTeam" class="w-full border-gray-300 rounded-md p-2 border" onchange="handleTeamSelect()">
                        <option value="Alla">-- Alla Lag --</option>
                    </select>
                </div>
                <div class="md:col-span-2 flex justify-end">
                    <button class="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded border border-gray-300 transition-colors" onclick="resetFilters('sasong')">
                        Återställ & Rensa Allt
                    </button>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Filtrera på Nivå</label>
                    <select id="sasongLevel" class="w-full border-gray-300 rounded-md p-2 border" onchange="syncDropdowns('sasongLevel', 'sasongDivision', 'levelToDiv'); renderSasong()">
                        <option value="Alla">-- Alla Nivåer --</option>
                        <option value="1">Nivå 1</option><option value="2">Nivå 2</option>
                        <option value="3">Nivå 3</option><option value="4">Nivå 4</option><option value="5">Nivå 5</option>
                    </select>
                </div>
                <div class="md:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Filtrera på Seriebeteckning</label>
                    <select id="sasongDivision" class="w-full border-gray-300 rounded-md p-2 border" onchange="syncDropdowns('sasongDivision', 'sasongLevel', 'divToLevel'); renderSasong()">
                        <option value="Alla">-- Alla Beteckningar --</option>
                    </select>
                </div>
            </div>
            
            <div class="flex justify-between items-end mb-2">
                <div class="text-sm text-gray-500" id="sasongCounter"></div>
                <div class="text-xs text-gray-500 flex gap-4">
                    <span class="flex items-center"><span class="w-3 h-3 rounded bg-green-100 border border-green-200 inline-block mr-1"></span> Uppflyttad / SM-Guld</span>
                    <span class="flex items-center"><span class="w-3 h-3 rounded bg-red-100 border border-red-200 inline-block mr-1"></span> Degraderad året efter</span>
                </div>
            </div>

            <div class="table-container border border-gray-200 rounded-lg">
                <table class="min-w-full text-sm text-left whitespace-nowrap" id="sasongTable">
                    <thead class="text-xs text-gray-700 uppercase bg-gray-100" id="sasongHead"></thead>
                    <tbody class="divide-y divide-gray-200" id="sasongBody"></tbody>
                </table>
            </div>
        </div>

        <!-- ============================================== -->
        <!-- FLIK 3: SERIEVANDRINGAR                        -->
        <!-- ============================================== -->
        <div id="tab-vandring" class="tab-content">
            <div class="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4 bg-gray-50 p-4 rounded-lg border border-gray-200 items-end">
                <div class="md:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Sök Lag</label>
                    <input type="text" id="vandringSearch" placeholder="Skriv för att söka..." class="w-full border-gray-300 rounded-md p-2 border" onkeyup="renderVandringar()">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Fokusera på</label>
                    <select id="vandringMode" class="w-full border-gray-300 rounded-md p-2 border" onchange="toggleVandringMode()">
                        <option value="niva">Serienivå (Fast trappsteg)</option>
                        <option value="division">Seriebeteckning (Historiskt namn)</option>
                    </select>
                </div>
                <div id="vandringLevelWrapper">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Välj Serienivå</label>
                    <select id="vandringLevel" class="w-full border-gray-300 rounded-md p-2 border" onchange="renderVandringar()">
                        <option value="1">Nivå 1 (Allsvenskan etc)</option>
                        <option value="2">Nivå 2</option>
                        <option value="3">Nivå 3</option>
                        <option value="4">Nivå 4</option>
                        <option value="5">Nivå 5</option>
                    </select>
                </div>
                <div id="vandringDivisionWrapper" class="hidden">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Välj Seriebeteckning</label>
                    <select id="vandringDivision" class="w-full border-gray-300 rounded-md p-2 border" onchange="renderVandringar()"></select>
                </div>
                <div>
                    <button class="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded border border-gray-300 transition-colors" onclick="resetFilters('vandring')">
                        Återställ
                    </button>
                </div>
            </div>
            
            <div class="text-sm text-gray-500 mb-2 flex justify-between">
                <span id="vandringCounter">Beräknar sviter och vandringar...</span>
                <span class="italic text-xs">Tips: Klicka på ett lag för att se alla deras tabeller för denna nivå/beteckning.</span>
            </div>
            <div class="table-container border border-gray-200 rounded-lg">
                <table class="min-w-full text-sm text-left whitespace-nowrap" id="vandringTable">
                    <thead class="text-xs text-gray-700 uppercase bg-gray-100" id="vandringHead"></thead>
                    <tbody class="divide-y divide-gray-200" id="vandringBody"></tbody>
                </table>
            </div>
        </div>

        <!-- ============================================== -->
        <!-- FLIK 4: TOPPLISTOR                             -->
        <!-- ============================================== -->
        <div id="tab-topp" class="tab-content">
            <div class="grid grid-cols-1 md:grid-cols-6 gap-4 mb-4 bg-gray-50 p-4 rounded-lg border border-gray-200 items-end">
                <div class="md:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Analyskategori</label>
                    <select id="toppCategory" class="w-full border-gray-300 rounded-md p-2 border bg-white font-semibold" onchange="updateToppMetrics()">
                        <option value="sasong">Bästa/Sämsta enskilda säsong</option>
                        <option value="maraton">Maratontotalt (Hela historiken)</option>
                        <option value="vandring">Serievandringar & Jojolag</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Mätvärdestyp</label>
                    <select id="toppMetricType" class="w-full border-gray-300 rounded-md p-2 border bg-white" onchange="updateToppMetrics()">
                        <option value="abs">Absoluta tal</option>
                        <option value="kvot">Kvoter (/match)</option>
                    </select>
                </div>
                <div class="md:col-span-3">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Mätvärde att visa</label>
                    <select id="toppMetric" class="w-full border-gray-300 rounded-md p-2 border bg-white" onchange="renderTopplistor()"></select>
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Serienivå</label>
                    <select id="toppLevel" class="w-full border-gray-300 rounded-md p-2 border bg-white" onchange="renderTopplistor()">
                        <option value="Alla">-- Alla Nivåer --</option>
                        <option value="1">Nivå 1</option>
                        <option value="2">Nivå 2</option>
                        <option value="3">Nivå 3</option>
                        <option value="4">Nivå 4</option>
                        <option value="5">Nivå 5</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Antal resultat</label>
                    <select id="toppCount" class="w-full border-gray-300 rounded-md p-2 border bg-white" onchange="renderTopplistor()">
                        <option value="10">Topp 10</option>
                        <option value="15">Topp 15</option>
                        <option value="20">Topp 20</option>
                        <option value="25">Topp 25</option>
                    </select>
                </div>
                <div class="md:col-span-4 flex items-center h-full pb-2">
                    <label class="inline-flex items-center cursor-pointer">
                        <input type="checkbox" id="toppUnique" class="form-checkbox h-5 w-5 text-blue-600 rounded" onchange="renderTopplistor()" checked>
                        <span class="ml-2 text-sm text-gray-700 font-medium">Endast unika lag <span class="font-normal text-gray-500">(Bocka ur för att tillåta ett lag att ha flera säsonger på samma lista)</span></span>
                    </label>
                </div>
            </div>
            
            <div class="text-sm text-gray-500 mb-2 flex justify-between">
                <span id="toppCounter">Beräknar topplista...</span>
            </div>
            <div class="table-container border border-gray-200 rounded-lg">
                <table class="min-w-full text-sm text-left whitespace-nowrap" id="toppTable">
                    <thead class="text-xs text-gray-700 uppercase bg-gray-100" id="toppHead"></thead>
                    <tbody class="divide-y divide-gray-200" id="toppBody"></tbody>
                </table>
            </div>
        </div>

        <!-- ============================================== -->
        <!-- FLIK 5: ADMINISTRATION                         -->
        <!-- ============================================== -->
        <div id="tab-admin" class="tab-content">
            <div class="bg-blue-50 border border-blue-200 p-4 rounded-lg shadow-sm mb-6">
                <h3 class="text-blue-800 font-bold mb-2 flex items-center">
                    <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path></svg>
                    Information: Vår- och höstserier (1991-1992) m.m.
                </h3>
                <p class="text-sm text-blue-900 mb-2">Säsongerna 1991 och 1992 (samt div 2 Norrland 2025) spelades delvis uppdelade i vår- och höstserier. Systemet är byggt för att hantera denna komplexitet logiskt:</p>
                <ul class="list-disc pl-5 text-sm text-blue-900 space-y-1">
                    <li><strong>I Topplistor (Säsong) & Maratontabeller:</strong> Både vår- och höstsäsongens matcher slås ihop till ett helt kalenderår för ett lag. Ev. bonuspoäng i starten av höstserier räknas ej med i totalen (endast utdömda minuspoäng). Resultatet är lagets samlade faktiska prestation det året.</li>
                    <li><strong>I Serievandringar & Sviter:</strong> Båda säsongshalvornas rad läses in, men "År på serienivån" grupperas per kalenderår så att inget lag ser ut att ha spelat två år under samma säsong, vilket ger matematiskt korrekta sviter.</li>
                </ul>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div class="space-y-6">
                    <div class="bg-gray-50 p-6 rounded-lg border border-gray-200 shadow-sm">
                        <h2 class="text-lg font-bold text-gray-800 mb-4">Databasens Hälsa (Nivå 1-5)</h2>
                        <ul class="space-y-3 text-sm text-gray-700" id="adminStatsList"></ul>
                    </div>
                    
                    <div class="bg-gray-50 p-6 rounded-lg border border-gray-200 shadow-sm">
                        <h2 class="text-lg font-bold text-gray-800 mb-2">Registrerade Namnbyten</h2>
                        <p class="text-xs text-gray-500 mb-3">Lag som har haft flera olika inskrivna namn i nationellt seriespel.</p>
                        <div class="max-h-60 overflow-y-auto bg-white p-3 rounded border border-gray-200">
                            <ul class="space-y-2 text-sm text-gray-800" id="adminNameChanges"></ul>
                        </div>
                    </div>
                </div>

                <div class="bg-red-50 p-6 rounded-lg border border-red-200 shadow-sm h-full flex flex-col">
                    <h2 class="text-lg font-bold text-red-800 mb-2">Föräldralösa lag (Saknar Alias)</h2>
                    <p class="text-sm text-red-600 mb-3">Dessa lagnamn hittades i fliken "Tabeller" men saknar koppling i fliken "Lag_nr". Deras statistik kommer inte matchas till något Standard-namn.</p>
                    <div class="flex-grow overflow-y-auto bg-white p-3 rounded border border-red-100">
                        <ul class="list-disc pl-5 text-sm text-gray-800" id="adminOrphansList"></ul>
                    </div>
                </div>
            </div>
            
            <!-- Hidden table for CSV export -->
            <div class="mt-8 hidden" id="adminTableContainer">
               <table id="adminTable">
                   <thead><tr><th>Information</th></tr></thead>
                   <tbody id="adminBody"></tbody>
               </table>
            </div>
        </div>

    </div>

    <!-- DATA INJECTION OCH LOGIK -->
    <script>
        const matchData = __JSON_DATA__;
        const snabbvalData = __SNABBVAL_JSON__;
        const adminData = __ADMIN_JSON__;
        const ongoingSeason = __ONGOING_SEASON__;
        let currentTabId = 'tab-maraton';
        
        // 1. KARTLÄGG BEROENDEN MELLAN NIVÅ OCH DIVISION SAMT FRAMTIDA NIVÅER FÖR FÄRGLÄGGNING
        const levelDivMap = { levels: {}, divs: {} };
        const teamYearLevel = {}; 
        const snabbvalMap = {};
        
        // Bearbeta Snabbval
        snabbvalData.forEach(row => {
            let name = row.Benämning;
            if(!snabbvalMap[name]) snabbvalMap[name] = [];
            let sista = (row.Sista_säsnr === 'Senaste') ? 999999 : (parseInt(row.Sista_säsnr) || 999999);
            snabbvalMap[name].push({
                niva: parseInt(row.Nivå) || 0,
                div: row.Division,
                start: parseInt(row.Första_säsnr) || 0,
                end: sista
            });
        });
        
        matchData.forEach(d => {
            let lvl = String(d.Nivå);
            let div = d.Division;
            if(lvl && div) {
                if(!levelDivMap.levels[lvl]) levelDivMap.levels[lvl] = new Set();
                levelDivMap.levels[lvl].add(div);
                
                if(!levelDivMap.divs[div]) levelDivMap.divs[div] = new Set();
                levelDivMap.divs[div].add(lvl);
            }
            
            let tName = d.Analys_Lagnamn;
            if(!teamYearLevel[tName]) teamYearLevel[tName] = {};
            // Spara den LÄGSTA siffan (högsta nivån) om vår/höst spelas på olika
            if(teamYearLevel[tName][d.Startår_Numerisk]) {
                teamYearLevel[tName][d.Startår_Numerisk] = Math.min(teamYearLevel[tName][d.Startår_Numerisk], d.Nivå);
            } else {
                teamYearLevel[tName][d.Startår_Numerisk] = d.Nivå;
            }
        });

        // Extrahera unika säsonger (som objekt för snyggare dropdown)
        const uniqueSeasonsObj = [];
        const seenSeasons = new Set();
        matchData.forEach(d => {
            if(!seenSeasons.has(d.Säsong)) {
                seenSeasons.add(d.Säsong);
                uniqueSeasonsObj.push({ sStr: d.Säsong, sNum: d.Startår_Numerisk });
            }
        });
        uniqueSeasonsObj.sort((a,b) => a.sNum - b.sNum);

        const allYears = [...new Set(matchData.map(d => parseInt(d.Startår_Numerisk)))].filter(y => !isNaN(y) && y > 0).sort((a,b) => a-b);
        const completedYears = ongoingSeason ? allYears.filter(y => y < ongoingSeason) : allYears;
        const completedMatchData = matchData.filter(d => completedYears.includes(d.Startår_Numerisk));
        
        // Till Serietabeller-dropdown (endast completed)
        const completedSeasonsObj = ongoingSeason ? uniqueSeasonsObj.filter(seq => seq.sNum < ongoingSeason) : uniqueSeasonsObj;
        
        const allDivisions = [...new Set(matchData.map(d => d.Division))].filter(Boolean).sort((a,b) => a.localeCompare(b));
        const allTeams = [...new Set(matchData.map(d => d.Analys_Lagnamn))].sort((a,b) => a.localeCompare(b));
        
        // Definitioner för Topplistor (Uppdelat)
        const toppMetrics = {
            'sasong': {
                'abs': [
                    {id: 'p_max', text: 'Flest Poäng'},
                    {id: 'p_min', text: 'Minst Poäng (Minst 10 sp)'},
                    {id: 'gj_max', text: 'Flest Gjorda Mål'},
                    {id: 'insl_min', text: 'Minst Insläppta Mål (Minst 10 sp)'}
                ],
                'kvot': [
                    {id: 'p_snitt_max', text: 'Bäst Poängsnitt'},
                    {id: 'p_snitt_min', text: 'Sämst Poängsnitt'},
                    {id: 'gj_snitt_max', text: 'Högst Målsnitt framåt'}
                ]
            },
            'maraton': {
                'abs': [
                    {id: 'p_max', text: 'Flest Poäng Totalt'},
                    {id: 'gj_max', text: 'Flest Gjorda Mål Totalt'},
                    {id: 'sasong_max', text: 'Flest Spelade Säsonger'}
                ],
                'kvot': [
                    {id: 'p_snitt_max', text: 'Bäst Poängsnitt (Minst 30 sp)'}
                ]
            },
            'vandring': {
                'abs': [
                    {id: 'jojo_max', text: 'Största Jojolag (Flest upp+ned)'},
                    {id: 'upp_max', text: 'Flest totala uppflyttningar'},
                    {id: 'ned_max', text: 'Flest totala nedflyttningar'},
                    {id: 'svit_max', text: 'Längsta obrutna svit (år)'}
                ],
                'kvot': []
            }
        };

        function populateDropdown(selectId, dataArray, reverse=false, defaultLast=false) {
            const select = document.getElementById(selectId);
            if(!select) return;
            
            let hasPlaceholder = select.options.length > 0 && select.options[0].value.includes('Alla');
            let placeholderHTML = hasPlaceholder ? select.options[0].outerHTML : '';
            
            select.innerHTML = placeholderHTML;
            let displayData = reverse ? [...dataArray].reverse() : dataArray;
            
            displayData.forEach(item => {
                let opt = document.createElement('option');
                opt.value = item;
                opt.innerHTML = item;
                select.appendChild(opt);
            });
            
            if(defaultLast && dataArray.length > 0) {
                select.value = dataArray[dataArray.length - 1];
            } else if(!hasPlaceholder && dataArray.length > 0) {
                select.value = dataArray[0];
            }
        }

        // CASCADING DROPDOWNS
        function syncDropdowns(changedSelectId, targetSelectId, mapType) {
            let changedVal = document.getElementById(changedSelectId).value;
            let targetSelect = document.getElementById(targetSelectId);
            
            let validTargets = null;
            if (changedVal !== 'Alla') {
                if (mapType === 'levelToDiv' && levelDivMap.levels[changedVal]) {
                    validTargets = levelDivMap.levels[changedVal];
                } else if (mapType === 'divToLevel' && levelDivMap.divs[changedVal]) {
                    validTargets = levelDivMap.divs[changedVal];
                }
            }

            let options = Array.from(targetSelect.options);
            let allaOption = options.shift();

            options.forEach(opt => {
                if (validTargets === null || validTargets.has(opt.value)) {
                    opt.disabled = false;
                    opt.style.color = "";
                    opt.dataset.valid = "1";
                } else {
                    opt.disabled = true;
                    opt.style.color = "#9ca3af";
                    opt.dataset.valid = "0";
                }
            });

            options.sort((a, b) => {
                if (a.dataset.valid !== b.dataset.valid) return b.dataset.valid.localeCompare(a.dataset.valid);
                return a.text.localeCompare(b.text);
            });

            targetSelect.innerHTML = '';
            targetSelect.appendChild(allaOption);
            options.forEach(opt => targetSelect.appendChild(opt));

            if (targetSelect.options[targetSelect.selectedIndex].disabled) {
                targetSelect.value = 'Alla';
            }
        }

        function resetSelect(selectId) {
            let select = document.getElementById(selectId);
            if(!select) return;
            
            let hasPlaceholder = select.options.length > 0 && select.options[0].value.includes('Alla');
            let options = Array.from(select.options);
            let first = hasPlaceholder ? options.shift() : null;
            
            options.forEach(opt => {
                opt.disabled = false;
                opt.style.color = "";
                opt.dataset.valid = "1";
            });
            options.sort((a,b) => a.text.localeCompare(b.text));
            
            select.innerHTML = '';
            if(first) {
                select.appendChild(first);
                select.value = first.value;
            } else if (options.length > 0) {
                select.value = options[0].value;
            }
            options.forEach(opt => select.appendChild(opt));
        }

        function toggleSnabbval() {
            const useSnabbval = document.getElementById('maratonSnabbval').value !== 'Inget';
            let filters = document.querySelectorAll('.custom-filter');
            filters.forEach(el => {
                el.disabled = useSnabbval;
            });
            renderMaraton();
        }

        function resetFilters(tab) {
            if (tab === 'maraton') {
                document.getElementById('maratonSearch').value = '';
                document.getElementById('maratonPointsMode').value = '3';
                document.getElementById('maratonSnabbval').value = 'Inget';
                document.getElementById('maratonStartYear').value = completedYears[0];
                document.getElementById('maratonEndYear').value = completedYears[completedYears.length - 1];
                resetSelect('maratonLevel');
                resetSelect('maratonDivision');
                toggleSnabbval();
            } else if (tab === 'sasong') {
                let sy = document.getElementById('sasongYear');
                sy.value = sy.options[1] ? sy.options[1].value : 'Alla'; // Nollställ till Senaste år (index 1 är nyast)
                document.getElementById('sasongTeam').value = 'Alla';
                resetSelect('sasongLevel');
                resetSelect('sasongDivision');
                renderSasong();
            } else if (tab === 'vandring') {
                document.getElementById('vandringSearch').value = '';
                document.getElementById('vandringMode').value = 'niva';
                document.getElementById('vandringLevel').value = '1';
                let vd = document.getElementById('vandringDivision');
                if (vd.options.length > 0) vd.value = allDivisions[0];
                toggleVandringMode();
            }
        }

        // SMART LÄNK: HOPPA TILL SERIETABELLER MED KONTEXT
        function showTeamHistory(teamName, sourceTab) {
            switchTab('tab-sasong', document.querySelector('.tab-btn[onclick*="tab-sasong"]'));
            document.getElementById('sasongTeam').value = teamName;
            document.getElementById('sasongYear').value = 'Alla'; // Visa hela historiken
            
            if (sourceTab === 'maraton') {
                // If maraton had filters, bring them over if possible
                let snabbval = document.getElementById('maratonSnabbval').value;
                if(snabbval === 'Inget') {
                    document.getElementById('sasongLevel').value = document.getElementById('maratonLevel').value;
                    document.getElementById('sasongDivision').value = document.getElementById('maratonDivision').value;
                } else {
                    // Quick pick was active, best to show full history
                    document.getElementById('sasongLevel').value = 'Alla';
                    document.getElementById('sasongDivision').value = 'Alla';
                }
            } else if (sourceTab === 'vandring') {
                if(document.getElementById('vandringMode').value === 'niva') {
                    document.getElementById('sasongLevel').value = document.getElementById('vandringLevel').value;
                    document.getElementById('sasongDivision').value = 'Alla';
                } else {
                    document.getElementById('sasongLevel').value = 'Alla';
                    document.getElementById('sasongDivision').value = document.getElementById('vandringDivision').value;
                }
            } else if (sourceTab === 'topp') {
                document.getElementById('sasongLevel').value = document.getElementById('toppLevel').value;
                document.getElementById('sasongDivision').value = 'Alla';
            }
            
            syncDropdowns('sasongLevel', 'sasongDivision', 'levelToDiv');
            renderSasong();
        }
        
        function handleTeamSelect() {
            let team = document.getElementById('sasongTeam').value;
            if(team !== 'Alla') {
                document.getElementById('sasongYear').value = 'Alla'; 
            }
            renderSasong();
        }

        function switchTab(tabId, btnElement) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            btnElement.classList.add('active');
            currentTabId = tabId;
            
            if(tabId === 'tab-maraton') renderMaraton();
            if(tabId === 'tab-sasong') renderSasong();
            if(tabId === 'tab-vandring') renderVandringar();
            if(tabId === 'tab-topp') renderTopplistor(); 
        }

        function toggleVandringMode() {
            const mode = document.getElementById('vandringMode').value;
            if(mode === 'niva') {
                document.getElementById('vandringLevelWrapper').classList.remove('hidden');
                document.getElementById('vandringDivisionWrapper').classList.add('hidden');
            } else {
                document.getElementById('vandringLevelWrapper').classList.add('hidden');
                document.getElementById('vandringDivisionWrapper').classList.remove('hidden');
            }
            renderVandringar();
        }

        // RENDER: MARATONTABELL
        function renderMaraton() {
            const search = document.getElementById('maratonSearch').value.toLowerCase();
            const pMode = document.getElementById('maratonPointsMode').value;
            const snabbvalKey = document.getElementById('maratonSnabbval').value;
            const startYear = parseInt(document.getElementById('maratonStartYear').value) || 0;
            const endYear = parseInt(document.getElementById('maratonEndYear').value) || 9999;
            const level = document.getElementById('maratonLevel').value;
            const divFilter = document.getElementById('maratonDivision').value;
            
            const useSnabbval = (snabbvalKey !== 'Inget');
            const snabbvalConds = useSnabbval ? snabbvalMap[snabbvalKey] : [];

            const filtered = completedMatchData.filter(d => {
                if (search && !d.Analys_Lagnamn.toLowerCase().includes(search)) return false;
                
                if (useSnabbval) {
                    return snabbvalConds.some(c => {
                        return d.Nivå === c.niva &&
                               d.Division === c.div &&
                               d.Säsnr >= c.start &&
                               d.Säsnr <= c.end;
                    });
                } else {
                    if (d.Startår_Numerisk < startYear || d.Startår_Numerisk > endYear) return false;
                    if (level !== 'Alla' && String(d.Nivå) !== level) return false;
                    if (divFilter !== 'Alla' && d.Division !== divFilter) return false;
                    return true;
                }
            });

            let teams = {};
            filtered.forEach(d => {
                let t = d.Analys_Lagnamn;
                if (!teams[t]) teams[t] = { lag: t, saesonger: new Set(), sp: 0, v: 0, o: 0, f: 0, gj: 0, insl: 0, padv: 0, histP: 0 };
                teams[t].saesonger.add(d.Startår_Numerisk);
                teams[t].sp += Number(d.Sp) || 0;
                teams[t].v += Number(d.V) || 0;
                teams[t].o += Number(d.O) || 0;
                teams[t].f += Number(d.F) || 0;
                teams[t].gj += Number(d.Gjorda) || 0;
                teams[t].insl += Number(d.Insl) || 0;
                teams[t].padv += Number(d.Giltig_Poängavdrag) || 0;
                teams[t].histP += Number(d.P) || 0; 
            });

            let arr = Object.values(teams).map(t => {
                t.ant_saesonger = t.saesonger.size;
                t.ms = t.gj - t.insl;
                if(pMode === '3') t.poang = (t.v * 3) + (t.o * 1) + t.padv;
                else if(pMode === '2') t.poang = (t.v * 2) + (t.o * 1) + t.padv;
                else t.poang = t.histP;
                return t;
            });

            arr.sort((a, b) => b.poang - a.poang || b.ms - a.ms || b.gj - a.gj);

            document.getElementById('maratonHead').innerHTML = `
                <tr>
                    <th class="px-4 py-3">Plac</th>
                    <th class="px-4 py-3">Lag</th>
                    <th class="px-4 py-3 text-center">Säsonger</th>
                    <th class="px-4 py-3 text-center">Sp</th>
                    <th class="px-4 py-3 text-center">V</th>
                    <th class="px-4 py-3 text-center">O</th>
                    <th class="px-4 py-3 text-center">F</th>
                    <th class="px-4 py-3 text-center">Mål</th>
                    <th class="px-4 py-3 text-center">MS</th>
                    <th class="px-4 py-3 text-center font-bold text-gray-900">P</th>
                </tr>
            `;

            let tbody = '';
            arr.forEach((t, i) => {
                tbody += `
                    <tr class="hover:bg-blue-50 transition-colors">
                        <td class="px-4 py-2 text-gray-500">${i + 1}</td>
                        <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer" onclick="showTeamHistory('${t.lag}', 'maraton')" title="Klicka för att se lagets tabeller">${t.lag}</td>
                        <td class="px-4 py-2 text-center">${t.ant_saesonger}</td>
                        <td class="px-4 py-2 text-center">${t.sp}</td>
                        <td class="px-4 py-2 text-center">${t.v}</td>
                        <td class="px-4 py-2 text-center">${t.o}</td>
                        <td class="px-4 py-2 text-center">${t.f}</td>
                        <td class="px-4 py-2 text-center">${t.gj} - ${t.insl}</td>
                        <td class="px-4 py-2 text-center">${t.ms > 0 ? '+'+t.ms : t.ms}</td>
                        <td class="px-4 py-2 text-center font-bold text-gray-900">${t.poang}</td>
                    </tr>
                `;
            });
            document.getElementById('maratonBody').innerHTML = tbody;
            document.getElementById('maratonCounter').innerText = `Visar maratontabell för ${arr.length} lag.`;
        }

        // RENDER: SERIETABELL (ENSKILD SÄSONG / LAGHISTORIK)
        function renderSasong() {
            const seasonStr = document.getElementById('sasongYear').value;
            const teamFilter = document.getElementById('sasongTeam').value;
            const levelFilter = document.getElementById('sasongLevel').value;
            const divFilter = document.getElementById('sasongDivision').value;
            
            let data = completedMatchData.filter(d => {
                if(seasonStr !== 'Alla' && d.Säsong !== seasonStr) return false;
                if(teamFilter !== 'Alla' && d.Analys_Lagnamn !== teamFilter) return false;
                if(levelFilter !== 'Alla' && String(d.Nivå) !== levelFilter) return false;
                if(divFilter !== 'Alla' && d.Division !== divFilter) return false;
                return true;
            });
            
            data.sort((a, b) => {
                if(teamFilter !== 'Alla' || seasonStr === 'Alla') {
                    // Om vi följer historik över flera år, sortera kronologiskt framåt
                    return a.Startår_Numerisk - b.Startår_Numerisk || a.Nivå - b.Nivå;
                }
                // Enskilt år: Sortera per serie och placering
                return a.Nivå - b.Nivå || String(a.Serie).localeCompare(String(b.Serie)) || parseInt(a.Plac) - parseInt(b.Plac);
            });

            document.getElementById('sasongHead').innerHTML = `
                <tr>
                    <th class="px-4 py-3 text-center">År</th>
                    <th class="px-4 py-3 text-center">Nivå</th>
                    <th class="px-4 py-3">Beteckning</th>
                    <th class="px-4 py-3">Serie</th>
                    <th class="px-4 py-3 text-center">Plac</th>
                    <th class="px-4 py-3">Lag</th>
                    <th class="px-4 py-3 text-center">Sp</th>
                    <th class="px-4 py-3 text-center">V</th>
                    <th class="px-4 py-3 text-center">O</th>
                    <th class="px-4 py-3 text-center">F</th>
                    <th class="px-4 py-3 text-center">Gj-In</th>
                    <th class="px-4 py-3 text-center font-bold text-gray-900">P</th>
                    <th class="px-4 py-3 text-center">P-Just</th>
                </tr>
            `;

            let tbody = '';
            data.forEach(d => {
                let just = Number(d.Poängjustering_Startpoäng);
                
                let rowClass = "border-b border-gray-100 transition-colors";
                let nextYearLvl = teamYearLevel[d.Analys_Lagnamn][d.Startår_Numerisk + 1];
                let placNum = parseInt(d.Plac);
                
                // Mästare / Uppflyttad -> Grön
                if(nextYearLvl) {
                    if(nextYearLvl < d.Nivå || (d.Nivå === 1 && placNum === 1)) rowClass += " row-promoted";
                    else if(nextYearLvl > d.Nivå) rowClass += " row-relegated";
                    else rowClass += " hover:bg-blue-50";
                } else {
                    if(d.Nivå === 1 && placNum === 1) rowClass += " row-promoted";
                    else rowClass += " hover:bg-blue-50";
                }

                tbody += `
                    <tr class="${rowClass}">
                        <td class="px-4 py-2 text-center text-gray-500 font-medium">${d.Säsong}</td>
                        <td class="px-4 py-2 text-center font-medium">${d.Nivå}</td>
                        <td class="px-4 py-2 text-gray-600">${d.Division || '-'}</td>
                        <td class="px-4 py-2 text-gray-800">${d.Serie || '-'}</td>
                        <td class="px-4 py-2 text-center font-bold text-gray-900">${d.Plac || '-'}</td>
                        <td class="px-4 py-2 font-semibold text-gray-800" title="Standardnamn: ${d.Analys_Lagnamn}">${d['Laget i tabell']}</td>
                        <td class="px-4 py-2 text-center">${d.Sp}</td>
                        <td class="px-4 py-2 text-center">${d.V}</td>
                        <td class="px-4 py-2 text-center">${d.O}</td>
                        <td class="px-4 py-2 text-center">${d.F}</td>
                        <td class="px-4 py-2 text-center">${d.Gjorda} - ${d.Insl}</td>
                        <td class="px-4 py-2 text-center font-bold text-gray-900">${d.P}</td>
                        <td class="px-4 py-2 text-center text-gray-500">${just !== 0 ? just : ''}</td>
                    </tr>
                `;
            });
            document.getElementById('sasongBody').innerHTML = tbody;
            document.getElementById('sasongCounter').innerText = `Hittade ${data.length} rader utifrån valda filter.`;
        }

        // RENDER: SERIEVANDRINGAR
        function renderVandringar() {
            const search = document.getElementById('vandringSearch').value.toLowerCase();
            const mode = document.getElementById('vandringMode').value;
            const focusLevel = parseInt(document.getElementById('vandringLevel').value);
            const focusDivision = document.getElementById('vandringDivision').value;
            
            let teams = {};
            matchData.forEach(d => {
                if (search && !d.Analys_Lagnamn.toLowerCase().includes(search)) return;
                let t = d.Analys_Lagnamn;
                if(!teams[t]) teams[t] = { lag: t, history: [] };
                teams[t].history.push({ year: d.Startår_Numerisk, level: d.Nivå, division: d.Division });
            });

            let results = [];
            Object.values(teams).forEach(t => {
                t.history.sort((a,b) => a.year - b.year);
                
                let yearsOnFocus = new Set();
                let promoToHere = 0;
                let relegToHere = 0;

                for(let i=0; i<t.history.length; i++) {
                    let curr = t.history[i];
                    let isMatch = false;
                    if(mode === 'niva') isMatch = (curr.level === focusLevel);
                    else isMatch = (curr.division === focusDivision);

                    if(isMatch) {
                        yearsOnFocus.add(curr.year);
                        if(i > 0 && t.history[i-1].year === curr.year - 1) {
                            let prevLvl = t.history[i-1].level;
                            if(prevLvl > curr.level) promoToHere++;
                            if(prevLvl < curr.level) relegToHere++;
                        }
                    }
                }

                if(yearsOnFocus.size > 0) {
                    let sortedYears = Array.from(yearsOnFocus).sort((a,b) => a-b);
                    let maxStreak = 1;
                    let currentStreak = 1;
                    let maxGap = 0;

                    for(let j=1; j<sortedYears.length; j++) {
                        let diff = sortedYears[j] - sortedYears[j-1];
                        if(diff === 1) {
                            currentStreak++;
                            if(currentStreak > maxStreak) maxStreak = currentStreak;
                        } else {
                            currentStreak = 1;
                            let gap = diff - 1;
                            if(gap > maxGap) maxGap = gap;
                        }
                    }

                    results.push({
                        lag: t.lag, tot_years: sortedYears.length, max_streak: maxStreak,
                        max_gap: maxGap, promo: promoToHere, releg: relegToHere
                    });
                }
            });

            results.sort((a,b) => b.max_streak - a.max_streak || b.tot_years - a.tot_years);

            document.getElementById('vandringHead').innerHTML = `
                <tr>
                    <th class="px-4 py-3">Lag</th>
                    <th class="px-4 py-3 text-center" title="Totalt antal kalenderår de spelat på denna position">Totala År</th>
                    <th class="px-4 py-3 text-center font-bold text-blue-700" title="Hur många år i sträck de som mest spelat här">Längsta Svit (år i sträck)</th>
                    <th class="px-4 py-3 text-center text-red-600" title="Längsta tiden de var borta härifrån innan de kom tillbaka">Längsta Frånvaro (år)</th>
                    <th class="px-4 py-3 text-center text-green-600" title="Gånger de klättrat UPP hit från en lägre nivå">Uppflyttad hit (ggr)</th>
                    <th class="px-4 py-3 text-center text-orange-600" title="Gånger de ramlat NER hit från en högre nivå">Degraderad hit (ggr)</th>
                </tr>
            `;

            let tbody = '';
            results.forEach(r => {
                tbody += `
                    <tr class="hover:bg-blue-50 transition-colors">
                        <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer" onclick="showTeamHistory('${r.lag}', 'vandring')" title="Klicka för att se lagets tabeller">${r.lag}</td>
                        <td class="px-4 py-2 text-center text-gray-600">${r.tot_years}</td>
                        <td class="px-4 py-2 text-center font-bold text-blue-700">${r.max_streak}</td>
                        <td class="px-4 py-2 text-center text-red-500">${r.max_gap > 0 ? r.max_gap : '-'}</td>
                        <td class="px-4 py-2 text-center text-green-600">${r.promo > 0 ? r.promo : '-'}</td>
                        <td class="px-4 py-2 text-center text-orange-600">${r.releg > 0 ? r.releg : '-'}</td>
                    </tr>
                `;
            });
            document.getElementById('vandringBody').innerHTML = tbody;
            let context = mode === 'niva' ? `Nivå ${focusLevel}` : `Seriebeteckning: ${focusDivision}`;
            document.getElementById('vandringCounter').innerText = `Hittade ${results.length} lag som någon gång spelat på ${context}.`;
        }

        // ==============================================
        // NY FLIK: TOPPLISTOR
        // ==============================================
        function updateToppMetrics() {
            const cat = document.getElementById('toppCategory').value;
            const type = document.getElementById('toppMetricType').value;
            const select = document.getElementById('toppMetric');
            
            document.getElementById('toppUnique').disabled = (cat !== 'sasong');
            
            let currentType = type;
            if (toppMetrics[cat]['kvot'].length === 0) {
                document.getElementById('toppMetricType').value = 'abs';
                document.getElementById('toppMetricType').disabled = true;
                currentType = 'abs';
            } else {
                document.getElementById('toppMetricType').disabled = false;
            }
            
            select.innerHTML = '';
            let html = '';
            toppMetrics[cat][currentType].forEach(m => {
                html += `<option value="${m.id}">${m.text}</option>`;
            });
            select.innerHTML = html;
            renderTopplistor();
        }

        function formatVal(val, isFloat) {
            if(isFloat) return parseFloat(val).toFixed(2);
            return val;
        }

        function renderTopplistor() {
            const cat = document.getElementById('toppCategory').value;
            const metric = document.getElementById('toppMetric').value;
            const count = parseInt(document.getElementById('toppCount').value);
            const level = document.getElementById('toppLevel').value;
            const unique = document.getElementById('toppUnique').checked;
            
            let htmlHead = '';
            let htmlBody = '';
            let results = [];

            // SÄSONG (Med Vår/Höst ihopslog)
            if (cat === 'sasong') {
                let seasonDataMap = {};
                
                completedMatchData.forEach(d => {
                    if (level !== 'Alla' && String(d.Nivå) !== level) return;
                    
                    let key = d.Analys_Lagnamn + "_" + d.Startår_Numerisk;
                    if(!seasonDataMap[key]) {
                        seasonDataMap[key] = {
                            Analys_Lagnamn: d.Analys_Lagnamn,
                            'Laget i tabell': d['Laget i tabell'], 
                            Startår_Numerisk: d.Startår_Numerisk,
                            Nivå: d.Nivå,
                            Sp: 0, V: 0, O: 0, F: 0, Gjorda: 0, Insl: 0, P: 0, Målskillnad: 0
                        };
                    }
                    let entry = seasonDataMap[key];
                    entry.Sp += Number(d.Sp) || 0;
                    entry.V += Number(d.V) || 0;
                    entry.O += Number(d.O) || 0;
                    entry.F += Number(d.F) || 0;
                    entry.Gjorda += Number(d.Gjorda) || 0;
                    entry.Insl += Number(d.Insl) || 0;
                    entry.P += Number(d.P) || 0; 
                    entry.Målskillnad += Number(d.Målskillnad) || 0;
                    entry.Nivå = Math.min(entry.Nivå, d.Nivå); // Behåll högsta nivån om olika
                });

                let data = Object.values(seasonDataMap);
                
                data.forEach(d => {
                    d.p_snitt = d.Sp > 0 ? (d.P / d.Sp) : 0;
                    d.gj_snitt = d.Sp > 0 ? (d.Gjorda / d.Sp) : 0;
                });

                let isFloat = false;
                let valKey = '';
                
                if (metric === 'p_max') { data.sort((a,b) => b.P - a.P || b.Målskillnad - a.Målskillnad); valKey = 'P'; }
                else if (metric === 'p_min') { data = data.filter(d=>d.Sp>=10); data.sort((a,b) => a.P - b.P || a.Målskillnad - b.Målskillnad); valKey = 'P'; }
                else if (metric === 'gj_max') { data.sort((a,b) => b.Gjorda - a.Gjorda || b.P - a.P); valKey = 'Gjorda'; }
                else if (metric === 'insl_min') { data = data.filter(d=>d.Sp>=10); data.sort((a,b) => a.Insl - b.Insl || b.P - a.P); valKey = 'Insl'; }
                else if (metric === 'p_snitt_max') { data = data.filter(d=>d.Sp>=10); data.sort((a,b) => b.p_snitt - a.p_snitt); valKey = 'p_snitt'; isFloat = true; }
                else if (metric === 'p_snitt_min') { data = data.filter(d=>d.Sp>=10); data.sort((a,b) => a.p_snitt - b.p_snitt); valKey = 'p_snitt'; isFloat = true; }
                else if (metric === 'gj_snitt_max') { data = data.filter(d=>d.Sp>=10); data.sort((a,b) => b.gj_snitt - a.gj_snitt); valKey = 'gj_snitt'; isFloat = true; }

                if (unique) {
                    let seen = new Set();
                    data = data.filter(d => {
                        if (seen.has(d.Analys_Lagnamn)) return false;
                        seen.add(d.Analys_Lagnamn);
                        return true;
                    });
                }
                
                results = data.slice(0, count);

                htmlHead = `<tr><th class="px-4 py-3">Plac</th><th class="px-4 py-3">Lag</th><th class="px-4 py-3 text-center">År</th><th class="px-4 py-3 text-center">Nivå</th><th class="px-4 py-3 text-center">Sp</th><th class="px-4 py-3 text-center">V-O-F</th><th class="px-4 py-3 text-center">Gj-In</th><th class="px-4 py-3 text-center font-bold text-blue-700">Mätvärde</th></tr>`;
                
                results.forEach((d, i) => {
                    let displayVal = formatVal(d[valKey], isFloat);
                    htmlBody += `
                        <tr class="hover:bg-blue-50 transition-colors">
                            <td class="px-4 py-2 text-gray-500">${i+1}</td>
                            <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer" onclick="showTeamHistory('${d.Analys_Lagnamn}', 'topp')" title="Standardnamn: ${d.Analys_Lagnamn}">${d['Laget i tabell']}</td>
                            <td class="px-4 py-2 text-center text-gray-600 font-medium">${d.Startår_Numerisk}</td>
                            <td class="px-4 py-2 text-center">${d.Nivå}</td>
                            <td class="px-4 py-2 text-center">${d.Sp}</td>
                            <td class="px-4 py-2 text-center">${d.V}-${d.O}-${d.F}</td>
                            <td class="px-4 py-2 text-center">${d.Gjorda}-${d.Insl}</td>
                            <td class="px-4 py-2 text-center font-bold text-blue-700">${displayVal}</td>
                        </tr>
                    `;
                });
            } 
            
            // MARATON
            else if (cat === 'maraton') {
                let data = completedMatchData.filter(d => level === 'Alla' || String(d.Nivå) === level);
                let teams = {};
                data.forEach(d => {
                    let t = d.Analys_Lagnamn;
                    if (!teams[t]) teams[t] = { lag: t, saesonger: new Set(), sp: 0, v: 0, o: 0, f: 0, gj: 0, insl: 0, p: 0, histNamn: d['Laget i tabell'] };
                    teams[t].saesonger.add(d.Startår_Numerisk);
                    teams[t].sp += Number(d.Sp) || 0;
                    teams[t].v += Number(d.V) || 0;
                    teams[t].o += Number(d.O) || 0;
                    teams[t].f += Number(d.F) || 0;
                    teams[t].gj += Number(d.Gjorda) || 0;
                    teams[t].insl += Number(d.Insl) || 0;
                    // Standard 3-poäng för absolut rättvisa över tid
                    teams[t].p += (Number(d.V) * 3) + (Number(d.O) * 1) + Number(d.Giltig_Poängavdrag);
                });

                let arr = Object.values(teams).map(t => {
                    t.ant_saesonger = t.saesonger.size;
                    t.p_snitt = t.sp > 0 ? (t.p / t.sp) : 0;
                    return t;
                });

                let isFloat = false;
                let valKey = '';
                
                if (metric === 'p_max') { arr.sort((a,b) => b.p - a.p); valKey = 'p'; }
                else if (metric === 'gj_max') { arr.sort((a,b) => b.gj - a.gj); valKey = 'gj'; }
                else if (metric === 'sasong_max') { arr.sort((a,b) => b.ant_saesonger - a.ant_saesonger); valKey = 'ant_saesonger'; }
                else if (metric === 'p_snitt_max') { arr = arr.filter(t=>t.sp>=30); arr.sort((a,b) => b.p_snitt - a.p_snitt); valKey = 'p_snitt'; isFloat = true; }

                results = arr.slice(0, count);

                htmlHead = `<tr><th class="px-4 py-3">Plac</th><th class="px-4 py-3">Lag</th><th class="px-4 py-3 text-center">Säsonger</th><th class="px-4 py-3 text-center">Sp</th><th class="px-4 py-3 text-center">V-O-F</th><th class="px-4 py-3 text-center">Gj-In</th><th class="px-4 py-3 text-center">Poäng (3p)</th><th class="px-4 py-3 text-center font-bold text-blue-700">Mätvärde</th></tr>`;
                
                results.forEach((t, i) => {
                    let displayVal = formatVal(t[valKey], isFloat);
                    htmlBody += `
                        <tr class="hover:bg-blue-50 transition-colors">
                            <td class="px-4 py-2 text-gray-500">${i+1}</td>
                            <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer" onclick="showTeamHistory('${t.lag}', 'topp')">${t.lag}</td>
                            <td class="px-4 py-2 text-center">${t.ant_saesonger}</td>
                            <td class="px-4 py-2 text-center">${t.sp}</td>
                            <td class="px-4 py-2 text-center">${t.v}-${t.o}-${t.f}</td>
                            <td class="px-4 py-2 text-center">${t.gj}-${t.insl}</td>
                            <td class="px-4 py-2 text-center">${t.p}</td>
                            <td class="px-4 py-2 text-center font-bold text-blue-700">${displayVal}</td>
                        </tr>
                    `;
                });
            }

            // VANDRING & JOJO
            else if (cat === 'vandring') {
                let data = matchData; // Full historik ink pågående!
                let teams = {};
                
                data.forEach(d => {
                    let t = d.Analys_Lagnamn;
                    if(!teams[t]) teams[t] = { lag: t, history: [] };
                    teams[t].history.push({ year: d.Startår_Numerisk, level: d.Nivå });
                });

                let arr = [];
                Object.values(teams).forEach(t => {
                    t.history.sort((a,b) => a.year - b.year);
                    let upp_tot = 0, ned_tot = 0, max_svit = 0;
                    
                    for(let i=1; i<t.history.length; i++) {
                        if (t.history[i].year === t.history[i-1].year + 1) {
                            let diff = t.history[i-1].level - t.history[i].level;
                            if (diff > 0) upp_tot++;
                            if (diff < 0) ned_tot++;
                        }
                    }
                    
                    let yearsOnLevel = [];
                    t.history.forEach(h => {
                        if(level === 'Alla' || String(h.level) === level) {
                            yearsOnLevel.push(h.year);
                        }
                    });
                    
                    let uniqueYears = Array.from(new Set(yearsOnLevel)).sort((a,b) => a-b);
                    let currSvit = 1;
                    if (uniqueYears.length > 0) max_svit = 1;
                    
                    for(let j=1; j<uniqueYears.length; j++) {
                        if(uniqueYears[j] - uniqueYears[j-1] === 1) {
                            currSvit++;
                            if(currSvit > max_svit) max_svit = currSvit;
                        } else {
                            currSvit = 1;
                        }
                    }

                    arr.push({ lag: t.lag, upp: upp_tot, ned: ned_tot, jojo: upp_tot + ned_tot, svit: max_svit });
                });

                let valKey = '';
                if (metric === 'jojo_max') { arr.sort((a,b) => b.jojo - a.jojo); valKey = 'jojo'; }
                else if (metric === 'upp_max') { arr.sort((a,b) => b.upp - a.upp); valKey = 'upp'; }
                else if (metric === 'ned_max') { arr.sort((a,b) => b.ned - a.ned); valKey = 'ned'; }
                else if (metric === 'svit_max') { arr.sort((a,b) => b.svit - a.svit); valKey = 'svit'; }

                results = arr.slice(0, count);

                htmlHead = `<tr><th class="px-4 py-3">Plac</th><th class="px-4 py-3">Lag</th><th class="px-4 py-3 text-center">Uppflyttningar (Totalt)</th><th class="px-4 py-3 text-center">Nedflyttningar (Totalt)</th><th class="px-4 py-3 text-center">Längsta Svit (på nivån)</th><th class="px-4 py-3 text-center font-bold text-blue-700">Mätvärde</th></tr>`;
                
                results.forEach((t, i) => {
                    htmlBody += `
                        <tr class="hover:bg-blue-50 transition-colors">
                            <td class="px-4 py-2 text-gray-500">${i+1}</td>
                            <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer" onclick="showTeamHistory('${t.lag}', 'topp')">${t.lag}</td>
                            <td class="px-4 py-2 text-center text-green-600">${t.upp}</td>
                            <td class="px-4 py-2 text-center text-orange-600">${t.ned}</td>
                            <td class="px-4 py-2 text-center text-blue-600">${t.svit}</td>
                            <td class="px-4 py-2 text-center font-bold text-blue-700">${t[valKey]}</td>
                        </tr>
                    `;
                });
            }

            document.getElementById('toppHead').innerHTML = htmlHead;
            document.getElementById('toppBody').innerHTML = htmlBody;
            document.getElementById('toppCounter').innerText = `Visar ${results.length} resultat.`;
        }

        // RENDER: ADMINISTRATION
        function renderAdmin() {
            document.getElementById('adminStatsList').innerHTML = `
                <li><span class="font-semibold text-gray-800">Totalt antal matchrader (Nivå 1-5):</span> ${adminData.total_rows}</li>
                <li><span class="font-semibold text-gray-800">Unika Standard-lagnamn:</span> ${adminData.unique_teams}</li>
                <li><span class="font-semibold ${adminData.orphans_count > 0 ? 'text-red-600' : 'text-gray-800'}">Antal föräldralösa lag:</span> ${adminData.orphans_count} st</li>
            `;
            
            let namesHtml = '';
            if(adminData.name_changes.length > 0) {
                adminData.name_changes.forEach(n => {
                    namesHtml += `<li class="border-b border-gray-100 pb-2"><span class="font-bold text-blue-800">${n.standard}</span> har även spelat under alias: <span class="text-gray-600 italic">${n.aliases.join(', ')}</span></li>`;
                });
            } else {
                namesHtml = '<li class="text-gray-500">Inga namnbyten registrerade för giltiga Lag_ID.</li>';
            }
            document.getElementById('adminNameChanges').innerHTML = namesHtml;

            let orphanHtml = '';
            if(adminData.orphans_list.length > 0) {
                adminData.orphans_list.forEach(o => { orphanHtml += `<li>${o}</li>`; });
            } else {
                orphanHtml = '<li class="text-green-600 font-bold">Allt ser perfekt ut! Inga saknade alias.</li>';
            }
            document.getElementById('adminOrphansList').innerHTML = orphanHtml;
            
            let exportHtml = `<tr><td>STATISTIK OCH NAMNBYTEN</td></tr>`;
            adminData.name_changes.forEach(n => { exportHtml += `<tr><td>${n.standard} (Alias: ${n.aliases.join(', ')})</td></tr>`; });
            exportHtml += `<tr><td>SAKNADE ALIAS (ORPHANS)</td></tr>`;
            adminData.orphans_list.forEach(o => { exportHtml += `<tr><td>${o}</td></tr>`; });
            document.getElementById('adminBody').innerHTML = exportHtml;
        }

        // EXPORT CSV
        function exportCSV() {
            let csv = [];
            let activeTab = document.querySelector('.tab-content.active');
            let rows = activeTab.querySelectorAll("table tr");
            if(rows.length === 0) return alert("Det finns ingen tabell att exportera i denna flik.");

            for (let i = 0; i < rows.length; i++) {
                let row = [], cols = rows[i].querySelectorAll("td, th");
                for (let j = 0; j < cols.length; j++) {
                    let text = cols[j].innerText.replace(/"/g, '""');
                    row.push('"' + text + '"');
                }
                csv.push(row.join(";"));
            }
            let csvFile = new Blob(["\\uFEFF" + csv.join("\\n")], {type: "text/csv;charset=utf-8-sig;"});
            let downloadLink = document.createElement("a");
            downloadLink.download = `Fotbollsdata_${currentTabId}.csv`;
            downloadLink.href = window.URL.createObjectURL(csvFile);
            downloadLink.style.display = "none";
            document.body.appendChild(downloadLink);
            downloadLink.click();
        }

        window.onload = function() {
            populateDropdown('maratonStartYear', completedYears);
            populateDropdown('maratonEndYear', completedYears, true, true);
            
            // Fyll dropdown för Maratontabeller (Snabbval)
            if(Object.keys(snabbvalMap).length > 0) {
                let snabbvalHtml = '<option value="Inget">-- Använd egna filter nedan --</option>';
                Object.keys(snabbvalMap).sort().forEach(k => {
                    snabbvalHtml += `<option value="${k}">${k}</option>`;
                });
                document.getElementById('maratonSnabbval').innerHTML = snabbvalHtml;
            }

            // Fyll dropdown för Serietabeller med snygga Sträng-namn istället för bara årtal
            let sy = document.getElementById('sasongYear');
            sy.innerHTML = '<option value="Alla">-- Alla Säsonger --</option>';
            [...completedSeasonsObj].reverse().forEach(seq => { 
                sy.innerHTML += `<option value="${seq.sStr}">${seq.sStr}</option>`; 
            });
            if(sy.options.length > 1) sy.selectedIndex = 1;

            populateDropdown('sasongTeam', allTeams);
            populateDropdown('maratonDivision', allDivisions);
            populateDropdown('sasongDivision', allDivisions);
            populateDropdown('vandringDivision', allDivisions);
            
            updateToppMetrics(); // Initierar topplistor
            renderMaraton();
            renderAdmin();
        };
    </script>
</body>
</html>
"""
    
    html_output = html_template.replace('__JSON_DATA__', json_data)\
                               .replace('__SNABBVAL_JSON__', json_snabbval)\
                               .replace('__ADMIN_JSON__', json_admin)\
                               .replace('__ONGOING_SEASON__', str(PAGAENDE_SASONG) if PAGAENDE_SASONG else 'null')
    
    output_path = os.path.join(project_root, "Fotbollsanalys_Dashboard.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_output)
        
    print(f"✅ HTML Dashboard skapad: {os.path.basename(output_path)}")

if __name__ == "__main__":
    master_df, _, df_snabbval = get_master_data()
    if master_df is not None:
        export_html_dashboard(master_df, df_snabbval)
        print("\nAllt klart! Du hittar din nya dashboard-fil i mappen ovanför skriptet.")