from flask import Flask, request, render_template, redirect, abort, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from data import db_session
from data.users import User
from data.products import Product
from data.manufacturers import Manufacturer
from data.orders import Order
from data.books import Book

from data.log import *

from data.data_processing import *

import os
import shutil
import datetime

from __shop_config import *
from data.__errors import *

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["UPLOAD_FOLDER"] = "static/media/from_users"
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH_IN_MB * 1024 * 1024

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_message = LOGIN_MESSAGE

accept_images = make_accept_for_html(IMAGES)


@login_manager.user_loader
def load_user(user_id: int):
    db_sess = db_session.create_session()
    return db_sess.query(User).filter(User.id == user_id).first()


def load_theme():
    db_sess = db_session.create_session()
    if current_user.is_authenticated:
        user = db_sess.query(User).filter(User.id == current_user.id).first()
        return user.theme
    else:
        return session.get("theme") if session.get("theme") in [x[0] for x in THEMES] else DEFAULT_THEME


def change_theme():
    if "change-theme" in request.form and request.method == "POST":
        if request.form.get("change-theme") in [x[0] for x in THEMES]:
            if current_user.is_authenticated:
                db_sess = db_session.create_session()
                user = db_sess.query(User).filter(current_user.id == User.id).first()
                user.theme = request.form.get("change-theme")
                db_sess.commit()
                write_log(f"Пользователь {current_user.name} (ID - {current_user.id}) "
                          f"поменял тему на {request.form.get('change-theme')}")
            else:
                session["theme"] = request.form.get("change-theme")
                write_log(f"Анонимный пользователь (IP - {request.remote_addr}) поменял тему на "
                          f"{request.form.get('change-theme')}")
        else:
            flash(f"Ошибка: темы {request.form.get('change-theme')} не существует", "danger")
            write_log(f"Ошибка: темы {request.form.get('change-theme')} не существует")


def cart_check():
    if not session.get("cart"):
        session["cart"] = {}
        session["cart_changed"] = False
    else:
        db_sess = db_session.create_session()
        products_toggle_list = {}
        for product in db_sess.query(Product):
            products_toggle_list[product.id] = product.toggle
        remove_flag = False
        for product_id in session["cart"].copy():
            if int(product_id) not in products_toggle_list:
                session['cart'].pop(product_id)
                write_log(f"Книги с ID {product_id} не существует")
                remove_flag = True
            elif not products_toggle_list[int(product_id)]:
                session['cart'].pop(product_id)
                write_log(f"Книга с ID {product_id} больше не продаётся")
                remove_flag = True
        if remove_flag:
            flash("Некоторые книги были удалены из корзины по причине их несуществования или снятия с продажи",
                  "danger")
            session["cart_changed"] = True
        else:
            session["cart_changed"] = False


def orders_mod_check():
    if current_user.is_authenticated:
        if current_user.is_admin or current_user.is_moderator:
            db_sess = db_session.create_session()
            order = db_sess.query(Order).filter(Order.status < max(ORDER_STATUS.keys()),
                                                Order.poster_id != current_user.id).first()
            if order:
                session["orders_flag"] = True
            else:
                session["orders_flag"] = False
        else:
            session["orders_flag"] = False
    else:
        session["orders_flag"] = False


def base_settings_update_check():
    change_theme()
    cart_check()
    update_recommendations()
    orders_mod_check()


def base_settings_request_check():
    return "change-theme" in request.form


def update_user_status(page: str):
    write_log("\n")
    t = datetime.datetime.now()
    if current_user.is_authenticated:
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter(current_user.id == User.id).first()
        user.last_auth = t
        db_sess.commit()
        write_log(f"{str(t)} - запрос от пользователя {user.name} (ID - {user.id}, полномочия - "
                  f"{'админ' if user.is_admin else 'модератор' if user.is_moderator else 'нет'}) "
                  f"[{page}, {request.method}]")
    else:
        if not session.get("theme"):
            session["theme"] = DEFAULT_THEME
        write_log(f"{str(t)} - запрос от анонимного пользователя (IP - {request.remote_addr}) [{page}, "
                  f"{request.method}]")
    write_log("Состояние корзины ("
              f"{'ID - ' + str(current_user.id) if current_user.is_authenticated else 'IP - ' + request.remote_addr}"
              f"): {session.get('cart') if session.get('cart') else 'пусто'}")
    write_log("Состояние рекомендаций ("
              f"{'ID - ' + str(current_user.id) if current_user.is_authenticated else 'IP - ' + request.remote_addr}"
              f"): {session.get('rec') if session.get('rec') else 'пусто'}")


def update_recommendations():
    if not session.get("rec"):
        session["rec"] = []
    else:
        while len(session["rec"]) > TAGS_COUNT_IN_RECS:
            print(f"Тэг {session['rec'].pop(0)} убран из рекомендаций")
        session["rec"] = list(set(session["rec"]))


def clear_cart():
    user_text = current_user.name + f'[ID - {current_user.id}]' if current_user.is_authenticated else \
        request.remote_addr
    if session.get("cart"):
        session["cart"].clear()
        write_log(f"Корзина очищена (Запрос от пользователя {user_text})")
        flash("Корзина очищена", "success")
    else:
        flash("Корзина уже пуста", "danger")


def clear_rec():
    user_text = current_user.name + f'[ID - {current_user.id}]' if current_user.is_authenticated else \
        request.remote_addr
    if session.get("rec"):
        session["rec"].clear()
        write_log(f"Рекомендации были очищены (Запрос от пользователя {user_text})")
        flash("Рекомендации очищены", "success")
    else:
        flash("Рекомендации ещё не подготовлены", "danger")


def init_admin():
    db_sess = db_session.create_session()
    write_log("Проверка на существование аккаунта администратора...")
    if db_sess.query(User).filter(User.is_admin == 1).first():
        write_log("Аккаунт администратора уже существует")
    else:
        admin = User()
        admin.hashed_password = ADMIN_PASSWORD
        admin.name = ADMIN_NAME
        admin.email = ADMIN_EMAIL
        admin.phone = ADMIN_PHONE
        admin.is_admin = True
        db_sess.add(admin)
        db_sess.commit()
        write_log("Аккаунт администратора создан")


@app.route("/robots.txt")
def robots():
    update_user_status("robots.txt")
    return "<pre>" + open("robots.txt").read() + "</pre>"


@app.route("/admin/log")
@login_required
def logs_page():
    update_user_status("Логи")
    if current_user.is_admin:
        return "<pre>" + open("data/logs/shop_log.txt", encoding="utf-8").read() + "</pre>"
    else:
        abort(403)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    base_settings_update_check()
    update_user_status("Регистрация")
    if current_user.is_authenticated:
        return redirect("/home")
    else:
        if request.method == "GET":
            t = load_theme()
            return render_template("signup.html", title=f"{SHOP_NAME} - вход в аккаунт", current_user=current_user,
                                   theme=t, hf_flag=False, YEAR=datetime.datetime.now().year, COMPANY_NAME=COMPANY_NAME,
                                   main_class="form-signin w-100 m-auto px-4 my-5 border-color-theme border "
                                              "border-round", page_name="signup", THEMES=THEMES)
        elif request.method == "POST":
            if not base_settings_request_check():
                if request.form.get("name") and request.form.get("phone") and request.form.get("password") and \
                        request.form.get("password_confirm") and request.form.get("personal-data"):
                    if not phone_check(request.form.get("phone")):
                        session["name"] = request.form.get("name") if request.form.get("name") != "None" and \
                            request.form.get("name") else ""
                        session["phone"] = request.form.get("phone") if request.form.get("phone") != "None" and \
                            request.form.get("phone") else ""
                        session["email"] = request.form.get("email") if request.form.get("email") != "None" and \
                            request.form.get("email") else ""
                        flash("Телефон введён некорректно", "danger")
                        return redirect("/signup")
                    if request.form.get("password") == request.form.get("password_confirm"):
                        db_sess = db_session.create_session()
                        if request.form.get("email"):
                            existing_user = db_sess.query(User).filter((User.email ==
                                                                        request.form.get("email")) |
                                                                       (User.phone ==
                                                                        request.form.get("phone"))).first()
                        else:
                            existing_user = db_sess.query(User).filter(User.phone == request.form.get("phone")).first()
                        if existing_user:
                            session["name"] = request.form.get("name") if request.form.get("name") != "None" and \
                                                                          request.form.get("name") else ""
                            flash("Пользователь с такой почтой или таким телефоном уже существует", "danger")
                            return redirect("/signup")
                        else:
                            user = User()
                            user.name = name_correct(request.form.get("name"))
                            user.email = request.form.get("email") if request.form.get("email") else None
                            user.address = request.form.get("address") if request.form.get("address") else None
                            user.phone = phone_correct(request.form.get("phone"))
                            user.hashed_password = generate_password_hash(request.form.get("password"))
                            db_sess.add(user)
                            db_sess.commit()
                            login_user(user)
                            session["name"] = ""
                            session["phone"] = ""
                            session["email"] = ""
                            session["address"] = ""
                            flash("Регистрация прошла успешно", "success")
                            write_log(f"Зарегистрирован новый пользователь: {user.name} (ID - {user.id})")
                            return redirect("/home")
                    else:
                        session["name"] = request.form.get("name") if request.form.get("name") != "None" and \
                            request.form.get("name") else ""
                        session["phone"] = request.form.get("phone") if request.form.get("phone") != "None" and \
                            request.form.get("phone") else ""
                        session["email"] = request.form.get("email") if request.form.get("email") != "None" and \
                            request.form.get("email") else ""
                        session["address"] = request.form.get("address") if request.form.get("address") != "None" and \
                            request.form.get("address") else ""
                        flash("Пароль и подтверждение пароля не совпадают", "danger")
                        return redirect("/signup")
                else:
                    session["name"] = request.form.get("name") if request.form.get("name") != "None" and \
                        request.form.get("name") else ""
                    session["phone"] = request.form.get("phone") if request.form.get("phone") != "None" and \
                        request.form.get("phone") else ""
                    session["email"] = request.form.get("email") if request.form.get("email") != "None" and \
                        request.form.get("email") else ""
                    session["address"] = request.form.get("address") if request.form.get("address") != "None" and \
                        request.form.get("address") else ""
                    flash("Не все обязательные поля заполнены", "danger")
                    return redirect("/signup")
            else:
                return redirect("/signup")


@app.route("/login", methods=["GET", "POST"])
def login():
    base_settings_update_check()
    update_user_status("Вход в аккаунт")
    if current_user.is_authenticated:
        return redirect("/home")
    else:
        if request.method == "GET":
            t = load_theme()
            return render_template("login.html", title=f"{SHOP_NAME} - вход в аккаунт", current_user=current_user,
                                   theme=t, hf_flag=False, YEAR=datetime.datetime.now().year, COMPANY_NAME=COMPANY_NAME,
                                   main_class="form-signin w-100 m-auto px-4 my-5 border-color-theme border "
                                              "border-round", page_name="login", THEMES=THEMES)
        elif request.method == "POST":
            if not base_settings_request_check():
                db_sess = db_session.create_session()
                user = db_sess.query(User).filter((User.phone == phone_correct(request.form.get("login"))) |
                                                  (User.email == request.form.get("login"))).first()
                if user:
                    if check_password_hash(user.hashed_password, request.form.get("password")):
                        login_user(user)
                        session["login"] = ""
                        flash("Успешный вход", "success")
                        write_log(f"Пользователь {user.name} (ID - {user.id}) вошёл в аккаунт")
                        return redirect("/home")
                    else:
                        session["login"] = request.form.get("login") if request.form.get("login") != "None" and \
                            request.form.get("login") else ""
                        flash("Неверное имя пользователя или пароль", "danger")
                        return redirect("/login")
                else:
                    session["login"] = request.form.get("login") if request.form.get("login") != "None" and \
                            request.form.get("login") else ""
                    flash("Неверное имя пользователя или пароль", "danger")
                    return redirect("/login")
            else:
                return redirect("/login")


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    base_settings_update_check()
    update_user_status("Настройки")
    if request.method == "GET":
        t = load_theme()
        return render_template("settings.html", title=f"{SHOP_NAME} - настройки", current_user=current_user,
                               theme=t, hf_flag=False, YEAR=datetime.datetime.now().year, COMPANY_NAME=COMPANY_NAME,
                               main_class="form-signin w-100 m-auto px-4 my-5 border-color-theme border border-round",
                               page_name="settings", THEMES=THEMES)
    elif request.method == "POST":
        if not base_settings_request_check():
            if request.form.get("old_password"):
                write_log(request.form.get("phone") + ": " + str(phone_check(request.form.get("phone"))))
                if not phone_check(request.form.get("phone")):
                    session["new_name"] = request.form.get("name") if request.form.get("name") != "None" and \
                        request.form.get("name") else current_user.name
                    session["new_phone"] = request.form.get("phone") if request.form.get("phone") != "None" and \
                        request.form.get("phone") else current_user.phone
                    session["new_email"] = request.form.get("email") if request.form.get("email") != "None" and \
                        request.form.get("email") else current_user.email
                    session["new_address"] = request.form.get("address") if request.form.get("address") != "None" and \
                        request.form.get("address") else current_user.address
                    flash("Телефон введён некорректно", "danger")
                    return redirect("/settings")
                if check_password_hash(current_user.hashed_password, request.form.get("old_password")):
                    db_sess = db_session.create_session()
                    existing_user = db_sess.query(User).filter(((User.email == request.form.get("email")) |
                                                               (User.phone == request.form.get("phone"))),
                                                               User.id != current_user.id).first()
                    if existing_user:
                        flash("Пользователь с такой почтой или таким телефоном уже существует", "danger")
                        return redirect("/settings")
                    else:
                        user = db_sess.query(User).filter(User.id == current_user.id).first()
                        if request.form.get("name"):
                            user.name = name_correct(request.form.get("name"))
                        user.email = request.form.get("email")
                        user.address = request.form.get("address")
                        if request.form.get("phone"):
                            user.phone = phone_correct(request.form.get("phone"))
                        if request.form.get("new_password") and request.form.get("confirm_password") and \
                                request.form.get("new_password") == request.form.get("confirm_password"):
                            user.hashed_password = generate_password_hash(request.form.get("new_password"))
                        db_sess.add(user)
                        db_sess.commit()
                        login_user(user)
                        session["new_name"] = ""
                        session["new_phone"] = ""
                        session["new_email"] = ""
                        session["new_address"] = ""
                        flash("Данные обновлены", "success")
                        write_log(f"Пользователь обновил в аккаунте данные: {user.name} (ID - {user.id})")
                        return redirect("/home")
                else:
                    session["new_name"] = request.form.get("name") if request.form.get("name") != "None" and \
                        request.form.get("name") else current_user.name
                    session["new_phone"] = request.form.get("phone") if request.form.get("phone") != "None" and \
                        request.form.get("phone") else current_user.phone
                    session["new_email"] = request.form.get("email") if request.form.get("email") != "None" and \
                        request.form.get("email") else current_user.email
                    session["new_address"] = request.form.get("address") if request.form.get("address") != "None" and \
                        request.form.get("address") else current_user.address
                    flash("Пароль и подтверждение пароля не совпадают", "danger")
                    return redirect("/settings")
            else:
                session["new_name"] = request.form.get("name") if request.form.get("name") != "None" and \
                    request.form.get("name") else current_user.name
                session["new_phone"] = request.form.get("phone") if request.form.get("phone") != "None" and \
                    request.form.get("phone") else current_user.new_phone
                session["new_email"] = request.form.get("email") if request.form.get("email") != "None" and \
                    request.form.get("email") else current_user.email
                session["new_address"] = request.form.get("address") if request.form.get("address") != "None" and \
                    request.form.get("address") else current_user.address
                flash("Не все обязательные поля заполнены", "danger")
                return redirect("/settings")
        else:
            return redirect("/settings")


@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    update_user_status("Выход с аккаунта")
    logout_user()
    flash("Успешный выход", "success")
    return redirect("/")


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin_page():
    update_user_status("Меню администратора")
    db_sess = db_session.create_session()
    admin = db_sess.query(User).filter(User.id == current_user.id).first()
    if request.args.get("search"):
        users = user_search(request.args.get("search"), db_sess.query(User).filter(User.id != current_user.id))
    else:
        users = list(db_sess.query(User).filter(User.id != current_user.id))
    if admin.is_admin:
        base_settings_update_check()
        if request.method == "GET":
            t = load_theme()
            return render_template("admin.html", title=f"{SHOP_NAME} - меню администратора", page_name="admin",
                                   current_user=current_user, theme=t, YEAR=datetime.datetime.now().year, hf_flag=True,
                                   main_class="px-2", COMPANY_NAME=COMPANY_NAME, THEMES=THEMES, users=users)
        elif request.method == "POST":
            if "log" in request.form:
                flash("Логи перемещены в архив", "success")
                archive_log()
            elif "make_moderator" in request.form:
                moderator = db_sess.query(User).filter(User.id == request.form.get("make_moderator")).first()
                if moderator.is_admin:
                    flash("Пользователь {moderator.name} (ID - {moderator.id}) уже является администратором")
                else:
                    moderator.is_moderator = True
                    db_sess.commit()
                    flash(f"Пользователь {moderator.name} (ID - {moderator.id}) теперь является модератором", "success")
                    write_log(f"Пользователь {moderator.name} (ID - {moderator.id}) теперь является модератором")
            elif "unmake_moderator" in request.form:
                moderator = db_sess.query(User).filter(User.id == request.form.get("unmake_moderator")).first()
                if moderator.is_admin:
                    flash("Пользователь {moderator.name} (ID - {moderator.id}) уже является администратором")
                else:
                    moderator.is_moderator = False
                    db_sess.commit()
                    flash(f"Пользователь {moderator.name} (ID - {moderator.id}) теперь не является модератором",
                          "success")
                    write_log(f"Пользователь {moderator.name} (ID - {moderator.id}) теперь не является модератором")
            elif "clear_cart" in request.form:
                clear_cart()
            elif "clear_rec" in request.form:
                clear_rec()
            elif "clear_session" in request.form:
                if session:
                    session.clear()
                    flash("Словарь session очищен", "success")
                else:
                    flash("Словарь session уже был пустой", "danger")
            elif "make_backup" in request.form:
                shutil.copy2("db/shop.db", "db/backup_shop.db")
                write_log(f"БД скопирована")
                path = os.walk("data/backup_media")
                for fol in path:
                    for file in fol[2]:
                        if ".gitignore" not in file:
                            os.remove(fol[0] + "/" + file)
                            write_log(f'Файл {file} удалён')
                path = os.walk(app.config["UPLOAD_FOLDER"])
                for fol in path:
                    for file in fol[2]:
                        if ".gitignore" not in file:
                            shutil.copy2(fol[0] + "/" + file, "data/backup_media")
                            write_log(f"Файл {file} скопирован")
                flash("Копия сделана", "success")
                write_log("Админ сделал копию БД и файлов")
            elif "restore_from_backup" in request.form:
                if os.path.isfile("db/backup_shop.db"):
                    shutil.copy2("db/backup_shop.db", "db/shop.db")
                    write_log(f"БД скопирована")
                    path = os.walk("data/backup_media")
                    for fol in path:
                        for file in fol[2]:
                            if ".gitignore" not in file:
                                shutil.copy2(fol[0] + "/" + file, app.config["UPLOAD_FOLDER"])
                                write_log(f"Файл {file} скопирован")
                    flash("Данные восстановлены", "success")
                    write_log("Админ восстановил БД и файлы из резервной копии")
                else:
                    flash("Нет резервной копии", "danger")
            return redirect("/admin")
    else:
        abort(403)


@app.route("/add_product", methods=["GET", "POST"])
@login_required
def add_product():
    base_settings_update_check()
    update_user_status("Добавление товара")
    db_sess = db_session.create_session()
    user = db_sess.query(User).filter(User.id == current_user.id).first()
    manufacturers_list = list(db_sess.query(Manufacturer))
    if user.is_admin or user.is_moderator:
        base_settings_update_check()
        if request.method == "GET":
            if not manufacturers_list:
                flash("Сперва нужно создать автора", "danger")
                return redirect("/add_manufacturer")
            t = load_theme()
            return render_template("add_product.html", title=f"{SHOP_NAME} - добавление товара", THEMES=THEMES,
                                   page_name="add_product", current_user=current_user, theme=t, hf_flag=False,
                                   YEAR=datetime.datetime.now().year, accept_images=accept_images,
                                   main_class="form-signin w-100 m-auto px-4 my-5 border-color-theme border "
                                              "border-round", COMPANY_NAME=COMPANY_NAME,
                                   manufacturers_list=manufacturers_list)
        elif request.method == "POST":
            if not base_settings_request_check():
                if request.form.get("name") and request.form.get("about") and request.form.get("tags"):
                    files = request.files.getlist("files[]")
                    write_log("Проверка файлов:")
                    f_count = 0
                    if files:
                        for file in files:
                            if not allowed_type(file.filename, IMAGES):
                                write_log(f"Файл {file.filename} не прошёл проверку")
                                f_count += 1
                    if not f_count and not files:
                        write_log("Файлов нет (либо они некорректных форматов), отправка отменяется")
                        flash("Отсутствуют фотографии. Выложите их и проверьте, чтобы они были одним из поддерживаемых "
                              "сайтом форматов", "danger")
                        session["product_name"] = request.form.get("name") if request.form.get("name") != "None" and \
                            request.form.get("name") else ""
                        session["about"] = request.form.get("about") if request.form.get("about") != "None" and \
                            request.form.get("about") else ""
                        session["tags"] = request.form.get("tags") if request.form.get("tags") != "None" and \
                            request.form.get("tags") else ""
                        session["manufacturer"] = request.form.get("manufacturer") if \
                            request.form.get("manufacturer") != "None" and request.form.get("manufacturer") else ""
                        return redirect("/add_product")
                    manufacturer = db_sess.query(Manufacturer).filter(Manufacturer.id ==
                                                                      request.form.get("manufacturer")).first()
                    if not manufacturer:
                        write_log(f"Автора с ID {request.form.get('manufacturer')} не существует")
                        flash(f"Автора с ID {request.form.get('manufacturer')} не существует", "danger")
                        session["product_name"] = request.form.get("name") if request.form.get("name") != "None" and \
                            request.form.get("name") else ""
                        session["about"] = request.form.get("about") if request.form.get("about") != "None" and \
                            request.form.get("about") else ""
                        session["tags"] = request.form.get("tags") if request.form.get("tags") != "None" and \
                            request.form.get("tags") else ""
                        session["manufacturer"] = request.form.get("manufacturer") if \
                            request.form.get("manufacturer") != "None" and request.form.get("manufacturer") else ""
                    product = Product()
                    product.poster_id = current_user.id
                    product.name = request.form.get("name")
                    product.about = request.form.get("about")
                    product.tags = request.form.get("tags")
                    product.manufacturer_id = manufacturer.id
                    product.images = ""
                    product.image_preview = ""
                    db_sess.add(product)
                    db_sess.commit()
                    images = []
                    f_count = 0
                    write_log("Начало процесса сохранения картинок")
                    for file in files:
                        if allowed_type(file.filename, IMAGES):
                            filename = f"product_{product.id}_{f_count}.{file.filename.rsplit('.', 1)[1].lower()}"
                            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                            images.append(filename)
                            write_log(f"Файл {file.filename} сохранён как {filename}")
                            f_count += 1
                    product.images = ",".join(images)
                    product.image_preview = make_image_preview(os.path.join(app.config["UPLOAD_FOLDER"], images[0]),
                                                               os.path.join(app.config["UPLOAD_FOLDER"],
                                                                            f"product_{product.id}_preview.png"))
                    db_sess.commit()
                    write_log("Картинки сохранены")
                    session["product_name"] = ""
                    session["about"] = ""
                    session["tags"] = ""
                    session["manufacturer"] = ""
                    return redirect(f"/products/{product.id}")
                else:
                    session["product_name"] = request.form.get("name") if request.form.get("name") != "None" and \
                        request.form.get("name") else ""
                    session["about"] = request.form.get("about") if request.form.get("about") != "None" and \
                        request.form.get("about") else ""
                    session["tags"] = request.form.get("tags") if request.form.get("tags") != "None" and \
                        request.form.get("tags") else ""
                    session["manufacturer"] = request.form.get("manufacturer") if \
                        request.form.get("manufacturer") != "None" and request.form.get("manufacturer") else ""
                    flash("Не все обязательные поля заполнены", "danger")
                    return redirect("/add_product")
            else:
                return redirect("/add_product")
    else:
        abort(403)


@app.route("/add_manufacturer", methods=["GET", "POST"])
@login_required
def add_manufacturer():
    base_settings_update_check()
    update_user_status("Добавление автора")
    db_sess = db_session.create_session()
    user = db_sess.query(User).filter(User.id == current_user.id).first()
    if user.is_admin or user.is_moderator:
        base_settings_update_check()
        if request.method == "GET":
            t = load_theme()
            return render_template("add_manufacturer.html", title=f"{SHOP_NAME} - добавление автора",
                                   THEMES=THEMES, page_name="add_manufacturer", current_user=current_user, theme=t,
                                   hf_flag=False, YEAR=datetime.datetime.now().year, accept_images=accept_images,
                                   main_class="form-signin w-100 m-auto px-4 my-5 border-color-theme border "
                                              "border-round", COMPANY_NAME=COMPANY_NAME)
        elif request.method == "POST":
            if not base_settings_request_check():
                if request.form.get("name") and request.form.get("about"):
                    files = request.files.getlist("file")
                    write_log("Проверка файла:")
                    if files:
                        for file in files:
                            if not allowed_type(file.filename, IMAGES):
                                write_log(f"Файл {file.filename} не прошёл проверку, отправка отменяется")
                                flash("Отсутствуют фотографии. Выложите их и проверьте, чтобы они были одним из "
                                      "поддерживаемых сайтом форматов", "danger")
                                session["manufacturer_name"] = request.form.get("name") if request.form.get("name") \
                                    != "None" and request.form.get("name") else ""
                                session["manufacturer_about"] = request.form.get("about") if request.form.get("about") \
                                    != "None" and request.form.get("about") else ""
                                return redirect("/add_manufacturer")
                    else:
                        flash("Отсутствуют фотографии. Выложите их и проверьте, чтобы они были одним из поддерживаемых "
                              "сайтом форматов", "danger")
                        session["manufacturer_name"] = request.form.get("name") if request.form.get("name") != "None" \
                            and request.form.get("name") else ""
                        session["manufacturer_about"] = request.form.get("about") if request.form.get("about") \
                            != "None" and request.form.get("about") else ""
                        return redirect("/add_manufacturer")
                    manufacturer = Manufacturer()
                    manufacturer.poster_id = current_user.id
                    manufacturer.name = request.form.get("name")
                    manufacturer.about = request.form.get("about")
                    manufacturer.logo = ""
                    manufacturer.logo_preview = ""
                    db_sess.add(manufacturer)
                    db_sess.commit()
                    write_log("Начало процесса сохранения логотипа")
                    for file in files:
                        filename = f"manufacturer_{manufacturer.id}.{file.filename.rsplit('.', 1)[1].lower()}"
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(file_path)
                        write_log(f"Файл {file.filename} сохранён как {filename}")
                        manufacturer.logo = filename
                        manufacturer.logo_preview = make_image_preview(file_path,
                                                                       os.path.join(app.config['UPLOAD_FOLDER'],
                                                                                    f"manufacturer_{manufacturer.id}"
                                                                                    "_preview.png"))
                    db_sess.commit()
                    write_log("Логотип сохранён")
                    session["manufacturer_name"] = ""
                    session["manufacturer_about"] = ""
                    return redirect(f"/manufacturers/{manufacturer.id}")
                else:
                    session["manufacturer_name"] = request.form.get("name") if request.form.get("name") != "None" and \
                        request.form.get("name") else ""
                    session["manufacturer_about"] = request.form.get("about") if request.form.get("about") != "None" \
                        and request.form.get("about") else ""
                    flash("Не все обязательные поля заполнены", "danger")
                    return redirect("/add_manufacturer")
            else:
                return redirect("/add_manufacturer")
    else:
        abort(403)


@app.route("/", methods=["GET", "POST"])
def index():
    base_settings_update_check()
    if request.method == "GET":
        update_user_status("Главная страница")
        db_sess = db_session.create_session()
        if current_user.is_authenticated:
            if current_user.is_admin or current_user.is_moderator:
                products_list = [x for x in db_sess.query(Product)]
            else:
                products_list = [x for x in db_sess.query(Product).filter(Product.toggle)]
        else:
            products_list = [x for x in db_sess.query(Product).filter(Product.toggle)]
        products_list.sort(key=lambda x: x.name)
        products_list.sort(key=lambda x: rec_sort(x.tags, session.get("rec")), reverse=True)
        products_list = products_list[:PRODUCTS_IN_INDEX]
        t = load_theme()
        return render_template("index.html", title=SHOP_NAME, hf_flag=True, current_user=current_user, THEMES=THEMES,
                               main_class="px-2", theme=t, YEAR=datetime.datetime.now().year, page_name="index",
                               COMPANY_NAME=COMPANY_NAME, products_list=products_list)
    elif request.method == "POST":
        if "put_into_cart" in request.form:
            db_sess = db_session.create_session()
            if db_sess.query(Product).filter(Product.id == int(request.form.get("put_into_cart"))).first():
                count = int(request.form.get("count")) if request.form.get("count").isdigit() else 1
                if count:
                    if request.form.get("put_into_cart") in session["cart"]:
                        flash("Кол-во книг в корзине изменено", "success")
                    else:
                        flash("Книга добавлена в корзину", "success")
                    session["cart"][request.form.get("put_into_cart")] = count
                else:
                    if request.form.get("put_into_cart") in session["cart"]:
                        session["cart"].pop(request.form.get("put_into_cart"))
                        write_log(f'Книга с ID {request.form.get("put_into_cart")} убрана из корзины')
                        flash("Книга убрана из корзины", "success")
                    else:
                        flash("Книги не было в корзине", "danger")
        elif "remove_from_cart" in request.form:
            if request.form.get("remove_from_cart") in session["cart"]:
                db_sess = db_session.create_session()
                if db_sess.query(Product).filter(Product.id == int(request.form.get("remove_from_cart"))).first():
                    write_log('Книга с ID '
                              f'{session["cart"][session["cart"].pop(request.form.get("remove_from_cart"))]} '
                              'убрана из корзины')
                    flash("Книга убрана из корзины", "success")
                else:
                    flash("Книги не существует", "danger")
            else:
                flash("Книги не было в корзине", "danger")
        elif "clear_rec" in request.form:
            clear_rec()
        return redirect("/")


@app.route("/about", methods=["GET", "POST"])
def about():
    base_settings_update_check()
    if request.method == "GET":
        update_user_status("О компании")
        t = load_theme()
        return render_template("about.html", title=f"{SHOP_NAME} - о компании", hf_flag=True, current_user=current_user,
                               THEMES=THEMES, main_class="px-2", theme=t, YEAR=datetime.datetime.now().year,
                               page_name="about", COMPANY_NAME=COMPANY_NAME, COMPANY_ABOUT=COMPANY_ABOUT)
    elif request.method == "POST":
        return redirect("/about")


@app.route("/home", methods=["GET", "POST"])
@login_required
def home():
    base_settings_update_check()
    if request.method == "GET":
        update_user_status("Личный кабинет")
        t = load_theme()
        return render_template("home.html", title=f"{SHOP_NAME} - личный кабинет", hf_flag=True, THEMES=THEMES,
                               current_user=current_user, main_class="px-2", theme=t, YEAR=datetime.datetime.now().year,
                               page_name="home", COMPANY_NAME=COMPANY_NAME)
    elif request.method == "POST":
        if "clear_cart" in request.form:
            clear_cart()
        elif "clear_rec" in request.form:
            clear_rec()
        return redirect("/home")


@app.route("/products", methods=["GET", "POST"])
def products():
    base_settings_update_check()
    if request.method == "GET":
        update_user_status("Книги")
        db_sess = db_session.create_session()
        if request.args.get("search"):
            if current_user.is_authenticated:
                if current_user.is_admin or current_user.is_moderator:
                    products_list = product_name_search(request.args.get("search"), db_sess.query(Product))
                else:
                    products_list = product_name_search(request.args.get("search"),
                                                        db_sess.query(Product).filter(Product.toggle))
            else:
                products_list = product_name_search(request.args.get("search"),
                                                    db_sess.query(Product).filter(Product.toggle))
        else:
            if current_user.is_authenticated:
                if current_user.is_admin or current_user.is_moderator:
                    products_list = list(db_sess.query(Product))
                else:
                    products_list = list(db_sess.query(Product).filter(Product.toggle))
            else:
                products_list = list(db_sess.query(Product).filter(Product.toggle))
        products_list.sort(key=lambda x: x.name)
        products_list.sort(key=lambda x: rec_sort(x.tags, session.get("rec")), reverse=True)
        t = load_theme()
        return render_template("products.html", title=f"{SHOP_NAME} - товары", hf_flag=True, current_user=current_user,
                               THEMES=THEMES, main_class="px-2", theme=t, YEAR=datetime.datetime.now().year,
                               page_name="products", COMPANY_NAME=COMPANY_NAME, products_list=products_list)
    elif request.method == "POST":
        if "put_into_cart" in request.form:
            db_sess = db_session.create_session()
            if db_sess.query(Product).filter(Product.id == int(request.form.get("put_into_cart"))).first():
                count = int(request.form.get("count")) if request.form.get("count").isdigit() else 1
                if count:
                    if request.form.get("put_into_cart") in session["cart"]:
                        flash("Кол-во книг в корзине изменено", "success")
                    else:
                        flash("Книга добавлена в корзину", "success")
                    session["cart"][request.form.get("put_into_cart")] = count
                else:
                    if request.form.get("put_into_cart") in session["cart"]:
                        session["cart"].pop(request.form.get("put_into_cart"))
                        write_log(f'Книга с ID {request.form.get("put_into_cart")} убрана из корзины')
                        flash("Книга убрана из корзины", "success")
                    else:
                        flash("Книги не было в корзине", "danger")
        elif "remove_from_cart" in request.form:
            if request.form.get("remove_from_cart") in session["cart"]:
                db_sess = db_session.create_session()
                if db_sess.query(Product).filter(Product.id == int(request.form.get("remove_from_cart"))).first():
                    session["cart"].pop(request.form.get("remove_from_cart"))
                    write_log(f'Книга с ID {request.form.get("remove_from_cart")} убрана из корзины')
                    flash("Книга убрана из корзины", "success")
                else:
                    flash("Книги не существует", "danger")
            else:
                flash("Книги не было в корзине", "danger")
        elif "clear_rec" in request.form:
            clear_rec()
        return redirect("/products")


@app.route("/manufacturers", methods=["GET", "POST"])
def manufacturers():
    base_settings_update_check()
    if request.method == "GET":
        update_user_status("Авторы")
        db_sess = db_session.create_session()
        if request.args.get("search"):
            if current_user.is_authenticated:
                if current_user.is_admin or current_user.is_moderator:
                    manufacturers_list = user_search(request.args.get("search"), db_sess.query(Manufacturer))
                else:
                    manufacturers_list = user_search(request.args.get("search"),
                                                     db_sess.query(Manufacturer).filter(Manufacturer.toggle))
            else:
                manufacturers_list = user_search(request.args.get("search"),
                                                 db_sess.query(Manufacturer).filter(Manufacturer.toggle))
        else:
            if current_user.is_authenticated:
                if current_user.is_admin or current_user.is_moderator:
                    manufacturers_list = list(db_sess.query(Manufacturer))
                else:
                    manufacturers_list = list(db_sess.query(Manufacturer).filter(Manufacturer.toggle))
            else:
                manufacturers_list = list(db_sess.query(Manufacturer).filter(Manufacturer.toggle))
        manufacturers_list.sort(key=lambda x: x.name)
        t = load_theme()
        return render_template("manufacturers.html", title=f"{SHOP_NAME} - авторы", hf_flag=True,
                               current_user=current_user, THEMES=THEMES, main_class="px-2", theme=t,
                               YEAR=datetime.datetime.now().year, page_name="manufacturers", COMPANY_NAME=COMPANY_NAME,
                               manufacturers_list=manufacturers_list)
    elif request.method == "POST":
        return redirect("/manufacturers")


@app.route("/products/<product_id>", methods=["GET", "POST"])
def product_info(product_id):
    base_settings_update_check()
    db_sess = db_session.create_session()
    product = db_sess.query(Product).filter(Product.id == product_id).first()
    poster = db_sess.query(User).filter(User.id == product.poster_id).first()
    manufacturer = db_sess.query(Manufacturer).filter(Manufacturer.id == product.manufacturer_id).first()
    product_images = product.images.split(",")
    product_tags = product.tags.split()
    books = db_sess.query(Book).filter(product_id == Book.product_id).count()
    max_book_count = db_sess.query(Book).filter(Book.product_id == product_id, Book.owner == None, Book.toggle).count()
    if request.method == "GET":
        update_user_status(f"Товар (ID - {product_id})")
        t = load_theme()
        for product_tag in product_tags:
            session["rec"].append(product_tag)
        return render_template("product.html", title=f"{SHOP_NAME} - {product.name}", hf_flag=True, THEMES=THEMES,
                               current_user=current_user, main_class="px-2", theme=t, YEAR=datetime.datetime.now().year,
                               page_name="product", COMPANY_NAME=COMPANY_NAME, product=product, poster=poster,
                               product_images=product_images, product_tags=product_tags, manufacturer=manufacturer,
                               product_images_l=len(product_images), books=books, max_book_count=max_book_count)
    elif request.method == "POST":
        if "put_into_cart" in request.form:
            db_sess = db_session.create_session()
            if db_sess.query(Product).filter(Product.id == product_id).first():
                count = int(request.form.get("count")) if request.form.get("count").isdigit() else 1

                if 0 < count <= max_book_count:
                    if str(product_id) in session["cart"]:
                        flash("Кол-во книг в корзине изменено", "success")
                    else:
                        flash("Книга добавлена в корзину", "success")
                    session["cart"][str(product_id)] = count
                elif not count:
                    if str(product_id) in session["cart"]:
                        session["cart"].pop(str(product_id))
                        write_log(f'Книга с ID {product_id} убрана из корзины')
                        flash("Книга убрана из корзины", "success")
                    else:
                        flash("Книги не было в корзине", "danger")
                else:
                    session["cart"][str(product_id)] = max_book_count
                    flash("Ваш спрос превысил количество экземпляров этой книги, поэтому в корзину помещено "
                          "их максимально допустимое кол-во", "warning")
        elif "remove_from_cart" in request.form:
            if str(product_id) in session["cart"]:
                db_sess = db_session.create_session()
                if db_sess.query(Product).filter(Product.id == product_id).first():
                    session["cart"].pop(str(product_id))
                    write_log(f'Книга с ID {product_id} убрана из корзины')
                    flash("Книга убрана из корзины", "success")
                else:
                    flash("Книги не существует", "danger")
            else:
                flash("Книги не было в корзине", "danger")
        if current_user.is_authenticated:
            if "delete_product" in request.form:
                if current_user.is_admin or current_user.is_moderator:
                    orders_list = list(db_sess.query(Order))
                    for order in orders_list:
                        if int(product_id) in bake_dict_from_db(order.products_list, func_for_key=int):
                            flash("Эту книгу удалить нельзя, она уже была когда-то заказана", "danger")
                            return redirect(f"/products/{product_id}")
                    for img in product_images:
                        img_path = os.path.join(app.config["UPLOAD_FOLDER"], img)
                        if os.path.isfile(img_path):
                            os.remove(img_path)
                    name = product.name
                    db_sess.delete(product)
                    db_sess.commit()
                    flash(f"Книга {name} (ID - {product_id}) успешно удалена", "success")
                    write_log(f"Книга {name} (ID - {product_id}) был удалена")
                    return redirect("/products")
                else:
                    flash("У вас нет прав")
            elif "toggle_product" in request.form:
                if current_user.is_admin or current_user.is_moderator:
                    if manufacturer.toggle:
                        product.poster_id = current_user.id
                        if product.toggle:
                            product.toggle = False
                            db_sess.commit()
                            flash(f"Книга {product.name} (ID - {product_id}) успешно отключена", "success")
                            write_log(f"Книга {product.name} (ID - {product_id}) был отключена")
                        else:
                            product.toggle = True
                            db_sess.commit()
                            flash(f"Книга {product.name} (ID - {product_id}) успешно включена", "success")
                            write_log(f"Книга {product.name} (ID - {product_id}) был включена")
                    else:
                        flash("Сначала надо включить автора этой книги", "danger")
            elif "change_product_count" in request.form:
                if current_user.is_admin or current_user.is_moderator:
                    if product.toggle:
                        if request.form.get("max_count").isdigit():
                            print(books, int(request.form.get("max_count")))
                            if books == int(request.form.get("max_count")):
                                flash("Вы не меняли кол-во книг", "warning")
                            elif books < int(request.form.get("max_count")) and \
                                    int(request.form.get("max_count")) >= 0:
                                for book_i in range(books, int(request.form.get("max_count"))):
                                    book = Book()
                                    book.product_id = product_id
                                    book.poster_id = current_user.id
                                    book.status = 0
                                    db_sess.add(book)
                                db_sess.commit()
                            elif books > int(request.form.get("max_count")) >= 0:
                                for book_i in range(int(request.form.get("max_count")), books):
                                    book = db_sess.query(Book).filter(product_id == Book.product_id,
                                                                      Book.owner == None).first()
                                    if book:
                                        db_sess.delete(book)
                                    else:
                                        flash("Невозможно удалить какую-то часть этих книг: "
                                              "они уже были заказаны", "danger")
                                db_sess.commit()
                        else:
                            flash("В поле максимального кол-ва книг нужно ввести число", "danger")
                    else:
                        flash("Сначала надо включить эту книгу", "danger")
        return redirect(f"/products/{product_id}")


@app.route("/manufacturers/<manufacturer_id>", methods=["GET", "POST"])
def manufacturer_info(manufacturer_id):
    base_settings_update_check()
    db_sess = db_session.create_session()
    manufacturer = db_sess.query(Manufacturer).filter(Manufacturer.id == manufacturer_id).first()
    poster = db_sess.query(User).filter(User.id == manufacturer.poster_id).first()
    if request.args.get("search"):
        if current_user.is_authenticated:
            if current_user.is_admin or current_user.is_moderator:
                products_list = product_name_search(request.args.get("search"),
                                                    db_sess.query(Product).filter(Product.manufacturer_id ==
                                                                                  manufacturer_id))
            else:
                products_list = product_name_search(request.args.get("search"),
                                                    db_sess.query(Product).filter(Product.toggle,
                                                                                  Product.manufacturer_id ==
                                                                                  manufacturer_id))
        else:
            products_list = product_name_search(request.args.get("search"),
                                                db_sess.query(Product).filter(Product.toggle,
                                                                              Product.manufacturer_id ==
                                                                              manufacturer_id))
    else:
        if current_user.is_authenticated:
            if current_user.is_admin or current_user.is_moderator:
                products_list = list(db_sess.query(Product).filter(Product.manufacturer_id == manufacturer_id))
            else:
                products_list = list(db_sess.query(Product).filter(Product.toggle,
                                                                   Product.manufacturer_id == manufacturer_id))
        else:
            products_list = list(db_sess.query(Product).filter(Product.toggle,
                                                               Product.manufacturer_id == manufacturer_id))
    products_list.sort(key=lambda x: x.name)
    if request.method == "GET":
        update_user_status(f"Автор (ID - {manufacturer_id})")
        t = load_theme()
        return render_template("manufacturer.html", title=f"{SHOP_NAME} - {manufacturer.name}", hf_flag=True,
                               THEMES=THEMES, current_user=current_user, main_class="px-2", theme=t,
                               YEAR=datetime.datetime.now().year, page_name="manufacturer", COMPANY_NAME=COMPANY_NAME,
                               manufacturer=manufacturer, poster=poster, products_list=products_list)
    elif request.method == "POST":
        if "delete_manufacturer" in request.form:
            if current_user.is_admin or current_user.is_moderator:
                orders_list = db_sess.query(Order)
                products_list = db_sess.query(Product).filter(Product.manufacturer_id == manufacturer_id)
                products_list_id = [x.id for x in products_list]
                for product_id in products_list_id:
                    for order in orders_list:
                        if product_id in bake_dict_from_db(order.products_list, func_for_key=int):
                            flash("Нельзя удалить автора: одна из его книг была заказана когда-либо", "danger")
                            return redirect(f"/manufacturers/{manufacturer_id}")
                logo_path = os.path.join(app.config["UPLOAD_FOLDER"], manufacturer.logo)
                if os.path.isfile(logo_path):
                    os.remove(logo_path)
                for product in products_list:
                    for img in product.images.split(","):
                        img_path = os.path.join(app.config["UPLOAD_FOLDER"], img)
                        if os.path.isfile(img_path):
                            os.remove(img_path)
                    name = product.name
                    product_id = product.id
                    db_sess.delete(product)
                    db_sess.commit()
                    write_log(f"Книга {name} (ID - {product_id}) была удалена")
                name = manufacturer.name
                db_sess.delete(manufacturer)
                db_sess.commit()
                flash(f"Книга {name} (ID - {manufacturer_id}) успешно удалена", "success")
                write_log(f"Книга {name} (ID - {manufacturer_id}) был удалена")
                return redirect("/manufacturers")
            else:
                flash("У вас нет прав", "danger")
        elif "toggle_manufacturer" in request.form:
            if current_user.is_admin or current_user.is_moderator:
                if manufacturer.toggle:
                    manufacturer.toggle = False
                    manufacturer.poster_id = current_user.id
                    products_list = db_sess.query(Product).filter(Product.manufacturer_id == manufacturer_id)
                    for product in products_list:
                        product.toggle = False
                        product.poster_id = current_user.id
                    flash("Автор и все его книги выключены", "success")
                    write_log(f"Автор {manufacturer.id} (ID - {manufacturer_id}) был выключен")
                    db_sess.commit()
                else:
                    manufacturer.toggle = True
                    manufacturer.poster_id = current_user.id
                    products_list = db_sess.query(Product).filter(Product.manufacturer_id == manufacturer_id)
                    for product in products_list:
                        product.toggle = True
                        product.poster_id = current_user.id
                    write_log(f"Автор {manufacturer.id} (ID - {manufacturer_id}) был включен")
                    db_sess.commit()
                    flash("Автор и все его книги включены", "success")
            else:
                flash("У вас нет прав", "danger")
        elif "put_into_cart" in request.form:
            db_sess = db_session.create_session()
            if db_sess.query(Product).filter(Product.id == int(request.form.get("put_into_cart"))).first():
                count = int(request.form.get("count")) if request.form.get("count").isdigit() else 1
                if count:
                    if request.form.get("put_into_cart") in session["cart"]:
                        flash("Кол-во книг в корзине изменено", "success")
                    else:
                        flash("Книга добавлена в корзину", "success")
                    session["cart"][request.form.get("put_into_cart")] = count
                else:
                    if request.form.get("put_into_cart") in session["cart"]:
                        session["cart"].pop(request.form.get("put_into_cart"))
                        write_log(f'Книга с ID {request.form.get("put_into_cart")} убрана из корзины')
                        flash("Книга убрана из корзины", "success")
                    else:
                        flash("Книги не было в корзине", "danger")
        elif "remove_from_cart" in request.form:
            if request.form.get("remove_from_cart") in session["cart"]:
                db_sess = db_session.create_session()
                if db_sess.query(Product).filter(Product.id == int(request.form.get("remove_from_cart"))).first():
                    session["cart"].pop(request.form.get("remove_from_cart"))
                    write_log(f'Книга с ID {request.form.get("remove_from_cart")} убрана из корзины')
                    flash("Книга убрана из корзины", "success")
                else:
                    flash("Книги не существует", "danger")
            else:
                flash("Книги не было в корзине", "danger")
        return redirect(f"/manufacturers/{manufacturer_id}")


@app.route("/update_product/<product_id>", methods=["GET", "POST"])
@login_required
def update_product(product_id):
    update_user_status("Изменение книги")
    db_sess = db_session.create_session()
    user = db_sess.query(User).filter(User.id == current_user.id).first()
    manufacturers_list = list(db_sess.query(Manufacturer))
    if user.is_admin or user.is_moderator:
        base_settings_update_check()
        if not manufacturers_list:
            flash("Сперва нужно создать автора", "danger")
            return redirect("/add_manufacturer")
        product = db_sess.query(Product).filter(Product.id == product_id).first()
        if not product:
            abort(404)
        if request.method == "GET":
            t = load_theme()
            return render_template("update_product.html", title=f"{SHOP_NAME} - изменение книги",
                                   page_name="change_product", current_user=current_user, theme=t,
                                   YEAR=datetime.datetime.now().year, hf_flag=False, accept_images=accept_images,
                                   main_class="form-signin w-100 m-auto px-4 my-5 border-color-theme border "
                                              "border-round", COMPANY_NAME=COMPANY_NAME, THEMES=THEMES,
                                   product=product, manufacturers_list=manufacturers_list)
        elif request.method == "POST":
            if not base_settings_request_check():
                files = request.files.getlist("files[]")
                write_log("Проверка файлов:")
                images = []
                f_count = 0
                for file in files:
                    if allowed_type(file.filename, IMAGES):
                        filename = f"product_{product.id}_{f_count}.{file.filename.rsplit('.', 1)[1].lower()}"
                        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                        file.save(os.path.join(file_path))
                        images.append(filename)
                        write_log(f"Файл {file.filename} сохранён как {filename}")
                    else:
                        write_log(f"Файл {file.filename} не прошёл проверку")
                    f_count += 1
                manufacturer = db_sess.query(Manufacturer).filter(Manufacturer.id ==
                                                                  request.form.get("manufacturer")).first()
                if not manufacturer:
                    write_log(f"Автора с ID {request.form.get('manufacturer')} не существует")
                    flash(f"Автора с ID {request.form.get('manufacturer')} не существует", "danger")
                    session["new_product_name"] = request.form.get("name") if request.form.get("name") and \
                        request.form.get("name") != "None" else product.name
                    session["new_about"] = request.form.get("about") if request.form.get("about") and \
                        request.form.get("about") != "None" else product.about
                    session["new_tags"] = request.form.get("tags") if request.form.get("tags") and \
                        request.form.get("tags") != "None" else product.tags
                    session["new_manufacturer"] = product.manufacturer_id
                    return redirect(f"/update_product/{product_id}")
                product.poster_id = current_user.id
                product.name = request.form.get("name")
                product.about = request.form.get("about")
                product.tags = request.form.get("tags")
                product.manufacturer_id = manufacturer.id
                if images:
                    for old_img in product.images.split(","):
                        print(old_img, images)
                        if old_img not in images:
                            old_file_path = os.path.join(app.config["UPLOAD_FOLDER"], old_img)
                            if os.path.isfile(old_file_path):
                                os.remove(old_file_path)
                    product.images = ",".join(images)
                    img_path = os.path.join(app.config["UPLOAD_FOLDER"], images[0])
                    img_preview_path = os.path.join(app.config["UPLOAD_FOLDER"], f"product_{product_id}_preview.png")
                    product.image_preview = make_image_preview(img_path, img_preview_path)
                    write_log("Картинки сохранены")
                else:
                    write_log("Файлы без изменений")
                db_sess.commit()
                session["new_product_name"] = ""
                session["new_about"] = ""
                session["new_tags"] = ""
                session["new_manufacturer"] = ""
                return redirect(f"/products/{product.id}")
            else:
                session["new_product_name"] = request.form.get("name") if request.form.get("name") and \
                    request.form.get("name") != "None" else product.name
                session["new_about"] = request.form.get("about") if request.form.get("about") and \
                    request.form.get("about") != "None" else product.about
                session["new_tags"] = request.form.get("tags") if request.form.get("tags") and \
                    request.form.get("tags") != "None" else product.tags
                session["new_manufacturer"] = request.form.get("manufacturer") if request.form.get("manufacturer") and \
                    request.form.get("manufacturer") != "None" else product.manufacturer_id
                return redirect(f"/update_product/{product_id}")
    else:
        abort(403)


@app.route("/update_manufacturer/<manufacturer_id>", methods=["GET", "POST"])
@login_required
def update_manufacturer(manufacturer_id):
    base_settings_update_check()
    update_user_status("Изменение автора")
    db_sess = db_session.create_session()
    user = db_sess.query(User).filter(User.id == current_user.id).first()
    if user.is_admin or user.is_moderator:
        base_settings_update_check()
        manufacturer = db_sess.query(Manufacturer).filter(Manufacturer.id == manufacturer_id).first()
        if not manufacturer:
            abort(404)
        if request.method == "GET":
            t = load_theme()
            return render_template("update_manufacturer.html", title=f"{SHOP_NAME} - изменение автора",
                                   THEMES=THEMES, page_name="update_manufacturer", current_user=current_user, theme=t,
                                   hf_flag=False, YEAR=datetime.datetime.now().year, accept_images=accept_images,
                                   main_class="form-signin w-100 m-auto px-4 my-5 border-color-theme border "
                                              "border-round", COMPANY_NAME=COMPANY_NAME, manufacturer=manufacturer)
        elif request.method == "POST":
            if not base_settings_request_check():
                files = request.files.getlist("file")
                file_f = False
                write_log("Проверка файла:")
                for file in files:
                    if allowed_type(file.filename, IMAGES):
                        file_f = True
                manufacturer.poster_id = current_user.id
                manufacturer.name = request.form.get("name")
                manufacturer.about = request.form.get("about")
                if file_f:
                    for file in files:
                        write_log("Начало процесса сохранения логотипа")
                        filename = f"manufacturer_{manufacturer.id}.{file.filename.rsplit('.', 1)[1].lower()}"
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        old_file_path = os.path.join(app.config['UPLOAD_FOLDER'], manufacturer.logo)
                        if os.path.isfile(old_file_path):
                            os.remove(old_file_path)
                        file.save(file_path)
                        write_log(f"Файл {file.filename} сохранён как {filename}")
                        manufacturer.logo = filename
                        manufacturer.logo_preview = make_image_preview(file_path,
                                                                       os.path.join(app.config['UPLOAD_FOLDER'],
                                                                                    f"manufacturer_{manufacturer.id}"
                                                                                    "_preview.png"))
                        write_log("Логотип сохранён")
                db_sess.commit()
                session["new_manufacturer_name"] = ""
                session["new_manufacturer_about"] = ""
                return redirect(f"/manufacturers/{manufacturer.id}")
            else:
                session["new_manufacturer_name"] = request.form.get("name") if request.form.get("name") != "None" and \
                    request.form.get("name") else ""
                session["new_manufacturer_about"] = request.form.get("about") if request.form.get("about") != "None" \
                    and request.form.get("about") else ""
                flash("Не все обязательные поля заполнены", "danger")
                return redirect(f"/update_manufacturer/{manufacturer_id}")
        else:
            return redirect(f"/update_manufacturer/{manufacturer_id}")
    else:
        abort(403)


@app.route("/orders", methods=["GET", "POST"])
@login_required
def orders():
    base_settings_update_check()
    if request.method == "GET":
        update_user_status("Заказы")
        t = load_theme()
        db_sess = db_session.create_session()
        if request.args.get("search"):
            try:
                orders_list = list(db_sess.query(Order).filter(Order.poster_id == current_user.id,
                                                               int(request.args.get("search")) == Order.id))
            except ValueError:
                orders_list = []
            try:
                orders_list_mod = list(db_sess.query(Order).filter(Order.poster_id != current_user.id,
                                                                   Order.status < max(ORDER_STATUS.keys()),
                                                                   int(request.args.get("search")) == Order.id))
            except ValueError:
                orders_list_mod = []
        else:
            orders_list = list(db_sess.query(Order).filter(Order.poster_id == current_user.id))
            orders_list_mod = list(db_sess.query(Order).filter(Order.poster_id != current_user.id,
                                                               Order.status < max(ORDER_STATUS.keys()),))
            write_log(f"Список заказов, показанных пользователю {current_user.name} (ID - {current_user.id}): "
                      f"{orders_list if orders_list else 'пусто'}")
            if current_user.is_admin or current_user.is_moderator:
                write_log("Так как данный пользователь - модератор или админ, то ему ещё были показаны "
                          f"активные заказы: {orders_list_mod if orders_list_mod else 'пусто'}")
        return render_template("orders.html", title=f"{SHOP_NAME} - заказы", hf_flag=True, current_user=current_user,
                               THEMES=THEMES, main_class="px-2", theme=t, YEAR=datetime.datetime.now().year,
                               page_name="orders", COMPANY_NAME=COMPANY_NAME, orders_list=orders_list,
                               ORDER_STATUS=ORDER_STATUS, orders_list_mod=orders_list_mod)
    elif request.method == "POST":
        return redirect("/orders")


@app.route("/orders/<order_id>", methods=["GET", "POST"])
@login_required
def order_info(order_id):
    base_settings_update_check()
    db_sess = db_session.create_session()
    order = db_sess.query(Order).filter(Order.id == order_id).first()
    if order:
        if order.poster_id == current_user.id or current_user.is_admin or current_user.is_moderator:
            if request.method == "GET":
                update_user_status(f"Заказ №{order_id}")
                t = load_theme()
                products_in_order = bake_dict_from_db(order.products_list, func_for_key=int, func_for_item=int)
                products_price = bake_dict_from_db(order.products_price, func_for_key=int, func_for_item=int)
                products_list = set()
                for product_id in products_in_order:
                    product = db_sess.query(Product).filter(Product.id == product_id).first()
                    if product:
                        products_list.add(product)
                return render_template("order.html", title=f"{SHOP_NAME} - заказ №{order_id}", hf_flag=True,
                                       current_user=current_user, THEMES=THEMES, main_class="px-2", theme=t,
                                       YEAR=datetime.datetime.now().year, page_name="order", COMPANY_NAME=COMPANY_NAME,
                                       products_price=products_price, products_in_order=products_in_order,
                                       products_list=products_list, order=order, ORDER_STATUS=ORDER_STATUS)
            elif request.method == "POST":
                if "cancel" in request.form:
                    if current_user.is_authenticated:
                        if current_user.id == order.poster_id or current_user.is_admin or current_user.is_moderator:
                            if order.status == 0:
                                db_sess.delete(order)
                                db_sess.commit()
                                flash(f"Заказ №{order_id} отменён", "success")
                                return redirect("/orders")
                            else:
                                flash(f"Заказ №{order_id} отменить уже нельзя", "danger")
                        else:
                            flash("У вас нет прав", "danger")
                    else:
                        flash("У вас нет прав", "danger")
                elif "next_step" in request.form:
                    if current_user.is_authenticated:
                        if current_user.is_admin or current_user.is_moderator:
                            if order.status + 1 in ORDER_STATUS:
                                if request.form.get("next_step").isdigit():
                                    if int(request.form["next_step"]) == order.status:
                                        order.status += 1
                                        db_sess.commit()
                                    elif int(request.form["next_step"]) > max(ORDER_STATUS.keys()):
                                        flash("Администратору: некорректный value внутри кнопки "
                                              f"({request.form.get('next_step')})", "danger")
                                        write_log("(!) Некорректный value внутри кнопки "
                                                  f"({request.form.get('next_step')})")
                                    else:
                                        flash("Кто-то уже менял статус до вас", "danger")
                                else:
                                    flash("Администратору: некорректный value внутри кнопки "
                                          f"({request.form.get('next_step')})", "danger")
                                    write_log("(!) Некорректный value внутри кнопки "
                                              f"({request.form.get('next_step')})")
                            else:
                                flash("Менять статус нельзя: достигнута последняя стадия заказа", "danger")
                        else:
                            flash("У вас нет прав", "danger")
                    else:
                        flash("У вас нет прав", "danger")
                return redirect(f"/orders/{order_id}")
        else:
            abort(403)
    else:
        abort(404)


@app.route("/cart", methods=["GET", "POST"])
def cart():
    base_settings_update_check()
    products_list = set()
    if session.get("cart"):
        db_sess = db_session.create_session()
        for product_id in session["cart"]:
            product = db_sess.query(Product).filter(Product.id == int(product_id)).first()
            products_list.add(product)
    if request.method == "GET":
        update_user_status("Корзина")
        t = load_theme()
        return render_template("cart.html", title=f"{SHOP_NAME} - корзина", hf_flag=True, current_user=current_user,
                               main_class="px-2", theme=t, YEAR=datetime.datetime.now().year, page_name="cart",
                               COMPANY_NAME=COMPANY_NAME, THEMES=THEMES, products_list=products_list, cost=cost)
    elif request.method == "POST":
        if "clear_cart" in request.form:
            clear_cart()
        elif "change_count" in request.form:
            db_sess = db_session.create_session()
            if db_sess.query(Product).filter(Product.id == int(request.form.get("change_count"))).first():
                count = int(request.form.get("count")) if request.form.get("count").isdigit() else 1
                if count:
                    if request.form.get("change_count") in session["cart"]:
                        flash("Кол-во книг корзине изменено", "success")
                    else:
                        flash("Книга добавлена в корзину", "success")
                    session["cart"][request.form.get("change_count")] = count
                else:
                    if request.form.get("change_count") in session["cart"]:
                        session["cart"].pop(request.form.get("change_count"))
                        write_log(f'Книга с ID {request.form.get("change_count")} убрана из корзины')
                        flash("Книга убрана из корзины", "success")
                    else:
                        flash("Книги не было в корзине", "danger")
        elif "remove_from_cart" in request.form:
            if request.form.get("remove_from_cart") in session["cart"]:
                db_sess = db_session.create_session()
                if db_sess.query(Product).filter(Product.id == int(request.form.get("remove_from_cart"))).first():
                    session["cart"].pop(request.form.get("remove_from_cart"))
                    write_log(f'Книга с ID {request.form.get("remove_from_cart")} убрана из корзины')
                    flash("Книга убрана из корзины", "success")
                else:
                    flash("Книги не существует", "danger")
            else:
                flash("Книги не было в корзине", "danger")
        elif "make_order" in request.form:
            if not session.get("cart"):
                flash("Корзина пуста", "danger")
            elif current_user.is_authenticated:
                if request.form.get("name") and request.form.get("address"):
                    if session.get("cart_changed"):
                        flash("Бронирование было предотвращено из-за изменений в книгах")
                        session["cart_changed"] = False
                        return redirect("/cart")
                    db_sess = db_session.create_session()
                    order = Order()
                    order.poster_id = current_user.id
                    order.poster_name = name_correct(request.form.get("name"))
                    order.address = request.form.get("address")
                    order.commentary = request.form.get("commentary")
                    order.products_list = bake_dict_for_db(session.get("cart"))
                    books = []
                    for product in products_list:
                        for c in range(session.get("cart")[str(product.id)]):
                            book = db_sess.query(Book).filter(product.id == Book.product_id, Book.owner == None,
                                                              Book.toggle).first()
                            book.status = 1
                            book.owner = current_user.id
                            books.append(str(book.id))
                    order.books = ";".join(books)
                    db_sess.add(order)
                    db_sess.commit()
                    session["cart"].clear()
                    session["commentary"] = ""
                    return redirect(f"/orders/{order.id}")
                else:
                    session["commentary"] = request.form.get("commentary") if \
                        request.form.get("commentary") != "None" and request.form.get("commentary") else ""
                    flash("Не все обязательные поля заполнены", "danger")
            else:
                abort(401)
        return redirect("/cart")


@app.errorhandler(401)
def e401(code):
    if request.method == "GET":
        update_user_status("401")
        write_log(code)
        flash(LOGIN_MESSAGE, "warning")
        return redirect("/login")


@app.errorhandler(403)
def e403(code):
    if request.method == "GET":
        update_user_status("403")
        write_log(code)
        flash("У вас нет прав на посещение этой страницы", "danger")
        return redirect("/")


@app.errorhandler(404)
def e404(code):
    if request.method == "GET":
        update_user_status("404")
        write_log(code)
        t = load_theme()
        return render_template("error.html", title=f"{SHOP_NAME} - 404", hf_flag=False, current_user=current_user,
                               main_class="form-signin w-100 m-auto px-4 my-5 border-color-theme border border-round",
                               theme=t, YEAR=datetime.datetime.now().year, page_name="404", THEMES=THEMES,
                               code="Этой страницы не существует.", COMPANY_NAME=COMPANY_NAME), 404


@app.errorhandler(413)
def e413(code):
    if request.method == "GET":
        update_user_status("413")
        write_log(code)
        t = load_theme()
        return render_template("error.html", title=f"{SHOP_NAME} - 413", hf_flag=False, current_user=current_user,
                               main_class="form-signin w-100 m-auto px-4 my-5 border-color-theme border border-round",
                               theme=t, YEAR=datetime.datetime.now().year, page_name="413", THEMES=THEMES,
                               code="Были отправлены слишком большие файлы", COMPANY_NAME=COMPANY_NAME), 413


@app.errorhandler(500)
def e500(code):
    if request.method == "GET":
        update_user_status("500")
        write_log(code)
        t = load_theme()
        return render_template("error.html", title=f"{SHOP_NAME} - 500", hf_flag=False, current_user=current_user,
                               main_class="form-signin w-100 m-auto px-4 my-5 border-color-theme border border-round",
                               theme=t, YEAR=datetime.datetime.now().year, page_name="500", THEMES=THEMES,
                               code="Произошла ошибка на сервере.", COMPANY_NAME=COMPANY_NAME), 500


if __name__ == "__main__":
    write_log("Запуск от " + str(datetime.datetime.now()))

    try:
        db_session.global_init("db/shop.db")
        init_admin()
    except ImportError as e:
        write_log(f"Произошла проблема с импортом класса, вероятно, в скрипте __all_models.py: ({e})", console=False)
        exit(f"Произошла проблема с импортом класса, вероятно, в скрипте __all_models.py: ({e})")
    except Exception as e:
        write_log(f"Произошла непредвиденная ошибка во время инициализации БД: ({e})", console=False)
        exit(f"Произошла непредвиденная ошибка во время инициализации БД: ({e})")
    else:
        write_log("Запуск БД прошёл успешно")

    write_log("Проверка тем...")
    if THEMES:
        for theme in THEMES[:]:
            if os.path.exists(f"static/css/{theme[0]}.css"):
                write_log(f"{theme[0]} ({theme[1]}) - OK!")
            else:
                THEMES.remove(theme[0])
                write_log(f"{theme[0]} ({theme[1]}) - не найден файл css")
    if not THEMES:
        write_log("Ошибка: нет тем")
        raise ThemeError("Нет тем")
    else:
        write_log("Темы - OK!")
    if DEFAULT_THEME not in [x[0] for x in THEMES]:
        DEFAULT_THEME = THEMES[0][0]
        write_log(f"Тема, заданная по умолчанию, отсутствует, она заменена на тему {DEFAULT_THEME} ({THEMES[0][1]})")
    write_log("\n")

    app.run(HOST, port=PORT, debug=DEBUG)

    write_log(f"Завершение работы ({str(datetime.datetime.now())})...")
