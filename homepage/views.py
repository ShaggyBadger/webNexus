from django.shortcuts import render


def index(request):
    return render(request, "homepage/index.html")


def about(request):
    return render(request, "homepage/about.html")


def contact(request):
    return render(request, "homepage/contact.html")
