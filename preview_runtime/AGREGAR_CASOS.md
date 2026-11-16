# Cómo agregar casos después de esta revisión

El banco del ensayo está en misterio_original.json, separado de las reglas. Cada caso nuevo necesita:

- id único estable (m51, m52, etc.), categoría, título y enunciado original.
- Solución de revisión, lista accepted de equivalencias explícitas y dos pistas que no dependan de ver imágenes ni de oír sonidos.
- near para palabras cercanas, rejected para errores concretos revisados y review_status que indique quién lo revisó. difficulty es solo una etiqueta provisional, no dificultad medida.

No copiar historias, acertijos publicados ni contenido protegido. Probar la lectura en voz alta, descartar ambigüedades y aceptar distintas frases que expresen la misma solución. Negaciones, alternativas múltiples y respuestas no confirmadas no deben convertirse en aciertos por contener una palabra de la solución.

Esta versión está revisada para 50 casos con diez por cada una de cinco categorías. No basta con pegar el caso 51: mystery_race.order usa diez vueltas equilibradas, y algunos avisos, descripciones y pruebas dicen cincuenta. Para ampliar hay que actualizar juntos el generador de secuencia, los mensajes y las pruebas, sin omitir casos ni repetirlos. Una ampliación equilibrada puede sumar un caso por categoría; una cantidad desigual requiere una mezcla nueva explícita. No se debe cambiar silenciosamente el objetivo de una partida empezada.

Comprobar siempre: ids únicos, enunciados distintos, todas las equivalencias aceptadas, errores de control rechazados, longitud y cobertura completa de la secuencia, progreso privado, un solo ganador, lectura y reloj, y recorrido completo del banco sin repetir. Actualizar el documento de revisión con spoilers y hacer que Rocky revise el nuevo contenido. Subir al ensayo y publicar en producción conservan sus permisos separados.

## Cinco o seis jugadores

La carrera admite varias personas en paralelo. Todos empiezan con el mismo caso y el mismo orden, pero cada uno avanza por su cuenta. Cinco o seis pueden resolver simultáneamente el caso 1 sin competir por un único acierto: cada cual recibe crédito al acertar. Si uno pasa al caso 2 no se obliga a los demás a pasar ni esperar. Un modo distinto donde todos quedan siempre juntos y nadie avanza hasta resolver el caso compartido no está implementado; requeriría otra regla y aprobación. La sala permite hasta 50 personas en total, incluyendo espectadores; eso es un límite configurado, no una garantía de rendimiento de 50 voces simultáneas en el servicio gratuito.
