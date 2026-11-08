/* Local Chart.js only. Values remain available in server-rendered text. */
(() => {
  const source = document.getElementById('trend-data');
  const canvas = document.getElementById('trend-chart');
  if (!source || !canvas || !window.Chart) return;
  const data = JSON.parse(source.textContent);
  const palette = ['#276449', '#8a4933', '#395f9c', '#795a91', '#756118', '#28767a'];
  const scales = {x: {type: 'linear', min: 0, max: Math.max(1, data.dates.length - 1),
    title: {display: true, text: 'Local date'}, ticks: {maxTicksLimit: 6, precision: 0,
      callback: value => data.dates[value] || ''}}};
  data.units.forEach((unit, index) => {
    scales['unit' + index] = {type: 'linear', position: index % 2 ? 'right' : 'left',
      title: {display: true, text: unit}, grid: {drawOnChartArea: index === 0}};
  });
  new Chart(canvas, {type: 'scatter', data: {datasets: data.datasets.map((set, index) => ({
    ...set, borderColor: palette[index % palette.length], backgroundColor: palette[index % palette.length],
    pointRadius: 4, pointHoverRadius: 6,
  }))}, options: {responsive: true, maintainAspectRatio: false, animation: false, scales,
    plugins: {legend: {position: 'bottom'}, tooltip: {callbacks: {
      title: items => items.length ? data.dates[items[0].parsed.x] : '',
    }}}}});
})();
