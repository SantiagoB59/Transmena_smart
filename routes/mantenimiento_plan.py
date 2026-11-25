from flask import Blueprint, request, jsonify
from models import (
    db,
    Vehiculo,
    VehiculoPlanItem,
    PlanItem,
    Mantenimiento,
    MantenimientoProgramado,
    Alerta
)

from datetime import date, timedelta, datetime

mantenimiento_plan_bp = Blueprint(
    'mantenimiento_plan',
    __name__
)

# =========================================
# 📌 1. CREAR PLAN VEHÍCULO
# =========================================
@mantenimiento_plan_bp.route(
    '/vehiculos/<int:vehiculo_id>/plan',
    methods=['POST']
)
def crear_plan_vehiculo(vehiculo_id):

    data = request.get_json()

    vehiculo = Vehiculo.query.get_or_404(
        vehiculo_id
    )
    # =====================================
    # VEHÍCULO INACTIVO = BLOQUEO TOTAL
    # =====================================
    if (
        (vehiculo.estado or '').strip().upper() == 'INACTIVO'
        or vehiculo.activo is False
    ):
        return jsonify({
            "error":
                "Vehículo inactivo: no se pueden crear planes ni alertas"
        }), 403
    
    # =====================================
# 🔥 INICIALIZAR CONTROL GPS
# =====================================

    if vehiculo.km_base_control is None:
        vehiculo.km_base_control = vehiculo.km_actual or 0

    if vehiculo.km_gps_inicial is None:
        vehiculo.km_gps_inicial = vehiculo.km_gps or 0

    plan_item_id = data.get('plan_item_id')

    if not plan_item_id:
        return jsonify({
            "error": "plan_item_id requerido"
        }), 400

    plan_item = PlanItem.query.get_or_404(
        plan_item_id
    )

    vpi = VehiculoPlanItem(

        vehiculo_id=vehiculo.id,

        plan_item_id=plan_item.id,

        tipo_control=(
            data.get('tipo_control')
            or plan_item.tipo_control
        ),

        frecuencia_valor=(
            data.get('frecuencia_valor')
            or plan_item.frecuencia_valor
        ),

        alerta_valor=(
            data.get('alerta_valor')
            or plan_item.alerta_valor
        ),

        ultimo_km=(
            vehiculo.km_actual or 0
        ),
        ultima_fecha=date.today(),

        activo=True
    )

    db.session.add(vpi)
    db.session.commit()

    return jsonify(
        vpi.to_dict()
    ), 201


# =========================================
# 📌 1B. REGISTRAR CORRECTIVO (UNA SOLA VEZ)
# =========================================
@mantenimiento_plan_bp.route(
    '/vehiculos/<int:vehiculo_id>/plan/correctivo',
    methods=['POST']
)
def crear_correctivo_vehiculo(vehiculo_id):

    data = request.get_json() or {}

    vehiculo = Vehiculo.query.get_or_404(
        vehiculo_id
    )
    # =====================================
    # VEHÍCULO INACTIVO = BLOQUEO TOTAL
    # =====================================
    if (
        (vehiculo.estado or '').strip().upper() == 'INACTIVO'
        or vehiculo.activo is False
    ):
        return jsonify({
            "error":
                "Vehículo inactivo: no se pueden crear planes ni alertas"
        }), 403

    plan_item_id = data.get('plan_item_id')
    km_realizado = data.get('km_realizado')

    if not plan_item_id:
        return jsonify({
            "error": "plan_item_id requerido"
        }), 400

    if km_realizado is None:
        return jsonify({
            "error": "km_realizado requerido"
        }), 400

    plan_item = PlanItem.query.get_or_404(
        plan_item_id
    )

    fecha = date.today()

    # El correctivo NO se programa: frecuencia y alerta en 0.
    # Así el generador no crea ciclos ni recordatorios.
    vpi = VehiculoPlanItem(

        vehiculo_id=vehiculo.id,

        plan_item_id=plan_item.id,

        tipo_control='KM',

        frecuencia_valor=0,

        alerta_valor=0,

        ultimo_km=km_realizado,

        ultima_fecha=fecha,

        activo=True
    )

    db.session.add(vpi)
    db.session.flush()

    mantenimiento = Mantenimiento(

        vehiculo_id=vehiculo.id,

        plan_item_id=plan_item.id,

        vehiculo_plan_item_id=vpi.id,

        fecha=fecha,

        km=km_realizado,

        tipo='CORRECTIVO',

        observaciones=data.get('observaciones'),

        completado=True
    )

    db.session.add(mantenimiento)
    db.session.flush()

    # Alerta ya resuelta para que el indicador HSEQ lo cuente
    # como reportado y ejecutado, sin dejar pendientes.
    alerta = Alerta(

        vehiculo_id=vehiculo.id,

        plan_item_id=plan_item.id,

        vehiculo_plan_item_id=vpi.id,

        mantenimiento_id=mantenimiento.id,

        tipo='MANTENIMIENTO',

        categoria='CORRECTIVO',

        titulo=f'Correctivo: {plan_item.nombre}',

        mensaje=(
            'Correctivo registrado una sola vez al '
            f'{km_realizado} km.'
        ),

        prioridad='MEDIA',

        estado='RESUELTA',

        origen='CORRECTIVO',

        fecha_evento=datetime.utcnow(),

        fecha_resolucion=datetime.utcnow()
    )

    db.session.add(alerta)
    db.session.commit()

    return jsonify(
        vpi.to_dict()
    ), 201


# =========================================
# 📌 2. OBTENER PLAN VEHÍCULO
# =========================================
@mantenimiento_plan_bp.route(
    '/vehiculos/<int:vehiculo_id>/plan',
    methods=['GET']
)
def get_plan_vehiculo(vehiculo_id):

    Vehiculo.query.get_or_404(
        vehiculo_id
    )

    items = VehiculoPlanItem.query.filter_by(
        vehiculo_id=vehiculo_id,
        activo=True
    ).all()

    return jsonify([
        i.to_dict()
        for i in items
    ])


# =========================================
# 📌 3. ALERTAS
# =========================================
@mantenimiento_plan_bp.route(
    '/mantenimientos/alertas',
    methods=['GET']
)
def alertas():

    items = VehiculoPlanItem.query.filter_by(
        activo=True
    ).all()

    alertas = []

    for item in items:

        estado = item.calcular_estado()

        if estado in ['PENDIENTE', 'VENCIDO']:

            data = item.to_dict()

            alertas.append({

                "vehiculo_id": item.vehiculo_id,

                "placa": (
                    item.vehiculo.placa
                    if item.vehiculo else None
                ),

                "estado": estado,

                "tipo_control": item.tipo_control,

                "restante": data.get(
                    'restante'
                ),

                "programado": data.get(
                    'programado'
                ),

                "plan_item": data.get(
                    'plan_item'
                )
            })

    return jsonify(alertas)


@mantenimiento_plan_bp.route(
    '/plan/<int:id>/completar',
    methods=['PUT']
)
def completar(id):

    # =========================================
    # 1. OBTENER PLAN DEL VEHÍCULO
    # =========================================

    vpi = VehiculoPlanItem.query.get_or_404(id)

    vehiculo = Vehiculo.query.get_or_404(
        vpi.vehiculo_id
    )

    plan_item = vpi.plan_item

    fecha_hoy = date.today()

    km_actual = vehiculo.km_actual or 0

    tipo_mantenimiento = (
        plan_item.tipo_mantenimiento
        if plan_item
        else None
    )

    # =========================================
    # CORRECTIVO = ARREGLO DE UNA SOLA VEZ
    # =========================================
    # Si el ítem ya tiene un arreglo completado, no se crea
    # otro mantenimiento aunque corra el tiempo/km y vuelva
    # a aparecer la alerta.
    # =========================================

    es_correctivo = (
        (tipo_mantenimiento or '').upper() == 'CORRECTIVO'
    )

    if es_correctivo:
        ya_arreglado = Mantenimiento.query.filter(
            Mantenimiento.completado == True,
            Mantenimiento.vehiculo_plan_item_id == vpi.id
        ).order_by(
            Mantenimiento.id.asc()
        ).first()

        if ya_arreglado:
            alertas = Alerta.query.filter(
                Alerta.tipo == 'MANTENIMIENTO',
                Alerta.estado == 'ACTIVA',
                Alerta.vehiculo_plan_item_id == vpi.id
            ).all()

            for alerta in alertas:
                alerta.estado = 'RESUELTA'
                alerta.mantenimiento_id = ya_arreglado.id
                alerta.fecha_resolucion = datetime.utcnow()

            db.session.commit()

            return jsonify({
                "mensaje": (
                    "El correctivo ya fue arreglado. No se crea "
                    "una nueva ejecución por ciclo."
                ),
                "mantenimiento_id": ya_arreglado.id,
                "ya_completado": True
            }), 200

    # =========================================
    # 2. BUSCAR PROGRAMACIÓN PENDIENTE
    # =========================================

    programado = None

    if tipo_mantenimiento == 'PREVENTIVO':

        programado = MantenimientoProgramado.query.filter(
            MantenimientoProgramado.vehiculo_plan_item_id == vpi.id,
            MantenimientoProgramado.estado == 'PROGRAMADO'
        ).order_by(
            MantenimientoProgramado.id.asc()
        ).first()

    # =========================================
    # 3. CREAR MANTENIMIENTO
    # =========================================

    mantenimiento = Mantenimiento(

        vehiculo_id=vpi.vehiculo_id,

        plan_item_id=vpi.plan_item_id,

        vehiculo_plan_item_id=vpi.id,

        mantenimiento_programado_id=(
            programado.id
            if programado
            else None
        ),

        fecha=fecha_hoy,

        km=km_actual,

        tipo=tipo_mantenimiento
    )

    db.session.add(mantenimiento)

    # =========================================
    # 4. MARCAR PROGRAMACIÓN COMO EJECUTADA
    # =========================================

    if programado:

        programado.estado = 'EJECUTADO'

        programado.fecha_ejecucion = fecha_hoy

    # =========================================
    # 5. ACTUALIZAR CICLO DEL PLAN
    # =========================================

    if vpi.tipo_control == 'KM':

        vpi.ultimo_km = km_actual

    elif vpi.tipo_control == 'DIAS':

        vpi.ultima_fecha = fecha_hoy

    # =========================================
    # 6. CREAR SIGUIENTE PROGRAMACIÓN
    # =========================================

    nueva_programacion = None

    if tipo_mantenimiento == 'PREVENTIVO':

        nueva_programacion = MantenimientoProgramado(

            vehiculo_id=vpi.vehiculo_id,

            plan_item_id=vpi.plan_item_id,

            vehiculo_plan_item_id=vpi.id,

            estado='PROGRAMADO'
        )

        # -----------------------------------------
        # CONTROL POR KM
        # -----------------------------------------

        if vpi.tipo_control == 'KM':

            nueva_programacion.km_programado = (
                km_actual +
                (vpi.frecuencia_valor or 0)
            )

        # -----------------------------------------
        # CONTROL POR DÍAS
        # -----------------------------------------

        elif vpi.tipo_control == 'DIAS':

            nueva_programacion.fecha_programada = (
                fecha_hoy +
                timedelta(
                    days=vpi.frecuencia_valor or 0
                )
            )

        db.session.add(
            nueva_programacion
        )

    # =========================================
    # 7. GUARDAR
    # =========================================

    db.session.commit()

    return jsonify({

        "msg": "Mantenimiento registrado correctamente",

        "mantenimiento_id": mantenimiento.id,

        "programacion_anterior": (
            programado.id
            if programado
            else None
        ),

        "siguiente_programacion": (
            nueva_programacion.id
            if nueva_programacion
            else None
        )

    }), 201