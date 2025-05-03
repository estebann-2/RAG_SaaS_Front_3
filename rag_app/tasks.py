from celery import shared_task
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings.openai import OpenAIEmbeddings
from .models import Chunk, Document

# Initialize embedding model
embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")

# Define chunking parameters
text_splitter = RecursiveCharacterTextSplitter(chunk_size=50000, chunk_overlap=10000)

@shared_task
def process_document_task(document_id):
    """Celery task to process document asynchronously."""
    try:
        document = Document.objects.get(id=document_id)

        # Read file content
        file_path = document.file.path
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        # Split text into chunks
        chunks = text_splitter.split_text(text)

        # Process each chunk
        for chunk in chunks:
            chunk_embedding = embedding_model.embed_documents([chunk])[0]
            Chunk.objects.create(document=document, content=chunk, embedding=chunk_embedding)

        # Mark document as processed
        document.processed = True
        document.save()

    except Exception as e:
        print(f"Error processing document {document_id}: {e}")
