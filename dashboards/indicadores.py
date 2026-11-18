"""Indicator catalog of the dashboards.

Every indicator is a thin wrapper over Central de Reportes' engine: no
formula is written here. The commercial-traction cards take their row from
Central's own commercial indicators table (`tabla_comercial.construir_tabla`),
so a card shows exactly the value, comparison and arrow of Central's
commercial report for the same branches and period.

Each entry documents its definition, source and rule for the help page and
docs/INDICATORS.md. Status: "listo" (shown), "por_construir", "sin_fuente".
"""

from dataclasses import dataclass
from decimal import Decimal

from central.motor import formato, scorecard, semaforos, tabla_comercial
from central.motor.comparativos import Variacion

from .lectura import Seleccion


def _pct(x: Decimal) -> str:
    return f"{x * 100:.0f}%"


def regla_meta_historica() -> str:
    """The scorecard's historic-target light (owner, 2026-11-18: the dashboards
    use it on gross sales), written from Central's own constants."""
    crece = _pct(scorecard.CRECIMIENTO_META - 1)
    return (f"Semáforo (scorecard de Central): meta = mismo periodo del año anterior +{crece}; sin año "
            f"anterior, el periodo inmediato anterior +{crece}; solo sucursales comparables, y sin "
            f"comparativo fiable no hay meta ni color. Verde desde el {_pct(semaforos.PCT_META_VERDE)} de "
            f"la meta, naranja desde el {_pct(semaforos.PCT_META_NARANJA)}, rojo abajo.")


@dataclass(frozen=True)
class Indicador:
    clave: str
    etiqueta: str
    pestana: str
    definicion: str
    fuente: str
    regla: str
    fila_comercial: str  # key of Central's tabla_comercial row it shows
    regla_semaforo: str = ""  # empty = the card carries no light


CATALOGO = [
    Indicador(
        "venta_bruta",
        "Venta bruta (con IVA)",
        "portada",
        "Venta total con IVA de los cortes de caja del periodo (día operativo: un corte antes de "
        "las 14:00 cuenta para el día anterior; cortes duplicados una sola vez).",
        "Wansoft (cortes de caja), con la capa unificada Wansoft/Odoo.",
        "Contra la misma semana del año anterior (semana ISO) o el mismo mes del año anterior; "
        "solo sucursales comparables (con datos en al menos 90% de los días de ambos periodos). "
        "Flecha: sube/baja si cambia más de ±1%; «s/cf» si algún periodo no tiene datos fiables.",
        "venta_bruta",
        regla_meta_historica(),
    ),
]
POR_CLAVE = {i.clave: i for i in CATALOGO}


@dataclass(frozen=True)
class Tarjeta:
    indicador: Indicador
    valor: Decimal | None
    anio_anterior: Decimal | None
    var_anio: Variacion
    anterior: Decimal | None
    var_anterior: Variacion
    excluidas_anio: list[str]
    formato: str  # Central's display format of the row (MONEDA, PORCENTAJE...)
    # The period's value over the branches compared with last year only (equal
    # to `valor` when none is left out): the side the change is computed on.
    valor_comparable_anio: Decimal | None = None
    # Central's scorecard light of the row (verde / naranja / rojo, None = no
    # target), the value as a share of the target, and the target itself with
    # its base (META_ANIO = last year, META_ANTERIOR = previous period).
    semaforo: str | None = None
    logro: Decimal | None = None
    meta: Decimal | None = None
    meta_contra: str | None = None

    @property
    def meta_texto(self) -> str:
        return formato.valor(self.meta, self.formato)

    @property
    def logro_texto(self) -> str:
        return "" if self.logro is None else f"{self.logro * 100:.1f}%"

    @property
    def meta_base_texto(self) -> str:
        crece = _pct(scorecard.CRECIMIENTO_META - 1)
        if self.meta_contra == tabla_comercial.META_ANIO:
            return f"año anterior +{crece}"
        if self.meta_contra == tabla_comercial.META_ANTERIOR:
            return f"periodo anterior +{crece} (sin año anterior)"
        return ""

    @property
    def comparable_texto(self) -> str:
        return formato.valor(self.valor_comparable_anio, self.formato)

    @property
    def valor_texto(self) -> str:
        return formato.valor(self.valor, self.formato)

    @property
    def anio_texto(self) -> str:
        return formato.valor(self.anio_anterior, self.formato)

    @property
    def var_anio_texto(self) -> str:
        return formato.variacion(self.var_anio, self.formato)

    @property
    def anterior_texto(self) -> str:
        return formato.valor(self.anterior, self.formato)

    @property
    def var_anterior_texto(self) -> str:
        return formato.variacion(self.var_anterior, self.formato)


def tarjetas(sel: Seleccion, pestana: str) -> list[Tarjeta]:
    """The cards of a tab for a selection, from Central's commercial table."""
    filas = {f.indicador.clave: f for f in tabla_comercial.construir_tabla(
        sel.actual, sel.contra_anterior, sel.contra_anio)}
    # Same table over the comparable branches only (its "actual" column).
    comparables = {f.indicador.clave: f.actual for f in tabla_comercial.construir_tabla(
        sel.contra_anio.actual, None, None)}
    salida = []
    for ind in CATALOGO:
        if ind.pestana != pestana:
            continue
        f = filas[ind.fila_comercial]
        con_luz = bool(ind.regla_semaforo) and f.semaforo is not None
        meta = None
        if con_luz:
            base = f.anio_anterior if f.meta_contra == tabla_comercial.META_ANIO else f.anterior
            meta = scorecard.meta_historica(base, None)  # the same target Central's light used
        salida.append(Tarjeta(ind, f.actual, f.anio_anterior, f.var_anio, f.anterior, f.var_anterior,
                              sel.contra_anio.excluidas, f.indicador.formato,
                              comparables[ind.fila_comercial],
                              f.semaforo if con_luz else None, f.logro if con_luz else None, meta,
                              f.meta_contra if con_luz else None))
    return salida
