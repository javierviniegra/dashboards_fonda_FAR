import logging

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from central.motor.periodo import TipoPeriodo

from . import graficas, indicadores, lectura
from .models import Sucursal

log = logging.getLogger(__name__)

# The v1 tabs (owner, 2026-11-17), in display order: (slug, label, block of
# the owner's indicator list). Each tab gets its indicators block by block.
PESTANAS = [
    ("portada", "Dirección General", "Vista general de la red y por sucursal"),
    ("ranking", "Ranking", "Bloque 2 · Ranking & Scorecard de sucursales"),
    ("comercial", "Comercial", "Bloque 3 · Tracción comercial"),
    ("operaciones", "Operaciones", "Bloque 4 · Salón, cocina y gastos operativos"),
    ("cedis", "CEDIS", "Bloque 5 · El Bodegón de Fito: abasto, pedidos e insumos"),
]
_POR_SLUG = {p[0]: p for p in PESTANAS}
# Tabs that draw Central's charts under their cards (owner, 2026-11-18: charts
# in Comercial; compact cards with the details in a hover tooltip).
PESTANAS_CON_GRAFICAS = {"portada", "comercial", "operaciones"}
TIPOS_ETIQUETA = {TipoPeriodo.SEMANA: "Semana", TipoPeriodo.MES: "Mes"}


def home(request):
    return redirect("tablero", pestana="portada")


def _filtros(request):
    """(branch key or None, period) from the query string; defaults: the
    consolidated and the last closed week. Unknown values fall back to them."""
    sucursal = request.GET.get("sucursal") or None
    if sucursal and not Sucursal.objects.filter(clave=sucursal, activa=True).exists():
        sucursal = None
    tipo = request.GET.get("tipo") or TipoPeriodo.SEMANA.value
    try:
        periodo = lectura.periodo_de(tipo, request.GET.get("desde", ""))
    except ValueError:
        t = TipoPeriodo(tipo) if tipo in [x.value for x in lectura.TIPOS] else TipoPeriodo.SEMANA
        periodo = lectura.periodos_cerrados(t)[0]
    return sucursal, periodo


@login_required
def tablero(request, pestana):
    if pestana not in _POR_SLUG:
        raise Http404
    slug, titulo, subtitulo = _POR_SLUG[pestana]
    ctx = {"pestanas": PESTANAS, "activa": slug, "titulo": titulo, "subtitulo": subtitulo}
    if any(slug in i.pestanas for i in indicadores.CATALOGO):
        sucursal, periodo = _filtros(request)
        ctx.update({
            "con_filtros": True,
            "sucursales": Sucursal.objects.filter(activa=True).order_by("nombre"),
            "sucursal_sel": sucursal or "",
            "tipos": [(t.value, TIPOS_ETIQUETA[t]) for t in lectura.TIPOS],
            "tipo_sel": periodo.tipo.value,
            "periodos": [(p.desde.isoformat(), p.etiqueta()) for p in lectura.periodos_cerrados(periodo.tipo)],
            "desde_sel": periodo.desde.isoformat(),
            "periodo": periodo,
        })
        refrescar = request.GET.get("refrescar") == "1"
        try:
            if slug == "cedis":  # Central's CEDIS reading (Odoo) + input inflation: a reading of its own
                lec = lectura.leer_cedis(periodo, refrescar=refrescar)
                sel = lectura.seleccionar_cedis(lec, sucursal, refrescar=refrescar)
                ctx.update({
                    "seleccion": sel,
                    "tarjetas": indicadores.tarjetas_cedis(sel),
                    "leido_en": timezone.localtime(lec.leido_en),
                    "origen": lec.origen,
                    "graficas": graficas.de_cedis(sel, sucursal is None),
                })
                return render(request, "dashboards/tablero.html", ctx)
            if slug == "operaciones":  # Central's waiters' report + butchery: a reading of its own
                lec = lectura.leer_operaciones(periodo, refrescar=refrescar)
                sel = lectura.seleccionar_operaciones(lec, sucursal)
                ctx.update({
                    "seleccion": sel,
                    "tarjetas": indicadores.tarjetas_operaciones(sel),
                    "leido_en": timezone.localtime(lec.leido_en),
                    "origen": lec.origen,
                    "anio_anterior": lec.anio_anterior,
                    "anterior": lec.anterior,
                    "excluidas_anio": sel.contra_anio.excluidas,
                    "anio_sin_base": bool(sel.contra_anio.excluidas) and sel.contra_anio.base is None,
                    "graficas": graficas.de_operaciones(lec, sel, sucursal),
                })
                return render(request, "dashboards/tablero.html", ctx)
            lec = lectura.leer(periodo, refrescar=refrescar)
            sel = lectura.seleccionar(lec, sucursal)
            ctx.update({
                "seleccion": sel,
                "tarjetas": indicadores.tarjetas(sel, slug),
                "leido_en": timezone.localtime(lec.leido_en),
                "origen": lec.origen,
                "anio_anterior": lec.anio_anterior,
                "anterior": lec.anterior,
                "excluidas_anio": sel.contra_anio.excluidas,
                "anio_sin_base": bool(sel.contra_anio.excluidas) and sel.contra_anio.base is None,
                # The cost note only where the tab shows costs.
                "sin_costo": sel.sin_costo if any(i.es_costo and slug in i.pestanas
                                                  for i in indicadores.CATALOGO) else (),
                "facturado_incompleto": sel.facturado_incompleto,
            })
            if slug == "portada":
                ctx["graficas"] = graficas.de_portada(lec, sucursal)
            elif slug in PESTANAS_CON_GRAFICAS:
                ctx["graficas"] = (graficas.de_venta(lec, sel) + graficas.de_mezcla(sel)
                                   + graficas.de_composicion(sel))
        except Exception:  # sources unreachable: say so, never a 500 in the meeting
            log.exception("No se pudieron leer las fuentes")
            ctx["error_fuentes"] = True
    return render(request, "dashboards/tablero.html", ctx)


@login_required
def ayuda(request):
    return render(request, "dashboards/ayuda.html", {"pestanas": PESTANAS, "catalogo": indicadores.CATALOGO})
