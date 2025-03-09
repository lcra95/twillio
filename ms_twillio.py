import os

from dotenv import load_dotenv
from flask import Flask, request, jsonify
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import requests
import mysql.connector
from datetime import datetime, timedelta

load_dotenv()

env = os.environ

app = Flask(__name__)

# Conexión a la base de datos MySQL
db = mysql.connector.connect(
    host=env.get('DB_HOST'),
    user=env.get('DB_USER'),
    password=env.get('DB_PASSWORD'),
    database=env.get('DB_NAME'),
    port=env.get('DB_PORT')
)
cursor = db.cursor(dictionary=True)

# Obtener credenciales de Twilio desde la base de datos
cursor.execute("SELECT * FROM twilio_credentials LIMIT 1")
credentials = cursor.fetchone()
account_sid = credentials['account_sid']
auth_token = credentials['auth_token']
twilio_phone_number = credentials['phone_number']

client = Client(account_sid, auth_token)
@app.route('/webhook', methods=['GET'])
def hello():
    return "hello"


# Endpoint Webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    from_number = request.form.get('From')
    message_body = request.form.get('Body')

    print(f"📩 Nuevo mensaje recibido de {from_number}: {message_body}")

    # Registrar mensaje recibido en la base de datos
    cursor.execute("""
        INSERT INTO messages (phone_number, message_body, direction)
        VALUES (%s, %s, 'incoming')
    """, (from_number, message_body))
    db.commit()

    # Enviar el mensaje al endpoint externo
    endpoint_url = "http://localhost:8000/agents/4/ask"
    payload = {"question": message_body}

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "insomnia/10.3.1"
    }

    try:
        response = requests.post(endpoint_url, json=payload, headers=headers)
        if response.status_code == 200:
            response_data = response.json()
            respuesta_final = response_data.get('answer', 'No se recibió una respuesta válida del servicio.')
        else:
            respuesta_final = "❌ Error al consultar el servicio externo."
    except Exception as e:
        respuesta_final = f"❌ Error de conexión: {str(e)}"

    # Registrar mensaje de salida en la base de datos
    cursor.execute("""
        INSERT INTO messages (phone_number, message_body, direction)
        VALUES (%s, %s, 'outgoing')
    """, (from_number, respuesta_final))
    db.commit()

    # Enviar la respuesta al usuario por WhatsApp
    twilio_response = MessagingResponse()
    twilio_response.message(f"🤖 Respuesta del asistente: {respuesta_final}")

    return str(twilio_response)

# Nuevo endpoint que envía mensajes a los contactos recientes
@app.route('/send-messages', methods=['POST'])
def send_messages():
    now = datetime.now()
    ultimas_24_horas = now - timedelta(hours=24)

    # Obtener contactos recientes desde la tabla de mensajes
    cursor.execute("""
        SELECT DISTINCT phone_number 
        FROM messages 
        WHERE timestamp >= %s AND direction = 'incoming'
    """, (ultimas_24_horas,))
    contactos = cursor.fetchall()

    numeros_unicos = [contacto['phone_number'] for contacto in contactos]

    if not numeros_unicos:
        return jsonify({"status": "No hay contactos recientes para enviar mensajes."})

    # Mensaje a enviar
    mensaje = """
    🌟 ¡Gracias por contactarnos! 🌟
    Te recordamos que estamos aquí para ayudarte. Si tienes alguna duda, solo responde este mensaje. 😊
    """

    for numero in numeros_unicos:
        try:
            client.messages.create(
                body=mensaje,
                from_=f'whatsapp:{twilio_phone_number}',
                to=numero
            )

            # Registrar mensaje de salida en la base de datos
            cursor.execute("""
                INSERT INTO messages (phone_number, message_body, direction)
                VALUES (%s, %s, 'outgoing')
            """, (numero, mensaje))
            db.commit()

            print(f"✅ Mensaje enviado a {numero}")
        except Exception as e:
            print(f"❌ Error al enviar mensaje a {numero}: {str(e)}")

    return jsonify({
        "status": "Mensajes enviados exitosamente",
        "total_enviados": len(numeros_unicos),
        "numeros": numeros_unicos
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5530, debug=True)
