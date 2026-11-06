
from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError

from models import db, PlanItem, PlanItemDetalle

plan_items_bp = Blueprint('plan_items', __name__)

TIPOS_MANTENIMIENTO = {
    'PREVENTIVO',
    'INSPECCION',
    'CORRECTIVO'
}

TIPOS_CONTROL = {
    'KM',
    'DIAS',
    'HORAS',
    'OCASIONAL'
}


# =========================
# VALIDAR ARTICULOS
# =========================
def validar_articulos(data):
    """
    Valida nombre y cantidad mínima del catálogo.

    La fecha de vencimiento NO pertenece al catálogo: se administra
    por vehículo en vehiculo_plan_item_detalles.
    """

    if not isinstance(data, list):
        return None, 'El campo articulos debe ser una lista.'

    articulos_validados = []

    for indice, articulo in enumerate(data, start=1):
        if not isinstance(articulo, dict):
            return None, (
                f'El artículo {indice} debe ser un objeto válido.'
            )

        # Validar id opcional (para conservar el inventario por vehículo
        # cuando se edita el catálogo).
        detalle_id = articulo.get('id')

        if detalle_id is not None:
            if (
                isinstance(detalle_id, bool)
                or not isinstance(detalle_id, int)
                or detalle_id < 1
            ):
                return None, (
                    f'El id del artículo {indice} no es válido.'
                )

        # Validar nombre
        nombre = articulo.get('nombre')

        if not isinstance(nombre, str):
            return None, (
                f'El nombre del artículo {indice} es obligatorio.'
            )

        nombre = nombre.strip()

        if not nombre:
            return None, (
                f'El nombre del artículo {indice} es obligatorio.'
            )

        if len(nombre) > 150:
            return None, (
                f'El nombre del artículo {indice} '
                'no puede superar 150 caracteres.'
            )

        # Validar cantidad mínima
        cantidad = articulo.get('cantidad')

        if (
            isinstance(cantidad, bool)
            or not isinstance(cantidad, int)
            or cantidad < 1
        ):
            return None, (
                f'La cantidad del artículo {indice} '
                'debe ser un entero mayor que cero.'
            )

        articulos_validados.append({
            'id': detalle_id,
            'nombre': nombre,
            'cantidad': cantidad
        })

    return articulos_validados, None


# =========================
# VALIDAR JSON
# =========================
def obtener_json():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return None, (
            jsonify({
                'error': 'El cuerpo de la solicitud debe ser un JSON válido.'
            }),
            400
        )

    return data, None


# =========================
# VALIDAR CAMPOS CATALOGO
# =========================
def validar_campos_catalogo(data, crear=False):
    """
    Valida los campos principales del catálogo.
    Conserva los campos opcionales existentes.
    """

    if crear or 'sistema' in data:
        sistema = data.get('sistema')

        if not isinstance(sistema, str) or not sistema.strip():
            return 'El sistema es obligatorio.'

        if len(sistema.strip()) > 100:
            return 'El sistema no puede superar 100 caracteres.'

    if crear or 'nombre' in data:
        nombre = data.get('nombre')

        if not isinstance(nombre, str) or not nombre.strip():
            return 'El nombre del mantenimiento es obligatorio.'

        if len(nombre.strip()) > 150:
            return 'El nombre no puede superar 150 caracteres.'

    if 'tipo_mantenimiento' in data:
        if data['tipo_mantenimiento'] not in TIPOS_MANTENIMIENTO:
            return 'El tipo de mantenimiento no es válido.'

    if 'tipo_control' in data:
        if data['tipo_control'] not in TIPOS_CONTROL:
            return 'El tipo de control no es válido.'

    for campo in ('frecuencia_valor', 'alerta_valor'):
        if campo not in data or data[campo] is None:
            continue

        valor = data[campo]

        if (
            isinstance(valor, bool)
            or not isinstance(valor, int)
            or valor < 0
        ):
            return f'{campo} debe ser un entero mayor o igual a cero.'

    if 'obligatorio' in data:
        if not isinstance(data['obligatorio'], bool):
            return 'El campo obligatorio debe ser verdadero o falso.'

    if 'descripcion' in data:
        descripcion = data['descripcion']

        if descripcion is not None and not isinstance(descripcion, str):
            return 'La descripción debe ser un texto o null.'

    return None


# =========================
# LISTAR
# GET /plan-items
# =========================
@plan_items_bp.route('/plan-items', methods=['GET'])
def listar_plan_items():

    items = PlanItem.query.order_by(
        PlanItem.id.desc()
    ).all()

    return jsonify([
        item.to_dict()
        for item in items
    ])


# =========================
# OBTENER UNO
# GET /plan-items/<id>
# =========================
@plan_items_bp.route('/plan-items/<int:id>', methods=['GET'])
def obtener_plan_item(id):

    item = PlanItem.query.get_or_404(id)

    return jsonify(item.to_dict())


# =========================
# CREAR
# POST /plan-items
# =========================
@plan_items_bp.route('/plan-items', methods=['POST'])
def crear_plan_item():

    data, error_response = obtener_json()

    if error_response:
        return error_response

    error = validar_campos_catalogo(data, crear=True)

    if error:
        return jsonify({'error': error}), 400

    articulos_data = data.get('articulos', [])

    articulos_validados, error = validar_articulos(articulos_data)

    if error:
        return jsonify({'error': error}), 400

    item = PlanItem(
        sistema=data['sistema'].strip(),
        nombre=data['nombre'].strip(),
        descripcion=data.get('descripcion'),
        tipo_mantenimiento=data.get(
            'tipo_mantenimiento',
            'PREVENTIVO'
        ),
        tipo_control=data.get(
            'tipo_control',
            'KM'
        ),
        frecuencia_valor=data.get('frecuencia_valor'),
        alerta_valor=data.get('alerta_valor'),
        obligatorio=data.get('obligatorio', True),
        activo=True
    )

    try:
        db.session.add(item)
        db.session.flush()

        for articulo_data in articulos_validados:
            item.articulos.append(
                PlanItemDetalle(
                    nombre=articulo_data['nombre'],
                    cantidad=articulo_data['cantidad']
                )
            )

        db.session.commit()

        return jsonify(item.to_dict()), 201

    except SQLAlchemyError:
        db.session.rollback()

        return jsonify({
            'error': (
                'No fue posible guardar el mantenimiento '
                'y sus artículos.'
            )
        }), 500


# =========================
# ACTUALIZAR
# PUT /plan-items/<id>
# =========================
@plan_items_bp.route('/plan-items/<int:id>', methods=['PUT'])
def actualizar_plan_item(id):

    item = PlanItem.query.get_or_404(id)

    data, error_response = obtener_json()

    if error_response:
        return error_response

    error = validar_campos_catalogo(data)

    if error:
        return jsonify({'error': error}), 400

    articulos_validados = None

    # Solo reemplazar los artículos si la propiedad fue enviada.
    if 'articulos' in data:
        articulos_validados, error = validar_articulos(
            data['articulos']
        )

        if error:
            return jsonify({'error': error}), 400

    if 'sistema' in data:
        item.sistema = data['sistema'].strip()

    if 'nombre' in data:
        item.nombre = data['nombre'].strip()

    if 'descripcion' in data:
        item.descripcion = data['descripcion']

    if 'tipo_mantenimiento' in data:
        item.tipo_mantenimiento = data['tipo_mantenimiento']

    if 'tipo_control' in data:
        item.tipo_control = data['tipo_control']

    if 'frecuencia_valor' in data:
        item.frecuencia_valor = data['frecuencia_valor']

    if 'alerta_valor' in data:
        item.alerta_valor = data['alerta_valor']

    if 'obligatorio' in data:
        item.obligatorio = data['obligatorio']

    try:
        if articulos_validados is not None:
            existentes = list(item.articulos)
            existentes_por_id = {
                detalle.id: detalle
                for detalle in existentes
            }

            ids_enviados = [
                articulo_data.get('id')
                for articulo_data in articulos_validados
                if articulo_data.get('id')
            ]

            if len(ids_enviados) != len(set(ids_enviados)):
                return jsonify({
                    'error': 'No se puede repetir el mismo artículo.'
                }), 400

            for detalle_id in ids_enviados:
                if detalle_id not in existentes_por_id:
                    return jsonify({
                        'error': (
                            'Uno de los artículos enviados no pertenece '
                            'a este mantenimiento.'
                        )
                    }), 400

            usados = set()

            for articulo_data in articulos_validados:

                detalle = existentes_por_id.get(
                    articulo_data.get('id')
                )

                # Compatibilidad con clientes que aún no envían id:
                # conservar el detalle por nombre para no perder el
                # inventario de los vehículos.
                if not detalle:
                    nombre_normalizado = (
                        articulo_data['nombre'].casefold()
                    )

                    for existente in existentes:
                        if (
                            existente.id in usados
                            or existente.nombre is None
                        ):
                            continue

                        if (
                            existente.nombre.strip().casefold()
                            == nombre_normalizado
                        ):
                            detalle = existente
                            break

                if detalle:
                    detalle.nombre = articulo_data['nombre']
                    detalle.cantidad = articulo_data['cantidad']
                    usados.add(detalle.id)
                    continue

                item.articulos.append(
                    PlanItemDetalle(
                        nombre=articulo_data['nombre'],
                        cantidad=articulo_data['cantidad']
                    )
                )

            # Solo se eliminan los artículos retirados explícitamente
            # del catálogo.
            for existente in existentes:
                if existente.id not in usados:
                    item.articulos.remove(existente)

        db.session.commit()

        return jsonify(item.to_dict())

    except SQLAlchemyError:
        db.session.rollback()

        return jsonify({
            'error': (
                'No fue posible actualizar el mantenimiento '
                'y sus artículos.'
            )
        }), 500


# =========================
# ELIMINAR (SOFT DELETE)
# DELETE /plan-items/<id>
# =========================
@plan_items_bp.route('/plan-items/<int:id>', methods=['DELETE'])
def eliminar_plan_item(id):

    item = PlanItem.query.get_or_404(id)

    item.activo = False

    try:
        db.session.commit()

        return jsonify({
            'msg': 'Plan eliminado'
        })

    except SQLAlchemyError:
        db.session.rollback()

        return jsonify({
            'error': 'No fue posible desactivar el mantenimiento.'
        }), 500
