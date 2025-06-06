import logging
from datetime import datetime
import pytz

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# --- CONFIGURACIÓN DE PRODUCCIÓN ---
BOT_TOKEN = "8058281780:AAFom7Semc7lyBU-KnGEL4pJiGdmZqQnPVg"
GROUP_ID = -1002609847603  # <--- ID DEL GRUPO DE PRODUCCIÓN

# --- MAPA DE TEMAS DE ORIGEN Y SUS ARCHIVOS DE LOG ---
TOPIC_CONFIG = {
    "sin_conexion":      {"topic_id": 2, "log_file": "log_sin_conexion.txt", "pretty_name": "Sin Conexión"},
    "intermitencia":     {"topic_id": 6, "log_file": "log_intermitencia.txt", "pretty_name": "Intermitencia"},
    "capacidad":         {"topic_id": 9, "log_file": "log_capacidad.txt", "pretty_name": "Capacidad"},
    "cambio_de_clave":   {"topic_id": 10, "log_file": "log_cambio_de_clave.txt", "pretty_name": "Cambio de Clave"},
    "cambio_de_equipo":  {"topic_id": 8, "log_file": "log_cambio_de_equipo.txt", "pretty_name": "Cambio de Equipo"},
    "reubicacion":       {"topic_id": 7, "log_file": "log_reubicacion.txt", "pretty_name": "Reubicación"},
    "cambio_de_domicilio": {"topic_id": 5, "log_file": "log_cambio_de_domicilio.txt", "pretty_name": "Cambio de Domicilio"},
    "configuracion":     {"topic_id": 11, "log_file": "log_configuracion.txt", "pretty_name": "Configuración"},
}
SIN_CONEXION_TOPIC_ID = 2

# --- IDs de los TEMAS de DESTINO ---
REPARACIONES_DEST_TOPIC_ID = 55
GENERAL_DEST_TOPIC_ID = 56

# --- CÓDIGO DEL BOT ---
VENEZUELA_TZ = pytz.timezone('America/Caracas')
# La línea de abajo es la que hemos corregido
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

def contar_en_archivo(archivo, mes_buscado, año_buscado):
    """Función auxiliar para contar líneas en un archivo para un mes/año específico."""
    contador = 0
    try:
        with open(archivo, "r") as f:
            for linea in f:
                año, mes, _ = map(int, linea.strip().split("-"))
                if año == año_buscado and mes == mes_buscado:
                    contador += 1
    except FileNotFoundError:
        pass
    return contador

async def total_command(update: Update, context) -> None:
    """Comando /total para mostrar estadísticas."""
    try:
        tipo = context.args[0].lower()
        mes_buscado = int(context.args[1])
        año_buscado = int(context.args[2])

        if tipo == "completo":
            mensaje_respuesta = f"📊 **Resumen Total para {mes_buscado}/{año_buscado}**\n\n"
            total_general = 0
            
            for slug, config in TOPIC_CONFIG.items():
                contador_tema = contar_en_archivo(config['log_file'], mes_buscado, año_buscado)
                mensaje_respuesta += f"- {config['pretty_name']}: **{contador_tema}**\n"
                total_general += contador_tema
            
            mensaje_respuesta += f"\n----------------------------------\n"
            mensaje_respuesta += f"📈 **TOTAL GENERAL: {total_general}**"
            
            await update.message.reply_text(mensaje_respuesta, parse_mode='Markdown')
            return

        if tipo in TOPIC_CONFIG:
            config = TOPIC_CONFIG[tipo]
            contador = contar_en_archivo(config['log_file'], mes_buscado, año_buscado)
            await update.message.reply_text(
                f"📊 Estadísticas para **{config['pretty_name']}** en {mes_buscado}/{año_buscado}:\n"
                f"Total de tareas finalizadas: **{contador}**",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("⚠️ Categoría no reconocida. Revisa el identificador del tema.")

    except (IndexError, ValueError):
        await update.message.reply_text(
            "⚠️ Uso incorrecto. Formatos:\n"
            "`/total <tema> <mes> <año>`\n"
            "`/total completo <mes> <año>`\n\n"
            "**Ejemplos:**\n"
            "`/total sin_conexion 6 2025`\n"
            "`/total completo 6 2025`",
            parse_mode='Markdown'
        )

async def procesar_mensaje(update: Update, context) -> None:
    message = update.message
    
    if message.chat.id != GROUP_ID or not message.reply_to_message or not message.text:
        return

    if message.text.lower().strip().startswith("listo"):
        origen_thread_id = message.message_thread_id
        
        archivo_log_destino = ""
        for slug, config in TOPIC_CONFIG.items():
            if origen_thread_id == config['topic_id']:
                archivo_log_destino = config['log_file']
                break
        
        if archivo_log_destino:
            try:
                with open(archivo_log_destino, "a") as f:
                    fecha_log = datetime.now(VENEZUELA_TZ).strftime("%Y-%m-%d")
                    f.write(f"{fecha_log}\n")
                logger.info(f"Registrada nueva tarea en {archivo_log_destino}")
            except Exception as e:
                logger.error(f"No se pudo escribir en el archivo de log: {e}")
        
        destino_thread_id = GENERAL_DEST_TOPIC_ID
        if origen_thread_id == SIN_CONEXION_TOPIC_ID:
            destino_thread_id = REPARACIONES_DEST_TOPIC_ID
            
        try:
            mensaje_original = message.reply_to_message
            mensaje_respuesta = message
            fecha_actual = datetime.now(VENEZUELA_TZ).strftime("%d/%m/%Y %I:%M %p")
            texto_archivo = (f"✅ **Tarea Completada**\n🗓️ **Fecha:** {fecha_actual}\n\n--- MENSAJE ORIGINAL ---\n{mensaje_original.text}\n\n--- RESPUESTA ---\n{mensaje_respuesta.text}\n\n................................................................")
            await context.bot.send_message(chat_id=GROUP_ID, text=texto_archivo, message_thread_id=destino_thread_id, parse_mode='Markdown')
            await context.bot.delete_message(chat_id=GROUP_ID, message_id=mensaje_respuesta.message_id)
            await context.bot.delete_message(chat_id=GROUP_ID, message_id=mensaje_original.message_id)
        except Exception as e:
            logger.error(f"Ocurrió un error al procesar mensaje: {e}")

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("total", total_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_mensaje))
    logger.info("¡Bot v4.1 (Producción - Corregido) está iniciando!")
    application.run_polling()

if __name__ == "__main__":
    main()