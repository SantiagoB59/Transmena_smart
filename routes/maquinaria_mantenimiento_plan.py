from flask import Blueprint, request, jsonify
from datetime import date, timedelta

from models import (
    db,
    Maquinaria,
    MaquinariaPlanItem,
    MaquinariaMantenimiento,
    MantenimientoProgramado
)

maquinaria_plan_bp = Blueprint(
    'maquinaria_plan',
    __name__
)

# =========================================
# CREAR PLAN
# =========================================
@maquinaria_plan_bp.route(
    '/maquinaria/<int:maquinaria_id>/plan',
    methods=['POST']
)
def crear_plan(maquinaria_id):

    data = request.get_json()

    maquinaria = Maquinaria.query.get_or_404(maquinaria_id)

    mpi = MaquinariaPlanItem(
        maquinaria_id=maquinaria.id,
        plan_item_id=data.get('plan_item_id'),

        frecuencia_horas=data.get('frecuencia_horas'),

        alerta_horas=data.get('alerta_horas', 20),

        activo=True
    )

    db.session.add(mpi)
    db.session.commit()

    return jsonify(mpi.to_dict()), 201


# =========================================
# OBTENER PLANES
# =========================================
@maquinaria_plan_bp.route(
    '/maquinaria/<int:maquinaria_id>/plan',
    methods=['GET']
)
def obtener_planes(maquinaria_id):

    items = MaquinariaPlanItem.query.filter_by(
        maquinaria_id=maquinaria_id,
        activo=True
    ).all()

    return jsonify([
        i.to_dict()
        for i in items
    ])


# =========================================
# ALERTAS
# =========================================
@maquinaria_plan_bp.route(
    '/maquinaria/alertas',
    methods=['GET']
)
def alertas():

    items = MaquinariaPlanItem.query.filter_by(
        activo=True
    ).all()

    response = []

    for i in items:

        restantes = i.calcular_horas_restantes()

        if restantes is None:
            continue

        if restantes <= i.alerta_horas:

            response.append({
                "maquinaria_id": i.maquinaria_id,

                "codigo": (
                    i.maquinaria.codigo
                    if i.maquinaria else None
                ),

                "estado": i.calcular_estado(),

                "horometro_actual": (
                    i.maquinaria.horometro_actual
                    if i.maquinaria else 0
                ),

                "horas_programadas": i.calcular_horas_programadas(),

                "horas_restantes": restantes,

                "plan_item": (
                    i.plan_item.to_dict()
                    if i.plan_item else None
                )
            })

    return jsonify(response)



@maquinaria_plan_bp.route(
    '/maquinaria/plan/<int:id>/completar',
    methods=['PUT']
)
def completar(id):

    # =========================================
    # 1. OBTENER PLAN DE LA MAQUINARIA
    # =========================================

    mpi = MaquinariaPlanItem.query.get_or_404(id)

    maquinaria = Maquinaria.query.get_or_404(
        mpi.maquinaria_id
    )

    plan_item = mpi.plan_item

    fecha_hoy = date.today()

    horas_actuales = (
        maquinaria.horometro_actual or 0
    )

    tipo_mantenimiento = (
        plan_item.tipo_mantenimiento
        if plan_item
        else None
    )

    # =========================================
    # 2. BUSCAR PROGRAMACIÓN PENDIENTE
    # =========================================

    programado = None

    if tipo_mantenimiento == 'PREVENTIVO':

        programado = MantenimientoProgramado.query.filter(
            MantenimientoProgramado.maquinaria_plan_item_id == mpi.id,
            MantenimientoProgramado.estado == 'PROGRAMADO'
        ).order_by(
            MantenimientoProgramado.id.asc()
        ).first()

    # =========================================
    # 3. CREAR MANTENIMIENTO
    # =========================================

    mantenimiento = MaquinariaMantenimiento(

        maquinaria_id=mpi.maquinaria_id,

        maquinaria_plan_item_id=mpi.id,

        plan_item_id=mpi.plan_item_id,

        mantenimiento_programado_id=(
            programado.id
            if programado
            else None
        ),

        fecha=fecha_hoy,

        horas=horas_actuales,

        tipo=tipo_mantenimiento
    )

    db.session.add(
        mantenimiento
    )

    # =========================================
    # 4. MARCAR PROGRAMACIÓN COMO EJECUTADA
    # =========================================

    if programado:

        programado.estado = 'EJECUTADO'

        programado.fecha_ejecucion = fecha_hoy

    # =========================================
    # 5. ACTUALIZAR CICLO
    # =========================================

    mpi.ultima_horas = horas_actuales

    mpi.ultima_fecha = fecha_hoy

    # =========================================
    # 6. CREAR SIGUIENTE PROGRAMACIÓN
    # =========================================

    nueva_programacion = None

    if tipo_mantenimiento == 'PREVENTIVO':

        nueva_programacion = MantenimientoProgramado(

            maquinaria_id=mpi.maquinaria_id,

            plan_item_id=mpi.plan_item_id,

            maquinaria_plan_item_id=mpi.id,

            horas_programadas=(
                horas_actuales +
                (mpi.frecuencia_horas or 0)
            ),

            estado='PROGRAMADO'
        )

        db.session.add(
            nueva_programacion
        )

    # =========================================
    # 7. GUARDAR
    # =========================================

    db.session.commit()

    return jsonify({

        "message": "Mantenimiento registrado correctamente",

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