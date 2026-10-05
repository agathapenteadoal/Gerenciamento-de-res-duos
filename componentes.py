# componentes.py
import tkinter as tk
from tkinter import messagebox as tk_msg
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from datetime import datetime, date, timedelta
import calendar
from tkcalendar import Calendar

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

# =======================================================
# CALENDÁRIO PREMIUM CUSTOMIZADO (LIVRE DE BUGS)
# =======================================================
class CalendarioPremium(tb.Frame):
    def __init__(self, master, dateformat="%d/%m/%y", **kwargs):
        super().__init__(master, **kwargs)
        self.dateformat = dateformat
        self.data_selecionada = tk.StringVar()
        
        # Preenche com a data de hoje por padrão
        self.data_selecionada.set(date.today().strftime(self.dateformat))

        # Entry visual (agora permite digitação manual)
        self.entry = tb.Entry(self, textvariable=self.data_selecionada, state="normal")
        self.entry.pack(side=LEFT, fill=X, expand=True)
        
        # Botão com ícone (O calendário abre apenas ao clicar aqui)
        self.btn = tb.Button(self, text="📅", bootstyle=SECONDARY, command=self.abrir_calendario)
        self.btn.pack(side=RIGHT, padx=(2, 0))

        self.popup = None

    def get(self):
        # Este método faz o CalendarioPremium funcionar exatamente como o DateEntry antigo
        return self.data_selecionada.get()

    def set_date(self, data_obj):
        """Permite que o sistema injete uma data via código (ex: botão 'Este Mês')"""
        try:
            # Converte o objeto de data para o formato string (ex: %d/%m/%y) e joga na tela
            self.data_selecionada.set(data_obj.strftime(self.dateformat))
        except Exception as e:
            print(f"Erro ao setar a data: {e}")

    def get_date(self):
        """Devolve a data selecionada já convertida para o sistema fazer os cálculos"""
        texto = self.data_selecionada.get()
        try:
            # Tenta converter o texto da tela para um objeto de data real
            return datetime.strptime(texto, self.dateformat).date()
        except ValueError:
            # Se por algum motivo o texto estiver vazio ou quebrado, devolve a data de hoje para não travar
            return date.today()

    def abrir_calendario(self):
        # 1. Por defeito, assume o mês atual
        hoje = date.today()
        self.ano_atual = hoje.year
        self.mes_atual = hoje.month

        # 2. Tenta ler o que foi digitado para ir para o mês correto
        try:
            texto = self.data_selecionada.get().strip()
            if texto:
                try:
                    # Tenta ler no formato padrão (ex: 15/03/24)
                    data_digitada = datetime.strptime(texto, self.dateformat).date()
                except ValueError:
                    # Tenta ler no formato com ano de 4 dígitos (ex: 15/03/2024)
                    data_digitada = datetime.strptime(texto, "%d/%m/%Y").date()
                
                # Se conseguiu ler, atualiza a memória do calendário
                self.mes_atual = data_digitada.month
                self.ano_atual = data_digitada.year
        except Exception:
            pass # Se a data for inválida, ignora e mantém a data de hoje
        
        # Se o popup já estiver aberto, fecha
        if self.popup and self.popup.winfo_exists():
            self.popup.destroy()
            return

        # Cria a janela flutuante sem bordas do Windows
        self.popup = tk.Toplevel(self)
        self.popup.overrideredirect(True)
        self.popup.attributes('-topmost', True) # Mantém por cima de tudo

        # Calcula onde o popup deve aparecer (logo abaixo do campo)
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 2
        self.popup.geometry(f"+{x}+{y}")

        # Fundo e Borda do calendário
        frame_principal = tb.Frame(self.popup, bootstyle="default", borderwidth=1, relief="solid")
        frame_principal.pack(fill=BOTH, expand=True)

        self.frame_calendario = tb.Frame(frame_principal, padding=10)
        self.frame_calendario.pack()

        # Botão para fechar o calendário
        tb.Button(frame_principal, text="Fechar X", bootstyle="danger-link", command=self.popup.destroy).pack(pady=(0,5))

        self.renderizar_mes()

    def escolher_data(self, dia):
        data_escolhida = date(self.ano_atual, self.mes_atual, dia)
        self.data_selecionada.set(data_escolhida.strftime(self.dateformat))
        self.popup.destroy() # Fecha ao clicar no dia

    def mudar_mes(self, delta):
        """Avança ou recua os meses e atualiza a tela do calendário."""
        self.mes_atual += delta
        
        # Se passar de Dezembro, vai para Janeiro do ano seguinte
        if self.mes_atual > 12:
            self.mes_atual = 1
            self.ano_atual += 1
            
        # Se voltar antes de Janeiro, vai para Dezembro do ano anterior
        elif self.mes_atual < 1:
            self.mes_atual = 12
            self.ano_atual -= 1
            
        # Manda desenhar a telinha do calendário de novo com o novo mês
        self.renderizar_mes()

    def renderizar_mes(self):
        for widget in self.frame_calendario.winfo_children():
            widget.destroy()

        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        dias_semana = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]

        # Cabeçalho (Botão de Voltar, Mês/Ano, Botão de Avançar)
        header = tb.Frame(self.frame_calendario)
        header.grid(row=0, column=0, columnspan=7, sticky="ew", pady=(0, 10)) # <-- CORRIGIDO AQUI!

        tb.Button(header, text="<", bootstyle="primary-link", command=lambda: self.mudar_mes(-1)).pack(side=LEFT)
        lbl_mes = tb.Label(header, text=f"{meses[self.mes_atual-1]} {self.ano_atual}", font=("Helvetica", 10, "bold"))
        lbl_mes.pack(side=LEFT, expand=True)
        tb.Button(header, text=">", bootstyle="primary-link", command=lambda: self.mudar_mes(1)).pack(side=RIGHT)

        # Letras dos dias da semana
        for col, dia in enumerate(dias_semana):
            tb.Label(self.frame_calendario, text=dia, font=("Helvetica", 8, "bold"), anchor="center").grid(row=1, column=col, padx=2, pady=2, sticky="nsew")

        # Matriz de dias
        calendar.setfirstweekday(calendar.SUNDAY)
        cal = calendar.monthcalendar(self.ano_atual, self.mes_atual)

        for row, semana in enumerate(cal):
            for col, dia in enumerate(semana):
                if dia != 0:
                    btn = tb.Button(self.frame_calendario, text=str(dia), bootstyle="secondary-outline", width=3,
                                    command=lambda d=dia: self.escolher_data(d))
                    btn.grid(row=row+2, column=col, padx=2, pady=2)
                    
                    # Pinta de azul o dia que está selecionado atualmente
                    try:
                        data_atual = datetime.strptime(self.get(), self.dateformat).date()
                        if data_atual.day == dia and data_atual.month == self.mes_atual and data_atual.year == self.ano_atual:
                            btn.configure(bootstyle="primary")
                    except: pass

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

def obter_data_segura(widget_dateentry):
    """
    Força a leitura do TEXTO digitado no DateEntry.
    Se o usuário digitou '01/01/23', converte isso para data,
    ignorando a seleção interna do calendário se ela estiver desatualizada.
    """
    try:
        # 1. Pega o texto puro que o usuário digitou (ex: "04/02/25")
        texto_digitado = widget_dateentry.entry.get()
        
        # 2. Tenta converter usando o formato brasileiro dia/mes/ano(2 digitos)
        return datetime.strptime(texto_digitado, "%d/%m/%y").date()
    except ValueError:
        try:
            # Tenta com ano de 4 dígitos por segurança
            return datetime.strptime(texto_digitado, "%d/%m/%Y").date()
        except:
            # 3. Se falhar (texto inválido), tenta o método nativo do widget
            return widget_dateentry.get_date() # Retorna o que estiver no calendário
