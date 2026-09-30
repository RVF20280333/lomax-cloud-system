import io
import requests
from PIL import Image, ImageDraw

API = "http://localhost:8000"
COLORES = {"TEC": (40, 90, 160), "MON": (30, 130, 90), "MOU": (170, 90, 40)}

for pid in range(1, 21):
    d = requests.get(f"{API}/productos/{pid}").json()
    if d.get("estado") == "PUBLICADO":
        print(pid, "ya publicado")
        continue
    img = Image.new("RGB", (1000, 700), COLORES[d["codigo"][:3]])
    ImageDraw.Draw(img).text((40, 320), f'{d["codigo"]} - {d["nombre"]}', fill="white")
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    r = requests.post(f"{API}/productos/{pid}/imagen",
                      files={"file": (f"{pid}.jpg", buf.getvalue(), "image/jpeg")})
    print(pid, r.status_code, r.json())