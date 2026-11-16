# Ensayo local: memoria, casilleros y ruleta

16 de noviembre de 2026. Construido localmente; sin nuevo commit, permiso GitHub ni despliegue. El ensayo remoto sigue en f2e619b y se reinició por memoria con seis personas. Esta copia necesita aprobación de subida y verificación remota antes de recomendarla a ese grupo.

## Ahorcado

- Sin pista de significado en pantalla, lectura ni estado enviado. Se empieza con todos los casilleros vacíos. No se revela una letra gratis ni se agrega una ruleta temática.
- Cada letra acertada anuncia todos sus casilleros. Las vecinas se juntan en grupos conocidos: G en 1, A en 2, formaste GA. No se revela GATO por inferencia; se dice al resolver o perder.
- Casilleros individuales con nombres para el lector y un botón Escuchar mi palabra formada. Ese botón prepara una lectura natural privada y pausa el reloj de ese turno hasta la confirmación de lectura o el botón de inicio.
- Muñeco sin soga ni escenas de daño: cabeza, cuerpo, brazos y piernas. Cada fallo anuncia lo añadido y muestra las partes. Se mantiene la regla previa de tres intentos para palabras cortas y cuatro para largas: por eso algunos errores agregan un grupo de partes, no un nuevo intento por cada brazo. Se avisa el último intento. No se aumentaron los intentos a seis sin pedirlo.
- Al perder, se muestra el muñeco completo como último desafío terminado y se revela la palabra con una de seis frases suaves de humor. No se dice te ahorcamos ni se agregó una risa grabada o burla personal. Ejemplo: El muñeco pidió recreo. Esta palabra ganó la ronda, no la guerra del café.
- Se conservan cien palabras únicas, cuenta separada de desafíos terminados y aciertos, palabra e intentos entre turnos y final sin reinicio automático.
- No se cambió aún el reparto por longitud en bloques de veinte ni se inventó un umbral nuevo del nivel diez. La progresión de dificultad/rareza queda para una decisión explícita y revisión del banco.

## Misterio

Se conservan exactamente los cincuenta casos de v3, las pistas privadas, la carrera individual y la secuencia común. No se incorporó el banco alternativo de deducciones ni una progresión nueva. La propuesta de endurecerlo quedó fuera de esta copia después de la aclaración de Rocky.

La ruleta sí tiene sección visible, rueda decorativa, cinco apartados escritos y botón Girar mi ruleta. El resultado muestra y anuncia apartado y número de caso. Cada persona gira a su ritmo y la secuencia sigue siendo igual para todos. Antes del giro no se envía su caso siguiente; no puede iniciar el reloj ni pedir su pista. Repetir o reconectar después del giro conserva el resultado y no vuelve a sortear. No depende de colores ni animación para entenderse.

## Memoria

Incluye v4: un conversor activo, hilos limitados, preparación compartida de textos idénticos, cancelación que mata y recoge el proceso, audio retenido hasta 32 MiB y módulos precompilados al construir la imagen.

La prueba local final de seis navegadores pasó con pico medido de 196 MiB para el servidor más todos sus hijos. Los seis resolvieron el mismo caso con crédito independiente y uno avanzó de nuevo sin filtrar su caso siguiente. No es una cifra de Render: local usa Python 3.10 y Render 3.12. Hace falta repetir la prueba remota después de aprobar y desplegar.

## Verificación

46 pruebas Python pasan. Incluyen no filtrar caso antes de girar, giro duplicado, pistas bloqueadas hasta girar, reconexión, privacidad, cien palabras sin repetir, memoria, casilleros, grupos GA, lectura privada, partes del muñeco y cierre sin frase amenazante.

Dos navegadores mantienen avance independiente y privacidad con el giro nuevo. Prueba detallada con palabra GATO: G y A aparecen en sus casilleros sin revelar T/O; la lectura repite los huecos; dos fallos agregan cabeza/cuerpo/brazos; el tercero muestra el final amable y revela GATO. Ambas campañas pasan axe a 320/430/1024 sin desborde ni errores JavaScript. Se inspeccionaron capturas de ruleta, casilleros y muñeco. La prueba física con el Samsung y lector de Rocky sigue pendiente.

No se tocó producción, main, Telegram, Arena, Leyenda ni Adivina el sonido. El Dockerfile modificado es solo el del ensayo.
