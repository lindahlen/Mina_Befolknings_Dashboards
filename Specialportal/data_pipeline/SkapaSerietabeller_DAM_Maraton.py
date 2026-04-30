import os
import pandas as pd
import numpy as np
import json

# =====================================================================
# 1. ANVÄNDARINSTÄLLNINGAR FÖR VYER OCH FILER (ÄNDRA HÄR VID BEHOV)
# =====================================================================

# Titeln som visas högst upp på själva webbsidan och i webbläsarfliken
DASHBOARD_TITEL = "Svensk Fotbollshistoria - Damernas nationella seriesystem"

# Vilken Excel-fil ska systemet leta efter? 
EXCEL_FILNAMN_SOKORD = "DAM_Serietabellerna_samlade"

# Vad ska den färdiga, klickbara hemsidan heta?
HTML_UTDATA_FILNAMN = "Fotbollsanalys_Damserier_Dashboard.html"

# Vilket år är innevarande säsong?
PAGAENDE_SASONG = 2026

# Hur ska SM-guld (Grön färg) markeras i Serietabellerna?
# False = Standard för herrar (Nivå 1, Plac 1 tar automatiskt guldet)
# True  = Standard för damer (Guldet markeras ENBART via kolumnen 'SM_vinnare')
ANVAND_SM_VINNARE_FOR_GULD = False

# =====================================================================

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
except NameError:
    project_root = os.getcwd()
    pass 

def find_target_file(keyword, search_root):
    # 1. Leta först efter en EXAKT matchning
    for root, dirs, files in os.walk(search_root):
        for filename in files:
            if not filename.startswith("~$") and filename.lower().endswith(".xlsx"):
                name_without_ext = filename[:-5]
                if keyword.lower() == name_without_ext.lower() or keyword.lower() == filename.lower():
                    return os.path.join(root, filename)
                    
    # 2. Om ingen exakt match hittades, leta efter del-matchning
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
    excel_path = find_target_file(EXCEL_FILNAMN_SOKORD, project_root)
    if not excel_path:
        print(f"FEL: Hittade inte någon Excel-fil som matchar '{EXCEL_FILNAMN_SOKORD}'.")
        return None, None, None
        
    print(f"Laddar databasen från: {os.path.basename(excel_path)}...")
    excel_dict = pd.read_excel(excel_path, sheet_name=None, engine='openpyxl')
    
    df_tabeller = clean_dataframe(excel_dict.get('Tabeller'))
    df_lag_nr = clean_dataframe(excel_dict.get('Lag_nr'))
    df_lag_id = clean_dataframe(excel_dict.get('Lag_id'))
    df_serieniva = clean_dataframe(excel_dict.get('Serienivå'))
    df_snabbval = clean_dataframe(excel_dict.get('Snabbval'))
    df_viktning = clean_dataframe(excel_dict.get('Viktningstabell'))
    
    if df_tabeller is not None:
        df_tabeller = df_tabeller.rename(columns={'Lag': 'Laget i tabell'}) 
    
    master = pd.merge(df_tabeller, df_lag_nr[['Laget', 'Lag_ID']], left_on='Laget i tabell', right_on='Laget', how='left')
    
    cols_lag_id = ['Lag_ID', 'Lag', 'Distrikt', 'Kommun']
    if 'Bildad' in df_lag_id.columns:
        cols_lag_id.append('Bildad')
        
    master = pd.merge(master, df_lag_id[cols_lag_id], on='Lag_ID', how='left').rename(columns={'Lag': 'Standard_Lagnamn'})
    
    cols_niva = ['Säsnr', 'Poäng_seger']
    if 'SM_vinnare' in df_serieniva.columns:
        cols_niva.append('SM_vinnare')
    master = pd.merge(master, df_serieniva[cols_niva], on='Säsnr', how='left')
    
    master['Analys_Lagnamn'] = master['Standard_Lagnamn'].fillna(master['Laget i tabell'])
    master['Startår_Numerisk'] = master['Säsong'].astype(str).str.extract(r'^(\d{4})').astype(float)
    
    master['Säsongsdel'] = 0
    for col in ['Serie', 'Division', 'Anm']:
        if col in master.columns:
            master.loc[master[col].astype(str).str.lower().str.contains('vår'), 'Säsongsdel'] = 1
            master.loc[master[col].astype(str).str.lower().str.contains('höst'), 'Säsongsdel'] = 2
    
    if 'Poängjustering_Startpoäng' in master.columns:
        master['Poängjustering_Startpoäng'] = pd.to_numeric(master['Poängjustering_Startpoäng'], errors='coerce').fillna(0)
        master['Giltig_Poängavdrag'] = master['Poängjustering_Startpoäng'].apply(lambda x: x if x < 0 else 0)
    else:
        master['Giltig_Poängavdrag'] = 0
        master['Poängjustering_Startpoäng'] = 0

    for col in ['Sp', 'V', 'O', 'F', 'Gjorda', 'Insl', 'P', 'Säsnr']:
        master[col] = pd.to_numeric(master[col], errors='coerce').fillna(0)

    master['Målskillnad'] = master['Gjorda'] - master['Insl']
    
    master['Nivå_multiplikator'] = 1.0
    master['Epok_multiplikator'] = 1.0
    
    if df_viktning is not None and not df_viktning.empty:
        print("💡 Applicerar historiska viktningar från fliken 'Viktningstabell'...")
        if 'Första_säsnr' in df_viktning.columns:
            df_viktning['Första_säsnr'] = pd.to_numeric(df_viktning['Första_säsnr'], errors='coerce').fillna(0)
            df_viktning['Sista_säsnr'] = df_viktning['Sista_säsnr'].replace('Senaste', 999999)
            df_viktning['Sista_säsnr'] = pd.to_numeric(df_viktning['Sista_säsnr'], errors='coerce').fillna(999999)
            
            for _, rule in df_viktning.iterrows():
                niva = pd.to_numeric(rule.get('Nivå', 0), errors='coerce')
                div = str(rule.get('Division', 'Alla')).strip()
                start = rule['Första_säsnr']
                end = rule['Sista_säsnr']
                
                n_mult = pd.to_numeric(rule.get('Nivå_multiplikator', 1.0), errors='coerce')
                e_mult = pd.to_numeric(rule.get('Epok_multiplikator', 1.0), errors='coerce')
                if np.isnan(n_mult): n_mult = 1.0
                if np.isnan(e_mult): e_mult = 1.0
                
                mask = (master['Säsnr'] >= start) & (master['Säsnr'] <= end)
                if pd.notna(niva) and niva > 0:
                    mask = mask & (master['Nivå'].astype(float) == niva)
                if div != 'Alla' and div != 'nan' and div != '':
                    mask = mask & (master['Division'] == div)
                    
                master.loc[mask, 'Nivå_multiplikator'] = n_mult
                master.loc[mask, 'Epok_multiplikator'] = e_mult

    return master, df_tabeller, df_snabbval

# ==========================================
# 3. HTML DASHBOARD GENERATOR (FLIKAR)
# ==========================================
def export_html_dashboard(df, df_snabbval):
    print("\nSkapar interaktiv flik-baserad HTML-dashboard...")
    
    export_cols = [
        'Startår_Numerisk', 'Säsong', 'Säsnr', 'Säsongsdel', 'Nivå', 'Division', 'Serie', 'Plac', 
        'Analys_Lagnamn', 'Sp', 'V', 'O', 'F', 'Gjorda', 'Insl', 'P', 'Poäng_seger', 'Anm',
        'Giltig_Poängavdrag', 'Poängjustering_Startpoäng', 'Lag_ID', 'Laget i tabell', 'Standard_Lagnamn',
        'Nivå_multiplikator', 'Epok_multiplikator', 'Nya', 'Distrikt', 'Kommun'
    ]
    if 'SM_vinnare' in df.columns:
        export_cols.append('SM_vinnare')
    if 'Bildad' in df.columns:
        export_cols.append('Bildad')
    if 'Namnbyte' in df.columns:
        export_cols.append('Namnbyte')
        
    available_cols = [c for c in export_cols if c in df.columns]
    df_export = df[available_cols].copy()
    
    df_export = df_export.fillna('')
    df_export['Nivå'] = pd.to_numeric(df_export['Nivå'], errors='coerce').fillna(0) 
    df_export = df_export[(df_export['Nivå'] > 0) & (df_export['Nivå'] <= 5)]
    
    json_data = df_export.to_json(orient='records').replace('</script>', '<\/script>')
    
    if df_snabbval is not None and not df_snabbval.empty:
        if 'Fokus' not in df_snabbval.columns:
            df_snabbval['Fokus'] = ''
        json_snabbval = df_snabbval.to_json(orient='records').replace('</script>', '<\/script>')
    else:
        json_snabbval = "[]"
    
    orphans = df_export[df_export['Lag_ID'] == '']['Laget i tabell'].unique().tolist()
    name_changes = []
    grouped_teams = df_export[df_export['Lag_ID'] != ''].groupby('Analys_Lagnamn')
    
    for std_name, group in grouped_teams:
        aliases = group['Laget i tabell'].unique()
        if len(aliases) > 1:
            alias_info = []
            for alias in aliases:
                alias_rows = group[group['Laget i tabell'] == alias]
                if not alias_rows.empty:
                    min_year = int(alias_rows['Startår_Numerisk'].min())
                    max_year = int(alias_rows['Startår_Numerisk'].max())
                    if min_year == max_year: alias_info.append(f"{alias} ({min_year})")
                    else: alias_info.append(f"{alias} ({min_year}-{max_year})")
                else: alias_info.append(alias)
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
    <title>__DASHBOARD_TITLE__</title>
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
<body class="p-2 sm:p-4 md:p-6">

    <div class="max-w-7xl mx-auto bg-white rounded-xl shadow-lg p-4 sm:p-6 relative">
        <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-4">
            <h1 class="text-2xl sm:text-3xl font-bold text-gray-800">__DASHBOARD_TITLE__</h1>
            <button onclick="exportCSV()" class="w-full md:w-auto bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded shadow flex items-center justify-center">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                Ladda ner CSV
            </button>
        </div>

        <!-- TILLBAKA-KNAPP CONTAINER -->
        <div id="backButtonContainer" class="hidden mb-4 bg-indigo-50 border border-indigo-200 p-3 rounded-lg flex flex-col sm:flex-row justify-between items-start sm:items-center shadow-sm gap-3">
            <span class="text-sm text-indigo-800 font-medium" id="backButtonText">Du tittar på ett specifikt urval.</span>
            <button onclick="navigateBack()" class="w-full sm:w-auto bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold py-2 px-4 rounded shadow flex items-center justify-center transition-colors shrink-0">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
                Gå tillbaka
            </button>
        </div>

        <!-- Flik-navigering -->
        <div class="flex overflow-x-auto border-b border-gray-200 mb-6 pb-1 space-x-1 scrollbar-hide">
            <button class="tab-btn active px-3 sm:px-4 py-2 text-gray-600 hover:text-blue-600 focus:outline-none whitespace-nowrap text-xs sm:text-sm md:text-base" onclick="clickMainTab('tab-maraton', this)">Maraton</button>
            <button class="tab-btn px-3 sm:px-4 py-2 text-gray-600 hover:text-blue-600 focus:outline-none whitespace-nowrap text-xs sm:text-sm md:text-base" onclick="clickMainTab('tab-sasong', this)">Serietabeller</button>
            <button class="tab-btn px-3 sm:px-4 py-2 text-gray-600 hover:text-blue-600 focus:outline-none whitespace-nowrap text-xs sm:text-sm md:text-base" onclick="clickMainTab('tab-vandring', this)">Vandringar</button>
            <button class="tab-btn px-3 sm:px-4 py-2 text-gray-600 hover:text-blue-600 focus:outline-none whitespace-nowrap text-xs sm:text-sm md:text-base" onclick="clickMainTab('tab-placering', this)">Placeringsanalys</button>
            <button class="tab-btn px-3 sm:px-4 py-2 text-gray-600 hover:text-blue-600 focus:outline-none whitespace-nowrap text-xs sm:text-sm md:text-base" onclick="clickMainTab('tab-bildad', this)">Klubbålder</button>
            <button class="tab-btn px-3 sm:px-4 py-2 text-gray-600 hover:text-blue-600 focus:outline-none whitespace-nowrap text-xs sm:text-sm md:text-base" onclick="clickMainTab('tab-topp', this)">Topplistor</button>
            <button class="tab-btn px-3 sm:px-4 py-2 text-gray-600 hover:text-blue-600 focus:outline-none whitespace-nowrap text-xs sm:text-sm md:text-base" onclick="clickMainTab('tab-admin', this)">Admin</button>
        </div>

        <!-- ============================================== -->
        <!-- FLIK 1: MARATONTABELL                          -->
        <!-- ============================================== -->
        <div id="tab-maraton" class="tab-content active">
            <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-4 bg-gray-50 p-4 rounded-lg border border-gray-200 items-end">
                <div class="sm:col-span-2 lg:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Sök Lag</label>
                    <input type="text" id="maratonSearch" placeholder="Skriv för att söka..." class="w-full border-gray-300 rounded-md p-2 border" onkeyup="renderMaraton()">
                </div>
                <div class="sm:col-span-2 lg:col-span-1">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Poängsystem</label>
                    <select id="maratonPointsMode" class="w-full border-gray-300 rounded-md p-2 border bg-blue-50 font-medium text-blue-900" onchange="renderMaraton()">
                        <option value="3">3 poäng för seger</option>
                        <option value="2">2 poäng för seger</option>
                        <option value="hist">Historiska poäng (P)</option>
                        <option value="viktad_p">Viktade poäng (Total historik)</option>
                        <option value="viktat_snitt">Viktat poängsnitt (/match)</option>
                    </select>
                </div>
                <div class="sm:col-span-2 lg:col-span-2">
                    <label class="block text-sm font-medium text-blue-700 mb-1">Snabbval (Färdiga Maraton)</label>
                    <select id="maratonSnabbval" class="w-full border-blue-300 bg-blue-50 text-blue-900 font-medium rounded-md p-2 border" onchange="toggleSnabbval()">
                        <option value="Inget">-- Använd egna filter --</option>
                    </select>
                </div>
                <div class="sm:col-span-2 lg:col-span-1">
                    <button class="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded border border-gray-300 transition-colors" onclick="resetFilters('maraton')">
                        Återställ
                    </button>
                </div>
                
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
                    </select>
                </div>
                <div class="sm:col-span-2 lg:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Seriebeteckning (Division)</label>
                    <select id="maratonDivision" class="w-full border-gray-300 rounded-md p-2 border custom-filter" onchange="syncDropdowns('maratonDivision', 'maratonLevel', 'divToLevel'); renderMaraton()">
                        <option value="Alla">-- Alla Beteckningar --</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Visa Tidsperiod</label>
                    <select id="maratonTidsperiod" class="w-full border-gray-300 rounded-md p-2 border" onchange="renderMaraton()">
                        <option value="dold">Dölj (Standard)</option>
                        <option value="full">Första &ndash; Sista säsong</option>
                        <option value="premiar">Endast Premiärsäsong</option>
                    </select>
                </div>
            </div>
            <div class="text-sm text-gray-500 mb-2 flex justify-between">
                <span id="maratonCounter"></span>
                <span class="italic text-xs hidden sm:inline">Tips: Klicka på ett lag för att se deras tabeller.</span>
            </div>
            <div class="table-container border border-gray-200 rounded-lg overflow-x-auto">
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
            <div id="sasongFiltersContainer" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-2 bg-gray-50 p-4 rounded-lg border border-gray-200 items-end transition-opacity">
                <div class="sm:col-span-2 lg:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Välj Säsong</label>
                    <select id="sasongYear" class="w-full border-gray-300 rounded-md p-2 border font-medium" onchange="renderSasong()">
                        <option value="Alla">-- Alla Säsonger --</option>
                    </select>
                </div>
                <div class="sm:col-span-2 lg:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Specifikt Lag (Följ historik)</label>
                    <select id="sasongTeam" class="w-full border-gray-300 rounded-md p-2 border" onchange="handleTeamSelect()">
                        <option value="Alla">-- Alla Lag --</option>
                    </select>
                </div>
                <div class="sm:col-span-2 lg:col-span-2 flex justify-end">
                    <button class="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded border border-gray-300 transition-colors" onclick="resetFilters('sasong')">
                        Återställ & Rensa Allt
                    </button>
                </div>
                <div class="sm:col-span-1 lg:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Filtrera på Nivå</label>
                    <select id="sasongLevel" class="w-full border-gray-300 rounded-md p-2 border" onchange="syncDropdowns('sasongLevel', 'sasongDivision', 'levelToDiv'); renderSasong()">
                        <option value="Alla">-- Alla Nivåer --</option>
                    </select>
                </div>
                <div class="sm:col-span-2 lg:col-span-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Filtrera på Seriebeteckning</label>
                    <select id="sasongDivision" class="w-full border-gray-300 rounded-md p-2 border" onchange="syncDropdowns('sasongDivision', 'sasongLevel', 'divToLevel'); renderSasong()">
                        <option value="Alla">-- Alla Beteckningar --</option>
                    </select>
                </div>
            </div>
            
            <div class="flex flex-col lg:flex-row justify-between items-start lg:items-end mb-2 gap-2">
                <div class="text-sm text-gray-500" id="sasongCounter"></div>
                <div class="text-xs text-gray-600 flex gap-2 flex-wrap bg-white p-2 rounded border border-gray-100 shadow-sm">
                    <span class="flex items-center"><span class="ml-1 px-1 rounded bg-blue-100 text-blue-700 font-bold mr-1 text-[10px]">NY</span> Ny i systemet</span>
                    <span class="flex items-center"><span class="ml-1 px-1 rounded bg-green-100 text-green-700 font-bold mr-1 text-[10px]">NY</span> Uppflyttad hit</span>
                    <span class="flex items-center"><span class="ml-1 px-1 rounded bg-red-100 text-red-700 font-bold mr-1 text-[10px]">D</span> Degraderad hit</span>
                    <span class="flex items-center"><span class="text-yellow-500 font-bold text-lg mr-1 leading-none">&#9733;</span> Första Säsongen</span>
                    <span class="flex items-center"><span class="text-red-500 font-bold text-lg mr-1 leading-none">*</span> Nytt Alias</span>
                    <span class="flex items-center"><span class="text-blue-500 font-bold text-lg mr-1 leading-none">*</span> Återtaget Alias</span>
                    <span class="flex items-center"><span class="text-red-600 font-bold text-lg mr-1 leading-none">!</span> Oväntat Inträde</span>
                    <span class="flex items-center"><span class="w-3 h-3 rounded bg-green-100 border border-green-200 inline-block mr-1 ml-2"></span> Guld/Upp nästa år</span>
                    <span class="flex items-center"><span class="w-3 h-3 rounded bg-red-100 border border-red-200 inline-block mr-1"></span> Ned nästa år</span>
                    <span class="flex items-center"><span class="text-gray-500 font-bold mr-1">▼</span> Naturligt ur systemet</span>
                    <span class="flex items-center"><span class="text-red-600 font-bold mr-1">⚠️</span> Oväntat avhopp</span>
                </div>
            </div>

            <div class="table-container border border-gray-200 rounded-lg overflow-x-auto">
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
            <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-4 bg-gray-50 p-4 rounded-lg border border-gray-200 items-end">
                <div class="sm:col-span-2 lg:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Sök Lag</label>
                    <input type="text" id="vandringSearch" placeholder="Skriv för att söka..." class="w-full border-gray-300 rounded-md p-2 border" onkeyup="renderVandringar()">
                </div>
                <div class="sm:col-span-2 lg:col-span-1">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Fokusera på</label>
                    <select id="vandringMode" class="w-full border-gray-300 rounded-md p-2 border font-medium" onchange="toggleVandringMode()">
                        <option value="niva">Serienivå (Fast trappsteg)</option>
                        <option value="division">Seriebeteckning (Alla)</option>
                        <option value="kombination">Kombination (Snabbval)</option>
                    </select>
                </div>
                <div id="vandringLevelWrapper" class="sm:col-span-2 lg:col-span-1">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Välj Serienivå</label>
                    <select id="vandringLevel" class="w-full border-gray-300 rounded-md p-2 border" onchange="renderVandringar()">
                        <option value="1">Nivå 1</option>
                    </select>
                </div>
                <div id="vandringDivisionWrapper" class="hidden sm:col-span-2 lg:col-span-1">
                    <label class="block text-sm font-medium text-gray-700 mb-1" id="vandringDivisionLabel">Välj Seriebeteckning</label>
                    <select id="vandringDivision" class="w-full border-gray-300 rounded-md p-2 border" onchange="renderVandringar()"></select>
                </div>
                <div id="vandringKombinationWrapper" class="hidden sm:col-span-2 lg:col-span-2">
                    <label class="block text-sm font-medium text-blue-700 mb-1">Välj Fokus-Kombination</label>
                    <select id="vandringKombination" class="w-full border-blue-300 bg-blue-50 rounded-md p-2 border" onchange="renderVandringar()"></select>
                </div>
                <div class="sm:col-span-2 lg:col-span-1">
                    <button class="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded border border-gray-300 transition-colors" onclick="resetFilters('vandring')">
                        Återställ
                    </button>
                </div>
            </div>
            
            <div class="text-sm text-gray-500 mb-2 flex justify-between">
                <span id="vandringCounter">Beräknar sviter och vandringar...</span>
                <span class="italic text-xs hidden sm:inline">Tips: Klicka på ett lag för att se enbart raderna för just den sviten!</span>
            </div>
            <div class="table-container border border-gray-200 rounded-lg overflow-x-auto">
                <table class="min-w-full text-sm text-left whitespace-nowrap" id="vandringTable">
                    <thead class="text-xs text-gray-700 uppercase bg-gray-100" id="vandringHead"></thead>
                    <tbody class="divide-y divide-gray-200" id="vandringBody"></tbody>
                </table>
            </div>
        </div>

        <!-- ============================================== -->
        <!-- FLIK NY: PLACERINGSANALYS                      -->
        <!-- ============================================== -->
        <div id="tab-placering" class="tab-content">
            <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-7 gap-4 mb-4 bg-gray-50 p-4 rounded-lg border border-gray-200 items-end">
                <div class="sm:col-span-2 lg:col-span-1">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Fokusera på</label>
                    <select id="placeringMode" class="w-full border-gray-300 rounded-md p-2 border font-medium" onchange="togglePlaceringType()">
                        <option value="niva">Serienivå (Fast trappsteg)</option>
                        <option value="division">Seriebeteckning (Alla)</option>
                        <option value="kombination">Kombination (Snabbval)</option>
                    </select>
                </div>
                <div id="placeringLevelWrapper" class="sm:col-span-2 lg:col-span-1">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Välj Serienivå</label>
                    <select id="placeringLevel" class="w-full border-gray-300 rounded-md p-2 border" onchange="renderPlacering()">
                        <option value="1">Nivå 1</option>
                    </select>
                </div>
                <div id="placeringDivisionWrapper" class="hidden sm:col-span-2 lg:col-span-1">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Välj Seriebeteckning</label>
                    <select id="placeringDivision" class="w-full border-gray-300 rounded-md p-2 border" onchange="renderPlacering()"></select>
                </div>
                <div id="placeringKombinationWrapper" class="hidden sm:col-span-2 lg:col-span-2">
                    <label class="block text-sm font-medium text-blue-700 mb-1">Välj Fokus-Kombination</label>
                    <select id="placeringKombination" class="w-full border-blue-300 bg-blue-50 rounded-md p-2 border" onchange="renderPlacering()"></select>
                </div>
                <div class="sm:col-span-2 lg:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Typ av Analys</label>
                    <select id="placeringType" class="w-full border-gray-300 rounded-md p-2 border font-medium bg-white" onchange="togglePlaceringType()">
                        <option value="stats">Summerad tabellrad per placering</option>
                        <option value="kedja">Markov-kedja (Före ➔ Nu ➔ Efter)</option>
                        <option value="efter">Framåt (Vad hände året efter?)</option>
                        <option value="fore">Bakåt (Var kom de ifrån?)</option>
                    </select>
                </div>
                <div id="placeringSpecificWrapper" class="hidden sm:col-span-2 lg:col-span-1">
                    <label class="block text-sm font-medium text-blue-700 mb-1">Målplacering</label>
                    <select id="placeringSpecific" class="w-full border-blue-300 bg-blue-50 rounded-md p-2 border font-bold" onchange="renderPlacering()">
                        <!-- Fylls i JS -->
                    </select>
                </div>
                <div class="sm:col-span-2 lg:col-span-1 flex items-center h-full pb-2">
                    <label class="inline-flex items-center cursor-pointer" title="Hoppar över höstsäsonger vid sökningar av sviter/år.">
                        <input type="checkbox" id="placeringEndastVar" class="form-checkbox h-5 w-5 text-blue-600 rounded" onchange="renderPlacering()">
                        <span class="ml-2 text-xs text-gray-700 font-medium">Ignorera<br>höstsäsonger</span>
                    </label>
                </div>
                <div class="sm:col-span-2 lg:col-span-1">
                    <button class="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded border border-gray-300 transition-colors" onclick="resetFilters('placering')">
                        Återställ
                    </button>
                </div>
            </div>
            
            <div class="text-sm text-gray-500 mb-2 flex justify-between">
                <span id="placeringCounter">Beräknar placeringsmatriser...</span>
                <span class="italic text-xs hidden sm:inline" id="placeringTip">Visar en aggregerad bild av olika placeringar i ligasystemet.</span>
            </div>
            <div class="table-container border border-gray-200 rounded-lg overflow-x-auto">
                <table class="min-w-full text-sm text-left whitespace-nowrap" id="placeringTable">
                    <thead class="text-xs text-gray-700 uppercase bg-gray-100" id="placeringHead"></thead>
                    <tbody class="divide-y divide-gray-200" id="placeringBody"></tbody>
                </table>
            </div>
        </div>
        
        <!-- ============================================== -->
        <!-- FLIK NY: KLUBBÅLDER (BILDAD)                   -->
        <!-- ============================================== -->
        <div id="tab-bildad" class="tab-content">
            <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 mb-4 bg-gray-50 p-4 rounded-lg border border-gray-200 items-end">
                <div class="sm:col-span-2 md:col-span-1">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Typ av vy</label>
                    <select id="bildadMode" class="w-full border-gray-300 rounded-md p-2 border font-medium" onchange="renderBildad()">
                        <option value="laglista">Lagsammanställning (Maraton)</option>
                        <option value="niva">Nivåfördelning per Decennium</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Välj Decennium</label>
                    <select id="bildadDecennium" class="w-full border-gray-300 rounded-md p-2 border" onchange="document.getElementById('bildadYear').value='Alla'; renderBildad()">
                        <option value="Alla">-- Alla Decennier --</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Välj Specifikt År</label>
                    <select id="bildadYear" class="w-full border-gray-300 rounded-md p-2 border" onchange="document.getElementById('bildadDecennium').value='Alla'; renderBildad()">
                        <option value="Alla">-- Alla Årtal --</option>
                    </select>
                </div>
                <div>
                    <button class="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-2 px-4 rounded border border-gray-300 transition-colors" onclick="resetFilters('bildad')">
                        Återställ
                    </button>
                </div>
            </div>
            
            <div class="text-sm text-gray-500 mb-2 flex justify-between">
                <span id="bildadCounter">Beräknar historik...</span>
                <span class="italic text-xs hidden sm:inline">Sammanställer historiska resultat baserat på klubbarnas ålder/bildandeår.</span>
            </div>
            <div class="table-container border border-gray-200 rounded-lg overflow-x-auto">
                <table class="min-w-full text-sm text-left whitespace-nowrap" id="bildadTable">
                    <thead class="text-xs text-gray-700 uppercase bg-gray-100" id="bildadHead"></thead>
                    <tbody class="divide-y divide-gray-200" id="bildadBody"></tbody>
                </table>
            </div>
        </div>

        <!-- ============================================== -->
        <!-- FLIK 4: TOPPLISTOR                             -->
        <!-- ============================================== -->
        <div id="tab-topp" class="tab-content">
            <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-4 bg-gray-50 p-4 rounded-lg border border-gray-200 items-end">
                <div class="sm:col-span-2 lg:col-span-2">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Analyskategori</label>
                    <select id="toppCategory" class="w-full border-gray-300 rounded-md p-2 border bg-white font-semibold" onchange="updateToppMetrics()">
                        <option value="sasong">Bästa/Sämsta enskilda säsong</option>
                        <option value="maraton">Maratontotalt (Hela historiken)</option>
                        <option value="vandring">Serievandringar & Jojolag</option>
                        <option value="nya_lag">Nya Lag i Systemet</option>
                        <option value="handelser">Händelser (Oväntade & Förväntade)</option>
                        <option value="distrikt">Distriktstabeller</option>
                        <option value="kommun">Kommuntabeller</option>
                    </select>
                </div>
                <div class="sm:col-span-1 lg:col-span-1">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Mätvärdestyp</label>
                    <select id="toppMetricType" class="w-full border-gray-300 rounded-md p-2 border bg-white" onchange="updateToppMetrics()">
                        <option value="abs">Absoluta tal</option>
                        <option value="kvot">Kvoter (/match)</option>
                    </select>
                </div>
                <div class="sm:col-span-2 lg:col-span-3">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Mätvärde att visa</label>
                    <select id="toppMetric" class="w-full border-gray-300 rounded-md p-2 border bg-white" onchange="renderTopplistor()"></select>
                </div>
                
                <div class="sm:col-span-1 lg:col-span-1">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Serienivå</label>
                    <select id="toppLevel" class="w-full border-gray-300 rounded-md p-2 border bg-white" onchange="renderTopplistor()">
                        <option value="Alla">-- Alla Nivåer --</option>
                    </select>
                </div>
                <div class="sm:col-span-1 lg:col-span-1">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Antal resultat</label>
                    <select id="toppCount" class="w-full border-gray-300 rounded-md p-2 border bg-white" onchange="renderTopplistor()">
                        <option value="10">Topp 10</option>
                        <option value="15">Topp 15</option>
                        <option value="20">Topp 20</option>
                        <option value="25">Topp 25</option>
                        <option value="999999">Alla</option>
                    </select>
                </div>
                <div class="sm:col-span-2 lg:col-span-4 flex items-center h-full pb-2">
                    <label class="inline-flex items-center cursor-pointer">
                        <input type="checkbox" id="toppUnique" class="form-checkbox h-5 w-5 text-blue-600 rounded" onchange="renderTopplistor()" checked>
                        <span class="ml-2 text-sm text-gray-700 font-medium">Endast unika lag <span class="font-normal text-gray-500 hidden sm:inline">(Bocka ur för att se lagets alla sviter/säsonger separat)</span></span>
                    </label>
                </div>
            </div>
            
            <div class="text-sm text-gray-500 mb-2 flex justify-between">
                <span id="toppCounter">Beräknar topplista...</span>
            </div>
            <div class="table-container border border-gray-200 rounded-lg overflow-x-auto">
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
            <div class="bg-blue-50 border border-blue-200 p-4 rounded-lg shadow-sm mb-6 relative">
                <button onclick="runLocalPythonScript()" class="hidden md:block absolute top-4 right-4 bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded shadow text-sm">
                    Instruktion: Uppdatera Data
                </button>
                <h3 class="text-blue-800 font-bold mb-2 flex items-center">
                    <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path></svg>
                    Systemlogik & Avancerad Analys
                </h3>
                <p class="text-sm text-blue-900 mb-2">Denna dashboard drivs av en skräddarsydd python-motor som säkerställer perfekt kvalitet:</p>
                <ul class="list-disc pl-5 text-sm text-blue-900 space-y-1">
                    <li><strong>Uppdatering av data:</strong> När du har ändrat i din Excel-fil, dubbelklicka på <code>uppdatera_dashboard.bat</code> i din mapp på datorn. När den svarta rutan säger "Klar", ladda om denna webbsida (F5) så är din dashboard uppdaterad!</li>
                    <li><strong>Markov-kedjor (Placeringsmatriser):</strong> Avancerad statistisk modell som spårar övergångssannolikheter. I fliken <i>Placeringsanalys</i> kan du välja en placering och följa varifrån lagen kom (År -1), och vart de tog vägen (År +1). Diagonaler (samma placering) markeras med blå färg.</li>
                    <li><strong>Viktningstabeller:</strong> Systemet stöder dynamisk upp-/nedskalning av poäng över olika epoker för att skapa rättvisa "Pound-for-Pound"-jämförelser i Maratontabellen. Läs mer i din Excel-fil!</li>
                    <li><strong>Kronologisk exakthet (Säsnr):</strong> Vår/Höst-serier hanteras med 100% precision. Ordet "Normal" i kolumnen <i>Anm</i> i Excel tvingar dessutom systemet att ignorera varningar vid serieomläggningar (t.ex. 1946/47).</li>
                </ul>
                <button onclick="runLocalPythonScript()" class="md:hidden mt-4 w-full bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded shadow text-sm">
                    Instruktion: Uppdatera Data
                </button>
            </div>
            
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 h-full">
                <!-- Vänster kolumn -->
                <div class="flex flex-col gap-6">
                    <div class="bg-gray-50 p-6 rounded-lg border border-gray-200 shadow-sm">
                        <h2 class="text-lg font-bold text-gray-800 mb-4">Databasens Hälsa (Nivå 1-5)</h2>
                        <ul class="space-y-3 text-sm text-gray-700" id="adminStatsList"></ul>
                    </div>
                    
                    <div class="bg-red-50 p-6 rounded-lg border border-red-200 shadow-sm flex-grow">
                        <h2 class="text-lg font-bold text-red-800 mb-2">Data-varningar (Matematikfel)</h2>
                        <p class="text-xs text-red-600 mb-3">Rader där Vunna + Oavgjorda + Förlorade INTE är lika med Spelade matcher.</p>
                        <div class="h-48 overflow-y-auto bg-white p-3 rounded border border-red-200">
                            <ul class="space-y-2 text-sm text-gray-800" id="adminMathErrors"></ul>
                        </div>
                    </div>
                    
                    <div class="bg-red-50 p-6 rounded-lg border border-red-200 shadow-sm">
                        <h2 class="text-lg font-bold text-red-800 mb-2">Föräldralösa lag (Saknar Alias)</h2>
                        <div class="max-h-48 overflow-y-auto bg-white p-3 rounded border border-red-100">
                            <ul class="list-disc pl-5 text-sm text-gray-800" id="adminOrphansList"></ul>
                        </div>
                    </div>
                </div>

                <!-- Höger kolumn -->
                <div class="flex flex-col h-full bg-gray-50 p-6 rounded-lg border border-gray-200 shadow-sm">
                    <h2 class="text-lg font-bold text-gray-800 mb-2">Registrerade Namnbyten</h2>
                    <p class="text-xs text-gray-500 mb-3">Lag som har haft flera olika inskrivna namn i nationellt seriespel.</p>
                    <div class="flex-grow overflow-y-auto bg-white p-3 rounded border border-gray-200" style="min-height: 400px;">
                        <ul class="space-y-2 text-sm text-gray-800" id="adminNameChanges"></ul>
                    </div>
                </div>
            </div>
        </div>

    </div>

    <!-- MODAL FÖR KÖR SKRIPT -->
    <div id="scriptModal" class="fixed inset-0 bg-black bg-opacity-50 z-50 hidden flex items-center justify-center p-4">
        <div class="bg-white rounded-lg p-6 max-w-md mx-auto shadow-xl">
            <h2 class="text-xl font-bold text-gray-800 mb-4">Säkerhetsspärr för webbläsare</h2>
            <p class="text-gray-600 mb-4 text-sm">
                Av säkerhetsskäl tillåter inte webbläsare att hemsidor kör program direkt på din dator.
                För att uppdatera dashboarden med din senaste Excel-data gör du så här:
            </p>
            <ol class="list-decimal pl-5 text-sm text-gray-700 mb-6 space-y-2 font-medium">
                <li>Stäng eller spara din Excel-fil.</li>
                <li>Öppna mappen på din dator där filerna ligger.</li>
                <li>Dubbelklicka på filen <span class="font-bold text-blue-600">uppdatera_dashboard.bat</span></li>
                <li>När den svarta rutan säger "Allt klart!", stäng rutan.</li>
                <li>Ladda om den här webbsidan (Tryck F5 eller Uppdatera-knappen i webbläsaren).</li>
            </ol>
            <div class="flex justify-end">
                <button onclick="document.getElementById('scriptModal').classList.add('hidden')" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded transition-colors">Jag förstår!</button>
            </div>
        </div>
    </div>

    <!-- DATA INJECTION OCH LOGIK -->
    <script>
        const rawMatchData = __JSON_DATA__;
        const snabbvalData = __SNABBVAL_JSON__;
        const adminData = __ADMIN_JSON__;
        const ongoingSeason = __ONGOING_SEASON__;
        const useSMVinnare = __USE_SM_VINNARE__ === 'true';
        let currentTabId = 'tab-maraton';
        
        // --- NAVIGATION STATE MEMORY ---
        let navHistory = { sourceTab: null, sasnrFilter: null, teamFilter: null };
        
        // 1. KARTLÄGG BEROENDEN OCH HÄMTA MAXNIVÅER
        const levelDivMap = { levels: {}, divs: {} };
        const teamSasnrLevel = {}; 
        const maxLevelPerSasnr = {}; 
        const snabbvalMap = {};
        const focusMap = {}; 
        const aliasFirstAppearance = {};
        const teamFirstAppearance = {};
        window.teamDataLookup = {}; // Lookup för Placeringsanalys
        
        snabbvalData.forEach(row => {
            let name = row.Benämning;
            if(!snabbvalMap[name]) snabbvalMap[name] = [];
            let sista = (row.Sista_säsnr === 'Senaste') ? 999999 : (parseInt(row.Sista_säsnr) || 999999);
            let obj = { niva: parseFloat(row.Nivå) || 0, div: row.Division, start: parseInt(row.Första_säsnr) || 0, end: sista };
            snabbvalMap[name].push(obj);
            
            if(row.Fokus && String(row.Fokus).toLowerCase() === 'f') {
                if(!focusMap[name]) focusMap[name] = [];
                focusMap[name].push(obj);
            }
        });

        // 1. SORTERA DATA KRONOLOGISKT OCH ENLIGT SÄSONGSDEL FÖR EXAKTA BERÄKNINGAR
        rawMatchData.sort((a,b) => {
            let aS = parseInt(a.Säsnr) || 0, bS = parseInt(b.Säsnr) || 0;
            let aSd = parseInt(a.Säsongsdel) || 0, bSd = parseInt(b.Säsongsdel) || 0;
            let aN = parseFloat(a.Nivå) || 0, bN = parseFloat(b.Nivå) || 0;
            return aS - bS || aSd - bSd || aN - bN;
        });

        let maxGlobalSasnr = 0;
        rawMatchData.forEach(d => {
            let sasnr = parseInt(d.Säsnr) || 0;
            let lvl = String(d.Nivå).trim();
            let div = String(d.Division || '').trim();
            let alias = d['Laget i tabell'];
            let tName = d.Analys_Lagnamn;
            
            if(lvl && div) {
                if(!levelDivMap.levels[lvl]) levelDivMap.levels[lvl] = new Set();
                levelDivMap.levels[lvl].add(div);
                if(!levelDivMap.divs[div]) levelDivMap.divs[div] = new Set();
                levelDivMap.divs[div].add(lvl);
            }
            
            if(!teamSasnrLevel[tName]) teamSasnrLevel[tName] = {};
            if(teamSasnrLevel[tName][sasnr]) {
                teamSasnrLevel[tName][sasnr] = Math.min(teamSasnrLevel[tName][sasnr], parseFloat(d.Nivå) || 0);
            } else {
                teamSasnrLevel[tName][sasnr] = parseFloat(d.Nivå) || 0;
            }
            
            if(!maxLevelPerSasnr[sasnr] || (parseFloat(d.Nivå)||0) > maxLevelPerSasnr[sasnr]) {
                maxLevelPerSasnr[sasnr] = parseFloat(d.Nivå) || 0;
            }
            if(sasnr > maxGlobalSasnr) maxGlobalSasnr = sasnr;
            
            if(!aliasFirstAppearance[alias] || sasnr < aliasFirstAppearance[alias]) aliasFirstAppearance[alias] = sasnr;
            if(!teamFirstAppearance[tName] || sasnr < teamFirstAppearance[tName]) teamFirstAppearance[tName] = sasnr;
            
            if(!window.teamDataLookup[tName]) window.teamDataLookup[tName] = {};
            if(!window.teamDataLookup[tName][sasnr]) window.teamDataLookup[tName][sasnr] = [];
            window.teamDataLookup[tName][sasnr].push(d);
        });

        // 2. ENRICHMENT ENGINE: BERÄKNA BADGES OCH UPP/NED PER RAD BASERAT PÅ RAW HISTORY
        const teamState = {};
        const matchData = rawMatchData.map(d => {
            let row = { ...d };
            let t = row.Analys_Lagnamn;
            let sasnr = parseInt(row.Säsnr) || 0;
            let alias = row['Laget i tabell'];
            let d_niva = parseFloat(row.Nivå) || 0;
            let maxLvl = maxLevelPerSasnr[sasnr] ? Math.floor(maxLevelPerSasnr[sasnr]) : 99;
            let isNormalOverride = (row.Anm && String(row.Anm).toLowerCase().includes('normal'));

            if(!teamState[t]) {
                teamState[t] = { seenAliases: new Set([alias]), lastAlias: alias, lastSasnr: sasnr, lastLvl: d_niva };
                row.AliasBadge = 'first_ever';
                if (sasnr > 5 && d_niva < maxLvl && !isNormalOverride) row.EntryBadge = 'unexp_in';
                else row.EntryBadge = 'normal_in';
                row.Movement = 'new';
            } else {
                let state = teamState[t];
                
                if (alias !== state.lastAlias) {
                    if (state.seenAliases.has(alias)) row.AliasBadge = 'reverted'; 
                    else { row.AliasBadge = 'new_alias'; state.seenAliases.add(alias); } 
                    state.lastAlias = alias;
                } else {
                    row.AliasBadge = '';
                }

                if (sasnr - state.lastSasnr > 1) {
                    if (d_niva < maxLvl && !isNormalOverride) row.EntryBadge = 'unexp_in';
                    else row.EntryBadge = 'normal_in';
                    row.Movement = 'new';
                } else {
                    row.EntryBadge = '';
                    if (state.lastLvl > d_niva) row.Movement = 'promoted';
                    else if (state.lastLvl < d_niva) row.Movement = 'relegated';
                    else row.Movement = 'same';
                }

                state.lastSasnr = sasnr;
                state.lastLvl = d_niva;
            }
            return row;
        });

        // Efterberäkning för Exits (kikar framåt för exit) OCH RowEvent_In/Out (för nya listor)
        Object.keys(teamState).forEach(t => {
            let tRows = matchData.filter(d => d.Analys_Lagnamn === t);
            for(let i=0; i<tRows.length; i++) {
                let curr = tRows[i];
                let next = (i < tRows.length - 1) ? tRows[i+1] : null;
                let c_sasnr = parseInt(curr.Säsnr) || 0;
                let n_sasnr = next ? (parseInt(next.Säsnr) || 0) : maxGlobalSasnr;
                let gap = next ? (n_sasnr - c_sasnr) : (maxGlobalSasnr - c_sasnr);
                
                let c_niva = parseFloat(curr.Nivå) || 0;
                let maxLvl = maxLevelPerSasnr[c_sasnr] ? Math.floor(maxLevelPerSasnr[c_sasnr]) : 99;
                let isNormalOverride = (curr.Anm && String(curr.Anm).toLowerCase().includes('normal'));

                if (gap > 1) {
                    if (c_niva < maxLvl && !isNormalOverride) curr.ExitBadge = 'unexp_out';
                    else curr.ExitBadge = 'normal_out';
                } else {
                    curr.ExitBadge = '';
                }
                
                // RowEvent_In (Definierar hur laget anlände till säsongen)
                let isNykomlingExplicit = curr.Nya ? String(curr.Nya).toLowerCase().includes('nykomling') : false;
                if (c_sasnr === 1) {
                    curr.RowEvent_In = isNykomlingExplicit ? 'NY' : '-';
                } else {
                    if (curr.Movement === 'new' || curr.Movement === 'promoted' || curr.EntryBadge === 'normal_in') curr.RowEvent_In = 'NY';
                    else if (curr.Movement === 'relegated') curr.RowEvent_In = 'D';
                    else curr.RowEvent_In = '-';
                }
                
                // RowEvent_Out (Definierar hur laget lämnade säsongen)
                let nextSasnrLvl = (teamSasnrLevel[t] || {})[c_sasnr + 1];
                let isGuld = false;
                if (useSMVinnare) {
                    let smV = curr.SM_vinnare ? String(curr.SM_vinnare).trim() : '';
                    if (smV && smV !== '..' && smV !== 'nan') {
                        if (curr.Analys_Lagnamn === smV || curr.Standard_Lagnamn === smV || curr['Laget i tabell'] === smV) isGuld = true;
                    }
                } else {
                    let pNum = parseInt(String(curr.Plac).replace(/\D/g, '')) || 999;
                    if (c_niva === 1 && pNum === 1) isGuld = true;
                }

                if (curr.ExitBadge === 'unexp_out') {
                    curr.RowEvent_Out = '-';
                } else if (curr.ExitBadge === 'normal_out') {
                    curr.RowEvent_Out = 'NED';
                } else {
                    if (isGuld) {
                        curr.RowEvent_Out = 'UPP';
                    } else if (nextSasnrLvl !== undefined && nextSasnrLvl !== null) {
                        let nLvl = parseFloat(nextSasnrLvl);
                        if (nLvl < c_niva) curr.RowEvent_Out = 'UPP';
                        else if (nLvl > c_niva) curr.RowEvent_Out = 'NED';
                        else curr.RowEvent_Out = '-';
                    } else {
                        curr.RowEvent_Out = '-';
                    }
                }
            }
        });

        // 3. SKAPA HJÄLP-ARRAYS SÄKERT
        const uniqueSeasonsObj = [];
        const seenSeasons = new Set();
        matchData.forEach(d => {
            if(!seenSeasons.has(d.Säsong)) {
                seenSeasons.add(d.Säsong);
                uniqueSeasonsObj.push({ sStr: d.Säsong, sNum: parseFloat(d.Startår_Numerisk) || 0 });
            }
        });
        uniqueSeasonsObj.sort((a,b) => a.sNum - b.sNum);

        const allYears = [...new Set(matchData.map(d => parseInt(d.Startår_Numerisk)))].filter(y => !isNaN(y) && y > 0).sort((a,b) => a-b);
        const completedYears = ongoingSeason ? allYears.filter(y => y < ongoingSeason) : allYears;
        const completedMatchData = matchData.filter(d => {
            let yr = parseFloat(d.Startår_Numerisk) || 0;
            return completedYears.includes(yr);
        });
        const completedSeasonsObj = ongoingSeason ? uniqueSeasonsObj.filter(seq => seq.sNum < ongoingSeason) : uniqueSeasonsObj;
        
        const allDivisions = [...new Set(matchData.map(d => d.Division))].filter(Boolean).sort((a,b) => String(a).localeCompare(String(b)));
        const allTeams = [...new Set(matchData.map(d => d.Analys_Lagnamn))].filter(Boolean).sort((a,b) => String(a).localeCompare(String(b)));
        const allLevels = [...new Set(matchData.map(d => Number(d.Nivå)))].filter(n => n > 0 && !isNaN(n)).sort((a,b) => a-b);
        
        // --- KLUBBÅLDER (BILDAD) SETUP ---
        const allBildadYearsSet = new Set();
        const allDecadesSet = new Set();
        completedMatchData.forEach(d => {
            let bildadRaw = d.Bildad || '';
            let yMatch = String(bildadRaw).match(/(\d{4})/);
            if (yMatch) {
                let yNum = parseInt(yMatch[1]);
                if(yNum > 1800 && yNum <= new Date().getFullYear()) {
                    allBildadYearsSet.add(yNum);
                    allDecadesSet.add(Math.floor(yNum / 10) * 10);
                }
            }
        });
        const allBildadYears = [...allBildadYearsSet].sort((a,b) => a-b);
        const allDecades = [...allDecadesSet].sort((a,b) => a-b);

        // Definitioner för Topplistor
        const toppMetrics = {
            'sasong': {
                'abs': [
                    {id: 'p_max', text: 'Flest Poäng'},
                    {id: 'p_min', text: 'Minst Poäng (Minst 10 sp)'},
                    {id: 'v_max', text: 'Flest Vunna Matcher'},
                    {id: 'v_min', text: 'Minst Vunna Matcher (Minst 10 sp)'},
                    {id: 'f_max', text: 'Flest Förlorade Matcher'},
                    {id: 'f_min', text: 'Minst Förlorade Matcher (Minst 10 sp)'},
                    {id: 'gj_max', text: 'Flest Gjorda Mål'},
                    {id: 'gj_min', text: 'Minst Gjorda Mål (Minst 10 sp)'},
                    {id: 'insl_max', text: 'Flest Insläppta Mål'},
                    {id: 'insl_min', text: 'Minst Insläppta Mål (Minst 10 sp)'}
                ],
                'kvot': [
                    {id: 'viktat_snitt_max', text: 'Bäst Viktat Poängsnitt (Enskild säsong, Minst 10 sp)'},
                    {id: 'p_snitt_max', text: 'Bäst Poängsnitt (Standardiserat 3p, Minst 10 sp)'},
                    {id: 'p_snitt_min', text: 'Sämst Poängsnitt (Standardiserat 3p, Minst 10 sp)'},
                    {id: 'gj_snitt_max', text: 'Högst Målsnitt framåt (Minst 10 sp)'},
                    {id: 'insl_snitt_max', text: 'Högst Målsnitt bakåt (Minst 10 sp)'}
                ]
            },
            'maraton': {
                'abs': [
                    {id: 'viktad_p_max', text: 'Flest Viktade Poäng Totalt (Index)'},
                    {id: 'p_max', text: 'Flest Poäng Totalt'},
                    {id: 'v_max', text: 'Flest Vunna Matcher Totalt'},
                    {id: 'f_max', text: 'Flest Förlorade Matcher Totalt'},
                    {id: 'gj_max', text: 'Flest Gjorda Mål Totalt'},
                    {id: 'sasong_max', text: 'Flest Spelade Säsonger'}
                ],
                'kvot': [
                    {id: 'viktat_snitt_max', text: 'Bäst Viktat Poängsnitt (Total Historik, Minst 30 sp)'},
                    {id: 'p_snitt_max', text: 'Bäst Poängsnitt Konventionellt (Minst 30 sp)'}
                ]
            },
            'vandring': {
                'abs': [
                    {id: 'jojo_max', text: 'Mest Pendlande lag (Flest totala upp+ned)'},
                    {id: 'studs_max', text: 'Största "Hiss-lag" (Flest direkta jojo-studsar året efter)'},
                    {id: 'upp_max', text: 'Flest totala uppflyttningar (inom systemet)'},
                    {id: 'ned_max', text: 'Flest totala nedflyttningar (inom systemet)'},
                    {id: 'svit_max', text: 'Längsta obrutna svit (säsonger i rad)'},
                    {id: 'klattring_max', text: 'Flest på varandra följande avancemang (säsonger i rad)'},
                    {id: 'ras_max', text: 'Flest på varandra följande degraderingar (säsonger i rad)'},
                    {id: 'krono_ny_upp', text: 'Nykomlingar som omedelbart avancerat (Kronologiskt)'},
                    {id: 'krono_ny_ned', text: 'Nykomlingar som omedelbart degraderats (Kronologiskt)'},
                    {id: 'krono_d_upp', text: 'Nedflyttade som omedelbart avancerat (Kronologiskt)'},
                    {id: 'krono_d_ned', text: 'Nedflyttade som omedelbart degraderats (Kronologiskt)'}
                ],
                'kvot': []
            },
            'nya_lag': {
                'abs': [
                    {id: 'nya_antal', text: 'Antal Nya Lag per Säsong (Sorterat på antal)'},
                    {id: 'nya_antal_krono', text: 'Antal Nya Lag per Säsong (Kronologiskt)'},
                    {id: 'nya_krono', text: 'Alla Nya Lag (Kronologisk lista)'}
                ],
                'kvot': []
            },
            'handelser': {
                'abs': [
                    {id: 'norm_upp_max', text: 'Uppflyttningar INOM systemet (Förväntade)'},
                    {id: 'norm_ned_max', text: 'Nedflyttningar INOM systemet (Förväntade)'},
                    {id: 'in_max', text: 'Upp FRÅN distriktsserier (Förväntade)'},
                    {id: 'ut_max', text: 'Ned TILL distriktsserier (Förväntade)'},
                    {id: 'ovan_ut_max', text: 'Oväntade avhopp ur systemet (⚠️ Från för hög nivå)'},
                    {id: 'ovan_in_max', text: 'Oväntade inträden i systemet (! Till för hög nivå)'}
                ],
                'kvot': []
            },
            'distrikt': {
                'abs': [
                    {id: 'p_max', text: 'Flest Poäng Totalt'},
                    {id: 'gj_max', text: 'Flest Gjorda Mål Totalt'},
                    {id: 'lag_max', text: 'Flest Unika Lag i Systemet'}
                ],
                'kvot': [
                    {id: 'p_snitt_max', text: 'Bäst Poängsnitt (/match)'}
                ]
            },
            'kommun': {
                'abs': [
                    {id: 'p_max', text: 'Flest Poäng Totalt'},
                    {id: 'gj_max', text: 'Flest Gjorda Mål Totalt'},
                    {id: 'lag_max', text: 'Flest Unika Lag i Systemet'}
                ],
                'kvot': [
                    {id: 'p_snitt_max', text: 'Bäst Poängsnitt (/match)'}
                ]
            }
        };

        function populateDropdown(selectId, dataArray, reverse=false, defaultLast=false, isLevels=false) {
            try {
                const select = document.getElementById(selectId);
                if(!select || !dataArray) return;
                
                let hasPlaceholder = select.options.length > 0 && select.options[0].value.includes('Alla');
                let placeholderHTML = hasPlaceholder ? select.options[0].outerHTML : '';
                
                select.innerHTML = placeholderHTML;
                let displayData = reverse ? [...dataArray].reverse() : dataArray;
                
                displayData.forEach(item => {
                    if (item === undefined || item === null) return;
                    let opt = document.createElement('option');
                    opt.value = item;
                    if(selectId === 'bildadDecennium' && item !== 'Alla') opt.innerHTML = item + "-talet";
                    else opt.innerHTML = isLevels ? `Nivå ${item}` : item;
                    select.appendChild(opt);
                });
                
                if(defaultLast && dataArray.length > 0) {
                    select.value = dataArray[dataArray.length - 1];
                } else if(!hasPlaceholder && dataArray.length > 0) {
                    select.value = dataArray[0];
                }
            } catch (e) {
                console.error("Error populating dropdown:", selectId, e);
            }
        }

        function syncDropdowns(changedSelectId, targetSelectId, mapType) {
            try {
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
                if(options.length === 0) return;
                
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
                    if (a.dataset.valid !== b.dataset.valid) return String(b.dataset.valid).localeCompare(String(a.dataset.valid));
                    return String(a.text).localeCompare(String(b.text));
                });

                targetSelect.innerHTML = '';
                targetSelect.appendChild(allaOption);
                options.forEach(opt => targetSelect.appendChild(opt));

                if (targetSelect.options[targetSelect.selectedIndex] && targetSelect.options[targetSelect.selectedIndex].disabled) {
                    targetSelect.value = 'Alla';
                }
            } catch(e) {
                console.error("Sync error:", e);
            }
        }

        function resetSelect(selectId) {
            try {
                let select = document.getElementById(selectId);
                if(!select) return;
                
                let hasPlaceholder = select.options.length > 0 && select.options[0].value.includes('Alla');
                let options = Array.from(select.options);
                if(options.length === 0) return;
                
                let first = hasPlaceholder ? options.shift() : null;
                
                options.forEach(opt => {
                    opt.disabled = false;
                    opt.style.color = "";
                    opt.dataset.valid = "1";
                });
                options.sort((a,b) => String(a.text).localeCompare(String(b.text)));
                
                select.innerHTML = '';
                if(first) {
                    select.appendChild(first);
                    select.value = first.value;
                } else if (options.length > 0) {
                    select.value = options[0].value;
                }
                options.forEach(opt => select.appendChild(opt));
            } catch(e) {
                console.error("Reset error:", e);
            }
        }

        function toggleSnabbval() {
            const useSnabbval = document.getElementById('maratonSnabbval').value !== 'Inget';
            let filters = document.querySelectorAll('.custom-filter');
            filters.forEach(el => { el.disabled = useSnabbval; });
            renderMaraton();
        }

        function resetFilters(tab) {
            if (tab === 'maraton') {
                document.getElementById('maratonSearch').value = '';
                document.getElementById('maratonPointsMode').value = '3';
                document.getElementById('maratonSnabbval').value = 'Inget';
                document.getElementById('maratonStartYear').value = String(completedYears[0] || '');
                document.getElementById('maratonEndYear').value = String(completedYears[completedYears.length - 1] || '');
                document.getElementById('maratonTidsperiod').value = 'dold';
                
                populateDropdown('maratonLevel', allLevels, false, false, true);
                populateDropdown('maratonDivision', allDivisions);
                document.getElementById('maratonLevel').value = 'Alla';
                document.getElementById('maratonDivision').value = 'Alla';
                syncDropdowns('maratonLevel', 'maratonDivision', 'levelToDiv');
                
                toggleSnabbval();
                renderMaraton();
            } else if (tab === 'sasong') {
                navHistory.sasnrFilter = null; 
                document.getElementById('sasongFiltersContainer').classList.remove('opacity-50', 'pointer-events-none');
                
                let sy = document.getElementById('sasongYear');
                if(sy.options.length > 1) sy.value = sy.options[1].value; 
                document.getElementById('sasongTeam').value = 'Alla';
                
                populateDropdown('sasongLevel', allLevels, false, false, true);
                populateDropdown('sasongDivision', allDivisions);
                document.getElementById('sasongLevel').value = 'Alla';
                document.getElementById('sasongDivision').value = 'Alla';
                syncDropdowns('sasongLevel', 'sasongDivision', 'levelToDiv');
                
                document.getElementById('backButtonContainer').classList.add('hidden');
                renderSasong();
            } else if (tab === 'vandring') {
                document.getElementById('vandringSearch').value = '';
                document.getElementById('vandringMode').value = 'niva';
                
                populateDropdown('vandringLevel', allLevels, false, false, true);
                populateDropdown('vandringDivision', allDivisions);
                if(allLevels.length > 0) document.getElementById('vandringLevel').value = allLevels.includes(1) ? '1' : String(allLevels[0]);
                let vd = document.getElementById('vandringDivision');
                if (vd.options.length > 1) vd.value = vd.options[1].value;
                
                toggleVandringMode();
            } else if (tab === 'placering') {
                document.getElementById('placeringMode').value = 'kombination';
                document.getElementById('placeringEndastVar').checked = false;
                
                populateDropdown('placeringLevel', allLevels, false, false, true);
                populateDropdown('placeringDivision', allDivisions);
                
                let pk = document.getElementById('placeringKombination');
                if(Array.from(pk.options).some(opt => opt.value === 'Allsvenskan')) pk.value = 'Allsvenskan';
                else if(pk.options.length > 1) pk.value = pk.options[1].value;
                
                document.getElementById('placeringType').value = 'stats';
                let specSel = document.getElementById('placeringSpecific');
                if(specSel.options.length > 0) specSel.value = '1';
                
                togglePlaceringType();
            } else if (tab === 'bildad') {
                document.getElementById('bildadMode').value = 'laglista';
                document.getElementById('bildadDecennium').value = 'Alla';
                document.getElementById('bildadYear').value = 'Alla';
                renderBildad();
            }
        }

        // SMART LÄNK: HOPPA TILL SERIETABELLER MED KONTEXT OCH NAMN-HISTORIK
        function showTeamHistory(teamName, sourceTab, sasnrStr = '') {
            navHistory.sourceTab = sourceTab;
            navHistory.sasnrFilter = sasnrStr ? sasnrStr.split(',').map(Number) : null;
            navHistory.teamFilter = teamName;
            
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-sasong').classList.add('active');
            document.querySelector('.tab-btn[onclick*="tab-sasong"]').classList.add('active');
            currentTabId = 'tab-sasong';
            
            let bb = document.getElementById('backButtonContainer');
            let bt = document.getElementById('backButtonText');
            bb.classList.remove('hidden');
            
            // --- BYGG UPP NAMNHISTORIK (ALIASES + NAMNBYTE-KOLUMN) ---
            let aliasStr = "";
            let teamNameChanges = adminData.name_changes.find(n => n.standard === teamName);
            if(teamNameChanges && teamNameChanges.aliases.length > 1) {
                aliasStr += `<br><span class="text-xs text-indigo-600 font-normal">Namnhistorik (i tabellerna): ${teamNameChanges.aliases.join(', ')}</span>`;
            }
            
            let explicitNamnbyte = new Set();
            completedMatchData.filter(d => d.Analys_Lagnamn === teamName && d.Namnbyte).forEach(d => explicitNamnbyte.add(d.Namnbyte));
            if(explicitNamnbyte.size > 0) {
                aliasStr += `<br><span class="text-xs text-purple-600 font-normal">Tidigare / Andra namn: ${Array.from(explicitNamnbyte).join(' | ')}</span>`;
            }
            // --------------------------------------------------------
            
            if(navHistory.sasnrFilter) {
                bt.innerHTML = `Du detaljgranskar specifika säsonger för <b>${teamName}</b>.${aliasStr}`;
                document.getElementById('sasongFiltersContainer').classList.add('opacity-50', 'pointer-events-none');
            } else {
                bt.innerHTML = `Du tittar på hela historiken för <b>${teamName}</b>.${aliasStr}`;
                document.getElementById('sasongFiltersContainer').classList.remove('opacity-50', 'pointer-events-none');
            }
            
            document.getElementById('sasongTeam').value = teamName;
            document.getElementById('sasongYear').value = 'Alla'; 
            
            if(!navHistory.sasnrFilter) {
                if (sourceTab === 'maraton') {
                    let snabbval = document.getElementById('maratonSnabbval').value;
                    if(snabbval === 'Inget') {
                        document.getElementById('sasongLevel').value = document.getElementById('maratonLevel').value;
                        document.getElementById('sasongDivision').value = document.getElementById('maratonDivision').value;
                    } else {
                        document.getElementById('sasongLevel').value = 'Alla';
                        document.getElementById('sasongDivision').value = 'Alla';
                    }
                } else if (sourceTab === 'vandring') {
                    if(document.getElementById('vandringMode').value === 'niva') {
                        document.getElementById('sasongLevel').value = document.getElementById('vandringLevel').value;
                        document.getElementById('sasongDivision').value = 'Alla';
                    } else if(document.getElementById('vandringMode').value === 'division') {
                        document.getElementById('sasongLevel').value = 'Alla';
                        document.getElementById('sasongDivision').value = document.getElementById('vandringDivision').value;
                    } else {
                        document.getElementById('sasongLevel').value = 'Alla';
                        document.getElementById('sasongDivision').value = 'Alla';
                    }
                } else if (sourceTab === 'topp' || sourceTab === 'placering' || sourceTab === 'bildad') {
                    document.getElementById('sasongLevel').value = 'Alla';
                    document.getElementById('sasongDivision').value = 'Alla';
                }
            }
            
            syncDropdowns('sasongLevel', 'sasongDivision', 'levelToDiv');
            renderSasong();
        }

        function navigateBack() {
            document.getElementById('backButtonContainer').classList.add('hidden');
            navHistory.sasnrFilter = null;
            document.getElementById('sasongFiltersContainer').classList.remove('opacity-50', 'pointer-events-none');
            
            if(navHistory.sourceTab) {
                switchTab(`tab-${navHistory.sourceTab}`, document.querySelector(`.tab-btn[onclick*="tab-${navHistory.sourceTab}"]`));
            }
        }

        function handleTeamSelect() {
            let team = document.getElementById('sasongTeam').value;
            if(team !== 'Alla') {
                document.getElementById('sasongYear').value = 'Alla'; 
            }
            document.getElementById('backButtonContainer').classList.add('hidden'); 
            navHistory.sasnrFilter = null;
            document.getElementById('sasongFiltersContainer').classList.remove('opacity-50', 'pointer-events-none');
            renderSasong();
        }

        function clickMainTab(tabId, btnElement) {
            document.getElementById('backButtonContainer').classList.add('hidden');
            navHistory.sasnrFilter = null;
            document.getElementById('sasongFiltersContainer').classList.remove('opacity-50', 'pointer-events-none');
            switchTab(tabId, btnElement);
        }

        function switchTab(tabId, btnElement) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            if(btnElement) btnElement.classList.add('active');
            currentTabId = tabId;
            
            if(tabId === 'tab-maraton') renderMaraton();
            if(tabId === 'tab-sasong') renderSasong();
            if(tabId === 'tab-vandring') renderVandringar();
            if(tabId === 'tab-placering') renderPlacering();
            if(tabId === 'tab-bildad') renderBildad();
            if(tabId === 'tab-topp') renderTopplistor(); 
        }

        function toggleVandringMode() {
            const mode = document.getElementById('vandringMode').value;
            document.getElementById('vandringLevelWrapper').classList.add('hidden');
            document.getElementById('vandringDivisionWrapper').classList.add('hidden');
            document.getElementById('vandringKombinationWrapper').classList.add('hidden');
            
            if(mode === 'niva') {
                document.getElementById('vandringLevelWrapper').classList.remove('hidden');
            } else if(mode === 'division') {
                document.getElementById('vandringDivisionWrapper').classList.remove('hidden');
            } else if(mode === 'kombination') {
                document.getElementById('vandringKombinationWrapper').classList.remove('hidden');
            }
            renderVandringar();
        }
        
        function togglePlaceringType() {
            const pType = document.getElementById('placeringType').value;
            const mode = document.getElementById('placeringMode').value;
            
            document.getElementById('placeringLevelWrapper').classList.add('hidden');
            document.getElementById('placeringDivisionWrapper').classList.add('hidden');
            document.getElementById('placeringKombinationWrapper').classList.add('hidden');
            
            if(mode === 'niva') document.getElementById('placeringLevelWrapper').classList.remove('hidden');
            else if(mode === 'division') document.getElementById('placeringDivisionWrapper').classList.remove('hidden');
            else if(mode === 'kombination') document.getElementById('placeringKombinationWrapper').classList.remove('hidden');
            
            let specWrap = document.getElementById('placeringSpecificWrapper');
            if(pType === 'kedja' || pType === 'fore' || pType === 'efter' || pType === 'fore_och_efter') specWrap.classList.remove('hidden');
            else specWrap.classList.add('hidden');
            
            // Fyll Målplacering dynamiskt om den är tom
            let specSel = document.getElementById('placeringSpecific');
            if(specSel.options.length === 0) {
                for(let i=1; i<=20; i++) {
                    let opt = document.createElement('option');
                    opt.value = i; opt.innerHTML = i;
                    specSel.appendChild(opt);
                }
            }
            
            renderPlacering();
        }

        // RENDER: MARATONTABELL
        function renderMaraton() {
            try {
                const search = document.getElementById('maratonSearch').value.toLowerCase();
                const pMode = document.getElementById('maratonPointsMode').value;
                const snabbvalKey = document.getElementById('maratonSnabbval').value;
                const startYear = parseInt(document.getElementById('maratonStartYear').value) || 0;
                const endYear = parseInt(document.getElementById('maratonEndYear').value) || 9999;
                const level = document.getElementById('maratonLevel').value;
                const divFilter = document.getElementById('maratonDivision').value;
                const tMode = document.getElementById('maratonTidsperiod').value;
                
                const useSnabbval = (snabbvalKey !== 'Inget');
                const snabbvalConds = useSnabbval ? snabbvalMap[snabbvalKey] : [];

                let seasonDataMap = {};
                
                completedMatchData.forEach(d => {
                    if (search && !String(d.Analys_Lagnamn).toLowerCase().includes(search)) return;
                    
                    let isMatch = false;
                    let dNivaStr = String(d.Nivå).trim();
                    let dDivStr = String(d.Division || '').trim();
                    
                    if (useSnabbval) {
                        isMatch = snabbvalConds.some(c => {
                            return d.Nivå === c.niva &&
                                   (c.div === 'Alla' || dDivStr === c.div) &&
                                   d.Säsnr >= c.start &&
                                   d.Säsnr <= c.end;
                        });
                    } else {
                        isMatch = (d.Startår_Numerisk >= startYear && d.Startår_Numerisk <= endYear &&
                                  (level === 'Alla' || dNivaStr === level) &&
                                  (divFilter === 'Alla' || dDivStr === divFilter));
                    }
                    
                    if(isMatch) {
                        let key = d.Analys_Lagnamn + "_" + d.Startår_Numerisk; 
                        if(!seasonDataMap[key]) {
                            seasonDataMap[key] = {
                                Analys_Lagnamn: d.Analys_Lagnamn, Startår_Numerisk: d.Startår_Numerisk,
                                Säsong: d.Säsong, 
                                Sp: 0, V: 0, O: 0, F: 0, Gjorda: 0, Insl: 0, 
                                P: 0, Giltig_Poängavdrag: 0,
                                Nivå_mult: Number(d.Nivå_multiplikator) || 1.0,
                                Epok_mult: Number(d.Epok_multiplikator) || 1.0,
                                Match_P: 0
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
                        entry.Giltig_Poängavdrag += Number(d.Giltig_Poängavdrag) || 0;
                        
                        let p_seger = Number(d.Poäng_seger) || 2; 
                        let match_p = (Number(d.V) * p_seger) + (Number(d.O) * 1) + (Number(d.Giltig_Poängavdrag) || 0);
                        entry.Match_P += match_p;
                    }
                });

                let teams = {};
                Object.values(seasonDataMap).forEach(d => {
                    let t = d.Analys_Lagnamn;
                    if (!teams[t]) teams[t] = { lag: t, ant_saesonger: 0, sp: 0, v: 0, o: 0, f: 0, gj: 0, insl: 0, padv: 0, histP: 0, viktadP: 0, matchP: 0, minYear: 9999, maxYear: 0, minYearStr: "", maxYearStr: "" };
                    
                    teams[t].ant_saesonger++;
                    teams[t].sp += d.Sp;
                    teams[t].v += d.V;
                    teams[t].o += d.O;
                    teams[t].f += d.F;
                    teams[t].gj += d.Gjorda;
                    teams[t].insl += d.Insl;
                    teams[t].padv += d.Giltig_Poängavdrag;
                    teams[t].histP += d.P; 
                    teams[t].matchP += d.Match_P;
                    
                    if(d.Startår_Numerisk < teams[t].minYear) {
                        teams[t].minYear = d.Startår_Numerisk;
                        teams[t].minYearStr = d.Säsong;
                    }
                    if(d.Startår_Numerisk > teams[t].maxYear) {
                        teams[t].maxYear = d.Startår_Numerisk;
                        teams[t].maxYearStr = d.Säsong;
                    }
                    
                    let base2p = (d.V * 2) + (d.O * 1);
                    let factor22 = d.Sp > 0 ? (22 / d.Sp) : 0;
                    teams[t].viktadP += base2p * factor22 * d.Nivå_mult * d.Epok_mult;
                });

                let arr = Object.values(teams).map(t => {
                    t.ms = t.gj - t.insl;
                    
                    if(pMode === '3') t.poang = (t.v * 3) + (t.o * 1) + t.padv;
                    else if(pMode === '2') t.poang = (t.v * 2) + (t.o * 1) + t.padv;
                    else if(pMode === 'viktad_p') t.poang = t.viktadP;
                    else if(pMode === 'viktat_snitt') {
                        // Förhindra 22/Sp inflationen, beräkna riktigt snitt
                        t.poang = t.sp > 0 ? ( ((t.v * 2) + (t.o * 1)) / t.sp ) : 0;
                    }
                    else t.poang = t.histP;
                    return t;
                });

                arr.sort((a, b) => b.poang - a.poang || b.ms - a.ms || b.gj - a.gj);
                
                let isFloat = (pMode === 'viktat_snitt' || pMode === 'viktad_p');
                let pLabel = 'P';
                if(pMode === 'viktad_p') pLabel = 'Viktade P';
                if(pMode === 'viktat_snitt') pLabel = 'Viktat Snitt';
                
                let thTidsperiod = '';
                if(tMode === 'full') thTidsperiod = `<th class="px-4 py-3 text-center">Tidsperiod</th>`;
                else if(tMode === 'premiar') thTidsperiod = `<th class="px-4 py-3 text-center">Premiär</th>`;

                document.getElementById('maratonHead').innerHTML = `
                    <tr>
                        <th class="px-4 py-3">Plac</th>
                        <th class="px-4 py-3">Lag</th>
                        ${thTidsperiod}
                        <th class="px-4 py-3 text-center">Säsonger</th>
                        <th class="px-4 py-3 text-center">Sp</th>
                        <th class="px-4 py-3 text-center">V</th>
                        <th class="px-4 py-3 text-center">O</th>
                        <th class="px-4 py-3 text-center">F</th>
                        <th class="px-4 py-3 text-center">Mål</th>
                        <th class="px-4 py-3 text-center">MS</th>
                        <th class="px-4 py-3 text-center font-bold text-gray-900">${pLabel}</th>
                    </tr>
                `;

                let tbody = '';
                arr.forEach((t, i) => {
                    let displayVal = isFloat ? t.poang.toFixed(3) : t.poang;
                    
                    let tdTidsperiod = '';
                    if(tMode === 'full') {
                        let tStr = t.minYear === t.maxYear ? t.minYearStr : `${t.minYearStr} &ndash; ${t.maxYearStr}`;
                        tdTidsperiod = `<td class="px-4 py-2 text-center text-gray-500">${tStr}</td>`;
                    } else if(tMode === 'premiar') {
                        tdTidsperiod = `<td class="px-4 py-2 text-center text-gray-500">${t.minYearStr}</td>`;
                    }

                    tbody += `
                        <tr class="hover:bg-blue-50 transition-colors">
                            <td class="px-4 py-2 text-gray-500">${i + 1}</td>
                            <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer" onclick="showTeamHistory('${t.lag}', 'maraton')" title="Klicka för att se lagets tabeller">${t.lag}</td>
                            ${tdTidsperiod}
                            <td class="px-4 py-2 text-center">${t.ant_saesonger}</td>
                            <td class="px-4 py-2 text-center">${t.sp}</td>
                            <td class="px-4 py-2 text-center">${t.v}</td>
                            <td class="px-4 py-2 text-center">${t.o}</td>
                            <td class="px-4 py-2 text-center">${t.f}</td>
                            <td class="px-4 py-2 text-center">${t.gj} &ndash; ${t.insl}</td>
                            <td class="px-4 py-2 text-center">${t.ms > 0 ? '+'+t.ms : t.ms}</td>
                            <td class="px-4 py-2 text-center font-bold text-gray-900">${displayVal}</td>
                        </tr>
                    `;
                });
                document.getElementById('maratonBody').innerHTML = tbody;
                document.getElementById('maratonCounter').innerText = `Visar maratontabell för ${arr.length} lag.`;
            } catch(e) {
                console.error("Error in renderMaraton:", e);
            }
        }

        // RENDER: SERIETABELL (ENSKILD SÄSONG / LAGHISTORIK)
        function renderSasong() {
            try {
                const seasonStr = document.getElementById('sasongYear').value;
                const teamFilter = document.getElementById('sasongTeam').value;
                const levelFilter = document.getElementById('sasongLevel').value;
                const divFilter = document.getElementById('sasongDivision').value;
                
                let data = completedMatchData.filter(d => {
                    if(navHistory.sasnrFilter && navHistory.sasnrFilter.length > 0) {
                        if(navHistory.teamFilter && d.Analys_Lagnamn !== navHistory.teamFilter) return false;
                        if(!navHistory.sasnrFilter.includes(parseInt(d.Säsnr))) return false;
                        return true;
                    }
                    if(seasonStr !== 'Alla' && String(d.Säsong) !== seasonStr) return false;
                    if(teamFilter !== 'Alla' && d.Analys_Lagnamn !== teamFilter) return false;
                    
                    let dNivaStr = String(d.Nivå).trim();
                    let dDivStr = String(d.Division || '').trim();
                    if(levelFilter !== 'Alla' && dNivaStr !== levelFilter) return false;
                    if(divFilter !== 'Alla' && dDivStr !== divFilter) return false;
                    return true;
                });
                
                data.sort((a, b) => {
                    let aS = parseInt(a.Säsnr) || 0, bS = parseInt(b.Säsnr) || 0;
                    let aSd = parseInt(a.Säsongsdel) || 0, bSd = parseInt(b.Säsongsdel) || 0;
                    let aN = parseFloat(a.Nivå) || 0, bN = parseFloat(b.Nivå) || 0;
                    let aP = parseInt(String(a.Plac || '').replace(/\D/g, '')) || 999;
                    let bP = parseInt(String(b.Plac || '').replace(/\D/g, '')) || 999;

                    if(navHistory.sasnrFilter || teamFilter !== 'Alla' || seasonStr === 'Alla') {
                        // Kronologiskt via Säsnr, därefter Vår/Höst, sedan Nivå
                        return aS - bS || aSd - bSd || aN - bN || aP - bP; 
                    }
                    return aS - bS || aSd - bSd || aN - bN || String(a.Serie || '').localeCompare(String(b.Serie || '')) || aP - bP;
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
                        <th class="px-4 py-3 text-center text-blue-800" title="Uträknat poängsnitt med historiska multiplikatorer">Viktat Snitt</th>
                    </tr>
                `;

                let tbody = '';
                data.forEach(d => {
                    try {
                        let rowClass = "border-b border-gray-100 transition-colors";
                        let placDisplay = d.Plac || '-';
                        let lagDisplay = d['Laget i tabell'] || 'Okänt Lag';
                        
                        let currSasnr = parseInt(d.Säsnr) || 0;
                        let d_Niva = parseFloat(d.Nivå) || 0;
                        let placNum = parseInt(String(d.Plac || '').replace(/\D/g, '')) || 999;
                        
                        let isGuld = false;
                        if (useSMVinnare) {
                            let smV = d.SM_vinnare ? String(d.SM_vinnare).trim() : '';
                            if (smV && smV !== '..' && smV !== 'nan') {
                                if (d.Analys_Lagnamn === smV || d.Standard_Lagnamn === smV || d['Laget i tabell'] === smV) {
                                    isGuld = true;
                                }
                            }
                        } else {
                            if (d_Niva === 1 && placNum === 1) isGuld = true;
                        }
                        
                        if(d.AliasBadge === 'first_ever') lagDisplay += ` <span class="text-yellow-500 font-bold text-lg leading-none ml-1" title="Lagets absolut första säsong i systemet">&#9733;</span>`;
                        else if(d.AliasBadge === 'new_alias') lagDisplay += ` <span class="text-red-500 font-bold text-lg leading-none ml-1" title="Nytt alias/namn">*</span>`;
                        else if(d.AliasBadge === 'reverted') lagDisplay += ` <span class="text-blue-500 font-bold text-lg leading-none ml-1" title="Återtaget alias/namn">*</span>`;
                        
                        // -- INTRÄDE OCH NYKOMLING --
                        let isNykomlingExplicit = d.Nya ? String(d.Nya).toLowerCase().includes('nykomling') : false;
                        let customNyStr = (d.Nya && String(d.Nya).trim() !== '' && !isNykomlingExplicit) ? String(d.Nya).trim() : null;

                        if (currSasnr === 1) {
                            if (isNykomlingExplicit) lagDisplay += ` <span class="ny-badge ml-2 px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 text-[10px] font-bold" title="Ny i systemet">NY</span>`;
                            else if (customNyStr) lagDisplay += ` <span class="text-xs text-gray-500 italic ml-2">(${customNyStr})</span>`;
                        } else {
                            if (d.EntryBadge === 'unexp_in') lagDisplay += ` <span class="text-red-600 font-bold text-lg leading-none ml-1" title="Oväntat inträde i systemet högt upp">!</span>`;
                            else if (d.Movement === 'new' || d.EntryBadge === 'normal_in') lagDisplay += ` <span class="ny-badge ml-2 px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 text-[10px] font-bold" title="Ny i systemet från distrikt">NY</span>`;
                            else if (d.Movement === 'promoted') lagDisplay += ` <span class="ny-badge ml-2 px-1.5 py-0.5 rounded bg-green-100 text-green-700 text-[10px] font-bold" title="Uppflyttad från lägre nivå">NY</span>`;
                            else if (d.Movement === 'relegated') lagDisplay += ` <span class="rel-badge ml-2 px-1.5 py-0.5 rounded bg-red-100 text-red-700 text-[10px] font-bold" title="Degraderad från högre nivå">D</span>`;
                        }
                        
                        if (d.ExitBadge === 'unexp_out') {
                            placDisplay = `<span>${d.Plac} <span class="warn-badge text-red-600 font-bold" title="Laget försvann oväntat ur systemet året efter">⚠️</span></span>`;
                            rowClass += " hover:bg-red-50";
                        } else if (d.ExitBadge === 'normal_out') {
                            placDisplay = `<span>${d.Plac} <span class="rel-badge text-gray-500 font-bold" title="Nedflyttad ur det nationella systemet">▼</span></span>`;
                            rowClass += " row-relegated";
                        } else {
                            if (d.RowEvent_Out === 'UPP') rowClass += " row-promoted" + (isGuld ? " font-bold" : "");
                            else if (d.RowEvent_Out === 'NED') rowClass += " row-relegated";
                            else {
                                if (isGuld) rowClass += " row-promoted font-bold";
                                else rowClass += " hover:bg-blue-50";
                            }
                        }
                        
                        let vNum = Number(d.V) || 0;
                        let oNum = Number(d.O) || 0;
                        let spNum = Number(d.Sp) || 0;
                        let just = Number(d.Poängjustering_Startpoäng) || 0;
                        
                        let base2p = (vNum * 2) + oNum;
                        let nMult = Number(d.Nivå_multiplikator) || 1.0;
                        let eMult = Number(d.Epok_multiplikator) || 1.0;
                        
                        let viktat_snitt = spNum > 0 ? ((base2p / spNum) * nMult * eMult).toFixed(3) : "0.000";

                        tbody += `
                            <tr class="${rowClass}">
                                <td class="px-4 py-2 text-center text-gray-500 font-medium">${d.Säsong || '-'}</td>
                                <td class="px-4 py-2 text-center font-medium">${d.Nivå || '-'}</td>
                                <td class="px-4 py-2 text-gray-600">${d.Division || '-'}</td>
                                <td class="px-4 py-2 text-gray-800">${d.Serie || '-'}</td>
                                <td class="px-4 py-2 text-center font-bold text-gray-900">${placDisplay}</td>
                                <td class="px-4 py-2 font-semibold text-gray-800" title="Standardnamn: ${d.Analys_Lagnamn}">${lagDisplay}</td>
                                <td class="px-4 py-2 text-center">${d.Sp}</td>
                                <td class="px-4 py-2 text-center">${d.V}</td>
                                <td class="px-4 py-2 text-center">${d.O}</td>
                                <td class="px-4 py-2 text-center">${d.F}</td>
                                <td class="px-4 py-2 text-center">${d.Gjorda || 0} &ndash; ${d.Insl || 0}</td>
                                <td class="px-4 py-2 text-center font-bold text-gray-900">${d.P}</td>
                                <td class="px-4 py-2 text-center text-gray-500">${just !== 0 ? just : ''}</td>
                                <td class="px-4 py-2 text-center text-blue-800 font-semibold">${viktat_snitt}</td>
                            </tr>
                        `;
                    } catch (e) {
                        console.error("Row render error in renderSasong:", e, d);
                    }
                });
                document.getElementById('sasongBody').innerHTML = tbody;
                document.getElementById('sasongCounter').innerText = `Hittade ${data.length} rader utifrån valda filter.`;
            } catch(e) {
                console.error("Fatal error in renderSasong:", e);
            }
        }

        // RENDER: SERIEVANDRINGAR
        function renderVandringar() {
            try {
                const search = document.getElementById('vandringSearch').value.toLowerCase();
                const mode = document.getElementById('vandringMode').value;
                const focusLevel = parseFloat(document.getElementById('vandringLevel').value);
                const focusDivision = String(document.getElementById('vandringDivision').value).trim();
                const focusKombKey = document.getElementById('vandringKombination').value;
                
                const useKomb = (mode === 'kombination' && focusKombKey !== 'Inget');
                const kombConds = useKomb ? focusMap[focusKombKey] : [];

                let teams = {};
                matchData.forEach(d => {
                    if (search && !String(d.Analys_Lagnamn).toLowerCase().includes(search)) return;
                    let t = d.Analys_Lagnamn;
                    if(!teams[t]) teams[t] = { lag: t, historyMap: {} };
                    
                    let sas = parseInt(d.Säsnr) || 0;
                    if(!teams[t].historyMap[sas]) {
                        teams[t].historyMap[sas] = { year: d.Startår_Numerisk, level: parseFloat(d.Nivå)||0, division: String(d.Division||'').trim(), sasnr: sas };
                    } else {
                        if((parseFloat(d.Nivå)||0) < teams[t].historyMap[sas].level) {
                            teams[t].historyMap[sas].level = parseFloat(d.Nivå)||0;
                            teams[t].historyMap[sas].division = String(d.Division||'').trim();
                        }
                    }
                });

                let results = [];
                Object.values(teams).forEach(t => {
                    t.history = Object.values(t.historyMap);
                    t.history.sort((a,b) => a.sasnr - b.sasnr);
                    
                    let focusSasnrs = new Set();
                    let promoToHere = 0, relegToHere = 0;
                    let promoFromHere = 0, relegFromHere = 0;
                    let inDistrikt = 0, utDistrikt = 0;

                    for(let i=0; i<t.history.length; i++) {
                        let curr = t.history[i];
                        let isMatch = false;
                        
                        if (useKomb) {
                            isMatch = kombConds.some(c => curr.level === c.niva && (c.div === 'Alla' || curr.division === c.div) && curr.sasnr >= c.start && curr.sasnr <= c.end);
                        } else if(mode === 'niva') {
                            isMatch = (curr.level === focusLevel);
                        } else if(mode === 'division') {
                            isMatch = (curr.division === focusDivision);
                        }

                        if(isMatch) {
                            focusSasnrs.add(curr.sasnr);
                            
                            // Klev in? (Från systemet ELLER distrikt)
                            if(i === 0 || curr.sasnr - t.history[i-1].sasnr > 1) {
                                inDistrikt++; 
                            } else if(i > 0) {
                                let prevLvl = t.history[i-1].level;
                                if(prevLvl > curr.level) promoToHere++;
                                if(prevLvl < curr.level) relegToHere++;
                            }
                            
                            // Klev ut? (Ut ur systemet ELLER till annan nivå)
                            if(i === t.history.length - 1 && curr.sasnr < maxGlobalSasnr) {
                                utDistrikt++;
                            } else if (i < t.history.length - 1) {
                                if(t.history[i+1].sasnr - curr.sasnr > 1) {
                                    utDistrikt++;
                                } else {
                                    let nextLvl = t.history[i+1].level;
                                    if(nextLvl < curr.level) promoFromHere++;
                                    if(nextLvl > curr.level) relegFromHere++;
                                }
                            }
                        }
                    }

                    if(focusSasnrs.size > 0) {
                        let sortedSasnrs = Array.from(focusSasnrs).sort((a,b) => a-b);
                        let maxStreak = 1, currentStreak = 1;
                        let maxStreakSasnrs = [sortedSasnrs[0]];
                        let currStreakSasnrs = [sortedSasnrs[0]];
                        
                        for(let j=1; j<sortedSasnrs.length; j++) {
                            if(sortedSasnrs[j] - sortedSasnrs[j-1] === 1) {
                                currentStreak++;
                                currStreakSasnrs.push(sortedSasnrs[j]);
                                if(currentStreak > maxStreak) {
                                    maxStreak = currentStreak;
                                    maxStreakSasnrs = [...currStreakSasnrs];
                                }
                            } else {
                                currentStreak = 1;
                                currStreakSasnrs = [sortedSasnrs[j]];
                            }
                        }

                        results.push({
                            lag: t.lag, tot_years: sortedSasnrs.length, max_streak: maxStreak,
                            promo_to: promoToHere, releg_to: relegToHere, 
                            promo_from: promoFromHere, releg_from: relegFromHere,
                            in_distrikt: inDistrikt, ut_distrikt: utDistrikt, 
                            sasnrs: maxStreakSasnrs.join(',')
                        });
                    }
                });

                results.sort((a,b) => b.max_streak - a.max_streak || b.tot_years - a.tot_years);

                document.getElementById('vandringHead').innerHTML = `
                    <tr>
                        <th class="px-4 py-3" rowspan="2">Lag</th>
                        <th class="px-4 py-3 text-center border-l" rowspan="2" title="Totalt antal säsonger de spelat på denna position">Totala Säsonger</th>
                        <th class="px-4 py-3 text-center font-bold text-blue-700 border-r" rowspan="2" title="Hur många säsonger i sträck de som mest spelat här">Längsta Svit</th>
                        <th class="px-2 py-2 text-center bg-gray-200 border-b border-white" colspan="3">ENTRÉ (In hit)</th>
                        <th class="px-2 py-2 text-center bg-gray-200 border-b border-white border-l" colspan="3">EXIT (Ut härifrån)</th>
                    </tr>
                    <tr>
                        <th class="px-2 py-2 text-center text-xs text-blue-600 bg-gray-50" title="Klev in från distriktsserierna">Från Distrikt</th>
                        <th class="px-2 py-2 text-center text-xs text-green-600 bg-gray-50" title="Uppflyttad från lägre nationell nivå">Underifrån</th>
                        <th class="px-2 py-2 text-center text-xs text-orange-600 bg-gray-50 border-r" title="Nedflyttad från högre nationell nivå">Ovanifrån</th>
                        
                        <th class="px-2 py-2 text-center text-xs text-green-600 bg-gray-50" title="Gått UPP till högre nationell nivå">Uppåt</th>
                        <th class="px-2 py-2 text-center text-xs text-orange-600 bg-gray-50" title="Ramlat UR till lägre nationell nivå">Nedåt</th>
                        <th class="px-2 py-2 text-center text-xs text-gray-500 bg-gray-50" title="Trillat ut i distriktsserierna">Ned i Distrikt</th>
                    </tr>
                `;

                let tbody = '';
                results.forEach(r => {
                    let promToStr = r.promo_to > 0 ? r.promo_to : '-';
                    let relToStr = r.releg_to > 0 ? r.releg_to : '-';
                    let inDistStr = r.in_distrikt > 0 ? r.in_distrikt : '-';
                    
                    let promFromStr = r.promo_from > 0 ? r.promo_from : '-';
                    let relFromStr = r.releg_from > 0 ? r.releg_from : '-';
                    let utDistStr = r.ut_distrikt > 0 ? r.ut_distrikt : '-';

                    tbody += `
                        <tr class="hover:bg-blue-50 transition-colors border-b border-gray-100">
                            <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer" onclick="showTeamHistory('${r.lag}', 'vandring', '${r.sasnrs}')" title="Klicka för att se enbart raderna för den längsta sviten">${r.lag}</td>
                            <td class="px-4 py-2 text-center text-gray-600 border-l">${r.tot_years}</td>
                            <td class="px-4 py-2 text-center font-bold text-blue-700 border-r bg-blue-50">${r.max_streak}</td>
                            <td class="px-2 py-2 text-center text-blue-600">${inDistStr}</td>
                            <td class="px-2 py-2 text-center text-green-600">${promToStr}</td>
                            <td class="px-2 py-2 text-center text-orange-600 border-r">${relToStr}</td>
                            <td class="px-2 py-2 text-center text-green-600">${promFromStr}</td>
                            <td class="px-2 py-2 text-center text-orange-600">${relFromStr}</td>
                            <td class="px-2 py-2 text-center text-gray-500">${utDistStr}</td>
                        </tr>
                    `;
                });
                document.getElementById('vandringBody').innerHTML = tbody;
                document.getElementById('vandringCounter').innerText = `Hittade ${results.length} lag.`;
            } catch(e) {
                console.error("Error in renderVandringar:", e);
            }
        }

        // ==============================================
        // NY FLIK: PLACERINGSANALYS
        // ==============================================
        function renderPlacering() {
            try {
                const mode = document.getElementById('placeringMode').value;
                const focusLevel = parseFloat(document.getElementById('placeringLevel').value);
                const focusDivision = String(document.getElementById('placeringDivision').value).trim();
                const focusKombKey = document.getElementById('placeringKombination').value;
                const pType = document.getElementById('placeringType').value;
                const ignHost = document.getElementById('placeringEndastVar').checked;
                
                const useKomb = (mode === 'kombination' && focusKombKey !== 'Inget');
                const kombConds = useKomb ? focusMap[focusKombKey] : [];

                let filteredData = completedMatchData.filter(d => {
                    if (ignHost && parseInt(d.Säsongsdel) === 2) return false;
                    
                    if (useKomb) {
                        return kombConds.some(c => d.Nivå === c.niva && (c.div === 'Alla' || String(d.Division||'').trim() === c.div) && d.Säsnr >= c.start && d.Säsnr <= c.end);
                    } else if (mode === 'niva') {
                        return d.Nivå === focusLevel;
                    } else if (mode === 'division') {
                        return String(d.Division||'').trim() === focusDivision;
                    }
                    return false;
                });
                
                let maxP = 0;
                filteredData.forEach(d => {
                    let p = parseInt(String(d.Plac).replace(/\D/g, ''));
                    if(!isNaN(p) && p > maxP) maxP = p;
                });
                if(maxP > 24) maxP = 24; 

                let validSasnrs = [...new Set(filteredData.map(d => parseInt(d.Säsnr)))].sort((a,b)=>a-b);
                let localMaxSasnr = validSasnrs.length > 0 ? validSasnrs[validSasnrs.length - 1] : maxGlobalSasnr;

                let htmlHead = '';
                let htmlBody = '';

                if (pType === 'stats') {
                    let stats = {};
                    filteredData.forEach(d => {
                        let p = parseInt(String(d.Plac).replace(/\D/g, ''));
                        if(isNaN(p)) return;
                        if(!stats[p]) stats[p] = { Plac: p, Sasonger: 0, Sp:0, V:0, O:0, F:0, Gj:0, Insl:0, MatchP:0 };
                        stats[p].Sasonger++;
                        stats[p].Sp += Number(d.Sp) || 0;
                        stats[p].V += Number(d.V) || 0;
                        stats[p].O += Number(d.O) || 0;
                        stats[p].F += Number(d.F) || 0;
                        stats[p].Gj += Number(d.Gjorda) || 0;
                        stats[p].Insl += Number(d.Insl) || 0;
                        stats[p].MatchP += (Number(d.V) * 3) + (Number(d.O) * 1); // RENT 3p SNITT
                    });
                    
                    htmlHead = `<tr><th class="px-4 py-3">Placering</th><th class="px-4 py-3 text-center">Gånger</th><th class="px-4 py-3 text-center">Sp</th><th class="px-4 py-3 text-center">V</th><th class="px-4 py-3 text-center">O</th><th class="px-4 py-3 text-center">F</th><th class="px-4 py-3 text-center">Gj-In</th><th class="px-4 py-3 text-center">MS</th><th class="px-4 py-3 text-center">Tot P (3p)</th><th class="px-4 py-3 text-center text-blue-800">Snitt P (3p)</th></tr>`;
                    
                    for(let i=1; i<=maxP; i++) {
                        let t = stats[i];
                        if(!t) continue;
                        let ms = t.Gj - t.Insl;
                        let snitt = t.Sp > 0 ? (t.MatchP / t.Sp).toFixed(2) : "0.00";
                        htmlBody += `
                            <tr class="hover:bg-blue-50 transition-colors">
                                <td class="px-4 py-2 font-bold">${i}</td>
                                <td class="px-4 py-2 text-center text-gray-600">${t.Sasonger}</td>
                                <td class="px-4 py-2 text-center">${t.Sp}</td>
                                <td class="px-4 py-2 text-center">${t.V}</td>
                                <td class="px-4 py-2 text-center">${t.O}</td>
                                <td class="px-4 py-2 text-center">${t.F}</td>
                                <td class="px-4 py-2 text-center">${t.Gj}&ndash;${t.Insl}</td>
                                <td class="px-4 py-2 text-center">${ms > 0 ? '+'+ms : ms}</td>
                                <td class="px-4 py-2 text-center">${t.MatchP}</td>
                                <td class="px-4 py-2 text-center font-bold text-blue-700">${snitt}</td>
                            </tr>
                        `;
                    }
                } 
                else if (pType === 'kedja') {
                    let targetPlac = parseInt(document.getElementById('placeringSpecific').value) || 1;
                    let matrix = {};
                    let rowLabels = [];
                    let colLabels = [];
                    
                    for(let i=1; i<=maxP; i++) { rowLabels.push(i); colLabels.push(i); }
                    rowLabels.push('Ned hit (Högre Nivå)', 'Upp hit (Lägre Nivå)', 'Ny från Distrikt'); 
                    colLabels.push('Upp (Högre Nivå)', 'Ned (Lägre Nivå)', 'Ut i Distrikt');
                    
                    let totalMatches = 0;

                    filteredData.forEach(d => {
                        let p = parseInt(String(d.Plac).replace(/\D/g, ''));
                        if(p !== targetPlac) return;

                        totalMatches++;
                        let currSasnr = parseInt(d.Säsnr) || 0;
                        let tName = d.Analys_Lagnamn;
                        let currIdx = validSasnrs.indexOf(currSasnr);
                        
                        let prevSasnr = (currIdx > 0) ? validSasnrs[currIdx - 1] : null;
                        let nextSasnr = (currIdx !== -1 && currIdx < validSasnrs.length - 1) ? validSasnrs[currIdx + 1] : null;
                        
                        let isNykomlingExplicit = d.Nya ? String(d.Nya).toLowerCase().includes('nykomling') : false;
                        let customNy = d.Nya && !isNykomlingExplicit && String(d.Nya).trim() !== '' ? String(d.Nya).trim() : null;

                        // PREV STATE
                        let prevRows = prevSasnr ? window.teamDataLookup[tName][prevSasnr] : null;
                        let rKey = customNy ? customNy : 'Ny från Distrikt';

                        if(prevRows && prevRows.length > 0) {
                            let sameLvlRow = prevRows.find(r => parseFloat(r.Nivå) === parseFloat(d.Nivå));
                            if(sameLvlRow) {
                                let p0 = parseInt(String(sameLvlRow.Plac).replace(/\D/g, ''));
                                if(!isNaN(p0) && p0 <= maxP) rKey = p0;
                            } else {
                                let minPrevLvl = Math.min(...prevRows.map(r => parseFloat(r.Nivå)));
                                if(minPrevLvl < parseFloat(d.Nivå)) rKey = 'Ned hit (Högre Nivå)';
                                else rKey = 'Upp hit (Lägre Nivå)';
                            }
                        }
                        
                        if(!rowLabels.includes(rKey)) {
                            rowLabels.push(rKey);
                        }
                        if(!matrix[rKey]) {
                            matrix[rKey] = { total: 0 };
                            colLabels.forEach(c => matrix[rKey][c] = 0);
                        }

                        // NEXT STATE
                        let nextRows = nextSasnr ? window.teamDataLookup[tName][nextSasnr] : null;
                        let cKey = 'Ut i Distrikt';

                        if(nextRows && nextRows.length > 0) {
                            let sameLvlRow = nextRows.find(r => parseFloat(r.Nivå) === parseFloat(d.Nivå));
                            if(sameLvlRow) {
                                let p1 = parseInt(String(sameLvlRow.Plac).replace(/\D/g, ''));
                                if(!isNaN(p1) && p1 <= maxP) cKey = p1;
                            } else {
                                let minNextLvl = Math.min(...nextRows.map(r => parseFloat(r.Nivå)));
                                if(minNextLvl < parseFloat(d.Nivå)) cKey = 'Upp (Högre Nivå)';
                                else cKey = 'Ned (Lägre Nivå)';
                            }
                        } else {
                            if(currSasnr >= localMaxSasnr) cKey = null; // Stannar här
                        }
                        
                        if(cKey) {
                            if(matrix[rKey][cKey] === undefined) matrix[rKey][cKey] = 0; 
                            matrix[rKey][cKey]++;
                        }
                        matrix[rKey].total++;
                    });

                    htmlHead = `<tr><th class="px-2 py-3 bg-gray-200 border-r border-gray-300 text-xs">År -1 \\ År +1</th>`;
                    for(let i=1; i<=maxP; i++) htmlHead += `<th class="px-2 py-3 text-center text-gray-600">${i}</th>`;
                    htmlHead += `<th class="px-2 py-3 text-center text-green-600 border-l">Upp</th><th class="px-2 py-3 text-center text-orange-600">Ned</th><th class="px-2 py-3 text-center text-gray-500">Ut</th><th class="px-2 py-3 text-center bg-gray-100 font-bold border-l">Totalt</th></tr>`;

                    rowLabels.forEach(r => {
                        let rowSum = matrix[r] ? matrix[r].total : 0;
                        if(rowSum === 0 && typeof r === 'string') return; 

                        htmlBody += `<tr class="hover:bg-gray-50 transition-colors">`;
                        let rTitle = typeof r === 'number' ? `Placering ${r}` : r;
                        let rClass = typeof r === 'number' ? "font-bold bg-gray-50 border-r border-gray-300" : "italic text-gray-600 bg-gray-50 border-r border-gray-300 text-xs";
                        htmlBody += `<td class="px-2 py-2 ${rClass}">${rTitle}</td>`;

                        colLabels.forEach(c => {
                            let isDiagonal = (r === targetPlac && c === targetPlac);
                            let val = matrix[r] && matrix[r][c] > 0 ? matrix[r][c] : '-';
                            let cClass = "text-center font-medium text-gray-700";
                            if(c === 'Upp (Högre Nivå)') cClass = "text-center font-bold text-green-600 border-l bg-green-50";
                            if(c === 'Ned (Lägre Nivå)') cClass = "text-center font-bold text-orange-600 bg-orange-50";
                            if(c === 'Ut i Distrikt') cClass = "text-center font-bold text-gray-500 bg-gray-100";
                            
                            if(isDiagonal) cClass += " bg-blue-100 border border-blue-400"; // Highlight!
                            htmlBody += `<td class="px-2 py-2 ${cClass}">${val}</td>`;
                        });

                        htmlBody += `<td class="px-2 py-2 text-center font-bold bg-gray-200 border-l">${rowSum}</td></tr>`;
                    });
                    
                    // Totalt rad
                    htmlBody += `<tr><td class="px-2 py-2 font-bold bg-gray-200 border-r border-gray-300 text-right text-xs">TOTALT ÅR +1</td>`;
                    colLabels.forEach(c => {
                        let colSum = 0;
                        rowLabels.forEach(r => { if(matrix[r]) colSum += matrix[r][c]; });
                        let val = colSum > 0 ? colSum : '-';
                        let cClass = "text-center font-bold bg-gray-200";
                        if(c === 'Upp (Högre Nivå)' || c === 'Ned (Lägre Nivå)' || c === 'Ut i Distrikt') cClass += " border-l";
                        
                        let isDiagonalCol = (c === targetPlac);
                        if(isDiagonalCol) cClass += " text-blue-800";
                        htmlBody += `<td class="px-2 py-2 ${cClass}">${val}</td>`;
                    });
                    htmlBody += `<td class="px-2 py-2 text-center font-bold bg-gray-300 border-l text-blue-800">${totalMatches}</td></tr>`;
                }
                else if (pType === 'efter') {
                    let matrixAfter = {};
                    filteredData.forEach(d => {
                        let pT = parseInt(String(d.Plac).replace(/\D/g, ''));
                        if(isNaN(pT)) return;
                        if(!matrixAfter[pT]) matrixAfter[pT] = { Plac: pT, nextPlac: {}, upp: 0, ned: 0, ut: 0 };
                        
                        let currSasnr = parseInt(d.Säsnr) || 0;
                        let currIdx = validSasnrs.indexOf(currSasnr);
                        let nextSasnr = (currIdx !== -1 && currIdx < validSasnrs.length - 1) ? validSasnrs[currIdx + 1] : null;
                        
                        let nextRows = nextSasnr ? window.teamDataLookup[d.Analys_Lagnamn][nextSasnr] : null;
                        
                        if(nextRows && nextRows.length > 0) {
                            let sameLevelRow = nextRows.find(r => parseFloat(r.Nivå) === parseFloat(d.Nivå));
                            if(sameLevelRow) {
                                let pT1 = parseInt(String(sameLevelRow.Plac).replace(/\D/g, ''));
                                if(!isNaN(pT1)) matrixAfter[pT].nextPlac[pT1] = (matrixAfter[pT].nextPlac[pT1] || 0) + 1;
                            } else {
                                let bestNextLvl = Math.min(...nextRows.map(r => parseFloat(r.Nivå)));
                                if(bestNextLvl < parseFloat(d.Nivå)) matrixAfter[pT].upp++;
                                else matrixAfter[pT].ned++;
                            }
                        } else {
                            if(currSasnr < localMaxSasnr) matrixAfter[pT].ut++;
                        }
                    });

                    htmlHead = `<tr><th class="px-2 py-3 bg-gray-200">Plac År 1 \\ Plac År 2</th>`;
                    for(let i=1; i<=maxP; i++) htmlHead += `<th class="px-2 py-3 text-center border-l text-gray-500">${i}</th>`;
                    htmlHead += `<th class="px-2 py-3 text-center border-l text-green-600">Upp</th><th class="px-2 py-3 text-center text-orange-600">Ned</th><th class="px-2 py-3 text-center text-red-600">Ut</th></tr>`;
                    
                    for(let p=1; p<=maxP; p++) {
                        if(!matrixAfter[p]) continue;
                        htmlBody += `<tr class="hover:bg-blue-50 transition-colors"><td class="px-2 py-2 font-bold bg-gray-50">${p}</td>`;
                        for(let i=1; i<=maxP; i++) {
                            let val = matrixAfter[p].nextPlac[i] || '-';
                            let isDiag = (p === i);
                            let cClass = isDiag ? "text-center border-l font-bold bg-blue-50 text-blue-800" : "text-center border-l font-medium text-gray-700";
                            htmlBody += `<td class="px-2 py-2 ${cClass}">${val}</td>`;
                        }
                        htmlBody += `
                            <td class="px-2 py-2 text-center border-l text-green-600 font-bold bg-green-50">${matrixAfter[p].upp || '-'}</td>
                            <td class="px-2 py-2 text-center text-orange-600 font-bold bg-orange-50">${matrixAfter[p].ned || '-'}</td>
                            <td class="px-2 py-2 text-center text-red-600 font-bold bg-red-50">${matrixAfter[p].ut || '-'}</td>
                        </tr>`;
                    }
                }
                else if (pType === 'fore') {
                    let matrixBefore = {};
                    filteredData.forEach(d => {
                        let pT = parseInt(String(d.Plac).replace(/\D/g, ''));
                        if(isNaN(pT)) return;
                        if(!matrixBefore[pT]) matrixBefore[pT] = { Plac: pT, prevPlac: {}, ned_hit: 0, upp_hit: 0, nykomling: 0 };
                        
                        let currSasnr = parseInt(d.Säsnr) || 0;
                        let currIdx = validSasnrs.indexOf(currSasnr);
                        let prevSasnr = (currIdx > 0) ? validSasnrs[currIdx - 1] : null;
                        let prevRows = prevSasnr ? window.teamDataLookup[d.Analys_Lagnamn][prevSasnr] : null;
                        
                        if(prevRows && prevRows.length > 0) {
                            let sameLevelRow = prevRows.find(r => parseFloat(r.Nivå) === parseFloat(d.Nivå));
                            if(sameLevelRow) {
                                let pT0 = parseInt(String(sameLevelRow.Plac).replace(/\D/g, ''));
                                if(!isNaN(pT0)) matrixBefore[pT].prevPlac[pT0] = (matrixBefore[pT].prevPlac[pT0] || 0) + 1;
                            } else {
                                let bestPrevLvl = Math.min(...prevRows.map(r => parseFloat(r.Nivå)));
                                if(bestPrevLvl < parseFloat(d.Nivå)) matrixBefore[pT].ned_hit++;
                                else matrixBefore[pT].upp_hit++;
                            }
                        } else {
                            if(currIdx > 0) matrixBefore[pT].nykomling++;
                        }
                    });

                    htmlHead = `<tr><th class="px-2 py-3 bg-gray-200">Plac År 2 \\ Plac År 1</th>`;
                    for(let i=1; i<=maxP; i++) htmlHead += `<th class="px-2 py-3 text-center border-l text-gray-500">${i}</th>`;
                    htmlHead += `<th class="px-2 py-3 text-center border-l text-orange-600">Ned hit</th><th class="px-2 py-3 text-center text-green-600">Upp hit</th><th class="px-2 py-3 text-center text-blue-600">In (Distr)</th></tr>`;
                    
                    for(let p=1; p<=maxP; p++) {
                        if(!matrixBefore[p]) continue;
                        htmlBody += `<tr class="hover:bg-blue-50 transition-colors"><td class="px-2 py-2 font-bold bg-gray-50">${p}</td>`;
                        for(let i=1; i<=maxP; i++) {
                            let val = matrixBefore[p].prevPlac[i] || '-';
                            let isDiag = (p === i);
                            let cClass = isDiag ? "text-center border-l font-bold bg-blue-50 text-blue-800" : "text-center border-l font-medium text-gray-700";
                            htmlBody += `<td class="px-2 py-2 ${cClass}">${val}</td>`;
                        }
                        htmlBody += `
                            <td class="px-2 py-2 text-center border-l text-orange-600 font-bold bg-orange-50">${matrixBefore[p].ned_hit || '-'}</td>
                            <td class="px-2 py-2 text-center text-green-600 font-bold bg-green-50">${matrixBefore[p].upp_hit || '-'}</td>
                            <td class="px-2 py-2 text-center text-blue-600 font-bold bg-blue-50">${matrixBefore[p].nykomling || '-'}</td>
                        </tr>`;
                    }
                }

                document.getElementById('placeringHead').innerHTML = htmlHead;
                document.getElementById('placeringBody').innerHTML = htmlBody;
                document.getElementById('placeringCounter').innerText = `Hittade ${filteredData.length} placeringar för din valda avgränsning.`;
            } catch(e) {
                console.error("Error in renderPlacering:", e);
            }
        }

        // ==============================================
        // NY FLIK: BILDAD (ÅLDERSANALYS)
        // ==============================================
        function renderBildad() {
            try {
                const mode = document.getElementById('bildadMode').value;
                const decennium = document.getElementById('bildadDecennium').value;
                const year = document.getElementById('bildadYear').value;

                let teamInfo = {};
                completedMatchData.forEach(d => {
                    let t = d.Analys_Lagnamn;
                    if (!teamInfo[t]) {
                        let bildadRaw = d.Bildad || '';
                        let yMatch = String(bildadRaw).match(/(\d{4})/);
                        let yNum = yMatch ? parseInt(yMatch[1]) : 0;
                        let dec = yNum > 0 ? Math.floor(yNum / 10) * 10 : 0;
                        
                        teamInfo[t] = {
                            lag: t,
                            bildadRaw: bildadRaw,
                            bildadYear: yNum,
                            decennium: dec,
                            sp: 0, v: 0, o: 0, f: 0, gj: 0, insl: 0, matchP: 0,
                            viktadP_snitt: 0, 
                            nivaMap: new Set()
                        };
                    }
                    
                    let entry = teamInfo[t];
                    entry.sp += Number(d.Sp) || 0;
                    entry.v += Number(d.V) || 0;
                    entry.o += Number(d.O) || 0;
                    entry.f += Number(d.F) || 0;
                    entry.gj += Number(d.Gjorda) || 0;
                    entry.insl += Number(d.Insl) || 0;
                    
                    entry.matchP += (Number(d.V) * 3) + (Number(d.O) * 1) + (Number(d.Giltig_Poängavdrag) || 0); // Std 3p
                    
                    let base2p = (Number(d.V) * 2) + (Number(d.O) * 1);
                    let mult = (Number(d.Nivå_multiplikator) || 1.0) * (Number(d.Epok_multiplikator) || 1.0);
                    entry.viktadP_snitt += base2p * mult; // För snitt
                    
                    entry.nivaMap.add(d.Nivå);
                });

                let allTeams = Object.values(teamInfo);

                if (mode === 'laglista') {
                    let filtered = allTeams.filter(t => {
                        if (t.bildadYear === 0) return false; // Dölj om årtal saknas
                        if (decennium !== 'Alla' && t.decennium !== parseInt(decennium)) return false;
                        if (year !== 'Alla' && t.bildadYear !== parseInt(year)) return false;
                        return true;
                    });

                    filtered.sort((a,b) => b.matchP - a.matchP || (b.gj - b.insl) - (a.gj - a.insl));

                    document.getElementById('bildadHead').innerHTML = `
                        <tr>
                            <th class="px-4 py-3">Plac</th>
                            <th class="px-4 py-3">Lag</th>
                            <th class="px-4 py-3 text-center text-blue-700 font-bold">Serieinträde</th>
                            <th class="px-4 py-3 text-center">Sp</th>
                            <th class="px-4 py-3 text-center">V-O-F</th>
                            <th class="px-4 py-3 text-center">Gj-In</th>
                            <th class="px-4 py-3 text-center font-bold text-gray-900">Tot P (3p)</th>
                            <th class="px-4 py-3 text-center text-blue-800">Viktat Snitt</th>
                        </tr>
                    `;

                    let htmlBody = '';
                    filtered.forEach((t, i) => {
                        let vsnitt = t.sp > 0 ? (t.viktadP_snitt / t.sp).toFixed(3) : "0.000";
                        let bText = t.bildadRaw || '-';
                        htmlBody += `
                            <tr class="hover:bg-blue-50 transition-colors">
                                <td class="px-4 py-2 text-gray-500">${i+1}</td>
                                <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer" onclick="showTeamHistory('${t.lag}', 'bildad')">${t.lag}</td>
                                <td class="px-4 py-2 text-center text-blue-700 font-bold">${bText}</td>
                                <td class="px-4 py-2 text-center">${t.sp}</td>
                                <td class="px-4 py-2 text-center">${t.v}&ndash;${t.o}&ndash;${t.f}</td>
                                <td class="px-4 py-2 text-center">${t.gj}&ndash;${t.insl}</td>
                                <td class="px-4 py-2 text-center font-bold text-gray-900">${t.matchP}</td>
                                <td class="px-4 py-2 text-center text-blue-800 font-semibold">${vsnitt}</td>
                            </tr>
                        `;
                    });
                    document.getElementById('bildadBody').innerHTML = htmlBody;
                    document.getElementById('bildadCounter').innerText = `Hittade ${filtered.length} lag som matchar åldersurvalet.`;
                    
                } else if (mode === 'niva') {
                    let decades = [...new Set(allTeams.map(t => t.decennium))].filter(d => d > 0).sort((a,b) => a-b);
                    let htmlHead = `<tr><th class="px-4 py-3">Decennium (Serieinträde)</th><th class="px-4 py-3 text-center border-l">Totalt Antal Lag</th>`;
                    allLevels.forEach(lvl => { htmlHead += `<th class="px-4 py-3 text-center border-l">Nivå ${lvl}</th>`; });
                    htmlHead += `</tr>`;
                    
                    let htmlBody = '';
                    decades.forEach(dec => {
                        let decTeams = allTeams.filter(t => t.decennium === dec);
                        let totTeams = decTeams.length;
                        htmlBody += `<tr class="hover:bg-blue-50 transition-colors">
                            <td class="px-4 py-2 font-bold">${dec} - ${dec+9}</td>
                            <td class="px-4 py-2 text-center border-l font-semibold text-gray-700">${totTeams}</td>`;
                            
                        allLevels.forEach(lvl => {
                            let count = decTeams.filter(t => t.nivaMap.has(lvl)).length;
                            htmlBody += `<td class="px-4 py-2 text-center border-l ${count>0 ? 'font-semibold text-blue-700' : 'text-gray-400'}">${count > 0 ? count : '-'}</td>`;
                        });
                        htmlBody += `</tr>`;
                    });
                    document.getElementById('bildadHead').innerHTML = htmlHead;
                    document.getElementById('bildadBody').innerHTML = htmlBody;
                    document.getElementById('bildadCounter').innerText = `Visar fördelning över ${decades.length} decennier. Endast unika lag räknas i kolumnerna.`;
                }
            } catch(e) {
                console.error("Error in renderBildad:", e);
            }
        }

        // ==============================================
        // NY FLIK: TOPPLISTOR
        // ==============================================
        function updateToppMetrics() {
            const cat = document.getElementById('toppCategory').value;
            const type = document.getElementById('toppMetricType').value;
            const select = document.getElementById('toppMetric');
            
            document.getElementById('toppUnique').disabled = (cat === 'maraton' || cat === 'distrikt' || cat === 'kommun' || cat === 'vinnare');
            if(cat === 'maraton' || cat === 'distrikt' || cat === 'kommun' || cat === 'vinnare') document.getElementById('toppUnique').checked = true;
            
            let countSelect = document.getElementById('toppCount');
            if (cat === 'handelser' || cat === 'vinnare') {
                countSelect.value = "999999";
                countSelect.disabled = true;
            } else {
                countSelect.disabled = false;
                if(countSelect.value === "999999") countSelect.value = "25";
            }
            
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
            if(isFloat) return parseFloat(val).toFixed(3);
            return val;
        }

        function renderTopplistor() {
            try {
                const cat = document.getElementById('toppCategory').value;
                const metric = document.getElementById('toppMetric').value;
                const count = parseInt(document.getElementById('toppCount').value);
                const level = document.getElementById('toppLevel').value;
                const unique = document.getElementById('toppUnique').checked;
                
                let htmlHead = '';
                let htmlBody = '';
                let results = [];

                // SÄSONG
                if (cat === 'sasong') {
                    let seasonDataMap = {};
                    
                    completedMatchData.forEach(d => {
                        if (level !== 'Alla' && String(d.Nivå).trim() !== level) return;
                        
                        let key = d.Analys_Lagnamn + "_" + d.Startår_Numerisk;
                        if(!seasonDataMap[key]) {
                            seasonDataMap[key] = {
                                Analys_Lagnamn: d.Analys_Lagnamn,
                                'Laget i tabell': d['Laget i tabell'], 
                                Startår_Numerisk: d.Startår_Numerisk,
                                Säsong: d.Säsong,
                                Säsnr: d.Säsnr,
                                Nivå: d.Nivå,
                                Sp: 0, V: 0, O: 0, F: 0, Gjorda: 0, Insl: 0, P: 0, Målskillnad: 0, Viktad_P: 0, Match_P: 0
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
                        entry.Nivå = Math.min(parseFloat(entry.Nivå) || 99, parseFloat(d.Nivå) || 99);
                        
                        let match_p = (Number(d.V) * 3) + (Number(d.O) * 1); 
                        entry.Match_P += match_p;
                        
                        let base2p = (Number(d.V) * 2) + (Number(d.O) * 1);
                        let mult = (Number(d.Nivå_multiplikator) || 1.0) * (Number(d.Epok_multiplikator) || 1.0);
                        entry.Viktad_P += base2p * mult; // Inget 22/Sp för per match!
                    });

                    let data = Object.values(seasonDataMap);
                    
                    data.forEach(d => {
                        d.p_snitt = d.Sp > 0 ? (d.Match_P / d.Sp) : 0;
                        d.gj_snitt = d.Sp > 0 ? (d.Gjorda / d.Sp) : 0;
                        d.insl_snitt = d.Sp > 0 ? (d.Insl / d.Sp) : 0;
                        d.viktat_snitt = d.Sp > 0 ? (d.Viktad_P / d.Sp) : 0;
                    });

                    let isFloat = false;
                    let valKey = '';
                    
                    if (metric === 'p_max') { data.sort((a,b) => b.P - a.P || b.Målskillnad - a.Målskillnad); valKey = 'P'; }
                    else if (metric === 'p_min') { data = data.filter(d=>d.Sp>=10); data.sort((a,b) => a.P - b.P || a.Målskillnad - b.Målskillnad); valKey = 'P'; }
                    else if (metric === 'v_max') { data.sort((a,b) => b.V - a.V || b.P - a.P); valKey = 'V'; }
                    else if (metric === 'v_min') { data = data.filter(d=>d.Sp>=10); data.sort((a,b) => a.V - b.V || a.P - b.P); valKey = 'V'; }
                    else if (metric === 'f_max') { data.sort((a,b) => b.F - a.F || a.P - b.P); valKey = 'F'; }
                    else if (metric === 'f_min') { data = data.filter(d=>d.Sp>=10); data.sort((a,b) => a.F - b.F || b.P - a.P); valKey = 'F'; }
                    else if (metric === 'gj_max') { data.sort((a,b) => b.Gjorda - a.Gjorda || b.P - a.P); valKey = 'Gjorda'; }
                    else if (metric === 'gj_min') { data = data.filter(d=>d.Sp>=10); data.sort((a,b) => a.Gjorda - b.Gjorda || a.P - b.P); valKey = 'Gjorda'; }
                    else if (metric === 'insl_max') { data.sort((a,b) => b.Insl - a.Insl || b.P - a.P); valKey = 'Insl'; }
                    else if (metric === 'insl_min') { data = data.filter(d=>d.Sp>=10); data.sort((a,b) => a.Insl - b.Insl || b.P - a.P); valKey = 'Insl'; }
                    else if (metric === 'p_snitt_max') { data = data.filter(d=>d.Sp>=10); data.sort((a,b) => b.p_snitt - a.p_snitt); valKey = 'p_snitt'; isFloat = true; }
                    else if (metric === 'p_snitt_min') { data = data.filter(d=>d.Sp>=10); data.sort((a,b) => a.p_snitt - b.p_snitt); valKey = 'p_snitt'; isFloat = true; }
                    else if (metric === 'gj_snitt_max') { data = data.filter(d=>d.Sp>=10); data.sort((a,b) => b.gj_snitt - a.gj_snitt); valKey = 'gj_snitt'; isFloat = true; }
                    else if (metric === 'insl_snitt_max') { data = data.filter(d=>d.Sp>=10); data.sort((a,b) => b.insl_snitt - a.insl_snitt); valKey = 'insl_snitt'; isFloat = true; }
                    else if (metric === 'viktat_snitt_max') { data = data.filter(d=>d.Sp>=10); data.sort((a,b) => b.viktat_snitt - a.viktat_snitt); valKey = 'viktat_snitt'; isFloat = true; }

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
                                <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer" onclick="showTeamHistory('${d.Analys_Lagnamn}', 'topp', '${d.Säsnr}')" title="Standardnamn: ${d.Analys_Lagnamn}">${d['Laget i tabell']}</td>
                                <td class="px-4 py-2 text-center text-gray-600 font-medium">${d.Säsong}</td>
                                <td class="px-4 py-2 text-center">${d.Nivå}</td>
                                <td class="px-4 py-2 text-center">${d.Sp}</td>
                                <td class="px-4 py-2 text-center">${d.V}&ndash;${d.O}&ndash;${d.F}</td>
                                <td class="px-4 py-2 text-center">${d.Gjorda}&ndash;${d.Insl}</td>
                                <td class="px-4 py-2 text-center font-bold text-blue-700">${displayVal}</td>
                            </tr>
                        `;
                    });
                } 
                
                // MARATON
                else if (cat === 'maraton') {
                    let seasonDataMap = {};
                    completedMatchData.forEach(d => {
                        if (level !== 'Alla' && String(d.Nivå).trim() !== level) return;
                        let key = d.Analys_Lagnamn + "_" + d.Startår_Numerisk;
                        if(!seasonDataMap[key]) {
                            seasonDataMap[key] = { Analys_Lagnamn: d.Analys_Lagnamn, Sp: 0, V: 0, O: 0, F: 0, Gjorda: 0, Insl: 0, Giltig_Poängavdrag: 0, Viktad_P_Total: 0, Viktad_P_Snitt: 0, Match_P: 0 };
                        }
                        let entry = seasonDataMap[key];
                        entry.Sp += Number(d.Sp) || 0; 
                        entry.V += Number(d.V) || 0; 
                        entry.O += Number(d.O) || 0; 
                        entry.F += Number(d.F) || 0;
                        entry.Gjorda += Number(d.Gjorda) || 0; 
                        entry.Insl += Number(d.Insl) || 0; 
                        entry.Giltig_Poängavdrag += Number(d.Giltig_Poängavdrag) || 0;
                        
                        let match_p = (Number(d.V) * 3) + (Number(d.O) * 1);
                        entry.Match_P += match_p;
                        
                        let base2p = (Number(d.V) * 2) + (Number(d.O) * 1);
                        let mult = (Number(d.Nivå_multiplikator) || 1.0) * (Number(d.Epok_multiplikator) || 1.0);
                        let factor22 = d.Sp > 0 ? (22 / d.Sp) : 0;
                        
                        entry.Viktad_P_Total += base2p * factor22 * mult;
                        entry.Viktad_P_Snitt += base2p * mult; 
                    });

                    let teams = {};
                    Object.values(seasonDataMap).forEach(d => {
                        let t = d.Analys_Lagnamn;
                        if (!teams[t]) teams[t] = { lag: t, ant_saesonger: 0, sp: 0, v: 0, f: 0, gj: 0, p: 0, viktadP: 0, matchP: 0, viktadPSnitt: 0 };
                        teams[t].ant_saesonger++;
                        teams[t].sp += d.Sp;
                        teams[t].v += d.V;
                        teams[t].f += d.F;
                        teams[t].gj += d.Gjorda;
                        teams[t].p += (d.V * 3) + (d.O * 1) + d.Giltig_Poängavdrag; // Historiska totals
                        teams[t].matchP += d.Match_P;
                        teams[t].viktadP += d.Viktad_P_Total;
                        teams[t].viktadPSnitt += d.Viktad_P_Snitt;
                    });

                    let arr = Object.values(teams).map(t => {
                        t.p_snitt = t.sp > 0 ? (t.matchP / t.sp) : 0;
                        t.viktat_snitt = t.sp > 0 ? (t.viktadPSnitt / t.sp) : 0;
                        return t;
                    });

                    let isFloat = false;
                    let valKey = '';
                    
                    if (metric === 'p_max') { arr.sort((a,b) => b.p - a.p); valKey = 'p'; }
                    else if (metric === 'viktad_p_max') { arr.sort((a,b) => b.viktadP - a.viktadP); valKey = 'viktadP'; isFloat=true; }
                    else if (metric === 'v_max') { arr.sort((a,b) => b.v - a.v); valKey = 'v'; }
                    else if (metric === 'f_max') { arr.sort((a,b) => b.f - a.f); valKey = 'f'; }
                    else if (metric === 'gj_max') { arr.sort((a,b) => b.gj - a.gj); valKey = 'gj'; }
                    else if (metric === 'sasong_max') { arr.sort((a,b) => b.ant_saesonger - a.ant_saesonger); valKey = 'ant_saesonger'; }
                    else if (metric === 'p_snitt_max') { arr = arr.filter(t=>t.sp>=30); arr.sort((a,b) => b.p_snitt - a.p_snitt); valKey = 'p_snitt'; isFloat = true; }
                    else if (metric === 'viktat_snitt_max') { arr = arr.filter(t=>t.sp>=30); arr.sort((a,b) => b.viktat_snitt - a.viktat_snitt); valKey = 'viktat_snitt'; isFloat = true; }

                    results = arr.slice(0, count);

                    htmlHead = `<tr><th class="px-4 py-3">Plac</th><th class="px-4 py-3">Lag</th><th class="px-4 py-3 text-center">Säsonger</th><th class="px-4 py-3 text-center">Sp</th><th class="px-4 py-3 text-center">Mål</th><th class="px-4 py-3 text-center font-bold text-blue-700">Mätvärde</th></tr>`;
                    
                    results.forEach((t, i) => {
                        let displayVal = formatVal(t[valKey], isFloat);
                        htmlBody += `
                            <tr class="hover:bg-blue-50 transition-colors">
                                <td class="px-4 py-2 text-gray-500">${i+1}</td>
                                <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer" onclick="showTeamHistory('${t.lag}', 'topp')">${t.lag}</td>
                                <td class="px-4 py-2 text-center">${t.ant_saesonger}</td>
                                <td class="px-4 py-2 text-center">${t.sp}</td>
                                <td class="px-4 py-2 text-center">${t.gj}</td>
                                <td class="px-4 py-2 text-center font-bold text-blue-700">${displayVal}</td>
                            </tr>
                        `;
                    });
                }

                // NYA LAG
                else if (cat === 'nya_lag') {
                    let nyaLagArr = [];
                    completedMatchData.forEach(d => {
                        if (level !== 'Alla' && String(d.Nivå).trim() !== level) return;
                        let tName = d.Analys_Lagnamn;
                        if (parseInt(d.Säsnr) === parseInt(teamFirstAppearance[tName])) {
                            nyaLagArr.push(d);
                        }
                    });

                    if (metric === 'nya_antal' || metric === 'nya_antal_krono') {
                        let yearCounts = {};
                        nyaLagArr.forEach(d => {
                            let y = d.Säsong;
                            if(!yearCounts[y]) yearCounts[y] = { sasong: y, count: 0, lags: [], sasnr: d.Säsnr, yearNum: d.Startår_Numerisk };
                            yearCounts[y].count++;
                            if(yearCounts[y].lags.length < 4) yearCounts[y].lags.push(d.Analys_Lagnamn);
                        });
                        
                        let arr = Object.values(yearCounts);
                        if (metric === 'nya_antal') {
                            arr.sort((a,b) => b.count - a.count);
                        } else {
                            arr.sort((a,b) => a.yearNum - b.yearNum);
                        }
                        
                        results = arr.slice(0, count);

                        htmlHead = `<tr><th class="px-4 py-3">Plac</th><th class="px-4 py-3">Säsong</th><th class="px-4 py-3 text-center font-bold text-blue-700">Antal Nya Lag</th><th class="px-4 py-3 text-gray-500">Exempel på lag</th></tr>`;
                        
                        results.forEach((t, i) => {
                            let lagStr = t.lags.join(', ');
                            if(t.count > 4) lagStr += ' m.fl.';
                            htmlBody += `
                                <tr class="hover:bg-blue-50 transition-colors">
                                    <td class="px-4 py-2 text-gray-500">${i+1}</td>
                                    <td class="px-4 py-2 font-medium text-gray-800">${t.sasong}</td>
                                    <td class="px-4 py-2 text-center font-bold text-blue-700">${t.count}</td>
                                    <td class="px-4 py-2 text-xs text-gray-500 italic">${lagStr}</td>
                                </tr>
                            `;
                        });
                    } else if (metric === 'nya_krono') {
                        nyaLagArr.sort((a,b) => (parseInt(a.Säsnr)||0) - (parseInt(b.Säsnr)||0) || (parseFloat(a.Nivå)||0) - (parseFloat(b.Nivå)||0));
                        results = nyaLagArr.slice(0, count);
                        
                        htmlHead = `<tr><th class="px-4 py-3">Säsong</th><th class="px-4 py-3">Nivå</th><th class="px-4 py-3">Beteckning</th><th class="px-4 py-3 font-bold text-blue-700">Nytt Lag i Systemet</th></tr>`;
                        
                        results.forEach(d => {
                            htmlBody += `
                                <tr class="hover:bg-blue-50 transition-colors">
                                    <td class="px-4 py-2 text-gray-500 font-medium">${d.Säsong}</td>
                                    <td class="px-4 py-2 text-gray-700">${d.Nivå}</td>
                                    <td class="px-4 py-2 text-gray-700">${d.Division || '-'}</td>
                                    <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer" onclick="showTeamHistory('${d.Analys_Lagnamn}', 'topp', '${d.Säsnr}')">${d['Laget i tabell']}</td>
                                </tr>
                            `;
                        });
                    }
                }

                // VANDRING & JOJO
                else if (cat === 'vandring') {
                    if (metric.startsWith('krono_')) {
                        let evList = [];
                        completedMatchData.forEach(d => {
                            if (level !== 'Alla' && String(d.Nivå).trim() !== level) return;
                            
                            let isMatch = false;
                            if(metric === 'krono_ny_upp' && d.RowEvent_In === 'NY' && d.RowEvent_Out === 'UPP') isMatch = true;
                            if(metric === 'krono_ny_ned' && d.RowEvent_In === 'NY' && d.RowEvent_Out === 'NED') isMatch = true;
                            if(metric === 'krono_d_upp' && d.RowEvent_In === 'D' && d.RowEvent_Out === 'UPP') isMatch = true;
                            if(metric === 'krono_d_ned' && d.RowEvent_In === 'D' && d.RowEvent_Out === 'NED') isMatch = true;
                            
                            if(isMatch) evList.push(d);
                        });
                        
                        evList.sort((a,b) => (parseInt(a.Säsnr)||0) - (parseInt(b.Säsnr)||0) || (parseFloat(a.Nivå)||0) - (parseFloat(b.Nivå)||0));
                        results = evList.slice(0, count);

                        htmlHead = `<tr><th class="px-4 py-3">Säsong</th><th class="px-4 py-3 text-center">Nivå</th><th class="px-4 py-3">Lag</th><th class="px-4 py-3 text-center">In</th><th class="px-4 py-3 text-center">Ut</th></tr>`;
                        
                        results.forEach(d => {
                            let inStr = d.RowEvent_In === 'NY' ? '<span class="text-blue-600 font-bold">NYKOMLING</span>' : '<span class="text-red-600 font-bold">NEDFLYTTAD HIT</span>';
                            let utStr = d.RowEvent_Out === 'UPP' ? '<span class="text-green-600 font-bold">AVANCERAR</span>' : '<span class="text-orange-600 font-bold">DEGRADERAS</span>';
                            htmlBody += `
                                <tr class="hover:bg-blue-50 transition-colors border-b border-gray-100">
                                    <td class="px-4 py-2 font-medium text-gray-600">${d.Säsong}</td>
                                    <td class="px-4 py-2 text-center text-gray-700">${d.Nivå}</td>
                                    <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer" onclick="showTeamHistory('${d.Analys_Lagnamn}', 'topp', '${parseInt(d.Säsnr)},${parseInt(d.Säsnr)+1}')">${d['Laget i tabell']}</td>
                                    <td class="px-4 py-2 text-center text-xs">${inStr}</td>
                                    <td class="px-4 py-2 text-center text-xs">${utStr}</td>
                                </tr>
                            `;
                        });

                    } else {
                        let teams = {};
                        completedMatchData.forEach(d => {
                            let t = d.Analys_Lagnamn;
                            if(!teams[t]) teams[t] = { lag: t, historyMap: {} };
                            let sas = parseInt(d.Säsnr) || 0;
                            if(!teams[t].historyMap[sas]) {
                                teams[t].historyMap[sas] = { year: d.Startår_Numerisk, level: parseFloat(d.Nivå)||0, division: d.Division, sasnr: sas };
                            } else {
                                if((parseFloat(d.Nivå)||0) < teams[t].historyMap[sas].level) {
                                    teams[t].historyMap[sas].level = parseFloat(d.Nivå)||0;
                                    teams[t].historyMap[sas].division = d.Division;
                                }
                            }
                        });

                        let all_sviter = [];
                        let all_klattringar = [];
                        let all_ras = [];
                        let all_totals = [];

                        Object.values(teams).forEach(t => {
                            t.history = Object.values(t.historyMap);
                            t.history.sort((a,b) => a.sasnr - b.sasnr);
                            
                            let upp_tot = 0, ned_tot = 0, direkta_studsar = 0;
                            let in_tot = 0, ut_tot = 0;
                            let klattring_len = 0, klattring_sasnrs = [];
                            let ras_len = 0, ras_sasnrs = [];
                            
                            for(let i=0; i<t.history.length; i++) {
                                let curr = t.history[i];
                                let matchCurr = (level === 'Alla' || String(curr.level) === level);
                                
                                if(i === 0 || curr.sasnr - t.history[i-1].sasnr > 1) {
                                    if(matchCurr) in_tot++;
                                }
                                
                                if(i < t.history.length - 1) {
                                    if(t.history[i+1].sasnr - curr.sasnr > 1) {
                                        if(matchCurr) ut_tot++;
                                    }
                                } else {
                                    if(curr.sasnr < maxGlobalSasnr) {
                                        if(matchCurr) ut_tot++; 
                                    }
                                }
                                
                                if(i > 0) {
                                    if(curr.sasnr - t.history[i-1].sasnr === 1) {
                                        let diff = t.history[i-1].level - curr.level;
                                        if(diff > 0) { 
                                            if(matchCurr) upp_tot++;
                                            if(klattring_len === 0) klattring_sasnrs = [t.history[i-1].sasnr];
                                            klattring_len++;
                                            klattring_sasnrs.push(curr.sasnr);
                                            
                                            if(ras_len >= 1) all_ras.push({ lag: t.lag, len: ras_len, sasnrs: ras_sasnrs.join(',') });
                                            ras_len = 0;
                                        } else if(diff < 0) {
                                            if(matchCurr) ned_tot++;
                                            if(ras_len === 0) ras_sasnrs = [t.history[i-1].sasnr];
                                            ras_len++;
                                            ras_sasnrs.push(curr.sasnr);
                                            
                                            if(klattring_len >= 1) all_klattringar.push({ lag: t.lag, len: klattring_len, sasnrs: klattring_sasnrs.join(',') });
                                            klattring_len = 0;
                                        } else {
                                            if(klattring_len >= 1) all_klattringar.push({ lag: t.lag, len: klattring_len, sasnrs: klattring_sasnrs.join(',') });
                                            if(ras_len >= 1) all_ras.push({ lag: t.lag, len: ras_len, sasnrs: ras_sasnrs.join(',') });
                                            klattring_len = 0; ras_len = 0;
                                        }
                                        
                                        if(i > 1 && (curr.sasnr - t.history[i-2].sasnr === 2)) {
                                            let diff1 = t.history[i-2].level - t.history[i-1].level;
                                            let diff2 = t.history[i-1].level - curr.level;
                                            if ((diff1 > 0 && diff2 < 0) || (diff1 < 0 && diff2 > 0)) {
                                                let matchPrev = (level === 'Alla' || String(t.history[i-1].level) === level);
                                                if(matchPrev) direkta_studsar++;
                                            }
                                        }
                                    } else {
                                        if(klattring_len >= 1) all_klattringar.push({ lag: t.lag, len: klattring_len, sasnrs: klattring_sasnrs.join(',') });
                                        if(ras_len >= 1) all_ras.push({ lag: t.lag, len: ras_len, sasnrs: ras_sasnrs.join(',') });
                                        klattring_len = 0; ras_len = 0;
                                    }
                                } else {
                                    klattring_sasnrs = [curr.sasnr];
                                    ras_sasnrs = [curr.sasnr];
                                }
                            }
                            if(klattring_len >= 1) all_klattringar.push({ lag: t.lag, len: klattring_len, sasnrs: klattring_sasnrs.join(',') });
                            if(ras_len >= 1) all_ras.push({ lag: t.lag, len: ras_len, sasnrs: ras_sasnrs.join(',') });

                            let sasnrsOnLevel = [];
                            t.history.forEach(h => { 
                                if(level === 'Alla' || String(h.level) === level) sasnrsOnLevel.push(h.sasnr); 
                            });
                            
                            if(sasnrsOnLevel.length > 0) {
                                let cSvit = 1;
                                let currSvitSasnrs = [sasnrsOnLevel[0]];
                                for(let j=1; j<sasnrsOnLevel.length; j++) {
                                    if(sasnrsOnLevel[j] - sasnrsOnLevel[j-1] === 1) {
                                        cSvit++;
                                        currSvitSasnrs.push(sasnrsOnLevel[j]);
                                    } else {
                                        all_sviter.push({ lag: t.lag, len: cSvit, sasnrs: currSvitSasnrs.join(',') });
                                        cSvit = 1;
                                        currSvitSasnrs = [sasnrsOnLevel[j]];
                                    }
                                }
                                all_sviter.push({ lag: t.lag, len: cSvit, sasnrs: currSvitSasnrs.join(',') });
                            }

                            all_totals.push({ lag: t.lag, upp: upp_tot, ned: ned_tot, jojo: upp_tot + ned_tot, studs: direkta_studsar });
                        });

                        let finalData = [];
                        if(metric === 'svit_max') {
                            if(unique) {
                                let best = {};
                                all_sviter.forEach(s => {
                                    if(!best[s.lag] || s.len > best[s.lag].len) best[s.lag] = s;
                                });
                                finalData = Object.values(best);
                            } else {
                                finalData = all_sviter;
                            }
                            finalData.sort((a,b) => b.len - a.len);
                        } else if(metric === 'klattring_max') {
                            if(unique) {
                                let best = {};
                                all_klattringar.forEach(s => {
                                    if(!best[s.lag] || s.len > best[s.lag].len) best[s.lag] = s;
                                });
                                finalData = Object.values(best);
                            } else {
                                finalData = all_klattringar;
                            }
                            finalData.sort((a,b) => b.len - a.len);
                        } else if(metric === 'ras_max') {
                            if(unique) {
                                let best = {};
                                all_ras.forEach(s => {
                                    if(!best[s.lag] || s.len > best[s.lag].len) best[s.lag] = s;
                                });
                                finalData = Object.values(best);
                            } else {
                                finalData = all_ras;
                            }
                            finalData.sort((a,b) => b.len - a.len);
                        } else {
                            finalData = all_totals;
                            if(metric === 'jojo_max') finalData.sort((a,b) => b.jojo - a.jojo);
                            else if(metric === 'upp_max') finalData.sort((a,b) => b.upp - a.upp);
                            else if(metric === 'ned_max') finalData.sort((a,b) => b.ned - a.ned);
                            else if(metric === 'studs_max') finalData.sort((a,b) => b.studs - a.studs);
                        }
                        
                        results = finalData.slice(0, count);

                        if(metric === 'svit_max' || metric === 'klattring_max' || metric === 'ras_max') {
                            htmlHead = `<tr><th class="px-4 py-3">Plac</th><th class="px-4 py-3">Lag</th><th class="px-4 py-3 text-center font-bold text-blue-700">Mätvärde (Antal i rad)</th></tr>`;
                            results.forEach((t, i) => {
                                htmlBody += `
                                    <tr class="hover:bg-blue-50 transition-colors">
                                        <td class="px-4 py-2 text-gray-500">${i+1}</td>
                                        <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer" onclick="showTeamHistory('${t.lag}', 'topp', '${t.sasnrs}')" title="Klicka för att se endast dessa säsonger i Serietabeller">${t.lag}</td>
                                        <td class="px-4 py-2 text-center font-bold text-blue-700">${t.len}</td>
                                    </tr>
                                `;
                            });
                        } else {
                            htmlHead = `<tr><th class="px-4 py-3">Plac</th><th class="px-4 py-3">Lag</th><th class="px-4 py-3 text-center font-bold text-blue-700">Mätvärde</th></tr>`;
                            results.forEach((t, i) => {
                                let val = t[metric.split('_')[0]]; 
                                htmlBody += `
                                    <tr class="hover:bg-blue-50 transition-colors">
                                        <td class="px-4 py-2 text-gray-500">${i+1}</td>
                                        <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer" onclick="showTeamHistory('${t.lag}', 'topp')">${t.lag}</td>
                                        <td class="px-4 py-2 text-center font-bold text-blue-700">${val}</td>
                                    </tr>
                                `;
                            });
                        }
                    }
                }

                // HÄNDELSER OCH OMFÖRFLYTTNINGAR
                else if (cat === 'handelser') {
                    let data = matchData; 
                    let teams = {};
                    
                    data.forEach(d => {
                        if (level !== 'Alla' && String(d.Nivå).trim() !== level) return;
                        let t = d.Analys_Lagnamn;
                        if(!teams[t]) teams[t] = { lag: t, historyMap: {} };
                        
                        let sas = parseInt(d.Säsnr) || 0;
                        if(!teams[t].historyMap[sas]) {
                            teams[t].historyMap[sas] = { year: d.Startår_Numerisk, sStr: d.Säsong, level: parseFloat(d.Nivå)||0, division: d.Division, sasnr: sas, anm: String(d.Anm||'').toLowerCase() };
                        } else {
                            if((parseFloat(d.Nivå)||0) < teams[t].historyMap[sas].level) {
                                teams[t].historyMap[sas].level = parseFloat(d.Nivå)||0;
                                teams[t].historyMap[sas].division = d.Division;
                                teams[t].historyMap[sas].sStr = d.Säsong; 
                                teams[t].historyMap[sas].anm = String(d.Anm||'').toLowerCase();
                            }
                        }
                    });

                    let all_totals = [];

                    Object.values(teams).forEach(t => {
                        t.history = Object.values(t.historyMap);
                        t.history.sort((a,b) => a.sasnr - b.sasnr);
                        
                        let ovan_in = 0, ovan_ut = 0, norm_in = 0, norm_ut = 0, norm_upp = 0, norm_ned = 0;
                        let ovan_in_detaljer = [], ovan_ut_detaljer = [], norm_in_detaljer = [], norm_ut_detaljer = [], norm_upp_detaljer = [], norm_ned_detaljer = [];
                        
                        for(let i=0; i<t.history.length; i++) {
                            let curr = t.history[i];
                            let maxLvl = maxLevelPerSasnr[curr.sasnr] ? Math.floor(maxLevelPerSasnr[curr.sasnr]) : 99;
                            let isLowestLevel = curr.level >= maxLvl;
                            let isNormalOverride = curr.anm.includes('normal');
                            
                            // Klev in i systemet
                            if(i === 0 || curr.sasnr - t.history[i-1].sasnr > 1) {
                                if(!isLowestLevel && curr.sasnr > 5 && curr.level < maxLvl && !isNormalOverride) {
                                    ovan_in++;
                                    ovan_in_detaljer.push(`${curr.sStr} (In på Nivå ${curr.level})`);
                                } else {
                                    norm_in++;
                                    norm_in_detaljer.push(`${curr.sStr} (In på Nivå ${curr.level})`);
                                }
                            }
                            
                            // Utträde eller internt
                            if(i < t.history.length - 1) {
                                if(t.history[i+1].sasnr - curr.sasnr > 1) {
                                    if(!isLowestLevel && !isNormalOverride) {
                                        ovan_ut++; ovan_ut_detaljer.push(`${curr.sStr} (Från Nivå ${curr.level})`);
                                    } else {
                                        norm_ut++; norm_ut_detaljer.push(`${curr.sStr} (Ned från Nivå ${curr.level})`);
                                    }
                                } else {
                                    let diff = curr.level - t.history[i+1].level;
                                    if(diff > 0) { 
                                        norm_upp++; norm_upp_detaljer.push(`${t.history[i+1].sStr} (Upp till Nivå ${t.history[i+1].level})`);
                                    } else if(diff < 0) { 
                                        norm_ned++; norm_ned_detaljer.push(`${t.history[i+1].sStr} (Ned till Nivå ${t.history[i+1].level})`);
                                    }
                                }
                            } else {
                                if(curr.sasnr < maxGlobalSasnr) {
                                    if(!isLowestLevel && !isNormalOverride) {
                                        ovan_ut++; ovan_ut_detaljer.push(`${curr.sStr} (Från Nivå ${curr.level})`);
                                    } else {
                                        norm_ut++; norm_ut_detaljer.push(`${curr.sStr} (Ned från Nivå ${curr.level})`);
                                    }
                                }
                            }
                        }
                        if(ovan_in > 0 || ovan_ut > 0 || norm_in > 0 || norm_ut > 0 || norm_upp > 0 || norm_ned > 0) {
                            all_totals.push({ 
                                lag: t.lag, 
                                ovan_ut: ovan_ut, ovan_in: ovan_in, 
                                norm_in: norm_in, norm_ut: norm_ut,
                                norm_upp: norm_upp, norm_ned: norm_ned,
                                in_det: ovan_in_detaljer.join('<br>'), 
                                ut_det: ovan_ut_detaljer.join('<br>'), 
                                norm_in_det: norm_in_detaljer.join('<br>'), 
                                norm_ut_det: norm_ut_detaljer.join('<br>'),
                                norm_upp_det: norm_upp_detaljer.join('<br>'), 
                                norm_ned_det: norm_ned_detaljer.join('<br>')
                            });
                        }
                    });

                    let finalData = [];
                    if(metric === 'ovan_ut_max') { finalData = all_totals.filter(t => t.ovan_ut > 0).sort((a,b) => b.ovan_ut - a.ovan_ut); } 
                    else if(metric === 'ovan_in_max') { finalData = all_totals.filter(t => t.ovan_in > 0).sort((a,b) => b.ovan_in - a.ovan_in); }
                    else if(metric === 'ut_max') { finalData = all_totals.filter(t => t.norm_ut > 0).sort((a,b) => b.norm_ut - a.norm_ut); }
                    else if(metric === 'in_max') { finalData = all_totals.filter(t => t.norm_in > 0).sort((a,b) => b.norm_in - a.norm_in); }
                    else if(metric === 'norm_upp_max') { finalData = all_totals.filter(t => t.norm_upp > 0).sort((a,b) => b.norm_upp - a.norm_upp); }
                    else if(metric === 'norm_ned_max') { finalData = all_totals.filter(t => t.norm_ned > 0).sort((a,b) => b.norm_ned - a.norm_ned); }
                    
                    results = finalData.slice(0, count);

                    htmlHead = `<tr><th class="px-4 py-3">Plac</th><th class="px-4 py-3">Lag</th><th class="px-4 py-3">Händelser (Kronologiskt)</th><th class="px-4 py-3 text-center font-bold text-blue-700">Mätvärde (Antal)</th></tr>`;
                    
                    results.forEach((t, i) => {
                        let val = t[metric.split('_')[0]]; 
                        if(metric === 'norm_upp_max') val = t.norm_upp;
                        else if(metric === 'norm_ned_max') val = t.norm_ned;
                        
                        let details = '';
                        if(metric === 'ovan_ut_max') details = t.ut_det;
                        else if(metric === 'ovan_in_max') details = t.in_det;
                        else if(metric === 'ut_max') details = t.norm_ut_det;
                        else if(metric === 'in_max') details = t.norm_in_det;
                        else if(metric === 'norm_upp_max') details = t.norm_upp_det;
                        else if(metric === 'norm_ned_max') details = t.norm_ned_det;
                        
                        htmlBody += `
                            <tr class="hover:bg-blue-50 transition-colors">
                                <td class="px-4 py-2 text-gray-500 align-top">${i+1}</td>
                                <td class="px-4 py-2 font-semibold text-blue-600 hover:text-blue-800 cursor-pointer align-top" onclick="showTeamHistory('${t.lag}', 'topp')">${t.lag}</td>
                                <td class="px-4 py-2 text-gray-600 text-xs whitespace-normal align-top leading-relaxed">${details}</td>
                                <td class="px-4 py-2 text-center font-bold text-blue-700 align-top">${val}</td>
                            </tr>
                        `;
                    });
                }
                
                // NY KATEGORI: MÄSTARE OCH SERIESEGRARE (DUBBLA LOGIKER)
                else if (cat === 'vinnare') {
                    let showSM = metric.includes('sm');
                    let sasongWinners = {};
                    
                    let sortedData = [...completedMatchData].sort((a, b) => (parseInt(a.Säsnr)||0) - (parseInt(b.Säsnr)||0) || (parseInt(a.Säsongsdel)||0) - (parseInt(b.Säsongsdel)||0));
                    
                    sortedData.forEach(d => {
                        let sasnr = parseInt(d.Säsnr);
                        if (isNaN(sasnr)) return;
                        if (!sasongWinners[sasnr]) {
                            sasongWinners[sasnr] = { sasong: d.Säsong, serieSegrare: null, smVinnare: null, noSM: false };
                        }
                        
                        let placNum = parseInt(String(d.Plac).replace(/\D/g, '')) || 999;
                        let nivaNum = parseFloat(d.Nivå) || 0;
                        let anm = d.Anm ? String(d.Anm).toLowerCase() : '';
                        let smVinnareStr = d.SM_vinnare ? String(d.SM_vinnare).trim() : '';
                        
                        // 1. Identifiera Seriesegrare Nivå 1
                        if (nivaNum === 1 && placNum === 1) {
                            sasongWinners[sasnr].serieSegrare = d.Analys_Lagnamn;
                        }
                        
                        // 2. Identifiera Explicit SM-vinnare ELLER "Inget SM"
                        if (smVinnareStr === '..') {
                            sasongWinners[sasnr].noSM = true;
                        } else if (smVinnareStr && smVinnareStr !== 'nan') {
                            sasongWinners[sasnr].smVinnare = smVinnareStr;
                        } else if (nivaNum === 1 && placNum === 1) {
                            // Inget skrivet i Excel. Har de vunnit serien kan de vara SM-vinnare,
                            // MEN om Anm säger 'seriemästare' och INTE 'svenska mästare', så delas inget SM ut.
                            if (anm.includes('seriemästare') && !anm.includes('svenska mästare')) {
                                sasongWinners[sasnr].noSM = true;
                            } else {
                                sasongWinners[sasnr].smVinnare = d.Analys_Lagnamn;
                            }
                        }
                    });

                    let winners = [];
                    let sortedSasnrs = Object.keys(sasongWinners).map(Number).sort((a,b) => a-b);
                    
                    sortedSasnrs.forEach(sasnr => {
                        let w = sasongWinners[sasnr];
                        let lag = "";
                        let extra = "";
                        
                        if (showSM) {
                            // Visa Svenska Mästare (Ignorera de år som saknar guld)
                            if (w.noSM || !w.smVinnare) return; 
                            lag = w.smVinnare; 
                            
                            if (w.serieSegrare && w.serieSegrare !== lag) {
                                extra = "Seriesegrare: " + w.serieSegrare;
                            }
                        } else {
                            // Visa Seriesegrare (Nivå 1)
                            lag = w.serieSegrare;
                            if (!lag) return;
                            
                            if (w.noSM) {
                                extra = "Inget SM-Guld utdelades";
                            } else if (w.smVinnare && w.smVinnare !== lag) {
                                extra = "Svensk Mästare: " + w.smVinnare;
                            }
                        }
                        
                        winners.push({
                            sasnr: sasnr,
                            sasong: w.sasong,
                            lag: lag,
                            extra: extra
                        });
                    });
                    
                    if(metric.includes('kronologisk')) {
                        results = winners; 
                        let titlePrimary = showSM ? "Svenska Mästare" : "Seriesegrare (Nivå 1)";
                        htmlHead = `<tr><th class="px-4 py-3">Säsong</th><th class="px-4 py-3">${titlePrimary}</th><th class="px-4 py-3 text-gray-500">Notering</th></tr>`;
                        results.forEach(w => {
                            htmlBody += `
                                <tr class="hover:bg-blue-50 transition-colors">
                                    <td class="px-4 py-2 font-medium text-gray-700">${w.sasong}</td>
                                    <td class="px-4 py-2 font-bold text-green-700 cursor-pointer" onclick="showTeamHistory('${w.lag.replace('Seriemästare: ', '')}', 'topp')">${w.lag}</td>
                                    <td class="px-4 py-2 text-sm text-gray-500 italic">${w.extra}</td>
                                </tr>
                            `;
                        });
                    } else {
                        let counts = {};
                        winners.forEach(w => {
                            let l = w.lag.replace('Seriemästare: ', '');
                            if(!counts[l]) counts[l] = 0;
                            counts[l]++;
                        });
                        let arrCounts = Object.keys(counts).map(k => ({ lag: k, antal: counts[k] }));
                        arrCounts.sort((a,b) => b.antal - a.antal);
                        results = arrCounts;
                        
                        let titleCount = showSM ? "Antal SM-Guld" : "Antal Seriesegrar (Nivå 1)";
                        htmlHead = `<tr><th class="px-4 py-3">Plac</th><th class="px-4 py-3">Lag</th><th class="px-4 py-3 text-center font-bold text-green-700">${titleCount}</th></tr>`;
                        results.forEach((t, i) => {
                            htmlBody += `
                                <tr class="hover:bg-blue-50 transition-colors">
                                    <td class="px-4 py-2 text-gray-500">${i+1}</td>
                                    <td class="px-4 py-2 font-semibold text-blue-600 cursor-pointer" onclick="showTeamHistory('${t.lag}', 'topp')">${t.lag}</td>
                                    <td class="px-4 py-2 text-center font-bold text-green-700">${t.antal}</td>
                                </tr>
                            `;
                        });
                    }
                }

                // DISTRIKT ELLER KOMMUN
                else if (cat === 'distrikt' || cat === 'kommun') {
                    let areaMap = {};
                    let groupKey = cat === 'distrikt' ? 'Distrikt' : 'Kommun';
                    let groupLabel = cat === 'distrikt' ? 'Distrikt' : 'Kommun';

                    completedMatchData.forEach(d => {
                        if (level !== 'Alla' && String(d.Nivå).trim() !== level) return;
                        let area = d[groupKey] || `Okänt ${groupLabel.toLowerCase()}`;
                        if(!areaMap[area]) {
                            areaMap[area] = { Area: area, Sp: 0, V: 0, O: 0, F: 0, Gjorda: 0, Insl: 0, P: 0, P_3p: 0, unika_lag: new Set() };
                        }
                        let entry = areaMap[area];
                        entry.Sp += d.Sp;
                        entry.V += d.V;
                        entry.O += d.O;
                        entry.F += d.F;
                        entry.Gjorda += d.Gjorda;
                        entry.Insl += d.Insl;
                        entry.P += d.P;
                        entry.P_3p += (Number(d.V) * 3) + (Number(d.O) * 1);
                        entry.unika_lag.add(d.Analys_Lagnamn);
                    });
                    
                    let arr = Object.values(areaMap).map(t => {
                        t.lag_count = t.unika_lag.size;
                        t.p_snitt = t.Sp > 0 ? (t.P_3p / t.Sp) : 0;
                        return t;
                    });
                    
                    let isFloat = false;
                    let valKey = '';
                    if (metric === 'p_max') { arr.sort((a,b) => b.P - a.P); valKey = 'P'; }
                    else if (metric === 'gj_max') { arr.sort((a,b) => b.Gjorda - a.Gjorda); valKey = 'Gjorda'; }
                    else if (metric === 'lag_max') { arr.sort((a,b) => b.lag_count - a.lag_count); valKey = 'lag_count'; }
                    else if (metric === 'p_snitt_max') { arr.sort((a,b) => b.p_snitt - a.p_snitt); valKey = 'p_snitt'; isFloat = true; }
                    
                    results = arr.slice(0, count);
                    
                    htmlHead = `<tr><th class="px-4 py-3">Plac</th><th class="px-4 py-3">${groupLabel}</th><th class="px-4 py-3 text-center">Unika Lag</th><th class="px-4 py-3 text-center">Sp</th><th class="px-4 py-3 text-center">V-O-F</th><th class="px-4 py-3 text-center">Gj-In</th><th class="px-4 py-3 text-center font-bold text-blue-700">Mätvärde</th></tr>`;
                    
                    results.forEach((t, i) => {
                        let displayVal = formatVal(t[valKey], isFloat);
                        htmlBody += `
                            <tr class="hover:bg-blue-50 transition-colors">
                                <td class="px-4 py-2 text-gray-500">${i+1}</td>
                                <td class="px-4 py-2 font-semibold text-gray-800">${t.Area}</td>
                                <td class="px-4 py-2 text-center">${t.lag_count}</td>
                                <td class="px-4 py-2 text-center">${t.Sp}</td>
                                <td class="px-4 py-2 text-center">${t.V}&ndash;${t.O}&ndash;${t.F}</td>
                                <td class="px-4 py-2 text-center">${t.Gjorda}&ndash;${t.Insl}</td>
                                <td class="px-4 py-2 text-center font-bold text-blue-700">${displayVal}</td>
                            </tr>
                        `;
                    });
                }

                document.getElementById('toppHead').innerHTML = htmlHead;
                document.getElementById('toppBody').innerHTML = htmlBody;
                document.getElementById('toppCounter').innerText = `Visar ${results.length} resultat.`;
            } catch(e) {
                console.error("Error in renderTopplistor:", e);
            }
        }

        // RENDER: ADMINISTRATION
        function renderAdmin() {
            let totSp = 0, totGj = 0, totIn = 0;
            let mathErrors = [];
            
            completedMatchData.forEach(d => {
                totSp += Number(d.Sp) || 0;
                totGj += Number(d.Gjorda) || 0;
                totIn += Number(d.Insl) || 0;
                
                let v = Number(d.V) || 0;
                let o = Number(d.O) || 0;
                let f = Number(d.F) || 0;
                let sp = Number(d.Sp) || 0;
                
                if(v + o + f !== sp && sp > 0) {
                    mathErrors.push(`[${d.Säsong}] ${d.Analys_Lagnamn} (Sp: ${sp} | V: ${v}, O: ${o}, F: ${f})`);
                }
            });
            
            let totMatcher = totSp / 2;
            let matchText = (totSp % 2 !== 0) ? `${Math.floor(totMatcher).toLocaleString()} (Obs! Spelade matcher totalt är ojämt: ${totSp})` : totMatcher.toLocaleString();
            let valWarn = (totGj !== totIn) ? `<span class="text-red-600 ml-2 font-bold">(Diff! Insläppta är ${totIn.toLocaleString()})</span>` : '';
            
            document.getElementById('adminStatsList').innerHTML = `
                <li><span class="font-semibold text-gray-800">Totalt antal tabellrader (Nivå 1-5):</span> ${adminData.total_rows.toLocaleString()}</li>
                <li><span class="font-semibold text-gray-800">Totalt antal spelade matcher:</span> ${matchText}</li>
                <li><span class="font-semibold text-gray-800">Totalt antal gjorda mål:</span> ${totGj.toLocaleString()} ${valWarn}</li>
                <li class="mt-4 border-t pt-2"><span class="font-semibold text-gray-800">Unika Standard-lagnamn:</span> ${adminData.unique_teams}</li>
                <li><span class="font-semibold ${adminData.orphans_count > 0 ? 'text-red-600' : 'text-gray-800'}">Antal föräldralösa lag:</span> ${adminData.orphans_count} st</li>
            `;
            
            let errHtml = '';
            if(mathErrors.length > 0) {
                mathErrors.forEach(e => { errHtml += `<li>${e}</li>`; });
            } else {
                errHtml = '<li class="text-green-600 font-bold">Inga V+O+F fel hittades!</li>';
            }
            document.getElementById('adminMathErrors').innerHTML = errHtml;
            
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
        }

        function exportCSV() {
            let csv = [];
            let activeTab = document.querySelector('.tab-content.active');
            let rows = activeTab.querySelectorAll("table tr");
            if(rows.length === 0) return alert("Det finns ingen tabell att exportera i denna flik.");

            for (let i = 0; i < rows.length; i++) {
                let row = [], cols = rows[i].querySelectorAll("td, th");
                for (let j = 0; j < cols.length; j++) {
                    let clone = cols[j].cloneNode(true);
                    let badges = clone.querySelectorAll('.ny-badge, .warn-badge, .rel-badge, .text-orange-500, .text-blue-500, .text-yellow-500, .text-red-600');
                    badges.forEach(b => b.remove());
                    let text = clone.innerText.replace(/–/g, '-').replace(/"/g, '""').replace(/⚠️/g, '').replace(/▼/g, '').replace(/★/g, '').trim(); 
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

        function runLocalPythonScript() {
            document.getElementById('scriptModal').classList.remove('hidden');
        }

        window.onload = function() {
            populateDropdown('maratonStartYear', completedYears);
            populateDropdown('maratonEndYear', completedYears, true, true);
            
            if(Object.keys(snabbvalMap).length > 0) {
                let snabbvalHtml = '<option value="Inget">-- Använd egna filter nedan --</option>';
                Object.keys(snabbvalMap).sort().forEach(k => {
                    snabbvalHtml += `<option value="${k}">${k}</option>`;
                });
                document.getElementById('maratonSnabbval').innerHTML = snabbvalHtml;
            }
            
            if(Object.keys(focusMap).length > 0) {
                let focusHtml = '<option value="Inget">-- Välj Snabbval --</option>';
                Object.keys(focusMap).sort().forEach(k => {
                    focusHtml += `<option value="${k}">${k}</option>`;
                });
                document.getElementById('vandringKombination').innerHTML = focusHtml;
                document.getElementById('placeringKombination').innerHTML = focusHtml;
            }

            let sy = document.getElementById('sasongYear');
            sy.innerHTML = '<option value="Alla">-- Alla Säsonger --</option>';
            [...completedSeasonsObj].reverse().forEach(seq => { 
                sy.innerHTML += `<option value="${seq.sStr}">${seq.sStr}</option>`; 
            });
            if(sy.options.length > 1) sy.selectedIndex = 1;
            
            populateDropdown('maratonLevel', allLevels, false, false, true);
            populateDropdown('sasongLevel', allLevels, false, false, true);
            populateDropdown('vandringLevel', allLevels, false, false, true);
            populateDropdown('toppLevel', allLevels, false, false, true);
            populateDropdown('placeringLevel', allLevels, false, false, true);
            
            populateDropdown('placeringSpecific', [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]);

            populateDropdown('sasongTeam', allTeams);
            populateDropdown('maratonDivision', allDivisions);
            populateDropdown('sasongDivision', allDivisions);
            populateDropdown('vandringDivision', allDivisions);
            populateDropdown('placeringDivision', allDivisions);
            
            // Fyll dropdowns för Klubbålder med standardvalet "Alla"
            let decList = ['Alla'].concat(allDecades);
            let yrList = ['Alla'].concat(allBildadYears);
            populateDropdown('bildadDecennium', decList);
            populateDropdown('bildadYear', yrList);
            
            let tCat = document.getElementById('toppCategory');
            let optM = document.createElement('option');
            optM.value = 'vinnare';
            optM.innerHTML = 'Mästare (Guld)';
            tCat.appendChild(optM);
            
            toppMetrics['vinnare'] = {
                'abs': [
                    {id: 'kronologisk_sm', text: 'Svenska Mästare (Alla, kronologiskt)'},
                    {id: 'antal_sm', text: 'Flest SM-Guld (Totalt)'},
                    {id: 'kronologisk_serie', text: 'Seriesegrare Nivå 1 (Alla, kronologiskt)'},
                    {id: 'antal_serie', text: 'Flest Seriesegrar Nivå 1 (Totalt)'}
                ],
                'kvot': []
            };

            updateToppMetrics();
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
                               .replace('__ONGOING_SEASON__', str(PAGAENDE_SASONG) if PAGAENDE_SASONG else 'null')\
                               .replace('__USE_SM_VINNARE__', 'true' if ANVAND_SM_VINNARE_FOR_GULD else 'false')\
                               .replace('__DASHBOARD_TITLE__', DASHBOARD_TITEL)
    
    output_path = os.path.join(project_root, HTML_UTDATA_FILNAMN)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_output)
        
    print(f"✅ HTML Dashboard skapad: {os.path.basename(output_path)}")

if __name__ == "__main__":
    master_df, _, df_snabbval = get_master_data()
    if master_df is not None:
        export_html_dashboard(master_df, df_snabbval)
        print("\nAllt klart! Du hittar din nya dashboard-fil i mappen ovanför skriptet.")