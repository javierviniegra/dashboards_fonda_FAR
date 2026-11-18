from django.contrib import admin

from .models import Sucursal


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ("nombre", "clave", "formato", "activa", "considerar_costo",
                    "wansoft_subsidiary_id", "odoo_company_id")
    list_filter = ("activa", "formato", "considerar_costo")
    search_fields = ("nombre", "clave")
