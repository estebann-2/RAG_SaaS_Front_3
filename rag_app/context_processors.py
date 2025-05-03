from .models import Conversation

def conversation_history(request):
    if request.user.is_authenticated:
        return {"conversations": Conversation.objects.filter(user=request.user).order_by("-created_at")}
    return {"conversations": []}
