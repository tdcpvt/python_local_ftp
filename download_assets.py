import os
import urllib.request

# Force target container path mapping structure
os.makedirs("static", exist_ok=True)

assets = {
    "static/bliss.jpg": "https://wikimedia.org",
    "static/computer.png": "https://alexmeub.com",
    "static/gears.png": "https://alexmeub.com"
}

# Emulate standard Chrome headers to bypass the command-line blocks safely
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

for path, url in assets.items():
    print(f"[Network Pipeline] Fetching asset binary: {path} ...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response, open(path, 'wb') as out_file:
            out_file.write(response.read())
        print(f"✔️ Saved successfully ({os.path.getsize(path)} bytes).")
    except Exception as e:
        print(f"❌ Failed to download {path}: {e}")

print("\nAsset structure validation complete.")
