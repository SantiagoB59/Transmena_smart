from flask import Blueprint, request, jsonify
from models import Viaje, Vehiculo
from extensions import db
from services.viajes_service import finalizar_viaje

viajes_bp = Blueprint('viajes', __name__)


@viajes_bp.route('/', methods=['GET'])
def listar_viajes():
    viajes = Viaje.query.filter_by(activo=True).all()
    return jsonify([v.to_dict() for v in viajes])


@viajes_bp.route('/', methods=['POST'])
def crear_viaje():

    data = request.json

    vehiculo = Vehiculo.query.get(data['vehiculo_id'])

    if not vehiculo:
        return jsonify({"error": "Vehículo no encontrado"}), 404

    viaje = Viaje(
        vehiculo_id=vehiculo.id,
        remolque_id=data.get('remolque_id'),

        conductor=data.get('conductor'),
        cc_conductor=data.get('cc_conductor'),

        origen=data.get('origen'),
        destino=data.get('destino'),

        cliente=data.get('cliente'),
        tipo_carga=data.get('tipo_carga'),
        descripcion_carga=data.get('descripcion_carga'),
        peso=data.get('peso'),

        # 🚫 NO km manual
        km_inicio=vehiculo.km_actual,

        estado='PROGRAMADO'
    )

    db.session.add(viaje)
    db.session.commit()

    return jsonify(viaje.to_dict()), 201


# =========================
# OBTENER VIAJE
# =========================
@viajes_bp.route('/<int:id>', methods=['GET'])
def obtener_viaje(id):

    viaje = Viaje.query.get_or_404(id)
    return jsonify(viaje.to_dict())


# =========================
# ACTUALIZAR VIAJE
# =========================
@viajes_bp.route('/<int:id>', methods=['PUT'])
def actualizar_viaje(id):

    viaje = Viaje.query.get_or_404(id)
    data = request.json

    viaje.vehiculo_id = data.get('vehiculo_id', viaje.vehiculo_id)
    viaje.remolque_id = data.get('remolque_id', viaje.remolque_id)

    viaje.conductor = data.get('conductor', viaje.conductor)
    viaje.cc_conductor = data.get('cc_conductor', viaje.cc_conductor)

    viaje.origen = data.get('origen', viaje.origen)
    viaje.destino = data.get('destino', viaje.destino)

    viaje.cliente = data.get('cliente', viaje.cliente)
    viaje.tipo_carga = data.get('tipo_carga', viaje.tipo_carga)
    viaje.descripcion_carga = data.get('descripcion_carga', viaje.descripcion_carga)
    viaje.peso = data.get('peso', viaje.peso)

    db.session.commit()

    return jsonify(viaje.to_dict())

# =========================
# ELIMINAR VIAJE
# =========================
@viajes_bp.route('/<int:id>', methods=['DELETE'])
def eliminar_viaje(id):

    viaje = Viaje.query.get_or_404(id)

    # 🔥 Eliminación lógica
    viaje.activo = False

    db.session.commit()

    return jsonify({
        "message": "Viaje desactivado correctamente"
    })
# =========================
# INICIAR VIAJE
# =========================
@viajes_bp.route('/<int:id>/iniciar', methods=['POST'])
def iniciar(id):

    viaje = Viaje.query.get_or_404(id)

    vehiculo = Vehiculo.query.get(viaje.vehiculo_id)

    viaje.estado = "EN_RUTA"

    # opcional: registrar km inicio real si quieres control
    viaje.km_inicio = vehiculo.km_actual

    db.session.commit()

    return jsonify(viaje.to_dict())
# =========================
# FINALIZAR VIAJE (IMPORTANTE)
# =========================
@viajes_bp.route('/<int:id>/finalizar', methods=['POST'])
def finalizar(id):

    viaje = Viaje.query.get_or_404(id)
    data = request.json

    viaje.km_fin = data.get("km_fin")
    viaje.observaciones = data.get("observaciones")
    viaje.estado = "FINALIZADO"

    viaje.km_recorrido = viaje.km_fin - viaje.km_inicio

    db.session.commit()

    return jsonify(viaje.to_dict())