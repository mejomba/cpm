from django.shortcuts import render


def home(request, *args, **kwargs):
    "return spa page from _template/core/spa.html"
    return render(request, "core/spa.html", context={})