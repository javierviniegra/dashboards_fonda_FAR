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


def _venta(sel, clave="venta_bruta"):
    """One card of the Dirección General tab."""
    return {t.indicador.clave: t for t in indicadores.tarjetas(sel, "portada")}[clave]


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
        t = _venta(sel)
        self.assertEqual(t.valor, Decimal(1500))            # every branch
        self.assertEqual(t.valor_comparable_anio, Decimal(1000))  # A only
        self.assertEqual(t.anio_anterior, Decimal(800))
        self.assertEqual(t.var_anio.porcentaje, Decimal("0.25"))
        self.assertEqual(t.excluidas_anio, ("B (nueva)",))
        self.assertEqual(t.valor_texto, "$1,500.00")
        self.assertEqual(t.var_anio_texto, "▲ +25.0%")

    def test_single_branch(self):
        t = _venta(lectura.seleccionar(self.lec, "a"))
        self.assertEqual((t.valor, t.anterior, t.excluidas_anio), (Decimal(1000), Decimal(900), ()))

    def test_light_consolidated_against_last_year_plus_5(self):
        t = _venta(lectura.seleccionar(self.lec, None))
        self.assertEqual(t.meta, Decimal(840))                      # A's 800 x 1.05
        self.assertEqual((t.semaforo, t.meta_base_texto), ("verde", "año anterior +5%"))
        self.assertEqual(t.logro_texto, "119.0%")                   # 1000 / 840

    def test_light_new_branch_against_previous_period(self):
        t = _venta(lectura.seleccionar(self.lec, "b"))
        self.assertEqual(t.meta, Decimal(420))                      # 400 x 1.05
        self.assertIn("periodo anterior", t.meta_base_texto)

    def _una(self, actual, anio, dias_anio=7, dias_ant=7):
        a = Sucursal(pk=1, clave="a", nombre="A")
        lec = lectura.Lectura([a], self.p, self.ant, self.anio, [_m(self.p, actual, 7)],
                              [_m(self.ant, 900, dias_ant)], [_m(self.anio, anio, dias_anio)],
                              datetime(2026, 11, 18, tzinfo=dt_tz.utc), "prod")
        return _venta(lectura.seleccionar(lec, "a"))

    def test_light_orange_and_red(self):
        self.assertEqual(self._una(1000, 1000).semaforo, "naranja")  # 95.2% of 1050
        self.assertEqual(self._una(850, 1000).semaforo, "rojo")      # 81.0%

    def test_unreliable_last_year_falls_back_to_previous_period(self):
        # 5 of 7 days last year: the branch leaves that comparison (Central's
        # comparable-branches rule), so the target is the previous week +5%.
        t = self._una(1000, 1000, dias_anio=5)
        self.assertEqual(t.meta, Decimal(945))
        self.assertIn("periodo anterior", t.meta_base_texto)

    def test_no_light_without_any_reliable_base(self):
        t = self._una(1000, 1000, dias_anio=5, dias_ant=5)
        self.assertIsNone(t.semaforo)
        self.assertIsNone(t.meta)

    def test_every_ready_card_has_a_central_row_and_pending_ones_say_why(self):
        from central.motor import tabla_comercial
        filas = {i.clave for i in tabla_comercial.INDICADORES}
        for ind in indicadores.CATALOGO:
            if ind.estado == indicadores.LISTO:
                self.assertIn(ind.fila_comercial, filas, ind.clave)
            else:
                self.assertTrue(ind.pendiente, ind.clave)

    def test_portada_cards_in_order(self):
        claves = [t.indicador.clave for t in indicadores.tarjetas(lectura.seleccionar(self.lec, None), "portada")]
        self.assertEqual(claves, ["venta_bruta", "venta_neta", "clientes", "afluencia_salon", "cheque_promedio",
                                  "ticket_promedio", "mix_bebidas", "costo_total_pct", "costo_ventas_pct", "ebitda"])

    def test_pending_cards_are_grey(self):
        sel = lectura.seleccionar(self.lec, None)
        for clave in ("afluencia_salon", "ebitda"):
            self.assertFalse(_venta(sel, clave).mostrar)

    def test_net_sales_has_no_light(self):
        self.assertIsNone(_venta(lectura.seleccionar(self.lec, None), "venta_neta").semaforo)

    def test_cost_band_light(self):
        m = _m(self.p, 1000, 7)
        m.costo_total, m.venta_neta_con_costo_total = Decimal(380), Decimal(1000)   # 38%: green
        lec = lectura.Lectura([self.a], self.p, self.ant, self.anio, [m], [_m(self.ant, 900, 7)],
                              [_m(self.anio, 800, 7)], datetime(2026, 11, 18, tzinfo=dt_tz.utc), "prod")
        t = _venta(lectura.seleccionar(lec, "a"), "costo_total_pct")
        self.assertEqual((t.valor, t.semaforo), (Decimal("0.38"), "verde"))
        self.assertEqual(t.meta_corta, "meta: de 37% a menos de 39%")
        m.costo_total = Decimal(360)                                               # 36%: orange
        self.assertEqual(_venta(lectura.seleccionar(lec, "a"), "costo_total_pct").semaforo, "naranja")
        m.costo_total = Decimal(395)                                               # 39.5%: red
        self.assertEqual(_venta(lectura.seleccionar(lec, "a"), "costo_total_pct").semaforo, "rojo")

    def test_cost_not_considered_branch(self):
        self.a.considerar_costo = False
        t = _venta(lectura.seleccionar(self.lec, "a"), "costo_total_pct")
        self.assertFalse(t.mostrar)
        self.assertIn("No se considera el costo", t.aviso)
        self.assertEqual(lectura.seleccionar(self.lec, None).sin_costo, ("A",))

    def test_partial_invoiced_cost_dropped_in_consolidated(self):
        self.lec.actual[0].costo_ventas_real = Decimal(300)
        self.lec.actual[0].venta_neta_con_costo = Decimal(1000)
        self.lec.actual[0].n_con_costo_ventas = 1                   # A has it, B does not
        sel = lectura.seleccionar(self.lec, None)
        self.assertTrue(sel.facturado_incompleto)
        t = _venta(sel, "costo_ventas_pct")
        self.assertFalse(t.mostrar)
        self.assertIn("no todas las sucursales", t.aviso)
        self.assertFalse(lectura.seleccionar(self.lec, "a").facturado_incompleto)

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


class PrecalentarTests(TestCase):
    def test_periods_are_last_closed_week_and_month(self):
        ps = lectura.periodos_a_precalentar(date(2026, 11, 18))
        self.assertEqual([(p.tipo, p.desde) for p in ps],
                         [(TipoPeriodo.SEMANA, date(2026, 11, 9)), (TipoPeriodo.MES, date(2026, 10, 1))])

    def test_reads_afresh_with_longer_life(self):
        with mock.patch.object(lectura, "leer") as leer:
            lectura.precalentar(date(2026, 11, 18))
        self.assertEqual(leer.call_count, 2)
        for llamada in leer.call_args_list:
            self.assertTrue(llamada.kwargs["refrescar"])
            self.assertEqual(llamada.kwargs["duracion"], lectura.DURACION_PRECALENTADO)
        self.assertGreater(lectura.DURACION_PRECALENTADO, 60 * 60)  # outlives the hourly schedule

    def test_command_fails_loudly(self):
        from django.core.management.base import CommandError
        with mock.patch.object(lectura, "precalentar", side_effect=OSError("down")):
            with self.assertRaises(CommandError):
                call_command("precalentar", stdout=mock.MagicMock())

    def test_warm_entry_is_served_from_cache(self):
        Sucursal.objects.create(clave="a", nombre="A", wansoft_subsidiary_id=1)
        p = Periodo.semana_de(date(2026, 11, 11))
        with mock.patch.object(lectura.metricas, "recolectar",
                               side_effect=lambda cw, cp, s, per, **kw: [_m(per, 100, per.dias)]) as rec, \
             mock.patch.object(lectura.conexiones, "abrir_wansoft"), \
             mock.patch.object(lectura.conexiones, "abrir_presupuestos"):
            lectura.leer(p, refrescar=True, duracion=lectura.DURACION_PRECALENTADO)
            n = rec.call_count
            lectura.leer(p)                       # a viewer: no new read
            self.assertEqual(rec.call_count, n)
