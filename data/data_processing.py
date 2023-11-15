import datetime

from __shop_config import IMAGES, VIDEOS, AUDIOS, FILE_TYPES

from PIL import Image


def phone_correct(phone: str) -> str:
    return "".join([x for x in phone[:2].replace("+7", "8") + phone[2:] if x.isdigit()]).strip()


def phone_check(phone: str) -> bool:
    phone = phone_correct(phone)
    if len(phone) == 11 and phone[0] == "8":
        return True
    return False


def name_correct(name: str) -> str:
    return "".join([x for x in name if x.lower().isalpha() or x in "- "]).strip()


def product_name_search(name: str, products) -> list:
    res = []
    for n in name.split():
        res += [x for x in products if n.lower() in x.name.lower() or
                [True for y in x.tags.split() if n.lower() in y.lower()]]
    res = list(set(res))
    return res


def user_search(name: str, users) -> list:
    res = []
    for n in name.split():
        res += [x for x in users if n.lower() in x.name.lower() or n.lower() == str(x.id)]
    return list(set(res))


def make_mime(mime: str) -> str:
    # Для тэга <input> в HTML
    if mime in IMAGES:
        return "image/" + mime
    elif mime in VIDEOS:
        return "video/" + mime
    elif mime in AUDIOS:
        return "audio/" + mime


def make_accept_for_html(types: set or list) -> str:
    return ",".join([make_mime(x) for x in types])


def allowed_type(filename: str, types: set or list) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in types


def bake_dict_for_db(d: dict) -> str:
    return ";".join([str(x) + ":" + str(d[x]) for x in d])


def bake_dict_from_db(d: str, func_for_key=str, func_for_item=str) -> dict:
    res = {}
    for i in d.split(";"):
        j = i.split(":")
        res[func_for_key(j[0])] = func_for_item(j[1])
    return res


def make_image_preview(img_orig_name: str, img_new_name: str) -> bool or str:
    try:
        orig = Image.open(img_orig_name)
    except FileNotFoundError:
        return None
    else:
        orig.thumbnail((200, 200))
        orig.save(img_new_name)
        return img_new_name.split("\\")[-1]


def rec_sort(tags, rec):
    for tag in tags.split():
        if tag in rec:
            return True
    return False


def prettify_datetime(t: datetime.datetime):
    t = str(t).split()
    date = ".".join(t[0].split("-")[::-1])
    time = t[1].split(":")
    time[-1] = time[-1][:2]
    time = ":".join(time)
    return {"date": date, "time": time}

if __name__ == "__main__":
    s = input("Введите строку: ")
    print(f"[phone_correct] {phone_correct(s)}")
    print(f"[phone_check] {phone_check(s)}")
    print(f"[name_correct] {name_correct(s)}")
    print(f"[make_mime] {make_mime(s)}")
    print(f"[make_accept_for_html] {make_accept_for_html(FILE_TYPES)}")
    print(f"[allowed_type] {allowed_type(s, FILE_TYPES)}")
    print(f"[bake_dict_from_db] {bake_dict_from_db(s)}")
