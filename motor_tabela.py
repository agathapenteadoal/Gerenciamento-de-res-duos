# motor_tabela.py
import pandas as pd
from datetime import datetime, timedelta, date
import tkinter as tk
from utilidades import clean_str, to_float_safe, fmt_moeda, fmt_kg, format_data_ptbr_abbrev
from componentes import obter_data_segura

def atualizar_menus_dinamicos(base, f_vars, menus):
    """Atualiza as Comboboxes de filtro (Parceiro, Resíduo, Destinação)."""
    if base.empty: 
        parc_set, res_set, dest_set = [], [], []
    else:
        parc_set = sorted({clean_str(x) for x in base["Parceiro"].astype("string").fillna("") if clean_str(x)})
        res_set = sorted({clean_str(x) for x in base["Residuo"].astype("string").fillna("") if clean_str(x)})
        dest_set = sorted({clean_str(x) for x in base["Destinacao"].astype("string").fillna("") if clean_str(x)})

    lista_parc = ["Todos"] + parc_set
    menus['parc'].configure(values=lista_parc)
    if f_vars['parc'].get() not in lista_parc: f_vars['parc'].set("Todos")

    lista_res = ["Todos"] + res_set
    menus['res'].configure(values=lista_res)
    if f_vars['res'].get() not in lista_res: f_vars['res'].set("Todos")

    lista_dest = ["Todas"] + dest_set
    menus['dest'].configure(values=lista_dest)
    if f_vars['dest'].get() not in lista_dest: f_vars['dest'].set("Todas")

def aplicar_filtros(df, f_vars):
    """Aplica os filtros selecionados na interface ao DataFrame."""
    if df.empty: return df
    d = df.copy()

    dt_inicio = None
    dt_fim = None
    try:
        dt_inicio_raw = obter_data_segura(f_vars['data_inicio'])
        dt_fim_raw = obter_data_segura(f_vars['data_fim'])
        
        if dt_inicio_raw is not None: 
            dt_inicio = pd.to_datetime(dt_inicio_raw)
        if dt_fim_raw is not None: 
            dt_fim = pd.to_datetime(dt_fim_raw) + timedelta(days=1, seconds=-1)

        if pd.notna(dt_inicio) and pd.notna(dt_fim):
            if dt_inicio <= dt_fim:
                d = d.dropna(subset=['Data']) 
                d = d[(d["Data"] >= dt_inicio) & (d["Data"] <= dt_fim)]
    except Exception as e:
        print(f"ERRO ao processar datas do filtro: {e}")

    if f_vars['parc'].get() != "Todos" and 'Parceiro' in d.columns:
        d = d[d["Parceiro"] == f_vars['parc'].get()]

    if f_vars['res'].get() != "Todos" and 'Residuo' in d.columns:
        d = d[d["Residuo"] == f_vars['res'].get()]

    if f_vars['estado'].get() != "Todas" and 'Estado' in d.columns:
        d = d[d["Estado"] == f_vars['estado'].get()]

    if f_vars['dest'].get() != "Todas" and 'Destinacao' in d.columns:
        d = d[d["Destinacao"] == f_vars['dest'].get()]

    if f_vars['tipo'].get() != "Todos" and 'Tipo' in d.columns:
        d = d[d["Tipo"] == f_vars['tipo'].get()]

    q = clean_str(f_vars['busca'].get()).lower()
    if q:
        conditions = []
        if 'Parceiro' in d.columns: conditions.append(d["Parceiro"].str.lower().str.contains(q, na=False))
        if 'PedidoCompra' in d.columns: conditions.append(d["PedidoCompra"].astype(str).str.contains(q, na=False))
        
        if conditions:
            final_condition = conditions[0]
            for cond in conditions[1:]: final_condition = final_condition | cond
            d = d[final_condition] 
        else: 
            return pd.DataFrame(columns=df.columns) 

    if 'Data' in d.columns:
        d = d.sort_values(by='Data', ascending=True)
            
    return d

def preencher_tabela(tabela, df):
    """Preenche a tabela formatando as linhas com as tags de cores."""
    for r in tabela.get_children(): tabela.delete(r)
    
    if df.empty: return
    hoje = date.today()
    
    for i, row in df.iterrows():
        tags = []
        estado_val = clean_str(row.get("Estado", "")).lower()
        
        if "sólido" in estado_val or "solido" in estado_val:
            tags.append("estado_solido")
        elif "líquido" in estado_val or "liquido" in estado_val:
            tags.append("estado_liquido")
        else:
            tags.append("evenrow" if i % 2 == 0 else "oddrow")

        cert_val_raw = clean_str(row.get("CertificadoOK", "")).lower()
        is_cert_ok = cert_val_raw in ("sim", "ok", "true", "1", "yes")
        is_cert_na = cert_val_raw in ("n/a", "na", "dispensado")
        
        data_registro = row.get('Data')
        if not is_cert_ok and not is_cert_na and pd.notna(data_registro):
            try:
                d_reg = data_registro.date() if isinstance(data_registro, datetime) else data_registro
                if isinstance(d_reg, date) and (hoje - d_reg).days > 30:
                    tags.append("atrasado")
            except: pass

        tipo_val = clean_str(row.get("Tipo", "")).lower()
        if tipo_val == "venda": tags.append("tipo_venda")
        elif tipo_val == "custo": tags.append("tipo_custo")
        
        if is_cert_ok: icon_cert = "✔"
        elif is_cert_na: icon_cert = ""
        else: icon_cert = "✖"; tags.append("cert_nao")

        nf_val_raw = clean_str(row.get("NFOk", "")).lower()
        if nf_val_raw in ("sim", "ok", "true", "1", "yes"):
            icon_nf = "✔"; tags.append("nf_ok")
        elif "solicitado" in nf_val_raw:
            icon_nf = "⏳"; tags.append("nf_solicitado")
        elif nf_val_raw in ("n/a", "na", "dispensado"): 
            icon_nf = ""
        else: 
            icon_nf = "✖"; tags.append("nf_nao")

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
            s_un = f"{peso:.0f}"
            peso_real_kg = to_float_safe(row.get("PesoEmKg", 0))
            peso_display = f"{s_un} un ({fmt_kg(peso_real_kg)})" if peso_real_kg > 0 else f"{s_un} un"

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

def ordenar_coluna(tabela, col, reverse):
    """Ordena a tabela clicando no cabeçalho."""
    data = [(tabela.set(k, col), k) for k in tabela.get_children("")]
    def to_key(v):
        v_str = str(v)
        if col in ("Peso","Valor por kg","Valor fechado","Transporte","Valor Total"):
            s = v_str.replace("R$","").replace("kg","").replace("un","").replace(" ","").replace(".","").replace(",",".")
            # Limpa parênteses caso seja unidade (ex: "10 un (20 kg)")
            if "(" in s: s = s.split("(")[0]
            try: return float(s)
            except ValueError: return 0.0
        elif col == "Data":
            try: return datetime.strptime(v_str, "%d/%b/%y")
            except ValueError: return datetime.min
        return v_str.lower()
        
    try:
        data.sort(key=lambda x: to_key(x[0]), reverse=reverse)
    except Exception as e:
        print(f"Erro ao ordenar coluna {col}: {e}")
        return
        
    for i, (_, k) in enumerate(data):
        try: tabela.move(k, "", i)
        except tk.TclError: continue
        
    tabela.heading(col, command=lambda c=col: ordenar_coluna(tabela, c, not reverse))

def atualizar_resumo_selecao(tabela, df_registros_global, resumo_selecao_var):
    """Atualiza a barra de status de seleção com a soma do peso e dinheiro."""
    selected_iids = tabela.selection()
    
    if not selected_iids:
        resumo_selecao_var.set("")
        return
    
    total_peso = 0.0
    total_valor = 0.0
    
    for iid_str in selected_iids:
        try:
            record_id = int(iid_str)
            row_data = df_registros_global.loc[record_id]
            
            total_valor += to_float_safe(row_data.get("ValorTotal", 0.0))
            modo = clean_str(row_data.get('Modo', 'kg')).lower()
            
            if modo == 'unidade':
                total_peso += to_float_safe(row_data.get('PesoEmKg', 0.0))
            else:
                total_peso += to_float_safe(row_data.get('Peso', 0.0))
                
        except Exception:
            continue 
    
    count = len(selected_iids)
    s_peso = fmt_kg(total_peso)
    s_valor = fmt_moeda(total_valor)
    resumo_str = f"Seleção: {count} {'item' if count == 1 else 'itens'} | Total Peso: {s_peso} | Total Valor: {s_valor}"
    resumo_selecao_var.set(resumo_str)
