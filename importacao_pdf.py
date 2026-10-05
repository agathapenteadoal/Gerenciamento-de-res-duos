# importacao_pdf.py
import os
import re
import pdfplumber
import unicodedata
from datetime import datetime
import database as db
from componentes import ModernMessageBox

def normalizar(texto):
    """Remove acentos e caracteres especiais para comparação."""
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^A-Za-z0-9]', '', texto).upper()

def processar_pdf_romaneio(pdf_path, parceiro_ui, data_db_fmt_ui, tipo_ui, destinacao_ui, mapa_produtos, banco_dict):
    """Processa PDFs no formato de Boletim de Medição/Romaneio."""
    registros = []
    erros_map = []
    print(f"\n--- ANALISANDO ARQUIVO (Romaneio): {os.path.basename(pdf_path)} ---")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                todas_tabelas = page.extract_tables()
                if not todas_tabelas: continue
                
                for tabela in todas_tabelas:
                    for row in tabela:
                        row_clean = []
                        for c in row:
                            if c:
                                txt = str(c).replace(u'\xa0', ' ').replace('\n', ' ').strip()
                                txt = re.sub(r'\s+', ' ', txt)
                                row_clean.append(txt)
                            else:
                                row_clean.append("")

                        if not any(row_clean) or len(row_clean) < 3: continue
                            
                        idx_qtd = -1
                        str_qtd = ""
                        for col_idx, celula in enumerate(row_clean):
                            if "kg" in celula.lower() and any(c.isdigit() for c in celula):
                                idx_qtd = col_idx
                                str_qtd = celula
                                break 
                        
                        if idx_qtd == -1: continue

                        desc_candidata = ""
                        for k in range(idx_qtd): 
                            texto = row_clean[k]
                            is_data = re.search(r'\d{2}/\d{2}/\d{4}', texto)
                            is_ticket = "Ticket" in texto or "OTR" in texto
                            is_num_curto = texto.replace(" ", "").replace(".", "").replace("-","").isdigit() and len(texto) < 5
                            
                            if len(texto) > 3 and not is_data and not is_ticket and not is_num_curto:
                                if len(texto) > len(desc_candidata): desc_candidata = texto
                        
                        raw_desc = desc_candidata
                        raw_desc = re.sub(r'^\d+[\s-]*', '', raw_desc) 
                        prefixes = ["CIRCUIBRAS -", "CIRCUIBRAS", "SETE -", "CLIENTE -", "SETE AMBIENTAL"]
                        upper_d = raw_desc.upper()
                        for p in prefixes:
                            if upper_d.startswith(p):
                                raw_desc = raw_desc[len(p):].strip()
                                upper_d = raw_desc.upper()

                        if not raw_desc or "DESCRIÇÃO" in raw_desc.upper() or "ITEM" == raw_desc.upper() or "TOTAL" in raw_desc.upper():
                            continue

                        try:
                            peso_float = float(str_qtd.lower().replace("kg", "").replace(".", "").replace(",", ".").strip())
                            cols_a_direita = row_clean[idx_qtd+1:]
                            numeros_encontrados = []
                            
                            for celula in cols_a_direita:
                                s_limpa = celula.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".").strip()
                                if any(c.isdigit() for c in s_limpa):
                                    try: numeros_encontrados.append(float(s_limpa))
                                    except: pass
                            
                            val_unit_float = 0.0
                            val_total_float = 0.0
                            
                            if len(numeros_encontrados) >= 2:
                                val_unit_float = numeros_encontrados[0]
                                val_total_float = numeros_encontrados[-1] 
                            elif len(numeros_encontrados) == 1:
                                val_unit_float = numeros_encontrados[0]
                                val_total_float = (val_unit_float * peso_float) if peso_float > 0 else val_unit_float
                            else:
                                continue 

                            val_total_float = round(val_total_float, 2)
                            
                            data_item = data_db_fmt_ui
                            for cel in row_clean:
                                match_data = re.search(r"(\d{2}/\d{2}/\d{4})", cel)
                                if match_data:
                                    try: data_item = datetime.strptime(match_data.group(1), "%d/%m/%Y").strftime("%Y-%m-%d"); break
                                    except: pass

                            nome_norm = normalizar(raw_desc)
                            nome_app = None
                            nome_db = db.get_residuo_from_pdf_mapping(nome_norm)
                            if not nome_db: nome_db = db.get_residuo_from_pdf_mapping(raw_desc)
                            
                            if nome_db: nome_app = nome_db
                            elif nome_app is None:
                                for nome_b, data_b in banco_dict.items():
                                    padrao = data_b.get('nome_pdf_padrao', '')
                                    if padrao and normalizar(padrao) in nome_norm:
                                        nome_app = nome_b; break
                                if not nome_app and nome_norm in mapa_produtos:
                                    nome_app = mapa_produtos[nome_norm]

                            if nome_app:
                                registros.append({
                                    'Data': data_item, 'Parceiro': parceiro_ui, 'Tipo': tipo_ui,
                                    'Destinacao': destinacao_ui, 'Residuo': nome_app,
                                    'Peso': peso_float, 'ValorPorKg': val_unit_float, 
                                    'ValorTotal': val_total_float, 'ProdutoPDF': raw_desc, 'Modo': 'kg'
                                })
                            else:
                                erros_map.append(raw_desc)

                        except Exception as e_row:
                            pass
    except Exception as e: print(f"ERRO FATAL: {e}")
    return registros, erros_map

def processar_pdf_ticket(pdf_path, parceiro_ui, data_db_fmt_ui, tipo_ui, destinacao_ui, mapa_produtos, banco_dict):
    """Processa PDFs no formato de Ticket padrão."""
    registros = []
    erros_map = []
    print(f"\n--- ANALISANDO ARQUIVO (Ticket): {os.path.basename(pdf_path)} ---")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text: full_text += page_text + "\n"

        if not full_text: return [], []

        linhas_validas = []

        for line in full_text.split('\n'):
            line = line.strip()
            
            # 1. Encontra onde começa o código do produto (Pula datas soltas no início)
            match_inicio = re.search(r"(\d{3,}\s*-\s*[A-Za-z]\s*-.*)", line)
            if not match_inicio:
                continue
                
            linha_limpa = match_inicio.group(1)
            tokens = linha_limpa.split()

            # 2. Remove qualquer lixo não numérico do final da linha (ex: PENDENTE, -, OK)
            while tokens:
                last_token = tokens[-1].upper()
                if last_token in ['KG', 'KGS', 'KGM', 'UN', 'TN', 'LT', 'M3', '-', '*', '|', '_']:
                    tokens.pop()
                    continue
                    
                teste_num = last_token.replace('R$', '').replace('$', '').replace('.', '').replace(',', '').replace('-', '').strip()
                if teste_num.isdigit():
                    break # Achou o último valor financeiro
                else:
                    tokens.pop() # Lixo, remove

            if not tokens:
                continue
            
            # 3. Lemos os pedaços de trás para frente com separação blindada
            numeros = []
            nome_tokens = []
            pegando_numeros = True
            
            for token in reversed(tokens):
                if pegando_numeros:
                    token_upper = token.upper()
                    
                    if token_upper in ['KG', 'KGS', 'KGM', 'UN', 'TN', 'LT', 'M3', '-', '*', '|', '_']:
                        continue
                        
                    # Verifica se o bloco é numérico (preservando parênteses como "FRESA (B)")
                    teste_num = token_upper.replace('R$', '').replace('$', '').replace('.', '').replace(',', '').replace('-', '').strip()
                    
                    if teste_num.isdigit():
                        token_limpo = token_upper.replace('R$', '').replace('$', '').strip()
                        numeros.insert(0, token_limpo)
                    else:
                        pegando_numeros = False
                        nome_tokens.insert(0, token)
                else:
                    nome_tokens.insert(0, token)

            # Se não encontrar pelo menos Peso e Total, ignora
            if len(numeros) < 2:
                continue

            nome_bruto = " ".join(nome_tokens)

            try:
                # 4. Limpa o nome para procurar no banco de dados
                nome_pdf_norm = normalizar(re.sub(r"^\d{3,}\s*-\s*[A-Za-z]\s*-\s*", "", nome_bruto).strip())

                # 5. Mapeia os valores extraídos
                valor_tot = float(numeros[-1].replace('.', '').replace(',', '.'))
                
                if len(numeros) >= 3:
                    preco_un = float(numeros[-2].replace('.', '').replace(',', '.'))
                    peso_liq = float(numeros[-3].replace('.', '').replace(',', '.'))
                else:
                    peso_liq = float(numeros[-2].replace('.', '').replace(',', '.'))
                    preco_un = valor_tot / peso_liq if peso_liq > 0 else 0.0

                # 6. Procura no banco de dados (de/para)
                nome_app = None
                if nome_pdf_norm in mapa_produtos:
                    nome_app = mapa_produtos[nome_pdf_norm]
                
                if not nome_app:
                    for n_banco, d_banco in banco_dict.items():
                        if normalizar(d_banco.get('nome_pdf_padrao', '')) == nome_pdf_norm:
                            nome_app = n_banco; break
                            
                if not nome_app:
                    for n_banco in banco_dict.keys():
                        if normalizar(n_banco) == nome_pdf_norm:
                            nome_app = n_banco; break

                # 7. Salva no sistema se encontrou, registra o erro se não encontrou
                if nome_app:
                    linhas_validas.append({
                        'Data': data_db_fmt_ui, 'Parceiro': parceiro_ui, 'Tipo': tipo_ui,
                        'Destinacao': destinacao_ui, 'Residuo': nome_app, 'Peso': peso_liq,
                        'ValorPorKg': preco_un, 'ValorTotal': valor_tot, 'ProdutoPDF': nome_bruto
                    })
                else:
                    erros_map.append(nome_bruto)
                    
            except Exception as e_map:
                 pass
                 
        registros = linhas_validas

    except Exception as e:
        print(f" -> ERRO GERAL PDF: {e}")
    return registros, erros_map

def iniciar_importacao(app, file_paths, parceiro, data_db_fmt, tipo, destinacao, mapa_produtos, banco_dict, callback_status, callback_atualizar):
    """Função mestre que orquestra a leitura de todos os arquivos e salva no banco de dados."""
    sucesso_total = 0
    erros_total = 0
    pdfs_processados = 0
    todos_erros_map = [] # Lista global de erros de mapeamento

    callback_status(f"Importando {len(file_paths)} arquivo(s)...")

    for pdf_path in file_paths:
        try:
            is_romaneio = False
            try:
                with pdfplumber.open(pdf_path) as temp_pdf:
                    first_page = temp_pdf.pages[0].extract_text() or ""
                    if "Boletim de Medição" in first_page or ("Item" in first_page and "Ticket" in first_page and "Quantidade" in first_page):
                        is_romaneio = True
            except: pass

            if is_romaneio:
                registros, erros_map = processar_pdf_romaneio(pdf_path, parceiro, data_db_fmt, tipo, destinacao, mapa_produtos, banco_dict)
            else:
                registros, erros_map = processar_pdf_ticket(pdf_path, parceiro, data_db_fmt, tipo, destinacao, mapa_produtos, banco_dict)

            todos_erros_map.extend(erros_map)

            if not registros:
                erros_total += 1; continue

            erros_pdf = 0
            for reg in registros:
                try:
                    # Lista de 18 campos para o Banco de Dados
                    novo_reg = [
                        reg['Data'], reg['Parceiro'], reg['Residuo'], reg.get('Estado', "Sólido"),
                        reg['Destinacao'], reg['Tipo'], reg.get('Modo', "kg"), reg['Peso'],
                        reg.get('ValorPorKg', 0.0), 0.0, 0.0, reg['ValorTotal'], "", "", "Não",
                        reg['Peso'], "Não", ""
                    ]
                    if db.add_registro(novo_reg): sucesso_total += 1
                    else: erros_pdf += 1
                except: erros_pdf += 1

            if erros_pdf > 0: erros_total += 1
            pdfs_processados += 1

        except Exception:
            erros_total += 1

    # Finalização e Feedbacks Interativos
    callback_status("")
    if pdfs_processados > 0:
        callback_atualizar()
        msg = f"Processamento concluído. {sucesso_total} itens importados."
        
        if todos_erros_map:
            msg += "\n\nAVISO: Os seguintes resíduos NÃO foram encontrados no sistema e foram ignorados:\n"
            msg += "\n".join(list(set(todos_erros_map))[:7])
            if len(set(todos_erros_map)) > 7:
                msg += "\n... (e outros)"
            ModernMessageBox.showwarning("Importação Concluída com Avisos", msg, parent=app)
        elif erros_total > 0: 
            msg += "\nAlguns erros de formato ocorreram."
            ModernMessageBox.showinfo("Importação", msg, parent=app)
        else:
            ModernMessageBox.showinfo("Sucesso", msg, parent=app)
    else:
        # Se nenhum arquivo foi processado devido a falha de mapeamento de Nomes
        if todos_erros_map:
            msg = "Nenhum registro pôde ser importado porque os resíduos abaixo NÃO existem no seu sistema:\n\n"
            msg += "\n".join(list(set(todos_erros_map))[:7])
            ModernMessageBox.showwarning("Resíduos Desconhecidos", msg, parent=app)
        else:
            ModernMessageBox.showwarning("Erro", "Nenhum arquivo pôde ser processado (Formato inválido).", parent=app)
