# dashboard_resumo.py
import pandas as pd
import ttkbootstrap as tb
from tkinter import ttk
from utilidades import to_float_safe, fmt_moeda, fmt_kg, clean_str, format_data_ptbr_abbrev, PT_ABREV_LIST
from componentes import ModernMessageBox
import calculos

def atualizar_totais(df, kpis, tot_txt):
    """Calcula totais com 4 categorias e atualiza os cards do dashboard."""
    if tot_txt:
        tot_txt.config(state="normal")
        tot_txt.delete("1.0", "end")
        
    if df.empty:
        if tot_txt:
            tot_txt.insert("end", "Nenhum registro no período.\n")
            tot_txt.config(state="disabled")
        if kpis:
            kpis['vendas'].set("R$ 0,00")
            kpis['custos'].set("R$ 0,00")
            kpis['lucro'].set("R$ 0,00")
            kpis['peso'].set("0 kg")
        return pd.DataFrame()

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

        categoria = 'Sólido'
        if 'líquido' in estado_db or 'liquido' in estado_db:
            categoria = 'Líquido'

        if tipo == 'Venda':
            pass 
        else:
            if any(k in res or k in dest for k in kw_analise):
                categoria = 'Análise'
            elif any(k in res for k in kw_transporte):
                categoria = 'Transporte'
        
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

    total_venda = sum(d['Venda'] for d in dados_resumo.values())
    total_custo = sum(d['Custo'] for d in dados_resumo.values())
    total_peso = sum(d['Peso'] for d in dados_resumo.values())
    lucro = total_venda - total_custo

    if kpis:
        kpis['vendas'].set(fmt_moeda(total_venda))
        kpis['custos'].set(fmt_moeda(total_custo))
        kpis['lucro'].set(fmt_moeda(lucro))
        kpis['peso'].set(fmt_kg(total_peso))

    if tot_txt:
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
        tot_txt.insert("end", "\n".join(linhas))
        tot_txt.config(state="disabled")

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

def preencher_resumo(df, resumo_tree):
    """Preenche a tabela de resumo mensal com cores dinâmicas e proteção contra erros."""
    for r in resumo_tree.get_children(): 
        resumo_tree.delete(r)
    
    try:
        # 1. ALARME 1: O dataframe principal chegou vazio?
        if df is None or df.empty:
            ModernMessageBox.showwarning("Diagnóstico 1", "O dataframe (df) chegou VAZIO na função de resumo. O problema está no filtro de datas ou no banco de dados!")
            return

        rdf_raw, rdf_fmt = calculos.resumo_mensal_df(df)
        
        # 2. ALARME 2: O calculos.py devolveu um resumo vazio?
        if rdf_raw is None or rdf_raw.empty: 
            ModernMessageBox.showwarning("Diagnóstico 2", "O df tem dados, MAS a função calculos.resumo_mensal_df(df) retornou VAZIO. O problema está no arquivo calculos.py!")
            return

        expected_cols = resumo_tree['columns']
        row_num = 0
        
        # Pega as colunas disponíveis para não dar KeyError
        raw_cols = [str(c) for c in rdf_raw.columns]
        fmt_cols = [str(c) for c in rdf_fmt.columns]
        
        # Descobre qual é a verdadeira coluna de Lucro no df bruto (raw)
        col_lucro = None
        for c in raw_cols:
            if 'lucro' in c.lower():
                col_lucro = c
                break

        for idx in rdf_raw.index:
            row_fmt = rdf_fmt.loc[idx]
            values_tuple = []
            
            # Busca flexível de colunas (ignora maiúscula/minúscula)
            for expected_col in expected_cols:
                if expected_col in row_fmt:
                    values_tuple.append(row_fmt[expected_col])
                else:
                    encontrado = ""
                    for fmt_col in fmt_cols:
                        if fmt_col.lower().strip() == str(expected_col).lower().strip():
                            encontrado = row_fmt[fmt_col]
                            break
                    values_tuple.append(encontrado)
            
            # Pega o lucro de forma segura
            lucro_val = 0
            if col_lucro is not None:
                try:
                    lucro_val = float(rdf_raw.loc[idx, col_lucro])
                except (ValueError, TypeError):
                    lucro_val = 0
            
            tags = ["evenrow" if row_num % 2 == 0 else "oddrow"]
            if lucro_val < 0: tags.append("lucro_neg")
            elif lucro_val > 0: tags.append("lucro_pos")
            
            resumo_tree.insert("", "end", iid=str(idx), values=tuple(values_tuple), tags=tuple(tags))
            row_num += 1
            
    except Exception as e: 
        print(f"Erro preencher resumo: {e}")
        try:
            ModernMessageBox.showerror("Erro na Aba Resumo", f"Ocorreu um erro ao processar os dados do resumo mensal:\n\n{e}\n\nVerifique o arquivo calculos.py.")
        except:
            pass
        
def mostrar_detalhes_resumo(app, resumo_tree, df_registros_global):
    """Exibe uma tela com os itens que compõem a linha clicada no resumo."""
    sel = resumo_tree.focus()
    if not sel: return
    
    try:
        item = resumo_tree.item(sel)
        vals = item['values']
        colunas = resumo_tree['columns']
        
        mes_str_original = str(vals[0])
        mes_str = mes_str_original.strip().lower()
        
        df_detalhe = df_registros_global.copy()
        df_detalhe['Data'] = pd.to_datetime(df_detalhe['Data'], errors='coerce')
        
        # 1. Filtra a Data de forma INQUEBRÁVEL (não importa se é mar/26 ou mar/2026)
        partes_data = mes_str.split("/")
        if len(partes_data) == 2:
            m_texto = partes_data[0].strip()
            a_texto = partes_data[1].strip()
            
            try:
                mes_idx = PT_ABREV_LIST.index(m_texto) + 1
                ano_idx = int(a_texto)
                if ano_idx < 100: ano_idx += 2000 # Transforma 26 em 2026
                
                # Filtra exatamente o mês e o ano numérico
                df_detalhe = df_detalhe[
                    (df_detalhe['Data'].dt.month == mes_idx) & 
                    (df_detalhe['Data'].dt.year == ano_idx)
                ]
            except ValueError:
                pass
        
        # 2. Filtra pelas outras colunas
        filtros_debug = []
        for i in [1, 2]:
            if i < len(colunas) and i < len(vals):
                col_nome = str(colunas[i])
                val_celula = str(vals[i]).strip().lower()
                
                db_col = col_nome
                # Traduz qualquer variação de nome de coluna para a coluna real do Banco de Dados
                if col_nome in ["Resíduo", "Residuo"]: db_col = "Residuo"
                if col_nome in ["Destinação", "Destinacao"]: db_col = "Destinacao"
                if col_nome in ["Estado", "estado"]: db_col = "Estado"
                
                if db_col in df_detalhe.columns:
                    filtros_debug.append(f"{db_col}: '{val_celula}'")
                    df_detalhe = df_detalhe[df_detalhe[db_col].astype(str).str.strip().str.lower() == val_celula]

        # 3. Avisa se não achar nada
        if df_detalhe.empty:
            msg = f"Nenhum registro individual encontrado.\n\nO sistema tentou filtrar por:\nMês: '{mes_str}'\n"
            msg += "\n".join(filtros_debug)
            msg += "\n\nSe isso apareceu, há alguma diferença de texto entre o resumo e o banco."
            ModernMessageBox.showinfo("Detalhes", msg, parent=app)
            return

        # 4. Desenha a tela pop-up com os resultados
        top = tb.Toplevel(app)
        top.title(f"Detalhes: {mes_str_original}")
        top.geometry("700x400")
        
        tb.Label(top, text=f"Composição do Mês: {mes_str_original}", font=("Segoe UI", 12, "bold"), bootstyle="primary").pack(pady=10)
        
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
        
        total_peso = 0
        total_valor = 0
        
        for _, row in df_detalhe.iterrows():
            try: d_fmt = row['Data'].strftime("%d/%m/%y")
            except: d_fmt = ""
            
            peso_real = row['PesoEmKg'] if str(row.get('Modo')).lower() == 'unidade' else row['Peso']
            peso_real = to_float_safe(peso_real)
            valor_total = to_float_safe(row['ValorTotal'])
            
            total_peso += peso_real
            total_valor += valor_total
            
            tree_det.insert("", "end", values=(
                d_fmt, clean_str(row['Parceiro']), clean_str(row['Residuo']),
                fmt_kg(peso_real), fmt_moeda(valor_total)
            ))
            
        lbl_resumo = tb.Label(top, text=f"Total Peso: {fmt_kg(total_peso)}  |  Total Financeiro: {fmt_moeda(total_valor)}", font=("Segoe UI", 10, "bold"), bootstyle="inverse-primary")
        lbl_resumo.pack(fill="x", padx=10, pady=10)
        
    except Exception as e:
        ModernMessageBox.showerror("Erro", f"Erro ao abrir detalhes: {e}", parent=app)
        print(e)
