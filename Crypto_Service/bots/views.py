from django.shortcuts import render, redirect

def bot_conf(request):
    return render(request,'bots/bot_conf.html')
        
