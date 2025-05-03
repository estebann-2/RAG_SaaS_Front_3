from langchain.text_splitter import RecursiveCharacterTextSplitter
import fitz  # PyMuPDF para extraer texto de PDFs
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma
import os
import mmap
import chardet
import logging
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from .models import Chunk
from docx import Document

# Configurar logging
logging.basicConfig(
    filename="document_processing.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Inicializar embeddings de OpenAI
embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")

# Definir chunking más eficiente
text_splitter = RecursiveCharacterTextSplitter(chunk_size=10000, chunk_overlap=2000)

# Iniciar medición de memoria
tracemalloc.start()

def log_memory_usage():
    """Muestra las 5 líneas que más memoria consumen."""
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics("lineno")
    logging.info("Top 5 Memory Usage Lines:")
    for stat in top_stats[:5]:
        logging.info(stat)

def process_chunk(index, chunk, document):
    """Procesa y guarda un chunk en la base de datos."""
    try:
        chunk_embedding = embedding_model.embed_documents([chunk])[0]
        Chunk.objects.create(document=document, content=chunk, embedding=chunk_embedding)
        return f"Chunk {index + 1} procesado"
    except Exception as e:
        return f"Error en chunk {index + 1}: {e}"

def try_utf8_read(file_path):
    """Intenta leer el archivo en UTF-8, y si falla, detecta la codificación."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip(), "utf-8"
    except UnicodeDecodeError:
        logging.warning(f"Error al leer {file_path} en UTF-8. Intentando detectar encoding...")
        
        with open(file_path, "rb") as f:
            raw_data = f.read(10000)  # Leer muestra para detectar encoding
            result = chardet.detect(raw_data)
            encoding = result.get("encoding", "latin1")  # Fallback a latin1 si falla

        logging.info(f"Encoding detectado: {encoding}")

        with open(file_path, "r", encoding=encoding, errors="replace") as f:
            return f.read().strip(), encoding

def extract_text(file_path):
    """Extracts text based on file type."""
    file_ext = os.path.splitext(file_path)[1].lower()

    try:
        if file_ext == ".pdf":
            logging.info(f"Extracting text from PDF: {file_path}")
            text = ""
            with fitz.open(file_path) as pdf_document:
                for page in pdf_document:
                    text += page.get_text("text")
            return text.strip()

        elif file_ext in [".docx"]:
            logging.info(f"Extracting text from Word document: {file_path}")
            doc = Document(file_path)
            return "\n".join([para.text for para in doc.paragraphs]).strip()

        elif file_ext == ".txt":
            logging.info(f"Reading text file: {file_path}")
            return try_utf8_read(file_path)[0]

        else:
            logging.warning(f"Unsupported file type: {file_ext}")
            return None

    except Exception as e:
        logging.error(f"Error extracting text from {file_path}: {e}", exc_info=True)
        return None

def process_document(document):
    """Procesa un documento: lectura, chunking, embedding y almacenamiento."""
    try:
        print("Iniciando procesamiento del documento...")
        file_path = document.file.path
        logging.info(f"Procesando documento: {document.title} ({file_path})")

        # Extraer texto del documento
        text = extract_text(file_path)

        if not text or len(text.strip()) == 0:
            logging.warning(f"Documento '{document.title}' no tiene contenido legible.")
            print(f"Documento '{document.title}' no tiene contenido legible.")
            return

        logging.info(f"Documento leído, longitud: {len(text)} caracteres")

        # División en chunks
        chunks = text_splitter.split_text(text)
        logging.info(f"Documento dividido en {len(chunks)} chunks")
        print(f"Documento dividido en {len(chunks)} chunks")

        # Procesamiento en batch
        batch_size = 10  # Ajustable según rendimiento
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_embeddings = embedding_model.embed_documents(batch_chunks)

            # Guardado en batch
            Chunk.objects.bulk_create([
                Chunk(document=document, content=batch_chunks[j], embedding=batch_embeddings[j])
                for j in range(len(batch_chunks))
            ])
            print(f"Batch {i//batch_size + 1} procesado")

        # Procesamiento paralelo con ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda i: process_chunk(i, chunks[i], document), range(len(chunks))))

        # Mostrar resultados de la ejecución
        for res in results:
            print(res)

        # Marcar documento como procesado
        document.processed = True
        document.save()
        logging.info(f"Documento '{document.title}' procesado con éxito")
        print(f"Documento '{document.title}' procesado con éxito!")

    except Exception as e:
        logging.error(f"Error procesando documento '{document.title}': {e}", exc_info=True)
        print(f"Error procesando documento '{document.title}': {e}")


from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

def query_llm(user_input):
    """Handles sending a query to the LLM and returning a response."""
    try:
        logging.info(f"Sending query to LLM: {user_input}")

        # Format messages
        messages = [
            SystemMessage(content="You are an AI assistant that provides helpful responses."),
            HumanMessage(content=user_input)
        ]

        # Get response from LLM
        response = llm(messages)

        # Extract text response
        response_text = response.content.strip()

        logging.info(f"LLM response: {response_text}")

        return response_text

    except Exception as e:
        logging.error(f"Error querying LLM: {str(e)}", exc_info=True)
        return "Error processing request. Please try again later."