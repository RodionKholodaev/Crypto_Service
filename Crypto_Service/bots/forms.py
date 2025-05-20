from django import forms
from django.forms import inlineformset_factory
from .models import Bot, Indicator, ExchangeAccount

class IndicatorForm(forms.ModelForm):
    # списки для ChoiceField
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
    
    # связь с бд и указание полей
    class Meta:
        model = Indicator
        fields = ['indicator_type', 'timeframe']
        # указываем какие поля модели не нужно включать в форму
        exclude = ['parameters']
    
    # метод для сохранения данных в бд
    def save(self, commit=True):
        # через super() обращаемся к родительскому классу у indicator (models.Model) и у него вызываем метод save()
        # сначала не сохраняем данные, что бы добавить поле parameters (пока не понял почему)
        indicator = super().save(commit=False)
        # заполняем поле parameters
        indicator.parameters = {
            'condition': self.cleaned_data['condition'],
            'value': self.cleaned_data['value']
        }
        # сохраняем данные в бд, так как commit=True
        if commit:
            indicator.save()
        return indicator

IndicatorFormSet = inlineformset_factory(  # обработка формы, которая появляется по кнопке (inline формы)
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
    
    base_currency = forms.ChoiceField(choices=BASE_CURRENCY_CHOICES, label="Базовая валюта")
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
            trading_pair = self.instance.trading_pair
            if trading_pair:
                # Удаляем 'USDT' из конца строки
                base = trading_pair[:-4]  # предполагаем формат XXXXXUSDT
                
                base_choices = dict(self.BASE_CURRENCY_CHOICES)
                if base not in base_choices:
                    self.fields['base_currency'].initial = 'CUSTOM'
                    self.fields['custom_currency'].initial = base
                else:
                    self.fields['base_currency'].initial = base
    
    def clean(self):
        cleaned_data = super().clean()
        base_currency = cleaned_data.get('base_currency')
        custom_currency = cleaned_data.get('custom_currency')
        
        # Handle custom currency
        if base_currency == 'CUSTOM':
            if not custom_currency:
                self.add_error('custom_currency', 'Пожалуйста, введите код валюты')
            else:
                cleaned_currency = custom_currency.strip().upper()
                if cleaned_currency == 'USDT':
                    self.add_error('custom_currency', 'Базовая валюта не может быть USDT')
                cleaned_data['base_currency'] = cleaned_currency
        
        # котируемая валюта USDT
        cleaned_data['trading_pair'] = f"{cleaned_data.get('base_currency')}USDT"
        
        return cleaned_data