import json
import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, request, session, jsonify
import requests
from sqlalchemy import text, func
from sqlalchemy.exc import SQLAlchemyError

# Importamos la configuración de DB
from database import engine, SessionLocal
# Importamos los modelos, incluyendo el nuevo modelo Tasa
from models import Base, Message, Number, Tasa

load_dotenv()
env = os.environ

app = Flask(__name__)

# Crear las tablas (opcional en producción)
Base.metadata.create_all(bind=engine)


@app.route('/', methods=['GET'])
def hello():
    session = SessionLocal()
    try:
        # Verificar a qué base de datos estamos conectados
        current_db = session.execute(text("SELECT DATABASE()")).scalar()
        print("Base de datos conectada:", current_db)
        
        # Consultar todos los registros de la tabla number
        numbers = session.query(Number).all()
        result = []
        for number in numbers:
            result.append({
                "id": number.id,
                "number_type": number.number_type,
                "number": number.number,
                "account_sid": number.account_sid,
                "auth_token": number.auth_token,
                "agente_id": number.agente_id,
                "status": number.status,
                "created_at": number.created_at.isoformat() if number.created_at else None,
                "updated_at": number.updated_at.isoformat() if number.updated_at else None,
                "agent_status": number.agent_status
            })
        return jsonify({
            "database": current_db,
            "numbers": result
        }), 200
    except SQLAlchemyError as e:
        print("Error al obtener los números:", e)
        return jsonify({"error": "Error al obtener los números"}), 500
    finally:
        session.close()


# Endpoint Webhook que solo registra el mensaje recibido en la tabla `message`
@app.route('/webhook', methods=['POST'])
def webhook():
    from_number = request.form.get('From')
    message_body = request.form.get('Body')
    twilio_phone_number = request.form.get('To')
    mid = request.form.get("SmsMessageSid")
    reply_to = request.form.get("OriginalRepliedMessageSid")

    session = SessionLocal()
    try:
        # Se asume que el mensaje fue enviado al número de Twilio y se utiliza para obtener el number_id.
        formatted_twilio_number = twilio_phone_number.split('+')
        number_obj = session.query(Number).filter(Number.number == formatted_twilio_number[1]).first()
        print(number_obj, formatted_twilio_number[1])
        if not number_obj:
            print(f"No se encontró el número {twilio_phone_number} en la tabla number.")
            return "Número receptor no registrado en el sistema", 400

        new_message = Message(
            to=twilio_phone_number,
            from_=from_number,
            direction="incoming",
            message=message_body,
            number_id=number_obj.id,
            mid=mid,
            reply_to=reply_to,
            object=str(request.form)
        )
        session.add(new_message)
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        print("Error al insertar mensaje:", e)
        return "Error interno", 500
    finally:
        session.close()

    return "Mensaje recibido", 200


# Endpoint de validación que registra el evento recibido (por ejemplo, de Instagram)
@app.route('/validation', methods=['POST'])
def handle_instagram_event():
    data = request.json
    print(f"📩 [Instagram] Evento recibido: {data}")

    session = SessionLocal()
    try:
        for entry in data.get("entry", []):
            for messaging in entry.get("messaging", []):
                sender_id = messaging.get("sender", {}).get("id")
                recipient_id = messaging.get("recipient", {}).get("id")
                message_info = messaging.get("message", {})

                # Se extrae el texto del mensaje, mid y reply_to (si existe)
                text_msg = message_info.get("text", "")
                mid = message_info.get("mid")
                reply_to = None
                if "reply_to" in message_info and message_info["reply_to"]:
                    reply_to = message_info["reply_to"].get("mid")

                # Se obtiene el número receptor usando el recipient_id
                number_obj = session.query(Number).filter(Number.number == recipient_id).first()
                if not number_obj:
                    print(f"No se encontró el número {recipient_id} en la tabla number.")
                    continue

                new_message = Message(
                    to=recipient_id,
                    from_=sender_id,
                    direction="incoming",
                    message=text_msg,
                    mid=mid,
                    reply_to=reply_to,
                    number_id=number_obj.id,
                    object=str(data)
                )
                session.add(new_message)
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        print("Error al insertar evento en DB:", e)
        return jsonify({"status": "Error al insertar en la base de datos"}), 500
    finally:
        session.close()

    return jsonify({"status": "Evento recibido"}), 200


@app.route('/validation', methods=['GET'])
def validation():
    mode = request.args.get("hub.mode")
    verify_token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and verify_token and challenge:
        if mode == "subscribe" and verify_token == "e9c2ec1c256e455e434702446c0d2cdf35839a5e":
            return challenge, 200
        else:
            return "Verificación fallida", 403


## Endpoint actualizado para recibir JSON
@app.route('/update-tasa', methods=['POST'])
def update_tasa():
    # Obtener datos JSON del cuerpo de la solicitud
    data = request.get_json()
    
    if not data or 'tasa' not in data:
        return jsonify({"error": "Falta el parámetro 'tasa' en el JSON"}), 400

    try:
        tasa_value = float(data['tasa'])
    except (ValueError, TypeError):
        return jsonify({"error": "Valor de 'tasa' inválido"}), 400

    session = SessionLocal()
    try:
        # Se busca si ya existe un registro en la tabla 'tasa'
        tasa_obj = session.query(Tasa).first()
        if tasa_obj:
            tasa_obj.tasa = tasa_value
        else:
            tasa_obj = Tasa(tasa=tasa_value)
            session.add(tasa_obj)

        session.commit()
        return jsonify({"status": "Tasa actualizada", "tasa": str(tasa_value)}), 200
    except SQLAlchemyError as e:
        session.rollback()
        print("Error al actualizar la tasa:", e)
        return jsonify({"error": "Error interno al actualizar la tasa"}), 500
    finally:
        session.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5530, debug=True)
