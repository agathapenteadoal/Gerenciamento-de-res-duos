# operacoes_tabela.py
import pandas as pd
import database as db
from componentes import ModernMessageBox

# Funções auxiliares locais
def clean_str(x):
    if x is None: return ""
    s = str(x).strip()
    return "" if s.lower() in ("nan", "none") else s

def to_float_safe(x, default=0.0):
    try:
        st = str(x).strip().replace(" ", "")
        if "," in st and "." in st: st = st.replace(".", "").replace(",", ".")
        else: st = st.replace(",", ".")
        return float(st)
    except:
        return float(default)

def excluir_registros(app, tabela, callback_atualizar, set_status):
    selected_iids_str = tabela.selection() 
    if not selected_iids_str:
        ModernMessageBox.showwarning("Aviso", "Nenhum registro selecionado para excluir.", parent=app)
        return
        
    try: record_ids = [int(iid) for iid in selected_iids_str]
    except ValueError: return

    count = len(record_ids)
    if not ModernMessageBox.askyesno("Confirmar Exclusão", f"Tem certeza que deseja excluir {count} item(ns)?", parent=app): return

    set_status(f"Excluindo {count} registros...")
    erros, sucessos = 0, 0

    for record_id in record_ids:
        try:
            if db.delete_registro(record_id): sucessos += 1
            else: erros += 1
        except Exception: erros += 1

    callback_atualizar() 
    if erros > 0: ModernMessageBox.showwarning("Aviso", f"{sucessos} excluídos.\nFalha ao excluir {erros} itens.", parent=app)
    else: ModernMessageBox.showinfo("Sucesso", f"{sucessos} registros excluídos permanentemente.", parent=app)


def marcar_certificados_ok(app, tabela, df_registros_global, callback_atualizar):
    selected_iids_str = tabela.selection()
    if not selected_iids_str:
        ModernMessageBox.showwarning("Aviso", "Selecione os itens na tabela primeiro.", parent=app)
        return
    
    ids = [int(i) for i in selected_iids_str]
    count = len(ids)
    if not ModernMessageBox.askyesno("Confirmar", f"Marcar 'Certificado OK' = 'Sim' para {count} item(ns)?", parent=app): return
    
    sucessos = 0
    for rid in ids:
        try:
            # 1. ATUALIZAÇÃO CIRÚRGICA: Toca apenas no campo do Certificado
            if hasattr(db, 'update_certificado'):
                db.update_certificado(rid, "Sim")
                sucessos += 1
            else:
                # 2. Fallback de Segurança: Limpa o formato do Pandas forçando textos e floats puros
                row = df_registros_global.loc[rid]
                data_dt = row.get('Data', pd.NaT)
                data_str = data_dt.strftime("%Y-%m-%d") if pd.notna(data_dt) else ""
                
                data_full = [
                    str(data_str), str(clean_str(row.get('Parceiro', ''))), str(clean_str(row.get('Residuo', ''))),
                    str(clean_str(row.get('Estado', 'Sólido'))), str(clean_str(row.get('Destinacao', ''))),
                    str(clean_str(row.get('Tipo', 'Venda'))), str(clean_str(row.get('Modo', 'kg'))),
                    float(to_float_safe(row.get('Peso', 0))), float(to_float_safe(row.get('ValorPorKg', 0))),
                    float(to_float_safe(row.get('ValorFechado', 0))), float(to_float_safe(row.get('Transporte', 0))),
                    float(to_float_safe(row.get('ValorTotal', 0))), str(clean_str(row.get('PedidoCompra', ''))),
                    str(clean_str(row.get('NumMTR', ''))), "Sim", 
                    float(to_float_safe(row.get('PesoEmKg', 0))), str(clean_str(row.get('NFOk', 'Não'))), 
                    str(clean_str(row.get('CaminhoAnexo', '')))
                ]
                if db.update_registro(rid, data_full): sucessos += 1
        except Exception as e: print(e)
            
    callback_atualizar()
    if sucessos > 0: ModernMessageBox.showinfo("Sucesso", f"{sucessos} certificados marcados como OK com sucesso.", parent=app)
    else: ModernMessageBox.showerror("Erro", "O banco de dados rejeitou a alteração.", parent=app)


def marcar_nf_ok(app, tabela, df_registros_global, callback_atualizar):
    selected_iids_str = tabela.selection()
    if not selected_iids_str:
        ModernMessageBox.showwarning("Aviso", "Selecione os itens na tabela primeiro.", parent=app)
        return
    
    ids = [int(i) for i in selected_iids_str]
    count = len(ids)
    if not ModernMessageBox.askyesno("Confirmar", f"Marcar 'NF OK' = 'Sim' para {count} item(ns)?", parent=app): return
    
    sucessos = 0
    for rid in ids:
        try:
            # 1. ATUALIZAÇÃO CIRÚRGICA: Toca apenas no campo da Nota Fiscal
            if hasattr(db, 'update_nf'):
                db.update_nf(rid, "Sim")
                sucessos += 1
            else:
                # 2. Fallback de Segurança: Limpa o formato do Pandas forçando textos e floats puros
                row = df_registros_global.loc[rid]
                data_dt = row.get('Data', pd.NaT)
                data_str = data_dt.strftime("%Y-%m-%d") if pd.notna(data_dt) else ""
                
                data_full = [
                    str(data_str), str(clean_str(row.get('Parceiro', ''))), str(clean_str(row.get('Residuo', ''))),
                    str(clean_str(row.get('Estado', 'Sólido'))), str(clean_str(row.get('Destinacao', ''))),
                    str(clean_str(row.get('Tipo', 'Venda'))), str(clean_str(row.get('Modo', 'kg'))),
                    float(to_float_safe(row.get('Peso', 0))), float(to_float_safe(row.get('ValorPorKg', 0))),
                    float(to_float_safe(row.get('ValorFechado', 0))), float(to_float_safe(row.get('Transporte', 0))),
                    float(to_float_safe(row.get('ValorTotal', 0))), str(clean_str(row.get('PedidoCompra', ''))),
                    str(clean_str(row.get('NumMTR', ''))), str(clean_str(row.get('CertificadoOK', 'Não'))), 
                    float(to_float_safe(row.get('PesoEmKg', 0))), "Sim", 
                    str(clean_str(row.get('CaminhoAnexo', '')))
                ]
                if db.update_registro(rid, data_full): sucessos += 1
        except Exception as e: print(e)
            
    callback_atualizar()
    if sucessos > 0: ModernMessageBox.showinfo("Sucesso", f"{sucessos} Notas Fiscais marcadas como OK com sucesso.", parent=app)
    else: ModernMessageBox.showerror("Erro", "O banco de dados rejeitou a alteração.", parent=app)


def marcar_pendencia_ok(app, pend_tbl, df_registros_global, callback_atualizar, callback_preencher_pend, set_status):
    sel = pend_tbl.focus()
    if not sel: return
    
    try: record_id = int(sel)
    except ValueError: ModernMessageBox.showerror("Erro", f"ID inválido: '{sel}'.", parent=app); return
    
    try:
        reg_series = df_registros_global.loc[record_id]
        data_dt = reg_series['Data']
        parceiro = reg_series['Parceiro']
        residuo = reg_series['Residuo']
        data_str_fmt = data_dt.strftime("%d/%m/%y") if pd.notna(data_dt) else "Sem data"
        
        if ModernMessageBox.askyesno("Confirmar", f"Marcar 'Sim'?\n({data_str_fmt} | {parceiro} | {residuo})?", parent=app):
            try:
                db.update_certificado(record_id, "Sim")
                if record_id in df_registros_global.index: 
                    df_registros_global.loc[record_id, 'CertificadoOK'] = "Sim"
                
                callback_atualizar() 
                callback_preencher_pend()
                set_status("Certificado marcado como 'Sim'.")
            except Exception as e_update: 
                ModernMessageBox.showerror("Erro", f"Não foi possível atualizar: {e_update}", parent=app)
    except KeyError: 
        ModernMessageBox.showwarning("Aviso", f"Registro ID {record_id} não encontrado nos dados principais.", parent=app)
    except Exception as e: 
        ModernMessageBox.showerror("Erro", f"Erro na busca de dados: {e}", parent=app)
