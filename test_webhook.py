import requests

url = "http://127.0.0.1:5000/webhook"
data = {
  "events": [
    {
      "type": "message",
      "message": {"type": "text", "text": "@billybot pay 100 ขนม"},
      "source": {"userId": "U123", "userName": "TestUser"}
    }
  ]
}

r = requests.post(url, json=data)

# debug ก่อนแปลง JSON
print("Status code:", r.status_code)
print("Response text:", r.text)

# ถ้า response เป็น JSON ถึงค่อยแปลง
try:
    print("Response JSON:", r.json())
except Exception as e:
    print("ไม่สามารถ decode JSON:", e)
