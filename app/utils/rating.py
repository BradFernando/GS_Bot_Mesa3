from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from sqlalchemy.orm import sessionmaker
import logging

from app.config import settings
from app.models import Recommendation

# Configurar el logger
logger = logging.getLogger(__name__)

# Configurar la base de datos
engine = create_async_engine(settings.database_url, echo=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)


async def handle_rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        await update.callback_query.answer()
        chat_id = update.callback_query.message.chat_id
        reply_function = update.callback_query.message.reply_text
    else:
        chat_id = update.message.chat_id
        reply_function = update.message.reply_text

    await reply_function(
        "Califica nuestro sistema y tu experiencia:\n1. ⭐️\n2. ⭐️⭐️\n3. ⭐️⭐️⭐️\n4. ⭐️⭐️⭐️⭐️\n5. ⭐️⭐️⭐️⭐️⭐️"
    )
    context.user_data['awaiting_rating'] = True


async def handle_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    chat_id = update.message.chat_id

    if context.user_data.get('awaiting_rating'):
        try:
            rating = int(user_message)
            if rating < 1 or rating > 5:
                raise ValueError("Calificación fuera de rango.")
        except ValueError:
            await update.message.reply_text("Lo siento, este no es un valor válido para calificarnos.")
            return

        context.user_data['rating'] = rating
        context.user_data['awaiting_comment'] = True
        context.user_data['awaiting_rating'] = False

        await update.message.reply_text(
            "Gracias, ahora por favor procede a enviarnos un comentario para decirnos en qué mejorar:"
        )
    elif context.user_data.get('awaiting_comment'):
        comment = user_message
        username = update.message.from_user.username or "Anonimo"  # Usar "Anonimo" si no hay username

        async with SessionLocal() as session:
            try:
                new_recommendation = Recommendation(
                    userName=username,
                    rating=context.user_data['rating'],
                    comment=comment
                )
                session.add(new_recommendation)
                await session.commit()
                logger.info(f"Recomendación guardada exitosamente para el usuario {username}")
            except Exception as e:
                await session.rollback()
                logger.error(f"Error al guardar la recomendación en la base de datos: {e}")
                await update.message.reply_text(
                    "Lo siento, hubo un error al guardar tu calificación. Inténtalo más tarde.")

        context.user_data['awaiting_comment'] = False

        await update.message.reply_text(
            "Gracias, tus comentarios nos ayudan a mejorar nuestra atención a los clientes."
        )

        # Ahora cerramos la sesión al final del flujo
        await exit_chat(update, context)


async def exit_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from app.telegram_bot import greeting_messages
    chat_id = update.message.chat_id

    context.chat_data["session_closed"] = True

    # Borrar los mensajes de saludo y el teclado
    if chat_id in greeting_messages:
        greeting_message_id = greeting_messages[chat_id]["greeting_message_id"]
        await context.bot.delete_message(chat_id=chat_id, message_id=greeting_message_id)
        del greeting_messages[chat_id]

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
