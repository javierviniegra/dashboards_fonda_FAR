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

from dataclasses import dataclass, replace
from decimal import Decimal

from central.motor import formato, reporte_meseros, scorecard, semaforos, tabla_comercial
from central.motor.comparativos import Variacion, kpi_costo, variacion

from .lectura import Seleccion, SeleccionOperaciones

LISTO, PENDIENTE, SIN_FUENTE = "listo", "pendiente", "sin_fuente"
# Kinds of light, each with its rule written from Central's constants.
LUZ_HISTORICA, LUZ_UMBRAL, LUZ_BANDA = "historica", "umbral", "banda"
# Thresholds of the owner's draft (Portal Directivo, "Reglas oficiales de
# semaforos"), adopted for the dashboards by the owner on 2026-11-18. Central
# has no rule for these two: they live here, painted with Central's
# `semaforos.umbral` (higher is better; the draft's yellow = Central's orange).
LUZ_BORRADOR = "borrador"
UMBRALES_BORRADOR = {
    "venta_mesero_dia": (Decimal("14500"), Decimal("11500")),   # >= $14,500 green; >= $11,500 orange
    "propina": (Decimal("0.09"), Decimal("0.08")),              # >= 9% green; >= 8% orange
}
# Where a card's row comes from.
FILA_COMERCIAL, FILA_MESEROS, FILA_TABLAJERIA = "comercial", "meseros", "tablajeria"


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


def _umbral_texto(fila: str, v: Decimal) -> str:
    return f"${v:,.0f}" if fila == "venta_mesero_dia" else _pct(v)


def regla_borrador(fila: str) -> str:
    verde, naranja = UMBRALES_BORRADOR[fila]
    return (f"Semáforo (reglas del portal directivo, adoptadas el 18-nov-2026): verde desde "
            f"{_umbral_texto(fila, verde)}, naranja desde {_umbral_texto(fila, naranja)}, rojo abajo.")


def meta_corta(luz: str, fila: str = "") -> str:
    """One line under a card's value for fixed-threshold and band lights."""
    if luz == LUZ_BORRADOR:
        return f"meta: {_umbral_texto(fila, UMBRALES_BORRADOR[fila][0])} o más"
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
    origen_fila: str = FILA_COMERCIAL  # which of Central's tables the row comes from

    @property
    def regla_semaforo(self) -> str:
        if self.luz == LUZ_BORRADOR:
            return regla_borrador(self.fila_comercial)
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
    # --- Operaciones (block 4, owner 2026-11-18): Central's waiters' report and butchery ---
    Indicador("venta_mesero_dia", "Venta por mesero por día", ("operaciones",),
              "Venta de salón (con IVA) de los meseros activos / días que trabajó cada uno (días con al menos "
              "una cuenta). Como el reporte de meseros de Central.",
              "Wansoft (detalle de tickets, órdenes de restaurante).", _COMPARACION, "venta_mesero_dia",
              LUZ_BORRADOR, origen_fila=FILA_MESEROS),
    Indicador("venta_mesero", "Venta por mesero", ("operaciones",),
              "Venta de salón (con IVA) / meseros activos (con al menos una cuenta en el periodo).",
              "Wansoft (detalle de tickets).", _COMPARACION, "venta_mesero", origen_fila=FILA_MESEROS),
    Indicador("plantilla", "Meseros activos", ("operaciones",),
              "Meseros con al menos una cuenta de salón en el periodo.",
              "Wansoft (detalle de tickets).", _COMPARACION, "plantilla", origen_fila=FILA_MESEROS),
    Indicador("cuentas", "Mesas atendidas", ("operaciones",),
              "Cuentas de salón del periodo (cada cuenta = una mesa atendida).",
              "Wansoft (detalle de tickets).", _COMPARACION, "cuentas", origen_fila=FILA_MESEROS),
    Indicador("propina", "Propina %", ("operaciones",),
              "Propina registrada en los pagos con tarjeta de las cuentas de salón / lo pagado con tarjeta "
              "(definición de Central desde el 17-nov-2026; el efectivo no registra propina).",
              "Wansoft (pagos de las cuentas de salón).", _COMPARACION, "propina", LUZ_BORRADOR,
              origen_fila=FILA_MESEROS),
    Indicador("tiempo_mesa", "Tiempo de mesa (min)", ("operaciones",),
              "Minutos promedio de la apertura al cierre de la cuenta de salón (sin las cuentas que quedaron "
              "abiertas por error: fuera del rango de minutos que usa Central).",
              "Wansoft (detalle de tickets).", _COMPARACION, "tiempo_mesa", origen_fila=FILA_MESEROS),
    Indicador("pct_control", "Cortesías + descuentos %", ("operaciones",),
              "Cortesías (a precio de venta) más descuentos de salón / venta de salón.",
              "Wansoft (detalle de tickets).", _COMPARACION, "pct_control", origen_fila=FILA_MESEROS),
    Indicador("cortesias", "Cortesías", ("operaciones",),
              "Cortesías de salón a precio de venta.", "Wansoft (detalle de tickets).", _COMPARACION,
              "cortesias", origen_fila=FILA_MESEROS),
    Indicador("descuentos", "Descuentos", ("operaciones",),
              "Descuentos de salón (sin las cortesías).", "Wansoft (detalle de tickets).", _COMPARACION,
              "descuentos", origen_fila=FILA_MESEROS),
    Indicador("cancelaciones", "Cancelaciones", ("operaciones",),
              "Cancelaciones de la sucursal a precio de venta (del corte de caja: Wansoft las quita de los "
              "tickets).", "Wansoft (cortes de caja).", _COMPARACION, "cancelaciones", origen_fila=FILA_MESEROS),
    Indicador("merma_tablajeria", "Merma tablajería %", ("operaciones",),
              "Kg de merma / kg de pieza base en la tablajería (cada pieza contada una vez; los productos "
              "porcionados quedan fuera), contra el mismo periodo del año anterior.",
              "Wansoft (tablajería), sección de merma del reporte comercial de Central.",
              "Contra el mismo periodo del año anterior, en puntos porcentuales (subir es peor).",
              "merma_pct", origen_fila=FILA_TABLAJERIA),
    Indicador("costo_merma", "Costo de la merma", ("operaciones",),
              "Kg de merma x costo por kg de cada pieza.",
              "Wansoft (tablajería).", "Contra el mismo periodo del año anterior.", "merma_costo",
              origen_fila=FILA_TABLAJERIA, es_costo=True),
    Indicador("costo_teorico", "Costo real vs teórico", ("operaciones",),
              "Desviación del costo real de alimentos y bebidas contra el costo teórico de las recetas.",
              "Por definir.", "", estado=PENDIENTE,
              pendiente="El motor de Central todavía no calcula el costo teórico; hay que definir su fuente."),
    Indicador("platillos_86", "Platillos en «86» y devoluciones", ("operaciones",),
              "Platillos agotados y devoluciones de clientes en el periodo.",
              "Sin fuente sistematizada.", "", estado=SIN_FUENTE,
              pendiente="Sin fuente sistematizada: hoy no se registra en ningún sistema que el tablero pueda leer."),
    Indicador("gastos_operativos", "Gas, carbón, limpieza y mantenimiento", ("operaciones",),
              "Gasto en gas, carbón, limpieza y mantenimiento, en pesos y como % de la venta.",
              "Facturas unificadas Wansoft/Odoo (lectura de gastos del scorecard de Central).", "",
              estado=PENDIENTE,
              pendiente="Está en el trabajo del scorecard de Central, que todavía no se sube a GitHub; se "
                        "muestra al mover el submódulo."),
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
    extra: tuple[str, ...] = ()  # more tooltip lines (e.g. the butchery vs every branch)

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
        return meta_corta(self.indicador.luz, self.indicador.fila_comercial)


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
        t = _desde_fila(ind, f, comparables[ind.fila_comercial], sel.contra_anio.excluidas)
        if ind.fila_comercial == "costo_ventas_pct" and sel.actual.costo_preliminar:
            t = replace(t, preliminar=True)
        salida.append(t)
    return salida


def _desde_fila(ind: Indicador, f, comparable=None, excluidas=()) -> Tarjeta:
    """A card from a row of Central's tables (commercial or waiters')."""
    semaforo = logro = meta = contra = None
    if ind.luz == LUZ_BORRADOR:
        verde, naranja = UMBRALES_BORRADOR[ind.fila_comercial]
        semaforo = semaforos.umbral(f.actual, verde, naranja, mayor_mejor=True)
    elif ind.luz and f.semaforo is not None:
        semaforo = f.semaforo
        if ind.luz == LUZ_HISTORICA:
            logro, contra = f.logro, f.meta_contra
            base = f.anio_anterior if f.meta_contra == tabla_comercial.META_ANIO else f.anterior
            meta = scorecard.meta_historica(base, None)  # the same target Central's light used
    return Tarjeta(ind, f.actual, f.anio_anterior, f.var_anio, f.anterior, f.var_anterior, tuple(excluidas),
                   f.indicador.formato, comparable, semaforo, logro, meta, contra,
                   estimado=getattr(f, "estimado", False))


def tarjetas_operaciones(sel: SeleccionOperaciones) -> list[Tarjeta]:
    """The cards of the Operaciones tab: Central's waiters' report table and
    the butchery section of its commercial report."""
    filas = {f.indicador.clave: f for f in reporte_meseros.construir_tabla(
        sel.actual, sel.contra_anterior, sel.contra_anio)}
    comparables = {f.indicador.clave: f.actual for f in reporte_meseros.construir_tabla(
        sel.contra_anio.actual, sel.contra_anterior, sel.contra_anio)}
    carne = sel.tablajeria
    salida = []
    for ind in CATALOGO:
        if "operaciones" not in ind.pestanas:
            continue
        if ind.estado != LISTO:
            salida.append(Tarjeta(ind))
        elif ind.origen_fila == FILA_MESEROS:
            salida.append(_desde_fila(ind, filas[ind.fila_comercial], comparables[ind.fila_comercial],
                                      sel.contra_anio.excluidas))
        elif ind.es_costo and not sel.con_costo:
            salida.append(Tarjeta(ind, aviso="No se considera el costo de esta sucursal (así está configurada)."))
        elif carne is None or carne.total is None:
            salida.append(Tarjeta(ind, aviso="Sin datos de tablajería en Wansoft para esta selección "
                                             "(o no se pudieron leer)."))
        else:
            t = carne.total
            if ind.fila_comercial == "merma_pct":
                extra = []
                if t.indice_grupo is not None and t.dif_grupo is not None:
                    extra.append(f"Todas las sucursales: {formato.valor(t.indice_grupo, tabla_comercial.PORCENTAJE)} "
                                 f"({'+' if t.dif_grupo >= 0 else ''}{t.dif_grupo * 100:.1f} pp).")
                if carne.sin_datos:
                    extra.append("Sin tablajería: " + ", ".join(carne.sin_datos) + ".")
                salida.append(Tarjeta(ind, t.indice, t.indice_anio, t.var_anio, None, variacion(None, None),
                                      formato=tabla_comercial.PORCENTAJE, extra=tuple(extra)))
            else:
                anio = t.anio.costo_merma if t.anio is not None else None
                salida.append(Tarjeta(ind, t.actual.costo_merma, anio,
                                      variacion(t.actual.costo_merma, anio, mejor_si_sube=False),
                                      None, variacion(None, None), formato=tabla_comercial.MONEDA))
    return salida
