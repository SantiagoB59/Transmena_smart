from models import (
    db,
    Alerta,
    Vehiculo,
    VehiculoPlanItem,
    VehiculoDocumento,
    VehiculoUbicacionActual,
    
    Maquinaria,
    MaquinariaPlanItem,
    MaquinariaDocumento,
    TipoVehiculoCampo,
    VehiculoCampoValor,
)

from datetime import datetime, date

# sockets
from sockets.socket_handler import socketio
from services.email_service import enviar_email_alerta

# =========================================================
# CREAR ALERTA
# =========================================================
from zoneinfo import ZoneInfo

datetime.now(ZoneInfo("America/Bogota"))

from datetime import datetime, timedelta

def crear_alerta(
    tipo,
    categoria,

    titulo,
    mensaje,

    prioridad='MEDIA',
    origen='SISTEMA',

    vehiculo_id=None,
    maquinaria_id=None,

    viaje_id=None,

    mantenimiento_id=None,
    maquinaria_mantenimiento_id=None,

    plan_item_id=None,

    vehiculo_plan_item_id=None,
    maquinaria_plan_item_id=None,

    metadata=None
):

    """
    Evita crear alertas duplicadas ACTIVAS
    y actualiza si ya existe
    """

    # =====================================================
    # BASE QUERY
    # =====================================================
    query = Alerta.query.filter_by(
        tipo=tipo,
        categoria=categoria,
        estado='ACTIVA'
    )

    # =====================================================
# IDENTIDAD ÚNICA DE LA ALERTA 🔥
# =====================================================
    if vehiculo_plan_item_id:
        query = query.filter_by(vehiculo_plan_item_id=vehiculo_plan_item_id)

    elif maquinaria_plan_item_id:
        query = query.filter_by(maquinaria_plan_item_id=maquinaria_plan_item_id)

    elif vehiculo_id:
        query = query.filter_by(vehiculo_id=vehiculo_id)

    elif maquinaria_id:
        query = query.filter_by(maquinaria_id=maquinaria_id)

# opcional pero recomendado
    if plan_item_id:
        query = query.filter_by(plan_item_id=plan_item_id)

    

    # =====================================================
    # BUSCAR ALERTA EXISTENTE
    # =====================================================
    alerta_existente = query.order_by(
        Alerta.created_at.desc()
    ).first()

    # =====================================================
    # SI EXISTE → ACTUALIZAR
    # =====================================================
    if alerta_existente:

        hubo_cambios = False

        if alerta_existente.titulo != titulo:
            alerta_existente.titulo = titulo
            hubo_cambios = True

        if alerta_existente.mensaje != mensaje:
            alerta_existente.mensaje = mensaje
            hubo_cambios = True

        if alerta_existente.prioridad != prioridad:
            alerta_existente.prioridad = prioridad
            hubo_cambios = True

        if alerta_existente.metadata_json != metadata:
            alerta_existente.metadata_json = metadata
            hubo_cambios = True

        # actualizar fecha si hubo cambios
        # siempre refresca la alerta (aunque no cambie texto)
        alerta_existente.fecha_evento = datetime.utcnow()

        if hubo_cambios:
            db.session.commit()

            socketio.emit(
                "alerta_actualizada",
                alerta_existente.to_dict()
            )

            # email solo críticas
            if prioridad == "CRITICA":
                try:
                    enviar_email_alerta(alerta_existente)
                except Exception as e:
                    print("Error enviando email:", e)

        return alerta_existente

    # =====================================================
    # CREAR NUEVA ALERTA
    # =====================================================
    alerta = Alerta(

        vehiculo_id=vehiculo_id,
        maquinaria_id=maquinaria_id,
        viaje_id=viaje_id,

        mantenimiento_id=mantenimiento_id,
        maquinaria_mantenimiento_id=maquinaria_mantenimiento_id,
        plan_item_id=plan_item_id,
        vehiculo_plan_item_id=vehiculo_plan_item_id,
        maquinaria_plan_item_id=maquinaria_plan_item_id,

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

    # =====================================================
    # SOCKET (TIEMPO REAL)
    # =====================================================
    socketio.emit(
        'nueva_alerta',
        alerta.to_dict()
    )

    # =====================================================
    # EMAIL (CRÍTICA / ALTA)
    # =====================================================
    try:
        if prioridad in ['CRITICA', 'ALTA']:
            enviar_email_alerta(alerta)
    except Exception as e:
        print("Error enviando email alerta:", e)

    return alerta


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
# RESOLVER ALERTAS CAMPOS DINÁMICOS
# =========================================================

def resolver_alertas_campo_dinamico(
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

        alerta.fecha_resolucion = (
            datetime.now(
                ZoneInfo("America/Bogota")
            )
        )

        socketio.emit(
            'alerta_resuelta',
            alerta.to_dict()
        )

    db.session.commit()

    return True


# =========================================================
# ALERTAS CAMPOS DINÁMICOS DE VEHÍCULOS
# =========================================================

def generar_alertas_campos_dinamicos():

    campos = (
        VehiculoCampoValor.query
        .join(
            TipoVehiculoCampo,
            VehiculoCampoValor.campo_id ==
            TipoVehiculoCampo.id
        )
        .join(
            Vehiculo,
            VehiculoCampoValor.vehiculo_id ==
            Vehiculo.id
        )
        .filter(
            TipoVehiculoCampo.tipo_dato == 'date',
            Vehiculo.activo == True
        )
        .all()
    )

    hoy = date.today()

    for campo_valor in campos:

        # =====================================================
        # VALIDACIONES
        # =====================================================

        if not campo_valor.valor:
            continue

        campo = campo_valor.campo

        if not campo:
            continue

        if campo.tipo_dato != 'date':
            continue

        vehiculo = Vehiculo.query.get(
            campo_valor.vehiculo_id
        )

        if not vehiculo:
            continue

        # =====================================================
        # CONVERTIR FECHA
        # =====================================================

        try:

            fecha_vencimiento = datetime.strptime(
                str(campo_valor.valor),
                '%Y-%m-%d'
            ).date()

        except (ValueError, TypeError):

            print(
                f"[ALERTAS] Fecha inválida en campo "
                f"{campo.nombre_campo}: "
                f"{campo_valor.valor}"
            )

            continue

        # =====================================================
        # CALCULAR DÍAS
        # =====================================================

        dias = (
            fecha_vencimiento - hoy
        ).days

        categoria = campo.nombre_campo

        # =====================================================
        # DOCUMENTO VIGENTE
        # =====================================================

        if dias > 15:

            resolver_alertas_campo_dinamico(
                vehiculo_id=vehiculo.id,
                categoria=categoria
            )

            continue

        # =====================================================
        # PRIORIDAD
        # =====================================================

        prioridad = (
            'CRITICA'
            if dias <= 0
            else 'MEDIA'
        )

        # =====================================================
        # ESTADO
        # =====================================================

        estado = (
            'VENCIDO'
            if dias <= 0
            else 'POR_VENCER'
        )

        # =====================================================
        # METADATA
        # =====================================================

        metadata = {

            'campo_id': campo.id,

            'campo': campo.nombre_campo,

            'fecha_vencimiento':
                fecha_vencimiento.isoformat(),

            'dias_restantes': dias,

            'estado': estado,

            'vehiculo_id': vehiculo.id,

            'placa': vehiculo.placa

        }

        # =====================================================
        # MENSAJE
        # =====================================================

        if dias > 1:

            mensaje = (
                f"{campo.nombre_campo} "
                f"del vehículo {vehiculo.placa} "
                f"vence en {dias} días"
            )

        elif dias == 1:

            mensaje = (
                f"{campo.nombre_campo} "
                f"del vehículo {vehiculo.placa} "
                f"vence mañana"
            )

        elif dias == 0:

            mensaje = (
                f"{campo.nombre_campo} "
                f"del vehículo {vehiculo.placa} "
                f"vence hoy"
            )

        else:

            mensaje = (
                f"{campo.nombre_campo} "
                f"del vehículo {vehiculo.placa} "
                f"venció hace {abs(dias)} días"
            )

        # =====================================================
        # CREAR / ACTUALIZAR ALERTA
        # =====================================================

        crear_alerta(

            tipo='DOCUMENTO',

            categoria=categoria,

            vehiculo_id=vehiculo.id,

            titulo=(
                f"{campo.nombre_campo} {estado}"
            ),

            mensaje=mensaje,

            prioridad=prioridad,

            origen='CAMPO_DINAMICO',

            metadata=metadata
        )
        
# =========================================================
# ALERTAS MANTENIMIENTO VEHÍCULOS
# =========================================================

def generar_alertas_vehiculos():

    items = VehiculoPlanItem.query.filter_by(
        activo=True
    ).all()

    for item in items:

        vehiculo = item.vehiculo

        if not vehiculo:
            continue

        # No generar nuevas alertas para vehículos INACTIVOS
        if vehiculo.estado == 'INACTIVO':
            continue

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

        vehiculo = Vehiculo.query.get(
            doc.vehiculo_id
        )

        if not vehiculo:
            continue

        # No generar nuevas alertas para vehículos INACTIVOS
        if vehiculo.estado == 'INACTIVO':
            continue

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

            'dias_restantes': dias,

            'estado': estado
}

        # -----------------------------------------
# MENSAJE
# -----------------------------------------

        if dias > 1:

            mensaje = (
                f"{doc.documento_tipo.nombre} vence en {dias} días"
            )

        elif dias == 1:

            mensaje = (
                f"{doc.documento_tipo.nombre} vence mañana"
            )

        elif dias == 0:

            mensaje = (
                f"{doc.documento_tipo.nombre} vence hoy"
            )

        else:

            mensaje = (
                f"{doc.documento_tipo.nombre} venció hace {abs(dias)} días"
            )

# -----------------------------------------
# CREAR / ACTUALIZAR ALERTA
# -----------------------------------------

        crear_alerta(

            tipo='DOCUMENTO',

            categoria=doc.documento_tipo.nombre,

            vehiculo_id=doc.vehiculo_id,

            titulo=f"Documento {estado}",

            mensaje=mensaje,

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

# No generar nuevas alertas para vehículos INACTIVOS
        if vehiculo.estado == 'INACTIVO':
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
    
    generar_alertas_maquinaria()

    generar_alertas_documentos()
    
    generar_alertas_documentos_maquinaria()

    generar_alertas_velocidad()
    
    generar_alertas_campos_dinamicos()

    # generar_alertas_apagado()


# =========================================================
# OBTENER TODAS
# =========================================================

def obtener_todas_alertas(estado_vehiculo=None):

    query = Alerta.query

    # ==========================================
    # FILTRAR POR ESTADO DEL VEHÍCULO
    # ==========================================
    if estado_vehiculo:
        query = query.join(
            Vehiculo,
            Alerta.vehiculo_id == Vehiculo.id
        ).filter(
            Vehiculo.estado == estado_vehiculo
        )

    alertas = query.order_by(
        Alerta.created_at.desc()
    ).all()

    return [
        a.to_dict()
        for a in alertas
    ]
# =========================================================
# OBTENER ACTIVAS
# =========================================================

def obtener_alertas_activas(estado_vehiculo=None):

    query = Alerta.query.filter_by(
        estado='ACTIVA'
    )

    # ==========================================
    # FILTRAR POR ESTADO DEL VEHÍCULO
    # ==========================================
    if estado_vehiculo:
        query = query.join(
            Vehiculo,
            Alerta.vehiculo_id == Vehiculo.id
        ).filter(
            Vehiculo.estado == estado_vehiculo
        )

    alertas = query.order_by(
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
    
    
# ========================================================
# OBTENER ALERTAS maquinaria
# ========================================================
def resolver_alertas_mantenimiento_maquinaria(
    maquinaria_plan_item_id
):

    alertas = Alerta.query.filter_by(
        tipo='MANTENIMIENTO',
        maquinaria_plan_item_id=maquinaria_plan_item_id,
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


def resolver_alertas_documento_maquinaria(
    maquinaria_id,
    categoria
):

    alertas = Alerta.query.filter_by(
        tipo='DOCUMENTO',
        categoria=categoria,
        maquinaria_id=maquinaria_id,
        estado='ACTIVA'
    ).all()

    for alerta in alertas:

        alerta.estado = 'RESUELTA'
        alerta.fecha_resolucion = datetime.utcnow()

    db.session.commit()

    return True


def generar_alertas_maquinaria():

    items = MaquinariaPlanItem.query.filter_by(
        activo=True
    ).all()

    for item in items:

        maquinaria = item.maquinaria

        if not maquinaria:
            continue

        # Solo generar alertas si la maquinaria está OPERATIVA
        if maquinaria.estado != 'OPERATIVO':
            continue

        estado = item.calcular_estado()

        if estado not in ['PENDIENTE', 'VENCIDO']:

            resolver_alertas_mantenimiento_maquinaria(
                item.id
            )

            continue

        prioridad = (
            'CRITICA'
            if estado == 'VENCIDO'
            else 'ALTA'
        )

        metadata = {

            'maquinaria': maquinaria.codigo,

            'plan_item': item.plan_item.nombre,

            'horometro_actual': maquinaria.horometro_actual,

            'ultima_horas': item.ultima_horas,

            'frecuencia_horas': item.frecuencia_horas,

            'estado_calculado': estado

        }

        crear_alerta(

            tipo='MANTENIMIENTO',

            categoria=estado,

            maquinaria_id=maquinaria.id,

            plan_item_id=item.plan_item_id,

            maquinaria_plan_item_id=item.id,

            titulo=f"Mantenimiento {estado}",

            mensaje=(
                f"Maquinaria {maquinaria.codigo} "
                f"requiere mantenimiento "
                f"{item.plan_item.nombre}"
            ),

            prioridad=prioridad,

            metadata=metadata
        )
        
        
def generar_alertas_documentos_maquinaria():

    documentos = MaquinariaDocumento.query.all()

    hoy = date.today()

    for doc in documentos:

        maquinaria = doc.maquinaria

        if not maquinaria:
            continue

        # Solo generar alertas si la maquinaria está OPERATIVA
        if maquinaria.estado != 'OPERATIVO':
            continue

        if not doc.fecha_vencimiento:
            continue

        dias = (
            doc.fecha_vencimiento - hoy
        ).days

        if dias > 15:

            resolver_alertas_documento_maquinaria(
                maquinaria_id=doc.maquinaria_id,
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

            'fecha_vencimiento': doc.fecha_vencimiento.isoformat(),

            'dias_restantes': dias,

            'estado': estado

        }

        if dias > 1:

            mensaje = (
                f"{doc.documento_tipo.nombre} vence en {dias} días"
            )

        elif dias == 1:

            mensaje = (
                f"{doc.documento_tipo.nombre} vence mañana"
            )

        elif dias == 0:

            mensaje = (
                f"{doc.documento_tipo.nombre} vence hoy"
            )

        else:

            mensaje = (
                f"{doc.documento_tipo.nombre} venció hace {abs(dias)} días"
            )

        crear_alerta(

            tipo='DOCUMENTO',

            categoria=doc.documento_tipo.nombre,

            maquinaria_id=doc.maquinaria_id,

            titulo=f"Documento {estado}",

            mensaje=mensaje,

            prioridad=prioridad,

            metadata=metadata
        )