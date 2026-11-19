"""Charts of the dashboards: Central's chart data, translated for Chart.js.

No figure is computed here. Every series comes from Central's engine, the
same data its commercial report draws: `graficas.construir_graficas`
(sales and guests per day vs last year; for a month, its sales per day and
the 12-month trend), `composicion.construir` (time bands, payment methods,
platforms, weekday and hour vs last year) and the channel / mix rows of
`tabla_comercial`. This module only turns them into plain JSON-ready dicts.
"""

from decimal import Decimal

from central.motor import composicion, tabla_comercial
from central.motor.graficas import Grafica, construir_graficas

from .lectura import Lectura, Seleccion

BARRAS, PASTEL = "barras", "pastel"


def _f(v: Decimal | None) -> float | None:
    return None if v is None else float(v)


def _de_grafica(clave: str, g: Grafica) -> dict:
    series = [{"nombre": g.nombre_actual, "valores": [_f(v) for v in g.actual]}]
    if any(v is not None for v in g.base):
        series.append({"nombre": g.nombre_base, "valores": [_f(v) for v in g.base]})
    return {"id": clave, "tipo": BARRAS, "titulo": g.titulo, "etiquetas": g.etiquetas, "series": series,
            "nota": g.nota or "", "pesos": g.pesos, "resaltar": g.resaltar}


def _pastel(clave: str, titulo: str, rebanadas: list[tuple[str, Decimal, int]], pesos: bool = True,
            nota: str = "") -> dict | None:
    if not rebanadas:
        return None
    return {"id": clave, "tipo": PASTEL, "titulo": titulo, "etiquetas": [r[0] for r in rebanadas],
            "valores": [_f(r[1]) for r in rebanadas], "pesos": pesos, "nota": nota}


def _filas(sel: Seleccion) -> dict:
    return {f.indicador.clave: f for f in tabla_comercial.construir_tabla(
        sel.actual, sel.contra_anterior, sel.contra_anio)}


def de_venta(lec: Lectura, sel: Seleccion) -> list[dict]:
    """Central's two sales charts of the commercial report for this period."""
    diario = None
    if lec.diario is not None:
        diario = {n: lec.diario.get(n, {}) for n in sel.nombres}
    return [_de_grafica(f"venta{i}", g) for i, g in enumerate(
        construir_graficas(lec.periodo, sel.actual, sel.contra_anterior, sel.contra_anio, diario))]


def de_mezcla(sel: Seleccion) -> list[dict]:
    """Channel and food / drinks shares, from Central's commercial rows (in %)."""
    filas = _filas(sel)
    salida = []
    for clave, titulo, claves in (
            ("canales", "Venta por canal", ("canal_salon", "canal_llevar", "canal_plataformas")),
            ("mezcla", "Alimentos y bebidas", ("mix_alimentos", "mix_bebidas"))):
        rebanadas = [(filas[k].indicador.etiqueta.split(": ", 1)[-1], filas[k].actual * 100, 0)
                     for k in claves if filas[k].actual]
        p = _pastel(clave, titulo, rebanadas, pesos=False)
        if p:
            salida.append(p)
    return salida


def de_composicion(sel: Seleccion) -> list[dict]:
    """Central's sales composition: time bands, payment methods, platforms
    (pies), and weekday / hour vs last year (bars)."""
    c = composicion.construir(sel.actual, sel.contra_anio, "Año anterior")  # Central's own label
    if c.vacia:
        return []
    salida = [p for p in (_pastel(f"pastel{i}", titulo, rebanadas)
                          for i, (titulo, rebanadas) in enumerate(c.pasteles)) if p]
    salida += [_de_grafica(f"barra{i}", g) for i, g in enumerate(c.barras)]
    return salida


# ---------------------------------------------------------------------------
# Network charts (owner, 2026-11-18: "gráficas, no solo barras y pay":
# bubble matrix, treemap, heatmap, diverging ranking, dumbbell). Every value
# is a figure of Central's tables for each branch, read from the same cached
# reading; these functions only place them.
# ---------------------------------------------------------------------------
from central.motor.composicion import DIAS, dias_horario  # noqa: E402
from central.motor.metricas import consolidar  # noqa: E402
from central.motor.reporte_meseros import construir_tabla as tabla_meseros, filas_meseros  # noqa: E402

from . import lectura as _lectura  # noqa: E402

BURBUJAS, ARBOL, CALOR, RANKING, MANCUERNA = "burbujas", "arbol", "calor", "ranking", "mancuerna"
_CORTO = {"Isabel La Católica": "Isabel", "Taquería Parroquia": "Tq. Parroquia", "Taquería Viaducto": "Tq. Viaducto",
          "Versalles (Taquería Exhibimex)": "Versalles", "CentroMyJ (Mario y July)": "CentroMyJ",
          "La Esquina Coyoacán": "La Esquina", "Playa del Carmen": "Playa"}


def corto(nombre: str) -> str:
    return _CORTO.get(nombre, nombre)


def _filas_por_sucursal(lec: Lectura) -> list[tuple]:
    """(branch, its Central commercial rows) for every active branch."""
    salida = []
    for s in lec.sucursales:
        sel = _lectura.seleccionar(lec, s.clave)
        salida.append((s, _filas(sel)))
    return salida


def de_portada(lec: Lectura, resaltar: str | None) -> list[dict]:
    """Network charts of the overview: performance matrix, sales treemap,
    growth ranking and the weekday heatmap. `resaltar`: the selected branch."""
    por = _filas_por_sucursal(lec)
    salida = []

    # 1. Performance matrix: growth vs last year (x) and total cost % (y), bubble = sales.
    puntos, fuera = [], []
    for s, f in por:
        x, y, v = f["venta_bruta"].var_anio.porcentaje, f["costo_total_pct"].actual, f["venta_bruta"].actual
        if x is None or y is None or not s.considerar_costo:
            fuera.append(corto(s.nombre))
            continue
        puntos.append({"etiqueta": corto(s.nombre), "x": _f(x * 100), "y": _f(y * 100), "v": _f(v),
                       "color": f["costo_total_pct"].semaforo, "resaltar": s.clave == resaltar})
    if puntos:
        salida.append({"id": "matriz", "tipo": BURBUJAS, "titulo": "Matriz de desempeño: crecimiento vs costo",
                       "puntos": puntos,
                       "ejes": {"x": "Venta bruta vs año anterior (%)", "y": "Costo total / venta neta (%)"},
                       "formato_x": "pct", "formato_y": "pct", "lineas_x": [0], "lineas_y": [37, 39],
                       "nota": "Burbuja = venta bruta; color = semáforo del costo (banda 37% a <39%)."
                               + (f" Sin año anterior o sin costo: {', '.join(fuera)}." if fuera else "")})

    # 2. Treemap: each branch's gross sales, coloured by its change vs last year.
    items = [{"etiqueta": corto(s.nombre), "valor": _f(f["venta_bruta"].actual),
              "color": f["venta_bruta"].var_anio.color, "var": _f(f["venta_bruta"].var_anio.porcentaje),
              "resaltar": s.clave == resaltar}
             for s, f in por if f["venta_bruta"].actual]
    if items:
        salida.append({"id": "arbol", "tipo": ARBOL, "titulo": "Peso de cada sucursal en la venta bruta",
                       "items": items, "nota": "Tamaño = venta bruta; color = cambio contra el año anterior "
                                               "(verde sube, rojo baja, gris sin cambio o sin comparativo)."})

    # 3. Diverging ranking of the change vs last year.
    rank = sorted(((corto(s.nombre), f["venta_bruta"].var_anio, s.clave == resaltar) for s, f in por
                   if f["venta_bruta"].var_anio.porcentaje is not None),
                  key=lambda t: t[1].porcentaje, reverse=True)
    if rank:
        salida.append({"id": "ranking", "tipo": RANKING, "titulo": "Crecimiento de la venta vs año anterior",
                       "etiquetas": [r[0] for r in rank], "valores": [_f(r[1].porcentaje * 100) for r in rank],
                       "colores": [r[1].color for r in rank], "resaltar": [r[2] for r in rank], "formato": "pct",
                       "nota": "Solo sucursales con el periodo del año anterior completo."})

    # 4. Heatmap: average day of each weekday per branch (Central's composicion.dias_horario).
    filas, celdas = [], []
    for s in lec.sucursales:
        i = [x.clave for x in lec.sucursales].index(s.clave)
        dias = {d.dia[:3]: d for d in dias_horario(lec.actual[i], None, None)}
        if not dias:
            continue
        fila = len(filas)
        filas.append(corto(s.nombre))
        for j, nombre in enumerate(DIAS):
            d = dias.get(nombre[:3])
            if d is not None:
                celdas.append({"x": j, "y": fila, "v": _f(d.total)})
    if celdas:
        salida.append({"id": "calor", "tipo": CALOR, "titulo": "Mapa de calor: venta de un día promedio",
                       "filas": filas, "columnas": DIAS, "celdas": celdas, "formato": "pesos",
                       "nota": "Venta bruta promedio de cada día de la semana en el periodo (del detalle de "
                               "tickets); el color se compara dentro de cada sucursal."})
    return salida


def de_operaciones(lec: "_lectura.LecturaOperaciones", sel: "_lectura.SeleccionOperaciones",
                   resaltar: str | None) -> list[dict]:
    """Operaciones charts: productivity bubble per branch, butchery dumbbell,
    and for one branch its waiters."""
    salida = []
    puntos = []
    for s in lec.sucursales:
        o = _lectura.seleccionar_operaciones(lec, s.clave)
        f = {x.indicador.clave: x for x in tabla_meseros(o.actual, o.contra_anterior, o.contra_anio)}
        x, y, v = f["venta_mesero_dia"].actual, f["propina"].actual, f["cuentas"].actual
        if x is None or y is None:
            continue
        puntos.append({"etiqueta": corto(s.nombre), "x": _f(x), "y": _f(y * 100), "v": _f(v),
                       "color": None, "resaltar": s.clave == resaltar})
    if puntos:
        from .indicadores import UMBRALES_BORRADOR
        salida.append({"id": "productividad", "tipo": BURBUJAS,
                       "titulo": "Productividad de salón: venta por mesero por día vs propina",
                       "puntos": puntos, "ejes": {"x": "Venta por mesero por día ($)", "y": "Propina (%)"},
                       "formato_x": "pesos", "formato_y": "pct",
                       "lineas_x": [_f(UMBRALES_BORRADOR["venta_mesero_dia"][0])],
                       "lineas_y": [_f(UMBRALES_BORRADOR["propina"][0] * 100)],
                       "nota": "Burbuja = mesas atendidas; líneas = metas del portal ($14,500 y 9%)."})

    carne = sel.tablajeria
    if carne is not None and carne.filas:
        if carne.consolidado:  # one row per branch: its % vs the % its own mix of cuts explains
            filas = [f for f in carne.filas if f.indice is not None and f.esperado is not None]
            nombre_b, titulo = "Esperado por su mezcla de cortes", "Merma de tablajería: real vs esperado"
            valores_b = [_f(f.esperado * 100) for f in filas]
            nota = ("Esperado = lo que perdería la sucursal con SUS cortes si cada corte perdiera lo que pierde "
                    "el grupo (cálculo de Central). Arriba de la marca: pierde más de lo que explica su mezcla.")
        else:  # one row per base product: the branch vs every branch
            filas = [f for f in carne.filas if f.indice is not None and f.indice_grupo is not None][:12]
            nombre_b, titulo = "Todas las sucursales", "Merma por corte: sucursal vs todas"
            valores_b = [_f(f.indice_grupo * 100) for f in filas]
            nota = "Los 12 cortes con más merma de la sucursal."
        if filas:
            salida.append({"id": "merma", "tipo": MANCUERNA, "titulo": titulo,
                           "etiquetas": [corto(f.etiqueta) for f in filas],
                           "a": [_f(f.indice * 100) for f in filas], "b": valores_b,
                           "nombre_a": "Real", "nombre_b": nombre_b, "formato": "pct", "nota": nota})

    if resaltar is not None:  # one branch: its waiters, sales per day worked vs tables served
        anterior = sel.contra_anterior.base
        meseros = [{"etiqueta": r.nombre.split(" · ")[-1], "x": _f(r.m.cuentas), "y": _f(r.m.venta_por_dia),
                    "v": _f(r.m.venta_bruta), "color": r.semaforo_cheque, "resaltar": False}
                   for r in filas_meseros(sel.actual, anterior) if r.m.venta_por_dia is not None]
        if meseros:
            salida.append({"id": "meseros", "tipo": BURBUJAS, "titulo": "Meseros: mesas atendidas vs venta por día",
                           "puntos": meseros, "ejes": {"x": "Mesas atendidas", "y": "Venta por día trabajado ($)"},
                           "formato_x": "entero", "formato_y": "pesos", "lineas_x": [], "lineas_y": [],
                           "nota": "Burbuja = venta del mesero; color = su cheque promedio contra el de la "
                                   "sucursal (regla del reporte de meseros de Central)."})
    return salida


def de_cedis(sel: "_lectura.SeleccionCedis", consolidado: bool) -> list[dict]:
    """CEDIS charts from Central's results: fill rate per branch, who modified
    the orders, the 20 inputs' price change, and the most changed products."""
    from central.motor import inflacion_insumos, reporte_cedis
    salida = []
    if consolidado:
        filas = sorted((x for x in sel.fill.por_sucursal if x.fill is not None), key=lambda x: x.fill, reverse=True)
        if filas:
            salida.append({"id": "fill", "tipo": RANKING, "titulo": "Fill rate por sucursal",
                           "etiquetas": [corto(x.grupo) for x in filas], "valores": [_f(x.fill * 100) for x in filas],
                           "colores": [x.estado for x in filas], "resaltar": [False] * len(filas), "formato": "pct",
                           "sufijo": " de lo pedido entregado",
                           "nota": "Verde desde 98%, naranja desde 95% (regla del borrador, en Central)."})
        por = {}
        for r in sel.modificaciones:
            a = por.setdefault(r["sucursal"], [0, 0])
            a[0] += r["por_sucursal"]
            a[1] += r["por_cedis"]
        if por:
            nombres = sorted(por, key=lambda n: -(por[n][0] + por[n][1]))
            salida.append({"id": "modif", "tipo": BARRAS, "titulo": "Pedidos modificados después de confirmar",
                           "etiquetas": [corto(n) for n in nombres],
                           "series": [{"nombre": "Por la sucursal", "valores": [por[n][0] for n in nombres]},
                                      {"nombre": "Por el CEDIS", "valores": [por[n][1] for n in nombres]}],
                           "nota": "Un pedido cambiado por los dos cuenta en ambas barras.", "pesos": False,
                           "resaltar": None})
    infl = sel.inflacion
    if infl is not None and infl.filas:
        filas = sorted((x for x in infl.filas if x.variacion is not None), key=lambda x: x.variacion, reverse=True)
        if filas:
            salida.append({"id": "insumos", "tipo": RANKING, "titulo": "Precio de los 20 insumos clave vs año anterior",
                           "etiquetas": [x.nombre[:28] for x in filas], "valores": [_f(x.variacion * 100) for x in filas],
                           "colores": [inflacion_insumos.estado(x.variacion, infl.inpc) for x in filas],
                           "resaltar": [False] * len(filas), "formato": "pct", "sufijo": " vs año anterior",
                           "nota": "Precio promedio ponderado de compra; color contra el INPC (verde hasta el INPC, "
                                   "naranja hasta INPC + 2 pp)."})
    cambiados = reporte_cedis.productos_mas_cambiados(sel.datos)[:10]
    if cambiados:
        salida.append({"id": "cambiados", "tipo": RANKING, "titulo": "Productos más cambiados en los pedidos",
                       "etiquetas": [x["producto"][:28] for x in cambiados], "valores": [x["cambios"] for x in cambiados],
                       "colores": ["naranja"] * len(cambiados), "resaltar": [False] * len(cambiados),
                       "formato": "entero", "sufijo": " cambios",
                       "nota": "Cambios de cantidad y líneas extra después de confirmar."})
    return salida

