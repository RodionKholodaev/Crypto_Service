from django import forms
from django.forms import inlineformset_factory
from .models import Bot, Indicator, ExchangeAccount

class IndicatorForm(forms.ModelForm):
    INDICATOR_CHOICES = [
        ('RSI', 'Relative Strength Index'),
        ('MACD', 'Moving Average Convergence Divergence'),
        ('MA', 'Moving Average'),
        ('BOLL', 'Bollinger Bands'),
        ('STOCH', 'Stochastic'),
    ]
    
    TIMEFRAME_CHOICES = [
        ('1m', '1 минута'),
        ('5m', '5 минут'),
        ('15m', '15 минут'),
        ('30m', '30 минут'),
        ('1h', '1 час'),
        ('4h', '4 часа'),
        ('1d', '1 день'),
    ]
    
    CONDITION_CHOICES = [
        ('lt', '<'),
        ('lte', '<='),
        ('gt', '>'),
        ('gte', '>='),
    ]
    
    indicator_type = forms.ChoiceField(choices=INDICATOR_CHOICES, label="Индикатор")
    timeframe = forms.ChoiceField(choices=TIMEFRAME_CHOICES, label="Таймфрейм")
    condition = forms.ChoiceField(choices=CONDITION_CHOICES, label="Условие")
    value = forms.FloatField(label="Значение")
    
    class Meta:
        model = Indicator
        fields = ['indicator_type', 'timeframe']
        exclude = ['parameters']
    
    def save(self, commit=True):
        indicator = super().save(commit=False)
        indicator.parameters = {
            'condition': self.cleaned_data['condition'],
            'value': self.cleaned_data['value']
        }
        if commit:
            indicator.save()
        return indicator

IndicatorFormSet = inlineformset_factory(
    Bot, Indicator, 
    form=IndicatorForm,
    extra=1,
    can_delete=True
)

class BotForm(forms.ModelForm):
    BASE_CURRENCY_CHOICES = [
        ('BTC', 'BTC'),
        ('ETH', 'ETH'),
        ('BNB', 'BNB'),
        ('SOL', 'SOL'),
        ('XRP', 'XRP'),
        ('CUSTOM', 'Другая'),
    ]
    
    QUOTE_CURRENCY_CHOICES = [
        ('USDT', 'USDT'),
        ('BUSD', 'BUSD'),
        ('BTC', 'BTC'),
        ('ETH', 'ETH'),
        ('CUSTOM', 'Другая'),
    ]
    
    base_currency = forms.ChoiceField(choices=BASE_CURRENCY_CHOICES, label="Базовая валюта")
    quote_currency = forms.ChoiceField(choices=QUOTE_CURRENCY_CHOICES, label="Котируемая валюта")
    custom_currency = forms.CharField(required=False, label="Пользовательская валюта")
    
    class Meta:
        model = Bot
        fields = [
            'exchange_account', 'name', 'deposit', 'strategy', 
            'bot_leverage', 'take_profit_percent', 'stop_loss_percent',
            'grid_orders_count', 'grid_overlap_percent'
        ]
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['exchange_account'].queryset = ExchangeAccount.objects.filter(user=user, is_active=True)
        
        if self.instance.pk:
            # If editing existing bot, set initial values for currency fields
            trading_pair = self.instance.trading_pair
            if trading_pair:
                # Simple parsing - assumes 3-4 character currencies
                base = trading_pair[:3] if len(trading_pair) == 6 else trading_pair[:4]
                quote = trading_pair[3:] if len(trading_pair) == 6 else trading_pair[4:]
                
                # Check if base is in our choices
                base_choices = dict(self.BASE_CURRENCY_CHOICES)
                if base not in base_choices:
                    self.fields['base_currency'].initial = 'CUSTOM'
                    self.fields['custom_currency'].initial = base
                else:
                    self.fields['base_currency'].initial = base
                
                # Check if quote is in our choices
                quote_choices = dict(self.QUOTE_CURRENCY_CHOICES)
                if quote not in quote_choices:
                    self.fields['quote_currency'].initial = 'CUSTOM'
                    self.fields['custom_currency'].initial = quote
                else:
                    self.fields['quote_currency'].initial = quote
    
    def clean(self):
        cleaned_data = super().clean()
        base_currency = cleaned_data.get('base_currency')
        quote_currency = cleaned_data.get('quote_currency')
        custom_currency = cleaned_data.get('custom_currency')
        
        # Handle custom currency
        if base_currency == 'CUSTOM':
            if not custom_currency:
                self.add_error('custom_currency', 'Пожалуйста, введите код валюты')
            else:
                cleaned_data['base_currency'] = custom_currency.strip().upper()
        
        if quote_currency == 'CUSTOM':
            if not custom_currency:
                self.add_error('custom_currency', 'Пожалуйста, введите код валюты')
            else:
                cleaned_data['quote_currency'] = custom_currency.strip().upper()
        
        # Create trading pair
        cleaned_data['trading_pair'] = f"{cleaned_data.get('base_currency')}{cleaned_data.get('quote_currency')}"
        
        return cleaned_data
    
    def save(self, commit=True):
        bot = super().save(commit=False)
        bot.trading_pair = self.cleaned_data['trading_pair']
        
        if commit:
            bot.save()
        
        return bot