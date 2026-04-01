from django.http import JsonResponse
from chatbot.service import chatbot_response


def chatbot_api(request):
    query = request.GET.get("q")

    if not query:
        return JsonResponse({"error": "No query provided"}, status=400)

    answer = chatbot_response(query)

    return JsonResponse({
        "question": query,
        "answer": answer
    })