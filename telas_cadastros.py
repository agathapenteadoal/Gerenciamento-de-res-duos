# telas_cadastros.py
import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import re
from decimal import Decimal

import database as db
from componentes import ModernMessageBox

# Funções auxiliares locais para manter o módulo independente
def clean_str(x):
    if x is None: return ""
    s = str(x).strip()
    return "" if s.lower() in ("nan", "none") else s

def to_float_safe(x, default=0.0):
    try:
        st = str(x).strip().replace(" ", "")
        if "," in st and "." in st: st = st.replace(".", "").replace(",", ".")
        else: st = st.replace(",", ".")
        return float(Decimal(st))
    except:
        return float(default)

def money_pt(s):
    return to_float_safe(s)

def abrir_janela_gerenciar_residuo(app, nome_antigo, banco_dict, grupos_relatorio, destinacoes, parceiros, vcmd_numeric, callback_sucesso, set_status):
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
    tb.Combobox(col_esq, textvariable=grupo_var, values=grupos_relatorio, state="readonly").grid(row=r, column=1, sticky="ew", pady=5); r+=1
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
            else: ModernMessageBox.showerror("Erro", "Não foi possível atualizar.", parent=edit_window)
        else:
            if db.add_residuo(nome_novo, nome_nf_novo, codigo_item_novo, codigo_ibama_novo, modo_novo, val_kg, val_fec, val_pu, calcula_rateio_novo, p_estado, p_dest, p_tipo, p_parc, grupo_novo, v_exige_nf, v_exige_cert):
                success = True; set_status(f"Resíduo '{nome_novo}' adicionado.")
            else: ModernMessageBox.showerror("Erro", "Não foi possível adicionar.", parent=edit_window)

        if success:
            if is_edit_mode:
                nf_bool = bool(exige_nf_var.get()); cert_bool = bool(exige_cert_var.get())
                msg = f"As regras de compliance para '{nome_novo}' foram salvas.\nDeseja atualizar TODOS os registros passados com essas novas regras?"
                if ModernMessageBox.askyesno("Atualizar Histórico?", msg, parent=edit_window):
                    if db.update_compliance_historico(nome_novo, nf_bool, cert_bool): ModernMessageBox.showinfo("Sucesso", "Registros atualizados!", parent=edit_window)
                    else: ModernMessageBox.showerror("Erro", "Falha ao atualizar.", parent=edit_window)
            edit_window.destroy()
            callback_sucesso() # Atualiza a tabela na tela principal
            
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

def abrir_janela_gerenciar_parceiro(app, nome_antigo, df_parceiros, parceiros_lista, callback_sucesso, set_status):
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
            if nome_novo in parceiros_lista: 
                ModernMessageBox.showerror("Erro", f"'{nome_novo}' já existe.", parent=edit_window)
                return

        success = False
        if is_edit_mode:
            if db.update_parceiro(nome_antigo, nome_novo, tipo_novo, cnpj_novo): 
                success = True; set_status("Atualizado.")
            else: 
                ModernMessageBox.showerror("Erro", "Falha ao atualizar.", parent=edit_window)
        else:
            if db.add_parceiro(nome_novo, tipo_novo, cnpj_novo): 
                success = True; set_status("Adicionado.")
            else: 
                ModernMessageBox.showerror("Erro", "Falha ao adicionar.", parent=edit_window)

        if success: 
            edit_window.destroy()
            callback_sucesso()

    tb.Button(button_frame, text="Cancelar", command=edit_window.destroy, bootstyle=SECONDARY).pack(side="right", padx=(10, 0))
    save_text = "Salvar" if is_edit_mode else "Adicionar"
    tb.Button(button_frame, text=save_text, command=salvar_dados_parceiro, bootstyle=SUCCESS).pack(side="right")
    
    edit_window.update_idletasks()
    x = app.winfo_x() + (app.winfo_width() // 2) - (edit_window.winfo_width() // 2)
    y = app.winfo_y() + (app.winfo_height() // 2) - (edit_window.winfo_height() // 2)
    edit_window.geometry(f"+{x}+{y}")
    edit_window.wait_window()

def abrir_janela_gerenciar_analise(app, nome_antigo, analises_dict, vcmd_numeric, callback_sucesso, set_status):
    is_edit_mode = (nome_antigo is not None)
    valor_atual = 0.0
    if is_edit_mode:
        valor_atual = analises_dict.get(nome_antigo, 0.0)
    
    edit_window = tb.Toplevel(app)
    title = f"Editar Análise: {nome_antigo}" if is_edit_mode else "Adicionar Nova Análise"
    edit_window.title(title)
    edit_window.geometry("450x250") 
    edit_window.resizable(False, False)
    edit_window.transient(app); edit_window.grab_set() 

    main_frame = tb.Frame(edit_window, padding=15)
    main_frame.pack(fill="both", expand=True)
    main_frame.columnconfigure(1, weight=1) 

    nome_var = tk.StringVar(value=nome_antigo if is_edit_mode else "")
    valor_var = tk.StringVar(value=f"{valor_atual:.2f}".replace(".", ","))

    row_num = 0
    tb.Label(main_frame, text="Nome da Análise:").grid(row=row_num, column=0, sticky="w", padx=(0,10), pady=5)
    tb.Entry(main_frame, textvariable=nome_var).grid(row=row_num, column=1, sticky="ew", pady=5)
    row_num += 1
    
    tb.Label(main_frame, text="Valor Padrão (R$):").grid(row=row_num, column=0, sticky="w", padx=(0,10), pady=5)
    tb.Entry(main_frame, textvariable=valor_var, validate="key", validatecommand=vcmd_numeric).grid(row=row_num, column=1, sticky="ew", pady=5)
    row_num += 1

    button_frame = tb.Frame(main_frame)
    button_frame.grid(row=row_num, column=0, columnspan=2, pady=(20, 0), sticky="e")

    def salvar_dados_analise():
        nome_novo = clean_str(nome_var.get())
        valor_novo = money_pt(valor_var.get()) 
        
        if not nome_novo:
            ModernMessageBox.showerror("Erro", "O nome da análise não pode ser vazio.", parent=edit_window)
            return
        
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
                ModernMessageBox.showerror("Erro", "Não foi possível atualizar a análise.", parent=edit_window)
        else:
            if db.add_analise(nome_novo, float(valor_novo)):
                success = True
                set_status(f"Análise '{nome_novo}' adicionada.")
            else:
                 ModernMessageBox.showerror("Erro", "Não foi possível adicionar a análise.", parent=edit_window)

        if success:
            edit_window.destroy()
            callback_sucesso()
            
    btn_cancelar = tb.Button(button_frame, text="Cancelar", command=edit_window.destroy, bootstyle=SECONDARY)
    btn_cancelar.pack(side="right", padx=(10, 0))
    save_text = "Salvar Alterações" if is_edit_mode else "Adicionar Análise"
    btn_salvar = tb.Button(button_frame, text=save_text, command=salvar_dados_analise, bootstyle=SUCCESS)
    btn_salvar.pack(side="right")

    edit_window.update_idletasks()
    x = app.winfo_x() + (app.winfo_width() // 2) - (edit_window.winfo_width() // 2)
    y = app.winfo_y() + (app.winfo_height() // 2) - (edit_window.winfo_height() // 2)
    edit_window.geometry(f"+{x}+{y}")
    edit_window.wait_window()
