from django.db import models


class Sucursal(models.Model):
    """A branch of the dashboards. Same fields as Central de Reportes'
    `cuentas.Sucursal` that Central's engine reads (`nombre`,
    `wansoft_subsidiary_id`, `wansoft_ticket_nombre`, `odoo_company_id`,
    `formato`, `considerar_costo`), so these objects go straight into
    `central.motor`. Loaded from Central's own list by `cargar_sucursales`."""

    class Formato(models.TextChoices):
        FONDA = "fonda", "Fonda"
        TAQUERIA = "taqueria", "Taquería"
        ESQUINA = "esquina", "La Esquina"

    clave = models.SlugField(max_length=40, unique=True)
    nombre = models.CharField(max_length=120)
    activa = models.BooleanField(default=True)
    formato = models.CharField(max_length=10, choices=Formato.choices, default=Formato.FONDA)
    wansoft_subsidiary_id = models.IntegerField(
        null=True, blank=True, unique=True, help_text="getglobalcashclosing.subsidiary_id (Wansoft).")
    wansoft_ticket_nombre = models.CharField(
        max_length=120, blank=True, help_text="Nombre de la sucursal en el detalle de tickets (vacío = sin detalle).")
    odoo_company_id = models.IntegerField(null=True, blank=True, unique=True, help_text="res.company de Odoo.")
    considerar_costo = models.BooleanField(
        default=True, help_text="Desmarcado: la sucursal no muestra costo y el consolidado no considera su costo.")

    class Meta:
        ordering = ["nombre"]
        verbose_name_plural = "sucursales"

    def __str__(self):
        return self.nombre
