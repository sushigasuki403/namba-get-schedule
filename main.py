import os
import re
import io
import datetime
import requests
from bs4 import BeautifulSoup
from PIL import Image
import easyocr

from google.oauth2 import service_account
from googleapiclient.discovery import build

# -----------------------------
# STEP 1: 画像URLを取得して保存
# -----------------------------
INFO_URL = "https://cs-plaza.co.jp/naniwa-sc/information/3106"

def download_images_from_target_article():
    # ページ取得
    response = requests.get(INFO_URL)
    soup = BeautifulSoup(response.content, "html.parser")

    # 特定の`<article>`タグを取得
    target_article = soup.find("article", class_="entry-body")  # 最初の`entry-body`だけ取得
    if not target_article:
        print("❌ 指定された記事が見つかりません。")
        return []

    # 画像を収集
    downloaded_images = []
    for img in target_article.find_all("img"):  # `article`内のすべての画像
        src = img.get("src")
        if src:  # `src`属性が存在する場合のみ処理
            img_url = requests.compat.urljoin(INFO_URL, src)  # 相対パスを絶対URLに変換
            img_data = requests.get(img_url).content
            filename = src.split("/")[-1]  # ファイル名を抽出
            with open(filename, "wb") as f:
                f.write(img_data)
            downloaded_images.append(filename)
            print(f"✅ ダウンロード完了: {img_url}")

    if not downloaded_images:
        print("❌ 画像が見つかりませんでした。")
    return downloaded_images


# -----------------------------
# STEP 2: OCRで画像から予定を抽出
# -----------------------------
def extract_events_from_image(image_path):
    reader = easyocr.Reader(['ja'], gpu=False)
    result = reader.readtext(image_path, detail=0)

    for line in result:
        print(f"OCR → {line}")

    events = []
    current_year = datetime.datetime.now().year
    current_month = None

    # 月をOCR結果から取得（例: "4月"）
    for line in result:
        m = re.search(r'(\d{1,2})月', line)
        if m:
            current_month = int(m.group(1))
            break
    if not current_month:
        print("❌ 月情報が見つかりませんでした。デフォルトで4月に設定します。")
        current_month = 4

    # 日付・時間を抽出
    for line in result:
        # 正規表現を柔軟に対応させる
        m = re.match(r"(\d{1,2})[日]?\s*一般営業.*?(\d{1,2})[:：](\d{2})[～~−\-ー](\d{1,2})[:：](\d{2})", line)
        if m:
            day = int(m.group(1))
            start_time = f"{int(m.group(2)):02}:{m.group(3)}"
            end_time = f"{int(m.group(4)):02}:{m.group(5)}"
            date = datetime.datetime(current_year, current_month, day)

            events.append({
                'summary': f'なんばスケートリンク 一般営業',
                'start': date.strftime(f'%Y-%m-%dT{start_time}:00'),
                'end': date.strftime(f'%Y-%m-%dT{end_time}:00'),
            })

    print(f"✅ 抽出されたイベント数: {len(events)}")
    return events


# -----------------------------
# STEP 3: Googleカレンダーへ登録
# -----------------------------
def register_to_google_calendar(events):
    credentials = service_account.Credentials.from_service_account_file(
        "credentials.json",
        scopes=["https://www.googleapis.com/auth/calendar"]
    )

    service = build("calendar", "v3", credentials=credentials)
    calendar_id = "rikushiomi.kfsc@gmail.com"  # or your specific calendar ID

    for event in events:
        # 修正：時間を`summary`に含める
        event_body = {
            'summary': f"{event['summary']} ({event['start'][-8:]}～{event['end'][-8:]})",  # 時間をsummaryに追加
            # 開始・終了時間を登録しない
            'start': {'date': event['start'][:10], 'timeZone': 'Asia/Tokyo'},  # 日付のみ
            'end': {'date': event['end'][:10], 'timeZone': 'Asia/Tokyo'}      # 日付のみ
        }
        service.events().insert(calendarId=calendar_id, body=event_body).execute()

    print("✅ Googleカレンダーへの登録完了")


# -----------------------------
# Main 実行
# -----------------------------
def main():
    image_paths = download_images_from_target_article()
    print(f"📎 image_path[0] = {image_paths[0]}")
    print(f"📎 type = {type(image_paths[0])}")

    if not image_paths:
        print("❌ 画像が見つからなかったため、処理を終了します。")
        return
# 最初の画像を使用する場合
    events = extract_events_from_image(image_paths[0])
    register_to_google_calendar(events)


if __name__ == "__main__":
    main()
