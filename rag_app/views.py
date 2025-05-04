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
def start_conversation(request):
    if request.method == "POST":
        title = request.POST.get("title", "Nueva Conversación")
        conversation = Conversation.objects.create(user=request.user, title=title)
        return redirect("conversation_detail", conversation_id=conversation.id)

    return render(request, "rag_app/start_conversation.html")


# View a Specific Conversation & Messages
@login_required
def conversation_detail(request, conversation_id):
    try:
        conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
        messages = conversation.messages.select_related("sender").order_by("timestamp")
        form = MessageForm()

        return render(request, "rag_app/conversation_detail.html", {
            "conversation": conversation,
            "messages": messages,
            "form": form
        })
    except:
        messages.error(request, "La conversación no existe o no tienes permiso para acceder a ella.")
        return redirect('home')


import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

# Configuration
API_BASE_URL = 'http://34.16.64.68:8000/api'
API_TOKEN = "539fb7f7fbec80f930c23667552635637e6ea0ac"

def get_headers(request):
    """Helper function to get authentication headers"""
    return {
        'Authorization': f'Token {API_TOKEN}'
    }

@login_required
def upload_document(request):
    if request.method == "POST" and request.FILES.get("document"):
        uploaded_file = request.FILES["document"]
        
        # Prepare the request
        files = {'document': uploaded_file}
        data = {
            'user': request.user.id
        }
        
        try:
            response = requests.post(
                f'{API_BASE_URL}/api_upload/',
                files=files,
                data=data,
                headers=get_headers(request)
            )
            
            if response.status_code == 201:
                api_response = response.json()
                # Create or get the conversation using the ID from the API response
                conversation, created = Conversation.objects.get_or_create(
                    id=api_response['conversation_id'],
                    defaults={
                        'user': request.user,
                        'title': f"Conversation about {uploaded_file.name}"
                    }
                )

                # Create the first message with the API response
                if api_response.get('response'):
                    Message.objects.create(
                        conversation=conversation,
                        sender=request.user,
                        text=api_response['response'],
                        role='assistant'
                    )

                return JsonResponse({
                    'success': True,
                    'conversation_id': conversation.id,
                    **api_response
                })
            return JsonResponse({'error': 'Upload failed'}, status=response.status_code)
            
        except requests.RequestException as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({"error": "No file provided"}, status=400)

@login_required
def conversation_history(request):
    try:
        response = requests.get(
            f'{API_BASE_URL}/api_conversation/history',
            params={'user': request.user.id},
            headers=get_headers(request)
        )
        
        if response.status_code == 200:
            conversations = response.json()
            return render(request, 'rag_app/conversation_history.html', {
                'conversations': conversations
            })
        
        messages.error(request, "Failed to fetch conversation history")
        return redirect('home')
        
    except requests.RequestException as e:
        messages.error(request, f"Error: {str(e)}")
        return redirect('home')

@login_required
def send_message(request, conversation_id):
    if request.method == "POST":
        try:
            # Get the conversation
            conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
            
            # Check if the request is AJAX/JSON
            if request.content_type == 'application/json':
                import json
                data = json.loads(request.body)
                message_text = data.get('text')
            else:
                message_text = request.POST.get('text')

            if not message_text:
                return JsonResponse({'error': 'Message text is required'}, status=400)
            
            payload = {
                'message': message_text,
                'user': str(request.user.id),
                'conversation': str(conversation_id)
            }
            
            try:
                response = requests.post(
                    f'{API_BASE_URL}/api_conversation/send/',
                    json=payload,
                    headers={
                        **get_headers(request),
                        'Content-Type': 'application/json'
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # Create local message records
                    Message.objects.create(
                        conversation=conversation,
                        sender=request.user,
                        text=message_text,
                        role='user'
                    )
                    if data.get('assistant_response'):
                        Message.objects.create(
                            conversation=conversation,
                            sender=request.user,
                            text=data['assistant_response'],
                            role='assistant'
                        )
                    
                    # If it's an AJAX request, return JSON response
                    if request.content_type == 'application/json':
                        return JsonResponse({
                            'success': True,
                            'assistant_response': data.get('assistant_response')
                        })
                    # For regular form submit, redirect back to conversation
                    return redirect('conversation_detail', conversation_id=conversation_id)
                
                error_msg = 'Failed to send message'
                if request.content_type == 'application/json':
                    return JsonResponse({'error': error_msg}, status=response.status_code)
                messages.error(request, error_msg)
                return redirect('conversation_detail', conversation_id=conversation_id)
                
            except requests.RequestException as e:
                error_msg = str(e)
                if request.content_type == 'application/json':
                    return JsonResponse({'error': error_msg}, status=500)
                messages.error(request, f"Error: {error_msg}")
                return redirect('conversation_detail', conversation_id=conversation_id)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Conversation.DoesNotExist:
            return JsonResponse({'error': 'Conversation not found'}, status=404)

    # For GET requests, redirect to conversation detail
    return redirect('conversation_detail', conversation_id=conversation_id)