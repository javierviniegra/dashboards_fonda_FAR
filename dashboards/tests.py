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
