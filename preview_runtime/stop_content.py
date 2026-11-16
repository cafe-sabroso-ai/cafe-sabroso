"""Common-word recognition, not an exhaustive dictionary. Unknown answers require review."""
CATEGORIES=('nombre','animal','país','comida','objeto')
# Intentionally a limited letter wheel. Every included letter has examples in all categories.
RAW={
'A':('Ana|Andrés|Alba','abeja|águila|ardilla','Argentina|Australia|Alemania','arroz|aceituna|almendra','anillo|aguja|almohada'),
'B':('Beto|Bruno|Beatriz','ballena|burro|búho','Bolivia|Brasil|Bélgica','banana|batata|budín','botella|banco|balde'),
'C':('Caro|Carlos|Camila','caballo|conejo|cabra','Chile|Colombia|Canadá','carne|cereza|chocolate','cama|cuchara|cuaderno'),
'D':('Dani|Diego|Daniela','delfín|dromedario|dingo','Dinamarca|Dominica','durazno|dátil|dulce','dado|dedal|destornillador'),
'E':('Elena|Eduardo|Emilia','elefante|erizo|escarabajo','España|Ecuador|Egipto','empanada|espinaca|ensalada','espejo|escoba|estuche'),
'F':('Florencia|Felipe|Francisco','foca|flamenco|faisán','Francia|Finlandia|Filipinas','fideos|frutilla|flan','flauta|frasco|farol'),
'G':('Gabriela|Gonzalo|Guillermo','gato|gallina|gorila','Guatemala|Grecia|Ghana','galleta|garbanzo|gelatina','goma|gorra|guante'),
'L':('Lucía|Lucas|Laura','león|lobo|lagarto','Líbano|Lituania|Letonia','lechuga|lenteja|limón','lápiz|libro|linterna'),
'M':('María|Mateo|Martín','mono|mariposa|murciélago','México|Marruecos|Madagascar','manzana|milanesa|mandarina','mesa|martillo|mochila'),
'P':('Pedro|Paula|Pablo','perro|pato|pingüino','Perú|Paraguay|Portugal','pan|papa|pera','plato|peine|pelota'),
'R':('Rosa|Ramiro|Rocío','rana|rinoceronte|ratón','Rusia|Rumania|Ruanda','ravioles|rabanito|rúcula','regla|reloj|regadera'),
'S':('Sofía|Santiago|Sergio','serpiente|sapo|salmón','Suecia|Suiza|Senegal','sopa|sandía|sándwich','silla|sombrero|servilleta'),
'T':('Tomás|Teresa|Tamara','tigre|tortuga|tucán','Turquía|Túnez|Tanzania','tomate|tarta|tortilla','taza|tijera|toalla')}


def examples(letter,category):return RAW[letter][CATEGORIES.index(category)].split('|')
