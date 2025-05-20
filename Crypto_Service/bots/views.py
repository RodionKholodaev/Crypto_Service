from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import BotForm, IndicatorFormSet
from .models import Bot, ExchangeAccount

@login_required
def create_bot(request):
    if request.method == 'POST':
        form = BotForm(request.user, request.POST)
        formset = IndicatorFormSet(request.POST, instance=None)
        
        if form.is_valid():
            bot = form.save(commit=False)
            bot.user = request.user
            bot.save()
            
            # Save indicators
            formset = IndicatorFormSet(request.POST, instance=bot)
            if formset.is_valid():
                formset.save()
            
            return redirect('home')
    else:
        form = BotForm(user=request.user)
        formset = IndicatorFormSet(instance=None)
    
    exchange_accounts = ExchangeAccount.objects.filter(user=request.user, is_active=True)
    return render(request, 'bots/bot_conf.html', {
        'form': form,
        'formset': formset,
        'exchange_accounts': exchange_accounts
    })

@login_required
def edit_bot(request, bot_id):
    bot = Bot.objects.get(id=bot_id, user=request.user)
    
    if request.method == 'POST':
        form = BotForm(request.user, request.POST, instance=bot)
        formset = IndicatorFormSet(request.POST, instance=bot)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect('bot_detail', bot_id=bot.id)
    else:
        form = BotForm(request.user, instance=bot)
        formset = IndicatorFormSet(instance=bot)
    
    exchange_accounts = ExchangeAccount.objects.filter(user=request.user, is_active=True)
    return render(request, 'bots/bot_conf.html', {
        'form': form,
        'formset': formset,
        'exchange_accounts': exchange_accounts,
        'editing': True
    })