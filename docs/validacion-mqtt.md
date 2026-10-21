# Validación de la entrega MQTT

- Pasaron las 5 pruebas aisladas del transporte, incluyendo ON/OFF, topics/QoS, ACK de identidad/estado incorrecto, mensajes retenidos, timeout, rechazo, MQTT deshabilitado y broker inaccesible.
- Se verificó la sintaxis Python de la API y las pruebas.
- Se verificó la sintaxis de Dashboard.jsx y api.js con el parser Babel.
- Se incluyeron pruebas HTTP para permisos, validación, bloqueo de bomba y errores de entrega.

Pendiente en un entorno con dependencias/hardware:

- Ejecutar la suite pytest HTTP completa: este entorno no tiene FastAPI/Paho instalados y la instalación de dependencias no estuvo disponible.
- Ejecutar el build Vite completo.
- Compilar con PlatformIO y ejecutar las pruebas C++: PlatformIO y ArduinoJson no están instalados aquí.
- Probar conexión Wi-Fi/Mosquitto, ACK y salidas físicas con el ESP32 real.

La guía de puesta en marcha está en docs/mqtt.md.
