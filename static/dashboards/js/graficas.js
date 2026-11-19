/* Draws the charts of a tab with Chart.js from the JSON the view embeds
   (id "datos-graficas"). The data is Central's figures, untouched; this
   file only paints them: bars, doughnuts, bubbles, treemap, heatmap,
   diverging ranking and dumbbell. */
(function () {
  "use strict";
  var nodo = document.getElementById("datos-graficas");
  if (!nodo || typeof Chart === "undefined") { return; }
  var graficas = JSON.parse(nodo.textContent);

  var css = getComputedStyle(document.documentElement);
  var VERDE = css.getPropertyValue("--verde").trim() || "#035953";
  var NARANJA = css.getPropertyValue("--naranja").trim() || "#eb6834";
  var BASE = "#c9bfa8";
  var LUZ = { verde: "#1e7d3a", naranja: NARANJA, rojo: "#b3261e", gris: "#9a9a9a" };
  var PASTEL = [VERDE, NARANJA, "#0a8f86", "#f0b48f", "#6b7f7c", BASE];

  var pesos = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 0 });
  var entero = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 0 });
  function corto(v) {
    var a = Math.abs(v);
    if (a >= 1e6) { return "$" + (v / 1e6).toFixed(1) + " M"; }
    if (a >= 1e3) { return "$" + Math.round(v / 1e3) + " k"; }
    return "$" + Math.round(v);
  }
  function fmt(v, f) {
    if (v === null || v === undefined) { return "sin dato"; }
    if (f === "pct") { return v.toFixed(1) + "%"; }
    if (f === "pesos") { return pesos.format(v); }
    return entero.format(v);
  }
  function eje(f) { return function (v) { return f === "pct" ? v + "%" : f === "pesos" ? corto(v) : entero.format(v); }; }
  function color(c, defecto) { return LUZ[c] || defecto || VERDE; }
  function alfa(hex, a) {
    var n = parseInt(hex.slice(1), 16);
    return "rgba(" + (n >> 16) + "," + ((n >> 8) & 255) + "," + (n & 255) + "," + a + ")";
  }

  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.color = "#555";
  var leyenda = { position: "bottom", labels: { boxWidth: 12 } };

  /* Reference lines (targets) at given x / y values, and point labels. */
  var lineas = {
    id: "lineas",
    afterDatasetsDraw: function (chart, _, opts) {
      if (!opts || (!opts.x && !opts.y)) { return; }
      var c = chart.ctx, a = chart.chartArea;
      c.save(); c.strokeStyle = "rgba(0,0,0,.35)"; c.setLineDash([5, 4]); c.lineWidth = 1;
      (opts.x || []).forEach(function (v) {
        var px = chart.scales.x.getPixelForValue(v);
        if (px >= a.left && px <= a.right) { c.beginPath(); c.moveTo(px, a.top); c.lineTo(px, a.bottom); c.stroke(); }
      });
      (opts.y || []).forEach(function (v) {
        var py = chart.scales.y.getPixelForValue(v);
        if (py >= a.top && py <= a.bottom) { c.beginPath(); c.moveTo(a.left, py); c.lineTo(a.right, py); c.stroke(); }
      });
      c.restore();
    }
  };
  var etiquetas = {
    id: "etiquetas",
    afterDatasetsDraw: function (chart, _, opts) {
      if (!opts || !opts.mostrar) { return; }
      var c = chart.ctx;
      c.save(); c.font = "11px " + Chart.defaults.font.family; c.fillStyle = "#333"; c.textAlign = "center";
      chart.getDatasetMeta(0).data.forEach(function (el, i) {
        var p = chart.data.datasets[0].data[i];
        c.fillText(p.etiqueta, el.x, el.y - (p.r || 6) - 3);
      });
      c.restore();
    }
  };

  function barras(lienzo, g) {
    var colores = [VERDE, BASE];
    var datasets = g.series.map(function (s, i) {
      var fondo = colores[i] || BASE;
      if (i === 0 && g.resaltar !== null && g.resaltar !== undefined) {
        fondo = g.etiquetas.map(function (_, j) { return j === g.resaltar ? NARANJA : VERDE; });
      }
      return { label: s.nombre, data: s.valores, backgroundColor: fondo, borderRadius: 3, maxBarThickness: 28 };
    });
    new Chart(lienzo, {
      type: "bar", data: { labels: g.etiquetas, datasets: datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: leyenda, tooltip: { callbacks: { label: function (c) {
          return " " + c.dataset.label + ": " + (c.raw === null ? "sin dato" : g.pesos ? pesos.format(c.raw) : entero.format(c.raw));
        } } } },
        scales: { x: { grid: { display: false } },
                  y: { beginAtZero: true, ticks: { callback: eje(g.pesos ? "pesos" : "entero") } } }
      }
    });
  }

  function pastel(lienzo, g) {
    var total = g.valores.reduce(function (a, b) { return a + (b || 0); }, 0);
    new Chart(lienzo, {
      type: "doughnut",
      data: { labels: g.etiquetas, datasets: [{ data: g.valores, backgroundColor: PASTEL, borderWidth: 1 }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: "55%",
        plugins: { legend: leyenda, tooltip: { callbacks: { label: function (c) {
          var v = c.raw || 0;
          if (!g.pesos) { return " " + c.label + ": " + v.toFixed(1) + "%"; }
          return " " + c.label + ": " + pesos.format(v) + " (" + (total ? (100 * v / total).toFixed(1) : "0") + "%)";
        } } } } }
    });
  }

  function burbujas(lienzo, g) {
    var max = Math.max.apply(null, g.puntos.map(function (p) { return p.v || 0; })) || 1;
    var datos = g.puntos.map(function (p) {
      return { x: p.x, y: p.y, r: 4 + 13 * Math.sqrt((p.v || 0) / max), etiqueta: p.etiqueta, v: p.v, resaltar: p.resaltar };
    });
    new Chart(lienzo, {
      type: "bubble",
      data: { datasets: [{
        data: datos,
        backgroundColor: g.puntos.map(function (p) { return alfa(color(p.color), p.resaltar ? 0.9 : 0.55); }),
        borderColor: g.puntos.map(function (p) { return p.resaltar ? NARANJA : color(p.color); }),
        borderWidth: g.puntos.map(function (p) { return p.resaltar ? 3 : 1; })
      }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          lineas: { x: g.lineas_x, y: g.lineas_y },
          etiquetas: { mostrar: g.id !== "meseros" && datos.length <= 25 },
          tooltip: { callbacks: { label: function (c) {
            var p = c.raw;
            return " " + p.etiqueta + ": " + fmt(p.x, g.formato_x) + " · " + fmt(p.y, g.formato_y);
          } } }
        },
        scales: {
          x: { title: { display: true, text: g.ejes.x }, ticks: { callback: eje(g.formato_x) }, grace: "8%" },
          y: { title: { display: true, text: g.ejes.y }, ticks: { callback: eje(g.formato_y) }, grace: "10%" }
        }
      },
      plugins: [lineas, etiquetas]
    });
  }

  function arbol(lienzo, g) {
    new Chart(lienzo, {
      type: "treemap",
      data: { datasets: [{
        tree: g.items, key: "valor", spacing: 1, borderWidth: 1, borderColor: "#fff",
        backgroundColor: function (c) {
          var d = c.raw && c.raw._data; if (!d) { return BASE; }
          return alfa(color(d.color, "#6b7f7c"), d.resaltar ? 1 : 0.8);
        },
        labels: { display: true, color: "#fff", font: { size: 11, weight: "bold" },
                  formatter: function (c) { var d = c.raw._data; return [d.etiqueta, corto(d.valor)]; } }
      }] },
      options: { responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: {
          title: function (items) { return items[0].raw._data.etiqueta; },
          label: function (c) {
            var d = c.raw._data;
            return " " + pesos.format(d.valor) + (d["var"] === null ? "" : " · " + (d["var"] > 0 ? "+" : "") + (100 * d["var"]).toFixed(1) + "% vs año ant.");
          } } } } }
    });
  }

  function calor(lienzo, g) {
    var porFila = {};
    g.celdas.forEach(function (c) {
      var r = porFila[c.y] || (porFila[c.y] = { min: Infinity, max: -Infinity });
      r.min = Math.min(r.min, c.v); r.max = Math.max(r.max, c.v);
    });
    var datos = g.celdas.map(function (c) { return { x: g.columnas[c.x], y: g.filas[c.y], v: c.v, fila: c.y }; });
    new Chart(lienzo, {
      type: "matrix",
      data: { datasets: [{
        data: datos, borderWidth: 1, borderColor: "#fff",
        backgroundColor: function (c) {
          var d = c.raw; if (!d) { return BASE; }
          var r = porFila[d.fila], t = r.max > r.min ? (d.v - r.min) / (r.max - r.min) : 0.5;
          return alfa(VERDE, 0.12 + 0.88 * t);
        },
        width: function (c) { var a = c.chart.chartArea; return a ? a.width / g.columnas.length - 2 : 10; },
        height: function (c) { var a = c.chart.chartArea; return a ? a.height / g.filas.length - 2 : 10; }
      }] },
      options: { responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: {
          title: function (items) { return items[0].raw.y + " · " + items[0].raw.x; },
          label: function (c) { return " " + fmt(c.raw.v, g.formato) + " en un día promedio"; } } } },
        scales: {
          x: { type: "category", labels: g.columnas, offset: true, grid: { display: false }, position: "top" },
          y: { type: "category", labels: g.filas, offset: true, grid: { display: false } }
        } }
    });
  }

  function ranking(lienzo, g) {
    new Chart(lienzo, {
      type: "bar",
      data: { labels: g.etiquetas, datasets: [{
        data: g.valores, borderRadius: 3,
        backgroundColor: g.colores.map(function (c, i) { return g.resaltar[i] ? NARANJA : color(c, "#9a9a9a"); })
      }] },
      options: { indexAxis: "y", responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: function (c) {
          if (g.formato === "entero") { return " " + entero.format(c.raw) + (g.sufijo || ""); }
          return " " + (g.formato === "pct" && g.sufijo === undefined && c.raw > 0 ? "+" : "") + c.raw.toFixed(1) + "%"
            + (g.sufijo === undefined ? " vs año anterior" : g.sufijo); } } } },
        scales: { x: { ticks: { callback: eje(g.formato || "pct") } }, y: { grid: { display: false } } } }
    });
  }

  function mancuerna(lienzo, g) {
    var tramo = g.a.map(function (a, i) { return [Math.min(a, g.b[i]), Math.max(a, g.b[i])]; });
    new Chart(lienzo, {
      type: "bar",
      data: { labels: g.etiquetas, datasets: [
        { type: "bar", data: tramo, backgroundColor: "rgba(0,0,0,.12)", barThickness: 4, label: "_" },
        { type: "scatter", label: g.nombre_a, pointRadius: 6,
          data: g.a.map(function (v, i) { return { x: v, y: g.etiquetas[i] }; }),
          backgroundColor: g.a.map(function (v, i) { return v > g.b[i] ? LUZ.rojo : LUZ.verde; }) },
        { type: "scatter", label: g.nombre_b, pointRadius: 5, pointStyle: "rectRot",
          data: g.b.map(function (v, i) { return { x: v, y: g.etiquetas[i] }; }), backgroundColor: BASE }
      ] },
      options: { indexAxis: "y", responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, filter: function (i) { return i.text !== "_"; } } },
          tooltip: { filter: function (i) { return i.dataset.label !== "_"; }, callbacks: { label: function (c) {
            return " " + c.dataset.label + ": " + fmt(c.raw.x, g.formato); } } }
        },
        scales: { x: { ticks: { callback: eje(g.formato) } }, y: { type: "category", grid: { display: false } } } }
    });
  }

  var dibujar = { barras: barras, pastel: pastel, burbujas: burbujas, arbol: arbol, calor: calor,
                  ranking: ranking, mancuerna: mancuerna };
  graficas.forEach(function (g) {
    var lienzo = document.getElementById("g-" + g.id);
    if (!lienzo || !dibujar[g.tipo]) { return; }
    try { dibujar[g.tipo](lienzo, g); } catch (e) {
      lienzo.parentNode.innerHTML = '<p class="muted">No se pudo dibujar esta gráfica.</p>';
      if (window.console) { console.error(g.id, e); }
    }
  });
})();
