# Revisión local: Brotañam, personajes, carnívora enemiga y barras

Esta revisión NO ESTÁ PUBLICADA. El jardín remoto sigue siendo la base 72d0a0e sin estas novedades. No hay autorización actual para subir esta revisión al ensayo ni a Corazón.

## Brotañam defensora (propuesta concreta)

5 rayitos, ocupa la única plaza de planta en una entrada. No reemplaza otra planta ni ataca sola. Elegí esa entrada y tocá Dar un mordisco con Brotañam. Cuenta una acción igual que semillas o insecticida, da rayito de día/tarde y hace avanzar al resto de los adversarios.

- Si el objetivo tiene MÁS de la mitad de su vida máxima, el mordisco lo deja exactamente en esa mitad.
- Si está en la mitad o menos, lo frena y suma uno a su meta. No hay azar de agarrarlo bien/mal, daño variable oculto ni falla aleatoria.
- Un bicho de 3 queda con 1,5 puntos; el lector recibe número con coma. No es la mitad de la vida ACTUAL cada vez.
- Mordisco no consume el refuerzo de Pepa, que es solo para semillas. No hay recarga en este piloto. Una entrada vacía o sin Brotañam no gasta acción ni da rayitos.
- Costo y activación son diseño de esta prueba local, no cifras dictadas por Rocky.

Salpicadura suave abstracta, de círculos como pintura: verde al zombi, celeste al esqueleto, violeta al bicho y dorada a Boca de Brote. Estática, sin destellos, gore o nuevas temporizaciones. Se muestra después del mordisco hasta la próxima acción o cambio de momento. El texto anuncia color/efecto; ninguna información depende del color. Brotañam no tiene barra de salud propia porque las plantas en este piloto no reciben daño. El helecho tiene su uso único como antes.

Barras de salud visuales para todos los adversarios y el jardín. HTML meter con etiqueta, valor numérico y valor accesible. Vidas del jardín expresadas como 2 vidas y media, etc. Los dibujos tienen barra pequeña y número de apoyo; toda la información también está en la lista legible.

Pruebas adicionales de mordisco con los cuatro tipos: máximo a mitad, mitad a frenado, costo, no consumir refuerzo y sin planta no avanzar. Prueba real de interfaz de plantar, morder y frenar al segundo mordisco. Axe limpio con barras y efecto. Capturas de mordisco/barras y selección inspeccionadas. La captura prepara un adversario y reserva de puntos localmente para mostrar el efecto, no es una partida remota ni evidencia de balance real.

## Documentación previa (lo anterior prevalece)

# Revisión local: tres personajes para el jardín

NO PUBLICADA. Base anterior en ensayo: 72d0a0e. Esta carpeta agrega personajes solo localmente. El nombre Jardín Chiflado sigue provisional y Rocky confirmó un personaje fijo para toda la partida. Ningún cambio en ensayo/Corazón.

## Carnívora enemiga nueva

Boca de Brote es un cuarto adversario original, con SVG y cuatro tonos propios. Tiene 4 puntos de vida y aparece una vez por cada momento (además de las metas de los tres tipos anteriores). Si llega, quita media vida. Las fracciones se anuncian como 2 vidas y media o media vida. No come a otros adversarios: esa parte de la idea sigue sin aclarar. Los escudos funcionan también contra ella y no cuenta como frenada si llegó. El piloto pasa a 18 adversarios si ninguno llega; sin ayudas requiere 26 defensas válidas. Ni esa cantidad ni el balance se presentan como cifras dictadas por Rocky.

## Cambios

Elección explícita ANTES de empezar. No hay personaje preseleccionado en la interfaz. Fijo durante los tres momentos; solo se cambia reiniciando toda la partida, con confirmación que avisa pérdida de progreso.

- Regadera Rita: seis rayitos iniciales, tres vidas.
- Caracol Tito: cuatro vidas iniciales, cuatro rayitos.
- Lata Pepa: tres vidas y cuatro rayitos; prepara con botón un +1 al próximo disparo de semillas, una vez por cada día/tarde/noche. No se apila ni acumula entre momentos. Insecticida y entrada vacía no lo consumen. Con malvón, semillas pasan de tres a cuatro. Prepararlo no mueve enemigos ni da rayitos.

Mismas plantas/armas para cualquiera, sin costo real o desbloqueos. Dibujos vectoriales propios para la selección. Estado de personaje y habilidad en texto y en Escuchar situación. Voz opcional/lector como antes, sin prueba física Samsung/TalkBack todavía.

Pruebas adicionales: 750 partidas completas (250 por personaje), además de los 1.000 juegos base actualizados con carnívora; Tito/Rita recursos correctos, Pepa una vez por momento, conservación con insecticida/entrada vacía, reinicio y combinación con malvón. Los quince tests base se conservan (inician sin habilidad de personaje como referencia del motor anterior). Prueba UI completa con Pepa y elección/reinicio con Tito y Rita, sin errores, Axe limpio incluyendo selección móvil y situación con media vida. Verificadas pérdida de media vida, reposición y derrota al perder la última media vida. Inspeccionada la selección real de 430 px. La narración de la prueba sigue sustituida, no se verificó audición física.

```
node test-engine.cjs
node test-characters.cjs
npm install
npx playwright install chromium
npm run test:browser
```

## Documentación de la base (las excepciones anteriores prevalecen)

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
