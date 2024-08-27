import os
import re

import openai
from fuzzywuzzy import process
from sqlalchemy import select
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from app.database import SessionLocal
from app.models import Product
from app.utils.keyboards import (show_categories, show_most_ordered_product, show_most_sold_drink,
                                 show_most_sold_sport_drink, show_most_sold_breakfast, show_most_sold_starter,
                                 show_most_sold_second, show_most_sold_snack, recommend_drink_by_price,
                                 recommend_sport_drink_by_price, recommend_breakfast_by_price,
                                 recommend_starter_by_price, recommend_second_by_price, recommend_snack_by_price,
                                 show_product_by_name, show_product_stock_by_name, show_product_stock_by_productname,
                                 show_product_price_by_name, show_most_sold_main, show_products_by_category_name,
                                 show_lunch_products)
from app.utils.logging_config import setup_logging
from app.utils.rating import handle_comment, handle_rating
from app.utils.rules import rules

logger = setup_logging()

# Configurar API de OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Construir el contexto del sistema dinámicamente
system_context = {
    "role": "system",
    "content": " ".join(rules)  # Une las cadenas en rules en una sola cadena
}

# Definir constantes para patrones de expresiones regulares
MENU_PATTERNS = [
    r'\bmen[úu]\b', r'\bcarta\b', r'\bver opciones\b', r'\bver men[úu]\b', r'\bver carta\b'
]

# Expresiones regulares para obtener el producto más pedido
MOST_ORDERED_PRODUCT_PATTERNS = [
    r'\bproducto m[aá]s pedido\b', r'\borden m[aá]s pedida\b', r'\bproducto m[aá]s vendido\b',
    r'\borden m[aá]s vendida\b', r'\bcu[aá]l es el producto más pedido\b', r'\bcu[aá]l es el producto m[aá]s popular\b',
    r'\bcu[aá]l es el producto m[aá]s vendido\b', r'\bcu[aá]l es la orden m[aá]s pedida\b',
    r'\bcu[aá]l es el pedido m[aá]s popular\b', r'\bcu[aá]l es la venta m[aá]s popular\b',
    r'\bcu[aá]l es la orden m[aá]s vendida\b', r'\bcu[aá]l es la venta m[aá]s vendida\b',
]

MOST_SOLD_DRINK_PATTERNS = [
    r'\bbebida m[aá]s vendida\b', r'\bbebida m[aá]s popular\b', r'\bbebida m[aá]s pedida\b',
    r'\bcu[aá]l es la bebida más vendida\b', r'\bcu[aá]l es la bebida más popular\b',
    r'\bcu[aá]l es la bebida más pedida\b', r'\bcu[aá]l es la bebida más solicitada\b',
    r'[Qq]u[eé] bebida es la m[aá]s vendida\b', r'[Qq]u[eé] bebida es la m[aá]s popular\b'
]

MOST_SOLD_SPORT_DRINK_PATTERNS = [
    r'\bbebida deportiva m[aá]s vendida\b', r'\bbebida deportiva m[aá]s popular\b',
    r'\bbebida deportiva m[aá]s pedida\b',
    r'\bcu[aá]l es la bebida deportiva más vendida\b', r'\bcu[aá]l es la bebida deportiva más popular\b',
    r'\bcu[aá]l es la bebida deportiva más pedida\b', r'\bcu[aá]l es la bebida deportiva más solicitada\b',
    r'[Qq]u[eé] bebida deportiva es la m[aá]s vendida\b', r'[Qq]u[eé] bebida deportiva es la m[aá]s popular\b'
]

MOST_SOLD_BREAKFAST_PATTERNS = [
    r'\bdesayuno m[aá]s vendido\b', r'\bdesayuno m[aá]s popular\b', r'\bdesayuno m[aá]s pedido\b',
    r'\bcu[aá]l es el desayuno m[aá]s vendido\b', r'\bcu[aá]l es el desayuno m[aá]s popular\b',
    r'\bcu[aá]l es el desayuno m[aá]s pedido\b', r'\bcu[aá]l es el desayuno m[aá]s solicitado\b',
    r'[Qq]u[eé] desayuno es el m[aá]s vendido\b', r'[Qq]u[eé] desayuno es el m[aá]s popular\b'

]

MOST_SOLD_STARTER_PATTERNS = [
    r'\bentrada m[aá]s vendida\b', r'\bentrada m[aá]s popular\b', r'\bentrada m[aá]s pedida\b',
    r'\bcu[aá]l es la entrada m[aá]s vendida\b', r'\bcu[aá]l es la entrada más popular\b',
    r'\bcu[aá]l es la entrada m[aá]s pedida\b', r'\bcu[aá]l es la entrada más solicitada\b',
    r'[Qq]u[eé] entrada es la m[aá]s vendida\b', r'[Qq]u[eé] entrada es la m[aá]s popular\b'
]

MOST_SOLD_SECOND_COURSE_PATTERNS = [
    r'\bsegundo m[aá]s vendido\b', r'\bsegundo m[aá]s popular\b', r'\bsegundo m[aá]s pedido\b',
    r'\bcu[aá]l es el segundo más vendido\b', r'\bcu[aá]l es el segundo más popular\b',
    r'\bcu[aá]l es el segundo más pedido\b', r'\bcu[aá]l es el segundo más solicitado\b',
    r'[Qq]u[eé] segundo es el m[aá]s vendido\b', r'[Qq]u[eé] segundo es el m[aá]s popular\b'
]

MOST_SOLD_SNACK_PATTERNS = [
    r'\bsnack m[aá]s vendido\b', r'\bsnack m[aá]s popular\b', r'\bsnack m[aá]s pedido\b',
    r'\bcu[aá]l es el snack m[aá]s vendido\b', r'\bcu[aá]l es el snack m[aá]s popular\b',
    r'\bcu[aá]l es el snack m[aá]s pedido\b', r'\bcu[aá]l es el snack m[aá]s solicitado\b',
    r'[Qq]u[eé] snack es el m[aá]s vendido\b', r'[Qq]u[eé] snack es el m[aá]s popular\b'
]

# Expresiones regulares para detectar categorías como "desayunos", "bebidas", etc.
PRODUCT_BY_NAME_CATEGORY_PATTERNS = [
    r'\b(?:qu[eé]|me\s+gustar[ií]a)\s+(?:ver|tener|una|la|un)\s+(desayunos?|bebidas?|bebidas deportivas?|entradas?|platos?|snacks?|almuerzos?|segundos?|postres?)\b',
    r'\b(?:mu[ée]strame|ens[ée][ñn]ame|ver|quiero\s+ver)\s+(?:el\s+)?(?:men[úu]|lista)\s+(?:de\s+)?(\w+)\b',
    r'\b(?:productos|art[ií]culos|opciones|cosas)\s+(?:de\s+la\s+categor[ií]a\s+)?(\w+)\b',
    r'\b(?:categor[ií]a\s+de\s+)?(\w+)\s+(?:productos|art[ií]culos|opciones|men[úu])\b',
    r'\b(?:tienes|hay)\s+(\w+)\s+(?:en\s+(?:el\s+men[úu]|la\s+categor[ií]a))\b',
    r'\b(?:quiero\s+la\s+lista\s+de\s+(\w+))\b',
    r'\b(?:cu[áa]les\s+son\s+los\s+productos\s+de\s+la\s+categor[ií]a\s+(\w+))\b',
]

# Bloquea si en la búsqueda de productos aparece una palabra que puede ser una categoría
PRODUCT_BY_NAME_PATTERN = [
    r'\b(?:tienes|quiero|quisiera|necesito|me\s+gustar[ií]a(?:\s+pedir|ordenar)?|deseo)\s+(?:una|un|la|el)\s+(?!desayuno|almuerzo|segundo|entrada|snack|postre\b)([\w\s]+)\b',
    r'\b(?:hay)\s+(?!desayuno|almuerzo|segundo|entrada|snack|postre\b)([\w\s]+)\b',
    r'\b(?:me\s+gustar[ií]a)\s+(?:pedir|ordenar)\s+(?:una|un)\s+(?!desayuno|almuerzo|segundo|entrada|snack|postre\b)([\w\s]+)\b',
    r'\b(?:quiero\s+la\s+opción\s+(?!desayuno|almuerzo|bebida|segundo|entrada|snack|postre\b)([\w\s]+))\b',
    r'\b(?:quiero)\s+(?:una|un)\s+(?!desayuno|almuerzo|segundo|entrada|snack|postre\b)([\w\s]+)\b',
]

# Patrones de expresión regular para extraer la cantidad y el nombre del producto
PRODUCT_ORDER_PATTERN = [
    r'\bquiero\s+(-?\d+)\s+(\w+)',  # Captura solo una palabra después del número
    r'\bquisiera\s+(-?\d+)\s+(\w+)',
    r'\bnecesito\s+(-?\d+)\s+(\w+)'
]

# Patrones de expresión regular para consultar la cantidad de un producto
PRODUCT_QUANTITY_PATTERN = [
    r'\bcu[aá]nt[oa]s?\s+([\w\s]+)\s+(?:tienes|hay|quedan)(?:\s+en\s+(?:stock|inventario|existencia|bodega|almac['
    r'eé]n|dep[oó]sito|disponibles))?\b'
]

# Patrones de expresión regular para consultar el precio por nombre de producto
PRODUCT_PRICE_PATTERN = [
    r'\bcu[aá]nto\s+(?:cuesta|vale|valen|cuestan)\s+(?:el|la|los|las)?\s*(.*)\b',
    r'\bqu[eé]\s+(?:precio|valor|costo)\s+(?:tiene|tienen)\s+(?:el|la|los|las)?\s*(.*)\b',
    r'\bprecio\s+(?:del|de\s+la|de\s+los|de\s+las)?\s*(.*)\b',
    r'\bcosto\s+(?:del|de\s+la|de\s+los|de\s+las)?\s*(.*)\b',
    r'\bvalor\s+(?:del|de\s+la|de\s+los|de\s+las)?\s*(.*)\b'
]


RECOMMEND_PRODUCT_PATTERNS = {
    "drink": [
        r'\bbebida recomendada\b', r'\bqu[eé] bebida recomiendas\b', r'\bqu[eé] bebida me recomiendas\b',
        r'\bqu[eé] bebida es buena\b', r'\bqu[eé] bebida econ[oó]mica me recomiendas\b',
        r'\bqu[eé] bebida es buena y econ[oó]mica\b'
    ],
    "sport_drink": [
        r'\bbebida deportiva recomendada\b', r'\bqu[eé] bebida deportiva recomiendas\b',
        r'\bqu[eé] bebida deportiva me recomiendas\b',
        r'\bqu[eé] bebida deportiva es buena\b', r'\bqu[eé] bebida deportiva econ[oó]mica me recomiendas\b',
        r'\bqu[eé] bebida deportiva es buena y econ[oó]mica\b'
    ],
    "breakfast": [
        r'\bdesayuno recomendado\b', r'\bqu[eé] desayuno recomiendas\b', r'\bqu[eé] desayuno me recomiendas\b',
        r'\bqu[eé] desayuno es bueno\b', r'\bqu[eé] desayuno econ[oó]mico me recomiendas\b',
        r'\bqu[eé] desayuno es bueno y econ[oó]mico\b'
    ],
    "starter": [
        r'\bentrada recomendada\b', r'\bqu[eé] entrada recomiendas\b', r'\bqu[eé] entrada me recomiendas\b',
        r'\bqu[eé] entrada es buena\b', r'\bqu[eé] entrada econ[oó]mica me recomiendas\b',
        r'\bqu[eé] entrada es buena y econ[oó]mica\b'
    ],
    "second_course": [
        r'\bsegundo recomendado\b', r'\bqu[eé] segundo recomiendas\b', r'\bqu[eé] segundo me recomiendas\b',
        r'\bqu[eé] segundo es bueno\b', r'\bqu[eé] segundo econ[oó]mico me recomiendas\b',
        r'\bqu[eé] segundo es bueno y econ[oó]mico\b', r'\bqu[eé] plato fuerte recomiendas\b',
        r'\bqu[eé] plato fuerte me recomiendas\b', r'\bqu[eé] plato fuerte es bueno\b',
        r'[Qq]u[eé] plato fuerte es el m[aá]s comprado\b', r'\bqu[eé] plato fuerte es el mas vendido\b'
    ],
    "snack": [
        r'\bsnack recomendado\b', r'\bqu[eé] snack recomiendas\b', r'\bqu[eé] snack me recomiendas\b',
        r'\bqu[eé] snack es bueno\b', r'\bqu[eé] snack econ[oó]mico me recomiendas\b',
        r'\bqu[eé] snack es bueno y econ[oó]mico\b'
    ],
    "main": [
        r'\balmuerzo recomendado\b', r'\bqu[eé] almuerzo recomiendas\b', r'\bqu[eé] almuerzo me recomiendas\b',
        r'\bcu[aá]l es el plato m[aá]s popular\b', r'\bcu[aá]l es el plato m[aá]s vendido\b',
        r'\bcu[aá]l es el plato m[aá]s pedido\b',
        r'\bqu[eé] almuerzo es bueno\b', r'\bqu[eé] almuerzo econ[oó]mico me recomiendas\b',
        r'\bqu[eé] almuerzo es bueno y econ[oó]mico\b',
        r'\bdeseo un almuerzo\b', r'\bqu[eé] almuerzo me recomiendas\b',
        r'\bdame un almuerzo\b'

    ]
}

# Definir patrones para saludos y conversaciones comunes
GREETING_PATTERNS = [
    r'\bhola\b', r'\bhi\b', r'\bhello\b', r'\bbuenos días\b', r'\bbuenas tardes\b', r'\bbuenas noches\b',
    r'\bcómo estás\b', r'\bqué tal\b', r'\bqué pasa\b'
]


# Función para manejar respuestas comunes
async def handle_common_responses(update: Update, patterns, response_text):
    if match_pattern(patterns, update.message.text.lower()):
        await update.message.reply_text(response_text)
        return True
    return False


EXIT_PATTERNS = [r'\bsalir\b', r'\bsalir del chat\b', r'\bterminar\b']


# Función para verificar si un mensaje coincide con algún patrón
def match_pattern(patterns, message):
    for pattern in patterns:
        if re.search(pattern, message):
            print(f"Pattern matched: {pattern}")
            return True
    return False


# Función para manejar la respuesta basada en el patrón detectado
async def handle_response(update, patterns, handler_function):
    if match_pattern(patterns, update.message.text.lower()):
        logger.info(f"Pattern matched. Handling with {handler_function.__name__}")
        fake_query = type('FakeQuery', (object,), {'edit_message_text': update.message.reply_text})
        await handler_function(fake_query)
        return True
    return False


# Función para normalizar el nombre del producto
def normalize_product_name(product_name):
    # Convertir a minúsculas y quitar acentos
    product_name = product_name.lower()
    product_name = re.sub(r'[áàäâ]', 'a', product_name)
    product_name = re.sub(r'[éèëê]', 'e', product_name)
    product_name = re.sub(r'[íìïî]', 'i', product_name)
    product_name = re.sub(r'[óòöô]', 'o', product_name)
    product_name = re.sub(r'[úùüû]', 'u', product_name)
    product_name = re.sub(r'[^a-z0-9\s]', '', product_name)

    # Devolver el nombre normalizado
    return product_name


# Función para manejar la respuesta basada en el patrón detectado por nombre
async def handle_response_by_name(update, handler_function):
    message = update.message.text.lower()

    # Expresión regular ajustada
    match = re.search(
        r'\b(?:tienes|quiero|dame|quisiera|necesito|me\s+puedes\s+ayudar\s+con|me\s+gustar[ií]a(?:\s+pedir|ordenar)?|deseo|y)\s+(?:una|un|la|el)\s+(?!desayuno|almuerzo|segundo|entrada|snack|postre\b)([\w\s]+)\b',
        message,
        re.IGNORECASE
    )

    # Resultados de la búsqueda
    if match:
        product_name = match.group(1).strip()

        # Normalizar el nombre del producto
        normalized_product_name = normalize_product_name(product_name)
        logger.info(f"Normalized product name: {normalized_product_name}")

        async with SessionLocal() as session:
            async with session.begin():
                # Búsqueda exacta
                query = select(Product.name).where(Product.name.ilike(f'%{normalized_product_name}%'))
                result = await session.execute(query)
                products = result.scalars().all()

                # Si no se encuentran coincidencias exactas, buscar productos similares
                if not products:
                    # Implementar una búsqueda más difusa si no hay coincidencias exactas
                    query_all = select(Product.name)
                    all_products = await session.execute(query_all)
                    all_products_list = all_products.scalars().all()

                    # Encontrar el producto más similar usando fuzzywuzzy
                    best_match = process.extractOne(normalized_product_name, all_products_list)
                    if best_match and best_match[1] > 70:  # Umbral de similitud
                        products = [best_match[0]]

        if products:
            product_name_to_use = products[0]  # Usar solo el primer producto encontrado
            logger.info(f"Producto encontrado en la base de datos: {product_name_to_use}")
            fake_query = type('FakeQuery', (object,), {'edit_message_text': update.message.reply_text})
            await handler_function(fake_query, product_name_to_use)
            return True

    logger.info("No se encontró un producto similar en la base de datos.")
    return False


# Función para manejar la respuesta basada en el patrón detectado por cantidad y nombre
async def handle_response_by_quantity(update: Update, patterns, handler_function):
    message = update.message.text.lower()
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            try:
                # Extraer la cantidad y el nombre del producto
                product_quantity = int(match.group(1).strip())
                product_name = match.group(2).strip().title()

                logger.info(f"Product quantity extracted: {product_quantity}")
                logger.info(f"Product name extracted: {product_name}")

                # Crear un objeto de consulta simulado para la función del controlador
                fake_query = type('FakeQuery', (object,), {'edit_message_text': update.message.reply_text})

                # Llamar a la función del controlador con la consulta simulada
                await handler_function(fake_query, product_name, product_quantity)
                return True
            except ValueError:
                logger.error(f"Cantidad no válida extraída: {match.group(1)}")
                await update.message.reply_text("Por favor, proporciona una cantidad válida.")
                return True
        else:
            logger.info("No se encontraron mensajes de cantidad y nombre, saltando...")
    return False


# Función para manejar la respuesta basada en el patrón detectado por cantidad
async def handle_response_by_quantityofproduct(update: Update, patterns, handler_function):
    message = update.message.text.lower()
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            try:
                product_name = match.group(1).strip().title()
                logger.info(f"Product name extracted: {product_name}")
                fake_query = type('FakeQuery', (object,), {'edit_message_text': update.message.reply_text})
                await handler_function(fake_query, product_name)
                return True
            except IndexError:
                logger.error("No such group in pattern matching")
                continue
        else:
            logger.info("No se encontraron mensajes de cantidad, saltando...")
    return False


# Función para manejar la respuesta basada en el patrón detectado por precio
async def handle_response_by_price(update: Update, patterns, handler_function):
    message = update.message.text.lower()
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            try:
                # Extraemos el nombre del producto y eliminamos artículos como "una", "un", "el", "la"
                product_name = match.group(1).strip()
                # Eliminamos artículos comunes que podrían estar al principio del nombre del producto
                product_name = re.sub(r'^(una|un|el|la|los|las)\s+', '', product_name, flags=re.IGNORECASE)
                product_name = product_name.title()

                logger.info(f"Product name extracted: {product_name}")

                # Creamos un objeto de consulta simulado para la función del controlador
                fake_query = type('FakeQuery', (object,), {'edit_message_text': update.message.reply_text})

                # Llamamos a la función del controlador con la consulta simulada
                await handler_function(fake_query, product_name)
                return True
            except IndexError:
                logger.error("No such group in pattern matching")
                continue
        else:
            logger.info("No se encontraron mensajes de precios, saltando...")
    return False


# Función para manejar la respuesta basada en el patrón detectado por categoría
async def handle_response_by_category(update: Update, patterns, handler_function):
    message = update.message.text.lower()

    # Mapeo de palabras clave a categorías específicas, asegurando que las más específicas se revisen primero
    category_keywords = {
        'almuerzo': 'Almuerzos',
        'sopa': 'Entradas',
        'sopas': 'Entradas',
        'bebida deportiva': 'Bebidas Deportivas',
        'bebidas deportivas': 'Bebidas Deportivas',
        'desayuno': 'Desayunos',
        'bebida': 'Bebidas',  # 'bebida' se verifica después de 'bebida deportiva'
        'segundo': 'Segundos',
        'entrada': 'Entradas',
        'snack': 'Snacks',
    }

    # Verificar si el mensaje contiene palabras clave específicas
    for keyword, category in category_keywords.items():
        if keyword in message:
            logger.info(f"Detected keyword: {keyword}, mapping to category: {category}")
            if category == 'Almuerzos':
                await show_lunch_products(update)  # Mostrar productos de almuerzo
            else:
                fake_query = type('FakeQuery', (object,), {'edit_message_text': update.message.reply_text})
                await handler_function(fake_query, category)
            return True

    # Proceder con la lógica habitual si no se encuentra una palabra clave específica
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            try:
                category_name = match.group(1).strip().title()
                logger.info(f"Category name extracted: {category_name}")
                fake_query = type('FakeQuery', (object,), {'edit_message_text': update.message.reply_text})
                await handler_function(fake_query, category_name)
                return True
            except IndexError:
                logger.error("No such group in pattern matching")
                continue
        else:
            logger.info("No se encontraron nombres de categorías en este mensaje, saltando...")
    return False


# Manejador de mensajes de texto
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja los mensajes de texto entrantes de los usuarios."""
    if context.chat_data.get("session_closed", True):  # La sesión está cerrada por defecto si no se ha establecido
        await update.message.reply_text("La sesión ha terminado. Para empezar de nuevo, escribe /start.")
        return

    user_message = update.message.text.lower()  # Convertir a minúsculas para coincidencia de patrones
    logger.info(f"Received message from user: {user_message}")

    if context.user_data.get('awaiting_rating') or context.user_data.get('awaiting_comment'):
        await handle_comment(update, context)
        return

    # Guardar el mensaje del usuario en el historial con su message_id
    chat_id = update.message.chat_id
    if "conversation_history" not in context.chat_data:
        context.chat_data["conversation_history"] = []

    context.chat_data["conversation_history"].append({
        "role": "user",
        "content": user_message,
        "message_id": update.message.message_id  # Guardar el ID del mensaje del usuario
    })

    # Verificar si el mensaje coincide con saludos o preguntas comunes
    if await handle_common_responses(update, GREETING_PATTERNS, "¡Hola Bienvenido al Costeñito! ¿Cómo puedo ayudarte "
                                                                "hoy?"):
        return

    # Verificar si el mensaje coincide con los patrones de salida
    if match_pattern(EXIT_PATTERNS, user_message):
        await handle_rating(update, context)
        return

    # 1. Verificar si corresponde a una acción específica
    pattern_handlers = [
        (MENU_PATTERNS, show_categories),
        (MOST_ORDERED_PRODUCT_PATTERNS, show_most_ordered_product),
        (MOST_SOLD_DRINK_PATTERNS, show_most_sold_drink),
        (MOST_SOLD_SPORT_DRINK_PATTERNS, show_most_sold_sport_drink),
        (MOST_SOLD_BREAKFAST_PATTERNS, show_most_sold_breakfast),
        (MOST_SOLD_STARTER_PATTERNS, show_most_sold_starter),
        (MOST_SOLD_SECOND_COURSE_PATTERNS, show_most_sold_second),
        (MOST_SOLD_SNACK_PATTERNS, show_most_sold_snack),
        (RECOMMEND_PRODUCT_PATTERNS["drink"], recommend_drink_by_price),
        (RECOMMEND_PRODUCT_PATTERNS["sport_drink"], recommend_sport_drink_by_price),
        (RECOMMEND_PRODUCT_PATTERNS["breakfast"], recommend_breakfast_by_price),
        (RECOMMEND_PRODUCT_PATTERNS["starter"], recommend_starter_by_price),
        (RECOMMEND_PRODUCT_PATTERNS["second_course"], recommend_second_by_price),
        (RECOMMEND_PRODUCT_PATTERNS["snack"], recommend_snack_by_price),
        (RECOMMEND_PRODUCT_PATTERNS["main"], show_most_sold_main)
    ]

    for patterns, handler_function in pattern_handlers:
        if await handle_response(update, patterns, handler_function):
            return

    # 2. Verificar si el mensaje corresponde a una categoría
    if await handle_response_by_category(update, PRODUCT_BY_NAME_CATEGORY_PATTERNS, show_products_by_category_name):
        return

    # 3. Si no es una categoría, verificar si es un producto específico
    if await handle_response_by_name(update, show_product_by_name):
        return

    # 4. Manejar cantidades de productos
    if await handle_response_by_quantity(update, PRODUCT_ORDER_PATTERN, show_product_stock_by_name):
        return

    # 5. Manejar cantidad por producto
    if await handle_response_by_quantityofproduct(update, PRODUCT_QUANTITY_PATTERN, show_product_stock_by_productname):
        return

    # 6. Manejar precios de productos
    if await handle_response_by_price(update, PRODUCT_PRICE_PATTERN, show_product_price_by_name):
        return

    # 7. Si no coincide con nada relacionado a productos o categorías, usar GPT para manejo de conversación general
    if user_message not in context.chat_data["conversation_history"]:
        messages = [system_context] + context.chat_data["conversation_history"]

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=150,
                temperature=0.5,  # Un poco de creatividad para respuestas más naturales
            )

            gpt_response = response.choices[0].message['content'].strip()

            # Revisar si la respuesta incluye recomendaciones de productos
            # Evitar usar recomendaciones de GPT si son de productos específicos
            if any(keyword in gpt_response.lower() for keyword in ["recomiendo", "te sugiero", "prueba"]):
                await update.message.reply_text("Lamentablemente no encuentro información a tu pregunta procura "
                                                "empezar con preguntas claras, puedes decir: quiero pedir tal cosa.")
            else:
                sent_message = await update.message.reply_text(
                    gpt_response)  # Enviar la respuesta y guardar el message_id

                context.chat_data["conversation_history"].append({
                    "role": "assistant",
                    "content": gpt_response,
                    "message_id": sent_message.message_id  # Guardar el ID del mensaje enviado
                })

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            await update.message.reply_text("Lo siento, algo salió mal al procesar tu solicitud.")


# Función para vaciar el chat y cerrar la sesión
async def exit_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from app.telegram_bot import greeting_messages  # Importación retrasada
    chat_id = update.message.chat_id

    # Marcar la sesión como cerrada
    context.chat_data["session_closed"] = True

    # Borrar mensajes previos de saludo
    if chat_id in greeting_messages:
        greeting_message_id = greeting_messages[chat_id]["greeting_message_id"]
        await context.bot.delete_message(chat_id=chat_id, message_id=greeting_message_id)
        del greeting_messages[chat_id]

    # Eliminar todos los mensajes en el historial del chat
    if "conversation_history" in context.chat_data:
        for message in context.chat_data["conversation_history"]:
            message_id = message.get("message_id")
            if message_id is not None:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                except BadRequest as e:
                    logger.warning(f"Could not delete message {message_id}: {e}")
            else:
                logger.warning(f"Message identifier is not specified for message: {message}")
        del context.chat_data["conversation_history"]

    await update.message.reply_text(
        "Gracias por preferirnos. ¡Hasta pronto 👋! Recuerda que para volver a ingresar "
        "puedes presionar el botón de este enlace para ejecutar el comando /start.👈",
    )
