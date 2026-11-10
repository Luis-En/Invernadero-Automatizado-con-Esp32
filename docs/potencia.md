# Etapa de potencia 110 VAC (P0)

> No energizar la bomba ni los ventiladores hasta completar esta lista. El
> prototipo actual usa relés de 10 A en la maqueta; **no son aptos para la
> bomba de 0.5 HP**.

## Bomba (110 VAC, 0.5 HP, 35 L/min)

| Elemento | Especificación mínima | Nota |
|----------|-----------------------|------|
| Contactor | 20 A, bobina 110 VAC (o 24 VDC con fuente) | Soporta el inrush de 12–18 A del motor |
| Breaker | 15 A curva C | Dedicado al circuito de la bomba |
| Cable | 12 AWG, 50 m | Caída de tensión y calentamiento |
| Protección | Varistor 275 V (MOV) + fusible | Transitorios del motor y red |
| Puesta a tierra | Barra única, conductor verde/amarillo | Gabinete y motor |
| SSR alternativo | SSR-40DA + disipador | Solo si se acepta conmutación por cruce de cero |

El GPIO del ESP32 **no** debe alimentar la bobina: usa un optoacoplador o un
módulo de relé con transistor y diodo flyback. El relé de 10 A de la maqueta
queda solo para pruebas con lámpara, nunca con el motor.

## Ventiladores y humidificadores

- Ventiladores 110 VAC: contactor/SSR de 10–20 A por canal, breaker compartido
  de 15 A si la suma lo permite.
- Humidificadores 24 VDC 800 mA: MOSFET de canal N con diodo flyback y fuente
  de 24 V / 3 A; no usar el regulador del ESP32.
- Fuente 5 V / 3 A separada para el ESP32; tierra común solo en un punto.

## Verificación antes de conectar

1. Medir continuidad y aislamiento del cableado con el breaker abierto.
2. Probar cada canal con una lámpara incandescente (no la bomba).
3. Verificar que `allOff()` deja 0 V en la salida y que el arranque del ESP32
   no da un pulso (pull-down de 10 kΩ en cada GPIO de relé).
4. Medir el consumo de la bomba en arranque y régimen; ajustar breaker.
5. Comprobar que el MOV y la tierra están instalados antes de energizar.

El firmware ya arranca con los pines en OFF antes de `Serial.begin()` y un
watchdog fuerza `allOff()` si el `loop()` se detiene, pero eso no sustituye la
protección eléctrica.

## Checklist de instalación física

- [ ] Contactor 20 A (o SSR-40DA con disipador) instalado para la bomba.
- [ ] Breaker 15 A curva C dedicado al circuito de la bomba.
- [ ] Cable 12 AWG, 50 m, con tierra y sin empalmes dentro del gabinete.
- [ ] Varistor 275 V + fusible en la entrada de 110 VAC.
- [ ] Pull-down de 10 kΩ en cada GPIO que excita un relé/opto.
- [ ] Bobina del contactor alimentada por fuente/opto, nunca directo del ESP32.
- [ ] Fuente 24 VDC 3 A para humidificadores y 5 VDC 3 A para el ESP32.
- [ ] Tierra única: gabinete, motor, fuente y ESP32 al mismo punto.
- [ ] Prueba con lámpara incandescente en cada canal antes de conectar la bomba.
- [ ] Medición de inrush de la bomba y ajuste del breaker.
- [ ] Verificación de que el arranque del ESP32 no produce un pulso en los relés.
- [ ] Rotulación del tablero y procedimiento de corte de emergencia.

Este checklist **no se puede completar por software**; requiere instalación y
medición en campo por una persona competente.
