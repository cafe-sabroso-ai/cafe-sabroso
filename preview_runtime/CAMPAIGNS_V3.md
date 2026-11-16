# Ensayo local v3: revisión pendiente

Versión del 16 de noviembre de 2026. Todavía no está subida al ensayo remoto. No es una publicación de producción ni aprobación del contenido.

## Misterio

- Banco nuevo de cincuenta casos breves originales, diez por cada uno de cinco apartados. Son ejercicios de lógica y observación cotidiana. No son cincuenta relatos policiales ni una escala de dificultad medida.
- Secuencia común sorteada y equilibrada: cada bloque de cinco contiene un caso de cada apartado. Cada jugador conserva su propio caso y avanza al resolverlo, sin esperar al resto. El primero en resolver cincuenta gana. No se activa rival máquina ni equipos en esta carrera.
- Solo nombres y cantidad resuelta son comunes. Cada dispositivo recibe su caso, lectura, teoría, resultado y pistas; los espectadores solo reciben el marcador. El marcador puede escucharse con un botón, además del aviso escrito accesible cuando cambia el progreso.
- La privacidad significa que el juego no transmite automáticamente casos, teorías ni pistas al otro jugador. No evita que alguien los comparta por el chat general, en persona o copiando una dirección de audio. No se ofrece cifrado por jugador ni acceso autenticado al audio. Si juegan en el mismo ambiente, hacen falta auriculares.
- Reloj personal de ciento cincuenta segundos por intento. Espera la confirmación de lectura y puede iniciarse con un botón. Repetir, pedir pista o escuchar el marcador pausa ese reloj, no el del otro jugador. El reconocimiento de voz tiene una gracia personal limitada. Un fallo de síntesis privada no bloquea los relojes de los demás.
- Una equivalencia desconocida no pierde intentos ni gana un acierto automáticamente. Se aceptan las formas explícitas revisadas, sin búsqueda por fragmentos. Solo los errores de control revisados descuentan intentos. Al agotar intentos o tiempo se reintenta el mismo caso; nunca se regala el acierto ni se revela la respuesta.
- Al recargar y volver a entrar desde la misma pestaña se conserva el asiento, caso y progreso, y se vuelve a leer antes de responder. Las salas siguen siendo temporales: no hay persistencia tras reinicio del servicio y la sala puede cerrarse si todos se desconectan durante treinta segundos. No se promete guardar una campaña de un día a otro.

## Ahorcado

- Cien palabras únicas por persona, mezcladas dentro de cinco tramos por longitud. No se repiten las palabras al fallar y no se llaman cien dificultades.
- Palabra, letras e intentos se conservan cuando pasa el turno. Acertar suma un acierto. Agotar intentos termina ese desafío sin sumar. Se cuentan por separado desafíos terminados y aciertos.
- Termina después de cien desafíos por persona, sin reiniciarse automáticamente. No exige cien aciertos para terminar y no se presenta como una carrera nueva de equipos.
- El reloj empieza después de la lectura o con Empezar mi turno. Las posiciones de letras largas se leen con números, sin limitarse a diez posiciones.

## Verificación local

- Treinta y cinco pruebas Python pasan: banco, equivalencias, rechazos, orden equilibrado, privacidad, progreso independiente, reconexión, reloj tras lectura, reintento tras agotarse, fallo de voz privada, un solo ganador simultáneo, recorrido completo de cincuenta casos y recorrido completo de cien palabras sin repetir.
- Dos navegadores reales conectados por WebSocket: una persona pasa al caso siguiente mientras otra sigue en el anterior. La otra puede resolver su propio caso sin perder el crédito. Se inspeccionaron los paquetes para comprobar que el caso siguiente y la pista no llegaran al otro jugador. Recarga real conserva caso y progreso.
- axe sin hallazgos a 320, 430 y 1024 píxeles en ambas campañas, sin desborde horizontal ni errores JavaScript. Capturas inspeccionadas. Esto no reemplaza una prueba física con el lector de pantalla y el Samsung de Rocky.
- La prueba de voz rota fuerza un fallo controlado de síntesis. Su excepción registrada en el test es esperada; no es un fallo del servidor de la prueba de navegadores.

## Alcance

No se cambió la producción, Telegram, Arena, Leyenda ni Adivina el sonido. La Bomba mantiene sus tiempos. El ensayo conserva las mejoras v2 de voz, despedidas y chat. Los documentos de revisión incluyen soluciones: contienen spoilers.

Próximo paso: Rocky revisa tono, ambigüedades, formas naturales de responder y largo de los recorridos. Subir al ensayo remoto requiere permiso nuevo. Publicar en Corazón requiere otra aprobación clara después de que se informe que está terminado. Este paquete no da ninguno de esos permisos.
