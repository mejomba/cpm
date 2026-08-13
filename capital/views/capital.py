from django.shortcuts import render
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

from capital.models.user_asset import UserAsset


def my_capital_list(request, *args, **kwargs):
    return render(request, "capital/my_list.html", context={})


@csrf_exempt
def datatable_api(request):
    if request.method == 'GET':
        # دریافت داده‌ها
        queryset = UserAsset.objects.all()
        
        # جستجوی سراسری
        search = request.GET.get('search', '')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        # فیلترهای ستونی
        for key, value in request.GET.items():
            if key.startswith('filter_'):
                field = key[7:]
                queryset = queryset.filter(**{f'{field}__icontains': value})
        
        # مرتب‌سازی
        sort = request.GET.get('sort')
        order = request.GET.get('order', 'asc')
        if sort:
            if order == 'desc':
                sort = f'-{sort}'
            queryset = queryset.order_by(sort)
        
        # صفحه‌بندی
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        # تبدیل به JSON
        data = [{
            'id': item.id,
            'asset__title': item.asset.title,
            'quantity': round(item.quantity, item.asset.max_decimal_point),
            'price_sar_be_sar': item.price_sar_be_sar, 
            'price_buy': item.price_buy, 
            'created_at': item.created_at, 
            'description': item.description
            # ... سایر فیلدها
        } for item in page_obj]
        
        return JsonResponse({
            'results': data,
            'count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page
        })
    
    elif request.method == 'PATCH':
        # ویرایش ردیف
        data = json.loads(request.body)
        # ...
        return JsonResponse({'status': 'success'})
    

@csrf_exempt
def capital_detail_api(request, id):
    obj = UserAsset.objects.get(pk=id)
    data = {
        "شناسه": obj.pk,
        "عنوان": obj.asset.title,
        "زمان ایجاد": obj.jcreated_at,
        "قیمت سر به سر": round(obj.price_sar_be_sar, obj.asset.max_decimal_point),
        "قیمت خرید": round(obj.price_buy, obj.asset.max_decimal_point)
    }

    return JsonResponse(data)