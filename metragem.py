# metragem.py
import database as db
from componentes import ModernMessageBox
from utilidades import money_pt

mapa_meses_num = {
    "Janeiro": "01", "Fevereiro": "02", "Março": "03", "Abril": "04", "Maio": "05", "Junho": "06",
    "Julho": "07", "Agosto": "08", "Setembro": "09", "Outubro": "10", "Novembro": "11", "Dezembro": "12"
}

mapa_meses_sigla_inv = {
    "jan": "Janeiro", "fev": "Fevereiro", "mar": "Março", "abr": "Abril", "mai": "Maio", "jun": "Junho",
    "jul": "Julho", "ago": "Agosto", "set": "Setembro", "out": "Outubro", "nov": "Novembro", "dez": "Dezembro"
}

def atualizar_tabela(tree_met):
    """Recarrega a tabela em ordem crescente e formato jan/25 centralizado."""
    for item in tree_met.get_children():
        tree_met.delete(item)
    
    dados = db.get_all_metragens() 
    dados_crescente = sorted(dados, key=lambda x: x[0]) 

    siglas = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]

    for mes_ano_db, valor in dados_crescente:
        ano_full, mes_num = mes_ano_db.split("-")
        sigla = siglas[int(mes_num)-1]
        exibicao = f"{sigla}/{ano_full[2:]}" 
        
        valor_fmt = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        tree_met.insert("", "end", values=(exibicao, f"{valor_fmt} m²"))

def excluir_selecionada(tree_met, set_status):
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
            atualizar_tabela(tree_met)
        else:
            ModernMessageBox.showerror("Erro", "Não foi possível excluir do banco de dados.")

def carregar_para_edicao(tree_met, var_met_mes, var_met_ano, var_met_valor):
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

def salvar_dinamica(var_met_mes, var_met_ano, var_met_valor, tree_met, set_status):
    """Salva os dados no banco usando o formato YYYY-MM."""
    mes_num = mapa_meses_num.get(var_met_mes.get())
    ano = var_met_ano.get()
    mes_ano_db = f"{ano}-{mes_num}" 
    
    try:
        valor = float(money_pt(var_met_valor.get()))
        if db.add_or_update_metragem(mes_ano_db, valor):
            set_status(f"Metragem de {var_met_mes.get()}/{ano} salva!")
            atualizar_tabela(tree_met)
            var_met_valor.set("")
        else:
            ModernMessageBox.showerror("Erro", "Erro ao salvar no banco.")
    except Exception:
        ModernMessageBox.showerror("Erro", "Valor de metragem inválido.")
