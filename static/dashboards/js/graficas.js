/* Draws the charts of a tab with Chart.js from the JSON the view embeds
   (id "datos-graficas"). The data is Central's chart data, untouched; this
   file only paints it with the brand colours. */
(function () {
  "use strict";
  var nodo = document.getElementById("datos-graficas");
  if (!nodo || typeof Chart === "undefined") { return; }
  var graficas = JSON.parse(nodo.textContent);

  var css = getComputedStyle(document.documentElement);
  var VERDE = css.getPropertyValue("--verde").trim() || "#035953";
  var NARANJA = css.getPropertyValue("--naranja").trim() || "#eb6834";
  var BASE = "#c9bfa8";            // last year / comparison series
  var PASTEL = [VERDE, NARANJA, "#0a8f86", "#f0b48f", "#6b7f7c", BASE];

  var pesos = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 0 });
  var entero = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 0 });
  function corto(v) {               // axis ticks: $1.2 M, $350 k
    var a = Math.abs(v);
    if (a >= 1e6) { return "$" + (v / 1e6).toFixed(1) + " M"; }
    if (a >= 1e3) { return "$" + Math.round(v / 1e3) + " k"; }
    return "$" + v;
  }

  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.color = "#555";

  graficas.forEach(function (g) {
    var lienzo = document.getElementById("g-" + g.id);
    if (!lienzo) { return; }
    if (g.tipo === "pastel") {
      var total = g.valores.reduce(function (a, b) { return a + (b || 0); }, 0);
      new Chart(lienzo, {
        type: "doughnut",
        data: { labels: g.etiquetas, datasets: [{ data: g.valores, backgroundColor: PASTEL, borderWidth: 1 }] },
        options: {
          responsive: true, maintainAspectRatio: false, cutout: "55%",
          plugins: {
            legend: { position: "bottom", labels: { boxWidth: 12 } },
            tooltip: { callbacks: { label: function (c) {
              var v = c.raw || 0;
              if (!g.pesos) { return " " + c.label + ": " + v.toFixed(1) + "%"; }
              return " " + c.label + ": " + pesos.format(v) + " (" + (total ? (100 * v / total).toFixed(1) : "0") + "%)";
            } } }
          }
        }
      });
      return;
    }
    var colores = [VERDE, BASE];
    var datasets = g.series.map(function (s, i) {
      var fondo = colores[i] || BASE;
      if (i === 0 && g.resaltar !== null && g.resaltar !== undefined) {   // the report's month in a trend
        fondo = g.etiquetas.map(function (_, j) { return j === g.resaltar ? NARANJA : VERDE; });
      }
      return { label: s.nombre, data: s.valores, backgroundColor: fondo, borderRadius: 3, maxBarThickness: 28 };
    });
    new Chart(lienzo, {
      type: "bar",
      data: { labels: g.etiquetas, datasets: datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12 } },
          tooltip: { callbacks: { label: function (c) {
            if (c.raw === null) { return " " + c.dataset.label + ": sin dato"; }
            return " " + c.dataset.label + ": " + (g.pesos ? pesos.format(c.raw) : entero.format(c.raw));
          } } }
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { callback: function (v) { return g.pesos ? corto(v) : entero.format(v); } } }
        }
      }
    });
  });
})();
