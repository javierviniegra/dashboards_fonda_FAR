"""Load the branches from Central de Reportes' own list (single source).

The list lives in Central's `cuentas/management/commands/cargar_sucursales.py`
(pinned submodule). That module cannot be imported here (it imports Central's
`cuentas` app, which is not installed), so its two constants are read with
`ast`: `SUCURSALES` (key, name, Wansoft subsidiary id, ticket name, Odoo
company id) and `FORMATOS` (key -> Sucursal.Formato.<NAME>).

Idempotent and non-destructive, as Central's: a missing branch is created; an
existing one only gets its EMPTY mapping fields filled (admin edits win).
"""

import ast

from django.conf import settings
from django.core.management.base import BaseCommand

from dashboards.models import Sucursal

ORIGEN = settings.CENTRAL_DIR / "cuentas" / "management" / "commands" / "cargar_sucursales.py"

# Branches whose cost is not considered. Central sets this by its migration
# 0004, not in its list (owner, 2026-10-05: Metepec never finishes discounting
# its cost in Wansoft). Only applied when the branch is created.
SIN_COSTO = {"metepec"}


def leer_lista_central(ruta=ORIGEN) -> tuple[list[tuple], dict[str, str]]:
    """(SUCURSALES, {key: formato value}) as written in Central's command."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    sucursales, formatos = None, {}
    for nodo in arbol.body:
        if not isinstance(nodo, ast.Assign) or len(nodo.targets) != 1:
            continue
        nombre = getattr(nodo.targets[0], "id", None)
        if nombre == "SUCURSALES":
            sucursales = [tuple(x) for x in ast.literal_eval(nodo.value)]
        elif nombre == "FORMATOS":
            for k, v in zip(nodo.value.keys, nodo.value.values):
                # Sucursal.Formato.TAQUERIA -> "taqueria"
                formatos[ast.literal_eval(k)] = Sucursal.Formato[v.attr].value
    if sucursales is None:
        raise ValueError(f"SUCURSALES not found in {ruta}")
    return sucursales, formatos


class Command(BaseCommand):
    help = "Carga las sucursales desde la lista de Central de Reportes (idempotente, no sobrescribe)."

    def handle(self, *args, **options):
        sucursales, formatos = leer_lista_central()
        for clave, nombre, subs_id, ticket, odoo_id in sucursales:
            suc, creada = Sucursal.objects.get_or_create(
                clave=clave,
                defaults=dict(
                    nombre=nombre,
                    wansoft_subsidiary_id=subs_id,
                    wansoft_ticket_nombre=ticket,
                    odoo_company_id=odoo_id,
                    formato=formatos.get(clave, Sucursal.Formato.FONDA),
                    considerar_costo=clave not in SIN_COSTO,
                ),
            )
            if creada:
                self.stdout.write(f"Creada: {nombre}")
                continue
            llenados = []
            for campo, valor in (("wansoft_subsidiary_id", subs_id), ("wansoft_ticket_nombre", ticket),
                                 ("odoo_company_id", odoo_id)):
                if valor not in (None, "") and getattr(suc, campo) in (None, ""):
                    setattr(suc, campo, valor)
                    llenados.append(campo)
            if llenados:
                suc.save()
            self.stdout.write(f"Ya existía: {nombre}" + (f" (completado: {', '.join(llenados)})" if llenados else ""))
