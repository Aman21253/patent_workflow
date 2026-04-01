# # from django.http import JsonResponse
# from django.shortcuts import render
# from .models import Patent

from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q

from .models import Patent, Recommendation
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .rag import ask_rag

def patents_page(request):
    patents = Patent.objects.all().prefetch_related("attorneys_map__attorney")[:50]

    return render(request, "core/patents.html", {
        "patents": patents
    })

# 📄 LIST PAGE
def patents_list(request):
    query = request.GET.get("q", "")

    patents = Patent.objects.all().prefetch_related(
        "attorneys_map__attorney"
    )

    # 🔥 FIX: ORDERING (IMPORTANT)
    patents = patents.order_by("-application_id")

    # 🔍 SEARCH
    if query:
        patents = patents.filter(
            Q(title__icontains=query) |
            Q(applicant_name__icontains=query) |
            Q(inventor_name__icontains=query) |
            Q(gau__icontains=query)
        )

    # 📄 PAGINATION
    paginator = Paginator(patents, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "core/patents_list.html", {
        "page_obj": page_obj,
        "query": query
    })


def patent_detail(request, application_id):
    patent = get_object_or_404(Patent, application_id=application_id)

    attorneys = [
        pa.attorney for pa in patent.attorneys_map.select_related("attorney")
    ]

    recommendations = []
    if patent.gau:
        recommendations = Recommendation.objects.filter(
            gau=patent.gau
        ).select_related("attorney").order_by("-success_rate")[:5]

    return render(request, "core/patent_detail.html", {
        "patent": patent,
        "attorneys": attorneys,
        "recommendations": recommendations
    })

def recommendation_view(request):
    gau = request.GET.get("gau")

    if gau:
        data = Recommendation.objects.filter(gau=gau).order_by("-success_rate")[:10]
    else:
        data = Recommendation.objects.all().order_by("-success_rate")[:10]

    return render(request, "core/recommendations.html", {"data": data, "gau": gau})

@csrf_exempt
def chatbot_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
        question = body.get("question", "").strip()
    except Exception as e:
        return JsonResponse({"error": f"Invalid JSON: {e}"}, status=400)

    if not question:
        return JsonResponse({"error": "Question is empty"}, status=400)

    try:
        answer = ask_rag(question)
        return JsonResponse({"answer": answer})
    except Exception as e:
        print(f"[Chatbot API Error] {e}")
        return JsonResponse({"error": str(e)}, status=500)
    
@csrf_exempt
def recommend_attorneys_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
        patent_name = body.get("patent_name", "").strip()
    except Exception as e:
        return JsonResponse({"error": f"Invalid JSON: {e}"}, status=400)

    if not patent_name:
        return JsonResponse({"error": "patent_name is required"}, status=400)

    # Search patent by title (fuzzy match)
    patent = Patent.objects.filter(
        Q(title__icontains=patent_name) |
        Q(application_id__icontains=patent_name)
    ).first()

    if not patent:
        return JsonResponse({
            "attorneys": [],
            "message": f"No patent found matching '{patent_name}'. Try a different name or application ID."
        })

    # Get attorney recommendations based on GAU
    recommendations = []
    if patent.gau:
        recs = Recommendation.objects.filter(
            gau=patent.gau
        ).select_related("attorney").order_by("-success_rate")[:5]

        recommendations = [
            {
                "name": rec.attorney.name,  # adjust field name if different
                "success_rate": float(rec.success_rate),
            }
            for rec in recs
        ]

    # Fallback: attorneys directly assigned to the patent
    if not recommendations:
        assigned = [
            pa.attorney for pa in patent.attorneys_map.select_related("attorney")
        ]
        recommendations = [
            {"name": a.name, "success_rate": 0.0}
            for a in assigned
        ]

    return JsonResponse({
        "patent_title": patent.title,
        "gau": patent.gau,
        "attorneys": recommendations,
    })