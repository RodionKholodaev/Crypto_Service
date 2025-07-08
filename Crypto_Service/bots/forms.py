from django import forms
from django.forms import inlineformset_factory
from .models import Bot, Indicator, ExchangeAccount

class IndicatorForm(forms.ModelForm):
    # списки для ChoiceField
    INDICATOR_CHOICES = [
        ('RSI', 'Relative Strength Index'),
        ('CCI', 'Commodity Channel Index'),
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
        # сначала не сохраняем данные, что бы добавить поле parameters (это нужно потому что parameters собирает значение из двух полей)
        indicator = super().save(commit=False)
        # заполняем поле parameters
        # собираем parameters и только потом сохраняем это в бд
        # это частая практика
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
    
    # виртуальные поля формы которых нет в модели
    # из этих полей мы собираем 
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
        # запуск __init__ родительской формы
        super().__init__(*args, **kwargs)
        # выбирает api ключи пользователя и is_active=True

        # QuerySet — это специальный объект в Django. Он обращается к бд но не сразу
        # каждое поле что связано с моделью имее атрибут queryset
        #  в этом поле мы меняем queryset для exchange_account чтобы там были только активные аккаунты пользователя
        # ExchangeAccount.objects.filter(...) возвращает стуктуру QuerySet
        # ExchangeAccount.objects.filter(...) - замена кода sql
        # из этого набора будет формироваться списко в выподающей html форме
        self.fields['exchange_account'].queryset = ExchangeAccount.objects.filter(user=user, is_active=True)
        
        # проверка, редактируем ли мы бот или создаем
        # instance - экземпляр модели с которой работает modelform
        # если форма создается для редактирования существубщего обекта, то в instance будут его поля
        # если объект пока не существует, то в self.instance будет None
        # что есть в instance:
        # pk, save(), delete(), id, все поля модели
        # initial - начальные значения для полей формы
        # в коде это используется для передачи с имеющихся данных при редактировании
        # pk - уникальный индентификатор записи в таблице
        # если pk существует -> объект сохранен в бд
        # если pk=None -> обект пока не существует

        if self.instance.pk:
            trading_pair = self.instance.trading_pair
            # есть ли у бота trading_pair
            if trading_pair:
                # Удаляем 'USDT' из конца строки
                base = trading_pair[:-4]  # предполагаем формат XXXXXUSDT
                
                # преобразуем список из кортежей с словарь
                base_choices = dict(self.BASE_CURRENCY_CHOICES)
                
                # проверяем есть ли валюта в BASE_CURRENCY_CHOICES
                if base not in base_choices:
                    self.fields['base_currency'].initial = 'CUSTOM'
                    self.fields['custom_currency'].initial = base
                else:
                    self.fields['base_currency'].initial = base
    
    def save(self, commit=True):
        bot = super().save(commit=False)
        # Устанавливаем trading_pair из cleaned_data
        bot.trading_pair = self.cleaned_data.get('trading_pair')
        if commit:
            bot.save()
        return bot


    def clean(self):
        # super().clean() проверяет валидность всех полей, возвращает словарь с приведенными к правильному типу значениями
        cleaned_data = super().clean()
        base_currency = cleaned_data.get('base_currency')
        custom_currency = cleaned_data.get('custom_currency')
        
        # работа с введенной валютой
        # проверяет введена ли CUSTOM валюта
        if base_currency == 'CUSTOM':
            # проверяет не пустое ли поле
            if not custom_currency:
                # вывод ошибки
                # словарь ошибок в forms.ModelForm
                self.add_error('custom_currency', 'Пожалуйста, введите код валюты')
            else:
                # .strip() удаляет пробелы .upper() приводит к верхнему регистру 
                cleaned_currency = custom_currency.strip().upper()
                # проверка на base=USDT
                if cleaned_currency == 'USDT':
                    self.add_error('custom_currency', 'Базовая валюта не может быть USDT')
                cleaned_data['base_currency'] = cleaned_currency
        
        # котируемая валюта USDT
        # записываем trading_pair в cleaned_data
        cleaned_data['trading_pair'] = f"{cleaned_data.get('base_currency')}USDT"
        
        return cleaned_data
    

