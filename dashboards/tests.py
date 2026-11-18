from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from . import motor_central
from .views import PESTANAS


class MotorCentralTests(TestCase):
    """Central's engine is importable from the pinned submodule, without
    shadowing this project's own packages."""

    def test_motor_importable(self):
        self.assertTrue(motor_central.disponible())

    def test_motor_from_submodule(self):
        import central.motor.periodos as periodos
        self.assertTrue(Path(periodos.__file__).resolve().is_relative_to(settings.CENTRAL_DIR.resolve()))

    def test_our_config_wins(self):
        import config
        self.assertEqual(Path(config.__file__).resolve().parent, settings.BASE_DIR / "config")

    def test_connections_module_reads_our_settings(self):
        from central.motor.fuentes import conexiones  # needs settings.FUENTES_ENV
        self.assertEqual(conexiones.origen(), settings.FUENTES_ENV)

    def test_version_known(self):
        self.assertRegex(motor_central.version(), r"^[0-9a-f]{7,}$")

    def test_engine_files_match_pinned_commit(self):
        # 2026-11-18: the submodule's files were once found reformatted on disk
        # (unknown cause). The numbers must come from the pinned code exactly.
        self.assertEqual(motor_central.cambios_locales(), [])


# Tests run with DEBUG=False; the manifest storage would need collectstatic first.
@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class VistasTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("director", password="x-prueba-123")

    def test_login_required(self):
        r = self.client.get(reverse("tablero", args=["portada"]))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r["Location"])

    def test_home_redirects_to_portada(self):
        r = self.client.get(reverse("home"))
        self.assertRedirects(r, reverse("tablero", args=["portada"]), fetch_redirect_response=False)

    def test_every_tab_renders(self):
        self.client.force_login(self.user)
        for slug, etiqueta, _ in PESTANAS:
            r = self.client.get(reverse("tablero", args=[slug]))
            self.assertContains(r, etiqueta)
            self.assertContains(r, motor_central.version())

    def test_unknown_tab_404(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("tablero", args=["no-existe"])).status_code, 404)

    def test_help(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("ayuda")), "¿De dónde salen los números?")

    def test_login_page(self):
        self.assertContains(self.client.get(reverse("login")), "Dashboards Fonda")


# ---------------------------------------------------------------------------
# Block 1: branches, periods, reading layer, cards (no source is touched).
# ---------------------------------------------------------------------------
from datetime import date, datetime, timezone as dt_tz
from decimal import Decimal
from unittest import mock

from django.core.management import call_command

from central.motor.metricas import Metricas
from central.motor.periodo import Periodo, TipoPeriodo

from . import indicadores, lectura
from .management.commands.cargar_sucursales import leer_lista_central
from .models import Sucursal


class SucursalesTests(TestCase):
    def test_list_read_from_central(self):
        lista, formatos = leer_lista_central()
        claves = [x[0] for x in lista]
        self.assertIn("acoxpa", claves)
        self.assertEqual(formatos["la-esquina-coyoacan"], "esquina")

    def test_load_is_idempotent_and_keeps_edits(self):
        call_command("cargar_sucursales", stdout=mock.MagicMock())
        n = Sucursal.objects.count()
        self.assertEqual(n, len(leer_lista_central()[0]))
        self.assertFalse(Sucursal.objects.get(clave="metepec").considerar_costo)
        Sucursal.objects.filter(clave="acoxpa").update(nombre="Acoxpa (editada)")
        call_command("cargar_sucursales", stdout=mock.MagicMock())
        self.assertEqual(Sucursal.objects.count(), n)
        self.assertEqual(Sucursal.objects.get(clave="acoxpa").nombre, "Acoxpa (editada)")


class PeriodosTests(TestCase):
    def test_last_closed_week(self):
        p = lectura.periodos_cerrados(TipoPeriodo.SEMANA, date(2026, 11, 18))[0]
        self.assertEqual((p.desde, p.hasta), (date(2026, 11, 9), date(2026, 11, 15)))

    def test_sunday_week_is_still_open(self):
        p = lectura.periodos_cerrados(TipoPeriodo.SEMANA, date(2026, 11, 15))[0]
        self.assertEqual(p.desde, date(2026, 11, 2))

    def test_last_closed_month_and_count(self):
        ps = lectura.periodos_cerrados(TipoPeriodo.MES, date(2026, 11, 18))
        self.assertEqual(len(ps), 12)
        self.assertEqual(ps[0].desde, date(2026, 10, 1))

    def test_only_offered_periods_are_accepted(self):
        hoy = date(2026, 11, 18)
        self.assertEqual(lectura.periodo_de("mes", "2026-10-01", hoy).hasta, date(2026, 10, 31))
        for tipo, desde in (("mes", "2026-11-01"), ("anio", "2026-01-01"), ("semana", "2026-11-10")):
            with self.assertRaises(ValueError):
                lectura.periodo_de(tipo, desde, hoy)


def _m(periodo, venta, dias):
    """A branch's metrics: `venta` of gross sales, closings on `dias` days."""
    return Metricas(periodo=periodo, venta_bruta=Decimal(venta), venta_neta=Decimal(venta),
                    dias_con_cierre=dias, dias_con_detalle=dias)


class SeleccionTests(TestCase):
    def setUp(self):
        self.p = Periodo.semana_de(date(2026, 11, 11))
        self.ant, self.anio = self.p.anterior(), self.p.mismo_periodo_anio_anterior()
        self.a = Sucursal(pk=1, clave="a", nombre="A")
        self.b = Sucursal(pk=2, clave="b", nombre="B (nueva)")
        self.lec = lectura.Lectura(
            [self.a, self.b], self.p, self.ant, self.anio,
            actual=[_m(self.p, 1000, 7), _m(self.p, 500, 7)],
            previo=[_m(self.ant, 900, 7), _m(self.ant, 400, 7)],
            anio=[_m(self.anio, 800, 7), _m(self.anio, 0, 0)],  # B did not exist last year
            leido_en=datetime(2026, 11, 18, tzinfo=dt_tz.utc), origen="prod")

    def test_consolidated_compares_comparable_branches_only(self):
        sel = lectura.seleccionar(self.lec, None)
        (t,) = indicadores.tarjetas(sel, "portada")
        self.assertEqual(t.valor, Decimal(1500))            # every branch
        self.assertEqual(t.valor_comparable_anio, Decimal(1000))  # A only
        self.assertEqual(t.anio_anterior, Decimal(800))
        self.assertEqual(t.var_anio.porcentaje, Decimal("0.25"))
        self.assertEqual(t.excluidas_anio, ["B (nueva)"])
        self.assertEqual(t.valor_texto, "$1,500.00")
        self.assertEqual(t.var_anio_texto, "▲ +25.0%")

    def test_single_branch(self):
        (t,) = indicadores.tarjetas(lectura.seleccionar(self.lec, "a"), "portada")
        self.assertEqual((t.valor, t.anterior, t.excluidas_anio), (Decimal(1000), Decimal(900), []))

    def test_unknown_branch(self):
        with self.assertRaises(KeyError):
            lectura.seleccionar(self.lec, "zzz")

    def test_cache_key_changes_with_engine_version(self):
        with mock.patch.object(lectura.motor_central, "version", return_value="aaaaaaa"):
            k1 = lectura._clave(self.p, [self.a], False)
        with mock.patch.object(lectura.motor_central, "version", return_value="bbbbbbb"):
            k2 = lectura._clave(self.p, [self.a], False)
        self.assertNotEqual(k1, k2)


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class PortadaTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("director", password="x-prueba-123"))
        Sucursal.objects.create(clave="a", nombre="A", wansoft_subsidiary_id=1)

    def _lectura(self, periodo, costos=False, refrescar=False):
        a = Sucursal.objects.get(clave="a")
        ant, anio = periodo.anterior(), periodo.mismo_periodo_anio_anterior()
        return lectura.Lectura([a], periodo, ant, anio, [_m(periodo, 1234, periodo.dias)],
                               [_m(ant, 1000, ant.dias)], [_m(anio, 1100, anio.dias)],
                               datetime(2026, 11, 18, 15, 0, tzinfo=dt_tz.utc), "prod")

    def test_portada_shows_card(self):
        with mock.patch.object(lectura, "leer", side_effect=self._lectura):
            r = self.client.get(reverse("tablero", args=["portada"]))
        self.assertContains(r, "Venta bruta (con IVA)")
        self.assertContains(r, "$1,234.00")
        self.assertContains(r, "▲ +12.2%")
        self.assertContains(r, "Leído a las")

    def test_refresh_flag_reaches_reader(self):
        with mock.patch.object(lectura, "leer", side_effect=self._lectura) as leer:
            self.client.get(reverse("tablero", args=["portada"]), {"refrescar": "1"})
        self.assertTrue(leer.call_args.kwargs["refrescar"])

    def test_sources_down_shows_notice(self):
        with mock.patch.object(lectura, "leer", side_effect=OSError("down")):
            r = self.client.get(reverse("tablero", args=["portada"]))
        self.assertContains(r, "No se pudieron leer las fuentes")

    def test_other_tabs_still_under_construction(self):
        self.assertContains(self.client.get(reverse("tablero", args=["comercial"])), "En construcción")

    def test_help_lists_indicators(self):
        self.assertContains(self.client.get(reverse("ayuda")), indicadores.CATALOGO[0].definicion[:40])
