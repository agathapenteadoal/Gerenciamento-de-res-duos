# telas_lote.py
import tkinter as tk
from tkinter import ttk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from decimal import Decimal, ROUND_HALF_UP
import re

import database as db
from componentes import ModernMessageBox, CalendarioPremium, obter_data_segura

def _dec(s, default=Decimal("0")):
    if s is None: return default
    try:
        st = str(s).strip().replace(" ", "")
        if st == "" or st.lower() in ("nan", "none"): return default
        if "," in st and "." in st: st = st.replace(".", "").replace(",", ".")
        else: st = st.replace(",", ".")
        return Decimal(st)
    except:
        try: return Decimal(str(s))
        except: return default

def money_pt(s) -> Decimal: return _dec(s, Decimal("0"))

def fmt_moeda(val) -> str:
    try: d = _dec(val, Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except: d = Decimal("0").quantize(Decimal("0.01"))
    s = f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

def fmt_kg(val) -> str:
    try: d = _dec(val, Decimal("0"))
    except: return "0 kg"
    s = f"{d:.3f}".rstrip("0").rstrip(".")
    if "." in s:
        pi, pd_part = s.split("."); pi = f"{int(pi):,}".replace(",", "."); s = f"{pi},{pd_part}"
    else: s = f"{int(s):,}".replace(",", ".")
    return f"{s} kg"

def abrir_janela_lote(app, parceiros, destinacoes, banco_residuos, banco_dict, func_pular_letra, callback_atualizar):
    lote_win = tb.Toplevel(app)
    lote_win.title("Lançamento de Histórico (Lote)")
    lote_win.geometry("1200x750") 
    
    itens_da_carga = []

    frame_comum = tb.Labelframe(lote_win, text="1. Dados Fixos (Parceiro/Destinação)", padding=15, bootstyle=INFO)
    frame_comum.pack(fill="x", padx=15, pady=15)
    frame_comum.columnconfigure((0,1,2,3), weight=1)

    tb.Label(frame_comum, text="Parceiro:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=5)
    parc_cb = tb.Combobox(frame_comum, values=parceiros, state="readonly")
    if parceiros: parc_cb.current(0)
    parc_cb.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
    
    tb.Label(frame_comum, text="Destinação:", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=5)
    dest_cb = tb.Combobox(frame_comum, values=destinacoes, state="readonly")
    if destinacoes: dest_cb.current(0)
    dest_cb.grid(row=1, column=1, sticky="ew", padx=5, pady=(0, 5))
    
    tb.Label(frame_comum, text="Tipo:", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=5)
    tipo_cb = tb.Combobox(frame_comum, values=["Venda", "Custo"], state="readonly")
    tipo_cb.set("Venda")
    tipo_cb.grid(row=1, column=2, sticky="ew", padx=5, pady=(0, 5))
    
    tb.Label(frame_comum, text="Pedido/Ticket (Opcional):").grid(row=0, column=3, sticky="w", padx=5)
    pedido_entry = tb.Entry(frame_comum)
    pedido_entry.grid(row=1, column=3, sticky="ew", padx=5, pady=(0, 5))

    frame_item = tb.Labelframe(lote_win, text="2. Adicionar Item", padding=15, bootstyle=SUCCESS)
    frame_item.pack(fill="x", padx=15, pady=5)
    frame_item.columnconfigure((0,1,2,3,4), weight=1)
    frame_item.columnconfigure(5, weight=0) 
    
    tb.Label(frame_item, text="Selecione o Resíduo:", font=("Segoe UI", 10, "bold"), bootstyle="primary").grid(row=0, column=0, columnspan=6, sticky="w", padx=5)
    res_lote_var = tk.StringVar()
    res_lote_cb = tb.Combobox(frame_item, textvariable=res_lote_var, values=banco_residuos, state="readonly", font=("Segoe UI", 10))
    res_lote_cb.grid(row=1, column=0, columnspan=6, sticky="ew", padx=5, pady=(5, 15))
    res_lote_cb.bind("<Key>", func_pular_letra)
    
    tb.Label(frame_item, text="Data").grid(row=2, column=0, sticky="w", padx=5)
    tb.Label(frame_item, text="Modo").grid(row=2, column=1, sticky="w", padx=5)
    tb.Label(frame_item, text="Qtd / Peso").grid(row=2, column=2, sticky="w", padx=5)
    lbl_valor = tb.Label(frame_item, text="Valor (R$)")
    lbl_valor.grid(row=2, column=3, sticky="w", padx=5)
    tb.Label(frame_item, text="Estado").grid(row=2, column=4, sticky="w", padx=5)

    dt_item_entry = CalendarioPremium(frame_item, dateformat="%d/%m/%y")
    dt_item_entry.grid(row=3, column=0, sticky="ew", padx=5, pady=(0, 5))
    
    modo_lote_var = tk.StringVar(value="kg")
    modo_cb = tb.Combobox(frame_item, textvariable=modo_lote_var, values=["kg", "fechado", "unidade"], state="readonly")
    modo_cb.grid(row=3, column=1, sticky="ew", padx=5, pady=(0, 5))

    def validate_numeric(P): return P == "" or bool(re.match(r"^[0-9]*[,]?[0-9]*$", P))
    vcmd_num = (app.register(validate_numeric), '%P')

    qtd_entry = tb.Entry(frame_item, validate="key", validatecommand=vcmd_num)
    qtd_entry.grid(row=3, column=2, sticky="ew", padx=5, pady=(0, 5))
    
    valor_entry = tb.Entry(frame_item, validate="key", validatecommand=vcmd_num)
    valor_entry.grid(row=3, column=3, sticky="ew", padx=5, pady=(0, 5))
    
    estado_lote_var = tk.StringVar(value="Sólido")
    estado_cb = tb.Combobox(frame_item, textvariable=estado_lote_var, values=["Sólido", "Líquido"], state="readonly")
    estado_cb.grid(row=3, column=4, sticky="ew", padx=5, pady=(0, 5))

    btn_add = tb.Button(frame_item, text="ADICIONAR (+)", bootstyle="success", width=12) 
    btn_add.grid(row=3, column=5, sticky="ew", padx=(10, 5), pady=(0, 5))

    frame_bottom = tb.Frame(frame_item)
    frame_bottom.grid(row=4, column=0, columnspan=6, sticky="ew", pady=(10, 0))
    
    var_nf_lote = tk.IntVar(value=1)
    var_cert_lote = tk.IntVar(value=1)
    
    tb.Label(frame_bottom, text="Compliance:", bootstyle="secondary").pack(side="left", padx=(5, 10))
    chk_nf = tb.Checkbutton(frame_bottom, text="Exige NF", variable=var_nf_lote, bootstyle="round-toggle")
    chk_nf.pack(side="left", padx=10)
    
    chk_cert = tb.Checkbutton(frame_bottom, text="Exige Certificado", variable=var_cert_lote, bootstyle="round-toggle")
    chk_cert.pack(side="left", padx=10)
    
    info_lbl = tb.Label(frame_bottom, text="", bootstyle="info") 
    info_lbl.pack(side="right", padx=10)

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
            
            var_nf_lote.set(1 if dados.get('exige_nf', True) else 0)
            var_cert_lote.set(1 if dados.get('exige_cert', True) else 0)

            peso_u = dados.get('peso_unitario', 0.0)
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
        except: ModernMessageBox.showerror("Erro", "Data inválida.", parent=lote_win); return

        residuo = res_lote_var.get()
        qtd_str = qtd_entry.get()
        val_str = valor_entry.get()
        if not residuo or not qtd_str: ModernMessageBox.showwarning("Aviso", "Preencha os dados.", parent=lote_win); return
            
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
        dt_item_entry.focus_set()

    btn_add.configure(command=adicionar_item_lista)
    qtd_entry.bind("<Return>", lambda e: adicionar_item_lista())
    valor_entry.bind("<Return>", lambda e: adicionar_item_lista())

    frame_lista = tb.Frame(lote_win, padding=15)
    frame_lista.pack(fill="both", expand=True)
    
    cols = ("Data", "Resíduo", "Modo", "Qtd", "Total", "NF?", "Cert?")
    tree_lote = ttk.Treeview(frame_lista, columns=cols, show="headings", height=8)
    tree_lote.pack(side="left", fill="both", expand=True)
    
    for c in cols: tree_lote.heading(c, text=c); tree_lote.column(c, anchor="center")
    tree_lote.column("Resíduo", width=250, anchor="w") 
    tree_lote.column("Data", width=90)
    tree_lote.column("Total", anchor="e")
    
    sb = ttk.Scrollbar(frame_lista, orient="vertical", command=tree_lote.yview)
    tree_lote.configure(yscroll=sb.set); sb.pack(side="right", fill="y")
    
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

    def salvar_carga_banco():
        if not itens_da_carga: ModernMessageBox.showwarning("Vazio", "Adicione itens.", parent=lote_win); return
        parc = parc_cb.get(); dest = dest_cb.get(); tip = tipo_cb.get(); ped = pedido_entry.get()
        if not parc or not dest: ModernMessageBox.showerror("Erro", "Parceiro/Destino obrigatórios.", parent=lote_win); return

        sucessos = 0
        for item in itens_da_carga:
            reg = [
                item['data_db'], parc, item['residuo'], item['estado'], dest, tip, item['modo'], 
                item['qtd_input'], item['valor_unit'], item['valor_fechado'], 0.0, item['total'], 
                ped, "", item['cert_ok'], item['peso_calc'], item['nf_ok'], ""
            ]

            try:
                rec_id = db.add_registro(reg)
                if rec_id != -1:
                    if hasattr(db, 'update_nf'): db.update_nf(rec_id, item['nf_ok'])
                    sucessos += 1
            except Exception as e: print(f"Erro lote: {e}")

        if sucessos > 0:
            ModernMessageBox.showinfo("Sucesso", f"{sucessos} registros salvos com sucesso!", parent=lote_win)
            lote_win.destroy()
            callback_atualizar()
        else:
            ModernMessageBox.showerror("Erro", "Nenhum registro foi salvo.", parent=lote_win)
            
    tb.Separator(lote_win).pack(fill="x", padx=15, pady=15)
    tb.Button(lote_win, text="CONCLUIR E SALVAR TUDO", bootstyle="success", width=30, command=salvar_carga_banco).pack(fill="x", padx=30, pady=(0,20))
