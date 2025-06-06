import matplotlib.pyplot as plt
from bots.models import Deal
import os
from django.conf import settings

def generate_pnl_chart(bot_id, output_path):
    """Генерация графика PNL для бота."""
    deals = Deal.objects.filter(bot_id=bot_id).order_by('created_at')
    if not deals.exists():
        return None
    
    dates = [deal.created_at for deal in deals]
    pnls = [float(deal.pnl) for deal in deals]
    
    plt.figure(figsize=(10, 6))
    plt.plot(dates, pnls, 'b-', label='PNL')
    plt.title('Прибыль и убытки по сделкам')
    plt.xlabel('Дата')
    plt.ylabel('PNL (USDT)')
    plt.grid(True)
    plt.legend()
    
    output_file = os.path.join(settings.MEDIA_ROOT, output_path)
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    plt.savefig(output_file)
    plt.close()
    return output_path