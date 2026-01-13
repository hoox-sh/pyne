const chart = LightweightCharts.createChart(document.getElementById('chart'), {
    width: document.querySelector('.chart-container').clientWidth,
    height: 500,
    layout: {
        backgroundColor: '#131722',
        textColor: '#d1d4dc',
    },
    grid: {
        vertLines: {
            color: '#334158',
        },
        horzLines: {
            color: '#334158',
        },
    },
    crosshair: {
        mode: LightweightCharts.CrosshairMode.Normal,
    },
    rightPriceScale: {
        borderColor: '#485c7b',
    },
    timeScale: {
        borderColor: '#485c7b',
    },
});

const candleSeries = chart.addCandlestickSeries({
    upColor: '#26a69a',
    downColor: '#ef5350',
    borderDownColor: '#ef5350',
    borderUpColor: '#26a69a',
    wickDownColor: '#ef5350',
    wickUpColor: '#26a69a',
});

let overlaySeries = null;

// Dummy data for now
const runButton = document.getElementById('run-button');
const pineScriptInput = document.getElementById('pine-script-input');
const output = document.getElementById('output');

let candleData = []; // Store fetched data globally

// Fetch Binance Data
fetch('https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=200')
    .then(res => res.json())
    .then(data => {
        candleData = data.map(d => {
            return {
                time: d[0] / 1000,
                open: parseFloat(d[1]),
                high: parseFloat(d[2]),
                low: parseFloat(d[3]),
                close: parseFloat(d[4])
            }
        });
        candleSeries.setData(candleData);
    })
    .catch(err => console.log(err));


runButton.addEventListener('click', () => {
    const pineScript = pineScriptInput.value;
    output.textContent = 'Running...';
    output.classList.remove('error');

    fetch('http://localhost:5002/run', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        // Send both script and data
        body: JSON.stringify({
            script: pineScript,
            data: candleData
        }),
    })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'error') {
                output.textContent = `Error: ${data.message}`;
                output.classList.add('error');
                console.error(data.message);
                return;
            }

            output.textContent = `Status: ${data.status}\nMessage: ${data.message}`;
            output.textContent += `\nPlots generated: ${data.data.length} points`;

            const plotData = data.data;

            if (Array.isArray(plotData)) {
                if (!overlaySeries) {
                    overlaySeries = chart.addLineSeries({
                        color: '#2962ff',
                        lineWidth: 2,
                    });
                }

                // Map backend results to chart time
                // Assuming backend returns result for every bar in order
                const lineData = [];
                for (let i = 0; i < candleData.length; i++) {
                    // If plotData is shorter (e.g. calculation starts later), handle indices carefully
                    // For now assuming 1-to-1 mapping
                    if (i < plotData.length && plotData[i] !== null) {
                        lineData.push({
                            time: candleData[i].time,
                            value: plotData[i]
                        });
                    }
                }

                overlaySeries.setData(lineData);
            }
        })
        .catch(err => {
            output.textContent = `Network Error: ${err.message}`;
            console.error(err);
        });
});