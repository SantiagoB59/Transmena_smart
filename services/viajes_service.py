from extensions import db

def finalizar_viaje(viaje):

    km = (viaje.km_llegada or 0) - (viaje.km_salida or 0)
    viaje.km_recorrido = km
    viaje.estado = "FINALIZADO"

    # 🚛 CABEZOTE
    vehiculo = viaje.vehiculo
    vehiculo.km_actual = (vehiculo.km_actual or 0) + km

    # 🚚 REMOLQUE
    if viaje.remolque:
        remolque = viaje.remolque
        remolque.km_actual = (remolque.km_actual or 0) + km

    db.session.commit()

    return viaje