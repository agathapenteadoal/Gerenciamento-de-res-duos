# utilidades.py
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from math import isnan
import pandas as pd

Q2 = Decimal("0.01")
PT_ABREV_LIST = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]

def _dec(s, default=Decimal("0")):
    if s is None: return default
    try:
        st = str(s).strip().replace(" ", "")
        if st == "" or st.lower() in ("nan", "none"): return default
        if "," in st and "." in st: st = st.replace(".", "").replace(",", ".")
        else: st = st.replace(",", ".")
        return Decimal(st)
    except Exception:
        try: return Decimal(str(s))
        except Exception: return default

def money_pt(s) -> Decimal: 
    return _dec(s, Decimal("0"))

def fmt_moeda(val) -> str:
    try: d = _dec(val, Decimal("0")).quantize(Q2, rounding=ROUND_HALF_UP)
    except Exception: d = Decimal("0").quantize(Q2)
    s = f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

def fmt_kg(val) -> str:
    try: d = _dec(val, Decimal("0"))
    except Exception: return "0 kg"
    s = f"{d:.3f}".rstrip("0").rstrip(".")
    if "." in s:
        pi, pd_part = s.split("."); pi = f"{int(pi):,}".replace(",", "."); s = f"{pi},{pd_part}"
    else: s = f"{int(s):,}".replace(",", ".")
    return f"{s} kg"

def clean_str(x):
    if x is None: return ""
    try:
        if isinstance(x, (float, Decimal)) and isnan(float(x)): return ""
    except Exception: pass
    s = str(x).strip()
    return "" if s.lower() in ("nan", "none") else s

def tag_por_estado(estado_val: str):
    s = clean_str(estado_val).lower()
    if "s" in s or "solido" in s or "sólido" in s: return "estado_solido"
    elif "l" in s or "liquido" in s or "líquido" in s: return "estado_liquido"
    return None

def to_float_safe(x, default=0.0):
    d = _dec(x, Decimal(str(default)))
    try: return float(d)
    except Exception: return float(default)

def format_data_ptbr_abbrev(dt_series):
    if not isinstance(dt_series, pd.Series): dt_series = pd.Series(dt_series)
    dt_series_parsed = pd.to_datetime(dt_series, errors="coerce")
    def format_date_cell(dt):
        if pd.isna(dt): return ""
        try: mes_abrev = PT_ABREV_LIST[dt.month - 1]; return f"{dt.day:02d}/{mes_abrev}/{dt.year % 100:02d}"
        except Exception: return ""
    return dt_series_parsed.apply(format_date_cell)

def normalizar(texto):
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^A-Za-z0-9]', '', texto).upper()

def get_df_com_peso_real(df):
    if df.empty:
        df['Peso_KG_Real'] = 0.0
        return df
    df_calc = df.copy()
    def calcular_peso(row):
        modo = clean_str(row.get('Modo', 'kg')).lower()
        if modo == 'unidade': return to_float_safe(row.get('PesoEmKg', 0.0))
        else: return to_float_safe(row.get('Peso', 0.0))
    df_calc['Peso_KG_Real'] = df_calc.apply(calcular_peso, axis=1)
    return df_calc

def filtrar_combobox(event, lista_completa):
    if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Tab', 'Escape', 'BackSpace'):
        if event.keysym != 'BackSpace': return
    texto = event.widget.get().lower()
    if texto == "": event.widget['values'] = lista_completa
    else:
        filtrados = [item for item in lista_completa if texto in item.lower()]
        event.widget['values'] = filtrados

def pular_para_letra(event):
    tecla = event.char.lower()
    if not tecla.isalnum(): return
    widget = event.widget
    valores = widget['values']
    for i, item in enumerate(valores):
        if str(item).lower().startswith(tecla):
            widget.current(i)
            widget.event_generate("<<ComboboxSelected>>")
            return

def configurar_autocomplete(combobox, lista_completa):
    def on_keyrelease(event):
        if event.keysym in ('Up', 'Down', 'Return', 'Tab', 'Left', 'Right'): return
        texto_digitado = combobox.get().lower()
        if texto_digitado == "": combobox['values'] = lista_completa
        else:
            filtrados = [item for item in lista_completa if texto_digitado in str(item).lower()]
            combobox['values'] = filtrados
        if combobox['values']:
            try: combobox.event_generate('<Down>')
            except: pass
    combobox.bind('<KeyRelease>', on_keyrelease)
    def on_click(event): combobox['values'] = lista_completa
    combobox.bind('<Button-1>', on_click)
