# calculos.py
import pandas as pd
import numpy as np
from decimal import Decimal, ROUND_HALF_UP, getcontext
from math import isnan
from datetime import datetime, date, timedelta
from pandas.tseries.offsets import MonthEnd
import queue
import locale
import holidays

# Importar funções do seu módulo de banco de dados
import database as db

# --- Constantes e Utilitários ---
getcontext().prec = 28
Q2 = Decimal("0.01")
Q6 = Decimal("0.000001")

try: locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    try: locale.setlocale(locale.LC_TIME, 'pt_BR')
    except locale.Error: print("Aviso (calculos.py): locale pt_BR não ativado.")

PT_ABREV_LIST = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]

# =======================================================
# CONFIGURAÇÃO DE FERIADOS E DIAS NÃO ÚTEIS (AUTOMATIZADO)
# =======================================================

# A lista de datas passa a ser carregada dinamicamente da base de dados
# Sempre que as funções precisarem de DATAS_MANUAIS, podem chamar db.get_datas_manuais()
DATAS_MANUAIS = db.get_datas_manuais()

# 2. Gera os feriados Nacionais automaticamente (Sem state='PR' para não matar o dia 19/12)
feriados_oficiais = holidays.Brazil(years=[2023, 2024, 2025, 2026, 2027])

# 3. Junta as datas manuais com as datas calculadas
HOLIDAYS_BR_2025 = list(set(DATAS_MANUAIS + [data.strftime('%Y-%m-%d') for data in feriados_oficiais]))

# Ordena a lista cronologicamente
HOLIDAYS_BR_2025.sort()

# =======================================================

def _dec(s, default=Decimal("0")):
    if s is None: return default
    st = str(s).strip().replace(" ", "") 
    if st == "" or st.lower() in ("nan", "none"): return default
    if "," in st and "." in st: st = st.replace(".", "").replace(",", ".")
    else: st = st.replace(",", ".")
    try: return Decimal(st)
    except: return default

def fmt_moeda(val) -> str:
    try: d = _dec(val, Decimal("0")).quantize(Q2, rounding=ROUND_HALF_UP)
    except: d = Decimal("0").quantize(Q2)
    s = f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

def fmt_kg(val) -> str:
    try: d = _dec(val, Decimal("0"))
    except: return "0 kg"
    s_num = f"{d:.3f}" 
    s = s_num.rstrip("0").rstrip(".") if '.' in s_num else s_num
    if "." in s:
        pi, pd_part = s.split(".")
        pi = f"{int(pi):,}".replace(",", ".")
        s = f"{pi},{pd_part}"
    else: 
        s = f"{int(s):,}".replace(",", ".")
    return f"{s} kg"

def clean_str(x):
    if x is None: return ""
    s = str(x).strip()
    return "" if s.lower() in ("nan", "none") else s

def to_float_safe(x, default=0.0):
    try: return float(_dec(x, Decimal(str(default))))
    except: return float(default)

def get_df_com_peso_real(df):
    if df.empty: return df
    df_calc = df.copy()
    def calcular_peso(row):
        modo = clean_str(row.get('Modo', 'kg')).lower()
        return to_float_safe(row.get('PesoEmKg', 0.0)) if modo == 'unidade' else to_float_safe(row.get('Peso', 0.0))
    df_calc['Peso_KG_Real'] = df_calc.apply(calcular_peso, axis=1)
    return df_calc

def get_prorated_weights_by_month(dt_inicio, dt_fim):
    df_full = db.get_all_registros_df() 
    df_full_with_weights = get_df_com_peso_real(df_full)
    df_data = df_full_with_weights[df_full_with_weights['Peso_KG_Real'] > 0].copy()
    if df_data.empty: return pd.DataFrame(columns=['Mes_Ano', 'Estado', 'Destinacao', 'Prorated_Weight_KG'])
    
    df_data['Data'] = pd.to_datetime(df_data['Data'], dayfirst=True, errors='coerce')
    df_data = df_data.dropna(subset=['Data'])
    
    meses_para_calcular = pd.date_range(dt_inicio.replace(day=1), dt_fim.replace(day=1), freq='MS')
    prorated_data = [] 

    for mes_date in meses_para_calcular:
        target_month_start = mes_date
        target_month_end = mes_date + MonthEnd(1)
        mes_ano_str = mes_date.strftime("%Y-%m")

        for residue in df_data['Residuo'].unique():
            df_residue = df_data[df_data['Residuo'] == residue].sort_values(by='Data')
            if len(df_residue) < 2: continue 

            for i in range(1, len(df_residue)):
                coll_curr = df_residue.iloc[i]
                coll_prev = df_residue.iloc[i-1]
                d_curr = coll_curr['Data']
                d_prev = coll_prev['Data']
                
                if d_curr < target_month_start or d_prev > target_month_end: continue
                
                # RESTAURADO: Dia útil da coleta atual é incluído, o intervalo começa no dia seguinte à coleta anterior
                d_prev_p1 = d_prev + pd.Timedelta(days=1)
                
                total_gap = np.busday_count(d_prev_p1.date(), (d_curr + pd.Timedelta(days=1)).date(), holidays=HOLIDAYS_BR_2025)
                if total_gap <= 0: continue 
                    
                calc_start = max(d_prev_p1, target_month_start)
                calc_end = min(d_curr, target_month_end)
                days_in_month = np.busday_count(calc_start.date(), (calc_end + pd.Timedelta(days=1)).date(), holidays=HOLIDAYS_BR_2025)

                if days_in_month > 0:
                    share = (days_in_month / total_gap) * float(coll_curr['Peso_KG_Real'])
                    prorated_data.append({
                        'Mes_Ano': mes_ano_str,
                        'Estado': clean_str(coll_curr['Estado']),
                        'Destinacao': clean_str(coll_curr['Destinacao']),
                        'Prorated_Weight_KG': share
                    })
    
    if not prorated_data: return pd.DataFrame(columns=['Mes_Ano', 'Estado', 'Destinacao', 'Prorated_Weight_KG'])
    return pd.DataFrame(prorated_data).groupby(['Mes_Ano', 'Estado', 'Destinacao'])['Prorated_Weight_KG'].sum().reset_index()

def calcular_geracao_para_mes(df_residuo_full, target_month_date):
    start = pd.to_datetime(target_month_date.replace(day=1))
    end = start + MonthEnd(1)
    total = 0.0
    logs = []
    
    if not pd.api.types.is_datetime64_any_dtype(df_residuo_full['Data']):
         df_residuo_full = df_residuo_full.copy()
         df_residuo_full['Data'] = pd.to_datetime(df_residuo_full['Data'], dayfirst=True, errors='coerce')

    for i in range(1, len(df_residuo_full)):
        curr, prev = df_residuo_full.iloc[i], df_residuo_full.iloc[i-1]
        d_c, d_p = curr['Data'], prev['Data']
        if pd.isna(d_c) or pd.isna(d_p) or d_c < start or d_p > end: continue
        
        # RESTAURADO: A contagem inicia amanhã (d_p + 1) e termina no dia da coleta incluído (d_c + 1)
        d_p_p1 = d_p + pd.Timedelta(days=1)
        
        try:
            total_gap = np.busday_count(d_p_p1.date(), (d_c + pd.Timedelta(days=1)).date(), holidays=HOLIDAYS_BR_2025)
            if total_gap <= 0: continue
            
            c_s = max(d_p_p1, start)
            c_e = min(d_c, end)
            days = np.busday_count(c_s.date(), (c_e + pd.Timedelta(days=1)).date(), holidays=HOLIDAYS_BR_2025)
            
            if days > 0:
                share = (days / total_gap) * float(curr['Peso_KG_Real'])
                total += share
                logs.append(f" - Coleta {d_c:%d/%m/%y}: ({days}/{total_gap}) * {curr['Peso_KG_Real']:.2f} = {share:.2f} kg")
        except: continue
    return total, logs

def calcular_relatorio_esg_data(dt_inicio, dt_fim):
    relatorio = [
        "RELATÓRIO DE INDICADORES ESG (GESTÃO DE RESÍDUOS)",
        f"Período de Análise: {dt_inicio:%d/%m/%Y} a {dt_fim:%d/%m/%Y}",
        "==================================================",
        ""
    ]
    try:
        df_prorated = get_prorated_weights_by_month(dt_inicio, dt_fim)
        df_real = df_prorated[~df_prorated['Destinacao'].isin(["Análise externa", "N/A"])]
    except Exception as e: return f"ERRO NO PROCESSAMENTO: {e}"

    relatorio.append("--- 1. INDICADORES DE DESTINAÇÃO (PESO RATEADO) --- \n")
    if df_real.empty:
        relatorio.append("Nenhum resíduo movimentado no período selecionado.")
    else:
        df_dest = df_real.groupby('Destinacao')['Prorated_Weight_KG'].sum().sort_values(ascending=False)
        total_periodo = df_dest.sum()
        relatorio.append(f"PESO TOTAL DESTINADO: {fmt_kg(total_periodo)}")
        relatorio.append("_" * 50)
        for dest, peso in df_dest.items():
            perc = (peso / total_periodo) * 100 if total_periodo > 0 else 0
            relatorio.append(f"\n {dest:<30} {fmt_kg(peso):>12} ({perc:>5.1f}%)")
    relatorio.append("\n" + "--- 2. INDICADOR DE ECOEFICIÊNCIA (kg/m²) ---\n")
    
    meses_range = pd.date_range(dt_inicio.replace(day=1), dt_fim.replace(day=1), freq='MS').strftime("%Y-%m")
    total_m2 = Decimal("0")
    log_m2 = []
    
    for m in sorted(meses_range):
        val = _dec(db.get_metragem(m))
        total_m2 += val
        dt_m = datetime.strptime(m, "%Y-%m")
        sigla = PT_ABREV_LIST[dt_m.month-1]
        txt_m2 = f"{val:.2f} m²" if val > 0 else "0,00 m² (NÃO LANÇADO)"
        log_m2.append(f"  - {sigla}/{dt_m.strftime('%y')}: {txt_m2}")

    relatorio.extend(log_m2)
    relatorio.append("_" * 50)

    if total_m2 <= 0:
        relatorio.append("AVISO: Metragem total é zero. Favor preencher na aba Configurações.")
    else:
        DEST_REC = ["Reciclagem", "Compostagem", "Logística reversa"]
        DEST_NAO_REC = ["Blendagem para coprocessamento", "Incineração", "Aterro Industrial"]
        DEST_LIQ = ["Tratamento de efluentes"]

        def get_sum(estado, lista):
            mask = (df_real['Estado'] == estado) & (df_real['Destinacao'].isin(lista))
            return _dec(df_real[mask]['Prorated_Weight_KG'].sum())

        w_sol_rec = get_sum('Sólido', DEST_REC)
        w_sol_n_rec = get_sum('Sólido', DEST_NAO_REC)
        w_liq = get_sum('Líquido', DEST_LIQ)

        relatorio.append(f"\n1. Sólidos Recicláveis/m²: {(w_sol_rec/total_m2):.2f} kg/m²")
        relatorio.append(f"2. Sólidos Não Recicláveis/ m²: {(w_sol_n_rec/total_m2):.2f} kg/m²")
        relatorio.append(f"3. Líquidos (Efluentes)/m²: {(w_liq/total_m2):.2f} kg/m²")
        relatorio.append("_" * 30)

    return "\n".join(relatorio)

def calcular_relatorio_geracao_data(dt_inicio, dt_fim, residuo_str_ou_lista, df_global):
    # Aceita nome único ou lista (ex: todas as bombonas)
    residuos = residuo_str_ou_lista if isinstance(residuo_str_ou_lista, list) else [residuo_str_ou_lista]
    
    meses = pd.date_range(dt_inicio.replace(day=1), dt_fim.replace(day=1), freq='MS')
    dict_meses = { m: {"Realizado": 0.0, "Previsao": 0.0, "Total": 0.0} for m in meses }
    
    total_geral_periodo = 0.0
    soma_medias_diarias = 0.0
    memoria_calc = []

    for res in residuos:
        df_calc = get_df_com_peso_real(df_global[df_global['Residuo'] == res])
        # 1. Remove pesos zerados
        df_calc = df_calc[df_calc['Peso_KG_Real'] > 0]
        
        # 2. Agrupa coletas feitas no mesmo dia e soma os pesos (evita divisão por zero)
        df_calc = df_calc.groupby('Data', as_index=False).agg({'Peso_KG_Real': 'sum'})
        
        # 3. Ordena cronologicamente
        df_calc = df_calc.sort_values('Data')
        
        if len(df_calc) < 2: continue

        # Calcula média do ciclo individual deste item
        last, prev = df_calc.iloc[-1], df_calc.iloc[-2]
        d_l, d_p = pd.to_datetime(last['Data']), pd.to_datetime(prev['Data'])
        gap = np.busday_count((d_p + pd.Timedelta(days=1)).date(), (d_l + pd.Timedelta(days=1)).date(), holidays=HOLIDAYS_BR_2025)
        avg = float(last['Peso_KG_Real']) / gap if gap > 0 else 0
        soma_medias_diarias += avg
        
        memoria_calc.append(f"\n=== PROCESSANDO: {res.upper()} ===")

        for m in meses:
            t_real, logs_mes = calcular_geracao_para_mes(df_calc, m)
            if logs_mes:
                memoria_calc.append(f"--- {PT_ABREV_LIST[m.month-1].upper()}/{m.year} ---")
                memoria_calc.extend(logs_mes)

            # --- NOVA LÓGICA DE PREVISÃO SOLICITADA ---
            t_prev = 0.0
            m_end = m + MonthEnd(1)
            
            # Só projeta se o fim do mês for depois da última coleta registrada do resíduo
            if m_end > d_l:
                # 1. Dias úteis do início do mês 'm' até a última coleta 'd_l'
                # Limitamos o início ao próprio mês caso a última coleta venha de um ciclo muito longo
                inicio_contagem_mes = max(m, df_calc['Data'].min()) 
                
                dias_uteis_ate_ultima = np.busday_count(
                    inicio_contagem_mes.date(), 
                    (d_l + pd.Timedelta(days=1)).date(), 
                    holidays=HOLIDAYS_BR_2025
                )
                
                # 2. Dias úteis que faltam para acabar o mês (do dia seguinte à última coleta até o fim do mês)
                proj_start = d_l + pd.Timedelta(days=1)
                proj_end = min(m_end, pd.to_datetime(dt_fim))
                
                dias_que_faltam = 0
                if proj_start <= proj_end:
                    dias_que_faltam = np.busday_count(
                        proj_start.date(), 
                        (proj_end + pd.Timedelta(days=1)).date(), 
                        holidays=HOLIDAYS_BR_2025
                    )
                
                # 3. Faz o cálculo se houver dias úteis decorridos para evitar divisão por zero
                if dias_uteis_ate_ultima > 0 and dias_que_faltam > 0:
                    # t_real é a quantidade total mandada/coletada dentro deste mês 'm' até agora
                    avg_mes = float(t_real) / dias_uteis_ate_ultima
                    t_prev = avg_mes * dias_que_faltam
                    
                    memoria_calc.append(
                        f"  * Projeção do Mês: ({t_real:.2f} kg / {dias_uteis_ate_ultima} d.ú. decorridos) "
                        f"x {dias_que_faltam} d.ú. restantes = {t_prev:.2f} kg"
                    )
            # -------------------------------------

            m_total = t_real + t_prev

            # Acumula os valores deste item no total do mês do grupo
            dict_meses[m]["Realizado"] += t_real
            dict_meses[m]["Previsao"] += t_prev
            dict_meses[m]["Total"] += m_total
            total_geral_periodo += m_total

    linhas_tabela = []
    for m in meses:
        linhas_tabela.append({
            "Mes": f"{PT_ABREV_LIST[m.month-1]}/{m.year}",
            "Realizado": dict_meses[m]["Realizado"],
            "Previsao": dict_meses[m]["Previsao"],
            "Total": dict_meses[m]["Total"]
        })

    return {
        "linhas": linhas_tabela,
        "total_geral": total_geral_periodo,
        "media_diaria": soma_medias_diarias,
        "memoria": "\n".join(memoria_calc)
    }

def resumo_mensal_df(df):
    cols = ["Mês", "Estado", "Destinacao", "Peso", "Vendas", "Custos", "Transporte", "Lucro"]
    empty = pd.DataFrame(columns=cols)
    
    if df.empty: 
        return empty, empty
        
    # Removido o try/except genérico para não engolir erros silenciosamente
    d = df.copy()
    
    # 1. Proteção de Data (se todas as datas forem inválidas, ele para antes de quebrar)
    if 'Data' not in d.columns: return empty, empty
    d['Data'] = pd.to_datetime(d['Data'], dayfirst=True, errors='coerce') 
    d = d.dropna(subset=['Data'])
    if d.empty: return empty, empty
    
    d["Periodo"] = d["Data"].dt.to_period("M")
    
    # 2. Busca flexível de colunas de texto (evita KeyError)
    d['Estado'] = d.get('Estado', 'N/A')
    d['Destinacao'] = d.get('Destinacao', d.get('Destinação', 'N/A'))
    d['Tipo'] = d.get('Tipo', 'Venda')
    d['Modo'] = d.get('Modo', 'kg')
    
    # 3. Busca e conversão flexível de colunas numéricas
    for c in ["Peso", "ValorPorKg", "ValorFechado", "Transporte"]:
        if c not in d.columns:
            d[c] = 0.0
        else:
            d[c] = pd.to_numeric(d[c].apply(to_float_safe), errors='coerce').fillna(0.0)
            
    # 4. Cálculos
    d['ValorBase'] = d.apply(lambda r: (r['ValorPorKg'] * r['Peso'] if str(r.get('Modo','')).lower() in ('kg', 'ton', 'unidade') else r['ValorFechado']), axis=1)
    
    d['Tipo_Norm'] = d['Tipo'].astype(str).str.lower().str.strip()
    d['Venda_Calc'] = np.where(d['Tipo_Norm'] == 'venda', d['ValorBase'], 0.0)
    d['Custo_Calc'] = np.where(d['Tipo_Norm'] == 'custo', d['ValorBase'], 0.0)
    
    # 5. Agrupamento (GroupBy)
    out = d.groupby(["Periodo", "Estado", "Destinacao"]).agg(
        Peso=("Peso", "sum"), 
        Vendas=("Venda_Calc", "sum"), 
        Custos=("Custo_Calc", "sum"), 
        Transporte=("Transporte", "sum")
    ).reset_index()
    
    # 6. Finalização e Formatação
    out["Lucro"] = out["Vendas"] - out["Custos"] - out["Transporte"]
    out = out.sort_values(["Periodo", "Estado", "Destinacao"]).reset_index(drop=True)
    out["Mês"] = out["Periodo"].apply(lambda p: f"{PT_ABREV_LIST[p.month-1]}/{p.year}")
    
    out_fmt = out.copy()
    for c, f in {"Peso": fmt_kg, "Vendas": fmt_moeda, "Custos": fmt_moeda, "Transporte": fmt_moeda, "Lucro": fmt_moeda}.items():
        if c in out_fmt.columns:
            out_fmt[c] = out_fmt[c].apply(f)
            
    return out[cols], out_fmt[cols]

# --- NOVA FUNÇÃO SINIR ---
def gerar_relatorio_sinir(df_registros, dt_inicio, dt_fim):
    if df_registros.empty: return pd.DataFrame()
    df = df_registros.copy()
    df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
    start = pd.to_datetime(dt_inicio)
    end = pd.to_datetime(dt_fim) + pd.Timedelta(days=1, seconds=-1)
    mask = (df['Data'] >= start) & (df['Data'] <= end)
    df = df.loc[mask]
    if df.empty: return pd.DataFrame()

    df_calc = get_df_com_peso_real(df)
    df_residuos = db.get_banco_residuos()
    df_parceiros = db.get_banco_parceiros()
    
    if 'CodigoIBAMA' in df_residuos.columns:
        df_calc = df_calc.merge(df_residuos[['Residuo', 'CodigoIBAMA']], on='Residuo', how='left')
    else:
        df_calc['CodigoIBAMA'] = "Não Cadastrado"

    if 'CNPJ' in df_parceiros.columns:
        df_calc = df_calc.merge(df_parceiros[['Parceiro', 'CNPJ']], on='Parceiro', how='left')
    else:
        df_calc['CNPJ'] = "Não Cadastrado"

    agrupamento = ['CodigoIBAMA', 'Residuo', 'Estado', 'CNPJ', 'Parceiro', 'Destinacao']
    agg_funcs = {
        'Peso_KG_Real': 'sum',
        'NumMTR': lambda x: ', '.join(set([str(i) for i in x if str(i).strip() and str(i).lower() != 'nan']))
    }
    df_sinir = df_calc.groupby(agrupamento, dropna=False).agg(agg_funcs).reset_index()
    df_sinir['Quantidade (t)'] = (df_sinir['Peso_KG_Real'] / 1000).round(4)
    df_sinir.rename(columns={
        'Residuo': 'Descrição do Resíduo',
        'Estado': 'Estado Físico',
        'Parceiro': 'Razão Social (Destinador)',
        'Destinacao': 'Tecnologia de Destinação',
        'NumMTR': 'MTRs Vinculados',
        'Peso_KG_Real': 'Quantidade (kg)'
    }, inplace=True)
    colunas_finais = [
        'CodigoIBAMA', 'Descrição do Resíduo', 'Estado Físico', 
        'Quantidade (t)', 'Quantidade (kg)', 
        'CNPJ', 'Razão Social (Destinador)', 'Tecnologia de Destinação', 'MTRs Vinculados'
    ]
    return df_sinir[colunas_finais]


# =======================================================
# DMR (DECLARAÇÃO DE MOVIMENTAÇÃO DE RESÍDUOS) - SINIR
# =======================================================
DESTINACOES_INVALIDAS_DMR = {"", "n/a", "na", "análise externa", "analise externa"}
DESTINACOES_FORA_DMR = {"logística reversa", "logistica reversa"}  # Não são declaradas na DMR

def periodo_trimestre(ano, trimestre):
    """Primeiro e último dia do trimestre (1 a 4) do ano."""
    mes_ini = 3 * (int(trimestre) - 1) + 1
    inicio = date(int(ano), mes_ini, 1)
    fim = (pd.Timestamp(inicio) + pd.DateOffset(months=3) - pd.Timedelta(days=1)).date()
    return inicio, fim

def ultimo_trimestre_fechado(hoje=None):
    """(ano, trimestre) do último trimestre completo — o que normalmente vai ser declarado."""
    hoje = hoje or date.today()
    tri_atual = (hoje.month - 1) // 3 + 1
    return (hoje.year - 1, 4) if tri_atual == 1 else (hoje.year, tri_atual - 1)

def formatar_codigo_ibama(codigo):
    """'161001' -> '16 10 01' (formato da Lista Brasileira de Resíduos). Mantém o '(*)' se houver."""
    txt = clean_str(codigo)
    if not txt: return ""
    perigoso = "*" in txt
    digitos = "".join(ch for ch in txt if ch.isdigit())
    if len(digitos) != 6: return txt
    return f"{digitos[0:2]} {digitos[2:4]} {digitos[4:6]}" + ("(*)" if perigoso else "")

def formatar_cnpj(cnpj):
    digitos = "".join(ch for ch in clean_str(cnpj) if ch.isdigit())
    if len(digitos) != 14: return clean_str(cnpj)
    return f"{digitos[0:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:14]}"

def _eh_servico(residuo):
    """Análises, fretes e locações não são resíduos: ficam fora da DMR."""
    nome = clean_str(residuo).upper()
    return nome.startswith(("[ANÁLISE]", "[ANALISE]", "[FRETE]", "LOCAÇÃO", "LOCACAO"))

def preparar_dmr(df_registros, dt_inicio, dt_fim):
    """Monta os dados da DMR do período e a lista do que precisa ser corrigido antes de declarar.

    Retorna um dict com DataFrames: 'resumo', 'por_codigo', 'por_mes', 'lancamentos',
    'pendencias' e 'ignorados'.
    """
    vazio = {k: pd.DataFrame() for k in ("resumo", "por_codigo", "por_mes", "lancamentos", "pendencias", "ignorados")}
    if df_registros is None or df_registros.empty: return vazio

    df = df_registros.copy()
    if 'id' not in df.columns: df = df.reset_index().rename(columns={'index': 'id'})
    df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
    fim = pd.to_datetime(dt_fim) + pd.Timedelta(days=1, seconds=-1)
    df = df[(df['Data'] >= pd.to_datetime(dt_inicio)) & (df['Data'] <= fim)]
    if df.empty: return vazio

    df = get_df_com_peso_real(df)
    df['Residuo'] = df['Residuo'].map(clean_str)
    df['Parceiro'] = df['Parceiro'].map(clean_str)
    df['Destinacao'] = df['Destinacao'].map(clean_str)

    residuos = db.get_banco_residuos()
    parceiros = db.get_banco_parceiros()

    # --- O que fica fora da DMR (e por quê) ---
    nao_entra = {clean_str(r) for r, e in zip(residuos.get('Residuo', []), residuos.get('EntraDMR', []))
                 if str(e) in ('0', '0.0', 'False')}
    def motivo_fora(row):
        if _eh_servico(row['Residuo']): return "Análise / frete / locação"
        if row['Destinacao'].lower() in DESTINACOES_FORA_DMR: return row['Destinacao']
        if row['Residuo'] in nao_entra: return "Resíduo marcado como 'não entra na DMR'"
        return ""
    df['Motivo'] = df.apply(motivo_fora, axis=1)
    ignorados = df[df['Motivo'] != ""]
    sem_peso = df[(df['Motivo'] == "") & (df['Peso_KG_Real'] <= 0)]
    df = df[(df['Motivo'] == "") & (df['Peso_KG_Real'] > 0)].copy()
    if df.empty:
        vazio['ignorados'] = ignorados[['Data', 'Residuo', 'Parceiro', 'Destinacao', 'Peso_KG_Real', 'Motivo']]
        return vazio
    mapa_ibama = {clean_str(r): clean_str(c) for r, c in zip(residuos.get('Residuo', []), residuos.get('CodigoIBAMA', []))}
    mapa_cnpj = {clean_str(p): clean_str(c) for p, c in zip(parceiros.get('Parceiro', []), parceiros.get('CNPJ', []))}
    df['CodigoIBAMA'] = df['Residuo'].map(lambda r: formatar_codigo_ibama(mapa_ibama.get(r, "")))
    df['CNPJ'] = df['Parceiro'].map(lambda p: formatar_cnpj(mapa_cnpj.get(p, "")))
    df['Mes'] = df['Data'].dt.month

    # --- Pendências: o que impede uma declaração correta ---
    pend = []
    for residuo, grp in df[df['CodigoIBAMA'] == ""].groupby('Residuo'):
        pend.append({"Problema": "Resíduo sem código IBAMA", "Item": residuo,
                     "Lançamentos": len(grp), "Peso (kg)": round(grp['Peso_KG_Real'].sum(), 2),
                     "Como resolver": "Configurações › Resíduos › Editar › Código IBAMA"})
    for parceiro, grp in df[df['CNPJ'] == ""].groupby('Parceiro'):
        pend.append({"Problema": "Destinador sem CNPJ", "Item": parceiro or "(sem parceiro)",
                     "Lançamentos": len(grp), "Peso (kg)": round(grp['Peso_KG_Real'].sum(), 2),
                     "Como resolver": "Configurações › Parceiros › Editar › CNPJ"})
    dest_inval = df['Destinacao'].str.lower().isin(DESTINACOES_INVALIDAS_DMR)
    for (residuo, destino), grp in df[dest_inval].groupby(['Residuo', 'Destinacao']):
        datas = ", ".join(sorted({d.strftime('%d/%m') for d in grp['Data']}))
        pend.append({"Problema": f"Destinação inválida ('{destino or 'vazia'}')", "Item": residuo,
                     "Lançamentos": len(grp), "Peso (kg)": round(grp['Peso_KG_Real'].sum(), 2),
                     "Como resolver": f"Aba Registros › editar o lançamento ({datas}) e corrigir a Destinação"})
    for residuo, grp in sem_peso.groupby('Residuo'):
        datas = ", ".join(sorted({d.strftime('%d/%m') for d in grp['Data']}))
        pend.append({"Problema": "Lançamento sem peso (fora da DMR)", "Item": residuo,
                     "Lançamentos": len(grp), "Peso (kg)": 0.0,
                     "Como resolver": f"Aba Registros › editar o lançamento ({datas}) e informar o peso"})
    pendencias = pd.DataFrame(pend, columns=["Problema", "Item", "Lançamentos", "Peso (kg)", "Como resolver"])

    # --- Resumo: uma linha por resíduo x destinador x tecnologia ---
    chaves = ['CodigoIBAMA', 'Residuo', 'Estado', 'Parceiro', 'CNPJ', 'Destinacao']
    resumo = df.groupby(chaves, dropna=False).agg(
        Peso_kg=('Peso_KG_Real', 'sum'), Lancamentos=('Peso_KG_Real', 'size')
    ).reset_index().sort_values(['CodigoIBAMA', 'Residuo', 'Parceiro'])
    resumo.insert(6, 'Quantidade (t)', (resumo['Peso_kg'] / 1000).round(4))
    resumo = resumo.rename(columns={
        'CodigoIBAMA': 'Código IBAMA', 'Residuo': 'Resíduo', 'Estado': 'Estado Físico',
        'Parceiro': 'Destinador', 'CNPJ': 'CNPJ Destinador', 'Destinacao': 'Tecnologia de Destinação',
        'Peso_kg': 'Quantidade (kg)', 'Lancamentos': 'Nº Lançamentos'})

    # --- Total por código IBAMA (para conferir com o que o SINIR mostra) ---
    df['_codigo'] = df['CodigoIBAMA'].replace("", "SEM CÓDIGO")
    por_codigo = df.groupby('_codigo').agg(
        Peso_kg=('Peso_KG_Real', 'sum'),
        Residuos=('Residuo', lambda x: ", ".join(sorted(set(x)))),
        Destinadores=('Parceiro', lambda x: ", ".join(sorted({p for p in x if p}))),
    ).reset_index()
    por_codigo.insert(1, 'Quantidade (t)', (por_codigo['Peso_kg'] / 1000).round(4))
    por_codigo.insert(0, 'Conferido', "")
    por_codigo = por_codigo.rename(columns={'_codigo': 'Código IBAMA', 'Peso_kg': 'Quantidade (kg)',
                                            'Residuos': 'Resíduos incluídos', 'Destinadores': 'Destinadores'})

    # --- Por mês (kg) ---
    por_mes = df.pivot_table(index=['_codigo', 'Residuo'], columns='Mes', values='Peso_KG_Real', aggfunc='sum', fill_value=0)
    por_mes.columns = [PT_ABREV_LIST[int(m) - 1].capitalize() + " (kg)" for m in por_mes.columns]
    por_mes['Total (kg)'] = por_mes.sum(axis=1)
    por_mes = por_mes.reset_index().rename(columns={'_codigo': 'Código IBAMA', 'Residuo': 'Resíduo'})

    # --- Lançamentos (detalhe para conferência) ---
    lanc = df.sort_values('Data')[['Data', 'CodigoIBAMA', 'Residuo', 'Estado', 'Parceiro', 'CNPJ', 'Destinacao', 'Peso_KG_Real', 'PedidoCompra']].copy()
    lanc['Data'] = lanc['Data'].dt.strftime('%d/%m/%Y')
    lanc = lanc.rename(columns={'CodigoIBAMA': 'Código IBAMA', 'Residuo': 'Resíduo', 'Estado': 'Estado Físico',
                                'Parceiro': 'Destinador', 'CNPJ': 'CNPJ Destinador', 'Destinacao': 'Tecnologia de Destinação',
                                'Peso_KG_Real': 'Peso (kg)', 'PedidoCompra': 'Pedido de Compra'})

    ign = ignorados.sort_values('Data')[['Data', 'Residuo', 'Parceiro', 'Destinacao', 'Peso_KG_Real', 'Motivo']].copy()
    ign['Data'] = pd.to_datetime(ign['Data']).dt.strftime('%d/%m/%Y')
    ign = ign.rename(columns={'Residuo': 'Resíduo', 'Parceiro': 'Parceiro', 'Destinacao': 'Destinação', 'Peso_KG_Real': 'Peso (kg)'})

    return {"resumo": resumo, "por_codigo": por_codigo, "por_mes": por_mes,
            "lancamentos": lanc, "pendencias": pendencias, "ignorados": ign}
