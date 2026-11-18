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
