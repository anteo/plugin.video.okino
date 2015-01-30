# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from util.enum import Enum
from okino.common import LocalizedEnum
from copy import copy

try:
    from collections import OrderedDict
except ImportError:
    from util.ordereddict import OrderedDict


class Attribute(LocalizedEnum):
    def get_lang_base(self):
        raise NotImplementedError()

    @property
    def lang_id(self):
        return self.get_lang_base() + self.id

    @property
    def id(self):
        return self.value[0]

    @property
    def filter_val(self):
        return self.value[1]

    def __repr__(self):
        return "<%s.%s>" % (self.__class__.__name__, self._name_)

    @classmethod
    def find(cls, what):
        for i in cls.__iter__():
            if what in i.value or i.name == what:
                return i
        return None

    @classmethod
    def all(cls):
        return [g for g in cls if g.id > 0]


class Order(Attribute):
    RATING = (1, 'film.rtg_value')
    USER_RATING = (2, 'okino_rating.rtg_value')
    YEAR = (3, 'SUBSTR(film.year,1,4)')
    NAME = (4, 'rus_name')
    DATE = (5, 'wld_prm_time')

    def get_lang_base(self):
        return 30280


class OrderDirection(Attribute):
    ASC = (1, 'asc')
    DESC = (2, 'desc')

    def get_lang_base(self):
        return 30290


class Section(Attribute):
    MOVIES = (10, 'movie', 'Movies')
    SERIES = (20, 'series', 'Series')
    CARTOONS = (30, 'animation', 'Cartoons')
    ANIMATED_SERIES = (40, 'animseries', 'Animated Series')

    # noinspection PyUnusedLocal
    def __init__(self, *args):
        self.lang_base = 31000

    def get_lang_base(self):
        return self.lang_base

    @property
    def singular(self):
        c = copy(self)
        c.lang_base = 31040
        return c

    @property
    def folder_name(self):
        return self.value[2]

    def is_series(self):
        return self in [Section.SERIES, Section.ANIMATED_SERIES]


class Format(Attribute):
    SD = (10, "SD", "Только SD")
    HD = (20, "HD", "Только HD")
    HD720 = (30, "HD 720p", None)
    HD1080 = (40, "HD 1080p", None)

    @property
    def filter_val(self):
        return self.value[2]

    def get_lang_base(self):
        return 30900

    @property
    def width(self):
        return FORMAT_DIMENSIONS[self][0]

    @property
    def height(self):
        return FORMAT_DIMENSIONS[self][1]


FORMAT_DIMENSIONS = {
    Format.SD: (720, 480),
    Format.HD: (1280, 720),
    Format.HD720: (1280, 720),
    Format.HD1080: (1920, 1080),
}


class Genre(Attribute):
    OTHER = (-1, "Другой")
    ANIME = (185, "Аниме")
    BIOGRAPHY = (98, "Биографический")
    ACTION = (70, "Боевик")
    WESTERN = (40, "Вестерн")
    MILITARY = (135, "Военный")
    DETECTIVE = (32, "Детектив")
    CHILDREN = (121, "Детский")
    ADULT = (72, "Для Взрослых")
    DOCUMENTARY = (123, "Документальный")
    DRAMA = (163, "Драма")
    GAME = (124, "Игровое Шоу")
    HISTORICAL = (109, "Исторический")
    CATASTROPHE = (177, "Катастрофа")
    STORY = (133, "Киноповесть")
    COMEDY = (151, "Комедия")
    SHORT = (126, "Короткометражный")
    CRIMINAL = (64, "Криминал")
    ROMANCE = (137, "Мелодрама")
    MYSTIC = (14, "Мистика")
    MUSIC = (119, "Музыкальный")
    CARTOON = (158, "Мультфильм")
    SOAP_OPERA = (171, "Мыльная опера")
    MUSICAL = (134, "Мюзикл")
    NOIR = (95, "Нуар")
    DOMESTIC = (117, "Отечественный")
    ADVENTURES = (127, "Приключения")
    PSYCHOLOGICAL = (178, "Психологический")
    REALITY_SHOW = (61, "Реалити-Шоу")
    FAMILY = (57, "Семейный")
    PLAY = (120, "Спектакль")
    SPORT = (33, "Спортивный")
    TALK_SHOW = (159, "Ток-Шоу")
    TOKUSATSU = (164, "Токусацу")
    THRILLER = (149, "Триллер")
    HORROR = (13, "Ужасы")
    FICTION = (157, "Фантастика")
    FANTASY = (153, "Фэнтези")
    CHRONICLE = (62, "Хроника")
    EROTIC = (93, "Эротика")

    def get_lang_base(self):
        return 30700

    @property
    def filter_val(self):
        return str(self.value[0])


class Country(Attribute):
    OTHER = (-1, "Другая")
    AUSTRALIA = (19, "Австралия")
    GREAT_BRITAIN = (33, "Великобритания")
    GERMANY = (7, "Германия")
    HONGKONG = (3, "Гонконг")
    WESTERN_GERMANY = (44, "Западная Германия")
    INDIA = (23, "Индия")
    SPAIN = (22, "Испания")
    ITALY = (20, "Италия")
    CANADA = (183, "Канада")
    CHINA = (9, "Китай")
    MEXICO = (61, "Мексика")
    NETHERLANDS = (36, "Нидерланды")
    POLAND = (26, "Польша")
    RUSSIA = (46, "Россия")
    USSR = (18, "СССР")
    USA = (6, "США")
    FRANCE = (8, "Франция")
    SWEDEN = (45, "Швеция")
    SOUTH_KOREA = (10, "Южная Корея")
    JAPAN = (13, "Япония")
    GEORGIA = (101, "Грузия")
    ESTONIA = (98, "Эстония")
    DENMARK = (24, "Дания")
    BRAZIL = (30, "Бразилия")
    NORWAY = (68, "Норвегия")
    IRELAND = (81, "Ирландия")
    INDONESIA = (57, "Индонезия")
    THAILAND = (14, "Тайланд")
    YUGOSLAVIA = (108, "Югославия")
    ISRAEL = (31, "Израиль")
    FINLAND = (49, "Финляндия")
    UKRAINE = (106, "Украина")
    BULGARIA = (86, "Болгария")
    SWITZERLAND = (21, "Швейцария")
    NEW_ZEALAND = (52, "Новая Зеландия")
    AZERBAIJAN = (165, "Азербайджан")
    CZECH_REPUBLIC = (72, "Чехия")
    UAE = (157, "Объединенные Арабские Эмираты")
    SOUTH_AFRICA = (32, "Южная Африка")
    AUSTRIA = (16, "Австрия")
    BELARUS = (127, "Беларусь")
    EGYPT = (131, "Египет")
    LUXEMBOURG = (39, "Люксембург")
    BELGIUM = (67, "Бельгия")
    TURKEY = (94, "Турция")
    GREECE = (111, "Греция")
    ARUBA = (182, "Аруба")
    SINGAPORE = (11, "Сингапур")
    TAIWAN = (12, "Тайвань")
    MALTA = (123, "Мальта")
    ARGENTINA = (37, "Аргентина")
    ROMANIA = (83, "Румыния")
    PERU = (119, "Перу")
    LATVIA = (138, "Латвия")
    BAHAMAS = (187, "Багамы")
    KAZAKHSTAN = (105, "Казахстан")
    VENEZUELA = (147, "Венесуэла")
    ICELAND = (90, "Исландия")
    MACEDONIA = (137, "Республика Македония")
    SLOVENIA = (73, "Словения")
    SERBIA = (87, "Сербия")
    CROATIA = (89, "Хорватия")
    MONTENEGRO = (205, "Черногория")
    FIJI = (218, "Фиджи")
    EASTERN_GERMANY = (150, "Восточная Германия")
    PHILIPPINES = (17, "Филиппины")
    CHILE = (118, "Чили")
    MONGOLIA = (135, "Монголия")
    CZECHOSLOVAKIA = (112, "Чехословакия")
    HUNGARY = (65, "Венгрия")

    def get_lang_base(self):
        return 30500

    @property
    def filter_val(self):
        return str(self.value[0])


class Language(Attribute):
    OTHER = (-1, "Другой")
    RUSSIAN = (10, "Русский")
    ENGLISH = (11, "Английский")
    JAPANESE = (12, "Японский")
    CHINESE = (13, "Китайский")
    GERMAN = (14, "Немецкий")
    FRENCH = (15, "Французский")
    ITALIAN = (16, "Итальянский")
    SPANISH = (17, "Испанский")
    KOREAN = (18, "Корейский")
    GOBLIN = (19, "Перевод Гоблина")
    HUNGARIAN = (20, "Венгерский")
    SWEDISH = (21, "Шведский")
    EUROPEAN = (22, "Европейские языки")
    WITHOUT_SPEECH = (23, "Без речи")
    GEORGIAN = (24, "Грузинский")
    ESTONIAN = (25, "Эстонский")
    DANISH = (26, "Датский")
    NORWEGIAN = (27, "Норвежский")
    INDONESIAN = (28, "Индонезийский")
    THAI = (29, "Тайский")
    HINDI = (30, "Хинди")
    SERBIAN = (31, "Сербский")
    POLISH = (32, "Польский")
    HEBREW = (33, "Иврит")
    UKRAINIAN = (34, "Украинский")
    DUTCH = (35, "Нидерландский")
    TURKISH = (36, "Турецкий")
    MALAYALAM = (37, "Малаялам")
    LITHUANIAN = (38, "Литовский")
    BENGALI = (39, "Бенгали")
    PORTUGUESE = (40, "Португальский")
    BENGAL = (41, "Бенгальский")
    LATVIAN = (42, "Латышский")
    BULGARIAN = (43, "Болгарский")
    TELUGU = (44, "Телугу")
    ICELANDIC = (45, "Исландский")
    MACEDONIAN = (46, "Македонский")
    FARSI = (47, "Фарси")
    MONGOLIAN = (48, "Монгольский")
    CZECH = (49, "Чешский")
    TAIWANESE = (50, "Тайваньский")

    def get_lang_base(self):
        return 30400


class AudioQuality(Attribute):
    UNKNOWN = (-1, "неизвестно")
    WITHOUT_TRANSLATION = (12, "нет перевода")
    CAM_RIP = (11, "дубляж с экранки")
    VOLODARSKY = (10, "озвучка секты им. Л.В. Володарского")
    ONE_VOICE = (20, "любительский одноголосый перевод")
    MANY_VOICES = (30, "любительский многоголосый перевод")
    LINE = (31, "звук line")
    PROFESSIONAL = (40, "профессиональный перевод")
    ORIGINAL = (50, "оригинальная дорожка/полный дубляж")

    def get_lang_base(self):
        return 30300

    def __nonzero__(self):
        return self.value[0] > 0


class VideoQuality(Attribute):
    UNKNOWN = (-1, "неизвестно")
    BAD_CAM_RIP = (10, "(1) плохая экранка")
    CAM_RIP = (20, "(2) экранка")
    VHS_RIP = (21, "(2) VHS-рип")
    TV_RIP = (30, "(3) TV-рип")
    DVD_SCR = (31, "(3) DVDscr")
    HDTV = (32, "(3) HDTV")
    HDTV_HD = (33, "(3) HDTV HD")
    DVD_RIP = (40, "(4) DVD-рип")
    WEB_DL = (41, "(4) Web-DL")
    HD_RIP = (50, "(5) HD-рип")
    WEB_DL_HD = (51, "(5) Web-DL HD")

    def get_lang_base(self):
        return 30100

    def __nonzero__(self):
        return self.value[0] > 0


class MPAA(Attribute):
    OTHER = (-1, 'other', 'Другой')
    G = (10, '6+')
    PG = (20, '12+')
    PG_13 = (30, '16+')
    R = (40, '18+')
    ANY = (50, 'any', 'Для всех')

    def get_lang_base(self):
        return 30200


class Flag(Attribute):
    QUALITY_UPDATED = (1, "files_up")
    RECENTLY_ADDED = (2, "files_new")
    NEW_SERIES = (3, "files_plus")

    def get_lang_base(self):
        return 30200
