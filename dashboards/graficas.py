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
