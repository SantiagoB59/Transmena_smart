from models import (
    db,
    Alerta,
    Vehiculo,
    VehiculoPlanItem,
    VehiculoDocumento,
    VehiculoUbicacionActual
)

from datetime import datetime, date

# sockets
from sockets.socket_handler import socketio
from services.email_service import enviar_email_alerta

# =========================================================
# CREAR ALERTA
# =========================================================

def crear_alerta(
    tipo,
    categoria,

    titulo,
    mensaje,

    prioridad='MEDIA',
    origen='SISTEMA',

    vehiculo_id=None,
    viaje_id=None,

    mantenimiento_id=None,
    plan_item_id=None,
    vehiculo_plan_item_id=None,

    metadata=None
):

    """
    Evita crear alertas duplicadas ACTIVAS
    """

    query = Alerta.query.filter_by(
        tipo=tipo,
        categoria=categoria,
        estado='ACTIVA'
    )

    # -----------------------------------------
    # VEHÍCULO
    # -----------------------------------------
    if vehiculo_id:
        query = query.filter_by(
            vehiculo_id=vehiculo_id
        )

    # -----------------------------------------
    # PLAN ITEM
    # -----------------------------------------
    if vehiculo_plan_item_id:
        query = query.filter_by(
            vehiculo_plan_item_id=vehiculo_plan_item_id
        )

    alerta_existente = query.first()

    if alerta_existente:
        return alerta_existente

    # -----------------------------------------
    # CREAR ALERTA
    # -----------------------------------------
    alerta = Alerta(

        vehiculo_id=vehiculo_id,
        viaje_id=viaje_id,

        mantenimiento_id=mantenimiento_id,
        plan_item_id=plan_item_id,
        vehiculo_plan_item_id=vehiculo_plan_item_id,

        tipo=tipo,
        categoria=categoria,

        titulo=titulo,
        mensaje=mensaje,

        prioridad=prioridad,
        estado='ACTIVA',

        origen=origen,

        fecha_evento=datetime.utcnow(),

        metadata_json=metadata
    )

    db.session.add(alerta)
    db.session.commit()

    # -----------------------------------------
    # SOCKET (TIEMPO REAL)
    # -----------------------------------------
    socketio.emit(
        'nueva_alerta',
        alerta.to_dict()
    )

    # -----------------------------------------
    # EMAIL (solo críticas y altas)
    # -----------------------------------------
    try:

        if prioridad in ['CRITICA', 'ALTA']:

            enviar_email_alerta(alerta)

    except Exception as e:

        print("Error enviando email alerta:", e)

    return alerta
# =========================================================
# RESOLVER ALERTA
# =========================================================

def resolver_alerta(alerta_id):

    alerta = Alerta.query.get(alerta_id)

    if not alerta:
        return None

    alerta.estado = 'RESUELTA'
    alerta.fecha_resolucion = datetime.utcnow()

    db.session.commit()

    socketio.emit(
        'alerta_resuelta',
        alerta.to_dict()
    )

    return alerta


# =========================================================
# RESOLVER ALERTAS MANTENIMIENTO
# =========================================================

def resolver_alertas_mantenimiento(
    vehiculo_plan_item_id
):

    alertas = Alerta.query.filter_by(
        tipo='MANTENIMIENTO',
        vehiculo_plan_item_id=vehiculo_plan_item_id,
        estado='ACTIVA'
    ).all()

    for alerta in alertas:

        alerta.estado = 'RESUELTA'
        alerta.fecha_resolucion = datetime.utcnow()

        socketio.emit(
            'alerta_resuelta',
            alerta.to_dict()
        )

    db.session.commit()

    return True

# =========================================================
# RESOLVER ALERTAS DOCUMENTOS
# =========================================================

def resolver_alertas_documento(
    vehiculo_id,
    categoria
):

    alertas = Alerta.query.filter_by(
        tipo='DOCUMENTO',
        categoria=categoria,
        vehiculo_id=vehiculo_id,
        estado='ACTIVA'
    ).all()

    for alerta in alertas:

        alerta.estado = 'RESUELTA'
        alerta.fecha_resolucion = datetime.utcnow()

    db.session.commit()

    return True


# =========================================================
# ALERTAS MANTENIMIENTO VEHÍCULOS
# =========================================================

def generar_alertas_vehiculos():

    items = VehiculoPlanItem.query.filter_by(
        activo=True
    ).all()

    for item in items:

        estado = item.calcular_estado()

        # -----------------------------------------
        # SI YA NO NECESITA ALERTA
        # -----------------------------------------

        if estado not in ['PENDIENTE', 'VENCIDO']:

            resolver_alertas_mantenimiento(
                vehiculo_plan_item_id=item.id
            )

            continue

        vehiculo = item.vehiculo

        prioridad = (
            'CRITICA'
            if estado == 'VENCIDO'
            else 'ALTA'
        )

        metadata = {

            'vehiculo': vehiculo.placa,

            'plan_item': item.plan_item.nombre,

            'km_actual': vehiculo.km_actual,

            'ultimo_km': item.ultimo_km,

            'frecuencia': item.frecuencia_valor,

            'estado_calculado': estado
        }

        crear_alerta(

            tipo='MANTENIMIENTO',

            categoria=estado,

            vehiculo_id=vehiculo.id,

            plan_item_id=item.plan_item_id,

            vehiculo_plan_item_id=item.id,

            titulo=f"Mantenimiento {estado}",

            mensaje=(
                f"Vehículo {vehiculo.placa} "
                f"requiere mantenimiento "
                f"{item.plan_item.nombre}"
            ),

            prioridad=prioridad,

            metadata=metadata
        )


# =========================================================
# ALERTAS DOCUMENTOS
# =========================================================

def generar_alertas_documentos():

    documentos = VehiculoDocumento.query.all()

    hoy = date.today()

    for doc in documentos:

        if not doc.fecha_vencimiento:
            continue

        dias = (
            doc.fecha_vencimiento - hoy
        ).days

        # -----------------------------------------
        # DOCUMENTO OK
        # -----------------------------------------

        if dias > 15:

            resolver_alertas_documento(
                vehiculo_id=doc.vehiculo_id,
                categoria=doc.documento_tipo.nombre
            )

            continue

        prioridad = (
            'CRITICA'
            if dias <= 0
            else 'MEDIA'
        )

        estado = (
            'VENCIDO'
            if dias <= 0
            else 'POR_VENCER'
        )

        metadata = {

            'documento': doc.documento_tipo.nombre,

            'fecha_vencimiento': (
                doc.fecha_vencimiento.isoformat()
            ),

            'dias_restantes': dias
        }

        crear_alerta(

            tipo='DOCUMENTO',

            categoria=doc.documento_tipo.nombre,

            vehiculo_id=doc.vehiculo_id,

            titulo=f"Documento {estado}",

            mensaje=(
                f"{doc.documento_tipo.nombre} "
                f"vence en {dias} días"
            ),

            prioridad=prioridad,

            metadata=metadata
        )


# =========================================================
# ALERTAS GPS VELOCIDAD
# =========================================================

def generar_alertas_velocidad():

    ubicaciones = VehiculoUbicacionActual.query.all()

    LIMITE = 80

    for ubicacion in ubicaciones:

        if not ubicacion.speed:
            continue

        velocidad = ubicacion.speed

        if velocidad <= LIMITE:
            continue

        vehiculo = Vehiculo.query.get(
            ubicacion.vehiculo_id
        )

        if not vehiculo:
            continue

        prioridad = (
            'CRITICA'
            if velocidad >= 100
            else 'ALTA'
        )

        metadata = {

            'velocidad_detectada': velocidad,

            'limite_permitido': LIMITE,

            'gps_id': ubicacion.gps_id,

            'latitud': float(ubicacion.latitude),

            'longitud': float(ubicacion.longitude),

            'direccion': ubicacion.direccion_texto,

            'ciudad': ubicacion.ciudad
        }

        crear_alerta(

            tipo='GPS',

            categoria='EXCESO_VELOCIDAD',

            vehiculo_id=vehiculo.id,

            titulo='Exceso de velocidad',

            mensaje=(
                f"Vehículo {vehiculo.placa} "
                f"superó límite permitido "
                f"({velocidad} km/h)"
            ),

            prioridad=prioridad,

            origen='GPS',

            metadata=metadata
        )


# =========================================================
# ALERTAS GPS VEHÍCULO APAGADO
# =========================================================

def generar_alertas_apagado():

    ubicaciones = VehiculoUbicacionActual.query.all()

    for ubicacion in ubicaciones:

        if ubicacion.ignition != 0:
            continue

        vehiculo = Vehiculo.query.get(
            ubicacion.vehiculo_id
        )

        if not vehiculo:
            continue

        metadata = {

            'evento': ubicacion.evento,

            'direccion': ubicacion.direccion_texto,

            'ciudad': ubicacion.ciudad
        }

        crear_alerta(

            tipo='GPS',

            categoria='VEHICULO_APAGADO',

            vehiculo_id=vehiculo.id,

            titulo='Vehículo apagado',

            mensaje=(
                f"Vehículo {vehiculo.placa} "
                f"se encuentra apagado"
            ),

            prioridad='BAJA',

            origen='GPS',

            metadata=metadata
        )


# =========================================================
# EJECUTAR MOTOR COMPLETO
# =========================================================

def ejecutar_motor_alertas():

    generar_alertas_vehiculos()

    generar_alertas_documentos()

    generar_alertas_velocidad()

    # generar_alertas_apagado()


# =========================================================
# OBTENER TODAS
# =========================================================

def obtener_todas_alertas():

    alertas = Alerta.query.order_by(
        Alerta.created_at.desc()
    ).all()

    return [
        a.to_dict()
        for a in alertas
    ]


# =========================================================
# OBTENER ACTIVAS
# =========================================================

def obtener_alertas_activas():

    alertas = Alerta.query.filter_by(
        estado='ACTIVA'
    ).order_by(
        Alerta.created_at.desc()
    ).all()

    return [
        a.to_dict()
        for a in alertas
    ]


# =========================================================
# ESTADÍSTICAS
# =========================================================

def obtener_estadisticas_alertas():

    total = Alerta.query.count()

    activas = Alerta.query.filter_by(
        estado='ACTIVA'
    ).count()

    resueltas = Alerta.query.filter_by(
        estado='RESUELTA'
    ).count()

    criticas = Alerta.query.filter_by(
        prioridad='CRITICA',
        estado='ACTIVA'
    ).count()

    return {

        'total': total,

        'activas': activas,

        'resueltas': resueltas,

        'criticas': criticas
    }