import os
import base64
import json
import requests
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from bs4 import BeautifulSoup

INFO_URL = "https://cs-plaza.co.jp/naniwa-sc/information/3106"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def download_image():
    response = requests.get(INFO_URL)
    soup = BeautifulSoup(response.content, "html.parser")
    target_article = soup.find("article", class_="entry-body")
    if not target_article:
        print("❌ 記事が見つかりませんでした")
        return None

    img_tags = target_article.find_all("img")
    if len(img_tags) < 2:
        print("❗ 画像が1枚しか見つかりません。1枚目を使用します。")
        img_tag = img_tags[0] if img_tags else None
    else:
        img_tag = img_tags[1]  # 2枚目を優先

    if not img_tag or not img_tag.get("src"):
        print("❌ 画像が見つかりませんでした")
        return None

    img_url = requests.compat.urljoin(INFO_URL, img_tag.get("src"))
    img_data = requests.get(img_url).content
    with open("calendar_image.png", "wb") as f:
        f.write(img_data)

    return "calendar_image.png"

def extract_events_with_gemini(image_path):
    with open(image_path, "rb") as img_file:
        image_data = base64.b64encode(img_file.read()).decode("utf-8")

    prompt = (
        "画像から、月・日・営業時間帯（例：10:00～19:00）を抽出して。"
        "結果は以下のようにJSON形式で返して："
        "[{\"date\": \"2025-04-10\", \"start\": \"10:00\", \"end\": \"19:00\"}, ...]"
    )

    body = {
        "contents": [
            {"role": "user", "parts": [
                {"text": prompt},
                {"inlineData": {
                    "mimeType": "image/png",
                    "data": image_data
                }}
            ]}
        ]
    }

    headers = {"Content-Type": "application/json"}
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

    res = requests.post(url, headers=headers, json=body)
    res.raise_for_status()

    text = res.json()["candidates"][0]["content"]["parts"][0]["text"]

    try:
        start_idx = text.find("[")
        end_idx = text.rfind("]") + 1
        events_json = text[start_idx:end_idx]
        return json.loads(events_json)
    except Exception as e:
        print("❌ JSONパースに失敗:", e)
        print("レスポンス:", text)
        return []

def register_to_google_calendar(events):
    credentials = service_account.Credentials.from_service_account_file(
        "credentials.json",
        scopes=["https://www.googleapis.com/auth/calendar"]
    )

    service = build("calendar", "v3", credentials=credentials)
    calendar_id = "rikushiomi.kfsc@gmail.com"

    for event in events:
        event_summary = f"{event['start']}～{event['end']}"
        event_date = event['date']

        # 重複チェック（当日のイベントを取得）
        existing_events = service.events().list(
            calendarId=calendar_id,
            timeMin=event_date + "T00:00:00+09:00",
            timeMax=event_date + "T23:59:59+09:00",
            singleEvents=True
        ).execute().get("items", [])

        if any(ev.get('summary') == event_summary for ev in existing_events):
            print(f"⚠️ イベント（{event_summary}）はすでに存在します。スキップ。")
            continue

        event_body = {
            'summary': event_summary,
            'start': {'date': event_date, 'timeZone': 'Asia/Tokyo'},
            'end': {'date': get_next_day(event_date), 'timeZone': 'Asia/Tokyo'}
        }

        service.events().insert(calendarId=calendar_id, body=event_body).execute()
        print(f"✅ イベント登録：{event_date} {event_summary}")

    print("✅ Googleカレンダーへの登録処理が完了しました")

def get_next_day(date_str):
    date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    next_day = date_obj + datetime.timedelta(days=1)
    return next_day.isoformat()

def main():
    image_path = download_image()
    if not image_path:
        return

    events = extract_events_with_gemini(image_path)
    if not events:
        print("❌ イベント情報が抽出できませんでした")
        return

    register_to_google_calendar(events)

if __name__ == "__main__":
    main()

