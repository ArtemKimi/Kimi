import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

CHANNEL = "kryvbasvodokanal"
# біркун — ловит Біркуна / Біркуну / Біркуні, а также русские и смешанные написания
PATTERN = re.compile(r"б[іiи]ркун", re.IGNORECASE)
STATE_FILE = "state.json"
TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]


def fetch_page():
    """Загружает страницу канала, до 3 попыток. None, если t.me не отвечает."""
    req = urllib.request.Request(
        f"https://t.me/s/{CHANNEL}", headers={"User-Agent": "Mozilla/5.0"}
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8")
        except Exception as e:
            print(f"Попытка {attempt + 1}: не удалось загрузить страницу: {e}")
            time.sleep(5)
    return None


def clean(raw):
    raw = re.sub(r"<br\s*/?>", "\n", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    return html.unescape(raw).strip()


def parse(page):
    """Возвращает {id_поста: текст}."""
    marks = list(re.finditer(rf'data-post="{CHANNEL}/(\d+)"', page))
    posts = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(page)
        seg = page[m.end():end]
        t = re.search(
            r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
            seg,
            re.S,
        )
        if t:
            posts[m.group(1)] = clean(t.group(1))
    return posts


def send(text):
    data = urllib.parse.urlencode(
        {
            "chat_id": CHAT_ID,
            "text": text[:4000],
            "disable_web_page_preview": "true",
        }
    ).encode()
    urllib.request.urlopen(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage", data, timeout=30
    ).read()


def main():
    first_run = not os.path.exists(STATE_FILE)
    seen = {}
    if not first_run:
        with open(STATE_FILE, encoding="utf-8") as f:
            seen = json.load(f)

    page = fetch_page()
    if page is None:
        # временный сбой сети: выходим без ошибки, следующая проверка через 10 минут
        print("t.me недоступен, пропускаем этот запуск")
        return

    posts = parse(page)
    if not posts:
        sys.exit("Не удалось разобрать страницу канала")

    for pid, text in posts.items():
        h = hashlib.md5(text.encode()).hexdigest()
        if not first_run and PATTERN.search(text) and seen.get(pid) != h:
            send(f"💧 Водоканал: згадано вашу вулицю\n\n{text[:3500]}\n\n"
                 f"https://t.me/{CHANNEL}/{pid}")
        seen[pid] = h

    if first_run:
        send("✅ Мониторинг запущен. Сообщу, когда в канале "
             "водоканала появится ваша улица.")

    # хранить только последние 300 постов
    keep = sorted(seen, key=int)[-300:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({k: seen[k] for k in keep}, f)


if __name__ == "__main__":
    main()
