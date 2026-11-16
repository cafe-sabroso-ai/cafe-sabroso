# Estado de esta copia: v3 local, no subida

Leé CAMPAIGNS_V3.md para las reglas y pruebas actuales. El texto de abajo conserva el historial inicial de v1; sus descripciones de bancos y final de Ahorcado/Misterio fueron reemplazadas en v3. El ensayo remoto v2 sigue separado y no contiene estos cambios.

# Corazón: ensayo aislado de mejoras

Base verificada: cafe-sabroso-ai/cafe-sabroso, main 2256c71ea510173526055fb79d866f0c68bc5399. La página reconstruida antes del parche coincide byte por byte con https://cafe-sabroso.onrender.com/amor-con-aroma-a-cafe al 16 de noviembre de 2026.

## Cambios del ensayo

- Ahorcado: cada persona conserva su palabra, letras correctas, letras incorrectas e intentos entre turnos. Si agota intentos, esa palabra se descarta. Al acertar, sube de nivel como antes. Esta regla es una variante de prueba, no una decisión definitiva del dueño.
- Bomba y Misterio: respuestas que terminan de evaluarse después de un cambio de ronda no afectan la siguiente; una misma resolución no puede duplicarse por concurrencia. En solo, perder una vida ya no declara ganador al único participante.
- Chat: globos entrantes y propios, sin HTML ejecutable en mensajes. Notas de voz reales: grabar hasta 60 segundos, escuchar, descartar o mandar explícitamente al destinatario seleccionado. Reproducción manual y repetible en el historial. El dictado a texto sigue separado.
- Se eliminó el aviso genérico incorrecto de cuatro vidas en estos tres juegos. Bomba y Misterio muestran sus tres vidas reales.
- Accesibilidad: nombres de botones coherentes con el texto, opciones encabezadas por su contenido, historial de chat semántico, sin desborde horizontal a 320/430/1024.
- El aviso del ensayo explica la variante de Ahorcado. La Bomba mantiene sus tiempos previos.

## Límites

- No hay cuenta de Telegram, claves, base de datos ni conexión a producción. Las salas y audios viven temporalmente en memoria del ensayo, no se sincronizan con la página principal.
- Solo se muestran Ahorcado, La Bomba y Resolver el misterio. El código de los otros juegos no se ha rediseñado ni presentado como terminado.
- Responder por voz depende del reconocimiento de voz del navegador. No hay transcripción de audio en servidor sin una clave. Grabar y recibir notas de voz reales del chat sí funciona sin claves.
- Bomba y Misterio usan sus bancos y evaluación local existentes, sin evaluación remota. No se promete entender cualquier sinónimo o teoría libre fuera de los bancos.
- La petición antigua de “tres minutos” para La Bomba no define si es por respuesta, mecha o ronda. Se dejó el tiempo existente, a confirmar antes de cambiarlo.
- No equivale a una prueba física en el Samsung A24 con el lector de pantalla de Rocky. Esa prueba sigue pendiente.
- Nada de este paquete autoriza una publicación en la página principal. Hace falta la aprobación nueva del dueño tras probar.

## Pruebas realizadas

- test_corazon_improvements.py: doce pruebas de lógica pasan.
- Dos navegadores separados: palabra/intentos del Ahorcado persisten al regresar el turno; texto privado solo al destinatario; grabación no enviada antes de confirmación; audio privado recibido como MP3 reproducible (200 audio/mpeg).
- Las tres pantallas de juego funcionan en solo. Error en Bomba y Misterio descuenta una vida.
- axe sin hallazgos en inicio y chat, y en las tres pantallas de juego a 320, 430 y 1024 píxeles. Sin errores de JavaScript ni desborde horizontal en esos tamaños.
- Capturas inspeccionadas: entrada, Ahorcado, Bomba, Misterio y chat.

## Despliegue de ensayo propuesto

Una rama separada corazon-mejoras-ensayo-nov16 y un servicio Render Free nuevo. Dockerfile de ensayo con Python, FFmpeg, FastAPI, Uvicorn, websockets y Edge TTS. Sin variables de entorno secretas. Nunca desplegar este Dockerfile en el servicio principal.

## Integración futura y rollback

Aplicar el parche acotado sobre el runtime completo validado de main, no reemplazar el proyecto principal por el ensayo. Conservar el hash de entrada de webapp.py y environment_ui.js. Retirar el aviso de ensayo, elegir regla definitiva y volver a verificar home, Arena, Leyenda, sonido y bot antes de cualquier aprobación de producción. Rollback actual de producción: 2256c71ea510173526055fb79d866f0c68bc5399.
