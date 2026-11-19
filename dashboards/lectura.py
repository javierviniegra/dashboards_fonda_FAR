"""Reading the sources through Central's engine, with a one-hour cache.

One read = Central's `metricas.recolectar` for ALL active branches over three
periods (the chosen one, the previous one, the same one last year): the
engine batches every branch into one query per period, so the consolidated
and every single branch are served from the same read. The result (Central's
own `Metricas` objects) is cached one hour (owner, 2026-11-17), keyed by the
period, the branch list and the engine's commit -- moving the submodule never
serves numbers computed by older code.

Selections are cut from the read with Central's comparable-branches rule
(`metricas.comparables`), exactly as Central's commercial report does for a
consolidated or a single branch.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime

from django.core.cache import cache
from django.utils import timezone

from central.motor import metricas
from central.motor.graficas import ventana_tendencia
from central.motor.fuentes import conexiones, odoo
from central.motor.periodo import Periodo, TipoPeriodo

from . import motor_central
from .models import Sucursal

log = logging.getLogger(__name__)

# v1 periods (owner, 2026-11-17): week and month, closed ones only -- an open
# period counts days not yet lived as expected and would always read "s/cf".
TIPOS = (TipoPeriodo.SEMANA, TipoPeriodo.MES)
PERIODOS_A_ELEGIR = 12


def periodos_cerrados(tipo: TipoPeriodo, hoy: date | None = None, n: int = PERIODOS_A_ELEGIR) -> list[Periodo]:
    """The last `n` periods of `tipo` that ended before `hoy`, newest first."""
    hoy = hoy or timezone.localdate()
    p = Periodo.de_fecha(tipo, hoy)
    if p.hasta >= hoy:
        p = p.anterior()
    salida = []
    while len(salida) < n:
        salida.append(p)
        p = p.anterior()
    return salida


def periodo_de(tipo: str, desde: str, hoy: date | None = None) -> Periodo:
    """The closed period of `tipo` starting `desde` (ISO date); ValueError
    when it is not one the screen offers."""
    t = TipoPeriodo(tipo)
    if t not in TIPOS:
        raise ValueError(tipo)
    d = date.fromisoformat(desde)
    for p in periodos_cerrados(t, hoy):
        if p.desde == d:
            return p
    raise ValueError(desde)


@dataclass
class Lectura:
    """Central's metrics of every branch (same order as `sucursales`) for the
    period, the previous period and the same period last year (None when it
    does not exist), and when they were read."""

    sucursales: list[Sucursal]
    periodo: Periodo
    anterior: Periodo
    anio_anterior: Periodo | None
    actual: list
    previo: list
    anio: list | None
    leido_en: datetime
    origen: str  # "prod" / "dev": which sources were read
    # A month only: gross sales per branch name and day over the 24 months
    # ending with it (Central's metricas.recolectar_diario), for the trend chart.
    diario: dict | None = None


def _clave(periodo: Periodo, sucursales: list[Sucursal], costos: bool) -> str:
    ids = ",".join(str(s.pk) for s in sucursales)
    return (f"lectura:{motor_central.version()}:{periodo.tipo.value}:{periodo.desde}:{periodo.hasta}"
            f":{int(costos)}:{ids}")


def _abrir_odoo():
    """Read-only Odoo client for the invoiced sales behind the estimated
    cost, or None when Odoo cannot be reached (the costs then come out
    flagged by Central's engine), as Central's commercial report does."""
    try:
        return odoo.abrir_odoo()
    except Exception:
        log.exception("Odoo no disponible para el costo estimado")
        return None


def leer(periodo: Periodo, costos: bool = True, refrescar: bool = False,
         duracion: int | None = None) -> Lectura:
    """Every active branch's metrics for `periodo` and its comparisons, from
    the cache when read in the last hour (unless `refrescar`). `duracion`
    (seconds) overrides the cache's one hour for this entry (warm-up)."""
    sucursales = list(Sucursal.objects.filter(activa=True).order_by("nombre"))
    clave = _clave(periodo, sucursales, costos)
    if not refrescar:
        guardada = cache.get(clave)
        if guardada is not None:
            return guardada
    anterior = periodo.anterior()
    anio_ant = periodo.mismo_periodo_anio_anterior()
    cli = _abrir_odoo() if costos and any(s.odoo_company_id for s in sucursales) else None
    with conexiones.abrir_wansoft() as cw, conexiones.abrir_presupuestos() as cp:
        def una(p):
            return metricas.recolectar(cw, cp, sucursales, p, odoo=cli, incluir_costos=costos)
        actual, previo = una(periodo), una(anterior)
        anio = None if anio_ant is None else (previo if anio_ant == anterior else una(anio_ant))
        diario = (metricas.recolectar_diario(cw, sucursales, *ventana_tendencia(periodo))
                  if periodo.tipo == TipoPeriodo.MES else None)
    lectura = Lectura(sucursales, periodo, anterior, anio_ant, actual, previo, anio,
                      timezone.now(), conexiones.origen(), diario)
    if duracion is None:
        cache.set(clave, lectura)
    else:
        cache.set(clave, lectura, duracion)
    return lectura


# Warm-up (owner, 2026-11-18): the periods the meetings open most -- the last
# closed week and the last closed month -- are read ahead by `manage.py
# precalentar` on a schedule (hourly), so nobody waits for a fresh read.
# Those entries live a little longer than the hourly schedule, so the
# previous one is still there while the next run reads (a run takes minutes).
DURACION_PRECALENTADO = 75 * 60


def periodos_a_precalentar(hoy: date | None = None) -> list[Periodo]:
    return [periodos_cerrados(t, hoy, 1)[0] for t in TIPOS]


def precalentar(hoy: date | None = None) -> list[tuple[Periodo, float]]:
    """Read every warm-up period afresh into the cache; (period, seconds) each."""
    salida = []
    for p in periodos_a_precalentar(hoy):
        inicio = timezone.now()
        leer(p, refrescar=True, duracion=DURACION_PRECALENTADO)
        # Operaciones' own reading (defined below; resolved at call time).
        leer_operaciones(p, refrescar=True, duracion=DURACION_PRECALENTADO)
        leer_cedis(p, refrescar=True, duracion=DURACION_PRECALENTADO)
        salida.append((p, (timezone.now() - inicio).total_seconds()))
    return salida


@dataclass
class Seleccion:
    """A selection (consolidated or one branch) cut from a reading, as
    Central's commercial report builds it."""

    nombre: str
    nombres: list[str]  # the branches it covers
    actual: metricas.Metricas
    contra_anterior: metricas.Comparacion
    contra_anio: metricas.Comparacion
    con_costo: bool = True  # False: a single branch whose cost is not considered (Metepec)
    sin_costo: tuple[str, ...] = ()  # consolidated: branches whose cost is not considered
    facturado_incompleto: bool = False  # consolidated: invoiced cost dropped (some branches lack it)


def seleccionar(lectura: Lectura, clave: str | None) -> Seleccion:
    """`clave` = a branch key, or None for the consolidated of every active branch."""
    if clave is None:
        indices, nombre = list(range(len(lectura.sucursales))), "Consolidado"
    else:
        indices = [i for i, s in enumerate(lectura.sucursales) if s.clave == clave]
        if not indices:
            raise KeyError(clave)
        nombre = lectura.sucursales[indices[0]].nombre
    nombres = [lectura.sucursales[i].nombre for i in indices]
    act = [lectura.actual[i] for i in indices]
    prev = [lectura.previo[i] for i in indices]
    anio = [lectura.anio[i] for i in indices] if lectura.anio is not None else None
    sel = Seleccion(
        nombre,
        nombres,
        metricas.consolidar(act, lectura.periodo),
        metricas.comparables(nombres, act, prev, lectura.periodo, lectura.anterior),
        metricas.comparables(nombres, act, anio, lectura.periodo, lectura.anio_anterior),
    )
    if clave is not None:
        sel.con_costo = lectura.sucursales[indices[0]].considerar_costo
        return sel
    sel.sin_costo = tuple(lectura.sucursales[i].nombre for i in indices
                          if not lectura.sucursales[i].considerar_costo)
    # Central's consolidated rule (owner, 2026-10-05): a budget or an invoiced
    # cost is shown only when every branch has it, each period on its own; a
    # partial one would stain the whole figure.
    for m in (sel.actual, sel.contra_anterior.actual, sel.contra_anterior.base,
              sel.contra_anio.actual, sel.contra_anio.base):
        if m is None:
            continue
        if 0 < m.n_con_presupuesto < m.n_sucursales:
            metricas.sin_presupuesto(m)
        if 0 < m.n_con_costo_ventas < m.n_sucursales:
            metricas.sin_costo_facturado(m)
            sel.facturado_incompleto = True
    return sel


# ---------------------------------------------------------------------------
# Operaciones (block 4): Central's waiters' report data and butchery pieces.
# A reading of its own (own cache entry), so the overview and Comercial do not
# pay for it. Same rules as Central's reports: the waiters' comparable branches
# (`reporte_meseros.comparables`) and the butchery section (`tablajeria`).
# ---------------------------------------------------------------------------
from central.motor import meseros as datos_meseros  # noqa: E402
from central.motor import reporte_meseros, tablajeria  # noqa: E402
from central.motor.fuentes import wansoft  # noqa: E402


@dataclass
class LecturaOperaciones:
    sucursales: list[Sucursal]
    periodo: Periodo
    anterior: Periodo
    anio_anterior: Periodo | None
    meseros_actual: list
    meseros_previo: list
    meseros_anio: list | None
    piezas_actual: list | None  # butchery pieces of every branch (None: could not be read)
    piezas_anio: list | None
    leido_en: datetime
    origen: str


def leer_operaciones(periodo: Periodo, refrescar: bool = False, duracion: int | None = None) -> LecturaOperaciones:
    """Waiters' data (Central's `meseros.recolectar`) for the period, the
    previous one and last year, and the butchery pieces of the period and last
    year (`wansoft.piezas_tablajeria`), for every active branch; cached as `leer`."""
    sucursales = list(Sucursal.objects.filter(activa=True).order_by("nombre"))
    clave = "operaciones:" + _clave(periodo, sucursales, False)
    if not refrescar:
        guardada = cache.get(clave)
        if guardada is not None:
            return guardada
    anterior, anio_ant = periodo.anterior(), periodo.mismo_periodo_anio_anterior()
    with conexiones.abrir_wansoft() as cw:
        ma = datos_meseros.recolectar(cw, sucursales, periodo)
        mp = datos_meseros.recolectar(cw, sucursales, anterior)
        my = None if anio_ant is None else (mp if anio_ant == anterior
                                            else datos_meseros.recolectar(cw, sucursales, anio_ant))
        ids = sorted(s.wansoft_subsidiary_id for s in sucursales if s.wansoft_subsidiary_id)
        try:  # as Central: the butchery never breaks the page
            pa = wansoft.piezas_tablajeria(cw, ids, periodo.desde, periodo.hasta)
            py = wansoft.piezas_tablajeria(cw, ids, anio_ant.desde, anio_ant.hasta) if anio_ant else []
        except Exception:
            log.exception("Tablajería no disponible")
            pa = py = None
    lec = LecturaOperaciones(sucursales, periodo, anterior, anio_ant, ma, mp, my, pa, py,
                             timezone.now(), conexiones.origen())
    if duracion is None:
        cache.set(clave, lec)
    else:
        cache.set(clave, lec, duracion)
    return lec


@dataclass
class SeleccionOperaciones:
    nombre: str
    actual: datos_meseros.DatosMeseros
    contra_anterior: metricas.Comparacion
    contra_anio: metricas.Comparacion
    tablajeria: "tablajeria.Tablajeria | None"
    con_costo: bool = True


def seleccionar_operaciones(lec: LecturaOperaciones, clave: str | None) -> SeleccionOperaciones:
    """The consolidated (None) or one branch, as Central's waiters' report and
    the commercial report's butchery section build them."""
    if clave is None:
        indices, nombre = list(range(len(lec.sucursales))), "Consolidado"
    else:
        indices = [i for i, s in enumerate(lec.sucursales) if s.clave == clave]
        if not indices:
            raise KeyError(clave)
        nombre = lec.sucursales[indices[0]].nombre
    sucs = [lec.sucursales[i] for i in indices]
    nombres = [s.nombre for s in sucs]
    ma = [lec.meseros_actual[i] for i in indices]
    mp = [lec.meseros_previo[i] for i in indices]
    my = [lec.meseros_anio[i] for i in indices] if lec.meseros_anio is not None else None
    if clave is None:
        actual = datos_meseros.consolidar(ma, lec.periodo, nombres)
    else:
        actual = ma[0]
    con_costo = clave is None or sucs[0].considerar_costo
    carne = None
    if lec.piezas_actual is not None:
        todos = {s.wansoft_subsidiary_id: s.nombre for s in lec.sucursales if s.wansoft_subsidiary_id}
        seleccion = [s.wansoft_subsidiary_id for s in sucs if s.wansoft_subsidiary_id]
        carne = tablajeria.construir(lec.piezas_actual, lec.piezas_anio, todos, seleccion, clave is None, con_costo)
    return SeleccionOperaciones(
        nombre, actual,
        reporte_meseros.comparables(nombres, ma, mp, lec.periodo, lec.anterior),
        reporte_meseros.comparables(nombres, ma, my, lec.periodo, lec.anio_anterior),
        carne, con_costo)


# ---------------------------------------------------------------------------
# CEDIS (block 5): Central's CEDIS reading (Odoo, provider side), its fill
# rate and the top-20 input inflation. The customer -> branch mapping and the
# INPC are read (read-only) from Central's own database (owner, 2026-11-18),
# with the queries Central's engine publishes for that.
# ---------------------------------------------------------------------------
from dataclasses import replace as _replace  # noqa: E402

from central.motor import fill_rate, inflacion_insumos, reporte_cedis  # noqa: E402


def _de_central() -> tuple[list, set[str], dict]:
    """(mapping rows, active branch keys, {month: INPC}) from Central's DB."""
    with conexiones._abrir("CENTRAL_DB") as cur:  # Central's read-only session (120 s cap)
        cur.execute(reporte_cedis.CONSULTA_CLIENTES)
        cols = [c[0] for c in cur.description]
        clientes = [reporte_cedis.fila_cliente(dict(zip(cols, fila))) for fila in cur.fetchall()]
        cur.execute(reporte_cedis.CONSULTA_ACTIVAS)
        activas = {fila[0] for fila in cur.fetchall()}
        cur.execute("SELECT mes, inpc FROM central_inflacion")
        inpc = {mes: valor for mes, valor in cur.fetchall()}
    return clientes, activas, inpc


@dataclass
class LecturaCedis:
    sucursales: list[Sucursal]
    periodo: Periodo
    datos: "reporte_cedis.DatosCedis"
    inpc: dict
    leido_en: datetime
    origen: str


def leer_cedis(periodo: Periodo, refrescar: bool = False, duracion: int | None = None) -> LecturaCedis:
    """Every order of the period to El Bodegón / Las Empanadas for every active
    branch (Central's `reporte_cedis.leer`), cached as `leer`."""
    sucursales = list(Sucursal.objects.filter(activa=True).order_by("nombre"))
    clave = "cedis:" + _clave(periodo, sucursales, False)
    if not refrescar:
        guardada = cache.get(clave)
        if guardada is not None:
            return guardada
    clientes, activas, inpc = _de_central()
    datos = reporte_cedis.leer(sucursales, periodo.desde, periodo.hasta, clientes=clientes, activas=activas)
    lec = LecturaCedis(sucursales, periodo, datos, inpc, timezone.now(), conexiones.origen())
    if duracion is None:
        cache.set(clave, lec)
    else:
        cache.set(clave, lec, duracion)
    return lec


@dataclass
class SeleccionCedis:
    nombre: str
    datos: "reporte_cedis.DatosCedis"  # the orders of the selection only
    fill: "fill_rate.ResumenFill"
    modificaciones: list[dict]  # Central's `resumen` rows (provider x branch)
    total: dict  # Central's `total_resumen`
    inflacion: "inflacion_insumos.InflacionInsumos | None"


def _inflacion(lec: LecturaCedis, sucs: list[Sucursal], refrescar: bool = False):
    """Central's top-20 input inflation of a selection, cached per selection."""
    clave = "inflacion:" + _clave(lec.periodo, sucs, False)
    if not refrescar:
        guardada = cache.get(clave)
        if guardada is not None:
            return guardada
    with conexiones.abrir_wansoft() as cur:
        r = inflacion_insumos.calcular(cur, sucs, lec.periodo, lec.inpc)
    cache.set(clave, r)
    return r


def seleccionar_cedis(lec: LecturaCedis, clave: str | None, refrescar: bool = False) -> SeleccionCedis:
    """The consolidated (None: every order read, customers outside our branches
    included, as Central's workbooks with every branch) or one branch."""
    if clave is None:
        nombre, sucs, datos = "Consolidado", lec.sucursales, lec.datos
    else:
        sucs = [s for s in lec.sucursales if s.clave == clave]
        if not sucs:
            raise KeyError(clave)
        nombre = sucs[0].nombre
        ordenes = [o for o in lec.datos.ordenes if o.sucursal == nombre]
        datos = _replace(lec.datos, ordenes=ordenes, sucursales=[nombre] if ordenes else [])
    filas = reporte_cedis.resumen(datos)
    try:
        infl = _inflacion(lec, sucs, refrescar)
    except Exception:  # Wansoft purchases unreachable: the rest of the tab still shows
        log.exception("Inflación de insumos no disponible")
        infl = None
    return SeleccionCedis(nombre, datos, fill_rate.resumen(datos), filas, reporte_cedis.total_resumen(filas), infl)
