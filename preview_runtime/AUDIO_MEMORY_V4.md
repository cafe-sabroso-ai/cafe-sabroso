# Corrección local de memoria: pendiente de subir

El ensayo v3 f2e619b se reinició por memoria durante la prueba remota de seis personas. No está validado para ese grupo hasta desplegar y verificar esta corrección. Las pruebas remotas previas de dos jugadores y Ahorcado sí pasaron.

## Causa y mediciones

El servicio Free tiene 512 MiB. Reproduciendo seis conexiones en local, un arranque sin código precompilado mantuvo unos 256 MiB de servidor y varios conversores de audio simultáneos sumaron 316 MiB: pico total medido de 572 MiB. Se midió RSS del servidor más todos sus procesos hijos, no un cálculo teórico. Esto reproduce una presión superior al límite y es coherente con el reinicio de Render; no es la cifra histórica exacta del contenedor remoto.

Con un único conversor activo y las demás correcciones, la misma prueba fría bajó a 359 MiB. Al precompilar los módulos durante la construcción de la imagen para evitar el gran pico y retención del compilador al arrancar, la misma prueba quedó en 196 MiB, con unos 93 MiB de servidor y 103 de conversor. La medición local usa Python 3.10 y el despliegue Python 3.12, por lo que no reemplaza medir la nueva imagen en Render.

## Cambios

- Una sola conversión de audio a la vez en todo el ensayo, también para las notas del chat. Un hilo por conversor y filtro.
- Lecturas idénticas preparadas simultáneamente comparten el trabajo de síntesis y conversión. La entrega sigue siendo individual; no se transmiten respuestas, pistas ni datos privados a otros jugadores.
- Cancelar o agotar el tiempo mata y recoge el conversor, sin dejarlo consumiendo memoria en segundo plano.
- El audio retenido tiene techo de 32 MiB. En mucha actividad se eliminan los más viejos: no se promete conservar indefinidamente sus enlaces de reproducción.
- La imagen compila los módulos durante la construcción. No cambia ninguna regla del juego ni requiere plan pago.

## Verificación local

39 pruebas Python pasan, incluidas cuatro nuevas: seis lecturas idénticas se preparan una vez, textos distintos nunca generan conversores simultáneos, una cancelación mata y recoge el proceso, y el audio retenido no supera el techo.

Seis navegadores locales reciben el mismo primer caso, los seis lo resuelven con crédito independiente y uno avanza de nuevo sin arrastrar a los otros ni mostrarles su caso siguiente. Las dos campañas conservan privacidad, reconexión y acceso por botones. axe sin hallazgos a 320/430/1024 y sin desborde ni errores JavaScript. La prueba física con el lector de pantalla de Rocky sigue pendiente.

No subido todavía. Hace falta permiso nuevo para push al ensayo y revocar enseguida, luego redeploy y otra prueba remota de seis. No es permiso para publicar en producción.
