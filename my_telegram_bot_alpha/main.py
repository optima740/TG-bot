from my_telegram_bot_alpha.config import TG_TOKEN, GEO_TOKEN
from telegram import Bot, Update, User, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext, CallbackQueryHandler, Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
import logging
import requests
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

BTN_SEARCH = 'Новый поиск'
BTN_BACK = 'Назад'
BTN_HISTORY = 'История'
LIST_USER_REQUEST = []
DICT_USER_ID = {}
DICT_ALL= {}

def get_address_from_text(address):
    PARAMS = {
        "apikey": GEO_TOKEN,
        "format": "json",
        "lang": "ru_RU",
        "kind": "house",
        "geocode": address
    }
    try:
        r = requests.get(url="https://geocode-maps.yandex.ru/1.x/", params=PARAMS)
        json_data = r.json()
        address_str = json_data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["metaDataProperty"][
            "GeocoderMetaData"]["AddressDetails"]["Country"]["AddressLine"]
        return address_str
    except Exception as e:
        # сообщение об ошибке.
        return "Не могу определить полный адресс по этому запросу.\n\n"

def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    update.message.reply_text('Привет {}, я Aplha Bot! Выбери действие на клавиатуре ниже:'.format(user.first_name), reply_markup=main_menu())
    return "OTHER"

def main_menu():
    menu_main = [[KeyboardButton(BTN_SEARCH),
                  KeyboardButton(BTN_HISTORY)],
                  [KeyboardButton(BTN_BACK)],
                 ]
    reply_markup = ReplyKeyboardMarkup(keyboard=menu_main, resize_keyboard=True)
    return reply_markup

def text(update: Update, context: CallbackContext):
    #получаем текст от пользователя и данные пользователя
    address = update.message.text
    user_data = context.user_data
    user = update.message.from_user
    user_chat_id = update.message.chat_id
    # проверяем наличие нажатых кнопок меню
    if address == BTN_BACK:
        return start(update=update, context=context)
    elif address == BTN_HISTORY:
        return history(update=update, context=context)
    elif address == BTN_SEARCH:
        update.message.reply_text('{}, Введите адрес, а не команду'.format(user.first_name))
    #отправляем текст в функцио получения адреса
    address_str = get_address_from_text(address)
    # запоминаем запрос
    if user_chat_id in DICT_USER_ID:
        LIST_USER_REQUEST = DICT_USER_ID[user_chat_id]
        LIST_USER_REQUEST.append(address_str)
        DICT_USER_ID[user_chat_id] = LIST_USER_REQUEST
    else:
        LIST_USER_REQUEST = []
        LIST_USER_REQUEST.append(address_str)
        DICT_USER_ID[user_chat_id] = LIST_USER_REQUEST
    #вовщращаем результат пользователю в боте
    update.message.reply_text(address_str)
    return search(update=update, context=context)

def search(update: Update, context: CallbackContext):
    text = update.message.text
    #if text == BTN_BACK:
        #return start(update=update, context=context)
    update.message.reply_text('Введи свой запрос или нажми "Назад", для возврата')
    return "TEXT"

def other_event(update: Update, context: CallbackContext):
    user_text = update.message.text
    if user_text == BTN_SEARCH:
        return search(update=update, context=context)
    elif user_text == BTN_BACK:
        return start(update=update, context=context)
    elif user_text == BTN_HISTORY:
        return history(update=update, context=context)
    else:
        user = update.message.from_user
        update.message.reply_text('{}, я тебя не понял, повтори последнее действие правильно'.format(user.first_name))

def cancel(update: Update, context: CallbackContext):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text('Пока! :)', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def history(update: Update, context: CallbackContext):
    user_chat_id = update.message.chat_id
    if len(DICT_USER_ID) != 0:
        if user_chat_id in DICT_USER_ID:
            list_request = DICT_USER_ID.get(user_chat_id)
            if len(list_request) != 0:
                update.message.reply_text('Пользователь с id {} запрашивал:'.format(user_chat_id))
                for item in list_request:
                    update.message.reply_text(item)
                return
    update.message.reply_text('У текущего пользователя пока нет запросов')

def main():
    updater = Updater(token=TG_TOKEN, )
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            "SEARCH": [MessageHandler(Filters.text, search)],
            "TEXT": [MessageHandler(Filters.text, text)],
            "OTHER": [MessageHandler(Filters.text, other_event)],
            "BACK": [MessageHandler(Filters.text, start)],
        },
        fallbacks=[]
    )
    updater.dispatcher.add_handler(CommandHandler("cancel", cancel))
    updater.dispatcher.add_handler(conv_handler)

    updater.start_polling()
    logger.info('Started polling')
    logger.info('Bot started. Press Ctrl-C to stop.')
    updater.idle()

if __name__ == "__main__":
    main()

