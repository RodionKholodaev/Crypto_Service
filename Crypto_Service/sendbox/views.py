from django.shortcuts import render

def demo(request):
    return render(request, 'sendbox/demo.html')