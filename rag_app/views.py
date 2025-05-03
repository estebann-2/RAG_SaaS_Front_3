from django.contrib.auth.models import User
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Document, Message, Conversation
from .forms import DocumentUploadForm, MessageForm
import os
from .utils import process_document, query_llm
from .retriever import retrieve_relevant_chunks
import logging



# User Login
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "Inicio de sesión exitoso.")
            return redirect('home')
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")
    else:
        form = AuthenticationForm()
    
    return render(request, 'rag_app/login.html', {'form': form})

# User Logout
def logout_view(request):
    if request.method == 'POST':
        logout(request)
        messages.info(request, "Has cerrado sesión correctamente.")
        return redirect('login')

@login_required
def home(request):
    conversations = Conversation.objects.filter(user=request.user).order_by("-created_at")  # Show newest first
    return render(request, 'rag_app/base.html', {'conversations': conversations})


@login_required
def upload_document(request):
    if request.method == "POST" and request.FILES.get("document"):
        uploaded_file = request.FILES["document"]

        # Extract the filename (without extension)
        document_name = os.path.splitext(uploaded_file.name)[0]

        # Ensure a conversation is created using the document title
        conversation = Conversation.objects.create(user=request.user, title=document_name)

        # Save the uploaded document and link it to the conversation
        document = Document.objects.create(
            user=request.user,
            file=uploaded_file,
            title=document_name,  # Store the document name
            conversation=conversation  # Link document to conversation
        )

        # Process document for chunking & embedding (async recommended)
        process_document(document)

        # Create a system message to confirm the document upload
        Message.objects.create(
            conversation=conversation,
            sender=request.user,  # Keeping sender as user for now
            text=f"📂 Documento '{document_name}' procesado y listo para consultas."
        )

        return JsonResponse({
            "success": True,
            "response": f"Documento '{document_name}' subido y procesado.",
            "conversation_id": conversation.id
        })

    return JsonResponse({"success": False, "error": "No se proporcionó un archivo."})



@login_required
def conversation_history(request):
    conversations = Conversation.objects.filter(user=request.user).order_by("-created_at")

    print(f"User {request.user.username} is viewing conversation history.")
    print(f"Found {conversations.count()} conversations for this user.")

    for convo in conversations:
        print(f"ID: {convo.id}, Title: {convo.title}, Created: {convo.created_at}")

    return render(request, 'rag_app/conversation_history.html', {'conversations': conversations})



@login_required
def start_conversation(request):
    if request.method == "POST":
        title = request.POST.get("title", "Nueva Conversación")
        conversation = Conversation.objects.create(user=request.user, title=title)
        return redirect("conversation_detail", conversation_id=conversation.id)

    return render(request, "rag_app/start_conversation.html")

@login_required
def start_conversation(request):
    if request.method == "POST":
        title = request.POST.get("title", "Nueva Conversación")
        conversation = Conversation.objects.create(user=request.user, title=title)
        return redirect("conversation_detail", conversation_id=conversation.id)

    return render(request, "rag_app/start_conversation.html")


# View a Specific Conversation & Messages
@login_required
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    messages = conversation.messages.select_related("sender").order_by("timestamp")  # Optimized query
    form = MessageForm()

    return render(request, "rag_app/conversation_detail.html", {
        "conversation": conversation,
        "messages": messages,
        "form": form
    })

# Send a Message and Get Response from LLM
@login_required
def send_message(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)

    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            # Save user message
            user_message = form.save(commit=False)
            user_message.conversation = conversation
            user_message.sender = request.user
            user_message.role = "user"
            user_message.save()


            # Retrieve relevant chunks
            relevant_chunks = retrieve_relevant_chunks(user_message.text, conversation, top_k=3)

            # Log retrieved chunks
            chunk_info = "\n".join([f"Chunk {c['chunk_id']} from {c['document']}: {c['content'][:50]}..." for c in relevant_chunks])
            logging.info(f"🔍 Relevant Chunks Used:\n{chunk_info}")

            # Format prompt for LLM
            context_text = "\n\n".join([f"Document: {c['document']}\nChunk {c['chunk_id']}:\n{c['content']}" for c in relevant_chunks])
            prompt = f"Context:\n{context_text}\n\nUser Query: {user_message.text}"

            # Query the LLM
            llm_response = query_llm(prompt)

            

            # Save LLM response
            Message.objects.create(
                conversation=conversation,
                sender=request.user,  # Keeping sender for structure, but should be an assistant bot user
                role="assistant",
                text=llm_response
            )

            return redirect("conversation_detail", conversation_id=conversation.id)

    return redirect("conversation_detail", conversation_id=conversation.id)