// ==========================================
// Grafer & UI 2035 - Visuell representation
// ==========================================

window.aggregateMatchData = function(dataset, refYear, labels, keyField, mapFn = null) {
    let result = { 'män': {}, 'kvinnor': {}, 'totalt': {} };
    labels.forEach(l => { result['män'][l] = 0; result['kvinnor'][l] = 0; result['totalt'][l] = 0; });
    
    let records = dataset.filter(r => window.extractYear(r) == refYear);
    if (records.length === 0) return result;
    
    let hasKonCol = records.some(r => window.getKon(r) !== null);
    let hasTotalRow = hasKonCol ? records.some(r => window.getKon(r) === 'totalt' || window.getKon(r) === '') : false;
    
    records.forEach(r => {
        let kon = window.getKon(r);
        if (!hasKonCol || kon === null || kon === '') kon = 'totalt'; 
        
        let isCountableTotal = false;
        if (!hasKonCol) {
            isCountableTotal = true;
        } else if (hasTotalRow) {
            isCountableTotal = (kon === 'totalt');
        } else {
            isCountableTotal = (kon === 'män' || kon === 'kvinnor');
        }
        
        if (keyField === 'Cols') {
            Object.keys(r).forEach(k => {
                let key = mapFn ? mapFn(k) : k;
                if (labels.includes(key)) {
                    let val = parseFloat(r[k]) || 0;
                    if (kon === 'män' || kon === 'kvinnor') result[kon][key] += val;
                    if (isCountableTotal) result['totalt'][key] += val;
                }
            });
        } else {
            let rawKey = String(r[keyField] || '').trim();
            let key = mapFn ? mapFn(rawKey) : rawKey;
            
            if (labels.includes(key)) {
                if (r['Män'] !== undefined || r['män'] !== undefined || r['Kvinnor'] !== undefined || r['kvinnor'] !== undefined) {
                    let mVal = parseFloat(r['Män'] || r['män'] || 0);
                    let kVal = parseFloat(r['Kvinnor'] || r['kvinnor'] || 0);
                    let tVal = parseFloat(r['Totalt'] || r['totalt'] || (mVal + kVal));
                    
                    result['män'][key] += mVal;
                    result['kvinnor'][key] += kVal;
                    if (isCountableTotal) result['totalt'][key] += tVal;
                } else {
                    let val = parseFloat(r['Totalt'] ?? r['Samtliga'] ?? r['Befolkning'] ?? r['Värde'] ?? r['Antal'] ?? 0);
                    if (isNaN(val)) val = 0;
                    if (kon === 'män' || kon === 'kvinnor') result[kon][key] += val;
                    if (isCountableTotal) result['totalt'][key] += val;
                }
            }
        }
    });
    return result;
};

window.drawMatchChart = function(year, labels, dagData, nattData, splitGender, useZeroAxis, isHorizontal = false) {
    const ctx = document.getElementById('trendChart').getContext('2d');
    if (window.trendChartInstance) {
        window.trendChartInstance.destroy();
        window.trendChartInstance = null;
    }
    
    let isProg = window.progDataStore && window.progDataStore[year] !== undefined;

    if (isProg && window.histDataStore && window.histDataStore[window.baseYear]) {
        const progD = window.progDataStore[year];
        const baseD = window.histDataStore[window.baseYear];
        const simModeEl = document.getElementById('simMode');
        const simMode = simModeEl ? simModeEl.value : 'full';
        const causalityModeEl = document.getElementById('causalityMode');
        const causalityMode = causalityModeEl ? causalityModeEl.value : 'analytic';
        
        const demandScale = (progD.demand && baseD.demand > 0) ? (progD.demand / baseD.demand) : 1;
        const supplyScale = simMode === 'full' 
            ? ((progD.totalSupply && baseD.totalSupply > 0) ? (progD.totalSupply / baseD.totalSupply) : 1) 
            : ((progD.supply && baseD.supply > 0) ? (progD.supply / baseD.supply) : 1);
        
        ['totalt', 'män', 'kvinnor'].forEach(kon => {
            labels.forEach(l => {
                if (dagData[kon] && dagData[kon][l] !== undefined) dagData[kon][l] *= demandScale;
                if (nattData[kon] && nattData[kon][l] !== undefined) nattData[kon][l] *= supplyScale;
            });
        });

        if (window.currentShocks && window.currentShocks.length > 0) {
            window.currentShocks.forEach(shock => {
                if (parseInt(shock['År']) <= year && shock['Bransch']) {
                    const bName = String(shock['Bransch']).trim();
                    const val = parseFloat(shock['Antal_Jobb']) || 0;
                    if (dagData['totalt'] && dagData['totalt'][bName] !== undefined) {
                        dagData['totalt'][bName] += val;
                        
                        let mShare = 0.5; 
                        if (shock['Andel_Män'] !== undefined && shock['Andel_Män'] !== null && String(shock['Andel_Män']).trim() !== '') {
                            let andelMStr = String(shock['Andel_Män']).trim();
                            let parsed = parseFloat(andelMStr.replace('%', '').replace(',', '.'));
                            if (!isNaN(parsed)) {
                                mShare = andelMStr.includes('%') || parsed > 1 ? parsed / 100 : parsed;
                                if (mShare > 1) mShare = 1;
                                if (mShare < 0) mShare = 0;
                            }
                        }
                        
                        if(dagData['män']) dagData['män'][bName] += val * mShare;
                        if(dagData['kvinnor']) dagData['kvinnor'][bName] += val * (1 - mShare);

                        if (causalityMode === 'dynamic') {
                            nattData['totalt'][bName] += val;
                            if(nattData['män']) nattData['män'][bName] += val * mShare;
                            if(nattData['kvinnor']) nattData['kvinnor'][bName] += val * (1 - mShare);
                        }
                    }
                }
            });
        }
    }

    let datasets = [];
    
    if (splitGender) {
        datasets = [
            { label: 'Efterfrågan (Män)', data: labels.map(l => dagData['män'][l]), backgroundColor: '#0284c7' },
            { label: 'Efterfrågan (Kvinnor)', data: labels.map(l => dagData['kvinnor'][l]), backgroundColor: '#be185d' },
            { label: 'Lokalt Utbud (Män)', data: labels.map(l => nattData['män'][l]), backgroundColor: '#0ea5e9' },
            { label: 'Lokalt Utbud (Kvinnor)', data: labels.map(l => nattData['kvinnor'][l]), backgroundColor: '#ec4899' }
        ];
    } else {
        let netData = {};
        labels.forEach(l => { netData[l] = nattData['totalt'][l] - dagData['totalt'][l]; });
        
        const simModeEl = document.getElementById('simMode');
        const supplyLabel = (simModeEl && simModeEl.value === 'full') ? 'Utbud (Inkl. all pendling)' : 'Lokalt Utbud (Nattbef.)';

        datasets = [
            { 
                type: isHorizontal ? 'bar' : 'line', 
                label: 'Rekryteringsgap (Lokal brist)', 
                data: labels.map(l => netData[l]), 
                borderColor: '#ef4444', 
                backgroundColor: isHorizontal ? 'rgba(239, 68, 68, 0.7)' : '#ef4444', 
                borderWidth: 2, 
                pointRadius: 4, 
                fill: false, 
                order: 1 
            },
            { type: 'bar', label: 'Efterfrågan/Jobb (Dag)', data: labels.map(l => dagData['totalt'][l]), backgroundColor: '#10b981', order: 2 },
            { type: 'bar', label: supplyLabel, data: labels.map(l => nattData['totalt'][l]), backgroundColor: '#0ea5e9', order: 3 }
        ];
    }

    const yGraceElement = document.getElementById('yGrace');
    const graceVal = yGraceElement && yGraceElement.style.display !== 'none' ? yGraceElement.value : '20%';
    
    const scaleConfig = isHorizontal ? {
        x: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, 0), font: { size: 10 } }, title: { display: true, text: 'Antal personer' } },
        y: { ticks: { font: { size: 10 } } }
    } : {
        x: { ticks: { font: { size: 10 } } },
        y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, 0), font: { size: 10 } }, title: { display: true, text: 'Antal personer' } }
    };

    window.trendChartInstance = new Chart(ctx, {
        type: 'bar',
        data: { labels: labels, datasets: datasets },
        options: {
            indexAxis: isHorizontal ? 'y' : 'x', 
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: scaleConfig,
            plugins: { tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + window.formatNumber(ctx.raw, 0) } }, legend: { labels: { boxWidth: 10, font: { size: 11 } } } }
        }
    });
};

window.updateDashboard = function(calledFromDropdown = true) {
    const chartTypeElement = document.getElementById('chartType');
    const subGroupSelect = document.getElementById('subGroupSelect');
    if (!chartTypeElement || !subGroupSelect) return;

    const chartType = chartTypeElement.value;
    
    const dualAxesContainer = document.getElementById('dualAxesContainer');
    const useDualAxesElement = document.getElementById('useDualAxes');

    // --- NY LOGIK FÖR STANDARDVÄRDEN (DELADE AXLAR) ---
    // Denna känner av om vi bytt diagramtyp sedan senast. Om ja, sätter den rätt default-kryss!
    if (window.lastChartType !== chartType) {
        if (useDualAxesElement) {
            if (chartType.includes('_utrikes')) {
                useDualAxesElement.checked = true; // Alltid på för inrikes/utrikes
            } else if (chartType.includes('_kon')) {
                useDualAxesElement.checked = false; // Alltid av för män/kvinnor
            }
        }
        window.lastChartType = chartType;
    }
    
    let useDualAxes = useDualAxesElement ? useDualAxesElement.checked : false;
    const useZeroAxisElement = document.getElementById('useZeroAxis');
    const useZeroAxis = useZeroAxisElement ? useZeroAxisElement.checked : false;

    // Förenklad kontroll: Alla diagram med _utrikes eller _kon stödjer delade axlar
    if (!(chartType.includes('_utrikes') || chartType.includes('_kon'))) {
        useDualAxes = false;
    }

    const exportPopBtn = document.getElementById('exportPopBtn');

    // --- UI LOGIK FÖR RULLISTOR OCH KNAPPAR BEROENDE PÅ DIAGRAM ---
    if (chartType === 'pop_dynamic') {
        if(exportPopBtn) exportPopBtn.classList.replace('hidden', 'flex');
        if(dualAxesContainer) { dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); }
        if (subGroupSelect.getAttribute('data-type') !== 'pop_dynamic') {
            subGroupSelect.innerHTML = '<option value="total">Totalt 16-74 år</option><option value="func">Funktionella grupper</option><option value="5yr">5-årsklasser</option>';
            subGroupSelect.setAttribute('data-type', 'pop_dynamic');
        }
        subGroupSelect.classList.remove('hidden');
        chartTypeElement.classList.remove('rounded-r');
        subGroupSelect.classList.add('rounded-r');
        
    } else if (chartType.includes('arbetsloshet') || chartType.includes('langtidsarb')) {
        if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
        if(dualAxesContainer && (chartType.includes('_utrikes') || chartType.includes('_kon'))) { 
            dualAxesContainer.classList.remove('hidden'); dualAxesContainer.classList.add('flex'); 
        } else if (dualAxesContainer) { 
            dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); 
        }
        
        let dataTypeKey = chartType.includes('langtidsarb') ? 'larb_type' : 'arb_type';
        if (subGroupSelect.getAttribute('data-type') !== dataTypeKey) {
            subGroupSelect.innerHTML = '<option value="pct">Andel av arbetskraften (%)</option>';
            if (chartType.includes('langtidsarb')) {
                subGroupSelect.innerHTML += '<option value="insk">Andel av inskrivna arbetslösa (%)</option>';
            }
            subGroupSelect.innerHTML += '<option value="num">Antal personer</option>';
            subGroupSelect.setAttribute('data-type', dataTypeKey);
        }
        subGroupSelect.classList.remove('hidden');
        chartTypeElement.classList.remove('rounded-r');
        subGroupSelect.classList.add('rounded-r');
        
    } else if (chartType === 'pendling_detalj') {
        if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
        if(dualAxesContainer) { dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); }
        
        if (subGroupSelect.getAttribute('data-type') !== 'pendling_dir') {
            subGroupSelect.innerHTML = '<option value="neg">Utpendling visas som negativ (-)</option><option value="pos">Utpendling visas som positiv (+)</option>';
            subGroupSelect.setAttribute('data-type', 'pendling_dir');
        }
        subGroupSelect.classList.remove('hidden');
        chartTypeElement.classList.remove('rounded-r');
        subGroupSelect.classList.add('rounded-r');
        
    } else if (chartType === 'bransch_match') {
        if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
        if(dualAxesContainer) { dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); }
        if (subGroupSelect.getAttribute('data-type') !== 'bransch') {
            subGroupSelect.innerHTML = '<option value="all">Alla branscher (SNI)</option>';
            if (window.syssConfig && window.syssConfig['SNIgrupper'] && window.syssConfig['SNIgrupper'].length > 0) {
                const firstRow = window.syssConfig['SNIgrupper'][0];
                const groupCols = Object.keys(firstRow).slice(1);
                groupCols.forEach(col => subGroupSelect.add(new Option(col, col)));
            }
            subGroupSelect.setAttribute('data-type', 'bransch');
        }
        subGroupSelect.classList.remove('hidden');
        chartTypeElement.classList.remove('rounded-r');
        subGroupSelect.classList.add('rounded-r');
        
    } else if (chartType === 'syssgrad_kon' || chartType === 'syssgrad_utrikes' || chartType === 'trend_kon' || chartType === 'trend_utrikes') {
        if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
        
        if(dualAxesContainer) { dualAxesContainer.classList.remove('hidden'); dualAxesContainer.classList.add('flex'); }
        
        if (chartType === 'syssgrad_kon') {
            if (subGroupSelect.getAttribute('data-type') !== 'syssgrad') {
                subGroupSelect.innerHTML = '';
                const sampleY = Object.keys(window.histDataStore).find(k => window.histDataStore[k].syssGradM);
                if (sampleY) {
                    const keys = Object.keys(window.histDataStore[sampleY].syssGradM).filter(k => !['År', 'år', 'Kön', 'kön'].includes(k));
                    keys.forEach(k => subGroupSelect.add(new Option(k, k)));
                    let defaultOpt = Array.from(subGroupSelect.options).find(o => o.value.includes('20-64'));
                    if (!defaultOpt && subGroupSelect.options.length > 0) defaultOpt = subGroupSelect.options[0];
                    if (defaultOpt) subGroupSelect.value = defaultOpt.value;
                }
                subGroupSelect.setAttribute('data-type', 'syssgrad');
            }
            subGroupSelect.classList.remove('hidden');
            chartTypeElement.classList.remove('rounded-r');
            subGroupSelect.classList.add('rounded-r');
        } else if (chartType === 'trend_kon') {
            if (subGroupSelect.getAttribute('data-type') !== 'trend_kon_age') {
                subGroupSelect.innerHTML = '<option value="totalt">Totalt</option>';
                const ageLabels = ['16-19', '20-24', '25-34', '35-44', '45-54', '55-59', '60-64', '65-74'];
                ageLabels.forEach(k => subGroupSelect.add(new Option(k + " år", k)));
                subGroupSelect.setAttribute('data-type', 'trend_kon_age');
            }
            subGroupSelect.classList.remove('hidden');
            chartTypeElement.classList.remove('rounded-r');
            subGroupSelect.classList.add('rounded-r');
        } else {
            subGroupSelect.classList.add('hidden');
            chartTypeElement.classList.add('rounded-r');
        }
        
    } else {
        if(exportPopBtn) exportPopBtn.classList.replace('flex', 'hidden');
        if(dualAxesContainer) { dualAxesContainer.classList.add('hidden'); dualAxesContainer.classList.remove('flex'); }
        subGroupSelect.classList.add('hidden');
        chartTypeElement.classList.add('rounded-r');
    }

    const startYearSelect = document.getElementById('startYearSelect');
    const desc = document.getElementById('chartDescription');
    const title = document.getElementById('trendTitle');
    const selectedYearStr = document.getElementById('yearSelect').value;
    const ctx = document.getElementById('trendChart').getContext('2d');
    const wrapper = document.getElementById('chartWrapper');
    
    const isComparing = window.savedProjectedData !== null;
    const simMode = document.getElementById('simMode').value;
    const showCommuting = simMode === 'full';
    const causalityMode = document.getElementById('causalityMode') ? document.getElementById('causalityMode').value : 'analytic';
    
    const selYearInt = parseInt(selectedYearStr);
    const isProgYear = window.progDataStore && window.progDataStore[selYearInt] !== undefined;
    const refYear = isProgYear ? window.baseYear : selYearInt;
    const currentPopData = (window.useCustomPop && window.customPopData) ? window.customPopData : window.popData;
    
    if (window.trendChartInstance) {
        window.trendChartInstance.data.datasets.forEach((ds, i) => {
            const meta = window.trendChartInstance.getDatasetMeta(i);
            window.globalChartVisibility[ds.label] = meta.hidden === null ? ds.hidden : meta.hidden;
        });
        window.trendChartInstance.destroy();
        window.trendChartInstance = null;
    }

    wrapper.style.minHeight = '300px';
    const yGraceElement = document.getElementById('yGrace');
    const graceVal = (typeof window.SHOW_Y_GRACE_UI !== 'undefined' && window.SHOW_Y_GRACE_UI) && yGraceElement ? yGraceElement.value : (window.DEFAULT_Y_GRACE || '20%');

    let labels = []; let datasets = []; let isHorizontal = false; let isStacked = false; let isBarChart = false; let customScale = null; let isMultiLine = false;
    const graphStartYear = isComparing ? window.baseYear : (parseInt(startYearSelect.value) || (window.allYears && window.allYears.length > 0 ? window.allYears[0] : 0));
    const activeYears = window.allYears ? window.allYears.filter(y => y >= graphStartYear) : [];

    // ==================
    // RITLOGIK PER TYP
    // ==================
    if (chartType === 'pop_dynamic') {
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (window.progDataStore[window.allYears[window.allYears.length-1]] ? " (Prognos)" : " (Historik)");
        if (title) title.innerText = "Framtida Befolkning 16-74 år (Dynamisk)" + suffix;
        if (desc) desc.innerText = "Visar kommunens basbefolkning i åldern 16-74 år. Om du har den dynamiska modellen aktiverad visar grafen även det simulerade befolkningstillskottet för motsvarande åldrar.";

        const popGroupVal = subGroupSelect.value;
        let hasProg = false;
        labels = activeYears;

        if (popGroupVal === 'total') {
            let h_pop=[], p_base=[], p_induced=[];
            labels.forEach(y => {
                let numericY = Number(y);
                if (y <= window.baseYear && window.histDataStore[numericY]) h_pop.push(window.histDataStore[numericY].pop);
                else h_pop.push(null);
                
                if (y > window.baseYear && window.progDataStore[numericY]) {
                    let d = window.progDataStore[numericY];
                    let induced = causalityMode === 'dynamic' ? (d.inducedPop || 0) : 0;
                    let base = d.pop - induced;
                    p_base.push(base); p_induced.push(induced); hasProg = true;
                } else if (y === window.baseYear && window.histDataStore[numericY]) {
                    p_base.push(window.histDataStore[numericY].pop); p_induced.push(0);
                } else {
                    p_base.push(null); p_induced.push(null);
                }
            });

            datasets = [ { label: 'Historisk Befolkning', data: h_pop, borderColor: '#0284c7', backgroundColor: '#0ea5e920', borderWidth: 3, fill: true, pointStyle: 'circle', spanGaps: true, stack: 'hist' } ];
            if (hasProg && !isComparing) {
                datasets.push({ label: 'Basbefolkning (Prognos)', data: p_base, borderColor: '#0ea5e9', backgroundColor: '#0ea5e920', borderWidth: 2, borderDash: [5,5], fill: true, pointStyle: 'circle', stack: 'prog' });
                datasets.push({ label: 'Inflyttning från jobbtillväxt', data: p_induced, borderColor: '#10b981', backgroundColor: '#10b98180', borderWidth: 2, fill: true, pointStyle: 'rect', stack: 'prog' });
            }
            isStacked = hasProg;
        } else {
            isMultiLine = true;
            const getPopForGroup = (yStr, group) => {
                let pop = 0;
                let records = currentPopData.filter(r => String(r.tid).trim() === yStr);
                if (records.length === 0) records = currentPopData.filter(r => String(r.tid).trim() === yStr.replace(' (Prognos)', ''));
                if (records.length === 0) records = currentPopData.filter(r => String(r.tid).trim() === String(window.baseYear)); 
                let useGender = records.some(r => String(r.kön).trim().toLowerCase() === 'män' || String(r.kön).trim().toLowerCase() === 'kvinnor');
                records.forEach(r => {
                    if (!String(r.ålder).toLowerCase().includes('totalt')) {
                        let konStr = String(r.kön).trim().toLowerCase();
                        if (useGender && konStr !== 'män' && konStr !== 'kvinnor') return;
                        if (group.sex && konStr !== group.sex) return;
                        const match = String(r.ålder).match(/\d+/);
                        if (match) {
                            const age = parseInt(match[0]);
                            if (age >= group.min && age <= group.max) pop += (r.Befolkning || 0);
                        }
                    }
                });
                if (pop === 0 && yStr.includes('Prognos')) {
                    let fallbackRecords = currentPopData.filter(r => String(r.tid).trim() === String(window.baseYear));
                    let fallbackUseGender = fallbackRecords.some(r => String(r.kön).trim().toLowerCase() === 'män' || String(r.kön).trim().toLowerCase() === 'kvinnor');
                    fallbackRecords.forEach(r => {
                        if (!String(r.ålder).toLowerCase().includes('totalt')) {
                            let konStr = String(r.kön).trim().toLowerCase();
                            if (fallbackUseGender && konStr !== 'män' && konStr !== 'kvinnor') return;
                            if (group.sex && konStr !== group.sex) return;
                            const match = String(r.ålder).match(/\d+/);
                            if (match) {
                                const age = parseInt(match[0]);
                                let minAge = group.min !== undefined ? group.min : 0;
                                let maxAge = group.max !== undefined ? group.max : 999;
                                if (age >= minAge && age <= maxAge) pop += (r.Befolkning || 0);
                            }
                        }
                    });
                }
                return pop;
            };

            let groups = window.getGroupDefinitions(popGroupVal);
            groups.forEach((g, idx) => {
                let h_data = [], p_data = [];
                labels.forEach((yStr) => {
                    let numericY = Number(yStr);
                    let isProg = numericY > window.baseYear;
                    let searchStr = isProg ? `${numericY} (Prognos)` : `${numericY}`;
                    let groupBase = getPopForGroup(searchStr, g);
                    let totalBase16_74 = getPopForGroup(searchStr, { min: 16, max: 74 });
                    let finalPop = groupBase;
                    if (isProg && window.progDataStore && window.progDataStore[numericY] && causalityMode === 'dynamic') {
                        let induced = window.progDataStore[numericY].inducedPop || 0;
                        let groupInduced = totalBase16_74 > 0 ? induced * (groupBase / totalBase16_74) : 0;
                        finalPop += groupInduced;
                    }
                    if (isProg) { h_data.push(null); p_data.push(finalPop); hasProg = true; } 
                    else { h_data.push(finalPop); p_data.push(null); }
                });
                labels.forEach((yStr, idx2) => { if (Number(yStr) === window.baseYear && idx2 < labels.length - 1) p_data[idx2] = h_data[idx2]; });
                datasets.push({ label: g.label, data: h_data, borderColor: g.color, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true });
                if (p_data.some(v => v !== null)) datasets.push({ label: g.label + ' (Prognos)', data: p_data, borderColor: g.color, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle' });
            });
        }

    } else if (chartType === 'medfoljande_behov') {
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (window.progDataStore[window.allYears[window.allYears.length-1]] ? " (Prognos)" : "");
        if (title) title.innerText = "Välfärdsbehov (Medföljande barn)" + suffix;
        if (desc) desc.innerText = causalityMode === 'dynamic' 
            ? "Visar uppskattat behov av nya förskole- och skolplatser som genereras av arbetskraftsinflyttningen varje år (beräknas via kvoter i styrfilen)."
            : "Visar teoretiskt behov av nya förskole- och skolplatser för att täcka det omatchade rekryteringsgapet.";
        
        isBarChart = true;
        isStacked = true; 

        let categories = [];
        if (window.syssConfig && window.syssConfig['Medföljande'] && window.syssConfig['Medföljande'].length > 0) {
            categories = window.syssConfig['Medföljande'].map(r => r['Skolform_Ålder']).filter(c => c);
        } else {
            categories = ['Förskola (0-5 år)', 'Grundskola F-3 (6-9 år)', 'Grundskola 4-9 (10-15 år)', 'Gymnasium (16-18 år)']; 
        }

        labels = activeYears.filter(y => y > window.baseYear); 
        if (labels.length === 0) labels = [(window.baseYear+1).toString()]; 
        
        const colors = ['#f59e0b', '#10b981', '#0ea5e9', '#8b5cf6', '#ec4899'];
        
        categories.forEach((cat, idx) => {
            let p_data = [];
            labels.forEach(y => {
                let numericY = Number(y);
                if (window.progDataStore && window.progDataStore[numericY] && window.progDataStore[numericY].medfoljande) {
                    p_data.push(window.progDataStore[numericY].medfoljande[cat] || 0);
                } else {
                    p_data.push(0);
                }
            });
            datasets.push({
                type: 'bar',
                label: cat,
                data: p_data,
                backgroundColor: colors[idx % colors.length]
            });
        });
        
        customScale = { y: { stacked: true, beginAtZero: useZeroAxis, ticks: { callback: val => window.formatNumber(val, 0) } } };

    } else if (chartType === 'utbud_efterfragan') {
        isMultiLine = true;
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (window.progDataStore[window.allYears[window.allYears.length-1]] ? " (Prognos)" : " (Historik)");
        if (title) title.innerText = "Utbud vs Efterfrågan" + suffix;
        if (desc) {
            if (causalityMode === 'dynamic') desc.innerHTML = "I <b>Dynamiskt läge</b> anpassar sig utbudet (den blå och lila linjen) automatiskt efter företagens efterfrågan. Grafen visar den slutgiltiga balansen.";
            else if (showCommuting) desc.innerText = "Grafen visar Efterfrågan på arbetskraft (Jobb/Grön), det lokala Utbudet (Bosatta/Blå), samt det Totala Utbudet inkl. in/ut-pendling (Streckad lila). När den lila linjen fångar in den gröna är arbetsmarknaden i balans!";
            else desc.innerText = "Grafen visar Efterfrågan på arbetskraft (Jobb/Grön) och det lokala Utbudet (Bosatta/Blå). Pendling visas ej i denna vy.";
        }

        labels = activeYears;
        let hDemand=[], hSupply=[], hTotalSupply=[], pDemand=[], pSupply=[], pTotalSupply=[], sDemand=[], sSupply=[], sTotalSupply=[];

        labels.forEach(y => {
            let numericY = Number(y);
            if (y <= window.baseYear && window.histDataStore[numericY]) { hDemand.push(window.histDataStore[numericY].demand); hSupply.push(window.histDataStore[numericY].supply); hTotalSupply.push(window.histDataStore[numericY].totalSupply); } 
            else { hDemand.push(null); hSupply.push(null); hTotalSupply.push(null); }
            
            if (y === window.baseYear && window.histDataStore[numericY]) { pDemand.push(window.histDataStore[numericY].demand); pSupply.push(window.histDataStore[numericY].supply); pTotalSupply.push(window.histDataStore[numericY].totalSupply); } 
            else if (y > window.baseYear && window.progDataStore[numericY]) { pDemand.push(window.progDataStore[numericY].demand); pSupply.push(window.progDataStore[numericY].supply); pTotalSupply.push(window.progDataStore[numericY].totalSupply); } 
            else { pDemand.push(null); pSupply.push(null); pTotalSupply.push(null); }
            
            if (isComparing) {
                if (y <= window.baseYear && window.histDataStore[numericY]) { sDemand.push(window.histDataStore[numericY].demand); sSupply.push(window.histDataStore[numericY].supply); sTotalSupply.push(window.histDataStore[numericY].totalSupply); } 
                else if (y > window.baseYear && window.savedProjectedData && window.savedProjectedData[numericY]) { sDemand.push(window.savedProjectedData[numericY].demand); sSupply.push(window.savedProjectedData[numericY].supply); sTotalSupply.push(window.savedProjectedData[numericY].totalSupply); } 
                else { sDemand.push(null); sSupply.push(null); sTotalSupply.push(null); }
            }
        });
        
        const hasProg = pDemand.some((v, idx) => v !== null && labels[idx] > window.baseYear);
        
        if (!isComparing) {
            datasets = [
                { label: 'Efterfrågan (Dagbefolkning)', data: hDemand, borderColor: '#10b981', backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'rect', spanGaps: true },
                { label: 'Lokalt Utbud (Nattbefolkning)', data: hSupply, borderColor: '#0ea5e9', backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true }
            ];
            if (showCommuting) datasets.push({ label: 'Totalt Utbud (Inkl. Pendling)', data: hTotalSupply, borderColor: '#8b5cf6', backgroundColor: 'transparent', borderWidth: 3, borderDash: [2, 2], pointStyle: 'triangle', spanGaps: true });
            
            if (hasProg) {
                datasets.push({ label: 'Efterfrågan (Prognos)', data: pDemand, borderColor: '#10b981', backgroundColor: 'transparent', borderWidth: 3, borderDash: [5, 5], pointStyle: 'rect' });
                datasets.push({ label: 'Lokalt Utbud (Prognos)', data: pSupply, borderColor: '#0ea5e9', backgroundColor: 'transparent', borderWidth: 3, borderDash: [5, 5], pointStyle: 'circle' });
                if (showCommuting) datasets.push({ label: 'Totalt Utbud (Prognos)', data: pTotalSupply, borderColor: '#8b5cf6', backgroundColor: 'transparent', borderWidth: 3, borderDash: [5, 5], pointStyle: 'triangle' });
            }
        } else {
            datasets = [
                { label: 'Efterfrågan (Aktuell)', data: pDemand, borderColor: '#10b981', backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'rect' },
                { label: 'Efterfrågan (Sparad)', data: sDemand, borderColor: '#10b981', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], opacity: 0.6, pointStyle: 'rectRot' },
                { label: 'Lokalt Utbud (Aktuell)', data: pSupply, borderColor: '#0ea5e9', backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle' },
                { label: 'Lokalt Utbud (Sparad)', data: sSupply, borderColor: '#0ea5e9', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], opacity: 0.6, pointStyle: 'rectRot' }
            ];
            if (showCommuting) {
                datasets.push({ label: 'Totalt Utbud (Aktuell)', data: pTotalSupply, borderColor: '#8b5cf6', backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'triangle' });
                datasets.push({ label: 'Totalt Utbud (Sparad)', data: sTotalSupply, borderColor: '#8b5cf6', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], opacity: 0.6, pointStyle: 'rectRot' });
            }
        }

        let defaultHiddenLabels = ['Efterfrågan (Aktuell)', 'Efterfrågan (Sparad)', 'Totalt Utbud (Inkl. Pendling)', 'Totalt Utbud (Aktuell)', 'Totalt Utbud (Sparad)'];
        if (showCommuting) defaultHiddenLabels.push('Efterfrågan (Prognos)');
        datasets.forEach(ds => { if (defaultHiddenLabels.includes(ds.label)) ds.hidden = true; });

    } else if (chartType.includes('arbetsloshet') || chartType.includes('langtidsarb')) {
        isMultiLine = true;
        startYearSelect.style.display = 'inline-block';
        let isLangtid = chartType.includes('langtidsarb');
        let groupStr = chartType.includes('_utrikes') ? 'utrikes' : (chartType.includes('_kon') ? 'kon' : 'totalt');
        let typeVal = subGroupSelect ? subGroupSelect.value : 'pct'; 
        
        if (title) {
            let baseT = isLangtid ? "Långtidsarbetslöshet" : "Arbetslöshet";
            if (groupStr === 'totalt') title.innerText = baseT + (isLangtid ? " (Kärnan)" : " & Arbetskraftsreserv");
            else if (groupStr === 'utrikes') title.innerText = baseT + ": Inrikes och Utrikes födda";
            else title.innerText = baseT + ": Män och Kvinnor";
        }
        
        let h_1=[], h_2=[], h_tot=[];
        
        // Filtrera axeln så att den slutar strikt vid basåret. Inga prognosår ritas ut för arbetslöshet.
        labels = activeYears.filter(y => y <= window.baseYear);
        
        labels.forEach(y => {
            let numericY = Number(y);
            if (numericY >= 1985 && window.histDataStore && window.histDataStore[numericY]) {
                let d = window.histDataStore[numericY];
                let obj = isLangtid ? d.larb : d.arb;
                
                if (obj) {
                    if (groupStr === 'totalt') {
                        let val = typeVal === 'num' ? obj.tot_num : (typeVal === 'insk' ? obj.tot_insk : obj.tot_pct);
                        h_1.push(val);
                    } else {
                        let v1 = null, v2 = null, vTot = null;
                        if (groupStr === 'utrikes') {
                            if (typeVal === 'num') { v1 = obj.in_num; v2 = obj.ut_num; }
                            else if (typeVal === 'insk') { v1 = obj.in_insk; v2 = obj.ut_insk; }
                            else { v1 = obj.in_pct; v2 = obj.ut_pct; }
                        } else {
                            if (typeVal === 'num') { v1 = obj.m_num; v2 = obj.k_num; vTot = obj.tot_num; }
                            else if (typeVal === 'insk') { v1 = obj.m_insk; v2 = obj.k_insk; vTot = obj.tot_insk; }
                            else { v1 = obj.m_pct; v2 = obj.k_pct; vTot = obj.tot_pct; }
                        }
                        h_1.push(v1); h_2.push(v2); h_tot.push(vTot);
                    }
                } else {
                    h_1.push(null); h_2.push(null); h_tot.push(null);
                }
            } else {
                h_1.push(null); h_2.push(null); h_tot.push(null);
            }
        });

        let lblSuffix = typeVal === 'num' ? ' (Antal)' : ' %';

        if (groupStr === 'totalt') {
            let lbl = isLangtid ? 'Långtidsarbetslösa' : 'Arbetslösa';
            datasets = [
                { label: lbl + lblSuffix, data: h_1, borderColor: isLangtid ? '#f97316' : '#ef4444', backgroundColor: isLangtid ? 'rgba(249, 115, 22, 0.2)' : 'rgba(239, 68, 68, 0.2)', borderWidth: 3, pointStyle: 'circle', fill: true, spanGaps: true }
            ];
        } else {
            let lbl1 = groupStr === 'utrikes' ? 'Inrikes' : 'Män';
            let lbl2 = groupStr === 'utrikes' ? 'Utrikes' : 'Kvinnor';
            let col1 = '#0ea5e9';
            let col2 = groupStr === 'utrikes' ? '#f97316' : '#ec4899';
            let baseL = isLangtid ? 'Långtidsarb.' : 'Arbetslöshet';
            
            datasets = [
                { label: `${baseL} ${lbl1}${lblSuffix}`, data: h_1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true },
                { label: `${baseL} ${lbl2}${lblSuffix}`, data: h_2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true }
            ];
            if (groupStr === 'kon') datasets.push({ label: 'Totalt' + lblSuffix, data: h_tot, borderColor: '#64748b', backgroundColor: 'transparent', borderWidth: 2, borderDash: [2,2], pointStyle: 'rect', spanGaps: true, hidden: true });
        }

        if (useDualAxes && (groupStr === 'utrikes' || groupStr === 'kon') && typeVal !== 'num') {
            let lbl1 = groupStr === 'utrikes' ? 'Inrikes' : 'Män';
            let lbl2 = groupStr === 'utrikes' ? 'Utrikes' : 'Kvinnor';
            let col1 = '#0ea5e9';
            let col2 = groupStr === 'utrikes' ? '#f97316' : '#ec4899';
            
            customScale = {
                y: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'left', title: { display: true, text: lbl1 + ' %', color: col1 }, ticks: { callback: val => window.formatNumber(val, 1) + '%' } },
                y1: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'right', title: { display: true, text: lbl2 + ' %', color: col2 }, grid: { drawOnChartArea: false }, ticks: { callback: val => window.formatNumber(val, 1) + '%' } }
            };
            datasets.forEach(ds => { ds.yAxisID = ds.label.includes(lbl2) ? 'y1' : 'y'; });
        } else {
            customScale = { y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, typeVal === 'num' ? 0 : 1) + (typeVal === 'num' ? '' : '%') } } };
        }

    } else if (chartType === 'brp_totalt') {
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (window.progDataStore[window.allYears[window.allYears.length-1]] ? " (Prognos)" : " (Historik)");
        if (title) title.innerText = "Ekonomisk Tillväxt" + suffix;

        let hBRP = [], pBRP = [], sBRP = [];
        labels = activeYears;
        labels.forEach(y => {
            let numericY = Number(y);
            if (y <= window.baseYear && window.histDataStore[numericY]) {
                let brpPer = window.histDataStore[numericY].brp || window.histDataStore[numericY].extrapolatedBrp;
                hBRP.push((brpPer && window.histDataStore[numericY].demand) ? (brpPer * window.histDataStore[numericY].demand) / 1000 : null);
            } else { hBRP.push(null); }
            
            if (y === window.baseYear && window.histDataStore[numericY]) {
                let brpPer = window.histDataStore[numericY].brp || window.histDataStore[numericY].extrapolatedBrp;
                pBRP.push((brpPer && window.histDataStore[numericY].demand) ? (brpPer * window.histDataStore[numericY].demand) / 1000 : null);
            } else if (y > window.baseYear && window.progDataStore[numericY]) {
                pBRP.push(window.progDataStore[numericY].totalBrpMkr);
            } else { pBRP.push(null); }
            
            if (isComparing) {
                if (y <= window.baseYear && window.histDataStore[numericY]) {
                    let brpPer = window.histDataStore[numericY].brp || window.histDataStore[numericY].extrapolatedBrp;
                    sBRP.push((brpPer && window.histDataStore[numericY].demand) ? (brpPer * window.histDataStore[numericY].demand) / 1000 : null);
                } else if (y > window.baseYear && window.savedProjectedData && window.savedProjectedData[numericY]) {
                    sBRP.push(window.savedProjectedData[numericY].totalBrpMkr);
                } else { sBRP.push(null); }
            }
        });

        if (!isComparing) {
            datasets = [
                { label: 'Total BRP (Mkr) - Historik', data: hBRP, borderColor: '#a855f7', backgroundColor: 'rgba(168, 85, 247, 0.2)', borderWidth: 3, pointStyle: 'rect', fill: true, spanGaps: true },
                { label: 'Total BRP (Mkr) - Prognos', data: pBRP, borderColor: '#a855f7', backgroundColor: 'transparent', borderWidth: 3, borderDash: [5, 5], pointStyle: 'rect', fill: false }
            ];
        } else {
             datasets = [
                { label: 'Total BRP (Mkr) - Aktuell', data: pBRP, borderColor: '#a855f7', backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'rect' },
                { label: 'Total BRP (Mkr) - Sparad', data: sBRP, borderColor: '#a855f7', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5, 5], opacity: 0.6, pointStyle: 'rectRot' }
            ];
        }
        customScale = { y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, 0) } } };

    } else if (chartType === 'utbud_efterfragan_delta') {
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        if (title) title.innerText = "Årlig förändring (Nytt utbud/Efterfrågan)";
        isBarChart = true;

        let dDemand = [], dSupply = [];
        labels = activeYears;
        
        labels.forEach(y => {
            let numY = Number(y);
            let currD = null, currS = null, prevD = null, prevS = null;

            if (numY <= window.baseYear && window.histDataStore[numY]) {
                currD = window.histDataStore[numY].demand; currS = window.histDataStore[numY].supply;
            } else if (numY > window.baseYear && window.progDataStore[numY]) {
                currD = window.progDataStore[numY].demand; currS = window.progDataStore[numY].supply;
            }

            if (numY - 1 <= window.baseYear && window.histDataStore[numY - 1]) {
                prevD = window.histDataStore[numY - 1].demand; prevS = window.histDataStore[numY - 1].supply;
            } else if (numY - 1 > window.baseYear && window.progDataStore[numY - 1]) {
                prevD = window.progDataStore[numY - 1].demand; prevS = window.progDataStore[numY - 1].supply;
            }

            if (currD != null && prevD != null) dDemand.push(currD - prevD); else dDemand.push(null);
            if (currS != null && prevS != null) dSupply.push(currS - prevS); else dSupply.push(null);
        });

        datasets = [
            { type: 'bar', label: 'Förändring Efterfrågan', data: dDemand, backgroundColor: '#10b981' },
            { type: 'bar', label: 'Förändring Lokalt Utbud', data: dSupply, backgroundColor: '#0ea5e9' }
        ];

    } else if (chartType === 'pendling_detalj') {
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        if (title) title.innerText = "In- och utpendling (Kommungräns)";
        isBarChart = true;

        const mode = subGroupSelect ? subGroupSelect.value : 'neg';
        let hIn = [], hUt = [], hNet = [], pIn = [], pUt = [], pNet = [];
        labels = activeYears;
        
        labels.forEach(y => {
            let numY = Number(y);
            if (numY <= window.baseYear && window.histDataStore[numY]) {
                hIn.push(window.histDataStore[numY].inpendling);
                let utVal = window.histDataStore[numY].utpendling;
                hUt.push(utVal ? (mode === 'neg' ? -utVal : utVal) : null); 
                hNet.push(window.histDataStore[numY].netCommuting);
            } else { hIn.push(null); hUt.push(null); hNet.push(null); }
            
            if (numY === window.baseYear && window.histDataStore[numY]) {
                pIn.push(null); pUt.push(null);
                pNet.push(window.histDataStore[numY].netCommuting);
            } else if (numY > window.baseYear && window.progDataStore[numY]) {
                pIn.push(window.progDataStore[numY].inpendling);
                let utVal = window.progDataStore[numY].utpendling;
                pUt.push(utVal ? (mode === 'neg' ? -utVal : utVal) : null);
                pNet.push(window.progDataStore[numY].explicitNetCommuting);
            } else { pIn.push(null); pUt.push(null); pNet.push(null); }
        });

        datasets = [
            { type: 'bar', label: 'Inpendling', data: hIn, backgroundColor: '#0ea5e9', order: 2 },
            { type: 'bar', label: 'Utpendling', data: hUt, backgroundColor: '#ef4444', order: 3 },
            { type: 'line', label: 'Pendlingsnetto', data: hNet, borderColor: '#334155', borderWidth: 3, fill: false, pointStyle: 'rect', order: 1 }
        ];
        
        const hasProg = pIn.some((v, idx) => v !== null && labels[idx] > window.baseYear);
        if (hasProg && !isComparing) {
            datasets.push({ type: 'bar', label: 'Inpendling (Prognos)', data: pIn, backgroundColor: 'rgba(14, 165, 233, 0.4)', order: 2 });
            datasets.push({ type: 'bar', label: 'Utpendling (Prognos)', data: pUt, backgroundColor: 'rgba(239, 68, 68, 0.4)', order: 3 });
            datasets.push({ type: 'line', label: 'Pendlingsnetto (Prognos)', data: pNet, borderColor: '#94a3b8', borderWidth: 3, borderDash: [5,5], fill: false, pointStyle: 'rect', order: 1 });
        }

    } else if (['utb_match', 'sektor_match', 'sektor_match_kon', 'bransch_match'].includes(chartType)) {
        startYearSelect.style.display = 'none'; 
        isBarChart = true;
        let dagData = {}, nattData = {};
        let isGenderSplit = false;
        
        const getDataset = (partialName) => {
            const key = Object.keys(window.syssBasdata).find(k => k.toLowerCase().includes(partialName.toLowerCase()));
            return key ? window.syssBasdata[key] : [];
        };

        const refYear = isProgYear ? window.baseYear : selYearInt;
        let suffix = isProgYear ? " (Prognos)" : "";
        
        if (chartType === 'utb_match') {
            if (title) title.innerText = `Utbildningsmatchning (År ${selYearInt})${suffix}`;
            labels = ['Förgymnasial', 'Gymnasial', 'Kort eftergymnasial', 'Lång eftergymnasial'];
            const mapLevel = (l) => {
                let t = String(l).toLowerCase();
                if (t.includes('förgymnasial')) return 'Förgymnasial';
                if (t.includes('kort eftergymnasial') || (t.includes('eftergymnasial') && t.includes('kort'))) return 'Kort eftergymnasial';
                if (t.includes('lång eftergymnasial') || (t.includes('eftergymnasial') && t.includes('lång')) || t.includes('forskar')) return 'Lång eftergymnasial';
                if (t.includes('eftergymnasial')) return 'Lång eftergymnasial'; 
                if (t.includes('gymnasial')) return 'Gymnasial';
                return 'Okänd';
            };
            dagData = window.aggregateMatchData(getDataset('Syss_utb'), refYear, labels, 'Utbildningsnivå', mapLevel);
            nattData = window.aggregateMatchData(getDataset('Natt_utb'), refYear, labels, 'Utbildningsnivå', mapLevel);
        
        } else if (chartType === 'sektor_match') {
            if (title) title.innerText = `Sektormatchning (År ${selYearInt})${suffix}`;
            labels = ['Privat sektor', 'Offentlig sektor'];
            dagData = window.aggregateMatchData(getDataset('Syss_sektor'), refYear, labels, 'Sektor');
            nattData = window.aggregateMatchData(getDataset('Natt_sektor'), refYear, labels, 'Sektor');
        
        } else if (chartType === 'sektor_match_kon') {
            if (title) title.innerText = `Sektormatchning: Män och Kvinnor (År ${selYearInt})${suffix}`;
            labels = ['Privat sektor', 'Offentlig sektor'];
            isGenderSplit = true;
            let d_m = { 'Privat sektor': 0, 'Offentlig sektor': 0 }, d_k = { 'Privat sektor': 0, 'Offentlig sektor': 0 };
            let n_m = { 'Privat sektor': 0, 'Offentlig sektor': 0 }, n_k = { 'Privat sektor': 0, 'Offentlig sektor': 0 };

            getDataset('Syss_sektor').filter(r => window.extractYear(r) == refYear).forEach(r => {
                let sec = String(r['Sektor'] || '').trim();
                if(labels.includes(sec)) { d_m[sec] += parseFloat(r['Män'] || r['män'] || 0); d_k[sec] += parseFloat(r['Kvinnor'] || r['kvinnor'] || 0); }
            });
            getDataset('Natt_sektor').filter(r => window.extractYear(r) == refYear).forEach(r => {
                let sec = String(r['Sektor'] || '').trim();
                if(labels.includes(sec)) { n_m[sec] += parseFloat(r['Män'] || r['män'] || 0); n_k[sec] += parseFloat(r['Kvinnor'] || r['kvinnor'] || 0); }
            });
            dagData = {'män': d_m, 'kvinnor': d_k};
            nattData = {'män': n_m, 'kvinnor': n_k};

        } else if (chartType === 'bransch_match') {
            if (title) title.innerText = `Branschmatchning (År ${selYearInt})${suffix}`;
            isHorizontal = true;
            const dfDag = getDataset('Syss_bransch');
            const dfNatt = getDataset('Natt_bransch');
            
            let rawLabels = [];
            if (dfDag.length > 0) {
                const excludeCols = ['År', 'år', 'Samtliga', 'Totalt', 'Kön', 'kön', 'Okänd bransch'];
                rawLabels = Object.keys(dfDag[0]).filter(k => !excludeCols.includes(k));
            }
            
            let dagDataRaw = window.aggregateMatchData(dfDag, refYear, rawLabels, 'Cols');
            let nattDataRaw = window.aggregateMatchData(dfNatt, refYear, rawLabels, 'Cols');
            
            const subGroupVal = subGroupSelect ? subGroupSelect.value : 'all';
            if (subGroupVal && subGroupVal !== 'all' && window.syssConfig['SNIgrupper']) {
                let groupedDag = { 'totalt': {} }, groupedNatt = { 'totalt': {} };
                const sniGrupper = window.syssConfig['SNIgrupper'];
                const firstKey = Object.keys(sniGrupper[0])[0]; 

                rawLabels.forEach(l => {
                    let mappingRow = sniGrupper.find(r => String(r[firstKey]).trim() === String(l).trim());
                    let targetGroup = mappingRow ? mappingRow[subGroupVal] : null;

                    if (targetGroup && String(targetGroup).trim() !== '') {
                        let groupName = String(targetGroup).trim();
                        if (!groupedDag['totalt'][groupName]) { groupedDag['totalt'][groupName] = 0; groupedNatt['totalt'][groupName] = 0; }
                        groupedDag['totalt'][groupName] += dagDataRaw['totalt'][l] || 0;
                        groupedNatt['totalt'][groupName] += nattDataRaw['totalt'][l] || 0;
                    }
                });
                labels = Object.keys(groupedDag['totalt']);
                dagData = groupedDag; nattData = groupedNatt;
            } else {
                labels = rawLabels; dagData = dagDataRaw; nattData = nattDataRaw;
            }

            if (labels.length > 15 && (!subGroupVal || subGroupVal === 'all')) {
                wrapper.style.minHeight = (labels.length * 20) + 'px';
            }
        }
        
        window.drawMatchChart(selYearInt, labels, dagData, nattData, isGenderSplit, useZeroAxis, isHorizontal);
        return; 
    } else if (chartType === 'trend_utrikes' || chartType === 'trend_kon') {
        isMultiLine = true;
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (window.progDataStore[window.allYears[window.allYears.length-1]] ? " (Prognos)" : " (Historik)");
        
        let key1_n, key2_n, key1_d, key2_d, lbl1_n, lbl2_n, lbl1_d, lbl2_d, col1, col2;
        if (chartType === 'trend_utrikes') {
            if (title) title.innerText = "Integration: Arbetsmarknad efter ursprung" + suffix;
            key1_n = 'n_inrikes'; key2_n = 'n_utrikes'; key1_d = 'd_inrikes'; key2_d = 'd_utrikes';
            lbl1_n = 'Lokalt Utbud (Inrikes)'; lbl2_n = 'Lokalt Utbud (Utrikes)'; lbl1_d = 'Efterfrågan (Inrikes)'; lbl2_d = 'Efterfrågan (Utrikes)';
            col1 = '#0ea5e9'; col2 = '#f97316';
        } else {
            if (title) title.innerText = "Jämställdhet: Arbetsmarknad efter kön" + suffix;
            key1_n = 'n_man'; key2_n = 'n_kvinna'; key1_d = 'd_man'; key2_d = 'd_kvinna';
            lbl1_n = 'Lokalt Utbud (Män)'; lbl2_n = 'Lokalt Utbud (Kvinnor)'; lbl1_d = 'Efterfrågan (Män)'; lbl2_d = 'Efterfrågan (Kvinnor)';
            col1 = '#0ea5e9'; col2 = '#ec4899';
        }

        labels = activeYears;
        let h_n1=[], h_n2=[], p_n1=[], p_n2=[], h_d1=[], h_d2=[], p_d1=[], p_d2=[];
        const ageGroup = chartType === 'trend_kon' ? subGroupSelect.value : 'totalt';

        labels.forEach(y => {
            let numericY = Number(y);
            if (numericY >= 1985) {
                if (y <= window.baseYear && window.histDataStore[numericY]) {
                    if (ageGroup === 'totalt' || chartType === 'trend_utrikes') {
                        h_n1.push(window.histDataStore[numericY][key1_n]); h_n2.push(window.histDataStore[numericY][key2_n]);
                        h_d1.push(window.histDataStore[numericY][key1_d]); h_d2.push(window.histDataStore[numericY][key2_d]);
                    } else {
                        h_n1.push(window.histDataStore[numericY].n_man_age && window.histDataStore[numericY].n_man_age[ageGroup] !== undefined ? window.histDataStore[numericY].n_man_age[ageGroup] : null);
                        h_n2.push(window.histDataStore[numericY].n_kvinna_age && window.histDataStore[numericY].n_kvinna_age[ageGroup] !== undefined ? window.histDataStore[numericY].n_kvinna_age[ageGroup] : null);
                        h_d1.push(window.histDataStore[numericY].d_man_age && window.histDataStore[numericY].d_man_age[ageGroup] !== undefined ? window.histDataStore[numericY].d_man_age[ageGroup] : null);
                        h_d2.push(window.histDataStore[numericY].d_kvinna_age && window.histDataStore[numericY].d_kvinna_age[ageGroup] !== undefined ? window.histDataStore[numericY].d_kvinna_age[ageGroup] : null);
                    }
                } else { h_n1.push(null); h_n2.push(null); h_d1.push(null); h_d2.push(null); }
                
                if (y === window.baseYear && window.histDataStore[numericY]) {
                    if (ageGroup === 'totalt' || chartType === 'trend_utrikes') {
                        p_n1.push(window.histDataStore[numericY][key1_n]); p_n2.push(window.histDataStore[numericY][key2_n]);
                        p_d1.push(window.histDataStore[numericY][key1_d]); p_d2.push(window.histDataStore[numericY][key2_d]);
                    } else {
                        p_n1.push(window.histDataStore[numericY].n_man_age && window.histDataStore[numericY].n_man_age[ageGroup] !== undefined ? window.histDataStore[numericY].n_man_age[ageGroup] : null);
                        p_n2.push(window.histDataStore[numericY].n_kvinna_age && window.histDataStore[numericY].n_kvinna_age[ageGroup] !== undefined ? window.histDataStore[numericY].n_kvinna_age[ageGroup] : null);
                        p_d1.push(window.histDataStore[numericY].d_man_age && window.histDataStore[numericY].d_man_age[ageGroup] !== undefined ? window.histDataStore[numericY].d_man_age[ageGroup] : null);
                        p_d2.push(window.histDataStore[numericY].d_kvinna_age && window.histDataStore[numericY].d_kvinna_age[ageGroup] !== undefined ? window.histDataStore[numericY].d_kvinna_age[ageGroup] : null);
                    }
                } else if (y > window.baseYear && window.progDataStore[numericY]) {
                    if (ageGroup === 'totalt' || chartType === 'trend_utrikes') {
                        p_n1.push(window.progDataStore[numericY][key1_n]); p_n2.push(window.progDataStore[numericY][key2_n]);
                        p_d1.push(window.progDataStore[numericY][key1_d]); p_d2.push(window.progDataStore[numericY][key2_d]);
                    } else {
                        p_n1.push(window.progDataStore[numericY].n_man_age && window.progDataStore[numericY].n_man_age[ageGroup] !== undefined ? window.progDataStore[numericY].n_man_age[ageGroup] : null);
                        p_n2.push(window.progDataStore[numericY].n_kvinna_age && window.progDataStore[numericY].n_kvinna_age[ageGroup] !== undefined ? window.progDataStore[numericY].n_kvinna_age[ageGroup] : null);
                        p_d1.push(window.progDataStore[numericY].d_man_age && window.progDataStore[numericY].d_man_age[ageGroup] !== undefined ? window.progDataStore[numericY].d_man_age[ageGroup] : null);
                        p_d2.push(window.progDataStore[numericY].d_kvinna_age && window.progDataStore[numericY].d_kvinna_age[ageGroup] !== undefined ? window.progDataStore[numericY].d_kvinna_age[ageGroup] : null);
                    }
                } else { p_n1.push(null); p_n2.push(null); p_d1.push(null); p_d2.push(null); }
            } else {
                h_n1.push(null); h_n2.push(null); h_d1.push(null); h_d2.push(null);
                p_n1.push(null); p_n2.push(null); p_d1.push(null); p_d2.push(null);
            }
        });

        datasets = [
            { label: lbl1_n, data: h_n1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true },
            { label: lbl2_n, data: h_n2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true },
            { label: lbl1_d, data: h_d1, borderColor: chartType === 'trend_utrikes' ? '#10b981' : '#0284c7', backgroundColor: 'transparent', borderWidth: 2, borderDash: [2,2], pointStyle: 'rect', spanGaps: true },
            { label: lbl2_d, data: h_d2, borderColor: chartType === 'trend_utrikes' ? '#8b5cf6' : '#be185d', backgroundColor: 'transparent', borderWidth: 2, borderDash: [2,2], pointStyle: 'rect', spanGaps: true }
        ];
        
        const hasProg = p_n1.some((v, idx) => v !== null && labels[idx] > window.baseYear);
        if(hasProg && !isComparing) {
            datasets.push({ label: lbl1_n.replace('Lokalt ', '') + ' (Prog)', data: p_n1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle' });
            datasets.push({ label: lbl2_n.replace('Lokalt ', '') + ' (Prog)', data: p_n2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle' });
            datasets.push({ label: lbl1_d + ' (Prog)', data: p_d1, borderColor: chartType === 'trend_utrikes' ? '#10b981' : '#0284c7', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], pointStyle: 'rect' });
            datasets.push({ label: lbl2_d + ' (Prog)', data: p_d2, borderColor: chartType === 'trend_utrikes' ? '#8b5cf6' : '#be185d', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], pointStyle: 'rect' });
        }

        if (useDualAxes && (chartType === 'trend_utrikes' || chartType === 'trend_kon')) {
            let isUtr = chartType === 'trend_utrikes';
            let title1 = isUtr ? 'Inrikes' : 'Män';
            let title2 = isUtr ? 'Utrikes' : 'Kvinnor';
            customScale = {
                y: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'left', title: { display: true, text: title1, color: col1 }, ticks: { callback: val => window.formatNumber(val) } },
                y1: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'right', title: { display: true, text: title2, color: col2 }, grid: { drawOnChartArea: false }, ticks: { callback: val => window.formatNumber(val) } }
            };
            datasets.forEach(ds => { ds.yAxisID = ds.label.includes(title2) ? 'y1' : 'y'; });
        }

    } else if (chartType === 'syssgrad_utrikes' || chartType === 'syssgrad_kon') {
        isMultiLine = true;
        startYearSelect.style.display = isComparing ? 'none' : 'inline-block';
        let suffix = isComparing ? " (Jämförelse)" : (window.progDataStore[window.allYears[window.allYears.length-1]] ? " (Prognos)" : " (Historik)");
        
        let key1, key2, lbl1, lbl2, col1, col2;
        if (chartType === 'syssgrad_utrikes') {
            if (title) title.innerText = "Sysselsättningsgrad: Inrikes och Utrikes födda" + suffix;
            key1 = 'syss_in_tot'; key2 = 'syss_ut_tot'; lbl1 = 'Inrikes'; lbl2 = 'Utrikes'; col1 = '#0ea5e9'; col2 = '#f97316';
        } else {
            if (title) title.innerText = "Sysselsättningsgrad: Män och Kvinnor" + suffix;
            key1 = 'syssGradM'; key2 = 'syssGradK'; lbl1 = 'Män'; lbl2 = 'Kvinnor'; col1 = '#0ea5e9'; col2 = '#ec4899';
        }

        const ageGroup = subGroupSelect.value;
        let h_1 = [], h_2 = [], h_tot = [], p_1 = [], p_2 = [], p_tot = [];
        labels = activeYears;
        labels.forEach(y => {
            let numericY = Number(y);
            if (numericY >= 1985) {
                let v1 = null, v2 = null;
                if (window.histDataStore[numericY]) {
                    if (chartType === 'syssgrad_utrikes') {
                        v1 = window.histDataStore[numericY][key1] != null ? parseFloat(window.histDataStore[numericY][key1]) : null;
                        v2 = window.histDataStore[numericY][key2] != null ? parseFloat(window.histDataStore[numericY][key2]) : null;
                    } else {
                        v1 = window.histDataStore[numericY][key1] && window.histDataStore[numericY][key1][ageGroup] != null ? parseFloat(window.histDataStore[numericY][key1][ageGroup]) : null;
                        v2 = window.histDataStore[numericY][key2] && window.histDataStore[numericY][key2][ageGroup] != null ? parseFloat(window.histDataStore[numericY][key2][ageGroup]) : null;
                    }
                }

                if (y <= window.baseYear) { h_1.push(v1); h_2.push(v2); h_tot.push(window.histDataStore[numericY] ? window.histDataStore[numericY].displayRate : null); } 
                else { h_1.push(null); h_2.push(null); h_tot.push(null); }
                
                if (y === window.baseYear) { p_1.push(v1); p_2.push(v2); p_tot.push(window.histDataStore[numericY] ? window.histDataStore[numericY].displayRate : null); } 
                else if (y > window.baseYear && window.progDataStore[numericY]) {
                    let base_1 = null, base_2 = null;
                    if (window.histDataStore[window.baseYear]) {
                        if (chartType === 'syssgrad_utrikes') {
                            base_1 = window.histDataStore[window.baseYear][key1] != null ? parseFloat(window.histDataStore[window.baseYear][key1]) : null;
                            base_2 = window.histDataStore[window.baseYear][key2] != null ? parseFloat(window.histDataStore[window.baseYear][key2]) : null;
                        } else {
                            base_1 = window.histDataStore[window.baseYear][key1] && window.histDataStore[window.baseYear][key1][ageGroup] != null ? parseFloat(window.histDataStore[window.baseYear][key1][ageGroup]) : null;
                            base_2 = window.histDataStore[window.baseYear][key2] && window.histDataStore[window.baseYear][key2][ageGroup] != null ? parseFloat(window.histDataStore[window.baseYear][key2][ageGroup]) : null;
                        }
                    }
                    let base_tot = window.histDataStore[window.baseYear].displayRate != null ? parseFloat(window.histDataStore[window.baseYear].displayRate) : null;
                    const sliderChange = parseFloat(document.getElementById('syssGradSlider').value);
                    const step = (numericY - window.baseYear) / 10;
                    p_1.push(base_1 != null ? base_1 + sliderChange * step : null);
                    p_2.push(base_2 != null ? base_2 + sliderChange * step : null);
                    p_tot.push(base_tot != null ? base_tot + sliderChange * step : null);
                } else { p_1.push(null); p_2.push(null); p_tot.push(null); }
            }
        });

        datasets = [
            { label: `Sysselsättningsgrad ${lbl1} %`, data: h_1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true },
            { label: `Sysselsättningsgrad ${lbl2} %`, data: h_2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, pointStyle: 'circle', spanGaps: true }
        ];
        if (chartType === 'syssgrad_kon') datasets.push({ label: 'Totalt %', data: h_tot, borderColor: '#64748b', backgroundColor: 'transparent', borderWidth: 2, borderDash: [2,2], pointStyle: 'rect', spanGaps: true, hidden: true });

        const hasProg = p_1.some((v, idx) => v !== null && labels[idx] > window.baseYear);
        if (hasProg) {
            datasets.push({ label: `${lbl1} % (Prognos)`, data: p_1, borderColor: col1, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle', fill: false });
            datasets.push({ label: `${lbl2} % (Prognos)`, data: p_2, borderColor: col2, backgroundColor: 'transparent', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle', fill: false });
            if (chartType === 'syssgrad_kon') datasets.push({ label: 'Totalt % (Prognos)', data: p_tot, borderColor: '#64748b', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5,5], pointStyle: 'rect', fill: false, hidden: true });
        }

        if (useDualAxes && (chartType === 'syssgrad_utrikes' || chartType === 'syssgrad_kon')) {
            let isUtr = chartType === 'syssgrad_utrikes';
            let title1 = isUtr ? 'Inrikes' : 'Män';
            let title2 = isUtr ? 'Utrikes' : 'Kvinnor';
            customScale = {
                y: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'left', title: { display: true, text: title1 + ' %', color: col1 }, ticks: { callback: val => window.formatNumber(val, 1) + '%' } },
                y1: { beginAtZero: useZeroAxis, grace: graceVal, type: 'linear', display: true, position: 'right', title: { display: true, text: title2 + ' %', color: col2 }, grid: { drawOnChartArea: false }, ticks: { callback: val => window.formatNumber(val, 1) + '%' } }
            };
            datasets.forEach(ds => { ds.yAxisID = ds.label.includes(title2) ? 'y1' : 'y'; });
        }

    }

    if (datasets.length > 0) {
        let maxValidIdx = -1;
        datasets.forEach(ds => {
            ds.data.forEach((val, idx) => {
                if (val !== null && val !== undefined && val !== '') {
                    if (idx > maxValidIdx) maxValidIdx = idx;
                }
            });
        });
        if (maxValidIdx >= 0 && maxValidIdx < labels.length - 1) {
            labels = labels.slice(0, maxValidIdx + 1);
            datasets.forEach(ds => {
                ds.data = ds.data.slice(0, maxValidIdx + 1);
            });
        }
    }

    datasets.forEach(ds => {
        if (window.globalChartVisibility[ds.label] !== undefined) ds.hidden = window.globalChartVisibility[ds.label];
    });

    if (!isBarChart) {
        let isPct = false;
        if (chartType.includes('arbetsloshet') || chartType.includes('syssgrad')) {
            let typeVal = subGroupSelect ? subGroupSelect.value : 'pct';
            isPct = typeVal !== 'num';
        }
        let decimals = isPct ? 1 : 0;
        let suffix_text = isPct ? '%' : (chartType === 'brp_totalt' ? ' Mkr' : '');

        let finalOptions = {
            responsive: true, 
            maintainAspectRatio: false, 
            interaction: { mode: isMultiLine ? 'index' : 'nearest', intersect: false },
            scales: customScale || { y: { stacked: isStacked, beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, decimals) + suffix_text } } },
            plugins: { 
                tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + window.formatNumber(ctx.raw, decimals) + suffix_text } }, 
                legend: { 
                    labels: { boxWidth: 10, font: { size: 11 }, generateLabels: function(chart) { return Chart.defaults.plugins.legend.labels.generateLabels(chart).map(l => { l.color = l.hidden ? '#cbd5e1' : '#334155'; return l; }); } },
                    onClick: function(e, legendItem, legend) {
                        Chart.defaults.plugins.legend.onClick.call(this, e, legendItem, legend);
                        setTimeout(() => {
                            const hideBtn = document.getElementById('hideAllBtn');
                            if (hideBtn && !hideBtn.classList.contains('hidden')) {
                                const anyVis = window.trendChartInstance.data.datasets.some((ds, i) => window.trendChartInstance.isDatasetVisible(i));
                                hideBtn.innerHTML = anyVis ? '<i class="fa-solid fa-eye-slash mr-1"></i> Dölj alla' : '<i class="fa-solid fa-eye mr-1"></i> Visa alla';
                            }
                        }, 50);
                    }
                } 
            }
        };

        window.trendChartInstance = new Chart(ctx, {
            type: 'line',
            data: { labels: labels.map(l => String(l).replace(' (Prognos)', '')), datasets: datasets },
            options: finalOptions
        });
    } else if (isBarChart && datasets.length > 0) {
        
        let decimals = 0;
        let scaleConfig = isHorizontal ? {
            x: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, decimals), font: { size: 10 } }, title: { display: true, text: 'Antal personer' } },
            y: { ticks: { font: { size: 10 } } }
        } : {
            x: { ticks: { font: { size: 10 } } },
            y: { beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, decimals), font: { size: 10 } }, title: { display: true, text: 'Antal personer' } }
        };

        if (chartType === 'pendling_detalj') {
            scaleConfig = {
                x: { ticks: { font: { size: 10 } } },
                y: { beginAtZero: true, grace: graceVal, ticks: { callback: val => window.formatNumber(val, 0), font: { size: 10 } } }
            };
        }
        if (chartType === 'medfoljande_behov') {
            scaleConfig = {
                x: { ticks: { font: { size: 10 } } },
                y: { stacked: true, beginAtZero: useZeroAxis, grace: graceVal, ticks: { callback: val => window.formatNumber(val, 0), font: { size: 10 } } }
            };
        }

        window.trendChartInstance = new Chart(ctx, {
            type: 'bar',
            data: { labels: labels.map(l => String(l).replace(' (Prognos)', '')), datasets: datasets },
            options: {
                indexAxis: isHorizontal ? 'y' : 'x', 
                responsive: true, maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                scales: scaleConfig,
                plugins: { tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': ' + window.formatNumber(ctx.raw, decimals) } }, legend: { labels: { boxWidth: 10, font: { size: 11 } } } }
            }
        });
    }

    if (!calledFromDropdown) {
        if (typeof window.updateKPIs === 'function') window.updateKPIs();
    }
    
    const hideAllBtn = document.getElementById('hideAllBtn');
    if (hideAllBtn) {
        if (datasets.length > 1 && !chartType.includes('match') && chartType !== 'utbud_efterfragan_delta' && chartType !== 'pendling_detalj' && chartType !== 'medfoljande_behov') {
            hideAllBtn.classList.remove('hidden');
            hideAllBtn.classList.add('flex');
            
            const anyVis = datasets.some(ds => ds.hidden !== true);
            hideAllBtn.innerHTML = anyVis ? '<i class="fa-solid fa-eye-slash mr-1"></i> Dölj alla' : '<i class="fa-solid fa-eye mr-1"></i> Visa alla';
        } else {
            hideAllBtn.classList.add('hidden');
            hideAllBtn.classList.remove('flex');
        }
    }
};

window.toggleAllSeries = function() {
    if(!window.trendChartInstance) return;
    const anyVisible = window.trendChartInstance.data.datasets.some((ds, i) => window.trendChartInstance.isDatasetVisible(i));
    window.trendChartInstance.data.datasets.forEach((ds, i) => {
        const meta = window.trendChartInstance.getDatasetMeta(i);
        meta.hidden = anyVisible;
        window.globalChartVisibility[ds.label] = anyVisible;
    });
    window.trendChartInstance.update();
    const btn = document.getElementById('hideAllBtn');
    if (btn) btn.innerHTML = anyVisible ? '<i class="fa-solid fa-eye mr-1"></i> Visa alla' : '<i class="fa-solid fa-eye-slash mr-1"></i> Dölj alla';
};