# La colina del rey: versión local con rescate

Lista para revisión local. No publicada. No cambia Corazón ni el ensayo actual. Crear el prototipo no autoriza un despliegue.

## Arranque y pruebas

Python 3.11 o posterior:

```
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8898
python -m unittest -v
```

Abrir http://127.0.0.1:8898/ en dos o más navegadores/contextos. Este enlace es local, no funciona en el teléfono ni fuera de esa máquina. Para probarlo desde teléfonos hace falta el ensayo y su autorización de subida.

26 pruebas automáticas. También incluye test-browser.cjs, que usa Playwright y @axe-core/playwright (dependencias de Node para la batería de navegador). Se ejecutó con seis contextos locales, capturas y pruebas de voz real; no con un teléfono físico. El arnés inicia y detiene su propio servidor.

## Reglas aprobadas, implementadas

- Sala para 2 a 12 personas. Tres vidas por persona. Tres opciones por pregunta, orden igual para todos. Respuestas privadas hasta cerrar la ronda.
- Todas las personas activas responden una vez. Un error resta una vida. Un acierto suma un acierto. No hay reloj.
- Al perder la tercera vida, un rescate por persona en toda la partida: pregunta nueva y privada. Si acierta, vuelve con una vida y suma un acierto; si falla, queda como espectador. Al perder después esa vida no hay otro rescate.
- Quienes entran al rescate simultáneamente reciben la misma pregunta y opciones. Cada respuesta y su explicación son privadas. No se repite esa pregunta en lotes posteriores. La corona espera todos los rescates, incluso si una persona ya volvió con una vida.
- Corona virtual a la última persona con vidas. Si todas quedan fuera, no hay corona. No hay apuestas, pagos ni récords permanentes.
- El anfitrión abre cada ronda. Si alguien se desconecta, puede volver con el mismo navegador y conserva asiento, vidas, respuesta y rescate pendiente. La desconexión no quita vidas y no hace avanzar la ronda. No se permite incorporarse a mitad de partida.

## Banco

90 preguntas originales, 30 por categoría: Palabras y lenguaje; Lógica y números; Mundo y cultura. Tres tramos de complejidad creciente, no dificultad calibrada con jugadores. De cada categoría y tramo hay ocho preguntas de ronda y dos reservadas para rescate: 72 normales, 18 de reserva. El orden mezcla las tres categorías dentro de cada tramo y no vuelve a niveles anteriores en las rondas. Las opciones se mezclan al abrir una pregunta, igual para todos los destinatarios.

Se prioriza para el rescate una pregunta del tramo actual o de uno anterior si se agotó el actual; si ya no quedan de esos tramos, usa el siguiente disponible. En un lote todos reciben el mismo tramo. La reserva alcanza para doce rescates individuales incluso si cada jugador los necesita en una ronda distinta.

Operaciones y conteos se verifican por programa; hechos de cultura/ciencia/geografía tienen fuentes verificadas, detalladas en SOURCES.md. No hay contenido de obras, marcas, letras de canciones ni música de terceros.

Si se completan las 72 rondas y quedan varias personas, se cierra sin corona, informando el agotamiento del banco. No inventa un desempate ni repite preguntas. Se puede crear otra sala. Es una limitación explícita de esta versión, no eliminación automática.

## Accesibilidad y voz

Interfaz semántica para lector, foco en cada pregunta nueva y en rescate, regiones de estado, botones táctiles, lectura de pregunta/opciones y de vidas/estado bajo pedido. Voz natural en español con alternativa a voz del navegador y lector si falla. No se reproduce automáticamente ni hay micrófono permanente. El botón Detener voz cancela lectura y reconocimiento.

Reconocimiento del navegador bajo pedido, en español. Reconoce opción uno/dos/tres y enfoca el botón de esa opción para confirmar, sin enviar por sí solo. Si no entiende o falla el permiso, no pierde vidas ni manda una respuesta. El navegador procesa el audio con su servicio; no se recibe audio del micrófono en este servidor.

La lectura natural envía al sintetizador solo el texto que solicita el jugador: pregunta/opciones de su propio asiento o su estado. Caché de ocho audios, límite 600 KB cada uno, una síntesis a la vez, timeout 25 segundos. El endpoint valida la clave del asiento, no acepta texto arbitrario. No guarda grabaciones de micrófono ni archivos de audio en disco.

## Límites operativos

Las salas viven en memoria y se pierden al reiniciar. Clave aleatoria por asiento en sessionStorage, nunca en estados de otros asientos. Una pestaña nueva no hereda el asiento; recargar la misma sí. Máximo cien salas y doce personas por sala; las salas sin conexiones se limpian al crear otra después de seis horas desde su creación. Una instancia/un proceso: no está preparada para varios workers.

Si el anfitrión se desconecta, debe volver para continuar. No hay expulsión, reemplazo ni transferencia automática de anfitrión. La ronda espera a todos, también si alguien se aleja. Si comparten habitación, usen auriculares y no digan las respuestas en voz alta.

## Ruta prevista para el ensayo, no aplicada

El servidor es independiente y también fue probado montado bajo /colina/. Se puede copiar como paquete colina/ dentro del ensayo y montar su aplicación en esa ruta, sin cambiar las reglas o bancos de Ahorcado, Bomba o Misterio. No está montado en el ensayo publicado aún. Corazón de producción sigue aparte y requiere su autorización posterior.

## Evidencia local

26 pruebas: reglas, privacidad, doble respuesta, reconexión, rescate único, corona postergada, doce rescates simultáneos, agotamiento y 72 rondas completas; además 200 partidas simuladas de seis personas y transporte HTTP/WebSocket.

Seis navegadores: misma pregunta, espera hasta responder todos, aciertos independientes, reconexión, cinco rescates, uno exitoso vuelve con una vida, cuatro fallidos, siguiente error sin segundo rescate, cinco espectadores y una corona. Batería pasó en servidor raíz y montado bajo /colina/.

Axe sin hallazgos en inicio, ronda y rescate a 320/430/1024 píxeles. Sin desborde horizontal ni errores JS. Síntesis natural real producida, archivo MP3 inspeccionado por transcripción. Reconocimiento probado con fixture para verificar confirmación y no envío automático, NO prueba de micrófono físico. Capturas inspeccionadas directamente.

Pendiente antes de decir que está probado en el teléfono: Samsung/TalkBack y reconocimiento real, más despliegue y prueba remota después del permiso de subida. No se afirma memoria remota medida.
