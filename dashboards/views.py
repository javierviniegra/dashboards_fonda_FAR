from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render

# The v1 tabs (owner, 2026-11-17), in display order: (slug, label, block of
# the owner's indicator list). Each tab gets its indicators block by block.
PESTANAS = [
    ("portada", "Dirección General", "Vista general de la red y por sucursal"),
    ("ranking", "Ranking", "Bloque 2 · Ranking & Scorecard de sucursales"),
    ("comercial", "Comercial", "Bloque 3 · Tracción comercial"),
    ("operaciones", "Operaciones", "Bloque 4 · Salón, cocina y gastos operativos"),
]
_POR_SLUG = {p[0]: p for p in PESTANAS}


def home(request):
    return redirect("tablero", pestana="portada")


@login_required
def tablero(request, pestana):
    if pestana not in _POR_SLUG:
        raise Http404
    slug, titulo, subtitulo = _POR_SLUG[pestana]
    return render(request, "dashboards/tablero.html", {
        "pestanas": PESTANAS, "activa": slug, "titulo": titulo, "subtitulo": subtitulo,
    })


@login_required
def ayuda(request):
    return render(request, "dashboards/ayuda.html", {"pestanas": PESTANAS})
