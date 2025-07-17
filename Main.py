from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pdfreader import SimplePDFViewer
import re
import io
import base64

app = FastAPI()

class FileBase64(BaseModel):
    file: str  # PDF codificado en base64

def es_factura(texto1):
    texto = " ".join(texto1)
    texto_lower = texto.lower()

    palabras_clave_obligatorias = [
        "factura", "recibo", "ticket", "nota de crédito", "nota de débito", "comprobante"
    ]
    palabras_clave_opcionales = [
        "fecha de emisión", "período facturado", "fecha de vto.", "condición de venta",
        "condición frente al iva", "apellido y nombre", "razón social", "domicilio", "cuit",
        "ingresos brutos", "producto / servicio", "cantidad", "precio unit.",
        "subtotal", "importe total", "cae n°", "comprobante nro", "n°", "total"
    ]
    patron_cuit = r'\b\d{2}[-.\s]?\d{8}[-.\s]?\d{1}\b'
    patron_fecha = r'\b\d{2}/\d{2}/\d{4}\b'
    patron_importe = r'\b\d{1,3}(?:\.\d{3})*,\d{2}\b'

    obligatoria_presente = any(pk in texto_lower for pk in palabras_clave_obligatorias)
    if not obligatoria_presente:
        return False

    puntuacion = sum(1 for pk in palabras_clave_opcionales if pk in texto_lower)
    if re.search(patron_cuit, texto): puntuacion += 2
    if re.search(patron_fecha, texto): puntuacion += 1
    if re.search(patron_importe, texto): puntuacion += 1

    return puntuacion >= 5

@app.post("/es_factura/")
async def analizar_pdf(data: FileBase64):
    try:
        pdf_bytes = base64.b64decode(data.file)
        fd = io.BytesIO(pdf_bytes)
        viewer = SimplePDFViewer(fd)

        texto_extraido = []
        for canvas in viewer:
            texto_extraido.extend(canvas.strings)

        resultado = es_factura(texto_extraido)
        return JSONResponse(content={"es_factura": resultado})

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
