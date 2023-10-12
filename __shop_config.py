HOST = "0.0.0.0"
PORT = 8080
DEBUG = True

SECRET_KEY = "secret_key"  # Защитный ключ от взлома

MAX_CONTENT_LENGTH_IN_MB = 8  # Максимум МБ, которые могут быть отправлены пользователем на сервер

LOGIN_MESSAGE = "Войдите или зарегистрируйтесь"

with open("admin_data.txt", encoding="utf-8") as f:
    ADMIN_PASSWORD = f.readline().replace("\n", "")
    ADMIN_NAME = f.readline().replace("\n", "")
    ADMIN_PHONE = f.readline().replace("\n", "")
    ADMIN_EMAIL = f.readline().replace("\n", "")

SHOP_NAME = "LibReg"
COMPANY_NAME = "[Название компании]"
COMPANY_ABOUT = "[Описание магазина]"

THEMES = [
    ("light", "Светлая"),
    ("dark", "Тёмная")
]
DEFAULT_THEME = "dark"

IMAGES = ["png", "jpg", "jpeg"]
VIDEOS = []
AUDIOS = []
FILE_TYPES = IMAGES + VIDEOS + AUDIOS

ORDER_STATUS = {
    0: "на рассмотрении",
    1: "курьер забирает заказ из склада",
    2: "курьер везёт заказ к указанному адресу",
    3: "доставлен",
    4: "возвращён в библиотеку"
}

BOOK_STATUS = {
    0: "в библиотеке",
    1: "приобретена"
}

TAGS_COUNT_IN_RECS = 20
PRODUCTS_IN_INDEX = 10


if __name__ == "__main__":
    print(ADMIN_PASSWORD)
    print(ADMIN_NAME)
    print(ADMIN_PHONE)
    print(ADMIN_EMAIL)
