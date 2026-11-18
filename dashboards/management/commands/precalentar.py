"""Read the last closed week and month ahead into the cache (warm-up).

Run hourly by the scheduled task "Dashboards Fonda - Precalentar"
(deploy/precalentar.ps1). Exit code 1 when a read fails, so Task Scheduler
shows the run as failed.
"""

import logging

from django.core.management.base import BaseCommand, CommandError

from dashboards import lectura

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Lee por adelantado la última semana y el último mes cerrados (caché del tablero)."

    def handle(self, *args, **options):
        try:
            resultados = lectura.precalentar()
        except Exception as exc:
            log.exception("Precalentado falló")
            raise CommandError(f"Precalentado falló: {exc}") from exc
        for periodo, segundos in resultados:
            linea = f"{periodo.etiqueta()}: leído en {segundos:.0f} s"
            log.info("Precalentado %s", linea)
            self.stdout.write(linea)
