from django.contrib.auth.models import User
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Document, Message, Conversation
from .forms import DocumentUploadForm, MessageForm
import requests
from django.conf import settings
import logging
import json

# Configuration
API_BASE_URL = 'http://34.16.64.68:8000/api'
API_TOKEN = "539fb7f7fbec80f930c23667552635637e6ea0ac"

def get_headers(request):
    """Helper function to get authentication headers"""
    return {
        'Authorization': f'Token {API_TOKEN}'
    }

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
    try:
        response = requests.get(
            f'{API_BASE_URL}/api_conversation/history',
            params={'user': request.user.id},
            headers=get_headers(request)
        )
        
        if response.status_code == 200:
            conversations = response.json()
        else:
            conversations = []
            messages.error(request, "No se pudieron cargar las conversaciones.")
            
    except requests.RequestException:
        conversations = []
        messages.error(request, "Error al conectar con el servidor.")
    
    return render(request, 'rag_app/base.html', {'conversations': conversations})

@login_required
def start_conversation(request):
    return render(request, "rag_app/start_conversation.html")

@login_required
def conversation_detail(request, conversation_id):
    try:
        # Fetch conversation details from API
        response = requests.get(
            f'{API_BASE_URL}/api_conversation/{conversation_id}/',
            params={'user': request.user.id},
            headers=get_headers(request)
        )
        
        if response.status_code == 404:
            messages.error(request, "La conversación no existe o no tienes permiso para acceder a ella.")
            return redirect('home')
            
        if response.status_code != 200:
            messages.error(request, "Error al cargar la conversación.")
            return redirect('home')
            
        conversation_data = response.json()
        form = MessageForm()
        
        return render(request, "rag_app/conversation_detail.html", {
            "conversation": conversation_data,
            "messages": conversation_data.get('messages', []),
            "form": form
        })
        
    except requests.RequestException as e:
        messages.error(request, "Error al conectar con el servidor.")
        return redirect('home')

@login_required
def upload_document(request):
    if request.method == "POST" and request.FILES.get("document"):
        uploaded_file = request.FILES["document"]
        
        files = {'document': uploaded_file}
        data = {'user': request.user.id}
        
        try:
            response = requests.post(
                f'{API_BASE_URL}/api_upload/',
                files=files,
                data=data,
                headers=get_headers(request)
            )
            
            if response.status_code == 201:
                response_data = response.json()
                return JsonResponse({
                    'success': True,
                    'conversation_id': response_data['conversation_id']
                })
                
            return JsonResponse(
                {'error': 'Error al subir el documento'}, 
                status=response.status_code
            )
            
        except requests.RequestException as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({"error": "No se proporcionó ningún archivo"}, status=400)

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
        
        messages.error(request, "Error al cargar el historial de conversaciones")
        return redirect('home')
        
    except requests.RequestException as e:
        messages.error(request, f"Error de conexión: {str(e)}")
        return redirect('home')

@login_required
def send_message(request, conversation_id):
    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            message_text = form.cleaned_data['text']
            
            payload = {
                'message': message_text,
                'user': request.user.id,
                'conversation': conversation_id
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
                    return JsonResponse(response.json())
                
                error_message = 'Error al enviar el mensaje'
                if response.status_code == 404:
                    error_message = 'Conversación no encontrada'
                elif response.status_code == 400:
                    error_message = response.json().get('error', error_message)
                    
                return JsonResponse({'error': error_message}, status=response.status_code)
                
            except requests.RequestException as e:
                return JsonResponse(
                    {'error': 'Error de conexión al enviar el mensaje'}, 
                    status=500
                )

    return JsonResponse({'error': 'Petición inválida'}, status=400)