# database.py
import sqlite3
import pandas as pd
import os
from decimal import Decimal, ROUND_HALF_UP, getcontext
from math import isnan
import unicodedata
from datetime import datetime, date, timedelta
import logging

# --- Nome DB ---
DB_FILE = "residuos_db.sqlite"

# --- Colunas Registros ---
COLUMNS_DB = [
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"), ("Data", "TEXT"), ("Parceiro", "TEXT"),
    ("Residuo", "TEXT"), ("Estado", "TEXT"), ("Destinacao", "TEXT"), ("Tipo", "TEXT"),
    ("Modo", "TEXT"), ("Peso", "REAL"), ("ValorPorKg", "REAL"), ("ValorFechado", "REAL"),
    ("Transporte", "REAL"), ("ValorTotal", "REAL"), ("PedidoCompra", "TEXT"),
    ("NumMTR", "TEXT"), ("CertificadoOK", "TEXT"), ("PesoEmKg", "REAL DEFAULT 0.0"), ("NFOk", "TEXT DEFAULT 'Não'"),
    ("CaminhoAnexo", "TEXT DEFAULT ''")
]

# --- Funções Auxiliares ---
logging.basicConfig(
    filename='erros_sistema.log', 
    level=logging.ERROR, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

getcontext().prec = 28
Q2 = Decimal("0.01")
def _dec(s, default=Decimal("0")):
    if s is None:
        return default
    try:
        st = str(s).strip().replace(" ", "")
        if st == "" or st.lower() in ("nan", "none"):
            return default
        if "," in st and "." in st:
            st = st.replace(".", "").replace(",", ".")
        else:
            st = st.replace(",", ".")
        return Decimal(st)
    except Exception:
        try:
            return Decimal(str(s))
        except Exception:
            return default
        
def clean_str(x):
    if x is None:
        return ""
    try:
        if isinstance(x, (float, Decimal)) and isnan(float(x)):
            return ""
    except (TypeError, ValueError): 
        pass
    s = str(x).strip()
    return "" if s.lower() in ("nan", "none") else s

def to_float_safe(x, default=0.0):
    d = _dec(x, Decimal(str(default))) 
    try:
        return float(d)
    except Exception:
        return float(default) 

def parse_data_ptbr_series(s):
    PT_ABREV = { "jan":"01","fev":"02","mar":"03","abr":"04","mai":"05","jun":"06", "jul":"07","ago":"08","set":"09","out":"10","nov":"11","dez":"12" }
    if not isinstance(s, pd.Series):
        s = pd.Series(s)
    s = s.astype("string").fillna("").str.strip()
    out = pd.Series(pd.NaT, index=s.index, dtype='datetime64[ns]')

    mask_excel_num = s.str.match(r"^\d+(\.0*)?$", na=False)
    if mask_excel_num.any():
        num_dates = pd.to_numeric(s[mask_excel_num], errors="coerce")
        out.loc[mask_excel_num] = pd.to_datetime(num_dates, unit='D', origin='1899-12-30', errors="coerce")

    rem_mask = out.isna()
    if rem_mask.any():
        mask_iso = s[rem_mask].str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)
        if mask_iso.any():
            idx_iso = s[rem_mask][mask_iso].index
            out.loc[idx_iso] = pd.to_datetime(s.loc[idx_iso], format="%Y-%m-%d", errors="coerce")

    rem_mask = out.isna()
    if rem_mask.any():
        mask_pt = s[rem_mask].str.match(r"^\d{1,2}/[A-Za-z]{3}/\d{2}$", na=False)
        if mask_pt.any():
            idx_pt = s[rem_mask][mask_pt].index
            partes = s.loc[idx_pt].str.split("/", n=2, expand=True)
            if not partes.empty and partes.shape[1] >= 3:
                mes_num = partes[1].str.lower().map(PT_ABREV).fillna(partes[1])
                s_norm = partes[0].str.zfill(2) + "/" + mes_num + "/" + partes[2].str.zfill(2)
                out.loc[idx_pt] = pd.to_datetime(s_norm, format="%d/%m/%y", errors="coerce")

    rem_mask = out.isna()
    if rem_mask.any():
        mask_num4 = s[rem_mask].str.match(r"^\d{1,2}/\d{1,2}/\d{4}$", na=False)
        if mask_num4.any():
            idx_num4 = s[rem_mask][mask_num4].index
            out.loc[idx_num4] = pd.to_datetime(s.loc[idx_num4], dayfirst=True, errors="coerce")

    rem_mask = out.isna()
    if rem_mask.any():
        mask_num2 = s[rem_mask].str.match(r"^\d{1,2}/\d{1,2}/\d{2}$", na=False)
        if mask_num2.any():
            idx_num2 = s[rem_mask][mask_num2].index
            out.loc[idx_num2] = pd.to_datetime(s.loc[idx_num2], dayfirst=True, errors="coerce")

    rem_mask = out.isna()
    if rem_mask.any():
        out.loc[rem_mask] = pd.to_datetime(s[rem_mask], dayfirst=True, errors="coerce")

    return out

# --- Conexão e Criação de Tabelas ---
def connect_db(): return sqlite3.connect(DB_FILE, timeout=10)

def create_tables():
    conn = connect_db(); cursor = conn.cursor()
    
    cols_sql = ", ".join([f'"{name}" {dtype}' for name, dtype in COLUMNS_DB])
    cursor.execute(f"CREATE TABLE IF NOT EXISTS registros ({cols_sql})")
    
    cursor.execute("PRAGMA table_info(registros)")
    cols_registros = [col[1] for col in cursor.fetchall()]
    if 'PesoEmKg' not in cols_registros: cursor.execute("ALTER TABLE registros ADD COLUMN PesoEmKg REAL DEFAULT 0.0")
    if 'NFOk' not in cols_registros: cursor.execute("ALTER TABLE registros ADD COLUMN NFOk TEXT DEFAULT 'Não'")
    if 'CaminhoAnexo' not in cols_registros: cursor.execute("ALTER TABLE registros ADD COLUMN CaminhoAnexo TEXT DEFAULT ''")

    # --- Tabela Residuos ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS residuos (
        Residuo TEXT PRIMARY KEY,
        NomeNF TEXT DEFAULT '',
        CodigoItem TEXT DEFAULT '',
        CodigoIBAMA TEXT DEFAULT '',
        ModoPadrao TEXT DEFAULT 'kg',
        ValorPorKgPadrao REAL DEFAULT 0.0,
        ValorFechadoPadrao REAL DEFAULT 0.0,
        PesoUnitarioKgPadrao REAL DEFAULT 0.0,
        CalculaRateio INTEGER DEFAULT 0,
        NomePDFPadrao TEXT DEFAULT '',
        EstadoPadrao TEXT DEFAULT '',
        DestinacaoPadrao TEXT DEFAULT '',
        TipoPadrao TEXT DEFAULT '',
        ParceiroPadrao TEXT DEFAULT '',
        Grupo TEXT DEFAULT '',
        ExigeNF INTEGER DEFAULT 1,
        ExigeCertificado INTEGER DEFAULT 1
        )
    """)

    # --- MIGRAÇÃO AUTOMÁTICA RESIDUOS ---
    cursor.execute("PRAGMA table_info(residuos)")
    cols_residuos = [col[1] for col in cursor.fetchall()]
    
    colunas_check_residuos = [
        ('Grupo', "TEXT DEFAULT ''"),
        ('ExigeNF', "INTEGER DEFAULT 1"),           
        ('ExigeCertificado', "INTEGER DEFAULT 1"),   
        ('CodigoIBAMA', "TEXT DEFAULT ''")
    ]
    for col_name, col_def in colunas_check_residuos:
        if col_name not in cols_residuos:
            cursor.execute(f"ALTER TABLE residuos ADD COLUMN {col_name} {col_def}")
            
    # --- Tabela Parceiros e Migração CNPJ ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS parceiros (
        Parceiro TEXT PRIMARY KEY,
        TipoParceiro TEXT DEFAULT 'Destinador',
        CNPJ TEXT DEFAULT ''
    )
    """)
    cursor.execute("PRAGMA table_info(parceiros)")
    cols_parceiros = [col[1] for col in cursor.fetchall()]
    if 'CNPJ' not in cols_parceiros: 
        cursor.execute("ALTER TABLE parceiros ADD COLUMN CNPJ TEXT DEFAULT ''")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_data ON registros (Data)")

    conn.commit(); conn.close()
    print("Tabelas verificadas/atualizadas com sucesso.")
        
# --- CRUD Registros ---
def add_registro(data_full): 
    conn = connect_db(); cursor = conn.cursor(); last_id = -1
    col_names = [f'"{c[0]}"' for c in COLUMNS_DB if c[0] != 'id'] 
    placeholders = ", ".join(["?"] * len(col_names)) 
    sql = f"INSERT INTO registros ({', '.join(col_names)}) VALUES ({placeholders})"

    if len(data_full) != len(col_names):
         print(f"Erro em add_registro: Número incorreto de valores fornecidos. Esperado: {len(col_names)}, Recebido: {len(data_full)}")
         conn.close()
         return -1 

    try:
        cursor.execute(sql, data_full) 
        conn.commit()
        last_id = cursor.lastrowid
    except Exception as e:
        print(f"Erro em add_registro: {e}")
        conn.rollback()
    finally:
        conn.close()
    return last_id

def update_registro(id, data_full):
    conn = connect_db(); cursor = conn.cursor()
    col_updates = [f'"{c[0]}" = ?' for c in COLUMNS_DB if c[0] != 'id'] 
    sql = f"UPDATE registros SET {', '.join(col_updates)} WHERE id = ?"

    if len(data_full) != len(col_updates):
         print(f"Erro em update_registro: Número incorreto de valores fornecidos. Esperado: {len(col_updates)}, Recebido: {len(data_full)}")
         conn.close(); return

    try:
        cursor.execute(sql, data_full + [id]) 
        conn.commit()
    except Exception as e:
        print(f"Erro em update_registro para ID {id}: {e}")
        conn.rollback()
    finally:
        conn.close()

def delete_residuo(nome):
    conn = connect_db(); cursor = conn.cursor(); success = False
    try:
        cursor.execute("DELETE FROM residuos WHERE Residuo = ?", (nome,))
        conn.commit()
        success = True
    except Exception as e:
        print(f"Erro em delete_residuo: {e}")
        conn.rollback()
    finally:
        conn.close()
    return success

def get_all_registros_df(data_inicio=None):
    conn = connect_db()
    expected_cols = [c[0] for c in COLUMNS_DB] 

    try:
        if data_inicio:
            query = f"SELECT * FROM registros WHERE Data >= '{data_inicio}' ORDER BY Data ASC"
        else:
            query = "SELECT * FROM registros ORDER BY Data ASC"

        df = pd.read_sql_query(query, conn, index_col='id', parse_dates=['Data'])
        if 'PesoEmKg' not in df.columns: df['PesoEmKg'] = 0.0 

    except Exception as e:
        print(f"Erro em get_all_registros_df: {e}")
        df = pd.DataFrame(columns=expected_cols[1:]) 
        df.index.name = 'id'
    finally:
        conn.close()

    for col in expected_cols:
        if col != 'id' and col not in df.columns:
            dtype_info = next((item[1] for item in COLUMNS_DB if item[0] == col), "TEXT")
            df[col] = pd.NA if "TEXT" in dtype_info else 0.0

    if df.index.name != 'id': df.index.name = 'id'
    cols_finais = [col for col in expected_cols if col != 'id']
    df = df[cols_finais]

    return df

def update_certificado(id, novo_status):
    conn = connect_db(); cursor = conn.cursor()
    try:
        cursor.execute("UPDATE registros SET CertificadoOK = ? WHERE id = ?", (novo_status, id))
        conn.commit()
    except Exception as e:
        print(f"Erro em update_certificado para ID {id}: {e}"); conn.rollback()
    finally:
        conn.close()
        
def update_nf(registro_id, status_nf):
    """Atualiza o status da Nota Fiscal (NF) no banco de dados."""
    import sqlite3
    try:
        # ATENÇÃO: Confirme se o nome do seu banco e da tabela ('Registros') são esses mesmos.
        # Você pode olhar a função "update_certificado" aí perto para copiar o formato exato.
        conn = sqlite3.connect("residuos_db.sqlite") 
        cursor = conn.cursor()
        cursor.execute("UPDATE Registros SET NFOk = ? WHERE ID = ?", (status_nf, registro_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Erro ao atualizar NF: {e}")
        return False

# --- CRUD Apoio ---
def get_banco_residuos():
    conn = connect_db()
    df_cols = ['Residuo', 'NomeNF', 'CodigoItem', 'CodigoIBAMA', 'ModoPadrao', 'ValorPorKgPadrao', 'ValorFechadoPadrao', 'PesoUnitarioKgPadrao', 'CalculaRateio', 'EstadoPadrao', 'DestinacaoPadrao', 'TipoPadrao', 'ParceiroPadrao', 'Grupo', 'ExigeNF', 'ExigeCertificado']
    df = pd.DataFrame(columns=df_cols)
    try:
        df = pd.read_sql_query("SELECT " + ", ".join(df_cols) + " FROM residuos ORDER BY Residuo", conn)
    except Exception as e: print(f"Erro em get_banco_residuos: {e}")
    finally: conn.close()
    return df

def add_residuo(nome, nome_nf, codigo_item, codigo_ibama, modo, val_kg, val_fec, peso_unit_kg, calcula_rateio, estado, dest, tipo, parc, grupo, exige_nf, exige_cert): 
    conn=connect_db(); cursor=conn.cursor(); success=False
    try:
        cursor.execute("""
            INSERT INTO residuos (Residuo, NomeNF, CodigoItem, CodigoIBAMA, ModoPadrao, ValorPorKgPadrao, ValorFechadoPadrao, PesoUnitarioKgPadrao, CalculaRateio, EstadoPadrao, DestinacaoPadrao, TipoPadrao, ParceiroPadrao, Grupo, ExigeNF, ExigeCertificado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (nome, nome_nf, codigo_item, codigo_ibama, modo, val_kg, val_fec, peso_unit_kg, int(calcula_rateio), estado, dest, tipo, parc, grupo, int(exige_nf), int(exige_cert)))
        conn.commit(); success=True
    except sqlite3.IntegrityError: print(f"Resíduo '{nome}' já existe.")
    except Exception as e: print(f"Erro em add_residuo: {e}"); conn.rollback()
    finally: conn.close(); return success

def update_residuo(nome_antigo, nome_novo, nome_nf, codigo_item, codigo_ibama, modo, val_kg, val_fec, peso_unit_kg, calcula_rateio, estado, dest, tipo, parc, grupo, exige_nf, exige_cert): 
    conn=connect_db(); cursor=conn.cursor(); success=False
    try:
        cursor.execute("""
            UPDATE residuos SET
            Residuo = ?, NomeNF = ?, CodigoItem = ?, CodigoIBAMA = ?, ModoPadrao = ?,
            ValorPorKgPadrao = ?, ValorFechadoPadrao = ?, PesoUnitarioKgPadrao = ?, 
            CalculaRateio = ?, EstadoPadrao = ?, DestinacaoPadrao = ?, TipoPadrao = ?, ParceiroPadrao = ?, Grupo = ?, ExigeNF = ?, ExigeCertificado = ?
            WHERE Residuo = ?
            """, (nome_novo, nome_nf, codigo_item, codigo_ibama, modo, val_kg, val_fec, peso_unit_kg, int(calcula_rateio), estado, dest, tipo, parc, grupo, int(exige_nf), int(exige_cert), nome_antigo))
        conn.commit(); success=True
    except sqlite3.IntegrityError: conn.rollback(); print(f"Erro: Resíduo '{nome_novo}' já existe.")
    except Exception as e: print(f"Erro em update_residuo: {e}"); conn.rollback()
    finally: conn.close(); return success

def delete_registro(id):
    conn = connect_db(); cursor = conn.cursor(); success = False
    try:
        cursor.execute("DELETE FROM registros WHERE id = ?", (id,))
        conn.commit()
        success = True
    except Exception as e:
        print(f"Erro em delete_registro para ID {id}: {e}"); conn.rollback()
    finally:
        conn.close()
    return success

# --- CRUD Parceiros e Análises ---
def get_banco_parceiros():
    conn = connect_db()
    df = pd.DataFrame(columns=['Parceiro', 'TipoParceiro', 'CNPJ']) 
    try:
        df = pd.read_sql_query("SELECT Parceiro, TipoParceiro, CNPJ FROM parceiros ORDER BY Parceiro", conn)
    except Exception as e:
        print(f"AVISO em get_banco_parceiros (tentativa 1): {e}")
        print(" -> Tentando query de fallback (somente Parceiro)...")
        try:
            df_old = pd.read_sql_query("SELECT Parceiro FROM parceiros ORDER BY Parceiro", conn)
            df_old['TipoParceiro'] = 'Destinador' 
            df_old['CNPJ'] = ''
            df = df_old 
        except Exception as e_fallback:
            print(f"ERRO CRÍTICO em get_banco_parceiros (fallback): {e_fallback}")
    finally:
        conn.close()

    if 'Parceiro' not in df.columns: df['Parceiro'] = pd.NA
    if 'TipoParceiro' not in df.columns: df['TipoParceiro'] = 'Destinador'
    if 'CNPJ' not in df.columns: df['CNPJ'] = ''
    return df

def add_parceiro(nome, tipo, cnpj):
    conn=connect_db(); cursor=conn.cursor(); success=False
    try: 
        cursor.execute("INSERT INTO parceiros (Parceiro, TipoParceiro, CNPJ) VALUES (?, ?, ?)", (nome, tipo, cnpj))
        conn.commit(); success=True
    except sqlite3.IntegrityError: 
        print(f"Parceiro '{nome}' já existe."); conn.rollback()
    except Exception as e: 
        print(f"Erro em add_parceiro: {e}"); conn.rollback()
    finally: 
        conn.close()
    return success

def update_parceiro(nome_antigo, nome_novo, tipo_novo, cnpj_novo):
    conn=connect_db(); cursor=conn.cursor(); success=False
    try: 
        cursor.execute("UPDATE parceiros SET Parceiro = ?, TipoParceiro = ?, CNPJ = ? WHERE Parceiro = ?", (nome_novo, tipo_novo, cnpj_novo, nome_antigo))
        conn.commit(); success=True
    except sqlite3.IntegrityError: print(f"Erro: Parceiro '{nome_novo}' já existe."); conn.rollback()
    except Exception as e: print(f"Erro em update_parceiro: {e}"); conn.rollback()
    finally: conn.close(); return success

def delete_parceiro(nome):
    conn=connect_db(); cursor=conn.cursor(); success=False
    try: cursor.execute("DELETE FROM parceiros WHERE Parceiro = ?", (nome,)); conn.commit(); success=True
    except Exception as e: print(f"Erro em delete_parceiro: {e}"); conn.rollback()
    finally: conn.close(); return success

def get_banco_analises():
    conn = connect_db()
    df = pd.DataFrame(columns=['NomeAnalise', 'ValorPadrao'])
    try: df = pd.read_sql_query("SELECT NomeAnalise, ValorPadrao FROM analises ORDER BY NomeAnalise", conn)
    except Exception as e: print(f"Erro em get_banco_analises: {e}")
    finally: conn.close()
    return df

def add_analise(nome, valor_padrao):
    conn=connect_db(); cursor=conn.cursor(); success=False
    try:
        cursor.execute("INSERT INTO analises (NomeAnalise, ValorPadrao) VALUES (?, ?)", (nome, valor_padrao))
        conn.commit(); success=True
    except sqlite3.IntegrityError: print(f"Análise '{nome}' já existe.") 
    except Exception as e: print(f"Erro em add_analise: {e}"); conn.rollback()
    finally: conn.close()
    return success

def update_analise(nome_antigo, nome_novo, valor_padrao):
    conn=connect_db(); cursor=conn.cursor(); success=False
    try:
        cursor.execute("UPDATE analises SET NomeAnalise = ?, ValorPadrao = ? WHERE NomeAnalise = ?", (nome_novo, valor_padrao, nome_antigo))
        conn.commit(); success=True
    except sqlite3.IntegrityError:
        conn.rollback(); print(f"Erro: Análise '{nome_novo}' já existe ou outra violação.")
    except Exception as e: print(f"Erro em update_analise: {e}"); conn.rollback()
    finally: conn.close()
    return success

def delete_analise(nome):
    conn=connect_db(); cursor=conn.cursor(); success=False
    try: cursor.execute("DELETE FROM analises WHERE NomeAnalise = ?", (nome,)); conn.commit(); success=True
    except Exception as e: print(f"Erro em delete_analise: {e}"); conn.rollback()
    finally: conn.close(); return success

def add_or_update_metragem(mes_ano, metragem):
    conn = connect_db() 
    if conn is None: return False
    try:
        sql = '''
            INSERT INTO indicador_metragem (mes_ano, metragem)
            VALUES (?, ?)
            ON CONFLICT(mes_ano) DO UPDATE SET metragem = excluded.metragem
        '''
        c = conn.cursor()
        c.execute(sql, (mes_ano, float(metragem)))
        conn.commit(); return True
    except Exception as e: print(f"Erro em add_or_update_metragem: {e}"); return False
    finally: conn.close()

def get_metragem(mes_ano):
    conn = connect_db() 
    if conn is None: return 0.0
    try:
        sql = "SELECT metragem FROM indicador_metragem WHERE mes_ano = ?"
        c = conn.cursor()
        c.execute(sql, (mes_ano,))
        result = c.fetchone()
        if result: return float(result[0])
        else: return 0.0
    except Exception as e: print(f"Erro em get_metragem: {e}"); return 0.0
    finally: conn.close()

# --- Função Pendências ---
def get_pending_certificates(days_threshold=30):
    conn = connect_db()
    df_cols = ['Data', 'Parceiro', 'Residuo', 'NumMTR', 'CertificadoOK']
    df = pd.DataFrame(columns=df_cols)
    df.index.name = 'id' 

    try:
        limit_date = (date.today() - timedelta(days=days_threshold)).strftime('%Y-%m-%d')
        query = f"""
            SELECT id, Data, Parceiro, Residuo, NumMTR, CertificadoOK
            FROM registros
            WHERE COALESCE(CertificadoOK, '') != 'Sim'
             AND date(Data) <= date('{limit_date}')
            ORDER BY date(Data) ASC
        """
        df_temp = pd.read_sql_query(query, conn, index_col='id')

        if not df_temp.empty:
            df_temp['Data'] = pd.to_datetime(df_temp['Data'], errors='coerce')
            df = df_temp 
    except Exception as e: print(f"Erro em get_pending_certificates: {e}")
    finally:
        if conn: conn.close()
    return df

def update_compliance_historico(residuo, exige_nf, exige_cert):
    conn = connect_db(); cursor = conn.cursor()
    try:
        if not exige_nf: 
            cursor.execute("UPDATE registros SET NFOk = 'N/A' WHERE Residuo = ?", (residuo,))
        else: 
            cursor.execute("UPDATE registros SET NFOk = 'Não' WHERE Residuo = ? AND NFOk = 'N/A'", (residuo,))

        if not exige_cert:
            cursor.execute("UPDATE registros SET CertificadoOK = 'N/A' WHERE Residuo = ?", (residuo,))
        else:
            cursor.execute("UPDATE registros SET CertificadoOK = 'Não' WHERE Residuo = ? AND (CertificadoOK = 'N/A' OR CertificadoOK = '' OR CertificadoOK IS NULL)", (residuo,))
            
        conn.commit()
        return True
    except Exception as e: print(f"Erro update historico: {e}"); return False
    finally: conn.close()

# =========================================================
# MÉTODOS DE MAPEAMENTO PDF (DE-PARA)
# =========================================================

def add_pdf_mapping(pdf_text, residuo_sistema):
    conn = connect_db(); cursor = conn.cursor()
    try:
        text_clean = str(pdf_text).strip().upper()
        cursor.execute("INSERT OR REPLACE INTO pdf_mapping (pdf_text_original, residuo_sistema) VALUES (?, ?)", 
                  (text_clean, residuo_sistema))
        conn.commit(); return True
    except sqlite3.Error as e: print(f"Erro DB Mapping: {e}"); return False
    finally: conn.close()

def get_residuo_from_pdf_mapping(pdf_text):
    conn = connect_db(); cursor = conn.cursor()
    try:
        text_clean = str(pdf_text).strip().upper()
        cursor.execute("SELECT residuo_sistema FROM pdf_mapping WHERE pdf_text_original = ?", (text_clean,))
        row = cursor.fetchone()
        if row: return row[0]
        return None
    finally: conn.close()

def get_all_mappings():
    conn = connect_db()
    try: return pd.read_sql_query("SELECT id, pdf_text_original, residuo_sistema FROM pdf_mapping ORDER BY pdf_text_original", conn)
    except Exception: return pd.DataFrame()
    finally: conn.close()

def delete_pdf_mapping(mapping_id):
    conn = connect_db(); cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM pdf_mapping WHERE id = ?", (mapping_id,))
        conn.commit(); return True
    except sqlite3.Error: return False
    finally: conn.close()

def get_all_metragens():
    conn = connect_db() 
    if conn is None: return []
    try:
        c = conn.cursor()
        c.execute("SELECT mes_ano, metragem FROM indicador_metragem ORDER BY mes_ano DESC")
        return c.fetchall()
    finally: conn.close()

def delete_metragem(mes_ano):
    conn = connect_db()
    if conn is None: return False
    try:
        c = conn.cursor()
        c.execute("DELETE FROM indicador_metragem WHERE mes_ano = ?", (mes_ano,))
        conn.commit(); return True
    except: return False
    finally: conn.close()

# --- Gestão de Feriados e Dias Não Úteis ---

def criar_tabela_feriados():
    """Cria a tabela para guardar as datas manuais, caso não exista."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dias_nao_uteis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_bloqueada TEXT UNIQUE,
                descricao TEXT
            )
        ''')
        conn.commit()
    except Exception as e:
        logging.error(f"Erro ao criar tabela de feriados: {e}")
    finally:
        conn.close()

def get_datas_manuais():
    """Retorna uma lista simples com as datas no formato guardado (ex: 'YYYY-MM-DD')."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT data_bloqueada FROM dias_nao_uteis")
        # Retorna apenas a lista de datas para o calculos.py usar
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logging.error(f"Erro ao carregar datas manuais: {e}")
        return []
    finally:
        conn.close()

def adicionar_dia_nao_util(data, descricao):
    """Adiciona um novo dia não útil à base de dados."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO dias_nao_uteis (data_bloqueada, descricao) VALUES (?, ?)", (data, descricao))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False # A data já existe
    finally:
        conn.close()

def remover_dia_nao_util(data):
    """Remove uma data específica."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM dias_nao_uteis WHERE data_bloqueada = ?", (data,))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def renomear_residuo_em_massa(nome_antigo, nome_novo):
    """Substitui o nome de um resíduo em todas as tabelas onde ele aparece."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 1. Renomeia na tabela de registros (onde ficam os lançamentos)
        cursor.execute("UPDATE registros SET Residuo = ? WHERE Residuo = ?", (nome_novo, nome_antigo))
        
        # 2. Renomeia na tabela de definições/cadastro (a lista que aparece no Combobox)
        cursor.execute("UPDATE residuos SET Residuo = ? WHERE Residuo = ?", (nome_novo, nome_antigo))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao renomear resíduo no banco: {e}")
        return False
    finally:
        conn.close()

# --- Inicialização ---
def initialize_database():
    print("Inicializando banco de dados...")
    create_tables() 
    print("Banco de dados pronto.")

if __name__ == "__main__":
    initialize_database()
