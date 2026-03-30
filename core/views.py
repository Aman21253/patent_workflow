# # from django.http import JsonResponse
# from django.shortcuts import render
# from .models import Patent

from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q

from .models import Patent, Recommendation

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
    patent = Patent.objects.get(application_id=application_id)

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