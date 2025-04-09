from flask import Flask, request
import requests, hmac, hashlib, time, os
import logging, sys

app = Flask(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        print("\n===== Webhook受信 - 爆発検知Bot =====")
        print("受信データ:", data)

        symbol = data.get("symbol", "BTC-USDT")
        side = data.get("side", "BUY").upper()
        quantity = float(data.get("amount", 0.01))
        tp1 = float(data.get("tp1", 0.0088))
        tp2 = float(data.get("tp2", 0.018))
        sl = float(data.get("sl", 0.0033))
        bot_name = "爆発検知Bot"

        price_res = requests.get(f"https://open-api.bingx.com/openApi/spot/v1/ticker/price?symbol={symbol}")
        price = float(price_res.json().get("price", 0))
        if price == 0:
            print("🚨 価格取得失敗")
            return {"status": "price_error"}

        print(f"現在価格: {price}")

        if side == "BUY":
            tp1_price = round(price * (1 + tp1), 4)
            tp2_price = round(price * (1 + tp2), 4)
            sl_price = round(price * (1 - sl), 4)
        else:
            tp1_price = round(price * (1 - tp1), 4)
            tp2_price = round(price * (1 - tp2), 4)
            sl_price = round(price * (1 + sl), 4)

        print(f"TP1: {tp1_price}, TP2: {tp2_price}, SL: {sl_price}")

        # エントリー注文
        timestamp = str(int(time.time() * 1000))
        order_params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": str(quantity),
            "timestamp": timestamp
        }
        sorted_items = sorted(order_params.items())
        query_string = '&'.join([f"{k}={v}" for k, v in sorted_items])
        signature = hmac.new(API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()
        order_query = query_string + f"&signature={signature}"

        headers = {
            "X-BX-APIKEY": API_KEY,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        url = "https://open-api.bingx.com/openApi/spot/v1/trade/order"
        print(f"[{bot_name}] 本体注文送信中...")
        order_res = requests.post(url, headers=headers, data=order_query)
        print("注文レスポンス:", order_res.text)

        time.sleep(1.5)

        tp_side = "SELL" if side == "BUY" else "BUY"

        # TP1
        tp1_params = {
            "symbol": symbol,
            "side": tp_side,
            "type": "LIMIT",
            "price": str(tp1_price),
            "quantity": str(quantity / 2),
            "timestamp": str(int(time.time() * 1000))
        }
        tp1_query = '&'.join([f"{k}={v}" for k, v in sorted(tp1_params.items())])
        tp1_sig = hmac.new(API_SECRET.encode(), tp1_query.encode(), hashlib.sha256).hexdigest()
        tp1_final = tp1_query + f"&signature={tp1_sig}"
        tp1_res = requests.post(url, headers=headers, data=tp1_final)
        print("TP1注文レスポンス:", tp1_res.text)

        # TP2
        tp2_params = {
            "symbol": symbol,
            "side": tp_side,
            "type": "LIMIT",
            "price": str(tp2_price),
            "quantity": str(quantity / 2),
            "timestamp": str(int(time.time() * 1000))
        }
        tp2_query = '&'.join([f"{k}={v}" for k, v in sorted(tp2_params.items())])
        tp2_sig = hmac.new(API_SECRET.encode(), tp2_query.encode(), hashlib.sha256).hexdigest()
        tp2_final = tp2_query + f"&signature={tp2_sig}"
        tp2_res = requests.post(url, headers=headers, data=tp2_final)
        print("TP2注文レスポンス:", tp2_res.text)

        # SL
        sl_params = {
            "symbol": symbol,
            "side": tp_side,
            "type": "STOP_MARKET",
            "stopPrice": str(sl_price),
            "quantity": str(quantity),
            "timestamp": str(int(time.time() * 1000))
        }
        sl_query = '&'.join([f"{k}={v}" for k, v in sorted(sl_params.items())])
        sl_sig = hmac.new(API_SECRET.encode(), sl_query.encode(), hashlib.sha256).hexdigest()
        sl_final = sl_query + f"&signature={sl_sig}"
        sl_res = requests.post(url, headers=headers, data=sl_final)
        print("SL注文レスポンス:", sl_res.text)

    except Exception as e:
        print("\n🚨 エラー発生:", str(e))

    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
