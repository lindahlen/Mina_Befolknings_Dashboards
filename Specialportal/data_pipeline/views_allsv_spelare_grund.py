import pandas as pd
import os
import json

# ==========================================
# 1. SETUP OCH KONFIGURATION AV SÖKVÄGAR
# ==========================================
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    csv_path = os.path.join(project_root, "csv_filer", "Allsv_spelare_Tvattad_Databas.csv")
    
    dashboard_dir = os.path.join(project_root, "dashboards")
    if not os.path.exists(dashboard_dir):
        os.makedirs(dashboard_dir)
        
    output_html = os.path.join(dashboard_dir, "Allsvensk_Rapport.html")

except NameError:
    print("⚠️ Kunde inte sätta arbetsmapp via __file__.")
    csv_path = "Allsv_spelare_Tvattad_Databas.csv"
    output_html = "Allsvensk_Rapport.html"

# ==========================================
# 2. LÄS IN OCH FÖRBERED DATA
# ==========================================
print("⏳ Läser in databasen för Dashboard...")
if not os.path.exists(csv_path):
    print(f"❌ Hittade inte filen: {csv_path}. Har du kört tvättmaskinen först?")
    exit()

df = pd.read_csv(csv_path).fillna("")

# ==========================================
# 3. FÖRBERED DATA FÖR JAVASCRIPT
# ==========================================
print("📊 Preppar interaktiv data...")
json_data = df.to_json(orient='records')

# ==========================================
# 4. BYGG HTML-DASHBOARD
# ==========================================
print("🌐 Genererar dynamisk HTML-dashboard...")

html_part1 = """
<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Allsvensk Spelarstatistik</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; color: #333; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); position: relative; }
        
        .back-link { color: #3498db; text-decoration: none; font-weight: 600; transition: color 0.2s; margin-bottom: 15px; }
        .back-link:hover { color: #1d6fa5; text-decoration: underline; }

        h1 { text-align: center; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-top: 0; margin-bottom: 30px; }
        
        .summary-cards { display: flex; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 15px; }
        .card { background: #3498db; color: white; padding: 20px; border-radius: 8px; text-align: center; flex: 1; min-width: 200px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .card h3 { margin: 0; font-size: 1.2em; font-weight: normal; opacity: 0.9; }
        .card p { margin: 10px 0 0 0; font-size: 2.2em; font-weight: bold; }
        
        /* Uppdaterad layout för filter för att rymma 4 dropdowns */
        .filters { display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 30px; background: #eef2f5; padding: 20px; border-radius: 8px; border-left: 5px solid #2c3e50; }
        .filter-item { flex: 1; min-width: 220px; }
        .filters select, .filters input { width: 100%; padding: 10px; font-size: 15px; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; outline: none; }
        .filters select:focus, .filters input:focus { border-color: #3498db; }
        
        .tabs { display: flex; border-bottom: 2px solid #ddd; margin-bottom: 20px; }
        .tab-btn { background: none; border: none; padding: 12px 20px; font-size: 16px; cursor: pointer; color: #7f8c8d; transition: 0.3s; font-weight: 500; }
        .tab-btn:hover { background-color: #f1f1f1; color: #2c3e50; }
        .tab-btn.active { border-bottom: 3px solid #2c3e50; font-weight: bold; color: #2c3e50; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        .tables-container { display: flex; gap: 20px; flex-wrap: wrap; }
        .table-wrapper { flex: 1; min-width: 300px; background: #fafafa; padding: 15px; border-radius: 8px; border: 1px solid #ddd; }
        .table-scroll { max-height: 600px; overflow-y: auto; }
        .data-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 15px;}
        .data-table th, .data-table td { padding: 10px; border-bottom: 1px solid #ddd; }
        .data-table th { background-color: #2c3e50; color: white; position: sticky; top: 0; z-index: 10; }
        .data-table tr:hover { background-color: #e1e8ed; }
        
        .player-link { color: #2980b9; font-weight: 600; text-decoration: underline; cursor: pointer; transition: color 0.2s; }
        .player-link:hover { color: #154360; }
        .gk-tag { color: #7f8c8d; font-size: 0.85em; font-weight: normal; margin-left: 4px; }

        .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.6); }
        .modal-content { background-color: #fff; margin: 5% auto; padding: 30px; border-radius: 10px; width: 90%; max-width: 650px; box-shadow: 0 5px 20px rgba(0,0,0,0.4); position: relative; }
        .close { color: #aaa; float: right; font-size: 18px; font-weight: bold; cursor: pointer; transition: 0.2s; position: relative; z-index: 10; display: flex; align-items: center; gap: 4px; }
        .close:hover { color: #e74c3c; }
        .close-icon { font-size: 26px; line-height: 1; }
        
        .modal-header { background-color: #ebf5fb; margin: -30px -30px 20px -30px; padding: 25px 30px; border-radius: 10px 10px 0 0; border-bottom: 2px solid #3498db; }
        .modal-header h2 { margin: 0; color: #2c3e50; font-size: 1.8em; }
        .modal-subtitle { color: #5a6e7f; font-size: 0.95em; margin-top: 8px; font-weight: 500; }
        
        .modal-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px; }
        .modal-field { background: #f9f9f9; padding: 12px; border-radius: 5px; border: 1px solid #eee; }
        .modal-field strong { color: #7f8c8d; display: block; font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
        .club-history { background: #eef2f5; padding: 20px; border-radius: 5px; border-left: 4px solid #3498db; }
        .club-history ul { margin: 0; padding-left: 20px; line-height: 1.6; }
        .club-history li { margin-bottom: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <!-- LÄNK-INSTÄLLNING: För att dölja "Tillbaka"-länken, ändra 'inline-block' till 'none' -->
        <a href="../nationella_index.html" class="back-link" style="display: inline-block;">&larr; Tillbaka till översikten</a>
        
        <h1>⚽ Allsvensk Spelarstatistik</h1>
        
        <!-- KPI-kort -->
        <div class="summary-cards">
            <div class="card"><h3>Antal Spelare</h3><p id="kpi-spelare">0</p></div>
            <div class="card"><h3>Totalt Antal Mål</h3><p id="kpi-mal">0</p></div>
            <div class="card"><h3>Totalt Antal Matcher</h3><p id="kpi-matcher">0</p></div>
        </div>

        <!-- Filter -->
        <div class="filters">
            <div class="filter-item">
                <label for="klubbFilter" style="display:block; margin-bottom:5px; font-weight:bold; color:#2c3e50;">Filtrera på Klubb:</label>
                <select id="klubbFilter">
                    <option value="">-- Alla Klubbar --</option>
                </select>
            </div>
            <div class="filter-item">
                <label for="namnFilter" style="display:block; margin-bottom:5px; font-weight:bold; color:#2c3e50;">Sök Spelare (Namn):</label>
                <input type="text" id="namnFilter" placeholder="Sök på namn...">
            </div>
            <!-- Nya Decennium-filter -->
            <div class="filter-item">
                <label for="startDecadeFilter" style="display:block; margin-bottom:5px; font-weight:bold; color:#2c3e50;">Startade under decennium:</label>
                <select id="startDecadeFilter">
                    <option value="">-- Alla Decennier --</option>
                </select>
            </div>
            <div class="filter-item">
                <label for="endDecadeFilter" style="display:block; margin-bottom:5px; font-weight:bold; color:#2c3e50;">Avslutade under decennium:</label>
                <select id="endDecadeFilter">
                    <option value="">-- Alla Decennier --</option>
                </select>
            </div>
        </div>

        <!-- Flikmeny -->
        <div class="tabs">
            <button class="tab-btn active" onclick="openTab(event, 'tab-oversikt')">📊 Topplistor & Statistik</button>
            <button class="tab-btn" onclick="openTab(event, 'tab-lista')">📋 Alla Spelarprofiler</button>
            <button class="tab-btn" onclick="openTab(event, 'tab-multi')">🔄 Historik: Flerklubbsspelare</button>
        </div>

        <div id="tab-oversikt" class="tab-content active">
            <div class="tables-container">
                <div class="table-wrapper">
                    <h2>🏆 Flest Matcher (Urval)</h2>
                    <div id="table-mat"></div>
                </div>
                <div class="table-wrapper">
                    <h2>⚽ Flest Mål (Urval)</h2>
                    <div id="table-mal"></div>
                </div>
                <div class="table-wrapper">
                    <h2>🌍 Vanligaste Nat. (Urval)</h2>
                    <div id="table-nat"></div>
                </div>
            </div>
        </div>

        <div id="tab-lista" class="tab-content">
            <div class="table-wrapper">
                <h2>📋 Komplett Spelarlista för aktuellt urval</h2>
                <div class="table-scroll">
                    <div id="table-players"></div>
                </div>
            </div>
        </div>

        <div id="tab-multi" class="tab-content">
            <div class="table-wrapper">
                <h2>🔄 Spelare i flera klubbar</h2>
                <p style="font-size: 0.9em; color: #666; margin-top:0;">Visar spelare inom ditt urval som representerat mer än en allsvensk klubb.</p>
                <div class="table-scroll">
                    <div id="table-multi"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- Modal -->
    <div id="playerModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <span class="close" onclick="closeModal()">Stäng <span class="close-icon">&times;</span></span>
                <h2 id="modal-name">Spelarnamn</h2>
                <div id="modal-subtitle" class="modal-subtitle"></div>
            </div>
            
            <div class="modal-grid">
                <div class="modal-field"><strong>Född:</strong> <span id="modal-born"></span></div>
                <div class="modal-field"><strong>Avled:</strong> <span id="modal-died"></span></div>
                <div class="modal-field"><strong>Nationalitet:</strong> <span id="modal-nat"></span></div>
                <div class="modal-field"><strong>Alias/Extranamn:</strong> <span id="modal-alias"></span></div>
                <div class="modal-field"><strong>Målvakt:</strong> <span id="modal-gk"></span></div>
                <div class="modal-field"><strong>Anteckningar:</strong> <span id="modal-notes"></span></div>
            </div>
            
            <div class="club-history">
                <strong style="color: #2c3e50; margin-bottom: 10px; display:block; font-size:1.1em;">Klubbhistorik:</strong>
                <div id="modal-clubs"></div>
            </div>
        </div>
    </div>
"""

html_part2 = """
    <script>
        const rawData = """ + json_data + """;
        const playerCareerYears = {}; // Håller koll på första och sista spelåret per spelare

        // Funktion för Smarta Namn ("Efternamn, Förnamn" -> "Förnamn Efternamn")
        function formatSmartName(nameStr) {
            if (!nameStr) return "Okänd";
            
            // Hjälpfunktion för snygg Title Case som hanterar bindestreck
            const toTitleCase = (str) => {
                return str.toLowerCase().replace(/(?:^|[\\s-])\\S/g, match => match.toUpperCase());
            };

            let parts = nameStr.split(',');
            if (parts.length === 2) {
                let lastName = parts[0].trim();
                let firstName = parts[1].trim();
                return toTitleCase(firstName) + " " + toTitleCase(lastName);
            } else {
                return toTitleCase(nameStr.trim()); // Fallback för brassar/artistnamn utan komma
            }
        }

        document.addEventListener("DOMContentLoaded", () => {
            const klubbSelect = document.getElementById("klubbFilter");
            const namnInput = document.getElementById("namnFilter");
            const startSelect = document.getElementById("startDecadeFilter");
            const endSelect = document.getElementById("endDecadeFilter");

            // --- 1. Extrahera klubbar ---
            const klubbar = [...new Set(rawData.map(d => d.Klubb))].filter(Boolean).sort();
            klubbar.forEach(k => {
                klubbSelect.add(new Option(k, k));
            });

            // --- 2. Beräkna Start- och Slutår för alla spelare & Bygg decenniumlistor ---
            const decadesSet = new Set();
            
            rawData.forEach(d => {
                const id = d.Nr || d.Rent_Namn;
                // Plocka ut alla 4-siffriga årtal i Tid-kolumnen (t.ex. "1999-2005" -> [1999, 2005])
                let years = (d.Tid || "").match(/\\d{4}/g);
                if (years) {
                    years = years.map(Number);
                    let pMin = Math.min(...years);
                    let pMax = Math.max(...years);
                    
                    if (!playerCareerYears[id]) {
                        playerCareerYears[id] = { min: pMin, max: pMax };
                    } else {
                        if (pMin < playerCareerYears[id].min) playerCareerYears[id].min = pMin;
                        if (pMax > playerCareerYears[id].max) playerCareerYears[id].max = pMax;
                    }
                }
            });

            // Hitta unika decennier baserat på den uträknade karriären
            Object.values(playerCareerYears).forEach(c => {
                if (c.min) decadesSet.add(Math.floor(c.min / 10) * 10);
                if (c.max) decadesSet.add(Math.floor(c.max / 10) * 10);
            });

            const sortedDecades = [...decadesSet].sort((a, b) => a - b);
            sortedDecades.forEach(dec => {
                const label = dec + "-talet";
                startSelect.add(new Option(label, dec));
                endSelect.add(new Option(label, dec));
            });

            // --- 3. Lyssna på ändringar ---
            klubbSelect.addEventListener('change', updateDashboard);
            namnInput.addEventListener('keyup', updateDashboard);
            startSelect.addEventListener('change', updateDashboard);
            endSelect.addEventListener('change', updateDashboard);
            
            updateDashboard(); // Kör initiering
        });

        function openTab(evt, tabName) {
            const tabcontent = document.getElementsByClassName("tab-content");
            for (let i = 0; i < tabcontent.length; i++) { tabcontent[i].style.display = "none"; }
            const tablinks = document.getElementsByClassName("tab-btn");
            for (let i = 0; i < tablinks.length; i++) { tablinks[i].className = tablinks[i].className.replace(" active", ""); }
            document.getElementById(tabName).style.display = "block";
            evt.currentTarget.className += " active";
        }

        window.openModal = function(idString) {
            const cleanId = String(idString);
            const playerRows = rawData.filter(d => String(d.Nr) === cleanId || String(d.Rent_Namn) === cleanId);
            if(playerRows.length === 0) return;
            
            const p = playerRows[0];
            const isGk = (p.Målvakt === "Ja") ? ' <span class="gk-tag" style="font-size:0.6em; vertical-align:middle;">(mv)</span>' : '';
            
            // Applicera den smarta namnomvandlaren för Popupens header!
            const fancyName = formatSmartName(p.Rent_Namn);
            document.getElementById('modal-name').innerHTML = fancyName + isGk;
            
            const bornStr = p.Född || "";
            const diedStr = p.Avled || "";
            let subtitleHtml = "";
            
            if (bornStr.length >= 4) {
                const bYear = bornStr.substring(0, 4);
                subtitleHtml = `Född ${bYear}`;
                
                if (diedStr && diedStr.length >= 4 && diedStr !== "-") {
                    const bDate = new Date(bornStr);
                    const dDate = new Date(diedStr);
                    if (!isNaN(bDate) && !isNaN(dDate)) {
                        let age = dDate.getFullYear() - bDate.getFullYear();
                        const m = dDate.getMonth() - bDate.getMonth();
                        if (m < 0 || (m === 0 && dDate.getDate() < bDate.getDate())) { age--; }
                        
                        if (age >= 0) {
                            const dYear = diedStr.substring(0, 4);
                            subtitleHtml += ` &mdash; Avled ${dYear} (Blev ${age} år)`;
                        } else {
                            const dYear = diedStr.substring(0, 4);
                            subtitleHtml += ` &mdash; Avled ${dYear}`;
                        }
                    } else {
                        const dYear = diedStr.substring(0, 4);
                        subtitleHtml += ` &mdash; Avled ${dYear}`;
                    }
                }
            }
            document.getElementById('modal-subtitle').innerHTML = subtitleHtml;
            
            document.getElementById('modal-born').innerText = p.Född || "-";
            document.getElementById('modal-died').innerText = p.Avled || "-";
            document.getElementById('modal-nat').innerText = p.Nationalitet || "SWE";
            document.getElementById('modal-alias').innerText = p.Alias || "-";
            document.getElementById('modal-gk').innerText = p.Målvakt || "Nej";
            document.getElementById('modal-notes').innerText = p.Anteckningar || "-";

            let historyHtml = '<ul>';
            let totMat = 0, totMal = 0;
            playerRows.forEach(r => {
                const mat = parseInt(r.Mat)||0;
                const mal = parseInt(r['Mål'])||0;
                totMat += mat; totMal += mal;
                historyHtml += `<li><strong>${r.Klubb}</strong> (${r.Tid || 'Okänd tid'}) &nbsp;&mdash;&nbsp; ${mat} mat, ${mal} mål</li>`;
            });
            historyHtml += `</ul><hr style="border:0; border-top:1px solid #ccc; margin:15px 0;"><p style="margin:0; font-weight:bold; font-size:1.1em;">Totalt: ${totMat} matcher, ${totMal} mål</p>`;
            document.getElementById('modal-clubs').innerHTML = historyHtml;

            document.getElementById('playerModal').style.display = 'block';
        };

        window.closeModal = function() { document.getElementById('playerModal').style.display = 'none'; };
        window.onclick = function(event) {
            const modal = document.getElementById('playerModal');
            if (event.target == modal) { modal.style.display = "none"; }
        };

        function updateDashboard() {
            const valdKlubb = document.getElementById("klubbFilter").value;
            const sokNamn = document.getElementById("namnFilter").value.toLowerCase();
            const valdStartDec = document.getElementById("startDecadeFilter").value;
            const valdEndDec = document.getElementById("endDecadeFilter").value;

            // --- FILTRERING ---
            let filtered = rawData;
            
            // Filtrera på Klubb
            if (valdKlubb) filtered = filtered.filter(d => d.Klubb === valdKlubb);
            
            // Filtrera på Namn
            if (sokNamn) filtered = filtered.filter(d => d.Rent_Namn && d.Rent_Namn.toLowerCase().includes(sokNamn));
            
            // Filtrera på Start-decennium (Baserat på spelarens HELA karriär)
            if (valdStartDec) {
                filtered = filtered.filter(d => {
                    const id = d.Nr || d.Rent_Namn;
                    const career = playerCareerYears[id];
                    return career && career.min && Math.floor(career.min / 10) * 10 == valdStartDec;
                });
            }
            
            // Filtrera på Avslut-decennium
            if (valdEndDec) {
                filtered = filtered.filter(d => {
                    const id = d.Nr || d.Rent_Namn;
                    const career = playerCareerYears[id];
                    return career && career.max && Math.floor(career.max / 10) * 10 == valdEndDec;
                });
            }

            // --- UPPDATERA KPI:ER ---
            const unikaSpelare = new Set(filtered.map(d => d.Nr)).size;
            const totalMat = filtered.reduce((sum, d) => sum + (parseInt(d.Mat) || 0), 0);
            const totalMal = filtered.reduce((sum, d) => sum + (parseInt(d['Mål']) || 0), 0);

            document.getElementById('kpi-spelare').innerText = unikaSpelare.toLocaleString('sv-SE');
            document.getElementById('kpi-mal').innerText = totalMal.toLocaleString('sv-SE');
            document.getElementById('kpi-matcher').innerText = totalMat.toLocaleString('sv-SE');

            // --- DATA-AGGRERERING FÖR TABELLER ---
            const playerStats = {};
            const natStats = {};
            const seenPlayersForNat = new Set(); 

            filtered.forEach(d => {
                const id = d.Nr || d.Rent_Namn; 
                if (!playerStats[id]) {
                    playerStats[id] = { id: id, namn: d.Rent_Namn || "Okänd", nat: d.Nationalitet || "SWE", isGk: d.Målvakt === "Ja", klubbar: new Set(), mat: 0, mal: 0 };
                }
                if(d.Klubb) playerStats[id].klubbar.add(d.Klubb);
                playerStats[id].mat += (parseInt(d.Mat) || 0);
                playerStats[id].mal += (parseInt(d['Mål']) || 0);

                if (!seenPlayersForNat.has(id)) {
                    seenPlayersForNat.add(id);
                    const nat = d.Nationalitet || "SWE";
                    natStats[nat] = (natStats[nat] || 0) + 1;
                }
            });

            const statArray = Object.values(playerStats);
            
            // --- FLIK 1: ÖVERSIKT (TOPPLISTOR) ---
            const topMat = [...statArray].sort((a,b) => b.mat - a.mat).slice(0, 10);
            const topMal = [...statArray].sort((a,b) => b.mal - a.mal).slice(0, 10);
            const topNat = Object.entries(natStats).map(([nat, count]) => ({nat, count})).sort((a,b) => b.count - a.count).slice(0, 10);

            function renderTopTable(data, labelKey, valKey, valHeader) {
                if (data.length === 0) return "<p>Ingen data.</p>";
                let html = '<table class="data-table"><thead><tr><th>Namn / Nat</th><th>' + valHeader + '</th></tr></thead><tbody>';
                data.forEach(row => {
                    let displayLabel = row[labelKey];
                    if(row.id && row.isGk) displayLabel += ' <span class="gk-tag">(mv)</span>';
                    if(row.id) {
                        const safeId = String(row.id).replace(/'/g, "\\\\'");
                        displayLabel = `<a class="player-link" onclick="openModal('${safeId}')">${displayLabel}</a>`;
                    }
                    html += `<tr><td>${displayLabel}</td><td>${row[valKey]}</td></tr>`;
                });
                return html + '</tbody></table>';
            }

            document.getElementById('table-mat').innerHTML = renderTopTable(topMat, 'namn', 'mat', 'Matcher');
            document.getElementById('table-mal').innerHTML = renderTopTable(topMal, 'namn', 'mal', 'Mål');
            document.getElementById('table-nat').innerHTML = renderTopTable(topNat, 'nat', 'count', 'Antal Spelare');

            // --- FLIK 2: KOMPLETT SPELARLISTA ---
            const sortedPlayers = [...statArray].sort((a, b) => (a.namn || "").localeCompare(b.namn || ""));
            let htmlPlayers = '<table class="data-table"><thead><tr><th>Namn (Klicka för info)</th><th>Nat</th><th>Klubbar (i urvalet)</th><th>Matcher (Totalt)</th><th>Mål (Totalt)</th></tr></thead><tbody>';
            if(sortedPlayers.length === 0) htmlPlayers += '<tr><td colspan="5">Ingen data hittades.</td></tr>';
            sortedPlayers.forEach(p => {
                const safeId = String(p.id).replace(/'/g, "\\\\'");
                let displayName = p.namn || "-";
                if(p.isGk) displayName += ' <span class="gk-tag">(mv)</span>';

                htmlPlayers += `<tr>
                    <td><a class="player-link" onclick="openModal('${safeId}')">${displayName}</a></td>
                    <td>${p.nat}</td>
                    <td style="font-size: 0.85em; color: #555;">${Array.from(p.klubbar).join(", ")}</td>
                    <td>${p.mat}</td>
                    <td>${p.mal}</td>
                </tr>`;
            });
            document.getElementById('table-players').innerHTML = htmlPlayers + '</tbody></table>';

            // --- FLIK 3: FLERKLUBBSSPELARE ---
            let multiArr = statArray.filter(p => p.klubbar.size > 1);
            multiArr.sort((a, b) => b.mat - a.mat);

            let htmlMulti = '<table class="data-table"><thead><tr><th>Namn (Klicka för info)</th><th>Nat</th><th>Klubbar</th><th>Matcher</th><th>Mål</th></tr></thead><tbody>';
            if(multiArr.length === 0) htmlMulti += '<tr><td colspan="5">Inga flerklubbsspelare hittades i detta urval.</td></tr>';
            multiArr.forEach(p => {
                const safeId = String(p.id).replace(/'/g, "\\\\'");
                let displayName = p.namn;
                if(p.isGk) displayName += ' <span class="gk-tag">(mv)</span>';

                htmlMulti += `<tr>
                    <td><a class="player-link" onclick="openModal('${safeId}')">${displayName}</a></td>
                    <td>${p.nat}</td>
                    <td style="font-size: 0.85em; color: #555;">${Array.from(p.klubbar).join(", ")}</td>
                    <td>${p.mat}</td>
                    <td>${p.mal}</td>
                </tr>`;
            });
            document.getElementById('table-multi').innerHTML = htmlMulti + '</tbody></table>';
        }
    </script>
</body>
</html>
"""

final_html = html_part1 + html_part2

# ==========================================
# 5. SPARA FILEN
# ==========================================
with open(output_html, "w", encoding="utf-8") as f:
    f.write(final_html)

print(f"✅ Dashboard uppdaterad med Smarta Namn och Decenniefilter!")
print(f"👉 Öppna filen: {output_html}")