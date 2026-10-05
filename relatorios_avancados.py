# relatorios_avancados.py
import threading
import queue
import pandas as pd
from tkinter import filedialog, END
from componentes import ModernMessageBox
import calculos

def run_esg_calculation_thread(dt_inicio, dt_fim, result_queue):
    report_text = calculos.calcular_relatorio_esg_data(dt_inicio, dt_fim)
    result_queue.put(report_text)

def check_esg_result_queue(app, esg_txt, btn_gerar_esg, set_status, result_queue):
    try:
        report_text = result_queue.get_nowait()
        esg_txt.config(state="normal")
        esg_txt.delete("1.0", END)
        esg_txt.insert(END, report_text)
        esg_txt.config(state="disabled")
        btn_gerar_esg.config(state="normal")
        set_status("Relatório ESG concluído.")
    except queue.Empty:
        app.after(100, lambda: check_esg_result_queue(app, esg_txt, btn_gerar_esg, set_status, result_queue))
    except Exception as e:
        ModernMessageBox.showerror("Erro UI", f"Erro ao exibir resultado ESG: {e}", parent=app)
        btn_gerar_esg.config(state="normal")
        set_status("Erro ao exibir relatório.")

def start_esg_calculation(app, dt_inicio, dt_fim, esg_txt, btn_gerar_esg, set_status, result_queue):
    if dt_inicio > dt_fim: 
        ModernMessageBox.showwarning("Filtro Inválido", "Data início > Data fim.", parent=app)
        return

    esg_txt.config(state="normal")
    esg_txt.delete("1.0", END)
    esg_txt.insert(END, "Calculando relatório...\n\nIsso pode levar alguns instantes dependendo do período selecionado.")
    esg_txt.config(state="disabled")
    btn_gerar_esg.config(state="disabled")
    set_status("Calculando Relatório ESG...")
    app.update_idletasks()

    while not result_queue.empty():
        try: result_queue.get_nowait()
        except queue.Empty: break
        
    calc_thread = threading.Thread(
        target=run_esg_calculation_thread, 
        args=(dt_inicio, dt_fim, result_queue),
        daemon=True
    )
    calc_thread.start()
    app.after(100, lambda: check_esg_result_queue(app, esg_txt, btn_gerar_esg, set_status, result_queue))


def run_geracao_calculation_thread(dt_inicio, dt_fim, residuo_selecionado, df_global, result_queue):
    resultado_dict = calculos.calcular_relatorio_geracao_data(dt_inicio, dt_fim, residuo_selecionado, df_global)
    result_queue.put(resultado_dict)

def check_geracao_result_queue(app, ger_tbl, ger_kpi_total_var, ger_kpi_media_var, btn_gerar_geracao, set_status, result_queue):
    try:
        result_data = result_queue.get_nowait()
        
        for r in ger_tbl.get_children(): ger_tbl.delete(r)

        if "memoria" in result_data:
            txt_memoria_geracao.delete("1.0", tk.END)
            txt_memoria_geracao.insert(tk.END, result_data["memoria"])

        if "erro" in result_data:
            ModernMessageBox.showwarning("Aviso", result_data["erro"], parent=app)
            ger_kpi_total_var.set("0 kg")
            ger_kpi_media_var.set("0,00 kg/dia")
        else:
            ger_kpi_total_var.set(f"{result_data['total_geral']:,}".replace(",", ".") + " kg")
            media_formatada = f"{result_data['media_diaria']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            ger_kpi_media_var.set(f"{media_formatada} kg/dia")

            for row_num, linha in enumerate(result_data["linhas"]):
                real_str = f"{linha['Realizado']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if linha['Realizado'] > 0 else "-"
                prev_str = f"{linha['Previsao']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if linha['Previsao'] > 0 else "-"
                tot_str = f"{linha['Total']:,}".replace(",", ".")
                tag = "evenrow" if row_num % 2 == 0 else "oddrow"
                ger_tbl.insert("", "end", values=(linha['Mes'].capitalize(), real_str, prev_str, tot_str), tags=(tag,))
        
        btn_gerar_geracao.config(state="normal")
        set_status("Relatório de geração concluído.")
        
    except queue.Empty:
        app.after(100, lambda: check_geracao_result_queue(app, ger_tbl, ger_kpi_total_var, ger_kpi_media_var, btn_gerar_geracao, set_status, result_queue))
    except Exception as e:
        ModernMessageBox.showerror("Erro UI", f"Erro ao exibir resultado da Geração: {e}", parent=app)
        btn_gerar_geracao.config(state="normal")
        set_status("Erro ao exibir relatório.")

def start_geracao_calculation(app, dt_inicio, dt_fim, selecao, df_banco, df_registros_global, ger_tbl, ger_kpi_total_var, ger_kpi_media_var, btn_gerar_geracao, set_status, result_queue):
    if dt_inicio > dt_fim: 
        ModernMessageBox.showwarning("Erro", "Data início > fim.", parent=app)
        return
    if not selecao:
        ModernMessageBox.showwarning("Aviso", "Selecione um Item.", parent=app)
        return

    for r in ger_tbl.get_children(): ger_tbl.delete(r)
    ger_kpi_total_var.set("Calculando...")
    ger_kpi_media_var.set("Calculando...")
    btn_gerar_geracao.config(state="disabled")
    app.update_idletasks()

    while not result_queue.empty():
        try: result_queue.get_nowait()
        except queue.Empty: break
        
    df_copy = df_registros_global.copy()
    
    # --- LÓGICA DIRETA (SEM GRUPOS DO BANCO) ---
    if selecao in ["Plástico", "Plásticos"]:
        residuos_alvo = ["Plástico", "Mylar"]
    else:
        residuos_alvo = [selecao]
    # -------------------------------------------
    
    calc_thread = threading.Thread(
        target=run_geracao_calculation_thread, 
        args=(dt_inicio, dt_fim, residuos_alvo, df_copy, result_queue), 
        daemon=True 
    )
    calc_thread.start()
    app.after(100, lambda: check_geracao_result_queue(app, ger_tbl, ger_kpi_total_var, ger_kpi_media_var, btn_gerar_geracao, set_status, result_queue))
    
def exportar_para_sinir(app, dt_inicio, dt_fim, df_registros):
    try:
        df_sinir = calculos.gerar_relatorio_sinir(df_registros, dt_inicio, dt_fim)
        
        if df_sinir.empty:
            ModernMessageBox.showinfo("SINIR", f"Nenhum dado encontrado no período de {dt_inicio:%d/%m/%Y} a {dt_fim:%d/%m/%Y}.", parent=app)
            return

        default_filename = f"DMR_SINIR_{dt_inicio:%m-%Y}_a_{dt_fim:%m-%Y}.xlsx"
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", 
            filetypes=[("Arquivo Excel", "*.xlsx")], 
            initialfile=default_filename, 
            title="Salvar Relatório SINIR"
        )
        if not path: return

        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            df_sinir.to_excel(writer, sheet_name="DMR_SINIR", index=False)
            ws = writer.sheets['DMR_SINIR']
            for col in ws.columns:
                col_name = col[0].value
                length = max((len(str(cell.value)) for cell in col), default=15)
                ws.column_dimensions[col[0].column_letter].width = min(length + 2, 50)
                
        ModernMessageBox.showinfo("Sucesso", "Relatório SINIR exportado com sucesso!\nCopie os dados da planilha para o portal do órgão ambiental.", parent=app)
    except Exception as e:
        ModernMessageBox.showerror("Erro", f"Falha ao salvar arquivo: {e}", parent=app)
