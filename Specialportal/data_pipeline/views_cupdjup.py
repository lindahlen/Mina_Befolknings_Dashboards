import os
import sys
import pandas as pd
import json

# ==========================================
# SÖKVÄGAR
# ==========================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_folder)
    main_folder = os.path.abspath(os.path.join(current_folder, '..'))
    excel_folder = os.path.join(main_folder, 'excel_filer')
    json_folder = os.path.join(main_folder, 'json_data')
except NameError:
    pass 

filnamn_excel = os.path.join(excel_folder, "Cupen_Svenska_matcher_samlade.xlsx")
filnamn_json = os.path.join(json_folder, "cup_djupdykning.json")
output_file = os.path.join(main_folder, "Matchanalys_Cupen_Djup_Dashboard.html")

print("Hämtar grundläggande matchfakta...")
base_matches = {}
try:
    df_cup = pd.read_excel(filnamn_excel, sheet_name="Cupen")
    for _, r in df_cup.iterrows():
        m_id = r.get('Match_ID')
        if pd.notna(m_id) and str(m_id).strip() != "":
            mid_str = str(int(float(str(m_id))))
            sasong = str(r.get('Säsong', '')).replace('.0', '').strip()
            
            datum = r.get('Matchdatum', '')
            if pd.notna(datum):
                if isinstance(datum, pd.Timestamp): datum = datum.strftime('%Y-%m-%d')
                else: datum = str(datum).split(' ')[0]
            else: datum = str(r.get('År', ''))
                
            win_team = ""
            adv = r.get('Avancerade')
            if pd.notna(adv) and str(adv).strip() != "":
                try:
                    adv_int = int(float(adv))
                    if adv_int in [1, 5]: win_team = str(r.get('Hemmalag', '')).strip()
                    elif adv_int in [2, 4, 6]: win_team = str(r.get('Bortalag', '')).strip()
                except: pass
            
            if not win_team:
                try:
                    hm = int(float(r.get('HM', 0)))
                    bm = int(float(r.get('BM', 0)))
                    if hm > bm: win_team = str(r.get('Hemmalag', '')).strip()
                    elif bm > hm: win_team = str(r.get('Bortalag', '')).strip()
                except: pass

            base_matches[mid_str] = {
                "sasong": sasong,
                "datum": datum,
                "fas": str(r.get('Fas', '')).strip(),
                "hemma": str(r.get('Hemmalag', '')).strip(),
                "borta": str(r.get('Bortalag', '')).strip(),
                "hm": str(r.get('HM', '')).replace('.0', ''),
                "bm": str(r.get('BM', '')).replace('.0', ''),
                "fh": str(r.get('Förl_H', '')).replace('.0', ''),
                "fb": str(r.get('Förl_B', '')).replace('.0', ''),
                "sh": str(r.get('Straff_H', '')).replace('.0', ''),
                "sb": str(r.get('Straff_B', '')).replace('.0', ''),
                "publik": str(r.get('Publik', '')).replace('.0', ''),
                "domare": str(r.get('Domare', '')).strip(),
                "arena": str(r.get('Arena', '')).strip(),
                "ort": str(r.get('Ort', '')).strip(),
                "winner": win_team,
                "avancerade": str(r.get('Avancerade', '')).replace('.0', '')
            }
except Exception as e:
    print(f"Kunde inte läsa Cup-excelen för metadata: {e}")
    sys.exit(1)

print("Laddar in djupdyknings-databasen (JSON)...")
try:
    with open(filnamn_json, 'r', encoding='utf-8') as f:
        djup_data_str = f.read()
except Exception as e:
    print(f"Kunde inte läsa JSON-filen. Har du kört bygg_cup_djupdykning.py? Felet: {e}")
    sys.exit(1)

base_matches_json = json.dumps(base_matches, ensure_ascii=False)

print("Genererar Dashboard...")

html_template = """
<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Djupdykning - Svenska Cupen</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .custom-scroll::-webkit-scrollbar { width: 8px; height: 8px; }
        .custom-scroll::-webkit-scrollbar-track { background: #f1f1f1; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
        .tab-btn.active { border-bottom: 2px solid #2563eb; color: #1e3a8a; font-weight: 600; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .mat-subtab-btn.active { border-bottom: 2px solid #2563eb; color: #1e3a8a; font-weight: 700; }
        .mat-subtab-content { display: none; }
        .mat-subtab-content.active { display: block; }
        .match-box { transition: transform 0.1s; cursor: pointer; }
        .match-box:hover { transform: translateY(-2px); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        .info-card { transition: all 0.2s; }
        .info-card:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
    </style>
</head>
<body class="bg-slate-50 text-slate-800 font-sans min-h-screen flex flex-col">

    <header class="bg-blue-800 text-white shadow-md border-b-4 border-yellow-500">
        <div class="max-w-7xl mx-auto px-4 py-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
                <div class="flex items-center gap-3">
                    <span class="text-3xl">🏆</span>
                    <h1 class="text-3xl font-bold tracking-tight">Svenska Cupen: Fördjupning</h1>
                </div>
                <p class="text-blue-200 mt-1 pl-11">Djupdykning i slutspel, mästare och målskyttar</p>
                <p class="text-xs text-blue-400 mt-1 pl-11">Sammanställning av Jimmy Lindahl</p>
            </div>
            <a href="Matchanalys_SvenskaCupen_Dashboard.html" class="inline-flex items-center justify-center text-blue-100 hover:text-white transition-colors text-sm font-medium bg-blue-900 hover:bg-blue-700 px-4 py-2 rounded-md shadow-sm border border-blue-700">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
                Tillbaka till matchlistan
            </a>
        </div>
    </header>

    <nav class="bg-white shadow-sm sticky top-0 z-20 border-b border-slate-200">
        <div class="max-w-7xl mx-auto px-4 flex overflow-x-auto custom-scroll">
            <button onclick="switchTab('slutspel')" id="btn-slutspel" class="tab-btn active whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-600">Slutspel & Finaler</button>
            <button onclick="switchTab('vag')" id="btn-vag" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-600">Mästarens Väg</button>
            <button onclick="switchTab('skyttar')" id="btn-skyttar" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-600">Skytteligor</button>
            <button onclick="switchTab('topplistor')" id="btn-topplistor" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-600">Topplistor & Historik</button>
            <button onclick="switchTab('matrix')" id="btn-matrix" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-600">Matris & Grafer</button>
            <button onclick="switchTab('players')" id="btn-players" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-600">Spelarregister</button>
            <button onclick="switchTab('analys')" id="btn-tab-analys" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-600">Analys</button>
            <button onclick="switchTab('admin')" id="btn-admin" class="tab-btn whitespace-nowrap py-4 px-6 text-slate-500 hover:text-blue-600">Admin (Varningar)</button>
        </div>
    </nav>

    <main class="flex-grow max-w-7xl mx-auto px-4 py-8 w-full">
        
        <!-- GEMENSAM SÄSONGSVÄLJARE -->
        <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6 flex flex-col lg:flex-row gap-6 items-center" id="global-season-selector">
            <div class="w-full lg:w-1/4">
                <label class="block text-sm font-medium text-slate-700 mb-1">Välj Säsong</label>
                <div class="flex items-center gap-1">
                    <button onclick="changeSeason(1)" class="p-3 bg-slate-100 hover:bg-blue-100 text-slate-600 hover:text-blue-700 rounded-md transition-colors border border-slate-200" title="Föregående säsong i listan">◀</button>
                    <select id="season-select" onchange="renderSeasonData()" class="w-full border border-slate-300 rounded-md p-3 bg-slate-50 focus:ring-blue-500 font-bold text-slate-800 text-base shadow-inner"></select>
                    <button onclick="changeSeason(-1)" class="p-3 bg-slate-100 hover:bg-blue-100 text-slate-600 hover:text-blue-700 rounded-md transition-colors border border-slate-200" title="Nästa säsong i listan">▶</button>
                </div>
            </div>
            
            <div id="season-header-info" class="hidden w-full lg:w-3/4 grid grid-cols-1 md:grid-cols-3 gap-4">
                <div class="info-card bg-gradient-to-br from-yellow-50 to-amber-100 p-4 rounded-xl border border-yellow-200 shadow-sm flex flex-col justify-center relative">
                    <div class="absolute top-2 right-2 text-2xl opacity-20">©️</div>
                    <span class="text-[10px] font-bold text-yellow-600 uppercase tracking-widest">Kapten, Mästarna</span>
                    <span class="font-black text-yellow-900 text-lg mt-1 truncate" id="h-kapten">-</span>
                </div>
                <div class="info-card bg-gradient-to-br from-blue-50 to-indigo-100 p-4 rounded-xl border border-blue-200 shadow-sm flex flex-col justify-center relative">
                    <div class="absolute top-2 right-2 text-2xl opacity-20">👔</div>
                    <span class="text-[10px] font-bold text-blue-600 uppercase tracking-widest">Tränare, Mästarna</span>
                    <span class="font-black text-blue-900 text-base mt-1 leading-tight" id="h-tranare1">-</span>
                </div>
                <div class="info-card bg-gradient-to-br from-slate-100 to-slate-200 p-4 rounded-xl border border-slate-300 shadow-sm flex flex-col justify-center relative">
                    <div id="pokal-img-container" class="absolute top-2 right-2 text-2xl opacity-20">🏆</div>
                    <span class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Pokal</span>
                    <span class="font-black text-slate-800 text-sm mt-1 leading-tight" id="h-pokal">-</span>
                </div>
            </div>
        </div>

        <!-- FLIK 1: SLUTSPEL -->
        <section id="tab-slutspel" class="tab-content active">
            <div id="slutspel-content" class="hidden">
                <div class="flex flex-col lg:flex-row gap-8 overflow-x-auto custom-scroll pb-6 items-stretch min-h-[450px]" id="tree-container">
                </div>
            </div>
            <div id="slutspel-placeholder" class="text-center py-20 text-slate-400">Välj en säsong ovan för att se slutspelet.</div>
        </section>

        <!-- FLIK 2: MÄSTARENS VÄG -->
        <section id="tab-vag" class="tab-content">
            <div id="vag-content" class="hidden max-w-3xl mx-auto">
                <h3 class="text-xl font-bold text-slate-800 mb-4 border-b pb-2">Mästarens väg till titeln</h3>
                <div id="vag-list" class="flex flex-col gap-3"></div>
            </div>
            <div id="vag-placeholder" class="text-center py-20 text-slate-400">Välj en säsong ovan för att se mästarens väg.</div>
        </section>

        <!-- FLIK 3: SKYTTELIGOR -->
        <section id="tab-skyttar" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6 flex flex-col gap-4">
                <div class="flex flex-wrap gap-4 border-b border-slate-100 pb-4">
                    <button onclick="renderSkytteliga('Slutomgångar')" id="btn-sk-slut" class="px-4 py-2 bg-blue-600 text-white rounded font-medium shadow-sm transition-colors">Mål i Slutomgångar</button>
                    <button onclick="renderSkytteliga('Mästarna')" id="btn-sk-mast" class="px-4 py-2 bg-slate-200 text-slate-700 rounded font-medium shadow-sm transition-colors">Mål av Mästarlag</button>
                    <button onclick="renderTopScorersPerSeason()" id="btn-sk-season" class="px-4 py-2 bg-slate-200 text-slate-700 rounded font-medium shadow-sm transition-colors">Årets Skyttekung (Mästarna)</button>
                </div>
                
                <div id="sk-filters-container" class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end transition-opacity duration-300">
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Filtrera Klubb</label>
                        <input type="text" id="sk-filter-club" onkeyup="renderSkytteliga(CURRENT_SKYTTELIGA_TYP)" placeholder="T.ex. Malmö FF" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Filtrera Fas</label>
                        <select id="sk-filter-fas" onchange="renderSkytteliga(CURRENT_SKYTTELIGA_TYP)" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500">
                            <option value="">Alla faser</option>
                            <option value="final">Finaler (inkl omspel)</option>
                            <option value="semi">Semifinaler</option>
                            <option value="kvart">Kvartsfinaler</option>
                            <option value="grupp" class="mast-only">Gruppspel</option>
                            <option value="tidiga" class="mast-only">Tidiga omgångar (inkl. 1/8)</option>
                        </select>
                    </div>
                    <div class="md:col-span-2 flex flex-col gap-2 justify-center pb-1">
                        <div class="flex flex-col md:flex-row gap-4">
                            <label class="flex items-center gap-2 cursor-pointer text-slate-700 font-medium text-sm">
                                <input type="checkbox" id="sk-filter-gwg" onchange="renderSkytteliga(CURRENT_SKYTTELIGA_TYP)" class="w-4 h-4 text-blue-600">
                                Visa endast Matchavgörande mål (GWG)
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer text-slate-700 font-medium text-sm">
                                <input type="checkbox" id="sk-filter-no-owngoals" onchange="renderSkytteliga(CURRENT_SKYTTELIGA_TYP)" class="w-4 h-4 text-blue-600">
                                Exklusive självmål
                            </label>
                        </div>
                        <div class="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 mt-1 bg-slate-50 p-2 rounded border border-slate-200">
                            <span class="text-xs font-bold text-slate-500 uppercase tracking-widest">Straffläggning:</span>
                            <label class="flex items-center gap-1 cursor-pointer text-slate-700 font-medium text-sm">
                                <input type="radio" name="sk-filter-pen" value="exclude" onchange="renderSkytteliga(CURRENT_SKYTTELIGA_TYP)" checked class="w-4 h-4 text-blue-600">
                                Exkludera
                            </label>
                            <label class="flex items-center gap-1 cursor-pointer text-slate-700 font-medium text-sm">
                                <input type="radio" name="sk-filter-pen" value="include" onchange="renderSkytteliga(CURRENT_SKYTTELIGA_TYP)" class="w-4 h-4 text-blue-600">
                                Inkludera
                            </label>
                            <label class="flex items-center gap-1 cursor-pointer text-slate-700 font-medium text-sm">
                                <input type="radio" name="sk-filter-pen" value="only" onchange="renderSkytteliga(CURRENT_SKYTTELIGA_TYP)" class="w-4 h-4 text-blue-600">
                                Enbart straffar
                            </label>
                        </div>
                    </div>
                </div>
            </div>

            <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                <h3 id="skytteliga-title" class="px-6 py-4 bg-slate-50 border-b border-slate-200 font-bold text-lg text-slate-800">Skytteliga</h3>
                <div class="overflow-x-auto custom-scroll" style="max-height: 700px;">
                    <table class="w-full text-left text-sm">
                        <thead id="skytteliga-head" class="bg-slate-100 text-slate-600 font-medium sticky top-0 shadow-sm border-b border-slate-200">
                            <tr>
                                <th class="px-4 py-3">Spelare</th>
                                <th class="px-4 py-3 text-center">Antal Mål</th>
                                <th class="px-4 py-3">Klubb (Vid målet)</th>
                                <th class="px-4 py-3">Säsonger</th>
                            </tr>
                        </thead>
                        <tbody id="skytteliga-body" class="divide-y divide-slate-100"></tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- FLIK 4: TOPPLISTOR & HISTORIK -->
        <section id="tab-topplistor" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                    <div>
                        <h2 class="text-xl font-bold mb-1 flex items-center gap-2"><span class="text-2xl">🥇</span> Historik & Rekord</h2>
                        <p class="text-sm text-slate-500">Utforska kronologiska mästarlistor och unika spelarrekord från finalerna.</p>
                    </div>
                </div>
                <div class="mt-6 flex flex-col md:flex-row gap-4 items-end">
                    <div class="w-full md:w-1/3">
                        <label class="block text-sm font-medium text-slate-700 mb-1">Välj Topplista</label>
                        <select id="toplist-category" onchange="renderToplist()" class="w-full border border-slate-300 rounded-md p-2 bg-slate-50 focus:ring-blue-500">
                            <option value="champions_chronological">👑 Kronologisk Mästarlängd (Kaptener & Tränare)</option>
                            <option disabled>────────── Spelarrekord i Finaler ──────────</option>
                            <option value="flest_titlar">Flest Cuptitlar (Guld)</option>
                            <option value="flest_finaler">Flest Cupfinaler (Antal Spelade Finaler)</option>
                            <option value="flest_finalmal">Flest Finalmål (Exkl. straffläggning)</option>
                            <option value="oldest_player">Äldsta finalspelaren</option>
                            <option value="youngest_player">Yngsta finalspelaren</option>
                            <option value="oldest_scorer">Äldsta finalmålskytten (Exkl. straffläggning)</option>
                            <option value="youngest_scorer">Yngsta finalmålskytten (Exkl. straffläggning)</option>
                            <option value="longest_span">Längst period mellan första och sista finalen</option>
                        <option disabled>────────── Visste du att... ──────────</option>
                            <option value="multi_club_winners">Klubb-hopparna (Cupguld med olika klubbar)</option>
                            <option value="fastest_goals">Snabbaste finalmålen genom tiderna</option>
                            <option value="super_subs">Superinhopparna (Mål som inbytt i en final)</option>
                            <option value="silver_no_gold">Final-förlorarna (Flest silver utan guld)</option>
                            <option value="captain_winners">Kaptensligan (Lyft pokalen flest gånger)</option>
                            <option value="gwg_knockout">Clutch-spelarna: Avgörande mål (Kvart till Final)</option>
                            <option value="penalty_shootout">Straffspecialisterna (Mål i straffavgöranden)</option>
                            <option value="referee_knockout">Domarligan (Flest dömda slutspelsmatcher)</option>
                        <option disabled>────────── Demografi & Ålder ──────────</option>
                            <option value="birth_months">Födelsemånad (Relativ Ålderseffekt)</option>
                            <option value="birth_decades">Födelsedecennium (När är spelarna födda?)</option>
                            <option value="rae_over_time">RAE över tid (Har ålderseffekten ökat?)</option>
                        </select>
                    </div>
                    <div class="w-full md:w-2/3 pb-2 transition-opacity duration-300 flex flex-col sm:flex-row gap-2" id="toplist-filters-container">
    <label class="flex items-center gap-2 cursor-pointer text-slate-700 font-medium text-sm bg-yellow-50 border border-yellow-200 p-2 rounded-md">
        <input type="checkbox" id="toplist-only-champ" onchange="renderToplist()" class="w-4 h-4 text-yellow-600">
        Visa ENDAST spelare när de vann Cupen (Cupmästare)
    </label>
    
    <!-- Uppdaterad label med relativ positionering för tooltip -->
    <label id="toplist-played-container" class="flex items-center gap-2 cursor-pointer text-slate-700 font-medium text-sm bg-emerald-50 border border-emerald-200 p-2 rounded-md relative">
        <input type="checkbox" id="toplist-only-played" onchange="renderToplist()" class="w-4 h-4 text-emerald-600">
        <span>Visa enbart de som deltog på planen</span>
        
        <!-- NY I-KNAPP FÖR RAE (Dold som standard) -->
        <span id="rae-info-btn" class="hidden ml-1 group cursor-help text-emerald-600 hover:text-emerald-800 flex items-center">
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path></svg>
            
            <!-- Själva Tooltippen (Visas vid hover) -->
            <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block w-72 p-3 bg-slate-800 text-white text-xs rounded shadow-lg z-[100] pointer-events-none normal-case font-normal leading-relaxed text-left">
                <strong class="text-emerald-300 text-sm mb-1 block">Relativa Ålderseffekten (RAE)</strong>
                Ett välkänt fenomen inom idrott där barn födda tidigt på året (kvartal 1) överrepresenteras på elitnivå. Eftersom de var fysiskt mognare än sina jämnåriga under ungdomsåren, valdes de oftare ut till akademier, vilket gav dem bättre förutsättningar hela vägen upp i vuxen ålder.
            </div>
        </span>
    </label>
</div>
                </div>
            </div>

            <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                <h3 id="toplist-title" class="px-6 py-4 bg-slate-50 border-b border-slate-200 font-bold text-lg text-slate-800">Topplista</h3>
                <div class="overflow-x-auto custom-scroll" style="max-height: 800px;">
                    <table class="w-full text-left text-sm whitespace-nowrap">
                        <thead id="toplist-head" class="bg-slate-100 text-slate-600 font-medium sticky top-0 shadow-sm border-b border-slate-200">
                        </thead>
                        <tbody id="toplist-body" class="divide-y divide-slate-100"></tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- FLIK 5: MATRIS & GRAFER -->
        <section id="tab-matrix" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <div class="flex gap-4 border-b border-slate-200 pb-2">
                    <button onclick="switchMatrixTab('dubbeln')" id="btn-mat-dubbeln" class="mat-subtab-btn active text-blue-600 border-b-2 border-blue-600 px-2 pb-1 transition-colors">Dubbeln (SM & Cup)</button>
                    <button onclick="switchMatrixTab('facit')" id="btn-mat-facit" class="mat-subtab-btn font-medium text-slate-500 hover:text-blue-600 px-2 pb-1 transition-colors">Klubbarnas Facit</button>
                    <button onclick="switchMatrixTab('grafer')" id="btn-mat-grafer" class="mat-subtab-btn font-medium text-slate-500 hover:text-blue-600 px-2 pb-1 transition-colors">Historiska Grafer</button>
                </div>

                <!-- SUB-FLIK: DUBBELN -->
                <div id="mat-sub-dubbeln" class="mat-subtab-content active mt-4">
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-end mb-4 gap-4">
                        <div>
                            <div class="flex items-center gap-3 mb-2">
                                <span class="text-2xl">⚔️</span>
                                <h2 class="text-xl font-bold text-slate-800">Dubbeln (SM-Guld & Cupguld)</h2>
                            </div>
                            <p class="text-slate-500 text-sm max-w-2xl">Klubbar som lyckats med bedriften att vinna både Allsvenskan och Svenska Cupen.</p>
                        </div>
                        <div class="flex flex-col gap-2 bg-slate-50 p-3 rounded-md border border-slate-200">
                            <label class="flex items-center gap-2 cursor-pointer text-sm font-medium text-slate-700">
                                <input type="checkbox" id="mat-double-only" onchange="renderMatrixAndGraphs()" class="w-4 h-4 text-blue-600"> Visa enbart lagen som vann dubbeln
                            </label>
                            <label class="flex items-center gap-2 cursor-pointer text-sm font-medium text-slate-700">
                                <input type="checkbox" id="mat-double-shifted" onchange="renderMatrixAndGraphs()" class="w-4 h-4 text-blue-600"> Förskjuten dubbel (SM-Guld året innan)
                            </label>
                        </div>
                    </div>
                    <div class="overflow-x-auto custom-scroll max-h-[600px] border rounded-lg">
                        <table class="w-full text-left text-sm whitespace-nowrap relative">
                            <thead class="bg-slate-100 text-slate-600 font-medium sticky top-0 z-10 shadow-sm">
                                <tr><th class="px-4 py-3">Säsong (Cupen)</th><th class="px-4 py-3 font-bold text-yellow-600">Cupmästare</th><th class="px-4 py-3">SM-vinnare</th><th class="px-4 py-3 text-center">Status</th></tr>
                            </thead>
                            <tbody id="matrix-doubles-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                        </table>
                    </div>
                </div>

                <!-- SUB-FLIK: FACIT -->
                <div id="mat-sub-facit" class="mat-subtab-content mt-4">
                    <div class="flex items-center gap-3 mb-2">
                        <span class="text-2xl">📊</span>
                        <h2 class="text-xl font-bold text-slate-800">Klubbarnas Facit i Slutspelet</h2>
                    </div>
                    <p class="text-slate-500 text-sm max-w-4xl mb-4">En ackumulerad matris över hur många säsonger respektive klubb har spelat i slutspelets olika faser. Siffran visar antal <b>unika säsonger</b> som laget nått minst den fasen.</p>
                    <div class="overflow-x-auto custom-scroll max-h-[600px] border rounded-lg">
                        <table class="w-full text-left text-sm whitespace-nowrap relative">
                            <thead class="bg-slate-100 text-slate-600 font-medium sticky top-0 z-10 shadow-sm">
                                <tr>
                                    <th class="px-4 py-3 sortable-th" onclick="sortMatrix('team')">Klubb ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center text-yellow-600 font-bold" onclick="sortMatrix('guld')">Guld ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center" onclick="sortMatrix('final')">Spelat Final ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center" onclick="sortMatrix('semi')">Spelat Semifinal ↕</th>
                                    <th class="px-4 py-3 sortable-th text-center" onclick="sortMatrix('kvart')">Spelat Kvartsfinal ↕</th>
                                </tr>
                            </thead>
                            <tbody id="matrix-phases-body" class="divide-y divide-slate-100 text-slate-700"></tbody>
                        </table>
                    </div>
                </div>

                <!-- SUB-FLIK: GRAFER -->
                <div id="mat-sub-grafer" class="mat-subtab-content mt-4">
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                        <div class="bg-white p-4 rounded-lg shadow-sm border border-slate-200">
                            <h3 class="font-bold text-lg text-slate-800 mb-1">Mästardominans över Decennierna</h3>
                            <p class="text-xs text-slate-500 mb-4">Titlar fördelade på årtionde för de 10 mest framgångsrika klubbarna.</p>
                            <div class="relative h-80 w-full"><canvas id="chart-dominance"></canvas></div>
                        </div>
                        <div class="bg-white p-4 rounded-lg shadow-sm border border-slate-200 flex flex-col">
                            <div class="flex justify-between items-start mb-4">
                                <div>
                                    <h3 class="font-bold text-lg text-slate-800 mb-1">Matchdramatik i Slutspelet</h3>
                                    <p class="text-xs text-slate-500">Andel utslagsmatcher (Kvart till Final) som gått till förlängning/straffar.</p>
                                </div>
                                <select id="mat-chart-type" onchange="renderMatrixAndGraphs()" class="border border-slate-300 rounded p-1 text-sm bg-slate-50 focus:ring-blue-500">
                                    <option value="pen">Gick till Straffar</option>
                                    <option value="et">Gick till Förlängning</option>
                                </select>
                            </div>
                            <div class="relative flex-grow min-h-[20rem] w-full"><canvas id="chart-penalties"></canvas></div>
                        </div>
                    </div>
                    
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <div class="bg-white p-4 rounded-lg shadow-sm border border-slate-200 flex flex-col">
                            <div class="flex justify-between items-start mb-4">
                                <div>
                                    <h3 class="font-bold text-lg text-slate-800 mb-1">Publiksnitt över Decennierna</h3>
                                    <p class="text-xs text-slate-500">Genomsnittlig publik per match i vald fas.</p>
                                </div>
                                <select id="mat-att-phase-dec" onchange="renderMatrixAndGraphs()" class="border border-slate-300 rounded p-1 text-sm bg-slate-50 focus:ring-blue-500">
                                    <option value="all">Alla Slutspelsmatcher</option>
                                    <option value="kvart">Kvartsfinaler</option>
                                    <option value="semi">Semifinaler</option>
                                    <option value="final">Finaler</option>
                                </select>
                            </div>
                            <div class="relative flex-grow min-h-[20rem] w-full"><canvas id="chart-att-dec"></canvas></div>
                        </div>
                        
                        <div class="bg-white p-4 rounded-lg shadow-sm border border-slate-200 flex flex-col">
                            <div class="flex justify-between items-start mb-4">
                                <div>
                                    <h3 class="font-bold text-lg text-slate-800 mb-1">Publiksnitt per Säsong</h3>
                                    <p class="text-xs text-slate-500">Utveckling år för år för vald fas.</p>
                                </div>
                                <select id="mat-att-phase-sea" onchange="renderMatrixAndGraphs()" class="border border-slate-300 rounded p-1 text-sm bg-slate-50 focus:ring-blue-500">
                                    <option value="all">Alla Slutspelsmatcher</option>
                                    <option value="kvart">Kvartsfinaler</option>
                                    <option value="semi">Semifinaler</option>
                                    <option value="final">Finaler</option>
                                </select>
                            </div>
                            <div class="relative flex-grow min-h-[20rem] w-full"><canvas id="chart-att-sea"></canvas></div>
                        </div>
                    </div>
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
                        <div class="bg-white p-4 rounded-lg shadow-sm border border-slate-200 flex flex-col">
                            <div class="flex justify-between items-start mb-4">
                                <div>
                                    <h3 class="font-bold text-lg text-slate-800 mb-1">Snittålder i Finaler (Decennier)</h3>
                                    <p class="text-xs text-slate-500">Genomsnittlig ålder på finalspelarna.</p>
                                </div>
                                <div class="flex flex-col gap-1">
                                    <select id="mat-age-team-dec" onchange="renderMatrixAndGraphs()" class="border border-slate-300 rounded p-1 text-xs bg-slate-50 focus:ring-blue-500 font-medium">
                                        <option value="all">Båda finallagen</option>
                                        <option value="champ">Endast Mästarna</option>
                                        <option value="runner">Endast Tvåorna</option>
                                    </select>
                                    <select id="mat-age-type-dec" onchange="renderMatrixAndGraphs()" class="border border-slate-300 rounded p-1 text-xs bg-slate-50 focus:ring-blue-500 font-medium">
                                        <option value="start">Endast Startelvan</option>
                                        <option value="played">Alla spelare på planen</option>
                                    </select>
                                </div>
                            </div>
                            <div class="relative flex-grow min-h-[20rem] w-full"><canvas id="chart-age-dec"></canvas></div>
                        </div>
                        
                        <div class="bg-white p-4 rounded-lg shadow-sm border border-slate-200 flex flex-col">
                            <div class="flex justify-between items-start mb-4">
                                <div>
                                    <h3 class="font-bold text-lg text-slate-800 mb-1">Snittålder i Finaler (Säsonger)</h3>
                                    <p class="text-xs text-slate-500">Åldersutveckling år för år i finalerna.</p>
                                </div>
                                <div class="flex flex-col gap-1">
                                    <select id="mat-age-team-sea" onchange="renderMatrixAndGraphs()" class="border border-slate-300 rounded p-1 text-xs bg-slate-50 focus:ring-blue-500 font-medium">
                                        <option value="all">Båda finallagen</option>
                                        <option value="champ">Endast Mästarna</option>
                                        <option value="runner">Endast Tvåorna</option>
                                    </select>
                                    <select id="mat-age-type-sea" onchange="renderMatrixAndGraphs()" class="border border-slate-300 rounded p-1 text-xs bg-slate-50 focus:ring-blue-500 font-medium">
                                        <option value="start">Endast Startelvan</option>
                                        <option value="played">Alla spelare på planen</option>
                                    </select>
                                </div>
                            </div>
                            <div class="relative flex-grow min-h-[20rem] w-full"><canvas id="chart-age-sea"></canvas></div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- FLIK 6: SPELARREGISTER -->
        <section id="tab-players" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <div class="flex flex-col md:flex-row gap-4 mb-4">
                    <input type="text" id="player-search" onkeyup="searchPlayers()" placeholder="Sök på spelarnamn..." class="flex-1 border border-slate-300 rounded p-3 bg-slate-50 focus:ring-blue-500">
                    <input type="text" id="club-search" onkeyup="searchPlayers()" placeholder="Sök på klubb..." class="flex-1 border border-slate-300 rounded p-3 bg-slate-50 focus:ring-blue-500">
                </div>
                <div class="flex flex-wrap gap-6 items-center text-sm">
                    <label class="flex items-center gap-2 cursor-pointer text-slate-700 font-medium"><input type="checkbox" id="check-champ" onchange="searchPlayers()" class="w-4 h-4 text-blue-600"> Visa endast Cupmästare</label>
                    <label class="flex items-center gap-2 cursor-pointer text-slate-700 font-medium"><input type="checkbox" id="check-runner" onchange="searchPlayers()" class="w-4 h-4 text-slate-500"> Visa endast Tvåor</label>
                    <label class="flex items-center gap-2 cursor-pointer text-slate-700 font-medium"><input type="checkbox" id="check-played" onchange="searchPlayers()" class="w-4 h-4 text-emerald-600"> Visa enbart spelare som deltog på planen i final</label>
                </div>
            </div>
            
            <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                <div class="overflow-y-auto custom-scroll" style="max-height: 800px;">
                    <table class="w-full text-left text-sm whitespace-nowrap relative">
                        <thead class="bg-slate-100 text-slate-600 font-medium border-b border-slate-200 sticky top-0 z-10 shadow-sm">
                            <tr><th class="px-4 py-3">Spelarnamn (A-Ö)</th><th class="px-4 py-3">Klubb(ar)</th><th class="px-4 py-3">Meriter i Finaler</th><th class="px-4 py-3 text-center">Speltid (Vald Fas)</th><th class="px-4 py-3 text-right">Åtgärd</th></tr>
                        </thead>
                        <tbody id="player-search-results" class="divide-y divide-slate-100"></tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- FLIK: TAKTIK & ANALYS -->
        <section id="tab-analys" class="tab-content hidden">
            <div class="bg-white p-6 rounded-b-lg rounded-tr-lg shadow-md border border-slate-200">
                <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                    <div>
                        <h2 class="text-2xl font-black text-slate-800">Djupanalys & Taktik</h2>
                        <p class="text-sm text-slate-500 mt-1">Avancerade beräkningar av spelmönster, ålder och dubbla roller, samt finalarenor och matchresultat.</p>
                    </div>
                    <select id="analys-category" onchange="renderAnalys()" class="p-2 border border-slate-300 rounded-md bg-slate-50 font-bold text-slate-700 focus:ring-blue-500 focus:border-blue-500 shadow-sm">
                        <option value="" disabled selected>-- Välj analys --</option>
                        <option value="player_coach">I dubbla roller (Spelare & Tränare)</option>
                        <option value="comeback_kings">Vändningarnas Mästare (Vänt underläge till guld)</option>
                        <option value="age_gap">Åldersgapets Betydelse (Rutin vs Ungdom)</option>
                        <option value="iron_men">Järnmännen (Flest spelade finalminuter & förlängningar)</option>
                        <!-- Här fyller vi på med Vändningar, Åldersgap etc. -->
                        <option disabled>────────── Övrigt & Sammanställningar ──────────</option>
                        <option value="final_arenas">Finalarenor (Var har pokalen lyfts?)</option>
                        <option value="all_results">Matchresultat (Alla cupmatcher genom tiderna)</option>
                    </select>
                    </select>
                </div>
                
                <div class="overflow-x-auto rounded-lg border border-slate-200 shadow-inner">
                    <table class="w-full text-left border-collapse whitespace-nowrap min-w-max">
                        <thead id="analys-head"></thead>
                        <tbody id="analys-body" class="text-sm"></tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- FLIK 7: ADMIN (VARNINGAR) -->
        <section id="tab-admin" class="tab-content">
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <h2 class="text-xl font-bold text-slate-800 mb-2 flex items-center gap-2"><span>⚠️</span> 1. Saknade Målskyttar i Slutspelet</h2>
                <p class="text-sm text-slate-600 mb-4">Visar alla sena matcher (Kvartsfinal och framåt) som inte slutade 0-0, men där systemet inte hittar några inlagda målskyttar.</p>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-rose-50 text-rose-800 font-medium">
                            <tr><th class="px-4 py-2">Säsong</th><th class="px-4 py-2">Fas</th><th class="px-4 py-2">Match</th><th class="px-4 py-2 text-center">Resultat</th></tr>
                        </thead>
                        <tbody id="admin-warnings-body" class="divide-y divide-slate-100"></tbody>
                    </table>
                </div>
            </div>
            
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <h2 class="text-xl font-bold text-slate-800 mb-2 flex items-center gap-2"><span>🚨</span> 2. Ologiska Mål & Innebörd</h2>
                <p class="text-sm text-slate-600 mb-4">Hittar mål med samma innebörd i samma match (t.ex. två "1-0"), matcher som har både 1-0 och 0-1, samt matcher där fler mål registrerats än resultatet anger. Även varningar om för <b>få inlagda mål</b>.</p>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-amber-50 text-amber-800 font-medium">
                            <tr><th class="px-4 py-2">Typ av Fel</th><th class="px-4 py-2">Match & Säsong</th><th class="px-4 py-2">Felsammanfattning</th><th class="px-4 py-2">Match_ID</th></tr>
                        </thead>
                        <tbody id="admin-goals-body" class="divide-y divide-slate-100"></tbody>
                    </table>
                </div>
            </div>

            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <h2 class="text-xl font-bold text-slate-800 mb-2 flex items-center gap-2"><span>🔍</span> 3. Avvikelser mellan Mål-flikarna</h2>
                <p class="text-sm text-slate-600 mb-4">Visar mål som finns inlagda i både "Mästarna" och "Slutomgångar" för samma match, men där namnet, minuten eller klubben skiljer sig åt, vilket kan orsaka att de skrivs ut som dubbletter i matchrutan.</p>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-indigo-50 text-indigo-800 font-medium">
                            <tr><th class="px-4 py-2">Match & Säsong</th><th class="px-4 py-2">Felorsak (Mästarna jämfört med Slutomgångar)</th><th class="px-4 py-2">Match_ID</th></tr>
                        </thead>
                        <tbody id="admin-mismatch-body" class="divide-y divide-slate-100"></tbody>
                    </table>
                </div>
            </div>
            
            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <h2 class="text-xl font-bold text-slate-800 mb-2 flex items-center gap-2"><span>⏳</span> 4. Spelare med Lång Karriär (> 10 år)</h2>
                <p class="text-sm text-slate-600 mb-4">Dessa spelare har mer än 10 år mellan sitt första och sista framträdande i databasen. Kontrollera om det rör sig om två olika personer med samma namn.</p>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-emerald-50 text-emerald-800 font-medium">
                            <tr><th class="px-4 py-2">Spelare</th><th class="px-4 py-2 text-center">Första År</th><th class="px-4 py-2 text-center">Sista År</th><th class="px-4 py-2 text-center">Spann (År)</th></tr>
                        </thead>
                        <tbody id="admin-career-body" class="divide-y divide-slate-100"></tbody>
                    </table>
                </div>
            </div>

            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <h2 class="text-xl font-bold text-slate-800 mb-2 flex items-center gap-2"><span>👻</span> 5. Övergivna Spelare i Registret</h2>
                <p class="text-sm text-slate-600 mb-4">Spelare som finns inlagda i fliken <b>Spelarnamn</b> men som saknar inlagda finaler, mål eller utvisningar i djupdykningsdatabasen.</p>
                <div class="overflow-y-auto custom-scroll max-h-64 border rounded p-4 bg-slate-50 text-sm text-slate-600">
                    <ul id="admin-players-list" class="list-disc pl-4 space-y-1"></ul>
                </div>
            </div>

            <div class="bg-white p-6 rounded-lg shadow-sm border border-slate-200 mb-6">
                <h2 class="text-xl font-bold text-slate-800 mb-2 flex items-center gap-2"><span>🛠️</span> 6. Varningar från Excel-inläsningen (Python)</h2>
                <p class="text-sm text-slate-600 mb-4">Varningar som upptäcktes direkt när Excel-filen byggdes ihop (t.ex. dubbletter i spelarregistret med olika födelseår).</p>
                <div class="overflow-y-auto custom-scroll max-h-64 border rounded p-4 bg-slate-50 text-sm text-slate-600">
                    <ul id="admin-python-warnings" class="list-disc pl-4 space-y-1"></ul>
                </div>
            </div>
        </section>

        <!-- ENDA INSTANSEN AV MODALERNA -->
        <div id="match-modal" class="hidden fixed inset-0 bg-slate-900/60 z-[100] flex items-center justify-center p-4">
            <div class="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden">
                <div class="p-4 border-b bg-slate-100 flex justify-between items-center">
                    <div class="text-xs font-bold text-slate-500 uppercase tracking-widest" id="mm-fas"></div>
                    <button onclick="document.getElementById('match-modal').classList.add('hidden')" class="text-slate-400 hover:text-slate-800 font-bold flex items-center gap-1 transition-colors">
                        <span class="text-sm font-medium uppercase tracking-wider">Stäng</span>
                        <span class="text-2xl leading-none">&times;</span>
                    </button>
                </div>
                <div class="p-6 bg-blue-800 text-white text-center">
                    <div class="text-sm text-blue-200 mb-2" id="mm-date"></div>
                    <div class="text-3xl font-black flex justify-center items-center gap-6">
                        <span class="w-1/3 text-right" id="mm-home"></span>
                        <span class="bg-white text-blue-900 px-4 py-1 rounded shadow" id="mm-res"></span>
                        <span class="w-1/3 text-left" id="mm-away"></span>
                    </div>
                    <div class="text-sm text-blue-300 mt-4 flex justify-center gap-2" id="mm-extra-info">
                    </div>
                </div>
                <div class="overflow-y-auto custom-scroll flex-1 p-6" id="mm-content"></div>
            </div>
        </div>
        
        <div id="player-modal" class="hidden fixed inset-0 bg-slate-900/80 z-[110] flex items-center justify-center p-4">
            <div class="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
                <div class="p-6 border-b bg-slate-900 text-white flex justify-between items-start">
                    <div>
                        <div class="text-xs font-bold text-yellow-500 uppercase tracking-widest mb-1">Spelarprofil</div>
                        <h3 id="pm-name" class="text-3xl font-black"></h3>
                        <div id="pm-clubs" class="text-sm text-slate-400 mt-1"></div>
                    </div>
                    <button onclick="document.getElementById('player-modal').classList.add('hidden')" class="text-slate-400 hover:text-white flex items-center gap-1">
                        <span class="text-sm font-medium uppercase tracking-wider">Stäng</span>
                        <span class="text-2xl leading-none">&times;</span>
                    </button>
                </div>
                <div class="overflow-y-auto custom-scroll flex-1 p-6 bg-slate-50 flex flex-col gap-6" id="pm-content">
                </div>
            </div>
        </div>

    </main>

    <script>
        const DJUP = %%DJUP_DATA_JSON%%;
        const BASE_MATCHES = %%BASE_MATCHES_JSON%%;
        let ALL_SEASONS = [];
        let CURRENT_SEASON = "";
        let CURRENT_SKYTTELIGA_TYP = 'Slutomgångar';
        let SEASON_CHAMPIONS = {}; 
        
        window.cupCharts = {}; 
        let currentMatrixData = [];
        let currentMatrixSort = { col: 'guld', asc: false };

        let DECADES = {};

        // --- Hjälpfunktioner ---
        
        function safeSetHTML(id, html) {
            let el = document.getElementById(id);
            if (el) el.innerHTML = html;
        }

        // Tvingar fram helt html-säkra strängar för dataset i HTML-element.
        function escapeHtml(unsafe) {
            if(!unsafe) return "";
            return String(unsafe)
                 .replace(/&/g, "&amp;")
                 .replace(/</g, "&lt;")
                 .replace(/>/g, "&gt;")
                 .replace(/"/g, "&quot;")
                 .replace(/'/g, "&#039;");
        }

        function formatDate(val, fallbackYear) {
            if (!val) return fallbackYear || '-';
            let s = String(val).trim();
            if (s.length === 4) return s;
            if (typeof val === 'number') {
                return (Math.abs(val) > 0 && Math.abs(val) < 10000) ? String(val) : new Date(val).toISOString().split('T')[0];
            }
            return s.length > 10 ? s.substring(0, 10) : s;
        }
        
        function formatName(nameStr) {
            if (!nameStr) return "";
            let cleanedName = nameStr.replace(/\\b\\d+\\b/g, '').replace(/\\s+/g, ' ').trim();
            
            let splitters = [' & ', ' / ', ' och '];
            let activeSplitter = splitters.find(s => cleanedName.includes(s));
            
            if (activeSplitter) {
                let parts = cleanedName.split(activeSplitter);
                return parts.map(p => {
                    if (p.includes(",")) {
                        let pParts = p.split(",");
                        return (pParts[1].trim() + " " + pParts[0].trim()).trim();
                    }
                    return p.trim();
                }).join(activeSplitter);
            }

            if (cleanedName.includes(",")) {
                let parts = cleanedName.split(",");
                return (parts[1].trim() + " " + parts[0].trim()).trim();
            }
            return cleanedName;
        }
        
        // GLOBAL HJÄLPFUNKTION: Kollar om en spelare var lagkapten i en viss match
    function isPlayerCaptain(pName, pKaptenKolumn, pTeam, matchSeasonStr) {
    if (!pName) return false;
    
    // 1. Snabbkoll: Finns flaggan direkt i matchloggen?
    if (pKaptenKolumn && (String(pKaptenKolumn).toLowerCase() === 'ja' || String(pKaptenKolumn) === '1' || String(pKaptenKolumn).toLowerCase() === 'true')) return true;
    if (String(pName).toLowerCase().includes('(c)')) return true;

    // 2. Djupkoll mot Excel-fliken Lagkapten_Tränare
    if (typeof DJUP === 'undefined' || !DJUP.sasonger || !matchSeasonStr) return false;
    
    let startYear = String(matchSeasonStr).substring(0, 4);
    let champion = (typeof SEASON_CHAMPIONS !== 'undefined') ? SEASON_CHAMPIONS[matchSeasonStr.replace(/\.0$/, '')] : "Okänd";
    
    // NYHET: Söker på NYCKELN istället för en kolumn i datan!
    let sKeyMatch = Object.keys(DJUP.sasonger).find(k => String(k).startsWith(startYear));
    if (!sKeyMatch) return false;
    
    let sRow = DJUP.sasonger[sKeyMatch];

    let capMastRaw = "", capTvaaRaw = "";
    Object.keys(sRow).forEach(k => {
        let kLow = String(k).toLowerCase().trim();
        if (kLow === 'kapten' || kLow.includes('lagkapten_mast') || kLow === 'lagkapten') capMastRaw = String(sRow[k]).trim();
        if (kLow === 'tvaa_kapten' || kLow.includes('lagkapten_tva') || kLow.includes('lagkapten_två')) capTvaaRaw = String(sRow[k]).trim();
    });

    const washName = (str) => str.toLowerCase().replace(/,/g, ' ').split(/\s+/).filter(x=>x).sort().join('');
    
    let pKey = washName(pName);
    let teamSafe = String(pTeam || "").toLowerCase().trim();
    let champSafe = String(champion || "").toLowerCase().trim();

    if (capMastRaw && washName(capMastRaw) === pKey && teamSafe === champSafe) return true;
    if (capTvaaRaw && washName(capTvaaRaw) === pKey && teamSafe !== champSafe) return true;

    return false;
}

        function cleanNumber(val) {
            if (val === null || val === undefined || val === "") return "";
            let s = String(val).trim();
            if (s.toLowerCase() === "nan") return "";
            return s.replace(/\\.0$/, '');
        }
        
        function isSameSeason(s1, s2) {
            if (!s1 || !s2) return false;
            let c1 = String(s1).replace(/\\.0$/, '').trim();
            let c2 = String(s2).replace(/\\.0$/, '').trim();
            if (c1 === c2) return true;
            let n1 = c1.replace(/^(\\d{4})\\/\\d{2}(\\d{2})$/, "$1/$2");
            let n2 = c2.replace(/^(\\d{4})\\/\\d{2}(\\d{2})$/, "$1/$2");
            return n1 === n2;
        }

        function getFullResult(m) {
            let hm = parseInt(cleanNumber(m.hm));
            let bm = parseInt(cleanNumber(m.bm));
            if (isNaN(hm)) return "-";
            
            let res = `${hm} - ${bm}`;
            let fhStr = cleanNumber(m.fh); let fbStr = cleanNumber(m.fb);
            if (fhStr !== "" && fbStr !== "") {
                res = `${hm + parseInt(fhStr)} - ${bm + parseInt(fbStr)} e.f.`;
            }
            let shStr = cleanNumber(m.sh); let sbStr = cleanNumber(m.sb);
            if (shStr !== "" && sbStr !== "") {
                res += ` (${shStr}-${sbStr} str)`;
            }
            return res;
        }

        function groupMatchesByPair(mids) {
            let groups = [];
            mids.forEach(mid => {
                let m = BASE_MATCHES[mid];
                let pairKey = [m.hemma, m.borta].sort().join("|");
                let existing = groups.find(g => g.key === pairKey);
                if(existing) existing.mids.push(mid);
                else groups.push({key: pairKey, mids: [mid]});
            });
            return groups;
        }
        
        function precalculateChampions() {
            let seasonMatches = {};
            Object.keys(BASE_MATCHES).forEach(mid => {
                let m = BASE_MATCHES[mid];
                let s = m.sasong.replace(/\\.0$/, '');
                if (!seasonMatches[s]) seasonMatches[s] = [];
                seasonMatches[s].push(mid);
                
                let adv = parseInt(m.avancerade);
                if (adv === 5) {
                    SEASON_CHAMPIONS[s] = m.hemma;
                } else if (adv === 6) {
                    SEASON_CHAMPIONS[s] = m.borta;
                }
            });
            
            Object.keys(seasonMatches).forEach(s => {
                if (!SEASON_CHAMPIONS[s]) {
                    let mids = seasonMatches[s];
                    mids.sort((a,b) => new Date(BASE_MATCHES[a].datum).getTime() - new Date(BASE_MATCHES[b].datum).getTime());
                    let fin = mids.filter(mid => {
                        let m = BASE_MATCHES[mid];
                        let f = m.fas.toLowerCase();
                        let adv = parseInt(m.avancerade);
                        return f.includes('final') && !f.includes('åtton') && !f.includes('kvart') && !f.includes('semi') && adv !== 8;
                    });
                    if (fin.length > 0) {
                        let lastFin = BASE_MATCHES[fin[fin.length-1]];
                        let adv = parseInt(lastFin.avancerade);
                        if (adv === 1) SEASON_CHAMPIONS[s] = lastFin.hemma;
                        else if (adv === 2) SEASON_CHAMPIONS[s] = lastFin.borta;
                        else SEASON_CHAMPIONS[s] = lastFin.winner;
                    }
                }
            });
        }

        function getPlayerTeam(pLag, bm) {
            let season = bm.sasong.replace(/\\.0$/, '');
            let champion = SEASON_CHAMPIONS[season];
            
            if (champion && (bm.hemma === champion || bm.borta === champion)) {
                return (pLag == 1 || pLag == "1") ? champion : ((bm.hemma === champion) ? bm.borta : bm.hemma);
            }
            return (pLag == 1 || pLag == "1") ? bm.hemma : bm.borta;
        }

        function getPlayerTeamInSeason(playerName, seasonStr) {
            let sMatches = Object.keys(DJUP.matcher).filter(mid => BASE_MATCHES[mid] && BASE_MATCHES[mid].sasong.replace(/\\.0$/, '') === seasonStr);
            for (let mid of sMatches) {
                let pLineup = DJUP.matcher[mid].uppstallning.find(p => p.namn === playerName);
                if (pLineup) {
                    return getPlayerTeam(pLineup.lag, BASE_MATCHES[mid]);
                }
            }
            return null;
        }

        function getPlayerAgeAtMatch(playerName, matchDateStr) {
            let pInfo = DJUP.spelare[playerName];
            if (!pInfo || !matchDateStr) return null;
            let mDate = new Date(matchDateStr);
            if (isNaN(mDate.getTime())) return null;
            
            if (pInfo.fodd && pInfo.fodd.length >= 4) {
                let bDate = new Date(pInfo.fodd);
                if (!isNaN(bDate.getTime())) {
                    let diffTime = mDate.getTime() - bDate.getTime();
                    if (diffTime < 0) return null;
                    
                    let years = mDate.getFullYear() - bDate.getFullYear();
                    let months = mDate.getMonth() - bDate.getMonth();
                    let days = mDate.getDate() - bDate.getDate();

                    if (days < 0) {
                        months--;
                        let prevMonth = new Date(mDate.getFullYear(), mDate.getMonth(), 0);
                        days += prevMonth.getDate();
                    }
                    if (months < 0) {
                        years--;
                        months += 12;
                    }
                    
                    let totalDays = diffTime / (1000 * 3600 * 24);
                    return { totalDays, text: `${years} år, ${months} mån, ${days} dgr`, exact: true, years: years };
                }
            }
            if (pInfo.ar) {
                let bYear = parseInt(pInfo.ar);
                let mYear = mDate.getFullYear();
                if (!isNaN(bYear)) {
                    let years = mYear - bYear;
                    if (years < 0) return null;
                    return { totalDays: years * 365.25, text: `ca ${years} år`, exact: false, years: years };
                }
            }
            return null;
        }

        document.addEventListener('DOMContentLoaded', () => {
            try {
                let sSet = new Set();
                Object.values(BASE_MATCHES).forEach(m => sSet.add(m.sasong));
                
                ALL_SEASONS = Array.from(sSet).sort((a, b) => {
                    let yearA = parseInt(String(a).substring(0, 4)) || 0;
                    let yearB = parseInt(String(b).substring(0, 4)) || 0;
                    return yearA - yearB;
                });
                
                ALL_SEASONS.forEach(s => {
                    let yearStr = s.replace(/[^0-9]/g, '').substring(0, 4);
                    if(yearStr.length === 4) {
                        let dec = yearStr.substring(0, 3) + "0-talet";
                        if(!DECADES[dec]) DECADES[dec] = [];
                        DECADES[dec].push(s);
                    }
                });
                
                let opts = '<option value="">-- Välj en säsong --</option>';
                [...ALL_SEASONS].reverse().forEach(s => { opts += `<option value="${s}">${s}</option>`; });
                if (document.getElementById('season-select')) {
                    document.getElementById('season-select').innerHTML = opts;
                }

                if (ALL_SEASONS.length > 0 && document.getElementById('season-select')) {
                    document.getElementById('season-select').value = [...ALL_SEASONS].reverse()[0];
                }

                precalculateChampions(); 
                buildPlayerStats();
                runAdminCheck();
                renderSkytteliga('Slutomgångar');
                renderSeasonData(); 
                renderToplist();
                renderMatrixAndGraphs();
            } catch (e) {
                console.error("Fel vid initialisering:", e);
                alert("Ett fel inträffade när sidan laddades. Vissa funktioner kanske inte fungerar. Felmeddelande: " + e.message);
            }
        });

        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            document.getElementById('btn-' + tabId).classList.add('active');
            
            if(tabId === 'skyttar' || tabId === 'players' || tabId === 'admin' || tabId === 'topplistor' || tabId === 'matrix') {
                document.getElementById('global-season-selector').classList.add('hidden');
            } else {
                document.getElementById('global-season-selector').classList.remove('hidden');
            }
        }
        
        function switchMatrixTab(subTabId) {
            document.querySelectorAll('.mat-subtab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.mat-subtab-btn').forEach(el => {
                el.classList.remove('active', 'text-blue-600', 'border-blue-600');
                el.classList.add('text-slate-500');
                el.classList.remove('font-bold');
                el.classList.add('font-medium');
            });
            
            document.getElementById('mat-sub-' + subTabId).classList.add('active');
            let activeBtn = document.getElementById('btn-mat-' + subTabId);
            activeBtn.classList.remove('text-slate-500', 'font-medium');
            activeBtn.classList.add('active', 'text-blue-600', 'border-blue-600', 'font-bold');
        }
        
        function changeSeason(dir) {
            let sel = document.getElementById('season-select');
            if(!sel) return;
            let newIdx = sel.selectedIndex + dir;
            if (newIdx > 0 && newIdx < sel.options.length) {
                sel.selectedIndex = newIdx;
                renderSeasonData();
            }
        }

        // --- SÄSONG / MÄSTARENS VÄG ---
        function renderSeasonData() {
            let sel = document.getElementById('season-select');
            if(!sel) return;
            CURRENT_SEASON = sel.value;
            
            if(!CURRENT_SEASON) {
                document.getElementById('slutspel-content').classList.add('hidden');
                document.getElementById('slutspel-placeholder').classList.remove('hidden');
                document.getElementById('vag-content').classList.add('hidden');
                document.getElementById('vag-placeholder').classList.remove('hidden');
                document.getElementById('season-header-info').classList.add('hidden');
                return;
            }
            
            let sKey = Object.keys(DJUP.sasonger).find(k => isSameSeason(k, CURRENT_SEASON));
            
            if(!sKey) {
                // Snygg fallback för pågående säsonger (eller när djupdata ännu inte fyllts i)
                document.getElementById('h-kapten').innerText = "Avgörs i vår";
                document.getElementById('h-kapten').classList.remove('text-rose-600');
                document.getElementById('h-kapten').classList.add('text-slate-500');
                
                document.getElementById('h-tranare1').innerText = "Avgörs i vår";
                document.getElementById('h-tranare1').classList.remove('text-rose-600');
                document.getElementById('h-tranare1').classList.add('text-slate-500');
                
                document.getElementById('h-pokal').innerText = "Avgörs i vår";
                document.getElementById('h-pokal').classList.remove('text-rose-600');
                document.getElementById('h-pokal').classList.add('text-slate-500');
            } else {
                const sInfo = DJUP.sasonger[sKey];
                document.getElementById('h-kapten').innerText = sInfo.kapten ? formatName(sInfo.kapten) : "Okänd";
                document.getElementById('h-kapten').classList.remove('text-rose-600', 'text-slate-500');
                document.getElementById('h-tranare1').innerText = sInfo.tranare_vinnare ? formatName(sInfo.tranare_vinnare) : "Okänd";
                document.getElementById('h-tranare1').classList.remove('text-rose-600', 'text-slate-500');
                document.getElementById('h-pokal').innerText = sInfo.pokal || "-";
                document.getElementById('h-pokal').classList.remove('text-rose-600', 'text-slate-500');
            }
            document.getElementById('season-header-info').classList.remove('hidden');
            
            document.getElementById('slutspel-placeholder').classList.add('hidden');
            document.getElementById('slutspel-content').classList.remove('hidden');
            document.getElementById('vag-placeholder').classList.add('hidden');
            document.getElementById('vag-content').classList.remove('hidden');

            let sMatches = Object.keys(BASE_MATCHES).filter(mid => BASE_MATCHES[mid].sasong.replace(/\\.0$/, '') === CURRENT_SEASON.replace(/\\.0$/, ''));
            sMatches.sort((a,b) => new Date(BASE_MATCHES[a].datum).getTime() - new Date(BASE_MATCHES[b].datum).getTime());

            let qf = [], sf = [], fin = [];
            sMatches.forEach(mid => {
                let f = BASE_MATCHES[mid].fas.toLowerCase();
                if(f.includes('kvart')) qf.push(mid);
                else if(f.includes('semi')) sf.push(mid);
                else if(f.includes('final') && !f.includes('åtton') && !f.includes('kvart') && !f.includes('semi')) fin.push(mid);
            });

            let qfGroups = groupMatchesByPair(qf);
            let sfGroups = groupMatchesByPair(sf);
            let finGroups = groupMatchesByPair(fin);

            if (finGroups.length > 0) {
                let fMatch = BASE_MATCHES[finGroups[0].mids[0]];
                let fTeams = [fMatch.hemma, fMatch.borta];
                sfGroups.sort((a,b) => {
                    let aM = BASE_MATCHES[a.mids[0]];
                    let bM = BASE_MATCHES[b.mids[0]];
                    let aI = fTeams.indexOf(aM.hemma) !== -1 ? fTeams.indexOf(aM.hemma) : (fTeams.indexOf(aM.borta) !== -1 ? fTeams.indexOf(aM.borta) : 99);
                    let bI = fTeams.indexOf(bM.hemma) !== -1 ? fTeams.indexOf(bM.hemma) : (fTeams.indexOf(bM.borta) !== -1 ? fTeams.indexOf(bM.borta) : 99);
                    return aI - bI;
                });
            }

            if (sfGroups.length > 0) {
                let sTeams = [];
                sfGroups.forEach(g => {
                    let m = BASE_MATCHES[g.mids[0]];
                    sTeams.push(m.hemma, m.borta);
                });
                qfGroups.sort((a,b) => {
                    let aM = BASE_MATCHES[a.mids[0]];
                    let bM = BASE_MATCHES[b.mids[0]];
                    let aI = sTeams.indexOf(aM.hemma) !== -1 ? sTeams.indexOf(aM.hemma) : (sTeams.indexOf(aM.borta) !== -1 ? sTeams.indexOf(aM.borta) : 99);
                    let bI = sTeams.indexOf(bM.hemma) !== -1 ? sTeams.indexOf(bM.hemma) : (sTeams.indexOf(bM.borta) !== -1 ? sTeams.indexOf(bM.borta) : 99);
                    return aI - bI;
                });
            }

            let treeHtml = '';
            
            if(qfGroups.length > 0) treeHtml += `
                <div class="flex-1 min-w-[250px] flex flex-col">
                    <h4 class="text-center font-bold text-slate-400 mb-4 uppercase text-xs tracking-widest">Kvartsfinaler</h4>
                    <div class="flex flex-col flex-1 justify-around gap-4">
                        ${qfGroups.map(g => g.mids.length===1 ? buildSmallMatch(g.mids[0]) : `<div class="flex flex-row gap-2 p-2 bg-slate-100 rounded-md border border-slate-200 shadow-inner overflow-x-auto custom-scroll w-full">` + g.mids.map(mid=>buildSmallMatch(mid, false, true)).join('') + `</div>`).join('')}
                    </div>
                </div>`;
            
            if(sfGroups.length > 0) treeHtml += `
                <div class="flex-1 min-w-[250px] flex flex-col">
                    <h4 class="text-center font-bold text-slate-400 mb-4 uppercase text-xs tracking-widest">Semifinaler</h4>
                    <div class="flex flex-col flex-1 justify-around gap-8">
                        ${sfGroups.map(g => g.mids.length===1 ? buildSmallMatch(g.mids[0]) : `<div class="flex flex-row gap-2 p-2 bg-slate-100 rounded-md border border-slate-200 shadow-inner overflow-x-auto custom-scroll w-full">` + g.mids.map(mid=>buildSmallMatch(mid, false, true)).join('') + `</div>`).join('')}
                    </div>
                </div>`;
            
            if(finGroups.length > 0) treeHtml += `
                <div class="flex-1 min-w-[280px] flex flex-col">
                    <h4 class="text-center font-bold text-yellow-500 mb-4 uppercase text-xs tracking-widest">Finaler</h4>
                    <div class="flex flex-col flex-1 justify-center gap-4">
                        ${finGroups.map(g => g.mids.length===1 ? buildSmallMatch(g.mids[0], true) : `<div class="flex flex-row gap-2 p-2 bg-yellow-50 rounded-md border border-yellow-200 shadow-inner overflow-x-auto custom-scroll w-full">` + g.mids.map(mid=>buildSmallMatch(mid, true, true)).join('') + `</div>`).join('')}
                    </div>
                </div>`;
            
            if(!treeHtml) treeHtml = '<div class="text-slate-500 italic p-6">Slutspelsmatcher saknas för denna säsong.</div>';
            document.getElementById('tree-container').innerHTML = treeHtml;

            let champion = SEASON_CHAMPIONS[CURRENT_SEASON.replace(/\\.0$/, '')];
            if(!champion && fin.length > 0) {
                champion = BASE_MATCHES[fin[fin.length-1]].winner;
            }
            
            if(champion) {
                let champMatches = sMatches.filter(mid => BASE_MATCHES[mid].hemma === champion || BASE_MATCHES[mid].borta === champion);
                document.getElementById('vag-list').innerHTML = champMatches.map(m => buildSmallMatch(m)).join('');
            } else {
                document.getElementById('vag-list').innerHTML = '<div class="text-slate-500 italic">Kunde inte identifiera en mästare att visa vägen för.</div>';
            }
        }

        function buildSmallMatch(mid, isFinal=false, isGrouped=false) {
            let m = BASE_MATCHES[mid];
            let fLow = m.fas.toLowerCase();
            
            let phaseColor = "border-slate-200";
            let bgLight = "bg-white";
            
            if (fLow.includes("final") && !fLow.includes("kvart") && !fLow.includes("semi") && !fLow.includes("åtton") && !fLow.includes("1/8")) {
                phaseColor = "border-yellow-400"; bgLight = "bg-yellow-50/30";
            }
            else if (fLow.includes("semi")) {
                phaseColor = "border-purple-400"; bgLight = "bg-purple-50/30";
            }
            else if (fLow.includes("kvart")) {
                phaseColor = "border-rose-400"; bgLight = "bg-rose-50/30";
            }
            else if (fLow.includes("grupp")) {
                phaseColor = "border-emerald-400"; bgLight = "bg-emerald-50/30";
            }
            
            let border = isFinal && !isGrouped ? "border-yellow-400 border-l-4" : (isGrouped ? "border-slate-200 border-l-4" : `${phaseColor} border-l-4`);
            let bg = isFinal && !isGrouped ? "bg-yellow-50" : (isGrouped ? "bg-white" : bgLight);
            let extraClass = isGrouped ? "min-w-[180px]" : "";
            
            let res = getFullResult(m);
            return `
            <div onclick="openMatchModal('${mid}')" class="match-box ${bg} p-2 rounded shadow-sm border border-r-slate-200 border-t-slate-200 border-b-slate-200 ${border} ${extraClass}">
                <div class="text-[10px] text-slate-400 mb-1 flex justify-between"><span>${m.datum}</span><span class="truncate ml-2">${m.fas}</span></div>
                <div class="font-bold text-sm text-slate-700 truncate">${m.hemma}</div>
                <div class="font-bold text-sm text-slate-700 truncate mb-1">${m.borta}</div>
                <div class="font-mono text-xs text-blue-700 font-bold bg-blue-50/50 px-1 py-0.5 rounded border border-blue-100 inline-block">${res}</div>
            </div>`;
        }

        function openMatchModal(mid) {
            let m = BASE_MATCHES[mid];
            let dm = DJUP.matcher[mid] || {uppstallning:[], mal:[], utvisningar:[]};
            let isFinal = m.fas.toLowerCase().includes('final') && !m.fas.toLowerCase().includes('kvart') && !m.fas.toLowerCase().includes('semi') && !m.fas.toLowerCase().includes('åtton') && !m.fas.toLowerCase().includes('1/8');

            document.getElementById('mm-fas').innerText = `${m.sasong} | ${m.fas}`;
            document.getElementById('mm-date').innerText = m.datum;
            document.getElementById('mm-home').innerText = m.hemma;
            document.getElementById('mm-res').innerText = getFullResult(m);
            document.getElementById('mm-away').innerText = m.borta;
            
            let arenaName = m.arena;
            if (m.ort && m.arena && m.arena !== m.ort) {
                arenaName = `${m.arena} (${m.ort})`;
            } else if (m.ort) {
                arenaName = m.ort;
            } else if (m.arena) {
                arenaName = m.arena;
            }
            
            let arenaStr = arenaName ? `Spelplats: ${arenaName}` : "";
            let pubStr = m.publik ? `Publik: ${m.publik}` : "";
            let domStr = m.domare ? `Domare: ${formatName(m.domare)}` : "";
            
            let infoArr = [arenaStr, pubStr, domStr].filter(Boolean);
            document.getElementById('mm-extra-info').innerHTML = infoArr.join(' <span class="text-blue-500 font-bold px-2">|</span> ');

            let allEvents = [];
            let getGoalSum = (inn) => {
                if(!inn) return 999;
                let match = String(inn).match(/(\d+)\s*-\s*(\d+)/);
                return match ? parseInt(match[1]) + parseInt(match[2]) : 999;
            };

            let eventCounter = 0;
            dm.mal.forEach(g => { 
                allEvents.push({
                    type: 'goal', 
                    data: g, 
                    min: parseInt(cleanNumber(g.minut)) || 999,
                    goalSum: getGoalSum(g.innebord),
                    origIdx: eventCounter++
                }); 
            });
            
            dm.utvisningar.forEach(u => { 
                allEvents.push({
                    type: 'red', 
                    data: u, 
                    min: parseInt(cleanNumber(u.minut)) || 999,
                    goalSum: 999,
                    origIdx: eventCounter++
                }); 
            });

            allEvents.forEach(e => e.sortMin = e.min);
            let goalsWithSum = allEvents.filter(e => e.type === 'goal' && e.goalSum !== 999);
            goalsWithSum.sort((a, b) => a.goalSum - b.goalSum);
            
            let lastKnownMin = 1;
            for (let i = 0; i < goalsWithSum.length; i++) {
                let g = goalsWithSum[i];
                if (g.min !== 999) {
                    lastKnownMin = g.min;
                } else {
                    let nextKnownMin = 120;
                    for (let j = i + 1; j < goalsWithSum.length; j++) {
                        if (goalsWithSum[j].min !== 999) {
                            nextKnownMin = goalsWithSum[j].min;
                            break;
                        }
                    }
                    let estimatedMin = Math.min(lastKnownMin + 1, nextKnownMin > lastKnownMin ? nextKnownMin - 1 : nextKnownMin);
                    g.sortMin = estimatedMin;
                    lastKnownMin = estimatedMin;
                }
            }

            allEvents.sort((a, b) => {
                if (a.sortMin !== b.sortMin) return a.sortMin - b.sortMin;
                if (a.goalSum !== 999 && b.goalSum !== 999 && a.goalSum !== b.goalSum) return a.goalSum - b.goalSum;
                return a.origIdx - b.origIdx;
            });

            let regularEvents = [];
            let shootoutEvents = [];
            
            allEvents.forEach(e => {
                if (e.type === 'goal') {
                    let infoLower = e.data.info ? e.data.info.toLowerCase() : "";
                    let innebordLower = e.data.innebord ? e.data.innebord.toLowerCase() : "";
                    
                    if (infoLower.includes('straffläggning') || innebordLower.includes('straffläggning')) {
                        shootoutEvents.push(e);
                    } else {
                        regularEvents.push(e);
                    }
                } else {
                    regularEvents.push(e);
                }
            });

            let contentHtml = '';
            
            if(regularEvents.length > 0 || shootoutEvents.length > 0) {
                contentHtml += `<div class="mb-6"><h4 class="font-bold text-slate-600 mb-3 border-b pb-1">Händelser</h4><ul class="space-y-2">`;
                
                regularEvents.forEach(e => {
                    if(e.type === 'goal') {
                        let g = e.data;
                        let gMin = g.minut ? cleanNumber(g.minut)+"'" : "";
                        
                        let isOwnGoal = g.skytt.toLowerCase().includes('självmål');
                        let skyttStr = formatName(g.skytt);
                        
                        let isPen = false;
                        if (g.info && g.info.toLowerCase() === 'straff') isPen = true;
                        if (g.innebord && g.innebord.toLowerCase() === 'straff') isPen = true;
                        
                        let extraInfo = isPen ? ` <span class="text-slate-400 text-xs italic ml-1">straff</span>` : ``;

                        if (isOwnGoal) {
                            if (g.info && g.info.trim() !== '' && !isPen) {
                                skyttStr = `Självmål av ${formatName(g.info)}`;
                            } else {
                                skyttStr = `Självmål`;
                            }
                        }
                        
                        let innebordBadge = '';
                        if (g.innebord && g.innebord.trim() !== '' && g.innebord.match(/\d+\s*-\s*\d+/)) {
                            innebordBadge = `<span class="bg-slate-200 px-1 rounded text-xs">${g.innebord}</span>`;
                        }
                        
                        let gwgBadge = g.avgorande === 'GWG' ? `<span class="bg-yellow-100 text-yellow-700 text-[10px] px-1 rounded font-bold ml-1">GWG</span>` : '';
                        
                        contentHtml += `<li class="flex items-center gap-2 text-sm"><span class="text-emerald-500">⚽</span> <strong>${skyttStr}</strong> <span class="text-slate-500 w-16">${gMin}${extraInfo}</span> ${innebordBadge} ${gwgBadge}</li>`;
                    } else {
                        let u = e.data;
                        let uMin = u.minut ? cleanNumber(u.minut)+"'" : "";
                        contentHtml += `<li class="flex items-center gap-2 text-sm"><span class="text-rose-500">🟥</span> <strong>${formatName(u.namn)}</strong> <span class="text-slate-500 w-16">${uMin}</span></li>`;
                    }
                });
                
                if (shootoutEvents.length > 0) {
                    contentHtml += `<div class="w-full text-center text-[11px] font-bold text-slate-400 mt-4 mb-2 border-t border-slate-200 pt-2 tracking-widest">STRAFFLÄGGNING</div>`;
                    shootoutEvents.forEach(e => {
                        let g = e.data;
                        let inn = g.innebord || '';
                        let innBadge = (inn && !inn.toLowerCase().includes('straffläggning')) ? inn : 'Str';
                        
                        contentHtml += `<li class="flex items-center gap-2 text-sm"><span class="text-emerald-500">⚽</span> <strong>${formatName(g.skytt)}</strong> <span class="bg-slate-100 text-slate-500 px-1 rounded text-xs ml-auto">${innBadge}</span> ${g.avgorande==='GWG'?`<span class="bg-yellow-100 text-yellow-700 text-[10px] px-1 rounded font-bold">GWG</span>`:''}</li>`;
                    });
                }
                
                contentHtml += `</ul></div>`;
            } else {
                 contentHtml += `<div class="mb-6 text-sm text-slate-400 italic">Inga specifika matchhändelser (mål/utvisningar) inlagda för denna match.</div>`;
            }

            if(isFinal && dm.uppstallning.length > 0) {
                let t1='', t2='';
                
                let t1Players = dm.uppstallning.filter(p => p.lag == 1 || p.lag == "1");
                let t2Players = dm.uppstallning.filter(p => p.lag == 2 || p.lag == "2");
                
                t1Players.sort((a,b) => (parseInt(a.pos)||99) - (parseInt(b.pos)||99));
                t2Players.sort((a,b) => (parseInt(a.pos)||99) - (parseInt(b.pos)||99));
                
                let season = m.sasong.replace(/\\.0$/, '');
                let champion = SEASON_CHAMPIONS[season];
                let t1Name = m.hemma;
                let t2Name = m.borta;
                
                if (champion && (m.hemma === champion || m.borta === champion)) {
                    t1Name = champion;
                    t2Name = (m.hemma === champion) ? m.borta : m.hemma;
                }

                let t1Crown = (t1Name === champion) ? " <span title='Cupmästare' class='text-yellow-500'>👑</span>" : "";
                let t2Crown = (t2Name === champion) ? " <span title='Cupmästare' class='text-yellow-500'>👑</span>" : "";

                let t1Coach = "", t2Coach = "";
                let sKey = Object.keys(DJUP.sasonger).find(k => isSameSeason(k, season));
                let seasonData = sKey ? DJUP.sasonger[sKey] : null;
                
                if (seasonData) {
                    if (t1Name === champion) t1Coach = formatName(seasonData.tranare_vinnare);
                    else if (seasonData.tranare_tvaa) t1Coach = formatName(seasonData.tranare_tvaa);
                    
                    if (t2Name === champion) t2Coach = formatName(seasonData.tranare_vinnare);
                    else if (seasonData.tranare_tvaa) t2Coach = formatName(seasonData.tranare_tvaa);
                }

                const processPlayer = (p, index, isTeam1) => {
                    let icons = "";
                    
                    if (p.byte) {
                        let bText = String(p.byte).toLowerCase();
                        let hasIn = /\bin\b/.test(bText) || bText === 'in';
                        let hasUt = /\but\b/.test(bText) || bText === 'ut';
                        let hasUtv = /\butv\b/.test(bText) || bText.includes('utv');
                        
                        if (hasIn) {
                            icons += `<span style="color: #10b981; font-size: 11px; margin-left: 4px;" title="Inbytt">▲</span>`;
                        }
                        if (hasUt) {
                            icons += `<span style="color: #f43f5e; font-size: 11px; margin-left: 4px;" title="Utbytt">▼</span>`;
                        }
                        if (hasUtv) {
                            icons += `<span style="font-size: 11px; margin-left: 4px;" title="Utvisad">🟥</span>`;
                        }
                        
                        if (!hasIn && !hasUt && !hasUtv && bText.trim() !== '') {
                            icons += `<span class="text-slate-400 text-xs ml-1" title="Byte">🔄</span>`;
                        }
                    }
                    
                    let hasRedCardEvent = dm.utvisningar.some(u => u.namn === p.namn);
                    if (hasRedCardEvent && !icons.includes("🟥")) {
                        icons += `<span style="font-size: 11px; margin-left: 4px;" title="Utvisad">🟥</span>`;
                    }
                    
                    let pMin = p.minuter ? cleanNumber(p.minuter)+"'" : "";
                    let pName = formatName(p.namn);
                    
                    // --- NYHET: Kaptens-detektorn ---
                    // Hämtar spelarens lag för att jämföra med mästarlaget/silverlaget
                    let pTeam = getPlayerTeam(p.lag, m); 
                    // Anropar vår globala hjälpfunktion vi skapade tidigare
                    let capBadge = isPlayerCaptain(p.namn, p.kapten, pTeam, m.sasong) ? ' <span class="font-bold text-amber-500" title="Lagkapten">(c)</span>' : '';
                    // ---------------------------------
                    
                    // Lade in ${capBadge} direkt efter ${pName}
                    let rowHtml = `<div class="flex justify-between py-1.5 border-b border-slate-100 text-sm"><span>${p.pos}. ${pName}${capBadge} ${icons}</span><span class="text-slate-400 text-xs">${pMin}</span></div>`;
                    
                    if (index === 11) {
                        let header = `<div class="w-full border-t border-dashed border-slate-300 my-1 pt-2 text-[10px] text-slate-400 font-bold tracking-widest text-center">AVBYTARE</div>`;
                        if (isTeam1) t1 += header; else t2 += header;
                    }
                    
                    if (isTeam1) t1 += rowHtml; else t2 += rowHtml;
                };
                
                t1Players.forEach((p, i) => processPlayer(p, i, true));
                t2Players.forEach((p, i) => processPlayer(p, i, false));
                
                if (t1Coach && t1Coach !== "Okänd") {
                    t1 += `<div class="w-full border-t border-solid border-slate-300 mt-2 pt-2 text-[10px] text-slate-400 font-bold tracking-widest text-center uppercase">Tränare</div>`;
                    t1 += `<div class="text-center font-bold text-slate-700 text-sm mt-1">${t1Coach}</div>`;
                }
                if (t2Coach && t2Coach !== "Okänd") {
                    t2 += `<div class="w-full border-t border-solid border-slate-300 mt-2 pt-2 text-[10px] text-slate-400 font-bold tracking-widest text-center uppercase">Tränare</div>`;
                    t2 += `<div class="text-center font-bold text-slate-700 text-sm mt-1">${t2Coach}</div>`;
                }
                
                contentHtml += `<div class="grid grid-cols-2 gap-6"><div class="bg-slate-50 p-4 rounded"><h5 class="font-bold mb-3 text-slate-800">${t1Name}${t1Crown}</h5>${t1}</div><div class="bg-slate-50 p-4 rounded"><h5 class="font-bold mb-3 text-slate-800">${t2Name}${t2Crown}</h5>${t2}</div></div>`;
            }

            document.getElementById('mm-content').innerHTML = contentHtml;
            document.getElementById('match-modal').classList.remove('hidden');
        }

        // --- SKYTTELIGOR ---
        function renderSkytteliga(typ) {
            CURRENT_SKYTTELIGA_TYP = typ;
            
            document.getElementById('btn-sk-slut').className = typ === 'Slutomgångar' ? "px-4 py-2 bg-blue-600 text-white rounded font-medium shadow-sm transition-colors" : "px-4 py-2 bg-slate-200 text-slate-700 rounded font-medium shadow-sm hover:bg-slate-300 transition-colors";
            document.getElementById('btn-sk-mast').className = typ === 'Mästarna' ? "px-4 py-2 bg-blue-600 text-white rounded font-medium shadow-sm transition-colors" : "px-4 py-2 bg-slate-200 text-slate-700 rounded font-medium shadow-sm hover:bg-slate-300 transition-colors";
            document.getElementById('btn-sk-season').className = "px-4 py-2 bg-slate-200 text-slate-700 rounded font-medium shadow-sm hover:bg-slate-300 transition-colors";
            
            document.getElementById('sk-filters-container').classList.remove('opacity-50', 'pointer-events-none');
            
            let mastOnlyOpts = document.querySelectorAll('.mast-only');
            let qFasEl = document.getElementById('sk-filter-fas');
            if (typ === 'Slutomgångar') {
                mastOnlyOpts.forEach(opt => { opt.disabled = true; opt.classList.add('text-slate-300'); });
                if (qFasEl.value === 'grupp' || qFasEl.value === 'tidiga') {
                    qFasEl.value = ''; 
                }
            } else {
                mastOnlyOpts.forEach(opt => { opt.disabled = false; opt.classList.remove('text-slate-300'); });
            }

            document.getElementById('skytteliga-head').innerHTML = `<tr><th class="px-4 py-3">Spelare</th><th class="px-4 py-3 text-center">Antal Mål</th><th class="px-4 py-3">Klubb (Vid målet)</th><th class="px-4 py-3">Säsonger</th></tr>`;

            let qClub = document.getElementById('sk-filter-club').value.toLowerCase();
            let qFas = document.getElementById('sk-filter-fas').value.toLowerCase();
            let onlyGwg = document.getElementById('sk-filter-gwg').checked;
            let noOwnGoals = document.getElementById('sk-filter-no-owngoals').checked;
            let penMode = document.querySelector('input[name="sk-filter-pen"]:checked').value;

            let extraTitle = [];
            if(onlyGwg) extraTitle.push("Endast avgörande");
            if(noOwnGoals) extraTitle.push("Exkl. Självmål");
            if(penMode === 'include') extraTitle.push("Inkl. Straffar");
            else if(penMode === 'only') extraTitle.push("Enbart Straffar");
            else extraTitle.push("Exkl. Straffar");

            if(qClub) extraTitle.push(`Klubb: ${qClub}`);
            if(qFas) {
                if (qFas === 'final') extraTitle.push(`Fas: Finaler`);
                else if (qFas === 'semi') extraTitle.push(`Fas: Semifinaler`);
                else if (qFas === 'kvart') extraTitle.push(`Fas: Kvartsfinaler`);
                else if (qFas === 'grupp') extraTitle.push(`Fas: Gruppspel`);
                else if (qFas === 'tidiga') extraTitle.push(`Fas: Tidiga omgångar`);
            }

            document.getElementById('skytteliga-title').innerText = `Skytteliga: ${typ} (${extraTitle.join(', ')})`;

            let agg = {};
            Object.keys(DJUP.matcher).forEach(mid => {
                let dm = DJUP.matcher[mid];
                let bm = BASE_MATCHES[mid];
                if(!bm) return;
                
                dm.mal.forEach(g => {
                    let season = bm.sasong.replace(/\\.0$/, '');
                    let champion = SEASON_CHAMPIONS[season] || bm.winner;
                    
                    let playerTeam = g.lag;
                    if (!playerTeam) {
                        let pLineup = dm.uppstallning.find(p => p.namn === g.skytt);
                        if (pLineup) {
                            playerTeam = getPlayerTeam(pLineup.lag, bm);
                        } else {
                            playerTeam = getPlayerTeamInSeason(g.skytt, season);
                        }
                    }
                    
                    if (!playerTeam && typ === 'Mästarna') {
                        playerTeam = champion;
                    }

                    let isMastarMal = false;
                    if (typ === 'Mästarna') {
                        if (playerTeam && playerTeam !== champion) return; 
                        if (g.kalla_flik === 'Mästarna') isMastarMal = true;
                        else if (playerTeam && playerTeam === champion) isMastarMal = true;
                        if (!isMastarMal) return;
                    } else if (typ === 'Slutomgångar') {
                        if (g.kalla_flik !== 'Slutomgångar') return;
                    }

                    let infoLower = g.info ? g.info.toLowerCase() : "";
                    let innebordLower = g.innebord ? g.innebord.toLowerCase() : "";
                    let isPenShootout = infoLower.includes('straffläggning') || innebordLower.includes('straffläggning');
                    
                    if (penMode === 'exclude' && isPenShootout) return;
                    if (penMode === 'only' && !isPenShootout) return;

                    if (noOwnGoals && g.skytt.toLowerCase().includes('självmål')) return;
                    if (onlyGwg && g.avgorande !== 'GWG') return;

                    if (qFas) {
                        let mFas = bm.fas.toLowerCase();
                        if (qFas === 'final') {
                            if (!mFas.includes('final') || mFas.includes('kvart') || mFas.includes('semi') || mFas.includes('åtton') || mFas.includes('1/8')) return;
                        } else if (qFas === 'semi') {
                            if (!mFas.includes('semi')) return;
                        } else if (qFas === 'kvart') {
                            if (!mFas.includes('kvart')) return;
                        } else if (qFas === 'grupp') {
                            if (!mFas.includes('grupp')) return;
                        } else if (qFas === 'tidiga') {
                            if (mFas.includes('final') || mFas.includes('semi') || mFas.includes('kvart') || mFas.includes('grupp')) return;
                        }
                    }
                    
                    if (qClub && (!playerTeam || !playerTeam.toLowerCase().includes(qClub))) return;

                    if(!agg[g.skytt]) agg[g.skytt] = { count: 0, seasons: new Set(), clubs: new Set() };
                    agg[g.skytt].count++;
                    let clnSeason = bm.sasong.replace(/\\.0$/, '');
                    agg[g.skytt].seasons.add(clnSeason);
                    
                    if(playerTeam) agg[g.skytt].clubs.add(playerTeam);
                });
            });

            let arr = Object.keys(agg).map(k => ({
                namn: k, 
                mal: agg[k].count,
                seasons: Array.from(agg[k].seasons).sort((a,b) => parseInt(a)-parseInt(b)),
                clubs: Array.from(agg[k].clubs)
            }));
            arr.sort((a,b) => b.mal - a.mal || a.namn.localeCompare(b.namn));

            document.getElementById('skytteliga-body').innerHTML = arr.map(r => {
                let clubStr = r.clubs.length > 0 ? r.clubs.join(', ') : (DJUP.spelare[r.namn] ? DJUP.spelare[r.namn].klubbar : "-");
                let seasonStr = r.seasons.join(', ');
                
                return `
                <tr class="hover:bg-slate-50 transition-colors border-b border-slate-50">
                    <td class="px-4 py-3 font-bold text-slate-800">${formatName(r.namn)}</td>
                    <td class="px-4 py-3 text-center font-bold text-blue-600 text-lg">${r.mal}</td>
                    <td class="px-4 py-3 text-slate-600 text-sm max-w-[200px] truncate" title="${clubStr}">${clubStr}</td>
                    <td class="px-4 py-3 text-slate-500 text-xs max-w-[200px] truncate" title="${seasonStr}">${seasonStr}</td>
                </tr>
                `;
            }).join('');
        }

        // --- SKYTTEKUNG PER SÄSONG ---
        function renderTopScorersPerSeason() {
            CURRENT_SKYTTELIGA_TYP = 'PerSäsong';
            
            document.getElementById('btn-sk-slut').className = "px-4 py-2 bg-slate-200 text-slate-700 rounded font-medium shadow-sm hover:bg-slate-300 transition-colors";
            document.getElementById('btn-sk-mast').className = "px-4 py-2 bg-slate-200 text-slate-700 rounded font-medium shadow-sm hover:bg-slate-300 transition-colors";
            document.getElementById('btn-sk-season').className = "px-4 py-2 bg-blue-600 text-white rounded font-medium shadow-sm transition-colors";
            
            document.getElementById('sk-filters-container').classList.add('opacity-50', 'pointer-events-none');
            document.getElementById('skytteliga-title').innerText = "Årets Skyttekung (Mål för Mästarlaget under hela cupen)";

            let seasonScorers = {};
            Object.keys(DJUP.matcher).forEach(mid => {
                let dm = DJUP.matcher[mid];
                let bm = BASE_MATCHES[mid];
                if(!bm) return;
                
                let season = bm.sasong.replace(/\\.0$/, '');
                let champion = SEASON_CHAMPIONS[season] || bm.winner;
                if(!seasonScorers[season]) seasonScorers[season] = { champ: champion, players: {} };

                dm.mal.forEach(g => {
                    let playerTeam = g.lag;
                    if (!playerTeam) {
                        let pLineup = dm.uppstallning.find(p => p.namn === g.skytt);
                        if (pLineup) {
                            playerTeam = getPlayerTeam(pLineup.lag, bm);
                        } else {
                            playerTeam = getPlayerTeamInSeason(g.skytt, season);
                        }
                    }
                    
                    if (!playerTeam) {
                        playerTeam = champion;
                    }
                    
                    if (playerTeam !== champion) return; 
                    
                    let isMastarMal = false;
                    if (g.kalla_flik === 'Mästarna') isMastarMal = true;
                    else if (playerTeam && playerTeam === champion) isMastarMal = true;
                    
                    if (isMastarMal && !g.skytt.toLowerCase().includes('självmål')) {
                        let infoLower = g.info ? g.info.toLowerCase() : "";
                        let innebordLower = g.innebord ? g.innebord.toLowerCase() : "";
                        let isPenShootout = infoLower.includes('straffläggning') || innebordLower.includes('straffläggning');
                        if (isPenShootout) return; 

                        if (!seasonScorers[season].players[g.skytt]) seasonScorers[season].players[g.skytt] = 0;
                        seasonScorers[season].players[g.skytt]++;
                    }
                });
            });

            let arr = [];
            Object.keys(seasonScorers).forEach(s => {
                let topCount = 0;
                let topScorers = [];
                let playersMap = seasonScorers[s].players;
                Object.keys(playersMap).forEach(player => {
                    let count = playersMap[player];
                    if (count > topCount) {
                        topCount = count;
                        topScorers = [player];
                    } else if (count === topCount && count > 0) {
                        topScorers.push(player);
                    }
                });
                if (topCount > 0) {
                    arr.push({
                        season: s,
                        scorers: topScorers,
                        goals: topCount,
                        champion: seasonScorers[s].champ
                    });
                }
            });

            arr.sort((a,b) => {
                let yA = parseInt(a.season.substring(0,4)) || 0;
                let yB = parseInt(b.season.substring(0,4)) || 0;
                return yB - yA;
            });
            
            document.getElementById('skytteliga-head').innerHTML = `<tr><th class="px-4 py-3 w-32">Säsong</th><th class="px-4 py-3">Skyttekung(ar)</th><th class="px-4 py-3 text-center">Antal Mål</th><th class="px-4 py-3">Mästarlag</th></tr>`;

            let html = arr.map(r => {
                let names = r.scorers.map(formatName).join(', ');
                return `<tr class="hover:bg-slate-50 transition-colors border-b border-slate-50">
                    <td class="px-4 py-3 font-bold text-slate-600">${r.season}</td>
                    <td class="px-4 py-3 font-bold text-slate-800">${names}</td>
                    <td class="px-4 py-3 text-center font-bold text-blue-600 text-lg">${r.goals}</td>
                    <td class="px-4 py-3 text-slate-600">${r.champion}</td>
                </tr>`;
            }).join('');
            
            document.getElementById('skytteliga-body').innerHTML = html;
        }

        // --- MATRIS & GRAFER ---
        function renderMatrixAndGraphs() {
            let sortedSeasons = [...ALL_SEASONS].sort((a,b)=> parseInt(a.substring(0,4)) - parseInt(b.substring(0,4)));
            let isShifted = document.getElementById('mat-double-shifted').checked;
            let onlyDouble = document.getElementById('mat-double-only').checked;
            let chartType = document.getElementById('mat-chart-type').value;

            // 1. DUBBELN
            let doubles = [];
            for(let i=0; i<sortedSeasons.length; i++) {
                let s = sortedSeasons[i];
                let prevS = i > 0 ? sortedSeasons[i-1] : null;

                let sKey = Object.keys(DJUP.sasonger).find(k => isSameSeason(k, s));
                let prevSKey = prevS ? Object.keys(DJUP.sasonger).find(k => isSameSeason(k, prevS)) : null;

                let sm_text = "";
                let smObj = isShifted ? DJUP.sasonger[prevSKey] : DJUP.sasonger[sKey];
                if (smObj && smObj.sm_vinnare) sm_text = smObj.sm_vinnare;
                
                let champ = "";
                if (sKey && DJUP.sasonger[sKey] && DJUP.sasonger[sKey].cup_vinnare) {
                    champ = formatName(DJUP.sasonger[sKey].cup_vinnare);
                } else {
                    champ = SEASON_CHAMPIONS[s];
                }
                
                let isDouble = false;
                if (champ && sm_text) {
                    isDouble = sm_text.toLowerCase().includes(champ.toLowerCase());
                }
                
                if (onlyDouble && !isDouble) continue;

                if (champ || sm_text) {
                    doubles.push({ season: s, champ: champ || "-", sm_text: sm_text || "-", isDouble: isDouble });
                }
            }
            
            let doubleHtml = doubles.map(d => {
                let status = d.isDouble ? `<span class="bg-yellow-100 text-yellow-800 font-bold px-2 py-1 rounded shadow-sm">👑 DUBBELN</span>` : `<span class="text-slate-400">-</span>`;
                return `<tr class="hover:bg-slate-50 border-b border-slate-50">
                    <td class="px-4 py-3 font-medium text-slate-600">${d.season}</td>
                    <td class="px-4 py-3 font-bold text-yellow-600">${d.champ}</td>
                    <td class="px-4 py-3 text-slate-800">${d.sm_text}</td>
                    <td class="px-4 py-3 text-center">${status}</td>
                </tr>`;
            }).join('');
            document.getElementById('matrix-doubles-body').innerHTML = doubleHtml || `<tr><td colspan="4" class="text-center py-4 text-slate-500">Inga resultat hittades för vald filtrering.</td></tr>`;

            // 2. FAS-MATRISEN
            let matrixData = {};
            sortedSeasons.forEach(s => {
                let sMatches = Object.values(BASE_MATCHES).filter(m => String(m.sasong).replace(/\\.0$/, '') === s && parseInt(m.avancerade) !== 7);
                let kvartTeams = new Set();
                let semiTeams = new Set();
                let finalTeams = new Set();
                
                sMatches.forEach(m => {
                    let f = m.fas.toLowerCase();
                    if (f.includes('kvart')) { kvartTeams.add(m.hemma); kvartTeams.add(m.borta); }
                    if (f.includes('semi')) { semiTeams.add(m.hemma); semiTeams.add(m.borta); }
                    if (f.includes('final') && !f.includes('kvart') && !f.includes('semi') && !f.includes('åtton') && !f.includes('1/8')) { 
                        finalTeams.add(m.hemma); finalTeams.add(m.borta); 
                    }
                });
                
                let champ = SEASON_CHAMPIONS[s];
                let allTeamsThisSeason = new Set([...kvartTeams, ...semiTeams, ...finalTeams]);
                if (champ) allTeamsThisSeason.add(champ);

                allTeamsThisSeason.forEach(t => {
                    if (!matrixData[t]) matrixData[t] = { team: t, guld: 0, final: 0, semi: 0, kvart: 0 };
                    if (champ === t) matrixData[t].guld++;
                    if (finalTeams.has(t)) matrixData[t].final++;
                    if (semiTeams.has(t)) matrixData[t].semi++;
                    if (kvartTeams.has(t)) matrixData[t].kvart++;
                });
            });

            currentMatrixData = Object.values(matrixData);
            sortMatrix('guld', true);

            // 3. GRAF: MÄSTARDOMINANS
            let top10Teams = [...currentMatrixData].sort((a,b) => b.guld - a.guld).slice(0, 10);
            let teamNames = top10Teams.map(t => t.team);
            
            let availableDecades = Object.keys(DECADES).sort(); 
            const colors = ['#ef4444', '#f97316', '#eab308', '#84cc16', '#10b981', '#06b6d4', '#3b82f6', '#8b5cf6', '#d946ef', '#f43f5e', '#14b8a6', '#6366f1', '#fcd34d', '#a855f7', '#0ea5e9'];
            let datasets = [];
            
            availableDecades.forEach((dec, i) => {
                let dataForDecade = [];
                let seasonsInDecade = DECADES[dec];
                teamNames.forEach(team => {
                    let guldCount = 0;
                    seasonsInDecade.forEach(s => {
                        if (SEASON_CHAMPIONS[s] === team) guldCount++;
                    });
                    dataForDecade.push(guldCount);
                });
                
                if (dataForDecade.some(v => v > 0)) {
                    datasets.push({
                        label: dec,
                        data: dataForDecade,
                        backgroundColor: colors[i % colors.length],
                    });
                }
            });

            const ctxDominance = document.getElementById('chart-dominance').getContext('2d');
            if(window.cupCharts['dominance']) window.cupCharts['dominance'].destroy();
            window.cupCharts['dominance'] = new Chart(ctxDominance, {
                type: 'bar',
                data: {
                    labels: teamNames,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { stacked: true },
                        y: { stacked: true, beginAtZero: true, title: { display: true, text: 'Antal Titlar' }, ticks: { stepSize: 1 } }
                    },
                    plugins: {
                        legend: { position: 'right' }
                    }
                }
            });

            // 4. GRAF: STRAFFAR / FÖRLÄNGNING
            let penStats = [];
            availableDecades.forEach(dec => {
                let sInDecade = DECADES[dec];
                let knockoutMatches = 0;
                let occurences = 0;
                
                sInDecade.forEach(s => {
                    let sMatches = Object.values(BASE_MATCHES).filter(m => String(m.sasong).replace(/\\.0$/, '') === s && parseInt(m.avancerade) !== 7);
                    sMatches.forEach(m => {
                        let f = m.fas.toLowerCase();
                        if (f.includes('kvart') || f.includes('semi') || (f.includes('final') && !f.includes('åtton') && !f.includes('1/8'))) {
                            knockoutMatches++;
                            if (chartType === 'pen') {
                                if (cleanNumber(m.sh) !== "" && cleanNumber(m.sb) !== "") occurences++;
                            } else {
                                if (cleanNumber(m.fh) !== "" && cleanNumber(m.fb) !== "") occurences++;
                            }
                        }
                    });
                });
                
                let pct = knockoutMatches > 0 ? (occurences / knockoutMatches) * 100 : 0;
                penStats.push({ decade: dec, pct: pct, koMatches: knockoutMatches, occs: occurences });
            });
            
            penStats = penStats.filter(p => p.koMatches > 0);

            const ctxPenalties = document.getElementById('chart-penalties').getContext('2d');
            if(window.cupCharts['penalties']) window.cupCharts['penalties'].destroy();
            
            let chartLabel = chartType === 'pen' ? '% av slutspelet som gick till straffar' : '% av slutspelet som gick till förlängning';
            
            window.cupCharts['penalties'] = new Chart(ctxPenalties, {
                type: 'line',
                data: {
                    labels: penStats.map(p => p.decade),
                    datasets: [{
                        label: chartLabel,
                        data: penStats.map(p => p.pct),
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        borderWidth: 3,
                        pointBackgroundColor: '#1e3a8a',
                        pointRadius: 5,
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, max: 100, title: { display: true, text: 'Procent (%)' } }
                    },
                    plugins: {
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    let d = penStats[context.dataIndex];
                                    return `${d.pct.toFixed(1)}% (${d.occs} av ${d.koMatches} matcher)`;
                                }
                            }
                        }
                    }
                }
            });

            // 5. GRAF: PUBLIKSNITT PER DECENNIUM
            let attPhaseDec = document.getElementById('mat-att-phase-dec').value;
            let attDecData = [];
            availableDecades.forEach(dec => {
                let sInDecade = DECADES[dec];
                let totPub = 0; let countPub = 0;
                sInDecade.forEach(s => {
                    let sMatches = Object.values(BASE_MATCHES).filter(m => String(m.sasong).replace(/\.0$/, '') === s && parseInt(m.avancerade) !== 7);
                    sMatches.forEach(m => {
                        let f = m.fas.toLowerCase();
                        let isMatch = false;
                        if (attPhaseDec === 'all' && (f.includes('kvart') || f.includes('semi') || (f.includes('final') && !f.includes('åtton') && !f.includes('1/8')))) isMatch = true;
                        if (attPhaseDec === 'kvart' && f.includes('kvart')) isMatch = true;
                        if (attPhaseDec === 'semi' && f.includes('semi')) isMatch = true;
                        if (attPhaseDec === 'final' && f.includes('final') && !f.includes('kvart') && !f.includes('semi') && !f.includes('åtton') && !f.includes('1/8')) isMatch = true;

                        if (isMatch) {
                            let p = parseInt(cleanNumber(m.publik));
                            if (!isNaN(p) && p > 0) { totPub += p; countPub++; }
                        }
                    });
                });
                attDecData.push(countPub > 0 ? Math.round(totPub / countPub) : 0);
            });

            const ctxAttDec = document.getElementById('chart-att-dec').getContext('2d');
            if(window.cupCharts['attDec']) window.cupCharts['attDec'].destroy();
            window.cupCharts['attDec'] = new Chart(ctxAttDec, {
                type: 'bar',
                data: {
                    labels: availableDecades,
                    datasets: [{
                        label: 'Publiksnitt',
                        data: attDecData,
                        backgroundColor: '#0ea5e9',
                        borderRadius: 4
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
            });

            // 6. GRAF: PUBLIKSNITT PER SÄSONG
            let attPhaseSea = document.getElementById('mat-att-phase-sea').value;
            let attSeaLabels = [];
            let attSeaData = [];
            sortedSeasons.forEach(s => {
                let sMatches = Object.values(BASE_MATCHES).filter(m => String(m.sasong).replace(/\.0$/, '') === s && parseInt(m.avancerade) !== 7);
                let totPub = 0; let countPub = 0;
                sMatches.forEach(m => {
                    let f = m.fas.toLowerCase();
                    let isMatch = false;
                    if (attPhaseSea === 'all' && (f.includes('kvart') || f.includes('semi') || (f.includes('final') && !f.includes('åtton') && !f.includes('1/8')))) isMatch = true;
                    if (attPhaseSea === 'kvart' && f.includes('kvart')) isMatch = true;
                    if (attPhaseSea === 'semi' && f.includes('semi')) isMatch = true;
                    if (attPhaseSea === 'final' && f.includes('final') && !f.includes('kvart') && !f.includes('semi') && !f.includes('åtton') && !f.includes('1/8')) isMatch = true;

                    if (isMatch) {
                        let p = parseInt(cleanNumber(m.publik));
                        if (!isNaN(p) && p > 0) { totPub += p; countPub++; }
                    }
                });
                if (countPub > 0) {
                    attSeaLabels.push(s);
                    attSeaData.push(Math.round(totPub / countPub));
                }
            });

            const ctxAttSea = document.getElementById('chart-att-sea').getContext('2d');
            if(window.cupCharts['attSea']) window.cupCharts['attSea'].destroy();
            window.cupCharts['attSea'] = new Chart(ctxAttSea, {
                type: 'line',
                data: {
                    labels: attSeaLabels,
                    datasets: [{
                        label: 'Publiksnitt',
                        data: attSeaData,
                        borderColor: '#0284c7',
                        backgroundColor: 'rgba(2, 132, 199, 0.1)',
                        borderWidth: 2,
                        pointRadius: 3,
                        fill: true,
                        tension: 0.2
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
            });
            // 7. GRAF: SNITTÅLDER PER DECENNIUM
            let ageTeamDec = document.getElementById('mat-age-team-dec') ? document.getElementById('mat-age-team-dec').value : 'all';
            let ageTypeDec = document.getElementById('mat-age-type-dec') ? document.getElementById('mat-age-type-dec').value : 'start';
            
            let ageDecData = [];
            availableDecades.forEach(dec => {
                let sInDecade = DECADES[dec];
                let totDays = 0; let countPlayers = 0;
                
                sInDecade.forEach(s => {
                    let champion = SEASON_CHAMPIONS[s];
                    Object.keys(DJUP.matcher).forEach(mid => {
                        let bm = BASE_MATCHES[mid];
                        if (!bm || String(bm.sasong).replace(/\.0$/, '') !== s) return;
                        
                        let f = bm.fas.toLowerCase();
                        if (f.includes('final') && !f.includes('kvart') && !f.includes('semi') && !f.includes('åtton') && !f.includes('1/8')) {
                            let dm = DJUP.matcher[mid];
                            if(!dm) return;
                            
                            dm.uppstallning.forEach(p => {
                                let pTeam = getPlayerTeam(p.lag, bm);
                                let isChamp = (pTeam === champion);
                                
                                if (ageTeamDec === 'champ' && !isChamp) return;
                                if (ageTeamDec === 'runner' && isChamp) return;
                                
                                let isStarter = (parseInt(p.pos) <= 11);
                                let pMinVal = parseInt(cleanNumber(p.minuter)) || 0;
                                let bText = String(p.byte || '').toLowerCase();
                                let isPlayed = isStarter || (pMinVal > 0) || /\bin\b/.test(bText) || /\but\b/.test(bText) || bText === 'in' || bText === 'ut';
                                
                                if (ageTypeDec === 'start' && !isStarter) return;
                                if (ageTypeDec === 'played' && !isPlayed) return;
                                
                                let ageData = getPlayerAgeAtMatch(p.namn, formatDate(bm.datum, s));
                                if (ageData) {
                                    totDays += ageData.totalDays;
                                    countPlayers++;
                                }
                            });
                        }
                    });
                });
                
                let avgYears = countPlayers > 0 ? (totDays / countPlayers) / 365.25 : 0;
                ageDecData.push(avgYears > 0 ? parseFloat(avgYears.toFixed(1)) : null);
            });

            const ctxAgeDec = document.getElementById('chart-age-dec').getContext('2d');
            if(window.cupCharts['ageDec']) window.cupCharts['ageDec'].destroy();
            window.cupCharts['ageDec'] = new Chart(ctxAgeDec, {
                type: 'bar',
                data: {
                    labels: availableDecades,
                    datasets: [{
                        label: 'Snittålder (År)',
                        data: ageDecData,
                        backgroundColor: '#10b981',
                        borderRadius: 4
                    }]
                },
                options: { 
                    responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, 
                    scales: { y: { suggestedMin: 22, suggestedMax: 30 } } 
                }
            });

            // 8. GRAF: SNITTÅLDER PER SÄSONG
            let ageTeamSea = document.getElementById('mat-age-team-sea') ? document.getElementById('mat-age-team-sea').value : 'all';
            let ageTypeSea = document.getElementById('mat-age-type-sea') ? document.getElementById('mat-age-type-sea').value : 'start';
            
            let ageSeaLabels = []; let ageSeaData = [];
            
            sortedSeasons.forEach(s => {
                let champion = SEASON_CHAMPIONS[s];
                let totDays = 0; let countPlayers = 0;
                
                Object.keys(DJUP.matcher).forEach(mid => {
                    let bm = BASE_MATCHES[mid];
                    if (!bm || String(bm.sasong).replace(/\.0$/, '') !== s) return;
                    
                    let f = bm.fas.toLowerCase();
                    if (f.includes('final') && !f.includes('kvart') && !f.includes('semi') && !f.includes('åtton') && !f.includes('1/8')) {
                        let dm = DJUP.matcher[mid];
                        if(!dm) return;
                        
                        dm.uppstallning.forEach(p => {
                            let pTeam = getPlayerTeam(p.lag, bm);
                            let isChamp = (pTeam === champion);
                            
                            if (ageTeamSea === 'champ' && !isChamp) return;
                            if (ageTeamSea === 'runner' && isChamp) return;
                            
                            let isStarter = (parseInt(p.pos) <= 11);
                            let pMinVal = parseInt(cleanNumber(p.minuter)) || 0;
                            let bText = String(p.byte || '').toLowerCase();
                            let isPlayed = isStarter || (pMinVal > 0) || /\bin\b/.test(bText) || /\but\b/.test(bText) || bText === 'in' || bText === 'ut';
                            
                            if (ageTypeSea === 'start' && !isStarter) return;
                            if (ageTypeSea === 'played' && !isPlayed) return;
                            
                            let ageData = getPlayerAgeAtMatch(p.namn, formatDate(bm.datum, s));
                            if (ageData) {
                                totDays += ageData.totalDays;
                                countPlayers++;
                            }
                        });
                    }
                });
                
                if (countPlayers > 0) {
                    ageSeaLabels.push(s);
                    let avgYears = (totDays / countPlayers) / 365.25;
                    ageSeaData.push(parseFloat(avgYears.toFixed(2)));
                }
            });

            const ctxAgeSea = document.getElementById('chart-age-sea').getContext('2d');
            if(window.cupCharts['ageSea']) window.cupCharts['ageSea'].destroy();
            window.cupCharts['ageSea'] = new Chart(ctxAgeSea, {
                type: 'line',
                data: {
                    labels: ageSeaLabels,
                    datasets: [{
                        label: 'Snittålder (År)',
                        data: ageSeaData,
                        borderColor: '#059669',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        borderWidth: 2,
                        pointRadius: 3,
                        fill: true,
                        tension: 0.2
                    }]
                },
                options: { 
                    responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, 
                    scales: { y: { suggestedMin: 22, suggestedMax: 30 } } 
                }
            });
        }

        function sortMatrix(col, forceDesc = false) {
            if (forceDesc) { currentMatrixSort.col = col; currentMatrixSort.asc = false; }
            else if (currentMatrixSort.col === col) { currentMatrixSort.asc = !currentMatrixSort.asc; }
            else { currentMatrixSort.col = col; currentMatrixSort.asc = false; }
            
            currentMatrixData.sort((a, b) => {
                let valA = a[col], valB = b[col];
                if (typeof valA === 'string') return currentMatrixSort.asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
                return currentMatrixSort.asc ? valA - valB : valB - valA;
            });
            
            let html = currentMatrixData.map(r => `
                <tr class="hover:bg-slate-50">
                    <td class="px-4 py-3 font-bold text-slate-800">${r.team}</td>
                    <td class="px-4 py-3 text-center font-bold text-yellow-600 text-lg bg-yellow-50/30">${r.guld}</td>
                    <td class="px-4 py-3 text-center text-slate-700 font-semibold">${r.final}</td>
                    <td class="px-4 py-3 text-center text-slate-600">${r.semi}</td>
                    <td class="px-4 py-3 text-center text-slate-500">${r.kvart}</td>
                </tr>
            `).join('');
            
            document.getElementById('matrix-phases-body').innerHTML = html;
        }

        // --- TOPPLISTOR & HISTORIK ---
        function renderToplist() {
            let cat = document.getElementById('toplist-category').value;
            let onlyChamp = document.getElementById('toplist-only-champ').checked;
            let onlyPlayedEl = document.getElementById('toplist-only-played');
            let onlyPlayed = onlyPlayedEl ? onlyPlayedEl.checked : false;
            // Visa RAE-info-knappen endast på demografi-flikarna
            let raeBtn = document.getElementById('rae-info-btn');
            if (raeBtn) {
                if (cat === 'birth_months' || cat === 'birth_decades' || cat === 'rae_over_time') {
                    raeBtn.classList.remove('hidden');
                } else {
                    raeBtn.classList.add('hidden');
                }
            }

            let titleEl = document.getElementById('toplist-title');
            let headEl = document.getElementById('toplist-head');
            let bodyEl = document.getElementById('toplist-body');
            
            if (cat === 'champions_chronological') {
                document.getElementById('toplist-filters-container').classList.add('opacity-30', 'pointer-events-none');
                titleEl.innerText = "Kronologisk Mästarlängd (Cupmästare)";
                headEl.innerHTML = `<tr><th class="px-4 py-3">Säsong</th><th class="px-4 py-3">Cupmästare (Titel)</th><th class="px-4 py-3">Lagkapten</th><th class="px-4 py-3">Tränare</th></tr>`;
                
                let html = '';
                let titleCounts = {};
                let sortedSeasons = [...ALL_SEASONS].sort((a,b)=> parseInt(a.substring(0,4)) - parseInt(b.substring(0,4)));
                
                sortedSeasons.forEach(s => {
                    let champ = SEASON_CHAMPIONS[s];
                    if(champ) {
                        titleCounts[champ] = (titleCounts[champ] || 0) + 1;
                        let sKey = Object.keys(DJUP.sasonger).find(k => isSameSeason(k, s));
                        let kapten = sKey && DJUP.sasonger[sKey].kapten ? formatName(DJUP.sasonger[sKey].kapten) : "Okänd";
                        let tranare = sKey && DJUP.sasonger[sKey].tranare_vinnare ? formatName(DJUP.sasonger[sKey].tranare_vinnare) : "Okänd";
                        
                        html += `<tr class="hover:bg-yellow-50/50 transition-colors border-b border-slate-50">
                            <td class="px-4 py-3 font-medium text-slate-500">${s}</td>
                            <td class="px-4 py-3 font-bold text-yellow-600">${champ} <span class="text-xs text-yellow-500/70 font-medium">(#${titleCounts[champ]})</span> 👑</td>
                            <td class="px-4 py-3 text-slate-800">${kapten}</td>
                            <td class="px-4 py-3 text-slate-800">${tranare}</td>
                        </tr>`;
                    }
                });
                bodyEl.innerHTML = html;
                return;
            }
            
            document.getElementById('toplist-filters-container').classList.remove('opacity-30', 'pointer-events-none');
            
            let results = [];
            
            if (cat === 'flest_titlar') {
                titleEl.innerText = "Spelare: Flest Cuptitlar (Guld)";
                headEl.innerHTML = `<tr><th class="px-4 py-3 w-10">#</th><th class="px-4 py-3">Spelare</th><th class="px-4 py-3 text-center">Antal Guld</th><th class="px-4 py-3">Klubb(ar)</th><th class="px-4 py-3">Säsonger</th></tr>`;
                
                window.PLAYER_STATS.forEach(p => {
                    let validGolds = p.goldMedals;
                    if (onlyPlayed) validGolds = validGolds.filter(m => m.played);

                    if (validGolds.length > 0) {
                        let sortedGolds = [...validGolds].sort((a,b)=>parseInt(a.year)-parseInt(b.year));
                        results.push({
                            name: p.namn,
                            count: validGolds.length,
                            clubs: Array.from(p.goldClubs).join(', '),
                            years: sortedGolds.map(g => g.played ? g.year : `${g.year} (ej spel)`).join(', '),
                            isChamp: true
                        });
                    }
                });
                
                results.sort((a,b) => b.count - a.count || a.name.localeCompare(b.name));
                
                bodyEl.innerHTML = results.slice(0, 50).map((r, i) => {
                    let safeName = escapeHtml(r.name);
                    return `<tr class="hover:bg-slate-50 border-b border-slate-50"><td class="px-4 py-3 font-bold text-slate-400">${i+1}</td><td class="px-4 py-3 font-bold text-slate-800 cursor-pointer hover:text-blue-600" onclick="openPlayerModal('${safeName}')">${formatName(r.name)} 👑</td><td class="px-4 py-3 text-center font-bold text-yellow-600 text-lg">${r.count}</td><td class="px-4 py-3 text-sm text-slate-600">${r.clubs}</td><td class="px-4 py-3 text-xs text-slate-500 max-w-xs truncate" title="${r.years}">${r.years}</td></tr>`;
                }).join('');
            }
            else if (cat === 'flest_finaler') {
                titleEl.innerText = "Spelare: Flest Cupfinaler (Matchtrupp)";
                headEl.innerHTML = `<tr><th class="px-4 py-3 w-10">#</th><th class="px-4 py-3">Spelare</th><th class="px-4 py-3 text-center">Antal Finaler</th><th class="px-4 py-3">Klubb(ar)</th><th class="px-4 py-3">Säsonger</th></tr>`;
                
                window.PLAYER_STATS.forEach(p => {
                    let validMedals = onlyChamp ? [...p.goldMedals] : [...p.goldMedals, ...p.silverMedals];
                    if (onlyPlayed) validMedals = validMedals.filter(m => m.played);

                    if (validMedals.length > 0) {
                        let sortedM = validMedals.sort((a,b)=>parseInt(a.year)-parseInt(b.year));
                        let hasGold = p.goldMedals.filter(m => !onlyPlayed || m.played).length > 0;
                        results.push({
                            name: p.namn,
                            count: validMedals.length,
                            clubs: Array.from(onlyChamp ? p.goldClubs : p.allClubs).join(', '),
                            years: sortedM.map(m => m.played ? m.year : `${m.year} (ej spel)`).join(', '),
                            isChamp: hasGold
                        });
                    }
                });
                results.sort((a,b) => b.count - a.count || a.name.localeCompare(b.name));
                
                bodyEl.innerHTML = results.slice(0, 50).map((r, i) => {
                    let safeName = escapeHtml(r.name);
                    return `<tr class="hover:bg-slate-50 border-b border-slate-50"><td class="px-4 py-3 font-bold text-slate-400">${i+1}</td><td class="px-4 py-3 font-bold text-slate-800 cursor-pointer hover:text-blue-600" onclick="openPlayerModal('${safeName}')">${formatName(r.name)} ${r.isChamp ? '👑' : ''}</td><td class="px-4 py-3 text-center font-bold text-indigo-600 text-lg">${r.count}</td><td class="px-4 py-3 text-sm text-slate-600">${r.clubs}</td><td class="px-4 py-3 text-xs text-slate-500 max-w-xs truncate" title="${r.years}">${r.years}</td></tr>`;
                }).join('');
            }
            else if (cat === 'flest_finalmal') {
                titleEl.innerText = "Spelare: Flest Finalmål (Exklusive straffläggning)";
                headEl.innerHTML = `<tr><th class="px-4 py-3 w-10">#</th><th class="px-4 py-3">Spelare</th><th class="px-4 py-3 text-center">Finalmål</th><th class="px-4 py-3">Klubb(ar)</th><th class="px-4 py-3">Säsonger</th></tr>`;
                
                let goalCounts = {};
                Object.keys(DJUP.matcher).forEach(mid => {
                    let dm = DJUP.matcher[mid];
                    let bm = BASE_MATCHES[mid];
                    if(!bm || !bm.fas.toLowerCase().includes('final') || bm.fas.toLowerCase().includes('kvart') || bm.fas.toLowerCase().includes('semi') || bm.fas.toLowerCase().includes('åtton') || bm.fas.toLowerCase().includes('1/8')) return;
                    
                    let season = bm.sasong.replace(/\\.0$/, '');
                    let champion = SEASON_CHAMPIONS[season];
                    
                    dm.mal.forEach(g => {
                        let infoLower = g.info ? g.info.toLowerCase() : "";
                        let innebordLower = g.innebord ? g.innebord.toLowerCase() : "";
                        if (infoLower.includes('straffläggning') || innebordLower.includes('straffläggning')) return;
                        if (g.skytt.toLowerCase().includes('självmål')) return;
                        
                        let playerTeam = getPlayerTeamInSeason(g.skytt, season);
                        if (!playerTeam) {
                            let pLineup = dm.uppstallning.find(p => p.namn === g.skytt);
                            if (pLineup) playerTeam = getPlayerTeam(pLineup.lag, bm);
                        }
                        if (!playerTeam && g.kalla_flik === 'Mästarna') playerTeam = champion;
                        
                        if (onlyChamp && playerTeam !== champion) return;
                        
                        if (!goalCounts[g.skytt]) goalCounts[g.skytt] = { count: 0, clubs: new Set(), seasons: new Set() };
                        goalCounts[g.skytt].count++;
                        if(playerTeam) goalCounts[g.skytt].clubs.add(playerTeam);
                        goalCounts[g.skytt].seasons.add(season);
                    });
                });
                
                Object.keys(goalCounts).forEach(player => {
                    let isChamp = false;
                    let pStats = window.PLAYER_STATS.find(p => p.namn === player);
                    if (pStats) {
                        let validGolds = pStats.goldMedals;
                        if (onlyPlayed) validGolds = validGolds.filter(m => m.played);
                        if (validGolds.length > 0) isChamp = true;
                    }
                    
                    results.push({
                        name: player,
                        count: goalCounts[player].count,
                        clubs: Array.from(goalCounts[player].clubs).join(', '),
                        years: Array.from(goalCounts[player].seasons).sort((a,b)=>parseInt(a)-parseInt(b)).join(', '),
                        isChamp: isChamp
                    });
                });
                results.sort((a,b) => b.count - a.count || a.name.localeCompare(b.name));
                
                bodyEl.innerHTML = results.slice(0, 50).map((r, i) => {
                    let safeName = escapeHtml(r.name);
                    return `<tr class="hover:bg-slate-50 border-b border-slate-50"><td class="px-4 py-3 font-bold text-slate-400">${i+1}</td><td class="px-4 py-3 font-bold text-slate-800 cursor-pointer hover:text-blue-600" onclick="openPlayerModal('${safeName}')">${formatName(r.name)} ${r.isChamp ? '👑' : ''}</td><td class="px-4 py-3 text-center font-bold text-emerald-600 text-lg">${r.count}</td><td class="px-4 py-3 text-sm text-slate-600">${r.clubs}</td><td class="px-4 py-3 text-xs text-slate-500 max-w-xs truncate" title="${r.years}">${r.years}</td></tr>`;
                }).join('');
            }
            else if (cat === 'oldest_player' || cat === 'youngest_player') {
                let isOldest = cat === 'oldest_player';
                titleEl.innerText = isOldest ? "Äldsta spelarna i en Final (Matchtrupp)" : "Yngsta spelarna i en Final (Matchtrupp)";
                headEl.innerHTML = `<tr><th class="px-4 py-3 w-10">#</th><th class="px-4 py-3">Spelare</th><th class="px-4 py-3 text-center">Ålder</th><th class="px-4 py-3">Klubb</th><th class="px-4 py-3">Final / Datum</th></tr>`;
                
                Object.keys(DJUP.matcher).forEach(mid => {
                    let dm = DJUP.matcher[mid];
                    let bm = BASE_MATCHES[mid];
                    if(!bm || !bm.fas.toLowerCase().includes('final') || bm.fas.toLowerCase().includes('kvart') || bm.fas.toLowerCase().includes('semi') || bm.fas.toLowerCase().includes('åtton') || bm.fas.toLowerCase().includes('1/8')) return;
                    
                    let season = bm.sasong.replace(/\\.0$/, '');
                    let champion = SEASON_CHAMPIONS[season];
                    
                    dm.uppstallning.forEach(p => {
                        let playerTeam = getPlayerTeam(p.lag, bm);
                        if (onlyChamp && playerTeam !== champion) return;
                        
                        let pMinVal = parseInt(cleanNumber(p.minuter)) || 0;
                        let bText = String(p.byte || '').toLowerCase();
                        let playedInMatch = (parseInt(p.pos) <= 11) || (pMinVal > 0) || /\bin\b/.test(bText) || /\but\b/.test(bText) || bText === 'in' || bText === 'ut';
                        
                        if (onlyPlayed && !playedInMatch) return;
                        
                        let ageData = getPlayerAgeAtMatch(p.namn, formatDate(bm.datum, season));
                        if (ageData) {
                            let isChamp = playerTeam === champion;
                            results.push({
                                name: p.namn,
                                team: playerTeam,
                                ageData: ageData,
                                matchDate: formatDate(bm.datum, season),
                                season: season,
                                isChamp: isChamp
                            });
                        }
                    });
                });
                
                if (isOldest) results.sort((a,b) => b.ageData.totalDays - a.ageData.totalDays);
                else results.sort((a,b) => a.ageData.totalDays - b.ageData.totalDays);
                
                let uniqueResults = []; let seen = new Set();
                results.forEach(r => {
                    if(!seen.has(r.name)) {
                        seen.add(r.name);
                        uniqueResults.push(r);
                    }
                });
                
                bodyEl.innerHTML = uniqueResults.slice(0, 50).map((r, i) => {
                    let safeName = escapeHtml(r.name);
                    return `<tr class="hover:bg-slate-50 border-b border-slate-50"><td class="px-4 py-3 font-bold text-slate-400">${i+1}</td><td class="px-4 py-3 font-bold text-slate-800 cursor-pointer hover:text-blue-600" onclick="openPlayerModal('${safeName}')">${formatName(r.name)} ${r.isChamp ? '👑' : ''}</td><td class="px-4 py-3 text-center font-bold text-indigo-600 ${r.ageData.exact ? '' : 'italic'}">${r.ageData.text}</td><td class="px-4 py-3 text-sm text-slate-600">${r.team}</td><td class="px-4 py-3 text-xs text-slate-500">${r.matchDate} <span class="bg-slate-200 px-1 rounded ml-1">${r.season}</span></td></tr>`;
                }).join('');
            }
            else if (cat === 'oldest_scorer' || cat === 'youngest_scorer') {
                let isOldest = cat === 'oldest_scorer';
                titleEl.innerText = isOldest ? "Äldsta målskyttarna i en Final" : "Yngsta målskyttarna i en Final";
                headEl.innerHTML = `<tr><th class="px-4 py-3 w-10">#</th><th class="px-4 py-3">Spelare</th><th class="px-4 py-3 text-center">Ålder</th><th class="px-4 py-3">Klubb</th><th class="px-4 py-3">Final / Datum</th></tr>`;
                
                Object.keys(DJUP.matcher).forEach(mid => {
                    let dm = DJUP.matcher[mid];
                    let bm = BASE_MATCHES[mid];
                    if(!bm || !bm.fas.toLowerCase().includes('final') || bm.fas.toLowerCase().includes('kvart') || bm.fas.toLowerCase().includes('semi') || bm.fas.toLowerCase().includes('åtton') || bm.fas.toLowerCase().includes('1/8')) return;
                    
                    let season = bm.sasong.replace(/\\.0$/, '');
                    let champion = SEASON_CHAMPIONS[season];
                    
                    dm.mal.forEach(g => {
                        let infoLower = g.info ? g.info.toLowerCase() : "";
                        let innebordLower = g.innebord ? g.innebord.toLowerCase() : "";
                        if (infoLower.includes('straffläggning') || innebordLower.includes('straffläggning')) return;
                        if (g.skytt.toLowerCase().includes('självmål')) return;
                        
                        let playerTeam = getPlayerTeamInSeason(g.skytt, season);
                        if (!playerTeam) {
                            let pLineup = dm.uppstallning.find(p => p.namn === g.skytt);
                            if (pLineup) playerTeam = getPlayerTeam(pLineup.lag, bm);
                        }
                        if (!playerTeam && g.kalla_flik === 'Mästarna') playerTeam = champion;
                        
                        if (onlyChamp && playerTeam !== champion) return;
                        
                        let ageData = getPlayerAgeAtMatch(g.skytt, formatDate(bm.datum, season));
                        if (ageData) {
                            let isChamp = playerTeam === champion;
                            results.push({
                                name: g.skytt,
                                team: playerTeam || "Okänd Klubb",
                                ageData: ageData,
                                matchDate: formatDate(bm.datum, season),
                                season: season,
                                isChamp: isChamp
                            });
                        }
                    });
                });
                
                if (isOldest) results.sort((a,b) => b.ageData.totalDays - a.ageData.totalDays);
                else results.sort((a,b) => a.ageData.totalDays - b.ageData.totalDays);
                
                let uniqueResults = []; let seen = new Set();
                results.forEach(r => {
                    if(!seen.has(r.name)) {
                        seen.add(r.name);
                        uniqueResults.push(r);
                    }
                });
                
                bodyEl.innerHTML = uniqueResults.slice(0, 50).map((r, i) => {
                    let safeName = escapeHtml(r.name);
                    return `<tr class="hover:bg-slate-50 border-b border-slate-50"><td class="px-4 py-3 font-bold text-slate-400">${i+1}</td><td class="px-4 py-3 font-bold text-slate-800 cursor-pointer hover:text-blue-600" onclick="openPlayerModal('${safeName}')">${formatName(r.name)} ${r.isChamp ? '👑' : ''}</td><td class="px-4 py-3 text-center font-bold text-emerald-600 ${r.ageData.exact ? '' : 'italic'}">${r.ageData.text}</td><td class="px-4 py-3 text-sm text-slate-600">${r.team}</td><td class="px-4 py-3 text-xs text-slate-500">${r.matchDate} <span class="bg-slate-200 px-1 rounded ml-1">${r.season}</span></td></tr>`;
                }).join('');
            }
            else if (cat === 'longest_span') {
                titleEl.innerText = "Längst period mellan första och sista Cupfinalen";
                headEl.innerHTML = `<tr><th class="px-4 py-3 w-10">#</th><th class="px-4 py-3">Spelare</th><th class="px-4 py-3 text-center">Spann (År)</th><th class="px-4 py-3 text-center">Mästerskap (Guld)</th><th class="px-4 py-3">Säsonger (Första & Sista)</th></tr>`;
                
                window.PLAYER_STATS.forEach(p => {
                    let validMedals = onlyChamp ? [...p.goldMedals] : [...p.goldMedals, ...p.silverMedals];
                    if (onlyPlayed) validMedals = validMedals.filter(m => m.played);

                    if (validMedals.length > 1) {
                        let years = validMedals.map(m => parseInt(m.year)).filter(y => !isNaN(y));
                        if (years.length > 1) {
                            let minYear = Math.min(...years);
                            let maxYear = Math.max(...years);
                            let span = maxYear - minYear;
                            if (span > 0) {
                                let hasGold = p.goldMedals.filter(m => !onlyPlayed || m.played).length > 0;
                                results.push({
                                    name: p.namn,
                                    span: span,
                                    minYear: minYear,
                                    maxYear: maxYear,
                                    golds: p.goldMedals.filter(m => !onlyPlayed || m.played).length,
                                    isChamp: hasGold
                                });
                            }
                        }
                    }
                });
                results.sort((a,b) => b.span - a.span || a.name.localeCompare(b.name));
                
                bodyEl.innerHTML = results.slice(0, 50).map((r, i) => {
                    let safeName = escapeHtml(r.name);
                    return `<tr class="hover:bg-slate-50 border-b border-slate-50"><td class="px-4 py-3 font-bold text-slate-400">${i+1}</td><td class="px-4 py-3 font-bold text-slate-800 cursor-pointer hover:text-blue-600" onclick="openPlayerModal('${safeName}')">${formatName(r.name)} ${r.isChamp ? '👑' : ''}</td><td class="px-4 py-3 text-center font-bold text-indigo-600 text-lg">${r.span}</td><td class="px-4 py-3 text-center text-sm font-bold text-yellow-600">${r.golds}</td><td class="px-4 py-3 text-sm text-slate-500">${r.minYear} — ${r.maxYear}</td></tr>`;
                }).join('');
            }
            else if (cat === 'multi_club_winners') {
                titleEl.innerText = "Visste du att: Spelare som vunnit Cupguld med FLERA olika klubbar";
                headEl.innerHTML = `<tr><th class="px-4 py-3 w-10">#</th><th class="px-4 py-3">Spelare</th><th class="px-4 py-3 text-center">Antal Klubbar</th><th class="px-4 py-3 text-center">Totalt Guld</th><th class="px-4 py-3">Klubbar (Och guldåren)</th></tr>`;
                
                window.PLAYER_STATS.forEach(p => {
                    let validGolds = p.goldMedals;
                    if (onlyPlayed) validGolds = validGolds.filter(m => m.played);

                    let clubGolds = {};
                    validGolds.forEach(g => {
                        if (!clubGolds[g.club]) clubGolds[g.club] = [];
                        clubGolds[g.club].push(g.year);
                    });

                    let uniqueClubs = Object.keys(clubGolds);

                    if (uniqueClubs.length > 1) {
                        let clubDetails = uniqueClubs.map(c => {
                            return `<b>${c}</b> (${clubGolds[c].sort((a,b)=>parseInt(a)-parseInt(b)).join(', ')})`;
                        }).join(' <span class="text-slate-300 mx-1">|</span> ');

                        results.push({
                            name: p.namn,
                            clubCount: uniqueClubs.length,
                            goldCount: validGolds.length,
                            details: clubDetails
                        });
                    }
                });
                
                results.sort((a,b) => b.clubCount - a.clubCount || b.goldCount - a.goldCount || a.name.localeCompare(b.name));
                
                bodyEl.innerHTML = results.map((r, i) => {
                    let safeName = escapeHtml(r.name);
                    return `<tr class="hover:bg-slate-50 border-b border-slate-50"><td class="px-4 py-3 font-bold text-slate-400">${i+1}</td><td class="px-4 py-3 font-bold text-slate-800 cursor-pointer hover:text-blue-600" onclick="openPlayerModal('${safeName}')">${formatName(r.name)} 👑</td><td class="px-4 py-3 text-center font-bold text-indigo-600 text-lg">${r.clubCount}</td><td class="px-4 py-3 text-center font-bold text-yellow-600">${r.goldCount}</td><td class="px-4 py-3 text-sm text-slate-600">${r.details}</td></tr>`;
                }).join('');
            }
            else if (cat === 'fastest_goals') {
                titleEl.innerText = "Visste du att: Snabbaste målen i en Cupfinal";
                headEl.innerHTML = `<tr><th class="px-4 py-3 w-10">#</th><th class="px-4 py-3">Spelare</th><th class="px-4 py-3 text-center">Minut</th><th class="px-4 py-3">Klubb</th><th class="px-4 py-3">Match (Säsong)</th></tr>`;
                
                Object.keys(DJUP.matcher).forEach(mid => {
                    let dm = DJUP.matcher[mid];
                    let bm = BASE_MATCHES[mid];
                    if(!bm || !bm.fas.toLowerCase().includes('final') || bm.fas.toLowerCase().includes('kvart') || bm.fas.toLowerCase().includes('semi') || bm.fas.toLowerCase().includes('åtton') || bm.fas.toLowerCase().includes('1/8')) return;
                    
                    let season = bm.sasong.replace(/\.0$/, '');
                    let champion = SEASON_CHAMPIONS[season];
                    
                    dm.mal.forEach(g => {
                        let infoLower = g.info ? g.info.toLowerCase() : "";
                        let innebordLower = g.innebord ? g.innebord.toLowerCase() : "";
                        if (infoLower.includes('straffläggning') || innebordLower.includes('straffläggning')) return;
                        
                        let minStr = cleanNumber(g.minut);
                        if (!minStr) return; 
                        
                        let baseMin = parseInt(minStr.split('+')[0]);
                        if (isNaN(baseMin)) return;

                        let playerTeam = getPlayerTeamInSeason(g.skytt, season);
                        if (!playerTeam) {
                            let pLineup = dm.uppstallning.find(p => p.namn === g.skytt);
                            if (pLineup) playerTeam = getPlayerTeam(pLineup.lag, bm);
                        }
                        if (!playerTeam && g.kalla_flik === 'Mästarna') playerTeam = champion;
                        
                        if (onlyChamp && playerTeam !== champion) return;
                        
                        let isOwnGoal = g.skytt.toLowerCase().includes('självmål');
                        let skyttName = isOwnGoal ? `Självmål (${g.info || 'okänd'})` : g.skytt;

                        results.push({
                            name: skyttName,
                            minute: baseMin,
                            minuteRaw: minStr,
                            team: playerTeam || "-",
                            matchStr: `${bm.hemma} - ${bm.borta}`,
                            season: season,
                            isChamp: (playerTeam === champion)
                        });
                    });
                });
                
                results.sort((a,b) => a.minute - b.minute || a.name.localeCompare(b.name));
                
                bodyEl.innerHTML = results.slice(0, 50).map((r, i) => {
                    let isSjalvmal = r.name.includes('Självmål');
                    let rawName = isSjalvmal ? r.name.split('(')[1].replace(')','') : r.name;
                    let safeName = escapeHtml(rawName);
                    let crown = r.isChamp ? '👑' : '';
                    let onClick = isSjalvmal ? '' : `cursor-pointer hover:text-blue-600" onclick="openPlayerModal('${safeName}')"`;
                    
                    return `<tr class="hover:bg-slate-50 border-b border-slate-50"><td class="px-4 py-3 font-bold text-slate-400">${i+1}</td><td class="px-4 py-3 font-bold text-slate-800 ${onClick}>${formatName(r.name)} ${crown}</td><td class="px-4 py-3 text-center font-bold text-emerald-600 text-lg">${r.minuteRaw}'</td><td class="px-4 py-3 text-sm text-slate-600">${r.team}</td><td class="px-4 py-3 text-xs text-slate-500">${r.matchStr} <span class="bg-slate-200 px-1 rounded ml-1">${r.season}</span></td></tr>`;
                }).join('');
            }
            else if (cat === 'super_subs') {
                titleEl.innerText = "Visste du att: Superinhopparna (Mål efter inbyte i finalen)";
                headEl.innerHTML = `<tr><th class="px-4 py-3 w-10">#</th><th class="px-4 py-3">Spelare</th><th class="px-4 py-3 text-center">Mål som inhoppare</th><th class="px-4 py-3">Klubb(ar)</th><th class="px-4 py-3">Match (Minut & Säsong)</th></tr>`;
                
                let subGoals = {};
                Object.keys(DJUP.matcher).forEach(mid => {
                    let dm = DJUP.matcher[mid];
                    let bm = BASE_MATCHES[mid];
                    if(!bm || !bm.fas.toLowerCase().includes('final') || bm.fas.toLowerCase().includes('kvart') || bm.fas.toLowerCase().includes('semi') || bm.fas.toLowerCase().includes('åtton') || bm.fas.toLowerCase().includes('1/8')) return;
                    
                    let season = bm.sasong.replace(/\.0$/, '');
                    let champion = SEASON_CHAMPIONS[season];
                    
                    dm.mal.forEach(g => {
                        let infoLower = g.info ? g.info.toLowerCase() : "";
                        let innebordLower = g.innebord ? g.innebord.toLowerCase() : "";
                        if (infoLower.includes('straffläggning') || innebordLower.includes('straffläggning') || g.skytt.toLowerCase().includes('självmål')) return;
                        
                        let pLineup = dm.uppstallning.find(p => p.namn === g.skytt);
                        if (!pLineup) return;

                        let bText = String(pLineup.byte || '').toLowerCase();
                        let startedOnBench = (parseInt(pLineup.pos) > 11);
                        let subbedIn = /\bin\b/.test(bText) || bText === 'in';

                        if (startedOnBench || subbedIn) {
                            let playerTeam = getPlayerTeam(pLineup.lag, bm);
                            if (onlyChamp && playerTeam !== champion) return;

                            if (!subGoals[g.skytt]) subGoals[g.skytt] = { count: 0, details: [], isChamp: false };
                            subGoals[g.skytt].count++;
                            if (playerTeam === champion) subGoals[g.skytt].isChamp = true;
                            
                            let minStr = cleanNumber(g.minut) ? `${cleanNumber(g.minut)}'` : '?';
                            subGoals[g.skytt].details.push(`<b>${playerTeam}</b>: ${minStr} (${season})`);
                        }
                    });
                });
                
                Object.keys(subGoals).forEach(player => {
                    results.push({
                        name: player,
                        count: subGoals[player].count,
                        details: subGoals[player].details.join('<br>'),
                        isChamp: subGoals[player].isChamp
                    });
                });
                
                results.sort((a,b) => b.count - a.count || a.name.localeCompare(b.name));
                
                bodyEl.innerHTML = results.slice(0, 50).map((r, i) => {
                    let safeName = escapeHtml(r.name);
                    return `<tr class="hover:bg-slate-50 border-b border-slate-50"><td class="px-4 py-3 font-bold text-slate-400">${i+1}</td><td class="px-4 py-3 font-bold text-slate-800 cursor-pointer hover:text-blue-600" onclick="openPlayerModal('${safeName}')">${formatName(r.name)} ${r.isChamp ? '👑' : ''}</td><td class="px-4 py-3 text-center font-bold text-rose-600 text-lg">${r.count}</td><td class="px-4 py-3 text-sm text-slate-600" colspan="2">${r.details}</td></tr>`;
                }).join('');
            }
            else if (cat === 'gwg_knockout') {
                titleEl.innerText = "Matchavgörande mål (GWG) i de sista slutspelsfaserna";
                headEl.innerHTML = `<tr><th class="px-4 py-3 w-10">#</th><th class="px-4 py-3">Spelare</th><th class="px-4 py-3 text-center">Totalt GWG</th><th class="px-4 py-3 text-center">I Final</th><th class="px-4 py-3 text-center">I Semi</th><th class="px-4 py-3 text-center">I Kvart</th><th class="px-4 py-3">Klubb(ar)</th><th class="px-4 py-3">Säsonger</th></tr>`;
                
                let gwgStats = {};
                
                Object.keys(DJUP.matcher).forEach(mid => {
                    let dm = DJUP.matcher[mid];
                    let bm = BASE_MATCHES[mid];
                    if(!bm) return;
                    
                    let fLow = bm.fas.toLowerCase();
                    let phase = "";
                    if (fLow.includes('final') && !fLow.includes('kvart') && !fLow.includes('semi') && !fLow.includes('åtton') && !fLow.includes('1/8')) phase = "final";
                    else if (fLow.includes('semi')) phase = "semi";
                    else if (fLow.includes('kvart')) phase = "kvart";
                    else return; 
                    
                    let season = bm.sasong.replace(/\.0$/, '');
                    let champion = SEASON_CHAMPIONS[season];
                    
                    dm.mal.forEach(g => {
                        if (g.avgorande !== 'GWG') return;
                        
                        let infoLower = g.info ? g.info.toLowerCase() : "";
                        let innebordLower = g.innebord ? g.innebord.toLowerCase() : "";
                        if (infoLower.includes('straffläggning') || innebordLower.includes('straffläggning')) return;
                        
                        let playerTeam = getPlayerTeamInSeason(g.skytt, season);
                        if (!playerTeam) {
                            let pLineup = dm.uppstallning.find(p => p.namn === g.skytt);
                            if (pLineup) playerTeam = getPlayerTeam(pLineup.lag, bm);
                        }
                        if (!playerTeam && g.kalla_flik === 'Mästarna') playerTeam = champion;
                        
                        if (onlyChamp && playerTeam !== champion) return;
                        
                        let isOwnGoal = g.skytt.toLowerCase().includes('självmål');
                        let pName = isOwnGoal ? `Självmål (${g.info || 'okänd'})` : g.skytt;
                        
                        if (!gwgStats[pName]) {
                            gwgStats[pName] = { total: 0, final: 0, semi: 0, kvart: 0, clubs: new Set(), seasons: new Set(), isChamp: false, originalName: g.skytt };
                        }
                        
                        gwgStats[pName].total++;
                        if (phase === 'final') gwgStats[pName].final++;
                        else if (phase === 'semi') gwgStats[pName].semi++;
                        else if (phase === 'kvart') gwgStats[pName].kvart++;
                        
                        if (playerTeam) gwgStats[pName].clubs.add(playerTeam);
                        gwgStats[pName].seasons.add(season);
                        if (playerTeam === champion) gwgStats[pName].isChamp = true;
                    });
                });
                
                Object.keys(gwgStats).forEach(player => {
                    results.push({
                        name: gwgStats[player].originalName, 
                        displayName: player,
                        total: gwgStats[player].total,
                        final: gwgStats[player].final,
                        semi: gwgStats[player].semi,
                        kvart: gwgStats[player].kvart,
                        clubs: Array.from(gwgStats[player].clubs).join(', '),
                        seasons: Array.from(gwgStats[player].seasons).sort((a,b)=>parseInt(a)-parseInt(b)).join(', '),
                        isChamp: gwgStats[player].isChamp
                    });
                });
                
                results.sort((a,b) => b.total - a.total || b.final - a.final || b.semi - a.semi || a.displayName.localeCompare(b.displayName));
                
                bodyEl.innerHTML = results.slice(0, 50).map((r, i) => {
                    let isSjalvmal = r.displayName.includes('Självmål');
                    let rawName = isSjalvmal ? r.displayName.split('(')[1].replace(')','') : r.name;
                    let safeName = escapeHtml(rawName);
                    let crown = r.isChamp ? '👑' : '';
                    
                    // Buggfix för förskjutna rader! Säkrar upp klass-attributet
                    let interactClasses = isSjalvmal ? "" : "cursor-pointer hover:text-blue-600";
                    let onClickAttr = isSjalvmal ? "" : `onclick="openPlayerModal('${safeName}')"`;
                    
                    return `<tr class="hover:bg-slate-50 border-b border-slate-50"><td class="px-4 py-3 font-bold text-slate-400">${i+1}</td><td class="px-4 py-3 font-bold text-slate-800 ${interactClasses}" ${onClickAttr}>${formatName(r.displayName)} ${crown}</td><td class="px-4 py-3 text-center font-black text-rose-600 text-lg">${r.total}</td><td class="px-4 py-3 text-center font-bold text-yellow-600 bg-yellow-50/30">${r.final}</td><td class="px-4 py-3 text-center font-bold text-slate-600">${r.semi}</td><td class="px-4 py-3 text-center font-bold text-slate-500">${r.kvart}</td><td class="px-4 py-3 text-sm text-slate-600">${r.clubs}</td><td class="px-4 py-3 text-xs text-slate-500 truncate max-w-xs" title="${r.seasons}">${r.seasons}</td></tr>`;
                }).join('');
            }
            else if (cat === 'silver_no_gold') {
                titleEl.innerText = "Final-förlorarna (Spelare med flest silver, utan att ha vunnit guld)";
                headEl.innerHTML = `<tr><th class="px-4 py-3 w-10">#</th><th class="px-4 py-3">Spelare</th><th class="px-4 py-3 text-center">Antal Silver</th><th class="px-4 py-3">Klubb(ar) i final</th><th class="px-4 py-3">Finalsäsonger</th></tr>`;
                
                window.PLAYER_STATS.forEach(p => {
                    let validGolds = p.goldMedals;
                    let validSilvers = p.silverMedals;
                    if (onlyPlayed) {
                        validGolds = validGolds.filter(m => m.played);
                        validSilvers = validSilvers.filter(m => m.played);
                    }

                    if (validGolds.length === 0 && validSilvers.length > 0) {
                        results.push({
                            name: p.namn,
                            silverCount: validSilvers.length,
                            clubs: Array.from(new Set(validSilvers.map(s => s.club))).join(', '),
                            years: validSilvers.sort((a,b)=>parseInt(a.year)-parseInt(b.year)).map(s => s.played ? s.year : `${s.year} (ej spel)`).join(', ')
                        });
                    }
                });
                
                results.sort((a,b) => b.silverCount - a.silverCount || a.name.localeCompare(b.name));
                
                bodyEl.innerHTML = results.slice(0, 50).map((r, i) => {
                    let safeName = escapeHtml(r.name);
                    return `<tr class="hover:bg-slate-50 border-b border-slate-50"><td class="px-4 py-3 font-bold text-slate-400">${i+1}</td><td class="px-4 py-3 font-bold text-slate-800 cursor-pointer hover:text-blue-600" onclick="openPlayerModal('${safeName}')">${formatName(r.name)}</td><td class="px-4 py-3 text-center font-bold text-slate-400 text-lg">${r.silverCount}</td><td class="px-4 py-3 text-sm text-slate-600">${r.clubs}</td><td class="px-4 py-3 text-xs text-slate-500">${r.years}</td></tr>`;
                }).join('');
            }
            else if (cat === 'captain_winners') {
                titleEl.innerText = "Kaptensligan (Lyft pokalen flest gånger som lagkapten)";
                headEl.innerHTML = `<tr><th class="px-4 py-3 w-10">#</th><th class="px-4 py-3">Spelare</th><th class="px-4 py-3 text-center">Guld som Kapten</th><th class="px-4 py-3">Klubb(ar)</th><th class="px-4 py-3">Säsonger</th></tr>`;
                
                let captains = {};
                ALL_SEASONS.forEach(s => {
                    let sKey = Object.keys(DJUP.sasonger).find(k => isSameSeason(k, s));
                    if (sKey && DJUP.sasonger[sKey].kapten) {
                        // 1. Skapa den 100% unika (oformaterade) nyckeln
                        let rawName = String(DJUP.sasonger[sKey].kapten).trim();
                        
                        if (rawName.toLowerCase() !== "okänd") {
                            let champ = SEASON_CHAMPIONS[s] || "Okänd klubb";
                            if (!captains[rawName]) captains[rawName] = { count: 0, seasons: [], clubs: new Set() };
                            captains[rawName].count++;
                            captains[rawName].seasons.push(s);
                            captains[rawName].clubs.add(champ);
                        }
                    }
                });

                Object.keys(captains).forEach(rawName => {
                    results.push({
                        rawName: rawName,
                        // 2. Skapa det vackra formaterade namnet (för tabellen)
                        prettyName: typeof formatName === 'function' ? formatName(rawName) : rawName,
                        count: captains[rawName].count,
                        clubs: Array.from(captains[rawName].clubs).join(', '),
                        seasons: captains[rawName].seasons.sort((a,b)=>parseInt(a)-parseInt(b)).join(', ')
                    });
                });

                // Sortera på det formaterade namnet
                results.sort((a,b) => b.count - a.count || a.prettyName.localeCompare(b.prettyName));

                bodyEl.innerHTML = results.slice(0, 50).map((r, i) => {
                    // 3. SKICKA IN RAWNAME TILL MODALEN (SÅ DEN HITTAR RÄTT SPELARE), MEN VISA PRETTYNAME I UI
                    let safeName = escapeHtml(r.rawName);
                    return `<tr class="hover:bg-slate-50 border-b border-slate-50"><td class="px-4 py-3 font-bold text-slate-400">${i+1}</td><td class="px-4 py-3 font-bold text-slate-800 cursor-pointer hover:text-blue-600" onclick="openPlayerModal('${safeName}')">${r.prettyName} ©️</td><td class="px-4 py-3 text-center font-bold text-yellow-600 text-lg">${r.count}</td><td class="px-4 py-3 text-sm text-slate-600">${r.clubs}</td><td class="px-4 py-3 text-xs text-slate-500">${r.seasons}</td></tr>`;
                }).join('');
            }
            else if (cat === 'penalty_shootout') {
                titleEl.innerHTML = "Straffspecialisterna i Slutspelet <span class='text-xs font-normal text-slate-400 ml-2'>(OBS: Historiken över straffläggningar är ännu inte helt komplett)</span>";
                headEl.innerHTML = `<tr><th class="px-4 py-3 w-10">#</th><th class="px-4 py-3">Spelare</th><th class="px-4 py-3 text-center">Satta Straffar</th><th class="px-4 py-3">Klubb(ar)</th><th class="px-4 py-3">Match (Säsong)</th></tr>`;
                
                let penStats = {};
                
                Object.keys(DJUP.matcher).forEach(mid => {
                    let dm = DJUP.matcher[mid];
                    let bm = BASE_MATCHES[mid];
                    if(!bm || (!bm.fas.toLowerCase().includes('final') && !bm.fas.toLowerCase().includes('semi') && !bm.fas.toLowerCase().includes('kvart'))) return;
                    
                    let season = bm.sasong.replace(/\.0$/, '');
                    
                    // Läs av matchfasen för K, S eller F
                    let fLow = bm.fas.toLowerCase();
                    let phaseAbbr = "";
                    if (fLow.includes('final') && !fLow.includes('kvart') && !fLow.includes('semi') && !fLow.includes('åtton') && !fLow.includes('1/8')) phaseAbbr = "F";
                    else if (fLow.includes('semi')) phaseAbbr = "S";
                    else if (fLow.includes('kvart')) phaseAbbr = "K";
                    
                    // Skapa en snygg badge för fasen
                    let phaseBadge = phaseAbbr ? `<span class="bg-indigo-100 text-indigo-800 text-[10px] px-1.5 py-0.5 rounded ml-1 font-bold" title="${bm.fas}">${phaseAbbr}</span>` : "";

                    dm.mal.forEach(g => {
                        let infoLower = g.info ? g.info.toLowerCase() : "";
                        let innebordLower = g.innebord ? g.innebord.toLowerCase() : "";
                        
                        // Fångar upp alla mål där info eller innebörd varnar om att det är en avgörande straffsparksläggning
                        if (infoLower.includes('straffläggning') || innebordLower.includes('straffläggning')) {
                            
                            // 1. PRIMÄR SÖKNING: Hämta klubben direkt från den explicita kolumnen i Excel-fliken
                            // Vi kollar både stor och liten bokstav ifall Python ändrat namnet vid JSON-exporten
                            let playerTeam = g.klubben || g.Klubben || g.klubb; 
                            
                            // 2. FALLBACK 1: Sök i uppställningarna för den specifika säsongen
                            if (!playerTeam) {
                                playerTeam = getPlayerTeamInSeason(g.skytt, season);
                            }
                            
                            // 3. FALLBACK 2: Sök i matchens egen laguppställning
                            if (!playerTeam) {
                                let pLineup = dm.uppstallning.find(p => p.namn === g.skytt);
                                if (pLineup) playerTeam = getPlayerTeam(pLineup.lag, bm);
                            }
                            
                            // 4. FALLBACK 3: Finns 'lag' (1 eller 2) ifyllt direkt på mål-raden?
                            if (!playerTeam && g.lag) {
                                if (g.lag == 1 || g.lag == "1" || g.lag == 2 || g.lag == "2") {
                                    playerTeam = getPlayerTeam(g.lag, bm);
                                } else {
                                    playerTeam = g.lag;
                                }
                            }
                            
                            if (!playerTeam) playerTeam = "Klubb saknas";
                            
                            // Filtrering om användaren valt "Visa ENDAST Cupmästare"
                            if (onlyChamp && playerTeam !== SEASON_CHAMPIONS[season]) return;
                            
                            if (!penStats[g.skytt]) penStats[g.skytt] = { count: 0, clubs: new Set(), details: [] };
                            penStats[g.skytt].count++;
                            
                            // Undvik att lägga in texten "Klubb saknas" i klubb-sammanställningen
                            if (playerTeam !== "Klubb saknas") {
                                penStats[g.skytt].clubs.add(playerTeam);
                            }
                            
                            let gwgBadge = (g.avgorande === 'GWG') ? `<span class="bg-yellow-100 text-yellow-800 text-[10px] px-1 py-0.5 rounded ml-1 font-bold">Avgörande</span>` : "";
                            
                            // Lägg till fas-badgen (K, S, F) och eventuell GWG-badge i resultatsträngen
                            penStats[g.skytt].details.push(`${bm.hemma}-${bm.borta} (${season})${phaseBadge}${gwgBadge}`);
                        }
                    });
                });
                
                Object.keys(penStats).forEach(player => {
                    results.push({
                        name: player,
                        count: penStats[player].count,
                        clubs: Array.from(penStats[player].clubs).join(', '),
                        details: penStats[player].details.join('<br>')
                    });
                });
                
                results.sort((a,b) => b.count - a.count || a.name.localeCompare(b.name));
                
                bodyEl.innerHTML = results.slice(0, 50).map((r, i) => {
                    let safeName = escapeHtml(r.name);
                    return `<tr class="hover:bg-slate-50 border-b border-slate-50"><td class="px-4 py-3 font-bold text-slate-400">${i+1}</td><td class="px-4 py-3 font-bold text-slate-800 cursor-pointer hover:text-blue-600" onclick="openPlayerModal('${safeName}')">${formatName(r.name)}</td><td class="px-4 py-3 text-center font-bold text-emerald-600 text-lg">${r.count}</td><td class="px-4 py-3 text-sm text-slate-600">${r.clubs}</td><td class="px-4 py-3 text-xs text-slate-500 leading-relaxed">${r.details}</td></tr>`;
                }).join('');
            }
            else if (cat === 'referee_knockout') {
                titleEl.innerText = "Domarligan i Slutspelet (Kvart till Final)";
                headEl.innerHTML = `<tr><th class="px-4 py-3 w-10">#</th><th class="px-4 py-3">Domare</th><th class="px-4 py-3 text-center">Totalt Dömda</th><th class="px-4 py-3 text-center">Finaler</th><th class="px-4 py-3 text-center">Semifinaler</th><th class="px-4 py-3 text-center">Kvartsfinaler</th><th class="px-4 py-3">Säsonger</th></tr>`;
                
                let refStats = {};
                let results = []; // Garanterar att arrayen finns tillgänglig i detta block
                
                Object.keys(BASE_MATCHES).forEach(mid => {
                    let bm = BASE_MATCHES[mid];
                    if(!bm || !bm.domare) return;
                    
                    let refName = formatName(bm.domare);
                    if (refName.toLowerCase() === 'okänd' || refName.trim() === '') return;
                    
                    let fLow = bm.fas.toLowerCase();
                    let phase = "";
                    if (fLow.includes('final') && !fLow.includes('kvart') && !fLow.includes('semi') && !fLow.includes('åtton') && !fLow.includes('1/8')) phase = "final";
                    else if (fLow.includes('semi')) phase = "semi";
                    else if (fLow.includes('kvart')) phase = "kvart";
                    else return; // Räkna bara slutspel
                    
                    if (!refStats[refName]) {
                        refStats[refName] = { total: 0, final: 0, semi: 0, kvart: 0, seasons: new Set() };
                    }
                    
                    refStats[refName].total++;
                    if (phase === 'final') refStats[refName].final++;
                    else if (phase === 'semi') refStats[refName].semi++;
                    else if (phase === 'kvart') refStats[refName].kvart++;
                    
                    refStats[refName].seasons.add(bm.sasong.replace(/\.0$/, ''));
                });
                
                Object.keys(refStats).forEach(ref => {
                    results.push({
                        name: ref,
                        total: refStats[ref].total,
                        final: refStats[ref].final,
                        semi: refStats[ref].semi,
                        kvart: refStats[ref].kvart,
                        seasons: Array.from(refStats[ref].seasons).sort((a,b)=>parseInt(a)-parseInt(b)).join(', ')
                    });
                });
                
                // Sortera på Totalt, därefter Finaler, sedan alfabetiskt
                results.sort((a,b) => b.total - a.total || b.final - a.final || b.semi - a.semi || a.name.localeCompare(b.name));
                
                bodyEl.innerHTML = results.slice(0, 50).map((r, i) => {
                    // NYHET: Säkrar namnet så att HTML-klicket inte går sönder om domaren har specialtecken i namnet
                    let safeName = escapeHtml(r.name);
                    
                    return `<tr class="hover:bg-slate-50 border-b border-slate-50">
                        <td class="px-4 py-3 font-bold text-slate-400">${i+1}</td>
                        <td class="px-4 py-3 font-black text-slate-800 cursor-pointer hover:text-blue-600" onclick="openPlayerModal('${safeName}')">${r.name} ⚖️</td>
                        <td class="px-4 py-3 text-center font-black text-indigo-600 text-lg">${r.total}</td>
                        <td class="px-4 py-3 text-center font-bold text-yellow-600 bg-yellow-50/30">${r.final}</td>
                        <td class="px-4 py-3 text-center font-bold text-slate-600">${r.semi}</td>
                        <td class="px-4 py-3 text-center font-bold text-slate-500">${r.kvart}</td>
                        <td class="px-4 py-3 text-xs text-slate-500 truncate max-w-xs" title="${r.seasons}">${r.seasons}</td>
                    </tr>`;
                }).join('');
            }
            else if (cat === 'birth_months' || cat === 'birth_decades') {
                let isMonth = (cat === 'birth_months');
                titleEl.innerHTML = isMonth ? "Den relativa ålderseffekten (När på året är finalisterna födda?)" : "Födelsedecennier (Vilka generationer har spelat final?)";

                // Dynamiska headers baserat på om "Endast Mästare" är ibockad
                let lbl = isMonth ? "Månad" : "Decennium";
                let silverHeader = onlyChamp ? "" : `<th class="px-4 py-2 text-center border-l border-b border-slate-200 bg-slate-50" colspan="2">Endast Tvåor</th>`;
                let silverSub = onlyChamp ? "" : `<th class="px-2 py-1 text-center text-[11px] uppercase tracking-wide border-l border-b border-slate-200 bg-slate-50 font-bold text-slate-700">Spelare</th><th class="px-2 py-1 text-center text-[11px] uppercase tracking-wide border-b border-slate-200 bg-slate-50 text-slate-400">Matcher</th>`;

                headEl.innerHTML = `
                    <tr>
                        <th class="px-4 py-2 border-b border-slate-200 bg-slate-100" rowspan="2">${lbl}</th>
                        <th class="px-4 py-2 text-center border-l border-b border-slate-200 bg-slate-100" colspan="2">Totalt ${onlyChamp ? "(Endast Mästare)" : "(Båda Lagen)"}</th>
                        <th class="px-4 py-2 text-center border-l border-b border-slate-200 bg-yellow-50/50" colspan="2">Guld / Mästare</th>
                        ${silverHeader}
                    </tr>
                    <tr>
                        <th class="px-2 py-1 text-center text-[11px] uppercase tracking-wide border-l border-b border-slate-200 bg-slate-100 font-bold text-indigo-700">Spelare</th>
                        <th class="px-2 py-1 text-center text-[11px] uppercase tracking-wide border-b border-slate-200 bg-slate-100 text-slate-500">Matcher</th>
                        <th class="px-2 py-1 text-center text-[11px] uppercase tracking-wide border-l border-b border-slate-200 bg-yellow-50/50 font-bold text-yellow-700">Spelare</th>
                        <th class="px-2 py-1 text-center text-[11px] uppercase tracking-wide border-b border-slate-200 bg-yellow-50/50 text-yellow-600/70">Matcher</th>
                        ${silverSub}
                    </tr>
                `;

                let stats = {};

                window.PLAYER_STATS.forEach(p => {
                    let gMedals = p.goldMedals;
                    let sMedals = p.silverMedals;
                    
                    // 1. Filtrera på "Endast de som deltog på planen"
                    if (onlyPlayed) {
                        gMedals = gMedals.filter(m => m.played);
                        sMedals = sMedals.filter(m => m.played);
                    }
                    
                    // 2. Filtrera på "Endast Cupmästare"
                    if (onlyChamp) {
                        sMedals = []; // Nollställ silvret helt
                    }

                    let goldCount = gMedals.length;
                    let silverCount = sMedals.length;
                    let totalCount = goldCount + silverCount;

                    // Hoppa över spelaren om den inte har några relevanta matcher efter filtreringen
                    if (totalCount === 0) return; 

                    let birthStr = "";
                    if (DJUP.spelare && DJUP.spelare[p.namn]) {
                        let sp = DJUP.spelare[p.namn];
                        birthStr = sp.fodd || sp.Född || sp.fodelsedatum || sp.Födelsedatum || sp.fodelsear || sp.Födelseår || "";
                    }
                    birthStr = String(birthStr).trim();
                    if (birthStr.length < 4) return;

                    let yyyy = null, mm = null;
                    let m1 = birthStr.match(/^(\d{4})-(\d{2})/);
                    if (m1) { yyyy = m1[1]; mm = m1[2]; }
                    else {
                        let m2 = birthStr.match(/^(\d{4})(\d{2})\d{2}$/);
                        if (m2) { yyyy = m2[1]; mm = m2[2]; }
                        else {
                            let m3 = birthStr.match(/^(\d{4})/);
                            if (m3) yyyy = m3[1];
                        }
                    }

                    let key = null;
                    let sortVal = 0;
                    if (isMonth) {
                        if (!mm) return;
                        let mInt = parseInt(mm);
                        if (mInt < 1 || mInt > 12) return;
                        let monthNames = ["", "Januari", "Februari", "Mars", "April", "Maj", "Juni", "Juli", "Augusti", "September", "Oktober", "November", "December"];
                        key = monthNames[mInt];
                        sortVal = mInt;
                    } else {
                        if (!yyyy) return;
                        let dec = Math.floor(parseInt(yyyy) / 10) * 10;
                        key = dec + "-talet";
                        sortVal = dec;
                    }

                    if (!stats[key]) {
                        stats[key] = {
                            key: key, sortVal: sortVal,
                            pTotal: 0, mTotal: 0,
                            pGold: 0, mGold: 0,
                            pSilver: 0, mSilver: 0
                        };
                    }

                    stats[key].pTotal++;
                    stats[key].mTotal += totalCount;

                    if (goldCount > 0) {
                        stats[key].pGold++;
                        stats[key].mGold += goldCount;
                    }
                    if (silverCount > 0) {
                        stats[key].pSilver++;
                        stats[key].mSilver += silverCount;
                    }
                });

                let resultsArr = Object.values(stats);
                resultsArr.sort((a,b) => a.sortVal - b.sortVal);

                let sumTotalP=0, sumTotalM=0, sumGoldP=0, sumGoldM=0, sumSilverP=0, sumSilverM=0;
                resultsArr.forEach(r => {
                    sumTotalP += r.pTotal; sumTotalM += r.mTotal;
                    sumGoldP += r.pGold; sumGoldM += r.mGold;
                    sumSilverP += r.pSilver; sumSilverM += r.mSilver;
                });

                let rowsHtml = resultsArr.map(r => {
                    // Dölj silvercellerna dynamiskt
                    let silverCells = onlyChamp ? "" : `<td class="px-2 py-2 text-center border-l border-slate-100 font-bold text-slate-600">${r.pSilver}</td><td class="px-2 py-2 text-center text-slate-400 bg-slate-50/50">${r.mSilver}</td>`;
                    
                    return `<tr class="hover:bg-blue-50 border-b border-slate-100">
                        <td class="px-4 py-2 font-bold text-slate-800">${r.key}</td>
                        <td class="px-2 py-2 text-center border-l border-slate-100 font-bold text-indigo-600">${r.pTotal}</td>
                        <td class="px-2 py-2 text-center text-slate-500 bg-slate-50/50">${r.mTotal}</td>
                        <td class="px-2 py-2 text-center border-l border-yellow-100 font-bold text-yellow-600 bg-yellow-50/30">${r.pGold}</td>
                        <td class="px-2 py-2 text-center text-yellow-600/70 bg-yellow-50/30">${r.mGold}</td>
                        ${silverCells}
                    </tr>`;
                }).join('');

                let silverSum = onlyChamp ? "" : `<td class="px-2 py-3 text-center border-l border-slate-200 font-black text-slate-700">${sumSilverP}</td><td class="px-2 py-3 text-center text-slate-600 font-bold">${sumSilverM}</td>`;

                rowsHtml += `<tr class="border-t-2 border-slate-300 bg-slate-100">
                    <td class="px-4 py-3 font-black text-slate-800">TOTALT</td>
                    <td class="px-2 py-3 text-center border-l border-slate-200 font-black text-indigo-700">${sumTotalP}</td>
                    <td class="px-2 py-3 text-center text-slate-600 font-bold">${sumTotalM}</td>
                    <td class="px-2 py-3 text-center border-l border-yellow-200 font-black text-yellow-700 bg-yellow-100/50">${sumGoldP}</td>
                    <td class="px-2 py-3 text-center text-yellow-700 font-bold bg-yellow-100/50">${sumGoldM}</td>
                    ${silverSum}
                </tr>`;

                bodyEl.innerHTML = rowsHtml;
            }
            else if (cat === 'rae_over_time') {
                titleEl.innerHTML = "Utveckling av RAE: Vilket årtionde (finalens år) var ålderseffekten starkast?";
                
                headEl.innerHTML = `
                    <tr>
                        <th class="px-4 py-3 border-b border-slate-200 bg-slate-100">Finalens Decennium</th>
                        <th class="px-4 py-3 text-center border-l border-b border-slate-200 bg-slate-100">Unika Finalister</th>
                        <th class="px-4 py-3 text-center border-l border-b border-blue-200 bg-blue-50 text-blue-800">Q1 (Jan-Mar)</th>
                        <th class="px-4 py-3 text-center border-l border-b border-slate-200 bg-slate-50 text-slate-700">Q2 (Apr-Jun)</th>
                        <th class="px-4 py-3 text-center border-l border-b border-slate-200 bg-slate-50 text-slate-700">Q3 (Jul-Sep)</th>
                        <th class="px-4 py-3 text-center border-l border-b border-slate-200 bg-slate-50 text-slate-700">Q4 (Okt-Dec)</th>
                    </tr>
                `;

                let decadeStats = {};

                Object.keys(DJUP.matcher).forEach(mid => {
                    let bm = BASE_MATCHES[mid];
                    if(!bm) return;
                    let fLow = bm.fas.toLowerCase();
                    if (!fLow.includes('final') || fLow.includes('kvart') || fLow.includes('semi') || fLow.includes('åtton') || fLow.includes('1/8')) return;

                    let season = bm.sasong.replace(/\.0$/, '');
                    let matchYear = parseInt(season.substring(0, 4));
                    if (isNaN(matchYear)) return;
                    
                    let dec = Math.floor(matchYear / 10) * 10;
                    let decKey = dec + "-talet";

                    let dm = DJUP.matcher[mid];
                    let champion = SEASON_CHAMPIONS[season];

                    dm.uppstallning.forEach(p => {
                        let pTeam = getPlayerTeam(p.lag, bm);
                        if (onlyChamp && pTeam !== champion) return;

                        let isStarter = (parseInt(p.pos) <= 11);
                        let pMinVal = parseInt(cleanNumber(p.minuter)) || 0;
                        let bText = String(p.byte || '').toLowerCase();
                        let isPlayed = isStarter || (pMinVal > 0) || /\bin\b/.test(bText) || /\but\b/.test(bText) || bText === 'in' || bText === 'ut';

                        if (onlyPlayed && !isPlayed) return;

                        let birthStr = "";
                        if (DJUP.spelare && DJUP.spelare[p.namn]) {
                            let sp = DJUP.spelare[p.namn];
                            birthStr = sp.fodd || sp.Född || sp.fodelsedatum || sp.Födelsedatum || sp.fodelsear || sp.Födelseår || "";
                        }
                        birthStr = String(birthStr).trim();
                        if (birthStr.length < 4) return;

                        let mm = null;
                        let m1 = birthStr.match(/^(\d{4})-(\d{2})/);
                        if (m1) mm = m1[2];
                        else {
                            let m2 = birthStr.match(/^(\d{4})(\d{2})\d{2}$/);
                            if (m2) mm = m2[2];
                        }

                        if (!mm) return;
                        let mInt = parseInt(mm);
                        if (mInt < 1 || mInt > 12) return;

                        if (!decadeStats[decKey]) {
                            // BUGGFIX: key: decKey tillagt här så att raderna får rätt namn!
                            decadeStats[decKey] = { key: decKey, sortVal: dec, total: 0, q1: 0, q2: 0, q3: 0, q4: 0, uniquePlayers: new Set() };
                        }

                        if (!decadeStats[decKey].uniquePlayers.has(p.namn)) {
                            decadeStats[decKey].uniquePlayers.add(p.namn);
                            decadeStats[decKey].total++;
                            if (mInt <= 3) decadeStats[decKey].q1++;
                            else if (mInt <= 6) decadeStats[decKey].q2++;
                            else if (mInt <= 9) decadeStats[decKey].q3++;
                            else decadeStats[decKey].q4++;
                        }
                    });
                });

                let resultsArr = Object.values(decadeStats);
                resultsArr.sort((a,b) => a.sortVal - b.sortVal);

                // Variabler för att summera den totala raden
                let sumTotal = 0, sumQ1 = 0, sumQ2 = 0, sumQ3 = 0, sumQ4 = 0;

                let rowsHtml = resultsArr.map(r => {
                    // Addera till totalen
                    sumTotal += r.total;
                    sumQ1 += r.q1;
                    sumQ2 += r.q2;
                    sumQ3 += r.q3;
                    sumQ4 += r.q4;

                    let pctQ1 = r.total > 0 ? Math.round((r.q1 / r.total) * 100) : 0;
                    let pctQ2 = r.total > 0 ? Math.round((r.q2 / r.total) * 100) : 0;
                    let pctQ3 = r.total > 0 ? Math.round((r.q3 / r.total) * 100) : 0;
                    let pctQ4 = r.total > 0 ? Math.round((r.q4 / r.total) * 100) : 0;

                    let q1Class = pctQ1 > 30 ? "font-black text-blue-700 bg-blue-100/50" : "font-bold text-blue-600 bg-blue-50/50";

                    return `<tr class="hover:bg-slate-50 border-b border-slate-100">
                        <td class="px-4 py-3 font-bold text-slate-800">${r.key}</td>
                        <td class="px-4 py-3 text-center border-l border-slate-200 font-bold text-slate-600">${r.total}</td>
                        <td class="px-4 py-3 text-center border-l border-blue-200 ${q1Class}">${r.q1} <span class="text-xs text-blue-400 ml-1">(${pctQ1}%)</span></td>
                        <td class="px-4 py-3 text-center border-l border-slate-100 font-bold text-slate-600">${r.q2} <span class="text-xs text-slate-400 ml-1">(${pctQ2}%)</span></td>
                        <td class="px-4 py-3 text-center border-l border-slate-100 font-bold text-slate-600">${r.q3} <span class="text-xs text-slate-400 ml-1">(${pctQ3}%)</span></td>
                        <td class="px-4 py-3 text-center border-l border-slate-100 font-bold text-slate-600">${r.q4} <span class="text-xs text-slate-400 ml-1">(${pctQ4}%)</span></td>
                    </tr>`;
                }).join('');

                // Räkna ut procenten för summeringsraden
                let pctTotQ1 = sumTotal > 0 ? Math.round((sumQ1 / sumTotal) * 100) : 0;
                let pctTotQ2 = sumTotal > 0 ? Math.round((sumQ2 / sumTotal) * 100) : 0;
                let pctTotQ3 = sumTotal > 0 ? Math.round((sumQ3 / sumTotal) * 100) : 0;
                let pctTotQ4 = sumTotal > 0 ? Math.round((sumQ4 / sumTotal) * 100) : 0;
                
                let q1TotClass = pctTotQ1 > 30 ? "font-black text-blue-800 bg-blue-200/50" : "font-black text-blue-700 bg-blue-100/50";

                // Lägg till Summeringsraden
                rowsHtml += `<tr class="border-t-2 border-slate-300 bg-slate-100">
                    <td class="px-4 py-3 font-black text-slate-800">TOTALT</td>
                    <td class="px-4 py-3 text-center border-l border-slate-200 font-black text-indigo-700">${sumTotal}</td>
                    <td class="px-4 py-3 text-center border-l border-blue-300 ${q1TotClass}">${sumQ1} <span class="text-xs text-blue-600 ml-1">(${pctTotQ1}%)</span></td>
                    <td class="px-4 py-3 text-center border-l border-slate-200 font-black text-slate-700">${sumQ2} <span class="text-xs text-slate-500 ml-1">(${pctTotQ2}%)</span></td>
                    <td class="px-4 py-3 text-center border-l border-slate-200 font-black text-slate-700">${sumQ3} <span class="text-xs text-slate-500 ml-1">(${pctTotQ3}%)</span></td>
                    <td class="px-4 py-3 text-center border-l border-slate-200 font-black text-slate-700">${sumQ4} <span class="text-xs text-slate-500 ml-1">(${pctTotQ4}%)</span></td>
                </tr>`;

                bodyEl.innerHTML = rowsHtml;
            }
        }

        function searchPlayers() {
            let qName = document.getElementById('player-search').value.toLowerCase();
            let qClub = document.getElementById('club-search').value.toLowerCase();
            let onlyChamp = document.getElementById('check-champ').checked;
            let onlyRun = document.getElementById('check-runner').checked;
            let onlyPlayed = document.getElementById('check-played').checked;

            let filtered = window.PLAYER_STATS.filter(p => {
                let displayClubsSet = new Set();
                if (onlyChamp) p.goldClubs.forEach(c => displayClubsSet.add(c));
                if (onlyRun) p.silverClubs.forEach(c => displayClubsSet.add(c));
                if (!onlyChamp && !onlyRun) p.allClubs.forEach(c => displayClubsSet.add(c));

                if (qClub) {
                    let filteredSet = new Set();
                    displayClubsSet.forEach(c => {
                        if (c.toLowerCase().includes(qClub)) filteredSet.add(c);
                    });
                    displayClubsSet = filteredSet;
                }
                
                let mName = p.namn.toLowerCase().includes(qName);
                
                let mClub = true;
                if (qClub !== "" && displayClubsSet.size === 0) {
                    mClub = false; 
                }

                let matchingGold = qClub ? p.goldMedals.filter(m => m.club.toLowerCase().includes(qClub)) : p.goldMedals;
                let matchingSilver = qClub ? p.silverMedals.filter(m => m.club.toLowerCase().includes(qClub)) : p.silverMedals;
                
                let mChamp = onlyChamp ? matchingGold.length > 0 : true;
                let mRun = onlyRun ? matchingSilver.length > 0 : true;
                
                let mPlayed = true;
                if (onlyPlayed) {
                    let relevantMedals = [...matchingGold, ...matchingSilver];
                    if (relevantMedals.length > 0) {
                        mPlayed = relevantMedals.some(m => m.played);
                    } else {
                        mPlayed = p.hasPlayed; 
                    }
                }
                
                return mName && mClub && mChamp && mRun && mPlayed;
            });

            document.getElementById('player-search-results').innerHTML = filtered.map(r => {
                let meritParts = [];
                
                let displayGold = qClub ? r.goldMedals.filter(m => m.club.toLowerCase().includes(qClub)) : [...r.goldMedals];
                let displaySilver = qClub ? r.silverMedals.filter(m => m.club.toLowerCase().includes(qClub)) : [...r.silverMedals];

                if (onlyChamp && !onlyRun) displaySilver = [];
                if (onlyRun && !onlyChamp) displayGold = [];

                if (displayGold.length > 0) {
                    displayGold.sort((a,b) => parseInt(a.year) - parseInt(b.year));
                    let goldStrs = displayGold.map(g => g.played ? g.year : `${g.year} <span class="text-[9px] text-slate-400 uppercase tracking-widest">(ej spel)</span>`);
                    meritParts.push(`<span class="text-yellow-600 font-bold">${displayGold.length} Guld</span> <span class="text-xs text-slate-500">(${goldStrs.join(', ')})</span>`);
                }

                if (displaySilver.length > 0) {
                    displaySilver.sort((a,b) => parseInt(a.year) - parseInt(b.year));
                    let silverStrs = displaySilver.map(s => s.played ? s.year : `${s.year} <span class="text-[9px] text-slate-400 uppercase tracking-widest">(ej spel)</span>`);
                    meritParts.push(`<span class="text-slate-500 font-bold">${displaySilver.length} Silver</span> <span class="text-xs text-slate-500">(${silverStrs.join(', ')})</span>`);
                }

                let merit = meritParts.length > 0 ? meritParts.join('<br>') : '-';
                let displayNamn = r.namn.replace(/\\b\\d+\\b/g, '').replace(/\\s+/g, ' ').trim();
                
                let displayClubsSet = new Set();
                if (onlyChamp) r.goldClubs.forEach(c => displayClubsSet.add(c));
                if (onlyRun) r.silverClubs.forEach(c => displayClubsSet.add(c));
                if (!onlyChamp && !onlyRun) r.allClubs.forEach(c => displayClubsSet.add(c));

                if (qClub) {
                    let filteredSet = new Set();
                    displayClubsSet.forEach(c => {
                        if (c.toLowerCase().includes(qClub)) filteredSet.add(c);
                    });
                    displayClubsSet = filteredSet;
                }
                
                let displayClubsStr = displayClubsSet.size > 0 ? Array.from(displayClubsSet).join(', ') : (r.infoKlubbar || '-');
                
                let dynamicMins = 0;
                r.minEntries.forEach(entry => {
                    let matchClub = true;
                    if (qClub !== "" && !entry.club.toLowerCase().includes(qClub)) matchClub = false;
                    
                    let matchChamp = true;
                    if (onlyChamp && !entry.isGold) matchChamp = false;
                    if (onlyRun && !entry.isSilver) matchChamp = false;
                    
                    if (matchClub && matchChamp) {
                        dynamicMins += entry.mins;
                    }
                });
                
                let safeName = escapeHtml(r.namn);
                return `<tr class="hover:bg-slate-50 border-b border-slate-50"><td class="px-4 py-2 font-bold text-slate-800">${displayNamn}</td><td class="px-4 py-2 text-xs truncate max-w-xs text-slate-600">${displayClubsStr}</td><td class="px-4 py-2 leading-relaxed">${merit}</td><td class="px-4 py-2 text-center font-mono text-slate-600">${dynamicMins}'</td><td class="px-4 py-2 text-right"><button onclick="openPlayerModal('${safeName}')" class="text-xs bg-indigo-100 text-indigo-700 hover:bg-indigo-600 hover:text-white px-3 py-1 font-bold rounded shadow-sm transition-colors">Visa Profil</button></td></tr>`;
            }).join('');
        }

        function buildPlayerStats() {
            let playerStats = [];
            Object.keys(DJUP.spelare).forEach(namn => {
                let info = DJUP.spelare[namn];
                
                let goldMedals = [];
                let silverMedals = [];
                let minEntries = [];
                
                let allClubs = new Set();
                let goldClubs = new Set();
                let silverClubs = new Set();
                let hasPlayed = false;
                
                Object.keys(DJUP.matcher).forEach(mid => {
                    let dm = DJUP.matcher[mid];
                    let bm = BASE_MATCHES[mid];
                    if(!bm || !bm.fas.toLowerCase().includes('final') || bm.fas.toLowerCase().includes('kvart') || bm.fas.toLowerCase().includes('semi') || bm.fas.toLowerCase().includes('åtton') || bm.fas.toLowerCase().includes('1/8')) return;
                    
                    let pData = dm.uppstallning.find(p => p.namn === namn);
                    if(pData) {
                        let pTeam = getPlayerTeam(pData.lag, bm);
                        let mins = parseInt(cleanNumber(pData.minuter)) || 0;
                        
                        let bText = String(pData.byte || '').toLowerCase();
                        let playedInMatch = (parseInt(pData.pos) <= 11) || (mins > 0) || /\bin\b/.test(bText) || /\but\b/.test(bText) || bText === 'in' || bText === 'ut';
                        
                        if(playedInMatch) hasPlayed = true;

                        let sas = bm.sasong.replace(/\\.0$/, '');
                        let champion = SEASON_CHAMPIONS[sas];

                        let isGold = false;
                        let isSilver = false;
                        
                        if(pTeam) {
                            allClubs.add(pTeam);
                            if (champion) {
                                if (champion === pTeam) { 
                                    isGold = true;
                                    let existing = goldMedals.find(m => m.year === sas);
                                    if (!existing) goldMedals.push({ year: sas, played: playedInMatch, club: pTeam });
                                    else if (playedInMatch) existing.played = true; 
                                    goldClubs.add(pTeam);
                                }
                                else if (champion !== pTeam) { 
                                    isSilver = true;
                                    let existing = silverMedals.find(m => m.year === sas);
                                    if (!existing) silverMedals.push({ year: sas, played: playedInMatch, club: pTeam });
                                    else if (playedInMatch) existing.played = true;
                                    silverClubs.add(pTeam);
                                }
                            } else {
                                if(bm.winner === pTeam) { 
                                    isGold = true;
                                    let existing = goldMedals.find(m => m.year === sas);
                                    if (!existing) goldMedals.push({ year: sas, played: playedInMatch, club: pTeam });
                                    else if (playedInMatch) existing.played = true;
                                    goldClubs.add(pTeam);
                                }
                                else if(bm.winner && bm.winner !== pTeam) { 
                                    isSilver = true;
                                    let existing = silverMedals.find(m => m.year === sas);
                                    if (!existing) silverMedals.push({ year: sas, played: playedInMatch, club: pTeam });
                                    else if (playedInMatch) existing.played = true;
                                    silverClubs.add(pTeam);
                                }
                            }
                            
                            minEntries.push({ club: pTeam, isGold: isGold, isSilver: isSilver, mins: mins });
                        }
                    }
                });
                
                playerStats.push({ 
                    namn: namn, 
                    allClubs: Array.from(allClubs),
                    goldClubs: Array.from(goldClubs),
                    silverClubs: Array.from(silverClubs),
                    hasPlayed: hasPlayed,
                    goldMedals: goldMedals,
                    silverMedals: silverMedals,
                    minEntries: minEntries,
                    infoKlubbar: info.klubbar || '-'
                });
            });
            window.PLAYER_STATS = playerStats.sort((a,b) => a.namn.localeCompare(b.namn));
            searchPlayers();
        }

        function openPlayerModal(namn) {
    try {
        if (!namn) throw new Error("Inget spelarnamn angavs till funktionen.");
        
        const info = DJUP.spelare[namn] || {};
        
        // FIX: Se till att rubriken i modalen blir snygg (formatName), 
        // även om vi skickat in ett oformaterat namn!
        document.getElementById('pm-name').innerText = typeof formatName === 'function' ? formatName(namn) : namn;
        
        let ar = info.ar ? cleanNumber(info.ar) : '';
        
        let pData = window.PLAYER_STATS ? window.PLAYER_STATS.find(p => p.namn === namn) : null;
        if(!pData) {
            pData = { allClubs: new Set(), goldClubs: new Set(), silverClubs: new Set(), infoKlubbar: info.klubbar || '-' };
        }

        let qClubModal = document.getElementById('club-search') ? document.getElementById('club-search').value.toLowerCase() : "";
        let onlyChampModal = document.getElementById('check-champ') ? document.getElementById('check-champ').checked : false;
        let onlyRunModal = document.getElementById('check-runner') ? document.getElementById('check-runner').checked : false;
        
        let displayClubsSet = new Set();
        if (onlyChampModal && pData.goldClubs) pData.goldClubs.forEach(c => displayClubsSet.add(c));
        if (onlyRunModal && pData.silverClubs) pData.silverClubs.forEach(c => displayClubsSet.add(c));
        if (!onlyChampModal && !onlyRunModal && pData.allClubs) pData.allClubs.forEach(c => displayClubsSet.add(c));

        if (qClubModal) {
            let filteredSet = new Set();
            displayClubsSet.forEach(c => {
                if (c.toLowerCase().includes(qClubModal)) filteredSet.add(c);
            });
            displayClubsSet = filteredSet;
        }
        
        let displayClubsStrModal = displayClubsSet.size > 0 ? Array.from(displayClubsSet).join(', ') : (pData.infoKlubbar || '-');
        
        document.getElementById('pm-clubs').innerText = (ar ? "Född " + ar + " | " : "") + displayClubsStrModal;
        
        let contentHtml = '';
        let spMatches = []; let spGoals = []; let spCards = []; let spRef = [];
        
        // --- DEN NYA, SÄKRA MATCHNINGSLOGIKEN ---
        const searchName = namn.trim().toLowerCase();
        
        const getNum = (str) => {
            let m = String(str).trim().match(/\d+$/);
            return m ? m[0] : "";
        };
        const searchNum = getNum(namn);

        const isMatch = (dbName) => {
            if (!dbName) return false;
            
            // 1. Spärr för siffror
            if (getNum(dbName) !== searchNum) return false;
            
            // 2. Använd formatName säkert för den sista jämförelsen
            let fDb = typeof formatName === 'function' ? formatName(dbName).trim().toLowerCase() : dbName.trim().toLowerCase();
            let fSearch = typeof formatName === 'function' ? formatName(namn).trim().toLowerCase() : searchName;
            
            return fDb === fSearch || dbName.trim().toLowerCase() === searchName;
        };
        // ----------------------------------------
        
        Object.keys(DJUP.matcher).forEach(mid => {
            const dm = DJUP.matcher[mid];
            const bm = BASE_MATCHES[mid];
            if(!bm || !dm) return;
            
            if (dm.uppstallning) dm.uppstallning.forEach(p => { if(isMatch(p.namn)) spMatches.push({m: bm, p: p}); });
            if (dm.mal) dm.mal.forEach(g => { if(isMatch(g.skytt)) spGoals.push({m: bm, g: g}); });
            if (dm.utvisningar) dm.utvisningar.forEach(u => { if(isMatch(u.namn)) spCards.push({m: bm, u: u}); });
            
            if (bm.domare && isMatch(bm.domare)) {
                let fLow = String(bm.fas || "").toLowerCase();
                if (fLow.includes('final') || fLow.includes('semi') || fLow.includes('kvart')) {
                    spRef.push(bm);
                }
            }
        });

        // ---------------------------------------------------------
        // RITA UT MATCHER (Samma logik som förut, rör ej HTML:en)
        // ---------------------------------------------------------
        if(spGoals.length > 0) {
            contentHtml += `<div class="bg-white rounded-lg p-4 border border-slate-200 shadow-sm"><h4 class="font-bold text-slate-800 mb-3 flex items-center gap-2"><span class="text-emerald-500 text-xl">⚽</span> Mål (${spGoals.length} st)</h4><ul class="space-y-2 text-sm">`;
            spGoals.sort((a,b)=>String(a.m.sasong).localeCompare(String(b.m.sasong))).forEach(item => {
                let isPenShootout = (item.g.info && item.g.info.toLowerCase().includes('straffläggning')) || (item.g.innebord && item.g.innebord.toLowerCase().includes('straffläggning'));
                let gMin = item.g.minut ? cleanNumber(item.g.minut) + "'" : '?';
                let minText = isPenShootout ? `<span class="bg-slate-100 text-slate-500 px-1 rounded text-xs ml-auto">Straffläggning</span>` : `Minut ${gMin}`;
                contentHtml += `<li class="flex justify-between border-b border-slate-50 pb-1"><span class="text-slate-600">${cleanNumber(item.m.sasong)} (${item.m.fas})</span><span class="font-medium">${item.m.hemma} - ${item.m.borta}</span><span>${minText} ${item.g.avgorande==='GWG'?'<span class="bg-yellow-100 text-yellow-700 text-[10px] px-1 rounded ml-1">GWG</span>':''}</span></li>`;
            });
            contentHtml += `</ul></div>`;
        }

        if(spMatches.length > 0) {
            contentHtml += `<div class="bg-white rounded-lg p-4 border border-slate-200 shadow-sm"><h4 class="font-bold text-slate-800 mb-3 flex items-center gap-2"><span class="text-amber-500 text-xl">🏆</span> Matcher i databasen (${spMatches.length} st)</h4><ul class="space-y-2 text-sm">`;
            spMatches.sort((a,b)=>String(a.m.sasong).localeCompare(String(b.m.sasong))).forEach(item => {
                let pMinVal = parseInt(cleanNumber(item.p.minuter)) || 0;
                let bText = String(item.p.byte || '').toLowerCase();
                let playedInMatch = (parseInt(item.p.pos) <= 11) || (pMinVal > 0) || /\bin\b/.test(bText) || /\but\b/.test(bText) || bText === 'in' || bText === 'ut';

                let pTeam = getPlayerTeam(item.p.lag, item.m);
                let isCap = isPlayerCaptain(item.p.namn, item.p.kapten, pTeam, item.m.sasong);
                let capBadge = isCap ? ` <span class="font-bold text-amber-500" title="Lagkapten">(c)</span>` : "";

                let pMin = pMinVal > 0 ? `${pMinVal}'` : (playedInMatch ? '?' : 'Spelade ej');
                let posText = `Position ${item.p.pos||'?'}`;
                if (pMin === 'Spelade ej') posText = `Bänken (Spelade ej)`;
                posText += capBadge;

                let mSeason = item.m.sasong.replace(/\.0$/, '');
                let tCrown = (typeof SEASON_CHAMPIONS !== 'undefined' && SEASON_CHAMPIONS[mSeason] === getPlayerTeam(item.p.lag, item.m)) ? " <span title='Cupmästare' class='text-yellow-500'>👑</span>" : "";

                let icons = "";
                if (item.p.byte) {
                    let hasIn = /\bin\b/.test(bText) || bText === 'in';
                    let hasUt = /\but\b/.test(bText) || bText === 'ut';
                    let hasUtv = /\butv\b/.test(bText) || bText.includes('utv');
                    if (hasIn) icons += `<span style="color: #10b981; font-size: 11px; margin-left: 4px;" title="Inbytt">▲</span>`;
                    if (hasUt) icons += `<span style="color: #f43f5e; font-size: 11px; margin-left: 4px;" title="Utbytt">▼</span>`;
                    if (hasUtv) icons += `<span style="font-size: 11px; margin-left: 4px;" title="Utvisad">🟥</span>`;
                }
                let isSentOff = spCards.some(c => c.m === item.m);
                if (isSentOff && !icons.includes("🟥")) icons += `<span style="font-size: 11px; margin-left: 4px;" title="Utvisad">🟥</span>`;

                contentHtml += `<li class="flex justify-between border-b border-slate-50 pb-1"><span class="text-slate-600">${cleanNumber(item.m.sasong)} (${item.m.fas})</span><span class="font-medium">${item.m.hemma} - ${item.m.borta}${tCrown}</span><span class="text-slate-400">${posText} ${pMin !== 'Spelade ej' && pMin !== '?' ? `(${pMin})` : ''}${icons}</span></li>`;
            });
            contentHtml += `</ul></div>`;
        }
        
        if(spCards.length > 0) {
             contentHtml += `<div class="bg-white rounded-lg p-4 border border-slate-200 shadow-sm"><h4 class="font-bold text-rose-800 mb-3 flex items-center gap-2"><span class="text-rose-500 text-xl">🟥</span> Utvisningar i finaler</h4><ul class="space-y-2 text-sm text-rose-700">`;
             spCards.forEach(item => {
                 let uMin = item.u.minut ? cleanNumber(item.u.minut) + "'" : '?';
                 contentHtml += `<li class="flex justify-between border-b border-rose-50 pb-1"><span>${cleanNumber(item.m.sasong)}</span><span class="font-medium">${item.m.hemma} - ${item.m.borta}</span><span>Minut ${uMin}</span></li>`;
             });
             contentHtml += `</ul></div>`;
        }
        
        if(spRef.length > 0) {
             contentHtml += `<div class="bg-white rounded-lg p-4 border border-slate-200 shadow-sm"><h4 class="font-bold text-slate-800 mb-3 flex items-center gap-2"><span class="text-slate-500 text-xl">⚖️</span> Dömda matcher i slutomgångar (${spRef.length} st)</h4><ul class="space-y-2 text-sm">`;
             spRef.sort((a,b)=>String(a.sasong).localeCompare(String(b.sasong))).forEach(m => {
                 contentHtml += `<li class="flex justify-between border-b border-slate-50 pb-1"><span class="text-slate-600">${cleanNumber(m.sasong)} <span class="text-xs text-slate-400 ml-1">(${m.fas})</span></span><span class="font-medium">${m.hemma} - ${m.borta}</span></li>`;
             });
             contentHtml += `</ul></div>`;
        }

        if(contentHtml === '') contentHtml = '<div class="text-center text-slate-500 italic py-6">Inga specifika matchhändelser registrerade i djupdykningsdatabasen för denna spelare.</div>';

        safeSetHTML('pm-content', contentHtml);
        
        document.querySelectorAll('#player-modal').forEach(el => el.classList.remove('hidden'));
    } catch(e) {
        console.error("Fel i openPlayerModal:", e);
        alert("Ett fel uppstod när profilen skulle öppnas för " + (namn || "okänd") + ": " + e.message);
    }
}

        // --- ADMIN WARNINGS ---
        function runAdminCheck() {
            let missingScorers = [];
            let goalWarnings = [];
            let tab4Warnings = [];
            
            Object.keys(BASE_MATCHES).forEach(mid => {
                let m = BASE_MATCHES[mid];
                let f = String(m.fas).toLowerCase();
                let dm = DJUP.matcher[mid];
                
                if(f.includes('kvart') || f.includes('semi') || f.includes('final')) {
                    let is00 = parseInt(m.hm||0) === 0 && parseInt(m.bm||0) === 0;
                    let hasStraff = String(m.hm).includes('-') || String(m.bm).includes('-'); 
                    
                    if(!is00 || hasStraff) {
                        if(!dm || dm.mal.length === 0) {
                            missingScorers.push(m);
                        }
                    }
                }
                
                if (dm && dm.mal.length > 0) {
                    let innebordMap = {};
                    let has1_0 = false;
                    let has0_1 = false;
                    let regularGoalsCount = 0;
                    
                    let mast_unmerged = [];
                    let slut_goals = [];

                    let missingGWG = []; // NYHET: Håller koll på matcher utan GWG

                    dm.mal.forEach(g => {
                        let inn = (g.innebord || "").trim().toLowerCase();
                        let nfo = (g.info || "").trim().toLowerCase();
                        let avg = (g.avgorande || "").trim().toUpperCase();
                        
                        // NYHET: Analysera om det saknas GWG i matcher som inte slutade oavgjort
                        if (avg !== 'GWG' && avg !== 'JA') {
                            // Vi kollar detta senare när vi vet slutresultatet
                            g.saknarGWG_potentiellt = true; 
                        }
                        
                        // NYHET: Exakt filtrering. Utesluter BARA straffläggning (inte straffspark under spelets gång)
                        let isShootout = inn.includes('straffläggning') || nfo.includes('straffläggning') || inn === 'str' || nfo === 'str';
                        
                        if (inn && !isShootout) {
                            if(!innebordMap[inn]) innebordMap[inn] = [];
                            innebordMap[inn].push(g);

                            if(inn === "1-0") has1_0 = true;
                            if(inn === "0-1") has0_1 = true;
                            regularGoalsCount++;
                        }
                        
                        if (g.klubb_mismatch) {
                            tab4Warnings.push({match: m, desc: `Spelare ${g.skytt}: ${g.klubb_mismatch}`, mid: mid});
                        }
                        if (g.kalla_flik === 'Mästarna' && !g.merged) mast_unmerged.push(g);
                        if (g.kalla_flik === 'Slutomgångar') slut_goals.push(g);
                    });

                    Object.keys(innebordMap).forEach(inn => {
                        if(innebordMap[inn].length > 1) {
                            goalWarnings.push({ type: 'Dubblett innebörd', match: m, desc: `Innebörd '${inn}' är registrerad ${innebordMap[inn].length} gånger.`, mid: mid });
                        }
                    });

                    if(has1_0 && has0_1) {
                        goalWarnings.push({ type: 'Ologisk öppning', match: m, desc: 'Både 1-0 och 0-1 finns registrerat i samma match.', mid: mid });
                    }
                    
                    let totalScore = parseInt(cleanNumber(m.hm) || 0) + parseInt(cleanNumber(m.bm) || 0) + parseInt(cleanNumber(m.fh) || 0) + parseInt(cleanNumber(m.fb) || 0);
                    if (regularGoalsCount > totalScore && totalScore > 0) {
                        goalWarnings.push({ type: 'Fler mål än resultat', match: m, desc: `${regularGoalsCount} mål inlagda i spelet, men slutresultatet är totalt ${totalScore} mål.`, mid: mid });
                    } else if (regularGoalsCount < totalScore && totalScore > 0) {
                        if (f.includes('kvart') || f.includes('semi') || f.includes('final')) {
                            goalWarnings.push({ type: 'För få mål inlagda', match: m, desc: `Endast ${regularGoalsCount} mål inlagda, men matchen slutade med ${totalScore} mål i spelet.`, mid: mid });
                        }
                    }
                    // --- NYHET: GWG (Game Winning Goal) Koll ---
                    // 1. Identifiera om det är en slutspelsmatch
                    let fasLower = String(m.fas).toLowerCase();
                    let isKnockoutStage = fasLower.includes('kvart') || fasLower.includes('semi') || fasLower.includes('final');
                    
                    // 2. Kolla om matchen hade en vinnare (Hemma totalt vs Borta totalt)
                    let didMatchHaveWinner = (parseInt(cleanNumber(m.hm) || 0) + parseInt(cleanNumber(m.fh) || 0)) !== (parseInt(cleanNumber(m.bm) || 0) + parseInt(cleanNumber(m.fb) || 0));
                    
                    // 3. Larma ENDAST om det är slutspel, matchen är avgjord och GWG saknas
                    if (isKnockoutStage && didMatchHaveWinner && dm.mal.length > 0) {
                        let hasGWG = dm.mal.some(g => (g.avgorande || "").trim().toUpperCase() === 'GWG' || (g.avgorande || "").trim().toUpperCase() === 'JA');
                        if (!hasGWG) {
                            goalWarnings.push({ type: 'Saknar GWG', match: m, desc: `Slutspelsmatch avgjord, men inget mål är markerat som GWG.`, mid: mid });
                        }
                    }
                    
                    if (mast_unmerged.length > 0 && slut_goals.length > 0) {
                        mast_unmerged.forEach(gM => {
                            let bestMatch = null;
                            let matchReason = "";
                            slut_goals.forEach(gS => {
                                if (gS.skytt === gM.skytt) {
                                    bestMatch = gS;
                                    if (String(gS.minut) !== String(gM.minut)) matchReason = `Minut skiljer sig åt (${gM.minut || 'tom'} vs ${gS.minut || 'tom'})`;
                                    else if (String(gS.innebord) !== String(gM.innebord)) matchReason = `Innebörden skiljer sig åt (${gM.innebord || 'tom'} vs ${gS.innebord || 'tom'})`;
                                }
                            });

                            if (bestMatch) {
                                tab4Warnings.push({match: m, desc: `Mål från 'Mästarna' (${gM.skytt}) skapar dubblett. Orsak: ${matchReason}`, mid: mid});
                            } else {
                                tab4Warnings.push({match: m, desc: `Målskytten '${gM.skytt}' i 'Mästarna' saknas, eller stavas annorlunda, i 'Slutomgångar'.`, mid: mid});
                            }
                        });
                    }
                }
            });

            missingScorers.sort((a,b) => String(a.sasong).localeCompare(String(b.sasong)));
            safeSetHTML('admin-warnings-body', missingScorers.length === 0 ? '<tr><td colspan="4" class="p-4 text-emerald-600 font-bold">Bra jobbat! Inga saknade målskyttar i slutspelen.</td></tr>' : missingScorers.map(m => `<tr class="hover:bg-rose-50/50"><td class="px-4 py-2 font-bold">${m.sasong}</td><td class="px-4 py-2 text-slate-600">${m.fas}</td><td class="px-4 py-2">${m.hemma} - ${m.borta}</td><td class="px-4 py-2 text-center font-mono">${m.hm} - ${m.bm}</td></tr>`).join(''));

            safeSetHTML('admin-goals-body', goalWarnings.length === 0 ? '<tr><td colspan="4" class="p-4 text-emerald-600 font-bold">Inga ologiska mål hittades!</td></tr>' : goalWarnings.map(w => `<tr class="hover:bg-amber-50/50"><td class="px-4 py-2 font-bold text-amber-800">${w.type}</td><td class="px-4 py-2 text-slate-600">${w.match.sasong} (${w.match.fas})</td><td class="px-4 py-2 text-slate-800">${w.desc}</td><td class="px-4 py-2 font-mono text-slate-500">${w.mid}</td></tr>`).join(''));
            
            safeSetHTML('admin-mismatch-body', tab4Warnings.length === 0 ? '<tr><td colspan="3" class="p-4 text-emerald-600 font-bold">Inga avvikelser mellan mål-flikarna hittades!</td></tr>' : tab4Warnings.map(w => `<tr class="hover:bg-indigo-50/50"><td class="px-4 py-2 text-slate-600 font-bold">${w.match.sasong} (${w.match.fas})</td><td class="px-4 py-2 text-slate-800">${w.desc}</td><td class="px-4 py-2 font-mono text-slate-500">${w.mid}</td></tr>`).join(''));

            let playerYears = {};
            Object.keys(DJUP.spelare).forEach(p => playerYears[p] = new Set());
            Object.keys(DJUP.matcher).forEach(mid => {
                let m = BASE_MATCHES[mid];
                if (!m) return;
                let s = String(m.sasong).replace(/\.0$/, '');
                let year = parseInt(s.substring(0, 4));
                if(isNaN(year)) return;
                
                let dm = DJUP.matcher[mid];
                if (!dm) return;
                
                if (dm.uppstallning) dm.uppstallning.forEach(p => { if(playerYears[p.namn]) playerYears[p.namn].add(year); });
                if (dm.mal) dm.mal.forEach(g => { if(playerYears[g.skytt]) playerYears[g.skytt].add(year); });
                if (dm.utvisningar) dm.utvisningar.forEach(u => { if(playerYears[u.namn]) playerYears[u.namn].add(year); });
            });
            
            let careerWarnings = [];
            Object.keys(playerYears).forEach(p => {
                let years = Array.from(playerYears[p]);
                if(years.length > 0) {
                    let min = Math.min(...years);
                    let max = Math.max(...years);
                    if (max - min > 10) careerWarnings.push({player: p, min: min, max: max, diff: max - min});
                }
            });
            careerWarnings.sort((a,b) => b.diff - a.diff);
            
            safeSetHTML('admin-career-body', careerWarnings.length === 0 ? '<tr><td colspan="4" class="p-4 text-emerald-600 font-bold">Inga onormalt långa karriärer upptäcktes.</td></tr>' : careerWarnings.map(w => `<tr class="hover:bg-emerald-50/50"><td class="px-4 py-2 font-bold text-emerald-900">${w.player}</td><td class="px-4 py-2 text-center text-slate-600">${w.min}</td><td class="px-4 py-2 text-center text-slate-600">${w.max}</td><td class="px-4 py-2 text-center font-bold text-rose-600">${w.diff} år</td></tr>`).join(''));

            let orphanedPlayers = [];
            Object.keys(DJUP.spelare).forEach(pName => {
                if(playerYears[pName] && playerYears[pName].size === 0) orphanedPlayers.push(pName);
            });
            orphanedPlayers.sort((a,b) => a.localeCompare(b));
            safeSetHTML('admin-players-list', orphanedPlayers.length === 0 ? '<li class="text-emerald-600 font-bold list-none">Alla spelare i registret är kopplade till händelser!</li>' : orphanedPlayers.map(p => `<li>${p}</li>`).join(''));

            let pyWarnings = DJUP.admin_varningar || [];
            if (pyWarnings.length > 0) {
                safeSetHTML('admin-python-warnings', pyWarnings.map(w => `<li class="text-amber-700">${w}</li>`).join(''));
            } else {
                safeSetHTML('admin-python-warnings', '<li class="text-emerald-600 font-bold list-none">Inga strukturfel hittades i Excel-filen!</li>');
            }
        }
        function renderAnalys() {
            let cat = document.getElementById('analys-category').value;
            let headEl = document.getElementById('analys-head');
            let bodyEl = document.getElementById('analys-body');
            
            if (!cat) return; // Avbryt om användaren inte valt något

            headEl.innerHTML = "";
            bodyEl.innerHTML = "";

            if (cat === 'player_coach') {
                headEl.innerHTML = `
                    <tr>
                        <th class="px-4 py-3 border-b border-slate-200 bg-slate-100 w-10">#</th>
                        <th class="px-4 py-3 border-b border-slate-200 bg-slate-100">Namn</th>
                        <th class="px-4 py-3 text-center border-l border-b border-yellow-200 bg-yellow-50 text-yellow-800" colspan="2">Som Spelare</th>
                        <th class="px-4 py-3 text-center border-l border-b border-indigo-200 bg-indigo-50 text-indigo-800" colspan="2">Som Tränare</th>
                        <th class="px-4 py-3 border-l border-b border-slate-200 bg-slate-100">Meriter (Klubbar & År)</th>
                    </tr>
                    <tr>
                        <th class="px-4 py-1 border-b border-slate-200 bg-slate-100"></th>
                        <th class="px-4 py-1 border-b border-slate-200 bg-slate-100"></th>
                        <th class="px-2 py-1 text-center text-[10px] uppercase border-l border-b border-yellow-200 bg-yellow-50 font-bold text-yellow-700">Guld</th>
                        <th class="px-2 py-1 text-center text-[10px] uppercase border-b border-yellow-200 bg-yellow-50 font-bold text-slate-500">Silver</th>
                        <th class="px-2 py-1 text-center text-[10px] uppercase border-l border-b border-indigo-200 bg-indigo-50 font-bold text-indigo-700">Guld</th>
                        <th class="px-2 py-1 text-center text-[10px] uppercase border-b border-indigo-200 bg-indigo-50 font-bold text-slate-500">Silver</th>
                        <th class="px-4 py-1 border-l border-b border-slate-200 bg-slate-100"></th>
                    </tr>
                `;

                // --- NYHET 1: SVARTLISTAN FÖR NAMN ---
                // Fyll på med namn som INTE får matchas. Skriv dem med små bokstäver.
                const BLACKLIST = [
                    "nilsson, bo",
                    "karlsson, johan",
                    "svensson, rolf",
                    "johansson, bo",
                    "andersson, lars" // Exempel: Lägg till fler om du upptäcker namnkrockar
                ];

                function createNameKey(str) {
                    if (!str || str.toLowerCase() === 'okänd' || str === 'undefined') return "";
                    let lower = str.toLowerCase().trim();
                    if (BLACKLIST.some(badName => lower.includes(badName))) {
                        return "blocked_" + Math.random();
                    }
                    return lower.replace(/,/g, ' ').split(/\s+/).filter(x=>x).sort().join('');
                }

                function getSmartChampion(seasonStr) {
                    let startYear = String(seasonStr).substring(0, 4);
                    for (let key of Object.keys(SEASON_CHAMPIONS)) {
                        if (key.startsWith(startYear)) return SEASON_CHAMPIONS[key];
                    }
                    return "Okänd";
                }

                // 1. KARTLÄGG TRÄNARE
                let coachStats = {};
                if (DJUP.sasonger) {
                    Object.keys(DJUP.sasonger).forEach(sKey => {
                        let sInfo = DJUP.sasonger[sKey];
                        let season = String(sKey).replace(/\.0$/, '').trim(); 
                        let startYear = season.substring(0, 4); 
                        
                        let winnerRaw = "";
                        let runnerUpRaw = "";
                        let winnerClub = "";
                        
                        Object.keys(sInfo).forEach(k => {
                            let kLow = String(k).toLowerCase().trim();
                            if (kLow.includes('tranare_mast') || kLow.includes('tränare_mäst') || kLow.includes('tranare_vinn')) winnerRaw = String(sInfo[k] || "").trim();
                            if (kLow.includes('tranare_tva') || kLow.includes('tränare_två') || kLow.includes('tranare_forl')) runnerUpRaw = String(sInfo[k] || "").trim();
                            if (kLow === 'cupvinnare' || kLow.includes('vinnande_lag') || kLow === 'lag') winnerClub = String(sInfo[k] || "").trim();
                        });

                        if (!winnerClub || winnerClub.toLowerCase() === "okänd" || winnerClub === "undefined") {
                            winnerClub = getSmartChampion(startYear);
                        }

                        let wKey = createNameKey(winnerRaw);
                        if (wKey && !wKey.startsWith('blocked_')) {
                            if (!coachStats[wKey]) coachStats[wKey] = { name: formatName(winnerRaw), cGold: [], cSilver: [] };
                            coachStats[wKey].cGold.push({ year: season, club: winnerClub });
                        }
                        
                        let rKey = createNameKey(runnerUpRaw);
                        if (rKey && !rKey.startsWith('blocked_')) {
                            if (!coachStats[rKey]) coachStats[rKey] = { name: formatName(runnerUpRaw), cGold: [], cSilver: [] };
                            let runnerUpClub = "Okänd";
                            let finalMatch = null;
                            
                            if (typeof BASE_MATCHES !== 'undefined') {
                                finalMatch = Object.values(BASE_MATCHES).find(m => {
                                    if(!m || !m.sasong || !m.fas) return false;
                                    let mStartYear = String(m.sasong).substring(0, 4);
                                    let mFas = String(m.fas).toLowerCase().trim();
                                    return mStartYear === startYear && mFas.includes('final') && !mFas.includes('kvart') && !mFas.includes('semi');
                                });
                            }
                            
                            if (finalMatch) {
                                let h = String(finalMatch.hemma).trim();
                                let b = String(finalMatch.borta).trim();
                                let actualChamp = (winnerClub !== "Okänd") ? winnerClub : getSmartChampion(startYear);
                                
                                if (actualChamp) {
                                    if (h.toLowerCase() === actualChamp.toLowerCase()) runnerUpClub = b;
                                    else if (b.toLowerCase() === actualChamp.toLowerCase()) runnerUpClub = h;
                                    else runnerUpClub = `${h} eller ${b}`; 
                                } else {
                                    runnerUpClub = `${h} eller ${b}`;
                                }
                            }
                            coachStats[rKey].cSilver.push({ year: season, club: runnerUpClub });
                        }
                    });
                }

                // 2. KARTLÄGG SPELARE (MED KAPTENS-KOLL!)
                let playerMedals = {};
                Object.keys(DJUP.matcher).forEach(mid => {
                    let bm = BASE_MATCHES[mid];
                    if(!bm || !bm.fas.toLowerCase().includes('final') || bm.fas.toLowerCase().includes('kvart') || bm.fas.toLowerCase().includes('semi')) return;

                    let season = String(bm.sasong).replace(/\.0$/, '').trim();
                    let startYear = season.substring(0, 4);
                    let champion = getSmartChampion(startYear); 
                    let dm = DJUP.matcher[mid];

                    if(!dm || !dm.uppstallning) return;

                    // NYHET: Säker sökning i listan av säsonger från Excel
                    let capMastRaw = "";
                    let capTvaaRaw = "";
                    if (DJUP.sasonger) {
                        let sKeyMatch = Object.keys(DJUP.sasonger).find(k => String(k).startsWith(startYear));
                        
                        if (sKeyMatch) {
                            let sRow = DJUP.sasonger[sKeyMatch];
                            Object.keys(sRow).forEach(k => {
                                let kLow = String(k).toLowerCase().trim();
                                if (kLow === 'kapten' || kLow.includes('lagkapten_mast') || kLow === 'lagkapten') capMastRaw = String(sRow[k]).trim();
                                if (kLow === 'tvaa_kapten' || kLow.includes('lagkapten_tva') || kLow.includes('lagkapten_två')) capTvaaRaw = String(sRow[k]).trim();
                            });
                        }
                    }

                    dm.uppstallning.forEach(p => {
                        let pKey = createNameKey(p.namn);
                        if (!pKey || pKey.startsWith('blocked_')) return;

                        if (!playerMedals[pKey]) playerMedals[pKey] = { name: formatName(p.namn), gold: [], silver: [] };

                        let pTeam = getPlayerTeam(p.lag, bm);
                        let isCap = false;
                        
                        let teamSafe = String(pTeam || "").toLowerCase().trim();
                        let champSafe = String(champion || "").toLowerCase().trim();
                        
                        // 1. Kolla mot Säsongs-fliken
                        if (capMastRaw && createNameKey(capMastRaw) === pKey && teamSafe === champSafe) isCap = true;
                        if (capTvaaRaw && createNameKey(capTvaaRaw) === pKey && teamSafe !== champSafe) isCap = true;
                        
                        // 2. Fallback: Kolla om kapten-flagga finns direkt i laguppställningen
                        if (p.kapten && (String(p.kapten).toLowerCase() === 'ja' || String(p.kapten) === '1' || String(p.kapten).toLowerCase() === 'true')) isCap = true;
                        if (String(p.namn).toLowerCase().includes('(c)')) isCap = true;

                        if (pTeam === champion) {
                            playerMedals[pKey].gold.push({year: season, club: pTeam, kapten: isCap});
                        } else {
                            playerMedals[pKey].silver.push({year: season, club: pTeam || "Okänd", kapten: isCap});
                        }
                    });
                });

                // 3. SLÅ IHOP OCH HITTA DUBBLA ROLLER
                let dualRoles = [];
                Object.keys(coachStats).forEach(cKey => {
                    let cStats = coachStats[cKey];
                    let pStats = playerMedals[cKey]; 

                    if (pStats) {
                        let pGoldCount = pStats.gold.length;
                        let pSilverCount = pStats.silver.length;
                        let cGoldCount = cStats.cGold.length;
                        let cSilverCount = cStats.cSilver.length;

                        if ((pGoldCount > 0 || pSilverCount > 0) && (cGoldCount > 0 || cSilverCount > 0)) {
                            
                            let history = [];
                            
                            // NYHET: Formaterar texten så att kapten får ett snyggt, gyllene (c)
                            const formatMedal = (m) => {
                                let capBadge = m.kapten ? ` <span class="font-bold text-amber-500" title="Lagkapten">(c)</span>` : "";
                                return `${m.club} '${m.year.slice(-2)}${capBadge}`;
                            };

                            if (pGoldCount > 0) history.push(`<b>Spelare (Guld):</b> ${pStats.gold.map(formatMedal).join(', ')}`);
                            if (pSilverCount > 0) history.push(`<b>Spelare (Silver):</b> ${pStats.silver.map(formatMedal).join(', ')}`);
                            if (cGoldCount > 0) history.push(`<span class='text-indigo-600'><b>Tränare (Guld):</b> ${cStats.cGold.map(m=>m.club + " '" + m.year.slice(-2)).join(', ')}</span>`);
                            if (cSilverCount > 0) history.push(`<span class='text-indigo-400'><b>Tränare (Silver):</b> ${cStats.cSilver.map(m=>m.club + " '" + m.year.slice(-2)).join(', ')}</span>`);

                            dualRoles.push({
                                name: cStats.name,
                                pGold: pGoldCount, pSilver: pSilverCount,
                                cGold: cGoldCount, cSilver: cSilverCount,
                                totalScore: (pGoldCount*3) + (pSilverCount*1) + (cGoldCount*4) + (cSilverCount*2),
                                historyStr: history.join(' <span class="text-slate-300 mx-1">|</span> ')
                            });
                        }
                    }
                });

                dualRoles.sort((a,b) => b.totalScore - a.totalScore || a.name.localeCompare(b.name));

                bodyEl.innerHTML = dualRoles.map((r, i) => {
                    let safeName = escapeHtml(r.name);
                    return `<tr class="hover:bg-slate-50 border-b border-slate-50">
                        <td class="px-4 py-3 font-bold text-slate-400">${i+1}</td>
                        <td class="px-4 py-3 font-black text-slate-800 cursor-pointer hover:text-blue-600" onclick="openPlayerModal('${safeName}')">${r.name} 👔</td>
                        <td class="px-2 py-3 text-center border-l border-yellow-100 font-bold text-yellow-600 bg-yellow-50/50 text-lg">${r.pGold}</td>
                        <td class="px-2 py-3 text-center border-yellow-100 text-slate-400 font-bold bg-yellow-50/50">${r.pSilver}</td>
                        <td class="px-2 py-3 text-center border-l border-indigo-100 font-bold text-indigo-700 bg-indigo-50/50 text-lg">${r.cGold}</td>
                        <td class="px-2 py-3 text-center border-indigo-100 text-slate-400 font-bold bg-indigo-50/50">${r.cSilver}</td>
                        <td class="px-4 py-3 text-[11px] leading-relaxed text-slate-600">${r.historyStr}</td>
                    </tr>`;
                }).join('');
                
                if (dualRoles.length === 0) {
                    bodyEl.innerHTML = `<tr><td colspan="7" class="px-4 py-6 text-center text-slate-500 italic">Inga matchningar hittades.</td></tr>`;
                }
            }
            else if (cat === 'comeback_kings') {
                headEl.innerHTML = `
                    <tr>
                        <th class="px-4 py-3 border-b border-slate-200 bg-slate-100 w-10">#</th>
                        <th class="px-4 py-3 border-b border-slate-200 bg-slate-100">Säsong (Mästare)</th>
                        <th class="px-4 py-3 text-center border-l border-b border-rose-200 bg-rose-50 text-rose-800">Största Underläge</th>
                        <th class="px-4 py-3 text-center border-l border-b border-emerald-200 bg-emerald-50 text-emerald-800">Slutresultat</th>
                        <th class="px-4 py-3 border-l border-b border-slate-200 bg-slate-100">Matchutveckling (Minut för minut)</th>
                    </tr>
                `;

                let comebacks = [];

                // Hjälpfunktion för att hämta mästaren säkert
                function getSmartChampion(seasonStr) {
                    let startYear = String(seasonStr).substring(0, 4);
                    for (let key of Object.keys(SEASON_CHAMPIONS)) {
                        if (key.startsWith(startYear)) return SEASON_CHAMPIONS[key];
                    }
                    return "Okänd";
                }

                Object.keys(DJUP.matcher).forEach(mid => {
                    let bm = BASE_MATCHES[mid];
                    // Filtrera: Bara finaler
                    if(!bm || !bm.fas.toLowerCase().includes('final') || bm.fas.toLowerCase().includes('kvart') || bm.fas.toLowerCase().includes('semi')) return;

                    let season = String(bm.sasong).replace(/\.0$/, '').trim();
                    let startYear = season.substring(0, 4);
                    let champion = getSmartChampion(startYear);
                    if (champion === "Okänd") return;

                    let dm = DJUP.matcher[mid];
                    if (!dm.mal || dm.mal.length === 0) return;

                    let isHomeChamp = (String(bm.hemma).trim().toLowerCase() === champion.toLowerCase());
                    let oppClub = isHomeChamp ? bm.borta : bm.hemma;
                    
                    let homeScore = 0;
                    let awayScore = 0;
                    let maxDeficit = 0;
                    let goalSeq = [];

                    dm.mal.forEach(g => {
                        let info = (g.info || "").toLowerCase();
                        let innebord = (g.innebord || "").toLowerCase();
                        
                        // Straffsparksläggningar räknas inte in i den löpande matchutvecklingen här
                        if (info.includes('straffläggning') || innebord.includes('straffläggning')) return;

                        let isOwnGoal = g.skytt.toLowerCase().includes('självmål');
                        
                        // Lista ut vilket lag som fick målet
                        let scoredForHome = false;
                        let teamLag = parseInt(g.lag);
                        
                        if (teamLag === 1) {
                            scoredForHome = true;
                        } else if (teamLag === 2) {
                            scoredForHome = false;
                        } else {
                            // Fallback: Sök på spelaren
                            let pTeam = "";
                            let pLineup = dm.uppstallning.find(p => p.namn === g.skytt);
                            if (pLineup) pTeam = getPlayerTeam(pLineup.lag, bm);
                            
                            if (pTeam && String(bm.hemma).trim().toLowerCase() === pTeam.toLowerCase()) {
                                scoredForHome = true;
                            }
                        }

                        // Justera om det är ett självmål (då får motståndaren poängen)
                        if (isOwnGoal) scoredForHome = !scoredForHome;

                        if (scoredForHome) homeScore++;
                        else awayScore++;

                        // Beräkna mästarens underläge vid detta specifika mål
                        let curDeficit = isHomeChamp ? (awayScore - homeScore) : (homeScore - awayScore);
                        if (curDeficit > maxDeficit) maxDeficit = curDeficit;

                        let displayMin = g.minut ? g.minut + "'" : "?'";
                        
                        // Färgkoda minut-loggen baserat på ställningen för mästaren
                        let badgeColor = "bg-slate-100 text-slate-600";
                        if (curDeficit > 0) badgeColor = "bg-rose-100 text-rose-700 font-bold";
                        else if (curDeficit < 0) badgeColor = "bg-emerald-100 text-emerald-700";

                        goalSeq.push(`<span class="px-2 py-1 rounded text-xs ${badgeColor}" title="Mål av ${escapeHtml(g.skytt)}">${displayMin} (${homeScore}-${awayScore})</span>`);
                    });

                    // Spara endast de matcher där mästaren vid något tillfälle legat under (maxDeficit > 0)
                    if (maxDeficit > 0) {
                        comebacks.push({
                            season: season,
                            champion: champion,
                            opponent: oppClub,
                            deficit: maxDeficit,
                            finalScore: `${homeScore}-${awayScore}`,
                            sequence: goalSeq.join(' <span class="text-slate-300">➔</span> ')
                        });
                    }
                });

                // Sortera: Först de som vänt störst underläge, sedan de nyaste säsongerna
                comebacks.sort((a, b) => b.deficit - a.deficit || parseInt(b.season.substring(0,4)) - parseInt(a.season.substring(0,4)));

                bodyEl.innerHTML = comebacks.map((r, i) => {
                    return `<tr class="hover:bg-slate-50 border-b border-slate-50">
                        <td class="px-4 py-3 font-bold text-slate-400">${i+1}</td>
                        <td class="px-4 py-3 font-bold text-slate-800">
                            ${r.champion} <span class="text-xs text-slate-500 font-normal block">Besegrade ${r.opponent} (${r.season})</span>
                        </td>
                        <td class="px-4 py-3 text-center border-l border-rose-100 font-black text-rose-600 text-lg bg-rose-50/30">-${r.deficit} mål</td>
                        <td class="px-4 py-3 text-center border-l border-emerald-100 font-bold text-emerald-700 bg-emerald-50/30">${r.finalScore}</td>
                        <td class="px-4 py-3 border-l border-slate-100 leading-relaxed">${r.sequence}</td>
                    </tr>`;
                }).join('');
                
                if (comebacks.length === 0) {
                    bodyEl.innerHTML = `<tr><td colspan="5" class="px-4 py-6 text-center text-slate-500 italic">Inga vändningar hittades. (Mästarna tog antingen ledningen och höll den, eller vann på straffar efter 0-0).</td></tr>`;
                }
            }
            else if (cat === 'age_gap') {
                headEl.innerHTML = `
                    <tr>
                        <th class="px-4 py-3 border-b border-slate-200 bg-slate-100 w-10">#</th>
                        <th class="px-4 py-3 border-b border-slate-200 bg-slate-100">Säsong (Final)</th>
                        <th class="px-4 py-3 text-center border-l border-b border-yellow-200 bg-yellow-50 text-yellow-800">Mästarnas Snittålder</th>
                        <th class="px-4 py-3 text-center border-l border-b border-slate-200 bg-slate-50 text-slate-600">Tvåornas Snittålder</th>
                        <th class="px-4 py-3 text-center border-l border-b border-indigo-200 bg-indigo-50 text-indigo-800">Åldersgap</th>
                        <th class="px-4 py-3 border-l border-b border-slate-200 bg-slate-100">Slutsats (Startelvor)</th>
                    </tr>
                `;

                let ageGaps = [];

                function getSmartChampion(seasonStr) {
                    let startYear = String(seasonStr).substring(0, 4);
                    for (let key of Object.keys(SEASON_CHAMPIONS)) {
                        if (key.startsWith(startYear)) return SEASON_CHAMPIONS[key];
                    }
                    return "Okänd";
                }

                Object.keys(DJUP.matcher).forEach(mid => {
                    let bm = BASE_MATCHES[mid];
                    if(!bm || !bm.fas.toLowerCase().includes('final') || bm.fas.toLowerCase().includes('kvart') || bm.fas.toLowerCase().includes('semi')) return;

                    let season = String(bm.sasong).replace(/\.0$/, '').trim();
                    let startYear = season.substring(0, 4);
                    let matchYear = parseInt(startYear);
                    if (isNaN(matchYear)) return;

                    let champion = getSmartChampion(startYear);
                    if (champion === "Okänd") return;

                    let dm = DJUP.matcher[mid];
                    if (!dm.uppstallning || dm.uppstallning.length === 0) return;

                    let champAges = [];
                    let runnerAges = [];
                    let runnerClub = "Okänd";

                    dm.uppstallning.forEach(p => {
                        let isStarter = (parseInt(p.pos) <= 11);
                        if (!isStarter) return; // Analysera endast startelvan (Rutin från start)

                        let pTeam = getPlayerTeam(p.lag, bm);
                        if (pTeam !== champion && runnerClub === "Okänd") {
                            runnerClub = pTeam || (bm.hemma === champion ? bm.borta : bm.hemma);
                        }

                        // Leta upp födelseår
                        let birthYear = null;
                        if (DJUP.spelare && DJUP.spelare[p.namn]) {
                            let sp = DJUP.spelare[p.namn];
                            let birthStr = String(sp.fodd || sp.Född || sp.fodelsedatum || sp.Födelsedatum || sp.fodelsear || sp.Födelseår || "").trim();
                            let m = birthStr.match(/^(\d{4})/);
                            if (m) birthYear = parseInt(m[1]);
                        }

                        // Beräkna ålder på matchåret (Rimlighetskoll 15-50 år)
                        if (birthYear) {
                            let age = matchYear - birthYear;
                            if (age >= 15 && age <= 50) { 
                                if (pTeam === champion) champAges.push(age);
                                else runnerAges.push(age);
                            }
                        }
                    });

                    // Vi kräver att vi har födelsedata på minst 7 spelare i varje lag för att snittet ska bli statistiskt tillförlitligt
                    if (champAges.length >= 7 && runnerAges.length >= 7) { 
                        let champAvg = champAges.reduce((a, b) => a + b, 0) / champAges.length;
                        let runnerAvg = runnerAges.reduce((a, b) => a + b, 0) / runnerAges.length;
                        let diff = champAvg - runnerAvg; // Plusvärde = Mästaren var äldst

                        ageGaps.push({
                            season: season,
                            champion: champion,
                            runnerUp: runnerClub,
                            champAvg: champAvg,
                            runnerAvg: runnerAvg,
                            diff: diff
                        });
                    }
                });

                // Sortera: Matcherna med STÖRST åldersgap (oavsett vem som var äldst) hamnar överst
                ageGaps.sort((a, b) => Math.abs(b.diff) - Math.abs(a.diff)); 

                bodyEl.innerHTML = ageGaps.map((r, i) => {
                    let diffAbs = Math.abs(r.diff).toFixed(1);
                    
                    let conclusion = "";
                    let badgeClass = "";
                    
                    // Färgkoda slutsatsen
                    if (r.diff > 1.5) {
                        conclusion = "Rutin segrade (Mästarna >1.5 år äldre)";
                        badgeClass = "bg-blue-100 text-blue-800 border border-blue-200";
                    } else if (r.diff < -1.5) {
                        conclusion = "Ungdom segrade (Mästarna >1.5 år yngre)";
                        badgeClass = "bg-emerald-100 text-emerald-800 border border-emerald-200";
                    } else if (r.diff > 0) {
                        conclusion = "Jämnt (Mästarna marginellt äldre)";
                        badgeClass = "bg-slate-100 text-slate-600 border border-slate-200";
                    } else {
                        conclusion = "Jämnt (Mästarna marginellt yngre)";
                        badgeClass = "bg-slate-100 text-slate-600 border border-slate-200";
                    }

                    return `<tr class="hover:bg-slate-50 border-b border-slate-50">
                        <td class="px-4 py-3 font-bold text-slate-400">${i+1}</td>
                        <td class="px-4 py-3 font-bold text-slate-800">${r.season}</td>
                        <td class="px-4 py-3 text-center border-l border-yellow-100 font-bold text-yellow-700 bg-yellow-50/50">${r.champAvg.toFixed(1)} år <span class="block text-[10px] text-yellow-600/70 font-normal uppercase tracking-wider mt-0.5">${r.champion}</span></td>
                        <td class="px-4 py-3 text-center border-l border-slate-100 font-bold text-slate-600">${r.runnerAvg.toFixed(1)} år <span class="block text-[10px] text-slate-400 font-normal uppercase tracking-wider mt-0.5">${r.runnerUp}</span></td>
                        <td class="px-4 py-3 text-center border-l border-indigo-100 font-black text-indigo-600 bg-indigo-50/30 text-lg">${diffAbs} år</td>
                        <td class="px-4 py-3 border-l border-slate-100"><span class="px-2 py-1 rounded text-xs font-bold ${badgeClass}">${conclusion}</span></td>
                    </tr>`;
                }).join('');
                
                if (ageGaps.length === 0) {
                    bodyEl.innerHTML = `<tr><td colspan="6" class="px-4 py-6 text-center text-slate-500 italic">Kunde inte beräkna åldersgap. Saknas födelsedata för startelvorna.</td></tr>`;
                }
            }
            else if (cat === 'iron_men') {
                headEl.innerHTML = `
                    <tr>
                        <th class="px-4 py-3 border-b border-slate-200 bg-slate-100 w-10">#</th>
                        <th class="px-4 py-3 border-b border-slate-200 bg-slate-100">Namn</th>
                        <th class="px-4 py-3 text-center border-l border-b border-slate-200 bg-slate-50">Finaler Spelade</th>
                        <th class="px-4 py-3 text-center border-l border-b border-blue-200 bg-blue-50 text-blue-800">Totala Minuter</th>
                        <th class="px-4 py-3 text-center border-l border-b border-orange-200 bg-orange-50 text-orange-800">Förlängningar</th>
                        <th class="px-4 py-3 border-l border-b border-slate-200 bg-slate-100">
                            <div class="flex items-center gap-2">
                                Detaljer (Säsonger & Minuter)
                                <button onclick="document.getElementById('iron-legend').classList.toggle('hidden')" class="text-blue-500 hover:text-blue-700 font-bold text-xs bg-blue-100 px-2 py-0.5 rounded cursor-pointer">Förklaring ℹ️</button>
                            </div>
                        </th>
                    </tr>
                    <tr id="iron-legend" class="hidden bg-slate-800 text-white">
                        <td colspan="6" class="px-4 py-3 text-xs leading-relaxed">
                            <strong class="text-white block mb-2 border-b border-slate-600 pb-1">Förklaring av etiketter:</strong>
                            <div class="flex flex-wrap gap-4">
                                <div class="flex items-center gap-2"><span class="px-1.5 py-0.5 rounded text-[10px] font-bold text-white bg-blue-500 border border-blue-600 w-12 text-center">90' ✓</span> <span class="text-slate-300">Spelade hela matchen</span></div>
                                <div class="flex items-center gap-2"><span class="px-1.5 py-0.5 rounded text-[10px] font-bold text-white bg-orange-500 border border-orange-600 w-12 text-center">120' 🔥</span> <span class="text-slate-300">Hela matchen inkl. förlängning/Golden Goal</span></div>
                                <div class="flex items-center gap-2"><span class="px-1.5 py-0.5 rounded text-[10px] font-bold text-orange-700 bg-orange-100 border border-orange-300 w-12 text-center">105'</span> <span class="text-slate-300">Byttes in/ut under förlängning</span></div>
                                <div class="flex items-center gap-2"><span class="px-1.5 py-0.5 rounded text-[10px] font-bold text-slate-600 bg-slate-100 border border-slate-300 w-12 text-center">75'</span> <span class="text-slate-300">Byttes in/ut under ordinarie tid</span></div>
                            </div>
                        </td>
                    </tr>
                `;

                let ironStats = {};

                Object.keys(DJUP.matcher).forEach(mid => {
                    let bm = BASE_MATCHES[mid];
                    if(!bm || !bm.fas.toLowerCase().includes('final') || bm.fas.toLowerCase().includes('kvart') || bm.fas.toLowerCase().includes('semi')) return;

                    let dm = DJUP.matcher[mid];
                    if (!dm || !dm.uppstallning) return;
                    
                    let season = String(bm.sasong).replace(/\.0$/, '').trim();

                    // 1. SMART CHECK: Hitta matchens faktiska längd! (Löser Golden Goal automatiskt)
                    let maxMatchMin = 0;
                    dm.uppstallning.forEach(p => {
                        let m = parseInt(String(p.minuter || "").replace(/[^0-9]/g, '')) || 0;
                        if (m > maxMatchMin) maxMatchMin = m;
                    });
                    
                    // Fallback: En hel fotbollsmatch är minst 90 min. (Skyddar mot ofullständig data)
                    if (maxMatchMin > 0 && maxMatchMin < 90) maxMatchMin = 90; 

                    dm.uppstallning.forEach(p => {
                        let pMinStr = String(p.minuter || "").replace(/[^0-9]/g, '');
                        let pMinVal = parseInt(pMinStr) || 0;
                        
                        if (pMinVal === 0) return; 

                        let pName = formatName(p.namn);
                        if (!pName || pName.toLowerCase() === 'okänd') return;

                        if (!ironStats[pName]) {
                            ironStats[pName] = { name: pName, totalMins: 0, finalsPlayed: 0, extraTimeFinals: 0, fullMatches: 0, details: [] };
                        }

                        ironStats[pName].totalMins += pMinVal;
                        ironStats[pName].finalsPlayed += 1;
                        
                        // Kolla om spelaren körde hela matchen!
                        let playedFullMatch = (pMinVal === maxMatchMin);
                        if (playedFullMatch) ironStats[pName].fullMatches += 1;

                        // Har spelaren spelat över 90 min (Förlängning/Golden Goal)
                        let isExtraTime = (pMinVal > 90);
                        if (isExtraTime) ironStats[pName].extraTimeFinals += 1;

                        // 2. DESIGN AV BADGES
                        let badgeStyle = "";
                        let icon = "";
                        let tooltip = "";
                        
                        if (playedFullMatch && isExtraTime) {
                            badgeStyle = "text-white bg-orange-500 border-orange-600 shadow-sm"; // Solid orange
                            icon = "🔥"; 
                            tooltip = "Spelade hela matchen (inkl. Förlängning/Golden Goal)";
                        } else if (playedFullMatch) {
                            badgeStyle = "text-white bg-blue-500 border-blue-600 shadow-sm"; // Solid blå
                            icon = "✓";
                            tooltip = "Spelade hela matchen";
                        } else if (isExtraTime) {
                            badgeStyle = "text-orange-700 bg-orange-100 border-orange-300"; // Ljus orange
                            tooltip = "Byttes in/ut under förlängningen";
                        } else {
                            badgeStyle = "text-slate-600 bg-slate-100 border-slate-300"; // Ljus grå
                            tooltip = "Byttes in/ut under ordinarie tid";
                        }

                        ironStats[pName].details.push(`<span title="${tooltip}" class="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold border ${badgeStyle} mr-1 mb-1 cursor-help">${season}: ${pMinVal}' ${icon}</span>`);
                    });
                });

                let ironArr = Object.values(ironStats);
                
                // Sortera: 1. Minuter, 2. Flest förlängningar, 3. Flest HELA matcher
                ironArr.sort((a,b) => b.totalMins - a.totalMins || b.extraTimeFinals - a.extraTimeFinals || b.fullMatches - a.fullMatches || a.name.localeCompare(b.name));

                bodyEl.innerHTML = ironArr.slice(0, 50).map((r, i) => { 
                    let safeName = escapeHtml(r.name);
                    
                    let extraHtml = r.extraTimeFinals > 0 
                        ? `<span class="font-black text-orange-600 text-lg">${r.extraTimeFinals}</span>` 
                        : `<span class="text-slate-300">-</span>`;

                    return `<tr class="hover:bg-slate-50 border-b border-slate-50">
                        <td class="px-4 py-3 font-bold text-slate-400">${i+1}</td>
                        <td class="px-4 py-3 font-black text-slate-800 cursor-pointer hover:text-blue-600" onclick="openPlayerModal('${safeName}')">${r.name}</td>
                        <td class="px-4 py-3 text-center border-l border-slate-100 font-bold text-slate-600">${r.finalsPlayed} <span class="block text-[10px] text-slate-400 font-normal">(${r.fullMatches} hela)</span></td>
                        <td class="px-4 py-3 text-center border-l border-blue-100 font-black text-blue-700 bg-blue-50/50 text-lg">${r.totalMins}'</td>
                        <td class="px-4 py-3 text-center border-l border-orange-50 bg-orange-50/30">${extraHtml}</td>
                        <td class="px-4 py-2 border-l border-slate-100 max-w-md flex flex-wrap gap-1 items-center">${r.details.join('')}</td>
                    </tr>`;
                }).join('');
                
                if (ironArr.length === 0) {
                    bodyEl.innerHTML = `<tr><td colspan="6" class="px-4 py-6 text-center text-slate-500 italic">Ingen minut-data hittades för finalerna.</td></tr>`;
                }
            }
            else if (cat === 'final_arenas') {
                headEl.innerHTML = `
                    <tr>
                        <th class="px-4 py-3 border-b border-slate-200 bg-slate-100 w-10">#</th>
                        <th class="px-4 py-3 border-b border-slate-200 bg-slate-100">Arena & Ort</th>
                        <th class="px-4 py-3 text-center border-l border-b border-slate-200 bg-slate-100 font-bold text-slate-800">Antal Finaler</th>
                        <th class="px-4 py-3 border-l border-b border-slate-200 bg-slate-50 text-slate-600">Säsonger (År)</th>
                    </tr>
                `;

                const ARENA_MERGE = {
                    "friends": "Strawberry Arena",
                    "swedbank": "Eleda Stadion"
                    // "tele2": "3Arena",
                    // "bravida": "Nordic Wellness Arena"
                    // Fyll på med fler vid behov
                };

                let arenas = {};
                let hasAnyMerged = false;

                Object.keys(BASE_MATCHES).forEach(mid => {
                    let bm = BASE_MATCHES[mid];
                    if(!bm || !bm.fas.toLowerCase().includes('final') || bm.fas.toLowerCase().includes('kvart') || bm.fas.toLowerCase().includes('semi')) return;

                    let arenaRaw = String(bm.arena || "Okänd arena").trim();
                    let ortRaw = String(bm.ort || "Okänd ort").trim();
                    let isMerged = false;
                    
                    // Applicera namnbytet
                    let matchedAlias = Object.keys(ARENA_MERGE).find(oldName => arenaRaw.toLowerCase().includes(oldName.toLowerCase()));
                    if (matchedAlias) {
                        arenaRaw = ARENA_MERGE[matchedAlias];
                        isMerged = true;
                        hasAnyMerged = true;
                    }
                    
                    // Bygg den unika ID-nyckeln UTAN stjärnan
                    let key = arenaRaw;
                    if (arenaRaw.toLowerCase() !== ortRaw.toLowerCase() && arenaRaw !== "Okänd arena") {
                        key += " i " + ortRaw;
                    } else if (arenaRaw === "Okänd arena" && ortRaw !== "Okänd ort") {
                        key = ortRaw;
                    }

                    // Registrera arenan i databasen om den är ny
                    if (!arenas[key]) arenas[key] = { name: key, count: 0, seasons: [], mergedFlag: false };
                    
                    // Om denna specifika match krävde en namnändring, flagga arenan för en stjärna
                    if (isMerged) arenas[key].mergedFlag = true;
                    
                    arenas[key].count++;
                    arenas[key].seasons.push(String(bm.sasong).replace(/\.0$/, ''));
                });

                let arenaArr = Object.values(arenas).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));

                let rowsHtml = arenaArr.map((r, i) => `
                    <tr class="hover:bg-slate-50 border-b border-slate-50">
                        <td class="px-4 py-3 font-bold text-slate-400">${i+1}</td>
                        <td class="px-4 py-3 font-black text-slate-800">
                            ${r.name}
                            ${r.mergedFlag ? ' <span class="text-rose-500 font-black ml-1" title="Sammanslagen / Namnbytt">*</span>' : ''}
                        </td>
                        <td class="px-4 py-3 text-center border-l border-slate-100 font-black text-indigo-600 bg-indigo-50/30 text-lg">${r.count}</td>
                        <td class="px-4 py-2 border-l border-slate-100 text-xs text-slate-500 max-w-md flex flex-wrap gap-1">
                            ${r.seasons.map(s => `<span class="bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded shadow-sm">${s}</span>`).join('')}
                        </td>
                    </tr>
                `).join('');
                
                if (hasAnyMerged) {
                    rowsHtml += `<tr><td colspan="4" class="px-4 py-3 text-xs text-slate-500 bg-slate-50 italic"><span class="text-rose-500 font-black">*</span> Arenans namn har uppdaterats eller slagits samman med ett historiskt namn.</td></tr>`;
                }
                
                bodyEl.innerHTML = rowsHtml;
            }
            
            else if (cat === 'all_results') {
                if (typeof window.res_mode === 'undefined') window.res_mode = 'full';
                if (typeof window.res_epoch === 'undefined') window.res_epoch = 'all';
                
                // BYGG DYNAMISK RULLISTA MED OPTGROUP (GRUPPERING)
                let epochOptions = `<option value="all">Totalt (Alla säsonger)</option>`;
                
                if (typeof window.EPOKER !== 'undefined') {
                    let allKeys = Object.keys(window.EPOKER);
                    
                    // Separera årtionden och egna epoker
                    let decades = allKeys.filter(k => k.includes('-talet'));
                    let customEpochs = allKeys.filter(k => !k.includes('-talet'));
                    
                    // Sortera årtionden (nyast överst) och epoker (kronologiskt/alfabetiskt)
                    decades.sort((a, b) => b.localeCompare(a));
                    customEpochs.sort();

                    if (customEpochs.length > 0) {
                        epochOptions += `<optgroup label="Egna Epoker">`;
                        customEpochs.forEach(ep => {
                            let isSelected = window.res_epoch === ep ? 'selected' : '';
                            epochOptions += `<option value="${ep}" ${isSelected}>${ep}</option>`;
                        });
                        epochOptions += `</optgroup>`;
                    }

                    if (decades.length > 0) {
                        epochOptions += `<optgroup label="Årtionden">`;
                        decades.forEach(ep => {
                            let isSelected = window.res_epoch === ep ? 'selected' : '';
                            epochOptions += `<option value="${ep}" ${isSelected}>${ep}</option>`;
                        });
                        epochOptions += `</optgroup>`;
                    }
                }

                headEl.innerHTML = `
                    <tr>
                        <th colspan="4" class="px-4 py-3 bg-slate-800 border-b border-slate-700 text-white rounded-tl-lg rounded-tr-lg">
                            <div class="flex flex-col lg:flex-row items-start lg:items-center gap-4 justify-between">
                                <span class="font-bold text-slate-200">Frekvens av matchresultat</span>
                                
                                <div class="flex flex-wrap gap-3 items-center">
                                    <!-- Rullista för Tidsperiod/Epok -->
                                    <select onchange="window.res_epoch = this.value; renderAnalys()" class="bg-slate-700 text-white text-xs font-bold p-1.5 rounded border border-slate-600 focus:ring-blue-500 focus:border-blue-500 cursor-pointer outline-none">
                                        ${epochOptions}
                                    </select>
                                    
                                    <div class="flex flex-wrap gap-3 text-xs font-normal bg-slate-700 p-1.5 rounded border border-slate-600">
                                        <label class="flex items-center gap-1 cursor-pointer hover:text-white">
                                            <input type="radio" name="res_time" value="full" ${window.res_mode === 'full' ? 'checked' : ''} onclick="window.res_mode = 'full'; renderAnalys()" class="text-blue-500 focus:ring-blue-500 cursor-pointer"> 
                                            Slutresultat
                                        </label>
                                        <label class="flex items-center gap-1 cursor-pointer hover:text-white">
                                            <input type="radio" name="res_time" value="90" ${window.res_mode === '90' ? 'checked' : ''} onclick="window.res_mode = '90'; renderAnalys()" class="text-blue-500 focus:ring-blue-500 cursor-pointer"> 
                                            90 min
                                        </label>
                                        <label class="flex items-center gap-1 cursor-pointer hover:text-white text-rose-300">
                                            <input type="radio" name="res_time" value="penalties" ${window.res_mode === 'penalties' ? 'checked' : ''} onclick="window.res_mode = 'penalties'; renderAnalys()" class="text-rose-500 focus:ring-rose-500 cursor-pointer"> 
                                            Straffläggning
                                        </label>
                                    </div>
                                </div>
                            </div>
                        </th>
                    </tr>
                    <tr>
                        <th class="px-4 py-3 border-b border-slate-200 bg-slate-100 w-24">Resultat</th>
                        <th class="px-4 py-3 text-center border-l border-b border-slate-200 bg-slate-100">Antal Matcher</th>
                        <th class="px-4 py-3 text-center border-l border-b border-slate-200 bg-slate-100">Andel (%)</th>
                        <th class="px-4 py-3 border-l border-b border-slate-200 bg-slate-50 text-slate-600">Historik (Första - Senaste)</th>
                    </tr>
                `;

                let resultsMap = {};
                let totalMatches = 0;

            // NYA ANALYVARIABLER
                let totalGoalsMap = {};
                let cleanSheets = 0;
                let doubleDigits = 0;
                let absoluteTotalGoals = 0; // <-- LÄGG TILL DENNA

                Object.keys(BASE_MATCHES).forEach(mid => {
                    let bm = BASE_MATCHES[mid];
                    if (!bm) return;

                    // --- EPOK-FILTRET ---
                    if (window.res_epoch !== 'all' && typeof window.EPOKER !== 'undefined' && window.EPOKER[window.res_epoch]) {
                        let validSeasons = window.EPOKER[window.res_epoch];
                        let seasonKey1 = String(bm.sasong).replace(/\.0$/, '').trim();
                        let seasonKey2 = String(bm.sasong).trim();
                        
                        // Kolla om matchens säsong ingår i vald epok
                        if (!validSeasons.includes(seasonKey1) && !validSeasons.includes(seasonKey2)) {
                            return; // Hoppa över matchen!
                        }
                    }

                    let hm = NaN, bm_score = NaN, forlh = 0, forlb = 0, sh = NaN, sb = NaN;

                    Object.keys(bm).forEach(k => {
                        let kLow = String(k).toLowerCase().trim();
                        if (kLow === 'hm' || kLow === 'h_mal') hm = parseInt(bm[k]);
                        else if (kLow === 'bm' || kLow === 'b_mal') bm_score = parseInt(bm[k]);
                        else if (kLow === 'fh' || kLow.includes('förl_h') || kLow.includes('forl_h')) forlh = parseInt(bm[k]) || 0;
                        else if (kLow === 'fb' || kLow.includes('förl_b') || kLow.includes('forl_b')) forlb = parseInt(bm[k]) || 0;
                        else if (kLow === 'sh' || kLow.includes('straff_h')) sh = parseInt(bm[k]);
                        else if (kLow === 'sb' || kLow.includes('straff_b')) sb = parseInt(bm[k]);
                    });

                    let finalH, finalB;

                    if (window.res_mode === 'penalties') {
                        if (isNaN(sh) || isNaN(sb)) return;
                        if (sh === 0 && sb === 0) return;
                        finalH = sh;
                        finalB = sb;
                    } else {
                        if (isNaN(hm) || isNaN(bm_score)) return;
                        if (window.res_mode === '90') {
                            finalH = hm;
                            finalB = bm_score;
                        } else {
                            finalH = hm + forlh;
                            finalB = bm_score + forlb;
                        }
                    }

                    let sumGoals = finalH + finalB;
                    absoluteTotalGoals += sumGoals; // <-- LÄGG TILL DENNA
                    if (!totalGoalsMap[sumGoals]) totalGoalsMap[sumGoals] = 0;
                    totalGoalsMap[sumGoals]++;

                    if (finalH === 0) cleanSheets++;
                    if (finalB === 0) cleanSheets++;
                    
                    if (finalH >= 10) doubleDigits++;
                    if (finalB >= 10) doubleDigits++;

                    let high = Math.max(finalH, finalB);
                    let low = Math.min(finalH, finalB);
                    let resKey = `${high}-${low}`;
                    
                    if (!resultsMap[resKey]) resultsMap[resKey] = { key: resKey, count: 0, seasons: [] };
                    
                    resultsMap[resKey].count++;
                    totalMatches++;

                    let matchYear = parseInt(String(bm.sasong).substring(0, 4));
                    if (!isNaN(matchYear)) {
                        resultsMap[resKey].seasons.push(matchYear);
                    }
                });

                let resArr = Object.values(resultsMap).sort((a, b) => b.count - a.count);

                let mainTableHtml = resArr.map((r) => {
                    let pct = ((r.count / totalMatches) * 100).toFixed(1);
                    let minS = Math.min(...r.seasons);
                    let maxS = Math.max(...r.seasons);
                    let seasonText = (isFinite(minS) && isFinite(maxS)) ? (minS === maxS ? `${minS}` : `${minS} - ${maxS}`) : "Okänt";
                    let barColor = window.res_mode === 'penalties' ? 'bg-rose-500' : 'bg-indigo-500';
                    let textColor = window.res_mode === 'penalties' ? 'text-rose-700' : 'text-indigo-700';

                    return `
                    <tr class="hover:bg-slate-50 border-b border-slate-50">
                        <td class="px-4 py-3 font-black ${textColor} text-lg">${r.key}</td>
                        <td class="px-4 py-3 text-center border-l border-slate-100 font-bold text-slate-800">${r.count}</td>
                        <td class="px-4 py-3 text-center border-l border-slate-100 font-bold text-slate-500">
                            <div class="flex items-center justify-between gap-2"><span>${pct}%</span><div class="w-20 h-2 bg-slate-200 rounded overflow-hidden flex-shrink-0"><div class="h-full ${barColor}" style="width: ${pct}%"></div></div></div>
                        </td>
                        <td class="px-4 py-3 border-l border-slate-100 font-bold text-slate-600">${seasonText}</td>
                    </tr>`;
                }).join('');
                
                if (resArr.length === 0) mainTableHtml = `<tr><td colspan="4" class="px-4 py-6 text-center text-slate-500 italic">Inga resultat hittades för den valda perioden.</td></tr>`;

            // --- BYGG UPP TILLÄGGSDATAN LÄNGST NER ---
                let tgArr = Object.keys(totalGoalsMap).map(Number).sort((a, b) => a - b);
                let tgHtml = tgArr.map(g => {
                    let pct = ((totalGoalsMap[g] / totalMatches) * 100).toFixed(1);
                    return `<tr class="border-b border-slate-50 hover:bg-slate-50"><td class="px-3 py-2 font-bold text-slate-700">${g} mål</td><td class="px-3 py-2 text-right font-bold text-indigo-600">${totalGoalsMap[g]} <span class="text-xs text-slate-400 font-normal ml-1">(${pct}%)</span></td></tr>`;
                }).join('');
                
                if (tgArr.length === 0) tgHtml = `<tr><td colspan="2" class="px-3 py-4 text-center text-slate-400 italic">Ingen data</td></tr>`;

                let extColor = window.res_mode === 'penalties' ? 'rose' : 'indigo';

                // Lägg denna rad precis INNAN let statsGrid = `...`
                // Beräkna målsnittet innan HTML-strängen byggs
                let avgGoals = totalMatches > 0 ? (absoluteTotalGoals / totalMatches).toFixed(2) : "0.00";
                
                let statsGrid = `
                <div class="p-6 bg-slate-50 border-t border-slate-200">
                    <h4 class="font-bold text-slate-700 mb-4 text-lg">Sammanfattande Matchstatistik <span class="text-sm font-normal text-slate-500 ml-2">(${totalMatches} matcher)</span></h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        
                        <!-- VÄNSTER SPALT: Tabellen -->
                        <div class="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
                            <div class="bg-slate-700 text-white px-4 py-2 font-bold text-sm">Fördelning: Totalt antal mål i matchen</div>
                            <div class="max-h-56 overflow-y-auto">
                                <table class="w-full text-sm text-left">
                                    <thead class="bg-slate-100 text-slate-500 sticky top-0"><tr><th class="px-3 py-2">Mål totalt</th><th class="px-3 py-2 text-right">Antal matcher</th></tr></thead>
                                    <tbody>${tgHtml}</tbody>
                                </table>
                            </div>
                        </div>
                        
                        <!-- HÖGER SPALT: KPI-Boxarna -->
                        <div class="flex flex-col gap-4">
                            
                            <!-- NY BOX: Målproduktion -->
                            <div class="bg-sky-50 rounded-lg border border-sky-100 p-4 shadow-sm flex items-center justify-between">
                                <div>
                                    <div class="text-sky-500 text-xs font-bold uppercase tracking-wider">Målproduktion</div>
                                    <div class="text-sky-900 font-black text-lg">Totalt antal mål</div>
                                    <div class="text-xs text-sky-600 mt-1">Snitt per vald period: <span class="font-bold">${avgGoals} mål</span></div>
                                </div>
                                <div class="text-3xl font-black text-sky-600">${absoluteTotalGoals} <span class="text-sm font-normal text-sky-500">st</span></div>
                            </div>

                            <!-- BEFINTLIG BOX: Defensiv styrka -->
                            <div class="bg-${typeof extColor !== 'undefined' ? extColor : 'indigo'}-50 rounded-lg border border-${typeof extColor !== 'undefined' ? extColor : 'indigo'}-100 p-4 shadow-sm flex items-center justify-between">
                                <div>
                                    <div class="text-${typeof extColor !== 'undefined' ? extColor : 'indigo'}-400 text-xs font-bold uppercase tracking-wider">Defensiv styrka</div>
                                    <div class="text-${typeof extColor !== 'undefined' ? extColor : 'indigo'}-900 font-black text-lg">Hållna nollor</div>
                                </div>
                                <div class="text-3xl font-black text-${typeof extColor !== 'undefined' ? extColor : 'indigo'}-600">${cleanSheets} <span class="text-sm font-normal text-${typeof extColor !== 'undefined' ? extColor : 'indigo'}-400">ggr</span></div>
                            </div>
                            
                            <!-- BEFINTLIG BOX: Offensiv kross -->
                            <div class="bg-amber-50 rounded-lg border border-amber-100 p-4 shadow-sm flex items-center justify-between">
                                <div>
                                    <div class="text-amber-500 text-xs font-bold uppercase tracking-wider">Offensiv kross</div>
                                    <div class="text-amber-900 font-black text-lg">Tvåsiffrigt antal mål</div>
                                    <div class="text-xs text-amber-600 mt-1">Ett lag gör ≥ 10 mål</div>
                                </div>
                                <div class="text-3xl font-black text-amber-600">${doubleDigits} <span class="text-sm font-normal text-amber-500">ggr</span></div>
                            </div>
                            
                        </div>
                    </div>
                </div>
                `;

                bodyEl.innerHTML = mainTableHtml;
                if (totalMatches > 0) {
                    bodyEl.insertAdjacentHTML('beforeend', `<tr><td colspan="4" class="p-0">${statsGrid}</td></tr>`);
                }
            }
        }
    </script>
</body>
</html>
"""

# ==========================================
# NYTT: BYGG EPOKER / ÅRTIONDEN FRÅN EXCEL
# ==========================================
print("Skapar tidsperioder (Epoker)...")
epoker_data = {}
try:
    all_seasons = [str(s).replace('.0', '').strip() for s in df_cup['Säsong'].dropna().unique() if str(s).strip() != '']
    sas_nr_to_name = {}
    if 'Säs_nr' in df_cup.columns and 'Säsong' in df_cup.columns:
        for _, row in df_cup.iterrows():
            s_nr = row.get('Säs_nr')
            s_name = row.get('Säsong')
            if pd.notna(s_nr) and pd.notna(s_name) and str(s_nr).strip() != '':
                try: sas_nr_to_name[int(float(str(s_nr).replace(',', '.')))] = str(s_name).replace('.0', '').strip()
                except: pass

    for s in all_seasons:
        year_str = "".join(filter(str.isdigit, s))[:4]
        if len(year_str) == 4:
            decade = year_str[:3] + "0-talet"
            if decade not in epoker_data: epoker_data[decade] = []
            epoker_data[decade].append(s)
            
    df_epochs = pd.read_excel(filnamn_excel, sheet_name="Epoker")
    df_epochs.columns = df_epochs.columns.str.strip() 
    c_period = next((c for c in df_epochs.columns if 'period' in c.lower() or 'epok' in c.lower()), df_epochs.columns[0])
    c_start = next((c for c in df_epochs.columns if 'första' in c.lower() or 'start' in c.lower()), df_epochs.columns[1])
    c_end = next((c for c in df_epochs.columns if 'sista' in c.lower() or 'slut' in c.lower()), df_epochs.columns[2])
    
    for _, row in df_epochs.iterrows():
        period_name = str(row.get(c_period, '')).strip()
        if not period_name or period_name == "nan": continue
        epoch_seasons = []
        
        s_val = str(row.get(c_start, '')).strip()
        e_val = str(row.get(c_end, '')).strip()
        if s_val == '' or s_val == 'nan': continue
        
        start_val = float(s_val.replace(',', '.'))
        end_val = float(e_val.replace(',', '.')) if e_val and e_val.lower() != 'senaste' and e_val != 'nan' else 9999
        
        if start_val < 200:
            for nr, name in sas_nr_to_name.items():
                if start_val <= nr <= end_val: epoch_seasons.append(name)
        else:
            for s in all_seasons:
                s_dig = "".join(filter(str.isdigit, str(s)))
                if s_dig:
                    s_yr = float(s_dig[:4])
                    if start_val <= s_yr <= end_val: epoch_seasons.append(s)
        
        if epoch_seasons: epoker_data[period_name] = list(set(epoch_seasons))
except Exception as e: 
    print(f"Hittade ingen flik 'Epoker' eller fick fel, hoppar över. ({e})")

epoker_json = json.dumps(epoker_data, ensure_ascii=False)

# ==========================================
# TRICKET: Smyger in 'EPOKER' bredvid 'BASE_MATCHES'
# Använder window.EPOKER för 100% matematisk stabilitet i JS!
# ==========================================
combined_json_str = f"{base_matches_json};\n        window.EPOKER = {epoker_json};"
final_html = html_template.replace("%%DJUP_DATA_JSON%%", djup_data_str).replace("%%BASE_MATCHES_JSON%%", combined_json_str)

with open(output_file, "w", encoding="utf-8") as f:
    f.write(final_html)

print(f"SUCCÉ! Filen '{output_file}' har skapats. Epoker och Allt annat är nu inlagt!")