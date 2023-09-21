import os
import shutil


def check_log():
    if not os.path.isfile(f"{directory}/shop_log.txt"):
        print("Лог создан\n", file=open(f"{directory}/shop_log.txt", "w", encoding="utf-8"))


def write_log(message: str, console=True):
    if console:
        print(message)
    print(message, file=open(f"{directory}/shop_log.txt", "a", encoding="utf-8"))


def archive_log():
    logs = [x for x in os.listdir(directory) if "shop_log" in x]
    shutil.copyfile(f"{directory}/shop_log.txt", f"{directory}/shop_log_old{len(logs)}.txt")
    print("Очистка лога успешно завершена", file=open(f"{directory}/shop_log.txt", "w", encoding="utf-8"))


if __name__ == "__main__":
    directory = "logs"
    check_log()
    archive_log()
else:
    directory = "data/logs"
    check_log()
