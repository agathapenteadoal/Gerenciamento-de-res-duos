# -*- coding: utf-8 -*-
import os
import re
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP, getcontext
from math import isnan
import unicodedata
import locale
import calendar
import holidays

# --- Imports Atualizados para PDF ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, Frame, PageTemplate, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
import io

import pandas as pd
import openpyxl
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.ticker as mtick
from matplotlib.ticker import MaxNLocator
import numpy as np
from pandas.tseries.offsets import MonthEnd

import tkinter as tk
from tkinter import simpledialog, ttk, filedialog
from tkinter import messagebox as tk_msg

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.widgets import DateEntry
from ttkbootstrap.dialogs import Messagebox

import copy
from openpyxl import load_workbook
from openpyxl.utils.cell import get_column_letter

import fitz  # PyMuPDF
import tkinter.filedialog as fd # Para selecionar arquivos

import database as db # Importa o módulo database.py

import pdfplumber

import threading
import queue

import calculos

from tkcalendar import Calendar

import shutil

from PIL import Image, ImageTk
from componentes import ModernMessageBox, CalendarioPremium, obter_data_segura
from telas_secundarias import abrir_gestao_feriados

from tkinter import simpledialog, ttk, filedialog

# =======================================================
# INTERCEPTADOR DE MENSAGENS (POP-UPS MODERNOS)
# =======================================================
class ModernMessageBox:
    @staticmethod
    def showerror(title, message, **kwargs):
        tk_msg.showerror(title, message)

    @staticmethod
    def showinfo(title, message, **kwargs):
        tk_msg.showinfo(title, message)

    @staticmethod
    def showwarning(title, message, **kwargs):
        tk_msg.showwarning(title, message)

    @staticmethod
    def askyesno(title, message, **kwargs):
        return tk_msg.askyesno(title, message)
# =======================================================

# --- DEFINIÇÕES GLOBAIS ---
meses_lista = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

mapa_meses_num = {
    "Janeiro": "01", "Fevereiro": "02", "Março": "03", "Abril": "04", "Maio": "05", "Junho": "06",
    "Julho": "07", "Agosto": "08", "Setembro": "09", "Outubro": "10", "Novembro": "11", "Dezembro": "12"
}

# Mapa reverso para jan/25 -> Janeiro
mapa_meses_sigla_inv = {
    "jan": "Janeiro", "fev": "Fevereiro", "mar": "Março", "abr": "Abril", "mai": "Maio", "jun": "Junho",
    "jul": "Julho", "ago": "Agosto", "set": "Setembro", "out": "Outubro", "nov": "Novembro", "dez": "Dezembro"
}

# Alteração: Carregar 3 anos (1095 dias) para incluir todo o histórico de 2025 e 2024
DATA_CORTE_ISO = '2023-01-01'

def resource_path(relative_path):
    """ Retorna o caminho absoluto, correto tanto para dev quanto para PyInstaller """
    try:
        # PyInstaller cria uma pasta temporária e armazena o caminho em _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

esg_result_queue = queue.Queue()
geracao_result_queue = queue.Queue()

# Meses (O primeiro item deve ser vazio, pois os meses vão de 1 a 12)
calendar.month_name = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
calendar.month_abbr = ['', 'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

# Dias da Semana
calendar.day_name = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
calendar.day_abbr = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

# Locale
try: locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    try: locale.setlocale(locale.LC_TIME, 'pt_BR')
    except locale.Error: print("Aviso: locale pt_BR não ativado.")

try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'pt_BR')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil') # Tenta padrão Windows
        except:
            print("Aviso: locale pt_BR não ativado. Dias da semana podem ficar em Inglês.")

class CalendarFix(Calendar):
    def __init__(self, master=None, **kw):
        # Remove conflitos de estilo do bootstrap
        if 'style' in kw:
            del kw['style']
            
        self._properties = {} 
        super().__init__(master, **kw)
        
        # AGENDA A CORREÇÃO:
        # Espera 100ms para o calendário ser desenhado e então
        # aplica nossa correção manual nos cabeçalhos.
        self.after(100, self.force_header_fix)

    def force_header_fix(self):
        """Força o texto e o estilo dos dias da semana manualmente."""
        # Dias da semana em Português (Hardcoded para garantir)
        dias_pt = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
        
        # A lista _week_days contém os objetos Label dos dias (interno do tkcalendar)
        if hasattr(self, '_week_days'):
            for i, label in enumerate(self._week_days):
                # 1. Força o Texto (caso o locale tenha falhado)
                label.configure(text=dias_pt[i])
                
                # 2. Força um Estilo Funcional do Bootstrap
                # 'inverse-secondary' geralmente é Cinza Escuro com Texto Branco.
                # Isso "destrava" o layout que estava colapsado.
                try:
                    label.configure(style="secondary.Inverse.TLabel")
                except:
                    # Fallback se o estilo não existir
                    label.configure(style="TLabel")
                
                # 3. Ajuste fino de geometria (caso precise)
                label.configure(width=4, anchor="center")

    def configure(self, cnf=None, **kw):
        if 'style' in kw: del kw['style']
        if cnf is None: return super().configure(**kw)
        return super().configure(cnf, **kw)

    def __setitem__(self, key, value):
        if key == 'style': return
        super().__setitem__(key, value)

# =========================
# Config / Colunas UI
# =========================
COLUMNS_DISPLAY = [ "Data","Parceiro","Resíduo","Estado","Destinação","Tipo", "Peso","Valor por kg/unidade","Valor fechado", "Valor Total", "Transporte", "Pedido de Compra", "Certificado OK", "NF OK"]# =========================
DEFAULT_DESTINACOES = [ "Reciclagem","Blendagem para coprocessamento","Compostagem","Incineração", "Tratamento de efluentes","N/A","Logística reversa" ]
PT_ABREV_LIST = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]
DATA_HOJE_GLOBAL = datetime.now().date()
DATA_INICIO_MES_GLOBAL = DATA_HOJE_GLOBAL.replace(day=1)
# Vamos usar "Início do Ano" como padrão para a Aba Registros
DATA_INICIO_ANO_GLOBAL = DATA_HOJE_GLOBAL.replace(day=1, month=1)

mapa_produtos_app = {
    "FRESACOMCOBRE8": "Fresa sem ouro",
    "FRESACOMCOBRE12356": "Placa sem ouro",
    "COBRELIMPO": "Cobre",
    "METAISNAOFERROSOSALUMINIOOFFSET": "Alumínio",
    "METAISNAOFERROSOSALUMINIOPERFIL": "Alumínio perfil",
    "METAISNAOFERROSOSALUMINIODURO": "Alumínio duro",
    "PAPELAOLIMPO": "Papelão",
    "PLASTICOSPESTRETCH": "Plástico",
    "PLASTICOSABSMISTO": "Plástico",
    "PLASTICOSMISTO": "Mylar",
    "EMBALAGENSPLASTICO": "Mylar",
    "MADEIRAMISTA": "Madeira",
    "MADEIRASMISTOFRAGMENTO": "Madeira",
    "MADEIIRAMISTA": "Madeira",
    "EMBALAGENSMADEIRA": "Madeira",
    "FRESACOMOUROAAU4": "Placa com ouro",
    "FRESACOMOURONOVOB": "Fresa com ouro",
    "FILETEDECOBRE7": "Filete de cobre",
    "FR4COMCOBRE6": "FR-4 com cobre",
    "METAISFERROSOSFERROMISTO": "Sucata de ferro", 
    "ELETROELETRONICOSLOTEMISTO": "Sucata mista", 
    "ACUMULELETRICOSPILHASEBATERIASLO": "Pilhas", 
    "PLACASMEDIUMGRADEAMISTO": "Placa com componentes",
    "BROCASFRESASDEACO": "Brocas de aço",
    "METAISNAOFERROSOSALUMINIOLATINHA": "Alumínio latinha",
    "ACUMULELETRICOSPILHASEBATERIASLOTEMISTO": "Pilhas",
    "ACUMULELETRICOSPILHASEBATERIASLO": "Pilhas",
    "MOTORESELETRICOSCCOBRE": "Motor elétrico com cobre",
    "SUCATADECPU": "Sucata de CPU",
    "CELULARESMARTPHONESEMBATERIA": "Sucata de celular",
    "FIOSECABOSMISTOS": "Fios de cobre",
    "NAOELETRONICOSPRODUTOSRECICLAVEISSECOS": "Fibra de vidro",
    "PAPELECARTAOPAPELAO": "Papel para descaracterização",
    "APARELHODEARCONDICIONADOCHILLER": "Sucata de ar condicionado",
    "BROCASFRESASDEMETALDURO": "Fresa (ferramenta)",
    "METAISFERROSOSACOINOXLIMPO": "Sucata de inox",
    "SUCATAMISTAAPARINCOMPLETOS": "Sucata mista",
    "ALUMINIOOFFSET": "Alumínio",
    "FILMEPLASTICOSTRETCH": "Plástico",
    "MADEIRADEQUALQUERTIPO": "Madeira",
    "PAPELAO": "Papelão",
    "PLASTICOABS": "Plástico",
    "PLASTICOSDIVERSOS": "Mylar",
    "ALUMINIOCHAPARIAMOLE": "Alumínio mole",
    "SUCATADEMETALBRONZE": "Bronze",
    "SUCATADEFERRO": "Sucata de ferro",
    "CHAPASDECOBRE": "Chapas de cobre",
    "FIOSDECOBRESEMCONECTORES": "Fios de cobre",
    "PAPELBRANCO": "Papel para descaracterização",
    "SUCATAELETRONICADEBATERIA": "Bateria",
    "FRESACOMNIQUEL": "Fresa com níquel",
    "DISJUNTOR": "Disjuntor",
    "TRAFOSENROLAMENTOEMCOBRE": "Enrolamento cobre",
    "METAISNAOFERROSOSCOBREMISTO": "Cobre misto",
    "FIOSECABOSCABOSENERGIACOBRE": "Fios de cobre",
    "L BRANCA CLIMATIZADORES AR CONDICION": "Sucata de ar condicionado",
    
}

GRUPOS_RELATORIO = sorted(["Bombonas", "Plásticos", "Mylar", "Alumínio", "Papel", "Sucata de ferro", "Fresa sem ouro", "Fresa com ouro", "Placa com ouro", "Placa sem ouro", "Cobre", "Madeira",
                    "Filme fotossensível", "Borra de tinta", "Lodo", "Sólidos contaminados", "Concentrado", "Solução amoniacal", "Solução ácida contendo cobre",
                           "Solução ácida contendo estanho"])

# =========================
# Utils / Saneamento / Formatação
# =========================
getcontext().prec = 28
Q2 = Decimal("0.01")
Q6 = Decimal("0.000001") # <-- ADICIONE ESTA LINHA

def _dec(s, default=Decimal("0")):
    """Converte uma string/número para Decimal de forma segura."""
    if s is None:
        return default

    try:
        # Tenta limpar e converter
        st = str(s).strip().replace(" ", "")
        if st == "" or st.lower() in ("nan", "none"):
            return default

        if "," in st and "." in st:
            st = st.replace(".", "").replace(",", ".")
        else:
            st = st.replace(",", ".")

        return Decimal(st)

    except Exception:
        # Se a limpeza falhar, tenta converter a string original
        try:
            return Decimal(str(s))
        except Exception:
            return default # Retorna 0 se tudo falhar

def money_pt(s) -> Decimal: return _dec(s, Decimal("0"))

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
    s = str(x).strip(); return "" if s.lower() in ("nan", "none") else s

def tag_por_estado(estado_val: str):
    s = clean_str(estado_val).lower()
    if "s" in s or "solido" in s or "sólido" in s: return "estado_solido"
    elif "l" in s or "liquido" in s or "líquido" in s: return "estado_liquido"
    return None

def to_float_safe(x, default=0.0):
    d = _dec(x, Decimal(str(default)));
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
    # Remove acentos
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto)
                    if unicodedata.category(c) != 'Mn')
    # Remove espaços, parênteses e caracteres especiais
    texto = re.sub(r'[^A-Za-z0-9]', '', texto)
    # Coloca em maiúsculas
    return texto.upper()

def get_df_com_peso_real(df):
    """Retorna uma cópia do DF com uma nova coluna 'Peso_KG_Real'
       que normaliza o peso dos modos 'unidade', 'kg' e 'fechado'."""
    if df.empty:
        df['Peso_KG_Real'] = 0.0
        return df
        
    df_calc = df.copy()
    
    def calcular_peso(row):
        modo = clean_str(row.get('Modo', 'kg')).lower()
        if modo == 'unidade':
            # Modo 'unidade' armazena o KG real em 'PesoEmKg'
            return to_float_safe(row.get('PesoEmKg', 0.0))
        else:
            # Modos 'kg' e 'fechado' armazenam o KG em 'Peso'
            return to_float_safe(row.get('Peso', 0.0))

    df_calc['Peso_KG_Real'] = df_calc.apply(calcular_peso, axis=1)
    return df_calc



def filtrar_combobox(event, lista_completa):
    """Filtra os valores da Combobox conforme o usuário digita."""
    # Ignora teclas de navegação para não atrapalhar a seleção
    if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Tab', 'Escape', 'BackSpace'):
        # Backspace deixamos passar se quiser que atualize ao apagar, 
        # mas geralmente só queremos filtrar ao digitar caracteres. 
        # Se quiser que o BackSpace atualize a lista, remova ele dessa lista de ignorados.
        if event.keysym != 'BackSpace': 
            return

    # Pega o texto digitado
    texto = event.widget.get().lower()
    
    if texto == "":
        event.widget['values'] = lista_completa
    else:
        # Cria uma lista apenas com os itens que contém o texto digitado
        filtrados = [item for item in lista_completa if texto in item.lower()]
        event.widget['values'] = filtrados
        
        # Opcional: Se quiser que a lista abra automaticamente ao digitar:
        # try: event.widget.event_generate('<Down>')
        # except: pass

def pular_para_letra(event):
    """Ao digitar, seleciona pelo ÍNDICE (faz a lista aberta rolar até o item)."""
    tecla = event.char.lower()
    
    # Ignora teclas que não sejam letras/números
    if not tecla.isalnum():
        return

    widget = event.widget
    valores = widget['values']
    
    # Procura o item e pega o NÚMERO dele na lista (índice)
    for i, item in enumerate(valores):
        if str(item).lower().startswith(tecla):
            widget.current(i) # <--- O SEGREDO: Seleciona pelo índice
            widget.event_generate("<<ComboboxSelected>>") # Dispara o preenchimento de valores
            return # Para no primeiro que encontrar (importante!)

def configurar_autocomplete(combobox, lista_completa):
    """
    Configura um Combobox para filtrar opções conforme o usuário digita.
    Versão blindada contra perda de foco e bugs do Tkinter.
    """
    def on_keyrelease(event):
        # 1. Ignora teclas de sistema/navegação para não atrapalhar
        if event.keysym in ('Up', 'Down', 'Return', 'Tab', 'Left', 'Right', 'Escape', 'Shift_L', 'Shift_R', 'Caps_Lock', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R'):
            return

        # 2. Salva exatamente o que você digitou e onde o cursor está piscando
        texto = combobox.get()
        pos = combobox.index(tk.INSERT)

        # 3. Faz o filtro da lista ignorando acentos, maiúsculas e espaços
        texto_norm = normalizar(texto)
        if texto_norm == "":
            combobox['values'] = lista_completa
        else:
            filtrados = [item for item in lista_completa if texto_norm in normalizar(str(item))]
            combobox['values'] = filtrados

        # 4. Devolve o texto para a caixa e o cursor para a posição exata
        # (Isso impede que o Tkinter apague a sua palavra ao abrir a lista)
        combobox.set(texto)
        combobox.icursor(pos)

        # 5. Abre a lista APENAS se houver resultados e não for a tecla de apagar
        if combobox['values'] and event.keysym not in ('BackSpace', 'Delete'):
            try:
                # O SEGREDO: Abre a lista de forma "silenciosa" pelo motor interno do Tcl/Tk
                combobox.tk.call('ttk::combobox::Post', combobox)
                
                # Garante 100% que a caixa de texto continue selecionada para você digitar a próxima letra
                combobox.focus_set()
            except:
                pass

    # Vincula o evento para disparar logo após a letra aparecer na tela
    combobox.bind('<KeyRelease>', on_keyrelease)
    
    # Restaura a lista ao clicar na setinha com o mouse, caso a caixa esteja vazia
    def on_click(event):
        if combobox.get() == "":
            combobox['values'] = lista_completa
            
    combobox.bind('<Button-1>', on_click)

def atualizar_tabela_metragem():
    """Recarrega a tabela em ordem crescente e formato jan/25 centralizado."""
    for item in tree_met.get_children():
        tree_met.delete(item)
    
    dados = db.get_all_metragens() 
    # Ordena pelo campo mes_ano (YYYY-MM) de forma crescente
    dados_crescente = sorted(dados, key=lambda x: x[0]) 

    siglas = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]

    for mes_ano_db, valor in dados_crescente:
        ano_full, mes_num = mes_ano_db.split("-")
        sigla = siglas[int(mes_num)-1]
        exibicao = f"{sigla}/{ano_full[2:]}" # jan/25
        
        valor_fmt = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        tree_met.insert("", "end", values=(exibicao, f"{valor_fmt} m²"))

def excluir_metragem_selecionada():
    """Exclui a linha selecionada e atualiza a tabela."""
    selecionado = tree_met.selection()
    if not selecionado:
        ModernMessageBox.showwarning("Aviso", "Selecione uma linha para excluir.")
        return
    
    if ModernMessageBox.askyesno("Confirmar", "Deseja realmente excluir esta metragem?"):
        valores = tree_met.item(selecionado)['values']
        sigla, ano_abrev = valores[0].split("/")
        mes_extenso = mapa_meses_sigla_inv.get(sigla)
        mes_num = mapa_meses_num.get(mes_extenso)
        mes_ano_db = f"20{ano_abrev}-{mes_num}"
        
        if db.delete_metragem(mes_ano_db):
            set_status("Metragem removida com sucesso.")
            atualizar_tabela_metragem()
        else:
            ModernMessageBox.showerror("Erro", "Não foi possível excluir do banco de dados.")

def carregar_metragem_para_edicao():
    """Puxa os dados da tabela para os campos de entrada."""
    selecionado = tree_met.selection()
    if not selecionado:
        ModernMessageBox.showwarning("Aviso", "Selecione uma linha para editar.")
        return
    
    valores = tree_met.item(selecionado)['values']
    sigla, ano_abrev = valores[0].split("/")
    
    var_met_mes.set(mapa_meses_sigla_inv.get(sigla))
    var_met_ano.set(f"20{ano_abrev}")
    var_met_valor.set(valores[1].replace(" m²", ""))

def salvar_metragem_dinamica():
    """Salva os dados no banco usando o formato YYYY-MM."""
    mapa_meses = {
        "Janeiro": "01", "Fevereiro": "02", "Março": "03", "Abril": "04", "Maio": "05", "Junho": "06",
        "Julho": "07", "Agosto": "08", "Setembro": "09", "Outubro": "10", "Novembro": "11", "Dezembro": "12"
    }
    
    mes_num = mapa_meses.get(var_met_mes.get())
    ano = var_met_ano.get()
    mes_ano_db = f"{ano}-{mes_num}" 
    
    try:
        # money_pt limpa "R$", pontos e vírgulas
        valor = float(money_pt(var_met_valor.get()))
        if db.add_or_update_metragem(mes_ano_db, valor):
            set_status(f"Metragem de {var_met_mes.get()}/{ano} salva!")
            atualizar_tabela_metragem()
            var_met_valor.set("")
        else:
            ModernMessageBox.showerror("Erro", "Erro ao salvar no banco.")
    except:
        ModernMessageBox.showerror("Erro", "Valor de metragem inválido.")
    
# =========================
# Inicialização DB e Estado
# =========================
db.initialize_database()
db.criar_tabela_feriados()
df_registros_global = db.get_all_registros_df(data_inicio=DATA_CORTE_ISO)
df_banco = db.get_banco_residuos()
banco_dict = {row['Residuo']: {'modo': row.get('ModoPadrao', 'kg').lower(), 'kg': to_float_safe(row.get('ValorPorKgPadrao', 0.0)), 'ton': to_float_safe(row.get('ValorPorTonPadrao', 0.0)), 'fechado': to_float_safe(row.get('ValorFechadoPadrao', 0.0))} for _, row in df_banco.iterrows()} if not df_banco.empty else {}
df_parceiros = db.get_banco_parceiros(); parceiros = df_parceiros["Parceiro"].tolist() if not df_parceiros.empty else []
df_analises = db.get_banco_analises(); lista_analises = df_analises["NomeAnalise"].tolist() if not df_analises.empty else []
banco_residuos = sorted(df_banco["Residuo"].unique().tolist()) if not df_banco.empty else []
banco_residuos_rateio = []
destinacoes_unicas = df_registros_global["Destinacao"].unique().tolist() if not df_registros_global.empty else []
destinacoes = sorted(list(set(DEFAULT_DESTINACOES + [d for d in destinacoes_unicas if d])))
EDITING_ID = None

# =========================
# App / Tema / Validação
# =========================
app = tb.Window(themename="yeti"); app.title("Gerenciamento de Resíduos"); app.geometry("1200x820"); app.minsize(1040, 720)

def _erro_inesperado(exc_type, exc_value, exc_tb):
    """Erros não tratados em botões/telas: grava no log e avisa o usuário em vez de falhar em silêncio."""
    import logging, traceback
    logging.error("Erro inesperado:\n" + "".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
    try:
        ModernMessageBox.showerror("Erro inesperado", f"Ocorreu um erro e a ação pode não ter sido concluída.\n\nDetalhes: {exc_value}\n\n(O erro foi registrado em 'erros_sistema.log'.)")
    except Exception:
        pass
app.report_callback_exception = _erro_inesperado

def detalhe_erro_db(padrao):
    """Mensagem do último erro do banco de dados (ou a mensagem padrão, se não houver)."""
    msg = getattr(db, "ultimo_erro", "") or padrao
    db.ultimo_erro = ""
    return msg
app.option_add('*Calendar.TLabel.foreground', '#000000')  # Força texto preto
app.option_add('*Calendar.TLabel.background', '#cccccc')  # Força fundo cinza
try:
    # Cria um dicionário global para guardar os ícones
    ICONS = {
    "add": tk.PhotoImage(file=resource_path("icon_add.png")),
    "edit": tk.PhotoImage(file=resource_path("icon_edit.png")),
    "delete": tk.PhotoImage(file=resource_path("icon_delete.png")),
    "ok": tk.PhotoImage(file=resource_path("icon_ok.png")),
    "duplicate": tk.PhotoImage(file=resource_path("icon_duplicate.png")),
    "erase": tk.PhotoImage(file=resource_path("icon_erase.png")),
}
except tk.TclError as e:
    print(f"Aviso: Não foi possível carregar os ícones. {e}")
    print(" -> Certifique-se que 'icon_add.png', 'icon_edit.png', etc., estão na mesma pasta do script.")
    ICONS = {} # Usa um dicionário vazio se falhar
app.state('zoomed')
style = app.style;
style.configure('.', font=('Segoe UI', 9))
style.configure("Treeview", rowheight=28) # O padrão é ~20, ajuste conforme necessário
style.configure("Treeview.Heading", font=('Segoe UI', 10, 'bold')) # Deixa cabeçalhos em negrito (ajuste o '9' se necessário)
try: style.map("Treeview", background=[("selected", style.colors.primary)], foreground=[("selected", "white")])
except Exception: pass
def validate_numeric(P): return P == "" or bool(re.match(r"^[0-9]*[,]?[0-9]*$", P))
vcmd_numeric = (app.register(validate_numeric), '%P')

header = tb.Frame(app, padding=(12,10)); header.pack(fill="x")

# --- BLOCO DO LOGOTIPO ---
try:
    # 1. Carrega a imagem (Troque 'logo.png' pelo nome do seu arquivo)
    # Tente usar PNG com fundo transparente para ficar melhor
    arquivo_logo = resource_path("logo.png") 
    
    if os.path.exists(arquivo_logo):
        pil_image = Image.open(arquivo_logo)
        
        # 2. Redimensiona proporcionalmente para altura 45px
        altura_desejada = 45
        proporcao = altura_desejada / float(pil_image.size[1])
        largura_nova = int(float(pil_image.size[0]) * float(proporcao))
        
        pil_image = pil_image.resize((largura_nova, altura_desejada), Image.Resampling.LANCZOS)
        
        # 3. Converte para formato do Tkinter
        tk_image = ImageTk.PhotoImage(pil_image)
        
        # 4. Cria o Label da imagem e empacota ESQUERDA
        lbl_logo = tb.Label(header, image=tk_image)
        lbl_logo.image = tk_image # IMPORTANTE: Manter referência para não sumir
        lbl_logo.pack(side="left", padx=(0, 15)) # padx dá um espaço entre logo e texto
    else:
        print(f"Aviso: Arquivo '{arquivo_logo}' não encontrado.")

except Exception as e:
    print(f"Erro ao carregar logo: {e}")
# -------------------------

# Título do Programa (Agora vem DEPOIS do logo)
tb.Label(header, text="CONTROLE DE DESTINAÇÃO DE RESÍDUOS E ANÁLISES EXTERNAS", font="-size 16 -weight bold").pack(side="left")

# Resto do cabeçalho (Status e Botão Tema) - Mantém igual
status_var = tk.StringVar(value="")
tb.Label(header, textvariable=status_var, bootstyle=SECONDARY).pack(side="right", padx=8)
tema_btn = tb.Button(header, text="Alternar tema", bootstyle=SECONDARY, cursor="hand2")
tema_btn.pack(side="right")

def set_status(msg): status_var.set(msg); app.after(4000, lambda: status_var.set(""))

def alternar_tema():
    novo = "superhero" if style.theme.name != "superhero" else "yeti"; style.theme_use(novo);
    config_tags_por_tema()
    atualizar_dashboard()
    df_filtrado_atual = aplicar_filtros(obter_df_registros())
    preencher_tabela(df_filtrado_atual); set_status(f"Tema: {novo}")
tema_btn.configure(command=alternar_tema)

# ===================================================================
# RODAPÉ ISO 9001 (FIXO NO FUNDO)
# ===================================================================
# Configurações do Documento (Edite aqui)
ISO_CODIGO_GUI = "FO-5.1.00.016"
ISO_DATA_GUI = "26/06/2024"
ISO_REV_GUI = "08"

# Frame do Rodapé (side="bottom" garante que ele fique colado no chão)
footer_frame = tb.Frame(app, padding=2, bootstyle="secondary")
footer_frame.pack(side="bottom", fill="x")

# Configura o grid para dividir em 3 partes iguais
footer_frame.columnconfigure((0, 1, 2), weight=1)

# Estilo visual "Caixa" (Fundo escuro, texto claro, borda simulada)
# Usamos 'inverse-secondary' para dar destaque e aparência de barra de status
lbl_iso_cod = tb.Label(
    footer_frame, 
    text=f"Código do Documento: {ISO_CODIGO_GUI}", 
    font=("Segoe UI", 8), 
    anchor="center", 
    bootstyle="inverse-secondary"
)
lbl_iso_cod.grid(row=0, column=0, sticky="ew", padx=(0, 1))

lbl_iso_data = tb.Label(
    footer_frame, 
    text=f"Aprovado em: {ISO_DATA_GUI}", 
    font=("Segoe UI", 8), 
    anchor="center", 
    bootstyle="inverse-secondary"
)
lbl_iso_data.grid(row=0, column=1, sticky="ew", padx=1)

lbl_iso_rev = tb.Label(
    footer_frame, 
    text=f"Revisão: {ISO_REV_GUI}", 
    font=("Segoe UI", 8), 
    anchor="center", 
    bootstyle="inverse-secondary"
)
lbl_iso_rev.grid(row=0, column=2, sticky="ew", padx=(1, 0))

nb = tb.Notebook(app, bootstyle=PRIMARY)
nb.pack(fill="both", expand=True, padx=12, pady=(0,12))

# ===================================================================
# DEFINIÇÃO DAS ABAS PRINCIPAIS (NOVOS CONTÊINERES)
# ===================================================================

#1. ABA RESÍDUOS
aba_cad_fundo = tb.Frame(nb)
nb.add(aba_cad_fundo, text="Resíduos")

# Cria colunas invisíveis nas laterais para espremer o centro
aba_cad_fundo.columnconfigure(0, weight=1)
aba_cad_fundo.columnconfigure(1, weight=0) # O centro não expande
aba_cad_fundo.columnconfigure(2, weight=1)

aba_cad = tb.Frame(aba_cad_fundo, padding=12)
aba_cad.grid(row=0, column=1, sticky="n", pady=10) # Fica grudado no topo (North)

# TRUQUE DE DESIGN: Um frame invisível de 1 pixel para forçar a largura do formulário
tb.Frame(aba_cad, width=1000, height=1).pack()
# =======================================================
launch_type_var = tk.StringVar(value="Resíduo")
launch_frame = tb.Labelframe(aba_cad, text="Tipo de Lançamento", padding=(10, 5), bootstyle=INFO)
launch_frame.pack(fill="x", pady=(0, 10))

tb.Radiobutton(
    launch_frame, 
    text="Resíduo", 
    value="Resíduo", 
    variable=launch_type_var
).pack(side="left", padx=10)

tb.Radiobutton(
    launch_frame, 
    text="Transporte", 
    value="Transporte", 
    variable=launch_type_var
).pack(side="left", padx=10)

tb.Radiobutton(
    launch_frame, 
    text="Análise Externa", 
    value="Análise", 
    variable=launch_type_var
).pack(side="left", padx=10)

peso_var = tk.StringVar(value="")
#2. CALENDÁRIO
aba_cal = tb.Frame(nb, padding=10)
nb.add(aba_cal, text="Calendário")

#2.1 ABA REGISTROS
aba_regs = tb.Frame(nb, padding=12);
nb.add(aba_regs, text="Registros")

#3. ABA PENDÊNCIAS
aba_pend = tb.Frame(nb, padding=12);
nb.add(aba_pend, text="Pendências")

# 4. NOVA ABA RELATÓRIOS
aba_relatorios = tb.Frame(nb, padding=12)
nb.add(aba_relatorios, text="Relatórios")
# Notebook secundário para os relatórios
relatorios_nb = tb.Notebook(aba_relatorios, bootstyle=PRIMARY)
relatorios_nb.pack(fill="both", expand=True)

# ==========================================
# ABA 0 — DASHBOARD INICIAL (HOME)
# ==========================================
aba_dash = tb.Frame(relatorios_nb, padding=25)
# O insert(0, ...) garante que esta seja a primeira aba da esquerda!
relatorios_nb.add(aba_dash, text=" 🏠 Resumo do Mês ")

tb.Label(aba_dash, text="Desempenho Ambiental (Mês Atual)", font=("Segoe UI", 22, "bold"), bootstyle="primary").pack(pady=(0, 30))

frame_cards = tb.Frame(aba_dash)
frame_cards.pack(fill="x", expand=True)
frame_cards.columnconfigure((0, 1, 2), weight=1)

# --- Card 1: Total Gerado ---
card_peso = tb.Labelframe(frame_cards, text=" Total Gerado (kg) ", bootstyle="info", padding=20)
card_peso.grid(row=0, column=0, sticky="nsew", padx=10)
lbl_dash_peso = tb.Label(card_peso, text="0,00 kg", font=("Segoe UI", 32, "bold"), bootstyle="info")
lbl_dash_peso.pack(expand=True, pady=15)

# --- Card 2: Custo de Destinação ---
card_custo = tb.Labelframe(frame_cards, text=" Custo Total (R$) ", bootstyle="danger", padding=20)
card_custo.grid(row=0, column=1, sticky="nsew", padx=10)
lbl_dash_custo = tb.Label(card_custo, text="R$ 0,00", font=("Segoe UI", 32, "bold"), bootstyle="danger")
lbl_dash_custo.pack(expand=True, pady=15)

# --- Card 3: Taxa de Reciclabilidade ---
card_rec = tb.Labelframe(frame_cards, text=" Taxa de Reciclabilidade ", bootstyle="success", padding=20)
card_rec.grid(row=0, column=2, sticky="nsew", padx=10)
lbl_dash_rec = tb.Label(card_rec, text="0,0%", font=("Segoe UI", 32, "bold"), bootstyle="success")
lbl_dash_rec.pack(expand=True, pady=15)

# 5. NOVA ABA CONFIGURAÇÕES
aba_config = tb.Frame(nb, padding=12)
nb.add(aba_config, text="Configurações")
# Notebook secundário para as configurações
config_nb = tb.Notebook(aba_config, bootstyle=PRIMARY)
config_nb.pack(fill="both", expand=True)
aba_import_fundo = tb.Frame(config_nb) 
config_nb.add(aba_import_fundo, text="Importação")

aba_import_fundo.columnconfigure(0, weight=1)
aba_import_fundo.columnconfigure(1, weight=0)
aba_import_fundo.columnconfigure(2, weight=1)

aba_importacao_config = tb.Frame(aba_import_fundo, padding=12)
aba_importacao_config.grid(row=0, column=1, sticky="n", pady=10)

tb.Frame(aba_importacao_config, width=1000, height=1).pack()

# ===================================================================
# ABA 1 — Cadastro (UI)
# ===================================================================

#nb.add(aba_cad, text="Resíduos")

peso_var = tk.StringVar(value="")
peso_unitario_var = tk.StringVar(value="")
peso_kg_var = tk.StringVar(value="") # Campo calculado (read-only)

# --- DEFINIÇÕES DAS FUNÇÕES AUXILIARES DA ABA 1 (Local Correto) ---
def calcular_resumo_financeiro_automatico(*_):
    """Calcula e exibe o valor total da operação em tempo real no Card de Destaque."""
    if 'lbl_total_operacao' not in globals(): return
    
    try:
        modo = clean_str(calc_mode_var.get()).lower()
        v_transporte = money_pt(entrada_transporte.get())
        valor_base = Decimal("0")
        
        if modo == "kg" or modo == "unidade":
            v_unit = money_pt(entrada_valor_kg.get())
            qtd = money_pt(peso_var.get())
            valor_base = v_unit * qtd
        elif modo == "fechado":
            valor_base = money_pt(entrada_valor_fechado.get())
            
        total_final = valor_base + v_transporte
        tipo = clean_str(tipo_var.get()).lower()
        
        if tipo == "venda":
            lbl_total_operacao.config(text=f"{fmt_moeda(total_final)}", bootstyle="success")
        else:
            lbl_total_operacao.config(text=f"{fmt_moeda(total_final)}", bootstyle="danger")
            
    except Exception:
        lbl_total_operacao.config(text="R$ 0,00", bootstyle="secondary")

def calcular_peso_kg_automatico(*_):
    """Calcula o Peso Total (kg) e engatilha o cálculo financeiro."""
    if 'peso_kg_var' not in globals(): return 

    modo = clean_str(calc_mode_var.get()).lower()
    if modo != "unidade":
        peso_kg_var.set("") 
    else:
        try:
            quantidade = money_pt(peso_var.get())
            peso_unitario = money_pt(peso_unitario_var.get())

            if quantidade > 0 and peso_unitario > 0:
                total_kg = quantidade * peso_unitario
                s_val = f"{total_kg:.3f}".replace(".", ",").rstrip("0").rstrip(",")
                peso_kg_var.set(s_val)
            else:
                peso_kg_var.set("") 
        except Exception:
            peso_kg_var.set("Erro")
            
    calcular_resumo_financeiro_automatico()

def preencher_valor_residuo(modo, val_kg, val_ton, val_fec): 
    entrada_valor_kg.delete(0, tk.END)
    entrada_valor_fechado.delete(0, tk.END)

    val_kg_dec = Decimal(str(val_kg))
    val_fec_dec = Decimal(str(val_fec))

    visivel_kg = bool(entrada_valor_kg.grid_info())
    visivel_fec = bool(entrada_valor_fechado.grid_info())

    if modo in ('kg', 'unidade') and val_kg_dec > Decimal('0') and visivel_kg:
        s_val = f"{val_kg_dec:.3f}".replace(".", ",").rstrip("0").rstrip(",")
        entrada_valor_kg.insert(0, s_val)
    elif modo == 'fechado' and val_fec_dec > Decimal('0') and visivel_fec:
        entrada_valor_fechado.insert(0, f"{val_fec_dec:.2f}".replace(".", ","))
        
    calcular_resumo_financeiro_automatico()
        
def preencher_valores_edicao(modo, vkg_db, peso_db_kg, vfechado_db, transp):
    peso_display_str = f"{Decimal(str(peso_db_kg)):.3f}".replace(".",",").rstrip("0").rstrip(",")
    peso_var.set(peso_display_str)

    visivel_kg = bool(entrada_valor_kg.grid_info())
    visivel_fec = bool(entrada_valor_fechado.grid_info())

    if modo in ("kg", "unidade"):
        entrada_valor_kg.delete(0, tk.END) 
        if visivel_kg:
            entrada_valor_kg.insert(0, f"{Decimal(str(vkg_db)):.3f}".replace(".", ",").rstrip("0").rstrip(","))
    elif modo == "fechado":
        entrada_valor_fechado.delete(0, tk.END) 
        if visivel_fec:
            entrada_valor_fechado.insert(0, f"{vfechado_db:.2f}".replace(".",","))

    entrada_transporte.delete(0, tk.END)
    entrada_transporte.insert(0, f"{transp:.2f}".replace(".",","))
    calcular_resumo_financeiro_automatico()
        
def toggle_campos_por_modo(*_):
    """Mostra (grid) ou Esconde (grid_remove) os campos conforme o modo."""
    if 'label_valor_kg' not in globals(): return
    modo = clean_str(calc_mode_var.get()).lower()

    # 1. Esconde TUDO que é dinâmico primeiro
    for w in [label_valor_kg, entrada_valor_kg, label_valor_fechado, entrada_valor_fechado,
              label_peso_unitario, entrada_peso_unitario, label_peso_kg, entrada_peso_kg]:
        w.grid_remove()

    # 2. Limpa dados fantasmas para não salvar lixo
    if modo not in ("kg", "unidade"): entrada_valor_kg.delete(0, tk.END)
    if modo != "fechado": entrada_valor_fechado.delete(0, tk.END)
    if modo != "unidade":
        peso_unitario_var.set("")
        peso_kg_var.set("")

    # 3. Monta o LEGO: Mostra só o que importa
    if modo == "kg":
        label_valor_kg.config(text="Valor por kg (R$)")
        label_valor_kg.grid(); entrada_valor_kg.grid()
        label_peso.config(text="Peso (kg)", bootstyle=INFO)

    elif modo == "unidade":
        label_valor_kg.config(text="Valor Unitário (R$)")
        label_valor_kg.grid(); entrada_valor_kg.grid()
        label_peso.config(text="Quantidade (unid.)", bootstyle=INFO)
        label_peso_unitario.grid(); entrada_peso_unitario.grid()
        label_peso_kg.config(text="Peso Total (kg)", bootstyle=SUCCESS)
        label_peso_kg.grid(); entrada_peso_kg.grid()

    elif modo == "fechado":
        label_valor_fechado.grid(); entrada_valor_fechado.grid()
        label_peso.config(text="Peso (kg) [Obrigatório]", bootstyle=WARNING)

    calcular_resumo_financeiro_automatico()

def atualizar_form_por_residuo(*_):
    """Preenche modo, valor E AGORA TAMBÉM as regras de compliance."""
    nome_residuo = clean_str(res_var.get())
    dados = banco_dict.get(nome_residuo)

    if 'peso_unitario_var' in globals(): peso_unitario_var.set("")
    if 'peso_kg_var' in globals(): peso_kg_var.set("")

    if dados:
        # ... (código existente de modo e valores mantém igual) ...
        modo = dados.get('modo', 'kg')
        val_kg = dados.get('kg', 0.0)
        val_fec = dados.get('fechado', 0.0)
        val_pu = dados.get('peso_unitario', 0.0)

        calc_mode_var.set(modo)
        app.after(50, lambda: preencher_valor_residuo(modo, val_kg, 0.0, val_fec))
        
        if modo == 'unidade' and val_pu > 0:
             s_pu = f"{val_pu:.3f}".replace(".", ",").rstrip("0").rstrip(",")
             app.after(55, lambda: peso_unitario_var.set(s_pu))

        # Auto-preenchimento de Padrões
        p_estado = dados.get('estado_padrao'); 
        if p_estado: estado_var.set(p_estado)
        p_dest = dados.get('destinacao_padrao'); 
        if p_dest: destinacao_var.set(p_dest)
        p_tipo = dados.get('tipo_padrao'); 
        if p_tipo: tipo_var.set(p_tipo)
        p_parc = dados.get('parceiro_padrao'); 
        if p_parc: parceiro_var.set(p_parc)
        
        # --- NOVO: Atualiza os checkboxes manuais conforme o padrão ---
        # Se o padrão é True (1), marca. Se False (0), desmarca.
        padrao_nf = dados.get('exige_nf', True)
        padrao_cert = dados.get('exige_cert', True)
        
        var_nf_manual.set(1 if padrao_nf else 0)
        var_cert_manual.set(1 if padrao_cert else 0)
        # -------------------------------------------------------------

    else:
        calc_mode_var.set('kg')
        app.after(50, lambda: entrada_valor_kg.delete(0, tk.END))
        # Reseta para "Marcado" por segurança se for resíduo novo/desconhecido
        var_nf_manual.set(1)
        var_cert_manual.set(1)


    
def toggle_pedido_por_tipo(*_):
    """Habilita/desabilita campo Pedido de Compra se Tipo for Custo."""
    is_custo = clean_str(tipo_var.get()).lower() == "custo"
    entrada_pedido.configure(state=("normal" if is_custo else "disabled"))
    if not is_custo:
        entrada_pedido.delete(0, tk.END)

def toggle_launch_view(*_):
    """Mostra/esconde os formulários de Resíduo, Análise ou Transporte."""
    
    if 'cad' not in globals() or 'frm_ana' not in globals(): return 
    if 'frm_transporte' not in globals(): return # Garante que o novo form existe
        
    tipo = launch_type_var.get()
    
    # 1. Esconde tudo primeiro
    cad.pack_forget()
    cad_actions.pack_forget()
    frm_ana.pack_forget()
    btn_ana_add.pack_forget()
    frm_transporte.pack_forget()
    
    # 2. Mostra o correto
    if tipo == "Resíduo":
        # Filtro de destinação (remove Análise)
        destinacoes_residuo = [d for d in destinacoes if d != "Análise externa"]
        destinacao_cb.configure(values=destinacoes_residuo)
        if destinacao_var.get() == "Análise externa":
            destinacao_var.set(destinacoes_residuo[0] if destinacoes_residuo else "")
            
        cad.pack(fill="x")
        cad_actions.pack(fill="x", pady=(5,0))
        
    elif tipo == "Análise":
        frm_ana.pack(fill="x", pady=(0, 0))
        btn_ana_add.pack(pady=15, anchor="w")
        
    elif tipo == "Transporte":
        # Atualiza lista de parceiros e resíduos caso tenham mudado
        transp_parc_cb.configure(values=parceiros)
        transp_res_cb.configure(values=banco_residuos)
        
        frm_transporte.pack(fill="x", pady=(0, 0))

# --- CRIAÇÃO DOS WIDGETS DA ABA 1 ---
cad = tb.Labelframe(aba_cad, text="Novo registro",padding=12, bootstyle=INFO)
cad.pack(fill="x")
cad.columnconfigure((0,1,2,3), weight=1, uniform="group1")

# Linha 1: Data, Parceiro, Resíduo, Tipo
tb.Label(cad, text="Data").grid(row=0, column=0, sticky="w", padx=(0,5))

# --- MUDANÇA PARA TKCALENDAR (Navegação Melhor) ---
# date_pattern='dd/mm/yy' define o formato brasileiro
# locale='pt_BR' traduz os meses (se seu Windows estiver em PT-BR)
entrada_data = CalendarioPremium(cad, dateformat="%d/%m/%y")
entrada_data.grid(row=1, column=0, sticky="ew", padx=(0,5), pady=(2, 12))

tb.Label(cad, text="Resíduo").grid(row=0, column=1, sticky="w", padx=5)
res_var = tk.StringVar(value=(banco_residuos[0] if banco_residuos else ""))
# --- ALTERAÇÃO: state="normal" permite digitar ---
# --- Resíduo ---
# Mantém state="readonly" para não deixar digitar texto livre
res_cb = tb.Combobox(cad, textvariable=res_var, values=banco_residuos, state="normal")
res_cb.grid(row=1, column=1, sticky="ew", padx=5, pady=(2, 12))

# Configura o filtro inteligente (Removemos o pular_para_letra)
configurar_autocomplete(res_cb, banco_residuos)
res_cb.bind("<<ComboboxSelected>>", atualizar_form_por_residuo)
# Quando aperta ENTER após digitar:
res_cb.bind("<Return>", lambda e: atualizar_form_por_residuo())
# Quando sai do campo (aperta TAB ou clica fora):
res_cb.bind("<FocusOut>", lambda e: atualizar_form_por_residuo())

# --- Parceiro (Com Autocomplete) ---
tb.Label(cad, text="Parceiro").grid(row=0, column=2, sticky="w", padx=5)
parceiro_var = tk.StringVar(value=(parceiros[0] if parceiros else ""))

# Mudamos para state="normal"
parceiro_cb = tb.Combobox(cad, textvariable=parceiro_var, values=parceiros, state="normal")
parceiro_cb.grid(row=1, column=2, sticky="ew", padx=5, pady=(2, 12))

# Configura o filtro inteligente
configurar_autocomplete(parceiro_cb, parceiros)
parceiro_cb.bind("<<ComboboxSelected>>", lambda e: app.focus_set()) # Tira o foco para evitar bugs visuais

tb.Label(cad, text="Tipo").grid(row=0, column=3, sticky="w", padx=(5,0))
tipo_var = tk.StringVar(value="Venda")
tipo_frame = tb.Frame(cad); tipo_frame.grid(row=1, column=3, sticky="w", padx=(5,0), pady=(2, 12))
tb.Radiobutton(tipo_frame, text="Venda", value="Venda", variable=tipo_var).pack(side="left", padx=(2,12))
tb.Radiobutton(tipo_frame, text="Custo", value="Custo", variable=tipo_var).pack(side="left")

# Linha 2: Estado, Destinação, MTR, Pedido
tb.Label(cad, text="Estado").grid(row=2, column=0, sticky="w", padx=(0,5))
estado_var = tk.StringVar(value="Sólido")
estado_frame = tb.Frame(cad); estado_frame.grid(row=3, column=0, sticky="w", padx=(0,5), pady=(0, 10))
tb.Radiobutton(estado_frame, text="Sólido", value="Sólido", variable=estado_var).pack(side="left", padx=(0,10))
tb.Radiobutton(estado_frame, text="Líquido", value="Líquido", variable=estado_var).pack(side="left")

tb.Label(cad, text="Destinação").grid(row=2, column=1, sticky="w", padx=5)
destinacao_var = tk.StringVar(value=(destinacoes[0] if destinacoes else ""))
destinacao_cb = tb.Combobox(cad, textvariable=destinacao_var, values=destinacoes, state="readonly")
destinacao_cb.grid(row=3, column=1, sticky="ew", padx=5, pady=(0, 10))

tb.Label(cad, text="Pedido de compra (opcional)").grid(row=2, column=2, sticky="w", padx=5) # Movido para column=2
entrada_pedido = tb.Entry(cad); entrada_pedido.grid(row=3, column=2, sticky="ew", padx=5, pady=(0, 10)) # Movido para column=2
frame_compliance = tb.Frame(cad)
frame_compliance.grid(row=3, column=3, sticky="w", padx=5, pady=(0,10))

def selecionar_anexo():
    path = filedialog.askopenfilename(title="Selecione o Comprovante/MTR", filetypes=[("Documentos", "*.pdf *.jpg *.png *.jpeg")])
    if path:
        caminho_anexo_temp.set(path)
        lbl_anexo_info.config(text=f"📎 {os.path.basename(path)}", bootstyle="success")

btn_anexo = tb.Button(frame_compliance, text="Anexar", bootstyle="outline-secondary", command=selecionar_anexo, width=8)
btn_anexo.pack(side="left", padx=(15, 5))

# Label para mostrar o nome do arquivo selecionado
lbl_anexo_info = tb.Label(frame_compliance, text="", font=("Segoe UI", 8))
lbl_anexo_info.pack(side="left")

# Variáveis de controle (1 = Precisa, 0 = Não precisa/NA)
var_nf_manual = tk.IntVar(value=1)
var_cert_manual = tk.IntVar(value=1)
caminho_anexo_temp = tk.StringVar(value="")

# Checkboxes
chk_nf_manual = tb.Checkbutton(frame_compliance, text="Exige NF", variable=var_nf_manual, bootstyle="round-toggle")
chk_nf_manual.pack(side="left", padx=(0, 10))

chk_cert_manual = tb.Checkbutton(frame_compliance, text="Exige Certificado", variable=var_cert_manual, bootstyle="round-toggle")
chk_cert_manual.pack(side="left")

# Linha 3 - Cálculos (Layout Dinâmico e Limpo)
calc_lf = tb.Labelframe(cad, text="Cálculo de Valores", padding=15, bootstyle=INFO)
calc_lf.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(15, 5))
calc_lf.columnconfigure((0, 1, 2, 3), weight=1, uniform="group2") 

# Radio buttons de Modo
calc_mode_var = tk.StringVar(value="kg")
radio_frame = tb.Frame(calc_lf)
radio_frame.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0,15))
tb.Radiobutton(radio_frame, text="Valor por kg", value="kg", variable=calc_mode_var).pack(side="left", padx=(0,20))
tb.Radiobutton(radio_frame, text="Valor por unidade", value="unidade", variable=calc_mode_var).pack(side="left", padx=(0,20))
tb.Radiobutton(radio_frame, text="Valor fechado", value="fechado", variable=calc_mode_var).pack(side="left", padx=0)

# --- COLUNA 0: Valor Financeiro ---
# (Eles ocupam o mesmo grid e se revezam)
label_valor_kg = tb.Label(calc_lf, text="Valor por kg (R$)")
label_valor_kg.grid(row=1, column=0, sticky="w")
entrada_valor_kg = tb.Entry(calc_lf, validate="key", validatecommand=vcmd_numeric)
entrada_valor_kg.grid(row=2, column=0, sticky="ew", padx=(0,10), pady=(0, 15))
# Bind para atualizar total ao digitar
entrada_valor_kg.bind("<KeyRelease>", calcular_resumo_financeiro_automatico)

label_valor_fechado = tb.Label(calc_lf, text="Valor fechado (R$)")
label_valor_fechado.grid(row=1, column=0, sticky="w") 
entrada_valor_fechado = tb.Entry(calc_lf, validate="key", validatecommand=vcmd_numeric)
entrada_valor_fechado.grid(row=2, column=0, sticky="ew", padx=(0,10), pady=(0, 15))
entrada_valor_fechado.bind("<KeyRelease>", calcular_resumo_financeiro_automatico)

# --- COLUNA 1: Peso / Quantidade ---
label_peso = tb.Label(calc_lf, text="Peso (kg)", bootstyle=INFO) 
label_peso.grid(row=1, column=1, sticky="w")
entrada_peso = tb.Entry(calc_lf, textvariable=peso_var, validate="key", validatecommand=vcmd_numeric)
entrada_peso.grid(row=2, column=1, sticky="ew", padx=(0,10), pady=(0, 15))

# --- COLUNA 2: Peso Unitário (Apenas Unidade) ---
label_peso_unitario = tb.Label(calc_lf, text="Peso por Unidade (kg)")
label_peso_unitario.grid(row=1, column=2, sticky="w")
entrada_peso_unitario = tb.Entry(calc_lf, textvariable=peso_unitario_var, validate="key", validatecommand=vcmd_numeric)
entrada_peso_unitario.grid(row=2, column=2, sticky="ew", padx=(0,10), pady=(0, 15))

# --- COLUNA 3: Peso Total Calculado (Apenas Unidade) ---
label_peso_kg = tb.Label(calc_lf, text="Peso Total (kg)", bootstyle=SUCCESS) 
label_peso_kg.grid(row=1, column=3, sticky="w")
entrada_peso_kg = tb.Entry(calc_lf, textvariable=peso_kg_var, state="readonly", bootstyle="success") 
entrada_peso_kg.grid(row=2, column=3, sticky="ew", padx=(0,0), pady=(0, 15))

# --- LINHA DIVISÓRIA ---
tb.Separator(calc_lf).grid(row=3, column=0, columnspan=4, sticky="ew", pady=(0, 10))

# --- TRANSPORTE & TOTAL GERAL ---
label_transporte = tb.Label(calc_lf, text="Transporte (R$) [Custo Extra]")
label_transporte.grid(row=4, column=0, sticky="w")
entrada_transporte = tb.Entry(calc_lf, validate="key", validatecommand=vcmd_numeric)
entrada_transporte.grid(row=5, column=0, sticky="ew", padx=(0,10))
entrada_transporte.bind("<KeyRelease>", calcular_resumo_financeiro_automatico)

# CARD DO TOTAL GERAL (Destaque à Direita)
frame_total_destaque = tb.Frame(calc_lf)
frame_total_destaque.grid(row=4, column=2, rowspan=2, columnspan=2, sticky="e")

tb.Label(frame_total_destaque, text="TOTAL DA OPERAÇÃO", font=("Segoe UI", 9, "bold")).pack(side="top", anchor="e")
lbl_total_operacao = tb.Label(frame_total_destaque, text="R$ 0,00", font=("Segoe UI", 24, "bold"), bootstyle="success")
lbl_total_operacao.pack(side="top", anchor="e")

# --- LIGAÇÕES Traces/Binds da Aba 1 ---
res_var.trace_add("write", atualizar_form_por_residuo)
res_cb.bind("<<ComboboxSelected>>", atualizar_form_por_residuo)
calc_mode_var.trace_add("write", lambda *_: toggle_campos_por_modo())
tipo_var.trace_add("write", lambda *_: toggle_pedido_por_tipo())
peso_var.trace_add("write", calcular_peso_kg_automatico)
peso_unitario_var.trace_add("write", calcular_peso_kg_automatico)
calc_mode_var.trace_add("write", calcular_peso_kg_automatico) # Recalcula ao mudar de modo

def abrir_janela_lote():
    """Abre janela para lançar histórico com layout limpo e organizado."""
    
    lote_win = tb.Toplevel(app)
    lote_win.title("Lançamento de Histórico (Lote)")
    lote_win.geometry("1200x750") 
    
    itens_da_carga = []

    # ===========================
    # 1. DADOS FIXOS (CABEÇALHO)
    # ===========================
    frame_comum = tb.Labelframe(lote_win, text="1. Dados Fixos (Parceiro/Destinação)", padding=15, bootstyle=INFO)
    frame_comum.pack(fill="x", padx=15, pady=15)
    
    # Configura grid para distribuir espaço
    frame_comum.columnconfigure((0,1,2,3), weight=1)

    # Parceiro
    tb.Label(frame_comum, text="Parceiro:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=5)
    parc_cb = tb.Combobox(frame_comum, values=parceiros, state="readonly")
    if parceiros: parc_cb.current(0)
    parc_cb.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
    
    # Destinação
    tb.Label(frame_comum, text="Destinação:", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=5)
    dest_cb = tb.Combobox(frame_comum, values=destinacoes, state="readonly")
    if destinacoes: dest_cb.current(0)
    dest_cb.grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 5))
    
    # Tipo
    tb.Label(frame_comum, text="Tipo:", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=5)
    tipo_cb = tb.Combobox(frame_comum, values=["Venda", "Custo"], state="readonly")
    tipo_cb.set("Venda")
    tipo_cb.grid(row=1, column=2, sticky="ew", padx=5, pady=(0, 5))
    
    # Pedido
    tb.Label(frame_comum, text="Pedido/Ticket (Opcional):").grid(row=0, column=3, sticky="w", padx=5)
    pedido_entry = tb.Entry(frame_comum)
    pedido_entry.grid(row=1, column=3, sticky="ew", padx=5, pady=(0, 5))

    # ===========================
    # 2. ADICIONAR ITEM (ÁREA DE TRABALHO)
    # ===========================
    frame_item = tb.Labelframe(lote_win, text="2. Adicionar Item", padding=15, bootstyle=SUCCESS)
    frame_item.pack(fill="x", padx=15, pady=5)
    
    # Configura colunas: 0 a 4 são dados, 5 é botão
    frame_item.columnconfigure((0,1,2,3,4), weight=1)
    frame_item.columnconfigure(5, weight=0) # Botão não estica
    
    # --- Linha 1: Resíduo (Destaque total) ---
    tb.Label(frame_item, text="Selecione o Resíduo:", font=("Segoe UI", 10, "bold"), bootstyle="primary").grid(row=0, column=0, columnspan=6, sticky="w", padx=5)
    res_lote_var = tk.StringVar()
    res_lote_cb = tb.Combobox(frame_item, textvariable=res_lote_var, values=banco_residuos, state="readonly", font=("Segoe UI", 10))
    res_lote_cb.grid(row=1, column=0, columnspan=6, sticky="ew", padx=5, pady=(5, 15))
    res_lote_cb.bind("<Key>", pular_para_letra)
    
    # --- Linha 2: Labels dos Campos ---
    tb.Label(frame_item, text="Data").grid(row=2, column=0, sticky="w", padx=5)
    tb.Label(frame_item, text="Modo").grid(row=2, column=1, sticky="w", padx=5)
    tb.Label(frame_item, text="Qtd / Peso").grid(row=2, column=2, sticky="w", padx=5)
    lbl_valor = tb.Label(frame_item, text="Valor (R$)")
    lbl_valor.grid(row=2, column=3, sticky="w", padx=5)
    tb.Label(frame_item, text="Estado").grid(row=2, column=4, sticky="w", padx=5)

    # --- Linha 3: Inputs + Botão ---
    # Data
    dt_item_entry = CalendarioPremium(frame_item, dateformat="%d/%m/%y")
    dt_item_entry.grid(row=3, column=0, sticky="ew", padx=5, pady=(0, 5))
    
    # Modo
    modo_lote_var = tk.StringVar(value="kg")
    modo_cb = tb.Combobox(frame_item, textvariable=modo_lote_var, values=["kg", "fechado", "unidade"], state="readonly")
    modo_cb.grid(row=3, column=1, sticky="ew", padx=5, pady=(0, 5))

    # Qtd
    qtd_entry = tb.Entry(frame_item, validate="key", validatecommand=vcmd_numeric)
    qtd_entry.grid(row=3, column=2, sticky="ew", padx=5, pady=(0, 5))
    
    # Valor
    valor_entry = tb.Entry(frame_item, validate="key", validatecommand=vcmd_numeric)
    valor_entry.grid(row=3, column=3, sticky="ew", padx=5, pady=(0, 5))

    # 1. Variável exclusiva para mostrar o valor do item atual
    item_preview_var = tk.StringVar(value="R$ 0,00")

    def atualizar_preview_item(*args):
        """Calcula o Qtd x Valor instantaneamente enquanto o usuário digita"""
        try:
            qtd_str = qtd_entry.get()
            val_str = valor_entry.get()
            
            # Se a caixa estiver vazia, zera o painel
            if not qtd_str or not val_str:
                item_preview_var.set("R$ 0,00")
                return

            qtd = money_pt(qtd_str)
            val_in = money_pt(val_str)
            modo = modo_lote_var.get()

            # Se o modo for "fechado", o total é o próprio valor inserido. Senão, multiplica.
            if modo == 'fechado':
                total_fin = val_in
            else:
                total_fin = qtd * val_in

            item_preview_var.set(fmt_moeda(total_fin))
        except:
            item_preview_var.set("R$ 0,00")

    # 2. Faz o sistema disparar a conta a cada tecla pressionada ou mudança de modo
    qtd_entry.bind("<KeyRelease>", atualizar_preview_item)
    valor_entry.bind("<KeyRelease>", atualizar_preview_item)
    modo_lote_var.trace_add("write", atualizar_preview_item)
    
    # Estado
    estado_lote_var = tk.StringVar(value="Sólido")
    estado_cb = tb.Combobox(frame_item, textvariable=estado_lote_var, values=["Sólido", "Líquido"], state="readonly")
    estado_cb.grid(row=3, column=4, sticky="ew", padx=5, pady=(0, 5))

    # BOTÃO ADICIONAR (Ao lado do Estado)
    # bootstyle="success" para ficar verde cheio, chamativo
    btn_add = tb.Button(frame_item, text="ADICIONAR (+)", bootstyle="success", width=12) # command será ligado abaixo
    btn_add.grid(row=3, column=5, sticky="ew", padx=(10, 5), pady=(0, 5))

    # --- Linha 4: Compliance & Info ---
    frame_bottom = tb.Frame(frame_item)
    frame_bottom.grid(row=4, column=0, columnspan=6, sticky="ew", pady=(10, 0))
    
    # Checkboxes
    var_nf_lote = tk.IntVar(value=1)
    var_cert_lote = tk.IntVar(value=1)
    
    tb.Label(frame_bottom, text="Compliance:", bootstyle="secondary").pack(side="left", padx=(5, 10))
    chk_nf = tb.Checkbutton(frame_bottom, text="Exige NF", variable=var_nf_lote, bootstyle="round-toggle")
    chk_nf.pack(side="left", padx=10)
    
    chk_cert = tb.Checkbutton(frame_bottom, text="Exige Certificado", variable=var_cert_lote, bootstyle="round-toggle")
    chk_cert.pack(side="left", padx=10)
    
    # Info Label (Alinhado à direita para equilibrar)
    # Começa vazio para não mostrar "..."
    info_lbl = tb.Label(frame_bottom, text="", bootstyle="info") 
    info_lbl.pack(side="right", padx=10)

    # ===========================
    # LÓGICA DO FORMULÁRIO
    # ===========================
    def atualizar_rotulo_valor(*_):
        m = modo_lote_var.get()
        if m == "fechado": lbl_valor.config(text="Valor Total (R$):", bootstyle="warning")
        elif m == "unidade": lbl_valor.config(text="Valor Unit. (R$):", bootstyle="info")
        else: lbl_valor.config(text="Valor p/ kg (R$):", bootstyle="inverse-light")
    modo_lote_var.trace_add("write", atualizar_rotulo_valor)

    def ao_selecionar_residuo(*_):
        nome = res_lote_var.get()
        dados = banco_dict.get(nome)
        if dados:
            modo_padrao = dados.get('modo', 'kg')
            modo_lote_var.set(modo_padrao)
            
            val_kg = dados.get('kg', 0.0)
            val_fec = dados.get('fechado', 0.0)
            
            valor_entry.delete(0, tk.END)
            if modo_padrao == 'fechado' and val_fec > 0:
                valor_entry.insert(0, f"{val_fec:.2f}".replace(".", ","))
            elif val_kg > 0:
                valor_entry.insert(0, f"{val_kg:.4f}".replace(".", ","))
            
            est = dados.get('estado_padrao')
            if est: estado_lote_var.set(est)
            
            # Compliance auto
            var_nf_lote.set(1 if dados.get('exige_nf', True) else 0)
            var_cert_lote.set(1 if dados.get('exige_cert', True) else 0)

            peso_u = dados.get('peso_unitario', 0.0)
            # Atualiza o label de info
            if modo_padrao == 'unidade':
                info_lbl.config(text=f"ℹ Peso Referência: {peso_u} kg/un")
            else:
                info_lbl.config(text="")

    res_lote_cb.bind("<<ComboboxSelected>>", ao_selecionar_residuo)

    def adicionar_item_lista():
        try:
            d_item = obter_data_segura(dt_item_entry)
            data_str = d_item.strftime("%Y-%m-%d")
            data_view = d_item.strftime("%d/%m/%y")
        except: ModernMessageBox.showerror("Erro", "Data inválida."); return

        residuo = res_lote_var.get()
        qtd_str = qtd_entry.get()
        val_str = valor_entry.get()
        if not residuo or not qtd_str: ModernMessageBox.showwarning("Aviso", "Preencha dados."); return
            
        qtd = money_pt(qtd_str)
        val_in = money_pt(val_str)
        modo = modo_lote_var.get()
        
        dados = banco_dict.get(residuo, {})
        peso_unit_ref = _dec(dados.get('peso_unitario', 0.0))
        
        peso_real = Decimal("0"); total_fin = Decimal("0")
        v_unit = Decimal("0"); v_fechado = Decimal("0")
        
        if modo == 'fechado':
            peso_real = qtd; total_fin = val_in; v_fechado = val_in
            disp_qtd = f"{fmt_kg(qtd)}"
        elif modo == 'unidade':
            peso_real = qtd * peso_unit_ref; total_fin = qtd * val_in; v_unit = val_in
            disp_qtd = f"{qtd:.0f} un"
        else:
            peso_real = qtd; total_fin = qtd * val_in; v_unit = val_in
            disp_qtd = f"{fmt_kg(qtd)}"

        nf_status = "Não" if var_nf_lote.get() else "N/A"
        cert_status = "Não" if var_cert_lote.get() else "N/A"

        item_data = {
            "data_db": data_str, "residuo": residuo, "estado": estado_lote_var.get(),
            "modo": modo, "qtd_input": float(qtd), "valor_unit": float(v_unit),
            "valor_fechado": float(v_fechado), "total": float(total_fin),
            "peso_calc": float(peso_real),
            "nf_ok": nf_status,
            "cert_ok": cert_status
        }
        itens_da_carga.append(item_data)
        
        tree_lote.insert("", "end", values=(data_view, residuo, modo, disp_qtd, fmt_moeda(total_fin), nf_status, cert_status))
        
        qtd_entry.delete(0, tk.END)
        atualizar_preview_item()
        dt_item_entry.focus_set()

    # Ligar comando do botão
    btn_add.configure(command=adicionar_item_lista)
    
    qtd_entry.bind("<Return>", lambda e: adicionar_item_lista())
    valor_entry.bind("<Return>", lambda e: adicionar_item_lista())

    # ===========================
    # 3. LISTA VISUAL
    # ===========================
    frame_lista = tb.Frame(lote_win, padding=15)
    frame_lista.pack(fill="both", expand=True)
    
    cols = ("Data", "Resíduo", "Modo", "Qtd", "Total", "NF?", "Cert?")
    tree_lote = ttk.Treeview(frame_lista, columns=cols, show="headings", height=8)
    tree_lote.pack(side="left", fill="both", expand=True)
    
    for c in cols: tree_lote.heading(c, text=c); tree_lote.column(c, anchor="center")
    tree_lote.column("Resíduo", width=250, anchor="w") # Alinha nome à esquerda
    tree_lote.column("Data", width=90)
    tree_lote.column("Total", anchor="e")
    
    sb = ttk.Scrollbar(frame_lista, orient="vertical", command=tree_lote.yview)
    tree_lote.configure(yscroll=sb.set); sb.pack(side="right", fill="y")
    
    # Botão Remover
    frame_act = tb.Frame(lote_win, padding=(15,0)); frame_act.pack(fill="x")
    def remover_item():
        sel = tree_lote.selection()
        if not sel: return
        for i in reversed(sel):
            idx = tree_lote.index(i)
            del itens_da_carga[idx]
            tree_lote.delete(i)
    tb.Button(frame_act, text="Remover Item Selecionado", bootstyle="danger-outline", command=remover_item).pack(side="right")
    tree_lote.bind("<Delete>", lambda e: remover_item())

    # ===========================
    # 4. SALVAR
    # ===========================
# Em Gerenciamento de resíduos.py
    # Dentro da função salvar_carga_banco()

    def salvar_carga_banco():
        if not itens_da_carga: ModernMessageBox.showwarning("Vazio", "Adicione itens."); return
        parc = parc_cb.get(); dest = dest_cb.get(); tip = tipo_cb.get(); ped = pedido_entry.get()
        if not parc or not dest: ModernMessageBox.showerror("Erro", "Parceiro/Destino obrigatórios."); return

        sucessos = 0
        for item in itens_da_carga:
            # --- CORREÇÃO AQUI: Adicionados os campos faltantes ---
            reg = [
                item['data_db'],       # 1. Data
                parc,                  # 2. Parceiro
                item['residuo'],       # 3. Residuo
                item['estado'],        # 4. Estado
                dest,                  # 5. Destinacao
                tip,                   # 6. Tipo
                item['modo'],          # 7. Modo
                item['qtd_input'],     # 8. Peso (Input)
                item['valor_unit'],    # 9. ValorPorKg
                item['valor_fechado'], # 10. ValorFechado
                0.0,                   # 11. Transporte
                item['total'],         # 12. ValorTotal
                ped,                   # 13. PedidoCompra
                "",                    # 14. NumMTR
                item['cert_ok'],       # 15. CertificadoOK
                item['peso_calc'],     # 16. PesoEmKg
                item['nf_ok'],         # 17. NFOk (Adicionado)
                ""                     # 18. CaminhoAnexo (Adicionado - Vazio p/ Lote)
            ]
            # -----------------------------------------------------

            try:
                rec_id = db.add_registro(reg)
                
                # Verifica se o ID é válido (maior que -1) antes de contar sucesso
                if rec_id != -1:
                    # O NFOk já foi passado na lista acima, mas o update garante integridade se houver lógica extra no DB
                    if hasattr(db, 'update_nf'):
                        db.update_nf(rec_id, item['nf_ok'])
                    sucessos += 1
                else:
                    print(f"Erro DB ao salvar item do lote: {item['residuo']}")

            except Exception as e: print(f"Erro lote: {e}")

        if sucessos > 0:
            ModernMessageBox.showinfo("Sucesso", f"{sucessos} registros salvos!"); lote_win.destroy(); atualizar_views()
        else:
            ModernMessageBox.showerror("Erro", "Nenhum registro foi salvo.\n\n" + detalhe_erro_db("Erro no banco de dados."))
            
    # --- 1. LINHA DIVISÓRIA ---
    tb.Separator(lote_win).pack(fill="x", padx=15, pady=(15, 5))
    
    # --- 2. PAINEL VERDE DE PREVIEW ---
    tb.Label(lote_win, textvariable=item_preview_var, font=("Segoe UI", 18, "bold"), bootstyle="success").pack(anchor="e", padx=30, pady=(0, 15))
    
    # --- 3. BOTÃO GRANDE DE SALVAR (Restaurado!) ---
    tb.Button(lote_win, text="CONCLUIR E SALVAR TUDO", bootstyle="success", width=30, command=salvar_carga_banco).pack(fill="x", padx=30, pady=(0,20))


# --- Botões da Aba 1 ---
cad_actions = tb.Frame(aba_cad)
# AQUI ESTÁ O RESPIRO: pady=(30, 15) empurra toda essa barra 30 pixels para baixo
cad_actions.pack(fill="x", pady=(30, 15)) 

# Botões com width=20 para ficarem simétricos
btn_submit = tb.Button(cad_actions, text="Adicionar Registro", bootstyle=SUCCESS, width=20)
btn_submit.pack(side="left", padx=(0, 15)) # O padx afasta este botão do botão de limpar

btn_clear_form = tb.Button(cad_actions, text="Limpar Formulário", bootstyle="secondary-outline", width=20)
btn_clear_form.pack(side="left")

# --- NOVO BOTÃO DE LOTE (Mantido à direita) ---
btn_lote = tb.Button(cad_actions, text="Lançamento em Lote (Carga)", bootstyle="info-outline", command=abrir_janela_lote)
btn_lote.pack(side="right", padx=10)

frm_ana = tb.Labelframe(aba_cad, text="Nova análise externa", padding=12, bootstyle=INFO); frm_ana.pack(fill="x", pady=(20, 0)); # Adicionei um pady
for i in range(3): frm_ana.columnconfigure(i, weight=1)
# Linha 1
tb.Label(frm_ana, text="Data").grid(row=0, column=0, sticky="w", padx=(0,8)); ana_data = CalendarioPremium(frm_ana, dateformat="%d/%b/%y"); ana_data.grid(row=1, column=0, sticky="ew", padx=(0,8), pady=(0, 10))
tb.Label(frm_ana, text="Laboratório / Parceiro").grid(row=0, column=1, sticky="w", padx=(0,8)); ana_parc_var = tk.StringVar(value=(parceiros[0] if parceiros else "")); ana_parc_cb = tb.Combobox(frm_ana, textvariable=ana_parc_var, values=parceiros, state="readonly"); ana_parc_cb.grid(row=1, column=1, sticky="ew", padx=(0,8), pady=(0, 10))
tb.Label(frm_ana, text="Nome da análise").grid(row=0, column=2, sticky="w", padx=(0,0)); ana_nome_var = tk.StringVar(value=(lista_analises[0] if lista_analises else "")); ana_nome_cb = tb.Combobox(frm_ana, textvariable=ana_nome_var, values=lista_analises, state="readonly"); ana_nome_cb.grid(row=1, column=2, sticky="ew", padx=(0,0), pady=(0, 10))
# Linha 2
tb.Label(frm_ana, text="Valor fechado (R$)").grid(row=2, column=0, sticky="w", padx=(0,8), pady=(10,0)); ana_valor_fechado = tb.Entry(frm_ana, validate="key", validatecommand=vcmd_numeric); ana_valor_fechado.grid(row=3, column=0, sticky="ew", padx=(0,8))
frame_compl_ana = tb.Frame(frm_ana)
frame_compl_ana.grid(row=4, column=0, columnspan=3, sticky="w", padx=8, pady=5)

var_nf_ana = tk.IntVar(value=1)   # Padrão: Exige NF
var_cert_ana = tk.IntVar(value=0) # Padrão: Não exige Certificado

tb.Checkbutton(frame_compl_ana, text="Exige NF", variable=var_nf_ana, bootstyle="round-toggle").pack(side="left", padx=(0, 15))
tb.Checkbutton(frame_compl_ana, text="Exige Certificado", variable=var_cert_ana, bootstyle="round-toggle").pack(side="left")

tb.Label(frm_ana, text="Pedido de compra (opcional)").grid(row=2, column=1, sticky="w", padx=(0,8), pady=(10,0)); ana_pedido = tb.Entry(frm_ana); ana_pedido.grid(row=3, column=1, sticky="ew", padx=(0,8))
btn_ana_add = tb.Button(aba_cad, text="Adicionar análise (custo)", bootstyle=SUCCESS); btn_ana_add.pack(pady=15, anchor="w")

# ======================================================
# UI DE LANÇAMENTO DE TRANSPORTE (AUTOMATIZADA)
# ======================================================
frm_transporte = tb.Labelframe(aba_cad, text="Novo Lançamento de Frete", padding=12, bootstyle=WARNING)
frm_transporte.columnconfigure((0, 1, 2), weight=1)

# Linha 1
tb.Label(frm_transporte, text="Data").grid(row=0, column=0, sticky="w", padx=5)
transp_data = CalendarioPremium(frm_transporte, dateformat="%d/%b/%y")
transp_data.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 10))

tb.Label(frm_transporte, text="Transportadora").grid(row=0, column=1, sticky="w", padx=5)
transp_parc_var = tk.StringVar()
transp_parc_cb = tb.Combobox(frm_transporte, textvariable=transp_parc_var, values=parceiros, state="readonly")
transp_parc_cb.grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 10))

# --- MUDANÇA: Resíduo agora é OBRIGATÓRIO e define o destino ---
tb.Label(frm_transporte, text="Resíduo Atrelado (Obrigatório)").grid(row=0, column=2, sticky="w", padx=5)
transp_res_var = tk.StringVar()
transp_res_cb = tb.Combobox(frm_transporte, textvariable=transp_res_var, values=banco_residuos, state="readonly")
transp_res_cb.grid(row=1, column=2, sticky="ew", padx=5, pady=(0, 10))
# --------------------------------------------------------------

# Linha 2
tb.Label(frm_transporte, text="Valor do Frete (R$)").grid(row=2, column=0, sticky="w", padx=5)
transp_valor = tb.Entry(frm_transporte, validate="key", validatecommand=vcmd_numeric)
transp_valor.grid(row=3, column=0, sticky="ew", padx=5, pady=(0, 10))

tb.Label(frm_transporte, text="Pedido de Compra / Ticket").grid(row=2, column=1, columnspan=2, sticky="w", padx=5)
transp_pedido = tb.Entry(frm_transporte)
transp_pedido.grid(row=3, column=1, columnspan=2, sticky="ew", padx=5, pady=(0, 10))
frame_compl_transp = tb.Frame(frm_transporte)
frame_compl_transp.grid(row=4, column=0, columnspan=3, sticky="w", padx=5, pady=5)

var_nf_transp = tk.IntVar(value=1) # Transporte geralmente tem NF
var_cert_transp = tk.IntVar(value=0) # Transporte geralmente NÃO tem certificado

chk_nf_tr = tb.Checkbutton(frame_compl_transp, text="Exige NF (CT-e)", variable=var_nf_transp, bootstyle="round-toggle")
chk_nf_tr.pack(side="left", padx=(0, 15))

chk_cert_tr = tb.Checkbutton(frame_compl_transp, text="Exige Certificado", variable=var_cert_transp, bootstyle="round-toggle")
chk_cert_tr.pack(side="left")

# Botão Adicionar (Mova para a linha 5)
btn_transporte_add = tb.Button(frm_transporte, text="Adicionar Frete (Custo)", bootstyle=WARNING)
btn_transporte_add.grid(row=5, column=0, columnspan=3, sticky="w", padx=5, pady=10)

def adicionar_transporte_event(_=None):
    # --- 1. COLETA DE DADOS ---
    try:
        # Pega a data do campo específico de transporte
        data_obj = obter_data_segura(transp_data)
        data_str = data_obj.strftime("%Y-%m-%d")
    except Exception:
        ModernMessageBox.showerror("Erro", "Data inválida.")
        return

    parceiro = clean_str(transp_parc_var.get())
    residuo_base = clean_str(transp_res_var.get())
    val_str = transp_valor.get()
    valor_frete = money_pt(val_str)
    pedido = clean_str(transp_pedido.get())

    # --- 2. VALIDAÇÕES ---
    if not parceiro:
        ModernMessageBox.showwarning("Aviso", "Selecione a Transportadora/Parceiro.")
        return
    if not residuo_base:
        ModernMessageBox.showwarning("Aviso", "Selecione o Resíduo atrelado ao frete.")
        return
    if valor_frete <= 0:
        ModernMessageBox.showwarning("Aviso", "O valor do frete deve ser maior que zero.")
        return

    # --- 3. AUTO-PREENCHIMENTO DE DADOS DO RESÍDUO ---
    # Busca Estado e Destinação padrão do resíduo selecionado
    dados_res = banco_dict.get(residuo_base, {})
    estado_auto = dados_res.get('estado_padrao', 'Sólido')
    destinacao_auto = dados_res.get('destinacao_padrao', 'N/A')

    # Nome final no banco (Ex: "[FRETE] Papelão")
    nome_final = f"[FRETE] {residuo_base}"

    # --- 4. LÓGICA DE COMPLIANCE ---
    nf_status = "Não" if var_nf_transp.get() else "N/A"
    cert_status = "Não" if var_cert_transp.get() else "N/A"

    # --- 5. MONTAGEM DA LISTA (18 CAMPOS - Para bater com database.py) ---
    transporte_data = [
        data_str,           # 1. Data
        parceiro,           # 2. Parceiro
        nome_final,         # 3. Residuo
        estado_auto,        # 4. Estado
        destinacao_auto,    # 5. Destinacao
        "Custo",            # 6. Tipo
        "fechado",          # 7. Modo
        0.0,                # 8. Peso Input
        0.0,                # 9. Valor kg
        0.0,                # 10. Valor Fechado (Item)
        float(valor_frete), # 11. Transporte (O valor vai aqui)
        float(valor_frete), # 12. Total
        pedido,             # 13. Pedido
        "",                 # 14. MTR
        cert_status,        # 15. CertificadoOK
        0.0,                # 16. PesoEmKg
        nf_status,          # 17. NFOk
        ""                  # 18. CaminhoAnexo
    ]

    # --- 6. SALVAR NO BANCO ---
    try:
        rec_id = db.add_registro(transporte_data)
        
        # CORREÇÃO: Verifica explicitamente se é maior que 0
        if rec_id is not None and rec_id > 0:
            if hasattr(db, 'update_nf'): 
                db.update_nf(rec_id, nf_status) 
            
            atualizar_views()
            
            # Limpa os campos após salvar
            transp_valor.delete(0, tk.END)
            transp_pedido.delete(0, tk.END)
            
            set_status("Frete adicionado com sucesso.")
            ModernMessageBox.showinfo("Sucesso", "Frete lançado!")
        else:
            # Se falhar, agora vai mostrar o erro real
            ModernMessageBox.showerror("Erro de Banco de Dados", 
                               "Não foi possível salvar o registro.\n\n" + detalhe_erro_db(
                               "Verifique se o arquivo 'residuos_db.sqlite' não está aberto em outro programa."))

    except Exception as e: 
        ModernMessageBox.showerror("Erro Crítico", f"Erro ao adicionar transporte: {e}")

def adicionar_analise_event(_=None):
    """Lógica para salvar/editar registro de Análise Externa."""
    
    # --- 1. COLETA DE DADOS ---
    try:
        data_str = obter_data_segura(ana_data).strftime("%Y-%m-%d")
    except Exception:
        ModernMessageBox.showerror("Erro", "Data inválida."); return

    parceiro = clean_str(ana_parc_var.get())
    nome_analise = clean_str(ana_nome_var.get())
    val_str = ana_valor_fechado.get()
    valor_total = money_pt(val_str)
    pedido = clean_str(ana_pedido.get())

    # --- 2. VALIDAÇÕES ---
    if not parceiro:
        ModernMessageBox.showwarning("Aviso", "Selecione o Laboratório/Parceiro.")
        return
    if not nome_analise:
        ModernMessageBox.showwarning("Aviso", "Selecione o Nome da Análise.")
        return
    if valor_total <= 0:
        ModernMessageBox.showwarning("Aviso", "O valor deve ser maior que zero.")
        return

    # --- 3. PREPARAÇÃO DO NOME E DADOS ---
    # Adiciona o prefixo [ANÁLISE] se ainda não tiver (para diferenciar no banco)
    if not nome_analise.startswith("[ANÁLISE]"):
        residuo_final = f"[ANÁLISE] {nome_analise}"
    else:
        residuo_final = nome_analise

    # --- 4. LÓGICA DE COMPLIANCE (CHECKBOXES ESPECÍFICOS DA ABA ANÁLISE) ---
    nf_status = "Não" if var_nf_ana.get() else "N/A"
    cert_status = "Não" if var_cert_ana.get() else "N/A"

    # --- 5. VERIFICA SE É EDIÇÃO ---
    # Verifica se existe um ID atrelado ao botão (colocado pela função iniciar_edicao)
    editing_id = getattr(btn_ana_add, 'editing_id', None)
    
    # Se não achou no botão, tenta a variável global EDITING_ID se o tipo for Análise
    if editing_id is None and globals().get('EDITING_ID') is not None:
        if launch_type_var.get() == "Análise":
            editing_id = EDITING_ID

    # Se for edição, tentamos manter o status anterior se não for N/A
    if editing_id is not None:
        try:
            val_antigo_nf = df_registros_global.loc[editing_id, 'NFOk']
            # Se o checkbox diz que precisa (Não), mas o banco já diz 'Sim' ou 'Solicitado', mantemos o banco
            if nf_status == "Não" and val_antigo_nf not in ("N/A", "n/a"):
                nf_status = val_antigo_nf
                
            val_antigo_cert = df_registros_global.loc[editing_id, 'CertificadoOK']
            if cert_status == "Não" and val_antigo_cert not in ("N/A", "n/a"):
                cert_status = val_antigo_cert
        except: pass

    # --- 6. MONTAGEM DA LISTA (18 CAMPOS) ---
    registro_analise = [
        data_str,           # 1. Data
        parceiro,           # 2. Parceiro
        residuo_final,      # 3. Residuo (Com prefixo [ANÁLISE])
        "N/A",              # 4. Estado <--- CORREÇÃO: Mude de "Sólido" para "N/A"
        "Análise externa",  # 5. Destinacao
        "Custo",            # 6. Tipo
        "fechado",          # 7. Modo
        0.0,                # 8. Peso Input
        0.0,                # 9. Valor kg
        float(valor_total), # 10. Valor Fechado (Item)
        0.0,                # 11. Transporte
        float(valor_total), # 12. Total
        pedido,             # 13. Pedido
        "",                 # 14. MTR
        cert_status,        # 15. CertificadoOK
        0.0,                # 16. PesoEmKg
        nf_status,          # 17. NFOk
        ""                  # 18. CaminhoAnexo
    ]

    # --- 7. SALVAR NO BANCO ---
    try:
        if editing_id is not None:
            # UPDATE
            if db.update_registro(editing_id, registro_analise):
                # Gambiarra segura para NF
                if hasattr(db, 'update_nf'): db.update_nf(editing_id, nf_status)
                
                set_status("Análise atualizada com sucesso.")
                ModernMessageBox.showinfo("Sucesso", "Análise atualizada!")
            else:
                ModernMessageBox.showerror("Erro", "Falha ao atualizar registro no banco.")
        else:
            # INSERT
            rec_id = db.add_registro(registro_analise)
            if rec_id and rec_id != -1:
                # Gambiarra segura para NF
                if hasattr(db, 'update_nf'): db.update_nf(rec_id, nf_status)
                
                set_status("Análise adicionada com sucesso.")
                ModernMessageBox.showinfo("Sucesso", "Análise lançada!")
            else:
                ModernMessageBox.showerror("Erro", "Falha ao salvar registro no banco.")

        # Limpa e Atualiza
        clear_form_analise()
        atualizar_views()
        
        # Se foi edição, volta para aba registros
        if editing_id is not None:
            nb.select(aba_regs)

    except Exception as e:
        ModernMessageBox.showerror("Erro Crítico", f"Erro ao salvar análise: {e}")
        print(f"Erro save analise: {e}")
        
def atualizar_valor_por_analise(*_):
    """Preenche o valor fechado na Aba Análises Externas com base na análise selecionada."""
    nome_analise = clean_str(ana_nome_var.get())
    valor_padrao = analises_dict.get(nome_analise, 0.0) # Busca no novo dict

    # Limpa o campo primeiro
    ana_valor_fechado.delete(0, tk.END)

    # Preenche se valor > 0
    if valor_padrao > 0:
        ana_valor_fechado.insert(0, f"{valor_padrao:.2f}".replace(".", ","))
##        print(f"DEBUG: Preencheu valor análise '{nome_analise}' com {valor_padrao}") # DEBUG
    else:
        print(f"DEBUG: Análise '{nome_analise}' sem valor padrão (>0).") # DEBUG

ana_nome_var.trace_add("write", atualizar_valor_por_analise) # Trace na variável
ana_nome_cb.bind("<<ComboboxSelected>>", atualizar_valor_por_analise) # Bind na seleção

# ===================================================================
# ABA 2 (Reposicionada) — Calendário Visual
# ===================================================================
# Layout Principal
aba_cal.columnconfigure(0, weight=3) 
aba_cal.columnconfigure(1, weight=1)
aba_cal.rowconfigure(0, weight=1)

# --- Lado Esquerdo: Calendário ---
frame_cal_widget = tb.Labelframe(aba_cal, text="Visão Mensal", padding=10, bootstyle=INFO)
frame_cal_widget.grid(row=0, column=0, sticky="nsew", padx=(0,10))

# Área de Navegação
frame_nav_cal = tb.Frame(frame_cal_widget)
frame_nav_cal.pack(fill="x", pady=(0, 10))

titulo_mes_var = tk.StringVar(value="Mês Atual")

# Funções de Navegação (Mantidas iguais)
def atualizar_titulo_mes(event=None):
    try:
        m, y = cal_visual.get_displayed_month()
        nome_mes = PT_ABREV_LIST[m-1].capitalize() 
        titulo_mes_var.set(f"{nome_mes}/{y}")
    except Exception: pass

def navegar_calendario(delta):
    m, y = cal_visual.get_displayed_month()
    m += delta
    if m > 12: m = 1; y += 1
    elif m < 1: m = 12; y -= 1
    cal_visual.see(date(y, m, 1))
    atualizar_titulo_mes()

def ir_para_hoje():
    hoje = datetime.now().date()
    cal_visual.see(hoje)
    cal_visual.selection_set(hoje)
    on_cal_click(None)
    atualizar_titulo_mes()

btn_prev_cal = tb.Button(frame_nav_cal, text="< Anterior", bootstyle="outline-primary", command=lambda: navegar_calendario(-1))
btn_prev_cal.pack(side="left")

lbl_mes_cal = tb.Label(frame_nav_cal, textvariable=titulo_mes_var, font=("Segoe UI", 14, "bold"), bootstyle="primary", anchor="center")
lbl_mes_cal.pack(side="left", fill="x", expand=True)

btn_hoje_cal = tb.Button(frame_nav_cal, text="Hoje", bootstyle="info-outline", command=ir_para_hoje)
btn_hoje_cal.pack(side="left", padx=10)

btn_next_cal = tb.Button(frame_nav_cal, text="Próximo >", bootstyle="outline-primary", command=lambda: navegar_calendario(1))
btn_next_cal.pack(side="left")

# --- CORREÇÃO DO LAYOUT (A SOLUÇÃO DEFINITIVA) ---

# 1. Reseta a estrutura do Label do calendário.
# O ttkbootstrap altera a estrutura padrão, fazendo o texto sumir em alguns widgets do tkcalendar.
# Aqui nós dizemos: "Desenhe uma borda, um preenchimento e O TEXTO".
style.layout('Calendar.TLabel', [
    ('Label.border', {'sticky': 'nswe', 'children': [
        ('Label.padding', {'sticky': 'nswe', 'children': [
            ('Label.label', {'sticky': 'nswe'}) # <--- O elemento que desenha o texto e imagem
        ]})
    ]})
])

# 2. Configura as cores e fonte após corrigir o layout
# --- GARANTIA DE TAMANHO E COR ---
# width=3: Força o label a ter largura de 3 caracteres, mesmo se o texto falhar.
# anchor='center': Centraliza o texto.
style.configure('Calendar.TLabel', 
                foreground='black', 
                background='#e1e1e1', 
                font=('Segoe UI', 9, 'bold'),
                width=3, 
                anchor='center')

# 3. Garante que as cores não mudem com o mouse
style.map('Calendar.TLabel', 
          foreground=[('!disabled', '#000000')],
          background=[('!disabled', '#e1e1e1')])

import locale

# --- Tenta definir o Locale do Windows para Português ---
# O Windows usa 'Portuguese_Brazil', não 'pt_BR'.
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.utf8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil')
    except locale.Error:
        print("Aviso: Locale português não encontrado. Usando padrão.")

# --- Criação do Calendário ---
# Instanciação simplificada (a classe CalendarFix resolve o resto)
cal_visual = CalendarFix(
    frame_cal_widget, 
    selectmode='day', 
    date_pattern='dd/mm/yyyy', 
    cursor="hand2",
    # Não precisamos mais brigar com locale ou font aqui, 
    # a função force_header_fix vai sobrescrever.
    
    showweeknumbers=False,
    showothermonthdays=False, 
    firstweekday='sunday'
)
cal_visual.pack(fill="both", expand=True, pady=5)

app.after(100, atualizar_titulo_mes)

lbl_legenda = tb.Label(frame_cal_widget, text="Legenda: 🟢 = Dia com Movimentação Registrada", bootstyle="success")
lbl_legenda.pack(pady=5)

# --- Lado Direito: Detalhes ---
frame_cal_detalhes = tb.Labelframe(aba_cal, text="Detalhes do Dia Selecionado", padding=10, bootstyle=WARNING)
frame_cal_detalhes.grid(row=0, column=1, sticky="nsew", padx=(5,0))

# 1. Definindo as colunas
cal_cols = ("Resíduo", "Parceiro", "Peso/Qtd", "Valor Total", "Tipo")
cal_tree = ttk.Treeview(frame_cal_detalhes, columns=cal_cols, show="headings", selectmode="extended")

# 2. Configurando Cabeçalhos e Larguras (TUDO CENTRALIZADO)
cal_tree.heading("Resíduo", text="Resíduo");     cal_tree.column("Resíduo", width=130, anchor="center") # <--- Center
cal_tree.heading("Parceiro", text="Parceiro");   cal_tree.column("Parceiro", width=100, anchor="center") # <--- Center
cal_tree.heading("Peso/Qtd", text="Peso / Qtd"); cal_tree.column("Peso/Qtd", width=140, anchor="center") # <--- Center e +Largo
cal_tree.heading("Valor Total", text="Total (R$)"); cal_tree.column("Valor Total", width=90, anchor="center") # <--- Center
cal_tree.heading("Tipo", text="Tipo");           cal_tree.column("Tipo", width=60, anchor="center")

cal_tree.pack(fill="both", expand=True)

# 3. Label de Soma
lbl_soma_cal = tb.Label(
    frame_cal_detalhes, 
    text="Total Selecionado: R$ 0,00", 
    font=("Segoe UI", 11, "bold"), 
    bootstyle="inverse-info",
    anchor="center"
)
lbl_soma_cal.pack(fill="x", pady=(5,0))

# --- LÓGICA ---
def somar_selecao_calendario(event):
    """Soma os valores das linhas selecionadas na tabela do calendário."""
    selection = cal_tree.selection()
    soma = Decimal("0.00")
    
    for iid in selection:
        # Pega os valores da linha: (Residuo, Parceiro, Peso, ValorTotal, Tipo)
        valores = cal_tree.item(iid)['values']
        
        # O Valor Total está no índice 3 (quarta coluna)
        # O formato vem como "R$ 1.000,00", precisamos limpar para somar
        val_str = str(valores[3]).replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
        try:
            soma += Decimal(val_str)
        except:
            pass
            
    # Atualiza o Label lá embaixo
    lbl_soma_cal.config(text=f"Total Selecionado: {fmt_moeda(soma)}")

# LIGA O EVENTO: Toda vez que selecionar uma linha, chama a função
cal_tree.bind("<<TreeviewSelect>>", somar_selecao_calendario)

def on_cal_click(event):
    data_sel_str = cal_visual.get_date() 
    
    # Limpa a tabela e zera a soma visual
    for r in cal_tree.get_children(): cal_tree.delete(r)
    lbl_soma_cal.config(text="Total Selecionado: R$ 0,00")
    
    try:
        dt_sel = datetime.strptime(data_sel_str, "%d/%m/%Y").date()
        df_temp = df_registros_global.copy()
        df_temp['Data'] = pd.to_datetime(df_temp['Data'], errors='coerce')
        
        # Filtra pelo dia
        itens_do_dia = df_temp[df_temp['Data'].dt.date == dt_sel]
        
        if itens_do_dia.empty: return
        
        for _, row in itens_do_dia.iterrows():
            # Pega os valores brutos
            peso_input = to_float_safe(row.get("Peso", 0))       # O que foi digitado (qtd ou kg)
            peso_real_kg = to_float_safe(row.get("PesoEmKg", 0)) # O peso total calculado
            modo = str(row.get("Modo", "kg")).lower()
            
            # --- LÓGICA DE EXIBIÇÃO FORMATADA ---
            if modo == 'unidade':
                # Formata: "170 un (340 kg)"
                # Se o peso em KG for maior que 0, mostra entre parênteses
                if peso_real_kg > 0:
                    p_display = f"{peso_input:.0f} un ({fmt_kg(peso_real_kg)})"
                else:
                    p_display = f"{peso_input:.0f} un"
            else:
                # Se for KG normal, só mostra o KG
                p_display = fmt_kg(peso_input)
            
            # Formata Valor Total
            valor_total = to_float_safe(row.get("ValorTotal", 0.0))
            v_display = fmt_moeda(valor_total)

            # Insere na tabela
            cal_tree.insert("", "end", values=(
                clean_str(row.get("Residuo", "")), 
                clean_str(row.get("Parceiro", "")), 
                p_display,   # <--- Texto formatado aqui
                v_display, 
                clean_str(row.get("Tipo", ""))
            ))
            
    except Exception as e: 
        print(f"Erro ao carregar detalhes do dia: {e}")

# --- FUNÇÃO QUE FALTAVA ---
def atualizar_eventos_calendario():
    """Pinta os dias no calendário que possuem registros."""
    try:
        cal_visual.calevent_remove("all") # Limpa marcações anteriores
        
        if df_registros_global.empty: return

        df_temp = df_registros_global.copy()
        df_temp['Data'] = pd.to_datetime(df_temp['Data'], errors='coerce')
        df_temp = df_temp.dropna(subset=['Data'])
        
        datas_unicas = df_temp['Data'].dt.date.unique()
        
        for d in datas_unicas:
            # Cria um evento visual para o dia
            cal_visual.calevent_create(d, "Movimentação", "coleta")
        
        # Define a cor da marcação (Fundo verde claro, texto preto)
        cal_visual.tag_config("coleta", background="#d1e7dd", foreground="black")
        
    except Exception as e:
        print(f"Erro ao atualizar eventos do calendário: {e}")

cal_visual.bind("<<CalendarSelected>>", on_cal_click)
cal_visual.bind("<<CalendarMonthChanged>>", atualizar_titulo_mes)


# =========================
# ABA 2 — Registros (UI Formatada)
# =========================
# (Código UI da Aba 2 formatado)
#aba_regs = tb.Frame(nb, padding=12);
#nb.add(aba_regs, text="Registros");
filtros = tb.Labelframe(aba_regs, text="Filtros", padding=(10, 5), bootstyle=INFO);
filtros.pack(fill="x", pady=(0, 10)); # Aumenta espaço abaixo

# Configura 5 colunas principais com peso igual
for i in range(5):
    filtros.columnconfigure(i, weight=1, uniform="filters")

# --- Linha 1: Filtros Dropdown ---
row1 = 0

# Coluna 0: Parceiro
tb.Label(filtros, text="Parceiro").grid(row=row1, column=0, sticky="w", padx=(0,5), pady=(0,2))
f_parc = tk.StringVar(value="Todos")
parc_menu = tb.Combobox(filtros, textvariable=f_parc, values=["Todos"] + parceiros, state="readonly")
parc_menu.grid(row=row1+1, column=0, sticky="ew", padx=(0,10), pady=(0, 10))

# Coluna 1: Resíduo
tb.Label(filtros, text="Resíduo").grid(row=row1, column=1, sticky="w", padx=(0,5), pady=(0,2))
f_res = tk.StringVar(value="Todos")
res_menu = tb.Combobox(filtros, textvariable=f_res, values=["Todos"] + banco_residuos, state="normal")
res_menu.grid(row=row1+1, column=1, sticky="ew", padx=(0,10), pady=(0, 10))

# Coluna 2: Estado
tb.Label(filtros, text="Estado").grid(row=row1, column=2, sticky="w", padx=(0,5), pady=(0,2))
f_estado = tk.StringVar(value="Todas")
estado_menu = tb.Combobox(filtros, textvariable=f_estado, values=["Todas", "Sólido", "Líquido"], state="readonly")
estado_menu.grid(row=row1+1, column=2, sticky="ew", padx=(0,10), pady=(0, 10))

# Coluna 3: Destinação
tb.Label(filtros, text="Destinação").grid(row=row1, column=3, sticky="w", padx=(0,5), pady=(0,2))
f_dest = tk.StringVar(value="Todas")
dest_menu = tb.Combobox(filtros, textvariable=f_dest, values=["Todas"] + destinacoes, state="readonly")
dest_menu.grid(row=row1+1, column=3, sticky="ew", padx=(0,10), pady=(0, 10))

# Coluna 4: Tipo
tb.Label(filtros, text="Tipo").grid(row=row1, column=4, sticky="w", padx=(0,5), pady=(0,2))
f_tipo = tk.StringVar(value="Todos")
tipo_menu = tb.Combobox(filtros, textvariable=f_tipo, values=["Todos", "Venda", "Custo"], state="readonly")
tipo_menu.grid(row=row1+1, column=4, sticky="ew", padx=(0,10), pady=(0, 10))

# --- Linha 2: Datas e Botões Rápidos ---
row2 = 2 

# Frame para Agrupar Datas + Botões Rápidos
frame_datas = tb.Frame(filtros)
frame_datas.grid(row=row2+1, column=0, columnspan=2, sticky="w", padx=0, pady=(0,10))

# Data Início
tb.Label(filtros, text="Data Início").grid(row=row2, column=0, sticky="w", padx=(0,5), pady=(0,2))
f_data_inicio = CalendarioPremium(frame_datas, dateformat="%d/%m/%y")
f_data_inicio.set_date(DATA_INICIO_MES_GLOBAL)
f_data_inicio.pack(side="left", padx=(0, 5))

# Data Fim
tb.Label(filtros, text="Data Fim").grid(row=row2, column=1, sticky="w", padx=(0,5), pady=(0,2))
f_data_fim = CalendarioPremium(frame_datas, dateformat="%d/%m/%y")
f_data_fim.set_date(DATA_HOJE_GLOBAL)
f_data_fim.pack(side="left", padx=(0, 10))

# --- FUNÇÃO DE FILTRO RÁPIDO ---
def aplicar_filtro_rapido(periodo):
    hoje = date.today()
    if periodo == "mes":
        ini = hoje.replace(day=1)
        fim = hoje
    elif periodo == "ano":
        ini = hoje.replace(day=1, month=1)
        fim = hoje
    elif periodo == "tudo":
        ini = date(2020, 1, 1) # Data bem antiga
        fim = hoje
    elif periodo == "mes_passado":
        # Lógica simples para mês passado
        primeiro_deste_mes = hoje.replace(day=1)
        ultimo_mes_passado = primeiro_deste_mes - timedelta(days=1)
        ini = ultimo_mes_passado.replace(day=1)
        fim = ultimo_mes_passado
        
    f_data_inicio.set_date(ini)
    f_data_fim.set_date(fim)
    atualizar_views()

# Botões Pequenos (Outline)
btn_mes = tb.Button(frame_datas, text="Este Mês", bootstyle="outline-primary", width=8, command=lambda: aplicar_filtro_rapido("mes"))
btn_mes.pack(side="left", padx=2)

btn_mes_passado = tb.Button(frame_datas, text="Mês Passado", bootstyle="outline-primary", width=12, command=lambda: aplicar_filtro_rapido("mes_passado"))
btn_mes_passado.pack(side="left", padx=2)

btn_ano = tb.Button(frame_datas, text="Este Ano", bootstyle="outline-primary", width=8, command=lambda: aplicar_filtro_rapido("ano"))
btn_ano.pack(side="left", padx=2)

btn_all = tb.Button(frame_datas, text="Tudo", bootstyle="outline-secondary", width=6, command=lambda: aplicar_filtro_rapido("tudo"))
btn_all.pack(side="left", padx=2)


# Coluna 2 e 3: Busca (Ocupa 2 colunas) - Mantido Igual
tb.Label(filtros, text="Busca (Resíduo/Parceiro/Pedido)").grid(row=row2, column=2, columnspan=2, sticky="w", padx=(0,5), pady=(0,2))
f_busca = tk.StringVar()
tb.Entry(filtros, textvariable=f_busca).grid(row=row2+1, column=2, columnspan=2, sticky="ew", padx=(0,10), pady=(0, 10))

# Coluna 4: Botão Filtrar Principal - Mantido Igual
btn_filtrar_regs = tb.Button(filtros, text="Filtrar", bootstyle=SUCCESS)
btn_filtrar_regs.grid(row=row2+1, column=4, sticky="ew", padx=(0, 10), pady=(0, 10))

tbl_card = tb.Labelframe(aba_regs, text="Registros", padding=6, bootstyle=INFO); tbl_card.pack(fill="both", expand=True, pady=(10,0)); tbl_card.rowconfigure(0, weight=1); tbl_card.columnconfigure(0, weight=1)
colunas_tv = COLUMNS_DISPLAY
tabela = ttk.Treeview(tbl_card, columns=colunas_tv, show="headings", selectmode="extended")
tabela.grid(row=0, column=0, sticky="nsew")
sy=ttk.Scrollbar(tbl_card, orient="vertical", command=tabela.yview)
sx=ttk.Scrollbar(tbl_card, orient="horizontal", command=tabela.xview)
tabela.configure(yscroll=sy.set, xscroll=sx.set)
sy.grid(row=0, column=1, sticky="ns"); sx.grid(row=1, column=0, sticky="ew")

larg = { 
    "Data": 85, "Parceiro": 160, "Resíduo": 160, "Estado": 70, 
    "Destinação": 140, "Tipo": 70, "Peso": 100, "Valor por kg": 100, 
    "Valor fechado": 100, "Transporte": 100, "Valor Total": 110, 
    "Pedido de Compra": 110, "Certificado OK": 70, "NF OK": 60
}

# Colunas que devem ficar alinhadas à DIREITA (Números)
cols_numericas = ["Peso", "Valor por kg", "Valor fechado", "Transporte", "Valor Total"]
# Colunas que devem ficar CENTRADAS (Status/Datas)
cols_centro = ["Data", "Parceiro", "Resíduo", "Estado", "Destinação", "Tipo", "Certificado OK", "NF OK"]

TITULOS_TABELA = {}
for c in colunas_tv:
    header_name = c
    if c == "Valor por kg": header_name = "R$/kg" # Encurta o título
    TITULOS_TABELA[c] = header_name
    
    # Define o alinhamento baseado no tipo de dado
    if c in cols_numericas:
        meu_anchor = "e" # East (Direita)
    elif c in cols_centro:
        meu_anchor = "center"
    else:
        meu_anchor = "center" # West (Esquerda) - Padrão para texto
        
    tabela.heading(c, text=header_name, command=lambda col=c: ordenar_coluna(col))
    tabela.column(c, width=larg.get(c, 100), anchor=meu_anchor, stretch=True)

# --- ADICIONADO: StringVar para o resumo da seleção ---
resumo_selecao_var = tk.StringVar(value="")
# --- FIM ADIÇÃO ---

# Frame principal para a área de ações
act_area = tb.Frame(aba_regs); act_area.pack(fill="x", pady=(5, 10)) 

# Frame APENAS para os botões da ESQUERDA (Para ficarem juntos)
act_buttons_left = tb.Frame(act_area); act_buttons_left.pack(side="left", fill="x", expand=True)

# --- 1. CRIAÇÃO DOS BOTÕES DA ESQUERDA ---
btn_edit = tb.Button(act_buttons_left, text="Editar", image=ICONS.get("edit"), compound=LEFT, bootstyle=INFO)
btn_duplicar = tb.Button(act_buttons_left, text="Duplicar", image=ICONS.get("duplicate"), compound=LEFT) 
btn_del  = tb.Button(act_buttons_left, text="Excluir", image=ICONS.get("delete"), compound=LEFT, bootstyle=DANGER)
btn_cert = tb.Button(act_buttons_left, text="Certificado OK", image=ICONS.get("ok"), compound=LEFT,bootstyle=SUCCESS)
btn_nf = tb.Button(act_buttons_left, text="NF OK", image=ICONS.get("ok"), compound=LEFT, bootstyle="success-outline")
btn_exigencias = tb.Button(act_buttons_left, text="Edição em lote", image=ICONS.get("edit"), compound=LEFT, bootstyle="warning")

# --- 2. EMPACOTAMENTO DA ESQUERDA (NA ORDEM) ---
btn_edit.pack(side="left", padx=(0, 8)) 
btn_duplicar.pack(side="left", padx=8) 
btn_del.pack(side="left", padx=8)
btn_cert.pack(side="left", padx=8)
btn_nf.pack(side="left", padx=8)
btn_exigencias.pack(side="left", padx=8)

# --- 3. LABEL DE RESUMO (Ainda na esquerda, mas preenchendo o resto) ---
lbl_resumo_selecao = tb.Label(act_buttons_left, textvariable=resumo_selecao_var, bootstyle=SECONDARY, anchor="w")
lbl_resumo_selecao.pack(side="left", fill="x", expand=True, padx=10, pady=(5, 0)) 

# --- 4. BOTÕES DA DIREITA ---
btn_gerar_nf = tb.Button(act_area, text="Gerar Solicitação NF", bootstyle="outline-success") 
btn_gerar_nf.pack(side="right", anchor="se", padx=(10, 0), pady=(5,0))

# O NOVO BOTÃO DE EXPORTAÇÃO (Ligado diretamente à nossa função de Thread)
btn_exportar_regs = tb.Button(act_area, text="📊 Exportar Tabela (Excel)", bootstyle="success", command=lambda: exportar_para_excel())
btn_exportar_regs.pack(side="right", anchor="se", padx=(10, 0), pady=(5,0))

# =========================
# ABA 3 — Análises (COM BOTÕES RÁPIDOS)
# =========================
aba_ana = tb.Frame(relatorios_nb, padding=15) 
relatorios_nb.add(aba_ana, text="Análise")

# --- 1. FILTROS (Topo) ---
ana_filtros_frame = tb.Frame(aba_ana) 
ana_filtros_frame.pack(fill="x", pady=(0, 15))

# Seletores de Data
tb.Label(ana_filtros_frame, text="Período:", font=("Segoe UI", 10, "bold"), bootstyle="primary").pack(side="left", padx=(0, 10))

ana_data_inicio = CalendarioPremium(ana_filtros_frame, dateformat="%d/%m/%Y")
# Define o padrão para 01/01/2025 para mostrar o histórico completo
ana_data_inicio.set_date(date(2025, 1, 1)) 
ana_data_inicio.pack(side="left", padx=5)

tb.Label(ana_filtros_frame, text="até").pack(side="left", padx=5)

ana_data_fim = CalendarioPremium(ana_filtros_frame, dateformat="%d/%m/%Y")
ana_data_fim.set_date(DATA_HOJE_GLOBAL)
ana_data_fim.pack(side="left", padx=5)

# --- LÓGICA DOS BOTÕES RÁPIDOS ---
def aplicar_filtro_rapido_ana(periodo):
    """Define as datas e atualiza o dashboard automaticamente."""
    hoje = date.today()
    ini, fim = hoje, hoje
    
    if periodo == "mes":
        ini = hoje.replace(day=1)
        fim = hoje
    elif periodo == "mes_passado":
        # Pega o primeiro dia deste mês e subtrai 1 dia = Último dia do mês passado
        primeiro_deste_mes = hoje.replace(day=1)
        ultimo_dia_mes_passado = primeiro_deste_mes - timedelta(days=1)
        
        # Define o início e fim do mês passado
        ini = ultimo_dia_mes_passado.replace(day=1)
        fim = ultimo_dia_mes_passado
        
    elif periodo == "ano":
        ini = hoje.replace(day=1, month=1)
        fim = hoje
    elif periodo == "tudo":
        ini = date(2020, 1, 1)
        fim = hoje
        
    ana_data_inicio.set_date(ini)
    ana_data_fim.set_date(fim)
    atualizar_dashboard() # Já dispara a atualização

# Separador visual
tb.Label(ana_filtros_frame, text="|", bootstyle="secondary").pack(side="left", padx=10)

# Botões Rápidos
btn_mes_ana = tb.Button(ana_filtros_frame, text="Este Mês", bootstyle="outline-primary", width=9, command=lambda: aplicar_filtro_rapido_ana("mes"))
btn_mes_ana.pack(side="left", padx=2)

btn_mes_passado_ana = tb.Button(ana_filtros_frame, text="Mês Passado", bootstyle="outline-primary", width=12, command=lambda: aplicar_filtro_rapido_ana("mes_passado"))
btn_mes_passado_ana.pack(side="left", padx=2)

btn_ano_ana = tb.Button(ana_filtros_frame, text="Este Ano", bootstyle="outline-primary", width=9, command=lambda: aplicar_filtro_rapido_ana("ano"))
btn_ano_ana.pack(side="left", padx=2)

btn_tudo_ana = tb.Button(ana_filtros_frame, text="Tudo", bootstyle="outline-secondary", width=6, command=lambda: aplicar_filtro_rapido_ana("tudo"))
btn_tudo_ana.pack(side="left", padx=2)

# Botão Atualizar Manual (caso queira mudar data específica e clicar)
btn_atualizar_ana = tb.Button(ana_filtros_frame, text="Atualizar", bootstyle=SUCCESS, cursor="hand2")
btn_atualizar_ana.pack(side="right", padx=0) # Jogado para a direita

# --- 2. CARDS DE KPI (Mantém igual, apenas recriando para não quebrar o fluxo) ---
kpi_frame = tb.Frame(aba_ana)
kpi_frame.pack(fill="x", pady=(0, 15))
kpi_frame.columnconfigure((0,1,2,3), weight=1, uniform="kpi") 

def criar_card_kpi(parent, titulo, var_valor, cor_bootstyle, col_idx):
    card = tb.Frame(parent, bootstyle=f"{cor_bootstyle}", relief="raised", borderwidth=1)
    card.grid(row=0, column=col_idx, sticky="ew", padx=5 if col_idx > 0 else 0)
    lbl_titulo = tb.Label(card, text=titulo.upper(), font=("Segoe UI", 8), bootstyle=f"{cor_bootstyle}-inverse")
    lbl_titulo.pack(fill="x", pady=(5,0), padx=10)
    lbl_valor = tb.Label(card, textvariable=var_valor, font=("Segoe UI", 16, "bold"), bootstyle=f"{cor_bootstyle}-inverse")
    lbl_valor.pack(fill="x", pady=(0,10), padx=10)
    return card

kpi_vendas_var = tk.StringVar(value="R$ 0,00")
kpi_custos_var = tk.StringVar(value="R$ 0,00")
kpi_lucro_var = tk.StringVar(value="R$ 0,00")
kpi_peso_var = tk.StringVar(value="0 kg")

criar_card_kpi(kpi_frame, "Total Vendas", kpi_vendas_var, "success", 0)
criar_card_kpi(kpi_frame, "Total Custos", kpi_custos_var, "danger", 1)
criar_card_kpi(kpi_frame, "Lucro Líquido", kpi_lucro_var, "primary", 2)
criar_card_kpi(kpi_frame, "Peso Total", kpi_peso_var, "info", 3)

tot_txt = tk.Text(aba_ana, height=1)

# --- 3. ÁREA DE GRÁFICOS (Split View) ---
graficos_frame = tb.Frame(aba_ana)
graficos_frame.pack(fill="both", expand=True, pady=(0, 15))
graficos_frame.columnconfigure(0, weight=1, uniform="graf") # Esquerda
graficos_frame.columnconfigure(1, weight=1, uniform="graf") # Direita

# --- Gráfico Esquerdo (Barras) ---
frame_barras = tb.Frame(graficos_frame, relief="solid", borderwidth=1)
frame_barras.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

lbl_barras = tb.Label(frame_barras, text=" Comparativo Financeiro", font=("Segoe UI", 10, "bold"), bootstyle="secondary")
lbl_barras.pack(fill="x", pady=5, padx=5)

fig_bar, ax_bar = plt.subplots(figsize=(5, 3))
fig_bar.tight_layout(pad=2)
canvas_bar = FigureCanvasTkAgg(fig_bar, master=frame_barras)
canvas_bar.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

# --- Painel Direito (Notebook de Análises) ---
# Removemos a borda grossa do notebook para ficar mais clean
dash_notebook = tb.Notebook(graficos_frame, bootstyle="light") 
dash_notebook.grid(row=0, column=1, sticky="nsew")

# Aba 1: Custos (Pizza)
tab_pie_custo = tb.Frame(dash_notebook, padding=5)
dash_notebook.add(tab_pie_custo, text="Custos")
fig_pie_custo, ax_pie_custo = plt.subplots(figsize=(4, 3))
fig_pie_custo.tight_layout(pad=1)
canvas_pie_custo = FigureCanvasTkAgg(fig_pie_custo, master=tab_pie_custo)
canvas_pie_custo.get_tk_widget().pack(fill="both", expand=True)

# Aba 2: Volumes (Pizza)
tab_pie_peso = tb.Frame(dash_notebook, padding=5)
dash_notebook.add(tab_pie_peso, text="Volumes")
fig_pie_peso, ax_pie_peso = plt.subplots(figsize=(4, 3))
fig_pie_peso.tight_layout(pad=1)
canvas_pie_peso = FigureCanvasTkAgg(fig_pie_peso, master=tab_pie_peso)
canvas_pie_peso.get_tk_widget().pack(fill="both", expand=True)

# Aba 3: Lucro (Barras Horizontais)
tab_lucro_res = tb.Frame(dash_notebook, padding=5)
dash_notebook.add(tab_lucro_res, text="Lucro/Resíduo")
fig_lucro_res, ax_lucro_res = plt.subplots(figsize=(4, 3))
fig_lucro_res.tight_layout(pad=1)
canvas_lucro_res = FigureCanvasTkAgg(fig_lucro_res, master=tab_lucro_res)
canvas_lucro_res.get_tk_widget().pack(fill="both", expand=True)

# Aba 4: Evolução (Linha)
tab_evol = tb.Frame(dash_notebook, padding=5)
dash_notebook.add(tab_evol, text="Evolução (13 Meses)")
fig_evol, ax_evol = plt.subplots(figsize=(4, 3))
fig_evol.tight_layout(pad=1)
canvas_evol = FigureCanvasTkAgg(fig_evol, master=tab_evol)
canvas_evol.get_tk_widget().pack(fill="both", expand=True)

# ABA 5: Financeiro por Estado (Sólido vs Líquido)
tab_estado_fin = tb.Frame(dash_notebook, padding=5)
dash_notebook.add(tab_estado_fin, text="Financeiro por categoria")
fig_estado_fin, ax_estado_fin = plt.subplots(figsize=(4, 3))
fig_estado_fin.tight_layout(pad=1)
canvas_estado_fin = FigureCanvasTkAgg(fig_estado_fin, master=tab_estado_fin)
canvas_estado_fin.get_tk_widget().pack(fill="both", expand=True)

# --- 4. TABELA DE RESUMO (Rodapé) ---
# Frame container da tabela
table_container = tb.Frame(aba_ana)
table_container.pack(fill="both", expand=True)

# Cabeçalho da Tabela com Botão Exportar
header_tbl = tb.Frame(table_container)
header_tbl.pack(fill="x", pady=(0, 5))
tb.Label(header_tbl, text="Detalhamento Mensal", font=("Segoe UI", 10, "bold"), bootstyle="secondary").pack(side="left")
btn_export = tb.Button(header_tbl, text="Exportar Excel", bootstyle="success-outline", cursor="hand2")
btn_export.pack(side="right")

btn_pdf = tb.Button(header_tbl, text="Relatório PDF", bootstyle="danger-outline", cursor="hand2")
btn_pdf.pack(side="right", padx=0)
btn_sinir = tb.Button(header_tbl, text="DMR / SINIR", bootstyle="info", cursor="hand2")
btn_sinir.pack(side="right", padx=(0, 10))

# Tabela
resumo_cols = ("Mês","Estado","Destinacao","Peso","Vendas","Custos","Transporte","Lucro")
resumo = ttk.Treeview(table_container, columns=resumo_cols, show="headings", height=5) # Altura menor para priorizar gráficos

# Configuração Colunas (mesma de antes)
resumo_larg = {"Mês": 80, "Estado": 80, "Destinacao": 150, "Peso": 100, "Vendas": 100, "Custos": 100, "Transporte": 100, "Lucro": 100}
for col in resumo_cols:
    header_text = "Destinação" if col == "Destinacao" else col
    resumo.heading(col, text=header_text)
    resumo.column(col, width=resumo_larg.get(col, 100), anchor='center')

resumo.pack(side="left", fill="both", expand=True)

# Scrollbar da tabela
r_sy = ttk.Scrollbar(table_container, orient="vertical", command=resumo.yview)
resumo.configure(yscroll=r_sy.set)
r_sy.pack(side="right", fill="y")

# =========================
# ABA PENDÊNCIAS (UI Formatada)
# =========================
# (Código UI da Aba Pendências formatado)
##aba_pend = tb.Frame(nb, padding=12);
#nb.add(aba_pend, text="Pendências");
pend_card = tb.Labelframe(aba_pend, text="Certificados Pendentes (mais de 30 dias)", padding=6, bootstyle=WARNING);
pend_card.pack(fill="both", expand=True, pady=(0,0)); pend_card.rowconfigure(0, weight=1);
pend_card.columnconfigure(0, weight=1);
pend_cols = ("Data", "Parceiro", "Resíduo");
pend_tbl = ttk.Treeview(pend_card, columns=pend_cols, show="headings", selectmode="browse");
pend_tbl.grid(row=0, column=0, sticky="nsew");
pend_sy = ttk.Scrollbar(pend_card, orient="vertical", command=pend_tbl.yview);
pend_tbl.configure(yscroll=pend_sy.set); pend_sy.grid(row=0, column=1, sticky="ns");
# Configuração das colunas da tabela de pendências
pend_larg = {"Data": 110, "Parceiro": 250, "Resíduo": 250}
for c in pend_cols:
    pend_tbl.heading(c, text=c, anchor="center")
    pend_tbl.column(c, width=pend_larg.get(c, 120), anchor="center", stretch=True)
        
# =========================
# ABA 4 — Resíduos (UI Corrigida)
# =========================
aba_banco = tb.Frame(config_nb, padding=12); config_nb.add(aba_banco, text="Resíduos")
bn_actions = tb.Frame(aba_banco); bn_actions.pack(fill="x")
tb.Label(bn_actions, text="Cadastro de resíduos e valores padrão").pack(side="left")
btn_bn_add=tb.Button(bn_actions, text="Adicionar", image=ICONS.get("add"), compound=LEFT, bootstyle=SUCCESS)
btn_bn_edit=tb.Button(bn_actions, text="Editar", image=ICONS.get("edit"), compound=LEFT, bootstyle=INFO)
btn_bn_del=tb.Button(bn_actions, text="Excluir", image=ICONS.get("delete"), compound=LEFT, bootstyle=DANGER)
btn_bn_reclass = tb.Button(bn_actions, text="Reclassificar Nome", bootstyle="warning")

# --- NOVO BOTÃO ---
btn_bn_lote=tb.Button(bn_actions, text="Agrupar", image=ICONS.get("edit"), compound=LEFT, bootstyle="warning") 

btn_bn_del.pack(side="left", padx=6)
btn_bn_reclass.pack(side="left", padx=6)
btn_bn_lote.pack(side="left", padx=6) # Adiciona na tela
btn_bn_edit.pack(side="left", padx=6)
btn_bn_add.pack(side="left", padx=0)

# --- Busca por nome do resíduo ---
bn_busca = tk.StringVar()
bn_so_sem_ibama = tk.BooleanVar(value=False)
tb.Checkbutton(bn_actions, text="Só sem código IBAMA", variable=bn_so_sem_ibama, bootstyle="round-toggle",
               command=lambda: preencher_banco_tabela()).pack(side="right", padx=(10, 0))
tb.Entry(bn_actions, textvariable=bn_busca, width=30).pack(side="right", padx=(0, 6))
tb.Label(bn_actions, text="Buscar resíduo:").pack(side="right", padx=(0, 6))
bn_busca.trace_add("write", lambda *_: preencher_banco_tabela())

bn_card = tb.Labelframe(aba_banco, text="Resíduos cadastrados", padding=6, bootstyle=INFO)
bn_card.pack(fill="both", expand=True, pady=(10,0)); bn_card.rowconfigure(0, weight=1); bn_card.columnconfigure(0, weight=1)

bn_cols = ("Resíduo", "Código IBAMA", "Nome item (NF)", "Código item", "Destinação padrão", "Valor padrão")

# --- MUDOU PARA EXTENDED ---
bn_tbl = ttk.Treeview(bn_card, columns=bn_cols, show="headings", selectmode="extended")

bn_tbl.grid(row=0, column=0, sticky="nsew")
bn_sy = ttk.Scrollbar(bn_card, orient="vertical", command=bn_tbl.yview); bn_tbl.configure(yscroll=bn_sy.set); bn_sy.grid(row=0, column=1, sticky="ns")

# --- Configuração das Novas Colunas (Centralizadas) ---
for c, w, a, estica in (("Resíduo", 220, "w", True), ("Código IBAMA", 135, "center", False),
                        ("Nome item (NF)", 260, "w", True), ("Código item", 115, "center", False),
                        ("Destinação padrão", 170, "center", False), ("Valor padrão", 190, "e", False)):
    bn_tbl.heading(c, text=c); bn_tbl.column(c, width=w, anchor=a, stretch=estica)
bn_tbl.tag_configure("sem_ibama", foreground="#cc0000")
bn_tbl.bind("<Double-1>", lambda e: banco_edit_wrapper())  # Dois cliques abrem a edição

# =========================
# ABA  5 - Dados (UI Formatada)
# =========================
aba_parc = tb.Frame(config_nb, padding=12)
config_nb.add(aba_parc, text="Parceiros")
pc_actions = tb.Frame(aba_parc); pc_actions.pack(fill="x")
tb.Label(pc_actions, text="Cadastro de parceiros").pack(side="left")
btn_pc_add=tb.Button(pc_actions, text="Adicionar", image=ICONS.get("add"), compound=LEFT,bootstyle=SUCCESS)
btn_pc_edit=tb.Button(pc_actions, text="Editar", image=ICONS.get("edit"), compound=LEFT, bootstyle=INFO)
btn_pc_del=tb.Button(pc_actions, text="Excluir", image=ICONS.get("delete"), compound=LEFT, bootstyle=DANGER); btn_pc_del.pack(side="left", padx=6)
btn_pc_edit.pack(side="left", padx=6)
btn_pc_add.pack(side="left", padx=0)
pc_card = tb.Labelframe(aba_parc, text="Parceiros cadastrados", padding=6, bootstyle=INFO)
pc_card.pack(fill="both", expand=True, pady=(10,0))
pc_card.rowconfigure(0, weight=1)
pc_card.columnconfigure(0, weight=1)
pc_cols = ("Parceiro", "Tipo"); pc_tbl = ttk.Treeview(pc_card, columns=pc_cols, show="headings", selectmode="browse"); pc_tbl.grid(row=0, column=0, sticky="nsew"); pc_sy = ttk.Scrollbar(pc_card, orient="vertical", command=pc_tbl.yview); pc_tbl.configure(yscroll=pc_sy.set); pc_sy.grid(row=0, column=1, sticky="ns");
pc_tbl.heading("Parceiro", text="Nome do Parceiro"); pc_tbl.column("Parceiro", width=100, anchor="center", stretch=True)
pc_tbl.heading("Tipo", text="Tipo"); pc_tbl.column("Tipo", width=100, anchor="center", stretch=True)

# =========================
# ABA 6 — Banco de Análises (UI Corrigida)
# =========================
aba_ana_banco = tb.Frame(config_nb, padding=12)
config_nb.add(aba_ana_banco, text="Análises")

bana_actions = tb.Frame(aba_ana_banco)
bana_actions.pack(fill="x")
tb.Label(bana_actions, text="Cadastro de nomes e valores padrão de análises").pack(side="left")

# Botões (serão ligados no final)
btn_bana_add = tb.Button(bana_actions, text="Adicionar", image=ICONS.get("add"), compound=LEFT,bootstyle=SUCCESS)
btn_bana_edit = tb.Button(bana_actions, text="Editar", image=ICONS.get("edit"), compound=LEFT,bootstyle=INFO)
btn_bana_del = tb.Button(bana_actions, text="Excluir", image=ICONS.get("delete"), compound=LEFT,bootstyle=DANGER)
btn_bana_del.pack(side="left", padx=6)
btn_bana_edit.pack(side="left", padx=6)
btn_bana_add.pack(side="left", padx=0)

# Card da Tabela
bana_card = tb.Labelframe(aba_ana_banco, text="Análises cadastradas", padding=6, bootstyle=INFO)
bana_card.pack(fill="both", expand=True, pady=(10,0))
bana_card.rowconfigure(0, weight=1); bana_card.columnconfigure(0, weight=1)

# Define as DUAS colunas
bana_cols = ("Nome da análise", "Valor (R$)")
bana_tbl = ttk.Treeview(bana_card, columns=bana_cols, show="headings", selectmode="browse")

bana_tbl.grid(row=0, column=0, sticky="nsew")
bana_sy = ttk.Scrollbar(bana_card, orient="vertical", command=bana_tbl.yview)
bana_tbl.configure(yscroll=bana_sy.set)
bana_sy.grid(row=0, column=1, sticky="ns")

# Configura AMBAS as colunas (Centralizadas)
bana_tbl.heading("Nome da análise", text="Nome da análise", anchor="center") # Centraliza cabeçalho
bana_tbl.column("Nome da análise", width=300, anchor="center", stretch=True) # Centraliza conteúdo
bana_tbl.heading("Valor (R$)", text="Valor (R$)", anchor="center") # Centraliza cabeçalho
bana_tbl.column("Valor (R$)", width=200, anchor="center", stretch=True) # Centraliza conteúdo

# =========================
# ABA 8 — Indicadores ESG
# =========================
aba_esg = tb.Frame(relatorios_nb, padding=12)
relatorios_nb.add(aba_esg, text="Indicadores ESG")

# --- Filtros ESG ---
esg_filtros_frame = tb.Labelframe(aba_esg, text="Filtros ESG", padding=10, bootstyle=INFO)
esg_filtros_frame.pack(fill="x", pady=(0, 10))
esg_filtros_frame.columnconfigure((0, 1, 2, 3), weight=1)

tb.Label(esg_filtros_frame, text="Data Início:").grid(row=0, column=0, sticky="e", padx=(0,5))
esg_data_inicio = CalendarioPremium(esg_filtros_frame, dateformat="%d/%m/%Y")
esg_data_inicio.set_date(date(2025, 1, 1))
esg_data_inicio.grid(row=0, column=1, sticky="ew", padx=(0,5))

tb.Label(esg_filtros_frame, text="Data Fim:").grid(row=0, column=2, sticky="e", padx=(0,5))
esg_data_fim = CalendarioPremium(esg_filtros_frame, dateformat="%d/%m/%Y")
esg_data_fim.set_date(DATA_HOJE_GLOBAL)
esg_data_fim.grid(row=0, column=3, sticky="ew", padx=(0,10))

btn_gerar_esg = tb.Button(esg_filtros_frame, text="Gerar Relatório ESG", bootstyle=SUCCESS)
btn_gerar_esg.grid(row=1, column=0, columnspan=4, sticky="w", pady=(10,0))

esg_metragem_var = tk.StringVar(value="0") # Variável de segurança

# ==============================================================
# NOVO VISUAL ESG: CARDS E GRÁFICO DE ROSCA
# ==============================================================
esg_cards_frame = tb.Frame(aba_esg) 
esg_cards_frame.pack(fill="x", pady=(15, 10), padx=10)

card_esg_geracao = tb.Labelframe(esg_cards_frame, text=" Geração Total no Período (kg) ", bootstyle="info", padding=15)
card_esg_geracao.pack(side="left", fill="x", expand=True, padx=(0, 5))
lbl_esg_geracao = tb.Label(card_esg_geracao, text="0,00 kg", font=("Segoe UI", 24, "bold"), bootstyle="info")
lbl_esg_geracao.pack()

card_esg_taxa = tb.Labelframe(esg_cards_frame, text=" Taxa de Circularidade (%) ", bootstyle="success", padding=15)
card_esg_taxa.pack(side="left", fill="x", expand=True, padx=(5, 0))
lbl_esg_taxa = tb.Label(card_esg_taxa, text="0,0%", font=("Segoe UI", 24, "bold"), bootstyle="success")
lbl_esg_taxa.pack()

esg_graf_frame = tb.Labelframe(aba_esg, text=" Distribuição por Destinação Final ", bootstyle="warning", padding=10)
esg_graf_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

fig_esg_rosca, ax_esg_rosca = plt.subplots(figsize=(6, 4))
fig_esg_rosca.tight_layout(pad=2.0)
canvas_esg_rosca = FigureCanvasTkAgg(fig_esg_rosca, master=esg_graf_frame)
canvas_esg_rosca.get_tk_widget().pack(fill="both", expand=True)

# ==========================================
# ABA 9 — Balança Comercial (Financeiro)
# ==========================================
aba_fin = tb.Frame(relatorios_nb, padding=12)
relatorios_nb.add(aba_fin, text="Balança Comercial (R$)")

fin_filtros_frame = tb.Labelframe(aba_fin, text="Parâmetros Financeiros", padding=10, bootstyle=INFO)
fin_filtros_frame.pack(fill="x", pady=(0, 10))

tb.Label(fin_filtros_frame, text="Data Início:").grid(row=0, column=0, sticky="e", padx=(0,5))
fin_data_inicio = CalendarioPremium(fin_filtros_frame, dateformat="%d/%m/%Y")
fin_data_inicio.set_date(date(2025, 1, 1))
fin_data_inicio.grid(row=0, column=1, sticky="ew", padx=(0,15))

tb.Label(fin_filtros_frame, text="Data Fim:").grid(row=0, column=2, sticky="e", padx=(0,5))
fin_data_fim = CalendarioPremium(fin_filtros_frame, dateformat="%d/%m/%Y")
fin_data_fim.set_date(DATA_HOJE_GLOBAL)
fin_data_fim.grid(row=0, column=3, sticky="ew", padx=(0,15))

# Removemos o campo manual de Produção, pois agora o sistema puxa do Banco!
btn_gerar_fin = tb.Button(fin_filtros_frame, text="Gerar Balanço", bootstyle=SUCCESS)
btn_gerar_fin.grid(row=0, column=4, sticky="w", padx=(10,0))

# --- Cards Executivos (Totais do Período) ---
fin_cards_frame = tb.Frame(aba_fin)
fin_cards_frame.pack(fill="x", pady=(5, 10))

card_fin_receita = tb.Labelframe(fin_cards_frame, text=" Receita Total (R$) ", bootstyle="success", padding=15)
card_fin_receita.pack(side="left", fill="x", expand=True, padx=(0, 5))
lbl_fin_receita = tb.Label(card_fin_receita, text="R$ 0,00", font=("Segoe UI", 20, "bold"), bootstyle="success")
lbl_fin_receita.pack()

card_fin_custo = tb.Labelframe(fin_cards_frame, text=" Custos Totais (R$) ", bootstyle="danger", padding=15)
card_fin_custo.pack(side="left", fill="x", expand=True, padx=(5, 5))
lbl_fin_custo = tb.Label(card_fin_custo, text="R$ 0,00", font=("Segoe UI", 20, "bold"), bootstyle="danger")
lbl_fin_custo.pack()

card_fin_kpi = tb.Labelframe(fin_cards_frame, text=" Indicador Geral (R$/m²) ", bootstyle="primary", padding=15)
card_fin_kpi.pack(side="left", fill="x", expand=True, padx=(5, 0))
lbl_fin_kpi = tb.Label(card_fin_kpi, text="R$ 0,00 / m²", font=("Segoe UI", 20, "bold"), bootstyle="primary")
lbl_fin_kpi.pack()

# --- Área de Conteúdo (Tabela e Gráfico Lado a Lado) ---
fin_content_frame = tb.Frame(aba_fin)
fin_content_frame.pack(fill="both", expand=True)
fin_content_frame.columnconfigure(0, weight=1)
fin_content_frame.columnconfigure(1, weight=1)

# 1. Tabela (Lado Esquerdo)
fin_card_tabela = tb.Labelframe(fin_content_frame, text="Detalhamento Mensal", padding=10, bootstyle=INFO)
fin_card_tabela.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

fin_cols = ("Mês", "Receita (R$)", "Custos (R$)", "Custo Real (R$)", "Produção (m²)", "Indicador (R$/m²)")
fin_tbl = ttk.Treeview(fin_card_tabela, columns=fin_cols, show="headings")
fin_tbl.pack(side="left", fill="both", expand=True)

for c in fin_cols:
    fin_tbl.heading(c, text=c)
    fin_tbl.column(c, anchor="center", width=85) # Ajusta largura das colunas

fin_scroll = ttk.Scrollbar(fin_card_tabela, orient="vertical", command=fin_tbl.yview)
fin_tbl.configure(yscrollcommand=fin_scroll.set)
fin_scroll.pack(side="right", fill="y")

# 2. Gráfico (Lado Direito)
fin_graf_frame = tb.Labelframe(fin_content_frame, text=" Evolução: Custos vs Receitas ", bootstyle="dark", padding=10)
fin_graf_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

fig_fin, ax_fin = plt.subplots(figsize=(5,3))
fig_fin.tight_layout(pad=1.5)
canvas_fin = FigureCanvasTkAgg(fig_fin, master=fin_graf_frame)
canvas_fin.get_tk_widget().pack(fill="both", expand=True)

# --- Lógica da Aba ---
def calcular_balanca_comercial():
    """Calcula receitas e custos mês a mês, cruzando com a metragem do banco de dados."""
    try:
        dt_inicio = obter_data_segura(fin_data_inicio)
        dt_fim = obter_data_segura(fin_data_fim)
    except:
        ModernMessageBox.showwarning("Aviso", "Verifique as datas inseridas.")
        return

    ax_fin.clear()
    canvas_fin.draw()
    for r in fin_tbl.get_children(): fin_tbl.delete(r)
    btn_gerar_fin.config(state="disabled")

    def thread_fin():
        try:
            df = df_registros_global.copy()
            df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
            df = df[(df['Data'].dt.date >= dt_inicio) & (df['Data'].dt.date <= dt_fim)]

            if df.empty or 'ValorTotal' not in df.columns:
                app.after(0, lambda: btn_gerar_fin.config(state="normal"))
                return

            # =========================================================
            # REGRA DE SEPARAÇÃO BLINDADA (Textos em vez de True/False)
            # =========================================================
            palavras_receita = ['venda', 'sucata', 'venda de recicláveis', 'receita']
            def classificar_financeiro(dest):
                d = str(dest).lower()
                return 'Receita' if any(pr in d for pr in palavras_receita) else 'Custo'

            df['Is_Receita'] = df['Destinacao'].apply(classificar_financeiro)
            
            # Agrupa os valores por Mês e Ano
            df['Mes_Ano'] = df['Data'].dt.to_period('M')
            df_grafico = df.groupby(['Mes_Ano', 'Is_Receita'])['ValorTotal'].sum().unstack(fill_value=0).reset_index()

            # Garante que as colunas existam para não dar KeyError
            if 'Receita' not in df_grafico.columns: df_grafico['Receita'] = 0.0
            if 'Custo' not in df_grafico.columns: df_grafico['Custo'] = 0.0

            df_grafico = df_grafico.sort_values('Mes_Ano')

            # PUXA TODAS AS METRAGENS DO BANCO DE DADOS
            dados_metragem = db.get_all_metragens() 
            dict_metragem = {item[0]: item[1] for item in dados_metragem}

            linhas_tabela = []
            x_labels, val_receitas, val_custos = [], [], []
            
            total_receita_periodo = 0.0
            total_custo_periodo = 0.0
            total_metragem_periodo = 0.0

            # Prepara os cálculos linha a linha (Mês a Mês)
            for _, row in df_grafico.iterrows():
                mes_period = row['Mes_Ano']
                chave_db = f"{mes_period.year}-{mes_period.month:02d}"
                met_produzida = dict_metragem.get(chave_db, 0.0)

                # Agora busca com segurança pelo texto
                receita_mes = float(row['Receita'])
                custo_mes = float(row['Custo'])
                
                custo_real_mes = custo_mes - receita_mes
                indicador_mes = (custo_real_mes / met_produzida) if met_produzida > 0 else 0.0

                mes_str = f"{PT_ABREV_LIST[mes_period.month-1].capitalize()}/{mes_period.year%100:02d}"
                
                linhas_tabela.append((mes_str, receita_mes, custo_mes, custo_real_mes, met_produzida, indicador_mes))
                total_receita_periodo += receita_mes
                total_custo_periodo += custo_mes
                total_metragem_periodo += met_produzida

                x_labels.append(mes_str)
                val_receitas.append(receita_mes)
                val_custos.append(custo_mes)

            # Cálculo dos KPIs Globais
            saldo_custo_real_total = total_custo_periodo - total_receita_periodo
            kpi_total_periodo = saldo_custo_real_total / total_metragem_periodo if total_metragem_periodo > 0 else 0.0

            app.after(0, lambda: atualizar_ui_fin(
                linhas_tabela, total_receita_periodo, total_custo_periodo, kpi_total_periodo,
                x_labels, val_custos, val_receitas
            ))

        except Exception as e:
            print(f"Erro Financeiro: {e}")
            # Agora exibe o erro na tela caso algo ainda falhe!
            app.after(0, lambda: ModernMessageBox.showerror("Erro no Balanço", f"Falha ao gerar os dados:\n{e}"))
            app.after(0, lambda: btn_gerar_fin.config(state="normal"))

    import threading
    threading.Thread(target=thread_fin, daemon=True).start()

def atualizar_ui_fin(linhas, rec_tot, cus_tot, kpi_tot, x_labels, val_custos, val_receitas):
    """Insere os dados calculados nos elementos visuais da tela."""
    # Atualiza Cards Superiores
    lbl_fin_receita.config(text=fmt_moeda(rec_tot))
    lbl_fin_custo.config(text=fmt_moeda(cus_tot))
    lbl_fin_kpi.config(text=f"R$ {kpi_tot:,.2f} / m²".replace(",", "X").replace(".", ",").replace("X", "."))

    # Atualiza Tabela
    for r in fin_tbl.get_children(): fin_tbl.delete(r)
    for i, (mes, rec, cus, creal, met, ind) in enumerate(linhas):
        tag = "evenrow" if i % 2 == 0 else "oddrow"
        fin_tbl.insert("", "end", values=(
            mes,
            fmt_moeda(rec),
            fmt_moeda(cus),
            fmt_moeda(creal),
            f"{met:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            f"{ind:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        ), tags=(tag,))

    # Atualiza Gráfico
    desenhar_grafico_financeiro(x_labels, val_custos, val_receitas)

def desenhar_grafico_financeiro(x_labels, custos, receitas):
    """Desenha as barras de custos e receitas lado a lado no gráfico."""
    ax_fin.clear()
    bg_color, fg_color = style.colors.bg, style.colors.fg
    ax_fin.set_facecolor(bg_color)
    fig_fin.set_facecolor(bg_color)

    x = np.arange(len(x_labels))
    width = 0.35

    ax_fin.bar(x - width/2, custos, width, label='Custos', color='#e74c3c')
    ax_fin.bar(x + width/2, receitas, width, label='Receitas', color='#2ecc71')

    ax_fin.set_title("Balança Comercial Mensal (R$)", color=fg_color, weight='bold', fontsize=10)
    ax_fin.set_xticks(x)
    ax_fin.set_xticklabels(x_labels, rotation=30, ha='right', color=fg_color, fontsize=8)
    ax_fin.tick_params(axis='y', colors=fg_color, labelsize=8)

    ax_fin.yaxis.grid(True, linestyle=':', color=style.colors.secondary, alpha=0.4)
    for spine in ['top', 'right']: ax_fin.spines[spine].set_visible(False)
    for spine in ['left', 'bottom']: ax_fin.spines[spine].set_color(style.colors.secondary)

    ax_fin.legend(loc='upper left', frameon=False, labelcolor=fg_color, fontsize=8)
    fig_fin.subplots_adjust(bottom=0.2)

    canvas_fin.draw()
    btn_gerar_fin.config(state="normal")

### =========================
### ABA 9 — CEP (Peso Bruto)
### =========================
##aba_cep_peso = tb.Frame(nb, padding=12)
##nb.add(aba_cep_peso, text="CEP (Peso)")
##
### --- Filtros (Cópia da Aba ESG, com adição do Resíduo) ---
##cep_filtros_frame = tb.Labelframe(aba_cep_peso, text="Filtro de Processo", padding=10, bootstyle=INFO)
##cep_filtros_frame.pack(fill="x", pady=(0, 10))
##cep_filtros_frame.columnconfigure((0, 1, 2, 3, 4, 5), weight=1) # Adiciona coluna 5
##
### Coluna 0, 1: Data Início
##tb.Label(cep_filtros_frame, text="Data Início:").grid(row=0, column=0, sticky="e", padx=(0,5))
##cep_data_inicio = DateEntry(cep_filtros_frame, dateformat="%d/%m/%Y", firstweekday=6, bootstyle=PRIMARY)
##cep_data_inicio.set_date(DATA_INICIO_MES_GLOBAL)
##cep_data_inicio.grid(row=0, column=1, sticky="ew", padx=(0,5))
##
### Coluna 2, 3: Data Fim
##tb.Label(cep_filtros_frame, text="Data Fim:").grid(row=0, column=2, sticky="e", padx=(0,5))
##cep_data_fim = DateEntry(cep_filtros_frame, dateformat="%d/%m/%Y", firstweekday=6, bootstyle=PRIMARY)
##cep_data_fim.set_date(DATA_HOJE_GLOBAL)
##cep_data_fim.grid(row=0, column=3, sticky="ew", padx=(0,10))
##
### Coluna 4: Seleção de Resíduo
##tb.Label(cep_filtros_frame, text="Resíduo:").grid(row=0, column=4, sticky="e", padx=(0,5))
##cep_res_var = tk.StringVar(value="")
##cep_res_cb = tb.Combobox(cep_filtros_frame, textvariable=cep_res_var, values=banco_residuos, state="readonly")
##cep_res_cb.grid(row=0, column=5, sticky="ew")
##
### Botão na linha 1
##btn_gerar_cep = tb.Button(cep_filtros_frame, text="Gerar Gráfico de Controle", bootstyle=SUCCESS)
##btn_gerar_cep.grid(row=1, column=0, columnspan=6, sticky="w", pady=(10,0)) # Span 6
##
### --- Card do Gráfico ---
##cep_graf_card = tb.Labelframe(aba_cep_peso, text="Gráfico de Controle Individual (Peso KG)", padding=10, bootstyle=INFO)
##cep_graf_card.pack(fill="both", expand=True, pady=(10,0))
##fig_cep, ax_cep = plt.subplots(figsize=(8,4)) # Nova Figura/Eixo
##fig_cep.tight_layout(pad=0.5)
##canvas_cep = FigureCanvasTkAgg(fig_cep, master=cep_graf_card) # Novo Canvas
##canvas_cep.get_tk_widget().pack(fill="both", expand=True)

# =========================
# ABA 9.1 — Geração (Rateio)
# =========================
global ger_data_inicio, ger_data_fim

aba_geracao = tb.Frame(relatorios_nb, padding=12)
relatorios_nb.add(aba_geracao, text="Geração (Rateio)")

# --- Filtros ---
ger_filtros_frame = tb.Labelframe(aba_geracao, text="Filtro de Geração", padding=10, bootstyle=INFO)
ger_filtros_frame.pack(fill="x", pady=(0, 10))
ger_filtros_frame.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

# Coluna 0, 1: Data Início
tb.Label(ger_filtros_frame, text="Mês Início:").grid(row=0, column=0, sticky="e", padx=(0,5))
ger_data_inicio = CalendarioPremium(ger_filtros_frame, dateformat="%d/%m/%Y")
ger_data_inicio.set_date(date(2025, 1, 1))
ger_data_inicio.grid(row=0, column=1, sticky="ew", padx=(0,5))

# Coluna 2, 3: Data Fim
tb.Label(ger_filtros_frame, text="Mês Fim:").grid(row=0, column=2, sticky="e", padx=(0,5))
ger_data_fim = CalendarioPremium(ger_filtros_frame, dateformat="%d/%m/%Y")
ger_data_fim.set_date(DATA_HOJE_GLOBAL) 
ger_data_fim.grid(row=0, column=3, sticky="ew", padx=(0,10))

# Coluna 4: Seleção de Resíduo
tb.Label(ger_filtros_frame, text="Resíduo/Grupo:").grid(row=0, column=4, sticky="e", padx=(0,5))
ger_res_var = tk.StringVar(value="")
ger_res_cb = tb.Combobox(ger_filtros_frame, textvariable=ger_res_var, values=banco_residuos, state="readonly")
ger_res_cb.grid(row=0, column=5, sticky="ew")

# Botão
btn_gerar_geracao = tb.Button(ger_filtros_frame, text="Calcular Geração Rateada", bootstyle=SUCCESS)
btn_gerar_geracao.grid(row=1, column=0, columnspan=6, sticky="w", pady=(10,0))

# --- NOVO: Cards de Resumo (Topo) ---
ger_resumo_frame = tb.Frame(aba_geracao)
ger_resumo_frame.pack(fill="x", pady=(0, 10))
ger_resumo_frame.columnconfigure((0, 1), weight=1, uniform="ger_kpi")

ger_kpi_total_var = tk.StringVar(value="0 kg")
ger_kpi_media_var = tk.StringVar(value="0,00 kg/dia")

card_total = tb.Frame(ger_resumo_frame, bootstyle="success", relief="raised", borderwidth=1)
card_total.grid(row=0, column=0, sticky="ew", padx=(0, 5))
tb.Label(card_total, text="GERAÇÃO TOTAL (PERÍODO)", font=("Segoe UI", 8), bootstyle="success-inverse").pack(fill="x", pady=(5,0), padx=10)
tb.Label(card_total, textvariable=ger_kpi_total_var, font=("Segoe UI", 16, "bold"), bootstyle="success-inverse").pack(fill="x", pady=(0,10), padx=10)

card_media = tb.Frame(ger_resumo_frame, bootstyle="info", relief="raised", borderwidth=1)
card_media.grid(row=0, column=1, sticky="ew", padx=(5, 0))
tb.Label(card_media, text="MÉDIA DIÁRIA (ÚLTIMO CICLO)", font=("Segoe UI", 8), bootstyle="info-inverse").pack(fill="x", pady=(5,0), padx=10)
tb.Label(card_media, textvariable=ger_kpi_media_var, font=("Segoe UI", 16, "bold"), bootstyle="info-inverse").pack(fill="x", pady=(0,10), padx=10)

# --- NOVO: Tabela de Geração Mensal ---
ger_card = tb.Labelframe(aba_geracao, text="Detalhamento Mensal", padding=10, bootstyle=INFO)
ger_card.pack(fill="both", expand=True)

ger_cols = ("Mês", "Coletado (kg)", "Previsão (kg)", "Total (kg)")
ger_tbl = ttk.Treeview(ger_card, columns=ger_cols, show="headings", height=8)
ger_tbl.pack(side="left", fill="both", expand=True)

ger_tbl.heading("Mês", text="Mês/Ano")
ger_tbl.heading("Coletado (kg)", text="Resíduo coletado")
ger_tbl.heading("Previsão (kg)", text="Projeção Contínua (Previsão)")
ger_tbl.heading("Total (kg)", text="Total do Mês (kg)")

ger_tbl.column("Mês", anchor="center", width=120)
ger_tbl.column("Coletado (kg)", anchor="center", width=160)
ger_tbl.column("Previsão (kg)", anchor="center", width=160)
ger_tbl.column("Total (kg)", anchor="center", width=150)

ger_scroll = ttk.Scrollbar(ger_card, orient="vertical", command=ger_tbl.yview)
ger_tbl.configure(yscrollcommand=ger_scroll.set)
ger_scroll.pack(side="right", fill="y")

memoria_card = tb.Labelframe(aba_geracao, text="Memória de Cálculo (Log de Rateio)", padding=10, bootstyle=WARNING)
# expand=False e height menor para não esmagar a tabela principal
memoria_card.pack(fill="x", pady=(10, 0)) 

txt_memoria_geracao = tk.Text(memoria_card, height=6, wrap="word", font=("Consolas", 9))
txt_memoria_geracao.pack(side="left", fill="both", expand=True)

memoria_scroll = ttk.Scrollbar(memoria_card, orient="vertical", command=txt_memoria_geracao.yview)
txt_memoria_geracao.configure(yscrollcommand=memoria_scroll.set)
memoria_scroll.pack(side="right", fill="y")

# =========================
# ABA 9.2 — Ecoeficiência (kg/m²)
# =========================
aba_eco = tb.Frame(relatorios_nb, padding=12)
relatorios_nb.add(aba_eco, text="Ecoeficiência (kg/m²)")

# --- Filtros ---
eco_filtros_frame = tb.Labelframe(aba_eco, text="Filtros de Ecoeficiência", padding=10, bootstyle=INFO)
eco_filtros_frame.pack(fill="x", pady=(0, 10))
eco_filtros_frame.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

tb.Label(eco_filtros_frame, text="Mês Início:").grid(row=0, column=0, sticky="e", padx=(0,5))
eco_data_inicio = CalendarioPremium(eco_filtros_frame, dateformat="%d/%m/%Y")
eco_data_inicio.set_date(date(2025, 1, 1))
eco_data_inicio.grid(row=0, column=1, sticky="ew", padx=(0,5))

tb.Label(eco_filtros_frame, text="Mês Fim:").grid(row=0, column=2, sticky="e", padx=(0,5))
eco_data_fim = CalendarioPremium(eco_filtros_frame, dateformat="%d/%m/%Y")
eco_data_fim.set_date(DATA_HOJE_GLOBAL)
eco_data_fim.grid(row=0, column=3, sticky="ew", padx=(0,10))

tb.Label(eco_filtros_frame, text="Resíduo/Grupo:").grid(row=0, column=4, sticky="e", padx=(0,5))
eco_res_var = tk.StringVar(value="")
eco_res_cb = tb.Combobox(eco_filtros_frame, textvariable=eco_res_var, values=[], state="readonly")
eco_res_cb.grid(row=0, column=5, sticky="ew")

# Botão Calcular (ajustado para dar espaço aos outros)
btn_gerar_eco = tb.Button(eco_filtros_frame, text="Calcular Indicador (kg/m²)", bootstyle=SUCCESS)
btn_gerar_eco.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10,0))

# Novos Botões de Exportação
btn_export_eco_xls = tb.Button(eco_filtros_frame, text="📊 Exportar Excel", bootstyle="outline-success")
btn_export_eco_xls.grid(row=1, column=4, sticky="e", pady=(10,0), padx=5)

btn_export_eco_pdf = tb.Button(eco_filtros_frame, text="📕 Gerar PDF", bootstyle="outline-danger")
btn_export_eco_pdf.grid(row=1, column=5, sticky="e", pady=(10,0))

# --- Área de Conteúdo (Tabela e Gráfico Lado a Lado) ---
eco_content_frame = tb.Frame(aba_eco)
eco_content_frame.pack(fill="both", expand=True)
eco_content_frame.columnconfigure(0, weight=1)
eco_content_frame.columnconfigure(1, weight=1)

# Tabela
eco_card = tb.Labelframe(eco_content_frame, text="Detalhamento Mensal", padding=10, bootstyle=INFO)
eco_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

eco_cols = ("Mês", "Geração (kg)", "Produção (m²)", "Indicador (kg/m²)")
eco_tbl = ttk.Treeview(eco_card, columns=eco_cols, show="headings")
eco_tbl.pack(side="left", fill="both", expand=True)

for c in eco_cols:
    eco_tbl.heading(c, text=c)
    eco_tbl.column(c, anchor="center", width=110)

eco_scroll = ttk.Scrollbar(eco_card, orient="vertical", command=eco_tbl.yview)
eco_tbl.configure(yscrollcommand=eco_scroll.set)
eco_scroll.pack(side="right", fill="y")

# Gráfico
eco_graf_card = tb.Labelframe(eco_content_frame, text="Evolução do Indicador", padding=10, bootstyle=WARNING)
eco_graf_card.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

fig_eco, ax_eco = plt.subplots(figsize=(5,3))
fig_eco.tight_layout(pad=1.5)
canvas_eco = FigureCanvasTkAgg(fig_eco, master=eco_graf_card)
canvas_eco.get_tk_widget().pack(fill="both", expand=True)

# --- Frame de Parâmetros da Importação ---
pdf_params_frame = tb.Labelframe(aba_importacao_config, text="1. Importar dados de tickets", padding=12, bootstyle=INFO)
pdf_params_frame.pack(fill="x", pady=(0, 10))
pdf_params_frame.columnconfigure(1, weight=1)
pdf_params_frame.columnconfigure(3, weight=1) # Adiciona coluna 3

# Linha 0: Parceiro e Data
tb.Label(pdf_params_frame, text="Parceiro *:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
pdf_parceiro_var = tk.StringVar()
pdf_parceiro_cb = tb.Combobox(pdf_params_frame, textvariable=pdf_parceiro_var, values=parceiros, state="readonly", width=30)
pdf_parceiro_cb.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

tb.Label(pdf_params_frame, text="Data da Coleta *:").grid(row=0, column=2, sticky="w", padx=(15, 5), pady=5)
pdf_data_entry = CalendarioPremium(pdf_params_frame, dateformat="%d/%m/%y")
pdf_data_entry.set_date(DATA_HOJE_GLOBAL) # Padrão: Hoje
pdf_data_entry.grid(row=0, column=3, sticky="ew", padx=5, pady=5)

# Linha 1: Tipo e Destinação
tb.Label(pdf_params_frame, text="Tipo *:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
pdf_tipo_var = tk.StringVar(value="Venda") # Padrão Venda
# (Usamos um Combobox aqui, preparando para a Melhoria 1 que discutimos)
pdf_tipo_cb = tb.Combobox(pdf_params_frame, textvariable=pdf_tipo_var, values=["Venda", "Custo", "Reversa"], state="readonly", width=15)
pdf_tipo_cb.grid(row=1, column=1, sticky="w", padx=5, pady=5) # sticky="w" para não esticar muito

tb.Label(pdf_params_frame, text="Destinação *:").grid(row=1, column=2, sticky="w", padx=(15, 5), pady=5)
pdf_destinacao_var = tk.StringVar()
pdf_destinacao_cb = tb.Combobox(pdf_params_frame, textvariable=pdf_destinacao_var, values=destinacoes, state="readonly", width=30)
pdf_destinacao_cb.grid(row=1, column=3, sticky="ew", padx=5, pady=5)


# --- Frame de Ação e Status ---
pdf_action_frame = tb.Labelframe(aba_importacao_config, text="2. Selecionar Arquivo(s) e Importar", padding=12, bootstyle=INFO)
pdf_action_frame.pack(fill="x", pady=(10, 0))

btn_iniciar_import_pdf = tb.Button(pdf_action_frame, text="Selecionar PDF(s) e Importar Itens", bootstyle=SUCCESS)
btn_iniciar_import_pdf.pack(side="left", padx=5, pady=5)

pdf_status_var = tk.StringVar(value="")
tb.Label(pdf_action_frame, textvariable=pdf_status_var, bootstyle=SECONDARY).pack(side="left", padx=10)

# =========================
# Lógica (Definições Formatadas)
# =========================
def abrir_janela_gerenciar_residuo(nome_antigo=None):
    is_edit_mode = (nome_antigo is not None)
    dados_atuais = {}
    if is_edit_mode:
        try: dados_atuais = banco_dict.get(nome_antigo, {})
        except Exception: pass
    
    edit_window = tb.Toplevel(app)
    title = f"Editar: {nome_antigo}" if is_edit_mode else "Novo Resíduo"
    edit_window.title(title)
    edit_window.geometry("900x580") 
    
    main_frame = tb.Frame(edit_window, padding=15)
    main_frame.pack(fill="both", expand=True)
    
    col_esq = tb.Labelframe(main_frame, text="Dados Básicos & Valores", padding=10)
    col_esq.pack(side="left", fill="both", expand=True, padx=(0,10))
    
    col_dir = tb.Labelframe(main_frame, text="Auto-Preenchimento (Padrões)", padding=10, bootstyle=INFO)
    col_dir.pack(side="right", fill="both", expand=True)

    nome_var = tk.StringVar(value=nome_antigo if is_edit_mode else "")
    nome_nf_var = tk.StringVar(value=dados_atuais.get('nome_nf', ''))
    codigo_item_var = tk.StringVar(value=dados_atuais.get('codigo_item', ''))
    codigo_ibama_var = tk.StringVar(value=dados_atuais.get('codigo_ibama', ''))
    modo_var = tk.StringVar(value=dados_atuais.get('modo', 'kg'))
    val_kg_var = tk.StringVar(value=f"{dados_atuais.get('kg', 0.0):.3f}".replace('.',','))
    val_fec_var = tk.StringVar(value=f"{dados_atuais.get('fechado', 0.0):.2f}".replace('.',','))
    peso_unit_var = tk.StringVar(value=f"{dados_atuais.get('peso_unitario', 0.0):.3f}".replace('.',','))
    rateio_var = tk.IntVar(value= 1 if dados_atuais.get('calcula_rateio', 0) else 0)
    exige_nf_var = tk.IntVar(value=1 if not is_edit_mode else int(dados_atuais.get('exige_nf', 1)))
    exige_cert_var = tk.IntVar(value=1 if not is_edit_mode else int(dados_atuais.get('exige_cert', 1)))
    
    padrao_estado_var = tk.StringVar(value=dados_atuais.get('estado_padrao', ''))
    padrao_dest_var = tk.StringVar(value=dados_atuais.get('destinacao_padrao', ''))
    padrao_tipo_var = tk.StringVar(value=dados_atuais.get('tipo_padrao', ''))
    padrao_parc_var = tk.StringVar(value=dados_atuais.get('parceiro_padrao', ''))
    grupo_var = tk.StringVar(value=dados_atuais.get('grupo', ''))

    r=0
    tb.Label(col_esq, text="Resíduo (Interno):").grid(row=r, column=0, sticky="w", pady=5)
    tb.Entry(col_esq, textvariable=nome_var).grid(row=r, column=1, sticky="ew", pady=5); r+=1
    tb.Label(col_esq, text="Grupo de Relatório:", bootstyle="primary").grid(row=r, column=0, sticky="w", pady=5)
    tb.Combobox(col_esq, textvariable=grupo_var, values=sorted(GRUPOS_RELATORIO), state="normal").grid(row=r, column=1, sticky="ew", pady=5); r+=1
    tb.Label(col_esq, text="Nome p/ NF:").grid(row=r, column=0, sticky="w", pady=5)
    tb.Entry(col_esq, textvariable=nome_nf_var).grid(row=r, column=1, sticky="ew", pady=5); r+=1
    tb.Label(col_esq, text="Código Item:").grid(row=r, column=0, sticky="w", pady=5)
    tb.Entry(col_esq, textvariable=codigo_item_var).grid(row=r, column=1, sticky="ew", pady=5); r+=1
    tb.Label(col_esq, text="Código IBAMA:").grid(row=r, column=0, sticky="w", pady=5)
    tb.Entry(col_esq, textvariable=codigo_ibama_var).grid(row=r, column=1, sticky="ew", pady=5); r+=1
    tb.Label(col_esq, text="Modo de Cálculo:").grid(row=r, column=0, sticky="w", pady=5)
    tb.Combobox(col_esq, textvariable=modo_var, values=['kg', 'fechado', 'unidade'], state="readonly").grid(row=r, column=1, sticky="ew", pady=5); r+=1
    tb.Label(col_esq, text="Valor/kg (R$):").grid(row=r, column=0, sticky="w", pady=5)
    tb.Entry(col_esq, textvariable=val_kg_var, validate="key", validatecommand=vcmd_numeric).grid(row=r, column=1, sticky="ew", pady=5); r+=1
    tb.Label(col_esq, text="Valor Fechado (R$):").grid(row=r, column=0, sticky="w", pady=5)
    tb.Entry(col_esq, textvariable=val_fec_var, validate="key", validatecommand=vcmd_numeric).grid(row=r, column=1, sticky="ew", pady=5); r+=1
    tb.Label(col_esq, text="Peso/Unidade (kg):").grid(row=r, column=0, sticky="w", pady=5)
    tb.Entry(col_esq, textvariable=peso_unit_var, validate="key", validatecommand=vcmd_numeric).grid(row=r, column=1, sticky="ew", pady=5); r+=1
    tb.Checkbutton(col_esq, text="Incluir no Relatório de Geração?", variable=rateio_var, bootstyle="primary").grid(row=r, column=0, columnspan=2, sticky="w", pady=10)

    r=0
    tb.Label(col_dir, text="Estado Padrão:").grid(row=r, column=0, sticky="w", pady=5)
    tb.Combobox(col_dir, textvariable=padrao_estado_var, values=["Sólido", "Líquido"], state="readonly").grid(row=r, column=1, sticky="ew", pady=5); r+=1
    tb.Label(col_dir, text="Destinação Padrão:").grid(row=r, column=0, sticky="w", pady=5)
    tb.Combobox(col_dir, textvariable=padrao_dest_var, values=destinacoes, state="readonly").grid(row=r, column=1, sticky="ew", pady=5); r+=1
    tb.Label(col_dir, text="Tipo (Venda/Custo):").grid(row=r, column=0, sticky="w", pady=5)
    tb.Combobox(col_dir, textvariable=padrao_tipo_var, values=["Venda", "Custo"], state="readonly").grid(row=r, column=1, sticky="ew", pady=5); r+=1
    tb.Label(col_dir, text="Parceiro Padrão:").grid(row=r, column=0, sticky="w", pady=5)
    tb.Combobox(col_dir, textvariable=padrao_parc_var, values=parceiros, state="readonly").grid(row=r, column=1, sticky="ew", pady=5); r+=1
    tb.Label(col_dir, text="* Deixe em branco para não preencher automaticamente.", bootstyle="secondary", font=("Segoe UI", 8)).grid(row=r, column=0, columnspan=2, pady=20)
    tb.Separator(col_dir, orient='horizontal').grid(row=r, column=0, columnspan=2, sticky="ew", pady=15); r+=1
    tb.Label(col_dir, text="Regras de Compliance:", bootstyle="primary").grid(row=r, column=0, columnspan=2, sticky="w", pady=(0,5)); r+=1
    tb.Checkbutton(col_dir, text="Exige Nota Fiscal (NF)?", variable=exige_nf_var, bootstyle="round-toggle").grid(row=r, column=0, columnspan=2, sticky="w", pady=5); r+=1
    tb.Checkbutton(col_dir, text="Exige Certificado?", variable=exige_cert_var, bootstyle="round-toggle").grid(row=r, column=0, columnspan=2, sticky="w", pady=5); r+=1

    frame_btns = tb.Frame(edit_window)
    frame_btns.pack(fill="x", padx=15, pady=10)
    
    def salvar_dados_residuo():
        nome_novo = clean_str(nome_var.get())
        nome_nf_novo = clean_str(nome_nf_var.get())
        codigo_item_novo = clean_str(codigo_item_var.get())
        codigo_ibama_novo = clean_str(codigo_ibama_var.get())
        modo_novo = clean_str(modo_var.get()).lower()
        val_kg = to_float_safe(val_kg_var.get())
        val_fec = to_float_safe(val_fec_var.get())
        val_pu = to_float_safe(peso_unit_var.get())
        calcula_rateio_novo = rateio_var.get()
        v_exige_nf = exige_nf_var.get()
        v_exige_cert = exige_cert_var.get()
        p_estado = clean_str(padrao_estado_var.get())
        p_dest = clean_str(padrao_dest_var.get())
        p_tipo = clean_str(padrao_tipo_var.get())
        p_parc = clean_str(padrao_parc_var.get())
        grupo_novo = clean_str(grupo_var.get()) 
        
        if not nome_novo: ModernMessageBox.showerror("Erro", "O nome interno não pode ser vazio.", parent=edit_window); return
        if not is_edit_mode or (is_edit_mode and nome_novo != nome_antigo):
            if nome_novo in banco_dict: ModernMessageBox.showerror("Erro", f"Resíduo '{nome_novo}' já existe.", parent=edit_window); return

        success = False
        if is_edit_mode:
            if db.update_residuo(nome_antigo, nome_novo, nome_nf_novo, codigo_item_novo, codigo_ibama_novo, modo_novo, val_kg, val_fec, val_pu, calcula_rateio_novo, p_estado, p_dest, p_tipo, p_parc, grupo_novo, v_exige_nf, v_exige_cert):
                success = True; set_status(f"Resíduo '{nome_novo}' atualizado.")
            else: ModernMessageBox.showerror("Erro", detalhe_erro_db("Não foi possível atualizar."), parent=edit_window)
        else:
            if db.add_residuo(nome_novo, nome_nf_novo, codigo_item_novo, codigo_ibama_novo, modo_novo, val_kg, val_fec, val_pu, calcula_rateio_novo, p_estado, p_dest, p_tipo, p_parc, grupo_novo, v_exige_nf, v_exige_cert):
                success = True; set_status(f"Resíduo '{nome_novo}' adicionado.")
            else: ModernMessageBox.showerror("Erro", detalhe_erro_db("Não foi possível adicionar."), parent=edit_window)

        if success:
            if is_edit_mode:
                nf_bool = bool(exige_nf_var.get()); cert_bool = bool(exige_cert_var.get())
                msg = f"As regras de compliance para '{nome_novo}' foram salvas.\nDeseja atualizar TODOS os registros passados com essas novas regras?"
                if ModernMessageBox.askyesno("Atualizar Histórico?", msg, parent=edit_window):
                    if db.update_compliance_historico(nome_novo, nf_bool, cert_bool): ModernMessageBox.showinfo("Sucesso", "Registros atualizados!", parent=edit_window)
                    else: ModernMessageBox.showerror("Erro", detalhe_erro_db("Falha ao atualizar."), parent=edit_window)
            edit_window.destroy(); preencher_banco_tabela(); sincronizar_residuos_ui(); atualizar_views()
            
    btn_cancelar = tb.Button(frame_btns, text="Cancelar", command=edit_window.destroy, bootstyle=SECONDARY)
    btn_cancelar.pack(side="right", padx=(10, 0))
    save_text = "Salvar Alterações" if is_edit_mode else "Adicionar Resíduo"
    btn_salvar = tb.Button(frame_btns, text=save_text, command=salvar_dados_residuo, bootstyle=SUCCESS)
    btn_salvar.pack(side="right")
    edit_window.update_idletasks()
    x = app.winfo_x() + (app.winfo_width() // 2) - (edit_window.winfo_width() // 2)
    y = app.winfo_y() + (app.winfo_height() // 2) - (edit_window.winfo_height() // 2)
    edit_window.geometry(f"+{x}+{y}")
    edit_window.wait_window()
    
def obter_df_registros():
    """Retorna uma cópia do DataFrame global de registros."""
    return df_registros_global.copy()

def config_tags_por_tema():
    """Configura as cores das tags da Treeview principal baseadas no tema."""
    dark = (style.theme.name == "superhero")
    
    # --- DEFINIÇÃO DE CORES ---
    dark_venda_fg = "#28a745"   # Verde
    dark_custo_fg = "#dc3545"   # Vermelho
    light_venda_fg = "#155724"
    light_custo_fg = "#721c24"
    
    dark_solido_bg="#1f3a2e"; dark_liquido_bg="#1a2e4a"
    light_solido_bg="#e8f8ee"; light_liquido_bg="#e8f1fb"
    
    # Cores para Certificado/NF
    dark_cert_ok_fg="white"; dark_cert_nao_fg="#FF6347"
    light_cert_ok_fg="black"; light_cert_nao_fg="#CC0000"
    
    # --- NOVA COR DE ALERTA (ATRASO) ---
    # Vermelho bem suave para o fundo da linha inteira
    dark_alert_bg = "#4a1a1a" 
    light_alert_bg = "#ffe6e6" 
    
    font_normal = ("TkDefaultFont", 9); font_bold = ("TkDefaultFont", 9, "bold")

    # --- APLICAÇÃO DAS TAGS ---
    if dark:
        tabela.tag_configure("estado_solido", background=dark_solido_bg)
        tabela.tag_configure("estado_liquido", background=dark_liquido_bg)
        tabela.tag_configure("cert_ok", foreground=dark_cert_ok_fg, font=font_normal)
        tabela.tag_configure("cert_nao", foreground=dark_cert_nao_fg, font=font_bold)
        tabela.tag_configure("nf_ok", foreground=dark_cert_ok_fg, font=font_normal)
        tabela.tag_configure("nf_nao", foreground=dark_cert_nao_fg, font=font_bold)
        tabela.tag_configure("tipo_venda", foreground=dark_venda_fg)
        tabela.tag_configure("tipo_custo", foreground=dark_custo_fg, font=font_bold)
        resumo.tag_configure("lucro_pos", foreground="#28a745") # Verde
        resumo.tag_configure("lucro_neg", foreground="#ff4d4d") # Vermelho claro
        tabela.tag_configure("nf_solicitado", foreground="#ffc107") # Amarelo/Laranja
        
        # Tag de Alerta
        tabela.tag_configure("atrasado", background=dark_alert_bg) 

    else:
        tabela.tag_configure("estado_solido", background=light_solido_bg)
        tabela.tag_configure("estado_liquido", background=light_liquido_bg)
        tabela.tag_configure("cert_ok", foreground=light_cert_ok_fg, font=font_normal)
        tabela.tag_configure("cert_nao", foreground=light_cert_nao_fg, font=font_bold)
        tabela.tag_configure("nf_ok", foreground=light_cert_ok_fg, font=font_normal)
        tabela.tag_configure("nf_nao", foreground=light_cert_nao_fg, font=font_bold)
        tabela.tag_configure("tipo_venda", foreground=light_venda_fg)
        tabela.tag_configure("tipo_custo", foreground=light_custo_fg, font=font_bold)
        resumo.tag_configure("lucro_pos", foreground="#155724") # Verde escuro
        resumo.tag_configure("lucro_neg", foreground="#cc0000") # Vermelho forte
        tabela.tag_configure("nf_solicitado", foreground="#d39e00")
        
        # Tag de Alerta
        tabela.tag_configure("atrasado", background=light_alert_bg)

    # Configura cores alternadas (Zebra) - Mantido igual
    if dark:
        style.configure("Treeview", background=style.colors.bg) 
        style.map("Treeview", background=[('selected', style.colors.primary)])
        for tv in [tabela, resumo, pend_tbl, bn_tbl, pc_tbl, bana_tbl]:
            tv.tag_configure("oddrow", background=style.colors.bg) 
            tv.tag_configure("evenrow", background="#2a2a2a")
    else: 
        style.configure("Treeview", background=style.colors.bg) 
        style.map("Treeview", background=[('selected', style.colors.primary)]) 
        for tv in [tabela, resumo, pend_tbl, bn_tbl, pc_tbl, bana_tbl]:
            tv.tag_configure("oddrow", background=style.colors.bg) 
            tv.tag_configure("evenrow", background="#f2f2f2") # Um cinza bem leve

ORDEM_TABELA = {"col": None, "reverse": False}

def _chave_ordenacao(col, iid):
    """Valor usado para ordenar uma linha: lê os dados reais (data, kg, R$), não o texto formatado."""
    try: row = df_registros_global.loc[int(iid)]
    except Exception: row = None

    if col == "Data":
        v = pd.to_datetime(row.get("Data"), errors="coerce") if row is not None else pd.NaT
        return v if pd.notna(v) else pd.Timestamp.min
    if col == "Peso":
        if row is None: return 0.0
        modo = clean_str(row.get("Modo", "kg")).lower()
        return to_float_safe(row.get("PesoEmKg", 0.0)) if modo == "unidade" else to_float_safe(row.get("Peso", 0.0))
    colunas_valor = {"Valor por kg/unidade": "ValorPorKg", "Valor por kg": "ValorPorKg", "Valor fechado": "ValorFechado", "Transporte": "Transporte"}
    if col in colunas_valor:
        return to_float_safe(row.get(colunas_valor[col], 0.0)) if row is not None else 0.0
    if col == "Valor Total":
        # A coluna mostra o valor do resíduo (total sem o transporte)
        return (to_float_safe(row.get("ValorTotal", 0.0)) - to_float_safe(row.get("Transporte", 0.0))) if row is not None else 0.0
    return normalizar(str(tabela.set(iid, col)))

def _aplicar_ordenacao():
    """Reordena a tabela conforme ORDEM_TABELA e mostra ▲/▼ no título da coluna."""
    col, reverse = ORDEM_TABELA["col"], ORDEM_TABELA["reverse"]
    for c, titulo in TITULOS_TABELA.items():
        seta = (" ▼" if reverse else " ▲") if c == col else ""
        tabela.heading(c, text=titulo + seta)
    if not col: return
    try:
        itens = sorted(tabela.get_children(""), key=lambda k: _chave_ordenacao(col, k), reverse=reverse)
    except Exception as e:
        db._registrar_erro(f"Erro ao ordenar coluna {col}: {e}")
        return
    for i, k in enumerate(itens):
        tabela.move(k, "", i)

def ordenar_coluna(col):
    """Clique no título: ordena pela coluna; clicar de novo inverte a ordem."""
    if ORDEM_TABELA["col"] == col:
        ORDEM_TABELA["reverse"] = not ORDEM_TABELA["reverse"]
    else:
        ORDEM_TABELA["col"], ORDEM_TABELA["reverse"] = col, False
    _aplicar_ordenacao()

def atualizar_menus_dinamicos(base):
    """Atualiza as Comboboxes de filtro (Parceiro, Resíduo, Destinação)."""
    if base.empty: parc_set, res_set, dest_set = [], [], []
    else:
        parc_set=sorted({clean_str(x) for x in base["Parceiro"].astype("string").fillna("") if clean_str(x)})
        res_set=sorted({clean_str(x) for x in base["Residuo"].astype("string").fillna("") if clean_str(x)})
        dest_set=sorted({clean_str(x) for x in base["Destinacao"].astype("string").fillna("") if clean_str(x)})

    # Atualiza Combobox Parceiro
    lista_parc = ["Todos"] + parc_set
    parc_menu.configure(values=lista_parc)
    if f_parc.get() not in lista_parc: f_parc.set("Todos")

    # Atualiza Combobox Resíduo (digitável: o texto não é apagado enquanto o usuário escreve)
    lista_res = ["Todos"] + res_set
    res_menu.configure(values=lista_res)
    configurar_autocomplete(res_menu, lista_res)

    # Atualiza Combobox Destinação
    lista_dest = ["Todas"] + dest_set
    dest_menu.configure(values=lista_dest)
    if f_dest.get() not in lista_dest: f_dest.set("Todas")

def aplicar_filtros(df):
    """Aplica os filtros selecionados na UI ao DataFrame de forma blindada."""
    if df.empty: return df
    d = df.copy()

    # 1. Garante que a coluna do Banco de Dados seja lida corretamente
    if 'Data' in d.columns:
        # Tenta forçar o formato do banco primeiro (Ano-Mês-Dia)
        d['Data'] = pd.to_datetime(d['Data'], format='%Y-%m-%d', errors='coerce')
        # Fallback de segurança caso algo venha diferente
        if d['Data'].isna().all():
            d['Data'] = pd.to_datetime(d['Data'], errors='coerce')

    # 2. Filtro de Datas (Lendo diretamente o objeto do Calendário para evitar inversões)
    try:
        # get_date() extrai a data real, impossibilitando que 01/04 vire 04/01
        data_ini_obj = f_data_inicio.get_date()
        data_fim_obj = f_data_fim.get_date()
        
        dt_inicio = pd.to_datetime(data_ini_obj)
        dt_fim = pd.to_datetime(data_fim_obj) + timedelta(days=1, seconds=-1)

        d = d.dropna(subset=['Data'])
        d = d[(d["Data"] >= dt_inicio) & (d["Data"] <= dt_fim)]
    except Exception as e:
        print(f"Erro ao filtrar data: {e}")

    # 3. Filtros Textuais (Drop Downs)
    if f_parc.get() != "Todos" and 'Parceiro' in d.columns:
        d = d[d["Parceiro"] == f_parc.get()]

    res_sel = clean_str(f_res.get())
    if res_sel and res_sel != "Todos" and 'Residuo' in d.columns:
        if res_sel in banco_residuos or (d["Residuo"] == res_sel).any():
            d = d[d["Residuo"] == res_sel]
        else:
            # Texto parcial digitado: mostra os resíduos que contêm o texto (ignora acentos/maiúsculas)
            res_norm = normalizar(res_sel)
            d = d[d["Residuo"].astype(str).map(normalizar).str.contains(res_norm, regex=False)]

    if f_estado.get() != "Todas" and 'Estado' in d.columns:
        d = d[d["Estado"] == f_estado.get()]

    if f_dest.get() != "Todas" and 'Destinacao' in d.columns:
        d = d[d["Destinacao"] == f_dest.get()]

    if f_tipo.get() != "Todos" and 'Tipo' in d.columns:
        d = d[d["Tipo"] == f_tipo.get()]

    # 4. Filtro de Busca Escrita (Barra de Pesquisa)
    q = clean_str(f_busca.get()).lower()
    if q:
        conditions = []
        if 'Parceiro' in d.columns: 
            conditions.append(d["Parceiro"].str.lower().str.contains(q, na=False))
        if 'PedidoCompra' in d.columns: 
            conditions.append(d["PedidoCompra"].astype(str).str.contains(q, na=False))
        q_norm = normalizar(q)
        if 'Residuo' in d.columns and q_norm: 
            conditions.append(d["Residuo"].astype(str).map(normalizar).str.contains(q_norm, regex=False))
        
        if conditions:
            final_condition = conditions[0]
            for cond in conditions[1:]: 
                final_condition = final_condition | cond
            d = d[final_condition] 
        else: 
            return pd.DataFrame(columns=df.columns) 

    # Ordena Cronologicamente
    if 'Data' in d.columns:
        d = d.sort_values(by='Data', ascending=True)
        
    return d

def preencher_tabela(df):
    """Preenche a tabela priorizando as cores de Estado (Sólido/Líquido)."""
    for r in tabela.get_children(): tabela.delete(r)
    atualizar_totais_tabela(df)
    
    if df.empty: return
    
    hoje = date.today()
    
    for i, row in df.iterrows():
        tags = []
        
        # --- 1. DEFINIÇÃO DA COR DE FUNDO (A MUDANÇA ESTÁ AQUI) ---
        # Verifica o estado para aplicar a cor de fundo da linha
        estado_val = clean_str(row.get("Estado", "")).lower()
        
        if "sólido" in estado_val or "solido" in estado_val:
            tags.append("estado_solido") # Fundo Verde
        elif "líquido" in estado_val or "liquido" in estado_val:
            tags.append("estado_liquido") # Fundo Azul
        else:
            # Se não tiver estado definido, usa o zebra (par/ímpar)
            tags.append("evenrow" if i % 2 == 0 else "oddrow")
        # ----------------------------------------------------------

        # Alerta de Atraso (Certificado Pendente > 30 dias)
        # (Se estiver atrasado, adicionamos a tag 'atrasado' DEPOIS, para sobrescrever a cor se necessário
        # ou você pode optar por não sobrescrever. Aqui vou deixar o atraso ganhar destaque se quiser)
        cert_val_raw = clean_str(row.get("CertificadoOK", "")).lower()
        is_cert_ok = cert_val_raw in ("sim", "ok", "true", "1", "yes")
        is_cert_na = cert_val_raw in ("n/a", "na", "dispensado")
        
        data_registro = row.get('Data')
        if not is_cert_ok and not is_cert_na and pd.notna(data_registro):
            try:
                d_reg = data_registro.date() if isinstance(data_registro, datetime) else data_registro
                if isinstance(d_reg, date) and (hoje - d_reg).days > 30:
                    tags.append("atrasado") # Vermelho (Alerta Crítico)
            except: pass

        # Tags de Texto Colorido (Venda/Custo)
        tipo_val = clean_str(row.get("Tipo", "")).lower()
        if tipo_val == "venda": tags.append("tipo_venda")
        elif tipo_val == "custo": tags.append("tipo_custo")
        
        # Ícones
        if is_cert_ok: icon_cert = "✔"
        elif is_cert_na: icon_cert = ""
        else: 
            icon_cert = "✖"; tags.append("cert_nao") # Texto vermelho no X

        nf_val_raw = clean_str(row.get("NFOk", "")).lower()
        if nf_val_raw in ("sim", "ok", "true", "1", "yes"):
            icon_nf = "✔"
            tags.append("nf_ok")
        elif "solicitado" in nf_val_raw:
            icon_nf = "⏳" # Ícone de ampulheta
            tags.append("nf_solicitado")
        elif nf_val_raw in ("n/a", "na", "dispensado"): 
            icon_nf = ""
        else: 
            icon_nf = "✖"
            tags.append("nf_nao")

        # Valores
        data_str_fmt = format_data_ptbr_abbrev(pd.Series([row.get('Data', pd.NaT)])).iloc[0]
        peso = to_float_safe(row.get("Peso",0))
        vfixo = to_float_safe(row.get("ValorFechado",0))
        transp = to_float_safe(row.get("Transporte",0))
        vtotal = to_float_safe(row.get("ValorTotal",0))
        
        transp_display = fmt_moeda(transp) if transp > 0 else ""
        vfixo_display = fmt_moeda(vfixo) if vfixo > 0 else ""
        
        vkg = to_float_safe(row.get("ValorPorKg",0))
        modo = clean_str(row.get('Modo',"kg")).lower()
        
        valor_unit_display = ""
        if modo in ('kg', 'unidade', 'ton') and vkg > 0:
            valor_unit_display = fmt_moeda(vkg)

        peso_display = fmt_kg(peso)
        if modo == 'unidade':
             s_un = f"{Decimal(str(peso)):.0f}"
             
             peso_real_kg = to_float_safe(row.get("PesoEmKg", 0))
             
             if peso_real_kg > 0:
                 peso_display = f"{s_un} un ({fmt_kg(peso_real_kg)})"
             else:
                 peso_display = f"{s_un} un"

        val_res_calc = vtotal - transp
        val_res_display = fmt_moeda(val_res_calc) if val_res_calc > 0 else ""

        values_display = ( 
            data_str_fmt, clean_str(row.get('Parceiro',"")), clean_str(row.get('Residuo',"")), 
            clean_str(row.get('Estado',"")), clean_str(row.get('Destinacao',"")), 
            clean_str(row.get('Tipo',"")).capitalize(), 
            peso_display, valor_unit_display, vfixo_display, val_res_display, transp_display,
            clean_str(row.get("PedidoCompra","")), icon_cert, icon_nf
        )
        
        tabela.insert("", "end", iid=str(i), values=values_display, tags=tuple(tags))

    if ORDEM_TABELA["col"]: _aplicar_ordenacao()

def atualizar_totais_tabela(df):
    """Mostra no título do quadro 'Registros' a quantidade, o peso e os valores dos registros filtrados."""
    n = len(df)
    if n == 0:
        tbl_card.configure(text="Registros  —  nenhum registro encontrado")
        return
    peso_total = Decimal("0"); venda = Decimal("0"); custo = Decimal("0")
    for _, row in df.iterrows():
        modo = clean_str(row.get("Modo", "kg")).lower()
        peso_total += _dec(row.get("PesoEmKg", 0.0) if modo == "unidade" else row.get("Peso", 0.0))
        tipo = clean_str(row.get("Tipo", "")).lower()
        valor = _dec(row.get("ValorTotal", 0.0))
        if tipo == "venda": venda += valor
        elif tipo == "custo": custo += valor
    partes = [f"{n} {'registro' if n == 1 else 'registros'}", fmt_kg(peso_total)]
    if venda: partes.append(f"Venda: {fmt_moeda(venda)}")
    if custo: partes.append(f"Custo: {fmt_moeda(custo)}")
    tbl_card.configure(text="Registros  —  " + "  ·  ".join(partes))

# --- Funções Sincronização/Preenchimento Bancos Apoio ---
def preencher_banco_tabela():
    global df_banco, banco_dict 
    df_banco = db.get_banco_residuos() 
    banco_dict.clear()
    for r in bn_tbl.get_children(): bn_tbl.delete(r)
    q = normalizar(bn_busca.get())
        
    row_num = 0
    for i, row in df_banco.iterrows():
        residuo_nome = clean_str(row.get("Residuo", ""))
        if not residuo_nome: continue

        residuo_data = {
            'nome_nf': clean_str(row.get('NomeNF', '')),
            'codigo_item': clean_str(row.get('CodigoItem', '')),
            'codigo_ibama': clean_str(row.get('CodigoIBAMA', '')),
            'modo': clean_str(row.get('ModoPadrao', 'kg')).lower(),
            'kg': to_float_safe(row.get('ValorPorKgPadrao', 0.0)),
            'fechado': to_float_safe(row.get('ValorFechadoPadrao', 0.0)),
            'peso_unitario': to_float_safe(row.get('PesoUnitarioKgPadrao', 0.0)),
            'calcula_rateio': bool(row.get('CalculaRateio', 0)),
            'estado_padrao': clean_str(row.get('EstadoPadrao', '')),
            'destinacao_padrao': clean_str(row.get('DestinacaoPadrao', '')),
            'tipo_padrao': clean_str(row.get('TipoPadrao', '')),
            'parceiro_padrao': clean_str(row.get('ParceiroPadrao', '')),
            'grupo': clean_str(row.get('Grupo', '')),
            'exige_nf': bool(row.get('ExigeNF', 1)),
            'exige_cert': bool(row.get('ExigeCertificado', 1))
        }
        banco_dict[residuo_nome] = residuo_data 
        codigo_ibama = calculos.formatar_codigo_ibama(residuo_data['codigo_ibama'])
        if q and not any(q in normalizar(t) for t in (residuo_nome, residuo_data['nome_nf'], residuo_data['codigo_ibama'])): continue
        if bn_so_sem_ibama.get() and codigo_ibama: continue

        # Valor padrão numa coluna só, conforme o modo (vazio quando não há valor)
        modo = residuo_data['modo']
        if modo == 'fechado':
            valor_txt = f"{fmt_moeda(residuo_data['fechado'])} fechado" if residuo_data['fechado'] > 0 else ""
        elif modo == 'unidade':
            valor_txt = f"{fmt_moeda(residuo_data['kg'])}/un" if residuo_data['kg'] > 0 else ""
            if residuo_data['peso_unitario'] > 0: valor_txt = (valor_txt + f"  ({fmt_kg(residuo_data['peso_unitario'])}/un)").strip()
        else:
            valor_txt = f"{fmt_moeda(residuo_data['kg'])}/kg" if residuo_data['kg'] > 0 else ""

        values_display = (
            residuo_nome,
            codigo_ibama or "falta",
            residuo_data['nome_nf'],
            residuo_data['codigo_item'],
            residuo_data['destinacao_padrao'],
            valor_txt,
        )
        tags = ["evenrow" if row_num % 2 == 0 else "oddrow"]
        if not codigo_ibama: tags.append("sem_ibama")
        bn_tbl.insert("", "end", iid=str(i), values=values_display, tags=tuple(tags))
        row_num += 1
        
def sincronizar_residuos_ui():
    global banco_residuos, banco_residuos_rateio 
    banco_residuos = sorted(df_banco["Residuo"].tolist()) if 'Residuo' in df_banco.columns else []    
    lista_final_rateio = []
    
    if not df_banco.empty:
        # 1. Extrai apenas os nomes dos Grupos
        if 'Grupo' in df_banco.columns:
            grupos_existentes = [g for g in df_banco['Grupo'].unique() if clean_str(g)]
            lista_final_rateio.extend(grupos_existentes)
            
        # 2. Extrai os Itens que calculam rateio, MAS que NÃO possuem Grupo
        if 'CalculaRateio' in df_banco.columns:
            mask_rateio = df_banco['CalculaRateio'] == 1
            
            if 'Grupo' in df_banco.columns:
                # Cria uma máscara para identificar quem está com o grupo vazio ou nulo
                mask_sem_grupo = df_banco['Grupo'].isna() | (df_banco['Grupo'].astype(str).str.strip() == "")
                # Aplica as duas regras: Tem que calcular rateio E tem que estar sem grupo
                itens_individuais = df_banco[mask_rateio & mask_sem_grupo]['Residuo'].tolist()
            else:
                itens_individuais = df_banco[mask_rateio]['Residuo'].tolist()
                
            lista_final_rateio.extend(itens_individuais)
            
    banco_residuos_rateio = sorted(list(set(lista_final_rateio)))
    
    res_cb.configure(values=banco_residuos)
    configurar_autocomplete(res_cb, banco_residuos)
    
    lista_res = ["Todos"] + banco_residuos
    res_menu.configure(values=lista_res)
    configurar_autocomplete(res_menu, lista_res)
    
    if 'ger_res_cb' in globals(): 
        ger_res_cb.configure(values=banco_residuos_rateio)
        if ger_res_var.get() not in banco_residuos_rateio:
            if banco_residuos_rateio: ger_res_var.set(banco_residuos_rateio[0])
            else: ger_res_var.set("")

    if 'eco_res_cb' in globals(): 
        eco_res_cb.configure(values=banco_residuos_rateio)
        if eco_res_var.get() not in banco_residuos_rateio:
            if banco_residuos_rateio: eco_res_var.set(banco_residuos_rateio[0])
            else: eco_res_var.set("")
            
def preencher_parceiros_tabela():
    global df_parceiros
    df_parceiros = db.get_banco_parceiros() # Lê do DB (agora vazio)
    
    for r in pc_tbl.get_children(): 
        pc_tbl.delete(r)
        
    row_num = 0
    
    # O loop 'for' será pulado se df_parceiros estiver vazio, o que está correto.
    for i, row in df_parceiros.iterrows():
        # --- ESTAS LINHAS FORAM MOVIDAS PARA DENTRO DO LOOP ---
        tag = "evenrow" if row_num % 2 == 0 else "oddrow"
        # Adiciona o TipoParceiro (com 'Destinador' como padrão se estiver vazio)
        tipo = clean_str(row.get("TipoParceiro", "Destinador"))
        if not tipo: tipo = "Destinador" # Garante que não fique vazio
        pc_tbl.insert("", "end", iid=str(i), values=(clean_str(row["Parceiro"]), tipo), tags=(tag,))
        row_num += 1
        
# =======================================================
# SINCRONIZAÇÃO DE PARCEIROS (COM FILTRO INTELIGENTE)
# =======================================================
global lista_destinadores, lista_transportadores, lista_laboratorios, lista_todos_parceiros
lista_destinadores, lista_transportadores, lista_laboratorios, lista_todos_parceiros = [], [], [], []

def atualizar_combobox_parceiro_dinamico(*_):
    """Muda a lista de parceiros do Novo Registro dependendo do Radiobutton selecionado no topo"""
    if 'parceiro_cb' not in globals() or 'launch_type_var' not in globals(): return
    
    modo = clean_str(launch_type_var.get()).lower()
    
    # Escolhe a lista correta
    if "transporte" in modo:
        nova_lista = lista_transportadores if lista_transportadores else lista_todos_parceiros
    elif "análise" in modo or "analise" in modo:
        nova_lista = lista_laboratorios if lista_laboratorios else lista_todos_parceiros
    else:
        nova_lista = lista_destinadores if lista_destinadores else lista_todos_parceiros
            
    # Atualiza os valores visíveis da caixa principal
    parceiro_cb.configure(values=nova_lista)
    
    # RECONFIGURA O AUTOCOMPLETE PARA ELE NÃO PUXAR A LISTA ANTIGA!
    configurar_autocomplete(parceiro_cb, nova_lista)

    # Limpa o texto se o parceiro atual não for compatível com a nova lista
    if parceiro_cb.get() not in nova_lista and nova_lista:
        parceiro_cb.set(nova_lista[0])
    elif not nova_lista:
        parceiro_cb.set("")

def sincronizar_parceiros_ui():
    global lista_destinadores, lista_transportadores, lista_laboratorios, lista_todos_parceiros
    global parceiros # Mantém o alias antigo por compatibilidade
    
    df_parceiros = db.get_banco_parceiros()
    
    if df_parceiros.empty:
        lista_todos_parceiros = lista_destinadores = lista_transportadores = lista_laboratorios = parceiros = []
    else:
        lista_todos_parceiros = sorted(df_parceiros['Parceiro'].tolist())
        parceiros = lista_todos_parceiros 
        
        # Filtra de acordo com a coluna TipoParceiro (existente na sua aba 5)
        if 'TipoParceiro' in df_parceiros.columns:
            col = 'TipoParceiro'
            lista_destinadores = sorted(df_parceiros[df_parceiros[col].str.contains('Destinador|Receptor|Final', case=False, na=False)]['Parceiro'].tolist())
            lista_transportadores = sorted(df_parceiros[df_parceiros[col].str.contains('Transportador|Transporte|Logística', case=False, na=False)]['Parceiro'].tolist())
            lista_laboratorios = sorted(df_parceiros[df_parceiros[col].str.contains('Lab|Análise', case=False, na=False)]['Parceiro'].tolist())
        else:
            lista_destinadores = lista_transportadores = lista_laboratorios = lista_todos_parceiros

    # 1. Atualiza a Aba de Análise Externa (Força a ser só Laboratórios)
    if 'ana_parc_cb' in globals():
        ana_parc_cb.configure(values=lista_laboratorios if lista_laboratorios else lista_todos_parceiros)
        configurar_autocomplete(ana_parc_cb, lista_laboratorios if lista_laboratorios else lista_todos_parceiros)

    # 2. Atualiza a Aba de Transporte (Força a ser só Transportadores)
    if 'transp_parc_cb' in globals():
        transp_parc_cb.configure(values=lista_transportadores if lista_transportadores else lista_todos_parceiros)
        configurar_autocomplete(transp_parc_cb, lista_transportadores if lista_transportadores else lista_todos_parceiros)

    # 3. Atualiza a Aba de Importação PDF
    if 'pdf_parceiro_cb' in globals():
        pdf_parceiro_cb.configure(values=lista_todos_parceiros)

    # 4. Atualiza o Filtro da Tabela de Registros
    if 'parc_menu' in globals():
        lista_parc = ["Todos"] + lista_todos_parceiros
        parc_menu.configure(values=lista_parc)

    # 5. Dispara a atualização dinâmica da aba principal
    atualizar_combobox_parceiro_dinamico()
    
def preencher_analises_tabela():
    """Recarrega dados das análises do DB e preenche a tabela."""
    global df_analises
    df_analises = db.get_banco_analises() # Recarrega do DB

    # Limpa a tabela da UI
    for r in bana_tbl.get_children():
        bana_tbl.delete(r)

    row_num = 0
    # Preenche a tabela da UI com os dados recarregados
    for i, row in df_analises.iterrows():
        nome_analise = clean_str(row.get("NomeAnalise", ""))
        valor_padrao = to_float_safe(row.get("ValorPadrao", 0.0))
        
        if nome_analise: # Só adiciona se tiver nome
            # Insere os DOIS valores
            values_display = (nome_analise, fmt_moeda(valor_padrao))
            tag = "evenrow" if row_num % 2 == 0 else "oddrow"
            bana_tbl.insert("", "end", iid=str(i), values=values_display, tags=(tag,))
            row_num += 1

def sincronizar_analises_ui():
    global lista_analises, analises_dict
    if 'df_analises' in globals() and not df_analises.empty and 'NomeAnalise' in df_analises.columns:
        lista_analises = sorted(df_analises["NomeAnalise"].tolist())
        analises_dict = {row['NomeAnalise']: to_float_safe(row.get('ValorPadrao', 0.0))
                         for _, row in df_analises.iterrows() if clean_str(row.get("NomeAnalise", ""))}
    else: lista_analises = []; analises_dict = {}
    ana_nome_cb.configure(values=lista_analises)
    current_ana = ana_nome_var.get()
    if not current_ana and lista_analises: ana_nome_var.set(lista_analises[0])
    elif current_ana and current_ana not in lista_analises and lista_analises: ana_nome_var.set(lista_analises[0])
    elif not lista_analises: ana_nome_var.set("")
    atualizar_valor_por_analise()

# --- CRUD Abas Apoio ---
def banco_add():
    """Abre a janela de gerenciamento em 'Modo Adicionar'."""
    abrir_janela_gerenciar_residuo(nome_antigo=None)

def banco_edit_wrapper():
    """Pega o item selecionado e abre a janela de gerenciamento em 'Modo Editar'."""
    sel = bn_tbl.focus(); idx = int(sel) if sel else -1;
    if idx == -1: 
        ModernMessageBox.showerror("Erro","Selecione um resíduo para editar.")
        return
        
    try:
        nome_antigo = df_banco.loc[idx, "Residuo"]
        abrir_janela_gerenciar_residuo(nome_antigo=nome_antigo)
    except (KeyError, IndexError): 
        ModernMessageBox.showerror("Erro", "Índice inválido ou dados não encontrados.")
        
def banco_del():
    sel = bn_tbl.focus(); idx = int(sel) if sel else -1;
    if idx == -1: ModernMessageBox.showerror("Erro","Selecione."); return
    try: nome = df_banco.loc[idx, "Residuo"]
    except (KeyError, IndexError): ModernMessageBox.showerror("Erro", "Índice inválido."); return
    if ModernMessageBox.askyesno("Confirmar", f"Excluir '{nome}'?"):
        if db.delete_residuo(nome): preencher_banco_tabela(); sincronizar_residuos_ui(); set_status("Resíduo excluído.")
        else: ModernMessageBox.showerror("Erro", "Falha ao excluir.")

def parceiros_add():
    """Abre a janela de gerenciamento de parceiro em 'Modo Adicionar'."""
    abrir_janela_gerenciar_parceiro(nome_antigo=None)

def parceiros_edit_wrapper():
    """Pega o item selecionado e abre a janela de gerenciamento em 'Modo Editar'."""
    sel = pc_tbl.focus(); idx = int(sel) if sel else -1;
    if idx == -1: 
        ModernMessageBox.showerror("Erro","Selecione um parceiro para editar.")
        return

    try:
        nome_antigo = df_parceiros.loc[idx, "Parceiro"]
        abrir_janela_gerenciar_parceiro(nome_antigo=nome_antigo)
    except (KeyError, IndexError): 
        ModernMessageBox.showerror("Erro", "Índice inválido ou dados não encontrados.")

def abrir_janela_gerenciar_parceiro(nome_antigo=None):
    is_edit_mode = (nome_antigo is not None)
    tipo_atual = "Destinador"
    cnpj_atual = ""
    
    if is_edit_mode:
        try:
            df_filtrado = df_parceiros[df_parceiros['Parceiro'] == nome_antigo]
            tipo_atual = df_filtrado['TipoParceiro'].iloc[0]
            if 'CNPJ' in df_parceiros.columns:
                cnpj_atual = df_filtrado['CNPJ'].iloc[0]
            if not tipo_atual: tipo_atual = "Destinador"
        except Exception: 
            tipo_atual = "Destinador"

    edit_window = tb.Toplevel(app)
    title = f"Editar Parceiro: {nome_antigo}" if is_edit_mode else "Novo Parceiro"
    edit_window.title(title)
    edit_window.geometry("450x230") 
    edit_window.resizable(False, False)
    edit_window.transient(app); edit_window.grab_set() 
    
    main_frame = tb.Frame(edit_window, padding=15)
    main_frame.pack(fill="both", expand=True)
    main_frame.columnconfigure(1, weight=1) 

    nome_var = tk.StringVar(value=nome_antigo if is_edit_mode else "")
    tipo_var = tk.StringVar(value=tipo_atual)
    cnpj_var = tk.StringVar(value=cnpj_atual)
    lista_tipos = ["Destinador", "Laboratório", "Transportador"] 

    row_num = 0
    tb.Label(main_frame, text="Nome:").grid(row=row_num, column=0, sticky="w", padx=(0,10), pady=5)
    tb.Entry(main_frame, textvariable=nome_var).grid(row=row_num, column=1, sticky="ew", pady=5); row_num += 1
    tb.Label(main_frame, text="CNPJ:").grid(row=row_num, column=0, sticky="w", padx=(0,10), pady=5)
    tb.Entry(main_frame, textvariable=cnpj_var).grid(row=row_num, column=1, sticky="ew", pady=5); row_num += 1
    tb.Label(main_frame, text="Tipo:").grid(row=row_num, column=0, sticky="w", padx=(0,10), pady=5)
    tb.Combobox(main_frame, textvariable=tipo_var, values=lista_tipos, state="readonly").grid(row=row_num, column=1, sticky="ew", pady=5); row_num += 1

    button_frame = tb.Frame(main_frame)
    button_frame.grid(row=row_num, column=0, columnspan=2, pady=(15, 0), sticky="e")

    def salvar_dados_parceiro():
        nome_novo = clean_str(nome_var.get())
        tipo_novo = clean_str(tipo_var.get())
        cnpj_novo = clean_str(cnpj_var.get())
        
        if not nome_novo or not tipo_novo: 
            ModernMessageBox.showerror("Erro", "Preencha Nome e Tipo.", parent=edit_window)
            return
            
        if not is_edit_mode or (is_edit_mode and nome_novo != nome_antigo):
            if nome_novo in parceiros: 
                ModernMessageBox.showerror("Erro", f"'{nome_novo}' já existe.", parent=edit_window)
                return

        success = False
        if is_edit_mode:
            if db.update_parceiro(nome_antigo, nome_novo, tipo_novo, cnpj_novo): 
                success = True; set_status("Atualizado.")
            else: 
                ModernMessageBox.showerror("Erro", detalhe_erro_db("Falha ao atualizar."), parent=edit_window)
        else:
            if db.add_parceiro(nome_novo, tipo_novo, cnpj_novo): 
                success = True; set_status("Adicionado.")
            else: 
                ModernMessageBox.showerror("Erro", detalhe_erro_db("Falha ao adicionar."), parent=edit_window)

        if success: 
            edit_window.destroy()
            preencher_parceiros_tabela()
            sincronizar_parceiros_ui()

    tb.Button(button_frame, text="Cancelar", command=edit_window.destroy, bootstyle=SECONDARY).pack(side="right", padx=(10, 0))
    save_text = "Salvar" if is_edit_mode else "Adicionar"
    tb.Button(button_frame, text=save_text, command=salvar_dados_parceiro, bootstyle=SUCCESS).pack(side="right")
    
    edit_window.update_idletasks()
    x = app.winfo_x() + (app.winfo_width() // 2) - (edit_window.winfo_width() // 2)
    y = app.winfo_y() + (app.winfo_height() // 2) - (edit_window.winfo_height() // 2)
    edit_window.geometry(f"+{x}+{y}")
    edit_window.wait_window()

def parceiros_del():
    sel = pc_tbl.focus(); idx = int(sel) if sel else -1;
    if idx == -1: ModernMessageBox.showerror("Erro","Selecione."); return
    try: nome = df_parceiros.loc[idx, "Parceiro"]
    except (KeyError, IndexError): ModernMessageBox.showerror("Erro", "Índice inválido."); return
    if ModernMessageBox.askyesno("Confirmar", f"Excluir '{nome}'?"):
        if db.delete_parceiro(nome): preencher_parceiros_tabela(); sincronizar_parceiros_ui(); set_status("Parceiro excluído.")
        else: ModernMessageBox.showerror("Erro", "Falha ao excluir.")

def analises_add():
    """Abre a janela de gerenciamento de análise em 'Modo Adicionar'."""
    abrir_janela_gerenciar_analise(nome_antigo=None)

def analises_edit_wrapper():
    """Pega o item selecionado e abre a janela de gerenciamento em 'Modo Editar'."""
    sel = bana_tbl.focus(); idx = int(sel) if sel else -1;
    if idx == -1: 
        ModernMessageBox.showerror("Erro", "Selecione uma análise para editar.")
        return
        
    try:
        nome_antigo = df_analises.loc[idx, "NomeAnalise"]
        abrir_janela_gerenciar_analise(nome_antigo=nome_antigo)
    except (KeyError, IndexError): 
        ModernMessageBox.showerror("Erro", "Índice inválido ou dados não encontrados.")



def abrir_janela_gerenciar_analise(nome_antigo=None):
    """Abre uma janela Toplevel para Adicionar (nome_antigo=None) ou Editar análise."""
    
    is_edit_mode = (nome_antigo is not None)
    
    valor_atual = 0.0
    if is_edit_mode:
        # Tenta pegar o valor atual do dicionário ou do DF
        valor_atual = analises_dict.get(nome_antigo, 0.0)
    
    # --- Cria a Janela Toplevel ---
    edit_window = tk.Toplevel(app)
    title = f"Editar Análise: {nome_antigo}" if is_edit_mode else "Adicionar Nova Análise"
    edit_window.title(title)
    edit_window.geometry("450x250") # Tamanho ajustado
    edit_window.resizable(False, False)
    edit_window.transient(app); edit_window.grab_set() 

    main_frame = tb.Frame(edit_window, padding=15)
    main_frame.pack(fill="both", expand=True)
    main_frame.columnconfigure(1, weight=1) 

    # --- Variáveis ---
    nome_var = tk.StringVar(value=nome_antigo if is_edit_mode else "")
    # Formata o valor para o padrão brasileiro (vírgula)
    valor_var = tk.StringVar(value=f"{valor_atual:.2f}".replace(".", ","))

    # --- Widgets ---
    row_num = 0
    
    # Campo Nome
    tb.Label(main_frame, text="Nome da Análise:").grid(row=row_num, column=0, sticky="w", padx=(0,10), pady=5)
    tb.Entry(main_frame, textvariable=nome_var).grid(row=row_num, column=1, sticky="ew", pady=5)
    row_num += 1
    
    # Campo Valor
    tb.Label(main_frame, text="Valor Padrão (R$):").grid(row=row_num, column=0, sticky="w", padx=(0,10), pady=5)
    # Usamos vcmd_numeric para garantir que só entrem números
    tb.Entry(main_frame, textvariable=valor_var, validate="key", validatecommand=vcmd_numeric).grid(row=row_num, column=1, sticky="ew", pady=5)
    row_num += 1

    # Botões
    button_frame = tb.Frame(main_frame)
    button_frame.grid(row=row_num, column=0, columnspan=2, pady=(20, 0), sticky="e")

    # --- Função Interna para Salvar ---
    def salvar_dados_analise():
        nome_novo = clean_str(nome_var.get())
        valor_novo = money_pt(valor_var.get()) # Converte string "100,50" para Decimal/Float
        
        if not nome_novo:
            ModernMessageBox.showerror("Erro", "O nome da análise não pode ser vazio.", parent=edit_window)
            return
        
        # Verifica duplicidade (se nome mudou ou é novo)
        if not is_edit_mode or (is_edit_mode and nome_novo != nome_antigo):
            if nome_novo in analises_dict:
                ModernMessageBox.showerror("Erro", f"A análise '{nome_novo}' já existe.", parent=edit_window)
                return

        success = False
        if is_edit_mode:
            if db.update_analise(nome_antigo, nome_novo, float(valor_novo)):
                success = True
                set_status(f"Análise '{nome_novo}' atualizada.")
            else:
                ModernMessageBox.showerror("Erro ao Salvar", detalhe_erro_db("Não foi possível atualizar a análise."), parent=edit_window)
        else:
            if db.add_analise(nome_novo, float(valor_novo)):
                success = True
                set_status(f"Análise '{nome_novo}' adicionada.")
            else:
                 ModernMessageBox.showerror("Erro ao Salvar", detalhe_erro_db("Não foi possível adicionar a análise."), parent=edit_window)

        if success:
            edit_window.destroy()
            preencher_analises_tabela()
            sincronizar_analises_ui()
            
    # --- Botões UI ---
    btn_cancelar = tb.Button(button_frame, text="Cancelar", command=edit_window.destroy, bootstyle=SECONDARY)
    btn_cancelar.pack(side="right", padx=(10, 0))
    
    save_text = "Salvar Alterações" if is_edit_mode else "Adicionar Análise"
    btn_salvar = tb.Button(button_frame, text=save_text, command=salvar_dados_analise, bootstyle=SUCCESS)
    btn_salvar.pack(side="right")

    # Centralizar
    edit_window.update_idletasks()
    x = app.winfo_x() + (app.winfo_width() // 2) - (edit_window.winfo_width() // 2)
    y = app.winfo_y() + (app.winfo_height() // 2) - (edit_window.winfo_height() // 2)
    edit_window.geometry(f"+{x}+{y}")
    edit_window.wait_window()

def analises_del():
    sel = bana_tbl.focus(); idx = int(sel) if sel else -1;
    if idx == -1: ModernMessageBox.showerror("Erro","Selecione."); return
    try: nome = df_analises.loc[idx, "NomeAnalise"]
    except (KeyError, IndexError): ModernMessageBox.showerror("Erro", "Índice inválido."); return
    if ModernMessageBox.askyesno("Confirmar", f"Excluir '{nome}'?"):
        if db.delete_analise(nome): preencher_analises_tabela(); sincronizar_analises_ui(); set_status("Análise excluída.")
        else: ModernMessageBox.showerror("Erro", "Falha ao excluir.")
def banco_edit_grupo_lote():
    """Abre um pop-up para aplicar o mesmo Grupo de Relatório a vários resíduos de uma vez."""
    selecionados = bn_tbl.selection()
    if not selecionados:
        ModernMessageBox.showwarning("Aviso", "Selecione pelo menos um resíduo na tabela (use Shift ou Ctrl para selecionar vários).")
        return

    janela_lote = tb.Toplevel(app)
    janela_lote.title("Agrupar em Lote")
    janela_lote.geometry("450x220")
    janela_lote.resizable(False, False)
    janela_lote.transient(app); janela_lote.grab_set()

    tb.Label(janela_lote, text=f"Definir 'Grupo' para {len(selecionados)} resíduo(s) selecionado(s):", font=("Segoe UI", 11, "bold")).pack(pady=(20, 10))

    grupo_lote_var = tk.StringVar()
    cb_grupo = tb.Combobox(janela_lote, textvariable=grupo_lote_var, values=sorted(GRUPOS_RELATORIO), state="normal")
    cb_grupo.pack(fill="x", padx=40, pady=10)

    def salvar_lote():
        novo_grupo = clean_str(grupo_lote_var.get())
        sucessos = 0
        
        for iid in selecionados:
            idx = int(iid)
            try:
                nome_atual = df_banco.loc[idx, "Residuo"]
                dados = banco_dict.get(nome_atual, {})

                # Reaproveita os dados atuais e substitui apenas o grupo
                if db.update_residuo(
                    nome_atual, nome_atual, dados.get('nome_nf', ''), dados.get('codigo_item', ''),
                    dados.get('codigo_ibama', ''), dados.get('modo', 'kg'), float(dados.get('kg', 0.0)),
                    float(dados.get('fechado', 0.0)), float(dados.get('peso_unitario', 0.0)),
                    int(dados.get('calcula_rateio', 0)), dados.get('estado_padrao', ''),
                    dados.get('destinacao_padrao', ''), dados.get('tipo_padrao', ''),
                    dados.get('parceiro_padrao', ''), novo_grupo, int(dados.get('exige_nf', 1)),
                    int(dados.get('exige_cert', 1))
                ):
                    sucessos += 1
            except Exception as e:
                print(f"Erro no lote para o ID {idx}: {e}")

        janela_lote.destroy()
        if sucessos > 0:
            preencher_banco_tabela()
            sincronizar_residuos_ui()
            ModernMessageBox.showinfo("Sucesso", f"Grupo '{novo_grupo}' aplicado em {sucessos} resíduo(s)!")
        else:
            ModernMessageBox.showerror("Erro", "Não foi possível atualizar os resíduos.\n\n" + detalhe_erro_db(""))

    frame_btns = tb.Frame(janela_lote)
    frame_btns.pack(pady=15)
    tb.Button(frame_btns, text="Cancelar", command=janela_lote.destroy, bootstyle=SECONDARY).pack(side="left", padx=10)
    tb.Button(frame_btns, text="Aplicar Grupo", bootstyle=SUCCESS, command=salvar_lote).pack(side="left")
    
    janela_lote.update_idletasks()
    x = app.winfo_x() + (app.winfo_width() // 2) - (janela_lote.winfo_width() // 2)
    y = app.winfo_y() + (app.winfo_height() // 2) - (janela_lote.winfo_height() // 2)
    janela_lote.geometry(f"+{x}+{y}")

def reclassificar_lote():
    # Exemplo: Puxa o nome atual da tabela e pede o novo
    sel = bn_tbl.focus()
    if not sel: return
    
    nome_antigo = df_banco.loc[int(sel), "Residuo"]
    
    # Pergunta o novo nome
    novo_nome = simpledialog.askstring("Reclassificar", f"Novo nome para '{nome_antigo}':")
    
    if novo_nome and novo_nome != nome_antigo:
        if db.renomear_residuo_em_massa(nome_antigo, novo_nome):
            ModernMessageBox.showinfo("Sucesso", "Resíduo renomeado em todos os registros!")
            atualizar_views() # Recarrega tudo
        else:
            ModernMessageBox.showerror("Erro", "Falha ao renomear.")
        
# --- Funções Análise/Display (Dashboard) ---
def atualizar_dashboard_home():
    """Calcula os KPIs do mês atual e atualiza os Cards da tela inicial."""
    try:
        hoje = date.today()
        
        if 'df_registros_global' not in globals() or df_registros_global.empty:
            lbl_dash_peso.config(text="0,00 kg")
            lbl_dash_custo.config(text="R$ 0,00")
            lbl_dash_rec.config(text="0,0%")
            return

        # Puxa os dados e cria a coluna com o peso real convertido (kg/unidade)
        df = get_df_com_peso_real(df_registros_global.copy())
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        
        # Filtra apenas o que aconteceu no mês e ano em que estamos
        df_mes = df[(df['Data'].dt.month == hoje.month) & (df['Data'].dt.year == hoje.year)]
        
        peso_total = df_mes['Peso_KG_Real'].sum() if 'Peso_KG_Real' in df_mes.columns else 0.0
        # A coluna no banco chama-se 'ValorTotal'
        custo_total = df_mes['ValorTotal'].sum() if 'ValorTotal' in df_mes.columns else 0.0
        
        # Calcula a Taxa de Circularidade (COM TRAVA DE SEGURANÇA)
        palavras_verdes = ['reciclagem', 'compostagem', 'reuso', 'blendagem para co-processamento', 'coprocessamento', 'recuperação', 'logística reversa']
            
        def verifica_circularidade(dest):
            d = str(dest).lower()
            # Trava: se for efluente, aterro ou incineração, barra na hora (não é circular)
            if 'efluente' in d or 'aterro' in d or 'incineração' in d:
                return False
            # Se não bateu na trava, verifica se tem as palavras verdes
            return any(pv in d for pv in palavras_verdes)

        # CORREÇÃO 1: Substituição de 'agrupado' por 'df_mes'
        if not df_mes.empty:
            mask_verde = df_mes['Destinacao'].apply(verifica_circularidade)
            peso_circular = df_mes[mask_verde]['Peso_KG_Real'].sum()
        else:
            peso_circular = 0.0
            
        taxa_circ = (peso_circular / peso_total) * 100 if peso_total > 0 else 0.0

        peso_str = f"{peso_total:,.2f} kg".replace(",", "X").replace(".", ",").replace("X", ".")
        custo_str = f"R$ {custo_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        lbl_dash_peso.config(text=peso_str)
        lbl_dash_custo.config(text=custo_str)
        
        # CORREÇÃO 2: Substituição de 'taxa_rec' pela variável correta 'taxa_circ'
        lbl_dash_rec.config(text=f"{taxa_circ:.1f}%")
        
    except Exception as e:
        import traceback
        erro_detalhado = traceback.format_exc()
        print(f"Erro ao atualizar dashboard home:\n{erro_detalhado}")
        try:
            # Se voltar a falhar, agora vai saltar um aviso no ecrã para sabermos o motivo exato!
            ModernMessageBox.showerror("Erro no Resumo", f"Ocorreu um erro no Resumo do Mês:\n\n{e}")
        except:
            pass
            
        def verifica_circularidade(dest):
            d = str(dest).lower()
            # Trava: se for efluente, aterro ou incineração, barra na hora (não é circular)
            if 'efluente' in d or 'aterro' in d or 'incineração' in d:
                return False
            # Se não bateu na trava, verifica se tem as palavras verdes
            return any(pv in d for pv in palavras_verdes)

        mask_verde = agrupado['Destinacao'].apply(verifica_circularidade)
        peso_circular = agrupado[mask_verde]['Peso_KG_Real'].sum()
        taxa_circ = (peso_circular / peso_total) * 100 if peso_total > 0 else 0.0

        peso_str = f"{peso_total:,.2f} kg".replace(",", "X").replace(".", ",").replace("X", ".")
        custo_str = f"R$ {custo_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        lbl_dash_peso.config(text=peso_str)
        lbl_dash_custo.config(text=custo_str)
        lbl_dash_rec.config(text=f"{taxa_rec:.1f}%")
        
    except Exception as e:
        print(f"Erro ao atualizar dashboard: {e}")

def on_month_select_esg(event=None):
    """
    Função chamada ao selecionar uma data na aba ESG.
    Apenas verifica se há metragem no banco e avisa no status.
    """
    try:
        # Pega o mês selecionado no calendário da aba ESG
        data_sel = esg_data_inicio.get_date()
        mes_ano_str = data_sel.strftime("%Y-%m")
        
        # Busca o valor no banco de dados
        valor = db.get_metragem(mes_ano_str)
        
        if valor > 0:
            set_status(f"Metragem para {mes_ano_str} encontrada: {valor:,.2f} m²")
        else:
            set_status(f"Aviso: Metragem para {mes_ano_str} não encontrada no sistema.")
            
    except Exception as e:
        # Se der erro (ex: calendário ainda não carregado), ignora silenciosamente
        pass

def salvar_metragem_esg():
    """Salva o valor do campo metragem no DB para o mês de início (Aba ESG)."""
    try:
        data_selecionada = esg_data_inicio.get_date() # Usa data de início
        mes_ano_str = data_selecionada.strftime("%Y-%m")
        
        metragem_val = money_pt(esg_metragem_var.get()) # Usa a nova var
        
        if db.add_or_update_metragem(mes_ano_str, float(metragem_val)):
            set_status(f"Metragem {metragem_val} salva para {mes_ano_str}.")
        else:
            ModernMessageBox.showerror("Erro DB", f"Não foi possível salvar a metragem para {mes_ano_str}.")
            
    except Exception as e:
        ModernMessageBox.showerror("Erro", f"Erro ao salvar metragem: {e}")

def atualizar_totais(df):
    """
    Calcula totais com 4 categorias.
    CORREÇÃO: Vendas nunca são classificadas como Transporte/Análise.
    """
    if 'tot_txt' in globals():
        tot_txt.config(state="normal"); tot_txt.delete("1.0", "end")
        
    if df.empty:
        if 'tot_txt' in globals():
            tot_txt.insert("end", "Nenhum registro no período.\n"); tot_txt.config(state="disabled")
        if 'kpi_vendas_var' in globals():
            kpi_vendas_var.set("R$ 0,00"); kpi_custos_var.set("R$ 0,00"); kpi_lucro_var.set("R$ 0,00"); kpi_peso_var.set("0 kg")
        return None

    dados_resumo = {
        'Sólido':     {'Custo': 0.0, 'Venda': 0.0, 'Peso': 0.0},
        'Líquido':    {'Custo': 0.0, 'Venda': 0.0, 'Peso': 0.0},
        'Transporte': {'Custo': 0.0, 'Venda': 0.0, 'Peso': 0.0},
        'Análise':    {'Custo': 0.0, 'Venda': 0.0, 'Peso': 0.0}
    }
    
    kw_analise = ['análise', 'analise', 'laudo', 'laboratório', 'laboratorio', '[análise]', '[analise]']
    kw_transporte = ['frete', 'transporte', 'logística', 'logistica', '[frete]', '[transporte]']

    for _, row in df.iterrows():
        dest = str(row.get('Destinacao', '')).lower().strip()
        res = str(row.get('Residuo', '')).lower().strip()
        estado_db = str(row.get('Estado', '')).lower().strip()
        tipo = str(row.get('Tipo', 'Venda'))
        
        v_total = to_float_safe(row.get('ValorTotal', 0))
        v_transp = to_float_safe(row.get('Transporte', 0))
        peso_row = to_float_safe(row.get('Peso', 0))
        if str(row.get('Modo', '')).lower() == 'unidade':
             peso_row = to_float_safe(row.get('PesoEmKg', 0))

        # --- A. CLASSIFICAÇÃO BLINDADA ---
        categoria = 'Sólido'
        
        if 'líquido' in estado_db or 'liquido' in estado_db:
            categoria = 'Líquido'

        # Se é Venda, força material (ignora keywords de serviço)
        if tipo == 'Venda':
            pass 
        else:
            # Se é Custo, checa serviços
            if any(k in res or k in dest for k in kw_analise):
                categoria = 'Análise'
            elif any(k in res for k in kw_transporte):
                categoria = 'Transporte'
        # ---------------------------------
        
        # B. Distribuição
        if v_transp > 0:
            dados_resumo['Transporte']['Custo'] += v_transp
            
        val_material = v_total - v_transp
        
        if abs(val_material) > 0.001:
            if categoria in ['Análise', 'Transporte']:
                dados_resumo[categoria]['Custo'] += val_material
            else:
                dados_resumo[categoria]['Peso'] += peso_row
                if tipo == 'Venda':
                    dados_resumo[categoria]['Venda'] += v_total
                elif tipo == 'Custo':
                    dados_resumo[categoria]['Custo'] += val_material

    # Consolidação
    total_venda = sum(d['Venda'] for d in dados_resumo.values())
    total_custo = sum(d['Custo'] for d in dados_resumo.values())
    total_peso = sum(d['Peso'] for d in dados_resumo.values())
    lucro = total_venda - total_custo

    # UI Update
    if 'kpi_vendas_var' in globals():
        kpi_vendas_var.set(fmt_moeda(total_venda))
        kpi_custos_var.set(fmt_moeda(total_custo))
        kpi_lucro_var.set(fmt_moeda(lucro))
        kpi_peso_var.set(fmt_kg(total_peso))

    if 'tot_txt' in globals():
        linhas = [
            f"RESUMO FINANCEIRO:",
            f"Lucro Líquido: {fmt_moeda(lucro)}",
            f"",
            f"1. Sólidos (Venda): {fmt_moeda(dados_resumo['Sólido']['Venda'])}",
            f"   Sólidos (Custo): {fmt_moeda(dados_resumo['Sólido']['Custo'])}",
            f"2. Líquidos (Venda): {fmt_moeda(dados_resumo['Líquido']['Venda'])}",
            f"   Líquidos (Custo): {fmt_moeda(dados_resumo['Líquido']['Custo'])}",
            f"3. Custos Operacionais:",
            f"   Transporte: {fmt_moeda(dados_resumo['Transporte']['Custo'])}",
            f"   Análises:   {fmt_moeda(dados_resumo['Análise']['Custo'])}"
        ]
        tot_txt.config(state="normal"); tot_txt.delete("1.0", "end")
        tot_txt.insert("end", "\n".join(linhas)); tot_txt.config(state="disabled")

    # Export DataFrame
    export_list = []
    cats = ['Sólido', 'Líquido', 'Transporte', 'Análise']
    labels = ['Sólidos', 'Líquidos', 'Transporte (Fretes)', 'Análises (Laboratório)']
    
    for i, cat in enumerate(cats):
        export_list.append({
            "Categoria": labels[i],
            "Crédito (Venda)": dados_resumo[cat]['Venda'],
            "Débito (Custo)": dados_resumo[cat]['Custo'],
            "Peso (kg)": dados_resumo[cat]['Peso']
        })
        
    export_list.append({
        "Categoria": "TOTAL GERAL",
        "Crédito (Venda)": total_venda,
        "Débito (Custo)": total_custo,
        "Peso (kg)": total_peso
    })
    
    return pd.DataFrame(export_list)


def atualizar_grafico_barras(df, ax, canvas):
    """Gera o gráfico de Vendas x Custos (Versão Robusta)."""
    ax.clear()
    
    # Cores do tema atual
    bg_color = style.colors.bg
    fg_color = style.colors.fg
    grid_color = style.colors.secondary
    
    ax.set_facecolor(bg_color)
    # Se 'fig_bar' for global, tentamos acessar, senão ignoramos
    if 'fig_bar' in globals():
        fig_bar.set_facecolor(bg_color)

    # Validação básica
    if df.empty or 'Data' not in df.columns or df['Data'].isnull().all():
        ax.set_title("Sem dados no período", color=fg_color, fontsize=10)
        canvas.draw()
        return

    try:
        # 1. Preparação dos Dados
        d = df.copy()
        d['Data'] = pd.to_datetime(d['Data'], errors='coerce')
        d = d.dropna(subset=['Data']) # Remove datas inválidas
        
        # Cria coluna de Período para agrupar
        d["Periodo"] = d["Data"].dt.to_period("M")
        
        # Garante que ValorTotal seja numérico
        d["ValorTotal"] = d["ValorTotal"].apply(to_float_safe)
        
        # Pivota: Linhas=Periodo, Colunas=Tipo, Valores=Soma
        piv = d.pivot_table(index="Periodo", columns="Tipo", values="ValorTotal", aggfunc="sum", fill_value=0)
        
        # Garante que existam as colunas Venda e Custo (mesmo que zeradas)
        if "Venda" not in piv.columns: piv["Venda"] = 0.0
        if "Custo" not in piv.columns: piv["Custo"] = 0.0
        
        # Reordena para ficar bonito
        piv = piv[["Venda", "Custo"]]
        
        # --- CORREÇÃO DA FORMATAÇÃO DE DATA (Onde provávelmente estava o erro) ---
        # Em vez de usar listas externas complexas, vamos usar formatação nativa simples
        # Ex: "11/2025" -> "nov/25"
        def formatar_eixo_x(periodo):
            try:
                # Tenta usar o mês abreviado em português se disponível, senão usa número
                ts = periodo.to_timestamp()
                try:
                    mes_str = PT_ABREV_LIST[ts.month - 1] # Tenta usar a lista global
                except:
                    mes_str = str(ts.month) # Fallback para número
                
                return f"{mes_str}/{ts.year}"
            except:
                return str(periodo)

        piv.index = piv.index.map(formatar_eixo_x)
        piv.index.name = "" # Remove o label "Periodo" do eixo X para limpar
        # -----------------------------------------------------------------------

        # 2. Plotagem
        colors = [style.colors.info, style.colors.danger] # Azul para Venda, Vermelho para Custo
        piv.plot(kind="bar", ax=ax, color=colors, rot=0) # rot=0 deixa o texto reto se couber

        # 3. Estilização
        ax.set_title("Financeiro (Vendas x Custos)", color=fg_color, fontsize=10, weight='bold')
        ax.legend(title="", fontsize=8, facecolor=bg_color, labelcolor=fg_color)
        
        # Formata Eixo Y (Dinheiro)
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, p: f'R$ {x:,.0f}'.replace(',', '.')))
        
        # Grade e Cores
        ax.yaxis.grid(True, linestyle=':', which='major', color=grid_color, alpha=0.4)
        ax.set_axisbelow(True)
        
        ax.tick_params(axis='x', colors=fg_color, labelsize=8, rotation=45) # Rotaciona 45º para caber datas
        ax.tick_params(axis='y', colors=fg_color, labelsize=8)
        
        # Remove bordas feias
        for spine in ['top', 'right']: 
            ax.spines[spine].set_visible(False)
        for spine in ['left', 'bottom']: 
            ax.spines[spine].set_color(grid_color)
            ax.spines[spine].set_linewidth(0.5)

        # Ajuste de Layout
        if 'fig_bar' in globals():
            fig_bar.tight_layout(pad=1.5)
            
        canvas.draw()

    except Exception as e:
        # SE DER ERRO DE NOVO, ELE VAI DIZER O MOTIVO NO TÍTULO
        print(f"Erro detalhado no gráfico de barras: {e}")
        ax.set_title(f"Erro: {str(e)[:40]}...", color="red", fontsize=8)
        canvas.draw()
        
def atualizar_grafico_pie_custo(df, ax, canvas):
    """Gráfico de Rosca (Donut) - Legenda Limpa (Sem prefixo [ANÁLISE])."""
    ax.clear()
    bg_color = style.colors.bg
    fg_color = style.colors.fg
    
    ax.set_facecolor(bg_color)
    if 'fig_pie_custo' in globals():
        fig_pie_custo.set_facecolor(bg_color)

    # Validação
    if df.empty or 'ValorTotal' not in df.columns or 'Residuo' not in df.columns:
        ax.text(0.5, 0.5, "Sem dados", ha='center', va='center', color=fg_color)
        canvas.draw(); return

    try:
        # Dados
        custos = df[df['Tipo'] == 'Custo'].copy()
        if custos.empty: 
            ax.text(0.5, 0.5, "R$ 0,00", ha='center', va='center', color=fg_color)
            canvas.draw(); return
            
        custos['ValorTotal'] = custos['ValorTotal'].apply(to_float_safe)
        total_val = custos['ValorTotal'].sum()
        
        # Top 5
        top_custos = custos.groupby('Residuo')['ValorTotal'].sum().nlargest(5).sort_values(ascending=False)
        top_custos = top_custos[top_custos > 0]
        
        if top_custos.empty: 
            ax.text(0.5, 0.5, "R$ 0,00", ha='center', va='center', color=fg_color)
            canvas.draw(); return
            
        soma_outros = total_val - top_custos.sum()
        if soma_outros > 0.01: top_custos['Outros'] = soma_outros

        # Paleta
        colors = ['#3498db', '#e74c3c', '#f1c40f', '#2ecc71', '#9b59b6', '#95a5a6']
        
        # Plotagem
        wedges, texts = ax.pie(
            top_custos, 
            startangle=90, 
            colors=colors[:len(top_custos)],
            wedgeprops={'width': 0.25, 'edgecolor': bg_color, 'linewidth': 3}
        )

        # Texto Central
        ax.text(0, 0.15, "Total Custos", ha='center', va='center', fontsize=8, color=fg_color, alpha=0.7)
        ax.text(0, -0.05, fmt_moeda(total_val), ha='center', va='center', fontsize=10, fontweight='bold', color=fg_color)
        
        ax.set_title("Top 5 Custos", color=fg_color, fontsize=10, weight='bold')

        # --- LEGENDA LIMPA ---
        legend_labels = []
        for nome, valor in top_custos.items():
            pct = (valor / total_val) * 100
            
            # LIMPEZA DO NOME (Remove o prefixo indesejado)
            nome_limpo = str(nome).replace("[ANÁLISE] ", "").replace("[ANÁLISE]", "")
            nome_limpo = nome_limpo.replace("[TRANSPORTE] ", "").replace("[TRANSPORTE]", "Transporte")
            
            # Encurta se ainda estiver muito longo
            nome_curto = (nome_limpo[:15] + '..') if len(nome_limpo) > 15 else nome_limpo
            
            label = f"{nome_curto} | {pct:.1f}% ({fmt_moeda(valor)})"
            legend_labels.append(label)

        # Posiciona à direita
        ax.legend(wedges, legend_labels, 
                  loc="center left", 
                  bbox_to_anchor=(1.0, 0.5), 
                  ncol=1, 
                  fontsize=8, 
                  frameon=False, 
                  labelcolor=fg_color)

        # Ajuste de margem
        if 'fig_pie_custo' in globals():
            fig_pie_custo.subplots_adjust(left=0.0, bottom=0.1, right=0.55, top=0.9)
            
        canvas.draw()
        
    except Exception as e: 
        print(f"Erro pie custo: {e}")
        ax.text(0.5, 0.5, "Erro", ha='center', color='red')
        canvas.draw()

def atualizar_grafico_pie_peso(df, ax, canvas):
    """Gráfico de Rosca (Donut) - Volumes com Legenda na Direita."""
    ax.clear()
    bg_color = style.colors.bg
    fg_color = style.colors.fg
    
    ax.set_facecolor(bg_color)
    if 'fig_pie_peso' in globals():
        fig_pie_peso.set_facecolor(bg_color)

    if df.empty or 'Peso' not in df.columns:
        ax.text(0.5, 0.5, "Sem dados", ha='center', va='center', color=fg_color)
        canvas.draw(); return

    try:
        # Dados
        df_peso = df.copy()
        col_peso = 'PesoEmKg' if 'PesoEmKg' in df_peso.columns else 'Peso'
        df_peso['Peso_Calc'] = df_peso[col_peso].apply(to_float_safe)
        total_val = df_peso['Peso_Calc'].sum()
        
        top_peso = df_peso.groupby('Parceiro')['Peso_Calc'].sum().nlargest(5).sort_values(ascending=False)
        top_peso = top_peso[top_peso > 0]
        
        if top_peso.empty: 
            ax.text(0.5, 0.5, "0 kg", ha='center', va='center', color=fg_color)
            canvas.draw(); return
            
        soma_outros = total_val - top_peso.sum()
        if soma_outros > 0.01: top_peso['Outros'] = soma_outros

        # Cores
        colors = ['#1abc9c', '#3498db', '#9b59b6', '#34495e', '#16a085', '#7f8c8d']

        # Plotagem
        wedges, texts = ax.pie(
            top_peso, 
            startangle=90, 
            colors=colors[:len(top_peso)],
            wedgeprops={'width': 0.25, 'edgecolor': bg_color, 'linewidth': 3}
        )

        # Texto Central
        ax.text(0, 0.15, "Peso Total", ha='center', va='center', fontsize=8, color=fg_color, alpha=0.7)
        ax.text(0, -0.05, fmt_kg(total_val), ha='center', va='center', fontsize=10, fontweight='bold', color=fg_color)
        
        ax.set_title("Top 5 Volumes", color=fg_color, fontsize=10, weight='bold')

        # Legenda
        legend_labels = []
        for nome, valor in top_peso.items():
            pct = (valor / total_val) * 100
            nome_curto = (nome[:12] + '..') if len(nome) > 12 else nome
            label = f"{nome_curto} | {pct:.1f}% ({fmt_kg(valor)})"
            legend_labels.append(label)

        ax.legend(wedges, legend_labels, 
                  loc="center left", 
                  bbox_to_anchor=(1.0, 0.5), 
                  ncol=1, 
                  fontsize=8, 
                  frameon=False, 
                  labelcolor=fg_color)

        # Ajuste de margem para a legenda caber na direita
        if 'fig_pie_peso' in globals():
            fig_pie_peso.subplots_adjust(left=0.0, bottom=0.1, right=0.55, top=0.9)
            
        canvas.draw()
        
    except Exception as e: 
        print(f"Erro pie peso: {e}")
        ax.text(0.5, 0.5, "Erro", ha='center', color='red')
        canvas.draw()

def preencher_resumo(df):
    """Preenche a tabela de resumo mensal com cores dinâmicas e proteção contra erros."""
    for r in resumo.get_children(): 
        resumo.delete(r)
    
    try:
        # 1. Se não houver dados no período, para por aqui (sem dar erro)
        if df is None or df.empty: 
            return

        # 2. Chama a função de cálculos
        rdf_raw, rdf_fmt = calculos.resumo_mensal_df(df)
        
        if rdf_raw is None or rdf_raw.empty: 
            return

        expected_cols = resumo['columns']
        row_num = 0
        
        # Pega as colunas disponíveis dinamicamente
        raw_cols = [str(c) for c in rdf_raw.columns]
        
        # Procura a coluna de lucro independente de maiúsculas/minúsculas
        col_lucro = None
        for c in raw_cols:
            if 'lucro' in c.lower():
                col_lucro = c
                break

        # 3. Preenchimento linha por linha
        for idx in rdf_raw.index:
            row_fmt = rdf_fmt.loc[idx]
            values_tuple = []
            
            # Busca os valores de forma segura (se a coluna não existir, deixa em branco)
            for expected_col in expected_cols:
                if expected_col in row_fmt:
                    values_tuple.append(row_fmt[expected_col])
                else:
                    values_tuple.append("")
            
            # Pega o lucro com segurança para pintar a linha de verde ou vermelho
            lucro_val = 0
            if col_lucro is not None:
                try:
                    lucro_val = float(rdf_raw.loc[idx, col_lucro])
                except (ValueError, TypeError):
                    lucro_val = 0
            
            # Define as cores (zebra e lucro/prejuízo)
            tags = ["evenrow" if row_num % 2 == 0 else "oddrow"]
            if lucro_val < 0: tags.append("lucro_neg")
            elif lucro_val > 0: tags.append("lucro_pos")
            
            resumo.insert("", "end", iid=str(idx), values=tuple(values_tuple), tags=tuple(tags))
            row_num += 1
            
    except Exception as e: 
        # Agora, se der qualquer erro invisível, ele vai pular na sua tela!
        import traceback
        erro_detalhado = traceback.format_exc()
        print(f"Erro preencher resumo:\n{erro_detalhado}")
        try:
            ModernMessageBox.showerror("Erro Aba Resumo", f"Ocorreu um erro ao montar a tabela:\n\n{e}")
        except:
            pass

def mostrar_detalhes_resumo(event):
    """Exibe um popup com os itens que compõem a linha clicada no resumo."""
    sel = resumo.focus()
    if not sel: return
    
    try:
        # 1. Recupera os valores da linha clicada
        item = resumo.item(sel)
        vals = item['values']
        # Colunas: 0=Mês, 1=Estado, 2=Destinação ...
        mes_str, estado, destinacao = vals[0], vals[1], vals[2]
        
        # 2. Filtra o DataFrame Global para encontrar esses itens
        # Precisamos converter o "nov/25" de volta para filtrar datas
        df_detalhe = df_registros_global.copy()
        df_detalhe['Data'] = pd.to_datetime(df_detalhe['Data'], errors='coerce')
        
        # Filtra Estado e Destinação
        mask = (df_detalhe['Estado'] == estado) & (df_detalhe['Destinacao'] == destinacao)
        df_detalhe = df_detalhe[mask]
        
        # Filtra o Mês (Comparando strings formatadas é mais fácil aqui)
        # Função lambda para gerar "nov/25" a partir da data do registro
        try:
            df_detalhe['Mes_Fmt'] = df_detalhe['Data'].apply(
                lambda x: f"{PT_ABREV_LIST[x.month-1]}/{x.year%100:02d}" if pd.notna(x) else ""
            )
            df_detalhe = df_detalhe[df_detalhe['Mes_Fmt'] == mes_str]
        except Exception as e:
            print(f"Erro ao filtrar data detalhes: {e}"); return

        if df_detalhe.empty:
            ModernMessageBox.showinfo("Detalhes", "Nenhum registro individual encontrado para este agrupamento.")
            return

        # 3. Cria a Janela de Detalhes
        top = tb.Toplevel(app)
        top.title(f"Detalhes: {destinacao} ({mes_str})")
        top.geometry("700x400")
        
        tb.Label(top, text=f"Composição de: {estado} - {destinacao}", font=("Segoe UI", 12, "bold"), bootstyle="primary").pack(pady=10)
        
        # Tabela de Detalhes
        cols = ("Data", "Parceiro", "Resíduo", "Peso", "Valor Total")
        tree_det = ttk.Treeview(top, columns=cols, show="headings")
        
        tree_det.heading("Data", text="Data")
        tree_det.heading("Parceiro", text="Parceiro")
        tree_det.heading("Resíduo", text="Resíduo")
        tree_det.heading("Peso", text="Peso")
        tree_det.heading("Valor Total", text="Valor Total")
        
        tree_det.column("Data", width=80, anchor="center")
        tree_det.column("Parceiro", width=150)
        tree_det.column("Resíduo", width=150)
        tree_det.column("Peso", width=80, anchor="e")
        tree_det.column("Valor Total", width=100, anchor="e")
        
        tree_det.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Preenche
        total_peso = 0
        total_valor = 0
        
        for _, row in df_detalhe.iterrows():
            d_fmt = format_data_ptbr_abbrev([row['Data']])[0]
            
            # Calcula peso real (considerando unidade)
            peso_real = row['PesoEmKg'] if str(row.get('Modo')).lower() == 'unidade' else row['Peso']
            peso_real = to_float_safe(peso_real)
            valor_total = to_float_safe(row['ValorTotal'])
            
            total_peso += peso_real
            total_valor += valor_total
            
            tree_det.insert("", "end", values=(
                d_fmt,
                clean_str(row['Parceiro']),
                clean_str(row['Residuo']),
                fmt_kg(peso_real),
                fmt_moeda(valor_total)
            ))
            
        # Rodapé com totais
        lbl_resumo = tb.Label(top, text=f"Total Peso: {fmt_kg(total_peso)}  |  Total Financeiro: {fmt_moeda(total_valor)}", font=("Segoe UI", 10, "bold"), bootstyle="inverse-primary")
        lbl_resumo.pack(fill="x", padx=10, pady=10)
        
    except Exception as e:
        ModernMessageBox.showerror("Erro", f"Erro ao abrir detalhes: {e}")
        print(e)

def atualizar_grafico_lucro_residuo(df, ax, canvas):
    """Gráfico de Barras Divergentes - Nomes acompanham o lado vazio."""
    ax.clear()
    
    bg_color = style.colors.bg
    fg_color = style.colors.fg
    
    ax.set_facecolor(bg_color)
    if 'fig_lucro_res' in globals():
        fig_lucro_res.set_facecolor(bg_color)

    # Validação
    if df.empty or 'Data' not in df.columns or df['Data'].isnull().all():
        ax.text(0.5, 0.5, "Sem dados", ha='center', va='center', color=fg_color)
        canvas.draw(); return

    try:
        d = df.copy()
        num_cols = ["Peso", "ValorPorKg", "ValorFechado", "Transporte"]
        for col in num_cols: d[col] = d[col].apply(to_float_safe) if col in d.columns else 0.0
        
        d['ValorBase'] = d.apply(lambda r: (r['ValorPorKg'] * r['Peso'] if str(r.get('Modo','')).lower() in ('kg', 'ton', 'unidade') else r['ValorFechado']), axis=1)
        d["Tipo"] = d["Tipo"].astype("string").fillna("").str.capitalize()
        
        piv = d.pivot_table(index="Residuo", columns="Tipo", values="ValorBase", aggfunc="sum", fill_value=0)
        transp = d.groupby("Residuo")["Transporte"].sum()
        
        resumo = pd.concat([piv, transp], axis=1).fillna(0)
        resumo["Venda"] = resumo.get("Venda", 0.0); resumo["Custo"] = resumo.get("Custo", 0.0)
        resumo['Lucro'] = resumo['Venda'] - resumo['Custo'] - resumo['Transporte']
        
        resumo = resumo[resumo['Lucro'].abs() > 0.01].sort_values('Lucro', ascending=True)
        
        if len(resumo) > 10:
            top_bottom = pd.concat([resumo.head(5), resumo.tail(5)])
        else:
            top_bottom = resumo

        if top_bottom.empty: 
            ax.text(0.5, 0.5, "Sem Lucro/Prejuízo", ha='center', color=fg_color)
            canvas.draw(); return

        # Limpeza de nomes
        clean_index = []
        for nome in top_bottom.index:
            nome_limpo = str(nome).replace("[ANÁLISE] ", "").replace("[ANÁLISE]", "")
            nome_limpo = nome_limpo.replace("[TRANSPORTE] ", "Transporte ").replace("[TRANSPORTE]", "Transporte ")
            if len(nome_limpo) > 25: nome_limpo = nome_limpo[:22] + "..."
            clean_index.append(nome_limpo)
        top_bottom.index = clean_index

        # Cores
        colors = ['#2ecc71' if x >= 0 else '#e74c3c' for x in top_bottom['Lucro']]
        
        # Plotagem
        bars = ax.barh(top_bottom.index, top_bottom['Lucro'], color=colors, height=0.6)
        
        # Linha Zero Central
        ax.axvline(0, color=fg_color, linewidth=0.8, alpha=0.3)

        # --- LÓGICA DE POSICIONAMENTO (DIVERGENTE) ---
        max_val = top_bottom['Lucro'].abs().max()
        offset_value = max_val * 0.02 # Distância do valor numérico para a barra
        offset_name = max_val * 0.05  # Distância do nome para o eixo zero

        for i, bar in enumerate(bars):
            width = bar.get_width()
            label_y = bar.get_y() + bar.get_height() / 2
            nome_residuo = top_bottom.index[i]
            
            # CASO 1: LUCRO (VERDE) -> Barra vai pra Direita
            if width >= 0:
                # Nome fica na ESQUERDA do eixo zero
                ax.text(-offset_name, label_y, nome_residuo, 
                        va='center', ha='right', # Alinha à direita (encosta no eixo)
                        fontsize=8, color=fg_color)
                
                # Valor fica na PONTA DIREITA da barra
                ax.text(width + offset_value, label_y, fmt_moeda(width), 
                        va='center', ha='left', 
                        fontsize=8, color=fg_color, fontweight='bold')

            # CASO 2: PREJUÍZO (VERMELHO) -> Barra vai pra Esquerda
            else:
                # Nome fica na DIREITA do eixo zero (Lado vazio!)
                ax.text(offset_name, label_y, nome_residuo, 
                        va='center', ha='left', # Alinha à esquerda (encosta no eixo)
                        fontsize=8, color=fg_color)
                
                # Valor fica na PONTA ESQUERDA da barra
                ax.text(width - offset_value, label_y, fmt_moeda(width), 
                        va='center', ha='right', 
                        fontsize=8, color=fg_color, fontweight='bold')

        ax.set_title("Lucro/Prejuízo por Resíduo", color=fg_color, fontsize=10, weight='bold')
        
        # Remove TODOS os eixos e bordas padrão
        ax.set_xticks([]) 
        ax.set_yticks([]) # Remove os nomes automáticos do eixo Y (já colocamos manualmente)
        
        for spine in ax.spines.values():
            spine.set_visible(False)

        # --- AJUSTE DE MARGENS ---
        # Agora precisamos de espaço igual dos dois lados para caber os nomes
        if 'fig_lucro_res' in globals():
            fig_lucro_res.subplots_adjust(left=0.2, bottom=0.05, right=0.8, top=0.9)
            
        canvas.draw()
        
    except Exception as e: 
        print(f"Erro grafico lucro: {e}")
        ax.text(0.5, 0.5, "Erro", ha='center', color='red')
        canvas.draw()
        
def atualizar_grafico_evolucao(df_global, ax, canvas):
    """Gera um gráfico de linha com a evolução dos últimos 12 meses (Global)."""
    ax.clear()
    bg_color = style.colors.bg
    fg_color = style.colors.fg
    grid_color = style.colors.secondary
    
    ax.set_facecolor(bg_color)
    fig_evol.set_facecolor(bg_color)
    
    try:
        # 1. Define o período (Hoje menos 12 meses)
        hoje = datetime.now()
        data_inicio_12m = hoje - timedelta(days=394)
        
        # 2. Filtra o DataFrame GLOBAL (ignorando os filtros da tela, para ver a tendência real)
        d = df_global.copy()
        d = d.dropna(subset=['Data'])
        d = d[d['Data'] >= data_inicio_12m]
        
        if d.empty:
            ax.set_title("Sem dados nos últimos 12 meses", color=fg_color, fontsize=9)
            canvas.draw()
            return

        # 3. Calcula Peso Real
        d['Peso_Real'] = d.apply(lambda r: (r['PesoEmKg'] if str(r.get('Modo','')).lower() == 'unidade' else r['Peso']), axis=1)
        d['Peso_Real'] = d['Peso_Real'].apply(to_float_safe)
        
        # 4. Agrupa por Mês/Ano
        # Converte para período mensal para agrupar corretamente Jan/24, Fev/24...
        d['MesAno'] = d['Data'].dt.to_period('M')
        evolucao = d.groupby('MesAno')['Peso_Real'].sum()
        
        # Garante que todos os 12 meses apareçam, mesmo os zerados
        idx_periodo = pd.period_range(start=data_inicio_12m, end=hoje, freq='M')
        evolucao = evolucao.reindex(idx_periodo, fill_value=0)
        
        # Formata o índice para string (ex: "Jan/25")
        x_labels = [f"{PT_ABREV_LIST[p.month-1]}/{p.year%100:02d}" for p in evolucao.index]
        
        # 5. Plota a Linha
        # Marcador 'o' para bolinhas, linewidth 2 para destacar
        ax.plot(x_labels, evolucao.values, marker='o', linestyle='-', linewidth=2, color=style.colors.info)
        
        # Preenche a área abaixo da linha (efeito visual bonito)
        ax.fill_between(x_labels, evolucao.values, color=style.colors.info, alpha=0.1)

        # 6. Formatação
        ax.set_title("Evolução do Peso (kg)", color=fg_color, fontsize=10, weight='bold')
        
        # Formata eixo Y (kg)
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, p: f'{x:,.0f}'.replace(',', '.')))
        
        ax.grid(True, linestyle=':', which='major', color=grid_color, alpha=0.4)
        
        # Ajusta eixo X (Datas)
        ax.tick_params(axis='x', colors=fg_color, labelsize=7, rotation=45)
        ax.tick_params(axis='y', colors=fg_color, labelsize=7)
        
        # Remove bordas desnecessárias
        for spine in ['top', 'right']: ax.spines[spine].set_visible(False)
        for spine in ['left', 'bottom']: 
            ax.spines[spine].set_color(grid_color)
            ax.spines[spine].set_linewidth(0.5)
            
        # Adiciona rótulos de valor em cima dos pontos (opcional, ajuda a ler)
        for i, v in enumerate(evolucao.values):
            if v > 0: # Só mostra se tiver valor
                ax.text(i, v + (max(evolucao.values)*0.05), f"{v:.0f}", 
                        color=fg_color, ha='center', fontsize=6)

        fig_evol.tight_layout(pad=1)
        canvas_evol.draw()
        
    except Exception as e:
        print(f"Erro gráfico evolução: {e}")
        ax.set_title("Erro ao gerar gráfico", color=fg_color)
        canvas_evol.draw()

def atualizar_grafico_estado_financeiro(df, ax, canvas):
    """
    Gera gráfico com 4 categorias.
    CORREÇÃO: Definição de grid_color e lógica de Venda blindada.
    """
    ax.clear()
    
    # --- DEFINIÇÃO DE CORES (Onde estava o erro) ---
    bg_color = style.colors.bg
    fg_color = style.colors.fg
    grid_color = style.colors.secondary # <--- Adicionado
    
    ax.set_facecolor(bg_color)
    if 'fig_estado_fin' in globals():
        fig_estado_fin.set_facecolor(bg_color)

    if df.empty:
        ax.text(0.5, 0.5, "Sem dados", ha='center', va='center', color=fg_color)
        canvas.draw()
        return

    try:
        dados = {
            'Sólido':     {'Custo': 0.0, 'Venda': 0.0},
            'Líquido':    {'Custo': 0.0, 'Venda': 0.0},
            'Transporte': {'Custo': 0.0, 'Venda': 0.0},
            'Análise':    {'Custo': 0.0, 'Venda': 0.0}
        }
        
        kw_analise = ['análise', 'analise', 'laudo', 'laboratório', 'laboratorio', '[análise]', '[analise]']
        kw_transporte = ['frete', 'transporte', 'logística', 'logistica', '[frete]', '[transporte]']

        for _, row in df.iterrows():
            dest = str(row.get('Destinacao', '')).lower().strip()
            res = str(row.get('Residuo', '')).lower().strip()
            estado_db = str(row.get('Estado', '')).lower().strip()
            tipo = str(row.get('Tipo', 'Venda')) # Venda ou Custo
            
            v_total = to_float_safe(row.get('ValorTotal', 0))
            v_transp = to_float_safe(row.get('Transporte', 0))
            
            # --- A. LÓGICA DE CLASSIFICAÇÃO ---
            categoria = 'Sólido' # Default
            
            if 'líquido' in estado_db or 'liquido' in estado_db:
                categoria = 'Líquido'

            # REGRA DE OURO: Se for VENDA, ignoramos se tem nome de transporte/análise.
            if tipo == 'Venda':
                pass # Mantém como Sólido ou Líquido definido acima
            
            else:
                # Se for CUSTO, verificamos se é serviço
                if any(k in res or k in dest for k in kw_analise):
                    categoria = 'Análise'
                elif any(k in res for k in kw_transporte):
                    categoria = 'Transporte'
            # -------------------------------------------
            
            # B. Distribuição
            if v_transp > 0:
                dados['Transporte']['Custo'] += v_transp

            val_material = v_total - v_transp
            
            if abs(val_material) > 0.001:
                if categoria in ['Análise', 'Transporte']:
                    dados[categoria]['Custo'] += val_material
                else:
                    if tipo == 'Venda':
                        dados[categoria]['Venda'] += v_total # Venda Bruta
                    elif tipo == 'Custo':
                        dados[categoria]['Custo'] += val_material

        # Plotagem
        df_plot = pd.DataFrame(dados).T
        df_plot = df_plot[['Custo', 'Venda']]
        
        if df_plot.sum().sum() == 0:
             ax.text(0.5, 0.5, "Sem movimentação", ha='center', color=fg_color)
             canvas.draw(); return

        colors = [style.colors.danger, style.colors.success]
        df_plot.plot(kind='bar', ax=ax, color=colors, rot=0, width=0.8)

        ax.set_title("Custos vs Vendas por Categoria", color=fg_color, fontsize=10, weight='bold')
        ax.set_xlabel("")
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, p: f'{x/1000:.0f}k' if x >= 1000 else f'{x:.0f}'))
        ax.legend(title="", fontsize=8, facecolor=bg_color, labelcolor=fg_color)
        
        # Agora grid_color existe e não vai dar erro
        ax.grid(axis='y', linestyle=':', color=grid_color, alpha=0.4)
        
        ax.tick_params(colors=fg_color, labelsize=8)
        for spine in ['top', 'right']: ax.spines[spine].set_visible(False)
        for spine in ['left', 'bottom']: ax.spines[spine].set_color(grid_color)
        
        for container in ax.containers:
            labels = [fmt_moeda(v) if v > 0 else "" for v in container.datavalues]
            ax.bar_label(container, labels=labels, padding=2, fontsize=7, color=fg_color)

        if 'fig_estado_fin' in globals(): fig_estado_fin.tight_layout(pad=1)
        canvas.draw()

    except Exception as e:
        print(f"Erro gráfico estado: {e}")
        ax.set_title(f"Erro: {e}", color='red', fontsize=8)
        canvas.draw()
        
def run_geracao_calculation_thread(dt_inicio, dt_fim, residuo_selecionado, df_global):
    """Roda na thread para não travar a UI e captura qualquer falha matemática."""
    try:
        resultado_dict = calculos.calcular_relatorio_geracao_data(
            dt_inicio, dt_fim, residuo_selecionado, df_global
        )
        geracao_result_queue.put(resultado_dict)
    except Exception as e:
        import traceback
        erro_msg = f"Erro matemático no cálculo: {str(e)}\n{traceback.format_exc()}"
        geracao_result_queue.put({"erro": erro_msg})

def check_geracao_result_queue():
    """Verifica a fila e atualiza a Tabela, Cards e a Memória de Cálculo."""
    try:
        result_data = geracao_result_queue.get_nowait()
        
        # Limpa tabela antiga
        for r in ger_tbl.get_children(): ger_tbl.delete(r)

        # 1. Atualiza Log de Memória Visual
        if 'txt_memoria_geracao' in globals():
            txt_memoria_geracao.delete("1.0", tk.END)
            if "memoria" in result_data and result_data["memoria"]:
                txt_memoria_geracao.insert(tk.END, result_data["memoria"])
            else:
                txt_memoria_geracao.insert(tk.END, "Nenhum log gerado.")

        # 2. Tratamento de Erros Retornados do Cálculo
        if "erro" in result_data:
            ModernMessageBox.showwarning("Aviso de Cálculo", result_data["erro"])
            ger_kpi_total_var.set("0 kg")
            ger_kpi_media_var.set("0,00 kg/dia")
        else:
            # 3. Preenche Cards Superiores (Agora com formatação PT-BR correta)
            total_formatado = f"{result_data['total_geral']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            ger_kpi_total_var.set(f"{total_formatado} kg")
            
            media_formatada = f"{result_data['media_diaria']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            ger_kpi_media_var.set(f"{media_formatada} kg/dia")

            # 4. Preenche Linhas da Tabela
            # 4. Preenche Linhas da Tabela
            for row_num, linha in enumerate(result_data["linhas"]):
                real_str = f"{linha['Realizado']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if linha['Realizado'] > 0 else "-"
                prev_str = f"{linha['Previsao']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if linha['Previsao'] > 0 else "-"
                tot_str = f"{linha['Total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if linha['Total'] > 0 else "-"
                tag = "evenrow" if row_num % 2 == 0 else "oddrow"
                
                ger_tbl.insert("", "end", values=(
                    linha['Mes'].capitalize(), real_str, prev_str, tot_str
                ), tags=(tag,))
        
        btn_gerar_geracao.config(state="normal")
        set_status("Relatório de geração concluído.")
        
    except queue.Empty:
        app.after(100, check_geracao_result_queue)
    except Exception as e:
        ModernMessageBox.showerror("Erro Crítico UI", f"Erro na interface: {e}")
        btn_gerar_geracao.config(state="normal")
        set_status("Erro na interface.")

def start_geracao_calculation():
    """Prepara os dados e inicia o cálculo dinâmico por Grupo ou Item."""
    try:
        dt_inicio = obter_data_segura(ger_data_inicio)
        dt_fim = obter_data_segura(ger_data_fim)
    except: return

    selecao = clean_str(ger_res_var.get())
    if not selecao: return

    # Feedback visual
    for r in ger_tbl.get_children(): ger_tbl.delete(r)
    ger_kpi_total_var.set("Calculando...")
    ger_kpi_media_var.set("Calculando...")
    btn_gerar_geracao.config(state="disabled")

    df_copy = get_df_com_peso_real(df_registros_global.copy())
    
    # LÓGICA DINÂMICA: Descobre quais resíduos pertencem ao que foi selecionado
    if not df_banco.empty and 'Grupo' in df_banco.columns:
        # Se a seleção for um Grupo (ex: "Bombonas plásticas"), pega todos os itens dele
        residuos_alvo = df_banco[df_banco['Grupo'] == selecao]['Residuo'].tolist()
        # Se não encontrou nada como grupo, assume que é um item individual
        if not residuos_alvo: residuos_alvo = [selecao]
    else:
        residuos_alvo = [selecao]

    # Inicia a thread passando a LISTA de nomes
    calc_thread = threading.Thread(
        target=run_geracao_calculation_thread, 
        args=(dt_inicio, dt_fim, residuos_alvo, df_copy), 
        daemon=True 
    )
    calc_thread.start()
    app.after(100, check_geracao_result_queue)

def calcular_ecoeficiencia():
    """Cruza a geração rateada com a metragem do banco para calcular o indicador."""
    try:
        dt_inicio = obter_data_segura(eco_data_inicio)
        dt_fim = obter_data_segura(eco_data_fim)
    except: return

    selecao = clean_str(eco_res_var.get())
    if not selecao: 
        ModernMessageBox.showwarning("Aviso", "Selecione um resíduo ou grupo para analisar.")
        return

    # Limpa Tabela e Feedback
    for r in eco_tbl.get_children(): eco_tbl.delete(r)
    btn_gerar_eco.config(state="disabled")
    set_status("Calculando Ecoeficiência...")

    def thread_eco():
        try:
            df_copy = df_registros_global.copy()
            
            # Descobre quais resíduos analisar
            if not df_banco.empty and 'Grupo' in df_banco.columns:
                residuos_alvo = df_banco[df_banco['Grupo'] == selecao]['Residuo'].tolist()
                if not residuos_alvo: residuos_alvo = [selecao]
            else: residuos_alvo = [selecao]

            # 1. Pega os dados rateados usando o motor que você já criou!
            resultado_geracao = calculos.calcular_relatorio_geracao_data(dt_inicio, dt_fim, residuos_alvo, df_copy)
            linhas_geracao = resultado_geracao.get("linhas", [])

            # 2. Pega todas as metragens do banco
            dados_metragem = db.get_all_metragens() 
            dict_metragem = {item[0]: item[1] for item in dados_metragem}

            linhas_finais = []
            eixo_x, eixo_y = [], []
            mapa_meses = {"jan": "01", "fev": "02", "mar": "03", "abr": "04", "mai": "05", "jun": "06",
                          "jul": "07", "ago": "08", "set": "09", "out": "10", "nov": "11", "dez": "12"}

            # 3. Faz a junção das tabelas
            for linha in linhas_geracao:
                mes_str = linha['Mes'] # Ex: "jan/2025"
                partes = mes_str.split('/')
                ano = partes[1] if len(partes[1]) == 4 else f"20{partes[1]}"
                chave_db = f"{ano}-{mapa_meses.get(partes[0].lower(), '01')}"
                
                met_produzida = dict_metragem.get(chave_db, 0.0)
                geracao_kg = linha['Total']
                
                indicador = (geracao_kg / met_produzida) if met_produzida > 0 else 0.0
                
                linhas_finais.append((mes_str.capitalize(), geracao_kg, met_produzida, indicador))
                eixo_x.append(mes_str.capitalize())
                eixo_y.append(indicador)

            # 4. Envia para a tela
            app.after(0, lambda: atualizar_ui_eco(linhas_finais, eixo_x, eixo_y))

        except Exception as e:
            app.after(0, lambda: ModernMessageBox.showerror("Erro", f"Erro no cálculo: {e}"))
            app.after(0, lambda: btn_gerar_eco.config(state="normal"))

    threading.Thread(target=thread_eco, daemon=True).start()

def atualizar_ui_eco(linhas, x, y):
    """Atualiza a tabela e desenha o gráfico na UI principal."""
    for r in eco_tbl.get_children(): eco_tbl.delete(r)
    
    for i, (mes, ger, met, ind) in enumerate(linhas):
        tag = "evenrow" if i % 2 == 0 else "oddrow"
        ger_f = f"{ger:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        met_f = f"{met:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        # CORREÇÃO 1: Mudou de .4f para .2f na tabela
        ind_f = f"{ind:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        eco_tbl.insert("", "end", values=(mes, ger_f, met_f, ind_f), tags=(tag,))
    
    ax_eco.clear()
    bg_color, fg_color = style.colors.bg, style.colors.fg
    ax_eco.set_facecolor(bg_color); fig_eco.set_facecolor(bg_color)
    
    if sum(y) == 0:
        ax_eco.set_title("Nenhum dado ou metragem zerada", color=fg_color, fontsize=10)
    else:
        ax_eco.plot(x, y, marker='o', color=style.colors.success, linewidth=2)
        ax_eco.set_title("Evolução (kg/m²)", color=fg_color, fontsize=10, weight='bold')
        ax_eco.yaxis.grid(True, linestyle=':', color=style.colors.secondary, alpha=0.4)
        ax_eco.tick_params(axis='x', colors=fg_color, labelsize=8, rotation=30)
        ax_eco.tick_params(axis='y', colors=fg_color, labelsize=8)
        for spine in ['top', 'right']: ax_eco.spines[spine].set_visible(False)
        for spine in ['left', 'bottom']: ax_eco.spines[spine].set_color(style.colors.secondary)
        
        for i, v in enumerate(y):
            # CORREÇÃO 2: Mudou de .4f para .2f no texto do gráfico
            if v > 0: ax_eco.text(i, v + (max(y)*0.05), f"{v:.2f}", color=fg_color, ha='center', fontsize=7)

    canvas_eco.draw()
    btn_gerar_eco.config(state="normal")
    set_status("Cálculo de ecoeficiência concluído.")

def exportar_ecoeficiencia_excel():
    """Exporta a tabela de ecoeficiência visualizada para Excel."""
    itens = eco_tbl.get_children()
    if not itens:
        ModernMessageBox.showwarning("Aviso", "Não há dados calculados para exportar.")
        return

    residuo = eco_res_var.get()
    path = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        initialfile=f"Ecoeficiencia_{residuo}_{datetime.now():%d-%m-%Y}.xlsx",
        title="Salvar Ecoeficiência em Excel"
    )
    if not path: return

    # Extrai dados da Treeview
    colunas = ["Mês", "Geração (kg)", "Produção (m²)", "Indicador (kg/m²)"]
    dados_lista = []
    for item in itens:
        dados_lista.append(eco_tbl.item(item)['values'])

    df_export = pd.DataFrame(dados_lista, columns=colunas)
    
    try:
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            df_export.to_excel(writer, sheet_name="Ecoeficiência", index=False)
            # Ajuste de largura básico
            ws = writer.sheets['Ecoeficiência']
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = 20
        
        ModernMessageBox.showinfo("Sucesso", "Planilha Excel gerada com sucesso!")
    except Exception as e:
        ModernMessageBox.showerror("Erro", f"Falha ao salvar Excel: {e}")

def exportar_ecoeficiencia_pdf():
    """Gera um PDF profissional com a tabela e o gráfico de Ecoeficiência."""
    itens = eco_tbl.get_children()
    if not itens:
        ModernMessageBox.showwarning("Aviso", "Gere o indicador na tela primeiro.")
        return

    residuo = eco_res_var.get()
    path = filedialog.asksaveasfilename(
        defaultextension=".pdf",
        initialfile=f"Relatorio_Ecoeficiencia_{residuo}.pdf",
        title="Salvar Relatório em PDF"
    )
    if not path: return

    def gerar_pdf_eco_pesado():
        try:
            # 1. Captura o Gráfico atual como imagem
            buf = io.BytesIO()
            fig_eco.savefig(buf, format='png', dpi=300, bbox_inches='tight')
            buf.seek(0)
            img_grafico = RLImage(buf, width=18*cm, height=10*cm)

            # 2. Configura o documento
            doc = SimpleDocTemplate(path, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = []

            # Título
            elements.append(Paragraph(f"Relatório de Ecoeficiência - {residuo}", styles['Title']))
            elements.append(Paragraph(f"Período: {eco_data_inicio.get_date():%d/%m/%Y} a {eco_data_fim.get_date():%d/%m/%Y}", styles['Normal']))
            elements.append(Spacer(1, 1*cm))

            # Imagem do Gráfico
            elements.append(Paragraph("Evolução Mensal", styles['Heading2']))
            elements.append(img_grafico)
            elements.append(Spacer(1, 1*cm))

            # Tabela de Dados
            elements.append(Paragraph("Detalhamento dos Dados", styles['Heading2']))
            data_pdf = [["Mês", "Geração (kg)", "Produção (m²)", "Indicador"]]
            for item in itens:
                data_pdf.append(eco_tbl.item(item)['values'])

            table = Table(data_pdf, colWidths=[4*cm, 4*cm, 4*cm, 4*cm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey])
            ]))
            elements.append(table)

            doc.build(elements)
            app.after(0, lambda: ModernMessageBox.showinfo("Sucesso", "Relatório PDF gerado com sucesso!"))
        except Exception as e:
            app.after(0, lambda: ModernMessageBox.showerror("Erro PDF", f"Falha: {e}"))

    threading.Thread(target=gerar_pdf_eco_pesado, daemon=True).start()

def desenhar_grafico_rosca(df_agrupado):
    """Constrói o visual executivo da distribuição de resíduos com Cores Inteligentes."""
    ax_esg_rosca.clear()
    bg_color, fg_color = style.colors.bg, style.colors.fg
    ax_esg_rosca.set_facecolor(bg_color)
    fig_esg_rosca.set_facecolor(bg_color)

    if df_agrupado.empty:
        ax_esg_rosca.text(0.5, 0.5, "Sem dados no período", ha='center', va='center', color=fg_color)
        canvas_esg_rosca.draw()
        return

    labels = df_agrupado['Destinacao'].tolist()
    valores = df_agrupado['Peso_KG_Real'].tolist()
    total_peso = sum(valores)

    # --- NOVA LÓGICA DE CORES INTELIGENTES ---
    palavras_verdes = ['reciclagem', 'compostagem', 'reuso', 'coprocessamento', 'co-processamento', 'recuperação', 'logística reversa']
    cores_finais = []
    
    # Paleta para os "não verdes"
    paleta_neutra = ['#3498db', '#9b59b6', '#e67e22', '#f1c40f', '#e74c3c', '#95a5a6']
    idx_neutro = 0

    for dest in labels:
        d_lower = str(dest).lower()
        # Se for Efluente, Aterro ou Incineração, força a não ser verde
        if 'efluente' in d_lower or 'aterro' in d_lower or 'incineração' in d_lower:
            cores_finais.append(paleta_neutra[idx_neutro % len(paleta_neutra)])
            idx_neutro += 1
        # Se for ecológico, pinta de Verde
        elif any(pv in d_lower for pv in palavras_verdes):
            cores_finais.append('#2ecc71') # Verde fixo
        # Se não cair em nenhuma regra, pega cor neutra
        else:
            cores_finais.append(paleta_neutra[idx_neutro % len(paleta_neutra)])
            idx_neutro += 1

    def autopct_format(pct):
        return f'{pct:.1f}%' if pct > 3 else ''

    wedges, texts, autotexts = ax_esg_rosca.pie(
        valores, 
        autopct=autopct_format, 
        startangle=140,
        colors=cores_finais,
        textprops={'color': fg_color, 'fontsize': 10, 'weight': 'bold'},
        wedgeprops=dict(width=0.4, edgecolor=bg_color, linewidth=2),
        pctdistance=0.80 
    )

    ax_esg_rosca.set_title("Distribuição por Destinação Final", color=fg_color, weight='bold', pad=10)

    legend_labels = []
    for nome, valor in zip(labels, valores):
        pct = (valor / total_peso) * 100
        nome_curto = (nome[:25] + '..') if len(nome) > 25 else nome
        peso_fmt = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        legend_labels.append(f"{nome_curto} | {pct:.1f}% ({peso_fmt} kg)")

    ax_esg_rosca.legend(
        wedges, legend_labels, 
        title="Destinações",
        loc="center left", 
        bbox_to_anchor=(1.05, 0.5), 
        fontsize=9, 
        frameon=False, 
        labelcolor=fg_color
    )

    fig_esg_rosca.subplots_adjust(left=0.05, bottom=0.05, right=0.55, top=0.85)
    canvas_esg_rosca.draw()

def start_esg_calculation():
    """Calcula os dados ESG e atualiza os Cards e o Gráfico de Rosca."""
    try:
        dt_inicio = obter_data_segura(esg_data_inicio)
        dt_fim = obter_data_segura(esg_data_fim)
    except: 
        ModernMessageBox.showwarning("Aviso", "Verifique as datas inseridas.")
        return

    ax_esg_rosca.clear()
    canvas_esg_rosca.draw()
    btn_gerar_esg.config(state="disabled")
    set_status("Calculando Indicadores ESG...")

    def thread_esg():
        try:
            df = get_df_com_peso_real(df_registros_global.copy())
            df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
            
            df_filtrado = df[(df['Data'].dt.date >= dt_inicio) & (df['Data'].dt.date <= dt_fim)]
            df_filtrado = df_filtrado[~df_filtrado['Destinacao'].str.contains('Análise externa', case=False, na=False)]
            df_filtrado = df_filtrado[~df_filtrado['Destinacao'].isin(['N/A'])]

            peso_total = df_filtrado['Peso_KG_Real'].sum() if 'Peso_KG_Real' in df_filtrado.columns else 0.0
            
            if peso_total == 0:
                app.after(0, lambda: lbl_esg_geracao.config(text="0,00 kg"))
                app.after(0, lambda: lbl_esg_taxa.config(text="0,0%"))
                app.after(0, lambda: desenhar_grafico_rosca(pd.DataFrame()))
                app.after(0, lambda: btn_gerar_esg.config(state="normal"))
                return

            agrupado = df_filtrado.groupby('Destinacao')['Peso_KG_Real'].sum().reset_index()
            agrupado = agrupado[agrupado['Peso_KG_Real'] > 0]
            agrupado = agrupado.sort_values(by='Peso_KG_Real', ascending=False)
            
            # --- CORREÇÃO: ADICIONADO "COPROCESSAMENTO" SEM HÍFEN ---
            palavras_verdes = ['reciclagem', 'compostagem', 'reuso', 'co-processamento', 'coprocessamento', 'recuperação', 'logística reversa']
            
            def verifica_circularidade(dest):
                d = str(dest).lower()
                if 'efluente' in d or 'aterro' in d or 'incineração' in d:
                    return False
                return any(pv in d for pv in palavras_verdes)

            mask_verde = agrupado['Destinacao'].apply(verifica_circularidade)
            peso_circular = agrupado[mask_verde]['Peso_KG_Real'].sum()
            taxa_circ = (peso_circular / peso_total) * 100 if peso_total > 0 else 0.0

            peso_str = f"{peso_total:,.2f} kg".replace(",", "X").replace(".", ",").replace("X", ".")
            
            app.after(0, lambda: lbl_esg_geracao.config(text=peso_str))
            app.after(0, lambda: lbl_esg_taxa.config(text=f"{taxa_circ:.1f}%"))
            app.after(0, lambda: desenhar_grafico_rosca(agrupado))
            app.after(0, lambda: btn_gerar_esg.config(state="normal"))
            app.after(0, lambda: set_status("Indicadores ESG atualizados!"))

        except Exception as e:
            print(f"Erro no ESG: {e}")
            app.after(0, lambda: btn_gerar_esg.config(state="normal"))

    threading.Thread(target=thread_esg, daemon=True).start()

def calcular_balanca_comercial():
    """Separa Receitas de Custos e calcula o KPI R$/m²."""
    try:
        dt_inicio = obter_data_segura(fin_data_inicio)
        dt_fim = obter_data_segura(fin_data_fim)
        producao_m2 = float(fin_prod_var.get().replace('.', '').replace(',', '.'))
    except:
        ModernMessageBox.showwarning("Aviso", "Verifique as datas e a produção inserida.")
        return

    ax_fin.clear()
    canvas_fin.draw()
    btn_gerar_fin.config(state="disabled")

    def thread_fin():
        try:
            df = df_registros_global.copy()
            df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
            df = df[(df['Data'].dt.date >= dt_inicio) & (df['Data'].dt.date <= dt_fim)]

            if df.empty or 'ValorTotal' not in df.columns:
                app.after(0, lambda: btn_gerar_fin.config(state="normal"))
                return

            # ==============================================================
            # REGRA DE SEPARAÇÃO: O QUE GERA DINHEIRO?
            # Ajuste esta lista com as palavras que usa para identificar vendas
            palavras_receita = ['venda', 'sucata', 'venda de recicláveis', 'receita']
            
            def classificar_financeiro(dest):
                d = str(dest).lower()
                return any(pr in d for pr in palavras_receita)
            # ==============================================================

            df['Is_Receita'] = df['Destinacao'].apply(classificar_financeiro)

            total_receita = df[df['Is_Receita']]['ValorTotal'].sum()
            total_custo = df[~df['Is_Receita']]['ValorTotal'].sum()

            # Custo Ambiental Real = Tudo o que gastou MENOS o que recuperou vendendo
            saldo_custo_real = total_custo - total_receita
            kpi_m2 = saldo_custo_real / producao_m2 if producao_m2 > 0 else 0.0

            rec_str = f"R$ {total_receita:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            cus_str = f"R$ {total_custo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            kpi_str = f"R$ {kpi_m2:,.2f} / m²".replace(",", "X").replace(".", ",").replace("X", ".")

            app.after(0, lambda: lbl_fin_receita.config(text=rec_str))
            app.after(0, lambda: lbl_fin_custo.config(text=cus_str))
            app.after(0, lambda: lbl_fin_kpi.config(text=kpi_str))

            # Prepara os dados para o Gráfico Mensal
            df['Mes_Ano'] = df['Data'].dt.to_period('M')
            df_grafico = df.groupby(['Mes_Ano', 'Is_Receita'])['ValorTotal'].sum().unstack(fill_value=0).reset_index()

            if True not in df_grafico.columns: df_grafico[True] = 0.0
            if False not in df_grafico.columns: df_grafico[False] = 0.0

            df_grafico = df_grafico.sort_values('Mes_Ano')
            x_labels = [str(m) for m in df_grafico['Mes_Ano']]
            val_receitas = df_grafico[True].tolist()
            val_custos = df_grafico[False].tolist()

            app.after(0, lambda: desenhar_grafico_financeiro(x_labels, val_custos, val_receitas))

        except Exception as e:
            print(f"Erro Financeiro: {e}")
            app.after(0, lambda: btn_gerar_fin.config(state="normal"))

    import threading
    threading.Thread(target=thread_fin, daemon=True).start()

def desenhar_grafico_financeiro(x_labels, custos, receitas):
    """Desenha as barras de custos e receitas lado a lado."""
    ax_fin.clear()
    bg_color, fg_color = style.colors.bg, style.colors.fg
    ax_fin.set_facecolor(bg_color)
    fig_fin.set_facecolor(bg_color)

    x = np.arange(len(x_labels))
    width = 0.35

    ax_fin.bar(x - width/2, custos, width, label='Custos (Aterro/Efluentes)', color='#e74c3c')
    ax_fin.bar(x + width/2, receitas, width, label='Receitas (Venda Sucatas)', color='#2ecc71')

    ax_fin.set_title("Balança Comercial Mensal (R$)", color=fg_color, weight='bold')
    ax_fin.set_xticks(x)
    ax_fin.set_xticklabels(x_labels, rotation=45, ha='right', color=fg_color, fontsize=8)
    ax_fin.tick_params(axis='y', colors=fg_color, labelsize=8)

    ax_fin.yaxis.grid(True, linestyle=':', color=style.colors.secondary, alpha=0.4)
    for spine in ['top', 'right']: ax_fin.spines[spine].set_visible(False)
    for spine in ['left', 'bottom']: ax_fin.spines[spine].set_color(style.colors.secondary)

    ax_fin.legend(loc='upper left', frameon=False, labelcolor=fg_color)
    fig_fin.subplots_adjust(bottom=0.2)

    canvas_fin.draw()
    btn_gerar_fin.config(state="normal")

##def atualizar_grafico_cep():
##    """Gera o Gráfico de Controle Estatístico para um resíduo."""
##    
##    ax_cep.clear(); bg_color = style.colors.bg; fg_color = style.colors.fg; grid_color = style.colors.secondary; ax_cep.set_facecolor(bg_color); fig_cep.set_facecolor(bg_color)
##    
##    try:
##        dt_inicio = cep_data_inicio.get_date()
##        dt_fim = cep_data_fim.get_date()
##    except Exception as e: ModernMessageBox.showerror("Erro Data", f"Formato inválido: {e}"); return
##    if dt_inicio > dt_fim: ModernMessageBox.showwarning("Filtro Inválido", "Data início > Data fim."); return
##
##    residuo_selecionado = clean_str(cep_res_var.get())
##    if not residuo_selecionado:
##        ModernMessageBox.showwarning("Filtro Inválido", "Selecione um Resíduo para analisar.")
##        return
##
##    # 1. Filtra o DataFrame global
##    df_periodo = df_registros_global[
##        (df_registros_global['Data'].notna()) &
##        (df_registros_global['Data'] >= pd.to_datetime(dt_inicio)) &
##        (df_registros_global['Data'] <= pd.to_datetime(dt_fim)) &
##        (df_registros_global['Residuo'] == residuo_selecionado)
##    ].copy()
##    
##    if df_periodo.empty:
##        ax_cep.set_title(f"Sem dados para '{residuo_selecionado}' no período", color=fg_color, fontsize=10); canvas_cep.draw(); return
##
##    # 2. Usa a função auxiliar para obter o peso KG correto
##    df_analise = get_df_com_peso_real(df_periodo)
##    
##    # Filtra apenas os que têm peso > 0 (lançamentos reais)
##    df_analise = df_analise[df_analise['Peso_KG_Real'] > 0].sort_values(by='Data')
##    
##    n_pontos = len(df_analise)
##    if n_pontos < 2:
##        ax_cep.set_title(f"Dados insuficientes (N={n_pontos}) para cálculo CEP", color=fg_color, fontsize=10); canvas_cep.draw(); return
##
##    # 3. Calcula Estatísticas CEP
##    try:
##        media = df_analise['Peso_KG_Real'].mean()
##        desvio_padrao = df_analise['Peso_KG_Real'].std()
##        
##        # Define Limites de Controle (3-sigma)
##        lcs = media + (3 * desvio_padrao)
##        lci = media - (3 * desvio_padrao)
##        lci = max(0, lci) # Limite inferior não pode ser negativo
##        
##        # 4. Plota o Gráfico
##        ax_cep.plot(df_analise['Data'], df_analise['Peso_KG_Real'], marker='o', linestyle='-', label=f'Geração (kg) (N={n_pontos})', markersize=5)
##        
##        # Plota Linhas de Controle
##        ax_cep.axhline(media, color=style.colors.info, linestyle='--', label=f'Média ({media:.2f} kg)')
##        ax_cep.axhline(lcs, color=style.colors.danger, linestyle=':', label=f'LCS ({lcs:.2f} kg)')
##        ax_cep.axhline(lci, color=style.colors.danger, linestyle=':', label=f'LCI ({lci:.2f} kg)')
##
##        # Formatação
##        ax_cep.set_title(f"Gráfico de Controle (CEP) - {residuo_selecionado}", color=fg_color, fontsize=10, weight='bold')
##        ax_cep.set_ylabel("Peso (kg)", color=fg_color, fontsize=9)
##        ax_cep.set_xlabel("Data", color=fg_color, fontsize=9)
##        ax_cep.legend(fontsize=8)
##        
##        ax_cep.yaxis.grid(True, linestyle=':', which='major', color=grid_color, alpha=.4); ax_cep.set_axisbelow(True)
##        ax_cep.tick_params(axis='x', colors=fg_color, rotation=15, labelsize=8); ax_cep.tick_params(axis='y', colors=fg_color, labelsize=8)
##        
##        for spine in ['top', 'right']: ax_cep.spines[spine].set_visible(False)
##        for spine in ['left', 'bottom']: ax_cep.spines[spine].set_color(grid_color); ax_cep.spines[spine].set_linewidth(0.5)
##        
##        fig_cep.tight_layout(pad=1.2)
##        canvas_cep.draw()
##        
##    except Exception as e:
##        ax_cep.set_title(f"Erro ao calcular CEP: {e}", color=fg_color, fontsize=10); canvas_cep.draw()
##        print(f"Erro ao gerar gráfico CEP: {e}")



def atualizar_resumo_selecao(event=None):
    """Calcula e exibe a soma de Peso e Valor dos itens selecionados na tabela."""
    
    # Garante que a variável do label exista
    if 'resumo_selecao_var' not in globals():
        return

    selected_iids = tabela.selection()
    
    if not selected_iids:
        resumo_selecao_var.set("") # Limpa o label se nada estiver selecionado
        return
    
    total_peso = Decimal("0")
    total_valor = Decimal("0")
    
    for iid_str in selected_iids:
        try:
            record_id = int(iid_str)
            # Busca os dados brutos do DataFrame global
            row_data = df_registros_global.loc[record_id]
            
            # Soma o Valor Total (da coluna ValorTotal)
            total_valor += _dec(row_data.get("ValorTotal", 0.0))
            
            # Soma o Peso KG Real (usando a mesma lógica do seu relatório ESG)
            modo = clean_str(row_data.get('Modo', 'kg')).lower()
            if modo == 'unidade':
                # Modo 'unidade' armazena o KG real em 'PesoEmKg'
                total_peso += _dec(row_data.get('PesoEmKg', 0.0))
            else:
                # Modos 'kg', 'ton', e 'fechado' armazenam o KG em 'Peso'
                total_peso += _dec(row_data.get('Peso', 0.0))
                
        except (ValueError, KeyError, TypeError) as e:
            print(f"Erro ao somar seleção (ID: {iid_str}): {e}")
            continue # Pula este item se der erro
    
    # Formata a string de resumo
    s_peso = fmt_kg(total_peso)
    s_valor = fmt_moeda(total_valor)
    count = len(selected_iids)
    
    resumo_str = f"Seleção: {count} {'item' if count == 1 else 'itens'} | Total Peso: {s_peso} | Total Valor: {s_valor}"
    resumo_selecao_var.set(resumo_str)

# --- CRUD Principais ---
def clear_form(*_):
    global EDITING_ID; EDITING_ID = None

    if 'lbl_total_operacao' in globals():
        lbl_total_operacao.config(text="R$ 0,00", bootstyle="secondary")
        
    # Limpa apenas os campos de transação (que precisam ser inseridos a cada registro)
    entrada_valor_kg.delete(0, tk.END)
    entrada_valor_fechado.delete(0, tk.END)
    # --- MODIFICADO: Usa StringVars ---
    entrada_peso.delete(0, tk.END) # Limpa a entry (embora a var seja melhor)
    peso_var.set("") 
    peso_unitario_var.set("")
    peso_kg_var.set("") # Limpa o campo calculado
    # --- FIM ALTERAÇÃO ---
    entrada_transporte.delete(0, tk.END)
    entrada_pedido.delete(0, tk.END)

    # O Resíduo será limpo para forçar o usuário a re-selecionar (medida de segurança)
    res_var.set("") 
    
    # Reseta apenas o modo de cálculo (para usar os valores padrão do Resíduo)
    calc_mode_var.set("kg")

    btn_submit.configure(text="Adicionar", bootstyle=SUCCESS)
    btn_clear_form.configure(text="Limpar", bootstyle=PRIMARY)
    
    # Garante o estado correto dos campos e recarrega valores do resíduo (que estará vazio)
    app.after(10, toggle_campos_por_modo)
    app.after(10, toggle_pedido_por_tipo)
    # A chamada a atualizar_form_por_residuo não é mais estritamente necessária aqui
    # pois res_var.set("") aciona o trace que chama essa função.

    caminho_anexo_temp.set("")
    lbl_anexo_info.config(text="")

def clear_form_analise(*_):
    """Limpa o formulário e remove o ID do botão."""
    global EDITING_ID; EDITING_ID = None
    
    ana_parc_var.set("")
    ana_nome_var.set("")
    ana_valor_fechado.delete(0, tk.END)
    ana_pedido.delete(0, tk.END)
    
    # Restaura o botão e APAGA o ID guardado nele
    if 'btn_ana_add' in globals():
        btn_ana_add.configure(text="Adicionar análise (custo)", bootstyle=SUCCESS)
        # Remove o ID do botão para evitar confusão no próximo clique
        if hasattr(btn_ana_add, 'editing_id'):
            del btn_ana_add.editing_id

def salvar_arquivo_anexo(origem, id_registro=None):
    """Copia o anexo para a pasta do sistema e retorna o caminho relativo."""
    if not origem or not os.path.exists(origem): return ""
    
    # Cria pasta se não existir
    pasta_destino = "anexos_registros"
    if not os.path.exists(pasta_destino): os.makedirs(pasta_destino)
    
    try:
        nome_orig = os.path.basename(origem)
        # Cria um nome único: ID_DATA_NomeOriginal (Se ID for None, usa Timestamp)
        prefixo = f"ID{id_registro}" if id_registro else datetime.now().strftime("%Y%m%d%H%M%S")
        nome_final = f"{prefixo}_{nome_orig}"
        destino_final = os.path.join(pasta_destino, nome_final)
        
        shutil.copy2(origem, destino_final)
        return destino_final # Salva no banco ex: "anexos_registros/ID50_doc.pdf"
    except Exception as e:
        print(f"Erro ao salvar anexo: {e}")
        return ""
        
def submit_registro_event(_=None):
    global EDITING_ID
    
    # --- 1. COLETA DE DADOS BÁSICOS ---
    try:
        data_str = obter_data_segura(entrada_data).strftime("%Y-%m-%d")
    except Exception:
        ModernMessageBox.showerror("Erro", "Data inválida"); return

    parceiro = clean_str(parceiro_var.get())
    residuo = clean_str(res_var.get())
    tipo = clean_str(tipo_var.get())
    estado = clean_str(estado_var.get())
    destinacao = clean_str(destinacao_var.get())
    modo_atual = clean_str(calc_mode_var.get()).lower()
    
    pedido = clean_str(entrada_pedido.get()) if tipo.lower() == "custo" else ""
    vkg_input = money_pt(entrada_valor_kg.get())
    vfechado = money_pt(entrada_valor_fechado.get())
    peso_input = money_pt(entrada_peso.get())
    transp = money_pt(entrada_transporte.get())

    # --- 2. VALIDAÇÕES ---
    if not parceiro or not residuo: ModernMessageBox.showerror("Erro", "Preencha Parceiro e Resíduo."); return
    if not destinacao: ModernMessageBox.showerror("Erro", "Selecione Destinação."); return

    # Cálculo do Peso KG (para modo unidade)
    peso_kg_input = Decimal("0")
    if 'peso_kg_var' in globals():
        peso_kg_input = money_pt(peso_kg_var.get())
        if modo_atual == "unidade" and peso_kg_input == Decimal("0"):
            calcular_peso_kg_automatico()
            peso_kg_input = money_pt(peso_kg_var.get()) 

    # Lógica de valores (kg vs fechado vs unidade)
    vkg_a_salvar = Decimal("0"); valor_base = Decimal("0"); total = Decimal("0"); peso_a_salvar_quantidade = Decimal("0")
    peso_a_salvar_kg_opcional = Decimal("0") 
    
    if modo_atual == "kg": 
        if peso_input <= 0: ModernMessageBox.showerror("Erro", "Peso > 0."); return
        peso_a_salvar_quantidade = peso_input
        peso_a_salvar_kg_opcional = peso_input
        vkg_a_salvar = vkg_input
        valor_base = vkg_a_salvar * peso_a_salvar_quantidade
        total = valor_base + transp
        vfechado = Decimal("0")
    elif modo_atual == "unidade": 
        if peso_input <= 0: ModernMessageBox.showerror("Erro", "Quantidade > 0."); return
        peso_a_salvar_quantidade = peso_input
        peso_a_salvar_kg_opcional = peso_kg_input 
        vkg_a_salvar = vkg_input
        valor_base = vkg_a_salvar * peso_a_salvar_quantidade
        total = valor_base + transp
        vfechado = Decimal("0")
    elif modo_atual == "fechado":
        if vfechado <= 0: ModernMessageBox.showerror("Erro", "Valor fechado > 0."); return
        peso_a_salvar_quantidade = peso_input 
        valor_base = vfechado
        total = valor_base + transp
        vkg_a_salvar = Decimal("0")
        peso_a_salvar_kg_opcional = peso_kg_input
    else: 
        ModernMessageBox.showerror("Erro", f"Modo '{modo_atual}' inválido."); return

# =================================================================
    # 3. LÓGICA DE COMPLIANCE (BASEADA NO CHECKBOX MANUAL)
    # =================================================================
    
    # --- Regra NF ---
    if var_nf_manual.get() == 1: 
        # Se o usuário MARCOU o checkbox:
        nf_status = "Não" # Pendente
        
        # Se for edição, preserva o status atual (Sim/Não) se já existia
        if EDITING_ID is not None:
            try: 
                val_antigo = df_registros_global.loc[EDITING_ID, 'NFOk']
                if val_antigo and val_antigo not in ("N/A", "n/a"): 
                    nf_status = val_antigo
            except: pass
    else:
        # Se o usuário DESMARCOU:
        nf_status = "N/A"

    # --- Regra Certificado ---
    if var_cert_manual.get() == 1:
        cert_ok = "Não" # Pendente
        
        if EDITING_ID is not None:
            try: 
                val_antigo = df_registros_global.loc[EDITING_ID, 'CertificadoOK']
                if val_antigo and val_antigo not in ("N/A", "n/a"): 
                    cert_ok = val_antigo
            except: pass
    else:
        cert_ok = "N/A"

    # =================================================================
    # 4. CRIAÇÃO DA LISTA DE DADOS (Já com as variáveis calculadas)
    # =================================================================
    caminho_final = ""
    path_temp = caminho_anexo_temp.get()
    
    # Se tiver um anexo selecionado na tela
    if path_temp:
        # Se for edição, usamos o ID existente. Se for novo, usamos None (vai gerar timestamp)
        caminho_final = salvar_arquivo_anexo(path_temp, EDITING_ID)

    # Se for edição e o usuário NÃO selecionou novo anexo, precisamos MANTER o antigo
    if EDITING_ID is not None and not path_temp:
        try:
            # Pega o valor antigo do banco
            caminho_final = df_registros_global.loc[EDITING_ID, 'CaminhoAnexo']
        except:
            caminho_final = ""

    # LISTA COM 18 CAMPOS (Adicionado caminho_final no fim)
    data_full_para_db = [ 
        data_str, parceiro, residuo, estado, destinacao, tipo, modo_atual, 
        float(peso_a_salvar_quantidade), float(vkg_a_salvar), float(vfechado), 
        float(transp), float(total), pedido, 
        "",          # NumMTR (se você não usa o campo texto MTR, pode deixar vazio ou ligar a um entry)
        cert_ok,
        float(peso_a_salvar_kg_opcional),
        "Não",       # NFOk (Padrão, será atualizado abaixo se tiver manual)
        caminho_final # <--- CAMPO 18: O CAMINHO DO ARQUIVO
     ]   
    # =================================================================
    # 5. SALVAMENTO NO BANCO (TRY/EXCEPT CORRETO)
    # =================================================================
    try:
        foi_edicao = (EDITING_ID is not None)
        
        if foi_edicao: 
            if not db.update_registro(EDITING_ID, data_full_para_db):
                ModernMessageBox.showerror("Erro ao Salvar", "O registro NÃO foi atualizado.\n\n" + detalhe_erro_db("Erro no banco de dados."))
                return
            
            # GAMBIARRA SEGURA: Se o update_registro original não aceita NF (tem 16 campos e não 17),
            # fazemos um update extra só para garantir a NF.
            if hasattr(db, 'update_nf'):
                db.update_nf(EDITING_ID, nf_status)
                
            set_status("Registro atualizado.")
        else: 
            # Insere novo
            new_id = db.add_registro(data_full_para_db)
            if not new_id or new_id == -1:
                ModernMessageBox.showerror("Erro ao Salvar", "O registro NÃO foi salvo.\n\n" + detalhe_erro_db("Erro no banco de dados."))
                return
            
            # GAMBIARRA SEGURA: Atualiza a NF logo em seguida para o ID criado
            if new_id and new_id != -1 and hasattr(db, 'update_nf'):
                db.update_nf(new_id, nf_status)
                
            set_status("Registro adicionado.")
            
        clear_form()
        atualizar_views()
        
        if foi_edicao:
            nb.select(aba_regs)
            
    except Exception as e: 
        ModernMessageBox.showerror("Erro ao Salvar", f"Detalhes do erro: {e}")
        print(f"Erro submit: {e}")

def iniciar_edicao():
    global EDITING_ID
    # Usa selection() que nunca perde a memória ao clicar fora da tabela
    sel_list = tabela.selection()
    if not sel_list: 
        ModernMessageBox.showwarning("Aviso", "Selecione um registo na tabela para editar.")
        return
    
    record_id = int(sel_list[0])
    
    try:
        reg_series = df_registros_global.loc[record_id]
        EDITING_ID = record_id 
        
        residuo_val = clean_str(reg_series.get('Residuo',''))
        
        # === CASO 1: É UMA ANÁLISE ===
        if residuo_val.startswith("[ANÁLISE]"):
            launch_type_var.set("Análise") 
            data_dt = reg_series.get('Data', pd.NaT)
            if pd.notna(data_dt): ana_data.set_date(data_dt.date())
            ana_parc_var.set(reg_series.get('Parceiro',''))
            nome_real = residuo_val.replace("[ANÁLISE] ", "").strip()
            ana_nome_var.set(nome_real)
            v_fechado = reg_series.get('ValorFechado', 0.0)
            ana_valor_fechado.delete(0, tk.END)
            ana_valor_fechado.insert(0, f"{v_fechado:.2f}".replace(".", ","))
            ana_pedido.delete(0, tk.END)
            ana_pedido.insert(0, reg_series.get('PedidoCompra',''))
            
            if 'btn_ana_add' in globals():
                btn_ana_add.configure(text="Salvar Edição da Análise", bootstyle=WARNING)
                btn_ana_add.editing_id = record_id 
            nb.select(aba_cad_fundo)
            
        # === CASO 2: FRETE ===
        elif residuo_val.startswith("[FRETE]"):
            launch_type_var.set("Transporte")
            data_dt = reg_series.get('Data', pd.NaT)
            if pd.notna(data_dt): transp_data.set_date(data_dt.date())
            transp_parc_var.set(reg_series.get('Parceiro',''))
            transp_dest_var.set(reg_series.get('Destinacao',''))
            transp_estado_var.set(reg_series.get('Estado','Sólido'))
            nome_real = residuo_val.replace("[FRETE] ", "").strip()
            transp_res_var.set(nome_real)
            v_total = reg_series.get('ValorTotal', 0.0)
            transp_valor.delete(0, tk.END)
            transp_valor.insert(0, f"{v_total:.2f}".replace(".", ","))
            transp_pedido.delete(0, tk.END)
            transp_pedido.insert(0, reg_series.get('PedidoCompra',''))
            nb.select(aba_cad_fundo)

        # === CASO 3: RESÍDUO NORMAL ===
        else:
            launch_type_var.set("Resíduo")
            clear_form()
            EDITING_ID = record_id 
            data_dt = reg_series.get('Data', pd.NaT)
            if pd.notna(data_dt): entrada_data.set_date(data_dt.date())
            else: entrada_data.set_date(datetime.now().date())
            parceiro_var.set(reg_series.get('Parceiro',''))
            res_var.set(residuo_val)
            destinacao_var.set(reg_series.get('Destinacao',''))
            estado_var.set(reg_series.get('Estado','Sólido'))
            tipo_var.set(reg_series.get('Tipo','Venda'))
            modo = reg_series.get('Modo','kg')
            calc_mode_var.set(modo)
            val_nf = str(reg_series.get('NFOk', '')).upper()
            if val_nf in ['N/A', 'NA', 'DISPENSADO']: var_nf_manual.set(0)
            else: var_nf_manual.set(1) 
            val_cert = str(reg_series.get('CertificadoOK', '')).upper()
            if val_cert in ['N/A', 'NA', 'DISPENSADO']: var_cert_manual.set(0)
            else: var_cert_manual.set(1)
            entrada_pedido.delete(0, tk.END)
            entrada_pedido.insert(0, reg_series.get('PedidoCompra',''))
            peso_db_kg = reg_series.get('Peso', 0.0)
            vkg_db = reg_series.get('ValorPorKg', 0.0)
            vfechado_db = reg_series.get('ValorFechado', 0.0)
            transp = reg_series.get('Transporte', 0.0)
            app.after(200, lambda m=modo, vk=vkg_db, ps=peso_db_kg, vf=vfechado_db, tr=transp: preencher_valores_edicao(m, vk, ps, vf, tr))
            btn_submit.configure(text="Salvar Edição", bootstyle=SUCCESS)
            btn_clear_form.configure(text="Cancelar Edição", bootstyle=WARNING)
            nb.select(aba_cad_fundo)

    except KeyError: 
        ModernMessageBox.showerror("Erro", "ID não encontrado no banco de dados.")
        clear_form(); clear_form_analise()
    except Exception as e: 
        ModernMessageBox.showerror("Erro", f"Erro ao carregar: {e}")
        clear_form(); clear_form_analise()
        
def duplicar_registro():
    global EDITING_ID
    sel_list = tabela.selection()
    if not sel_list: 
        ModernMessageBox.showwarning("Aviso","Selecione um item para duplicar.")
        return
        
    record_id = int(sel_list[0])
    try:
        reg_series = df_registros_global.loc[record_id]
        data_dt = datetime.now().date()
        parceiro = reg_series.get('Parceiro','')
        residuo = reg_series.get('Residuo','')
        estado = reg_series.get('Estado','Sólido')
        destinacao = reg_series.get('Destinacao','')
        tipo = reg_series.get('Tipo','Venda')
        modo = reg_series.get('Modo','kg')
        peso_db_kg = 0.0 
        vkg_db = reg_series.get('ValorPorKg',0.0) 
        vfechado_db = reg_series.get('ValorFechado',0.0) 
        transp = 0.0 
        pedido = reg_series.get('PedidoCompra','') 
        
        clear_form() 
        entrada_data.set_date(data_dt)
        parceiro_var.set(parceiro); res_var.set(residuo); destinacao_var.set(destinacao)
        entrada_pedido.delete(0, tk.END); entrada_pedido.insert(0, pedido) 
        estado_var.set(estado); tipo_var.set(tipo); calc_mode_var.set(modo)
        app.after(50, lambda m=modo, vk=vkg_db, ps=peso_db_kg, vf=vfechado_db, tr=transp: preencher_valores_edicao(m, vk, ps, vf, tr))
        
        set_status("Registo duplicado. Insira peso e guarde.")
        nb.select(aba_cad_fundo) 
        
    except KeyError: 
        ModernMessageBox.showerror("Erro", "ID não encontrado.")
        clear_form()
    except Exception as e: 
        ModernMessageBox.showerror("Erro", f"Erro ao duplicar: {e}")
        clear_form()

def excluir_registros_selecionados():
    print(">>> O BOTÃO FOI CLICADO! <<<") # ADICIONE ESTA LINHA
    
    # Resto do seu código...
    selecao = tabela.selection()
    print(f">>> Itens selecionados: {selecao} <<<") # ADICIONE ESTA LINHA TAMBÉM
    selected_iids_str = tabela.selection() 
    if not selected_iids_str:
        ModernMessageBox.showwarning("Aviso", "Nenhum registo selecionado para excluir.")
        return
        
    try: record_ids = [int(iid) for iid in selected_iids_str]
    except ValueError: return

    count = len(record_ids)
    if not ModernMessageBox.askyesno("Confirmar Exclusão", f"Tem a certeza que deseja excluir {count} item(ns)?"): return

    set_status(f"A excluir {count} registos...")
    erros, sucessos = 0, 0

    for record_id in record_ids:
        try:
            if db.delete_registro(record_id): sucessos += 1
            else: erros += 1
        except Exception: erros += 1

    atualizar_views() 
    if erros > 0: ModernMessageBox.showwarning("Aviso", f"{sucessos} excluídos.\nFalha ao excluir {erros} itens.")
    else: ModernMessageBox.showinfo("Sucesso", f"{sucessos} registos excluídos permanentemente.")
    
        
def marcar_certificados_ok():
    selected_iids_str = tabela.selection()
    if not selected_iids_str:
        ModernMessageBox.showwarning("Aviso", "Selecione os itens na tabela primeiro.")
        return
    
    ids = [int(i) for i in selected_iids_str]
    count = len(ids)
    if not ModernMessageBox.askyesno("Confirmar", f"Marcar 'Certificado OK' = 'Sim' para {count} item(ns)?"): return
    
    sucessos = 0
    for rid in ids:
        try:
            # Usa a função direta do banco para alterar APENAS o campo do certificado
            resultado = db.update_certificado(rid, "Sim")
            if resultado is not False:
                sucessos += 1
        except Exception as e: 
            print(f"Erro ao atualizar certificado do ID {rid}: {e}")
            
    atualizar_views()
    if sucessos > 0: ModernMessageBox.showinfo("Sucesso", f"{sucessos} certificados marcados como OK com sucesso.")
    else: ModernMessageBox.showerror("Erro", "O banco de dados rejeitou a alteração.")

def marcar_nf_ok():
    selected_iids_str = tabela.selection()
    if not selected_iids_str:
        ModernMessageBox.showwarning("Aviso", "Selecione os itens na tabela primeiro.")
        return
    
    ids = [int(i) for i in selected_iids_str]
    count = len(ids)
    if not ModernMessageBox.askyesno("Confirmar", f"Marcar 'NF OK' = 'Sim' para {count} item(ns)?"): return
    
    sucessos = 0
    for rid in ids:
        try:
            # Usa a função direta do banco para alterar APENAS o campo da NF
            if hasattr(db, 'update_nf'):
                resultado = db.update_nf(rid, "Sim")
                if resultado is not False:
                    sucessos += 1
            else:
                print("Aviso: Função db.update_nf não encontrada no arquivo database.py")
        except Exception as e: 
            print(f"Erro ao atualizar NF do ID {rid}: {e}")
            
    atualizar_views()
    if sucessos > 0: ModernMessageBox.showinfo("Sucesso", f"{sucessos} Notas Fiscais marcadas como OK com sucesso.")
    else: ModernMessageBox.showerror("Erro", "O banco de dados rejeitou a alteração.")

def alterar_exigencias_lote():
    """Abre um pop-up com toggles idênticos ao cadastro para alterar Compliance em lote."""
    selecionados = tabela.selection()
    if not selecionados:
        ModernMessageBox.showwarning("Aviso", "Selecione pelo menos um registro na tabela.")
        return

    janela_lote = tb.Toplevel(app)
    janela_lote.title(f"Compliance em Lote ({len(selecionados)} itens)")
    janela_lote.geometry("350x200")
    janela_lote.resizable(False, False)
    janela_lote.transient(app); janela_lote.grab_set()

    tb.Label(janela_lote, text="Compliance:", font=("Segoe UI", 12, "bold"), bootstyle="secondary").pack(pady=(20, 10))

    frame_toggles = tb.Frame(janela_lote)
    frame_toggles.pack(pady=10)

    # Variáveis dos toggles (1 = Exige, 0 = N/A)
    var_nf = tk.IntVar(value=1)
    var_cert = tk.IntVar(value=1)

    chk_nf = tb.Checkbutton(frame_toggles, text="Exige NF", variable=var_nf, bootstyle="round-toggle")
    chk_nf.pack(side="left", padx=15)

    chk_cert = tb.Checkbutton(frame_toggles, text="Exige Certificado", variable=var_cert, bootstyle="round-toggle")
    chk_cert.pack(side="left", padx=15)

    def salvar():
        sucessos = 0
        for iid in selecionados:
            try:
                rid = int(iid)
                row = df_registros_global.loc[rid]

                # Lógica inteligente para preservar o "Sim" (se já entregou, não volta pra pendente)
                if var_cert.get() == 1:
                    val_atual = str(row.get('CertificadoOK', '')).lower()
                    cert_status = "Sim" if val_atual in ('sim', 'ok') else "Não"
                else:
                    cert_status = "N/A"
                    
                if var_nf.get() == 1:
                    val_atual = str(row.get('NFOk', '')).lower()
                    nf_status = "Sim" if val_atual in ('sim', 'ok') else "Não"
                else:
                    nf_status = "N/A"

                # Atualiza no banco de dados
                ok_cert = db.update_certificado(rid, cert_status)
                ok_nf = db.update_nf(rid, nf_status) if hasattr(db, 'update_nf') else True
                if ok_cert and ok_nf: sucessos += 1
            except Exception as e:
                db._registrar_erro(f"Erro ao atualizar exigência {rid}: {e}")

        janela_lote.destroy()
        atualizar_views()
        falhas = len(selecionados) - sucessos
        if falhas:
            ModernMessageBox.showwarning("Atenção", f"Regras aplicadas em {sucessos} registro(s).\n{falhas} registro(s) NÃO foram atualizados.\n\n" + detalhe_erro_db(""))
        else:
            ModernMessageBox.showinfo("Sucesso", f"Regras aplicadas em {sucessos} registro(s)!")

    frame_btns = tb.Frame(janela_lote)
    frame_btns.pack(pady=15)
    tb.Button(frame_btns, text="Cancelar", bootstyle="secondary", command=janela_lote.destroy).pack(side="left", padx=10)
    tb.Button(frame_btns, text="Aplicar", bootstyle="success", command=salvar).pack(side="left")

    janela_lote.update_idletasks()
    x = app.winfo_x() + (app.winfo_width() // 2) - (janela_lote.winfo_width() // 2)
    y = app.winfo_y() + (app.winfo_height() // 2) - (janela_lote.winfo_height() // 2)
    janela_lote.geometry(f"+{x}+{y}")
        
# --- Pendências ---
def preencher_pendencias():
    # Limpa a tabela visual
    for r in pend_tbl.get_children(): pend_tbl.delete(r)
    
    # Busca os dados do banco
    df_pend = db.get_pending_certificates()
    
    if not df_pend.empty:
        # --- CORREÇÃO: FILTRAGEM DE "N/A" ---
        # Verifica se a coluna de status veio do banco
        if 'CertificadoOK' in df_pend.columns:
            # Cria uma máscara para manter apenas o que NÃO for N/A ou Dispensado
            # O símbolo '~' inverte a lógica (NÃO ESTÁ na lista)
            criterio_exclusao = ['n/a', 'na', 'dispensado', 'não aplicável', 'nao aplicavel']
            
            # Converte para string e minúsculo para comparar com segurança
            mask = ~df_pend['CertificadoOK'].astype(str).str.lower().isin(criterio_exclusao)
            
            # Aplica o filtro
            df_pend = df_pend[mask]
        # ------------------------------------

        # Se após filtrar não sobrou nada, para por aqui
        if df_pend.empty: return

        df_pend['Data_fmt'] = format_data_ptbr_abbrev(df_pend['Data'])
        
        row_num = 0
        for db_id, row in df_pend.iterrows():
            # Prepara os valores para exibição
            parceiro_txt = clean_str(row.get('Parceiro', ''))
            residuo_txt = clean_str(row.get('Residuo', ''))
            
            values = (row['Data_fmt'], parceiro_txt, residuo_txt)
            
            tag = "evenrow" if row_num % 2 == 0 else "oddrow"
            pend_tbl.insert("", "end", iid=str(db_id), values=values, tags=(tag,))
            row_num += 1

def marcar_pendencia_ok(event=None):
    sel = pend_tbl.focus();
    if not sel: return; record_id = None
    try: record_id = int(sel)
    except ValueError: ModernMessageBox.showerror("Erro", f"ID inválido: '{sel}'."); return
    if record_id is None: ModernMessageBox.showerror("Erro", "Não foi possível obter ID."); return
    try:
        reg_series = df_registros_global.loc[record_id]; data_dt = reg_series['Data']; parceiro = reg_series['Parceiro']; residuo = reg_series['Residuo']; data_str_fmt = data_dt.strftime("%d/%m/%y") if pd.notna(data_dt) else "Sem data"
        if ModernMessageBox.askyesno("Confirmar", f"Marcar 'Sim'?\n({data_str_fmt} | {parceiro} | {residuo})?"):
            try:
                db.update_certificado(record_id, "Sim")
                if record_id in df_registros_global.index: df_registros_global.loc[record_id, 'CertificadoOK'] = "Sim"
                else: print(f"Aviso: Reg {record_id} não no DF global.")
                df_filtrado = aplicar_filtros(obter_df_registros()); preencher_tabela(df_filtrado); preencher_pendencias()
                set_status("Certificado 'Sim'.")
            except Exception as e_update: ModernMessageBox.showerror("Erro", f"Não foi possível atualizar: {e_update}")
    except KeyError: ModernMessageBox.showwarning("Aviso", f"Reg ID {record_id} não nos dados principais.")
    except Exception as e: ModernMessageBox.showerror("Erro", f"Erro busca dados: {e}")

# --- Exportar ---
# --- Exportar ---

def executar_com_carregamento(funcao_pesada, titulo="Processando", mensagem="Aguarde..."):
    """Cria uma tela de carregamento segura que roda operações pesadas em background."""
    janela_load = tb.Toplevel(app)
    janela_load.title(titulo)
    janela_load.geometry("350x150")
    janela_load.resizable(False, False)
    janela_load.grab_set()
    
    # Centraliza o popup
    janela_load.update_idletasks()
    x = app.winfo_x() + (app.winfo_width() // 2) - 175
    y = app.winfo_y() + (app.winfo_height() // 2) - 75
    janela_load.geometry(f"+{x}+{y}")

    tb.Label(janela_load, text=mensagem, font=("Helvetica", 11, "bold")).pack(pady=(25, 10))
    progresso = tb.Progressbar(janela_load, mode='indeterminate', bootstyle="success")
    progresso.pack(fill="x", padx=30)
    progresso.start(15)

    def tarefa_no_fundo():
        try:
            funcao_pesada()
            # Pede à Thread Principal para fechar a janela com Sucesso
            app.after(0, finalizar, True, None)
        except Exception as e:
            app.after(0, finalizar, False, str(e))

    def finalizar(sucesso, erro):
        progresso.stop()
        janela_load.destroy()
        if not sucesso:
            ModernMessageBox.showerror("Erro", f"Ocorreu um problema na exportação:\n{erro}")

    # Inicia o trabalho em 2º plano
    threading.Thread(target=tarefa_no_fundo, daemon=True).start()

def exportar_para_excel():
    """Exporta os dados filtrados da Aba Registros usando a Tela de Carregamento."""
    base = obter_df_registros()
    df_filtrado = aplicar_filtros(base)
    
    if df_filtrado.empty: 
        ModernMessageBox.showinfo("Exportar", "Nenhum dado filtrado para exportar.")
        return
        
    default_filename = f"Relatorio_Residuos_{datetime.now():%Y-%m-%d}.xlsx"
    # A janela de Salvar Como deve sempre abrir na Thread principal
    path = filedialog.asksaveasfilename(
        defaultextension=".xlsx", 
        filetypes=[("Arquivo Excel", "*.xlsx")], 
        initialfile=default_filename, 
        title="Salvar Relatório Excel da Tabela"
    )
    
    if not path: 
        set_status("Exportação cancelada.")
        return

    # Prepara os dados visuais na Thread Principal (Seguro para o Tkinter)
    df_totais = atualizar_totais(df_filtrado) 
    df_resumo_raw, _ = calculos.resumo_mensal_df(df_filtrado)
    df_registros_export = df_filtrado.copy()
    
    if 'Data' in df_registros_export.columns:
        df_registros_export['Data'] = pd.to_datetime(df_registros_export['Data']).dt.strftime('%d/%m/%Y').fillna('')
        
    rename_map_export = {
        'Residuo': 'Resíduo', 'Destinacao': 'Destinação', 'ValorPorKg': 'Valor Unitário', 
        'ValorFechado': 'Valor Fechado', 'ValorTotal': 'Valor Total', 
        'PedidoCompra': 'Pedido de Compra', 'CertificadoOK': 'Certificado OK',
        'Peso': 'Peso (Input)', 'PesoEmKg': 'Peso (Calculado KG)'
    }
    df_registros_export.rename(columns=rename_map_export, inplace=True)

    # FUNÇÃO PESADA (Roda em segundo plano para não travar a tela)
    def salvar_excel_tabela_pesado():
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            # Aba 1
            if df_totais is not None and not df_totais.empty:
                df_totais.to_excel(writer, sheet_name="Resumo Financeiro", index=False)
                worksheet = writer.sheets['Resumo Financeiro']
                worksheet.column_dimensions['A'].width = 25
                worksheet.column_dimensions['B'].width = 18
                worksheet.column_dimensions['C'].width = 18
                worksheet.column_dimensions['D'].width = 15

            # Aba 2
            if not df_resumo_raw.empty: 
                df_resumo_raw.to_excel(writer, sheet_name="Agrupado Mensal", index=False)
                
            # Aba 3
            if not df_registros_export.empty: 
                df_registros_export.to_excel(writer, sheet_name="Base de Dados Completa", index=False)

        # Devolve o aviso de sucesso de volta na interface principal
        app.after(0, lambda: ModernMessageBox.showinfo("Sucesso", "Exportação concluída!\nVerifique o Excel gerado."))
        app.after(0, lambda: set_status(f"Relatório salvo em {path}"))

    # Inicia o tiro de partida da barra de progresso
    executar_com_carregamento(salvar_excel_tabela_pesado, titulo="Exportando Excel", mensagem="A gerar planilhas e agrupar dados...")

def exportar_dados_dashboard():
    """Exporta dados filtrados (Versão com Tela de Carregamento e Threads)."""
    try:
        dt_inicio = ana_data_inicio.get_date()
        dt_fim = ana_data_fim.get_date()
    except Exception as e:
        ModernMessageBox.showerror("Erro Data", f"Datas inválidas: {e}"); return

    df_dashboard = df_registros_global.copy()
    if 'Data' in df_dashboard.columns:
        df_dashboard['Data'] = pd.to_datetime(df_dashboard['Data'], errors='coerce')
        mask = (df_dashboard['Data'] >= pd.to_datetime(dt_inicio)) & (df_dashboard['Data'] <= pd.to_datetime(dt_fim))
        df_dashboard = df_dashboard.loc[mask]
        df_dashboard.sort_values(by='Data', ascending=True, inplace=True)
    
    if df_dashboard.empty:
        ModernMessageBox.showinfo("Exportar", f"Nenhum dado encontrado entre {dt_inicio:%d/%m/%y} e {dt_fim:%d/%m/%y}.")
        return

    # Pede o caminho PRIMEIRO (Obrigatório rodar na Main Thread)
    default_filename = f"Relatorio_Financeiro_{dt_inicio:%d-%m}-{dt_fim:%d-%m-%Y}.xlsx"
    path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Arquivo Excel", "*.xlsx")], initialfile=default_filename, title="Salvar Relatório Financeiro")
    if not path: return

    # Prepara os dados visuais na Thread Principal (Seguro para o Tkinter)
    df_totais = atualizar_totais(df_dashboard)
    df_detalhado = df_dashboard.copy()
    rename_map = {'Residuo': 'Resíduo', 'Destinacao': 'Destinação', 'ValorPorKg': 'Valor Unit.', 'ValorTotal': 'Valor Total', 'Peso': 'Peso (Kg)', 'PesoEmKg': 'Peso Calc (Kg)'}
    df_detalhado.rename(columns=rename_map, inplace=True)

    # FUNÇÃO PESADA (Isolada para não travar o ecrã)
    def salvar_excel_pesado():
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            if df_totais is not None:
                df_totais.to_excel(writer, sheet_name="Resumo Financeiro", index=False)
                ws = writer.sheets['Resumo Financeiro']
                fmt_moeda = 'R$ #,##0.00'
                fmt_peso = '#,##0.000'
                for col in ws.columns:
                    col_name = col[0].value
                    length = max(len(str(cell.value)) for cell in col)
                    ws.column_dimensions[col[0].column_letter].width = length + 4
                    for cell in col[1:]:
                        if col_name in ["Crédito (Venda)", "Débito (Custo)"]: cell.number_format = fmt_moeda
                        elif "Peso" in col_name: cell.number_format = fmt_peso

            cols_export = ['Data', 'Parceiro', 'Resíduo', 'Estado', 'Destinação', 'Tipo', 'Peso (Kg)', 'Valor Unit.', 'Valor Total', 'Transporte']
            cols_finais = [c for c in cols_export if c in df_detalhado.columns]
            
            df_detalhado[cols_finais].to_excel(writer, sheet_name="Itens do Período", index=False)
            ws2 = writer.sheets['Itens do Período']
            
            for col in ws2.columns:
                col_name = col[0].value
                length = max((len(str(cell.value)) for cell in col), default=10)
                if length > 50: length = 50
                ws2.column_dimensions[col[0].column_letter].width = length + 3
                for cell in col[1:]:
                    if col_name == "Data": cell.number_format = 'dd/mm/yyyy'
                    elif col_name in ["Valor Total", "Transporte", "Valor Unit."]: cell.number_format = 'R$ #,##0.00'
                    elif "Peso" in col_name: cell.number_format = '#,##0.000'
        
        # Mensagem final executada de forma segura na Main Thread
        app.after(0, lambda: ModernMessageBox.showinfo("Sucesso", f"Relatório exportado!\nArquivo: {os.path.basename(path)}"))

    # Inicia a tela de carregamento animada
    executar_com_carregamento(salvar_excel_pesado, titulo="Exportando Excel", mensagem="A formatar a planilha, por favor aguarde...")

def iniciar_importacao_pdf_ui():
    """Lê os parâmetros da UI, pede os arquivos e chama a importação."""

    # 1. Ler Parâmetros da UI
    parceiro = clean_str(pdf_parceiro_var.get())
    tipo = clean_str(pdf_tipo_var.get())
    destinacao = clean_str(pdf_destinacao_var.get())
    data_obj = None
    data_db_fmt = ""

    try:
        data_obj = pdf_data_entry.get_date()
        data_db_fmt = data_obj.strftime("%Y-%m-%d") # Formato YYYY-MM-DD para o DB
    except Exception as e:
        ModernMessageBox.showerror("Erro de Data", f"Data da coleta inválida: {e}")
        return

    # Validação básica
    if not parceiro or not tipo or not destinacao:
        ModernMessageBox.showwarning("Campos Vazios", "Selecione Parceiro, Tipo e Destinação.")
        return

    # 2. Selecionar Arquivos
    file_paths = fd.askopenfilenames(
        title="Selecione os Tickets PDF para Importar",
        filetypes=[("Arquivos PDF", "*.pdf")]
    )

    if not file_paths:
        pdf_status_var.set("Importação cancelada.")
        return

    # 3. Chamar a Função de Processamento (Passando os parâmetros)
    importar_pdfs_tickets(file_paths, parceiro, data_db_fmt, tipo, destinacao)

def processar_pdf_romaneio(pdf_path, parceiro_ui, data_db_fmt_ui, tipo_ui, destinacao_ui):
    """
    Versão FINAL: Prioriza a captura correta do Valor Unitário e calcula o Total.
    """
    import database as db  
    import importlib       
    import re 
    importlib.reload(db)   
    
    registros = []
    print(f"\n--- ANALISANDO ARQUIVO (Valores FINAL): {os.path.basename(pdf_path)} ---")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                todas_tabelas = page.extract_tables()
                if not todas_tabelas: continue
                
                for tabela in todas_tabelas:
                    for row in tabela:
                        # 1. Limpeza PROFUNDA da linha
                        row_clean = []
                        for c in row:
                            if c:
                                txt = str(c).replace(u'\xa0', ' ').replace('\n', ' ').strip()
                                txt = re.sub(r'\s+', ' ', txt)
                                row_clean.append(txt)
                            else:
                                row_clean.append("")

                        if not any(row_clean) or len(row_clean) < 3: continue
                            
                        # 2. Acha a Quantidade (âncora)
                        idx_qtd = -1
                        str_qtd = ""
                        for col_idx, celula in enumerate(row_clean):
                            if "kg" in celula.lower() and any(c.isdigit() for c in celula):
                                idx_qtd = col_idx
                                str_qtd = celula
                                break 
                        
                        if idx_qtd == -1: continue

                        # 3. Acha Descrição, faz a Limpeza e Normalização (Mantido igual)
                        desc_candidata = ""
                        for k in range(idx_qtd): 
                            texto = row_clean[k]
                            is_data = re.search(r'\d{2}/\d{2}/\d{4}', texto)
                            is_ticket = "Ticket" in texto or "OTR" in texto
                            is_num_curto = texto.replace(" ", "").replace(".", "").replace("-","").isdigit() and len(texto) < 5
                            
                            if len(texto) > 3 and not is_data and not is_ticket and not is_num_curto:
                                if len(texto) > len(desc_candidata): desc_candidata = texto
                        
                        raw_desc = desc_candidata
                        raw_desc = re.sub(r'^\d+[\s-]*', '', raw_desc) 
                        prefixes = ["CIRCUIBRAS -", "CIRCUIBRAS", "SETE -", "CLIENTE -", "SETE AMBIENTAL"]
                        upper_d = raw_desc.upper()
                        for p in prefixes:
                            if upper_d.startswith(p):
                                raw_desc = raw_desc[len(p):].strip()
                                upper_d = raw_desc.upper()

                        if not raw_desc or "DESCRIÇÃO" in raw_desc.upper() or "ITEM" == raw_desc.upper() or "TOTAL" in raw_desc.upper():
                            continue

                        # 4. LÓGICA DE VALORES (Extração e Atribuição)
                        try:
                            # Prepara Peso (Qtd)
                            peso_float = float(str_qtd.lower().replace("kg", "").replace(".", "").replace(",", ".").strip())
                            
                            # Prepara lista de números encontrados à direita
                            cols_a_direita = row_clean[idx_qtd+1:]
                            numeros_encontrados = []
                            
                            for celula in cols_a_direita:
                                s_limpa = celula.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".").strip()
                                if any(c.isdigit() for c in s_limpa):
                                    try:
                                        val = float(s_limpa)
                                        numeros_encontrados.append(val)
                                    except: pass
                            
                            val_unit_float = 0.0
                            val_total_float = 0.0
                            
                            # --- ASSINATURA DA REGRA (A MUDANÇA ESTÁ AQUI) ---
                            if len(numeros_encontrados) >= 2:
                                # Caso 1: Achou Unitário E Total. Assina a ordem: Unit, Total
                                val_unit_float = numeros_encontrados[0]
                                val_total_float = numeros_encontrados[-1] 
                            
                            elif len(numeros_encontrados) == 1:
                                # Caso 2: Achou SÓ Unitário (o Total quebrou/sumiu).
                                # Assumi que o valor encontrado (ex: 3.10) é o Unitário
                                val_unit_float = numeros_encontrados[0]
                                
                                # NOVO: Recalcula o Total para manter a coerência (3.5kg * R$ 3.10 = R$ 10.85)
                                if peso_float > 0:
                                    val_total_float = val_unit_float * peso_float
                                else:
                                    val_total_float = val_unit_float
                                
                            else:
                                continue # Não tem valores para processar

                            # Arredondamento do Total (Para bater com o PDF)
                            val_total_float = round(val_total_float, 2)
                            
                            # ... (resto do código, Data e Mapeamento) ...
                            data_item = data_db_fmt_ui
                            for cel in row_clean:
                                match_data = re.search(r"(\d{2}/\d{2}/\d{4})", cel)
                                if match_data:
                                    try: data_item = datetime.strptime(match_data.group(1), "%d/%m/%Y").strftime("%Y-%m-%d")
                                    except: pass; break

                            # Mapeamento
                            nome_norm = normalizar(raw_desc)
                            nome_app = None
                            nome_db = db.get_residuo_from_pdf_mapping(nome_norm)
                            if not nome_db: nome_db = db.get_residuo_from_pdf_mapping(raw_desc)
                            
                            if nome_db: nome_app = nome_db
                            elif nome_app is None:
                                for nome_b, data_b in banco_dict.items():
                                    padrao = data_b.get('nome_pdf_padrao', '')
                                    if padrao and normalizar(padrao) in nome_norm:
                                        nome_app = nome_b; break
                                if not nome_app and nome_norm in mapa_produtos_app:
                                    nome_app = mapa_produtos_app[nome_norm]

                            if nome_app:
                                registros.append({
                                    'Data': data_item, 'Parceiro': parceiro_ui, 'Tipo': tipo_ui,
                                    'Destinacao': destinacao_ui, 'Residuo': nome_app,
                                    'Peso': peso_float, 
                                    'ValorPorKg': val_unit_float, 
                                    'ValorTotal': val_total_float, 
                                    'ProdutoPDF': raw_desc, 
                                    'Modo': 'kg'
                                })
                                print(f"   [SUCESSO] {raw_desc} | Unit: {val_unit_float} | Total: {val_total_float}")
                            else:
                                print(f"   [AVISO - NÃO MAPEADO] Texto Limpo: '{raw_desc}'")

                        except Exception as e_row:
                            print(f"   [ERRO LINHA] {e_row}")

    except Exception as e: print(f"ERRO FATAL: {e}")
    
    print(f"--- FIM: {len(registros)} itens importados ---")
    return registros

def importar_pdfs_tickets(file_paths, parceiro, data_db_fmt, tipo, destinacao):
    """
    Processa lista de PDFs, detectando automaticamente se é Ticket ou Boletim/Romaneio.
    """
    sucesso_total = 0
    erros_total = 0
    pdfs_processados = 0

    pdf_status_var.set(f"Importando {len(file_paths)} arquivo(s)...")
    app.update_idletasks()

    for pdf_path in file_paths:
        try:
            print(f"\n--- Analisando Arquivo: {os.path.basename(pdf_path)} ---")
            
            # 1. DETECÇÃO DE TIPO
            is_romaneio = False
            try:
                with pdfplumber.open(pdf_path) as temp_pdf:
                    first_page_text = temp_pdf.pages[0].extract_text() or ""
                    # Palavras-chave do seu PDF novo 
                    if "Boletim de Medição" in first_page_text or "Item" in first_page_text and "Ticket" in first_page_text and "Quantidade" in first_page_text:
                        is_romaneio = True
            except:
                pass # Se der erro ao abrir, vai cair no try abaixo e falhar normal

            # 2. PROCESSAMENTO
            registros_extraidos = []
            
            if is_romaneio:
                print(" -> Formato detectado: BOLETIM DE MEDIÇÃO (Tabela)")
                registros_extraidos = processar_pdf_romaneio(pdf_path, parceiro, data_db_fmt, tipo, destinacao)
            else:
                print(" -> Formato detectado: TICKET PADRÃO")
                registros_extraidos = processar_pdf_ticket(pdf_path, parceiro, data_db_fmt, tipo, destinacao)

            if not registros_extraidos:
                print(" -> Nenhum registro válido extraído.")
                erros_total += 1
                continue

            # 3. INSERÇÃO NO BANCO (Igual para os dois)
            erros_pdf = 0
            for reg_data in registros_extraidos:
                try:
                    novo_registro_db = [
                        reg_data['Data'],
                        reg_data['Parceiro'],
                        reg_data['Residuo'],
                        reg_data.get('Estado', "Sólido"),
                        reg_data['Destinacao'],
                        reg_data['Tipo'],
                        reg_data.get('Modo', "kg"),
                        reg_data['Peso'],
                        reg_data.get('ValorPorKg', 0.0),
                        0.0, # ValorFechado
                        0.0, # Transporte
                        reg_data['ValorTotal'],
                        "",  # PedidoCompra
                        "",  # NumMTR
                        "Não", # CertificadoOK
                        reg_data['Peso'], # PesoEmKg
                        "Não", # NFOk
                        ""     # CaminhoAnexo
                    ]
                    # Ajusta tamanho da lista caso seu banco tenha menos colunas (compatibilidade)
                    # Se seu database.py espera 18 colunas, certifique-se de mandar 18.
                    
                    res = db.add_registro(novo_registro_db)
                    if res: sucesso_total += 1
                    else: erros_pdf += 1
                except Exception as e_db:
                    print(f"Erro DB: {e_db}")
                    erros_pdf += 1

            if erros_pdf > 0: erros_total += 1
            pdfs_processados += 1

        except Exception as e:
            print(f"Erro crítico no arquivo: {e}")
            erros_total += 1

    # Feedback Final
    if pdfs_processados > 0:
        atualizar_views()
        msg = f"Processado. {sucesso_total} itens importados."
        if erros_total > 0: msg += f"\nAlguns itens NÃO foram importados.\n" + detalhe_erro_db("Detalhes em 'erros_sistema.log'.")
        ModernMessageBox.showinfo("Importação", msg)
    else:
        ModernMessageBox.showwarning("Erro", "Nenhum arquivo processado corretamente.")
    
    pdf_status_var.set("")
    
def processar_pdf_ticket(pdf_path, parceiro_ui, data_db_fmt_ui, tipo_ui, destinacao_ui):
    """Extrai ITENS de um PDF de ticket usando pdfplumber e mapeamento."""
    registros = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text: # Adiciona verificação se texto foi extraído
                    full_text += page_text + "\n"

        if not full_text:
            print(" -> Erro: Não foi possível extrair texto do PDF.")
            return []

        linhas_validas = []
        # Regex para capturar todos os 7 grupos principais da linha (a mesma de antes)
        item_regex = re.compile(
            r"(\d{4}-S-.*?)\s+"   # Group 1: Produto (Lazy match)
            r"([\d.,]+)\s+"       # Group 2: Bruto
            r"([\d.,]+)\s+"       # Group 3: Tara
            r"([\d.,]+)\s+"       # Group 4: Desc KG
            r"([\d.,]+)\s+"       # Group 5: Liquido
            r"([\d.,]+)\s+KG\s+"  # Group 6: Preco UN (followed by KG)
            r"([\d.,]+)"          # Group 7: Total R$ (no final)
        )

        for line in full_text.split('\n'):
            line = line.strip()
            match = item_regex.search(line)
            if match:
                produto_pdf_completo = match.group(1).strip() # Ex: 7622-S-FRESA COM COBRE (8)
                try:
                    # Extrai os valores numéricos usando os grupos corretos
                    liquido_str = match.group(5).replace('.', '').replace(',', '.')
                    preco_un_str = match.group(6).replace('.', '').replace(',', '.')
                    total_str = match.group(7).replace('.', '').replace(',', '.')

                    peso_liq = float(liquido_str)
                    preco_un = float(preco_un_str)
                    valor_tot = float(total_str)

                    # --- LÓGICA DE MAPEAMENTO (USANDO pdfplumber/standalone) ---
                    # 1. Extrai e Normaliza o nome do produto do PDF (sem o código)
                    nome_residuo_pdf = re.sub(r"^\d{4,}-S-\s*", "", produto_pdf_completo).strip()
                    nome_residuo_pdf_norm = normalizar(nome_residuo_pdf) # Usa a função do standalone

                    nome_residuo_app = None

                    # 2. Procura no mapa_produtos_app (do standalone)
                    if nome_residuo_pdf_norm in mapa_produtos_app:
                        nome_residuo_app = mapa_produtos_app[nome_residuo_pdf_norm]
                        print(f"   + OK: '{nome_residuo_pdf}' -> '{nome_residuo_app}' (Via Dicionário)")

                    # 3. Se não achou no mapa, tenta pelo "Nome Padrão PDF" da Aba 4
                    if nome_residuo_app is None:
                        for nome_banco, data_banco in banco_dict.items():
                            nome_pdf_cadastrado = data_banco.get('nome_pdf_padrao', '')
                            if nome_pdf_cadastrado:
                                nome_pdf_cadastrado_norm = normalizar(nome_pdf_cadastrado) # Normaliza o cadastrado
                                if nome_pdf_cadastrado_norm == nome_residuo_pdf_norm:
                                    nome_residuo_app = nome_banco
                                    print(f"   + OK: '{nome_residuo_pdf}' -> '{nome_residuo_app}' (Via Campo 'Nome PDF')")
                                    break

                    # 4. Se ainda não achou, tenta pelo nome principal (Aba 4)
                    if nome_residuo_app is None:
                        for nome_banco in banco_dict.keys():
                            nome_banco_norm = normalizar(nome_banco) # Normaliza o nome principal
                            if nome_banco_norm == nome_residuo_pdf_norm:
                                nome_residuo_app = nome_banco
                                print(f"   + OK: '{nome_residuo_pdf}' -> '{nome_residuo_app}' (Via Nome Principal)")
                                break
                    # --- FIM LÓGICA DE MAPEAMENTO ---

                    if nome_residuo_app:
                        # Adiciona aos registros válidos
                         linhas_validas.append({
                            'Data': data_db_fmt_ui,
                            'Parceiro': parceiro_ui,
                            'Tipo': tipo_ui,
                            'Destinacao': destinacao_ui,
                            'Residuo': nome_residuo_app, # Nome Mapeado/Encontrado
                            'Peso': peso_liq,
                            'ValorPorKg': preco_un,
                            'ValorTotal': valor_tot,
                            'ProdutoPDF': produto_pdf_completo # Debug
                        })
                    else:
                         print(f"   - ERRO MAP: Resíduo '{nome_residuo_pdf}' (norm: '{nome_residuo_pdf_norm}') não encontrado por Dicionário, Campo 'Nome PDF' ou Nome Principal.")

                except ValueError:
                    print(f"   - ERRO VALOR: Não foi possível converter números na linha: {line}")
                except Exception as e_map:
                     print(f"   - ERRO MAP (Exceção) para '{produto_pdf_completo}': {e_map}")

        registros = linhas_validas

    except pdfplumber.pdf_parser.PDFSyntaxError:
         print(f" -> Erro: Arquivo PDF mal formatado ou corrompido: {os.path.basename(pdf_path)}")
    except Exception as e:
        print(f" -> ERRO GERAL ao ler PDF {os.path.basename(pdf_path)}: {e}")

    return registros

def gerar_solicitacao_nf():
    """
    Gera solicitação de NF.
    Correção: Calcula totais ANTES de processar o Excel para garantir que
    todos os placeholders (data e valor) sejam preenchidos corretamente em qualquer lugar.
    """
    import re  # Necessário para limpar o nome do arquivo

    # 1. Validação de Seleção
    selected_iids_str = tabela.selection()
    if not selected_iids_str:
        ModernMessageBox.showwarning("Seleção Vazia", "Nenhum registro selecionado.")
        return
    
    try:
        record_ids = [int(iid) for iid in selected_iids_str]
        df_selecionados = df_registros_global.loc[record_ids].copy()

        if len(df_selecionados['Parceiro'].unique()) > 1:
            ModernMessageBox.showerror("Erro", "Selecione registros de apenas UM Parceiro por vez.")
            return

        # --- PREPARAÇÃO DE DADOS (Cálculo Prévio) ---
        nome_parceiro = df_selecionados['Parceiro'].iloc[0]
        
        # Datas
        dates = pd.to_datetime(df_selecionados['Data'], errors='coerce').dropna()
        if not dates.empty:
            data_carga_str = dates.max().strftime('%d/%m/%Y')
        else:
            data_carga_str = datetime.now().strftime('%d/%m/%Y')

        data_solicitacao_str = datetime.now().strftime("%d/%m/%Y")

        # --- LÓGICA DE AGRUPAMENTO E CÁLCULO TOTAL ---
        itens_agrupados = {}
        total_geral_carga = 0.0 # <--- Calculamos isso ANTES de abrir o Excel

        for _, row in df_selecionados.iterrows():
            # Dados do Resíduo
            nome_interno = clean_str(row.get('Residuo',''))
            dados_nf = banco_dict.get(nome_interno, {})
            desc_final = dados_nf.get('nome_nf', nome_interno)
            if not desc_final: desc_final = nome_interno
            cod_item = dados_nf.get('codigo_item', 'SEM_COD')
            
            # Chave
            valor_unit = float(row.get('ValorPorKg', 0))
            modo = str(row.get('Modo')).lower()
            
            if modo == 'fechado':
                chave = (cod_item, desc_final, "FECHADO") 
            else:
                chave = (cod_item, desc_final, valor_unit)

            if chave not in itens_agrupados:
                itens_agrupados[chave] = {'qtd': 0.0, 'total': 0.0, 'desc': desc_final, 'cod': cod_item, 'unit': valor_unit}
            
            # Soma valores
            peso_row = float(row.get('Peso', 0))
            val_row = float(row.get('ValorTotal', 0))
            
            itens_agrupados[chave]['qtd'] += peso_row
            itens_agrupados[chave]['total'] += val_row
            
            # Acumula Total Geral
            total_geral_carga += val_row

        # =================================================================
        # MANIPULAÇÃO DO EXCEL
        # =================================================================
        # =================================================================
        # MANIPULAÇÃO DO EXCEL
        # =================================================================
        template_path = resource_path('template_nf.xlsx')
        if not os.path.exists(template_path):
            ModernMessageBox.showerror("Erro", f"Template '{template_path}' não encontrado.")
            return

        try:
            wb = load_workbook(template_path)
            ws = wb.active

            # --- INÍCIO DA CORREÇÃO DO LOGO NO EXCEL ---
            # 1. Apaga qualquer erro (#VALOR!) ou texto residual na célula principal
            if ws['A1'].value == "#VALOR!":
                ws['A1'].value = ""

            try:
                # 2. Puxa o módulo de imagens do Excel e o caminho do logo
                from openpyxl.drawing.image import Image as XLImage
                logo_path = resource_path("logo.png")
                
                # 3. Se a imagem existir no seu computador, "carimba" ela na planilha
                if os.path.exists(logo_path):
                    img_logo = XLImage(logo_path)
                    
                    # Você pode ajustar esses valores se a imagem ficar achatada ou muito grande
                    img_logo.width = 310  
                    img_logo.height = 60  
                    
                    ws.add_image(img_logo, 'A1') # Coloca o logo na célula A1
            except Exception as e_logo:
                print(f"Aviso: Não foi possível inserir o logo no Excel: {e_logo}")
            # --- FIM DA CORREÇÃO DO LOGO ---

            # --- 1. SUBSTITUIÇÃO GLOBAL DE PLACEHOLDERS ---
            placeholders = {
                '{{data_solicitacao}}': data_solicitacao_str,
                '{{nome_parceiro}}': nome_parceiro,
                '{{data_carga}}': data_carga_str,
                '{{valor_total_carga}}': fmt_moeda(total_geral_carga)
            }

            for row in ws.iter_rows():
                for cell in row:
                    if cell.value and isinstance(cell.value, str):
                        novo_texto = cell.value
                        alterou = False
                        
                        for tag, valor_sub in placeholders.items():
                            if tag in novo_texto:
                                novo_texto = novo_texto.replace(tag, str(valor_sub))
                                alterou = True
                        
                        if alterou:
                            cell.value = novo_texto

            # --- 2. PREENCHIMENTO DA TABELA DE ITENS ---
            start_row = -1
            col_map = {} 
            
            for r in range(1, 100):
                row_values = [str(c.value).strip() if c.value else "" for c in ws[r]]
                
                if "DESCRIÇÃO" in row_values and "VALOR" in row_values:
                    start_row = r + 1
                    for idx, txt in enumerate(row_values):
                        col_idx = idx + 1
                        if "Cód" in txt: col_map['cod'] = col_idx
                        if "QTDE" in txt or "PESO" in txt: col_map['qtde'] = col_idx
                        if "DESCRIÇÃO" in txt: col_map['desc'] = col_idx
                        if "VALOR" in txt or "UNIT" in txt: col_map['unit'] = col_idx
                        if "UN" in txt or "UN." in txt: col_map['un'] = col_idx
                    break
            
            if start_row != -1 and col_map:
                current_row = start_row
                for chave, dados in itens_agrupados.items():
                    if chave[2] == "FECHADO":
                        v_unit = 0
                        if dados['qtd'] > 0: v_unit = dados['total'] / dados['qtd']
                    else:
                        v_unit = chave[2]

                    if 'cod' in col_map: ws.cell(current_row, col_map['cod']).value = dados['cod']

                    if 'un' in col_map:
                        ws.cell(current_row, col_map['un']).value = "kg"
                    
                    if 'qtde' in col_map: 
                        c = ws.cell(current_row, col_map['qtde'])
                        c.value = dados['qtd']
                        c.number_format = '#,##0.000'
                    
                    if 'desc' in col_map: 
                        ws.cell(current_row, col_map['desc']).value = dados['desc']
                    
                    if 'unit' in col_map: 
                        c = ws.cell(current_row, col_map['unit'])
                        c.value = v_unit
                        c.number_format = '"R$" #,##0.00'

                    current_row += 1
            else:
                print("Aviso: Cabeçalho da tabela de itens não encontrado. Apenas os placeholders foram preenchidos.")

            # --- SALVAR ARQUIVO (ALTERAÇÃO AQUI) ---
            
            # 1. Trata a data (de 07/11/2025 para 07-11-2025)
            data_arquivo = data_carga_str.replace("/", "-")
            
            # 2. Limpa o nome do parceiro (remove caracteres proibidos no Windows)
            nome_limpo = str(nome_parceiro).strip()
            nome_limpo = re.sub(r'[\\/*?:"<>|]', "", nome_limpo)

            # 3. Monta o nome final: Solicitacao NF - Nome - Data.xlsx
            filename = f"Solicitacao NF - {nome_limpo} - {data_arquivo}.xlsx"
            
            # 4. Abre a janela com o nome já sugerido
            save_path = filedialog.asksaveasfilename(initialfile=filename, defaultextension=".xlsx", title="Salvar Solicitação de NF")
            
            if save_path:
                wb.save(save_path)
                
                if ModernMessageBox.askyesno("Sucesso", f"Arquivo gerado!\nTotal da Carga: {fmt_moeda(total_geral_carga)}\n\nDeseja marcar os itens como 'NF Solicitada'?"):
                    # Usamos o motor garantido para forçar o "Solicitado"
                    for rid in record_ids:
                        try:
                            if rid in df_registros_global.index:
                                row = df_registros_global.loc[rid]
                                data_dt = row.get('Data', pd.NaT)
                                data_str = data_dt.strftime("%Y-%m-%d") if pd.notna(data_dt) else ""
                                data_full = [
                                    data_str, clean_str(row.get('Parceiro', '')), clean_str(row.get('Residuo', '')),
                                    clean_str(row.get('Estado', 'Sólido')), clean_str(row.get('Destinacao', '')),
                                    clean_str(row.get('Tipo', 'Venda')), clean_str(row.get('Modo', 'kg')),
                                    to_float_safe(row.get('Peso', 0)), to_float_safe(row.get('ValorPorKg', 0)),
                                    to_float_safe(row.get('ValorFechado', 0)), to_float_safe(row.get('Transporte', 0)),
                                    to_float_safe(row.get('ValorTotal', 0)), clean_str(row.get('PedidoCompra', '')),
                                    clean_str(row.get('NumMTR', '')), clean_str(row.get('CertificadoOK', 'Não')), 
                                    to_float_safe(row.get('PesoEmKg', 0)), "Solicitado", # <-- Ampulheta
                                    clean_str(row.get('CaminhoAnexo', ''))
                                ]
                                db.update_registro(rid, data_full)
                        except Exception as e: print(e)
                    
                    atualizar_views()
                    set_status("Solicitação gerada e status atualizados.")
                else:
                    set_status("Solicitação gerada.")

        except Exception as e:
            ModernMessageBox.showerror("Erro Excel", f"{e}")

    except Exception as e_main:
        ModernMessageBox.showerror("Erro Crítico", f"{e_main}")

# --- Função de atualização do DASHBOARD ---
def atualizar_dashboard():
    """Função Mestra que atualiza todos os gráficos e KPIs da aba Análise."""
    try:
        # 1. Pega as datas dos seletores
        dt_inicio = ana_data_inicio.get_date()
        dt_fim = ana_data_fim.get_date()
    except Exception as e: 
        ModernMessageBox.showerror("Erro Data", f"Formato inválido: {e}")
        return
        
    if dt_inicio > dt_fim: 
        ModernMessageBox.showwarning("Filtro Inválido", "Data início > Data fim.")
        return
    
    # 2. Filtra o DataFrame Global pelo período
    if df_registros_global.empty:
        df_periodo = pd.DataFrame()
    else:
        # Garante que a coluna Data é datetime
        df_temp = df_registros_global.copy()
        if 'Data' in df_temp.columns:
            df_temp['Data'] = pd.to_datetime(df_temp['Data'], errors='coerce')
            
            mask = (df_temp['Data'] >= pd.to_datetime(dt_inicio)) & (df_temp['Data'] <= pd.to_datetime(dt_fim))
            df_periodo = df_temp.loc[mask]
        else:
            df_periodo = pd.DataFrame() # Se não tiver coluna data, vazio
    
    # 3. Chama as funções de atualização de cada componente
    
    # Cards de Totais (KPIs) e Texto
    atualizar_totais(df_periodo)
    
    # Gráficos (Lado Esquerdo)
    atualizar_grafico_barras(df_periodo, ax_bar, canvas_bar)
    
    # Gráficos (Notebook Lado Direito)
    atualizar_grafico_pie_custo(df_periodo, ax_pie_custo, canvas_pie_custo)
    atualizar_grafico_pie_peso(df_periodo, ax_pie_peso, canvas_pie_peso)
    atualizar_grafico_lucro_residuo(df_periodo, ax_lucro_res, canvas_lucro_res)
    # Aba 4: Evolução (Usa o DF global para mostrar histórico de 12 meses)
    atualizar_grafico_evolucao(df_registros_global, ax_evol, canvas_evol)
    
    # Aba 5: Sólido vs Líquido vs Outros (O NOVO GRÁFICO)
    # Verifica se os widgets existem antes de tentar atualizar
    if 'ax_estado_fin' in globals() and 'canvas_estado_fin' in globals():
        atualizar_grafico_estado_financeiro(df_periodo, ax_estado_fin, canvas_estado_fin)
    
    # Tabela Resumo no rodapé
    preencher_resumo(df_periodo)
    
    # Atualiza barra de status
    set_status(f"Análise atualizada: {dt_inicio:%d/%m/%y} - {dt_fim:%d/%m/%y}.")
    
def exportar_para_sinir():
    """Assistente da DMR trimestral (SINIR): escolhe o trimestre, aponta pendências e gera a planilha."""
    win = tb.Toplevel(app)
    win.title("Assistente da DMR — SINIR")
    win.geometry("1000x600")
    win.transient(app)  # Sem grab_set: dá para corrigir cadastros com a janela aberta e clicar em "Verificar" de novo

    ano_padrao, tri_padrao = calculos.ultimo_trimestre_fechado()
    nomes_tri = ["1º trimestre (jan–mar)", "2º trimestre (abr–jun)", "3º trimestre (jul–set)", "4º trimestre (out–dez)"]
    ano_var = tk.StringVar(value=str(ano_padrao))
    tri_var = tk.StringVar(value=nomes_tri[tri_padrao - 1])
    resumo_var = tk.StringVar(value="")
    estado = {"dados": None, "periodo": None}

    topo = tb.Frame(win, padding=(15, 15, 15, 5)); topo.pack(fill="x")
    tb.Label(topo, text="Ano:").pack(side="left")
    tb.Spinbox(topo, from_=2020, to=2100, textvariable=ano_var, width=6).pack(side="left", padx=(5, 15))
    tb.Label(topo, text="Trimestre:").pack(side="left")
    tb.Combobox(topo, textvariable=tri_var, values=nomes_tri, state="readonly", width=24).pack(side="left", padx=(5, 15))
    btn_verificar = tb.Button(topo, text="Verificar", bootstyle=PRIMARY)
    btn_verificar.pack(side="left")

    tb.Label(win, textvariable=resumo_var, font=("Segoe UI", 10, "bold"), padding=(15, 5)).pack(fill="x")

    abas = tb.Notebook(win, bootstyle=PRIMARY)
    abas.pack(fill="both", expand=True, padx=15, pady=5)

    # Aba 1: totais por código IBAMA, para conferir com o SINIR (duplo clique marca como conferido)
    aba_cod = tb.Frame(abas, padding=6); abas.add(aba_cod, text="Conferência por código IBAMA")
    aba_cod.rowconfigure(1, weight=1); aba_cod.columnconfigure(0, weight=1)
    tb.Label(aba_cod, text="Compare cada código com o SINIR. Dê dois cliques na linha para marcar como conferida.",
             bootstyle=SECONDARY).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
    cols_cod = ("✔", "Código IBAMA", "Quantidade (t)", "Resíduos incluídos", "Destinadores")
    tv_cod = ttk.Treeview(aba_cod, columns=cols_cod, show="headings")
    for c, w, a in zip(cols_cod, (35, 125, 110, 410, 260), ("center", "center", "e", "w", "w")):
        tv_cod.heading(c, text=c); tv_cod.column(c, width=w, anchor=a, stretch=(c in ("Resíduos incluídos", "Destinadores")))
    tv_cod.grid(row=1, column=0, sticky="nsew")
    sb_cod = ttk.Scrollbar(aba_cod, orient="vertical", command=tv_cod.yview); tv_cod.configure(yscroll=sb_cod.set); sb_cod.grid(row=1, column=1, sticky="ns")
    tv_cod.tag_configure("conferido", foreground="#2e7d32")
    tv_cod.tag_configure("sem_codigo", foreground="#cc0000")

    def marcar_conferido(_evt=None):
        iid = tv_cod.focus()
        if not iid: return
        marcado = tv_cod.set(iid, "✔") == "✔"
        tv_cod.set(iid, "✔", "" if marcado else "✔")
        tags = [t for t in tv_cod.item(iid, "tags") if t != "conferido"]
        if not marcado: tags.append("conferido")
        tv_cod.item(iid, tags=tags)
    tv_cod.bind("<Double-1>", marcar_conferido)

    # Aba 2: pendências
    card = tb.Frame(abas, padding=6); abas.add(card, text="Pendências")
    card.rowconfigure(0, weight=1); card.columnconfigure(0, weight=1)
    cols = ("Problema", "Item", "Lançamentos", "Peso (kg)", "Como resolver")
    tv = ttk.Treeview(card, columns=cols, show="headings")
    for c, w, a in zip(cols, (270, 180, 95, 90, 360), ("w", "w", "center", "e", "w")):
        tv.heading(c, text=c); tv.column(c, width=w, anchor=a, stretch=(c == "Como resolver"))
    tv.grid(row=0, column=0, sticky="nsew")
    sb = ttk.Scrollbar(card, orient="vertical", command=tv.yview); tv.configure(yscroll=sb.set); sb.grid(row=0, column=1, sticky="ns")

    rodape = tb.Frame(win, padding=15); rodape.pack(fill="x")
    tb.Label(rodape, text="Análises, fretes e locações não entram na DMR.", bootstyle=SECONDARY).pack(side="left")
    tb.Button(rodape, text="Fechar", bootstyle=SECONDARY, command=win.destroy).pack(side="right")
    btn_gerar = tb.Button(rodape, text="Gerar planilha DMR", bootstyle=SUCCESS, state="disabled")
    btn_gerar.pack(side="right", padx=10)

    def verificar():
        try:
            ano = int(ano_var.get()); tri = nomes_tri.index(tri_var.get()) + 1
        except ValueError:
            ModernMessageBox.showerror("Ano inválido", "Informe um ano válido.", parent=win); return
        dt_ini, dt_fim = calculos.periodo_trimestre(ano, tri)
        base = db.get_all_registros_df(data_inicio=dt_ini.isoformat())  # Lê do banco: reflete correções recentes
        dados = calculos.preparar_dmr(base, dt_ini, dt_fim)
        estado["dados"], estado["periodo"] = dados, (ano, tri, dt_ini, dt_fim)

        for r in tv.get_children(): tv.delete(r)
        pend = dados["pendencias"]
        for _, row in pend.iterrows():
            tv.insert("", "end", values=(row["Problema"], row["Item"], row["Lançamentos"], fmt_kg(row["Peso (kg)"]), row["Como resolver"]))
        abas.tab(card, text=f"Pendências ({len(pend)})" if not pend.empty else "Pendências ✔")

        conferidos = {tv_cod.set(i, "Código IBAMA") for i in tv_cod.get_children() if tv_cod.set(i, "✔") == "✔"}
        for r in tv_cod.get_children(): tv_cod.delete(r)
        for _, row in dados["por_codigo"].iterrows():
            cod = row["Código IBAMA"]; ok = cod in conferidos
            t_fmt = f"{row['Quantidade (t)']:,.4f} t".replace(",", "X").replace(".", ",").replace("X", ".")
            tags = ["sem_codigo"] if cod == "SEM CÓDIGO" else []
            if ok: tags.append("conferido")
            tv_cod.insert("", "end", values=("✔" if ok else "", cod, t_fmt, row["Resíduos incluídos"], row["Destinadores"]), tags=tags)

        resumo = dados["resumo"]
        if resumo.empty:
            resumo_var.set(f"{dt_ini:%d/%m/%Y} a {dt_fim:%d/%m/%Y}: nenhum resíduo lançado no período.")
            btn_gerar.configure(state="disabled"); return
        total_t = resumo["Quantidade (t)"].sum()
        txt_pend = "nenhuma pendência ✔" if pend.empty else f"{len(pend)} pendência(s)"
        resumo_var.set(f"{dt_ini:%d/%m/%Y} a {dt_fim:%d/%m/%Y}  ·  {resumo['Resíduo'].nunique()} resíduos  ·  "
                       f"{total_t:,.3f} t".replace(",", "X").replace(".", ",").replace("X", ".") + f"  ·  {txt_pend}")
        btn_gerar.configure(state="normal")

    def gerar():
        dados = estado["dados"]
        ano, tri, dt_ini, dt_fim = estado["periodo"]
        if not dados["pendencias"].empty and not ModernMessageBox.askyesno(
                "Pendências", f"Ainda há {len(dados['pendencias'])} pendência(s).\nGerar a planilha mesmo assim?\n\n"
                "(Elas também serão listadas na aba 'Pendências' da planilha.)", parent=win):
            return
        path = filedialog.asksaveasfilename(parent=win, defaultextension=".xlsx", filetypes=[("Arquivo Excel", "*.xlsx")],
                                            initialfile=f"DMR_{tri}T_{ano}.xlsx", title="Salvar planilha da DMR")
        if not path: return
        try:
            from openpyxl.styles import Font, PatternFill
            abas_xlsx = [("Conferência por código", dados["por_codigo"]), ("Por código e destinador", dados["resumo"]),
                         ("Por mês", dados["por_mes"]), ("Lançamentos", dados["lancamentos"]),
                         ("Pendências", dados["pendencias"]), ("Fora da DMR", dados["ignorados"])]
            with pd.ExcelWriter(path, engine='openpyxl') as writer:
                for nome, df_aba in abas_xlsx:
                    df_aba.to_excel(writer, sheet_name=nome, index=False)
                    ws = writer.sheets[nome]
                    ws.freeze_panes = "A2"
                    for cel in ws[1]:
                        cel.font = Font(bold=True, color="FFFFFF"); cel.fill = PatternFill("solid", fgColor="1F6E8C")
                    for col in ws.columns:
                        largura = max((len(str(c.value)) for c in col if c.value is not None), default=10)
                        ws.column_dimensions[col[0].column_letter].width = min(largura + 2, 60)
                    # Destaca em amarelo células obrigatórias vazias (código IBAMA / CNPJ)
                    cabec = [c.value for c in ws[1]]
                    for nome_col in ("Código IBAMA", "CNPJ Destinador"):
                        if nome_col in cabec:
                            idx = cabec.index(nome_col) + 1
                            for linha in ws.iter_rows(min_row=2, min_col=idx, max_col=idx):
                                if not linha[0].value or linha[0].value == "SEM CÓDIGO":
                                    linha[0].fill = PatternFill("solid", fgColor="FFF2CC")
            ModernMessageBox.showinfo("DMR", f"Planilha da DMR do {tri}º trimestre de {ano} gerada!\n\n"
                                      "Use a aba 'Conferência por código' para conferir com o SINIR\n(a coluna 'Conferido' é para você marcar com X).", parent=win)
        except PermissionError:
            ModernMessageBox.showerror("Erro", "Não foi possível salvar: o arquivo está aberto no Excel?\nFeche-o e tente de novo.", parent=win)
        except Exception as e:
            db._registrar_erro(f"Erro ao gerar planilha DMR: {e}")
            ModernMessageBox.showerror("Erro", f"Falha ao salvar a planilha: {e}", parent=win)

    btn_verificar.configure(command=verificar)
    btn_gerar.configure(command=gerar)
    verificar()

# Liga o botão à função
btn_sinir.configure(command=exportar_para_sinir)

def exportar_dashboard_pdf():
    """Gera um PDF PROFISSIONAL (Versão Segura com Tela de Carregamento)."""
    try:
        dt_inicio = ana_data_inicio.get_date()
        dt_fim = ana_data_fim.get_date()
    except: return

    df_dashboard = df_registros_global.copy()
    if 'Data' in df_dashboard.columns:
        df_dashboard['Data'] = pd.to_datetime(df_dashboard['Data'], errors='coerce')
        mask = (df_dashboard['Data'] >= pd.to_datetime(dt_inicio)) & (df_dashboard['Data'] <= pd.to_datetime(dt_fim))
        df_dashboard = df_dashboard.loc[mask]

    if df_dashboard.empty:
        ModernMessageBox.showinfo("PDF", "Sem dados para gerar relatório."); return

    filename = f"Dashboard_{dt_inicio:%d-%m}_{dt_fim:%d-%m-%Y}.pdf"
    path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")], initialfile=filename, title="Salvar Relatório PDF")
    if not path: return

    # --- 1. PROCESSAMENTO NA MAIN THREAD (Proteção do Tkinter e Matplotlib) ---
    df_totais = atualizar_totais(df_dashboard) 
    row_total = df_totais[df_totais['Categoria'] == 'TOTAL GERAL'].iloc[0]
    v_vendas = row_total['Crédito (Venda)']
    v_custos = row_total['Débito (Custo)']
    v_lucro = v_vendas - v_custos
    v_peso = row_total['Peso (kg)']

    def fig_to_img_high_res(fig, w=13*cm, h=8*cm):
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=300, bbox_inches='tight', facecolor='white') 
        buf.seek(0)
        return RLImage(buf, width=w, height=h)

    # Transforma os gráficos da tela em imagens em memória ANTES da Thread 
    img_estado = fig_to_img_high_res(fig_estado_fin, w=12.5*cm, h=8*cm) if 'fig_estado_fin' in globals() else None
    img_lucro = fig_to_img_high_res(fig_lucro_res, w=12.5*cm, h=8*cm) if 'fig_lucro_res' in globals() else None
    img_pizza = fig_to_img_high_res(fig_pie_custo, w=12.5*cm, h=8*cm) if 'fig_pie_custo' in globals() else None

    # --- 2. FUNÇÃO PESADA (RODA NA THREAD EM SEGUNDO PLANO) ---
    def gerar_pdf_pesado():
        COR_PRIMARIA = colors.HexColor("#2C3E50")
        COR_SECUNDARIA = colors.HexColor("#18BC9C")
        COR_CINZA_CLARO = colors.HexColor("#ECF0F1")

        def draw_header_footer(c, doc):
            c.saveState()
            w, h = landscape(A4)
            c.setFillColor(COR_PRIMARIA)
            c.rect(0, h - 2.5*cm, w, 2.5*cm, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 18)
            c.drawString(2*cm, h - 1.5*cm, "RELATÓRIO DE GESTÃO DE RESÍDUOS")
            c.setFont("Helvetica", 10)
            c.drawString(2*cm, h - 2.1*cm, f"Período de Análise: {dt_inicio:%d/%m/%Y} a {dt_fim:%d/%m/%Y}")
            c.drawRightString(w - 2*cm, h - 1.7*cm, "SISTEMA DE GESTÃO AMBIENTAL - Circuibras")
            c.setStrokeColor(COR_SECUNDARIA)
            c.setLineWidth(1)
            c.line(1*cm, 1.5*cm, w - 1*cm, 1.5*cm)
            c.setFillColor(colors.gray)
            c.setFont("Helvetica", 8)
            c.drawString(1*cm, 1*cm, f"Gerado em: {datetime.now():%d/%m/%Y %H:%M}")
            c.drawRightString(w - 1*cm, 1*cm, f"Página {doc.page}")
            c.restoreState()

        doc = SimpleDocTemplate(path, pagesize=landscape(A4), topMargin=3.5*cm, bottomMargin=2.5*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
        elements = []
        styles = getSampleStyleSheet()
        h2_style = ParagraphStyle('H2_Custom', parent=styles['Heading2'], fontSize=14, textColor=COR_PRIMARIA, spaceBefore=15, spaceAfter=10)

        elements.append(Paragraph("Resumo", h2_style))
        kpi_data = [
            ["RECEITA BRUTA", "CUSTOS TOTAIS", "LUCRO LÍQUIDO", "VOLUME TOTAL"],
            [fmt_moeda(v_vendas), fmt_moeda(v_custos), fmt_moeda(v_lucro), fmt_kg(v_peso)]
        ]
        cw = (landscape(A4)[0] - 4*cm) / 4
        kpi_table = Table(kpi_data, colWidths=[cw, cw, cw, cw])
        kpi_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica'), ('FONTSIZE', (0,0), (-1,0), 9),
            ('TEXTCOLOR', (0,0), (-1,0), colors.gray), ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'), ('FONTSIZE', (0,1), (-1,1), 14),
            ('TEXTCOLOR', (0,1), (-1,1), COR_PRIMARIA), ('BOTTOMPADDING', (0,1), (-1,1), 15),
            ('LINEAFTER', (0,0), (2,1), 1, colors.lightgrey),
            ('TEXTCOLOR', (2,1), (2,1), colors.green if v_lucro >= 0 else colors.red),
        ]))
        elements.append(kpi_table)
        elements.append(Spacer(1, 0.5*cm))
        
        elements.append(Paragraph("Análise Gráfica", h2_style))
        
        if img_estado:
            tbl_estado = Table([[img_estado]], colWidths=[22*cm])
            tbl_estado.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
            elements.append(tbl_estado)
            elements.append(Spacer(1, 0.5*cm))

        row2_imgs = []
        if img_lucro: row2_imgs.append(img_lucro)
        if img_pizza: row2_imgs.append(img_pizza)
            
        if row2_imgs:
            col_w = [13*cm] * len(row2_imgs)
            chart_table = Table([row2_imgs], colWidths=col_w)
            chart_table.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
            elements.append(chart_table)
        
        elements.append(PageBreak())

        elements.append(Paragraph("Detalhamento Financeiro", h2_style))
        table_data = [["CATEGORIA", "CRÉDITO (Venda)", "DÉBITO (Custo)", "PESO (kg)"]]
        for _, row in df_totais.iterrows():
            if row['Categoria'] == 'TOTAL GERAL': continue
            table_data.append([row['Categoria'], fmt_moeda(row['Crédito (Venda)']), fmt_moeda(row['Débito (Custo)']), fmt_kg(row['Peso (kg)'])])
        table_data.append(["TOTAL GERAL", fmt_moeda(v_vendas), fmt_moeda(v_custos), fmt_kg(v_peso)])

        cw_tab = (landscape(A4)[0] - 4*cm) / 4
        resumo_table = Table(table_data, colWidths=[cw_tab*1.3, cw_tab*0.9, cw_tab*0.9, cw_tab*0.9])
        resumo_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,0), 10),
            ('BACKGROUND', (0,0), (-1,0), COR_PRIMARIA), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,0), 'CENTER'), ('BOTTOMPADDING', (0,0), (-1,0), 10), ('TOPPADDING', (0,0), (-1,0), 10),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,1), (-1,-1), 10),
            ('ALIGN', (1,1), (-1,-1), 'RIGHT'), ('ALIGN', (0,1), (0,-1), 'LEFT'),
            ('BOTTOMPADDING', (0,1), (-1,-1), 8), ('TOPPADDING', (0,1), (-1,-1), 8),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'), ('BACKGROUND', (0,-1), (-1,-1), COR_SECUNDARIA),
            ('TEXTCOLOR', (0,-1), (-1,-1), colors.white),
            ('GRID', (0,0), (-1,-2), 0.5, colors.lightgrey), ('BOX', (0,0), (-1,-1), 1, COR_PRIMARIA),
        ]))
        for i in range(1, len(table_data)-1):
            if i % 2 == 0: resumo_table.setStyle(TableStyle([('BACKGROUND', (0,i), (-1,i), COR_CINZA_CLARO)]))

        elements.append(resumo_table)
        doc.build(elements, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
        
        # Feedback final seguro
        app.after(0, lambda: set_status(f"PDF salvo em {path}"))
        app.after(0, lambda: ModernMessageBox.showinfo("Sucesso", "Relatório Dashboard gerado com sucesso!"))

    # 3. Dispara o carregamento
    executar_com_carregamento(gerar_pdf_pesado, titulo="Gerando Relatório", mensagem="A desenhar ficheiro PDF, aguarde...")
    
# --- Função principal de atualização ---
def atualizar_views():
    """Recarrega dados, atualiza UIs de apoio, filtros e tabela principal."""
    global df_registros_global, df_banco, banco_dict, df_parceiros, parceiros, df_analises, lista_analises, destinacoes
    
    try:
        data_sql = '2023-01-01' 
        if 'DATA_CORTE_ISO' in globals():
             data_sql = DATA_CORTE_ISO

        # 1. Puxa os dados do banco
        df_registros_global = db.get_all_registros_df(data_inicio=data_sql)
        atualizar_dashboard_home()
        
        # 2. Sincroniza todas as listas e tabelas de apoio
        preencher_banco_tabela()
        preencher_parceiros_tabela()
        preencher_analises_tabela()
        sincronizar_residuos_ui()
        sincronizar_parceiros_ui()
        sincronizar_analises_ui()
        
        destinacoes_unicas = df_registros_global["Destinacao"].unique().tolist() if not df_registros_global.empty else []
        destinacoes = sorted(list(set(DEFAULT_DESTINACOES + [d for d in destinacoes_unicas if d])))
        destinacao_cb.configure(values=destinacoes)

        if 'pdf_destinacao_cb' in globals(): pdf_destinacao_cb.configure(values=destinacoes)
        if not pdf_destinacao_var.get() and destinacoes: pdf_destinacao_var.set(destinacoes[0])
        
        if not destinacao_var.get() and destinacoes: destinacao_var.set(destinacoes[0])

        base = obter_df_registros()
        atualizar_menus_dinamicos(base) 

        # 3. Aplica os filtros da tela e preenche a tabela principal!
        df_filtrado_tabela = aplicar_filtros(base)
        preencher_tabela(df_filtrado_tabela)

        preencher_pendencias()
        atualizar_eventos_calendario()
        
    except Exception as e:
        ModernMessageBox.showerror("Erro Crítico", f"Falha ao atualizar dados/interface: {e}")
        print(f"Erro detalhado em atualizar_views: {e}")
        
        # --- RESTO DA FUNÇÃO ORIGINAL ---
        preencher_banco_tabela(); preencher_parceiros_tabela(); preencher_analises_tabela()
        sincronizar_residuos_ui(); sincronizar_parceiros_ui(); sincronizar_analises_ui()
        
        destinacoes_unicas = df_registros_global["Destinacao"].unique().tolist() if not df_registros_global.empty else []
        destinacoes = sorted(list(set(DEFAULT_DESTINACOES + [d for d in destinacoes_unicas if d])))
        destinacao_cb.configure(values=destinacoes)

        if 'pdf_destinacao_cb' in globals(): pdf_destinacao_cb.configure(values=destinacoes)
        if not pdf_destinacao_var.get() and destinacoes: pdf_destinacao_var.set(destinacoes[0])
        
        if not destinacao_var.get() and destinacoes: destinacao_var.set(destinacoes[0])

        base = obter_df_registros()
        atualizar_menus_dinamicos(base) 

        df_filtrado_tabela = aplicar_filtros(base)
        preencher_tabela(df_filtrado_tabela)

        preencher_pendencias()

        atualizar_eventos_calendario()
        
    except Exception as e:
        ModernMessageBox.showerror("Erro Crítico", f"Falha ao atualizar dados/interface: {e}")
        print(f"Erro detalhado em atualizar_views: {e}")

# =========================
# LIGAÇÕES FINAIS (Corrigido e Reorganizado)
# =========================

# --- 1. ABA CADASTRO ---
# (Formulário Principal)
btn_submit.configure(command=submit_registro_event)
btn_clear_form.configure(command=clear_form)
entrada_peso.bind("<Return>", submit_registro_event)
# (Formulário Análises Externas - movido para cá)
btn_ana_add.configure(command=adicionar_analise_event)
ana_valor_fechado.bind("<Return>", adicionar_analise_event)
launch_type_var.trace_add("write", toggle_launch_view)
launch_type_var.trace_add("write", atualizar_combobox_parceiro_dinamico)
btn_transporte_add.configure(command=adicionar_transporte_event)

# --- 2. ABA REGISTROS ---
# (Botões da tabela principal)
btn_edit.configure(command=iniciar_edicao)               
btn_del.configure(command=excluir_registros_selecionados)
tabela.bind("<Delete>", lambda e: excluir_registros_selecionados())
btn_cert.configure(command=marcar_certificados_ok)
btn_nf.configure(command=marcar_nf_ok)
btn_exigencias.configure(command=alterar_exigencias_lote)
btn_duplicar.configure(command=duplicar_registro)
btn_gerar_nf.configure(command=gerar_solicitacao_nf)

# (Filtros da tabela)
btn_filtrar_regs.configure(command=atualizar_views) 
tabela.bind("<<TreeviewSelect>>", atualizar_resumo_selecao)
f_parc.trace_add("write", lambda *_: atualizar_views())
f_res.trace_add("write", lambda *_: atualizar_views())
f_estado.trace_add("write", lambda *_: atualizar_views())
f_dest.trace_add("write", lambda *_: atualizar_views())
f_busca.trace_add("write", lambda *_: atualizar_views())
f_tipo.trace_add("write", lambda *_: atualizar_views())

def limpar_filtros_ui():
    # Reseta os Combobox
    f_parc.set("Todos")
    f_res.set("Todos")
    f_estado.set("Todas")
    f_dest.set("Todas")
    f_tipo.set("Todos")
    f_busca.set("")
    
    # Reseta Datas para o padrão (Inicio do Ano até Hoje)
    f_data_inicio.set_date(DATA_INICIO_MES_GLOBAL)
    f_data_fim.set_date(DATA_HOJE_GLOBAL)
    
    # Atualiza a tabela
    atualizar_views()

# Botão Limpar (Coloque ao lado do Filtrar)
btn_limpar_filtros = tb.Button(filtros, text="Limpar Filtros", bootstyle="secondary-outline", command=limpar_filtros_ui)
# Ajuste o grid para caber os dois
btn_filtrar_regs.grid(row=row2+1, column=4, sticky="e", padx=(0, 5), pady=(0, 10)) # Alinha Filtrar à direita
btn_limpar_filtros.grid(row=row2+1, column=3, sticky="e", padx=(0, 5), pady=(0, 10)) # Limpar ao lado dele


# --- 3. ABA PENDÊNCIAS ---
pend_tbl.bind("<Double-1>", marcar_pendencia_ok)


# --- 4. ABA RELATÓRIOS ---
# (Sub-aba Análise)
btn_export.configure(command=exportar_dados_dashboard)
btn_pdf.configure(command=exportar_dashboard_pdf)
btn_atualizar_ana.configure(command=atualizar_dashboard)
resumo.bind("<Double-1>", mostrar_detalhes_resumo)
btn_atualizar_ana.configure(command=atualizar_dashboard)
# (Sub-aba Indicadores ESG)
btn_gerar_esg.configure(command=start_esg_calculation) 
esg_data_inicio.entry.bind("<FocusOut>", on_month_select_esg)
esg_data_inicio.entry.bind("<Return>", on_month_select_esg)
# (Sub-aba Geração (Rateio))
##btn_gerar_cep.configure(command=atualizar_grafico_cep) 
btn_gerar_geracao.configure(command=start_geracao_calculation)
# (Sub-aba Ecoeficiência)
btn_gerar_eco.configure(command=calcular_ecoeficiencia)
btn_export_eco_xls.configure(command=exportar_ecoeficiencia_excel)
btn_export_eco_pdf.configure(command=exportar_ecoeficiencia_pdf)

# Conecta o botão da Balança Comercial
btn_gerar_fin.configure(command=calcular_balanca_comercial)

# --- 5. ABA CONFIGURAÇÕES ---
# (Sub-aba Resíduos)
btn_bn_add.configure(command=banco_add)                
btn_bn_edit.configure(command=banco_edit_wrapper) 
btn_bn_lote.configure(command=banco_edit_grupo_lote)
btn_bn_del.configure(command=banco_del)
btn_bn_reclass.configure(command=reclassificar_lote)

# (Sub-aba Parceiros)
btn_pc_add.configure(command=parceiros_add)
btn_pc_edit.configure(command=parceiros_edit_wrapper)
btn_pc_del.configure(command=parceiros_del)
pc_tbl.bind("<Delete>", lambda e: parceiros_del()) 

# (Sub-aba Análises)
btn_bana_add.configure(command=analises_add)       
btn_bana_edit.configure(command=analises_edit_wrapper) 
btn_bana_del.configure(command=analises_del)           
bana_tbl.bind("<Delete>", lambda e: analises_del()) 

# (Sub-aba Importação)
btn_iniciar_import_pdf.configure(command=iniciar_importacao_pdf_ui)

# --- SUB-ABA GESTÃO DE FERIADOS (CONFIGURAÇÕES) ---
aba_feriados_config = tb.Frame(config_nb, padding=12)
config_nb.add(aba_feriados_config, text="Feriados e Férias")

frame_info_feriados = tb.Labelframe(aba_feriados_config, text="Gerenciamento de Paradas", padding=20, bootstyle=INFO)
frame_info_feriados.pack(fill="x", pady=10)

tb.Label(frame_info_feriados, text="Adicione aqui os dias em que a empresa não opera (Férias coletivas, feriados emendados, etc).\nO sistema usará essas datas para descontar automaticamente dos cálculos de média e rateio.").pack(anchor="w", pady=(0, 15))

tb.Button(frame_info_feriados, text="📅 Abrir Painel de Feriados", bootstyle="primary", command=lambda: abrir_gestao_feriados(app), width=30).pack(anchor="w")

# --- SUB-ABA METRAGEM EM CONFIGURAÇÕES ---
aba_metragem_config = tb.Frame(config_nb, padding=12)
config_nb.add(aba_metragem_config, text="Metragem Mensal")

# Painel de Entrada (Mês e Ano separados)
met_input_frame = tb.Labelframe(aba_metragem_config, text="Registrar/Editar Metragem", padding=10, bootstyle=INFO)
met_input_frame.pack(fill="x", pady=(0, 10))

tb.Label(met_input_frame, text="Mês:").grid(row=0, column=0, padx=5, sticky="w")
var_met_mes = tk.StringVar(value=meses_lista[datetime.now().month - 1])
cb_met_mes = tb.Combobox(met_input_frame, textvariable=var_met_mes, values=meses_lista, width=12, state="readonly")
cb_met_mes.grid(row=0, column=1, padx=5)

tb.Label(met_input_frame, text="Ano:").grid(row=0, column=2, padx=5, sticky="w")
var_met_ano = tk.StringVar(value=str(datetime.now().year))
ent_met_ano = tb.Spinbox(met_input_frame, from_=2020, to=2050, textvariable=var_met_ano, width=8)
ent_met_ano.grid(row=0, column=3, padx=5)

tb.Label(met_input_frame, text="Valor (m²):").grid(row=0, column=4, padx=(15, 5), sticky="w")
var_met_valor = tk.StringVar()
ent_met_valor = tb.Entry(met_input_frame, textvariable=var_met_valor, width=12)
ent_met_valor.grid(row=0, column=5, padx=5)

btn_met_salvar = tb.Button(met_input_frame, text="Salvar", bootstyle=SUCCESS)
btn_met_salvar.grid(row=0, column=6, padx=15)

# Tabela com Alinhamento Centralizado
tree_met = tb.Treeview(aba_metragem_config, columns=("mes_ano", "valor"), show="headings", height=10, bootstyle=INFO)
tree_met.heading("mes_ano", text="Mês / Ano", anchor="center")
tree_met.heading("valor", text="Metragem Produzida (m²)", anchor="center")

# Centralizando os dados das colunas
tree_met.column("mes_ano", anchor="center", width=200)
tree_met.column("valor", anchor="center", width=200)

tree_met.pack(fill="both", expand=True)

# Botões de Suporte
btn_frame = tb.Frame(aba_metragem_config)
btn_frame.pack(fill="x", pady=5)

btn_met_editar = tb.Button(btn_frame, text="Editar Selecionado", bootstyle=WARNING)
btn_met_editar.pack(side="right", padx=5)

btn_met_excluir = tb.Button(btn_frame, text="Excluir Selecionado", bootstyle=DANGER)
btn_met_excluir.pack(side="right", padx=5)
tree_met.bind("<Delete>", lambda e: excluir_metragem_selecionada())

# --- MENU DE CONTEXTO (Botão Direito) ---
menu_tabela = tk.Menu(app, tearoff=0)

def abrir_anexo_selecionado():
    sel = tabela.focus()
    if not sel: return
    try:
        rec_id = int(sel)
        # Pega o caminho do DataFrame global
        caminho = df_registros_global.loc[rec_id, 'CaminhoAnexo']
        
        if not caminho or not os.path.exists(caminho):
            ModernMessageBox.showinfo("Anexo", "Este registro não possui anexo válido.")
            return
            
        # Abre o arquivo com o programa padrão do sistema
        os.startfile(os.path.abspath(caminho))
        
    except Exception as e:
        ModernMessageBox.showerror("Erro", f"Erro ao abrir arquivo: {e}")

menu_tabela.add_command(label="Ver Anexo/Comprovante", command=abrir_anexo_selecionado)
# Você pode adicionar as outras ações aqui também se quiser
menu_tabela.add_separator()
menu_tabela.add_command(label="Editar Registro", command=iniciar_edicao)

def mostrar_menu_tabela(event):
    try:
        # Seleciona a linha onde foi clicado
        item = tabela.identify_row(event.y)
        if item:
            tabela.selection_set(item)
            tabela.focus(item)
            menu_tabela.post(event.x_root, event.y_root)
    except: pass

# Liga o botão direito do mouse
tabela.bind("<Button-3>", mostrar_menu_tabela)

# =========================
# INICIALIZAÇÃO UI
# =========================
config_tags_por_tema()
preencher_banco_tabela(); preencher_parceiros_tabela(); preencher_analises_tabela()
sincronizar_residuos_ui(); sincronizar_parceiros_ui(); sincronizar_analises_ui()
toggle_campos_por_modo(); toggle_pedido_por_tipo()
atualizar_views() # Carrega dados do DB e preenche tudo, exceto dashboard
atualizar_dashboard() # Preenche o dashboard inicial com período padrão
clear_form() # Limpa o formulário de cadastro ao iniciar
clear_form_analise() # Limpa o formulário de análises ao iniciar
toggle_launch_view()
btn_met_salvar.configure(command=salvar_metragem_dinamica)
btn_met_editar.configure(command=carregar_metragem_para_edicao)
btn_met_excluir.configure(command=excluir_metragem_selecionada)
atualizar_tabela_metragem()

# ==========================================
# SISTEMA DE BACKUP AUTOMÁTICO (SEGURANÇA)
# ==========================================
def realizar_backup_e_fechar():
    """Cria uma cópia do banco ao fechar e encerra o programa."""
    try:
        # 1 cópia por dia na pasta "Backups", guardando os últimos 60 dias (ver backup.py)
        from backup import fazer_backup_diario
        fazer_backup_diario(db.DB_FILE)
    except Exception as e:
        # Se der erro no backup, avisa mas deixa fechar o programa
        db._registrar_erro(f"Erro no backup automático: {e}")
        ModernMessageBox.showwarning("Aviso de Backup", f"Não foi possível criar o backup automático:\n{e}")

    # 4. Encerra o programa
    try:
        app.destroy()
    except:
        pass

# Conecta o botão "X" da janela a esta função
app.protocol("WM_DELETE_WINDOW", realizar_backup_e_fechar)

# ==========================================

# =========================
# LOOP PRINCIPAL
# =========================
app.mainloop()
