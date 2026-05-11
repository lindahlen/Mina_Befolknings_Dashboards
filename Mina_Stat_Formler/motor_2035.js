// ==========================================
// Kalkylator Motor 2035 - Kärnlogik & Databearbetning
// ==========================================

var PROGNOS_SLUTAR = 2035;

// GLOBALA VARIABLER (Måste finnas för att grafer_2035.js ska kunna läsa dem)
var syssBasdata = {};
var syssConfig = {};
var popData = []; 
var customPopData = null; 
var useCustomPop = false; 

var histDataStore = {}; 
var progDataStore = {}; 
var savedProjectedData = null; 

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
var currentNaringScale = 100; 
var currentBKvotPeriod = 'Alla'; 

var takEffekter = {
    maxSyssGrad: 85.0,
    minArbetsloshet: 3.5,
    karnaLangtidsarbetslosa: 3.0,
    maxInpendlingsandel: 25.0,
    maxSyssGradAldre: 25.0,
    kapacitetstakInfrastruktur: 30000,
    studentAbsorptionsTak: 50
};

// STANDARDVÄRDEN (Ifall Excel-filen saknas)
window.scenarioSettings = {
    base: { jobGrowth: 0, syssGrad: 0, student: 0, inpendling: 0, utpendling: 0, distans: 0, region: 0, migrantSyss: 10, naringScale: 100, bosattningskvotPeriod: 'Alla', syssAge: {} },
    high: { jobGrowth: 5, syssGrad: 2.0, student: 10, inpendling: 10, utpendling: 5, distans: 10, region: 15, migrantSyss: 15, naringScale: 120, bosattningskvotPeriod: 'Alla', syssAge: {} },
    low: { jobGrowth: -5, syssGrad: -1.0, student: -2, inpendling: -5, utpendling: -2, distans: 0, region: 0, migrantSyss: 5, naringScale: 50, bosattningskvotPeriod: 'Alla', syssAge: {} },
    stagnant: { jobGrowth: -2, syssGrad: 0, student: 0, inpendling: 0, utpendling: 0, distans: 0, region: 0, migrantSyss: 10, naringScale: 20, bosattningskvotPeriod: 'Alla', syssAge: {} }
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
    
    let useGender = records.some(r => String(r.kön).trim().toLowerCase() === 'män' || String(r.kön).trim().toLowerCase() === 'kvinnor');
    records.forEach(r => {
        if (!String(r.ålder).toLowerCase().includes('totalt')) {
            if (useGender && String(r.kön).trim().toLowerCase() !== 'män' && String(r.kön).trim().toLowerCase() !== 'kvinnor') return;
            const match = String(r.ålder).match(/\d+/);
            if (match && parseInt(match[0]) === targetAge) pop += (r.Befolkning || 0);
        }
    });
    return pop;
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
             if(aYears.length > 0) {
                 const latestY = aYears[aYears.length - 1];
                 bYearData = popData.filter(r => String(r.tid).trim() === String(latestY) && !String(r.ålder).includes('Totalt'));
             }
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

function extractOriginPop(datasetName, targetYear) {
    let inr = 0, utr = 0, found = false;
    const ds = syssBasdata[datasetName] || [];
    const records = ds.filter(r => extractYear(r) == targetYear);
    if (records.length === 0) return null;
    
    let hasTotalRow = records.some(r => getKon(r) === 'totalt');

    records.forEach(r => {
        let kon = getKon(r);
        if (hasTotalRow && kon !== 'totalt' && kon !== null) return; 

        Object.keys(r).forEach(k => {
            let kl = k.toLowerCase().replace(/_/g, ' ');
            if (kl === 'inrikes född' || kl.includes('inrikes')) {
                inr += parseFloat(r[k]) || 0; found = true;
            } else if (kl === 'utrikes född' || kl.includes('utrikes')) {
                utr += parseFloat(r[k]) || 0; found = true;
            }
        });
    });
    return found ? { inr, utr } : null;
}

// ROBUST SÖKFUNKTION FÖR SCB TABELLER
const getScbVal = (row, searchTerms, excludeTerms=[]) => {
    if (!row) return null;
    for(let key of Object.keys(row)) {
        let k = key.toLowerCase().replace(/_/g, ' ').replace(/\s+/g, ' ').trim();
        if (searchTerms.some(term => k.includes(term)) && !excludeTerms.some(term => k.includes(term))) {
            let v = parseFloat(row[key]);
            if(!isNaN(v)) return v;
        }
    }
    return null;
};

// ==========================================
// UI-KONTROLLER FÖR ATT GARANTERA FUNKTIONALITET
// ==========================================
window.toggleSimMode = function() {
    const mode = document.getElementById('simMode').value;
    const geoPanel = document.getElementById('geoPanel');
    if (geoPanel) {
        if (mode === 'local') geoPanel.classList.add('opacity-40', 'pointer-events-none');
        else geoPanel.classList.remove('opacity-40', 'pointer-events-none');
    }
    if (typeof window.updateDashboard === 'function') window.updateDashboard(true); 
};

window.updatePendlingUI = function() {
    const type = document.getElementById('pendlingType').value;
    const inSlider = document.getElementById('inpendlingSlider');
    const utSlider = document.getElementById('utpendlingSlider');
    if (inSlider && utSlider) {
        if (type === 'pct') {
            inSlider.min = -50; inSlider.max = 50; inSlider.step = 1;
            utSlider.min = -50; utSlider.max = 50; utSlider.step = 1;
        } else {
            inSlider.min = -5000; inSlider.max = 5000; inSlider.step = 50;
            utSlider.min = -5000; utSlider.max = 5000; utSlider.step = 50;
        }
        window.updatePendlingValue('inpendlingSlider', 'inpendlingVal');
        window.updatePendlingValue('utpendlingSlider', 'utpendlingVal');
    }
};

window.updatePendlingValue = function(sliderId, textId) {
    const el = document.getElementById(sliderId);
    const typeEl = document.getElementById('pendlingType');
    if (el && typeEl) {
        const val = el.value;
        const prefix = val > 0 ? '+' : '';
        const suffix = typeEl.value === 'pct' ? '%' : ' pers';
        const textEl = document.getElementById(textId);
        if (textEl) textEl.innerText = prefix + val + suffix;
    }
};

window.toggleCivIng = function() {
    const container = document.getElementById('civIngContainer');
    const icon = document.getElementById('civIngToggleIcon');
    if (container && icon) {
        useSpecificCivIng = !useSpecificCivIng;
        if (useSpecificCivIng) {
            container.classList.remove('hidden');
            icon.classList.replace('fa-circle-plus', 'fa-circle-minus');
            icon.classList.replace('text-sky-600', 'text-red-500');
            icon.title = "Återgå till gemensam Kvarstannandegrad";
        } else {
            container.classList.add('hidden');
            icon.classList.replace('fa-circle-minus', 'fa-circle-plus');
            icon.classList.replace('text-red-500', 'text-sky-600');
            icon.title = "Dela upp på Civilingenjörer och Övriga";
            document.getElementById('civIngSlider').value = 0;
            document.getElementById('civIngVal').innerText = 'Baslinje';
        }
        window.runSimulation();
    }
};

window.setScenario = function(type) {
    if (!window.scenarioSettings || !window.scenarioSettings[type]) return;
    const s = window.scenarioSettings[type];
    
    document.getElementById('jobGrowthSlider').value = s.jobGrowth || 0;
    document.getElementById('jobGrowthVal').innerText = (s.jobGrowth > 0 ? '+' : '') + (s.jobGrowth || 0) + '%';
    document.getElementById('syssGradSlider').value = s.syssGrad || 0;
    document.getElementById('syssGradVal').innerText = (s.syssGrad > 0 ? '+' : '') + (s.syssGrad || 0) + '%-enh';
    document.getElementById('studentSlider').value = s.student || 0;
    document.getElementById('studentVal').innerText = (s.student > 0 ? '+' : '') + (s.student || 0) + '%-enh';
    
    const migrantSyssSlider = document.getElementById('migrantSyssSlider');
    if(migrantSyssSlider) {
        migrantSyssSlider.value = s.migrantSyss !== undefined ? s.migrantSyss : 10;
        document.getElementById('migrantSyssVal').innerText = (s.migrantSyss > 0 ? '+' : '') + (s.migrantSyss !== undefined ? s.migrantSyss : 10) + '%-enh';
    }

    const civIngSlider = document.getElementById('civIngSlider');
    if(civIngSlider) {
        civIngSlider.value = 0;
        document.getElementById('civIngVal').innerText = 'Baslinje';
    }

    const pendType = document.getElementById('pendlingType');
    if (pendType) pendType.value = 'pct';
    window.updatePendlingUI();
    
    const inSlider = document.getElementById('inpendlingSlider');
    if (inSlider) {
        inSlider.value = s.inpendling || 0;
        window.updatePendlingValue('inpendlingSlider', 'inpendlingVal');
    }
    const utSlider = document.getElementById('utpendlingSlider');
    if (utSlider) {
        utSlider.value = s.utpendling || 0;
        window.updatePendlingValue('utpendlingSlider', 'utpendlingVal');
    }
    
    document.getElementById('distansSlider').value = s.distans || 0;
    document.getElementById('distansVal').innerText = (s.distans > 0 ? '+' : '') + (s.distans || 0) + '%';
    document.getElementById('regionSlider').value = s.region || 0;
    document.getElementById('regionVal').innerText = (s.region == 0 || !s.region) ? 'Dagens nivå' : '+' + s.region + ' min';
    
    if (typeof window.currentNaringScale !== 'undefined') window.currentNaringScale = s.naringScale !== undefined ? s.naringScale : 100;
    if (typeof window.currentBKvotPeriod !== 'undefined') window.currentBKvotPeriod = s.bosattningskvotPeriod !== undefined ? s.bosattningskvotPeriod : 'Alla';
    
    if (s.syssAge) {
        for (let key in s.syssAge) {
            let slider = document.getElementById(key);
            let valEl = document.getElementById('val_' + key);
            if (slider) slider.value = s.syssAge[key];
            if (valEl) valEl.innerText = (s.syssAge[key] > 0 ? '+' : '') + s.syssAge[key];
        }
    }

    window.runSimulation();
};

window.resetSimulation = function() {
    const simMode = document.getElementById('simMode');
    if (simMode) {
        simMode.value = 'full';
        window.toggleSimMode();
    }
    
    document.getElementById('jobGrowthSlider').value = 0;
    document.getElementById('jobGrowthVal').innerText = '+0%';
    document.getElementById('syssGradSlider').value = 0;
    document.getElementById('syssGradVal').innerText = 'Oförändrad';
    document.getElementById('studentSlider').value = 0;
    document.getElementById('studentVal').innerText = 'Baslinje';
    
    if (useSpecificCivIng) window.toggleCivIng(); 
    
    const pendType = document.getElementById('pendlingType');
    if (pendType) pendType.value = 'pct';
    window.updatePendlingUI();
    
    const inSlider = document.getElementById('inpendlingSlider');
    if (inSlider) {
        inSlider.value = 0;
        document.getElementById('inpendlingVal').innerText = '+0%';
    }
    const utSlider = document.getElementById('utpendlingSlider');
    if (utSlider) {
        utSlider.value = 0;
        document.getElementById('utpendlingVal').innerText = '+0%';
    }
    
    document.getElementById('distansSlider').value = 0;
    document.getElementById('distansVal').innerText = 'Baslinje';
    document.getElementById('regionSlider').value = 0;
    document.getElementById('regionVal').innerText = 'Dagens nivå';
    
    progDataStore = {}; 
    savedProjectedData = null;
    
    const saveBtn = document.getElementById('saveBtn');
    if(saveBtn) {
        saveBtn.innerHTML = '<i class="fa-solid fa-code-compare mr-1"></i> Jämför';
        saveBtn.classList.remove('bg-red-100', 'text-red-800', 'hover:bg-red-200');
        saveBtn.classList.add('bg-indigo-100', 'text-indigo-800', 'hover:bg-indigo-200');
    }
    const startYearSelect = document.getElementById('startYearSelect');
    if (startYearSelect) startYearSelect.classList.remove('hidden');

    document.querySelectorAll('input[id^="syssAge"]').forEach(slider => {
        slider.value = 0;
        let valEl = document.getElementById('val_' + slider.id);
        if (valEl) valEl.innerText = '0';
    });

    if (typeof window.buildDropdowns === 'function') window.buildDropdowns();
    if (typeof window.updateDashboard === 'function') window.updateDashboard(false);
};

// ==========================================
// UPPSTART OCH INLÄSNING (DOMContentLoaded)
// ==========================================
window.addEventListener('DOMContentLoaded', () => {
    const isLocal = window.location.protocol === 'file:';
    const cb = isLocal ? '' : '?v=' + new Date().getTime(); 

    // Säkrad initiering av åldersreglage
    const ageContainer = document.getElementById('ageSlidersContainer');
    if (ageContainer && ageContainer.innerHTML.trim() === '') {
        let htmlContent = '';
        ['16-19','20-24','25-29','30-34','35-39','40-44','45-49','50-54','55-59','60-64','65-69','70-74'].forEach(a => {
            let id = 'syssAge' + a.replace('-', '_');
            htmlContent += `
            <div class="flex justify-between items-center mb-1">
                <span class="w-12 text-gray-700">${a}</span>
                <input type="range" id="${id}" min="-15" max="15" step="0.5" value="0" class="flex-grow mx-2 h-1" oninput="if(typeof window.updateSliderVal === 'function') window.updateSliderVal(this, 'val_${id}', '')">
                <span id="val_${id}" class="text-right text-xs font-bold w-10 text-slate-500">0</span>
            </div>`;
        });
        ageContainer.innerHTML = htmlContent;
    }

    Promise.all([
        fetchJSON('syss_basdata_2035.json' + cb),
        fetchJSON('syss_config_2035.json' + cb),
        fetchJSON('kalkylator_basdata_2035.json' + cb)
    ]).then(async ([sBas, sConf, pBas]) => {
        
        if (!sBas) sBas = await fetchJSON('syss_basdata.json' + cb);
        if (!sConf) sConf = await fetchJSON('syss_config.json' + cb);
        if (!pBas || pBas.length === 0) pBas = await fetchJSON('kalkylator_basdata.json' + cb) || [];

        const statusDiv = document.getElementById('dataStatus');
        if (!sBas) {
            if (statusDiv) {
                statusDiv.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Hittade ingen basdata.';
                statusDiv.className = "p-1.5 bg-red-50 rounded border border-red-100 text-xs font-medium text-red-600";
            }
            return;
        }

        syssBasdata = sBas;
        syssConfig = sConf || {};
        popData = pBas || [];

        // Dölj sektionen för Etableringschocker om den finns i HTML
        const shocksContainer = document.getElementById('shocksContainer');
        if (shocksContainer) shocksContainer.style.display = 'none';

        if (syssConfig['Scenarier'] && syssConfig['Scenarier'].length > 0) {
            const rows = syssConfig['Scenarier'];
            const growthRows = syssConfig['Tillväxt'] && syssConfig['Tillväxt'].length > 0 ? syssConfig['Tillväxt'] : rows;

            const mapScenario = (colName) => {
                let baseSyssRow = rows.find(r => String(r.Indikator || '').trim() === 'Sysselsättningsgrad');
                let baseSyss = baseSyssRow && baseSyssRow[colName] !== undefined ? parseFloat(baseSyssRow[colName]) : 0;
                
                let syssAgeObj = {};
                ['16-19','20-24','25-29','30-34','35-39','40-44','45-49','50-54','55-59','60-64','65-69','70-74'].forEach(a => {
                    let key = 'syssAge' + a.replace('-', '_');
                    let rowMatch = growthRows.find(r => {
                        let ind = String(r.Indikator || '').trim().toLowerCase().replace('_', ' ');
                        return ind === ('sysselsättningsgrad ' + a);
                    });
                    if (rowMatch && rowMatch[colName] !== undefined && rowMatch[colName] !== '') {
                        syssAgeObj[key] = parseFloat(rowMatch[colName]);
                    } else {
                        syssAgeObj[key] = baseSyss;
                    }
                });
                
                let bKvotPeriodRaw = rows.find(r => String(r.Indikator || '').trim().toLowerCase() === 'bosättningskvot_bransch')?.[colName];

                return {
                    jobGrowth: parseFloat(rows.find(r => String(r.Indikator || '').trim() === 'Jobbtillväxt')?.[colName] || 0),
                    syssGrad: baseSyss,
                    student: parseFloat(rows.find(r => String(r.Indikator || '').trim() === 'Kvarstannandegrad')?.[colName] || 0),
                    inpendling: parseFloat(rows.find(r => String(r.Indikator || '').trim() === 'Inpendling')?.[colName] || 0),
                    utpendling: parseFloat(rows.find(r => String(r.Indikator || '').trim() === 'Utpendling')?.[colName] || 0),
                    distans: parseFloat(rows.find(r => String(r.Indikator || '').trim() === 'Distansarbete')?.[colName] || 0),
                    region: parseFloat(rows.find(r => String(r.Indikator || '').trim() === 'Regionförstoring')?.[colName] || 0),
                    migrantSyss: parseFloat(rows.find(r => String(r.Indikator || '').trim() === 'Justering inflyttares syss.grad')?.[colName] || 10),
                    naringScale: parseFloat(rows.find(r => String(r.Indikator || '').trim().toLowerCase().includes('näringsliv'))?.[colName] || 100),
                    bosattningskvotPeriod: (bKvotPeriodRaw !== undefined && bKvotPeriodRaw !== '') ? bKvotPeriodRaw : 'Alla',
                    syssAge: syssAgeObj
                };
            };
            window.scenarioSettings.base = mapScenario('Bas');
            window.scenarioSettings.high = mapScenario('Hög');
            window.scenarioSettings.low = mapScenario('Låg');
            window.scenarioSettings.stagnant = mapScenario('Stagnerande');
        }

        if (syssConfig['Universitet'] && syssConfig['Universitet'].length > 0) {
            syssConfig['Universitet'].forEach(r => {
                let y = extractYear(r);
                if (y) {
                    let studentVal = r['Examinerade_Studenter'] !== undefined ? r['Examinerade_Studenter'] : r['Examinerade_studenter'];
                    let civingVal = r['Examinerade_Civilingenjörer'] !== undefined ? r['Examinerade_Civilingenjörer'] : null;
                    if (studentVal !== undefined && studentVal !== null) annualStudentsMap[y] = parseFloat(studentVal);
                    if (civingVal !== undefined && civingVal !== null) annualCivIngMap[y] = parseFloat(civingVal);
                }
            });
            const stYears = Object.keys(annualStudentsMap).map(Number).sort((a,b)=>a-b);
            if (stYears.length > 0) avgAnnualStudents = annualStudentsMap[stYears[stYears.length - 1]];
            
            const civYears = Object.keys(annualCivIngMap).map(Number).sort((a,b)=>a-b);
            if (civYears.length > 0) avgAnnualCivIng = annualCivIngMap[civYears[civYears.length - 1]];
        }

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

        let offData = syssConfig['Officiell_befolkningsprognos'] || syssConfig['officiell_prognos'];
        if (offData && offData.length > 0) {
            offData.forEach(row => {
                const year = extractYear(row);
                if (!year) return;
                
                const rawSex = String(row['Kön'] || row['kön'] || 'Totalt').trim().toLowerCase();
                let sex = 'Totalt';
                if (rawSex.startsWith('m')) sex = 'Män';
                else if (rawSex.startsWith('k')) sex = 'Kvinnor';
                
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

        const scP = document.getElementById('scenarioPanel');
        if (scP) scP.classList.remove('opacity-50', 'pointer-events-none');
        
        extractHistoricalData();
        calculateMigrantEmploymentRate(); 
        
        if(typeof window.checkSharedScenario === 'function') window.checkSharedScenario(); 
        if(typeof window.buildDropdowns === 'function') window.buildDropdowns(); 
        
        const ySel = document.getElementById('yearSelect');
        if (ySel && baseYear > 0) ySel.value = baseYear;

        if(typeof window.updateDashboard === 'function') window.updateDashboard(false); 

        let popStatus = (popData.length > 0 || customPopData !== null) ? "Befolkning kopplad." : "VARNING: Saknar befolkning!";
        if (statusDiv) {
            statusDiv.innerHTML = `<i class="fa-solid fa-circle-check"></i> Redo. <b>${popStatus}</b>`;
            statusDiv.className = "p-1.5 px-3 bg-green-50 rounded border border-green-100 text-xs font-medium text-green-600";
        }

    }).catch(error => {
        const ds = document.getElementById('dataStatus');
        if (ds) {
            ds.innerHTML = `<b>Krasch under start:</b> ${error.message}`;
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
        
        const syssGradTotObj = dfSyssGrad.find(r => extractYear(r) == y && (!getKon(r) || getKon(r) === 'totalt'));
        const syssGradMObj = dfSyssGrad.find(r => extractYear(r) == y && getKon(r) === 'män');
        const syssGradKObj = dfSyssGrad.find(r => extractYear(r) == y && getKon(r) === 'kvinnor');

        let syss_in_tot = null, syss_ut_tot = null;
        if(syssBasdata['Syssgrad_utrikes']) {
            const suRow = syssBasdata['Syssgrad_utrikes'].find(r => extractYear(r) == y);
            if (suRow) {
                syss_in_tot = getScbVal(suRow, ['inrikes född 20-64 år totalt', 'inrikes födda', 'inrikes'], ['män', 'kvinnor']);
                syss_ut_tot = getScbVal(suRow, ['utrikes född 20-64 år totalt', 'utrikes födda', 'utrikes'], ['män', 'kvinnor']);
            }
        }

        let brpPerSyss = null;
        const brpRow = dfBRP.find(r => extractYear(r) == y);
        if (brpRow && brpRow['Linköping_BRP_per_sysselsatt_dagbefolkning_(tkr)'] != null) {
            brpPerSyss = parseFloat(brpRow['Linköping_BRP_per_sysselsatt_dagbefolkning_(tkr)']);
            lastKnownBRP = brpPerSyss; lastKnownBRPYear = y; brpHistory.push({year: y, val: brpPerSyss});
        }

        let arb = { tot_num:null, m_num:null, k_num:null, in_num:null, ut_num:null, tot_pct:null, m_pct:null, k_pct:null, in_pct:null, ut_pct:null };
        if (syssBasdata['Arbetslöshet']) {
            const rowsY = syssBasdata['Arbetslöshet'].filter(r => extractYear(r) == y);
            if (rowsY.length > 0) {
                let rowTot = rowsY.find(r => getKon(r) === 'totalt' || getKon(r) === 'samtliga' || !getKon(r)) || rowsY[0];
                arb.tot_pct = getScbVal(rowTot, ['totalt andel av arbetskraften', 'andel av arbetskraften totalt', 'totalt %', '%'], ['inskrivna']);
                arb.m_pct = getScbVal(rowTot, ['män andel av arbetskraften', 'män andel', 'män %'], ['inskrivna']);
                arb.k_pct = getScbVal(rowTot, ['kvinnor andel av arbetskraften', 'kvinnor andel', 'kvinnor %'], ['inskrivna']);
                arb.in_pct = getScbVal(rowTot, ['inrikes födda andel av arbetskraften', 'inrikes andel', 'inrikes %', 'inrikes födda %'], ['inskrivna']);
                arb.ut_pct = getScbVal(rowTot, ['utrikes födda andel av arbetskraften', 'utrikes andel', 'utrikes %', 'utrikes födda %'], ['inskrivna']);
                if (arb.m_pct == null) {
                    let rM = rowsY.find(r => getKon(r) === 'män');
                    arb.m_pct = getScbVal(rM, ['totalt andel', '%', 'andel'], ['inskrivna']);
                }
                if (arb.k_pct == null) {
                    let rK = rowsY.find(r => getKon(r) === 'kvinnor');
                    arb.k_pct = getScbVal(rK, ['totalt andel', '%', 'andel'], ['inskrivna']);
                }
                arb.tot_num = getScbVal(rowTot, ['totalt', 'samtliga', 'antal', 'värde'], ['andel', '%', 'inrikes', 'utrikes', 'män', 'kvinnor']);
                arb.m_num = getScbVal(rowTot, ['män', 'man'], ['andel', '%']);
                arb.k_num = getScbVal(rowTot, ['kvinnor', 'kvinna'], ['andel', '%']);
                arb.in_num = getScbVal(rowTot, ['inrikes', 'inrikes född'], ['andel', '%']);
                arb.ut_num = getScbVal(rowTot, ['utrikes', 'utrikes född'], ['andel', '%']);
                if (arb.m_num == null) {
                    let rM = rowsY.find(r => getKon(r) === 'män');
                    arb.m_num = getScbVal(rM, ['totalt', 'antal', 'värde'], ['andel', '%']);
                }
                if (arb.k_num == null) {
                    let rK = rowsY.find(r => getKon(r) === 'kvinnor');
                    arb.k_num = getScbVal(rK, ['totalt', 'antal', 'värde'], ['andel', '%']);
                }
            }
        }

        let larb = { tot_num:null, m_num:null, k_num:null, in_num:null, ut_num:null, tot_pct:null, m_pct:null, k_pct:null, in_pct:null, ut_pct:null, tot_insk:null, m_insk:null, k_insk:null, in_insk:null, ut_insk:null };
        let lData = syssBasdata['Långtidsarbetslöshet'] || syssBasdata['Langtidsarbetsloshet'];
        if (lData) {
            const rowsY = lData.filter(r => extractYear(r) == y);
            if (rowsY.length > 0) {
                let rowTot = rowsY.find(r => getKon(r) === 'totalt' || getKon(r) === 'samtliga' || !getKon(r)) || rowsY[0];
                larb.tot_pct = getScbVal(rowTot, ['totalt 16-65 år andel av arbetskraften', 'andel av arbetskraften totalt', 'totalt andel']);
                larb.m_pct = getScbVal(rowTot, ['män 16-65 år andel av arbetskraften', 'män andel av arbetskraften']);
                larb.k_pct = getScbVal(rowTot, ['kvinnor 16-65 år andel av arbetskraften', 'kvinnor andel av arbetskraften', 'kvinnor 16-65 år andel av arbetskraften']);
                larb.in_pct = getScbVal(rowTot, ['inrikes födda 16-65 år andel av arbetskraften', 'inrikes födda 16-65 år andel av arbetskraften']);
                larb.ut_pct = getScbVal(rowTot, ['utrikes födda 16-65 år andel av arbetskraften', 'utrikes födda 16-65 år andel av arbetskraften']);

                larb.tot_insk = getScbVal(rowTot, ['totalt 16-65 år andel av inskrivna', 'andel av inskrivna totalt']);
                larb.m_insk = getScbVal(rowTot, ['män 16-65 år andel av inskrivna', 'män andel av inskrivna']);
                larb.k_insk = getScbVal(rowTot, ['kvinnor 16-65 år andel av inskrivna', 'kvinnor andel av inskrivna', 'kvinnor 16-65 år andel av inskrivna']);
                larb.in_insk = getScbVal(rowTot, ['inrikes födda 16-65 år andel av inskrivna', 'inrikes födda 16-65 år andel av inskrivna']);
                larb.ut_insk = getScbVal(rowTot, ['utrikes födda 16-65 år andel av inskrivna', 'utrikes födda 16-65 år andel av inskrivna']);

                if (larb.m_pct == null || larb.m_insk == null) {
                    let rM = rowsY.find(r => getKon(r) === 'män');
                    larb.m_pct = getScbVal(rM, ['andel av arbetskraften', 'totalt andel']);
                    larb.m_insk = getScbVal(rM, ['andel av inskrivna']);
                }
                if (larb.k_pct == null || larb.k_insk == null) {
                    let rK = rowsY.find(r => getKon(r) === 'kvinnor');
                    larb.k_pct = getScbVal(rK, ['andel av arbetskraften', 'totalt andel']);
                    larb.k_insk = getScbVal(rK, ['andel av inskrivna']);
                }

                larb.tot_num = getScbVal(rowTot, ['totalt', 'samtliga', 'antal', 'värde'], ['andel', '%', 'inrikes', 'utrikes', 'män', 'kvinnor']);
                larb.m_num = getScbVal(rowTot, ['män', 'man'], ['andel', '%']);
                larb.k_num = getScbVal(rowTot, ['kvinnor', 'kvinna'], ['andel', '%']);
                larb.in_num = getScbVal(rowTot, ['inrikes', 'inrikes född'], ['andel', '%']);
                larb.ut_num = getScbVal(rowTot, ['utrikes', 'utrikes född'], ['andel', '%']);
                
                if (larb.m_num == null) {
                    let rM = rowsY.find(r => getKon(r) === 'män');
                    larb.m_num = getScbVal(rM, ['totalt', 'antal', 'värde'], ['andel', '%']);
                }
                if (larb.k_num == null) {
                    let rK = rowsY.find(r => getKon(r) === 'kvinnor');
                    larb.k_num = getScbVal(rK, ['totalt', 'antal', 'värde'], ['andel', '%']);
                }
            }
        }

        let n_inrikes = null, n_utrikes = null, d_inrikes = null, d_utrikes = null;
        const n_orig = extractOriginPop('Natt_utrikes', y);
        if(n_orig) { n_inrikes = n_orig.inr; n_utrikes = n_orig.utr; }
        const d_orig = extractOriginPop('Syss_utrikes', y);
        if(d_orig) { d_inrikes = d_orig.inr; d_utrikes = d_orig.utr; }

        let pop16_74 = getPopForYear(popData, y);
        if(pop16_74 === 0 && nattTotalt > 0) pop16_74 = nattTotalt / 0.70; 
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
            syssGradTot: syssGradTotObj,
            syssGradM: syssGradMObj,
            syssGradK: syssGradKObj,
            syss_in_tot: syss_in_tot,
            syss_ut_tot: syss_ut_tot,
            brp: brpPerSyss,
            extrapolatedBrp: null,
            arb: arb, 
            larb: larb,
            arbetsloshetPct: arb.tot_pct, 
            langtidsPct: larb.tot_pct, 
            n_inrikes: n_inrikes,
            n_utrikes: n_utrikes,
            d_inrikes: d_inrikes,
            d_utrikes: d_utrikes,
            d_man: d_man,
            d_kvinna: d_kvinna,
            n_man: n_man,
            n_kvinna: n_kvinna,
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

    let lastKnown = {};
    sortedYears.forEach(y => {
        let d = histDataStore[y];
        if (!d) return;
        ['displayRate','syss_in_tot','syss_ut_tot','n_inrikes','n_utrikes','d_inrikes','d_utrikes','n_man','n_kvinna','d_man','d_kvinna','ageRates'].forEach(k => {
            if (d[k] != null) lastKnown[k] = (typeof d[k] === 'object') ? JSON.parse(JSON.stringify(d[k])) : d[k];
            else if (lastKnown[k] != null) d[k] = (typeof lastKnown[k] === 'object') ? JSON.parse(JSON.stringify(lastKnown[k])) : lastKnown[k];
        });
        
        if(d.arb.tot_pct == null && lastKnown.arb_tot_pct != null) { d.arb.tot_pct = lastKnown.arb_tot_pct; d.arbetsloshetPct = lastKnown.arb_tot_pct; }
        else if (d.arb.tot_pct != null) lastKnown.arb_tot_pct = d.arb.tot_pct;
        
        if(d.larb.tot_pct == null && lastKnown.larb_tot_pct != null) { d.larb.tot_pct = lastKnown.larb_tot_pct; d.langtidsPct = lastKnown.larb_tot_pct; }
        else if (d.larb.tot_pct != null) lastKnown.larb_tot_pct = d.larb.tot_pct;

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
        if (histDataStore[y].demand != null && histDataStore[y].supply != null && histDataStore[y].displayRate != null) {
            baseYear = y; break;
        }
    }
    
    if (!baseYear || baseYear < sortedYears[0]) {
        for (let i = sortedYears.length - 1; i >= 0; i--) {
            let y = sortedYears[i];
            if (histDataStore[y].demand != null && histDataStore[y].supply != null) {
                baseYear = y; break;
            }
        }
    }

    histYearsGlobal = sortedYears;
    for (let y in histDataStore) {
        const numericY = parseInt(y);
        if (!isNaN(numericY) && numericY > baseYear && y !== 'brpCAGR' && y !== 'lastKnownBRP') {
            histDataStore[y].demand = null;
            histDataStore[y].supply = null;
            histDataStore[y].totalSupply = null;
        }
    }
}

// ==========================================
// SIMULERING OCH DYNAMISK JÄMVIKT
// ==========================================
window.runSimulation = function() {
    const forecastYears = PROGNOS_SLUTAR - baseYear;
    if (forecastYears <= 0) return;

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

            const jobGrowthPct = parseFloat(document.getElementById('jobGrowthSlider')?.value) || 0; 
            const syssGradChangeOverall = parseFloat(document.getElementById('syssGradSlider')?.value) || 0;
            const studentChange = parseFloat(document.getElementById('studentSlider')?.value) || 0;
            const civIngChange = parseFloat(document.getElementById('civIngSlider')?.value) || 0;
            
            let inpendlingChange = 0, utpendlingChange = 0, distansChange = 0, regionChangeMin = 0;
            let pendlingType = 'pct';
            
            if (simMode === 'full') {
                const pendTypeEl = document.getElementById('pendlingType');
                pendlingType = pendTypeEl ? pendTypeEl.value : 'pct';
                inpendlingChange = parseFloat(document.getElementById('inpendlingSlider')?.value) || 0;
                utpendlingChange = parseFloat(document.getElementById('utpendlingSlider')?.value) || 0;
                distansChange = parseFloat(document.getElementById('distansSlider')?.value) || 0;
                regionChangeMin = parseFloat(document.getElementById('regionSlider')?.value) || 0;
            }

            const base = histDataStore[baseYear];
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
            
            const targetVirtualSupply = extraRegionSupplyTotal + (Math.max(0, baselineDemand - baselineSupply) * (distansChange / 100));
            const brpCAGR = histDataStore['brpCAGR'] || 0.015;
            const baseExtrapolatedBRP = (base.extrapolatedBrp != null) ? base.extrapolatedBrp : (histDataStore['lastKnownBRP'] || 1000);
            const syssGradDemandBoostTotal = (base.pop != null ? base.pop : 0) * (syssGradChangeOverall / 100);

            const base_n_ut = base.n_utrikes || 0;
            const base_n_in = base.n_inrikes || 0;
            const base_d_ut = base.d_utrikes || 0;
            const base_d_in = base.d_inrikes || 0;
            const share_n_ut = (base_n_ut + base_n_in > 0) ? (base_n_ut / (base_n_ut + base_n_in)) : 0.25;
            const share_d_ut = (base_d_ut + base_d_in > 0) ? (base_d_ut / (base_d_ut + base_d_in)) : 0.25;

            const base_d_man = base.d_man || 0;
            const base_d_kvinna = base.d_kvinna || 0;
            const share_d_man = (base_d_man + base_d_kvinna > 0) ? (base_d_man / (base_d_man + base_d_kvinna)) : 0.5;

            const base_n_man = base.n_man || 0;
            const base_n_kvinna = base.n_kvinna || 0;
            const share_n_man = (base_n_man + base_n_kvinna > 0) ? (base_n_man / (base_n_man + base_n_kvinna)) : 0.5;

            let extraNaringDemandTotal = 0;
            let structuralInpendlingAccumulated = 0;

            let futureInpendlingBase = base.inpendling != null ? Number(base.inpendling) : 0;
            let futureUtpendlingBase = base.utpendling != null ? Number(base.utpendling) : 0;
            
            const genericInpendlingKvot = baselineDemand > 0 ? (futureInpendlingBase / baselineDemand) : 0.35;
            const genericUtpendlingKvot = baselineSupply > 0 ? (futureUtpendlingBase / baselineSupply) : 0.15;

            let activePopData = popSource === 'fryst' ? [] : (useCustomPop && customPopData ? customPopData : popData);

            let inrikesSyssKorr = syssGradChangeOverall;
            let utrikesSyssKorr = syssGradChangeOverall;
            let mKorr = syssGradChangeOverall;
            let kKorr = syssGradChangeOverall;
            let dyn_share_n_ut = share_n_ut;
            let dyn_share_d_ut = share_d_ut;

            if (syssGradChangeOverall > 0) {
                inrikesSyssKorr = syssGradChangeOverall * 0.4; 
                utrikesSyssKorr = syssGradChangeOverall * 2.8; 
                mKorr = syssGradChangeOverall * 0.8;
                kKorr = syssGradChangeOverall * 1.2;
            } else if (syssGradChangeOverall < 0) {
                inrikesSyssKorr = syssGradChangeOverall * 0.4;
                utrikesSyssKorr = syssGradChangeOverall * 2.8;
            }

            let branschKvoter = {};
            if (syssBasdata['Bosättningskvot_bransch'] && syssBasdata['Bosättningskvot_bransch'].length > 0) {
                let bData = syssBasdata['Bosättningskvot_bransch'];
                let bYears = bData.map(r => extractYear(r)).filter(y => y != null).sort((a, b) => b - a);
                let numYears = window.currentBKvotPeriod === 'Alla' ? bYears.length : parseInt(window.currentBKvotPeriod) || bYears.length;
                let selectedYears = bYears.slice(0, numYears);
                let relevantRows = bData.filter(r => selectedYears.includes(extractYear(r)));
    
                let allBranscher = new Set();
                relevantRows.forEach(r => Object.keys(r).forEach(k => {
                    if (k.toLowerCase() !== 'år' && k.toLowerCase() !== 'tid') allBranscher.add(k);
                }));
    
                allBranscher.forEach(b => {
                    let sum = 0; let count = 0;
                    relevantRows.forEach(r => {
                        if (r[b] !== undefined && r[b] !== null && String(r[b]).trim() !== '') {
                            sum += parseFloat(r[b]); count++;
                        }
                    });
                    branschKvoter[b] = count > 0 ? (sum / count) : 0.60;
                });
            }

            let dynPopAccumulated = 0;
            let dynLaborAccumulated = 0;

            for (let i = 1; i <= forecastYears; i++) {
                const forecastYear = baseYear + i;
                
                if (syssGradChangeOverall > 0) {
                    let shiftMax = 0.05 * (syssGradChangeOverall / 5); 
                    dyn_share_n_ut = share_n_ut + (shiftMax * (i / forecastYears));
                    dyn_share_d_ut = share_d_ut + (shiftMax * (i / forecastYears));
                }

                let naringDemandThisYear = 0;
                let structuralInpendlingThisYear = 0;
                
                if (syssConfig['Näringslivsjustering']) {
                    syssConfig['Näringslivsjustering'].forEach(row => {
                        let bransch = row['SNIbokstav'] || row['Bransch'];
                        let valY = parseFloat(row[String(forecastYear)]) || 0;
                        let valPrev = parseFloat(row[String(forecastYear-1)]) || 0;
                        
                        let nScale = window.currentNaringScale !== undefined ? window.currentNaringScale : 100;
                        let deltaTotal = (valY - valPrev) * (nScale / 100);
                        
                        naringDemandThisYear += deltaTotal;
                        let bKvot = 1 - genericInpendlingKvot; 
                        if (branschKvoter[bransch] !== undefined) bKvot = Math.max(0, Math.min(1, branschKvoter[bransch]));
                        structuralInpendlingThisYear += (deltaTotal * (1 - bKvot));
                    });
                }
                
                let organicDeltaTotal = (baselineDemand * (jobGrowthPct / 100)) / forecastYears;
                structuralInpendlingThisYear += organicDeltaTotal * genericInpendlingKvot;
                extraNaringDemandTotal += naringDemandThisYear;
                structuralInpendlingAccumulated += structuralInpendlingThisYear;

                const demandGrowthFactor = 1 + ((jobGrowthPct / 100) * (i / forecastYears));
                const futureDemand = (baselineDemand * demandGrowthFactor) + extraNaringDemandTotal + (syssGradDemandBoostTotal * (i / forecastYears));

                let futurePop = getPopForYear(activePopData, forecastYear) || (base.pop != null ? Number(base.pop) : 0);

                const baseTotalStudents = annualStudentsMap[forecastYear] !== undefined ? annualStudentsMap[forecastYear] : avgAnnualStudents;
                const baseCivIng = annualCivIngMap[forecastYear] !== undefined ? annualCivIngMap[forecastYear] : avgAnnualCivIng;
                const otherStudents = Math.max(0, baseTotalStudents - baseCivIng);
                let extraStudentsThisYear = useSpecificCivIng ? (otherStudents * (studentChange / 100) + baseCivIng * (civIngChange / 100)) : baseTotalStudents * (studentChange / 100);
                cumulativeExtraStudents += extraStudentsThisYear;

                let futureSupply = 0, futureSupplyM = 0, futureSupplyK = 0, futureRate = 0;
                
                let ageRates = base.ageRates; 
                let isAgeWeighted = false;

                if (ageRates && popSource !== 'fryst' && activePopData.length > 0 && futurePop > 0) {
                    isAgeWeighted = true;
                    Object.values(ageRates).forEach(group => {
                        let groupFuturePop = 0;
                        let groupFuturePopM = 0;
                        let groupFuturePopK = 0;

                        let records = activePopData.filter(r => String(r.tid).trim() === `${forecastYear} (Prognos)`);
                        if (records.length === 0) records = activePopData.filter(r => String(r.tid).trim() === String(forecastYear));
                        
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
                    const targetRate = (base.displayRate || 80) + syssGradChangeOverall;
                    futureRate = (base.displayRate || 80) + (((targetRate) - (base.displayRate || 80)) * (i / forecastYears));
                    futureSupply = (futurePop * (futureRate / 100)) + cumulativeExtraStudents;
                    futureSupplyM = futureSupply * share_n_man;
                    futureSupplyK = futureSupply * (1 - share_n_man);
                }

                futureSupply += dynLaborAccumulated;
                futureSupplyM += dynLaborAccumulated * share_n_man;
                futureSupplyK += dynLaborAccumulated * (1 - share_n_man);

                let futureUtpendlingBase_dynamic = futureSupply * genericUtpendlingKvot;

                let futureInpendling = futureInpendlingBase;
                let futureUtpendling = futureUtpendlingBase_dynamic;

                if (simMode === 'full') {
                    if (pendlingType === 'pct') {
                        futureInpendling = (futureInpendlingBase + structuralInpendlingAccumulated) * (1 + ((inpendlingChange/100) * (i/forecastYears)));
                        futureUtpendling = futureUtpendlingBase_dynamic * (1 + ((utpendlingChange/100) * (i/forecastYears)));
                    } else {
                        futureInpendling = Math.max(0, futureInpendlingBase + structuralInpendlingAccumulated + (inpendlingChange * (i/forecastYears)));
                        futureUtpendling = Math.max(0, futureUtpendlingBase_dynamic + (utpendlingChange * (i/forecastYears)));
                    }
                }

                const explicitNetCommuting = futureInpendling - futureUtpendling;
                const virtualSupplyThisYear = targetVirtualSupply * (i / forecastYears);
                let futureTotalSupply = futureSupply + explicitNetCommuting + virtualSupplyThisYear;

                let inducedPopThisYear = 0;
                let reqForeignLabor = 0;
                
                if (causalityMode === 'dynamic') {
                    const currentGap = futureDemand - futureTotalSupply;
                    if (currentGap > 0) {
                        const migrantEl = document.getElementById('migrantSyssSlider');
                        const userSyssAdjustment = migrantEl ? parseFloat(migrantEl.value) / 100 : 0.10;
                        const empRate = Math.max(0.01, globalMigrantEmploymentRate + userSyssAdjustment);
                        inducedPopThisYear = currentGap / empRate;
                        
                        futureSupply += currentGap;
                        futureTotalSupply += currentGap;
                        futurePop += inducedPopThisYear;
                        dynPopAccumulated += inducedPopThisYear;
                        dynLaborAccumulated += currentGap;
                        
                        futureSupplyM += currentGap * share_n_man;
                        futureSupplyK += currentGap * (1 - share_n_man);
                        if (currentGap > 500) reqForeignLabor = currentGap - 500;
                    }
                }

                const baseDisplayRate = base.displayRate != null ? Number(base.displayRate) : 80;
                const displayTarget = baseDisplayRate + syssGradChangeOverall;
                const futureDisplayRate = baseDisplayRate + ((displayTarget - baseDisplayRate) * (i / forecastYears));

                const futureBrpPerSyss = baseExtrapolatedBRP ? baseExtrapolatedBRP * Math.pow(1 + brpCAGR, i) : null;
                const futureTotalBrpMkr = (futureBrpPerSyss != null && futureDemand > 0) ? (futureBrpPerSyss * futureDemand) / 1000 : null;

                let base_d_m_component = (base.d_man || 0) * demandGrowthFactor + (syssGradDemandBoostTotal * (i / forecastYears)) * share_d_man;
                let base_d_k_component = (base.d_kvinna || 0) * demandGrowthFactor + (syssGradDemandBoostTotal * (i / forecastYears)) * (1 - share_d_man);

                let fSyssGradM = null, fSyssGradK = null, fSyssGradTot = null;
                if (base.syssGradM) {
                    fSyssGradM = {};
                    for (let k in base.syssGradM) {
                        if (['år','tid','kön'].includes(k.toLowerCase())) continue;
                        let val = parseFloat(base.syssGradM[k]);
                        if (!isNaN(val)) fSyssGradM[k] = val + mKorr * (i / forecastYears);
                    }
                }
                if (base.syssGradK) {
                    fSyssGradK = {};
                    for (let k in base.syssGradK) {
                        if (['år','tid','kön'].includes(k.toLowerCase())) continue;
                        let val = parseFloat(base.syssGradK[k]);
                        if (!isNaN(val)) fSyssGradK[k] = val + kKorr * (i / forecastYears);
                    }
                }

                let blankArb = { tot_num:null, m_num:null, k_num:null, in_num:null, ut_num:null, tot_pct:null, m_pct:null, k_pct:null, in_pct:null, ut_pct:null };
                let blankLarb = { tot_num:null, m_num:null, k_num:null, in_num:null, ut_num:null, tot_pct:null, m_pct:null, k_pct:null, in_pct:null, ut_pct:null, tot_insk:null, m_insk:null, k_insk:null, in_insk:null, ut_insk:null };

                progDataStore[forecastYear] = {
                    demand: futureDemand,
                    supply: futureSupply,
                    inpendling: futureInpendling,
                    utpendling: futureUtpendling,
                    explicitNetCommuting: explicitNetCommuting,
                    virtualSupply: virtualSupplyThisYear,
                    totalSupply: futureTotalSupply,
                    antalKommunerBeraknade: beraknadeKommuner,
                    pop: futurePop,
                    rate: futureRate,
                    displayRate: futureDisplayRate,
                    inducedPop: inducedPopThisYear,
                    reqForeignLabor: reqForeignLabor,
                    brp: futureBrpPerSyss,
                    totalBrpMkr: futureTotalBrpMkr,
                    syss_in_tot: base.syss_in_tot != null ? base.syss_in_tot + inrikesSyssKorr * (i/forecastYears) : null,
                    syss_ut_tot: base.syss_ut_tot != null ? base.syss_ut_tot + utrikesSyssKorr * (i/forecastYears) : null,
                    n_utrikes: futureSupply * dyn_share_n_ut,
                    n_inrikes: futureSupply * (1 - dyn_share_n_ut),
                    d_utrikes: futureDemand * share_d_ut,
                    d_inrikes: futureDemand * (1 - share_d_ut),
                    n_man: futureSupplyM,
                    n_kvinna: futureSupplyK,
                    d_man: base_d_m_component,
                    d_kvinna: base_d_k_component,
                    syssGradTot: base.syssGradTot,
                    syssGradM: fSyssGradM, 
                    syssGradK: fSyssGradK,
                    arb: blankArb,
                    larb: blankLarb,
                    arbetsloshetPct: null,
                    langtidsPct: null
                };
            }

            if (typeof window.buildDropdowns === 'function') window.buildDropdowns(); 
            if (typeof window.updateDashboard === 'function') window.updateDashboard(false); 

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
};