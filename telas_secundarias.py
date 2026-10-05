# telas_secundarias.py
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from datetime import datetime, timedelta
import sqlite3

# Importa os módulos do seu sistema
import database as db
import calculos
from componentes import CalendarioPremium, obter_data_segura, ModernMessageBox

def abrir_gestao_feriados(app_principal):
    """Abre a janela de gestão de dias não úteis."""
    janela_feriados = tb.Toplevel(app_principal)
    janela_feriados.title("Gestão de Feriados e Férias Coletivas")
    janela_feriados.geometry("600x600") 
    janela_feriados.grab_set() 
    
    frame_add = tb.Frame(janela_feriados, padding=10)
    frame_add.pack(fill="x")
    frame_add.columnconfigure(2, weight=1)
    
    tb.Label(frame_add, text="Data Inicial:").grid(row=0, column=0, sticky="w", pady=5)
    data_ini_entry = CalendarioPremium(frame_add, dateformat="%d/%m/%Y") 
    data_ini_entry.grid(row=0, column=1, padx=10, pady=5)
    
    tb.Label(frame_add, text="Data Final:").grid(row=1, column=0, sticky="w", pady=5)
    data_fim_entry = CalendarioPremium(frame_add, dateformat="%d/%m/%Y") 
    data_fim_entry.grid(row=1, column=1, padx=10, pady=5)
    
    tb.Label(frame_add, text="Descrição:").grid(row=2, column=0, sticky="w", pady=5)
    desc_entry = tb.Entry(frame_add, width=25)
    desc_entry.grid(row=2, column=1, padx=10, pady=5)
    
    tb.Label(frame_add, text="(Para apenas 1 dia, deixe as duas datas iguais)", font=("Helvetica", 8, "italic")).grid(row=3, column=1, sticky="w")
    
    frame_lista = tb.Frame(janela_feriados, padding=10)
    frame_lista.pack(fill="both", expand=True)
    
    colunas = ("Data", "Descrição")
    tabela_feriados = tb.Treeview(frame_lista, columns=colunas, show="headings", bootstyle="info")
    tabela_feriados.heading("Data", text="Data")
    tabela_feriados.heading("Descrição", text="Descrição")
    tabela_feriados.column("Data", width=120, anchor="center")
    tabela_feriados.column("Descrição", width=300)
    tabela_feriados.pack(fill="both", expand=True, pady=10)
    
    def atualizar_tabela():
        tabela_feriados.delete(*tabela_feriados.get_children())
        conn = db.connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT data_bloqueada, descricao FROM dias_nao_uteis ORDER BY data_bloqueada")
            for linha in cursor.fetchall():
                d_obj = datetime.strptime(linha[0], "%Y-%m-%d")
                tabela_feriados.insert("", "end", values=(d_obj.strftime("%d/%m/%Y"), linha[1], linha[0]))
        except: pass
        finally: conn.close()

    def salvar_data():
        try:
            data_ini_obj = obter_data_segura(data_ini_entry)
            data_fim_obj = obter_data_segura(data_fim_entry)
        except:
            ModernMessageBox.showerror("Erro", "Data inválida", parent=janela_feriados)
            return
            
        nova_desc = desc_entry.get()
        if not nova_desc:
            ModernMessageBox.showwarning("Aviso", "Preencha a descrição.", parent=janela_feriados)
            return
            
        if data_fim_obj < data_ini_obj:
            ModernMessageBox.showwarning("Aviso", "A Data Final não pode ser menor que a Data Inicial.", parent=janela_feriados)
            return

        delta = data_fim_obj - data_ini_obj
        dias_adicionados = 0
        
        for i in range(delta.days + 1):
            dia_atual = data_ini_obj + timedelta(days=i)
            dia_str = dia_atual.strftime("%Y-%m-%d")
            if db.adicionar_dia_nao_util(dia_str, nova_desc):
                dias_adicionados += 1
        
        if dias_adicionados > 0:
            atualizar_tabela()
            desc_entry.delete(0, 'end')
            ModernMessageBox.showinfo("Sucesso", f"{dias_adicionados} dia(s) registado(s) com sucesso!", parent=janela_feriados)
            calculos.DATAS_MANUAIS = db.get_datas_manuais()
            calculos.HOLIDAYS_BR_2025 = list(set(calculos.DATAS_MANUAIS + [d.strftime('%Y-%m-%d') for d in calculos.feriados_oficiais]))
        else:
            ModernMessageBox.showwarning("Aviso", "Nenhuma data nova foi adicionada. (Podem já estar registadas).", parent=janela_feriados)

    def excluir_data():
        selecionados = tabela_feriados.selection()
        if not selecionados:
            ModernMessageBox.showwarning("Aviso", "Selecione pelo menos uma data para excluir.", parent=janela_feriados)
            return
            
        qtd = len(selecionados)
        if qtd == 1:
            valores = tabela_feriados.item(selecionados[0], "values")
            mensagem = f"Tem a certeza que deseja excluir a folga do dia {valores[0]}?"
        else:
            mensagem = f"Tem a certeza que deseja excluir as {qtd} datas selecionadas?"
            
        if ModernMessageBox.askyesno("Confirmar Exclusão", mensagem, parent=janela_feriados):
            dias_excluidos = 0
            for item in selecionados:
                valores = tabela_feriados.item(item, "values")
                data_remover = valores[2] 
                if db.remover_dia_nao_util(data_remover):
                    dias_excluidos += 1
                    
            atualizar_tabela()
            calculos.DATAS_MANUAIS = db.get_datas_manuais()
            calculos.HOLIDAYS_BR_2025 = list(set(calculos.DATAS_MANUAIS + [d.strftime('%Y-%m-%d') for d in calculos.feriados_oficiais]))
            
            if dias_excluidos > 1:
                ModernMessageBox.showinfo("Sucesso", f"{dias_excluidos} datas removidas.", parent=janela_feriados)

    btn_add = tb.Button(frame_add, text="➕ Adicionar\nPeríodo", bootstyle="success", command=salvar_data)
    btn_add.grid(row=0, column=2, rowspan=4, ipadx=10, padx=(20, 0), sticky="nsew")
    
    btn_del = tb.Button(frame_lista, text="🗑️ Excluir Selecionados", bootstyle="danger", command=excluir_data)
    btn_del.pack(side="bottom", anchor="e", pady=(10, 0))
    
    atualizar_tabela()
