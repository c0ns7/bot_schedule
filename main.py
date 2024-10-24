import mysql.connector
from mysql.connector import Error
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes, \
    CallbackQueryHandler
import datetime

# Конфигурация базы данных
DB_CONFIG = {
    'host': '185.114.247.170',
    'database': 'cd27743_chat',
    'user': 'cd27743_chat',
    'password': 'BQ6gW44n'
}

# Состояния диалога
GROUP_STATE, SUBGROUP_STATE, WEEK_SELECTION, SCHEDULE_STATE = range(4)


def create_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        return None


# Функция для добавления пользователя в базу данных
def add_user_to_db(user_id, group, subgroup):
    connection = create_connection()
    if connection is None:
        return

    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO users (user_id, group_name, subgroup) VALUES (%s, %s, %s)",
            (user_id, group, subgroup)
        )
        connection.commit()
    except Error as e:
        return False
    finally:
        cursor.close()
        connection.close()


def user_exists(user_id):
    connection = create_connection()
    if connection is None:
        return False

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        return result is not None
    except Error as e:
        return False
    finally:
        cursor.close()
        connection.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id

    if user_exists(user_id):
        await update.message.reply_text("👋 Привет, мы помним тебя!")
        await show_schedule_options(update, user_id) # Передача user_id
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 Вас приветствует бот Агинского Педагогического Колледжа им. Базара Ринчино 🏢"
    )
    await update.message.reply_text("📌 Введите номер вашей группы:")
    return GROUP_STATE

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id

    if user_exists(user_id):
        await show_schedule_options(update, user_id)
    else:
        await update.message.reply_text("Ошибка: Вы не зарегистрированы. Пожалуйста, введите номер вашей группы и подгруппы сначала.")
async def handle_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    group = update.message.text.strip()
    valid_groups = {'410', '420', '430', '440', '411', '612', '622', '632', '642', '511', '521', '531', '541', '720',
                    '730', '330', '615', '645', '210', '230'}

    if group not in valid_groups:
        await update.message.reply_text("❌ Ошибка: группа не найдена.\n\n✊ Попробуйте снова.")
        return GROUP_STATE

    context.user_data['group'] = group
    await update.message.reply_text(
        "✅ Группа успешно установлена!\n\n🕒 Остался последний момент, укажите вашу подгруппу:")
    return SUBGROUP_STATE


async def handle_subgroup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    subgroup = update.message.text.strip()

    if subgroup not in {'1', '2'}:
        await update.message.reply_text("❌ Ошибка: подгруппа должна быть 1 или 2.\n\n✊ Попробуйте снова.")
        return SUBGROUP_STATE

    group = context.user_data.get('group')
    add_user_to_db(update.message.from_user.id, group, subgroup)
    await update.message.reply_text("✅ Успешно! Ваши данные сохранены.")

    # Переход к выбору расписания
    await show_schedule_options(update, update.message.from_user.id) # Передача user_id

    return ConversationHandler.END


async def show_schedule_options(update: Update, user_id) -> None:
    keyboard = [
        [InlineKeyboardButton("🗓️ Понедельник", callback_data='monday')],
        [InlineKeyboardButton("🗓️ Вторник", callback_data='tuesday')],
        [InlineKeyboardButton("🗓️ Среда", callback_data='wednesday')],
        [InlineKeyboardButton("🗓️ Четверг", callback_data='thursday')],
        [InlineKeyboardButton("🗓️ Пятница", callback_data='friday')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👀 Выберите день недели, для просмотра расписания:", reply_markup=reply_markup)

def get_current_week():
    """Получает номер текущей недели."""
    # Получаем текущую дату в UTC
    today = datetime.datetime.utcnow()

    # Преобразуем в Московское время (UTC+3)
    moscow_time = today + datetime.timedelta(hours=3)

    # Определяем номер недели
    first_day_of_september = datetime.datetime(moscow_time.year, 9, 1)
    days_since_september = (moscow_time - first_day_of_september).days
    current_week = (days_since_september // 7) + 1  # Делим на 7, чтобы получить номер недели, +1 для первого сентября

    # Корректируем номер недели для отображения первой и второй недели
    if current_week % 2 == 0:
        current_week = 2
    else:
        current_week = 1

    return current_week

async def schedule_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    day_mapping = {
        'monday': 'Понедельник',
        'tuesday': 'Вторник',
        'wednesday': 'Среда',
        'thursday': 'Четверг',
        'friday': 'Пятница'
    }

    selected_day = day_mapping[query.data]

    user_id = query.from_user.id # Получение user_id из запроса
    group_name, subgroup = get_user_data(user_id) # Получение данных пользователя из базы данных

    schedule = get_schedule(selected_day, group_name, subgroup)
    current_week = get_current_week()

    if not schedule:
        await query.message.reply_text(f"❌ Нет занятий на {selected_day}.")
    else:
        response_message = f"🧑‍🏫 *Группа:* {group_name}\n⚡ *Подгруппа:* {subgroup}\n📅 *День недели:* {selected_day}\n🔑 *Неделя:* {current_week}\n\n"

        for subject, time, audience, teacher in schedule:
            response_message += f"⏰ {time} ⏰\n📒 {subject}\n🏢 *Кабинет:* {audience}\n\n"

        await query.message.reply_text(response_message, parse_mode="Markdown")


def get_schedule(day, group_name, subgroup):
    current_week = get_current_week()
    connection = create_connection()
    if connection is None:
        return []

    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT subject, time, audience, teacher FROM schedule WHERE day = %s AND group_name = %s AND (subgroup = %s OR subgroup = '0') AND (week = %s OR week = '0') ORDER BY time",
            (day, group_name, subgroup, current_week)
        )

        schedule_data = cursor.fetchall()
        return schedule_data
    except Error as e:
        return []
    finally:
        cursor.close()
        connection.close()


def get_user_data(user_id):
    connection = create_connection()
    if connection is None:
        return None, None

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT group_name, subgroup FROM users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        if result:
            return result[0], result[1]
        else:
            return None, None
    except Error as e:
        return None, None
    finally:
        cursor.close()
        connection.close()


def main() -> None:
    application = ApplicationBuilder().token("7233482573:AAEq0-KlXy0imbr2o6vLn6KXX7w49khf6-Q").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            GROUP_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group)],
            SUBGROUP_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_subgroup)],
            SCHEDULE_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_selection)],
        },
        fallbacks=[],
    )

    application.add_handler(conv_handler)

    application.add_handler(CallbackQueryHandler(schedule_selection))

    application.run_polling()


if __name__ == '__main__':
    main()
