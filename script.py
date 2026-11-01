import html
import os
import urllib.parse
import urllib.request
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TARGET_DATE = "20261225"
TARGET_DATE_LABEL = "Friday, 25 December 2026"
VOX_URL = (
    "https://egy.voxcinemas.com/showtimes"
    "?c=city-centre-almaza&d=" + TARGET_DATE
)
SENT_FILE = Path("sent.txt")


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode("utf-8")

    request = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(request, timeout=20) as response:
        result = response.read().decode("utf-8")
    if '"ok":true' not in result.replace(" ", ""):
        raise RuntimeError(f"Telegram did not confirm message delivery: {result}")
    print("Telegram alert sent successfully.")


def make_browser():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)


def load_sent_ids():
    if not SENT_FILE.exists():
        return set()
    return {
        line.strip()
        for line in SENT_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def save_sent_id(show_id):
    with SENT_FILE.open("a", encoding="utf-8") as file:
        file.write(show_id + "\n")


def find_target_max_showtimes(driver):
    driver.get(VOX_URL)
    WebDriverWait(driver, 30).until(
        lambda browser: browser.execute_script("return document.readyState") == "complete"
    )
    print("VOX page title:", driver.title)
    print("VOX final URL:", driver.current_url)
    print("VOX page text preview:", driver.find_element(By.TAG_NAME, "body").text[:5000])
    print("VOX HTML preview:", driver.page_source[:12000])

    articles = driver.find_elements(By.CSS_SELECTOR, "article.movie-compare")
    print(f"Loaded VOX showtimes page. Found {len(articles)} movie entries.")

    matching_articles = []
    for article in articles:
        headings = article.find_elements(By.TAG_NAME, "h2")
        title = headings[0].text.strip() if headings else ""
        normalized = " ".join(title.casefold().split())

        if (
            "avengers" in normalized
            and "doomsday" in normalized
            and "infinity vision" in normalized
        ):
            matching_articles.append((article, title))

    if not matching_articles:
        print(
            "Target movie is not listed for this date yet, or VOX changed "
            "its page layout. No alert will be sent."
        )
        driver.save_screenshot("vox_debug.png")
        Path("vox_debug.html").write_text(
            driver.page_source, encoding="utf-8"
        )
        return []

    found = []
    for article, title in matching_articles:
        hall_groups = article.find_elements(
            By.CSS_SELECTOR, "div.dates ol.showtimes > li"
        )

        for hall in hall_groups:
            hall_names = hall.find_elements(By.TAG_NAME, "strong")
            hall_name = hall_names[0].text.strip() if hall_names else ""

            if hall_name.casefold() != "max":
                continue

            for item in hall.find_elements(By.CSS_SELECTOR, "ol > li"):
                links = item.find_elements(By.CSS_SELECTOR, "a.showtime")
                if not links:
                    continue

                link = links[0]
                show_time = link.text.strip()
                booking_id = item.get_attribute("data-id") or ""
                booking_url = link.get_attribute("href") or ""

                unique_id = booking_id or booking_url
                if unique_id and show_time:
                    found.append({
                        "id": unique_id,
                        "title": title,
                        "time": show_time,
                        "url": booking_url,
                    })

    return found


def main():
    SENT_FILE.touch(exist_ok=True)
    sent_ids = load_sent_ids()
    driver = make_browser()

    try:
        showtimes = find_target_max_showtimes(driver)
    finally:
        driver.quit()

    if not showtimes:
        print(
            f"No {TARGET_DATE_LABEL} MAX showtimes found at "
            "VOX City Centre Almaza."
        )
        return

    new_count = 0
    for show in showtimes:
        if show["id"] in sent_ids:
            print(f"Already notified: {show['time']}")
            continue

        safe_title = html.escape(show["title"])
        safe_time = html.escape(show["time"])
        message = (
            "🎬 <b>VOX MAX showtime found!</b>\n\n"
            f"📍 City Centre Almaza\n"
            f"🎥 {safe_title}\n"
            f"📅 {TARGET_DATE_LABEL}\n"
            f"🍿 MAX — {safe_time}\n\n"
            "Open VOX to choose your seats and book manually."
        )
        if show["url"]:
            message += f"\n<a href=\"{html.escape(show['url'], quote=True)}\">Book on VOX</a>"

        send_telegram(message)
        save_sent_id(show["id"])
        sent_ids.add(show["id"])
        new_count += 1

    print(
        f"Finished. {len(showtimes)} MAX showtime(s) found; "
        f"{new_count} new alert(s) sent."
    )


if __name__ == "__main__":
    main()
