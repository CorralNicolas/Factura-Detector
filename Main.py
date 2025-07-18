from fastapi import FastAPI, File, UploadFile, status, HTTPException
from fastapi.responses import JSONResponse
from pdfreader import SimplePDFViewer
import re
import io
from pydantic import BaseModel
import os # Importar para leer variables de entorno

# --- Definición de Modelos de Pydantic para la respuesta ---
class EsFacturaResponse(BaseModel):
    """
    Modelo de respuesta para el endpoint /es_factura/.
    Indica si el documento analizado se considera una factura (True/False).
    """
    es_factura: bool

# --- Instancia de FastAPI ---
app = FastAPI(
    title="API de Detección de Facturas en PDF",
    description="Esta API recibe un archivo PDF y utiliza lógica de procesamiento de texto para intentar identificar si el contenido corresponde a una factura, recibo o comprobante.",
    version="1.0.0",
)

# --- Lógica central para determinar si un texto es una factura ---
def es_factura_logic(texto_list: list[str]) -> bool:
    """
    Analiza una lista de cadenas de texto extraídas de un PDF
    para determinar si el documento es probablemente una factura.

    Args:
        texto_list: Una lista de cadenas de texto extraídas del PDF.

    Returns:
        True si el texto cumple los criterios para ser una factura, False en caso contrario.
    """
    texto = " ".join(texto_list).lower() # Unir y convertir a minúsculas una sola vez para eficiencia

    palabras_clave_obligatorias = [
        "factura", "recibo", "ticket", "nota de crédito", "nota de débito", "comprobante"
    ]
    palabras_clave_opcionales = [
        "fecha de emisión", "período facturado", "fecha de vto.", "condición de venta",
        "condición frente al iva", "apellido y nombre", "razón social", "domicilio", "cuit",
        "ingresos brutos", "producto / servicio", "cantidad", "precio unit.",
        "subtotal", "importe total", "cae n°", "comprobante nro", "n°", "total"
    ]
    # Patrones RegEx mejorados para mayor robustez
    patron_cuit = r'\b\d{2}[-.\s]?\d{8}[-.\s]?\d{1}\b' # 11 dígitos, con o sin guiones/espacios
    patron_fecha = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b' # dd/mm/aaaa o dd-mm-aaaa
    patron_importe = r'\b(?:\d{1,3}(?:\.\d{3})*|\d+)[,\.]\d{2}\b' # Importe con coma o punto decimal

    # 1. Verificación de palabras clave obligatorias
    obligatoria_presente = any(pk in texto for pk in palabras_clave_obligatorias)
    if not obligatoria_presente:
        return False

    # 2. Puntuación basada en palabras clave opcionales y patrones RegEx
    puntuacion = sum(1 for pk in palabras_clave_opcionales if pk in texto)

    if re.search(patron_cuit, texto):
        puntuacion += 2 # CUIT es un indicador fuerte
    if re.search(patron_fecha, texto):
        puntuacion += 1
    if re.search(patron_importe, texto):
        puntuacion += 1

    # Umbral de puntuación
    return puntuacion >= 5

# --- Endpoint de la API ---
@app.post(
    "/es_factura/",
    response_model=EsFacturaResponse, # Define el tipo de respuesta para OpenAPI/Power Automate
    summary="Determina si un archivo PDF es una factura o comprobante",
    description="Recibe un archivo PDF y lo analiza textualmente para verificar la presencia de palabras clave y patrones que indican que el documento es una factura, recibo o comprobante.",
    status_code=status.HTTP_200_OK, # Código de estado HTTP por defecto para una respuesta exitosa
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": dict, # Usamos dict para un error simple, puedes crear un BaseModel si quieres
            "description": "Solicitud incorrecta (e.g., archivo no es PDF)."
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": dict,
            "description": "Error interno del servidor al procesar el archivo."
        }
    }
)
async def analizar_pdf(
    file: UploadFile = File(
        ...,
        media_type="application/pdf", # Sugiere que solo se aceptan PDFs en la documentación
        description="El archivo PDF a analizar (máximo 5MB recomendado para evitar timeouts)."
    )
):
    """
    Endpoint principal para cargar un PDF y verificar si es una factura.
    """
    # Validación de tipo de contenido para una mejor experiencia de usuario
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de archivo no soportado. Por favor, sube un documento PDF (application/pdf)."
        )

    try:
        # Leer el contenido del archivo subido
        contents = await file.read()
        fd = io.BytesIO(contents) # Usar BytesIO para tratar los bytes como un archivo

        # Inicializar el lector de PDF
        viewer = SimplePDFViewer(fd)

        texto_extraido = []
        # Iterar a través de cada página del PDF y extraer el texto
        for canvas in viewer:
            texto_extraido.extend(canvas.strings)

        # Llamar a la lógica de detección de factura
        es_fact = es_factura_logic(texto_extraido)

        # Retornar la respuesta usando el modelo Pydantic
        return EsFacturaResponse(es_factura=es_fact)

    except Exception as e:
        # Captura cualquier excepción inesperada durante el procesamiento
        print(f"Error interno al procesar el PDF: {e}") # Para depuración en los logs de Render
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ocurrió un error inesperado al procesar el archivo: {str(e)}. Por favor, inténtelo de nuevo o contacte al soporte."
        )

# --- Configuración para Uvicorn (usado por Render) ---
# Esto es necesario para que Uvicorn sepa qué aplicación ejecutar y en qué puerto.
# Render asigna el puerto a través de una variable de entorno.
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000)) # Leer el puerto de la variable de entorno o usar 8000 por defecto
    uvicorn.run(app, host="0.0.0.0", port=port)
