import requests
import time

URL = "http://localhost:8000/socket.io/"

def test_connection():
    print(f"Testing connection to {URL}...")
    params = {
        "EIO": "4",
        "transport": "polling",
        "t": str(time.time())
    }
    try:
        response = requests.get(URL, params=params)
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text[:100]}...")
        print(f"Headers: {response.headers}")
        
        if response.status_code == 200:
            print("✅ Connection Successful!")
        else:
            print("❌ Connection Failed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_connection()
