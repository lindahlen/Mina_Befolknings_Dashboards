// ==========================================
// Kalkylator Motor 2035 - Kärnlogik & Databearbetning
// ==========================================

var PROGNOS_SLUTAR = 2035;

// GLOBALA VARIABLER (Delas med grafer_2035.js)
var syssBasdata = {};
var syssConfig = {};
var popData = []; 
var customPopData = null; 
var useCustomPop = false; 

var histDataStore = {}; 
var progDataStore = {}; 
var savedProjectedData = null; 
var currentShocks = []; 

var trendChartInstance = null;
var globalChartVisibility = {}; 
var allYears = [];
var histYearsGlobal = [];
var baseYear = 0; 

var avgAnnualStudents = 3500; 
var annualStudentsMap = {}; 
var avgAnnualCivIng = 0;
var annualCivIngMap = {};
var useSpecificCivIng = false;

var globalMigrantEmploymentRate = 0.50; 
var takEffektMaxSyss = 100; 

var takEffekter = {
    maxSyssGrad: 85.0,
    minArbetsloshet: 3.5,
    karnaLangtidsarbetslosa: 3.0,
    maxInpendlingsandel: 25.0,
    maxSyssGradAldre: 25.0,
    kapacitetstakInfrastruktur: 30000,
    studentAbsorptionsTak: 50
};

window.scenarioSettings = {
    base: { jobGrowth: 5, syssGrad: 0.5, student: 2, inpendling: 0, utpendling: 0, distans: 0, region: 0, migrantSyss: 10 },
    high: { jobGrowth: 15, syssGrad: 2.0, student: 10, inpendling: 10, utpendling: 5, distans: 10, region: 15, migrantSyss: 15 },
    low: { jobGrowth: -5, syssGrad: -1.0, student: -2, inpendling: -5, utpendling: -2, distans: 0, region: 0, migrantSyss: 5 },
    stagnant: { jobGrowth: 0, syssGrad: 0, student: 0, inpendling: 0, utpendling: 0, distans: 0, region: 0, migrantSyss: 10 }
};

// ==========================================
// HJÄLPFUNKTIONER (Data-läsning)
// ==========================================
function extractYear(row) {
    if (row['År'] !== undefined) return parseInt(row['År']);
    if (row['år'] !== undefined) return parseInt(row['år']);
    if (row['ÅR'] !== undefined) return parseInt(row['ÅR']);
    return null;
}

function getKon(r) {
    for (let k in r) {
        if (k.toLowerCase().trim() === 'kön') return String(r[k]).trim().toLowerCase();
    }
    return null;
}

function getRowTotal(r) {
    if (r['Totalt 16-74 år'] != null) return parseFloat(r['Totalt 16-74 år']);
    if (r['Totalt 16-74'] != null) return parseFloat(r['Totalt 16-74']);
    if (r['Totalt'] != null) return parseFloat(r['Totalt']);
    if (r['Samtliga'] != null) return parseFloat(r['Samtliga']);
    let sum = 0;
    Object.keys(r).forEach(k => {
        if (k.match(/\d+/) && !k.toLowerCase().includes('totalt') && !['År','år','ÅR','Kön','kön','Sektor','Utbildningsnivå','Bransch'].includes(k)) {
            sum += parseFloat(r[k]) || 0;
        }
    });
    return sum;
}

function getPopForYear(dataset, year) {
    let pop = 0;
    let records = dataset.filter(r => String(r.tid).trim() === `${year} (Prognos)`);
    if (records.length === 0) records = dataset.filter(r => String(r.tid).trim() === String(year));
    
    let useGender = records.some(r => String(r.kön).trim().toLowerCase() === 'män' || String(r.kön).trim().toLowerCase() === 'kvinnor');
    records.forEach(r => {
        if (!String(r.ålder).toLowerCase().includes('totalt')) {
            if (useGender && String(r.kön).trim().toLowerCase() !== 'män' && String(r.kön).trim().toLowerCase() !== 'kvinnor') return;
            const match = String(r.ålder).match(/\d+/);
            if (match) {
                const age = parseInt(match[0]);
                if (age >= 16 && age <= 74) pop += (r.Befolkning || 0);
            }
        }
    });
    return pop;
}

function getPopForAge(dataset, year, targetAge) {
    let pop = 0;
    let records = dataset.filter(r => String(r.tid).trim() === `${year} (Prognos)`);
    if (records.length === 0) records = dataset.filter(r => String(r.tid).trim() === String(year));
    
    records.forEach(r => {
        if (!String(r.ålder).toLowerCase().includes('totalt')) {
            const match = String(r.ålder).match(/\d+/);
            if (match && parseInt(match[0]) === targetAge) pop += (r.Befolkning || 0);
        }
    });
    return pop;
}

function getBaseEmploymentRateForAge(age, baseAgeRates) {
    if (!baseAgeRates) return 0.80; 
    for (let key in baseAgeRates) {
        let group = baseAgeRates[key];
        if (age >= group.min && age <= group.max) return group.rate; 
    }
    return 0.80; 
}

function getSliderOffsetForAge(age) {
    if (age >= 16 && age <= 19) {
        let el = document.getElementById('syssAge16_19');
        return el ? parseFloat(el.value || 0) : 0;
    }
    let lower = Math.floor(age / 5) * 5;
    let el = document.getElementById(`syssAge${lower}_${lower+4}`);
    if (el) return parseFloat(el.value || 0);
    return 0;
}

function calculateMigrantEmploymentRate() {
    let totalInf = 0; let workingInf = 0;
    const migrantData = syssConfig['Andel_förvarb_inflytt_över_län'];
    let rateCol = null;
    
    if (migrantData && migrantData.length > 0) {
        const keys = Object.keys(migrantData[0]);
        rateCol = keys.find(k => k.includes('Förvärvsarbetande_Totalt_In_Snitt')) ||
                  keys.find(k => k.includes('Förvärvsarbetande_Totalt_In_2024')) ||
                  keys.find(k => k.includes('Förvärvsarbetande'));
    }

    if (popData && popData.length > 0 && rateCol) {
        let bYearData = popData.filter(r => String(r.tid).trim() === String(baseYear) && !String(r.ålder).includes('Totalt'));
        if (bYearData.length === 0) {
             const aYears = [...new Set(popData.map(r => parseInt(String(r.tid).substring(0,4))))].filter(y => !isNaN(y)).sort();
             const latestY = aYears[aYears.length - 1];
             bYearData = popData.filter(r => String(r.tid).trim() === String(latestY) && !String(r.ålder).includes('Totalt'));
        }

        for (let age = 0; age <= 100; age++) {
            let inflyttThisAge = 0;
            bYearData.forEach(r => {
                const match = String(r.ålder).match(/\d+/);
                if (match && parseInt(match[0]) === age) { inflyttThisAge += (r.Inflyttade || 0); }
            });
            
            let rate = 0;
            const mRow = migrantData.find(r => {
                const m = String(r['Ålder']).match(/\d+/);
                return m && parseInt(m[0]) === age;
            });
            if (mRow && mRow[rateCol]) rate = parseFloat(mRow[rateCol]) / 100;
            
            totalInf += inflyttThisAge;
            workingInf += inflyttThisAge * rate;
        }
    }
    if (totalInf > 0 && workingInf > 0) globalMigrantEmploymentRate = workingInf / totalInf;
    else globalMigrantEmploymentRate = 0.50; 
}

// ==========================================
// INITIERING (Hämtar all data vid start)
// ==========================================
async function fetchJSON(url) {
    try {
        const res = await fetch(url);
        if (!res.ok && res.status !== 0) return null; 
        let text = await res.text(); 
        text = text.replace(/:\s*NaN/g, ': null');
        return JSON.parse(text);
    } catch(e) { return null; }
}

window.addEventListener('DOMContentLoaded', () => {
    const isLocal = window.location.protocol === 'file:';
    const cb = isLocal ? '' : '?v=' + new Date().getTime(); 

    const generalSyssSlider = document.getElementById('syssGradSlider');
    if (generalSyssSlider) {
        generalSyssSlider.addEventListener('input', function() {
            let val = this.value;
            document.querySelectorAll('input[id^="syssAge"]').forEach(slider => {
                slider.value = val;
                document.getElementById(slider.id.replace('syssAge', 'val')).innerText = (val > 0 ? '+' : '') + val;
            });
        });
    }

    Promise.all([
        fetchJSON('syss_basdata_2035.json' + cb),
        fetchJSON('syss_config_2035.json' + cb),
        fetchJSON('kalkylator_basdata_2035.json' + cb).catch(() => [])
    ]).then(async ([sBas, sConf, pBas]) => {
        
        // Fallback: Leta efter de gamla filnamnen om 2035-filerna saknas
        if (!sBas) sBas = await fetchJSON('syss_basdata.json' + cb);
        if (!sConf) sConf = await fetchJSON('syss_config.json' + cb);
        if (!pBas || pBas.length === 0) pBas = await fetchJSON('kalkylator_basdata.json' + cb).catch(() => []);

        const statusDiv = document.getElementById('dataStatus');
        if (!sBas) {
            statusDiv.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Hittade ingen basdata.';
            statusDiv.className = "p-1.5 bg-red-50 rounded border border-red-100 text-xs font-medium text-red-600";
            return;
        }

        syssBasdata = sBas;
        syssConfig = sConf || {};
        popData = pBas || [];

        // Konfigurera scenarier från fil
        if (syssConfig['Scenarier'] && syssConfig['Scenarier'].length > 0) {
            const rows = syssConfig['Scenarier'];
            const mapScenario = (colName) => {
                return {
                    jobGrowth: parseFloat(rows.find(r => r.Indikator === 'Jobbtillväxt')?.[colName] || 0),
                    syssGrad: parseFloat(rows.find(r => r.Indikator === 'Sysselsättningsgrad')?.[colName] || 0),
                    student: parseFloat(rows.find(r => r.Indikator === 'Kvarstannandegrad')?.[colName] || 0),
                    inpendling: parseFloat(rows.find(r => r.Indikator === 'Inpendling')?.[colName] || 0),
                    utpendling: parseFloat(rows.find(r => r.Indikator === 'Utpendling')?.[colName] || 0),
                    distans: parseFloat(rows.find(r => r.Indikator === 'Distansarbete')?.[colName] || 0),
                    region: parseFloat(rows.find(r => r.Indikator === 'Regionförstoring')?.[colName] || 0),
                    migrantSyss: parseFloat(rows.find(r => r.Indikator === 'Justering inflyttares syss.grad')?.[colName] || 10)
                };
            };
            window.scenarioSettings.base = mapScenario('Bas');
            window.scenarioSettings.high = mapScenario('Hög');
            window.scenarioSettings.low = mapScenario('Låg');
            window.scenarioSettings.stagnant = mapScenario('Stagnerande');
        }

        // Studentdata
        if (syssConfig['Universitet'] && syssConfig['Universitet'].length > 0) {
            syssConfig['Universitet'].forEach(r => {
                let y = extractYear(r);
                if (y) {
                    let studentVal = r['Examinerade_Studenter'] !== undefined ? r['Examinerade_Studenter'] : r['Examinerade_studenter'];
                    if (studentVal !== undefined && studentVal !== null) annualStudentsMap[y] = parseFloat(studentVal);
                    if (r['Examinerade_Civilingenjörer'] !== undefined && r['Examinerade_Civilingenjörer'] !== null) annualCivIngMap[y] = parseFloat(r['Examinerade_Civilingenjörer']);
                }
            });
            const stYears = Object.keys(annualStudentsMap).map(Number).sort((a,b)=>a-b);
            if (stYears.length > 0) avgAnnualStudents = annualStudentsMap[stYears[stYears.length - 1]];
            const civYears = Object.keys(annualCivIngMap).map(Number).sort((a,b)=>a-b);
            if (civYears.length > 0) avgAnnualCivIng = annualCivIngMap[civYears[civYears.length - 1]];
        }

        // Tak-effekter
        if (syssConfig['Tak_effekten'] && syssConfig['Tak_effekten'].length > 0) {
            syssConfig['Tak_effekten'].forEach(r => {
                const keys = Object.keys(r);
                if (keys.length >= 2) {
                    const keyStr = String(r[keys[0]] || '').toLowerCase();
                    const val = parseFloat(r[keys[1]]);
                    if (!isNaN(val)) {
                        if (keyStr.includes('lägsta friktionsarbetslöshet')) takEffekter.minArbetsloshet = val;
                        if (keyStr.includes('max_sysselsättningsgrad') && !keyStr.includes('äldre')) { takEffekter.maxSyssGrad = val; takEffektMaxSyss = val; }
                        if (keyStr.includes('kärna_långtidsarbetslösa')) takEffekter.karnaLangtidsarbetslosa = val;
                        if (keyStr.includes('max_inpendlingsandel')) takEffekter.maxInpendlingsandel = val;
                        if (keyStr.includes('kapacitetstak_infrastruktur')) takEffekter.kapacitetstakInfrastruktur = val;
                    }
                }
            });
        }

        // Etableringschocker UI
        const shocksContainer = document.getElementById('shocksContainer');
        const shocksList = document.getElementById('shocksList');
        if (syssConfig['Etableringschocker'] && syssConfig['Etableringschocker'].length > 0 && shocksList) {
            syssConfig['Etableringschocker'].forEach((shock, index) => {
                if (!shock['År'] || !shock['Händelsenamn']) return;
                const div = document.createElement('div');
                const isPos = parseFloat(shock['Antal_Jobb']) >= 0;
                const colorClass = isPos ? 'text-emerald-700 bg-emerald-50' : 'text-red-700 bg-red-50';
                const sign = isPos ? '+' : '';
                div.innerHTML = `
                    <input type="checkbox" id="shock_${index}" class="hidden shock-checkbox" value="${index}" onchange="runSimulation()">
                    <label for="shock_${index}" class="flex justify-between items-center p-2 rounded border border-gray-200 cursor-pointer hover:bg-gray-50 transition text-xs text-gray-600">
                        <span><b>${shock['År']}:</b> ${shock['Händelsenamn']}</span>
                        <span class="font-bold ${colorClass} px-1.5 py-0.5 rounded text-[10px]">${sign}${shock['Antal_Jobb']}</span>
                    </label>
                `;
                shocksList.appendChild(div);
            });
            if (shocksContainer) shocksContainer.classList.remove('hidden');
        }

        // Bransch-rullista
        const subGroupSelect = document.getElementById('subGroupSelect');
        if (syssConfig['SNIgrupper'] && syssConfig['SNIgrupper'].length > 0 && subGroupSelect) {
            const firstRow = syssConfig['SNIgrupper'][0];
            const keys = Object.keys(firstRow);
            const groupCols = keys.slice(1);
            subGroupSelect.innerHTML = '<option value="all">Alla branscher (SNI)</option>';
            groupCols.forEach(col => { subGroupSelect.add(new Option(col, col)); });
            subGroupSelect.setAttribute('data-type', 'bransch');
        }

        // Officiell Befolkning (Styrfil)
        if (syssConfig['Officiell_befolkningsprognos'] && syssConfig['Officiell_befolkningsprognos'].length > 0) {
            syssConfig['Officiell_befolkningsprognos'].forEach(row => {
                const year = extractYear(row);
                const rawSex = String(row['Kön'] || row['kön'] || '').trim().toLowerCase();
                if (!year || !rawSex) return;
                
                let sex = null;
                if (rawSex.startsWith('m')) sex = 'Män';
                else if (rawSex.startsWith('k')) sex = 'Kvinnor';
                if (!sex) return;
                
                const tidStr = `${year} (Prognos)`; 
                let totalPop = 0;
                for (let age = 0; age <= 100; age++) {
                    let val = row[String(age)] !== undefined ? row[String(age)] : (row[age] !== undefined ? row[age] : null);
                    if (val !== undefined && val !== null) {
                        let popVal = parseFloat(val);
                        popData.push({ tid: tidStr, kön: sex, ålder: age === 100 ? "100+ år" : `${age} år`, Befolkning: popVal });
                        totalPop += popVal;
                    }
                }
                popData.push({ tid: tidStr, kön: sex, ålder: "Totalt", Befolkning: totalPop });
            });
        }

        // LÅS UPP GRÄNSSNITTET
        const scP = document.getElementById('scenarioPanel');
        if (scP) scP.classList.remove('opacity-50', 'pointer-events-none');
        
        if(typeof checkSharedScenario === 'function') checkSharedScenario(); 

        let popStatus = (popData.length > 0 || customPopData !== null) ? "Befolkning kopplad." : "VARNING: Saknar befolkning!";
        statusDiv.innerHTML = `<i class="fa-solid fa-circle-check"></i> Redo. <b>${popStatus}</b>`;
        statusDiv.className = "p-1.5 px-3 bg-green-50 rounded border border-green-100 text-xs font-medium text-green-600";

        extractHistoricalData();
        calculateMigrantEmploymentRate(); 
        
        if(typeof buildDropdowns === 'function') buildDropdowns(); 
        if(typeof updateDashboard === 'function') updateDashboard(false); 

    }).catch(error => {
        const ds = document.getElementById('dataStatus');
        if (ds) {
            ds.innerHTML = `<b>Krasch:</b> ${error.message}`;
            ds.className = "p-1.5 bg-red-50 rounded text-red-600 text-xs";
        }
    });
});

// ==========================================
// SCB-HISTORIK & DATATVÄTT
// ==========================================
function extractHistoricalData() {
    const dfTillagg = syssBasdata['Syss_tillägg'] || syssBasdata['Syss_tillagg'] || [];
    const dfSyssGrad = syssBasdata['Syssgrad'] || [];
    const dfBRP = syssBasdata['BRP'] || [];
    const dfPendling = syssBasdata['Pendling'] || [];
    
    let years = new Set();
    dfTillagg.forEach(r => { let y = extractYear(r); if(y) years.add(y); });
    dfSyssGrad.forEach(r => { let y = extractYear(r); if(y) years.add(y); });
    dfBRP.forEach(r => { let y = extractYear(r); if(y) years.add(y); });
    
    if(syssBasdata['Arbetslöshet']) syssBasdata['Arbetslöshet'].forEach(r => { let y = extractYear(r); if(y) years.add(y); });
    if(syssBasdata['Långtidsarbetslöshet'] || syssBasdata['Langtidsarbetsloshet']) {
        const lData = syssBasdata['Långtidsarbetslöshet'] || syssBasdata['Langtidsarbetsloshet'];
        lData.forEach(r => { let y = extractYear(r); if(y) years.add(y); });
    }
    if(syssBasdata['Natt_utrikes']) syssBasdata['Natt_utrikes'].forEach(r => { let y = extractYear(r); if(y) years.add(y); });
    if(syssBasdata['Syss_utrikes']) syssBasdata['Syss_utrikes'].forEach(r => { let y = extractYear(r); if(y) years.add(y); });
    if(syssBasdata['Syssgrad_utrikes']) syssBasdata['Syssgrad_utrikes'].forEach(r => { let y = extractYear(r); if(y) years.add(y); });
    
    const sortedYears = Array.from(years).filter(y => !isNaN(y)).sort((a,b)=>a-b);
    if (sortedYears.length === 0) return;

    histYearsGlobal = sortedYears; 
    histDataStore = {};
    let brpHistory = []; let lastKnownBRP = null; let lastKnownBRPYear = null;
    
    sortedYears.forEach(y => {
        let dagTotalt = null, nattTotalt = null;
        let inpendlingTot = 0, utpendlingTot = 0;
        let hasPendlingData = false;
        
        let d_man = null, d_kvinna = null;
        const dagRowM = dfTillagg.find(r => extractYear(r) == y && String(r['Typ']).toLowerCase().includes('dag') && getKon(r) === 'män');
        const dagRowK = dfTillagg.find(r => extractYear(r) == y && String(r['Typ']).toLowerCase().includes('dag') && getKon(r) === 'kvinnor');
        if (dagRowM) d_man = parseFloat(dagRowM['Totalt'] || dagRowM['Samtliga'] || 0);
        if (dagRowK) d_kvinna = parseFloat(dagRowK['Totalt'] || dagRowK['Samtliga'] || 0);

        let n_man = null, n_kvinna = null;
        const nattRowM = dfTillagg.find(r => extractYear(r) == y && String(r['Typ']).toLowerCase().includes('natt') && getKon(r) === 'män');
        const nattRowK = dfTillagg.find(r => extractYear(r) == y && String(r['Typ']).toLowerCase().includes('natt') && getKon(r) === 'kvinnor');
        if (nattRowM) n_man = parseFloat(nattRowM['Totalt'] || nattRowM['Samtliga'] || 0);
        if (nattRowK) n_kvinna = parseFloat(nattRowK['Totalt'] || nattRowK['Samtliga'] || 0);

        if (d_man == null || d_kvinna == null) {
            const syssAlderData = syssBasdata['Syss_ålder'] || syssBasdata['Syss_alder'] || [];
            let m = 0, k = 0, found = false;
            syssAlderData.filter(r => extractYear(r) == y).forEach(r => {
                let kon = getKon(r);
                if (kon === 'män') { m += getRowTotal(r); found = true; }
                if (kon === 'kvinnor') { k += getRowTotal(r); found = true; }
            });
            if (found) { d_man = m; d_kvinna = k; }
        }
        if (n_man == null || n_kvinna == null) {
            const nattAlderData = syssBasdata['Natt_ålder'] || syssBasdata['Natt_alder'] || [];
            let m = 0, k = 0, found = false;
            nattAlderData.filter(r => extractYear(r) == y).forEach(r => {
                let kon = getKon(r);
                if (kon === 'män') { m += getRowTotal(r); found = true; }
                if (kon === 'kvinnor') { k += getRowTotal(r); found = true; }
            });
            if (found) { n_man = m; n_kvinna = k; }
        }

        const dagRow = dfTillagg.find(r => extractYear(r) == y && String(r['Typ']).toLowerCase().includes('dag') && (getKon(r) === 'totalt' || getKon(r) === null));
        if (dagRow && dagRow['Totalt'] != null) dagTotalt = parseFloat(dagRow['Totalt']);
        else if (d_man != null && d_kvinna != null) dagTotalt = d_man + d_kvinna; 
        
        if (dagRow && dagRow['Pendling'] != null) {
            inpendlingTot = parseFloat(dagRow['Pendling']);
            hasPendlingData = true;
        }

        const nattRow = dfTillagg.find(r => extractYear(r) == y && String(r['Typ']).toLowerCase().includes('natt') && (getKon(r) === 'totalt' || getKon(r) === null));
        if (nattRow && nattRow['Totalt'] != null) nattTotalt = parseFloat(nattRow['Totalt']);
        else if (n_man != null && n_kvinna != null) nattTotalt = n_man + n_kvinna; 

        if (nattRow && nattRow['Pendling'] != null) {
            utpendlingTot = parseFloat(nattRow['Pendling']);
            hasPendlingData = true;
        }

        if (!hasPendlingData && dfPendling.length > 0) {
            const inRow = dfPendling.find(r => extractYear(r) == y && String(r['Pendlingsriktning']).includes('In') && (getKon(r) === 'totalt' || getKon(r) === null));
            if (inRow && inRow['Totalt'] != null) { inpendlingTot = parseFloat(inRow['Totalt']); hasPendlingData = true; }
            else {
                const inM = dfPendling.find(r => extractYear(r) == y && String(r['Pendlingsriktning']).includes('In') && getKon(r) === 'män');
                const inK = dfPendling.find(r => extractYear(r) == y && String(r['Pendlingsriktning']).includes('In') && getKon(r) === 'kvinnor');
                if (inM || inK) { inpendlingTot = (inM ? parseFloat(inM['Totalt']) : 0) + (inK ? parseFloat(inK['Totalt']) : 0); hasPendlingData = true; }
            }

            const utRow = dfPendling.find(r => extractYear(r) == y && String(r['Pendlingsriktning']).includes('Ut') && (getKon(r) === 'totalt' || getKon(r) === null));
            if (utRow && utRow['Totalt'] != null) { utpendlingTot = parseFloat(utRow['Totalt']); hasPendlingData = true; }
            else {
                const utM = dfPendling.find(r => extractYear(r) == y && String(r['Pendlingsriktning']).includes('Ut') && getKon(r) === 'män');
                const utK = dfPendling.find(r => extractYear(r) == y && String(r['Pendlingsriktning']).includes('Ut') && getKon(r) === 'kvinnor');
                if (utM || utK) { utpendlingTot = (utM ? parseFloat(utM['Totalt']) : 0) + (utK ? parseFloat(utK['Totalt']) : 0); hasPendlingData = true; }
            }
        }

        let faktiskRate = null;
        const syssGradRow = dfSyssGrad.find(r => extractYear(r) == y && (getKon(r) === 'totalt' || getKon(r) === null));
        if (syssGradRow && syssGradRow['Totalt 20-64 år'] != null) faktiskRate = parseFloat(syssGradRow['Totalt 20-64 år']);
        
        const syssGradM = dfSyssGrad.find(r => extractYear(r) == y && getKon(r) === 'män');
        const syssGradK = dfSyssGrad.find(r => extractYear(r) == y && getKon(r) === 'kvinnor');

        let syss_in_tot = null, syss_ut_tot = null;
        if(syssBasdata['Syssgrad_utrikes']) {
            const suRow = syssBasdata['Syssgrad_utrikes'].find(r => extractYear(r) == y);
            if (suRow) {
                const keys = Object.keys(suRow);
                const inKey = keys.find(k => k.includes('Inrikes') && k.includes('Totalt'));
                const utKey = keys.find(k => k.includes('Utrikes') && k.includes('Totalt'));
                if (inKey) syss_in_tot = parseFloat(suRow[inKey]);
                if (utKey) syss_ut_tot = parseFloat(suRow[utKey]);
            }
        }

        let brpPerSyss = null;
        const brpRow = dfBRP.find(r => extractYear(r) == y);
        if (brpRow && brpRow['Linköping_BRP_per_sysselsatt_dagbefolkning_(tkr)'] != null) {
            brpPerSyss = parseFloat(brpRow['Linköping_BRP_per_sysselsatt_dagbefolkning_(tkr)']);
            lastKnownBRP = brpPerSyss; lastKnownBRPYear = y; brpHistory.push({year: y, val: brpPerSyss});
        }

        let arbetsloshetPct = null, arb_inrikes = null, arb_utrikes = null, arb_man = null, arb_kvinna = null;
        if(syssBasdata['Arbetslöshet']) {
            const arbRow = syssBasdata['Arbetslöshet'].find(r => extractYear(r) == y);
            if(arbRow) {
                const pctKeys = Object.keys(arbRow).filter(k => String(k).toLowerCase().includes('%') || String(k).toLowerCase().includes('andel'));
                if(pctKeys.length > 0) arbetsloshetPct = parseFloat(arbRow[pctKeys[0]]);
                
                const inKey = pctKeys.find(k => k.toLowerCase().includes('inrikes'));
                const utKey = pctKeys.find(k => k.toLowerCase().includes('utrikes'));
                if(inKey) arb_inrikes = parseFloat(arbRow[inKey]); if(utKey) arb_utrikes = parseFloat(arbRow[utKey]);
                const mKeyArb = pctKeys.find(k => { const kl = k.toLowerCase(); return (kl.includes('män') || kl.includes('man')) && !kl.includes('kvinna'); });
                const kKeyArb = pctKeys.find(k => k.toLowerCase().includes('kvinnor') || k.toLowerCase().includes('kvinna'));
                if(mKeyArb) arb_man = parseFloat(arbRow[mKeyArb]); if(kKeyArb) arb_kvinna = parseFloat(arbRow[kKeyArb]);
            }
        }

        let langtidsPct = null, larb_inrikes = null, larb_utrikes = null, larb_man = null, larb_kvinna = null;
        if(syssBasdata['Långtidsarbetslöshet'] || syssBasdata['Langtidsarbetsloshet']) {
            const lData = syssBasdata['Långtidsarbetslöshet'] || syssBasdata['Langtidsarbetsloshet'];
            const lRow = lData.find(r => extractYear(r) == y);
            if(lRow) {
                const pctKeys = Object.keys(lRow).filter(k => String(k).toLowerCase().includes('%') || String(k).toLowerCase().includes('andel'));
                if(pctKeys.length > 0) langtidsPct = parseFloat(lRow[pctKeys[0]]);
                
                const inKey = pctKeys.find(k => k.toLowerCase().includes('inrikes'));
                const utKey = pctKeys.find(k => k.toLowerCase().includes('utrikes'));
                if(inKey) larb_inrikes = parseFloat(lRow[inKey]); if(utKey) larb_utrikes = parseFloat(lRow[utKey]);
                const mKeyLarb = pctKeys.find(k => { const kl = k.toLowerCase(); return (kl.includes('män') || kl.includes('man')) && !kl.includes('kvinna'); });
                const kKeyLarb = pctKeys.find(k => k.toLowerCase().includes('kvinnor') || k.toLowerCase().includes('kvinna'));
                if(mKeyLarb) larb_man = parseFloat(lRow[mKeyLarb]); if(kKeyLarb) larb_kvinna = parseFloat(lRow[kKeyLarb]);
            }
        }

        let n_inrikes = null, n_utrikes = null, d_inrikes = null, d_utrikes = null;
        if (syssBasdata['Natt_utrikes']) {
            const nuRow = syssBasdata['Natt_utrikes'].find(r => extractYear(r) == y && getKon(r) === 'totalt');
            if(nuRow) {
                let kIn = Object.keys(nuRow).find(k=>k.toLowerCase().includes('inrikes') || k.toLowerCase().includes('sverige'));
                let kUt = Object.keys(nuRow).find(k=>k.toLowerCase().includes('utrikes'));
                if(kIn) n_inrikes = parseFloat(nuRow[kIn]);
                if(kUt) n_utrikes = parseFloat(nuRow[kUt]);
            }
        }
        if (syssBasdata['Syss_utrikes']) {
            const duRow = syssBasdata['Syss_utrikes'].find(r => extractYear(r) == y && getKon(r) === 'totalt');
            if(duRow) {
                let kIn = Object.keys(duRow).find(k=>k.toLowerCase().includes('inrikes') || k.toLowerCase().includes('sverige'));
                let kUt = Object.keys(duRow).find(k=>k.toLowerCase().includes('utrikes'));
                if(kIn) d_inrikes = parseFloat(duRow[kIn]);
                if(kUt) d_utrikes = parseFloat(duRow[kUt]);
            }
        }

        let pop16_74 = 0;
        for (let a = 16; a <= 74; a++) {
            pop16_74 += getPopForAge(popData, y, a);
        }

        // Bro: SCB eftersläpning
        if (pop16_74 === 0 && nattTotalt > 0) {
            let futureBridgePop = 0;
            for (let fy = y + 1; fy <= y + 5; fy++) {
                let tempPop = 0;
                for (let a = 16; a <= 74; a++) { tempPop += getPopForAge(popData, fy, a); }
                if (tempPop > 0) { futureBridgePop = tempPop; break; }
            }
            pop16_74 = futureBridgePop > 0 ? futureBridgePop : (nattTotalt / 0.70);
        }
        
        let motorRate = null;
        if (pop16_74 > 0 && nattTotalt > 0) motorRate = (nattTotalt / pop16_74) * 100;

        let ageRates = null;
        const nattAlderData = syssBasdata['Natt_ålder'] || syssBasdata['Natt_alder'] || [];
        let nattAlderRowsForYear = nattAlderData.filter(r => extractYear(r) == y);
        
        let nattAlderRow = null;
        if (nattAlderRowsForYear.length > 0) {
            let totRow = nattAlderRowsForYear.find(r => getKon(r) === 'totalt');
            if (totRow) {
                nattAlderRow = totRow;
            } else {
                nattAlderRow = {};
                nattAlderRowsForYear.forEach(r => {
                    let kon = getKon(r);
                    if (kon === 'män' || kon === 'kvinnor') {
                        Object.keys(r).forEach(k => {
                            if (typeof r[k] === 'number' || (!isNaN(parseFloat(r[k])) && String(r[k]).trim() !== '')) {
                                nattAlderRow[k] = (nattAlderRow[k] || 0) + parseFloat(r[k]);
                            } else if (k === 'År' || k === 'år' || k === 'ÅR') {
                                nattAlderRow[k] = r[k];
                            }
                        });
                    }
                });
            }
        }
        
        if (nattAlderRow && popData.length > 0) {
            ageRates = {};
            let recordsForYear = popData.filter(r => String(r.tid).replace('(Prognos)','').trim() === String(y));
            let useGenderForYear = recordsForYear.some(r => String(r.kön).trim().toLowerCase() === 'män' || String(r.kön).trim().toLowerCase() === 'kvinnor');

            Object.keys(nattAlderRow).forEach(key => {
                if (String(key).toLowerCase().includes('totalt')) return;

                const match = String(key).match(/(\d+)\s*-\s*(\d+)/);
                if (match) {
                    const minAge = parseInt(match[1]);
                    const maxAge = parseInt(match[2]);
                    if ((maxAge - minAge) > 5) return;

                    const workers = parseFloat(nattAlderRow[key]) || 0;
                    let groupPop = 0;
                    
                    recordsForYear.forEach(r => {
                        if (!String(r.ålder).toLowerCase().includes('totalt')) {
                            if (useGenderForYear && String(r.kön).trim().toLowerCase() !== 'män' && String(r.kön).trim().toLowerCase() !== 'kvinnor') return;
                            const aMatch = String(r.ålder).match(/\d+/);
                            if (aMatch) {
                                const a = parseInt(aMatch[0]);
                                if (a >= minAge && a <= maxAge) groupPop += (r.Befolkning || 0);
                            }
                        }
                    });
                    if (groupPop > 0) ageRates[key] = { min: minAge, max: maxAge, rate: workers / groupPop };
                }
            });
        }

        let baseNetCommute = hasPendlingData ? (inpendlingTot - utpendlingTot) : 0;

        if (d_man != null && d_kvinna != null && dagTotalt == null) dagTotalt = d_man + d_kvinna;
        if (n_man != null && n_kvinna != null && nattTotalt == null) nattTotalt = n_man + n_kvinna;

        histDataStore[y] = { 
            demand: dagTotalt, 
            supply: nattTotalt, 
            inpendling: hasPendlingData ? inpendlingTot : null,
            utpendling: hasPendlingData ? utpendlingTot : null,
            netCommuting: hasPendlingData ? baseNetCommute : null,
            totalSupply: (nattTotalt != null && hasPendlingData) ? (nattTotalt + baseNetCommute) : null,
            pop: pop16_74 > 0 ? pop16_74 : null,
            rate: motorRate,
            displayRate: faktiskRate !== null ? faktiskRate : null,
            syssGradM: syssGradM,
            syssGradK: syssGradK,
            syss_in_tot: syss_in_tot,
            syss_ut_tot: syss_ut_tot,
            brp: brpPerSyss,
            extrapolatedBrp: null,
            arbetsloshetPct: arbetsloshetPct,
            langtidsPct: langtidsPct,
            arb_inrikes: arb_inrikes,
            arb_utrikes: arb_utrikes,
            larb_inrikes: larb_inrikes,
            larb_utrikes: larb_utrikes,
            n_inrikes: n_inrikes,
            n_utrikes: n_utrikes,
            d_inrikes: d_inrikes,
            d_utrikes: d_utrikes,
            d_man: d_man,
            d_kvinna: d_kvinna,
            n_man: n_man,
            n_kvinna: n_kvinna,
            arb_man: arb_man,
            arb_kvinna: arb_kvinna,
            larb_man: larb_man,
            larb_kvinna: larb_kvinna,
            ageRates: Object.keys(ageRates || {}).length > 0 ? ageRates : null
        };
    });

    let brpCAGR = 0.015; 
    if (brpHistory.length >= 2) {
        let first = brpHistory[Math.max(0, brpHistory.length - 11)];
        let last = brpHistory[brpHistory.length - 1];
        let yearsDiff = last.year - first.year;
        if (yearsDiff > 0 && first.val > 0) { brpCAGR = Math.pow(last.val / first.val, 1 / yearsDiff) - 1; }
    }

    // SCB Minne - fyll luckor
    let lastKnown = {};
    sortedYears.forEach(y => {
        let d = histDataStore[y];
        if (!d) return;
        ['displayRate','syss_in_tot','syss_ut_tot','arbetsloshetPct','arb_inrikes','arb_utrikes','arb_man','arb_kvinna','langtidsPct','larb_inrikes','larb_utrikes','larb_man','larb_kvinna','n_inrikes','n_utrikes','d_inrikes','d_utrikes','n_man','n_kvinna','d_man','d_kvinna','ageRates','syssGradM','syssGradK','rate'].forEach(k => {
            if (d[k] != null) lastKnown[k] = (typeof d[k] === 'object') ? JSON.parse(JSON.stringify(d[k])) : d[k];
            else if (lastKnown[k] != null) d[k] = (typeof lastKnown[k] === 'object') ? JSON.parse(JSON.stringify(lastKnown[k])) : lastKnown[k];
        });

        if (d.brp === null && lastKnownBRP !== null && y > lastKnownBRPYear) {
            let yearsAhead = y - lastKnownBRPYear;
            d.extrapolatedBrp = lastKnownBRP * Math.pow(1 + brpCAGR, yearsAhead);
        } else {
            d.extrapolatedBrp = d.brp;
        }
    });

    histDataStore['brpCAGR'] = brpCAGR;
    histDataStore['lastKnownBRP'] = lastKnownBRP;

    baseYear = sortedYears[0];
    for (let i = sortedYears.length - 1; i >= 0; i--) {
        let y = sortedYears[i];
        if (histDataStore[y].demand != null && histDataStore[y].supply != null) {
            baseYear = y; break;
        }
    }

    histYearsGlobal = sortedYears.filter(y => y <= baseYear);
    for (let y in histDataStore) {
        const numericY = parseInt(y);
        if (!isNaN(numericY) && numericY > baseYear && y !== 'brpCAGR' && y !== 'lastKnownBRP') {
            delete histDataStore[y];
        }
    }
}

// ==========================================
// SIMULERING OCH DYNAMISK JÄMVIKT
// ==========================================
function runSimulation() {
    const forecastYears = PROGNOS_SLUTAR - baseYear;
    if (forecastYears <= 0) {
        alert(`Slutåret för prognosen (${PROGNOS_SLUTAR}) måste ligga efter basåret (${baseYear}).`);
        return;
    }

    const btn = document.getElementById('simBtn');
    if(btn) {
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i> Beräknar...';
        btn.classList.add('opacity-75', 'cursor-not-allowed');
    }

    setTimeout(() => {
        try {
            const simModeEl = document.getElementById('simMode');
            const simMode = simModeEl ? simModeEl.value : 'full';
            const popSourceEl = document.getElementById('popSource');
            const popSource = popSourceEl ? popSourceEl.value : 'officiell';
            const causalityModeEl = document.getElementById('causalityMode');
            const causalityMode = causalityModeEl ? causalityModeEl.value : 'analytic';
            const pendlingTypeEl = document.getElementById('pendlingType');
            const pendlingType = pendlingTypeEl ? pendlingTypeEl.value : 'pct';

            const jobGrowthPct = parseFloat(document.getElementById('jobGrowthSlider')?.value) || 0; 
            const syssGradChangeOverall = parseFloat(document.getElementById('syssGradSlider')?.value) || 0;
            const studentChange = parseFloat(document.getElementById('studentSlider')?.value) || 0;
            const civIngChange = parseFloat(document.getElementById('civIngSlider')?.value) || 0;
            
            let inpendlingChange = 0, utpendlingChange = 0, distansChange = 0, regionChangeMin = 0;
            
            if (simMode === 'full') {
                inpendlingChange = parseFloat(document.getElementById('inpendlingSlider')?.value) || 0;
                utpendlingChange = parseFloat(document.getElementById('utpendlingSlider')?.value) || 0;
                distansChange = parseFloat(document.getElementById('distansSlider')?.value) || 0;
                regionChangeMin = parseFloat(document.getElementById('regionSlider')?.value) || 0;
            }

            currentShocks = [];
            document.querySelectorAll('.shock-checkbox:checked').forEach(cb => {
                const idx = parseInt(cb.value);
                if (syssConfig['Etableringschocker'] && syssConfig['Etableringschocker'][idx]) {
                    currentShocks.push(syssConfig['Etableringschocker'][idx]);
                }
            });

            const base = histDataStore[baseYear];
            if (!base) throw new Error("Kunde inte hitta data för basåret.");

            progDataStore = {};
            
            let cumulativeExtraStudents = 0;
            let extraRegionSupplyTotal = 0;
            let beraknadeKommuner = 0;
            
            if (regionChangeMin > 0 && syssConfig['Inom_en_timme']) {
                syssConfig['Inom_en_timme'].forEach(row => {
                    let inpendling = parseFloat(row['Inpendling_2024']) || 0;
                    let bilMin = parseFloat(row['Bil_minuter']);
                    let kollMin = parseFloat(row['Kollektivt_minuter']);
                    let basTid = isNaN(bilMin) ? kollMin : bilMin; 
                    
                    if (inpendling > 0 && !isNaN(basTid) && basTid > 0) {
                        let nyTid = Math.max(10, basTid - regionChangeMin); 
                        let okning = inpendling * (Math.pow(basTid / nyTid, 1.5) - 1);
                        extraRegionSupplyTotal += okning;
                        beraknadeKommuner++;
                    }
                });
            }

            const baselineDemand = base.demand != null ? Number(base.demand) : 0;
            const baselineSupply = base.supply != null ? Number(base.supply) : 0;
            const baselineGap = Math.max(0, baselineDemand - baselineSupply);
            const distansBoostTotal = baselineGap * (distansChange / 100);
            
            const targetVirtualSupply = extraRegionSupplyTotal + distansBoostTotal;
            const brpCAGR = histDataStore['brpCAGR'] || 0.015;
            const baseExtrapolatedBRP = histDataStore['lastKnownBRP'] || 1000;
            const syssGradDemandBoostTotal = (base.pop != null ? base.pop : 0) * (syssGradChangeOverall / 100);
            
            let totalShockDemandAccumulated = 0;
            let totalShockDemandAccumulatedM = 0;
            let totalShockDemandAccumulatedK = 0;

            const ageRates = base.ageRates; 
            let isAgeWeighted = false;

            const base_n_ut = base.n_utrikes || 0;
            const base_n_in = base.n_inrikes || 0;
            const base_d_ut = base.d_utrikes || 0;
            const base_d_in = base.d_inrikes || 0;
            const share_n_ut = (base_n_ut + base_n_in > 0) ? (base_n_ut / (base_n_ut + base_n_in)) : 0.2;
            const share_d_ut = (base_d_ut + base_d_in > 0) ? (base_d_ut / (base_d_ut + base_d_in)) : 0.2;

            const base_d_man = base.d_man || 0;
            const base_d_kvinna = base.d_kvinna || 0;
            const share_d_man = (base_d_man + base_d_kvinna > 0) ? (base_d_man / (base_d_man + base_d_kvinna)) : 0.5;

            const base_n_man = base.n_man || 0;
            const base_n_kvinna = base.n_kvinna || 0;
            const share_n_man = (base_n_man + base_n_kvinna > 0) ? (base_n_man / (base_n_man + base_n_kvinna)) : 0.5;

            let dynPopAccumulated = 0;
            let dynLaborAccumulated = 0;
            
            let futureInpendlingBase = base.inpendling != null ? Number(base.inpendling) : 0;
            let futureUtpendlingBase = base.utpendling != null ? Number(base.utpendling) : 0;

            let activePopData = popSource === 'fryst' ? [] : (useCustomPop && customPopData ? customPopData : popData);

            for (let i = 1; i <= forecastYears; i++) {
                const forecastYear = baseYear + i;
                
                let shockDemandThisYear = 0;
                let shockDemandThisYearM = 0;
                let shockDemandThisYearK = 0;

                currentShocks.forEach(shock => {
                    if (parseInt(shock['År']) === forecastYear) {
                        const val = parseFloat(shock['Antal_Jobb']) || 0;
                        shockDemandThisYear += val;
                        
                        let mShare = share_d_man; 
                        if (shock['Andel_Män'] !== undefined && shock['Andel_Män'] !== null && String(shock['Andel_Män']).trim() !== '') {
                            let andelMStr = String(shock['Andel_Män']).trim();
                            let parsed = parseFloat(andelMStr.replace('%', '').replace(',', '.'));
                            if (!isNaN(parsed)) {
                                mShare = andelMStr.includes('%') || parsed > 1 ? parsed / 100 : parsed;
                                if (mShare > 1) mShare = 1;
                                if (mShare < 0) mShare = 0;
                            }
                        }
                        shockDemandThisYearM += val * mShare;
                        shockDemandThisYearK += val * (1 - mShare);
                    }
                });
                totalShockDemandAccumulated += shockDemandThisYear;
                totalShockDemandAccumulatedM += shockDemandThisYearM;
                totalShockDemandAccumulatedK += shockDemandThisYearK;
                
                const demandGrowthFactor = 1 + ((jobGrowthPct / 100) * (i / forecastYears));
                const futureDemand = (baselineDemand * demandGrowthFactor) + (syssGradDemandBoostTotal * (i / forecastYears)) + totalShockDemandAccumulated;

                let futurePop = 0;
                let hasPopDataForYear = false; 
                
                if (popSource === 'fryst' || activePopData.length === 0) {
                    futurePop = base.pop != null ? Number(base.pop) : 0;
                } else {
                    futurePop = getPopForYear(activePopData, forecastYear);
                    if (futurePop > 0) {
                        hasPopDataForYear = true;
                    } else {
                        futurePop = base.pop != null ? Number(base.pop) : 0; 
                    }
                }

                // Hantering av Civilingenjörer / Övriga studenter
                const baseTotalStudents = annualStudentsMap[forecastYear] !== undefined ? annualStudentsMap[forecastYear] : avgAnnualStudents;
                let extraStudentsThisYear = 0;
                
                if (useSpecificCivIng) {
                    const baseCivIng = annualCivIngMap[forecastYear] !== undefined ? annualCivIngMap[forecastYear] : avgAnnualCivIng;
                    const otherStudents = Math.max(0, baseTotalStudents - baseCivIng);
                    
                    const extraOther = otherStudents * (studentChange / 100);
                    const extraCivIng = baseCivIng * (civIngChange / 100);
                    extraStudentsThisYear = extraOther + extraCivIng;
                } else {
                    extraStudentsThisYear = baseTotalStudents * (studentChange / 100);
                }

                cumulativeExtraStudents += extraStudentsThisYear;

                let futureSupply = 0;
                let futureSupplyM = 0;
                let futureSupplyK = 0;
                let futureRate = 0;
                
                if (ageRates && popSource !== 'fryst' && activePopData.length > 0 && hasPopDataForYear) {
                    isAgeWeighted = true;
                    Object.values(ageRates).forEach(group => {
                        let groupFuturePop = 0;
                        let groupFuturePopM = 0;
                        let groupFuturePopK = 0;

                        let records = activePopData.filter(r => String(r.tid).replace('(Prognos)','').trim() === String(forecastYear));
                        let useGender = records.some(r => String(r.kön).trim().toLowerCase() === 'män' || String(r.kön).trim().toLowerCase() === 'kvinnor');
                        
                        records.forEach(r => {
                            if (!String(r.ålder).toLowerCase().includes('totalt')) {
                                if (useGender && String(r.kön).trim().toLowerCase() !== 'män' && String(r.kön).trim().toLowerCase() !== 'kvinnor') return;
                                const aMatch = String(r.ålder).match(/\d+/);
                                if (aMatch) {
                                    const a = parseInt(aMatch[0]);
                                    if (a >= group.min && a <= group.max) {
                                        groupFuturePop += (r.Befolkning || 0);
                                        if (String(r.kön).trim().toLowerCase() === 'män') groupFuturePopM += (r.Befolkning || 0);
                                        else if (String(r.kön).trim().toLowerCase() === 'kvinnor') groupFuturePopK += (r.Befolkning || 0);
                                        else { 
                                            groupFuturePopM += (r.Befolkning || 0) * share_n_man; 
                                            groupFuturePopK += (r.Befolkning || 0) * (1 - share_n_man); 
                                        }
                                    }
                                }
                            }
                        });
                        
                        let sliderOffset = getSliderOffsetForAge(group.min); 
                        const specificTargetRate = group.rate + (sliderOffset / 100); 
                        const currentSpecificRate = group.rate + ((specificTargetRate - group.rate) * (i / forecastYears));
                        
                        futureSupply += (groupFuturePop * currentSpecificRate);
                        futureSupplyM += (groupFuturePopM * currentSpecificRate);
                        futureSupplyK += (groupFuturePopK * currentSpecificRate);
                    });
                    
                    futureSupply += cumulativeExtraStudents;
                    futureSupplyM += cumulativeExtraStudents * share_n_man;
                    futureSupplyK += cumulativeExtraStudents * (1 - share_n_man);
                    futureRate = futurePop > 0 ? (futureSupply / futurePop) * 100 : 0;
                } else {
                    const targetRate = (base.rate || base.displayRate || 80) + syssGradChangeOverall;
                    futureRate = (base.rate || base.displayRate || 80) + (((targetRate) - (base.rate || base.displayRate || 80)) * (i / forecastYears));
                    futureSupply = (futurePop * (futureRate / 100)) + cumulativeExtraStudents;
                    futureSupplyM = futureSupply * share_n_man;
                    futureSupplyK = futureSupply * (1 - share_n_man);
                }

                futureSupply += dynLaborAccumulated;
                futureSupplyM += dynLaborAccumulated * share_n_man;
                futureSupplyK += dynLaborAccumulated * (1 - share_n_man);
                
                let futureInpendling = futureInpendlingBase;
                let futureUtpendling = futureUtpendlingBase;

                if (simMode === 'full') {
                    if (pendlingType === 'pct') {
                        futureInpendling = futureInpendlingBase * (1 + ((inpendlingChange/100) * (i/forecastYears)));
                        futureUtpendling = futureUtpendlingBase * (1 + ((utpendlingChange/100) * (i/forecastYears)));
                    } else {
                        futureInpendling = Math.max(0, futureInpendlingBase + (inpendlingChange * (i/forecastYears)));
                        futureUtpendling = Math.max(0, futureUtpendlingBase + (utpendlingChange * (i/forecastYears)));
                    }
                }

                const explicitNetCommuting = futureInpendling - futureUtpendling;
                const virtualSupply = targetVirtualSupply * (i / forecastYears);
                let futureTotalSupply = futureSupply + explicitNetCommuting + virtualSupply;

                let inducedPopThisYear = 0;
                let inducedLaborThisYear = 0;
                let reqForeignLabor = 0;
                
                if (causalityMode === 'dynamic') {
                    const currentGap = futureDemand - futureTotalSupply;
                    
                    if (currentGap > 0) {
                        inducedLaborThisYear = currentGap;
                        const migrantEl = document.getElementById('migrantSyssSlider');
                        const userSyssAdjustment = (migrantEl ? parseFloat(migrantEl.value) : 10) / 100;
                        const empRate = Math.max(0.01, globalMigrantEmploymentRate + userSyssAdjustment);
                        
                        inducedPopThisYear = currentGap / empRate;
                        
                        futureSupply += inducedLaborThisYear;
                        futureTotalSupply += inducedLaborThisYear;
                        futurePop += inducedPopThisYear;
                        dynPopAccumulated += inducedPopThisYear;
                        
                        futureSupplyM += inducedLaborThisYear * share_n_man;
                        futureSupplyK += inducedLaborThisYear * (1 - share_n_man);
                        dynLaborAccumulated += inducedLaborThisYear; 

                        const maxDomesticNetWorkers = 500; 
                        if (inducedLaborThisYear > maxDomesticNetWorkers) {
                            reqForeignLabor = inducedLaborThisYear - maxDomesticNetWorkers;
                        }
                    }
                }

                const baseDisplayRate = base.displayRate != null ? Number(base.displayRate) : 80;
                const displayTarget = baseDisplayRate + syssGradChangeOverall;
                const futureDisplayRate = baseDisplayRate + ((displayTarget - baseDisplayRate) * (i / forecastYears));

                const futureBrpPerSyss = baseExtrapolatedBRP * Math.pow(1 + brpCAGR, i);
                const futureTotalBrpMkr = (futureBrpPerSyss && futureDemand) ? (futureBrpPerSyss * futureDemand) / 1000 : null;

                let futureArbetsloshet = base.arbetsloshetPct != null ? base.arbetsloshetPct - syssGradChangeOverall * (i/forecastYears) : null;

                let base_d_m_component = base_d_man * demandGrowthFactor + (syssGradDemandBoostTotal * (i / forecastYears)) * share_d_man;
                let base_d_k_component = base_d_kvinna * demandGrowthFactor + (syssGradDemandBoostTotal * (i / forecastYears)) * (1 - share_d_man);

                progDataStore[forecastYear] = {
                    demand: futureDemand,
                    supply: futureSupply,
                    inpendling: futureInpendling,
                    utpendling: futureUtpendling,
                    explicitNetCommuting: explicitNetCommuting,
                    virtualSupply: virtualSupply, 
                    totalSupply: futureTotalSupply,
                    antalKommunerBeraknade: beraknadeKommuner,
                    pop: futurePop,
                    rate: futureRate,
                    isAgeWeighted: isAgeWeighted,
                    displayRate: futureDisplayRate,
                    inducedPop: inducedPopThisYear,
                    reqForeignLabor: reqForeignLabor,
                    totalBrpMkr: futureTotalBrpMkr,
                    n_man: futureSupplyM,
                    n_kvinna: futureSupplyK,
                    n_utrikes: futureSupply * share_n_ut,
                    n_inrikes: futureSupply * (1 - share_n_ut),
                    d_utrikes: futureDemand * share_d_ut,
                    d_inrikes: futureDemand * (1 - share_d_ut),
                    d_man: base_d_m_component + totalShockDemandAccumulatedM,
                    d_kvinna: base_d_k_component + totalShockDemandAccumulatedK,
                    syss_in_tot: base.syss_in_tot != null ? base.syss_in_tot + syssGradChangeOverall * (i/forecastYears) : null,
                    syss_ut_tot: base.syss_ut_tot != null ? base.syss_ut_tot + syssGradChangeOverall * (i/forecastYears) : null,
                    arbetsloshetPct: futureArbetsloshet,
                    arb_inrikes: base.arb_inrikes != null ? base.arb_inrikes - syssGradChangeOverall * (i/forecastYears) : null,
                    arb_utrikes: base.arb_utrikes != null ? base.arb_utrikes - syssGradChangeOverall * (i/forecastYears) : null,
                    arb_man: base.arb_man != null ? base.arb_man - syssGradChangeOverall * (i/forecastYears) : null,
                    arb_kvinna: base.arb_kvinna != null ? base.arb_kvinna - syssGradChangeOverall * (i/forecastYears) : null,
                    larb_inrikes: base.larb_inrikes != null ? base.larb_inrikes : null,
                    larb_utrikes: base.larb_utrikes != null ? base.larb_utrikes : null,
                    larb_man: base.larb_man != null ? base.larb_man : null,
                    larb_kvinna: base.larb_kvinna != null ? base.larb_kvinna : null,
                    langtidsPct: base.langtidsPct
                };
            }

            if (typeof buildDropdowns === 'function') buildDropdowns(); 
            if (typeof updateDashboard === 'function') updateDashboard(false); 

            if(btn) {
                btn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Klar!';
                btn.classList.replace('bg-slate-800', 'bg-green-600');
                setTimeout(() => {
                    btn.innerHTML = '<i class="fa-solid fa-gears mr-1"></i> Kör';
                    btn.classList.replace('bg-green-600', 'bg-slate-800');
                    btn.classList.remove('opacity-75', 'cursor-not-allowed');
                }, 2000);
            }

        } catch (err) {
            console.error("Krasch i simuleringen:", err);
            if(btn) {
                btn.innerHTML = `<i class="fa-solid fa-triangle-exclamation mr-1"></i> Krasch: ${err.message}`;
                btn.classList.replace('bg-slate-800', 'bg-red-600');
                btn.classList.remove('opacity-75', 'cursor-not-allowed');
            }
        }
    }, 100);
}