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

from . import graficas, indicadores, lectura
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
        from central.motor import reporte_meseros, tabla_comercial
        filas = {indicadores.FILA_COMERCIAL: {i.clave for i in tabla_comercial.INDICADORES},
                 indicadores.FILA_MESEROS: {i.clave for i in reporte_meseros.INDICADORES},
                 indicadores.FILA_TABLAJERIA: {"merma_pct", "merma_costo"},
                 indicadores.FILA_CEDIS: {"fill_total", "fill_bodegon", "fill_empanadas", "pedidos",
                                          "pct_modificados", "por_cedis", "diferencia", "inflacion"}}
        for ind in indicadores.CATALOGO:
            if ind.estado == indicadores.LISTO:
                self.assertIn(ind.fila_comercial, filas[ind.origen_fila], ind.clave)
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
        self.assertContains(self.client.get(reverse("tablero", args=["ranking"])), "En construcción")

    def test_help_lists_indicators(self):
        self.assertContains(self.client.get(reverse("ayuda")), indicadores.CATALOGO[0].definicion[:40])


class PrecalentarTests(TestCase):
    def test_periods_are_last_closed_week_and_month(self):
        ps = lectura.periodos_a_precalentar(date(2026, 11, 18))
        self.assertEqual([(p.tipo, p.desde) for p in ps],
                         [(TipoPeriodo.SEMANA, date(2026, 11, 9)), (TipoPeriodo.MES, date(2026, 10, 1))])

    def test_reads_afresh_with_longer_life(self):
        with mock.patch.object(lectura, "leer") as leer, mock.patch.object(lectura, "leer_operaciones") as ops,              mock.patch.object(lectura, "leer_cedis"):
            lectura.precalentar(date(2026, 11, 18))
        self.assertEqual(ops.call_count, 2)
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


class GraficasTests(TestCase):
    def setUp(self):
        self.p = Periodo.semana_de(date(2026, 11, 11))
        self.ant, self.anio = self.p.anterior(), self.p.mismo_periodo_anio_anterior()
        a = Sucursal(pk=1, clave="a", nombre="A")

        def m(per, venta):
            x = _m(per, venta, 7)
            x.venta_por_dia = {per.desde: Decimal(venta)}
            x.clientes_por_dia = {per.desde: Decimal(10)}
            x.canal = {"salon": Decimal(venta) * Decimal("0.8"), "plataformas": Decimal(venta) * Decimal("0.2")}
            return x
        self.lec = lectura.Lectura([a], self.p, self.ant, self.anio, [m(self.p, 1000)], [m(self.ant, 900)],
                                   [m(self.anio, 800)], datetime(2026, 11, 18, tzinfo=dt_tz.utc), "prod")
        self.sel = lectura.seleccionar(self.lec, None)

    def test_week_sales_and_guests_vs_last_year_from_central(self):
        venta, clientes = graficas.de_venta(self.lec, self.sel)
        self.assertEqual(venta["etiquetas"][0][:3], "Lun")
        self.assertEqual(venta["series"][0]["valores"][0], 1000.0)
        self.assertEqual(venta["series"][1]["valores"][0], 800.0)       # last year, by position
        self.assertTrue(venta["pesos"])
        self.assertFalse(clientes["pesos"])

    def test_channel_pie_from_central_rows(self):
        canales = {g["id"]: g for g in graficas.de_mezcla(self.sel)}.get("canales")
        if canales is None:          # channel shares need ticket detail in Central's rows
            self.skipTest("no channel rows without ticket detail")
        self.assertAlmostEqual(sum(canales["valores"]), 100.0, places=3)

    def test_no_composition_without_hourly_detail(self):
        self.assertEqual(graficas.de_composicion(self.sel), [])


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class ComercialTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("director", password="x-prueba-123"))
        Sucursal.objects.create(clave="a", nombre="A", wansoft_subsidiary_id=1)

    def _lectura(self, periodo, costos=True, refrescar=False):
        a = Sucursal.objects.get(clave="a")
        ant, anio = periodo.anterior(), periodo.mismo_periodo_anio_anterior()
        actual = _m(periodo, 1234, periodo.dias)
        actual.venta_por_dia = {periodo.desde: Decimal(1234)}
        return lectura.Lectura([a], periodo, ant, anio, [actual], [_m(ant, 1000, ant.dias)],
                               [_m(anio, 1100, anio.dias)], datetime(2026, 11, 18, 15, 0, tzinfo=dt_tz.utc),
                               "prod", {"A": {}} if periodo.tipo == TipoPeriodo.MES else None)

    def test_comercial_tab_has_cards_charts_and_tooltips(self):
        with mock.patch.object(lectura, "leer", side_effect=self._lectura):
            r = self.client.get(reverse("tablero", args=["comercial"]))
        self.assertContains(r, "Venta por plataformas (delivery)")
        self.assertContains(r, 'id="datos-graficas"')
        self.assertContains(r, "chart.umd.min.js")
        self.assertContains(r, 'class="nube"')
        self.assertNotContains(r, "Costo total %")       # costs live in the overview

    def test_month_has_trend_chart(self):
        hoy_mes = lectura.periodos_cerrados(TipoPeriodo.MES)[0]
        with mock.patch.object(lectura, "leer", side_effect=self._lectura):
            r = self.client.get(reverse("tablero", args=["comercial"]),
                                {"tipo": "mes", "desde": hoy_mes.desde.isoformat()})
        self.assertContains(r, "Venta bruta mensual vs año anterior")

    def test_overview_has_network_charts(self):
        with mock.patch.object(lectura, "leer", side_effect=self._lectura):
            r = self.client.get(reverse("tablero", args=["portada"]))
        self.assertContains(r, 'id="datos-graficas"')
        self.assertContains(r, "chartjs-chart-matrix")


# ---------------------------------------------------------------------------
# Block 4: Operaciones (Central's waiters' report and butchery).
# ---------------------------------------------------------------------------
from types import SimpleNamespace

from central.motor import tabla_comercial as _tc
from central.motor.comparativos import variacion as _variacion
from central.motor.meseros import DatosMeseros, Mesero


def _fila(valor, formato=_tc.MONEDA):
    """A stand-in for a row of Central's tables."""
    return SimpleNamespace(actual=Decimal(valor), anio_anterior=None, var_anio=_variacion(None, None),
                           anterior=None, var_anterior=_variacion(None, None),
                           indicador=SimpleNamespace(formato=formato), semaforo=None)


def _dm(periodo, venta, dias=7):
    m = Mesero("Mesero 1", cuentas=Decimal(10), personas=Decimal(25), venta_bruta=Decimal(venta),
               venta_neta=Decimal(venta), dias=Decimal(dias), minutos_mesa=Decimal(900),
               mesas_con_tiempo=Decimal(10), propina=Decimal(venta) * Decimal("0.1"), tarjeta=Decimal(venta))
    con_datos = periodo.dias if venta else 0          # no sales = no closings that period
    return DatosMeseros(periodo=periodo, meseros={"Mesero 1": m}, dias_con_cierre=con_datos,
                        dias_con_detalle=con_datos)


def _pieza(sid, fecha, base, merma, costo, producto="Arrachera"):
    return {"sucursal": sid, "producto": producto, "base": Decimal(base), "merma": Decimal(merma),
            "generado": Decimal(base) - Decimal(merma), "costo": Decimal(costo), "fecha": fecha}


class OperacionesTests(TestCase):
    def test_draft_thresholds_waiter_sales_per_day(self):
        ind = indicadores.POR_CLAVE["venta_mesero_dia"]
        for valor, color in ((14500, "verde"), (14499.99, "naranja"), (11500, "naranja"), (11499.99, "rojo")):
            self.assertEqual(indicadores._desde_fila(ind, _fila(valor)).semaforo, color, valor)

    def test_draft_thresholds_tip(self):
        ind = indicadores.POR_CLAVE["propina"]
        for valor, color in (("0.09", "verde"), ("0.0899", "naranja"), ("0.08", "naranja"), ("0.0799", "rojo")):
            self.assertEqual(indicadores._desde_fila(ind, _fila(valor, _tc.PORCENTAJE)).semaforo, color, valor)
        self.assertIn("verde desde 9%", ind.regla_semaforo)

    def _lectura(self):
        p = Periodo.semana_de(date(2026, 11, 11))
        ant, anio = p.anterior(), p.mismo_periodo_anio_anterior()
        a = Sucursal(pk=1, clave="a", nombre="A", wansoft_subsidiary_id=10)
        b = Sucursal(pk=2, clave="b", nombre="B", wansoft_subsidiary_id=20, considerar_costo=False)
        piezas = [_pieza(10, p.desde, 100, 20, 1000), _pieza(20, p.desde, 100, 10, 1000)]
        piezas_anio = [_pieza(10, anio.desde, 100, 25, 900)]
        return lectura.LecturaOperaciones(
            [a, b], p, ant, anio, [_dm(p, 105000), _dm(p, 80000)], [_dm(ant, 90000), _dm(ant, 70000)],
            [_dm(anio, 95000), _dm(anio, 0, dias=0)], piezas, piezas_anio,
            datetime(2026, 11, 18, tzinfo=dt_tz.utc), "prod")

    def _tarjetas(self, clave):
        sel = lectura.seleccionar_operaciones(self._lectura(), clave)
        return {t.indicador.clave: t for t in indicadores.tarjetas_operaciones(sel)}

    def test_branch_waiter_cards(self):
        t = self._tarjetas("a")
        self.assertEqual(t["venta_mesero_dia"].valor, Decimal(15000))     # 105,000 / 7 days
        self.assertEqual(t["venta_mesero_dia"].semaforo, "verde")
        self.assertEqual(t["tiempo_mesa"].valor, Decimal(90))

    def test_consolidated_comparable_branches(self):
        t = self._tarjetas(None)
        self.assertEqual(t["venta_mesero"].excluidas_anio, ("B",))   # B had no data last year

    def test_butchery_branch_vs_every_branch_and_last_year(self):
        t = self._tarjetas("a")["merma_tablajeria"]
        self.assertEqual((t.valor, t.anio_anterior), (Decimal("0.2"), Decimal("0.25")))
        self.assertEqual(t.var_anio.color, "verde")                  # less shrinkage than last year
        self.assertIn("Todas las sucursales: 15.0%", t.extra[0])
        self.assertEqual(self._tarjetas("a")["costo_merma"].valor, Decimal(200))   # 20 kg x $10/kg

    def test_butchery_cost_not_considered(self):
        t = self._tarjetas("b")
        self.assertTrue(t["merma_tablajeria"].mostrar)
        self.assertIn("No se considera el costo", t["costo_merma"].aviso)

    def test_no_butchery_reading(self):
        lec = self._lectura()
        lec.piezas_actual = None
        t = {x.indicador.clave: x for x in indicadores.tarjetas_operaciones(lectura.seleccionar_operaciones(lec, "a"))}
        self.assertIn("Sin datos de tablajería", t["merma_tablajeria"].aviso)

    def test_pending_cards(self):
        t = self._tarjetas(None)
        for clave in ("costo_teorico", "platillos_86", "gastos_operativos"):
            self.assertFalse(t[clave].mostrar)


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class OperacionesVistaTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("director", password="x-prueba-123"))
        Sucursal.objects.create(clave="a", nombre="A", wansoft_subsidiary_id=10)

    def test_tab_renders_from_its_own_reading(self):
        lec = OperacionesTests()._lectura()
        lec.sucursales = [Sucursal.objects.get(clave="a")]
        lec.meseros_actual, lec.meseros_previo, lec.meseros_anio = (lec.meseros_actual[:1], lec.meseros_previo[:1],
                                                                    lec.meseros_anio[:1])
        with mock.patch.object(lectura, "leer_operaciones", return_value=lec) as ops, \
             mock.patch.object(lectura, "leer") as leer:
            r = self.client.get(reverse("tablero", args=["operaciones"]))
        self.assertTrue(ops.called)
        self.assertFalse(leer.called)                               # the commercial reading is not paid here
        self.assertContains(r, "Venta por mesero por día")
        self.assertContains(r, "Merma tablajería %")
        self.assertContains(r, "Gas, carbón, limpieza y mantenimiento")


class GraficasRedTests(TestCase):
    """Network charts: every value is a figure of Central's rows per branch."""

    def setUp(self):
        self.p = Periodo.semana_de(date(2026, 11, 11))
        ant, anio = self.p.anterior(), self.p.mismo_periodo_anio_anterior()
        self.a = Sucursal(pk=1, clave="a", nombre="A", wansoft_subsidiary_id=10)
        self.b = Sucursal(pk=2, clave="b", nombre="B", wansoft_subsidiary_id=20)

        def m(per, venta, costo=None):
            x = _m(per, venta, per.dias)
            if costo is not None:
                x.costo_total, x.venta_neta_con_costo_total = Decimal(costo), Decimal(venta)
            return x
        self.lec = lectura.Lectura([self.a, self.b], self.p, ant, anio,
                                   [m(self.p, 1100, 400), m(self.p, 900, 350)], [m(ant, 1000), m(ant, 950)],
                                   [m(anio, 1000), m(anio, 1000)], datetime(2026, 11, 18, tzinfo=dt_tz.utc), "prod")

    def test_overview_matrix_ranking_treemap(self):
        g = {x["id"]: x for x in graficas.de_portada(self.lec, "a")}
        puntos = {p["etiqueta"]: p for p in g["matriz"]["puntos"]}
        self.assertAlmostEqual(puntos["A"]["x"], 10.0)            # +10% vs last year
        self.assertAlmostEqual(puntos["A"]["y"], 400 / 11)        # cost 400 / net 1100
        self.assertTrue(puntos["A"]["resaltar"])
        self.assertEqual(g["ranking"]["etiquetas"], ["A", "B"])   # sorted by growth
        self.assertEqual(g["ranking"]["colores"], ["verde", "rojo"])
        self.assertEqual(sum(i["valor"] for i in g["arbol"]["items"]), 2000.0)

    def test_operations_charts_need_no_extra_reading(self):
        lec = OperacionesTests()._lectura()
        g = {x["id"]: x for x in graficas.de_operaciones(lec, lectura.seleccionar_operaciones(lec, "a"), "a")}
        self.assertIn("productividad", g)
        self.assertIn("merma", g)                                 # per cut, branch vs every branch
        self.assertIn("meseros", g)                               # one branch: its waiters
        self.assertEqual(g["productividad"]["lineas_x"], [14500.0])



class CedisTests(TestCase):
    """CEDIS cards from Central's fill rate, summary and input inflation."""

    def _sel(self, fill=Decimal("0.97"), inflacion=Decimal("0.05"), inpc=Decimal("0.04")):
        from central.motor import fill_rate, reporte_cedis
        f = fill_rate.Fill("Total", fill, 10, 7, 5)
        b = fill_rate.Fill(reporte_cedis.BODEGON, fill, 10, 7, 5)
        resumen = fill_rate.ResumenFill(f, [b], [fill_rate.Fill("A", fill, 10, 7, 5)], 1)
        total = dict(ordenes=5, modificadas=2, pct=Decimal("0.4"), con_cantidad=1, con_extras=1, con_monto=0,
                     por_sucursal=1, por_cedis=1, diferencia=Decimal("-100"))
        infl = SimpleNamespace(inflacion=inflacion, inpc=inpc, inpc_mes=date(2026, 9, 1), sin_comparar=[],
                               estado=__import__("central.motor.inflacion_insumos", fromlist=["estado"]).estado(inflacion, inpc),
                               filas=[])
        return lectura.SeleccionCedis("Consolidado", SimpleNamespace(ordenes=[]), resumen, [], total, infl)

    def _t(self, sel):
        return {t.indicador.clave: t for t in indicadores.tarjetas_cedis(sel)}

    def test_fill_rate_light_from_central(self):
        self.assertEqual(self._t(self._sel(Decimal("0.98")))["fill_rate"].semaforo, "verde")
        self.assertEqual(self._t(self._sel(Decimal("0.97")))["fill_rate"].semaforo, "naranja")
        self.assertEqual(self._t(self._sel(Decimal("0.94")))["fill_rate"].semaforo, "rojo")

    def test_missing_provider_says_so(self):
        self.assertIn("Sin pedidos", self._t(self._sel())["fill_empanadas"].aviso)

    def test_modifications_and_inflation(self):
        t = self._t(self._sel())
        self.assertEqual(t["pct_modificados"].valor, Decimal("0.4"))
        self.assertEqual(t["pct_modificados"].linea, "2 de 5 pedidos")
        self.assertEqual(t["inflacion_top20"].semaforo, "naranja")          # 5% vs INPC 4% (+2 pp margin)
        self.assertIsNone(t["fill_rate"].var_anio)                          # one period, no comparison

    def test_pending_cards(self):
        t = self._t(self._sel())
        for clave in ("exactitud_inventario", "rechazos_calidad", "cuatro_candados"):
            self.assertFalse(t[clave].mostrar)
