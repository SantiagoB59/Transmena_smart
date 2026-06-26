from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo

from services.reporte_alertas_email import (
    enviar_reporte_diario_alertas
)

# Configurar la zona horaria de Colombia
scheduler = BackgroundScheduler(
    timezone=ZoneInfo("America/Bogota")
)


def iniciar_scheduler(app):

    scheduler.add_job(
        func=lambda: enviar_reporte_diario_alertas(app),
        trigger='cron',
        hour=18,
        minute=0,
        id='reporte_alertas_diario',
        replace_existing=True
    )

    scheduler.start()

    print("✅ Scheduler iniciado (Reporte diario 6:00 PM - America/Bogota)")
    
    
# Ejecutar cada minuto para pruebas

# from apscheduler.schedulers.background import BackgroundScheduler
# from services.reporte_alertas_email import (
#     enviar_reporte_diario_alertas
# )

# scheduler = BackgroundScheduler()


# def iniciar_scheduler(app):

#     scheduler.add_job(
#         func=lambda: enviar_reporte_diario_alertas(app),
#         trigger='interval',
#         minutes=1,
#         id='reporte_alertas_diario',
#         replace_existing=True
#     )

#     scheduler.start()

#     print("✅ Scheduler iniciado")