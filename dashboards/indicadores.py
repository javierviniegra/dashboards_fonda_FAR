"""Indicator catalog of the dashboards.

Every indicator is a thin wrapper over Central de Reportes' engine: no
formula is written here. The commercial-traction cards take their row from
Central's own commercial indicators table (`tabla_comercial.construir_tabla`),
so a card shows exactly the value, comparison, arrow and light of Central's
commercial report for the same branches and period.

Each entry documents its definition, source and rules for the help page and
docs/INDICATORS.md. Status: "listo" (shown), "pendiente" (source exists, not
reachable yet), "sin_fuente" (no systematized source yet).
"""

from dataclasses import dataclass
from decimal import Decimal

from central.motor import formato, scorecard, semaforos, tabla_comercial
from central.motor.comparativos import Variacion, kpi_costo

from .lectura import Seleccion

LISTO, PENDIENTE, SIN_FUENTE = "listo", "pendiente", "sin_fuente"
# Kinds of light, each with its rule written from Central's constants.
LUZ_HISTORICA, LUZ_UMBRAL, LUZ_BANDA = "historica", "umbral", "banda"


def _pct(x: Decimal) -> str:
    return f"{x * 100:.0f}%"


def regla_meta_historica() -> str:
    """The scorecard's historic-target light (owner, 2026-11-18)."""
    crece = _pct(scorecard.CRECIMIENTO_META - 1)
    return (f"Semáforo (scorecard de Central): meta = mismo periodo del año anterior +{crece}; sin año "
            f"anterior, el periodo inmediato anterior +{crece}; solo sucursales comparables, y sin "
            f"comparativo fiable no hay meta ni color. Verde desde el {_pct(semaforos.PCT_META_VERDE)} de "
            f"la meta, naranja desde el {_pct(semaforos.PCT_META_NARANJA)}, rojo abajo.")


def regla_mix() -> str:
    mix = scorecard.POR_CLAVE["mix_bebidas"]
    return (f"Semáforo (scorecard de Central): verde desde {_pct(mix.verde)}, naranja desde "
            f"{_pct(mix.naranja)}, rojo abajo de {_pct(mix.naranja)}.")


def regla_costo() -> str:
    """Central's commercial cost band (owner, 2026-11-18: the dashboards use it)."""
    k = kpi_costo()
    return (f"Semáforo (banda del reporte comercial de Central): verde de {_pct(k.verde)} a menos de "
            f"{_pct(k.naranja)} de la venta neta; naranja abajo de {_pct(k.verde)} (se compró o se "
            f"registró de menos); rojo desde {_pct(k.naranja)}.")


def meta_corta(luz: str) -> str:
    """One line under a card's value for fixed-threshold and band lights."""
    if luz == LUZ_UMBRAL:
        return f"meta: {_pct(scorecard.POR_CLAVE['mix_bebidas'].verde)} o más"
    if luz == LUZ_BANDA:
        k = kpi_costo()
        return f"meta: de {_pct(k.verde)} a menos de {_pct(k.naranja)}"
    return ""


_COMPARACION = ("Contra la misma semana del año anterior (semana ISO) o el mismo mes del año anterior, "
                "y contra el periodo anterior; solo sucursales comparables (con datos en al menos 90% de "
                "los días de ambos periodos). Flecha: sube/baja si cambia más de ±1% (±1 punto en "
                "porcentajes); «s/cf» si algún periodo no tiene datos fiables.")
_DIA_OPERATIVO = "día operativo: un corte antes de las 14:00 cuenta para el día anterior; cortes duplicados una sola vez"
_COSTO_COMPARACION = _COMPARACION + " Los costos son sobre la venta neta (sin IVA)."


@dataclass(frozen=True)
class Indicador:
    clave: str
    etiqueta: str
    pestanas: tuple[str, ...]  # tabs that show it
    definicion: str
    fuente: str
    regla: str
    fila_comercial: str = ""  # key of Central's tabla_comercial row it shows ("" = not shown yet)
    luz: str = ""  # LUZ_*; "" = no light
    estado: str = LISTO
    es_costo: bool = False
    pendiente: str = ""  # why it is not shown yet (estado != LISTO)

    @property
    def regla_semaforo(self) -> str:
        return {LUZ_HISTORICA: regla_meta_historica, LUZ_UMBRAL: regla_mix,
                LUZ_BANDA: regla_costo}.get(self.luz, lambda: "")()


CATALOGO = [
    Indicador("venta_bruta", "Venta bruta (con IVA)", ("portada", "comercial"),
              f"Venta total con IVA de los cortes de caja del periodo ({_DIA_OPERATIVO}).",
              "Wansoft (cortes de caja), con la capa unificada Wansoft/Odoo.",
              _COMPARACION, "venta_bruta", LUZ_HISTORICA),
    Indicador("venta_neta", "Venta neta (sin IVA)", ("portada",),
              f"Venta sin IVA de los cortes de caja del periodo ({_DIA_OPERATIVO}). Sin semáforo: no hay "
              "presupuesto de ventas en ninguna fuente.",
              "Wansoft (cortes de caja).", _COMPARACION, "venta_neta"),
    Indicador("clientes", "Clientes", ("portada", "comercial"),
              "Personas registradas en las cuentas del periodo, de todas las órdenes (salón, para llevar y "
              "plataformas; cada orden fuera de salón cuenta 1).",
              "Wansoft (cortes de caja).", _COMPARACION, "clientes", LUZ_HISTORICA),
    Indicador("afluencia_salon", "Afluencia de salón", ("portada",),
              "Personas atendidas en las órdenes de restaurante (salón) solamente, como el scorecard de "
              "Semáforos (Power BI).",
              "Wansoft (detalle de tickets), lectura del scorecard de Central.", _COMPARACION,
              estado=PENDIENTE,
              pendiente="El motor de Central todavía no publica el conteo de salón del scorecard; se muestra "
                        "en cuanto esté en su repositorio."),
    Indicador("cheque_promedio", "Cheque promedio", ("portada", "comercial"),
              "Venta bruta (con IVA) / clientes.", "Wansoft (cortes de caja).", _COMPARACION,
              "cheque_promedio", LUZ_HISTORICA),
    Indicador("ticket_promedio", "Ticket promedio", ("portada", "comercial"),
              "Venta bruta (con IVA) / tickets (cuentas).", "Wansoft (cortes de caja).", _COMPARACION,
              "ticket_promedio", LUZ_HISTORICA),
    Indicador("mix_bebidas", "Mezcla de bebidas", ("portada", "comercial"),
              "Venta de bebidas / venta de alimentos y bebidas, del detalle de tickets.",
              "Wansoft (detalle de tickets).", _COMPARACION, "mix_bebidas", LUZ_UMBRAL),
    Indicador("costo_total_pct", "Costo total %", ("portada",),
              "Costo total del periodo (reporte de costos de Wansoft u Odoo: costo total menos consumo) "
              "sobre la venta neta de las sucursales que lo tienen. Semana = el corte del lunes siguiente; "
              "mes = el último corte del mes. Mientras Odoo no termina de facturar, es estimado.",
              "Wansoft / Odoo (reporte de costos).", _COSTO_COMPARACION, "costo_total_pct", LUZ_BANDA,
              es_costo=True),
    Indicador("costo_ventas_pct", "Costo facturado %", ("portada",),
              "Facturas de Costo de Ventas registradas en Presupuestos AP sobre la venta neta de las "
              "sucursales que las tienen. Preliminar hasta 10 días después del cierre del mes (se siguen "
              "capturando facturas). En el consolidado solo aparece si todas las sucursales lo tienen.",
              "Presupuestos AP (facturas de Odoo).", _COSTO_COMPARACION, "costo_ventas_pct", LUZ_BANDA,
              es_costo=True),
    Indicador("canal_plataformas", "Venta por plataformas (delivery)", ("comercial",),
              "Venta de las órdenes de plataformas (Uber Eats, Rappi, Didi y cuentas de apps) sobre la venta "
              "bruta, del detalle de tickets. Sin semáforo: no hay meta definida.",
              "Wansoft (detalle de tickets).", _COMPARACION, "canal_plataformas"),
    Indicador("ebitda", "EBITDA", ("portada",),
              "Utilidad antes de intereses, impuestos, depreciación y amortización.",
              "Contabilidad de Odoo (por construir).", "",
              estado=SIN_FUENTE,
              pendiente="Pendiente de fuente: hay que construirlo desde la contabilidad de Odoo."),
]
POR_CLAVE = {i.clave: i for i in CATALOGO}


@dataclass(frozen=True)
class Tarjeta:
    indicador: Indicador
    valor: Decimal | None = None
    anio_anterior: Decimal | None = None
    var_anio: Variacion | None = None
    anterior: Decimal | None = None
    var_anterior: Variacion | None = None
    excluidas_anio: tuple[str, ...] = ()
    formato: str = ""  # Central's display format of the row (MONEDA, PORCENTAJE...)
    # The period's value over the branches compared with last year only (equal
    # to `valor` when none is left out): the side the change is computed on.
    valor_comparable_anio: Decimal | None = None
    # Central's light of the row (verde / naranja / rojo, None = no light);
    # historic-target rows also carry the share of the target, the target and
    # its base (META_ANIO = last year, META_ANTERIOR = previous period).
    semaforo: str | None = None
    logro: Decimal | None = None
    meta: Decimal | None = None
    meta_contra: str | None = None
    estimado: bool = False  # total cost estimated (Odoo invoicing still behind)
    preliminar: bool = False  # invoiced cost still being captured
    aviso: str = ""  # why a ready card shows no value (e.g. cost not considered)

    @property
    def mostrar(self) -> bool:
        return self.indicador.estado == LISTO and not self.aviso

    def _v(self, x):
        return formato.valor(x, self.formato)

    @property
    def valor_texto(self) -> str:
        return self._v(self.valor)

    @property
    def comparable_texto(self) -> str:
        return self._v(self.valor_comparable_anio)

    @property
    def anio_texto(self) -> str:
        return self._v(self.anio_anterior)

    @property
    def var_anio_texto(self) -> str:
        return formato.variacion(self.var_anio, self.formato)

    @property
    def anterior_texto(self) -> str:
        return self._v(self.anterior)

    @property
    def var_anterior_texto(self) -> str:
        return formato.variacion(self.var_anterior, self.formato)

    @property
    def meta_texto(self) -> str:
        return self._v(self.meta)

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
    def meta_corta(self) -> str:
        return meta_corta(self.indicador.luz)


def tarjetas(sel: Seleccion, pestana: str) -> list[Tarjeta]:
    """The cards of a tab for a selection, from Central's commercial table."""
    filas = {f.indicador.clave: f for f in tabla_comercial.construir_tabla(
        sel.actual, sel.contra_anterior, sel.contra_anio)}
    # Same table over the comparable branches only (its "actual" column).
    comparables = {f.indicador.clave: f.actual for f in tabla_comercial.construir_tabla(
        sel.contra_anio.actual, None, None)}
    salida = []
    for ind in CATALOGO:
        if pestana not in ind.pestanas:
            continue
        if ind.estado != LISTO:
            salida.append(Tarjeta(ind))
            continue
        if ind.es_costo and not sel.con_costo:
            salida.append(Tarjeta(ind, aviso="No se considera el costo de esta sucursal (así está configurada)."))
            continue
        if ind.fila_comercial == "costo_ventas_pct" and sel.facturado_incompleto:
            salida.append(Tarjeta(ind, aviso="No se muestra en el consolidado: no todas las sucursales tienen "
                                             "costo facturado en el periodo."))
            continue
        f = filas[ind.fila_comercial]
        meta = None
        if ind.luz == LUZ_HISTORICA and f.semaforo is not None:
            base = f.anio_anterior if f.meta_contra == tabla_comercial.META_ANIO else f.anterior
            meta = scorecard.meta_historica(base, None)  # the same target Central's light used
        con_luz = bool(ind.luz) and f.semaforo is not None
        salida.append(Tarjeta(
            ind, f.actual, f.anio_anterior, f.var_anio, f.anterior, f.var_anterior,
            tuple(sel.contra_anio.excluidas), f.indicador.formato, comparables[ind.fila_comercial],
            f.semaforo if con_luz else None,
            f.logro if con_luz and ind.luz == LUZ_HISTORICA else None, meta,
            f.meta_contra if con_luz and ind.luz == LUZ_HISTORICA else None,
            estimado=f.estimado,
            preliminar=ind.fila_comercial == "costo_ventas_pct" and sel.actual.costo_preliminar,
        ))
    return salida
