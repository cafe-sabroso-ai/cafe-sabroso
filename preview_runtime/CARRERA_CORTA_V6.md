# Carrera corta de Misterio, v6 local

No subido. Base de ensayo 402a9c3; producción sigue con v5 4f6e1f2. Solo se cambian longitud y textos de Misterio. No cambia Ahorcado, Bomba, bancos, Telegram, Arena, Leyenda ni sonido.

## Reglas

- Selector nativo etiquetado antes de crear la sala: 10, 25 o 50 casos. Predeterminado 50, como antes.
- La distancia elegida se fija para toda la sala al crearla, no por jugador. Se conserva al reconectar y no cambia durante una carrera.
- Mismo orden sorteado para todos, avance individual. Prefijos equilibrados: dos, cinco o diez casos de cada apartado. Ninguno se repite en la carrera.
- Gana el primero en completar exactamente la meta. No sigue al caso 11 si la meta era 10, ni declara ganador antes de tiempo. Solo una corona de ganador aunque dos respuestas finales lleguen juntas.
- Pistas, teorías y casos siguientes siguen privados. Se anuncia la distancia en voz y en los marcadores.
- Resultados identificados como misterio-10, misterio-25 o misterio-50. No hay récords persistentes entre partidas ni un historial que mezcle distancias; no se agregó persistencia ficticia.
- La colina del rey no está implementada en esta copia. Requiere cerrar su mecánica, separada de esta carrera y sin confundirla con Arena/Los Reyes.

## Pruebas

50 pruebas Python pasan: las 46 previas y cuatro nuevas de distancias válidas/inválidas, orden equilibrado y objetivo fijo, final completo de 10/25/50, y ganador único concurrente.

Navegador local: selector real crea carrera de 10, se completan los diez casos reales; dos navegadores comparten carrera de 25, uno avanza sin arrastrar al otro; reconexión conserva distancia/progreso. Inicio y partida sin hallazgos axe a 320/430/1024, sin desborde ni errores JS. Capturas inspeccionadas, incluido final que dice carrera terminada, no invita a un caso inexistente.

Seis navegadores locales, con síntesis natural real, pasan en carrera de 10: seis créditos independientes y avance de uno sin filtrar el siguiente. Pico RSS servidor+hijos de esta prueba: 195,99 MiB. No es memoria remota ni prueba para 50 personas.

La batería rápida visual usa un archivo de audio de prueba para evitar latencias: local_visual.py es solo un arnés local y NO debe incluirse en despliegues. La prueba de seis usa rehearsal_app real, sin ese reemplazo. La prueba física del Samsung/lector permanece pendiente.

## Publicación

Hace falta un sí nuevo al permiso temporal de GitHub para subir a la rama y servicio de ensayo, revocarlo enseguida y verificar remotamente. Nada de esto autoriza publicar v6 en Corazón. No se creó grant, commit, push ni despliegue v6.
