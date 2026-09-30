import io
import os
import boto3
from PIL import Image

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL") or None
REGION = "us-east-1"
TABLA = "lomax-productos-atributos"
BUCKET_MINIATURAS = "lomax-miniaturas"

def _clientes():
    kw = dict(endpoint_url=ENDPOINT, region_name=REGION,
              aws_access_key_id="test", aws_secret_access_key="test")
    return boto3.client("s3", **kw), boto3.client("dynamodb", **kw)

def _estado(dynamo, producto_id, estado, miniatura_key=None):
    dynamo.update_item(
        TableName=TABLA,
        Key={"producto_id": {"N": str(producto_id)}},
        UpdateExpression="SET estado_procesamiento = :e, miniatura_key = :m",
        ExpressionAttributeValues={
            ":e": {"S": estado},
            ":m": {"S": miniatura_key} if miniatura_key else {"NULL": True},
        },
    )

def lambda_handler(event, context):
    producto_id = event["producto_id"]
    bucket = event["bucket"]
    key = event["key"]
    s3, dynamo = _clientes()
    try:
        data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data))
        if img.format not in ("JPEG", "PNG"):
            raise ValueError("Formato no permitido")
        img.thumbnail((300, 300))
        salida = io.BytesIO()
        fmt = img.format or "JPEG"
        if fmt == "JPEG" and img.mode != "RGB":
            img = img.convert("RGB")
        img.save(salida, format=fmt)
        ext = "png" if fmt == "PNG" else "jpg"
        mini_key = f"miniaturas/{producto_id}.{ext}"
        ctype = "image/png" if fmt == "PNG" else "image/jpeg"
        s3.put_object(Bucket=BUCKET_MINIATURAS, Key=mini_key,
                      Body=salida.getvalue(), ContentType=ctype)
        _estado(dynamo, producto_id, "LISTA", mini_key)
        return {"ok": True, "miniatura_key": mini_key,
                "ancho": img.width, "alto": img.height}
    except Exception as e:
        _estado(dynamo, producto_id, "ERROR")
        return {"ok": False, "error": str(e)}