"""Amor con aroma a café: the shared web ruleta, v3.

A real-time multiplayer party room for Rocky and his friends: one opens a
room, shares the link, everyone plays in the browser. No Telegram, no login,
no ads. One tap to enter unlocks sound; from then on the server's voices (the
same catalog as the Telegram bot) narrate every event to ALL players at once.

v3 (Rocky, 2026-11-10): start screen (Jugar solo / Sala de juego 2-20),
joins announced by name, 60-second turn timer with spoken warnings, four
categories (Verdad o Reto, Trivia, Refranes, Países) with local
multiple-choice banks, points and a winner, auto-rematch with a rotating
starter, and in-room chat (text read aloud + recorded voice clips). Fully
screen-reader accessible: real labeled buttons, aria-live on every beat.
"""

import asyncio
import hashlib
import json
import logging
import random
import string
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response

log = logging.getLogger("telegram-voice-bot")

router = APIRouter()

# ---------------------------------------------------------------------------
# Verdad o Reto: curated, harmless, doable dares and questions. "No locuras."
# ---------------------------------------------------------------------------
RETOS = [
    "Imitá a un animal hasta que alguien adivine cuál es.",
    "Cantá el estribillo de una canción que te guste.",
    "Contá un chiste corto, aunque sea malo.",
    "Hablá con acento de otro país por dos turnos.",
    "Decí un trabalenguas tres veces seguidas.",
    "Describí tu comida favorita sin nombrarla; los demás adivinan.",
    "Hacé el brindis más exagerado que puedas por el grupo.",
    "Tarareá una canción conocida hasta que la adivinen.",
    "Decí 5 cosas que te pongan contento, sin parar.",
    "Hablá como locutor de radio por un minuto.",
    "Contá tu mejor anécdota de la escuela.",
    "Hacé una publicidad inventada del mate o del café.",
    "Decí el abecedario lo más rápido que puedas.",
    "Imitá a un personaje famoso; los demás adivinan quién es.",
    "Nombrá 10 frutas en 15 segundos.",
    "Contá qué harías con un millón de pesos, en 30 segundos.",
    "Hacé una rima con el nombre de cada jugador.",
    "Describí tu película favorita en tres frases, sin decir el título.",
    "Saludá a cada jugador con un apodo cariñoso inventado.",
    "Contá un recuerdo feliz de cuando eras chico.",
    "Hablá en verso durante un turno completo.",
    "Hacé el sonido de 3 animales; el grupo puntúa el mejor.",
    "Decí una palabra bonita para cada letra de tu nombre.",
    "Contá qué superpoder tendrías y por qué.",
    "Hacé una entrevista de 3 preguntas al jugador de tu derecha.",
    "Inventá el nombre y el lema de una banda con otro jugador.",
    "Describí el plan perfecto de un domingo, con detalle.",
    "Hablá como si fueras el clima del noticiero.",
    "Decí 3 cosas buenas del jugador que giró antes que vos.",
    "Cantá el feliz cumpleaños al que cumpla más cerca de hoy.",
]
VERDADES = [
    "¿Cuál es tu comida favorita de todos los tiempos?",
    "¿A qué edad diste tu primer beso, más o menos?",
    "¿Qué canción cantás cuando nadie te escucha?",
    "¿Cuál fue tu momento más vergonzoso que hoy te da risa?",
    "¿Qué es lo que más te gusta de este grupo?",
    "¿Qué harías si fueras invisible por un día?",
    "¿Cuál es tu recuerdo favorito del año pasado?",
    "¿Qué comida odiabas de chico y ahora te encanta?",
    "¿Quién fue tu primer amor platónico?",
    "¿Qué es lo más loco que hiciste por un amigo?",
    "¿Qué programa o serie ves a escondidas?",
    "¿Qué te da un poco de miedo pero querés intentar?",
    "¿Cuál es tu lugar feliz?",
    "¿Qué mentira chiquita dijiste esta semana?",
    "¿A quién del grupo llamarías a las 3 de la mañana?",
    "¿Qué es lo primero que harías si ganaras la lotería?",
    "¿Cuál fue el mejor regalo que te hicieron?",
    "¿Qué apodo tuviste y cómo lo ganaste?",
    "¿Qué es algo que todos aman y a vos no te convence?",
    "¿Cuál es tu talento secreto?",
    "¿Qué te gustaría que el grupo haga más seguido?",
    "¿Qué película podés ver mil veces?",
    "¿Qué es lo más amable que hicieron por vos?",
    "¿Qué te pone de buen humor al instante?",
    "¿Si pudieras cenar con cualquier persona, con quién?",
    "¿Qué costumbre tuya hace reír a los demás?",
    "¿Cuál es tu olor favorito?",
    "¿Qué edad te gustaría tener para siempre y por qué?",
    "¿Qué es lo más valiente que hiciste?",
    "¿Qué querías ser de grande cuando tenías 10 años?",
]

SEGMENTS = ["reto", "verdad"]  # the wheel alternates these
SEGMENT_LABELS = {"reto": "RETO", "verdad": "VERDAD"}
SEGMENT_COLORS = {"reto": "#e53935", "verdad": "#1e88e5"}

# ---------------------------------------------------------------------------
# Multiple-choice banks: (pregunta, [opciones...], índice correcto).
# Locales a propósito: sin LLM, sin costo, giro instantáneo.
# ---------------------------------------------------------------------------
TRIVIA_MC = [
    ("¿Cuál es el planeta más grande del sistema solar?", ["Júpiter", "Saturno", "Neptuno"], 0),
    ("¿En qué continente está Egipto?", ["África", "Asia", "Europa"], 0),
    ("¿Cuántos jugadores tiene un equipo de fútbol en la cancha?", ["Once", "Nueve", "Siete"], 0),
    ("¿Qué animal es conocido por cambiar de color?", ["El camaleón", "La iguana", "El sapo"], 0),
    ("¿Qué gas respiramos para vivir?", ["Oxígeno", "Carbono", "Hidrógeno"], 0),
    ("¿Cuál es el océano más grande del mundo?", ["El Pacífico", "El Atlántico", "El Índico"], 0),
    ("¿En qué país nació el tango?", ["Argentina", "Brasil", "España"], 0),
    ("¿Qué instrumento tiene teclas blancas y negras?", ["El piano", "El violín", "La trompeta"], 0),
    ("¿Cuántos colores tiene el arcoíris?", ["Siete", "Cinco", "Nueve"], 0),
    ("¿Qué planeta es conocido como el planeta rojo?", ["Marte", "Venus", "Mercurio"], 0),
    ("¿Qué ave no puede volar y vive en el hielo?", ["El pingüino", "La gaviota", "El cóndor"], 0),
    ("¿Cuál es el metal más liviano usado en aviones?", ["El aluminio", "El plomo", "El oro"], 0),
    ("¿Qué fruta es la estrella de la sidra?", ["La manzana", "La pera", "La uva"], 0),
    ("¿Cuánto es 7 por 8?", ["56", "48", "64"], 0),
    ("¿Qué órgano bombea la sangre?", ["El corazón", "El pulmón", "El hígado"], 0),
    ("¿En qué deporte se usa una raqueta y una pelotita amarilla?", ["Tenis", "Básquet", "Rugby"], 0),
    ("¿Qué país tiene forma de bota?", ["Italia", "Grecia", "Portugal"], 0),
    ("¿Cuál es el animal terrestre más rápido?", ["El guepardo", "El león", "El caballo"], 0),
    ("¿Qué se celebra el 25 de diciembre?", ["Navidad", "Año Nuevo", "Reyes"], 0),
    ("¿Qué ciencia estudia los dinosaurios?", ["La paleontología", "La botánica", "La química"], 0),
    ("¿Cuál es el río más largo de Sudamérica?", ["El Amazonas", "El Paraná", "El Orinoco"], 0),
    ("¿Qué astro nos da luz y calor todos los días?", ["El Sol", "La Luna", "Marte"], 0),
    ("¿Cuántas patas tiene una araña?", ["Ocho", "Seis", "Diez"], 0),
    ("¿Qué dulce se hace con leche y azúcar cocidas?", ["El dulce de leche", "El turrón", "El mazapán"], 0),
    ("¿Qué país ganó el Mundial de Fútbol 2022?", ["Argentina", "Francia", "Brasil"], 0),
    ("¿Qué aparato convierte el viento en electricidad?", ["El molino de viento", "La antena", "La turbina de vapor"], 0),
    ("¿Qué continente es el más poblado?", ["Asia", "África", "Europa"], 0),
    ("¿Qué bebida se hace con granos tostados y molidos?", ["El café", "El mate", "El té"], 0),
    ("¿Qué animal produce la miel?", ["La abeja", "La avispa", "La mariposa"], 0),
    ("¿Cuál es la montaña más alta del mundo?", ["El Everest", "El Aconcagua", "El Kilimanjaro"], 0),
]
REFRANES_MC = [
    ("¿Qué significa 'A caballo regalado no se le miran los dientes'?", ["A lo que te regalan, no le busques defectos", "Los caballos tienen buenos dientes", "No aceptes regalos de desconocidos"], 0),
    ("¿Qué significa 'Más vale pájaro en mano que cien volando'?", ["Mejor lo seguro, aunque sea poco", "Los pájaros son difíciles de cazar", "Hay que soltar lo que uno tiene"], 0),
    ("¿Qué significa 'Camarón que se duerme se lo lleva la corriente'?", ["El que no está atento, pierde", "Los camarones duermen mucho", "La corriente es peligrosa"], 0),
    ("¿Qué significa 'No hay mal que dure cien años'?", ["Todo lo malo termina algún día", "Los males duran muchísimo", "La gente vive cien años"], 0),
    ("¿Qué significa 'A falta de pan, buenas son tortas'?", ["Con lo que hay, uno se arregla", "Las tortas son mejores que el pan", "Hay que cocinar más tortas"], 0),
    ("¿Qué significa 'Perro que ladra no muerde'?", ["El que mucho amenaza, poco hace", "Los perros ladran de noche", "Hay que tenerle miedo a los perros"], 0),
    ("¿Qué significa 'Ojos que no ven, corazón que no siente'?", ["Lo que no sabés, no te duele", "Los ojos engañan siempre", "El corazón es frío"], 0),
    ("¿Qué significa 'Del dicho al hecho hay mucho trecho'?", ["Decir es más fácil que hacer", "Hay que caminar mucho", "Las palabras sobran"], 0),
    ("¿Qué significa 'Quien madruga, Dios lo ayuda'?", ["El esfuerzo temprano da frutos", "Dios se levanta temprano", "Dormir es malo"], 0),
    ("¿Qué significa 'Agua que no has de beber, déjala correr'?", ["No te metas en lo que no te incumbe", "Hay que tomar mucha agua", "El agua corre rápido"], 0),
    ("¿Qué significa 'En boca cerrada no entran moscas'?", ["A veces conviene callarse", "Las moscas molestan", "Hay que hablar despacio"], 0),
    ("¿Qué significa 'Cría cuervos y te sacarán los ojos'?", ["A veces te traiciona a quien ayudaste", "Los cuervos son malas mascotas", "Hay que cuidar los ojos"], 0),
    ("¿Qué significa 'A lo hecho, pecho'?", ["Hay que hacerse cargo de lo hecho", "Hay que pelear siempre", "Lo hecho no se puede nombrar"], 0),
    ("¿Qué significa 'Más sabe el diablo por viejo que por diablo'?", ["La experiencia vale más que la astucia", "El diablo es muy viejo", "Los viejos son diablos"], 0),
    ("¿Qué significa 'El que ríe último, ríe mejor'?", ["La victoria final es la que cuenta", "Reír es sano", "Hay que reírse despacio"], 0),
    ("¿Qué significa 'No por mucho madrugar amanece más temprano'?", ["Las cosas llevan su tiempo", "Hay que madrugar poco", "Amanece muy tarde"], 0),
    ("¿Qué significa 'Un clavo saca otro clavo'?", ["Lo nuevo ayuda a olvidar lo viejo", "Los clavos son útiles", "Hay que usar clavos grandes"], 0),
    ("¿Qué significa 'Piedra que rueda no cría moho'?", ["El que se mueve no se estanca", "Las piedras no tienen moho", "Rodar es peligroso"], 0),
    ("¿Qué significa 'Háblame del cuñado'?", ["No quiero hablar más de eso", "Mi cuñado es simpático", "Hablemos de familia"], 0),
    ("¿Qué significa 'Costó un ojo de la cara'?", ["Fue muy caro", "Se lastimó un ojo", "Fue gratis"], 0),
    ("¿Qué significa 'Estar en el horno'?", ["Estar en un problema", "Hace mucho calor", "Está cocinando"], 0),
    ("¿Qué significa 'No hay tu tía'?", ["No hay solución", "Tu tía no vino", "No hay problema"], 0),
    ("¿Qué significa 'Tirar los tejos'?", ["Coquetear con alguien", "Jugar a un deporte", "Tirar cosas viejas"], 0),
    ("¿Qué significa 'Ser pan comido'?", ["Ser muy fácil", "Ser rico de comer", "Ser poco trabajo"], 0),
    ("¿Qué significa 'Meter la pata'?", ["Equivocarse", "Caminar rápido", "Tropezar"], 0),
]
PAISES_MC = [
    ("¿Cuál es la capital de Argentina?", ["Buenos Aires", "Córdoba", "Rosario"], 0),
    ("¿Cuál es la capital de México?", ["Ciudad de México", "Guadalajara", "Monterrey"], 0),
    ("¿Cuál es la capital de Bolivia?", ["La Paz", "Sucre", "Santa Cruz"], 0),
    ("¿Cuál es la capital de Chile?", ["Santiago", "Valparaíso", "Concepción"], 0),
    ("¿Cuál es la capital de Colombia?", ["Bogotá", "Medellín", "Cali"], 0),
    ("¿Cuál es la capital de Perú?", ["Lima", "Cusco", "Arequipa"], 0),
    ("¿Cuál es la capital de Uruguay?", ["Montevideo", "Punta del Este", "Salto"], 0),
    ("¿Cuál es la capital de Paraguay?", ["Asunción", "Encarnación", "Ciudad del Este"], 0),
    ("¿Cuál es la capital de Brasil?", ["Brasilia", "Río de Janeiro", "San Pablo"], 0),
    ("¿Cuál es la capital de España?", ["Madrid", "Barcelona", "Sevilla"], 0),
    ("¿Cuál es la capital de Venezuela?", ["Caracas", "Maracaibo", "Valencia"], 0),
    ("¿Cuál es la capital de Ecuador?", ["Quito", "Guayaquil", "Cuenca"], 0),
    ("¿En qué continente está Japón?", ["Asia", "Oceanía", "Europa"], 0),
    ("¿En qué continente está Marruecos?", ["África", "Europa", "Asia"], 0),
    ("¿En qué continente está Australia?", ["Oceanía", "Asia", "África"], 0),
    ("¿Qué país es famoso por la Torre Eiffel?", ["Francia", "Italia", "Inglaterra"], 0),
    ("¿Qué país es famoso por el machu picchu?", ["Perú", "Bolivia", "Ecuador"], 0),
    ("¿Qué país es famoso por las pirámides de Giza?", ["Egipto", "México", "Sudán"], 0),
    ("¿Qué idioma se habla en Brasil?", ["Portugués", "Español", "Brasileño"], 0),
    ("¿Cuál es el país más grande de Sudamérica?", ["Brasil", "Argentina", "Perú"], 0),
    ("¿Qué país tiene el Canal de Panamá?", ["Panamá", "Costa Rica", "Colombia"], 0),
    ("¿La Patagonia es de Argentina y de qué otro país?", ["Chile", "Uruguay", "Bolivia"], 0),
    ("¿Qué país es famoso por el carnaval de Río?", ["Brasil", "Argentina", "Uruguay"], 0),
    ("¿Qué moneda se usa en la mayoría de Europa?", ["El euro", "El dólar", "La libra"], 0),
    ("¿Qué país tiene la estatua del Cristo Redentor?", ["Brasil", "Portugal", "Perú"], 0),
]

DEPORTES_MC = [
    ("¿En qué deporte se usa un bate y una pelota pequeña?", ["Béisbol", "Golf", "Hockey"], 0),
    ("¿Cuántos puntos vale un try en el rugby?", ["Cinco", "Tres", "Siete"], 0),
    ("¿En qué deporte compitió Manu Ginóbili?", ["Básquet", "Vóley", "Handball"], 0),
    ("¿Qué deporte se juega en un ring con guantes?", ["Boxeo", "Judo", "Esgrima"], 0),
    ("¿En qué deporte se nada estilo mariposa?", ["Natación", "Remo", "Waterpolo"], 0),
    ("¿Qué se usa para jugar al golf?", ["Un palo y una pelotita", "Una raqueta", "Un arco"], 0),
    ("¿Cuántos jugadores de vóley hay por equipo en cancha?", ["Seis", "Cinco", "Siete"], 0),
    ("¿Qué deporte tiene caballos y se juega con mazo?", ["Polo", "Turf", "Doma"], 0),
    ("¿En qué deporte se gana por puntos con un shuttlecock?", ["Bádminton", "Squash", "Frontón"], 0),
    ("¿Qué carrera de atletismo es la más corta en los Juegos Olímpicos?", ["Los 100 metros", "La maratón", "Los 400 metros"], 0),
    ("¿En qué deporte argentino se usa una cancha de cemento y una pelota de cuero, de a parejas?", ["Pelota paleta", "Pato", "Bocho"], 0),
    ("¿Qué deporte se practica sobre hielo con piedras y escobas?", ["Curling", "Hockey sobre hielo", "Patinaje artístico"], 0),
]
FUTBOL_MC = [
    ("¿Qué país tiene más Mundiales ganados?", ["Brasil", "Alemania", "Italia"], 0),
    ("¿Cuántos Mundiales ganó Argentina?", ["Tres", "Dos", "Cuatro"], 0),
    ("¿Qué jugador es conocido como 'La Pulga'?", ["Messi", "Maradona", "Batistuta"], 0),
    ("¿En qué país se jugó el Mundial 2014?", ["Brasil", "Sudáfrica", "Rusia"], 0),
    ("¿Qué selección ganó la primera Copa del Mundo en 1930?", ["Uruguay", "Argentina", "Brasil"], 0),
    ("¿Cuánto dura un partido de fútbol reglamentario?", ["Noventa minutos", "Ochenta minutos", "Cien minutos"], 0),
    ("¿Qué arquero argentino atajó en la final del Mundial 2022?", ["Dibu Martínez", "Armani", "Rulli"], 0),
    ("¿Qué club inglés tiene el apodo 'Red Devils'?", ["Manchester United", "Liverpool", "Arsenal"], 0),
    ("¿Qué competencia enfrenta a los mejores clubes de Europa?", ["La Champions League", "La Europa League", "La Supercopa"], 0),
    ("¿Qué delantero portugués es histórico goleador de Champions?", ["Cristiano Ronaldo", "Eusébio", "Figo"], 0),
    ("¿Cada cuántos años se juega el Mundial?", ["Cuatro", "Dos", "Cinco"], 0),
    ("¿Qué tarjeta expulsa a un jugador?", ["La roja", "La amarilla", "La azul"], 0),
]
PELICULAS_MC = [
    ("¿Qué película argentina ganó el Oscar en 2010?", ["El secreto de sus ojos", "Relatos salvajes", "Nueve reinas"], 0),
    ("¿Quién dirigió la trilogía de 'El señor de los anillos'?", ["Peter Jackson", "Steven Spielberg", "James Cameron"], 0),
    ("¿Qué película tiene un barco llamado Titanic?", ["Titanic", "Avatar", "Poseidón"], 0),
    ("¿Qué saga tiene a Darth Vader?", ["Star Wars", "Star Trek", "Dune"], 0),
    ("¿Qué actor interpretó a Jack Sparrow?", ["Johnny Depp", "Orlando Bloom", "Brad Pitt"], 0),
    ("¿Qué película de Pixar trata de emociones dentro de la cabeza?", ["Intensamente", "Coco", "Up"], 0),
    ("¿Qué película mexicana de 2018 ganó el Oscar a mejor película extranjera?", ["Roma", "Amores perros", "El laberinto del fauno"], 0),
    ("¿En qué película un niño queda solo en casa en Navidad?", ["Mi pobre angelito", "El regalo prometido", "Frozen"], 0),
    ("¿Qué dinosaurio es el malo famoso de Jurassic Park?", ["El T-Rex", "El triceratops", "El brontosaurio"], 0),
    ("¿Qué película argentina de 1985 ganó el primer Oscar del país?", ["La historia oficial", "Camila", "Tango"], 0),
    ("¿Qué superhéroe tiene un martillo llamado Mjolnir?", ["Thor", "Iron Man", "Superman"], 0),
    ("¿Qué película tiene la frase 'Hasta la vista, baby'?", ["Terminator 2", "RoboCop", "Rambo"], 0),
]

SERIES_MC = [
    ("¿Qué serie tiene a un profesor de química que cocina metanfetamina?", ["Breaking Bad", "Better Call Saul", "Narcos"], 0),
    ("¿Qué serie argentina tiene a los hermanos Díaz y una remisería?", ["Los simuladores", "Okupas", "El marginal"], 0),
    ("¿En qué serie los personajes viven en el pueblo de Hawkins?", ["Stranger Things", "Dark", "The OA"], 0),
    ("¿Qué serie coreana de juegos mortales fue furor mundial?", ["El juego del calamar", "Kingdom", "Alice in Borderland"], 0),
    ("¿Qué serie tiene tronos, dragones y la familia Stark?", ["Game of Thrones", "Vikings", "The Witcher"], 0),
    ("¿Qué serie colombiana cuenta la vida de Pablo Escobar?", ["Narcos", "El patrón del mal", "Sin tetas no hay paraíso"], 0),
    ("¿Qué serie española trata de un robo a la Casa de la Moneda?", ["La casa de papel", "Élite", "Vis a vis"], 0),
    ("¿Qué serie sigue a un grupo de amigos en un café de Nueva York?", ["Friends", "How I Met Your Mother", "Seinfeld"], 0),
    ("¿Qué serie argentina de los 90 tenía a 'el Pollo' y a 'el Cabezón'?", ["Verano del 98", "Chiquititas", "Muñeca brava"], 0),
    ("¿Qué serie de zombis empieza con Rick despertando en un hospital?", ["The Walking Dead", "Z Nation", "Fear the Walking Dead"], 0),
    ("¿Qué serie animada amarilla vive en Springfield?", ["Los Simpson", "Futurama", "Padre de familia"], 0),
    ("¿Qué serie tiene al detective Sherlock Holmes moderno en Londres?", ["Sherlock", "Elementary", "Luther"], 0),
]
HISTORIA_MC = [
    ("¿En qué año llegó Colón a América?", ["1492", "1500", "1485"], 0),
    ("¿Qué prócer argentino cruzó los Andes?", ["San Martín", "Belgrano", "Sarmiento"], 0),
    ("¿Qué imperio construyó el Coliseo?", ["El romano", "El griego", "El egipcio"], 0),
    ("¿En qué año se declaró la independencia argentina?", ["1816", "1810", "1820"], 0),
    ("¿Quién fue el primer presidente de Estados Unidos?", ["George Washington", "Abraham Lincoln", "Thomas Jefferson"], 0),
    ("¿Qué guerra mundial empezó en 1939?", ["La Segunda", "La Primera", "La de Corea"], 0),
    ("¿Qué civilización construyó Machu Picchu?", ["La inca", "La azteca", "La maya"], 0),
    ("¿Qué faraona egipcia es la más famosa de la historia?", ["Cleopatra", "Nefertiti", "Hatshepsut"], 0),
    ("¿Quién pintó la Capilla Sixtina?", ["Miguel Ángel", "Leonardo da Vinci", "Rafael"], 0),
    ("¿Qué revolución empezó en Francia en 1789?", ["La Revolución Francesa", "La Revolución Industrial", "La Comuna"], 0),
    ("¿Qué muro cayó en 1989?", ["El Muro de Berlín", "La Muralla China", "El Muro de Adriano"], 0),
    ("¿Quién fue el Libertador de Venezuela, Colombia y Bolivia?", ["Simón Bolívar", "San Martín", "Sucre"], 0),
]
CIENCIA_MC = [
    ("¿Cuál es la fórmula química del agua?", ["H2O", "CO2", "O2"], 0),
    ("¿Qué científico propuso la teoría de la relatividad?", ["Einstein", "Newton", "Galileo"], 0),
    ("¿Qué partícula tiene carga negativa?", ["El electrón", "El protón", "El neutrón"], 0),
    ("¿Qué planeta está más cerca del Sol?", ["Mercurio", "Venus", "Marte"], 0),
    ("¿Qué órgano humano filtra la sangre y produce orina?", ["El riñón", "El hígado", "El bazo"], 0),
    ("¿Qué fuerza nos mantiene con los pies en el suelo?", ["La gravedad", "El magnetismo", "La fricción"], 0),
    ("¿Qué gas expulsan las plantas al hacer la fotosíntesis?", ["Oxígeno", "Dióxido de carbono", "Nitrógeno"], 0),
    ("¿Cuántos huesos tiene el cuerpo humano adulto, más o menos?", ["206", "150", "300"], 0),
    ("¿Qué mide la escala de Richter?", ["Los terremotos", "Los huracanes", "La temperatura"], 0),
    ("¿Qué científica ganó dos premios Nobel en química y física?", ["Marie Curie", "Rosalind Franklin", "Ada Lovelace"], 0),
    ("¿A qué velocidad viaja la luz, aproximadamente?", ["300 mil km por segundo", "300 mil km por hora", "30 mil km por segundo"], 0),
    ("¿Qué metal es líquido a temperatura ambiente?", ["El mercurio", "El sodio", "El aluminio"], 0),
]

ARTE_MC = [
    ("¿Quién pintó la Mona Lisa?", ["Leonardo da Vinci", "Miguel Ángel", "Picasso"], 0),
    ("¿Qué pintor argentino es famoso por sus figuras gorditas?", ["Quinquela Martín", "Xul Solar", "Spilimbergo"], 0),
    ("¿Qué pintor se cortó parte de la oreja?", ["Van Gogh", "Monet", "Dalí"], 0),
    ("¿Qué estilo artístico usaba puntitos de color?", ["El puntillismo", "El cubismo", "El surrealismo"], 0),
    ("¿Quién pintó 'La persistencia de la memoria', con relojes blandos?", ["Salvador Dalí", "Pablo Picasso", "Frida Kahlo"], 0),
    ("¿Qué artista mexicana es famosa por sus autorretratos?", ["Frida Kahlo", "Diego Rivera", "Remedios Varo"], 0),
    ("¿Qué museo de París guarda la Mona Lisa?", ["El Louvre", "El Prado", "El MoMA"], 0),
    ("¿Qué movimiento artístico fundó Picasso con Braque?", ["El cubismo", "El impresionismo", "El expresionismo"], 0),
    ("¿Qué bailarina clásica usa zapatillas de punta y tutú?", ["La bailarina de ballet", "La de flamenco", "La de tango"], 0),
    ("¿Qué pintor holandés pintó 'La noche estrellada'?", ["Van Gogh", "Rembrandt", "Vermeer"], 0),
    ("¿Qué escultor hizo 'El pensador'?", ["Rodin", "Miguel Ángel", "Bernini"], 0),
    ("¿Qué tanguero argentino es el más famoso de la historia?", ["Carlos Gardel", "Aníbal Troilo", "Astor Piazzolla"], 0),
]
COMIDA_MC = [
    ("¿Qué comida argentina es de masa rellena al horno o frita?", ["La empanada", "El locro", "La milanesa"], 0),
    ("¿De qué país es el sushi?", ["Japón", "China", "Tailandia"], 0),
    ("¿Qué comida italiana lleva masa, salsa y queso al horno?", ["La pizza", "El risotto", "La lasaña"], 0),
    ("¿Qué grano es la base del pan?", ["El trigo", "El arroz", "El maíz"], 0),
    ("¿Qué comida mexicana es una tortilla rellena y doblada?", ["El taco", "La quesadilla", "El burrito"], 0),
    ("¿Qué fruta amarilla se pela y es rica en potasio?", ["La banana", "El ananá", "El mango"], 0),
    ("¿Qué asado argentino se cocina a la parrilla con brasas?", ["El asado", "El puchero", "El matambre"], 0),
    ("¿De qué país es la paella?", ["España", "Portugal", "Italia"], 0),
    ("¿Qué verdura es la base de la ensalada César?", ["La lechuga", "La espinaca", "La rúcula"], 0),
    ("¿Qué postre italiano significa 'levantame'?", ["El tiramisú", "El gelato", "El panetone"], 0),
    ("¿Qué legumbre es la base del hummus?", ["El garbanzo", "La lenteja", "El poroto"], 0),
    ("¿Qué pescado crudo se usa en el ceviche peruano?", ["Pescado blanco", "Salmón ahumado", "Atún en lata"], 0),
]
NOMBRES_MC = [
    ("¿De dónde viene el nombre Diego?", ["Del latín Jacobus, como Santiago", "Del griego 'guerrero'", "Del árabe 'regalo'"], 0),
    ("¿Qué nombre significa 'la que trae la victoria'?", ["Verónica", "Victoria", "Valeria"], 0),
    ("¿Qué nombre de varón significa 'pequeño' en latín?", ["Pablo", "Pedro", "Pascual"], 0),
    ("¿Qué apellido es el más común en Argentina?", ["González", "Rodríguez", "García"], 0),
    ("¿Qué nombre significa 'regalo de Dios'?", ["Mateo", "Martín", "Marcos"], 0),
    ("¿De qué idioma vienen la mayoría de los apellidos terminados en 'ez'?", ["Del español: hijo de", "Del italiano: familia", "Del francés: lugar"], 0),
    ("¿Qué nombre femenino significa 'bella' en italiano?", ["Bella", "Luna", "Alma"], 0),
    ("¿Qué famoso futbolista se llama Lionel?", ["Messi", "Scaloni", "Di María"], 0),
    ("¿Qué nombre significa 'león' en latín?", ["León", "Bruno", "Dante"], 0),
    ("¿Qué nombre de mujer viene de la palabra 'gracia'?", ["Graciela", "Estela", "Noelia"], 0),
    ("¿Qué apellido indica oficio de herrero en español?", ["Herrero", "Molinero", "Pastor"], 0),
    ("¿Qué nombre griego significa 'amante de los caballos'?", ["Felipe", "Carlos", "Andrés"], 0),
]

MARCAS_MC = [
    ("¿Qué marca de gaseosa tiene el logo rojo con letra blanca?", ["Coca-Cola", "Pepsi", "Fanta"], 0),
    ("¿Qué marca de autos tiene cuatro aros en el logo?", ["Audi", "BMW", "Mercedes"], 0),
    ("¿Qué marca de tecnología tiene una manzana mordida?", ["Apple", "Samsung", "Xiaomi"], 0),
    ("¿Qué marca deportiva usa el lema 'Just Do It'?", ["Nike", "Adidas", "Puma"], 0),
    ("¿Qué marca de yerba mate argentina viene en paquete verde?", ["Taragüi", "Rosamonte", "Playadito"], 0),
    ("¿Qué marca de hamburguesas tiene un arco dorado?", ["McDonald's", "Burger King", "Wendy's"], 0),
    ("¿Qué marca de chocolate suizo es famosa por sus barritas con leche y miel?", ["Toblerone", "Lindt", "Nestlé"], 0),
    ("¿Qué marca de aviones es la más grande del mundo junto con Airbus?", ["Boeing", "Embraer", "Bombardier"], 0),
    ("¿Qué marca argentina de alfajores es de Mar del Plata?", ["Havanna", "Cachafaz", "Jorgito"], 0),
    ("¿Qué marca de relojes suizos es sinónimo de lujo?", ["Rolex", "Casio", "Swatch"], 0),
    ("¿Qué marca de zapatillas tiene tres tiras?", ["Adidas", "Nike", "Reebok"], 0),
    ("¿Qué marca de helados tiene corazón en el logo y es famosa mundial?", ["Häagen-Dazs", "Grido", "Freddo"], 0),
]
ANIMALES_MC = [
    ("¿Cuál es el animal más grande del mundo?", ["La ballena azul", "El elefante", "La jirafa"], 0),
    ("¿Qué animal pone huevos y tiene pico de pato?", ["El ornitorrinco", "El equidna", "El cisne"], 0),
    ("¿Qué animal argentino tiene peluche y vive en la Patagonia?", ["La mara", "El guanaco", "El zorrino"], 0),
    ("¿Qué animal puede dormir de pie?", ["El caballo", "El perro", "El gato"], 0),
    ("¿Cuál es el ave más grande que vuela?", ["El cóndor", "El águila", "El albatros"], 0),
    ("¿Qué animal tiene la lengua más larga en relación a su cuerpo?", ["El camaleón", "La jirafa", "El oso hormiguero"], 0),
    ("¿Qué animal marino tiene ocho brazos?", ["El pulpo", "El calamar", "La medusa"], 0),
    ("¿Cuál es el único mamífero que vuela?", ["El murciélago", "La ardilla voladora", "El petrel"], 0),
    ("¿Qué animal simboliza la sabiduría en los cuentos?", ["El búho", "El cuervo", "El zorro"], 0),
    ("¿Qué animal puede vivir más de 100 años en el mar?", ["La tortuga", "El delfín", "El tiburón"], 0),
    ("¿Qué animal produce el capullo de seda?", ["El gusano de seda", "La oruga común", "La araña"], 0),
    ("¿Qué animal es el mejor amigo del hombre?", ["El perro", "El gato", "El caballo"], 0),
]
POLITICA_MC = [
    ("¿Qué órgano argentino hace las leyes?", ["El Congreso", "La Corte Suprema", "La Presidencia"], 0),
    ("¿Cada cuántos años se elige presidente en Argentina?", ["Cuatro", "Seis", "Dos"], 0),
    ("¿Qué casa de gobierno argentina es rosada?", ["La Casa Rosada", "El Cabildo", "El Congreso"], 0),
    ("¿Qué signo político argentino fue famoso por los pañuelos?", ["Las Madres de Plaza de Mayo", "Los piqueteros", "Los sindicatos"], 0),
    ("¿Qué organismo internacional tiene sede en Nueva York?", ["La ONU", "La OMS", "La FIFA"], 0),
    ("¿Qué presidente argentino fue famoso por el 'vamos carajo'?", ["Alfonsín", "Menem", "Illia"], 0),
    ("¿Cómo se llama el sistema donde el pueblo elige a sus gobernantes?", ["La democracia", "La monarquía", "La dictadura"], 0),
    ("¿Qué documento argentino empieza con 'Nos los representantes'?", ["La Constitución", "El Acta de Independencia", "El Código Civil"], 0),
    ("¿Qué cargo gobierna una provincia argentina?", ["El gobernador", "El intendente", "El senador"], 0),
    ("¿Qué cargo gobierna un municipio?", ["El intendente", "El gobernador", "El diputado"], 0),
    ("¿Qué país tuvo a Nelson Mandela como presidente?", ["Sudáfrica", "Nigeria", "Ghana"], 0),
    ("¿Qué reina de Inglaterra reinó más de 70 años?", ["Isabel II", "Victoria", "Ana"], 0),
]

RELIGION_MC = [
    ("¿Qué religión tiene la Biblia como libro sagrado?", ["El cristianismo", "El islam", "El budismo"], 0),
    ("¿Qué profeta fundó el islam?", ["Mahoma", "Moisés", "Abraham"], 0),
    ("¿Qué papa argentino gobierna la Iglesia desde 2013?", ["Francisco", "Benedicto XVI", "Juan Pablo II"], 0),
    ("¿En qué ciudad está el Vaticano?", ["Roma", "Milán", "Florencia"], 0),
    ("¿Qué religión sigue las enseñanzas de Buda?", ["El budismo", "El hinduismo", "El sintoísmo"], 0),
    ("¿Qué libro sagrado leen los musulmanes?", ["El Corán", "La Torá", "Los Vedas"], 0),
    ("¿Qué fiesta cristiana celebra el nacimiento de Jesús?", ["La Navidad", "La Pascua", "La Epifanía"], 0),
    ("¿Qué religión tiene el Diwali como fiesta de las luces?", ["El hinduismo", "El budismo", "El judaísmo"], 0),
    ("¿Qué día sagrado guardan los judíos desde el atardecer del viernes?", ["El Shabat", "El Ramadán", "La Pascua"], 0),
    ("¿En qué río fue bautizado Jesús según la Biblia?", ["El Jordán", "El Nilo", "El Éufrates"], 0),
    ("¿Qué arca salvó a los animales del diluvio?", ["La de Noé", "La de Moisés", "La de Abraham"], 0),
    ("¿Qué virgen es patrona de Argentina?", ["La Virgen de Luján", "La Virgen del Carmen", "La Virgen de Guadalupe"], 0),
]
MUSICA_MC = [
    ("¿Qué instrumento tiene 6 cuerdas y se toca con los dedos o púa?", ["La guitarra", "El ukelele", "El bajo"], 0),
    ("¿Qué banda británica cantó 'Hey Jude'?", ["The Beatles", "Queen", "Rolling Stones"], 0),
    ("¿Qué cantante argentina es la voz de 'La Llorona' en el folklore?", ["Mercedes Sosa", "Soledad", "Marilina Ross"], 0),
    ("¿Qué género musical nació en Jamaica?", ["El reggae", "El ska", "El calypso"], 0),
    ("¿Qué bandoneonista revolucionó el tango?", ["Astor Piazzolla", "Aníbal Troilo", "Osvaldo Pugliese"], 0),
    ("¿Qué rey del pop hizo 'Thriller'?", ["Michael Jackson", "Prince", "Stevie Wonder"], 0),
    ("¿Qué grupo argentino cantó 'De música ligera'?", ["Soda Stereo", "Los Fabulosos Cadillacs", "Divididos"], 0),
    ("¿Qué instrumento de viento tiene lengüeta simple?", ["El clarinete", "La flauta", "La trompeta"], 0),
    ("¿Qué cantante es conocida como 'La Sole'?", ["Soledad Pastorutti", "Karina", "Lucía Galán"], 0),
    ("¿Qué rockero argentino es 'El Flaco'?", ["Luis Alberto Spinetta", "Charly García", "Fito Páez"], 0),
    ("¿Qué género popular argentino se baila en pareja abrazada?", ["El tango", "El cuarteto", "La cumbia"], 0),
    ("¿Qué compositor sordo escribió la Novena Sinfonía?", ["Beethoven", "Mozart", "Bach"], 0),
]
GEOGRAFIA_MC = [
    ("¿Cuál es el desierto más grande del mundo?", ["El Sahara", "El Gobi", "El Atacama"], 0),
    ("¿Qué cordillera recorre Sudamérica de norte a sur?", ["Los Andes", "Las Rocallosas", "Los Alpes"], 0),
    ("¿Cuál es la cascada más famosa entre Argentina y Brasil?", ["Las Cataratas del Iguazú", "El Salto Ángel", "El Niágara"], 0),
    ("¿Qué río pasa por Buenos Aires?", ["El Río de la Plata", "El Paraná", "El Uruguay"], 0),
    ("¿Cuál es el país más grande del mundo?", ["Rusia", "China", "Canadá"], 0),
    ("¿Qué lago navegable es el más alto del mundo, entre Perú y Bolivia?", ["El Titicaca", "El Nahuel Huapi", "El Maracaibo"], 0),
    ("¿Cuál es la isla más grande del mundo?", ["Groenlandia", "Australia", "Borneo"], 0),
    ("¿Qué canal une el Atlántico con el Pacífico?", ["El Canal de Panamá", "El Canal de Suez", "El Beagle"], 0),
    ("¿Cuál es la capital de Australia?", ["Canberra", "Sídney", "Melbourne"], 0),
    ("¿Qué volcán japonés es símbolo del país?", ["El Monte Fuji", "El Monte Aso", "El Sakurajima"], 0),
    ("¿Qué desierto chileno es el más árido del mundo?", ["Atacama", "Sonora", "Mojave"], 0),
    ("¿Qué glaciar argentino es famoso por sus rupturas?", ["El Perito Moreno", "El Upsala", "El Viedma"], 0),
]

TECNOLOGIA_MC = [
    ("¿Qué significa WWW en internet?", ["World Wide Web", "World Web Wide", "Web World Wide"], 0),
    ("¿Qué empresa creó el sistema Android?", ["Google", "Apple", "Microsoft"], 0),
    ("¿Qué red social tiene un pajarito o una X?", ["Twitter", "Facebook", "Instagram"], 0),
    ("¿Qué aparato guarda fotos, contactos y apps en el bolsillo?", ["El celular", "La tablet", "La notebook"], 0),
    ("¿Qué inventor es famoso por la lámpara eléctrica?", ["Edison", "Tesla", "Bell"], 0),
    ("¿Qué lenguaje de programación tiene nombre de serpiente?", ["Python", "Cobra", "Java"], 0),
    ("¿Qué empresa hace las consolas PlayStation?", ["Sony", "Nintendo", "Microsoft"], 0),
    ("¿Qué satélite natural orbita la Tierra?", ["La Luna", "El Hubble", "La ISS"], 0),
    ("¿Qué significa Wi-Fi, en criollo?", ["Conexión inalámbrica a internet", "Cable de red", "Señal de celular"], 0),
    ("¿Qué robot aspiradora es famoso por limpiar casas solo?", ["El Roomba", "El Terminator", "El R2D2"], 0),
    ("¿Qué app de mensajería usa el teléfono y es verde?", ["WhatsApp", "Telegram", "Signal"], 0),
    ("¿Qué letra identifica una unidad de almacenamiento gigante, mil veces el giga?", ["La T (tera)", "La M (mega)", "La K (kilo)"], 0),
]
VIDEOJUEGOS_MC = [
    ("¿Qué fontanero bigotudo salta sobre tortugas?", ["Mario", "Luigi", "Sonic"], 0),
    ("¿Qué juego tiene bloques cuadrados y creepers?", ["Minecraft", "Roblox", "Terraria"], 0),
    ("¿Qué erizo azul corre a toda velocidad?", ["Sonic", "Crash", "Spyro"], 0),
    ("¿Qué juego de fútbol hace EA todos los años?", ["El EA Sports FC", "El PES", "El Rocket League"], 0),
    ("¿Qué juego tiene batallas de 100 jugadores en una isla?", ["Fortnite", "Minecraft", "Among Us"], 0),
    ("¿Qué consola portátil tiene dos pantallas?", ["La Nintendo DS", "La PlayStation Vita", "La Switch"], 0),
    ("¿Qué personaje amarillo come bolitas en un laberinto?", ["Pac-Man", "Kirby", "Pikachu"], 0),
    ("¿Qué juego de carreras tiene caparazones y bananas?", ["Mario Kart", "Need for Speed", "Gran Turismo"], 0),
    ("¿Qué juego argentino de cartas se juega con truco y envido?", ["El Truco", "La Escoba", "El Chinchón"], 0),
    ("¿Qué juego tiene impostores en una nave espacial?", ["Among Us", "Fall Guys", "Fortnite"], 0),
    ("¿Qué saga tiene a Link y la princesa Zelda?", ["Zelda", "Final Fantasy", "Metroid"], 0),
    ("¿Qué juego de pelea tiene a Scorpion y Sub-Zero?", ["Mortal Kombat", "Street Fighter", "Tekken"], 0),
]

CATEGORIES = {
    "verdad_reto": "Verdad o Reto",
    "deportes": "Deportes",
    "fútbol mundial": "Fútbol mundial",
    "películas": "Películas",
    "series": "Series",
    "cultura": "Cultura",
    "historia": "Historia",
    "ciencia": "Ciencia",
    "arte": "Arte",
    "comida": "Comida",
    "nombres y apellidos": "Nombres y apellidos",
    "marcas": "Marcas",
    "animales": "Animales",
    "política": "Política",
    "religión": "Religión",
    "música": "Música",
    "geografía": "Geografía",
    "tecnología": "Tecnología",
    "videojuegos": "Videojuegos",
    "refranes": "Refranes",
    "países": "Países",
}
def _ensure_four_options(bank):
    """Existing questions already include the correct answer, so 'none' is false."""
    return [(q, list(opts) + (["Ninguna de las anteriores"] if len(opts) == 3 else []), c)
            for q, opts, c in bank]


MC_BANKS = {
    "deportes": DEPORTES_MC, "fútbol mundial": FUTBOL_MC,
    "películas": PELICULAS_MC, "series": SERIES_MC, "cultura": TRIVIA_MC,
    "historia": HISTORIA_MC, "ciencia": CIENCIA_MC, "arte": ARTE_MC,
    "comida": COMIDA_MC, "nombres y apellidos": NOMBRES_MC, "marcas": MARCAS_MC,
    "animales": ANIMALES_MC, "política": POLITICA_MC, "religión": RELIGION_MC,
    "música": MUSICA_MC, "geografía": GEOGRAFIA_MC, "tecnología": TECNOLOGIA_MC,
    "videojuegos": VIDEOJUEGOS_MC, "refranes": REFRANES_MC, "países": PAISES_MC,
}

MC_BANKS = {name: _ensure_four_options(bank) for name, bank in MC_BANKS.items()}

MC_USED_KEYS = {cat: "used_" + str(i) for i, cat in enumerate(MC_BANKS)}

WIN_SCORE = 5
COUNTRIES_TO_WIN = 2
QUESTIONS_PER_LEVEL = 5
CATEGORIES_TO_PASS = 3
TURN_SECONDS = 60
REMATCH_SECONDS = 10
NARRATOR_VOICES = ["es-AR-ElenaNeural", "es-AR-TomasNeural", "es-UY-ValentinaNeural"]
MAX_PLAYERS = 100  # Rocky's cap; spectators join beyond it

GAME_DESCRIPTIONS = {'bomba': 'La bomba: decí una respuesta que cumpla la consigna antes de que se termine la mecha. Si vale, pasás la bomba. Si no vale o se acaba el tiempo, perdés una vida.', 'misterio': 'Resolver el misterio: escuchá el caso y proponé una teoría hablando o escribiendo. Acertar gana el caso. Una teoría lejos de la solución cuesta una vida.', 'categorias': 'Girás la ruleta y seguís en la categoría que salga hasta conseguir cinco respuestas correctas. Empezás con cuatro vidas; cada error cuesta una. Cinco correctas seguidas regalan una vida, sin superar cuatro. Sin vidas volvés al comienzo y girás de nuevo, con cuatro vidas. No quedás eliminado. El primero en pasar tres categorías gana.', 'paises': 'Primero girás la ruleta de países. Girás la ruleta y seguís en la categoría que salga hasta conseguir cinco respuestas correctas. Empezás con cuatro vidas; cada error cuesta una. Cinco correctas seguidas regalan una vida, sin superar cuatro. Sin vidas volvés al comienzo y girás de nuevo, con cuatro vidas. No quedás eliminado. Completá todas las categorías para ganar el país. Dos países ganan la partida.', 'ahorcado': 'El ahorcado: adivinás la palabra letra por letra, hablando o escribiendo. Si la letra está, seguís jugando; si no, pasa el turno. El que adivina la palabra sube de nivel; el primero en pasar el nivel 5 gana.'}

# ---------------------------------------------------------------------------
# Rooms: everything in memory (party games; a restart ends the sala).
# ---------------------------------------------------------------------------
rooms = {}
audio_cache = {}  # key -> (mp3 bytes, timestamp)


def new_room_code() -> str:
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        if code not in rooms:
            return code


def connected(room):
    return [p for p in room["players"] if p["ws"] is not None]


TEAM_NAMES = ["Rojo", "Azul", "Verde", "Amarillo"]


def host_player(room):
    return next((p for p in room["players"] if not p.get("gone") and not p.get("spectator")), None)


def score_owner(room, player):
    return f"equipo:{player['team']}" if room.get("team_count") and player.get("team") is not None else player["id"]


def sync_score(room, player, score):
    for member in room["players"]:
        if member is player or (room.get("team_count") and member.get("team") == player.get("team") and not member.get("spectator")):
            room["scores"][member["id"]] = score


def current_player(room):
    active = [p for p in room["players"]
              if not p.get("gone") and not p.get("out") and not p.get("spectator")]
    if not active:
        return None
    if room.get("team_count"):
        groups = [[p for p in active if p.get("team") == team] for team in range(room["team_count"])]
        groups = [g for g in groups if g]
        if groups:
            return groups[room["turn"] % len(groups)][(room["turn"] // len(groups)) % len(groups[room["turn"] % len(groups)])]
    return active[room["turn"] % len(active)]


def survivor_winner(room, alive):
    if len(alive) == 1:
        return alive[0]
    if room.get("team_count") and alive and len({p.get("team") for p in alive}) == 1:
        return alive[0]
    return None


def room_state(room) -> dict:
    current = current_player(room)
    return {
        "event": "state",
        "quiz_lives": room.get("quiz_lives", {}),
        "quiz_run": room.get("quiz_run"),
        "question": public_question(room),
        "team_count": room.get("team_count", 0),
        "team_names": TEAM_NAMES[:room.get("team_count", 0)],
        "players": [
            {"id": p["id"], "name": p["name"], "score": room["scores"].get(p["id"], 0),
             "connected": p["ws"] is not None, "out": bool(p.get("out")),
             "spectator": bool(p.get("spectator")), "team": p.get("team")}
            for p in room["players"] if not p.get("gone")
        ],
        "turn": current["id"] if current else None,
        "turn_name": current["name"] if current else None,
        "turn_number": room["turn"],
        "case_idx": room.get("misterio", {}).get("case_idx", -1),
        "phase": room["phase"],
        "spinning": room["spinning"],
        "capacity": room["capacity"],
        "match": room["match"],
        "goal": WIN_SCORE,
        "game": room["game"],
        "country": room["country"],
        "country_done": len(room["country_done"]),
        "ahorcado": ({
            "board": ah_board(room["ahorcado"]["word"] or "", room["ahorcado"]["guessed"]),
            "hint": room["ahorcado"]["hint"],
            "attempts": room["ahorcado"]["attempts"],
            "wrong": sorted(room["ahorcado"]["wrong"]),
            "levels": room["ahorcado"]["levels"],
        } if room["game"] == "ahorcado" and room["ahorcado"]["word"] else None),
        "bomba": ({
            "prompt": room["bomba"]["prompt"],
            "fuse": room["bomba"]["fuse"],
            "lives": room["bomba"]["lives"],
            "said": len(room["bomba"]["said"]),
        } if room["game"] == "bomba" and room["bomba"].get("prompt") else None),
        "misterio": ({
            "title": room["misterio"]["case"][0],
            "case": room["misterio"]["case"][1],
            "lives": room["misterio"]["lives"],
            "solved": room["misterio"]["solved"],
            "to_win": MISTERIO_TO_WIN,
        } if room["game"] == "misterio" and room["misterio"].get("case") else None),
    }


async def tell(player, message: dict):
    if player["ws"] is None:
        return
    try:
        await player["ws"].send_text(json.dumps(message, ensure_ascii=False))
    except Exception:
        player["ws"] = None


async def broadcast(room, message: dict):
    for player in room["players"]:
        if not player.get("gone"):
            await tell(player, message)


async def ogg_to_mp3(ogg: bytes) -> bytes:
    """Safari can't play ogg/opus; every phone plays mp3."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "in.ogg"
        target = Path(directory) / "out.mp3"
        source.write_bytes(ogg)
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(source), "-c:a", "libmp3lame", "-b:a", "64k", str(target),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode:
            raise RuntimeError(f"ffmpeg mp3 failed: {stderr.decode()[:300]}")
        return target.read_bytes()


def cache_audio(mp3: bytes) -> str:
    key = hashlib.sha256(mp3).hexdigest()[:24]
    audio_cache[key] = (mp3, time.time())
    for old_key, (_, ts) in list(audio_cache.items()):
        if time.time() - ts > 3600:
            audio_cache.pop(old_key, None)
    return key


async def bounded_voice_mp3(text, voice):
    """A stalled remote voice must never hold a room's narration lock forever."""
    from app import synthesize, synthesize_once
    try:
        return await asyncio.wait_for(ogg_to_mp3(await asyncio.wait_for(
            synthesize(text, voice), timeout=6)), timeout=4)
    except Exception:
        log.warning("Web voice slow/unavailable; using local Spanish voice")
        return await asyncio.wait_for(ogg_to_mp3(await asyncio.wait_for(
            synthesize_once(text, "espeak-es-419"), timeout=6)), timeout=4)


async def say(room, text: str, voice=None, to=None, question_id=None):
    """Synthesize ONCE server-side and send to everyone (or one player)."""
    from app import synthesize  # local import: app.py mounts this router

    voice = voice or room.get("voice") or "es-AR-ElenaNeural"
    try:
        mp3 = await bounded_voice_mp3(text, voice)
        url = f"/amor-con-aroma-a-cafe/audio/{cache_audio(mp3)}.mp3"
    except Exception:
        log.exception("Web sala: synthesis failed; sending text only")
        url = None
    message = {"event": "say", "text": text, "audio": url}
    if question_id is not None:
        message["question_id"] = question_id
        q = room.get("question")
        if q and q.get("id") == question_id:
            q["audio"] = url
            q["audio_ready"] = True
    if to is not None:
        await tell(to, message)
    else:
        await broadcast(room, message)


async def narrate(room, text: str, voice=None, to=None, question_id=None):
    """Serialized per room so announcements never talk over each other."""
    async with room["audio_lock"]:
        await say(room, text, voice=voice, to=to, question_id=question_id)


def pick_mc(room, category):
    bank = MC_BANKS[category]
    used = room[MC_USED_KEYS[category]]
    available = [item for item in bank if item[0] not in used]
    if not available:
        used.clear()
        available = list(bank)
    pick = random.choice(available)
    used.add(pick[0])
    return pick


def cancel_timer(room):
    task = room.get("timer_task")
    if task and not task.done() and task is not asyncio.current_task():
        task.cancel()
    room["timer_task"] = None


CHATTER_VOICES = ["es-AR-ElenaNeural", "es-AR-TomasNeural", "es-UY-ValentinaNeural",
                  "es-MX-DaliaNeural", "es-CO-GonzaloNeural", "es-CL-CatalinaNeural"]
CHATTER_30 = [
    "Dale, {name}, ¡apurate!",
    "¡Vamos {name}, que se pasa el tiempo!",
    "Pensá rápido, {name}, ¡dale!",
    "¡{name}, che, el reloj corre!",
    "Órale {name}, ¡que no se te pase el turno!",
    "¡Dale {name}, vos podés!",
]
CHATTER_10 = [
    "¡10 segundos, {name}!",
    "¡Se te acaba, {name}! ¡10!",
    "¡Últimos 10, dale {name}!",
    "¡Apurate que son 10, {name}!",
]


def chatter_voice(room):
    idx = room.get("chatter_idx", 0)
    room["chatter_idx"] = idx + 1
    return CHATTER_VOICES[idx % len(CHATTER_VOICES)]


async def turn_chatter(room, player):
    # Ephemeral prompts: never queue them behind an important announcement.
    if room["audio_lock"].locked() or room.get("mic_until", 0) > asyncio.get_running_loop().time():
        return
    async with room["audio_lock"]:
        voice = chatter_voice(room)
        lines = {
            "es-AR-ElenaNeural": ["Dale, {name}, vos podés.", "Che, {name}, ¡el reloj corre!"],
            "es-AR-TomasNeural": ["Vamos, {name}, ¡a jugar!", "Dale, {name}, ¡no te duermas!"],
            "es-UY-ValentinaNeural": ["Bo, {name}, ¡metele!", "Vamos arriba, {name}."],
            "es-MX-DaliaNeural": ["Órale, {name}, ¡tú puedes!", "Ánimo, {name}, ¡ya casi!"],
            "es-CO-GonzaloNeural": ["¡Qué más, {name}! Dale con toda.", "Vamos, {name}, ¡tú puedes!"],
            "es-CL-CatalinaNeural": ["¡Vamos, {name}, al tiro!", "Dale, {name}, ¡qué buena onda!"],
        }
        text = random.choice(lines[voice]).format(name=player["name"])
        from app import synthesize
        try:
            data = await asyncio.wait_for(ogg_to_mp3(await synthesize(text, voice)), timeout=3)
        except Exception:
            log.exception("Chatter synthesis failed")
            return
        if room.get("mic_until", 0) > asyncio.get_running_loop().time():
            return
        await broadcast(room, {"event": "chatter", "text": text,
                              "audio": f"/amor-con-aroma-a-cafe/audio/{cache_audio(data)}.mp3" if data else None})


async def turn_clock(room, player_id):
    """Frequent nudges, independent of synthesis latency; no queued chatter."""
    chatter_task = None
    try:
        for elapsed in range(6, TURN_SECONDS + 1, 6):
            await asyncio.sleep(6)
            current = current_player(room)
            if not current or current["id"] != player_id or room["phase"] in ("lobby", "gameover", "answering"):
                return
            if elapsed < TURN_SECONDS and (chatter_task is None or chatter_task.done()):
                chatter_task = asyncio.create_task(turn_chatter(room, current))
        if room["phase"] == "question" and room.get("question") and room["game"] in ("categorias", "paises"):
            await narrate(room, "Se acabó el tiempo para esta pregunta.")
            await resolve_answer(room, current, -1)
            return
        room["turn"] += 1
        nxt = current_player(room)
        await narrate(room, f"Se acabó el tiempo. Ahora le toca a {nxt['name']}." if nxt else "Se acabó el tiempo.")
        await begin_turn(room)
    except asyncio.CancelledError:
        pass
    finally:
        if chatter_task and not chatter_task.done():
            chatter_task.cancel()


async def begin_turn(room):
    """Announce the turn and arm the clock; caller advances room['turn']."""
    cancel_timer(room)
    room["spinning"] = False
    room["question"] = None
    room["quiz_run"] = None
    player = current_player(room)
    if player is None:
        return
    if room["game"] == "ahorcado":
        await ah_start_turn(room)
        return
    if room["game"] == "bomba":
        await bb_next_prompt(room, new_prompt=False)
        return
    if room["game"] == "misterio":
        return  # not turn-based: the floor stays open
    if room["game"] == "paises" and room["country"] is None:
        room["phase"] = "country_spin_ready"
        await broadcast(room, room_state(room))
        await tell(player, {"event": "your_turn", "kind": "country"})
    else:
        room["phase"] = "spin_ready"
        await broadcast(room, room_state(room))
        await tell(player, {"event": "your_turn", "kind": "category"})
    room["timer_task"] = asyncio.create_task(turn_clock(room, player["id"]))


async def start_match(room):
    if room["game"] is None:
        return  # a sala waits for the host to pick the game
    room["quiz_lives"] = {p["id"]: 4 for p in room["players"] if not p.get("spectator")}
    room["quiz_run"] = None
    if room.get("team_count"):
        members = [p for p in room["players"] if not p.get("gone") and not p.get("spectator")]
        if len(members) < 2:
            await narrate(room, "Para jugar por equipos hacen falta al menos dos jugadores.")
            return
        for i, member in enumerate(members):
            if member.get("team") not in range(room["team_count"]):
                member["team"] = i % room["team_count"]
        if len({p["team"] for p in members}) < 2:
            members[-1]["team"] = (members[0]["team"] + 1) % room["team_count"]
        for team in range(room["team_count"]):
            names = [p["name"] for p in members if p["team"] == team]
            if names:
                await narrate(room, f"Equipo {TEAM_NAMES[team]}: {', '.join(names)}.")
    for p in room["players"]:
        p.pop("out", None)  # a new match un-eliminates everyone
    room["scores"] = {p["id"]: 0 for p in room["players"]
                      if not p.get("gone") and not p.get("spectator")}
    room["turn"] = room["starter"]
    if room["game"] == "bomba":
        room["bomba"] = {"lives": {p["id"]: BOMBA_LIVES for p in room["players"]
                                   if not p.get("gone") and not p.get("spectator")},
                         "prompt": None, "keywords": [], "said": set(),
                         "used": set(), "fuse": 0}
        await narrate(room, "¡Arranca La bomba! Digan algo que encaje con la consigna "
                            f"antes de que se acabe la mecha. {BOMBA_LIVES} vidas cada uno; "
                            "si les explota tres veces, quedan afuera. ¡El último en pie gana!")
        await bb_next_prompt(room, new_prompt=True)
        return
    if room["game"] == "misterio":
        room["misterio"] = {"lives": {p["id"]: MISTERIO_LIVES for p in room["players"]
                                      if not p.get("gone") and not p.get("spectator")},
                            "solved": {}, "used": set(), "case": None, "case_idx": -1}
        await narrate(room, "¡Arranca Resolver el misterio! Les cuento un caso y todos "
                            "tiran su teoría a la vez. El primero en resolver "
                            f"{MISTERIO_TO_WIN} casos gana. {MISTERIO_LIVES} vidas cada uno.")
        await mst_next_case(room)
        return
    if room["game"] == "ahorcado":
        room["ahorcado"] = {"levels": {}, "used": set(), "word": None, "hint": "",
                            "guessed": set(), "wrong": set(), "attempts": 0}
        await narrate(room, f"¡Arranca el ahorcado! Adiviná la palabra letra por letra. "
                            f"Si errás, pasa al siguiente. "
                            f"El primero en llegar al nivel {AHORCADO_WIN_LEVEL + 1} gana.")
        await begin_turn(room)
        return
    if room["game"] == "categorias":
        room["cat_progress"] = {}
    player = current_player(room)
    if player is None:
        return
    if room["game"] == "categorias":
        await narrate(room, f"¡Arranca la partida {room['match']}! El primero en pasar "
                            f"{CATEGORIES_TO_PASS} categorías gana: con {QUESTIONS_PER_LEVEL} "
                            f"correctas pasás cada categoría. Tenés cuatro vidas. Empieza {player['name']}.")
    else:
        await narrate(room, f"¡Arranca la partida {room['match']}! El primero en llegar a "
                            f"{WIN_SCORE} puntos gana. Empieza {player['name']}.")
    await begin_turn(room)


async def end_turn(room):
    """Resolve the turn: check the winner, else pass to the next player."""
    cancel_timer(room)
    room["question"] = None
    room["spinning"] = False
    winner = next(
        (p for p in room["players"] if not p.get("gone") and room["scores"].get(p["id"], 0) >= WIN_SCORE),
        None,
    )
    if winner is not None:
        await game_over(room, winner)
        return
    room["turn"] += 1
    await begin_turn(room)


async def game_over(room, winner):
    room["phase"] = "gameover"
    if room.get("team_count"):
        winner_name = "el equipo " + TEAM_NAMES[winner["team"]]
    else:
        winner_name = winner["name"]
    others = [p["name"] for p in room["players"] if not p.get("gone") and not p.get("spectator") and p["id"] != winner["id"]
              and (not room.get("team_count") or p.get("team") != winner.get("team"))]
    beat = ""
    if len(others) == 1:
        beat = f" Le ganó a {others[0]}."
    elif others:
        beat = " Le ganó a " + ", a ".join(others[:-1]) + " y a " + others[-1] + "."
    await narrate(room, f"¡Ganó {winner_name} con {room['scores'].get(winner['id'], 0)} puntos!{beat} "
                        f"En {REMATCH_SECONDS} segundos arranca una partida nueva.")
    await broadcast(room, room_state(room))
    await asyncio.sleep(REMATCH_SECONDS)
    active = [p for p in room["players"] if not p.get("gone") and not p.get("spectator")]
    if not active:
        return
    # The starter rotates: the winner never starts twice in a row by default.
    room["starter"] = (room["starter"] + 1) % len(active)
    room["match"] += 1
    await start_match(room)


async def do_category_spin(room, player, chosen=None):
    """The wheel lands on a category (random unless the player picked one)."""
    cancel_timer(room)
    room["spinning"] = True
    if room["game"] == "paises":
        pool = [c for c in MC_BANKS if c not in room["country_done"]]
    else:
        progress = room.get("cat_progress", {}).get(score_owner(room, player), {})
        pool = [c for c in CATEGORIES
                if c == "verdad_reto" or progress.get(c, 0) < QUESTIONS_PER_LEVEL]
    cat = chosen or random.choice(pool)
    labels = [CATEGORIES[c] for c in pool]
    await broadcast(room, {
        "event": "spin_start", "player": player["name"],
        "angle": random.randint(0, 359),
        "labels": labels, "colors": None,
    })
    await asyncio.sleep(3.5)
    room["spinning"] = False
    if cat == "verdad_reto":
        await narrate(room, "¡Giramos la ruleta! Gira, gira... ¡paró! ¡Verdad o Reto!")
        room["phase"] = "verdad_reto_ready"
        await broadcast(room, room_state(room))
        await do_spin(room, player)
        return
    room["phase"] = "question"
    where = f", por {room['country']}" if room.get("country") else ""
    await ask_question(room, player, cat, where)


async def do_country_spin(room, player):
    """La ruleta de países: lands the country the room plays for."""
    from app import TRIVIA_COUNTRIES

    cancel_timer(room)
    room["spinning"] = True
    await broadcast(room, {
        "event": "spin_start", "player": player["name"],
        "angle": random.randint(0, 359), "labels": None, "colors": None,
    })
    await asyncio.sleep(3.5)
    country = random.choice(TRIVIA_COUNTRIES)
    room["country"] = country
    room["country_done"] = set()
    room["spinning"] = False
    await narrate(room, f"¡Gira la ruleta de países! Gira, gira... ¡paró! ¡{country}! "
                        f"Para ganar {country} hay que completar todas las categorías. "
                        f"Arranca {player['name']}.")
    # The first category follows the country automatically. No hidden second step.
    room["phase"] = "category_spinning"
    await broadcast(room, room_state(room))
    await narrate(room, f"{player['name']}, ahora giramos automáticamente la primera categoría de {country}. "
                  "No tenés que tocar otro botón. Después escuchás la pregunta y sus cuatro opciones.")
    await do_category_spin(room, player)


async def do_spin(room, player):
    """Verdad o Reto: the wheel spins, then the card is read aloud."""
    cancel_timer(room)
    room["spinning"] = True
    segment = random.choice(SEGMENTS)
    bank, used = (RETOS, room["used_retos"]) if segment == "reto" else (VERDADES, room["used_verdades"])
    available = [item for item in bank if item not in used]
    if not available:
        used.clear()
        available = list(bank)
    pick = random.choice(available)
    used.add(pick)
    angle = random.randint(0, 359)
    await broadcast(room, {
        "event": "spin_start", "player": player["name"], "angle": angle,
        "segment": segment,
        "colors": [SEGMENT_COLORS[s] for s in SEGMENTS],
        "labels": [SEGMENT_LABELS[s] for s in SEGMENTS],
    })
    label = SEGMENT_LABELS[segment]
    announce = (
        f"¡Giramos la ruleta! Gira, gira... ¡paró! ¡{player['name']}, te salió {label}! "
        f"{label} para {player['name']}: {pick}"
    )
    await asyncio.sleep(3.5)  # the wheel spins ~4s; the voice lands as it stops
    await narrate(room, announce)
    room["phase"] = "verdad_reto"
    await tell(player, {"event": "await_done", "card": pick, "label": label})
    await broadcast(room, room_state(room))


def public_question(room):
    q = room.get("question")
    if not q or room["phase"] != "question":
        return None
    player = current_player(room)
    return {"event": "question", "id": q.get("id"), "category": q["category"],
            "q": q["q"], "options": q["options"], "player": player["id"] if player else None,
            "audio": q.get("audio"), "audio_ready": q.get("audio_ready", False),
            "clock_started": q.get("clock_started", False)}


async def start_question_clock(room, player, question_id):
    q = room.get("question")
    if (room["phase"] != "question" or not q or q.get("id") != question_id
            or current_player(room) is not player or q.get("clock_started")):
        return
    q["clock_started"] = True
    cancel_timer(room)
    await broadcast(room, {"event": "question_clock", "id": question_id, "seconds": TURN_SECONDS})
    room["timer_task"] = asyncio.create_task(turn_clock(room, player["id"]))


async def ask_question(room, player, category, where=""):
    cancel_timer(room)
    run = room.get("quiz_run")
    if not run or run["player"] != player["id"] or run["category"] != category:
        run = new_quiz_run(room, player, category)
    question, options, correct = pick_mc(room, category)
    options = list(options)
    correct_text = options[correct]
    random.shuffle(options)
    correct = options.index(correct_text)
    room["question_seq"] = room.get("question_seq", 0) + 1
    qid = room["question_seq"]
    room["question"] = {"id": qid, "category": category, "q": question, "options": options,
                        "correct": correct, "clock_started": False, "audio_ready": False}
    room["phase"] = "question"
    # Text and controls arrive before any slow voice request. No clock yet.
    await broadcast(room, public_question(room))
    await broadcast(room, room_state(room))
    spoken = question + " " + " ".join(f"{opt}." for opt in options)
    life_count = quiz_lives(room, player)
    await narrate(room, f"Categoría {CATEGORIES[category]}{where}, para {player['name']}. "
                  f"Llevás {run['correct']} de 5 correctas. "
                  f"Tenés {life_count} {'vida' if life_count == 1 else 'vidas'}. {spoken}",
                  voice=room["question_voice"], question_id=qid)
    # The owning browser arms the clock after playback, or its explicit button.


QUIZ_START_LIVES = 4
QUIZ_RUN_LENGTH = 5


def quiz_lives(room, player):
    """Lives are personal, including when category progress belongs to a team."""
    return room.setdefault("quiz_lives", {}).setdefault(player["id"], QUIZ_START_LIVES)


def new_quiz_run(room, player, category):
    run = {"player": player["id"], "owner": score_owner(room, player),
           "category": category, "answered": 0, "correct": 0, "mistakes": 0, "streak": 0}
    room["quiz_run"] = run
    quiz_lives(room, player)
    return run


def record_quiz_answer(room, player, correct):
    """Pure bookkeeping; progression/zero-life rules remain with the caller."""
    run = room["quiz_run"]
    if run["player"] != player["id"]:
        raise ValueError("answer does not belong to the active category run")
    run["answered"] += 1
    if correct:
        run["correct"] += 1
        run["streak"] = run.get("streak", 0) + 1
    else:
        run["streak"] = 0
        run["mistakes"] += 1
        room["quiz_lives"][player["id"]] = max(0, quiz_lives(room, player) - 1)
    return run


def quiz_bonus(room, player):
    run = room["quiz_run"]
    if run.get("streak", 0) >= QUIZ_RUN_LENGTH and not run.get("bonus_given"):
        room["quiz_lives"][player["id"]] = min(4, quiz_lives(room, player) + 1)
        run["bonus_given"] = True
        return True
    return False


async def resolve_answer(room, player, idx):
    question = room.get("question")
    if not question or room["phase"] != "question":
        return
    # Close this question before awaiting narration, preventing duplicate submissions.
    room["phase"] = "answering"
    cancel_timer(room)
    if not room.get("quiz_run"):
        new_quiz_run(room, player, question["category"])
    correct = idx == question["correct"]
    run = record_quiz_answer(room, player, correct)
    if correct:
        await narrate(room, f"¡Correcto, {player['name']}! Llevás {run['correct']} de 5 correctas.")
    else:
        letters = ["A", "B", "C", "D"]
        right = question["options"][question["correct"]]
        picked = letters[idx] if 0 <= idx < len(letters) else "sin respuesta"
        lives = quiz_lives(room, player)
        await narrate(room, f"{player['name']}, la {picked} no es la correcta. "
                      f"Es la {letters[question['correct']]}: {right}. "
                      f"Perdiste una vida, te quedan {['cero', 'una', 'dos', 'tres', 'cuatro'][lives]}.")
        if lives == 0:
            room["quiz_lives"][player["id"]] = QUIZ_START_LIVES
            player.pop("out", None)
            if not room.get("team_count"):
                room.setdefault("cat_progress", {}).pop(player["id"], None)
                room["countries_won"].pop(player["id"], None)
                room["scores"][player["id"]] = 0
                room["country"] = None
                room["country_done"] = set()
            reset_text = ("Tu equipo conserva sus niveles. Vos reiniciás con cuatro vidas. "
                          if room.get("team_count") else "Volvés al principio, nivel uno, con cuatro vidas. ")
            await narrate(room, f"{player['name']}, te quedaste sin vidas. " + reset_text + "Girá la ruleta de nuevo.")
            await begin_turn(room)
            return
    if run["correct"] >= 5:
        if quiz_bonus(room, player):
            await narrate(room, f"¡Cinco correctas seguidas! Ganaste una vida, te regalamos una. "
                          f"Tenés {quiz_lives(room, player)}; el máximo es cuatro.")
        category = run["category"]
        await narrate(room, f"¡{player['name']} pasó el nivel de {CATEGORIES[category]}!")
        if room["game"] == "paises":
            room["country_done"].add(category)
            if len(room["country_done"]) >= len(MC_BANKS):
                owner = score_owner(room, player)
                won = room["countries_won"].get(owner, 0) + 1
                room["countries_won"][owner] = won
                sync_score(room, player, won)
                country = room["country"]
                room["country"] = None
                room["country_done"] = set()
                await narrate(room, f"¡{player['name']} completó {country}!")
                if won >= COUNTRIES_TO_WIN:
                    await game_over(room, player)
                    return
            else:
                await narrate(room, f"Pasó al nivel {len(room['country_done']) + 1}. Seguís, {player['name']}.")
            await begin_turn(room)
        else:
            progress = room.setdefault("cat_progress", {}).setdefault(score_owner(room, player), {})
            progress[category] = QUESTIONS_PER_LEVEL
            passed = sum(n >= QUESTIONS_PER_LEVEL for n in progress.values())
            sync_score(room, player, passed)
            if passed >= CATEGORIES_TO_PASS:
                await game_over(room, player)
                return
            await end_turn(room)
        return
    await ask_question(room, player, run["category"], f", por {room['country']}" if room.get("country") else "")


async def complete_verdad_reto(room, player, done):
    if done:
        sync_score(room, player, room["scores"].get(player["id"], 0) + 1)
        await narrate(room, f"¡Muy bien, {player['name']}! Un punto. Lleva {room['scores'][player['id']]}.")
    else:
        await narrate(room, f"{player['name']} pasa. Sin punto esta vez.")
    await end_turn(room)


# ---------------------------------------------------------------------------
# El Ahorcado web: letter-by-letter word guessing, turns pass on a miss.
# ---------------------------------------------------------------------------
AHORCADO_WIN_LEVEL = 5
AH_ORDINALES = ["primer", "segundo", "tercer", "cuarto", "quinto",
                "sexto", "séptimo", "octavo", "noveno", "décimo"]


def ah_helpers():
    from app import (AHORCADO_BANK, AHORCADO_SPEAK, ahorcado_attempts_for,
                     ahorcado_band, ahorcado_clean, ahorcado_parse_guess)
    return AHORCADO_BANK, AHORCADO_SPEAK, ahorcado_attempts_for, ahorcado_band, ahorcado_clean, ahorcado_parse_guess


def ah_board(word, guessed):
    return " ".join(char if char in guessed else "_" for char in word)


def ah_spelled(word, speak):
    return ", ".join(speak[char] for char in word)


def ah_positions_text(word, letter, speak):
    """'La palabra lleva dos letras A: una en el primer casillero y otra en el segundo.'"""
    positions = [i for i, char in enumerate(word) if char == letter]
    name = speak[letter]
    if len(positions) == 1:
        return f"La palabra lleva una letra {name}, en el {AH_ORDINALES[positions[0]]} casillero."
    places = ", ".join(f"una en el {AH_ORDINALES[p]} casillero" for p in positions[:-1])
    places += f" y otra en el {AH_ORDINALES[positions[-1]]} casillero"
    return f"La palabra lleva {len(positions)} letras {name}: {places}."


def ah_adjacency_text(word, letter, guessed, speak):
    """'La A y la T están juntas.' for newly revealed neighbours."""
    pairs = []
    for i, char in enumerate(word):
        if char != letter:
            continue
        if i + 1 < len(word) and word[i + 1] in guessed:
            pair = (word[i], word[i + 1])
            if pair not in pairs:
                pairs.append(pair)
        if i - 1 >= 0 and word[i - 1] in guessed and word[i - 1] != letter:
            pair = (word[i - 1], word[i])
            if pair not in pairs:
                pairs.append(pair)
    return " ".join(f"La {speak[a]} y la {speak[b]} están juntas." for a, b in pairs)


async def ah_start_turn(room):
    """Deal a word at the current player's level and arm the clock."""
    _, _, attempts_for, band, _, _ = ah_helpers()
    cancel_timer(room)
    room["question"] = None
    player = current_player(room)
    if player is None:
        return
    ah = room["ahorcado"]
    level = ah["levels"].get(player["id"], 1)
    bank, _, _, _, _, _ = ah_helpers()
    lo, hi = band(level)
    choices = [(w, h) for w, h in bank if lo <= len(w) <= hi and w not in ah["used"]]
    if not choices:
        ah["used"] = {w for w in ah["used"] if not (lo <= len(w) <= hi)}
        choices = [(w, h) for w, h in bank if lo <= len(w) <= hi]
    word, hint = random.choice(choices)
    ah["used"].add(word)
    ah.update(word=word, hint=hint, guessed=set(), wrong=set(),
              attempts=attempts_for(word))
    room["phase"] = "ahorcado"
    await narrate(room, f"Turno de {player['name']}, nivel {level}. "
                        f"La palabra tiene {len(word)} letras. Pista: {hint} "
                        f"Tenés {ah['attempts']} intentos. Decí una letra o arriesgá la palabra.")
    await broadcast(room, room_state(room))
    await tell(player, {"event": "your_turn", "kind": "ahorcado"})
    room["timer_task"] = asyncio.create_task(turn_clock(room, player["id"]))


async def ah_pass(room, reason):
    """A miss: tell everyone, then the word/turn passes to the next player."""
    room["turn"] += 1
    nxt = current_player(room)
    await narrate(room, reason + (f" Ahora sigue {nxt['name']}." if nxt else ""))
    await ah_start_turn(room)


async def ah_guess(room, player, guess):
    """guess = ('letter', 'E') | ('word', 'PALABRA')."""
    bank, speak, _, _, clean, _ = ah_helpers()
    ah = room["ahorcado"]
    word = ah["word"]
    kind, value = guess
    if kind == "letter":
        if value in ah["guessed"] or value in ah["wrong"]:
            await narrate(room, f"La {speak[value]} ya salió, {player['name']}. Probá otra.")
            return
        if value in word:
            ah["guessed"].add(value)
            if all(char in ah["guessed"] for char in word):
                await ah_solved(room, player)
                return
            positions = ah_positions_text(word, value, speak)
            adjacency = ah_adjacency_text(word, value, ah["guessed"], speak)
            spoken_board = ", ".join(speak[c] if c in ah["guessed"] else "vacío" for c in word)
            await narrate(room, f"¡Sí! {positions} {adjacency} "
                                f"Así va: {spoken_board}. "
                                f"Seguís, {player['name']}.")
            await broadcast(room, room_state(room))
            return
        ah["wrong"].add(value)
        ah["attempts"] -= 1
        miss_beat = random.choice(["Uh, pifiaste. ", "¡Uy, no! ", "Esa no era, che. "])
        if ah["attempts"] <= 0:
            await ah_pass(room, miss_beat + f"No hay {speak[value]} y se te acabaron los intentos, "
                                f"{player['name']}. La palabra era {ah_spelled(word, speak)}.")
            return
        left = ah["attempts"]
        await ah_pass(room, miss_beat + f"No hay {speak[value]}. Te {'queda' if left == 1 else 'quedan'} "
                            f"{left} {'intento' if left == 1 else 'intentos'}, {player['name']}.")
        return
    # whole-word guess
    if value == word:
        await ah_solved(room, player)
        return
    ah["attempts"] -= 1
    if ah["attempts"] <= 0:
        await ah_pass(room, f"¡{ah_spelled(value, speak)} no es y se te acabaron los intentos, "
                            f"{player['name']}! La palabra era {ah_spelled(word, speak)}.")
        return
    left = ah["attempts"]
    await ah_pass(room, f"{ah_spelled(value, speak)} no es. Te {'queda' if left == 1 else 'quedan'} "
                        f"{left} {'intento' if left == 1 else 'intentos'}, {player['name']}.")


async def ah_solved(room, player):
    """Solved the word: level up, tell the room where everyone stands."""
    ah = room["ahorcado"]
    level = ah["levels"].get(player["id"], 1) + 1
    ah["levels"][player["id"]] = level
    room["scores"][player["id"]] = level - 1
    others = [p for p in room["players"] if not p.get("gone") and p["id"] != player["id"]]
    standing = ""
    if others:
        otros_niveles = {ah["levels"].get(p["id"], 1) for p in others}
        if len(otros_niveles) == 1:
            standing = f"; ustedes están en el nivel {otros_niveles.pop()}"
    if level > AHORCADO_WIN_LEVEL:
        room["phase"] = "ahorcado"  # coherent until game_over
        await game_over(room, player)
        return
    await narrate(room, f"¡{player['name']} adivinó la palabra! "
                        f"{player['name']} pasó al nivel {level}{standing}.")
    room["turn"] += 1
    await ah_start_turn(room)


# ---------------------------------------------------------------------------
# La bomba + Resolver el misterio (V3.3)
# ---------------------------------------------------------------------------
BOMBA_LIVES = 3
BOMBA_FUSE_MIN = 8
BOMBA_FUSE_MAX = 20
MISTERIO_LIVES = 3
MISTERIO_TO_WIN = 2

# (prompt, accepted answers). Association game: say one valid item, bomb passes.
BOMBA_PROMPTS = [
    ("Cosas que encontrás en una cocina", ["cuchara", "tenedor", "cuchillo", "plato", "olla", "sarten", "heladera", "horno", "microondas", "vaso", "taza", "mantel", "servilleta", "tabla", "colador", "rallador", "batidora", "tostadora", "jarra", "sal", "azucar", "aceite", "pava", "cafetera", "mate"]),
    ("Animales que viven en el campo", ["vaca", "caballo", "oveja", "cerdo", "gallina", "gallo", "cabrito", "cabra", "burro", "pato", "ganso", "toro", "ternero", "yegua", "potrillo", "perro", "gato", "zorro", "liebre", "ñandu", "hornero"]),
    ("Cosas que llevás a la playa", ["reposera", "sombrilla", "toalla", "protector", "bronceador", "anteojos", "lentes", "pelota", "paleta", "balde", "pala", "traje de baño", "malla", "ojotas", "heladerita", "agua", "terere", "mate", "gorra", "sombrero", "pareo", "flotador"]),
    ("Palabras que riman con amor", ["dolor", "calor", "flor", "color", "valor", "temor", "favor", "rumor", "ardor", "candor", "honor", "mejor", "peor", "sol", "corazon", "cancion", "pasión", "ilusion", "beso", "dulce", "sentimiento"]),
    ("Cosas rojas", ["manzana", "tomate", "fresa", "frutilla", "cereza", "rosa", "sangre", "fuego", "semáforo", "auto", "camioneta", "labial", "pimiento", "morron", "sandia", "corazon", "ladrillo", "camisa", "remera", "bandera", "amapola", "pimiento"]),
    ("Profesiones", ["maestra", "maestro", "doctor", "doctora", "medico", "enfermera", "enfermero", "policia", "bombero", "cocinero", "panadero", "carpintero", "plomero", "electricista", "abogado", "contador", "ingeniero", "arquitecto", "veterinario", "peluquero", "taxista", "colectivero", "kiosquero", "albañil", "mecanico", "futbolista", "cantante", "actor", "periodista", "mozo", "cajero"]),
    ("Cosas que hacen ruido", ["timbre", "telefono", "alarma", "bocina", "claxon", "trueno", "perro", "gato", "bebé", "tele", "radio", "licuadora", "taladro", "martillo", "moto", "colectivo", "tren", "avion", "viento", "lluvia", "tormenta", "fuegos artificiales", "cortina", "puerta", "timbre", "sirena", "ambulancia", "grito", "aplauso", "tambor", "guitarra"]),
    ("Comidas con queso", ["pizza", "empanadas", "milanesa", "napolitana", "hamburguesa", "lasagna", "fideos", "ñoquis", "ravioles", "sorrentinos", "tarta", "tostado", "sandwich", "provoleta", "faina", "quesadilla", "omelette", "tortilla", "chips", "pancho", "canelones"]),
    ("Cosas del mate", ["yerba", "bombilla", "pava", "termo", "agua", "azucar", "mate", "calabaza", "yerbera", "cebador", "bandeja", "facturas", "yerba mate"]),
    ("Animales que vuelan", ["pajaro", "paloma", "gaviota", "aguila", "halcon", "buitre", "cóndor", "loro", "cotorra", "lechuza", "buho", "colibri", "golondrina", "hornero", "carpintero", "flamenco", "cigueña", "murcielago", "mariposa", "abeja", "avispa", "mosca", "mosquito", "libelula", "avion", "helicoptero", "papagayo", "tucan"]),
    ("Cosas que hay en una escuela", ["banco", "pizarron", "tiza", "marcador", "cuaderno", "lapiz", "goma", "regla", "mochila", "libro", "carpeta", "maestra", "alumnos", "patio", "bandera", "campana", "timbre", "silla", "escritorio", "borrador", "sacapuntas", "cartuchera", "aula", "biblioteca", "guardapolvo"]),
    ("Palabras con la letra Ñ", ["niño", "niña", "mañana", "año", "baño", "araña", "montaña", "caña", "ñandu", "ñu", "ñato", "ñato", "ñoqui", "cabaña", "tacaño", "paño", "sueño", "otoño", "seño", "ñanduti"]),
    ("Cosas que se hacen de noche", ["dormir", "soñar", "cenar", "ver tele", "salir", "bailar", "asado", "mirar las estrellas", "contar ovejas", "roncar", "darle de comer al perro", "apagar la luz", "leer", "juntada", "previa", "cine", "pasear", "estudiar", "fiesta"]),
    ("Equipos de fútbol", ["river", "boca", "independiente", "racing", "san lorenzo", "estudiantes", "gimnasia", "velez", "huracan", "argentinos", "lanus", "banfield", "talleres", "belgrano", "newells", "rosario central", "colon", "union", "atletico tucuman", "defensa", "barracas"]),
    ("Cosas dulces", ["chocolate", "alfajor", "helado", "flan", "dulce de leche", "torta", "facturas", "medialuna", "churros", "budin", "galletitas", "caramelos", "chupetin", "turrón", "mermelada", "miel", "azucar", "pastelitos", "rogel", "lemon pie", "brownie", "panqueque"]),
    ("Cosas que hay en un auto", ["volante", "ruedas", "asientos", "espejo", "espejos", "cinturon", "freno", "acelerador", "embrague", "palanca", "cambios", "tablero", "radio", "parlantes", "airbag", "baul", "capot", "motor", "limpiaparabrisas", "luces", "patente", "llanta", "auxilio", "puertas", "vidrios"]),
    ("Cosas del verano", ["calor", "sol", "playa", "pileta", "helado", "terere", "ventilador", "aire acondicionado", "sandia", "melon", "malla", "ojotas", "anteojos", "protector", "vacaciones", "asado", "siesta", "sudor", "chicharra"]),
    ("Cosas que hay en un cumpleaños", ["torta", "velas", "velitas", "globos", "regalos", "piñata", "cotillon", "cumpleañero", "invitados", "cancion", "feliz cumpleaños", "abrazo", "beso", "souvenir", "gaseosa", "pizza", "empanadas", "sándwich", "fotos", "sombrerito"]),
    ("Animales de la granja", ["vaca", "caballo", "oveja", "cerdo", "chancho", "gallina", "gallo", "pato", "ganso", "cabra", "burro", "conejo", "perro", "gato", "toro", "ternero", "pollito", "pavo", "mula"]),
    ("Cosas que se pueden morder", ["manzana", "pan", "carne", "asado", "pizza", "empanada", "galletita", "chicle", "uña", "labio", "lapiz", "helado", "chocolate", "banana", "sandia", "durazno", "pera", "milanesa", "factura", "medialuna", "tostada", "caramelo", "turrón", "hueso"]),
    ("Cosas que hay en el living", ["sillon", "sofa", "mesa", "tele", "control remoto", "lampara", "cuadro", "alfombra", "cortinas", "ventana", "estufa", "aire", "ventilador", "parlantes", "revistas", "almohadones", "silla", "estante", "plantas", "fotos", "adornos"]),
    ("Cosas que se hacen con agua", ["tomar", "beber", "mate", "cocinar", "hervir", "lavar", "bañarse", "ducharse", "regar", "nadar", "pescar", "lavar los platos", "limpiar", "fregar", "hielo", "llenar el termo", "sopa", "te", "cafe"]),
    ("Cosas de madera", ["mesa", "silla", "puerta", "ventana", "ropero", "placard", "estante", "cama", "banco", "lapiz", "paleta", "bocha", "madero", "leño", "tronco", "tabla", "escalera", "piso", "deck", "cajon", "mango"]),
    ("Palabras que empiezan con M", ["mate", "mesa", "mano", "madre", "mujer", "miedo", "mar", "montaña", "musica", "milanesa", "mono", "moto", "mochila", "martes", "marzo", "mayo", "mermelada", "menta", "melon", "mosca", "mundo", "museo", "mujer", "manta"]),
    ("Cosas que se compran en el kiosco", ["caramelos", "chicles", "chocolate", "alfajor", "galletitas", "puchos", "cigarrillos", "fosforos", "encendedor", "gaseosa", "agua", "jugo", "diario", "revista", "pilas", "sube", "tarjeta", "papas", "manies", "chupetin", "helado"]),
    ("Cosas que hay en un casamiento", ["novia", "novio", "iglesia", "anillos", "vestido", "traje", "fiesta", "salon", "torta", "vals", "ramo", "liga", "cotillon", "carnaval carioca", "invitados", "madrina", "padrino", "testigos", "curas", "arroz", "brindis", "champan", "fotografo", "dj", "musica", "baile"]),
    ("Cosas que se prenden fuego", ["papel", "madera", "leño", "fosforo", "vela", "asado", "carbon", "pasto", "basura", "cigarro", "cortina", "cocina", "aceite", "fuegos artificiales", "espuma", "goma", "plastico", "tela", "paja"]),
    ("Cosas que huelen rico", ["asado", "cafe", "pan", "facturas", "flores", "jazmin", "rosa", "perfume", "jazmin del pais", "tilo", "lavanda", "lluvia", "pasto cortado", "torta", "chocolate", "vainilla", "canela", "carne", "milanesas", "pizza", "bebe", "ropa limpia", "jabon"]),
    ("Cosas que se hacen los domingos", ["asado", "dormir hasta tarde", "pastas", "fideos", "ñoquis", "familia", "futbol", "ver la tele", "siesta", "pasear", "iglesia", "mate", "vermut", "picada", "visitas", "descansar", "plaza", "parque", "helado", "preparar la semana"]),
    ("Cosas que se tiran al agua", ["piedra", "moneda", "botella", "basura", "anzuelo", "red", "salvavidas", "flotador", "pelota", "perro", "bomba", "buzo", "ancla", "pez", "miguitas", "pan"]),
]

# Pre-written mysteries: (título, caso narrado, solución, claves-acierto, claves-cerca)
MISTERIOS = [
    ("El paquete cerrado",
     "Un hombre aparece muerto en medio de un campo. No hay huellas, no hay armas, no hay nadie cerca. "
     "Junto al cuerpo hay un paquete cerrado. ¿Qué pasó?",
     "Es un paracaidista: el paquete es el paracaídas, que no se abrió, y se mató en la caída.",
     ["paracaidas", "paracaidista", "avion", "se tiro", "salto"],
     ["cielo", "aire", "cayó", "caída", "volaba", "altura"]),
    ("El vaso de agua",
     "Un hombre entra a un bar y pide un vaso de agua. El barman, en vez de servirle, saca una escopeta y le apunta. "
     "El hombre dice gracias y se va tranquilo. ¿Por qué?",
     "El hombre tenía hipo. El barman lo entendió y le sacó el hipo con el susto, por eso no necesitó el agua.",
     ["hipo"],
     ["susto", "miedo", "asustar", "sacar el hipo"]),
    ("La música paró",
     "La música se detuvo y ella murió. ¿Qué pasó?",
     "Era una equilibrista del circo: caminaba por la cuerda floja guiándose por la música. "
     "Cuando la música paró antes de tiempo, perdió el equilibrio y se cayó.",
     ["cuerda floja", "equilibrista", "circo", "trapecista", "funambula", "se cayo"],
     ["circo", "cuerda", "altura", "cayó", "música", "payaso"]),
    ("Cincuenta y tres bicicletas",
     "Encuentran a un hombre muerto en una habitación con cincuenta y tres bicicletas. ¿Qué pasó?",
     "Las bicicletas son cartas de juego de la marca Bicycle. Estaba jugando a las cartas, "
     "lo descubrieron haciendo trampa con una carta de más y lo mataron.",
     ["cartas", "baraja", "trampa", "jugando", "poker", "naipes"],
     ["juego", "jugadores", "apuesta", "casino"]),
    ("El ascensor",
     "Un hombre vive en el décimo piso. Todos los días baja en ascensor hasta la planta baja para ir a trabajar. "
     "Cuando vuelve, sube en ascensor hasta el séptimo piso y los otros tres pisos sube por la escalera. "
     "Los días de lluvia, en cambio, sube en ascensor hasta el décimo. ¿Por qué?",
     "Es una persona muy bajita: en el ascensor solo llega al botón del séptimo piso. "
     "Los días de lluvia lleva paraguas y con él aprieta el botón del décimo.",
     ["bajito", "enano", "no llega al boton", "no alcanza", "paraguas"],
     ["altura", "botón", "botones", "dedos", "lluvia", "escalera"]),
    ("Antonio y Cleopatra",
     "Antonio y Cleopatra aparecen muertos en el piso de una casa, entre agua y vidrios rotos. "
     "No hay heridas en los cuerpos. ¿Qué pasó?",
     "Antonio y Cleopatra son dos peces: su pecera se cayó al piso y se rompió, y murieron fuera del agua.",
     ["peces", "pecera", "pez", "se cayo la pecera", "acuario"],
     ["agua", "vidrio", "acuario", "se rompió", "asfixia"]),
    ("El faro",
     "Un hombre vive solo en un faro. Una noche apaga todas las luces y se va a dormir. "
     "A la mañana siguiente lee el diario y se suicida. ¿Por qué?",
     "Es el farero: al apagar la luz del faro, un barco se estrelló contra las rocas y murió gente. "
     "La noticia salió en el diario.",
     ["faro", "barco", "naufragio", "se estrello", "choco", "encallo"],
     ["luz", "rocas", "mar", "muertos", "noticia", "culpa"]),
    ("La caja cerrada",
     "Un hombre empuja su auto hasta llegar frente a un hotel y dice en voz alta: ¡Me fundí, estoy en bancarrota! ¿Qué pasó?",
     "Está jugando al Monopoly: el auto es su ficha, el hotel es del contrario y cayó en su casillero, "
     "así que debe pagar más de lo que tiene.",
     ["monopoly", "juego", "ficha", "jugando"],
     ["juego de mesa", "casillero", "tablero", "deuda", "pagó"]),
]


def norm(text: str) -> str:
    """Lowercase, strip accents and punctuation: for keyword matching."""
    import re
    import unicodedata
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return re.sub(r" +", " ", re.sub(r"[^a-zñ0-9 ]", " ", t)).strip()


def kw_hit(text: str, keywords) -> bool:
    t = " " + norm(text) + " "
    return any(" " + norm(k) + " " in t for k in keywords)


async def judge_yes_no(system_prompt: str, user_prompt: str, fallback):
    """Groq LLM judging; on any failure use the keyword fallback.

    Only game text goes to Groq: the prompt, the reference answer and the
    player's answer. Nothing personal is sent. The model answers SI or NO.
    """
    import os
    import httpx
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return fallback()
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": os.environ.get("GROQ_JUDGE_MODEL", "llama-3.1-8b-instant"),
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0,
                    "max_tokens": 5,
                },
                timeout=15,
            )
            if r.status_code < 400:
                verdict = norm(r.json()["choices"][0]["message"]["content"])
                if "si" in verdict.split():
                    return True
                if "no" in verdict.split():
                    return False
            log.warning("Web sala: Groq judge failed: %s", getattr(r, "status_code", "?"))
    except Exception:
        log.exception("Web sala: Groq judge error")
    return fallback()


JUDGE_BOMBA_SYSTEM = (
    "Sos el juez de un juego de asociación de palabras. Te doy una consigna y la respuesta "
    "de un jugador. Respondé únicamente SI si la respuesta encaja con la consigna (aceptá "
    "sinónimos y variantes razonables) o NO si no encaja. Nada más que SI o NO."
)
JUDGE_MISTERIO_SYSTEM = (
    "Sos el juez de un juego de misterios. Te doy la solución completa del caso y la "
    "respuesta de un jugador. Respondé con una sola palabra: ACIERTO si el jugador dio "
    "con la solución o su idea central, CERCA si va bien encaminado pero le falta una parte, "
    "o LEJOS si no tiene nada que ver. Nada más que esa palabra."
)


async def judge_bomba(prompt: str, answer: str, keywords):
    """True = the association is valid."""
    if kw_hit(answer, keywords):
        return True  # the local list settles it without spending a Groq call
    return await judge_yes_no(
        JUDGE_BOMBA_SYSTEM,
        f"Consigna: {prompt}\nRespuesta del jugador: {answer}\n¿Encaja?",
        lambda: False,
    )


async def judge_misterio(solution: str, guess: str, hit_keys, near_keys):
    """'acierto' | 'cerca' | 'lejos'. Groq first, keyword fallback."""
    import os
    import httpx
    if kw_hit(guess, hit_keys):
        return "acierto"
    if kw_hit(guess, near_keys):
        return "cerca"
    key = os.environ.get("GROQ_API_KEY", "")
    if key:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": os.environ.get("GROQ_JUDGE_MODEL", "llama-3.1-8b-instant"),
                        "messages": [
                            {"role": "system", "content": JUDGE_MISTERIO_SYSTEM},
                            {"role": "user", "content":
                                f"Solución del caso: {solution}\n"
                                f"Respuesta del jugador: {guess}\n¿ACIERTO, CERCA o LEJOS?"},
                        ],
                        "temperature": 0,
                        "max_tokens": 5,
                    },
                    timeout=15,
                )
                if r.status_code < 400:
                    verdict = norm(r.json()["choices"][0]["message"]["content"])
                    for word in ("acierto", "cerca", "lejos"):
                        if word in verdict.split():
                            return word
                log.warning("Web sala: Groq misterio judge failed: %s", getattr(r, "status_code", "?"))
        except Exception:
            log.exception("Web sala: Groq misterio judge error")
    return "lejos"



MISTERIO_CASE_SECONDS = 150


async def end_match_nobody(room):
    """Everyone is out (bomba/misterio, e.g. a solo loss): close and rematch."""
    room["phase"] = "gameover"
    await narrate(room, f"¡Se terminó para todos! En {REMATCH_SECONDS} segundos arranca una partida nueva.")
    await broadcast(room, room_state(room))
    await asyncio.sleep(REMATCH_SECONDS)
    active = [p for p in room["players"] if not p.get("gone")]
    if not active:
        return
    room["starter"] = (room["starter"] + 1) % len(active)
    room["match"] += 1
    await start_match(room)


async def bb_next_prompt(room, new_prompt):
    """Arm a fresh fuse for the current bomb holder; optionally a fresh prompt."""
    bb = room["bomba"]
    cancel_timer(room)
    holder = current_player(room)
    if holder is None:
        return
    if new_prompt or bb["prompt"] is None:
        choices = [i for i in range(len(BOMBA_PROMPTS)) if i not in bb["used"]]
        if not choices:
            bb["used"] = set()
            choices = list(range(len(BOMBA_PROMPTS)))
        idx = random.choice(choices)
        bb["used"].add(idx)
        bb["prompt"], bb["keywords"] = BOMBA_PROMPTS[idx]
        bb["said"] = set()
        prompt_line = f"La consigna es: {bb['prompt']}."
    else:
        prompt_line = f"Sigue la consigna: {bb['prompt']}."
    bb["fuse"] = random.randint(BOMBA_FUSE_MIN, BOMBA_FUSE_MAX)
    room["phase"] = "bomba"
    await narrate(room, f"La bomba la tiene {holder['name']}. {prompt_line} ¡Decí una, rápido!")
    await broadcast(room, room_state(room))
    await tell(holder, {"event": "your_turn", "kind": "bomba"})
    room["timer_task"] = asyncio.create_task(bb_fuse_clock(room, holder["id"]))


async def wait_with_chatter(room, seconds):
    task = None
    try:
        remaining = seconds
        while remaining > 0:
            step = min(6, remaining)
            await asyncio.sleep(step)
            remaining -= step
            current = current_player(room)
            if remaining > 0 and current and (task is None or task.done()):
                task = asyncio.create_task(turn_chatter(room, current))
    finally:
        if task and not task.done():
            task.cancel()


async def bb_fuse_clock(room, holder_id):
    """The fuse: when it burns out with the same holder, the bomb explodes."""
    try:
        await wait_with_chatter(room, room["bomba"]["fuse"])
        if room["phase"] != "bomba":
            return
        holder = next((p for p in room["players"] if p["id"] == holder_id), None)
        if holder is not None and current_player(room) is holder:
            await bb_explode(room, holder, "¡Se acabó la mecha!")
    except asyncio.CancelledError:
        pass


async def bb_answer(room, player, text):
    """The holder's association: valid passes the bomb, invalid explodes it."""
    bb = room["bomba"]
    if room["phase"] != "bomba" or current_player(room) is not player:
        return
    answer = norm(text).strip()
    if not answer:
        return
    if answer in bb["said"]:
        await narrate(room, f"Esa ya la dijeron, {player['name']}. ¡Otra!")
        return
    if not await judge_bomba(bb["prompt"], text, bb["keywords"]):
        await bb_explode(room, player, f"¡{text.strip()} no vale!")
        return
    bb["said"].add(answer)
    room["turn"] += 1
    nxt = current_player(room)
    await narrate(room, f"¡Sí, vale! {player['name']} se salva." +
                  (f" ¡{nxt['name']}, la tenés vos!" if nxt else ""))
    await bb_next_prompt(room, new_prompt=False)


async def bb_explode(room, holder, reason):
    """Life loss; elimination at zero; last one standing wins."""
    bb = room["bomba"]
    cancel_timer(room)
    bb["lives"][holder["id"]] = bb["lives"].get(holder["id"], BOMBA_LIVES) - 1
    left = bb["lives"][holder["id"]]
    room["scores"][holder["id"]] = left
    await broadcast(room, {"event": "boom", "name": holder["name"]})
    if left > 0:
        await narrate(room, f"¡BOOM! {reason} {holder['name']} pierde una vida: le "
                            f"{'queda' if left == 1 else 'quedan'} {left}.")
    else:
        holder["out"] = True
        await narrate(room, f"¡BOOM! {reason} {holder['name']} pierde su última vida. "
                            f"¡{holder['name']} queda eliminado!")
    alive = [p for p in room["players"] if not p.get("gone") and not p.get("out")
             and not p.get("spectator")]
    if survivor_winner(room, alive):
        await game_over(room, survivor_winner(room, alive))
        return
    if not alive:
        await end_match_nobody(room)
        return
    room["turn"] += 1
    await bb_next_prompt(room, new_prompt=True)


async def mst_next_case(room):
    """Tell a new mystery and open the floor: everyone guesses at once."""
    mst = room["misterio"]
    cancel_timer(room)
    alive = [p for p in room["players"] if not p.get("gone") and not p.get("out")
             and not p.get("spectator")]
    if not alive:
        return
    choices = [i for i in range(len(MISTERIOS)) if i not in mst["used"]]
    if not choices:
        mst["used"] = set()
        choices = list(range(len(MISTERIOS)))
    idx = random.choice(choices)
    mst["used"].add(idx)
    mst["case"] = MISTERIOS[idx]
    mst["case_idx"] = idx
    title, case, _, _, _ = mst["case"]
    room["phase"] = "misterio"
    await narrate(room, f"Misterio nuevo: {title}. {case} "
                        "Escriban o digan su teoría. El que acierta gana el caso; "
                        "el que está lejos pierde una vida. Tienen dos minutos y medio.")
    await broadcast(room, room_state(room))
    room["timer_task"] = asyncio.create_task(mst_case_clock(room, idx))


async def mst_case_clock(room, case_idx):
    """Unsolved in time: reveal and move to the next case."""
    try:
        await wait_with_chatter(room, MISTERIO_CASE_SECONDS)
        if room["phase"] != "misterio" or room["misterio"]["case_idx"] != case_idx:
            return
        _, _, solution, _, _ = room["misterio"]["case"]
        await narrate(room, f"Se acabó el tiempo. La solución era: {solution}")
        await mst_next_case(room)
    except asyncio.CancelledError:
        pass


async def mst_guess(room, player, text):
    """A theory, judged: acierto wins the case, cerca is a hint, lejos costs a life."""
    mst = room["misterio"]
    if room["phase"] != "misterio" or player.get("out") or player.get("spectator") \
            or mst["case"] is None:
        return
    _, _, solution, hit, near = mst["case"]
    verdict = await judge_misterio(solution, text, hit, near)
    if verdict == "cerca":
        await narrate(room, f"{player['name']} está cerca...")
        return
    if verdict == "lejos":
        mst["lives"][player["id"]] = mst["lives"].get(player["id"], MISTERIO_LIVES) - 1
        left = mst["lives"][player["id"]]
        if left > 0:
            await narrate(room, f"No, {player['name']}, lejos. Te "
                                f"{'queda' if left == 1 else 'quedan'} {left} "
                                f"{'vida' if left == 1 else 'vidas'}.")
        else:
            player["out"] = True
            await narrate(room, f"No, {player['name']}. Era tu última vida: "
                                f"¡quedás eliminado del misterio!")
        await broadcast(room, room_state(room))
        alive = [p for p in room["players"] if not p.get("gone") and not p.get("out")
                 and not p.get("spectator")]
        if survivor_winner(room, alive):
            await game_over(room, survivor_winner(room, alive))
        elif not alive:
            await end_match_nobody(room)
        return
    # acierto
    cancel_timer(room)
    owner = score_owner(room, player)
    mst["solved"][owner] = mst["solved"].get(owner, 0) + 1
    sync_score(room, player, mst["solved"][owner])
    won = mst["solved"][owner] >= MISTERIO_TO_WIN
    await narrate(room, f"¡{player['name']} resolvió el misterio! {solution}")
    if won:
        await game_over(room, player)
        return
    await narrate(room, f"{player['name']} lleva {mst['solved'][owner]} "
                        f"de {MISTERIO_TO_WIN} casos. ¡Va otro!")
    await mst_next_case(room)


# ---------------------------------------------------------------------------
# The sala socket.
# ---------------------------------------------------------------------------
@router.websocket("/amor-con-aroma-a-cafe/ws/{code}")
async def sala_ws(websocket: WebSocket, code: str, name: str = "", spectator: bool = False, seat_key: str = ""):
    code = code.upper()
    room = rooms.get(code)
    if room is None:
        await websocket.close(code=4004)
        return
    name = (name or "").strip()[:24]
    seat_key = str(seat_key or "")[:80]
    await websocket.accept()

    # A comeback with the same name re-takes its seat; nobody loses points.
    seat = next((p for p in room["players"] if not p.get("gone")
                 and seat_key and p.get("seat_key") == seat_key), None)
    if seat is None:
        seat = next(
        (p for p in room["players"] if not p.get("gone") and p["ws"] is None and p["name"] == name and (not spectator or p.get("spectator"))),
        None,
    ) if name else None
    active = [p for p in room["players"] if not p.get("gone") and not p.get("spectator")]
    if seat is None and room["capacity"] and len(active) >= room["capacity"]:
        spectator = True
    if seat is not None:
        pending_disconnect = room.get("disconnect_tasks", {}).pop(seat["id"], None)
        if pending_disconnect:
            pending_disconnect.cancel()
        previous_ws = seat.get("ws")
        seat["ws"] = websocket
        player = seat
        if previous_ws is not None and previous_ws is not websocket:
            try:
                await previous_ws.close(code=4001)
            except Exception:
                pass
        if current_player(room) is player and room["phase"] == "question" and room.get("question"):
            cancel_timer(room)
            room["question"]["clock_started"] = False
    else:
        if not name:
            name = f"Jugador {len(active) + 1}"
        player = {"id": room["next_id"], "name": name, "ws": websocket, "spectator": spectator, "seat_key": seat_key}
        room["next_id"] += 1
        room["players"].append(player)
        if room.get("team_count") and not spectator:
            counts = [sum(1 for p in active if p.get("team") == t) for t in range(room["team_count"])]
            player["team"] = counts.index(min(counts))
        room["scores"][player["id"]] = 0
        room.setdefault("chat_voices", {})[player["id"]] = NARRATOR_VOICES[(player["id"] - 1) % len(NARRATOR_VOICES)]
    log.info("Web sala %s: %s joined (%s players)", code, player["name"], len(active) + (seat is None))
    await tell(player, {"event": "welcome", "name": player["name"], "id": player["id"],
                        "code": code, "capacity": room["capacity"], "phase": room["phase"], "spectator": bool(player.get("spectator")), "build": CLIENT_BUILD})
    if player.get("team") is not None and not player.get("spectator"):
        await narrate(room, f"{player['name']} está en el equipo {TEAM_NAMES[player['team']]}.")
    count = len([p for p in room["players"] if not p.get("gone") and not p.get("spectator")])
    if player.get("spectator"):
        await narrate(room, f"{player['name']} entró a mirar. Puede escuchar y charlar, sin jugar turnos.")
    elif seat is not None:
        await narrate(room, f"¡{player['name']} volvió a la mesa!")
    elif count == 1:
        await say(room,
                  f"¡Listo, {player['name']}! Ya estás en la mesa. No hace falta escribir nada. "
                  "Pasales el link a tus amigos con el botón Copiar el link.",
                  to=player)
        await narrate(room, f"Se unió {player['name']}. Ahora son {count} en la sala.")
    else:
        await narrate(room, f"Se unió {player['name']}. Ahora son {count} en la sala.")
    await broadcast(room, room_state(room))
    if seat is not None and room["phase"] == "question" and current_player(room) is player:
        q = room.get("question")
        if q:
            await tell(player, public_question(room))
            await tell(player, {"event":"say", "question_id":q.get("id"),
                                "text":q["q"] + " " + ". ".join(q["options"]), "audio":q.get("audio")})
    # Solo starts at once; a sala starts when full or when the host taps Empezar.
    if not player.get("spectator") and room["phase"] == "lobby" and room["capacity"] == 1:
        await start_match(room)
    elif not player.get("spectator") and room["phase"] == "lobby" and room["capacity"] and count >= room["capacity"] and not room.get("team_count"):
        await start_match(room)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            action = message.get("action")
            if player["ws"] is not websocket:
                break
            current = current_player(room)
            if player.get("spectator") and action not in ("descripcion", "chat", "rename"):
                continue

            if action == "question-ready":
                await start_question_clock(room, player, message.get("id"))
                continue
            if action == "repetir-pregunta" and current is player and room["phase"] == "question":
                q = room.get("question")
                if q:
                    cancel_timer(room)
                    q["clock_started"] = False
                    await tell(player, public_question(room))
                    await tell(player, {"event":"say", "question_id":q.get("id"),
                                        "text":q["q"] + " " + ". ".join(q["options"]),
                                        "audio":q.get("audio")})
                continue
            if action == "equipos" and room["phase"] == "lobby" and player is host_player(room):
                try:
                    count = int(message.get("count", 0))
                except (TypeError, ValueError):
                    continue
                if count not in (0, 2, 3, 4):
                    continue
                room["team_count"] = count
                for i, member in enumerate(p for p in room["players"] if not p.get("spectator")):
                    member["team"] = i % count if count else None
                await narrate(room, f"Jugamos con {count} equipos." if count else "Jugamos todos contra todos.")
                await broadcast(room, room_state(room))
            elif action == "equipo" and room["phase"] == "lobby" and room.get("team_count"):
                try:
                    team = int(message.get("team", -1))
                except (TypeError, ValueError):
                    continue
                if team in range(room["team_count"]):
                    player["team"] = team
                    await narrate(room, f"{player['name']} eligió el equipo {TEAM_NAMES[team]}.")
                    await broadcast(room, room_state(room))
            elif action == "start" and room["phase"] == "lobby" and player is host_player(room):
                await start_match(room)
            elif action == "juego" and room["phase"] == "lobby" and player is host_player(room):
                picked = message.get("game")
                if room["game"] is None and picked in ("categorias", "paises", "ahorcado",
                                                       "bomba", "misterio"):
                    room["game"] = picked
                    names = {"categorias": "la ruleta de categorías",
                             "paises": "la ruleta de países", "ahorcado": "el ahorcado",
                             "bomba": "la bomba", "misterio": "resolver el misterio"}
                    await narrate(room, f"¡{player['name']} eligió {names[picked]}!")
                    await start_match(room)
            elif action == "guess" and room["phase"] == "bomba" and current_player(room) is player:
                await bb_answer(room, player, str(message.get("text") or ""))
            elif action == "guess" and room["phase"] == "misterio":
                await mst_guess(room, player, str(message.get("text") or ""))
            elif action == "guess" and room["phase"] == "ahorcado" and current_player(room) is player:
                _, _, _, _, clean, parse_guess = ah_helpers()
                guess = parse_guess(str(message.get("text") or ""))
                if guess:
                    await ah_guess(room, player, guess)
                else:
                    await narrate(room, f"No te entendí, {player['name']}. Decí una letra o la palabra.")
            elif action == "spin":
                if room["spinning"] or current is not player:
                    if current is not player:
                        await tell(player, {"event": "say", "text": "Todavía no es tu turno.", "audio": None})
                    continue
                if room["phase"] == "country_spin_ready":
                    asyncio.create_task(do_country_spin(room, player))
                elif room["phase"] == "spin_ready":
                    asyncio.create_task(do_category_spin(room, player))
                elif room["phase"] == "verdad_reto_ready":
                    asyncio.create_task(do_spin(room, player))
            elif action == "category":
                # The optional picker: play THIS category instead of spinning.
                if room["phase"] != "spin_ready" or current is not player:
                    continue
                cat = message.get("category")
                if cat not in CATEGORIES:
                    continue
                if room["game"] == "paises" and cat == "verdad_reto":
                    await tell(player, {"event": "say", "audio": None,
                                        "text": "En la ruleta de países no hay Verdad o Reto. "
                                                "Elegí otra categoría o girá la ruleta."})
                    continue
                room["question"] = None
                if cat == "verdad_reto":
                    await narrate(room, f"{player['name']} eligió Verdad o Reto. ¡Que gire la ruleta!")
                    room["phase"] = "verdad_reto_ready"
                    await broadcast(room, room_state(room))
                    await do_spin(room, player)
                else:
                    where = f", por {room['country']}" if room.get("country") else ""
                    await ask_question(room, player, cat, where)
            elif action == "answer":
                if room["phase"] == "question" and current is player and room.get("question"):
                    await resolve_answer(room, player, int(message.get("idx", -1)))
            elif action == "listo":
                if room["phase"] == "verdad_reto" and current is player:
                    await complete_verdad_reto(room, player, done=True)
            elif action == "pasar":
                if room["phase"] == "verdad_reto" and current is player:
                    await complete_verdad_reto(room, player, done=False)
            elif action == "microfono":
                if current is player or room["phase"] == "misterio":
                    room["mic_until"] = asyncio.get_running_loop().time() + (15 if message.get("active") else 0)
            elif action == "voz-texto":
                text = str(message.get("text") or "").strip()
                if not text or player.get("out") or player.get("spectator"):
                    continue
                if room["phase"] == "misterio":
                    await mst_guess(room, player, text)
                    continue
                if current is not player:
                    continue
                if room["phase"] == "bomba":
                    await bb_answer(room, player, text)
                elif room["phase"] == "ahorcado":
                    _, _, _, _, clean, parse_guess = ah_helpers()
                    guess = parse_guess(text)
                    if guess:
                        await ah_guess(room, player, guess)
                    else:
                        await narrate(room, f"No te entendí, {player['name']}. Decí una letra o la palabra.",
                                      to=player)
                elif room["phase"] == "question" and room.get("question"):
                    idx = match_option(text, room["question"]["options"])
                    if idx is None:
                        await narrate(room, f"No te entendí, {player['name']}. Decí A, B, C o D, o tocá una opción.",
                                      to=player)
                    else:
                        await resolve_answer(room, player, idx)
            elif action == "descripcion":
                game_key = message.get("game") or room["game"]
                text = GAME_DESCRIPTIONS.get(game_key)
                if text:
                    await narrate(room, text, to=player)
            elif action == "chat":
                await handle_chat(room, player, message)
            elif action == "rename":
                new_name = (message.get("name") or "").strip()[:24]
                if new_name:
                    player["name"] = new_name
                    await narrate(room, f"Ahora te llamás {new_name}.")
                    await broadcast(room, room_state(room))
    except WebSocketDisconnect:
        pass
    finally:
        if player["ws"] is websocket:
            player["ws"] = None
            if room["phase"] == "question" and current_player(room) is player and room.get("question"):
                cancel_timer(room)
                room["question"]["clock_started"] = False
        log.info("Web sala %s: %s disconnected", code, player["name"])
        # A mobile reconnect should not erase the room or the current question.
        if player["ws"] is None:
            tasks = room.setdefault("disconnect_tasks", {})
            old = tasks.pop(player["id"], None)
            if old:
                old.cancel()
            tasks[player["id"]] = asyncio.create_task(retire_disconnected(room, code, player))


async def retire_disconnected(room, code, player):
    try:
        await asyncio.sleep(30)
        if player.get("ws") is not None or rooms.get(code) is not room:
            return
        remaining = [p for p in room["players"] if not p.get("gone") and p.get("ws") is not None]
        if not remaining:
            cancel_timer(room)
            rooms.pop(code, None)
        elif room["phase"] != "lobby":
            await narrate(room, f"{player['name']} se fue de la mesa.")
            if current_player(room) is player:
                room["turn"] += 1
                await begin_turn(room)
            else:
                await broadcast(room, room_state(room))
    except asyncio.CancelledError:
        pass


async def handle_chat(room, player, message):
    text = (message.get("text") or "").strip()[:300]
    if not text:
        return
    to_id = message.get("to", "all")
    target = None
    if to_id != "all":
        target = next((p for p in room["players"] if p["id"] == to_id and not p.get("gone")), None)
        if target is None:
            return
    spoken = (f"{player['name']} te escribió: {text}" if target
              else f"{player['name']} escribió: {text}")
    from app import synthesize

    try:
        voice = room.get("chat_voices", {}).get(player["id"]) or room.get("voice") or "es-AR-ElenaNeural"
        mp3 = await ogg_to_mp3(await synthesize(spoken, voice))
        url = f"/amor-con-aroma-a-cafe/audio/{cache_audio(mp3)}.mp3"
    except Exception:
        url = None
    payload = {"event": "chat", "from_id": player["id"], "from_name": player["name"],
               "to": to_id, "text": text, "audio": url}
    if target is not None:
        await tell(target, payload)
        await tell(player, {**payload, "echo": True})
    else:
        await broadcast(room, payload)


from fastapi import Request


@router.post("/amor-con-aroma-a-cafe/api/voz/{code}")
async def voice_clip(code: str, request: Request, to: str = "all", sender: int = -1):
    """A recorded voice clip, converted to mp3 and relayed to the recipient(s)."""
    room = rooms.get(code.upper())
    if room is None:
        return Response(status_code=404)
    sender_p = next((p for p in room["players"] if p["id"] == sender and not p.get("gone")), None)
    if sender_p is None:
        return Response(status_code=403)
    body = await request.body()
    if not body or len(body) > 3_000_000:
        return Response(status_code=400)
    try:
        mp3 = await ogg_to_mp3(body)  # ffmpeg reads webm/opus from the same pipe
    except Exception:
        log.exception("Web sala: voice clip conversion failed")
        return Response(status_code=415)
    url = f"/amor-con-aroma-a-cafe/audio/{cache_audio(mp3)}.mp3"
    payload = {"event": "clip", "from_id": sender_p["id"], "from_name": sender_p["name"],
               "to": to, "url": url}
    intro_url = None
    try:
        from app import synthesize

        voice = room.get("chat_voices", {}).get(sender_p["id"]) or room.get("voice") or "es-AR-ElenaNeural"
        intro = await ogg_to_mp3(await synthesize(f"{sender_p['name']} mandó un audio.", voice))
        intro_url = f"/amor-con-aroma-a-cafe/audio/{cache_audio(intro)}.mp3"
    except Exception:
        log.exception("Web sala: clip intro synthesis failed")
    intro_msg = {"event": "say", "text": f"{sender_p['name']} mandó un audio.", "audio": intro_url}
    if to == "all":
        for p in room["players"]:
            if not p.get("gone") and p["id"] != sender_p["id"]:
                await tell(p, intro_msg)
        await broadcast(room, payload)
    else:
        try:
            target_id = int(to)
        except ValueError:
            return Response(status_code=400)
        target = next((p for p in room["players"] if p["id"] == target_id and not p.get("gone")), None)
        if target is None:
            return Response(status_code=404)
        await tell(target, intro_msg)
        await tell(target, payload)
        await tell(sender_p, {**payload, "echo": True})
    return {"ok": True}


@router.post("/amor-con-aroma-a-cafe/api/voz-respuesta/{code}")
async def voice_answer(code: str, request: Request, sender: int = -1):
    """A spoken answer to the live question, transcribed with Groq."""
    room = rooms.get(code.upper())
    if room is None:
        return Response(status_code=404)
    player = next((p for p in room["players"] if p["id"] == sender and not p.get("gone")), None)
    if player is None or player.get("out") or player.get("spectator"):
        return Response(status_code=409)
    phase = room["phase"]
    if phase in ("question", "ahorcado", "bomba") and current_player(room) is not player:
        return Response(status_code=409)
    if phase not in ("question", "ahorcado", "bomba", "misterio"):
        return Response(status_code=409)
    body = await request.body()
    if not body or len(body) > 3_000_000:
        return Response(status_code=400)
    text = await transcribe_clip(body)
    if not text:
        await narrate(room, f"No te escuché bien, {player['name']}. Probá de nuevo o escribila.",
                      to=player)
        return {"heard": False}
    if room["phase"] == "bomba":
        await bb_answer(room, player, text)
        return {"heard": True, "text": text}
    if room["phase"] == "misterio":
        await mst_guess(room, player, text)
        return {"heard": True, "text": text}
    if room["phase"] == "ahorcado":
        _, _, _, _, _, parse_guess = ah_helpers()
        guess = parse_guess(text)
        if guess is None:
            await narrate(room, f"{player['name']}, no entendí tu letra. Decí una letra o la palabra.")
            return {"heard": False, "text": text}
        await ah_guess(room, player, guess)
        return {"heard": True, "text": text}
    question = room.get("question")
    idx = match_option(text, question["options"]) if question else None
    if idx is None:
        await narrate(room, f"{player['name']}, no entendí tu respuesta. Decí A, B, C o D.")
        return {"heard": False, "text": text}
    await resolve_answer(room, player, idx)
    return {"heard": True, "text": text, "idx": idx}


async def transcribe_clip(webm: bytes) -> str:
    import os

    import httpx

    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return ""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                data={"model": os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"),
                      "language": "es", "response_format": "json"},
                files={"file": ("respuesta.webm", webm)},
                timeout=30,
            )
            if r.status_code < 400:
                return (r.json().get("text") or "").strip()
            log.warning("Web sala: Groq transcription failed: %s", r.status_code)
    except Exception:
        log.exception("Web sala: Groq transcription error")
    return ""


def match_option(text, options):
    import re

    t = text.lower().strip()
    if not t:
        return None
    if t in "abcd" and len(t) == 1:
        return "abcd".index(t) if "abcd".index(t) < len(options) else None
    m = re.search(r"(?:opci[oó]n|la|letra)\s+([abcd])\b", t)
    if m:
        return "abcd".index(m.group(1))
    for i, word in enumerate(("primera", "segunda", "tercera", "cuarta")):
        if word in t:
            return i
    best, best_score = None, 0
    for i, opt in enumerate(options):
        o = opt.lower()
        if o in t or t in o:
            return i
        score = sum(1 for tok in o.split() if len(tok) > 3 and tok in t)
        if score > best_score:
            best, best_score = i, score
    return best if best_score >= 1 else None


@router.post("/amor-con-aroma-a-cafe/api/salas")
async def crear_sala(request: Request):
    mode = "sala"
    capacity = None
    try:
        data = await request.json()
        if data.get("mode") in ("solo", "sala", "solo_paises", "paises",
                                "solo_ahorcado", "ahorcado",
                                "solo_bomba", "bomba", "solo_misterio", "misterio"):
            mode = data["mode"]
        capacity = int(data.get("capacity") or 0) or None
    except Exception:
        pass
    game = "categorias"
    if mode in ("solo_paises", "paises"):
        game = "paises"
    elif mode in ("solo_ahorcado", "ahorcado"):
        game = "ahorcado"
    elif mode in ("solo_bomba", "bomba"):
        game = "bomba"
    elif mode in ("solo_misterio", "misterio"):
        game = "misterio"
    elif mode == "sala":
        game = None  # the host picks the game in the lobby
    if mode in ("solo", "solo_paises", "solo_ahorcado", "solo_bomba", "solo_misterio"):
        capacity = 1
    elif capacity is not None:
        capacity = max(2, min(MAX_PLAYERS, capacity))
    code = new_room_code()
    voice = random.choice(NARRATOR_VOICES)
    rooms[code] = {
        "players": [],
        "next_id": 1,
        "mode": mode,
        "capacity": capacity,
        "starter": 0,
        "turn": 0,
        "match": 1,
        "phase": "lobby",
        "spinning": False,
        "question": None,
        "scores": {},
        "timer_task": None,
        "audio_lock": asyncio.Lock(),
        "used_retos": set(),
        "used_verdades": set(),
        **{key: set() for key in MC_USED_KEYS.values()},
        "voice": voice,
        "question_voice": random.choice([v for v in NARRATOR_VOICES if v != voice]),
        "game": game,
        "country": None,
        "country_done": set(),
        "countries_won": {},
        "ahorcado": {"levels": {}, "used": set(), "word": None, "hint": "",
                     "guessed": set(), "wrong": set(), "attempts": 0},
        "cat_progress": {},
        "chat_voices": {},
        "bomba": {"lives": {}, "prompt": None, "keywords": [], "said": set(),
                  "used": set(), "fuse": 0},
        "misterio": {"lives": {}, "solved": {}, "used": set(), "case": None,
                     "case_idx": -1},
        "teams": None,
    }
    return {"code": code}



# ---------------------------------------------------------------------------
# The page: one HTML file, no build step, screen-reader first.
# ---------------------------------------------------------------------------
PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>💕 Amor con aroma a café 💕</title>
<style>
  [hidden] { display: none !important; }
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: #000; color: #fff; min-height: 100vh;
    font-family: system-ui, sans-serif; text-align: center;
    display: flex; flex-direction: column; align-items: center;
    padding: 1rem;
  }
  h1 { font-size: 1.9rem; margin: 0.5rem 0 0; color: #ffb6c1; }
  .icons { font-size: 1.6rem; margin: 0.4rem 0 1rem; letter-spacing: 0.6rem; }
  button {
    font-size: 1.5rem; padding: 1rem 2rem; border-radius: 1rem; border: none;
    background: #d81b60; color: #fff; cursor: pointer; margin: 0.5rem;
    min-width: 14rem; min-height: 3.5rem; display: block;
  }
  #btn-actualizar { position: sticky; top: 0.4rem; z-index: 20; align-self: stretch; width: 100%; margin: 0 0 0.5rem; min-width: 8rem; font-size: 1.1rem; padding: 0.65rem 1rem; }
  #pregunta, #pregunta-texto { scroll-margin-top: 5rem; }
  button.secondary { background: #3949ab; }
  button.chatbtn { font-size: 1.1rem; min-width: 10rem; min-height: 2.8rem; padding: 0.6rem 1rem; }
  button:disabled { background: #555; color: #aaa; }
  button:focus-visible, input:focus-visible, select:focus-visible {
    outline: 4px solid #fdd835; outline-offset: 2px;
  }
  #wheel { width: min(80vw, 320px); height: min(80vw, 320px); margin: 1rem auto; }
  #estado { font-size: 1.4rem; min-height: 2.2rem; margin: 0.5rem; color: #fdd835; }
  #temporizador { font-size: 1.3rem; color: #ffab91; min-height: 1.8rem; }
  #jugadores { font-size: 1.1rem; color: #b2dfdb; margin: 0.5rem; list-style: none; padding: 0; }
  #jugadores li { margin: 0.2rem; }
  #compartir {
    background: #101418; border: 2px dashed #8e24aa; border-radius: 0.8rem;
    padding: 0.8rem; margin: 0.5rem; font-size: 1.1rem; word-break: break-all;
    max-width: 34rem;
  }
  #pregunta { max-width: 34rem; }
  #pregunta-texto { font-size: 1.5rem; font-weight: bold; color: #ffe082; }
  /* Cada opción con su color, alto contraste, letra grande (baja visión). */
  #pregunta .opcion[data-idx="0"] { background: #f9a825; color: #000; font-weight: bold; }
  #pregunta .opcion[data-idx="1"] { background: #00c853; color: #000; font-weight: bold; }
  #pregunta .opcion[data-idx="2"] { background: #29b6f6; color: #000; font-weight: bold; }
  #pregunta .opcion[data-idx="3"] { background: #ce93d8; color: #000; font-weight: bold; }
  #pregunta .opcion:disabled { background: #555; color: #ddd; }
  .ahorcado-btn { background: #6a1b9a; }
  .info-btn { font-size: 1.1rem; min-width: 10rem; min-height: 2.8rem; padding: 0.5rem 1rem; }
  .info-titulo { color: #fdd835; font-weight: bold; margin-bottom: 0.2rem; }
  .bomba-btn { background: #e64a19; }
  .misterio-btn { background: #00838f; }
  #bb-consigna, #mst-titulo { font-size: 1.6rem; font-weight: bold; color: #fdd835; }
  #mst-caso { font-size: 1.3rem; }
  #bb-quien, #bb-vidas, #mst-vidas { font-size: 1.2rem; }
  #ahorcado { max-width: 34rem; }
  #ah-pista { font-size: 1.4rem; color: #ffe082; }
  #ah-tablero {
    font-size: 3rem; font-weight: bold; letter-spacing: 1.2rem; color: #80d8ff;
    margin: 1rem 0; font-family: monospace;
  }
  #ah-intentos { font-size: 1.3rem; color: #ffab91; }
  #ah-letras { font-size: 1.2rem; color: #ef9a9a; }
  #ah-input { font-size: 1.5rem; padding: 0.7rem; border-radius: 0.6rem; width: 14rem; text-transform: uppercase; }
  #elegir-juego h2 { color: #fdd835; }
  #chat { max-width: 34rem; margin-top: 1rem; border-top: 2px solid #333; padding-top: 0.8rem; }
  #chat-log { list-style: none; padding: 0; text-align: left; font-size: 1rem; color: #cfd8dc; }
  #chat-log li { margin: 0.3rem 0; }
  #chat-texto { font-size: 1.2rem; padding: 0.6rem; border-radius: 0.6rem; width: 100%; }
  select { font-size: 1.2rem; min-height: 2.8rem; padding: 0.35rem; }
  #nombre-input, #inicio-nombre, #editar-nombre { font-size: 1.3rem; padding: 0.7rem; border-radius: 0.6rem; width: 16rem; }
  #cupos-select { font-size: 1.4rem; padding: 0.7rem; border-radius: 0.6rem; min-width: 8rem; }
  #chat-para { font-size: 1.1rem; padding: 0.5rem; border-radius: 0.6rem; }
  .visually-hidden {
    position: absolute; width: 1px; height: 1px; overflow: hidden;
    clip: rect(0 0 0 0); white-space: nowrap;
  }
</style>
</head>
<body>
  <header>
    <h1>💕 Amor con aroma a café 💕</h1>
    <div class="icons" aria-hidden="true">☕ 🧉 🧁 💗</div>
  </header>
  <button id="btn-actualizar" class="secondary" aria-label="Actualizar esta página y volver a mi mesa">Actualizar</button>

  <main>
    <p class="visually-hidden">
      Juego de la ruleta con amigos: Verdad o Reto, Trivia, Refranes y Países.
      Todo se hace con botones y cada jugada se anuncia en voz alta.
    </p>
    <p id="estado" role="status" tabindex="-1">Bienvenido a la mesa.</p>

    <section id="pantalla-inicio" aria-label="Pantalla de inicio">
      <label for="inicio-nombre">Tu nombre o apodo (podés cambiarlo cada día):</label>
      <input id="inicio-nombre" type="text" maxlength="24" autocomplete="nickname">
      <button id="btn-solo" aria-label="Jugar solo, sin amigos">Jugar solo</button>
      <button id="btn-sala" class="secondary" aria-label="Sala de juegos, para jugar con amigos">Sala de juegos (con amigos)</button>
      <button id="btn-paises" class="secondary" aria-label="Ruleta de Países, para jugar con amigos">Ruleta de Países</button>
    </section>

    <section id="pantalla-modo" hidden aria-label="A qué querés jugar">
      <button id="btn-modo-cat" aria-label="Ruleta de todas las categorías">Ruleta de categorías</button>
      <button id="btn-modo-paises" class="secondary" aria-label="Ruleta de países">Ruleta de países</button>
      <button id="btn-modo-ahorcado" class="ahorcado-btn" aria-label="El ahorcado, adivinar la palabra">El ahorcado</button>
      <button id="btn-modo-bomba" class="bomba-btn" aria-label="La bomba, decí algo de la consigna antes de que explote">La bomba</button>
      <button id="btn-modo-misterio" class="misterio-btn" aria-label="Resolver el misterio, adivinar qué pasó">Resolver el misterio</button>
    </section>

    <section id="pantalla-cupos" hidden aria-label="Cuántos jugadores">
      <label for="cupos-select" id="cupos-label">¿Cuántos jugadores son? De 2 a 20.</label><br>
      <select id="cupos-select" aria-labelledby="cupos-label"></select><br>
      <button id="btn-crear" aria-label="Crear la sala de juego">Crear la sala</button>
      <button id="btn-volver" class="secondary" aria-label="Volver a la pantalla de inicio">Volver</button>
    </section>

    <section id="pantalla-unirse" hidden aria-label="Unirse a la sala">
      <label for="nombre-input" id="nombre-label">Tu nombre o apodo (si lo dejás vacío, sos Jugador N):</label><br>
      <input id="nombre-input" type="text" autocomplete="off" aria-labelledby="nombre-label"><br>
      <button id="btn-entrar" aria-label="Entrar a jugar">Entrar a jugar</button>
      <button id="btn-mirar" class="secondary">Entrar a mirar</button>
    </section>

    <section id="sala" hidden aria-label="Sala de juego">
      <button id="btn-musica" class="secondary info-btn" aria-pressed="false" aria-label="Prender o apagar la musiquita de fondo">🎵 Musiquita: apagada</button>
      <label for="editar-nombre">Cambiar tu nombre o apodo:</label>
      <input id="editar-nombre" type="text" maxlength="24" autocomplete="nickname">
      <button id="btn-nombre" class="secondary">Guardar mi nombre</button>
      <div id="compartir" hidden>
        Pasá este link a tus amigos:<br><strong id="link"></strong><br>
        <button id="btn-copiar" class="secondary" aria-label="Copiar el link para invitar a tus amigos"><span aria-hidden="true">📤 </span>Copiar el link</button>
      </div>
      <div id="equipos-panel" hidden>
        <div id="equipos-host">
          <label for="equipos-count">Modo de equipos:</label>
          <select id="equipos-count"><option value="0">Todos contra todos</option><option value="2">Dos equipos</option><option value="3">Tres equipos</option><option value="4">Cuatro equipos</option></select>
          <button id="btn-equipos" class="secondary">Guardar modo de equipos</button>
        </div>
        <div id="equipo-propio" hidden>
          <label for="equipo-select">Tu equipo:</label><select id="equipo-select"></select>
          <button id="btn-equipo" class="secondary">Elegir mi equipo</button>
        </div>
      </div>
      <div id="elegir-juego" hidden>
        <h2>¿A qué jugamos?</h2>
        <button id="btn-juego-cat" aria-label="Jugar a la ruleta de categorías">Ruleta de categorías</button>
        <button id="btn-juego-paises" class="secondary" aria-label="Jugar a la ruleta de países">Ruleta de países</button>
        <button id="btn-juego-ahorcado" class="ahorcado-btn" aria-label="Jugar al ahorcado">El ahorcado</button>
        <button id="btn-juego-bomba" class="bomba-btn" aria-label="Jugar a la bomba">La bomba</button>
        <button id="btn-juego-misterio" class="misterio-btn" aria-label="Jugar a resolver el misterio">Resolver el misterio</button>
      </div>
      <div id="elegir-info" hidden>
        <p class="info-titulo">¿De qué se trata cada juego?</p>
        <button id="btn-info-bomba" class="secondary info-btn">De qué se trata la bomba</button>
        <button id="btn-info-misterio" class="secondary info-btn">De qué se trata resolver el misterio</button>
        <button id="btn-info-cat" class="secondary info-btn" aria-label="De qué se trata la ruleta de categorías">Ruleta de categorías</button>
        <button id="btn-info-paises" class="secondary info-btn" aria-label="De qué se trata la ruleta de países">Ruleta de países</button>
        <button id="btn-info-ahorcado" class="secondary info-btn" aria-label="De qué se trata el ahorcado">El ahorcado</button>

      </div>
        <button id="btn-info" class="secondary info-btn" aria-label="De qué se trata el juego elegido">¿De qué se trata?</button>
      <button id="btn-empezar" hidden aria-label="Empezar la partida ya">Empezar la partida</button>
      <p id="temporizador" role="timer" aria-hidden="true"></p>
      <canvas id="wheel" width="640" height="640" aria-hidden="true"></canvas>
      <ul id="jugadores" role="status" aria-label="Jugadores en la mesa"></ul>

      <div id="categorias" hidden>
        <label for="elegir-cat" id="elegir-label">O elegí la categoría vos:</label><br>
        <select id="elegir-cat" aria-labelledby="elegir-label"></select>
        <button id="btn-elegir" class="secondary chatbtn" aria-label="Jugar la categoría elegida">Jugar esta categoría</button>
      </div>

      <button id="btn-girar" hidden disabled><span aria-hidden="true">🎡 </span><span id="btn-girar-text">Girar la ruleta</span></button>

      <button id="btn-volver-cuestionario" class="secondary" hidden aria-label="Volver a la pregunta y sus cuatro opciones">Volver al cuestionario</button>
      <p id="quiz-progreso" role="status"></p>
      <div id="pregunta" hidden>
        <p id="pregunta-texto" role="status" tabindex="-1"></p>
        <button id="btn-pregunta-repetir" class="secondary" aria-label="Repetir la pregunta y las opciones">Repetir pregunta</button>
        <button id="btn-pregunta-lista" class="secondary" aria-label="Ya escuché o leí la pregunta, empezar el tiempo para responder">Empezar a responder</button>
        <button class="opcion secondary" data-idx="0"></button>
        <button class="opcion secondary" data-idx="1"></button>
        <button class="opcion secondary" data-idx="2"></button>
        <button class="opcion secondary" data-idx="3"></button>
        <button id="btn-voz-resp" aria-label="Responder por voz: decí A, B, C o D">Responder por voz</button>
      </div>

      <div id="ahorcado" hidden>
        <p id="ah-pista" role="status"></p>
        <p id="ah-tablero" aria-label="La palabra"></p>
        <p id="ah-intentos"></p>
        <p id="ah-letras"></p>
        <label for="ah-input" id="ah-label">Escribí una letra o la palabra entera:</label><br>
        <input id="ah-input" type="text" autocomplete="off" aria-labelledby="ah-label">
        <button id="btn-ah-mandar" aria-label="Mandar la letra o palabra escrita">Mandar</button>
        <button id="btn-ah-voz" class="secondary" aria-label="Decir una letra o la palabra por voz">Decirla por voz</button>
      </div>

      <div id="bomba" hidden>
        <p id="bb-consigna" role="status"></p>
        <p id="bb-quien"></p>
        <p id="bb-vidas"></p>
        <label for="bb-input" id="bb-label">Escribí algo que encaje con la consigna:</label><br>
        <input id="bb-input" type="text" autocomplete="off" aria-labelledby="bb-label">
        <button id="btn-bb-mandar" aria-label="Mandar la respuesta de la bomba">Mandar</button>
        <button id="btn-bb-voz" class="secondary" aria-label="Decir la respuesta por voz">Decirla por voz</button>
      </div>

      <div id="misterio" hidden>
        <p id="mst-titulo" role="status"></p>
        <p id="mst-caso"></p>
        <p id="mst-vidas"></p>
        <label for="mst-input" id="mst-label">Escribí tu teoría:</label><br>
        <input id="mst-input" type="text" autocomplete="off" aria-labelledby="mst-label">
        <button id="btn-mst-mandar" aria-label="Mandar la teoría">Mandar teoría</button>
        <button id="btn-mst-voz" class="secondary" aria-label="Decir la teoría por voz">Decirla por voz</button>
      </div>

      <div id="reto-verdad" hidden>
        <p id="carta-texto" role="status"></p>
        <button id="btn-listo" aria-label="Listo, ya lo hice">¡Listo, ya lo hice!</button>
        <button id="btn-pasar" class="secondary" aria-label="Pasar, sin punto">Paso</button>
      </div>

      <h2 id="sala-titulo">Sala de juegos</h2>
      <div id="chat">
        <h2 id="chat-titulo">Chat de la sala</h2>
        <ul id="chat-log" aria-live="polite" aria-label="Mensajes del chat"></ul>
        <label for="chat-para" class="visually-hidden">Destinatario del mensaje</label>
        <select id="chat-para" aria-label="Destinatario del mensaje"></select>
        <label for="chat-texto" class="visually-hidden">Escribí tu mensaje</label>
        <input id="chat-texto" type="text" autocomplete="off" placeholder="Escribí un mensaje (opcional)">
        <button id="btn-chat" class="chatbtn" aria-label="Mandar el mensaje de texto">Mandar mensaje</button>
        <button id="btn-grabar" class="chatbtn secondary" aria-label="Grabar una nota de voz">Grabar nota de voz</button>
      </div>
    </section>

    <div id="voz" class="visually-hidden" aria-live="assertive"></div>
    <audio id="player"></audio>
  </main>
<script>
"use strict";
const CLIENT_BUILD = "__CAFE_BUILD__";

const $ = (id) => document.getElementById(id);
const estado = $("estado"), voz = $("voz"), player = $("player");
let ws = null, audioUnlocked = false;
let myId = null, myName = localStorage.getItem("cafe_nombre") || "";
let salaCode = null, lastState = null, lastQuestion = null, lastHint = null;
let watching = false;
$("btn-mirar").addEventListener("click", () => {
  unlockAudio(); watching = true;
  myName = $("nombre-input").value.trim().slice(0,24);
  localStorage.setItem("cafe_nombre", myName);
  enterSala(inviteCode, myName);
});
let turnStartedAt = 0, timerInterval = null;
$("inicio-nombre").value = myName;
$("editar-nombre").value = myName;
function saveStartName() {
  myName = $("inicio-nombre").value.trim().slice(0, 24);
  localStorage.setItem("cafe_nombre", myName);
  $("editar-nombre").value = myName;
}
$("btn-nombre").addEventListener("click", () => {
  const name = $("editar-nombre").value.trim().slice(0,24);
  if (!name || !ws || ws.readyState !== 1) return;
  myName = name;
  localStorage.setItem("cafe_nombre", name);
  ws.send(JSON.stringify({action:"rename", name}));
});
let micActive = false;
$("btn-actualizar").addEventListener("click",()=>{
  if(micActive){announce("Terminá de grabar antes de actualizar, así no perdés tu mensaje.");return;}
  const active=lastState && !["lobby","gameover"].includes(lastState.phase);
  if(active && !confirm("Estás en una partida. Actualizar vuelve a cargar la página y reconecta tu mesa; puede interrumpir la lectura. ¿Actualizar ahora?"))return;
  location.reload();
});
function setMic(active) {
  micActive = active;
  updateMusicLevel();
  if (active) { player.pause(); playing = false; audioQueue.length = 0; }
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action:"microfono", active}));
  if (!active) pumpAudio();
}


// Soft original ambient music, off by default and muted during capture.
let musicOn = localStorage.getItem("cafe_musica") === "1";
let musicCtx = null, musicGain = null;
function updateMusicLevel() {
  if (musicCtx && musicGain) {
    if(micActive){musicGain.gain.cancelScheduledValues(musicCtx.currentTime);musicGain.gain.setValueAtTime(0,musicCtx.currentTime);}
    else musicGain.gain.setTargetAtTime(!player.paused ? 0.006 : 0.025,musicCtx.currentTime,0.15);
  }
}
function startMusic() {
  if (!musicOn) return;
  if (!musicCtx) {
    musicCtx = new (window.AudioContext || window.webkitAudioContext)();
    musicGain = musicCtx.createGain(); musicGain.gain.value=0;
    musicGain.connect(musicCtx.destination);
    [196, 246.94, 293.66].forEach((freq) => {
      const osc = musicCtx.createOscillator(), gain = musicCtx.createGain();
      osc.type = "sine"; osc.frequency.value = freq; gain.gain.value = 0.25;
      osc.connect(gain).connect(musicGain); osc.start();
    });
  }
  musicCtx.resume(); updateMusicLevel();
}
function renderMusic() {
  $("btn-musica").textContent = musicOn ? "Musiquita: prendida" : "Musiquita: apagada";
  $("btn-musica").setAttribute("aria-pressed", String(musicOn));
}
$("btn-musica").addEventListener("click", () => {
  musicOn = !musicOn;
  localStorage.setItem("cafe_musica", musicOn ? "1" : "0");
  if (musicOn) startMusic();
  else if (musicCtx) { musicCtx.close(); musicCtx = null; musicGain = null; }
  renderMusic();
});
["play", "pause", "ended"].forEach((event) => player.addEventListener(event, updateMusicLevel));
renderMusic();

// --- One queue for every sound: nothing talks over anything else. ---
const audioQueue = [];
let playing = false;
function queueAudio(url, done = null) {
  if (!url) return;
  audioQueue.push({url, done});
  pumpAudio();
}
function pumpAudio() {
  if (playing || micActive || !audioQueue.length || !audioUnlocked) return;
  playing = true;
  const item = audioQueue.shift();
  const url = item.url;
  player.src = url;
  player.onended = () => { playing = false; if (item.done) item.done(); pumpAudio(); };
  player.onerror = () => { playing = false; pumpAudio(); };
  player.play().catch(() => {
    // Autoplay blocked anyway: put it back; the next tap retries it.
    playing = false;
    audioQueue.unshift(item);
  });
}

function announce(text) {
  estado.textContent = text;
  voz.textContent = "";
  setTimeout(() => { voz.textContent = text; }, 60);
}

const SILENT_MP3 = "data:audio/mpeg;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//NwwAAAAAAAAAAAAEluZm8AAAAPAAAADgAABm0ALCwsLCwsLDw8PDw8PDxNTU1NTU1NXV1dXV1dXW1tbW1tbW19fX19fX19jo6Ojo6Ojp6enp6enp6erq6urq6urr6+vr6+vr7Pz8/Pz8/P39/f39/f3+/v7+/v7+//////////AAAAAExhdmM1OC4xMwAAAAAAAAAAAAAAACQDaQAAAAAAAAZtL+joNQAAAAAAAAAAAAAAAAD/80DEAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQsRbAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQMSkAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVTEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NCxKMAAANIAAAAAFVVVVVVVVVVVVVVVVVVVVVVVVVVTEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NAxKQAAANIAAAAAFVVVVVVVVVVVVVVVVVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX/80LEowAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX/80DEpAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQsSjAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQMSkAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVTEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NCxKMAAANIAAAAAFVVVVVVVVVVVVVVVVVVVVVVVVVVTEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NAxKQAAANIAAAAAFVVVVVVVVVVVVVVVVVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX/80LEowAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVMQU1FMy4xMDBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX/80DEpAAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQsSjAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVQ==";
function unlockAudio() {
  startMusic();
  // Runs on every tap: create/resume the WebAudio context (ticking, spin
  // sound) and prime the audio element with a real soundless mp3 so
  // autoplay policies count the gesture and later queued clips can play.
  try {
    const ctx = ac();
    if (ctx.state === "suspended") ctx.resume();
  } catch (err) {}
  if (!audioUnlocked) {
    audioUnlocked = true;
    player.src = SILENT_MP3;
    player.play().then(() => pumpAudio()).catch(() => {});
  } else {
    pumpAudio();
  }
}

function show(id) {
  for (const s of ["pantalla-inicio", "pantalla-modo", "pantalla-cupos", "pantalla-unirse", "sala"]) {
    $(s).hidden = (s !== id);
  }
  estado.focus();
}

// --- Sonidos generados (sin archivos): ticking del reloj y zumbido de giro ---
let audioCtx = null, clockTimer = null;
function ac() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === "suspended") audioCtx.resume();
  return audioCtx;
}
function click(freq, dur, gain) {
  if (!audioUnlocked || micActive) return;
  try {
    const ctx = ac(), osc = ctx.createOscillator(), g = ctx.createGain();
    osc.type = "square"; osc.frequency.value = freq;
    g.gain.setValueAtTime(gain, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
    osc.connect(g); g.connect(ctx.destination);
    osc.start(); osc.stop(ctx.currentTime + dur);
  } catch (err) {}
}
function spinSound() {
  if (!audioUnlocked) return;
  for (let i = 0; i < 14; i++) {
    setTimeout(() => click(600 + (i % 2) * 200, 0.06, 0.08), i * (120 + i * 12));
  }
}
function startTicking(duration = 60) {
  stopTicking();
  let pulse = 0;
  clockTimer = setInterval(() => {
    const left = duration - (Date.now() - turnStartedAt) / 1000;
    if (left <= 0) { stopTicking(); return; }
    pulse++;
    const fast = lastState && lastState.game === "bomba";
    const rate = fast ? (left <= 2 ? 1 : left <= 5 ? 2 : 4) : (left <= 10 ? 1 : 4);
    if (pulse % rate === 0) click(fast ? 900 + 300 * (1 - left / duration) : 800, 0.035, 0.045);
  }, 250);
}

function stopTicking() { if (clockTimer) { clearInterval(clockTimer); clockTimer = null; } }

// --- La ruleta (canvas decorativo; el control real es el botón) ---
const canvas = $("wheel"), ctx = canvas.getContext("2d");
let LABELS = ["RETO", "VERDAD"];
let COLORS = ["#e53935", "#1e88e5"];
const PALETTE = ["#e53935", "#1e88e5", "#43a047", "#fdd835", "#8e24aa", "#fb8c00", "#00acc1"];
let rotation = 0;
function drawWheel(rot) {
  const c = canvas.width / 2, r = c - 10;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const n = LABELS.length * 4;
  for (let i = 0; i < n; i++) {
    const start = rot + (i * 2 * Math.PI) / n, end = rot + ((i + 1) * 2 * Math.PI) / n;
    ctx.beginPath(); ctx.moveTo(c, c); ctx.arc(c, c, r, start, end); ctx.closePath();
    ctx.fillStyle = COLORS[i % COLORS.length]; ctx.fill();
    ctx.strokeStyle = "#000"; ctx.lineWidth = 4; ctx.stroke();
    ctx.save();
    ctx.translate(c, c); ctx.rotate(start + Math.PI / n);
    ctx.fillStyle = "#fff"; ctx.font = "bold " + (LABELS.length > 4 ? 18 : 34) + "px system-ui";
    ctx.textAlign = "right"; ctx.textBaseline = "middle";
    const label = LABELS[i % LABELS.length];
    ctx.fillText(label.length > 12 ? label.slice(0, 11) : label, r - 24, 0);
    ctx.restore();
  }
  ctx.beginPath(); ctx.arc(c, c, 26, 0, 2 * Math.PI);
  ctx.fillStyle = "#fdd835"; ctx.fill();
  ctx.beginPath(); ctx.moveTo(c - 18, 8); ctx.lineTo(c + 18, 8); ctx.lineTo(c, 44);
  ctx.closePath(); ctx.fillStyle = "#fdd835"; ctx.fill();
}
drawWheel(0);
let animId = null;
function spinAnimation(finalAngle) {
  const start = rotation, giros = 5 * 2 * Math.PI;
  const target = giros + ((360 - finalAngle) * Math.PI) / 180;
  const dur = 3600, t0 = performance.now();
  cancelAnimationFrame(animId);
  function frame(t) {
    const k = Math.min(1, (t - t0) / dur);
    const ease = 1 - Math.pow(1 - k, 3);
    rotation = start + (target - start) * ease;
    drawWheel(rotation % (2 * Math.PI));
    if (k < 1) animId = requestAnimationFrame(frame);
  }
  animId = requestAnimationFrame(frame);
}

// --- El reloj del turno (visible; los avisos hablados los manda el server) ---
function startClock(duration = 60) {
  turnStartedAt = Date.now();
  clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    const left = Math.max(0, duration - Math.floor((Date.now() - turnStartedAt) / 1000));
    $("temporizador").textContent = left > 0 ? ("Quedan " + left + " segundos") : "";
  }, 1000);
}

// --- Chat ---
function addChatLine(text) {
  const li = document.createElement("li");
  li.textContent = text;
  $("chat-log").appendChild(li);
  while ($("chat-log").children.length > 30) $("chat-log").removeChild($("chat-log").firstChild);
}
function refreshChatTargets() {
  const sel = $("chat-para");
  const current = sel.value || "all";
  sel.innerHTML = "";
  const all = document.createElement("option");
  all.value = "all"; all.textContent = "Para todos";
  sel.appendChild(all);
  if (lastState) {
    for (const p of lastState.players) {
      if (p.id === myId) continue;
      const opt = document.createElement("option");
      opt.value = String(p.id); opt.textContent = "Para " + p.name;
      sel.appendChild(opt);
    }
  }
  sel.value = current;
}

// --- Pantallas de entrada ---
const parts = location.pathname.split("/");
const inviteCode = parts[2] === "sala" ? (parts[3] || "").toUpperCase() : null;

(function fillCats() {
  const sel = $("elegir-cat");
  const cats = ["Verdad o Reto|verdad_reto", "Deportes|deportes", "Fútbol mundial|fútbol mundial",
    "Películas|películas", "Series|series", "Cultura|cultura", "Historia|historia", "Ciencia|ciencia",
    "Arte|arte", "Comida|comida", "Nombres y apellidos|nombres y apellidos", "Marcas|marcas",
    "Animales|animales", "Política|política", "Religión|religión", "Música|música",
    "Geografía|geografía", "Tecnología|tecnología", "Videojuegos|videojuegos",
    "Refranes|refranes", "Países|países"];
  for (const item of cats) {
    const label = item.split("|")[0], val = item.split("|")[1];
    const opt = document.createElement("option");
    opt.value = val; opt.textContent = label;
    sel.appendChild(opt);
  }
})();

(function fillCupos() {
  const sel = $("cupos-select");
  for (let n = 2; n <= 20; n++) {
    const opt = document.createElement("option");
    opt.value = String(n); opt.textContent = String(n);
    sel.appendChild(opt);
  }
})();

if (inviteCode) {
  $("nombre-input").value = myName;
  show("pantalla-unirse");
  announce("Te invitaron a una mesa. Si querés, escribí tu nombre; si no, sos Jugador N. Tocá Entrar a jugar.");
} else {
  show("pantalla-inicio");
  announce("Bienvenido. Tenés tres opciones: Jugar solo, Sala de juegos de 2 a 20 jugadores, o Ruleta de Países.");
}
let pendingMode = "sala";

async function crearYEntrar(mode) {
  saveStartName();
  announce("Creando tu mesa...");
  const res = await fetch("/amor-con-aroma-a-cafe/api/salas", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({mode: mode}),
  });
  const data = await res.json();
  history.pushState(null, "", "/amor-con-aroma-a-cafe/sala/" + data.code);
  enterSala(data.code, myName);
}

$("btn-solo").addEventListener("click", () => {
  unlockAudio();
  pendingMode = "solo";
  show("pantalla-modo");
  announce("¿A qué querés jugar? Ruleta de categorías, ruleta de países, o el ahorcado.");
});

$("btn-modo-cat").addEventListener("click", () => { unlockAudio(); crearYEntrar(pendingMode); });
$("btn-modo-paises").addEventListener("click", () => {
  unlockAudio();
  crearYEntrar(pendingMode === "solo" ? "solo_paises" : "paises");
});

$("btn-modo-ahorcado").addEventListener("click", () => {
  unlockAudio();
  crearYEntrar(pendingMode === "solo" ? "solo_ahorcado" : "ahorcado");
});

$("btn-sala").addEventListener("click", () => {
  unlockAudio();
  pendingMode = "sala";
  show("pantalla-cupos");
  announce("¿Cuántos jugadores son? Elegí un número de 2 a 20 y tocá Crear la sala.");
});

$("btn-paises").addEventListener("click", () => {
  unlockAudio();
  pendingMode = "paises";
  show("pantalla-cupos");
  announce("Ruleta de Países. ¿Cuántos jugadores son? Elegí un número de 2 a 20 y tocá Crear la sala.");
});

$("btn-volver").addEventListener("click", () => {
  show("pantalla-inicio");
  announce("Tocá Jugar solo o Sala de juego.");
});

$("btn-crear").addEventListener("click", async () => {
  saveStartName();
  unlockAudio();
  announce("Creando la sala...");
  const res = await fetch("/amor-con-aroma-a-cafe/api/salas", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({mode: pendingMode === "paises" ? "paises" : "sala", capacity: parseInt($("cupos-select").value, 10)}),
  });
  const data = await res.json();
  history.pushState(null, "", "/amor-con-aroma-a-cafe/sala/" + data.code);
  enterSala(data.code, myName);
});

$("btn-entrar").addEventListener("click", () => {
  unlockAudio();
  const typed = $("nombre-input").value.trim();
  if (typed) { myName = typed; localStorage.setItem("cafe_nombre", myName); }
  enterSala(inviteCode, myName);
});

$("btn-copiar").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("link").textContent);
    announce("Link copiado. Pegalo en un mensaje para invitar a tus amigos.");
  } catch (err) {
    announce("No pude copiarlo. El link está escrito arriba.");
  }
});

$("btn-equipos").addEventListener("click", () => { if (ws && ws.readyState === 1) ws.send(JSON.stringify({action:"equipos",count:Number($("equipos-count").value)})); });
$("btn-equipo").addEventListener("click", () => { if (ws && ws.readyState === 1) ws.send(JSON.stringify({action:"equipo",team:Number($("equipo-select").value)})); });
$("btn-empezar").addEventListener("click", () => {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "start"}));
});

function enterSala(code, name) {
  salaCode = code;
  show("sala");
  $("compartir").hidden = false;
  $("link").textContent = location.origin + "/amor-con-aroma-a-cafe/sala/" + code;
  connect(code, name);
}

async function checkClientVersion() {
  if (micActive || document.visibilityState !== "visible") return;
  try {
    const r=await fetch("/amor-con-aroma-a-cafe/api/version",{cache:"no-store"});
    if(!r.ok)return;
    const data=await r.json();
    if(data.build && data.build!==CLIENT_BUILD) {
      announce("Actualizando el juego. Se conserva tu nombre y tu enlace de mesa.");
      location.reload();
    }
  } catch(err) {}
}
window.addEventListener("focus",checkClientVersion);
document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="visible")checkClientVersion();});
function connect(code, name) {
  const seatStorage = "cafe_asiento_" + code;
  let seatKey = sessionStorage.getItem(seatStorage);
  if (!seatKey) {
    seatKey = crypto.randomUUID ? crypto.randomUUID() : Array.from(crypto.getRandomValues(new Uint8Array(24))).map(x=>x.toString(16).padStart(2,"0")).join("");
    sessionStorage.setItem(seatStorage, seatKey);
  }
  ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://")
    + location.host + "/amor-con-aroma-a-cafe/ws/" + code
    + "?name=" + encodeURIComponent(name || "") + "&seat_key=" + encodeURIComponent(seatKey) + "&spectator=" + (watching ? "true" : "false"));
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.event === "welcome") {
      if (msg.build && msg.build !== CLIENT_BUILD) {
        announce("Hay una actualización del juego. Actualizando la página para recuperar tu mesa.");
        location.reload(); return;
      }
      myId = msg.id; myName = msg.name;
      lastQuestion = null;
      watching = !!msg.spectator;
      $("editar-nombre").value = myName;
      localStorage.setItem("cafe_nombre", myName);
      const codeSpelled = code.split("").join(" ");
      if (watching) announce("Entraste a mirar. Podés escuchar y usar el chat, sin turnos.");
      announce("Estás en la mesa " + codeSpelled + " como " + myName + ".");
    } else if (msg.event === "state") {
      onState(msg);
    } else if (msg.event === "boom") {
      boomSound();
      if (navigator.vibrate) navigator.vibrate([300, 120, 300]);
      announce("¡BOOM! Le explotó la bomba a " + msg.name + ".");
    } else if (msg.event === "your_turn") {
      if (msg.kind === "country") announce("Es tu turno. Tocá el botón Girar la ruleta de países.");
      else if (msg.kind === "ahorcado") announce("Es tu turno. Decí una letra con el botón Decirla por voz, o escribila y tocá Mandar.");
      else if (msg.kind === "bomba") announce("¡Tenés la bomba! Decí o escribí algo de la consigna antes de que explote.");
      else announce("Es tu turno. Tocá el botón Girar la ruleta, o elegí la categoría y tocá Jugar esta categoría.");
    } else if (msg.event === "spin_start") {
      if (msg.labels) { LABELS = msg.labels; COLORS = PALETTE; }
      announce("Gira la ruleta de " + msg.player + "...");
      spinSound();
      spinAnimation(msg.angle);
    } else if (msg.event === "await_done") {
      $("carta-texto").textContent = msg.label + ": " + msg.card;
    } else if (msg.event === "question") {
      onQuestion(msg);
    } else if (msg.event === "question_clock") {
      if (lastQuestion && lastQuestion.id === msg.id) {
        startClock(msg.seconds); startTicking(msg.seconds);
        $("btn-pregunta-lista").hidden = true;
        if (lastQuestion.player===myId && !micActive &&
            ($("pregunta").contains(document.activeElement) || document.activeElement===estado || document.activeElement===document.body)) {
          const first=document.querySelector("#pregunta .opcion:not(:disabled)");
          if(first)first.focus();
        }
      }
    } else if (msg.event === "chatter") {
      if (!micActive && !playing && !audioQueue.length) {
        queueAudio(msg.audio);
      }
    } else if (msg.event === "say") {
      announce(msg.text);
      if (msg.question_id != null) {
        if (!lastQuestion || lastQuestion.id !== msg.question_id) return;
        // A question must not wait behind stale encouragement or room greetings.
        player.pause(); playing = false; audioQueue.length = 0;
        queueAudio(msg.audio, () => readyQuestion(msg.question_id));
      } else queueAudio(msg.audio);
    } else if (msg.event === "chat") {
      const who = msg.to === "all" ? "" : " (privado)";
      addChatLine(msg.from_name + who + ": " + msg.text);
      if (!msg.echo) queueAudio(msg.audio);
    } else if (msg.event === "clip") {
      addChatLine("Nota de voz de " + msg.from_name + (msg.to === "all" ? "" : " (privada)"));
      if (!msg.echo) queueAudio(msg.url);
    }
  };
  ws.onclose = (ev) => {
    if (ev.code === 4001) { announce("Esta mesa quedó abierta en otra conexión de este navegador."); return; }
    if (ev.code === 4004) announce("Esa mesa ya no existe. Creá una nueva.");
    else if (ev.code === 4009) announce("La sala está llena. Pediles que armen otra.");
    else {
      announce("Se cortó la conexión. Reintentando...");
      setTimeout(() => connect(code, myName), 2000);
    }
  };
}

function onState(msg) {
  const prev = lastState;
  const newTurn = !prev || prev.turn !== msg.turn || prev.turn_number !== msg.turn_number || prev.case_idx !== msg.case_idx || prev.phase === "lobby" || prev.phase === "gameover";
  lastState = msg;
  refreshChatTargets();
  const ul = $("jugadores");
  ul.innerHTML = "";
  for (const p of msg.players) {
    const li = document.createElement("li");
    li.textContent = p.name + (p.spectator ? " (mirando)" : (msg.team_count && p.team != null ? " (equipo " + msg.team_names[p.team] + ")" : "") + ": " + p.score + " puntos") + (p.connected ? "" : " (se fue)");
    ul.appendChild(li);
  }
  const run = msg.quiz_run;
  const lives = msg.quiz_lives && msg.quiz_lives[myId];
  $("quiz-progreso").textContent = [lives != null ? "Tus vidas: " + lives + " de 4" : "", run ? "Categoría: " + run.correct + " de 5 correctas, " + run.answered + " respuestas" : ""].filter(Boolean).join(". ");
  const mine = msg.turn === myId;
  const spinPhases = ["spin_ready", "country_spin_ready", "verdad_reto_ready"];
  $("categorias").hidden = !(mine && msg.phase === "spin_ready");
  $("btn-girar").hidden = !spinPhases.includes(msg.phase);
  $("btn-girar").disabled = !mine || msg.spinning;
  let girarText = "Girar la ruleta";
  if (msg.phase === "country_spin_ready") girarText = "Girar la ruleta de países";
  $("btn-girar-text").textContent = msg.spinning ? "Girando..." : (mine ? girarText : "Esperando a " + (msg.turn_name || "alguien"));
  $("reto-verdad").hidden = !(mine && msg.phase === "verdad_reto");
  $("btn-volver-cuestionario").hidden=msg.phase!=="question";
  if (msg.phase !== "question") { $("pregunta").hidden = true; }
  else if (msg.question && (!lastQuestion || lastQuestion.id !== msg.question.id || $("pregunta").hidden)) {
    onQuestion(msg.question);
  }
  $("btn-empezar").hidden = !(msg.phase === "lobby" && msg.game && msg.players.some(p => !p.spectator && p.id === myId && msg.players.find(x => !x.spectator).id === myId) && msg.capacity !== 1);
  const host = msg.players.find(p => !p.spectator);
  const imHost = !!host && host.id === myId;
  $("equipos-panel").hidden = msg.phase !== "lobby" || watching;
  $("equipos-host").hidden = !imHost;
  $("equipos-count").value = String(msg.team_count || 0);
  $("equipo-propio").hidden = !msg.team_count;
  const me = msg.players.find(p => p.id === myId);
  $("equipo-select").innerHTML = "";
  (msg.team_names || []).forEach((name, i) => {
    const option = document.createElement("option");option.value = i;option.textContent = name;
    option.selected = !!me && me.team === i;$("equipo-select").appendChild(option);
  });
  $("elegir-juego").hidden = !(msg.phase === "lobby" && !msg.game && imHost);
  $("elegir-info").hidden = !(msg.phase === "lobby" && !msg.game && imHost);
  $("btn-info").hidden = !msg.game;
  const ah = msg.ahorcado;
  $("ahorcado").hidden = !(msg.game === "ahorcado" && ah);
  if (msg.game === "ahorcado" && ah) {
    $("ah-pista").textContent = "Pista: " + ah.hint;
    if (ah.hint && ah.hint !== lastHint) {
      lastHint = ah.hint;
      announce("Palabra nueva. Pista: " + ah.hint);
    }
    $("ah-tablero").textContent = ah.board;
    $("ah-intentos").textContent = "Quedan " + ah.attempts + " intentos para esta palabra";
    $("ah-letras").textContent = ah.wrong.length ? "Letras que no están: " + ah.wrong.join(", ") : "";
    $("btn-ah-mandar").disabled = !mine;
    $("btn-ah-voz").disabled = !mine;
    $("ah-input").disabled = !mine;
  }
  const bb = msg.bomba;
  $("bomba").hidden = !(msg.game === "bomba" && bb);
  if (msg.game === "bomba" && bb) {
    $("bb-consigna").textContent = "Consigna: " + bb.prompt;
    $("bb-quien").textContent = "La bomba la tiene " + (msg.turn_name || "") + ". La mecha: " + bb.fuse + " segundos.";
    const myLives = bb.lives && myId != null ? bb.lives[myId] : null;
    $("bb-vidas").textContent = myLives != null ? ("Tus vidas: " + myLives) : "";
    $("btn-bb-mandar").disabled = !mine;
    $("btn-bb-voz").disabled = !mine;
    $("bb-input").disabled = !mine;
  }
  const mst = msg.misterio;
  $("misterio").hidden = !(msg.game === "misterio" && mst);
  if (msg.game === "misterio" && mst) {
    $("mst-titulo").textContent = "Misterio: " + mst.title;
    $("mst-caso").textContent = mst.case;
    const myLives = mst.lives && myId != null ? mst.lives[myId] : null;
    const owner = msg.team_count && me ? "equipo:" + me.team : myId;
    const mySolved = mst.solved && owner != null ? (mst.solved[owner] || 0) : 0;
    ["btn-mst-mandar", "btn-mst-voz", "mst-input"].forEach(id => $(id).disabled = watching || !!(me && me.out));
    $("mst-vidas").textContent = (myLives != null ? "Tus vidas: " + myLives + ". " : "") +
      "Casos tuyos: " + mySolved + " de " + mst.to_win + ".";
  }
  if (newTurn && !["question", "spin_ready", "country_spin_ready", "verdad_reto_ready"].includes(msg.phase) && msg.phase !== "lobby" && msg.phase !== "gameover") { startClock(msg.game === "bomba" && bb ? bb.fuse : msg.game === "misterio" ? 150 : 60); startTicking(msg.game === "bomba" && bb ? bb.fuse : msg.game === "misterio" ? 150 : 60); }
  if (msg.phase === "lobby" || msg.phase === "gameover") { stopTicking(); lastHint = null; }
  if (msg.phase === "gameover") { clearInterval(timerInterval); $("temporizador").textContent = ""; }
}

function focusQuestion() {
  if (!lastQuestion) return;
  $("pregunta").hidden=false;
  $("pregunta-texto").focus();
  $("pregunta").scrollIntoView({block:"start",behavior:"auto"});
  announce("Pregunta: "+lastQuestion.q+". Opciones: "+lastQuestion.options.join(". ")+". Después de la lectura tenés sesenta segundos para responder.");
}
$("btn-volver-cuestionario").addEventListener("click",focusQuestion);
function readyQuestion(id) {
  if (ws && ws.readyState === 1 && lastQuestion && lastQuestion.id === id && lastQuestion.player === myId)
    ws.send(JSON.stringify({action:"question-ready", id}));
}
$("btn-pregunta-lista").addEventListener("click", () => { if (lastQuestion) readyQuestion(lastQuestion.id); });
$("btn-pregunta-repetir").addEventListener("click", () => {
  unlockAudio();
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action:"repetir-pregunta"}));
});
function onQuestion(msg) {
  clearInterval(timerInterval); stopTicking();
  $("temporizador").textContent = "El tiempo empieza al terminar la lectura o al tocar Empezar a responder.";
  lastQuestion = msg;
  $("pregunta").hidden = false;
  const letters = ["A", "B", "C", "D"];
  $("pregunta-texto").textContent = msg.q;
  const mine = msg.player === myId;
  $("btn-pregunta-lista").hidden = !mine || !!msg.clock_started;
  $("btn-pregunta-repetir").disabled = !mine;
  document.querySelectorAll("#pregunta .opcion").forEach((btn, i) => {
    btn.textContent = "Opción " + letters[i] + ": " + msg.options[i];
    btn.setAttribute("aria-label", "Opción " + letters[i] + ": " + msg.options[i]);
    btn.disabled = !mine;
  });
  $("btn-voz-resp").disabled = !mine;
  if (mine) {
    $("btn-volver-cuestionario").hidden=false;
    focusQuestion();
  }
  if (!mine) announce("Pregunta para " + (lastState ? lastState.turn_name : "otro jugador") + ": " + msg.q);
}

$("btn-elegir").addEventListener("click", () => {
  const cat = $("elegir-cat").value;
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "category", category: cat}));
  $("categorias").hidden = true;
});

$("btn-girar").addEventListener("click", () => {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "spin"}));
});

document.querySelectorAll("#pregunta .opcion").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "answer", idx: parseInt(btn.dataset.idx, 10)}));
    $("pregunta").hidden = true;
  });
});

$("btn-juego-cat").addEventListener("click", () => {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "juego", game: "categorias"}));
});
$("btn-juego-paises").addEventListener("click", () => {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "juego", game: "paises"}));
});
$("btn-juego-ahorcado").addEventListener("click", () => {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "juego", game: "ahorcado"}));
});
const LOCAL_DESCRIPTIONS = {"bomba": "La bomba: decí una respuesta que cumpla la consigna antes de que se termine la mecha. Si vale, pasás la bomba. Si no vale o se acaba el tiempo, perdés una vida.", "misterio": "Resolver el misterio: escuchá el caso y proponé una teoría hablando o escribiendo. Acertar gana el caso. Una teoría lejos de la solución cuesta una vida.", "categorias": "Girás la ruleta y seguís en la categoría que salga hasta conseguir cinco respuestas correctas. Empezás con cuatro vidas; cada error cuesta una. Cinco correctas seguidas regalan una vida, sin superar cuatro. Sin vidas volvés al comienzo y girás de nuevo, con cuatro vidas. No quedás eliminado. El primero en pasar tres categorías gana.", "paises": "Primero girás la ruleta de países. Girás la ruleta y seguís en la categoría que salga hasta conseguir cinco respuestas correctas. Empezás con cuatro vidas; cada error cuesta una. Cinco correctas seguidas regalan una vida, sin superar cuatro. Sin vidas volvés al comienzo y girás de nuevo, con cuatro vidas. No quedás eliminado. Completá todas las categorías para ganar el país. Dos países ganan la partida.", "ahorcado": "El ahorcado: adivinás la palabra letra por letra, hablando o escribiendo. Si la letra está, seguís jugando; si no, pasa el turno. El que adivina la palabra sube de nivel; el primero en pasar el nivel 5 gana."};

function askDescription(game) {
  if (salaCode && ws && ws.readyState === 1) ws.send(JSON.stringify({action: "descripcion", game: game}));
  announce(LOCAL_DESCRIPTIONS[game]);
}
$("btn-info-bomba").addEventListener("click", () => askDescription("bomba"));
$("btn-info-misterio").addEventListener("click", () => askDescription("misterio"));
$("btn-info-cat").addEventListener("click", () => askDescription("categorias"));
$("btn-info-paises").addEventListener("click", () => askDescription("paises"));
$("btn-info-ahorcado").addEventListener("click", () => askDescription("ahorcado"));
$("btn-info").addEventListener("click", () => askDescription(lastState && lastState.game ? lastState.game : "ahorcado"));

function sendGuess() {
  const t = $("ah-input").value.trim();
  if (!t || !ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({action: "guess", text: t}));
  $("ah-input").value = "";
}
$("btn-ah-mandar").addEventListener("click", sendGuess);
$("ah-input").addEventListener("keydown", (e) => { if (e.key === "Enter") sendGuess(); });

function sendVoiceText(text) {
  if (salaCode && ws && ws.readyState === 1) ws.send(JSON.stringify({action: "voz-texto", text: text}));
}
function oneTapVoice(id) {
  $(id).addEventListener("click", async () => {
    if (micActive) return;
    unlockAudio();
    setMic(true);
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SR) {
      try {
        const rec = new SR();
        rec.lang = "es-AR";
        rec.interimResults = false;
        rec.maxAlternatives = 1;
        let got = false;
        announce("Te escucho. Hablá tranquilo: se manda sola.");
        rec.onresult = (e) => {
          got = true;
          setMic(false);
          const text = e.results[0][0].transcript;
          announce("Dijiste: " + text);
          sendVoiceText(text);
        };
        rec.onerror = () => { setMic(false); if (!got) announce("No te escuché. Probá de nuevo o escribila."); };
        rec.onend = () => { setMic(false); if (!got) announce("No te escuché. Probá de nuevo o escribila."); };
        rec.start();
        return;
      } catch (err) { /* fall through to the audio-upload path */ }
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio: true});
      const chunks = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
      const stopped = new Promise((res) => { recorder.onstop = res; });
      recorder.start();
      announce("Te escucho. Hablá tranquilo: se manda sola cuando terminás.");
      const mic = new (window.AudioContext || window.webkitAudioContext)();
      const analyser = mic.createAnalyser();
      analyser.fftSize = 512;
      mic.createMediaStreamSource(stream).connect(analyser);
      const buf = new Uint8Array(analyser.frequencyBinCount);
      let silentMs = 0, heard = false;
      const t0 = performance.now();
      while (recorder.state === "recording") {
        await new Promise((r) => setTimeout(r, 100));
        analyser.getByteTimeDomainData(buf);
        let peak = 0;
        for (const v of buf) peak = Math.max(peak, Math.abs(v - 128));
        if (peak > 12) { heard = true; silentMs = 0; } else silentMs += 100;
        if ((heard && silentMs >= 1400) || performance.now() - t0 > 9000) recorder.stop();
      }
      await stopped;
      stream.getTracks().forEach((t) => t.stop());
      mic.close();
      setMic(false);
      if (!heard) { announce("No escuché nada. Tocá el botón y hablá más cerca del micrófono."); return; }
      const blob = new Blob(chunks, {type: recorder.mimeType || "audio/webm"});
      announce("Mandando lo que dijiste...");
      try {
        const res = await fetch("/amor-con-aroma-a-cafe/api/voz-respuesta/" + salaCode + "?sender=" + myId, {method: "POST", body: blob});
        if (!res.ok) announce("No te entendí. Probá de nuevo o escribila.");
      } catch (err) { announce("No pude mandar tu voz. Escribila mejor."); }
    } catch (err) { setMic(false); announce("No pude usar el micrófono. Escribila mejor."); }
  });
}
oneTapVoice("btn-voz-resp");
oneTapVoice("btn-ah-voz");
oneTapVoice("btn-bb-voz");
oneTapVoice("btn-mst-voz");

function boomSound() {
  try {
    if (!audioCtx) return;
    const dur = 0.9, sr = audioCtx.sampleRate;
    const buf = audioCtx.createBuffer(1, dur * sr, sr);
    const data = buf.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / data.length, 2);
    const src = audioCtx.createBufferSource();
    src.buffer = buf;
    const gain = audioCtx.createGain();
    gain.gain.setValueAtTime(0.9, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + dur);
    src.connect(gain).connect(audioCtx.destination);
    src.start();
  } catch (err) {}
}

$("btn-modo-bomba").addEventListener("click", () => {
  crearYEntrar(pendingMode === "solo" ? "solo_bomba" : "bomba");
});
$("btn-modo-misterio").addEventListener("click", () => {
  crearYEntrar(pendingMode === "solo" ? "solo_misterio" : "misterio");
});
$("btn-juego-bomba").addEventListener("click", () => {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "juego", game: "bomba"}));
});
$("btn-juego-misterio").addEventListener("click", () => {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "juego", game: "misterio"}));
});

function sendBomba() {
  const t = $("bb-input").value.trim();
  if (!t || !ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({action: "guess", text: t}));
  $("bb-input").value = "";
}
$("btn-bb-mandar").addEventListener("click", sendBomba);
$("bb-input").addEventListener("keydown", (e) => { if (e.key === "Enter") sendBomba(); });

function sendMisterio() {
  const t = $("mst-input").value.trim();
  if (!t || !ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({action: "guess", text: t}));
  $("mst-input").value = "";
}
$("btn-mst-mandar").addEventListener("click", sendMisterio);
$("mst-input").addEventListener("keydown", (e) => { if (e.key === "Enter") sendMisterio(); });



$("btn-listo").addEventListener("click", () => {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "listo"}));
});
$("btn-pasar").addEventListener("click", () => {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action: "pasar"}));
});

// --- Chat: texto ---
$("btn-chat").addEventListener("click", () => {
  const text = $("chat-texto").value.trim();
  if (!text || !ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({action: "chat", to: $("chat-para").value === "all" ? "all" : parseInt($("chat-para").value, 10), text: text}));
  $("chat-texto").value = "";
  announce("Mensaje mandado.");
});

// --- Chat: nota de voz ---
let recorder = null, chunks = [];
$("btn-grabar").addEventListener("click", async () => {
  if (recorder && recorder.state === "recording") {
    recorder.stop();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
    chunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      $("btn-grabar").textContent = "Grabar nota de voz";
      $("btn-grabar").setAttribute("aria-label", "Grabar una nota de voz");
      const blob = new Blob(chunks, {type: recorder.mimeType || "audio/webm"});
      const to = $("chat-para").value;
      announce("Mandando tu nota de voz...");
      try {
        const res = await fetch("/amor-con-aroma-a-cafe/api/voz/" + salaCode + "?to=" + encodeURIComponent(to) + "&sender=" + myId, {method: "POST", body: blob});
        announce(res.ok ? "Nota de voz mandada." : "No pude mandar la nota. Probá de nuevo.");
      } catch (err) {
        announce("No pude mandar la nota. Probá de nuevo.");
      }
    };
    recorder.start();
    $("btn-grabar").textContent = "Parar y mandar";
    $("btn-grabar").setAttribute("aria-label", "Parar la grabación y mandar la nota de voz");
    announce("Grabando. Tocá Parar y mandar cuando termines.");
  } catch (err) {
    announce("No tengo permiso para el micrófono. Podés escribir el mensaje.");
  }
});
</script>
</body>
</html>
"""


@router.get("/amor-con-aroma-a-cafe/audio/{name}")
async def serve_audio(name: str):
    """Serves a cached narration mp3 (one hour TTL)."""
    key = name[:-4] if name.endswith(".mp3") else name
    item = audio_cache.get(key)
    if item is None:
        return Response(status_code=404)
    return Response(content=item[0], media_type="audio/mpeg")


@router.get("/amor-con-aroma-a-cafe", response_class=HTMLResponse)
@router.get("/amor-con-aroma-a-cafe/sala/{code}", response_class=HTMLResponse)
async def page(code: str = ""):
    return HTMLResponse(PAGE, headers={"Cache-Control":"no-store, no-cache, must-revalidate, max-age=0", "Pragma":"no-cache", "Expires":"0"})


# Fingerprint of the HTML before inserting itself: changes whenever the client changes.
CLIENT_BUILD = hashlib.sha256(PAGE.encode()).hexdigest()[:16]
PAGE = PAGE.replace("__CAFE_BUILD__", CLIENT_BUILD)


@router.get("/amor-con-aroma-a-cafe/api/version")
async def client_version():
    return Response(json.dumps({"build":CLIENT_BUILD}),media_type="application/json",
                    headers={"Cache-Control":"no-store"})
