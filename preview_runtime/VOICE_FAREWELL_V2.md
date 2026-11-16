# Ensayo local 2: voz y despedidas

Estado: preparado localmente. No subido a GitHub ni desplegado. El enlace de ensayo existente sigue ejecutando 5822133 y aún NO tiene estas correcciones.

## Correcciones

- Se repuso AHORCADO_LETTER_NAMES, omitido al separar rehearsal_words.py. Su ausencia causaba un error del servidor al procesar palabras completas por voz, como gato. El texto escrito recorría otro camino y no exponía ese fallo.
- Reconocimiento con resultados intermedios: si el navegador termina sin resultado final, se conserva el último texto recibido. Una respuesta se manda una sola vez. No se prueban alternativas como jugadas adicionales ni se acepta una palabra distinta por parecido.
- Captura limitada a diez segundos, mensajes distintos para permiso y red, texto reconocido conservado en el campo para revisarlo. Sin reconocimiento del navegador, se informa la limitación en lugar de intentar transcribir sin una clave.
- Ahorcado, Bomba y Misterio tienen hasta quince segundos extra por temporizador para capturar y enviar voz. No es una pausa ilimitada; en Misterio, por ahora, el presupuesto es compartido por el caso porque el juego sigue siendo simultáneo. Se conserva la mecha normal de Bomba.
- Seis despedidas rotativas en servidor y respaldo local. Selector opcional Amiga / Amigo / Con mi nombre, sin género. Nunca se deduce género a partir del nombre; si no hay elección se usa el nombre o una despedida neutra.

## Verificación local

- Doce pruebas de regresión y cuatro nuevas pruebas pasan: gato con signos/artículo, despedidas, pausa acotada y reloj sin micrófono.
- Navegador con reconocimiento simulado: gato final se manda una vez; gato intermedio al finalizar no se pierde; error de red no manda jugada; se libera el micrófono.
- WebSocket real: gato llega al servidor como jugada y la conexión sigue abierta. Salida real recibe despedida femenina seleccionada.
- Tres juegos: sin errores JS, sin hallazgos axe ni desborde a 320/430/1024. Inicio con selector: axe sin hallazgos. Captura del selector inspeccionada.
- No es prueba física del reconocimiento de Samsung/TalkBack. Las pruebas simuladas verifican el manejo de resultados, no la precisión del servicio de voz.

## Ampliaciones investigadas, no implementadas

Ahorcado tiene 76 palabras únicas en cinco bandas de longitud. Se anuncia meta al nivel 6, que se alcanza tras cinco aciertos. No se generaron 100/200/300 niveles.
Misterio tiene ocho casos; selección al azar sin repetición, teorías simultáneas, puntaje de equipo existente. Ruleta específica, turnos alternados, rival bot y casos propuestos por el jugador requieren trabajo nuevo.
Rey de la colina es el pedido de supervivencia hasta quedar una persona y ganar corona. No confundir con Los Reyes. No se modificó Arena.

## Despliegue

A la espera de autorización de acceso nueva para subir solo estos cambios a la rama de ensayo. No usar el permiso temporal anterior, ya revocado. No publicar en Corazón.
