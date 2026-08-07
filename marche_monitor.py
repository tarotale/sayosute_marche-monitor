import json
import os
import re
import time
from datetime import datetime, timedelta
import requests

# --- 設定 ---
LINE_TOKEN = os.getenv('LINE_ACCESS_TOKEN')
DB_FILE = "syst_last_inventory.json"

TARGET_CREATORS = [
    {"name": "城谷美温", "id": "syst_shirotanim", "emoji": "💙", "nickname": "みおりん"},
    {"name": "愛宮歌梨", "id": "syst_aimiya", "emoji": "❤️", "nickname": "かーりん"},
    {"name": "桃ノ井理子", "id": "syst_momonoi", "emoji": "💚", "nickname": "りっこー"},
    {"name": "萌波あかり", "id": "syst_monamiakar", "emoji": "🩷", "nickname": "あかにゃ"},
    {"name": "日永陽咲", "id": "syst_hinagaharu", "emoji": "💜", "nickname": "はるき"},
    {"name": "根岸かのん", "id": "syst_negishikan", "emoji": "💛", "nickname": "かにょ"},
]

def convert_to_jst_full(utc_str):
    if not utc_str: return "0000-00-00 00:00"
    try:
        dt_utc = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
        dt_jst = dt_utc + timedelta(hours=9)
        return dt_jst.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "0000-00-00 00:00"

def send_line(message):
    if not LINE_TOKEN:
        print("Error: LINE_ACCESS_TOKEN is not set.")
        return
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_TOKEN}"}
    payload = {"messages": [{"type": "text", "text": message}]}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        res.raise_for_status()
        print("LINE送信成功")
    except Exception as e:
        print(f"LINE送信エラー: {e}")

def main():
    # DBファイルが存在しない場合（＝初回実行時）のフラグ
    is_first_run = not os.path.exists(DB_FILE)
    
    last_data = {}
    if not is_first_run:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try: 
                last_data = json.load(f)
            except Exception as e:
                print(f"DB読み込みエラー: {e}")
                last_data = {}

    current_all_data = last_data.copy()
    update_list = []  # 新着・復活した商品を溜めるリスト

    for creator in TARGET_CREATORS:
        c_name, c_id, c_emoji = creator["name"], creator["id"], creator["emoji"]
        offset = 0
        while True:
            list_api = f"https://api.marche-yell.com/api/public/products?creator_marche_id={c_id}&limit=100&offset={offset}"
            headers = {"User-Agent": "Mozilla/5.0"}
            try:
                res = requests.get(list_api, headers=headers, timeout=15)
                products = res.json().get('products', [])
                if not products: 
                    break
                
                for p in products:
                    p_id = str(p.get('id'))
                    title = p.get('title', '不明')
                    start_jst = convert_to_jst_full(p.get('sales_start_at'))
                    limit = p.get('limit_quantity', 0)
                    stock = limit - p.get('sold_quantity', 0)
                    db_key = f"{c_id}_{p_id}"
                    
                    # 検知ロジック
                    status_prefix = ""
                    if db_key not in last_data:
                        status_prefix = "🍭【新着】"
                    elif stock > 0 and last_data[db_key].get('stock', 0) == 0:
                        status_prefix = "🔄【復活】"
                    
                    if status_prefix:
                        update_list.append({
                            "msg": f"{status_prefix}{c_emoji}{c_name}\n📝 {title}\n📅 開始: {start_jst}\n📦 在庫: {stock}/{limit}\n🔗 https://marche-yell.com/{c_id}/products/{p_id}",
                            "start": start_jst # ソート用
                        })

                    current_all_data[db_key] = {
                        "name": c_name, 
                        "title": title, 
                        "stock": stock, 
                        "limit": limit, 
                        "start": start_jst, 
                        "creator_id": c_id
                    }
                
                if len(products) < 100: 
                    break
                offset += 100
                time.sleep(1)
            except Exception as e:
                print(f"Error ({c_name}): {e}")
                break

    # --- 送信ロジック ---
    if update_list:
        if is_first_run:
            print("初回実行のため、現在の状態をキャッシュとして保存します（通知はスキップ）。")
        else:
            # 販売開始日(start)で降順ソート（新しい順）
            update_list.sort(key=lambda x: x['start'], reverse=True)
            
            # 最新10件を抽出して結合
            top_10 = update_list[:10]
            final_msg = "🌟 ChumToto マルシェ更新情報 🌟\n\n" + "\n\n---\n\n".join([item['msg'] for item in top_10])
            
            send_line(final_msg)
    else:
        print("新規・復活商品は検出されませんでした。")

    # DBの更新
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(current_all_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
