# graficos.py
import pandas as pd
import matplotlib.ticker as mtick
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

# --- Funções Auxiliares de Formatação (Copiadas para o módulo ser independente) ---
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

def to_float_safe(x, default=0.0):
    try: return float(_dec(x, Decimal(str(default))))
    except: return float(default)

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
        pi, pd_part = s.split(".")
        pi = f"{int(pi):,}".replace(",", ".")
        s = f"{pi},{pd_part}"
    else: 
        s = f"{int(s):,}".replace(",", ".")
    return f"{s} kg"

PT_ABREV_LIST = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]

# =====================================================================
# FUNÇÕES DE PLOTAGEM DOS GRÁFICOS
# =====================================================================

def atualizar_grafico_barras(df, ax, canvas, fig_bar, cores):
    ax.clear()
    ax.set_facecolor(cores['bg'])
    if fig_bar: fig_bar.set_facecolor(cores['bg'])

    if df.empty or 'Data' not in df.columns or df['Data'].isnull().all():
        ax.set_title("Sem dados no período", color=cores['fg'], fontsize=10)
        canvas.draw(); return

    try:
        d = df.copy()
        d['Data'] = pd.to_datetime(d['Data'], errors='coerce')
        d = d.dropna(subset=['Data'])
        d["Periodo"] = d["Data"].dt.to_period("M")
        d["ValorTotal"] = d["ValorTotal"].apply(to_float_safe)
        
        piv = d.pivot_table(index="Periodo", columns="Tipo", values="ValorTotal", aggfunc="sum", fill_value=0)
        if "Venda" not in piv.columns: piv["Venda"] = 0.0
        if "Custo" not in piv.columns: piv["Custo"] = 0.0
        piv = piv[["Venda", "Custo"]]
        
        def formatar_eixo_x(periodo):
            try:
                ts = periodo.to_timestamp()
                try: mes_str = PT_ABREV_LIST[ts.month - 1]
                except: mes_str = str(ts.month)
                return f"{mes_str}/{ts.year}"
            except: return str(periodo)

        piv.index = piv.index.map(formatar_eixo_x)
        piv.index.name = ""

        paleta = [cores['info'], cores['danger']]
        piv.plot(kind="bar", ax=ax, color=paleta, rot=0)

        ax.set_title("Financeiro (Vendas x Custos)", color=cores['fg'], fontsize=10, weight='bold')
        ax.legend(title="", fontsize=8, facecolor=cores['bg'], labelcolor=cores['fg'])
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, p: f'R$ {x:,.0f}'.replace(',', '.')))
        ax.yaxis.grid(True, linestyle=':', which='major', color=cores['grid'], alpha=0.4)
        ax.set_axisbelow(True)
        
        ax.tick_params(axis='x', colors=cores['fg'], labelsize=8, rotation=45)
        ax.tick_params(axis='y', colors=cores['fg'], labelsize=8)
        
        for spine in ['top', 'right']: ax.spines[spine].set_visible(False)
        for spine in ['left', 'bottom']: 
            ax.spines[spine].set_color(cores['grid'])
            ax.spines[spine].set_linewidth(0.5)

        if fig_bar: fig_bar.tight_layout(pad=1.5)
        canvas.draw()
    except Exception as e:
        print(f"Erro barras: {e}"); ax.set_title(f"Erro", color="red", fontsize=8); canvas.draw()

def atualizar_grafico_pie_custo(df, ax, canvas, fig_pie, cores):
    ax.clear()
    ax.set_facecolor(cores['bg'])
    if fig_pie: fig_pie.set_facecolor(cores['bg'])

    if df.empty or 'ValorTotal' not in df.columns or 'Residuo' not in df.columns:
        ax.text(0.5, 0.5, "Sem dados", ha='center', va='center', color=cores['fg'])
        canvas.draw(); return

    try:
        custos = df[df['Tipo'] == 'Custo'].copy()
        if custos.empty: 
            ax.text(0.5, 0.5, "R$ 0,00", ha='center', va='center', color=cores['fg'])
            canvas.draw(); return
            
        custos['ValorTotal'] = custos['ValorTotal'].apply(to_float_safe)
        total_val = custos['ValorTotal'].sum()
        
        top_custos = custos.groupby('Residuo')['ValorTotal'].sum().nlargest(5).sort_values(ascending=False)
        top_custos = top_custos[top_custos > 0]
        
        if top_custos.empty: 
            ax.text(0.5, 0.5, "R$ 0,00", ha='center', va='center', color=cores['fg'])
            canvas.draw(); return
            
        soma_outros = total_val - top_custos.sum()
        if soma_outros > 0.01: top_custos['Outros'] = soma_outros

        paleta = ['#3498db', '#e74c3c', '#f1c40f', '#2ecc71', '#9b59b6', '#95a5a6']
        wedges, texts = ax.pie(
            top_custos, startangle=90, colors=paleta[:len(top_custos)],
            wedgeprops={'width': 0.25, 'edgecolor': cores['bg'], 'linewidth': 3}
        )

        ax.text(0, 0.15, "Total Custos", ha='center', va='center', fontsize=8, color=cores['fg'], alpha=0.7)
        ax.text(0, -0.05, fmt_moeda(total_val), ha='center', va='center', fontsize=10, fontweight='bold', color=cores['fg'])
        ax.set_title("Top 5 Custos", color=cores['fg'], fontsize=10, weight='bold')

        legend_labels = []
        for nome, valor in top_custos.items():
            pct = (valor / total_val) * 100
            nome_limpo = str(nome).replace("[ANÁLISE] ", "").replace("[ANÁLISE]", "")
            nome_limpo = nome_limpo.replace("[TRANSPORTE] ", "").replace("[TRANSPORTE]", "Transporte")
            nome_curto = (nome_limpo[:15] + '..') if len(nome_limpo) > 15 else nome_limpo
            legend_labels.append(f"{nome_curto} | {pct:.1f}% ({fmt_moeda(valor)})")

        ax.legend(wedges, legend_labels, loc="center left", bbox_to_anchor=(1.0, 0.5), ncol=1, fontsize=8, frameon=False, labelcolor=cores['fg'])

        if fig_pie: fig_pie.subplots_adjust(left=0.0, bottom=0.1, right=0.55, top=0.9)
        canvas.draw()
        
    except Exception as e: 
        print(f"Erro pie custo: {e}"); ax.text(0.5, 0.5, "Erro", ha='center', color='red'); canvas.draw()

def atualizar_grafico_pie_peso(df, ax, canvas, fig_pie, cores):
    ax.clear()
    ax.set_facecolor(cores['bg'])
    if fig_pie: fig_pie.set_facecolor(cores['bg'])

    if df.empty or 'Peso' not in df.columns:
        ax.text(0.5, 0.5, "Sem dados", ha='center', va='center', color=cores['fg'])
        canvas.draw(); return

    try:
        df_peso = df.copy()
        col_peso = 'PesoEmKg' if 'PesoEmKg' in df_peso.columns else 'Peso'
        df_peso['Peso_Calc'] = df_peso[col_peso].apply(to_float_safe)
        total_val = df_peso['Peso_Calc'].sum()
        
        top_peso = df_peso.groupby('Parceiro')['Peso_Calc'].sum().nlargest(5).sort_values(ascending=False)
        top_peso = top_peso[top_peso > 0]
        
        if top_peso.empty: 
            ax.text(0.5, 0.5, "0 kg", ha='center', va='center', color=cores['fg'])
            canvas.draw(); return
            
        soma_outros = total_val - top_peso.sum()
        if soma_outros > 0.01: top_peso['Outros'] = soma_outros

        paleta = ['#1abc9c', '#3498db', '#9b59b6', '#34495e', '#16a085', '#7f8c8d']
        wedges, texts = ax.pie(
            top_peso, startangle=90, colors=paleta[:len(top_peso)],
            wedgeprops={'width': 0.25, 'edgecolor': cores['bg'], 'linewidth': 3}
        )

        ax.text(0, 0.15, "Peso Total", ha='center', va='center', fontsize=8, color=cores['fg'], alpha=0.7)
        ax.text(0, -0.05, fmt_kg(total_val), ha='center', va='center', fontsize=10, fontweight='bold', color=cores['fg'])
        ax.set_title("Top 5 Volumes", color=cores['fg'], fontsize=10, weight='bold')

        legend_labels = []
        for nome, valor in top_peso.items():
            pct = (valor / total_val) * 100
            nome_curto = (nome[:12] + '..') if len(nome) > 12 else nome
            legend_labels.append(f"{nome_curto} | {pct:.1f}% ({fmt_kg(valor)})")

        ax.legend(wedges, legend_labels, loc="center left", bbox_to_anchor=(1.0, 0.5), ncol=1, fontsize=8, frameon=False, labelcolor=cores['fg'])

        if fig_pie: fig_pie.subplots_adjust(left=0.0, bottom=0.1, right=0.55, top=0.9)
        canvas.draw()
        
    except Exception as e: 
        print(f"Erro pie peso: {e}"); ax.text(0.5, 0.5, "Erro", ha='center', color='red'); canvas.draw()

def atualizar_grafico_lucro_residuo(df, ax, canvas, fig_lucro, cores):
    ax.clear()
    ax.set_facecolor(cores['bg'])
    if fig_lucro: fig_lucro.set_facecolor(cores['bg'])

    if df.empty or 'Data' not in df.columns or df['Data'].isnull().all():
        ax.text(0.5, 0.5, "Sem dados", ha='center', va='center', color=cores['fg'])
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
        
        if len(resumo) > 10: top_bottom = pd.concat([resumo.head(5), resumo.tail(5)])
        else: top_bottom = resumo

        if top_bottom.empty: 
            ax.text(0.5, 0.5, "Sem Lucro/Prejuízo", ha='center', color=cores['fg'])
            canvas.draw(); return

        clean_index = []
        for nome in top_bottom.index:
            nome_limpo = str(nome).replace("[ANÁLISE] ", "").replace("[ANÁLISE]", "")
            nome_limpo = nome_limpo.replace("[TRANSPORTE] ", "Transporte ").replace("[TRANSPORTE]", "Transporte ")
            if len(nome_limpo) > 25: nome_limpo = nome_limpo[:22] + "..."
            clean_index.append(nome_limpo)
        top_bottom.index = clean_index

        paleta = ['#2ecc71' if x >= 0 else '#e74c3c' for x in top_bottom['Lucro']]
        bars = ax.barh(top_bottom.index, top_bottom['Lucro'], color=paleta, height=0.6)
        ax.axvline(0, color=cores['fg'], linewidth=0.8, alpha=0.3)

        max_val = top_bottom['Lucro'].abs().max()
        offset_value = max_val * 0.02 
        offset_name = max_val * 0.05  

        for i, bar in enumerate(bars):
            width = bar.get_width()
            label_y = bar.get_y() + bar.get_height() / 2
            nome_residuo = top_bottom.index[i]
            
            if width >= 0:
                ax.text(-offset_name, label_y, nome_residuo, va='center', ha='right', fontsize=8, color=cores['fg'])
                ax.text(width + offset_value, label_y, fmt_moeda(width), va='center', ha='left', fontsize=8, color=cores['fg'], fontweight='bold')
            else:
                ax.text(offset_name, label_y, nome_residuo, va='center', ha='left', fontsize=8, color=cores['fg'])
                ax.text(width - offset_value, label_y, fmt_moeda(width), va='center', ha='right', fontsize=8, color=cores['fg'], fontweight='bold')

        ax.set_title("Lucro/Prejuízo por Resíduo", color=cores['fg'], fontsize=10, weight='bold')
        ax.set_xticks([]); ax.set_yticks([]) 
        
        for spine in ax.spines.values(): spine.set_visible(False)

        if fig_lucro: fig_lucro.subplots_adjust(left=0.2, bottom=0.05, right=0.8, top=0.9)
        canvas.draw()
        
    except Exception as e: 
        print(f"Erro grafico lucro: {e}"); ax.text(0.5, 0.5, "Erro", ha='center', color='red'); canvas.draw()
        
def atualizar_grafico_evolucao(df_global, ax, canvas, fig_evol, cores):
    ax.clear()
    ax.set_facecolor(cores['bg'])
    if fig_evol: fig_evol.set_facecolor(cores['bg'])
    
    try:
        hoje = datetime.now()
        data_inicio_12m = hoje - timedelta(days=375)
        
        d = df_global.copy()
        d = d.dropna(subset=['Data'])
        d = d[d['Data'] >= data_inicio_12m]
        
        if d.empty:
            ax.set_title("Sem dados nos últimos 12 meses", color=cores['fg'], fontsize=9)
            canvas.draw(); return

        d['Peso_Real'] = d.apply(lambda r: (r['PesoEmKg'] if str(r.get('Modo','')).lower() == 'unidade' else r['Peso']), axis=1)
        d['Peso_Real'] = d['Peso_Real'].apply(to_float_safe)
        d['MesAno'] = d['Data'].dt.to_period('M')
        evolucao = d.groupby('MesAno')['Peso_Real'].sum()
        
        idx_periodo = pd.period_range(start=data_inicio_12m, end=hoje, freq='M')
        evolucao = evolucao.reindex(idx_periodo, fill_value=0)
        
        x_labels = [f"{PT_ABREV_LIST[p.month-1]}/{p.year%100:02d}" for p in evolucao.index]
        
        ax.plot(x_labels, evolucao.values, marker='o', linestyle='-', linewidth=2, color=cores['info'])
        ax.fill_between(x_labels, evolucao.values, color=cores['info'], alpha=0.1)

        ax.set_title("Evolução do Peso (kg)", color=cores['fg'], fontsize=10, weight='bold')
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, p: f'{x:,.0f}'.replace(',', '.')))
        ax.grid(True, linestyle=':', which='major', color=cores['grid'], alpha=0.4)
        
        ax.tick_params(axis='x', colors=cores['fg'], labelsize=7, rotation=45)
        ax.tick_params(axis='y', colors=cores['fg'], labelsize=7)
        
        for spine in ['top', 'right']: ax.spines[spine].set_visible(False)
        for spine in ['left', 'bottom']: 
            ax.spines[spine].set_color(cores['grid'])
            ax.spines[spine].set_linewidth(0.5)
            
        for i, v in enumerate(evolucao.values):
            if v > 0:
                ax.text(i, v + (max(evolucao.values)*0.05), f"{v:.0f}", color=cores['fg'], ha='center', fontsize=6)

        if fig_evol: fig_evol.tight_layout(pad=1)
        canvas.draw()
        
    except Exception as e:
        print(f"Erro evolução: {e}"); ax.set_title("Erro", color=cores['fg']); canvas.draw()

def atualizar_grafico_estado_financeiro(df, ax, canvas, fig_estado, cores):
    ax.clear()
    ax.set_facecolor(cores['bg'])
    if fig_estado: fig_estado.set_facecolor(cores['bg'])

    if df.empty:
        ax.text(0.5, 0.5, "Sem dados", ha='center', va='center', color=cores['fg'])
        canvas.draw(); return

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
            tipo = str(row.get('Tipo', 'Venda')) 
            
            v_total = to_float_safe(row.get('ValorTotal', 0))
            v_transp = to_float_safe(row.get('Transporte', 0))
            
            categoria = 'Sólido' 
            if 'líquido' in estado_db or 'liquido' in estado_db: categoria = 'Líquido'

            if tipo == 'Venda': pass 
            else:
                if any(k in res or k in dest for k in kw_analise): categoria = 'Análise'
                elif any(k in res for k in kw_transporte): categoria = 'Transporte'
            
            if v_transp > 0: dados['Transporte']['Custo'] += v_transp
            val_material = v_total - v_transp
            
            if abs(val_material) > 0.001:
                if categoria in ['Análise', 'Transporte']: dados[categoria]['Custo'] += val_material
                else:
                    if tipo == 'Venda': dados[categoria]['Venda'] += v_total 
                    elif tipo == 'Custo': dados[categoria]['Custo'] += val_material

        df_plot = pd.DataFrame(dados).T[['Custo', 'Venda']]
        
        if df_plot.sum().sum() == 0:
             ax.text(0.5, 0.5, "Sem movimentação", ha='center', color=cores['fg'])
             canvas.draw(); return

        paleta = [cores['danger'], cores['success']]
        df_plot.plot(kind='bar', ax=ax, color=paleta, rot=0, width=0.8)

        ax.set_title("Custos vs Vendas por Categoria", color=cores['fg'], fontsize=10, weight='bold')
        ax.set_xlabel("")
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, p: f'{x/1000:.0f}k' if x >= 1000 else f'{x:.0f}'))
        ax.legend(title="", fontsize=8, facecolor=cores['bg'], labelcolor=cores['fg'])
        ax.grid(axis='y', linestyle=':', color=cores['grid'], alpha=0.4)
        
        ax.tick_params(colors=cores['fg'], labelsize=8)
        for spine in ['top', 'right']: ax.spines[spine].set_visible(False)
        for spine in ['left', 'bottom']: ax.spines[spine].set_color(cores['grid'])
        
        for container in ax.containers:
            labels = [fmt_moeda(v) if v > 0 else "" for v in container.datavalues]
            ax.bar_label(container, labels=labels, padding=2, fontsize=7, color=cores['fg'])

        if fig_estado: fig_estado.tight_layout(pad=1)
        canvas.draw()

    except Exception as e:
        print(f"Erro estado fin: {e}"); ax.set_title(f"Erro", color='red', fontsize=8); canvas.draw()
