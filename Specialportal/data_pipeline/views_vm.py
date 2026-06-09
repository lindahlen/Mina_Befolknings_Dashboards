import os
import sys
import json

# =========================================================
# 1. SETUP & SÖKVÄGAR
# =========================================================
try:
    current_folder = os.path.dirname(os.path.abspath(__file__))
    root_folder = os.path.dirname(current_folder)
    os.chdir(root_folder)
except NameError:
    pass

JSON_FILE = os.path.join("json_data", "vm_data.json")
OUTPUT_HTML = "VM_Dashboard.html"

# =========================================================
# 2. BYGG HTML-MALLEN
# =========================================================
def build_dashboard():
    if not os.path.exists(JSON_FILE):
        print("❌ Hittar inte vm_data.json. Kör bygg_vm_data.py först!")
        sys.exit(1)

    print(f"📖 Läser in data från {JSON_FILE}...")
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        json_str = f.read()

    print("⚙️ Genererar HTML...")
    
    # Vi använder en vanlig sträng och .replace() för att undvika måsvinge-krockar med JS/CSS
    html_template = """<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fotbolls-VM Historik</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
        .modal-backdrop { background-color: rgba(0, 0, 0, 0.5); backdrop-filter: blur(2px); }
    </style>
</head>
<body class="bg-slate-100 text-slate-800 font-sans min-h-screen">

    <!-- Header -->
    <header class="bg-blue-900 text-white shadow-md sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
            <h1 class="text-2xl font-bold tracking-tight">🏆 VM-Databasen</h1>
            <span class="text-xs text-blue-200">Offline-läge</span>
        </div>
        
        <nav class="max-w-7xl mx-auto px-4 flex space-x-1 overflow-x-auto no-scrollbar pb-2">
            <button onclick="switchTab('tab-turneringar')" class="tab-btn px-4 py-2 rounded-t-lg bg-white text-blue-900 font-semibold transition whitespace-nowrap">Turneringar</button>
            <button onclick="switchTab('tab-matcher')" class="tab-btn px-4 py-2 rounded-t-lg bg-blue-800 text-blue-200 hover:bg-blue-700 transition whitespace-nowrap">Alla Matcher</button>
            <button onclick="switchTab('tab-admin')" class="tab-btn px-4 py-2 rounded-t-lg bg-red-800 text-red-200 hover:bg-red-700 transition flex items-center gap-2 whitespace-nowrap">
                <span>⚠️ Admin</span>
                <span id="admin-badge" class="bg-red-500 text-white text-xs px-2 py-1 rounded-full hidden">0</span>
            </button>
        </nav>
    </header>

    <main class="max-w-7xl mx-auto px-4 py-6">
        
        <!-- FLIK 1: Turneringar -->
        <div id="tab-turneringar" class="tab-content">
            <h2 class="text-2xl font-bold mb-6 text-slate-700">Turneringar genom tiderna</h2>
            <div id="tournaments-grid" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                <!-- Genereras av JS -->
            </div>
        </div>

        <!-- FLIK 2: Matcher -->
        <div id="tab-matcher" class="tab-content hidden">
            <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                <h2 class="text-2xl font-bold text-slate-700">Sök Matcher</h2>
                <div class="flex flex-col sm:flex-row gap-2 w-full md:w-auto">
                    <select id="filter-year" class="p-2 border border-slate-300 rounded-lg bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500" onchange="renderMatches()">
                        <option value="all">Alla turneringar</option>
                    </select>
                    <input type="text" id="search-input" placeholder="Sök lag, arena, fas..." class="p-2 border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-full sm:w-64" onkeyup="renderMatches()">
                </div>
            </div>
            
            <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                <div class="max-h-[70vh] overflow-y-auto">
                    <table class="w-full text-left border-collapse">
                        <thead class="bg-slate-50 sticky top-0 border-b border-slate-200 z-10">
                            <tr>
                                <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Datum & Fas</th>
                                <th class="p-3 text-xs font-semibold text-slate-500 uppercase text-right">Hemmalag</th>
                                <th class="p-3 text-xs font-semibold text-slate-500 uppercase text-center">Res</th>
                                <th class="p-3 text-xs font-semibold text-slate-500 uppercase">Bortalag</th>
                            </tr>
                        </thead>
                        <tbody id="matches-list" class="divide-y divide-slate-100">
                            <!-- Genereras av JS -->
                        </tbody>
                    </table>
                </div>
            </div>
            <p id="matches-count" class="text-sm text-slate-500 mt-2 text-right"></p>
        </div>

        <!-- FLIK 3: Admin -->
        <div id="tab-admin" class="tab-content hidden">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold text-red-800">Databas-Felsökning</h2>
                <button onclick="renderAdminWarnings()" class="text-sm bg-slate-200 hover:bg-slate-300 px-3 py-1 rounded">Ladda om lista</button>
            </div>
            <div class="bg-white rounded-lg shadow-sm border border-red-200 p-6">
                <p class="text-sm text-slate-600 mb-4">Logiska fel och saknad data från Excel-filen.</p>
                <div id="admin-list-container" class="space-y-2 max-h-[60vh] overflow-y-auto pr-2"></div>
            </div>
        </div>

    </main>

    <!-- MATCH MODAL -->
    <div id="match-modal" class="fixed inset-0 z-50 hidden modal-backdrop flex items-center justify-center p-4">
        <div class="bg-slate-100 rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden relative">
            
            <!-- Modal Header -->
            <div class="bg-blue-900 text-white p-4 flex justify-between items-center">
                <div>
                    <span id="modal-phase" class="text-xs font-bold uppercase tracking-wider text-blue-200">Fas</span>
                    <h3 class="text-lg font-bold" id="modal-title">Match Info</h3>
                </div>
                <button onclick="closeModal()" class="text-white hover:text-blue-200 p-2 text-2xl leading-none">&times;</button>
            </div>
            
            <!-- Modal Content (Scrollable) -->
            <div class="p-0 overflow-y-auto flex-1">
                
                <!-- Scoreboard -->
                <div class="bg-white p-6 border-b border-slate-200 text-center">
                    <div class="text-sm text-slate-500 mb-4"><span id="modal-date"></span> &bull; <span id="modal-arena"></span>, <span id="modal-city"></span> &bull; Publik: <span id="modal-attendance"></span></div>
                    
                    <div class="flex justify-center items-center gap-6 md:gap-12">
                        <div class="flex-1 text-right text-2xl md:text-3xl font-bold truncate" id="modal-home">Hemmalag</div>
                        <div class="text-4xl md:text-5xl font-black text-blue-900 bg-slate-50 px-4 py-2 rounded-lg border border-slate-200 shadow-inner" id="modal-score">0 - 0</div>
                        <div class="flex-1 text-left text-2xl md:text-3xl font-bold truncate" id="modal-away">Bortalag</div>
                    </div>
                    
                    <div id="modal-score-details" class="text-sm text-slate-500 mt-3 font-medium"></div>
                </div>

                <!-- Match Events (Goals & Cards) -->
                <div class="p-6 bg-slate-50">
                    <h4 class="text-sm font-bold uppercase text-slate-400 mb-3 text-center tracking-widest">Matchhändelser</h4>
                    <div class="max-w-xl mx-auto bg-white border border-slate-200 rounded-lg shadow-sm p-4" id="modal-events">
                        <!-- Genereras av JS -->
                    </div>
                </div>

                <!-- Lineups -->
                <div class="p-6 bg-white border-t border-slate-200">
                    <h4 class="text-sm font-bold uppercase text-slate-400 mb-4 text-center tracking-widest">Laguppställningar</h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                        
                        <!-- Home Lineup -->
                        <div>
                            <div class="font-bold text-lg mb-3 border-b-2 border-blue-900 pb-1" id="modal-lineup-home-title">Hemma</div>
                            <ul id="modal-lineup-home" class="space-y-1 text-sm"></ul>
                            <div class="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-500">
                                <strong>Förbundskapten:</strong> <span id="modal-coach-home"></span>
                            </div>
                        </div>
                        
                        <!-- Away Lineup -->
                        <div>
                            <div class="font-bold text-lg mb-3 border-b-2 border-blue-900 pb-1" id="modal-lineup-away-title">Borta</div>
                            <ul id="modal-lineup-away" class="space-y-1 text-sm"></ul>
                            <div class="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-500">
                                <strong>Förbundskapten:</strong> <span id="modal-coach-away"></span>
                            </div>
                        </div>

                    </div>
                </div>

            </div>
        </div>
    </div>

    <!-- JSON DATA INJECTION -->
    <script>
        // Databasen injiceras säkert via Python
        const db = __JSON_DATA_PLACEHOLDER__;
        
        // --- HJÄLPFUNKTIONER ---
        const safeText = (text) => text === null || text === undefined ? "" : text;
        const formatScore = (m) => m.score.home_total !== null ? `${m.score.home_total} - ${m.score.away_total}` : 'Ej spelad';

        // --- TAB LOGIC ---
        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('bg-white', 'text-blue-900', 'font-semibold');
                btn.classList.add('bg-blue-800', 'text-blue-200');
                if(btn.innerText.includes('Admin')) {
                    btn.classList.remove('bg-red-800', 'text-red-200');
                    btn.classList.add('bg-red-800', 'text-red-200');
                }
            });
            
            document.getElementById(tabId).classList.remove('hidden');
            
            const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(btn => btn.getAttribute('onclick').includes(tabId));
            if(activeBtn && !tabId.includes('admin')) {
                activeBtn.classList.remove('bg-blue-800', 'text-blue-200');
                activeBtn.classList.add('bg-white', 'text-blue-900', 'font-semibold');
            } else if (activeBtn && tabId.includes('admin')) {
                 activeBtn.classList.remove('bg-red-800', 'text-red-200');
                 activeBtn.classList.add('bg-white', 'text-red-900', 'font-semibold');
            }
        }

        // --- RENDERING: TURNERINGAR ---
        function renderTournaments() {
            const container = document.getElementById('tournaments-grid');
            const years = Object.keys(db.tournaments).sort((a, b) => b - a); // Nyast först
            
            let html = '';
            years.forEach(year => {
                const t = db.tournaments[year];
                html += `
                    <div onclick="filterByYear('${year}')" class="bg-white p-5 rounded-xl shadow-sm border border-slate-200 cursor-pointer hover:shadow-md hover:border-blue-300 transition group relative overflow-hidden">
                        <div class="absolute top-0 right-0 bg-slate-100 text-slate-400 text-xs px-2 py-1 rounded-bl-lg">${t.matches.length} matcher</div>
                        <h3 class="text-3xl font-black text-blue-900 mb-1 group-hover:text-blue-600 transition">${year}</h3>
                        <p class="text-sm font-medium text-slate-500 mb-3">${t.host}</p>
                        <div class="inline-block bg-yellow-50 border border-yellow-200 text-yellow-800 text-xs px-2 py-1 rounded font-bold">
                            🏆 ${t.winner || 'Okänd'}
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
        }

        function filterByYear(year) {
            document.getElementById('filter-year').value = year;
            switchTab('tab-matcher');
            renderMatches();
        }

        function populateYearFilter() {
            const select = document.getElementById('filter-year');
            const years = Object.keys(db.tournaments).sort((a, b) => b - a);
            years.forEach(year => {
                const opt = document.createElement('option');
                opt.value = year;
                opt.innerText = year;
                select.appendChild(opt);
            });
        }

        // --- RENDERING: MATCHER ---
        function renderMatches() {
            const container = document.getElementById('matches-list');
            const counter = document.getElementById('matches-count');
            const filterYear = document.getElementById('filter-year').value;
            const searchTerm = document.getElementById('search-input').value.toLowerCase();
            
            let html = '';
            let count = 0;
            
            // Konvertera matches objekt till array och sortera på datum
            let matchArray = Object.values(db.matches).sort((a, b) => new Date(b.date) - new Date(a.date));

            matchArray.forEach(m => {
                const matchYear = m.date.substring(0, 4);
                
                // Filtrering
                if (filterYear !== 'all' && matchYear !== filterYear) return;
                
                const searchString = `${m.home_team} ${m.away_team} ${m.arena} ${m.city} ${m.phase} ${matchYear}`.toLowerCase();
                if (searchTerm && !searchString.includes(searchTerm)) return;

                count++;
                const isPlayed = m.score.home_total !== null;
                const scoreClass = isPlayed ? "font-bold text-slate-800 bg-slate-100 px-3 py-1 rounded border border-slate-200" : "text-slate-400 text-xs";
                
                html += `
                    <tr onclick="openMatchModal('${m.id}')" class="hover:bg-blue-50 cursor-pointer transition group">
                        <td class="p-3 border-t border-slate-100">
                            <div class="text-xs font-semibold text-blue-900">${m.phase}</div>
                            <div class="text-xs text-slate-500">${m.date}</div>
                        </td>
                        <td class="p-3 border-t border-slate-100 text-right font-medium group-hover:text-blue-700">${m.home_team}</td>
                        <td class="p-3 border-t border-slate-100 text-center">
                            <span class="${scoreClass}">${formatScore(m)}</span>
                        </td>
                        <td class="p-3 border-t border-slate-100 font-medium group-hover:text-blue-700">${m.away_team}</td>
                    </tr>
                `;
            });

            container.innerHTML = html;
            counter.innerText = `Visar ${count} matcher`;
        }

        // --- RENDERING: MODAL (Detaljer) ---
        function openMatchModal(matchId) {
            const m = db.matches[matchId];
            if (!m) return;

            // Headers & Basic info
            document.getElementById('modal-phase').innerText = `${m.phase} - ${m.date.substring(0,4)}`;
            document.getElementById('modal-date').innerText = m.date;
            document.getElementById('modal-arena').innerText = safeText(m.arena);
            document.getElementById('modal-city').innerText = safeText(m.city);
            document.getElementById('modal-attendance').innerText = m.attendance ? m.attendance.toLocaleString('sv-SE') : 'Okänt';
            document.getElementById('modal-title').innerText = `Match-ID: ${m.id}`;

            document.getElementById('modal-home').innerText = m.home_team;
            document.getElementById('modal-away').innerText = m.away_team;
            document.getElementById('modal-score').innerText = formatScore(m);

            // Score details (Halftime, Extra Time, Penalties)
            let detailsHtml = '';
            if (m.score.home_ht !== null) detailsHtml += `HT: ${m.score.home_ht}-${m.score.away_ht}`;
            if (m.score.home_et !== null) detailsHtml += ` &bull; Efter förlängning: ${m.score.home_et}-${m.score.away_et}`;
            if (m.score.home_pen !== null) detailsHtml += ` &bull; Straffar: ${m.score.home_pen}-${m.score.away_pen}`;
            document.getElementById('modal-score-details').innerHTML = detailsHtml;

            // Events (Goals & Cards)
            const eventsContainer = document.getElementById('modal-events');
            let eventsArray = [];
            
            m.events.goals.forEach(g => eventsArray.push({min: parseInt(g.minute) || 999, raw_min: g.minute, text: `⚽ ${g.player} (${g.team}) ${g.type !== 'Spelmål' && g.type !== 'Okänt' ? ' - '+g.type : ''}`, team: g.team}));
            m.events.cards.forEach(c => eventsArray.push({min: parseInt(c.minute) || 999, raw_min: c.minute, text: `🟥 ${c.player} (Utvisning)`}));
            
            eventsArray.sort((a,b) => a.min - b.min);
            
            if (eventsArray.length > 0) {
                let evHtml = '<ul class="space-y-2 text-sm">';
                eventsArray.forEach(ev => {
                    const isHome = ev.team === m.home_team;
                    const alignClass = ev.team ? (isHome ? 'text-left' : 'text-right') : 'text-center text-slate-500';
                    evHtml += `<li class="${alignClass} border-b border-slate-100 pb-1 last:border-0"><span class="font-bold text-slate-400 text-xs w-8 inline-block">${ev.raw_min}'</span> ${ev.text}</li>`;
                });
                evHtml += '</ul>';
                eventsContainer.innerHTML = evHtml;
            } else {
                eventsContainer.innerHTML = '<p class="text-center text-slate-400 text-sm italic">Inga specifika mål- eller kortuppgifter registrerade.</p>';
            }

            // Lineups & Coaches
            const renderLineup = (teamData, elementId) => {
                const el = document.getElementById(elementId);
                if (!teamData || teamData.length === 0) {
                    el.innerHTML = '<li class="text-slate-400 italic">Laguppställning saknas</li>';
                    return;
                }
                
                // Sortera: Startspelare först (baserat på minut = 0 eller status = 'Start')
                teamData.sort((a, b) => {
                    const minA = parseInt(a.minute) || 0;
                    const minB = parseInt(b.minute) || 0;
                    return minA - minB;
                });

                let lHtml = '';
                teamData.forEach(p => {
                    const isSub = p.status.toLowerCase().includes('inbytt') || p.minute > 0;
                    const icon = isSub ? '<span class="text-green-500 font-bold ml-1 text-xs" title="Inbytt">↑</span>' : '';
                    const minText = p.minute > 0 ? `<span class="text-xs text-slate-400 ml-1">(${p.minute}')</span>` : '';
                    const nrText = p.shirt_nr ? `<span class="inline-block w-6 font-bold text-slate-400 text-xs">${p.shirt_nr}.</span>` : `<span class="inline-block w-6 text-slate-300">-</span>`;
                    
                    lHtml += `<li class="py-1 border-b border-slate-50 last:border-0 flex items-center">
                                ${nrText} 
                                <span class="${isSub ? 'text-slate-600' : 'font-medium'}">${p.name}</span>
                                ${icon} ${minText}
                              </li>`;
                });
                el.innerHTML = lHtml;
            };

            document.getElementById('modal-lineup-home-title').innerText = m.home_team;
            document.getElementById('modal-lineup-away-title').innerText = m.away_team;
            
            renderLineup(m.events.lineups.home, 'modal-lineup-home');
            renderLineup(m.events.lineups.away, 'modal-lineup-away');

            document.getElementById('modal-coach-home').innerText = safeText(m.coaches.home);
            document.getElementById('modal-coach-away').innerText = safeText(m.coaches.away);

            // Visa modal
            document.getElementById('match-modal').classList.remove('hidden');
        }

        function closeModal() {
            document.getElementById('match-modal').classList.add('hidden');
        }

        // --- ADMIN RENDERING ---
        function renderAdminWarnings() {
            const container = document.getElementById('admin-list-container');
            const badge = document.getElementById('admin-badge');
            const warnings = db.admin_warnings || [];
            
            if (warnings.length > 0) {
                badge.innerText = warnings.length;
                badge.classList.remove('hidden');
                
                let html = '';
                warnings.forEach(warn => {
                    let borderClass = "border-orange-200 bg-orange-50";
                    let textClass = "text-orange-800";
                    if(warn.includes("Kritisk") || warn.includes("Allvarlig") || warn.includes("Datafel")) {
                        borderClass = "border-red-200 bg-red-50";
                        textClass = "text-red-800 font-medium";
                    }
                    html += `<div class="p-3 border-l-4 rounded ${borderClass} ${textClass} text-sm shadow-sm">${warn}</div>`;
                });
                container.innerHTML = html;
            } else {
                badge.classList.add('hidden');
                container.innerHTML = `<div class="p-6 text-center text-green-700 bg-green-50 rounded border border-green-200">
                    <span class="text-2xl block mb-2">🎉</span>
                    Inga varningar! Databasen ser perfekt ut.
                </div>`;
            }
        }

        // Stäng modal om man klickar utanför
        document.getElementById('match-modal').addEventListener('click', function(e) {
            if (e.target === this) closeModal();
        });

        // --- INIT ---
        window.onload = () => {
            populateYearFilter();
            renderTournaments();
            renderMatches();
            renderAdminWarnings();
            console.log("Databas laddad:", db.metadata.title);
        };

    </script>
</body>
</html>"""

    # Injicera JSON-strängen på ett säkert sätt via .replace()
    final_html = html_template.replace("__JSON_DATA_PLACEHOLDER__", json_str)

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(final_html)
        
    print(f"✅ Dashboard genererad och sparad till: {OUTPUT_HTML}")
    print("🚀 Öppna filen i din webbläsare för att se resultatet!")

# =========================================================
# KÖR SKRIPTET
# =========================================================
if __name__ == "__main__":
    build_dashboard()