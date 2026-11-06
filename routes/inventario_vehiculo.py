from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from models import (
    db,
    PlanItemDetalle,
    Vehiculo,
    VehiculoPlanItem,
    VehiculoPlanItemDetalle,
)

from services.alertas_service import (
    evaluar_alerta_articulo,
    resolver_alertas_articulo,
)

inventario_vehiculo_bp = Blueprint(
    'inventario_vehiculo',
    __name__
)


# =========================================================
# HELPERS
# =========================================================

def _obtener_vpi(vehiculo_id, vpi_id):
    """
    Obtiene la asignación del mantenimiento validando que pertenezca
    al vehículo solicitado. Evita exponer información de otros vehículos.
    """

    vpi = VehiculoPlanItem.query.filter_by(
        id=vpi_id,
        vehiculo_id=vehiculo_id,
        activo=True,
    ).first()

    if not vpi:

        return None, (
            jsonify({
                'error': (
                    'El mantenimiento no está asignado al vehículo '
                    'indicado.'
                )
            }),
            404,
        )

    return vpi, None


def _obtener_detalle_catalogo(vpi, detalle_id):
    """
    Valida que el artículo del catálogo pertenezca al mantenimiento.
    """

    detalle = PlanItemDetalle.query.filter_by(
        id=detalle_id,
        plan_item_id=vpi.plan_item_id,
    ).first()

    if not detalle:

        return None, (
            jsonify({
                'error': (
                    'El artículo no pertenece al mantenimiento '
                    'seleccionado.'
                )
            }),
            404,
        )

    return detalle, None


def _parsear_cantidad(valor):
    if isinstance(valor, bool):
        return None

    if isinstance(valor, int):
        cantidad = valor

    elif isinstance(valor, str) and valor.strip().isdigit():
        cantidad = int(valor.strip())

    else:
        return None

    if cantidad < 1:
        return None

    return cantidad


def _parsear_fecha(valor):
    """
    Retorna (fecha, error). Acepta None/'' como fecha nula.
    """

    if valor in (None, ''):
        return None, None

    if not isinstance(valor, str):
        return None, 'La fecha debe tener formato YYYY-MM-DD.'

    try:
        fecha = datetime.strptime(valor, '%Y-%m-%d').date()

        if fecha.isoformat() != valor:
            raise ValueError

        return fecha, None

    except ValueError:
        return None, 'La fecha no es válida. Usa el formato YYYY-MM-DD.'


def _estado_grupo(lotes):
    if not lotes:
        return 'SIN_REGISTRO'

    estados = [lote.calcular_estado() for lote in lotes]

    if 'VENCIDO' in estados:
        return 'VENCIDO'

    if 'PROXIMO' in estados:
        return 'PROXIMO'

    if 'VIGENTE' in estados:
        return 'VIGENTE'

    return 'SIN_FECHA'


def _serializar_inventario(vpi):
    """
    Devuelve el catálogo del mantenimiento agrupado por artículo,
    con todos los lotes registrados para ese vehículo.
    """

    lotes = VehiculoPlanItemDetalle.query.filter_by(
        vehiculo_plan_item_id=vpi.id
    ).order_by(
        VehiculoPlanItemDetalle.plan_item_detalle_id.asc(),
        VehiculoPlanItemDetalle.fecha_vencimiento.asc(),
        VehiculoPlanItemDetalle.id.asc(),
    ).all()

    lotes_por_detalle = {}

    for lote in lotes:
        lotes_por_detalle.setdefault(
            lote.plan_item_detalle_id,
            []
        ).append(lote)

    articulos = []

    resumen = {
        'total_articulos': 0,
        'vigentes': 0,
        'proximos': 0,
        'vencidos': 0,
        'sin_fecha': 0,
        'sin_registro': 0,
        'inventario_insuficiente': 0,
    }

    for detalle_catalogo in vpi.plan_item.articulos:

        lotes_articulo = lotes_por_detalle.get(
            detalle_catalogo.id,
            []
        )

        cantidad_total = sum(
            lote.cantidad or 0
            for lote in lotes_articulo
        )

        estado = _estado_grupo(lotes_articulo)

        inventario_suficiente = (
            cantidad_total >= (detalle_catalogo.cantidad or 0)
        )

        resumen['total_articulos'] += 1

        if estado == 'VIGENTE':
            resumen['vigentes'] += 1
        elif estado == 'PROXIMO':
            resumen['proximos'] += 1
        elif estado == 'VENCIDO':
            resumen['vencidos'] += 1
        elif estado == 'SIN_FECHA':
            resumen['sin_fecha'] += 1
        else:
            resumen['sin_registro'] += 1

        if not inventario_suficiente:
            resumen['inventario_insuficiente'] += 1

        articulos.append({
            'plan_item_detalle_id': detalle_catalogo.id,
            'nombre': detalle_catalogo.nombre,
            'cantidad_minima': detalle_catalogo.cantidad,
            'cantidad_total': cantidad_total,
            'inventario_suficiente': inventario_suficiente,
            'estado': estado,
            'lotes': [
                lote.to_dict()
                for lote in lotes_articulo
            ],
        })

    vehiculo = vpi.vehiculo

    return {
        'vehiculo_plan_item_id': vpi.id,
        'vehiculo_id': vpi.vehiculo_id,
        'vehiculo': (
            {
                'id': vehiculo.id,
                'placa': vehiculo.placa,
                'marca': vehiculo.marca,
                'modelo': vehiculo.modelo,
            }
            if vehiculo
            else None
        ),
        'plan_item_id': vpi.plan_item_id,
        'plan_item': (
            {
                'id': vpi.plan_item.id,
                'nombre': vpi.plan_item.nombre,
                'sistema': vpi.plan_item.sistema,
                'descripcion': vpi.plan_item.descripcion,
            }
            if vpi.plan_item
            else None
        ),
        'articulos': articulos,
        'resumen': resumen,
    }


def _evaluar_alerta(lote_id):
    lote = db.session.get(VehiculoPlanItemDetalle, lote_id)

    if lote:
        evaluar_alerta_articulo(lote)


# =========================================================
# GET /vehiculos/<id>/plan/<vpi_id>/articulos
# =========================================================

@inventario_vehiculo_bp.route(
    '/vehiculos/<int:vehiculo_id>/plan/<int:vpi_id>/articulos',
    methods=['GET']
)
def obtener_inventario_plan(vehiculo_id, vpi_id):

    vpi, error = _obtener_vpi(vehiculo_id, vpi_id)

    if error:
        return error

    return jsonify(_serializar_inventario(vpi))


# =========================================================
# GET /vehiculos/<id>/inventario
# =========================================================

@inventario_vehiculo_bp.route(
    '/vehiculos/<int:vehiculo_id>/inventario',
    methods=['GET']
)
def obtener_inventario_vehiculo(vehiculo_id):

    vehiculo = db.session.get(Vehiculo, vehiculo_id)

    if not vehiculo:
        return jsonify({
            'error': 'Vehículo no encontrado.'
        }), 404

    planes = VehiculoPlanItem.query.filter_by(
        vehiculo_id=vehiculo_id,
        activo=True,
    ).all()

    inventarios = []

    for vpi in planes:

        if not vpi.plan_item or not vpi.plan_item.articulos:
            continue

        inventarios.append(_serializar_inventario(vpi))

    return jsonify({
        'vehiculo': {
            'id': vehiculo.id,
            'placa': vehiculo.placa,
        },
        'planes': inventarios,
    })


# =========================================================
# POST /vehiculos/<id>/plan/<vpi_id>/articulos
# Inventario inicial / carga masiva de lotes
# =========================================================

@inventario_vehiculo_bp.route(
    '/vehiculos/<int:vehiculo_id>/plan/<int:vpi_id>/articulos',
    methods=['POST']
)
def registrar_inventario_inicial(vehiculo_id, vpi_id):

    vpi, error = _obtener_vpi(vehiculo_id, vpi_id)

    if error:
        return error

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            'error': 'El cuerpo de la solicitud debe ser un JSON válido.'
        }), 400

    articulos = data.get('articulos')

    if not isinstance(articulos, list) or not articulos:
        return jsonify({
            'error': 'Debes enviar al menos un artículo.'
        }), 400

    # Evita duplicados accidentales dentro de la misma operación.
    # Si llega dos veces el mismo artículo con la misma fecha,
    # se suman las cantidades.
    agrupados = {}

    for indice, item in enumerate(articulos, start=1):

        if not isinstance(item, dict):
            return jsonify({
                'error': f'El artículo {indice} no es válido.'
            }), 400

        detalle_id = item.get('plan_item_detalle_id')

        if (
            isinstance(detalle_id, bool)
            or not isinstance(detalle_id, int)
        ):
            return jsonify({
                'error': (
                    f'El artículo {indice} no tiene un '
                    'plan_item_detalle_id válido.'
                )
            }), 400

        detalle_catalogo, error = _obtener_detalle_catalogo(
            vpi,
            detalle_id
        )

        if error:
            return error

        cantidad = _parsear_cantidad(item.get('cantidad'))

        if cantidad is None:
            return jsonify({
                'error': (
                    f'La cantidad del artículo {indice} debe ser '
                    'un entero mayor que cero.'
                )
            }), 400

        fecha, error = _parsear_fecha(
            item.get('fecha_vencimiento')
        )

        if error:
            return jsonify({
                'error': f'Artículo {indice}: {error}'
            }), 400

        clave = (
            detalle_catalogo.id,
            fecha.isoformat() if fecha else None,
        )

        if clave in agrupados:
            agrupados[clave]['cantidad'] += cantidad
        else:
            agrupados[clave] = {
                'plan_item_detalle_id': detalle_catalogo.id,
                'cantidad': cantidad,
                'fecha_vencimiento': fecha,
            }

    try:

        lotes = []

        for item in agrupados.values():

            lote = VehiculoPlanItemDetalle(
                vehiculo_plan_item_id=vpi.id,
                plan_item_detalle_id=item['plan_item_detalle_id'],
                cantidad=item['cantidad'],
                fecha_vencimiento=item['fecha_vencimiento'],
            )

            db.session.add(lote)
            lotes.append(lote)

        db.session.commit()

        for lote in lotes:
            _evaluar_alerta(lote.id)

        return jsonify(_serializar_inventario(vpi)), 201

    except SQLAlchemyError:

        db.session.rollback()

        return jsonify({
            'error': 'No fue posible registrar el inventario.'
        }), 500


# =========================================================
# POST /vehiculos/<id>/plan/<vpi_id>/articulos/<detalle_id>/lotes
# Agregar un nuevo lote del mismo artículo
# =========================================================

@inventario_vehiculo_bp.route(
    '/vehiculos/<int:vehiculo_id>/plan/<int:vpi_id>'
    '/articulos/<int:detalle_id>/lotes',
    methods=['POST']
)
def agregar_lote(vehiculo_id, vpi_id, detalle_id):

    vpi, error = _obtener_vpi(vehiculo_id, vpi_id)

    if error:
        return error

    detalle_catalogo, error = _obtener_detalle_catalogo(
        vpi,
        detalle_id
    )

    if error:
        return error

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            'error': 'El cuerpo de la solicitud debe ser un JSON válido.'
        }), 400

    cantidad = _parsear_cantidad(data.get('cantidad'))

    if cantidad is None:
        return jsonify({
            'error': 'La cantidad debe ser un entero mayor que cero.'
        }), 400

    fecha, error = _parsear_fecha(data.get('fecha_vencimiento'))

    if error:
        return jsonify({'error': error}), 400

    try:

        lote = VehiculoPlanItemDetalle(
            vehiculo_plan_item_id=vpi.id,
            plan_item_detalle_id=detalle_catalogo.id,
            cantidad=cantidad,
            fecha_vencimiento=fecha,
        )

        db.session.add(lote)
        db.session.commit()

        _evaluar_alerta(lote.id)

        return jsonify(lote.to_dict()), 201

    except SQLAlchemyError:

        db.session.rollback()

        return jsonify({
            'error': 'No fue posible registrar el lote.'
        }), 500


# =========================================================
# PUT /vehiculos/<id>/plan/<vpi_id>/lotes/<lote_id>
# =========================================================

@inventario_vehiculo_bp.route(
    '/vehiculos/<int:vehiculo_id>/plan/<int:vpi_id>'
    '/lotes/<int:lote_id>',
    methods=['PUT']
)
def actualizar_lote(vehiculo_id, vpi_id, lote_id):

    vpi, error = _obtener_vpi(vehiculo_id, vpi_id)

    if error:
        return error

    lote = VehiculoPlanItemDetalle.query.filter_by(
        id=lote_id,
        vehiculo_plan_item_id=vpi.id,
    ).first()

    if not lote:
        return jsonify({
            'error': 'El lote no existe o no pertenece a este vehículo.'
        }), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            'error': 'El cuerpo de la solicitud debe ser un JSON válido.'
        }), 400

    if 'cantidad' not in data and 'fecha_vencimiento' not in data:
        return jsonify({
            'error': 'Debes enviar cantidad o fecha_vencimiento.'
        }), 400

    if 'cantidad' in data:

        cantidad = _parsear_cantidad(data.get('cantidad'))

        if cantidad is None:
            return jsonify({
                'error': (
                    'La cantidad debe ser un entero mayor que cero.'
                )
            }), 400

        lote.cantidad = cantidad

    if 'fecha_vencimiento' in data:

        fecha, error = _parsear_fecha(
            data.get('fecha_vencimiento')
        )

        if error:
            return jsonify({'error': error}), 400

        lote.fecha_vencimiento = fecha

    try:

        db.session.commit()

        _evaluar_alerta(lote.id)

        return jsonify(lote.to_dict())

    except SQLAlchemyError:

        db.session.rollback()

        return jsonify({
            'error': 'No fue posible actualizar el lote.'
        }), 500


# =========================================================
# DELETE /vehiculos/<id>/plan/<vpi_id>/lotes/<lote_id>
# =========================================================

@inventario_vehiculo_bp.route(
    '/vehiculos/<int:vehiculo_id>/plan/<int:vpi_id>'
    '/lotes/<int:lote_id>',
    methods=['DELETE']
)
def eliminar_lote(vehiculo_id, vpi_id, lote_id):

    vpi, error = _obtener_vpi(vehiculo_id, vpi_id)

    if error:
        return error

    lote = VehiculoPlanItemDetalle.query.filter_by(
        id=lote_id,
        vehiculo_plan_item_id=vpi.id,
    ).first()

    if not lote:
        return jsonify({
            'error': 'El lote no existe o no pertenece a este vehículo.'
        }), 404

    try:

        resolver_alertas_articulo(lote.id)

        db.session.delete(lote)
        db.session.commit()

        return jsonify({
            'message': 'Lote eliminado correctamente.'
        })

    except SQLAlchemyError:

        db.session.rollback()

        return jsonify({
            'error': 'No fue posible eliminar el lote.'
        }), 500
