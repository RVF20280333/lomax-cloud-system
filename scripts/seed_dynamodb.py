import boto3

dynamodb = boto3.resource(
    "dynamodb", endpoint_url="http://localhost:4567",
    region_name="us-east-1",
    aws_access_key_id="test", aws_secret_access_key="test",
)
tabla = dynamodb.Table("lomax-productos-atributos")

def teclado(conexion, distribucion):
    return {"conexion": conexion, "distribucion": distribucion}
def monitor(pulgadas, resolucion):
    return {"pulgadas": pulgadas, "resolucion": resolucion}
def mouse(conexion, dpi):
    return {"conexion": conexion, "dpi": dpi}

atributos = {
    1: teclado("USB", "QWERTY"), 2: teclado("Bluetooth", "QWERTY"),
    3: teclado("USB", "QWERTY"), 4: teclado("USB", "QWERTY"),
    5: teclado("USB", "QWERTY"), 6: teclado("Bluetooth", "QWERTY"),
    7: teclado("Bluetooth", "QWERTY"),
    8: monitor(24, "1920x1080"), 9: monitor(27, "2560x1440"),
    10: monitor(32, "3840x2160"), 11: monitor(22, "1920x1080"),
    12: monitor(27, "2560x1440"), 13: monitor(24, "1920x1080"),
    14: monitor(34, "3440x1440"),
    15: mouse("Inalámbrico", 1000), 16: mouse("USB", 6400),
    17: mouse("Inalámbrico", 4000), 18: mouse("USB", 1000),
    19: mouse("USB", 6000), 20: mouse("Bluetooth", 1600),
}

for pid, attrs in atributos.items():
    tabla.put_item(Item={
        "producto_id": pid,
        "atributos": attrs,
        "imagen_original_key": None,
        "miniatura_key": None,
        "estado_procesamiento": "PENDIENTE",
    })
print(f"{len(atributos)} productos cargados (put_item es repetible: no duplica).")