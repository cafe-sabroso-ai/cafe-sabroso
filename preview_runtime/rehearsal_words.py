# No network and no Telegram integration in this isolated rehearsal.
import re,unicodedata,random


AHORCADO_BANK = [
    # 4-5 letras (nivel 1)
    ("MATE", "Infusión caliente que se comparte con bombilla."),
    ("GATO", "Animal que maúlla y duerme mucho."),
    ("LUNA", "Se ve de noche en el cielo."),
    ("TREN", "Va por las vías con vagones."),
    ("NUBE", "Blanca, flota en el cielo y a veces trae lluvia."),
    ("FARO", "Torre que guía a los barcos con su luz."),
    ("FLOR", "Crece en el jardín y huele rico."),
    ("DEDO", "Tenés cinco en cada mano."),
    ("VASO", "Se usa para tomar agua."),
    ("BOTE", "Barquito chico a remo."),
    ("PERRO", "El mejor amigo del hombre."),
    ("TORTA", "Se come en los cumpleaños."),
    ("LLAVE", "Sirve para abrir puertas."),
    ("SILLA", "Tiene cuatro patas y se usa para sentarse."),
    ("RADIO", "Aparato para escuchar música y noticias."),
    ("PLAZA", "Lugar con juegos y bancos para los chicos."),
    ("PLATO", "Ahí se sirve la comida."),
    ("CAMPO", "Lugar con vacas y sembrados."),
    ("LIBRO", "Tiene páginas para leer."),
    ("BANCO", "Te sentás en la plaza; también guarda plata."),
    ("PEINE", "Ordena el pelo."),
    ("JABON", "Hace espuma para lavarse."),
    ("QUESO", "Va rallado sobre los fideos."),
    # 6 letras (nivel 2)
    ("HELADO", "Postre frío y dulce."),
    ("ZAPATO", "Prenda que va en el pie."),
    ("ESPEJO", "Te devuelve tu imagen."),
    ("AZUCAR", "Endulza el café."),
    ("PUERTA", "Se abre para entrar a casa."),
    ("CAMINO", "Sendero que lleva a algún lugar."),
    ("PUEBLO", "Ciudad chiquita."),
    ("PIERNA", "La usás para patear una pelota."),
    ("MONEDA", "Plata chica de metal; sirve para el colectivo."),
    ("PLANTA", "Verde, crece en una maceta."),
    ("SOMBRA", "Te cubre del sol bajo el árbol."),
    ("BANANA", "Fruta amarilla que se pela."),
    ("COCINA", "Ambiente donde se prepara la comida."),
    ("PASTEL", "Torta dulce de cumpleaños."),
    # 7 letras (nivel 3)
    ("FACTURA", "Pastelito dulce que acompaña el mate."),
    ("VENTANA", "Abertura en la pared para ver afuera."),
    ("CUCHARA", "Utensilio para comer la sopa."),
    ("BOTELLA", "Envase para guardar líquidos."),
    ("TECLADO", "Tiene teclas con letras."),
    ("PELUCHE", "Juguete blando para abrazar."),
    ("LAMPARA", "Da luz sobre la mesa."),
    ("CABALLO", "Animal que se monta y relincha."),
    ("MANTECA", "Se unta en el pan."),
    ("VERDURA", "Lechuga o tomate: comida sana."),
    ("ZAPALLO", "Naranja y grande, va en la sopa o el puré."),
    ("NARANJA", "Fruta cítrica con mucho jugo."),
    ("CORAZON", "Órgano que late en el pecho."),
    ("SEMILLA", "Chiquita, se planta y crece."),
    # 8 letras (nivel 4)
    ("GUITARRA", "Instrumento de seis cuerdas."),
    ("BILLETERA", "Guarda la plata y las tarjetas."),
    ("PARAGUAS", "Te protege de la lluvia."),
    ("ESCALERA", "Sirve para subir a lo alto."),
    ("CAMISETA", "Prenda de manga corta; también la de tu club."),
    ("ALMOHADA", "Apoya la cabeza para dormir."),
    ("CUADERNO", "Tiene hojas para escribir."),
    ("MARIPOSA", "Insecto de alas de colores."),
    ("HELADERA", "Mantiene la comida fría en la cocina."),
    ("TELARAÑA", "La teje la araña en un rincón."),
    ("SOMBRERO", "Te cubre la cabeza del sol."),
    ("ELEFANTE", "Animal enorme con trompa."),
    # 9-10 letras (nivel 5 en adelante)
    ("AURICULAR", "Va en la oreja para escuchar música."),
    ("BICICLETA", "Dos ruedas y pedales."),
    ("CHOCOLATE", "Dulce marrón, el favorito de muchos."),
    ("CUCURUCHO", "El cono crocante del helado."),
    ("PARACAIDAS", "Te salva al saltar de un avión."),
    ("MURCIELAGO", "Animal nocturno que vuela."),
    ("DINOSAURIO", "Reptil gigante que ya no existe."),
    ("BIBLIOTECA", "Lugar lleno de libros para leer."),
    ("AEROPUERTO", "De ahí salen y llegan los aviones."),
    ("LAVARROPAS", "Electrodoméstico que lava la ropa solo."),
    ("MICROONDAS", "Calienta la comida en un minuto."),
    ("ESCARABAJO", "Insecto de caparazón duro."),
    ("HIPOPOTAMO", "Animal enorme que vive en el río."),
]

AHORCADO_SPEAK = {
    "A": "a", "B": "be", "C": "ce", "D": "de", "E": "e", "F": "efe",
    "G": "ge", "H": "hache", "I": "i", "J": "jota", "K": "ka",
    "L": "ele", "M": "eme", "N": "ene", "Ñ": "eñe", "O": "o",
    "P": "pe", "Q": "cu", "R": "ere", "S": "ese", "T": "te",
    "U": "u", "V": "ve", "W": "uve doble", "X": "equis", "Y": "ye",
    "Z": "zeta",
}

def ahorcado_clean(text: str) -> str:
    """Uppercase letters only; tildes dropped, Ñ preserved."""
    table = str.maketrans("ÁÉÍÓÚÜáéíóúü", "AEIOUUaeiouu")
    cleaned = text.strip().translate(table).upper()
    return "".join(
        char for char in cleaned if char in "ABCDEFGHIJKLMNOPQRSTUVWXYZÑ"
    )

def ahorcado_parse_guess(text: str):
    """('letter', 'E') | ('word', 'PALABRA') | None from voice or typed input."""
    cleaned = normalized(text).strip(" .,!¿?¡")
    cleaned = re.sub(r"^(?:(?:la|el|una|un|letra|es)\s+)+", "", cleaned)
    if cleaned in ("ene", "enie") and re.search(r"eñe|enie", text.lower()):
        return ("letter", "Ñ")  # normalized() flattens eñe to ene; check the raw text
    if len(cleaned) == 1 and cleaned.isalpha():
        return ("letter", ahorcado_clean(cleaned))
    if cleaned in AHORCADO_LETTER_NAMES:
        return ("letter", AHORCADO_LETTER_NAMES[cleaned])
    word = ahorcado_clean(cleaned)
    if len(word) >= 2:
        return ("word", word)
    return None

def ahorcado_band(level: int):
    """Word-length band per level: the difficulty that rises each level."""
    if level <= 1:
        return (4, 5)
    if level == 2:
        return (6, 6)
    if level == 3:
        return (7, 7)
    if level == 4:
        return (8, 8)
    return (9, 10)

def ahorcado_attempts_for(word: str) -> int:
    """His rule: 4 attempts for 7+ letters, 3 attempts for 6 or fewer."""
    return 4 if len(word) >= 7 else 3
def normalized(text: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(char) != "Mn"
    )
