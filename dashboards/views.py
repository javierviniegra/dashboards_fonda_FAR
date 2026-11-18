import logging

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from central.motor.periodo import TipoPeriodo

from . import indicadores, lectura
from .models import Sucursal

log = logging.getLogger(__name__)

# The v1 tabs (owner, 2026-11-17), in display order: (slug, label, block of
# the owner's indicator list). Each tab gets its indicators block by block.
PESTANAS = [
    ("portada", "Dirección General", "Vista general de la red y por sucursal"),
    ("ranking", "Ranking", "Bloque 2 · Ranking & Scorecard de sucursales"),
    ("comercial", "Comercial", "Bloque 3 · Tracción comercial"),
    ("operaciones", "Operaciones", "Bloque 4 · Salón, cocina y gastos operativos"),
]
_POR_SLUG = {p[0]: p for p in PESTANAS}
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
    if any(i.pestana == slug for i in indicadores.CATALOGO):
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
        try:
            lec = lectura.leer(periodo, refrescar=request.GET.get("refrescar") == "1")
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
                "sin_costo": sel.sin_costo,
                "facturado_incompleto": sel.facturado_incompleto,
            })
        except Exception:  # sources unreachable: say so, never a 500 in the meeting
            log.exception("No se pudieron leer las fuentes")
            ctx["error_fuentes"] = True
    return render(request, "dashboards/tablero.html", ctx)


@login_required
def ayuda(request):
    return render(request, "dashboards/ayuda.html", {"pestanas": PESTANAS, "catalogo": indicadores.CATALOGO})
