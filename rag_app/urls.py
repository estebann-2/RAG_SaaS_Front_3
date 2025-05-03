from django.urls import path
from .views import (
    login_view, logout_view, home, 
    start_conversation, conversation_detail, send_message, 
    upload_document, conversation_history
)

urlpatterns = [
    # Authentication Routes
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),

    # Home
    path('', home, name='home'),

    # Conversations
    path('conversation/new/', start_conversation, name='start_conversation'),
    path('conversation/<int:conversation_id>/', conversation_detail, name='conversation_detail'),
    path('conversation/<int:conversation_id>/send/', send_message, name='send_message'),
    path('conversation/history/', conversation_history, name='conversation_history'),

    # Documents
    path("document/upload/", upload_document, name="upload_document"),
]

