from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo

from services.reporte_alertas_email import (
    enviar_reporte_diario_alertas
)

from services.verificacion_kilometraje import (
    generar_verificacion_kilometraje
)

scheduler = BackgroundScheduler(
    timezone=ZoneInfo("America/Bogota")
)


def ejecutar_verificacion(app):
    with app.app_context():
        generar_verificacion_kilometraje()


def iniciar_scheduler(app):

    # Reporte diario
    scheduler.add_job(
        func=lambda: enviar_reporte_diario_alertas(app),
        trigger='cron',
        hour=18,
        minute=0,
        id='reporte_alertas_diario',
        replace_existing=True
    )

    # Verificación de kilometraje
    scheduler.add_job(
        func=lambda: ejecutar_verificacion(app),
        trigger='cron',
        day='1,16',
        hour=1,
        minute=0,
        id='verificacion_km',
        replace_existing=True
    )

    scheduler.start()

    print("✅ Scheduler iniciado")
    print("📧 Reporte diario: 6:00 PM")
    print("🚗 Verificación kilometraje: 1:00 AM")
    
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