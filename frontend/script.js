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
fetch('https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=200')
    .then(res => res.json())
    .then(data => {
        const cdata = data.map(d => {
            return {time:d[0]/1000,open:parseFloat(d[1]),high:parseFloat(d[2]),low:parseFloat(d[3]),close:parseFloat(d[4])}
        });
        candleSeries.setData(cdata);
    })
    .catch(err => console.log(err));

const runButton = document.getElementById('run-button');
const pineScriptInput = document.getElementById('pine-script-input');
const output = document.getElementById('output');

runButton.addEventListener('click', () => {
    const pineScript = pineScriptInput.value;
    output.textContent = 'Running...';

    fetch('http://localhost:5002/run', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ script: pineScript }),
    })
    .then(res => res.json())
    .then(data => {
        output.textContent = `Status: ${data.status}\nMessage: ${data.message}`;
        if (Array.isArray(data.data)) {
            output.textContent += `\nData: ${JSON.stringify(data.data)}`;

            if (!overlaySeries) {
                overlaySeries = chart.addLineSeries({
                    color: '#2962ff',
                    lineWidth: 2,
                });
            }

            const lineData = data.data.reduce((points, value, index) => {
                const candle = candleSeries.dataByIndex(index);
                if (!candle) {
                    return points;
                }
                points.push({ time: candle.time, value });
                return points;
            }, []);

            overlaySeries.setData(lineData);
        } else if (overlaySeries) {
            overlaySeries.setData([]);
        }
    })
    .catch(err => {
        output.textContent = `Error: ${err.message}`;
        console.error(err);
    });
});