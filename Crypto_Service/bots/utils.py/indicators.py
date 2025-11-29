# indicators.py
import pandas as pd
import pandas_ta as ta
from typing import Optional

class IndicatorCalculator:
    """Расчет технических индикаторов"""
    
    @staticmethod
    def calculate(indicator_type: str, df: pd.DataFrame, period: int, extra_params: dict = None) -> Optional[float]:
        """Универсальный метод расчета индикатора"""
        if extra_params is None:
            extra_params = {}
        
        if len(df) < period + 10:
            return None
        
        try:
            if indicator_type == 'RSI':
                result = ta.rsi(df['close'], length=period)
                return float(result.iloc[-1]) if not pd.isna(result.iloc[-1]) else None
            
            elif indicator_type == 'CCI':
                result = ta.cci(df['high'], df['low'], df['close'], length=period)
                return float(result.iloc[-1]) if not pd.isna(result.iloc[-1]) else None
            
            elif indicator_type == 'STOCH_RSI':
                stoch_rsi = ta.stochrsi(df['close'], length=period)
                k_col = f'STOCHRSIk_{period}_14_3_3'
                if k_col in stoch_rsi.columns:
                    return float(stoch_rsi[k_col].iloc[-1]) if not pd.isna(stoch_rsi[k_col].iloc[-1]) else None
                return None
            
            elif indicator_type == 'WILLIAMS_R':
                result = ta.willr(df['high'], df['low'], df['close'], length=period)
                return float(result.iloc[-1]) if not pd.isna(result.iloc[-1]) else None
            
            elif indicator_type == 'MFI':
                result = ta.mfi(df['high'], df['low'], df['close'], df['volume'], length=period)
                return float(result.iloc[-1]) if not pd.isna(result.iloc[-1]) else None
            
            elif indicator_type == 'BB_PBAND':
                std = extra_params.get('std', 2.0)
                bb = ta.bbands(df['close'], length=period, std=std)
                pband_col = f'BBP_{period}_{std}'
                if pband_col in bb.columns:
                    return float(bb[pband_col].iloc[-1]) if not pd.isna(bb[pband_col].iloc[-1]) else None
                return None
            
            elif indicator_type == 'VOL_SMA':
                vol_sma = df['volume'].rolling(window=period).mean()
                ratio = df['volume'] / vol_sma
                return float(ratio.iloc[-1]) if not pd.isna(ratio.iloc[-1]) else None
            
            return None
        
        except Exception as e:
            print(f"Ошибка расчета {indicator_type}: {e}")
            return None
