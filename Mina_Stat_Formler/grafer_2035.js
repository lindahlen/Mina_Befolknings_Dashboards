let mainChartInstance = null;
let globalChartVisibility = {}; 

const formatNumberGraph = (num, decimals = 0) => {
    if (num === null || num === undefined || isNaN(num)) return '-';
    return Number(num).toLocaleString('sv-SE', {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
};

function renderDashboard() {
    const chartTypeElement = document.getElementById('chartType');
    if (!chartTypeElement) return;
    
    const chartType = chartTypeElement.value;
    const ctx = document.getElementById('trendChart').getContext('2d');
    const startYear = parseInt(document.getElementById('startYearSelect').value) || 2015;

    // --- KPI Uppdatering ---
    const selY = parseInt(document.getElementById('yearSelect').value) || endYear;
    const dataY = selY > baseYear ? prognos2035[selY] : historiskData[selY];
    
    if (dataY) {
        document.getElementById('kpiUtbud').innerText = formatNumberGraph(dataY.supply);
        document.getElementById('kpiEfterfragan').innerText = formatNumberGraph(dataY.demand);
        document.getElementById('kpiPendling').innerText = formatNumberGraph(dataY.netCommuting);
        document.getElementById('kpiSyssGrad').innerText = formatNumberGraph(dataY.displayRate, 1) + '%';
        document.getElementById('kpiBRP').innerText = formatNumberGraph(dataY.brp, 1) + ' tkr';
        
        let gap = dataY.demand - dataY.totalSupply;
        let bBehov = 0;
        if (gap > 0 && document.getElementById('causalityMode').value !== 'dynamic') {
            bBehov = gap / 0.6; 
            document.getElementById('kpiBefolkning').innerText = '+' + formatNumberGraph(bBehov);
            document.getElementById('kpiBefolkning').className = "text-base md:text-lg font-bold text-orange-600";
        } else if (dataY.inducedPop > 0) {
            document.getElementById('kpiBefolkning').innerText = '+' + formatNumberGraph(dataY.inducedPop);
            document.getElementById('kpiBefolkning').className = "text-base md:text-lg font-bold text-emerald-600";
        } else {
            document.getElementById('kpiBefolkning').innerText = 'Balans';
            document.getElementById('kpiBefolkning').className = "text-base md:text-lg font-bold text-emerald-600";
        }
    }

    // --- GRAF RITNING ---
    if (mainChartInstance) {
        mainChartInstance.destroy();
    }

    let labels = Array.from(allYearsSet).filter(y => y >= startYear).sort((a,b)=>a-b);
    let dS = [];

    if (chartType === 'utbud_efterfragan') {
        let hD=[], hS=[], pD=[], pS=[], hP=[], pP=[];
        labels.forEach(y => {
            if (y <= baseYear && historiskData[y]) { 
                hD.push(historiskData[y].demand); hS.push(historiskData[y].supply); hP.push(historiskData[y].totalSupply);
                pD.push(null); pS.push(null); pP.push(null);
            }
            if (y === baseYear && historiskData[y]) { 
                pD[pD.length-1]=historiskData[y].demand; pS[pS.length-1]=historiskData[y].supply; pP[pP.length-1]=historiskData[y].totalSupply;
            }
            if (y > baseYear && prognos2035[y]) { 
                hD.push(null); hS.push(null); hP.push(null);
                pD.push(prognos2035[y].demand); pS.push(prognos2035[y].supply); pP.push(prognos2035[y].totalSupply);
            }
        });

        dS = [
            { label: 'Efterfrågan (Historik)', data: hD, borderColor: '#10b981', borderWidth: 3, pointStyle: 'rect', spanGaps: true },
            { label: 'Utbud (Historik)', data: hS, borderColor: '#0ea5e9', borderWidth: 3, pointStyle: 'circle', spanGaps: true },
            { label: 'Utbud inkl Pendling (Historik)', data: hP, borderColor: '#8b5cf6', borderWidth: 3, borderDash: [2,2], pointStyle: 'triangle', spanGaps: true },
            { label: 'Efterfrågan (Prognos)', data: pD, borderColor: '#10b981', borderWidth: 3, borderDash: [5,5], pointStyle: 'rect' },
            { label: 'Utbud (Prognos)', data: pS, borderColor: '#0ea5e9', borderWidth: 3, borderDash: [5,5], pointStyle: 'circle' },
            { label: 'Utbud inkl Pendling (Prognos)', data: pP, borderColor: '#8b5cf6', borderWidth: 3, borderDash: [5,5], pointStyle: 'triangle' }
        ];
    } else if (chartType === 'brp_totalt') {
        let hBRP=[], pBRP=[];
        labels.forEach(y => {
            if (y <= baseYear && historiskData[y]) { 
                let b = historiskData[y].brp || historiskData[y].extrapolatedBrp;
                hBRP.push(b && historiskData[y].demand ? (b * historiskData[y].demand)/1000 : null); pBRP.push(null);
            }
            if (y === baseYear && historiskData[y]) { 
                let b = historiskData[y].brp || historiskData[y].extrapolatedBrp;
                pBRP[pBRP.length-1] = (b && historiskData[y].demand ? (b * historiskData[y].demand)/1000 : null);
            }
            if (y > baseYear && prognos2035[y]) { 
                hBRP.push(null); pBRP.push(prognos2035[y].demand * 0.85); // Dummy BRP
            }
        });
        dS = [
            { label: 'Total BRP (Mkr) Historik', data: hBRP, borderColor: '#a855f7', backgroundColor: 'rgba(168,85,247,0.2)', fill: true, borderWidth: 3, pointStyle: 'rect' },
            { label: 'Total BRP (Mkr) Prognos', data: pBRP, borderColor: '#a855f7', borderWidth: 3, borderDash: [5,5], pointStyle: 'rect' }
        ];
    }

    const useZero = document.getElementById('useZeroAxis') ? document.getElementById('useZeroAxis').checked : false;

    mainChartInstance = new Chart(ctx, {
        type: 'line',
        data: { labels: labels.map(String), datasets: dS },
        options: {
            responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
            scales: { y: { beginAtZero: useZero, ticks: { callback: v => formatNumberGraph(v) } } },
            plugins: { tooltip: { callbacks: { label: c => c.dataset.label + ': ' + formatNumberGraph(c.raw) } } }
        }
    });
}