from config import TG_TOKEN
from telegram import Bot, Update, User, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from telegram.ext import CallbackContext, CallbackQueryHandler, Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
import logging
import requests
from translate import Translator
import transliterate
from lxml import html, etree
import urllib
import re
import emoji
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)
EMOJI = {'ok': emoji.emojize(":white_heavy_check_mark:", use_aliases=True),
        'danger': emoji.emojize(":no_entry:", use_aliases=True),
        'warning': emoji.emojize(":white_exclamation_mark::raised_hand:",  use_aliases=True),
        'stop_ganger': emoji.emojize(':double_exclamation_mark::no_entry:', use_aliases=True),
        'message': emoji.emojize(':speech_balloon:', use_aliases=True),
        'pill': emoji.emojize(':pill:', use_aliases=True)
         }

def start(update: Update, context: CallbackContext):
    # стартовая функция для бота (приветствие и ввод запроса)
    user = update.message.from_user
    update.message.reply_text('Привет {}! Я попробую помочь Вам оценить риск использования препарата. '
                              'Введите название Вашего препарата {} '
                              'на русском языке:'.format(user.first_name, EMOJI['pill']), parse_mode=ParseMode.MARKDOWN)
    return "ACTIV_SUBST"

def request_lacta(update: Update, context: CallbackContext, text):
    # Функция производит поиск действующего вещества на ресурсе e-lactancia.org и выдает одну из 4 рекомендаций по
    # уровню риска приема препарата.
    # text - входной параметр для поиска (заранее найденное действующее вещество).
    # Возвращает статус выполнения. True - активное вещество найдено, рекомендации даны. False - вещество не найдено.
    STATUS_OK = True
    STATUS_BAD = False
    RESPONCE_STATUS = {'Green': 'Совместим с грудным вскармливанием, поскольку имеется достаточная информация, '
                                'опубликованная в научной литературе об отсутствии доказанной токсичности при частом '
                                'использовании. У новорожденных или маленьких детей побочных эффектов не наблюдалось. '
                                'Но для полной уверенности, рекомендуется консультация с врачем.',
                       'Yellow': 'Условно безопасный продукт. Его наличие возможно в грудном молоке. '
                                 'Совместим с грудным вскармливанием, но с выполнением условий: '
                                 'Вы должны учитывать дозы, графики, время выведения, возраст ребенка и т.д. '
                                 'Физико-химические и фармакокинетические характеристики препарата дают малую '
                                 'вероятность появления побочных эффектов. Следуйте рекомендациям врача.',
                       'Orange': 'Не безопасный продукт! При острой необходимости применения нужно оценить риски. '
                                 'Трудно совместим с грудным вскармливанием: Вы должны оценить соотношение риска и '
                                 'пользы, найти более безопасную альтернативу или прекратить грудное вскармливание на '
                                 'необходимое время, пока препарат не будет полностью выведен из организма матери, '
                                 'что зависит от периода полувыведения препарата. Следуйте рекомендациям врача.',
                       'Red': 'Этот продукт, противопоказан во время грудного вскармливания! Необходимо прекратить '
                              'кормить грудью или выбрать более безопасный аналог. Период полувыведения '
                              'препарата может быть слишком длинным, для временной приостановки кормления.'
                              'Следуйте рекомендациям врача.'
                       }
    text = str(text)
    text = text.lower()
    url = 'http://e-lactancia.org/breastfeeding/' + text + '/product/' # формируем url для запроса html страницы
    #update.message.reply_text(url)
    parsed_body = parse_html(update, context, url) # возвращает тело html страницы для парсинга
    if parsed_body is not None:
        # поиск соответствия текста в теле html страницы:
        try:
            text = parsed_body.xpath('//h2[@class = "risk-header"]/text()')[0]
            if 'Riesgo muy bajo' in text:
                update.message.reply_text('*Безопасно.* {}'.format(EMOJI['ok']), parse_mode=ParseMode.MARKDOWN)
                update.message.reply_text(RESPONCE_STATUS['Green'])
                return STATUS_OK
            elif 'Riesgo bajo' in text:
                update.message.reply_text('*Низкий риск.* {}'.format(EMOJI['warning']), parse_mode=ParseMode.MARKDOWN)
                update.message.reply_text(RESPONCE_STATUS['Yellow'])
                return STATUS_OK
            elif 'Riesgo alto' in text:
                update.message.reply_text('*Высокий риск!* {}'.format(EMOJI['danger']), parse_mode=ParseMode.MARKDOWN)
                update.message.reply_text(RESPONCE_STATUS['Orange'])
                return STATUS_OK
            elif 'Riesgo muy alto' in text:
                update.message.reply_text('*Очень высокий риск!* {}'.format(EMOJI['stop_ganger']), parse_mode=ParseMode.MARKDOWN)
                update.message.reply_text(RESPONCE_STATUS['Red'])
                return STATUS_OK
        except Exception as e:
            return STATUS_BAD
    else:
        return STATUS_BAD

def swap_char(word):
    # вспомогательная функция для стыковки различного написания названий.
    text = str(word)
    text = text.replace("'", '')
    text = text.replace('thi', 'ti')
    text = text.replace('Th', 'T')
    if (text == 'Acetylsalicilic') or (text == 'Acetylsalicylic'):
        text = 'aspirin'
    return text

def request_activ_subst(update: Update, context: CallbackContext):
    # Функция поиска действующего вещества по названию препарата на ресурсе http://www.medcatalog.net/rus/
    # Ищет действующее вещество препарата, вызывает функцию request_lacta() для оценки риска,
    # в которую передает найденное активное вещество.
    active_subst = update.message.text
    encode_request = urllib.parse.quote_plus(active_subst.encode('cp1251'))
    url = 'https://www.rlsnet.ru/search_result.htm?word=' + encode_request + '&path=%2F&enter_clicked=1&letters='
    parsed_body = parse_html(update, context, url) # возвращает тело html страницы для парсинга.
    if parsed_body is not None:
        try:
            search_href = parsed_body.xpath('//div[@class = "search_serp_one"]/a/text()') # ищем текст из div в теле html.
            for item in search_href:
                if ('(' in item) and (')' in item):
                    result = re.findall('([A-Za-z]+)', item)  # ищем любые латинские буквы.
                    if len(result) != 0:
                        break
            #update.message.reply_text('все что нашел: {}'.format(result))
            count_activ_subst = 1
            index = 0
            for item in result:
                if item[0].isupper(): # если название с заглавной буквы, расцениваем это как название активного вещества
                    update.message.reply_text('*Действующее вещество № {}:*'.format(count_activ_subst), parse_mode=ParseMode.MARKDOWN)
                    update.message.reply_text(item) # печатаем найденное активное вещество.
                    text = swap_char(item) # оптимизируем написание для поиска.
                    response = request_lacta(update, context, text) # проверяем риск по найденному активному веществу,
                    # ожидаем результат выполения функции (True или False) request_lacta()
                    if not response and len(result) > 1: # если False и в result больше одного варианта, то пробуем
                        # к запросу прикрепить следубщее слово в списке result.
                        index += 1
                        if index <= (len(result) - 1):
                            text_1 = text + '-' + result[index]
                            update.message.reply_text(text_1)
                            response = request_lacta(update, context, text_1) # пробуем еще раз.
                            if not response:  # проверяем результат, если False, то сообщаем о неудаче.
                                update.message.reply_text(
                                    'К сожалению, по действующему веществу "{}" я не смог найти информацию. '
                                    'В этом случае рекомендуется уточнить все варианты написания '
                                    'действующего вещества, и произвести поиск в ручную.'.format(text_1))
                                update.message.reply_text(
                                    'На ресурсе e-lactancia вы сможете узнать совместимость действующего '
                                    'вещества лекарственных средств с грудным вскармливанием. '
                                    'Для этого в строку поиска введите латинское название препарата. '
                                    'Если указанное действующее вещество есть в справочнике ресурса,  '
                                    'в ответ вы получите описание риска его приема при грудном вскармливании.')
                                update.message.reply_text('http://e-lactancia.org/')
                    elif (not response) and (len(result)) == 1: # если False и в result только один вариант, и
                        # пробовать прикрепить еще одно слово неполучится. Сообщаем о неудаче.
                        update.message.reply_text(
                            'К сожалению, по действующему веществу "{}" я не смог найти информацию. '
                            'В этом случае рекомендуется уточнить все варианты написания '
                            'действующего вещества, и произвести поиск в ручную.'.format(text))
                        update.message.reply_text(
                            'На ресурсе e-lactancia вы сможете узнать совместимость действующего '
                            'вещества лекарственных средств с грудным вскармливанием. '
                            'Для этого в строку поиска введите латинское название препарата. '
                            'Если указанное действующее вещество есть в справочнике ресурса,  '
                            'в ответ вы получите описание риска его приема при грудном вскармливании.')
                        update.message.reply_text('http://e-lactancia.org/')
                    count_activ_subst += 1
        except Exception as e:
            update.message.reply_text("Не нашел указанный препарат. Проверьте правильность написания, "
                                      "и попробуйте еще раз. {}".format(EMOJI['message']))

def parse_html(update: Update, context: CallbackContext, url):
    # Вспомогательная функция для формирование запроса на получение html страницы для дальнейшего парсинга.
    # url - входной параметр с адресом страницы для запроса.
    # Возвращает тело полученной html страницы.
    ok_status_code = [200, 201, 202, 203, 204, 205, 206, 207] # возможные "хорошие" ответы сервера.
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/39.0.2171.95 Safari/537.36'} # маскировка работы под браузер.
    sessions = requests.Session()
    response = sessions.get(url, headers=headers) # запрос к серверу по url
    if response.status_code in ok_status_code: # если ответ сервера содержит "хороший" код,
        # то формируем тело html для дальнейшего парсинга
        try:
            parsed_body = html.fromstring(response.text)
            if len(parsed_body) != 0:
                return parsed_body # возвращаем тело html для парсинга
        except Exception as e:
            # сообщение об ошибке.
            update.message.reply_text("Не нашел указанный препарат. Проверьте правильность написания, "
                                      "и попробуйте еще раз. {}".format(EMOJI['message']))

def cancel(update: Update, context: CallbackContext):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text('Пока! :)', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    updater = Updater(token=TG_TOKEN, )
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            "ACTIV_SUBST": [MessageHandler(Filters.text, request_activ_subst)],
            "LACTA": [MessageHandler(Filters.text, request_lacta)],
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

