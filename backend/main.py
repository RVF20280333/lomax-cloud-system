import json
import os
import socket
from decimal import Decimal
from typing import Any, Dict

import boto3
import psycopg2
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from psycopg2 import errors
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, ConfigDict, Field

DB = dict(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    user=os.getenv("DB_USER", "lomax"),
    password=os.getenv("DB_PASSWORD", "lomax123"),
    dbname=os.getenv("DB_NAME", "lomaxdb"),
    connect_timeout=5,
)
AWS_ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4567")
TABLA = "lomax-productos-atributos"
B_ORIG = "lomax-originales"
B_MINI = "lomax-miniaturas"
LAMBDA = "lomax-resizer"
MAX_BYTES = 5 * 1024 * 1024
INSTANCIA = socket.gethostname()

_kw = dict(
    endpoint_url=AWS_ENDPOINT, region_name="us-east-1",
    aws_access_key_id="test", aws_secret_access_key="test",
    config=Config(read_timeout=120, connect_timeout=5, retries={"max_attempts": 1}),
)
s3 = boto3.client("s3", **_kw)
lam = boto3.client("lambda", **_kw)
dyn = boto3.resource("dynamodb", **_kw).Table(TABLA)

app = FastAPI(title="Lomax API")


class ApiError(Exception):
    def __init__(self, status, paso, mensaje, **extra):
        self.status, self.paso, self.mensaje, self.extra = status, paso, mensaje, extra


@app.exception_handler(ApiError)
async def _api_error(request, exc: ApiError):
    return JSONResponse(status_code=exc.status,
                        content={"paso": exc.paso, "error": exc.mensaje, **exc.extra})


@app.exception_handler(RequestValidationError)
async def _validation(request, exc: RequestValidationError):
    detalle = [{"campo": ".".join(str(x) for x in e["loc"]), "mensaje": e["msg"]}
               for e in exc.errors()]
    return JSONResponse(status_code=400,
                        content={"paso": "validacion", "error": detalle})


@app.middleware("http")
async def _instancia(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Instance-Id"] = INSTANCIA
    return resp


class ProductoIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    codigo: str = Field(min_length=1, max_length=40)
    nombre: str = Field(min_length=1, max_length=150)
    descripcion: str = Field(min_length=1)
    precio: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    categoria_id: int
    atributos: Dict[str, Any] = Field(min_length=1)


def conectar():
    try:
        return psycopg2.connect(**DB)
    except psycopg2.OperationalError as e:
        raise ApiError(503, "rds_conexion", str(e).strip())


def obtener_producto(pid: int):
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT p.producto_id, p.codigo, p.nombre, p.descripcion, p.precio, "
                "p.categoria_id, c.nombre AS categoria, p.fecha, p.estado "
                "FROM productos p JOIN categorias c USING (categoria_id) "
                "WHERE p.producto_id = %s", (pid,))
            return cur.fetchone()
    finally:
        conn.close()


def item_dynamo(pid: int):
    try:
        return dyn.get_item(Key={"producto_id": pid}).get("Item")
    except (ClientError, BotoCoreError) as e:
        raise ApiError(502, "dynamodb_lectura", str(e))


def procesar(pid: int):
    """Invoca Lambda y publica solo si todo está verificado. Reutilizable (idempotente)."""
    item = item_dynamo(pid)
    if not item or not item.get("imagen_original_key"):
        raise ApiError(409, "original_inexistente",
                       "El producto no tiene imagen original guardada", producto_id=pid)
    key = item["imagen_original_key"]
    try:
        r = lam.invoke(FunctionName=LAMBDA, InvocationType="RequestResponse",
                       Payload=json.dumps({"producto_id": pid, "bucket": B_ORIG, "key": key}))
        payload = json.loads(r["Payload"].read() or b"{}")
    except (ClientError, BotoCoreError) as e:
        raise ApiError(502, "lambda_invocacion", str(e), producto_id=pid, estado="PENDIENTE")
    if r.get("FunctionError") or not payload.get("ok"):
        raise ApiError(400, "lambda_procesamiento",
                       payload.get("error", "Falló la función Lambda"),
                       producto_id=pid, estado="PENDIENTE")
    mini = payload["miniatura_key"]
    try:
        s3.head_object(Bucket=B_MINI, Key=mini)
    except (ClientError, BotoCoreError) as e:
        raise ApiError(502, "s3_verificar_miniatura", str(e), producto_id=pid, estado="PENDIENTE")
    item = item_dynamo(pid)
    if not item or item.get("estado_procesamiento") != "LISTA" \
            or item.get("miniatura_key") != mini or not item.get("atributos"):
        raise ApiError(502, "dynamodb_verificacion",
                       "Atributos o miniatura no confirmados", producto_id=pid, estado="PENDIENTE")
    conn = conectar()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("UPDATE productos SET estado='PUBLICADO' WHERE producto_id=%s", (pid,))
    finally:
        conn.close()
    return {"producto_id": pid, "estado": "PUBLICADO", "miniatura_key": mini}


@app.get("/health")
def health():
    return {"ok": True, "instancia": INSTANCIA}


@app.get("/categorias")
def categorias():
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT categoria_id, nombre FROM categorias ORDER BY categoria_id")
            return cur.fetchall()
    finally:
        conn.close()


@app.post("/productos", status_code=201)
def crear_producto(p: ProductoIn):
    conn = conectar()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO productos (codigo,nombre,descripcion,precio,categoria_id) "
                "VALUES (%s,%s,%s,%s,%s) RETURNING producto_id",
                (p.codigo, p.nombre, p.descripcion, p.precio, p.categoria_id))
            pid = cur.fetchone()[0]
    except errors.UniqueViolation:
        raise ApiError(409, "rds_insert", f"El código '{p.codigo}' ya existe")
    except errors.ForeignKeyViolation:
        raise ApiError(400, "rds_insert", "La categoría no existe")
    except (errors.CheckViolation, errors.NotNullViolation) as e:
        raise ApiError(400, "rds_insert", str(e).splitlines()[0])
    finally:
        conn.close()
    try:
        atributos = json.loads(json.dumps(p.atributos), parse_float=Decimal)
        dyn.put_item(Item={"producto_id": pid, "atributos": atributos,
                           "imagen_original_key": None, "miniatura_key": None,
                           "estado_procesamiento": "PENDIENTE"})
    except (ClientError, BotoCoreError) as e:
        raise ApiError(502, "dynamodb_atributos", str(e), producto_id=pid, estado="PENDIENTE")
    return {"producto_id": pid, "estado": "PENDIENTE"}


@app.post("/productos/{pid}/imagen")
async def subir_imagen(pid: int, file: UploadFile = File(...)):
    if not obtener_producto(pid):
        raise ApiError(404, "rds_consulta", "Producto no encontrado")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise ApiError(413, "validacion_archivo", "El archivo supera 5 MB")
    if data.startswith(b"\xff\xd8\xff"):
        ext, ctype = "jpg", "image/jpeg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        ext, ctype = "png", "image/png"
    else:
        raise ApiError(415, "validacion_archivo", "Solo se permite JPEG o PNG")
    key = f"originales/{pid}.{ext}"
    try:
        s3.put_object(Bucket=B_ORIG, Key=key, Body=data, ContentType=ctype)
    except (ClientError, BotoCoreError) as e:
        raise ApiError(502, "s3_guardar_original", str(e), producto_id=pid, estado="PENDIENTE")
    try:
        dyn.update_item(
            Key={"producto_id": pid},
            UpdateExpression="SET imagen_original_key = :k, estado_procesamiento = :e",
            ConditionExpression="attribute_exists(producto_id)",
            ExpressionAttributeValues={":k": key, ":e": "PENDIENTE"})
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ApiError(409, "dynamodb_atributos",
                           "El producto no tiene atributos en DynamoDB", producto_id=pid)
        raise ApiError(502, "dynamodb_actualizar", str(e), producto_id=pid, estado="PENDIENTE")
    except BotoCoreError as e:
        raise ApiError(502, "dynamodb_actualizar", str(e), producto_id=pid, estado="PENDIENTE")
    return procesar(pid)


@app.post("/productos/{pid}/reprocesar")
def reprocesar(pid: int):
    if not obtener_producto(pid):
        raise ApiError(404, "rds_consulta", "Producto no encontrado")
    return procesar(pid)   # NO hace INSERT: solo reintenta Lambda


@app.get("/productos")
def listar():
    conn = conectar()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT p.producto_id, p.codigo, p.nombre, p.precio, c.nombre AS categoria "
                "FROM productos p JOIN categorias c USING (categoria_id) "
                "WHERE p.estado='PUBLICADO' ORDER BY p.producto_id")
            filas = cur.fetchall()
    finally:
        conn.close()
    for f in filas:
        it = item_dynamo(f["producto_id"]) or {}
        f["atributos"] = it.get("atributos", {})
        f["miniatura_key"] = it.get("miniatura_key")
    return filas


@app.get("/productos/{pid}")
def detalle(pid: int):
    p = obtener_producto(pid)
    if not p:
        raise ApiError(404, "rds_consulta", "Producto no encontrado")
    it = item_dynamo(pid) or {}
    p["atributos"] = it.get("atributos", {})
    p["imagen_original_key"] = it.get("imagen_original_key")
    p["miniatura_key"] = it.get("miniatura_key")
    p["estado_procesamiento"] = it.get("estado_procesamiento")
    return p


@app.get("/productos/{pid}/imagen")
def imagen(pid: int):
    it = item_dynamo(pid)
    if not it or not it.get("miniatura_key") or it.get("estado_procesamiento") != "LISTA":
        raise ApiError(404, "miniatura_no_disponible", "No hay miniatura disponible")
    try:
        obj = s3.get_object(Bucket=B_MINI, Key=it["miniatura_key"])
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            raise ApiError(404, "miniatura_no_disponible", "La miniatura no existe en S3")
        raise ApiError(502, "s3_leer_miniatura", str(e))
    except BotoCoreError as e:
        raise ApiError(502, "s3_leer_miniatura", str(e))
    return Response(content=obj["Body"].read(), media_type=obj["ContentType"])