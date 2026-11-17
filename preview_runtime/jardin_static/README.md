# Jardín Chiflado (nombre provisional)

Prototipo local separado, hecho el 17 de noviembre de 2026. No está en el ensayo ni en Corazón. No modifica la Bomba ni ningún juego publicado. Falta elegir el nombre y probarlo con Rocky. Sin grant de publicación.

## Primera partida

- Un jugador, un jardín ilustrado en 2D. Día, tarde y noche: tres oleadas con pausa explícita entre ellas.
- Metas: día 1 zombi, 1 esqueleto, 1 bicho; tarde 2 de cada; noche 2 de cada. Quince adversarios en total si ninguno llega. Una partida ganada sin plantas requiere 20 defensas válidas, más elegir entradas y pasar de oleada. No hay duración en minutos prometida: depende de lectura y decisiones.
- Tres vidas de jardín para toda la partida. Cada adversario que llega quita una vida. Aparece un reemplazo del mismo tipo para que la meta siga siendo alcanzable. Con cero vidas termina; volver a empezar exige confirmación.
- Cuatro entradas: frente, izquierda, atrás, techo de la casita del jardín. Los adversarios avanzan SOLO al confirmar una defensa contra una entrada ocupada. Apuntar, leer, escuchar, poner plantas y pausar no consume pasos. Una entrada vacía no consume pasos ni da puntos.
- Máximo tres adversarios en camino. Cada uno nace a seis acciones de distancia; por entrada se apunta al más cercano. Se muestran y anuncian tipo, entrada, vida y distancia en acciones. No depende de estéreo ni de reflejos.
- Zombi de maceta: 4 de vida. Esqueleto de cucharitas: 2. Bicho pompón: 3. Son personajes genéricos de fantasía dibujados desde cero con SVG, no personajes de otra obra.
- Semillas hacen 2 de daño. Insecticida VIRTUAL hace 3 a bichos y 1 a los demás. Sin munición limitada ni recargas pagas. Sin gore, apuestas o castigos reales.

## Plantas y recurso solar

Implementación propuesta para revisar, no números dictados por Rocky:

- Rayitos son puntos ficticios, NO dinero. Arrancás con 4, tope 12. El sol suma 1 por defensa válida de día y tarde. De noche se usa lo guardado, sin rayitos nuevos. No se puede juntar más por escuchar o tocar una entrada vacía.
- Malvón campana: 3 rayitos, hace que las semillas bajen 3 de vida en esa entrada (no dispara solo).
- Helecho paraguas: 4 rayitos, frena UNA llegada sin perder vida y se retira. Ese adversario se reemplaza y no suma como frenado para la meta.
- Una planta por entrada. No se pueden reemplazar plantas ocupadas en este piloto. Siguen de una oleada a otra. Plantar no mueve adversarios, solo descuenta rayitos. No hay compras reales ni cuentas.

## Acceso

Todo se puede jugar con botones HTML y lector. Tab, Enter/Espacio, o exploración táctil. Botones de misión, situación, pausa, detener audio y volver a empezar. Resumen por acción en región de estado, sin notificaciones cronometradas. Atajos de una tecla solo si se activan: 1-4 entradas, D semillas, I insecticida, E situación, P pausa. No funcionan al editar un campo ni al confirmar reinicio.

La narración propia está apagada al abrir para no superponerse con el lector. Al activarla usa SpeechSynthesis del dispositivo en español; intenta es-AR y después otra voz española. No se incluye un servicio de voz natural propio. Si no hay voz disponible, sigue todo en texto para el lector. La reproducción real de la voz no fue verificada en Samsung/TalkBack. No hay micrófono ni comandos hablados en este piloto.

Sonidos propios sintetizados por Web Audio con osciladores: zombi grave de dos tonos; esqueleto tres golpes agudos; bicho tres tonos ascendentes. Botón de muestra sin empezar partida. Opcionales y detenibles. No se cargan grabaciones ni bibliotecas externas. El cambio de noche no esconde información.

## Ejecutar localmente

Python 3, sin paquetes:

```
python -m http.server 8903 --bind 127.0.0.1
```

Abrí http://127.0.0.1:8903/. Ese es un enlace local, no entregable remoto para el teléfono de Rocky. También son archivos estáticos sin backend. No hay servidor de juego, conexión con cuentas, cookies, persistencia ni guardado. Recargar reinicia. Salir de la pestaña pausa automáticamente; volver requiere Seguir.

## Pruebas

Node 18+ sin paquetes para el motor:

```
node test-engine.cjs
```

Quince pruebas, incluidos 1.000 recorridos completos reproducibles, todos ganables sin perder vida usando la defensa adecuada; recursos, plantas, no duplicación de puntos, pausa, daño, entradas vacías, pérdida, reinicio y noche sin sol nuevo.

Prueba de navegador opcional (instala herramientas de desarrollo, no son dependencias del juego):

```
npm install
npx playwright install chromium
npm run test:browser
```

La prueba inicia su propio servidor local y lo cierra al terminar. Guarda capturas y muestra de sonidos en test-output (o OUTPUT_DIR). Usa estados forzados internos SOLO en la prueba para verificar escudo y derrota. El juego no tiene endpoint de trampas.

Comprobado en Chromium: partida completa por interfaz; colocar planta y descontar puntos; escudo de una llegada; derrota; confirmación/cancelación de reinicio; pausa; atajos opcionales; ninguna acción por esperar o escuchar. Axe sin hallazgos a 320, 430 y 1024 en entrada y estados activos, pausa, fin de oleada, victoria y derrota. Sin desborde ni errores JavaScript. Inspeccionadas capturas de día, tarde, noche, final y móvil. Sonidos capturados desde el grafo Web Audio real. La prueba de voz comprueba idioma y texto enviado, sustituyendo el sintetizador: NO prueba audición real ni lector físico.

## Cuidado de memoria y límites

Juego estático de unos 28 KB de HTML/CSS/JS, sin descargas de audio ni librerías en ejecución. Solo un estado pequeño en memoria, tres adversarios máximo, hasta cuatro plantas, colas finitas y sin historial creciente, intervalos de reloj, bucle de animación o caché de voz. Cada aviso detiene los osciladores previos; se desconectan al acabar. Cierra audio al salir. El motor y el render solo trabajan cuando se realiza una acción. Esto es diseño y medición del peso de archivos, NO un pico de memoria medido en el teléfono.

No incluye multijugador, armas reales, tiempo real, otros lugares, brujas ni plantas enemigas. Los dibujos, nombres de personajes y secuencias de tonos son originales de este prototipo; no se usaron imágenes, música, sonidos ni personajes de juegos comerciales. El nombre del juego sigue provisional.
