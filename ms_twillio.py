# app.py
import json
import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, request, jsonify
import requests

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

# Importamos la configuración de DB
from database import engine, SessionLocal
# Importamos los modelos
from models import Base, Message, Number

load_dotenv()
env = os.environ

app = Flask(__name__)

# Si fuera necesario, crear las tablas (opcional en producción)
Base.metadata.create_all(bind=engine)


@app.route('/', methods=['GET'])
def hello():
    return "hello"

# Endpoint Webhook que solo registra el mensaje recibido en la tabla `message`
@app.route('/webhook', methods=['POST'])
def webhook():
    from_number = request.form.get('From')
    message_body = request.form.get('Body')
    twilio_phone_number = request.form.get('To')
    print(f"📩 Nuevo mensaje recibido de {from_number}: {message_body}")

    session = SessionLocal()
    try:
        # Se asume que el mensaje fue enviado al número de Twilio y se utiliza para obtener el number_id.
        number_obj = session.query(Number).filter(Number.number == twilio_phone_number).first()
        if not number_obj:
            print(f"No se encontró el número {twilio_phone_number} en la tabla number.")
            return "Número receptor no registrado en el sistema", 400

        new_message = Message(
            to=twilio_phone_number,
            from_=from_number,
            direction="incoming",
            message=message_body,
            number_id=number_obj.id
        )
        session.add(new_message)
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        print("Error al insertar mensaje:", e)
        return "Error interno", 500
    finally:
        session.close()

    # Se elimina el envío de respuesta automática
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
                text = message_info.get("text", "")
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
                    message=text,
                    mid=mid,
                    reply_to=reply_to,
                    number_id=number_obj.id
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
def verify_instagram_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == "e9c2ec1c256e455e434702446c0d2cdf35839a5e":
        return challenge, 200
    else:
        return "Verificación fallida", 403


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5530, debug=True)
